"""Versioned build-route and assembly orchestration over existing CAD facts."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from zhangwen.auth.context import current_owner_subject
from zhangwen.cad_agent.profile_repository import MechanicalProfileRepository
from zhangwen.domains.classroom.models import BuildRoute, StructurePolicy
from zhangwen.domains.classroom.repository import ClassroomRepository
from zhangwen.domains.events.store import RealtimeEventStore
from zhangwen.domains.making.models import (
    AssemblyChecklistItem,
    AssemblyRecord,
    BuildRouteDecisionRecord,
    CadStructureCandidate,
    ChooseBuildRouteRequest,
    CreateStructureRevisionRequest,
    MakingWorkspace,
    MechanicalProfileRef,
    RecordAssemblyRequest,
    StructureRevisionRecord,
)
from zhangwen.domains.simulation.digest import canonical_digest


_LOCAL_SUBJECT = "__local__"
_BASE_ASSEMBLY_CHECKS = {
    "wiring_matches_plan",
    "fixing_secure",
    "insulation_complete",
    "power_safe",
}
_STRUCTURE_ASSEMBLY_CHECKS = {
    "fabricated_part_matches_revision",
    "clearance_checked",
    "fasteners_checked",
}
_CAD_OUTPUT_ROLES = {"STEP_ASSEMBLY", "STL_PRINTABLE_PARTS"}


class MakingError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 422,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable


class ProjectMakingService:
    """Keeps the two making routes on one Work and one physical evidence chain."""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = Path(data_dir)
        self._classroom = ClassroomRepository(self._data_dir)
        self._db_path = self._classroom.db_path
        self._actor = current_owner_subject() or _LOCAL_SUBJECT
        self._events = RealtimeEventStore(self._db_path)
        MechanicalProfileRepository(self._db_path).seed_builtin_profiles()

    def get_workspace(self, work_id: str) -> MakingWorkspace:
        self._classroom.assert_work_access(work_id)
        with self._connect() as conn:
            context = self._context(conn, work_id)
            decision_rows = conn.execute(
                "SELECT * FROM project_build_route_decisions WHERE work_id = ? "
                "ORDER BY version DESC, created_at DESC, id DESC",
                (work_id,),
            ).fetchall()
            structure_rows = conn.execute(
                "SELECT * FROM project_structure_revisions WHERE work_id = ? "
                "ORDER BY version DESC, created_at DESC, id DESC",
                (work_id,),
            ).fetchall()
            assembly_rows = conn.execute(
                "SELECT * FROM project_assembly_records WHERE work_id = ? "
                "ORDER BY version DESC, created_at DESC, id DESC",
                (work_id,),
            ).fetchall()
            cad_rows = conn.execute(
                """
                SELECT c.id, c.intent_summary, c.artifact_id, c.artifact_version_id,
                       c.confirmed_at,
                       COALESCE(GROUP_CONCAT(f.role), '') AS output_roles
                FROM cad_intent_revisions AS c
                LEFT JOIN artifact_files AS f
                  ON f.project_id = c.project_id
                 AND f.artifact_id = c.artifact_id
                 AND f.artifact_version_id = c.artifact_version_id
                WHERE c.project_id = ? AND c.status = 'CONFIRMED'
                  AND c.artifact_id IS NOT NULL
                  AND c.artifact_version_id IS NOT NULL
                GROUP BY c.id
                ORDER BY c.confirmed_at DESC, c.created_at DESC, c.id DESC
                """,
                (work_id,),
            ).fetchall()
            profile_rows = conn.execute(
                """
                SELECT id, profile_id, revision, display_name, evidence_level,
                       content_sha256
                FROM mechanical_profile_versions
                ORDER BY display_name, profile_id, revision
                """
            ).fetchall()
            eligible_run = self._current_eligible_run(conn, work_id, required=False)
            can_edit = self._can_student_edit(conn, work_id)

        decisions = [_decision(row) for row in decision_rows]
        structures = [_structure(row) for row in structure_rows]
        assemblies = [_assembly(row) for row in assembly_rows]
        decision_id = _optional(context["current_build_route_decision_id"])
        structure_id = _optional(context["current_structure_revision_id"])
        assembly_id = _optional(context["current_assembly_record_id"])
        current_decision = next(
            (item for item in decisions if item.id == decision_id), None
        )
        current_structure = next(
            (item for item in structures if item.id == structure_id), None
        )
        current_assembly = next(
            (item for item in assemblies if item.id == assembly_id), None
        )
        cad_candidates = []
        for row in cad_rows:
            roles = sorted(
                {item for item in str(row["output_roles"] or "").split(",") if item}
            )
            cad_candidates.append(
                CadStructureCandidate(
                    id=str(row["id"]),
                    summary=str(row["intent_summary"]),
                    artifactId=str(row["artifact_id"]),
                    artifactVersionId=str(row["artifact_version_id"]),
                    outputRoles=roles,
                    ready=_CAD_OUTPUT_ROLES.issubset(roles),
                    confirmedAt=_optional(row["confirmed_at"]),
                )
            )
        profiles = [
            MechanicalProfileRef(
                id=str(row["id"]),
                profileId=str(row["profile_id"]),
                revision=str(row["revision"]),
                displayName=str(row["display_name"]),
                evidenceLevel=str(row["evidence_level"]),
                contentSha256=str(row["content_sha256"]),
            )
            for row in profile_rows
        ]
        can_choose = bool(can_edit and eligible_run is not None)
        can_structure = bool(
            can_edit
            and current_decision is not None
            and current_decision.status == "CURRENT"
            and current_decision.route is BuildRoute.WITH_STRUCTURE
        )
        can_assemble = bool(
            can_edit
            and current_decision is not None
            and current_decision.status == "CURRENT"
            and (
                current_decision.route is BuildRoute.WITHOUT_STRUCTURE
                or (
                    current_structure is not None
                    and current_structure.status == "READY"
                )
            )
        )
        deployment_ready = bool(
            current_assembly is not None
            and current_assembly.status == "CURRENT"
            and current_decision is not None
            and current_assembly.build_route_decision_id == current_decision.id
        )
        blocked_reason: str | None = None
        if eligible_run is None:
            blocked_reason = "需要先完成当前正式 MicroPython 仿真验证。"
        elif current_decision is None:
            blocked_reason = "请选择包含结构件或不做结构件。"
        elif current_decision.route is BuildRoute.WITH_STRUCTURE and not any(
            item.ready for item in cad_candidates
        ):
            blocked_reason = "需要先在同一作品中确认带 STEP/STL 产物的 CAD 修订。"
        elif not deployment_ready:
            blocked_reason = "需要由学生完成当前制作路径的装配与安全检查。"
        return MakingWorkspace(
            structurePolicy=StructurePolicy(str(context["structure_policy"])),
            processState=str(context["process_state"]),
            routeDecisions=decisions,
            currentDecision=current_decision,
            structureRevisions=structures,
            currentStructure=current_structure,
            assemblyRecords=assemblies,
            currentAssembly=current_assembly,
            cadCandidates=cad_candidates,
            mechanicalProfiles=profiles,
            canChooseRoute=can_choose,
            canRecordStructure=can_structure,
            canRecordAssembly=can_assemble,
            deploymentReady=deployment_ready,
            blockedReason=blocked_reason,
        )

    def choose_route(
        self, *, work_id: str, request: ChooseBuildRouteRequest
    ) -> BuildRouteDecisionRecord:
        self._classroom.assert_work_access(work_id, edit=True)
        request_digest = canonical_digest(
            {"route": request.route.value, "rationale": request.rationale}
        )
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._require_student_editor(conn, work_id)
            existing = conn.execute(
                "SELECT * FROM project_build_route_decisions "
                "WHERE work_id = ? AND idempotency_key = ?",
                (work_id, request.idempotency_key),
            ).fetchone()
            if existing is not None:
                if str(existing["request_digest"] or "") != request_digest:
                    raise MakingError(
                        "BUILD_ROUTE_IDEMPOTENCY_CONFLICT",
                        "同一请求键已经用于另一项制作路径决定。",
                        status_code=409,
                    )
                return _decision(existing)
            context = self._context(conn, work_id)
            run = self._current_eligible_run(conn, work_id, required=True)
            policy = StructurePolicy(str(context["structure_policy"]))
            if policy is StructurePolicy.REQUIRED and request.route is not BuildRoute.WITH_STRUCTURE:
                raise MakingError(
                    "BUILD_ROUTE_POLICY_REQUIRED", "当前课程要求制作结构件。", status_code=409
                )
            if policy is StructurePolicy.PROHIBITED and request.route is not BuildRoute.WITHOUT_STRUCTURE:
                raise MakingError(
                    "BUILD_ROUTE_POLICY_PROHIBITED",
                    "当前课程不允许制作结构件，请选择无结构件路径。",
                    status_code=409,
                )
            previous = conn.execute(
                "SELECT id FROM project_build_route_decisions "
                "WHERE work_id = ? AND status = 'CURRENT' "
                "ORDER BY version DESC LIMIT 1",
                (work_id,),
            ).fetchone()
            self._invalidate_making_downstream(
                conn,
                work_id=work_id,
                reason="制作路径已经形成新修订，需要重新完成结构、装配和实体验证。",
                now=now,
                supersede_route=True,
            )
            version = self._next_version(conn, "project_build_route_decisions", work_id)
            decision_id = _id("build-route")
            conn.execute(
                """
                INSERT INTO project_build_route_decisions (
                  id, work_id, version, route, rationale, selected_by,
                  policy_revision_id, supersedes_revision_id, created_at,
                  simulation_run_id, status, idempotency_key, request_digest,
                  invalidated_at, invalidation_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'CURRENT', ?, ?, NULL, NULL)
                """,
                (
                    decision_id,
                    work_id,
                    version,
                    request.route.value,
                    request.rationale,
                    self._actor,
                    context["policy_revision_id"],
                    str(previous["id"]) if previous is not None else None,
                    now,
                    str(run["id"]),
                    request.idempotency_key,
                    request_digest,
                ),
            )
            process_state = (
                "STRUCTURE_DESIGN"
                if request.route is BuildRoute.WITH_STRUCTURE
                else "ASSEMBLY_IN_PROGRESS"
            )
            conn.execute(
                """
                UPDATE work_learning_contexts
                SET current_build_route_decision_id = ?,
                    current_structure_revision_id = NULL,
                    current_assembly_record_id = NULL,
                    current_device_deployment_id = NULL,
                    current_submission_revision_id = NULL,
                    process_milestone = 'MAKING', process_state = ?,
                    revision = revision + 1, updated_at = ?
                WHERE work_id = ?
                """,
                (decision_id, process_state, now, work_id),
            )
            self._checkpoint(conn, work_id, decision_id, now)
            self._journal(
                conn,
                work_id,
                "DECISION",
                "选择制作路径",
                (
                    "选择包含结构件，下一步固定 CAD 与尺寸检查。"
                    if request.route is BuildRoute.WITH_STRUCTURE
                    else "选择不做结构件，仍需完成接线、固定、绝缘和供电检查。"
                ),
                "BUILD_ROUTE_DECISION",
                decision_id,
                now,
            )
            self._events.append_work_event(
                conn,
                work_id=work_id,
                event_type="making.route.selected",
                source_event_id=f"making-route:{decision_id}",
                payload={
                    "buildRouteDecisionId": decision_id,
                    "naturalStatus": "已选择当前制作路径",
                },
            )
            row = conn.execute(
                "SELECT * FROM project_build_route_decisions WHERE id = ?",
                (decision_id,),
            ).fetchone()
            assert row is not None
            return _decision(row)

    def create_structure_revision(
        self, *, work_id: str, request: CreateStructureRevisionRequest
    ) -> StructureRevisionRecord:
        self._classroom.assert_work_access(work_id, edit=True)
        request_digest = canonical_digest(request.model_dump(mode="json", by_alias=True))
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._require_student_editor(conn, work_id)
            existing = conn.execute(
                "SELECT * FROM project_structure_revisions "
                "WHERE work_id = ? AND idempotency_key = ?",
                (work_id, request.idempotency_key),
            ).fetchone()
            if existing is not None:
                if str(existing["request_digest"]) != request_digest:
                    raise MakingError(
                        "STRUCTURE_IDEMPOTENCY_CONFLICT",
                        "同一请求键已经用于另一份结构检查。",
                        status_code=409,
                    )
                return _structure(existing)
            decision = self._current_decision(
                conn, work_id, request.build_route_decision_id
            )
            if str(decision["route"]) != BuildRoute.WITH_STRUCTURE.value:
                raise MakingError(
                    "STRUCTURE_ROUTE_REQUIRED", "当前制作路径不包含结构件。", status_code=409
                )
            cad = conn.execute(
                """
                SELECT * FROM cad_intent_revisions
                WHERE id = ? AND project_id = ? AND status = 'CONFIRMED'
                  AND artifact_id IS NOT NULL AND artifact_version_id IS NOT NULL
                """,
                (request.cad_intent_revision_id, work_id),
            ).fetchone()
            if cad is None:
                raise MakingError(
                    "STRUCTURE_CAD_REVISION_NOT_READY",
                    "请选择同一作品中已确认并生成产物的 CAD 修订。",
                    status_code=409,
                )
            latest_cad = conn.execute(
                """
                SELECT id FROM cad_intent_revisions
                WHERE project_id = ? AND status = 'CONFIRMED'
                ORDER BY confirmed_at DESC, created_at DESC, id DESC LIMIT 1
                """,
                (work_id,),
            ).fetchone()
            if latest_cad is None or str(latest_cad["id"]) != request.cad_intent_revision_id:
                raise MakingError(
                    "STRUCTURE_CAD_REVISION_NOT_CURRENT",
                    "请选择当前最新确认的 CAD 修订。",
                    status_code=409,
                )
            roles = {
                str(row["role"])
                for row in conn.execute(
                    """
                    SELECT role FROM artifact_files
                    WHERE project_id = ? AND artifact_id = ? AND artifact_version_id = ?
                    """,
                    (work_id, cad["artifact_id"], cad["artifact_version_id"]),
                ).fetchall()
            }
            if not _CAD_OUTPUT_ROLES.issubset(roles):
                raise MakingError(
                    "STRUCTURE_CAD_OUTPUTS_INCOMPLETE",
                    "结构修订需要当前 CAD 的 STEP 与 STL 产物。",
                    status_code=409,
                )
            self._validate_profile_ids(
                conn, request.mechanical_profile_revision_ids
            )
            dimensions_ok = all(
                abs(item.actual_mm - item.expected_mm) <= item.tolerance_mm
                for item in request.dimensions
            )
            interference_ok = all(item.passed for item in request.interference_checks)
            status = "READY" if dimensions_ok and interference_ok else "BLOCKED"
            self._invalidate_making_downstream(
                conn,
                work_id=work_id,
                reason="结构尺寸或 CAD 修订已经变化，需要重新装配和验证实体结果。",
                now=now,
                supersede_route=False,
            )
            version = self._next_version(conn, "project_structure_revisions", work_id)
            revision_id = _id("structure-revision")
            conn.execute(
                """
                INSERT INTO project_structure_revisions (
                  id, work_id, build_route_decision_id, version,
                  cad_intent_revision_id, artifact_id, artifact_version_id,
                  requirements_json, mechanical_profile_revision_ids_json,
                  dimensions_json, interference_checks_json, material,
                  fabrication_method, manufacturing_notes, status,
                  digital_validation_only, idempotency_key, request_digest,
                  created_by, created_at, invalidated_at, invalidation_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, NULL, NULL)
                """,
                (
                    revision_id,
                    work_id,
                    request.build_route_decision_id,
                    version,
                    request.cad_intent_revision_id,
                    cad["artifact_id"],
                    cad["artifact_version_id"],
                    _dump(request.requirements),
                    _dump(request.mechanical_profile_revision_ids),
                    _dump([item.model_dump(mode="json", by_alias=True) for item in request.dimensions]),
                    _dump(
                        [
                            item.model_dump(mode="json", by_alias=True)
                            for item in request.interference_checks
                        ]
                    ),
                    request.material,
                    request.fabrication_method,
                    request.manufacturing_notes,
                    status,
                    request.idempotency_key,
                    request_digest,
                    self._actor,
                    now,
                ),
            )
            conn.execute(
                """
                UPDATE work_learning_contexts
                SET current_structure_revision_id = ?,
                    current_assembly_record_id = NULL,
                    current_device_deployment_id = NULL,
                    process_state = ?, process_milestone = 'MAKING',
                    revision = revision + 1, updated_at = ?
                WHERE work_id = ?
                """,
                (
                    revision_id,
                    "ASSEMBLY_IN_PROGRESS" if status == "READY" else "STRUCTURE_DESIGN",
                    now,
                    work_id,
                ),
            )
            self._journal(
                conn,
                work_id,
                "TEST",
                "记录结构尺寸与干涉检查",
                (
                    "数字 CAD、尺寸与干涉检查已通过；仍不代表结构件已经加工或装配。"
                    if status == "READY"
                    else "数字结构检查存在未通过项，需要修改后形成新修订。"
                ),
                "STRUCTURE_REVISION",
                revision_id,
                now,
            )
            self._events.append_work_event(
                conn,
                work_id=work_id,
                event_type="making.structure.saved",
                source_event_id=f"making-structure:{revision_id}",
                payload={
                    "structureRevisionId": revision_id,
                    "naturalStatus": (
                        "结构数字检查已通过，等待真实制作和装配"
                        if status == "READY"
                        else "结构数字检查需要修改"
                    ),
                },
            )
            row = conn.execute(
                "SELECT * FROM project_structure_revisions WHERE id = ?",
                (revision_id,),
            ).fetchone()
            assert row is not None
            return _structure(row)

    def record_assembly(
        self, *, work_id: str, request: RecordAssemblyRequest
    ) -> AssemblyRecord:
        self._classroom.assert_work_access(work_id, edit=True)
        if not request.attested_by_user:
            raise MakingError(
                "ASSEMBLY_USER_ATTESTATION_REQUIRED",
                "装配结果必须由当前学生主动确认，不能由 AI 代签。",
            )
        request_digest = canonical_digest(request.model_dump(mode="json", by_alias=True))
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._require_student_editor(conn, work_id)
            existing = conn.execute(
                "SELECT * FROM project_assembly_records "
                "WHERE work_id = ? AND idempotency_key = ?",
                (work_id, request.idempotency_key),
            ).fetchone()
            if existing is not None:
                if str(existing["request_digest"]) != request_digest:
                    raise MakingError(
                        "ASSEMBLY_IDEMPOTENCY_CONFLICT",
                        "同一请求键已经用于另一份装配记录。",
                        status_code=409,
                    )
                return _assembly(existing)
            decision = self._current_decision(
                conn, work_id, request.build_route_decision_id
            )
            route = BuildRoute(str(decision["route"]))
            structure: sqlite3.Row | None = None
            if route is BuildRoute.WITH_STRUCTURE:
                if not request.structure_revision_id:
                    raise MakingError(
                        "ASSEMBLY_STRUCTURE_REVISION_REQUIRED",
                        "包含结构件的路径必须绑定当前结构修订。",
                        status_code=409,
                    )
                structure = self._current_structure(
                    conn, work_id, request.structure_revision_id
                )
                if not request.fabrication_confirmed:
                    raise MakingError(
                        "ASSEMBLY_FABRICATION_CONFIRMATION_REQUIRED",
                        "CAD 预览不能证明结构件已加工，请在真实制作后确认。",
                        status_code=409,
                    )
            elif request.structure_revision_id is not None:
                raise MakingError(
                    "ASSEMBLY_STRUCTURE_NOT_ALLOWED",
                    "无结构件路径不能绑定 CAD 结构修订。",
                    status_code=409,
                )
            self._validate_checklist(request.checklist, with_structure=structure is not None)
            self._validate_artifact_versions(
                conn, work_id, request.evidence_artifact_version_ids
            )
            self._invalidate_making_downstream(
                conn,
                work_id=work_id,
                reason="装配记录已经形成新修订，需要重新部署并观察实体结果。",
                now=now,
                supersede_route=False,
                stale_structure=False,
            )
            version = self._next_version(conn, "project_assembly_records", work_id)
            record_id = _id("assembly-record")
            conn.execute(
                """
                INSERT INTO project_assembly_records (
                  id, work_id, build_route_decision_id, structure_revision_id,
                  version, wiring_plan, fixing_method, insulation_plan, power_plan,
                  assembly_steps_json, checklist_json, fabrication_confirmed,
                  observations_json, reflection, evidence_artifact_version_ids_json,
                  status, attested_by, attested_by_user, source, idempotency_key,
                  request_digest, created_at, invalidated_at, invalidation_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                          'CURRENT', ?, 1, 'USER_INTERFACE', ?, ?, ?, NULL, NULL)
                """,
                (
                    record_id,
                    work_id,
                    request.build_route_decision_id,
                    request.structure_revision_id,
                    version,
                    request.wiring_plan,
                    request.fixing_method,
                    request.insulation_plan,
                    request.power_plan,
                    _dump(request.assembly_steps),
                    _dump(
                        [item.model_dump(mode="json", by_alias=True) for item in request.checklist]
                    ),
                    int(request.fabrication_confirmed),
                    _dump(request.observations),
                    request.reflection,
                    _dump(request.evidence_artifact_version_ids),
                    self._actor,
                    request.idempotency_key,
                    request_digest,
                    now,
                ),
            )
            self._record_making_evidence(
                conn,
                work_id=work_id,
                record_id=record_id,
                decision_id=request.build_route_decision_id,
                structure_id=request.structure_revision_id,
                now=now,
            )
            conn.execute(
                """
                UPDATE work_learning_contexts
                SET current_assembly_record_id = ?,
                    current_device_deployment_id = NULL,
                    process_state = 'DEVICE_DEPLOYMENT_READY',
                    process_milestone = 'MAKING', revision = revision + 1,
                    updated_at = ?
                WHERE work_id = ?
                """,
                (record_id, now, work_id),
            )
            self._journal(
                conn,
                work_id,
                "TEST",
                "完成装配与安全检查",
                "当前学生已逐项确认接线、固定、绝缘和供电，可以进入受控文件部署。",
                "ASSEMBLY_RECORD",
                record_id,
                now,
            )
            self._events.append_work_event(
                conn,
                work_id=work_id,
                event_type="making.assembly.confirmed",
                source_event_id=f"making-assembly:{record_id}",
                payload={
                    "assemblyRecordId": record_id,
                    "naturalStatus": "装配与安全检查已由学生确认",
                },
            )
            row = conn.execute(
                "SELECT * FROM project_assembly_records WHERE id = ?", (record_id,)
            ).fetchone()
            assert row is not None
            return _assembly(row)

    def _invalidate_making_downstream(
        self,
        conn: sqlite3.Connection,
        *,
        work_id: str,
        reason: str,
        now: str,
        supersede_route: bool,
        stale_structure: bool = True,
    ) -> None:
        if supersede_route:
            conn.execute(
                """
                UPDATE project_build_route_decisions
                SET status = 'SUPERSEDED', invalidated_at = ?, invalidation_reason = ?
                WHERE work_id = ? AND status = 'CURRENT'
                """,
                (now, reason, work_id),
            )
        if stale_structure:
            conn.execute(
                """
                UPDATE project_structure_revisions
                SET status = 'STALE', invalidated_at = ?, invalidation_reason = ?
                WHERE work_id = ? AND status != 'STALE'
                """,
                (now, reason, work_id),
            )
        conn.execute(
            """
            UPDATE project_assembly_records
            SET status = 'STALE', invalidated_at = ?, invalidation_reason = ?
            WHERE work_id = ? AND status = 'CURRENT'
            """,
            (now, reason, work_id),
        )
        conn.execute(
            """
            UPDATE project_device_deployments
            SET status = 'STALE', invalidated_at = ?, invalidation_reason = ?,
                updated_at = ?
            WHERE work_id = ? AND status != 'STALE'
            """,
            (now, reason, now, work_id),
        )
        conn.execute(
            """
            UPDATE creator_evidence
            SET status = 'STALE', invalidated_at = ?, invalidation_reason = ?
            WHERE project_id = ? AND status = 'CURRENT'
              AND kind IN (
                'STRUCTURE_CHECK', 'DEPLOYMENT', 'PHYSICAL_BEHAVIOR',
                'USER_ACCEPTANCE', 'REPRODUCTION'
              )
            """,
            (now, reason, work_id),
        )
        conn.execute(
            """
            UPDATE project_submission_revisions SET status = 'SUPERSEDED'
            WHERE work_id = ? AND status != 'SUPERSEDED'
            """,
            (work_id,),
        )
        conn.execute(
            """
            UPDATE work_learning_contexts
            SET current_assembly_record_id = NULL,
                current_device_deployment_id = NULL,
                current_submission_revision_id = NULL,
                current_structure_revision_id = CASE
                  WHEN ? THEN NULL ELSE current_structure_revision_id END
            WHERE work_id = ?
            """,
            (int(stale_structure), work_id),
        )

    def _record_making_evidence(
        self,
        conn: sqlite3.Connection,
        *,
        work_id: str,
        record_id: str,
        decision_id: str,
        structure_id: str | None,
        now: str,
    ) -> None:
        bindings = {
            "buildRouteDecisionId": decision_id,
            "assemblyRecordId": record_id,
            "structureRevisionId": structure_id,
            "evidenceScope": "ASSEMBLY_AND_SAFETY_CHECK",
        }
        conn.execute(
            """
            INSERT INTO creator_evidence (
              id, project_id, kind, status, passed, summary, bindings_json,
              source_id, recorded_at, invalidated_at, invalidation_reason
            ) VALUES (?, ?, 'STRUCTURE_CHECK', 'CURRENT', 1, ?, ?, ?, ?, NULL, NULL)
            """,
            (
                _id("evidence"),
                work_id,
                "制作路径、装配和安全检查已由当前学生逐项确认；这不代表实物行为已经通过。",
                _dump(bindings),
                record_id,
                now,
            ),
        )

    def _current_decision(
        self, conn: sqlite3.Connection, work_id: str, decision_id: str
    ) -> sqlite3.Row:
        row = conn.execute(
            """
            SELECT d.* FROM project_build_route_decisions AS d
            JOIN work_learning_contexts AS c
              ON c.current_build_route_decision_id = d.id
            WHERE d.id = ? AND d.work_id = ? AND d.status = 'CURRENT'
              AND c.work_id = ?
            """,
            (decision_id, work_id, work_id),
        ).fetchone()
        if row is None:
            raise MakingError(
                "BUILD_ROUTE_NOT_CURRENT", "制作路径已经变化，请重新读取。", status_code=409
            )
        current_run = self._current_eligible_run(conn, work_id, required=True)
        if str(row["simulation_run_id"] or "") != str(current_run["id"]):
            raise MakingError(
                "BUILD_ROUTE_SIMULATION_STALE",
                "制作路径未绑定当前仿真结果，请重新选择。",
                status_code=409,
            )
        return row

    def _current_structure(
        self, conn: sqlite3.Connection, work_id: str, structure_id: str
    ) -> sqlite3.Row:
        row = conn.execute(
            """
            SELECT s.* FROM project_structure_revisions AS s
            JOIN work_learning_contexts AS c ON c.current_structure_revision_id = s.id
            WHERE s.id = ? AND s.work_id = ? AND s.status = 'READY'
              AND c.work_id = ?
            """,
            (structure_id, work_id, work_id),
        ).fetchone()
        if row is None:
            raise MakingError(
                "STRUCTURE_REVISION_NOT_CURRENT",
                "结构修订未通过或已经变化，请重新检查。",
                status_code=409,
            )
        return row

    def _current_eligible_run(
        self, conn: sqlite3.Connection, work_id: str, *, required: bool
    ) -> sqlite3.Row | None:
        row = conn.execute(
            """
            SELECT r.* FROM simulation_runs AS r
            JOIN work_learning_contexts AS c ON c.current_simulation_run_id = r.id
            JOIN creator_evidence AS e
              ON e.project_id = r.work_id AND e.kind = 'SIMULATION'
             AND e.status = 'CURRENT' AND e.passed = 1 AND e.source_id = r.id
            WHERE c.work_id = ? AND r.work_id = ? AND r.status = 'PASSED'
              AND r.evidence_eligible = 1
            ORDER BY e.recorded_at DESC LIMIT 1
            """,
            (work_id, work_id),
        ).fetchone()
        if row is None and required:
            raise MakingError(
                "BUILD_ROUTE_REQUIRES_VERIFIED_SIMULATION",
                "需要先完成当前正式 MicroPython 仿真验证。",
                status_code=409,
            )
        return row

    def _validate_profile_ids(
        self, conn: sqlite3.Connection, profile_revision_ids: list[str]
    ) -> None:
        if not profile_revision_ids:
            return
        placeholders = ",".join("?" for _ in profile_revision_ids)
        rows = conn.execute(
            f"SELECT id FROM mechanical_profile_versions WHERE id IN ({placeholders})",
            tuple(profile_revision_ids),
        ).fetchall()
        found = {str(row["id"]) for row in rows}
        missing = sorted(set(profile_revision_ids) - found)
        if missing:
            raise MakingError(
                "STRUCTURE_MECHANICAL_PROFILE_MISSING",
                "结构检查引用了不存在的机械档案修订。",
                status_code=409,
            )

    @staticmethod
    def _validate_checklist(
        checklist: list[AssemblyChecklistItem], *, with_structure: bool
    ) -> None:
        by_id = {item.id: item for item in checklist}
        if len(by_id) != len(checklist):
            raise MakingError("ASSEMBLY_CHECKLIST_DUPLICATE", "装配检查项不能重复。")
        required = set(_BASE_ASSEMBLY_CHECKS)
        if with_structure:
            required.update(_STRUCTURE_ASSEMBLY_CHECKS)
        missing = required - set(by_id)
        failed = {item_id for item_id in required if item_id in by_id and not by_id[item_id].passed}
        if missing or failed:
            raise MakingError(
                "ASSEMBLY_SAFETY_CHECK_INCOMPLETE",
                "接线、固定、绝缘、供电或结构装配检查尚未全部通过。",
                status_code=409,
            )

    @staticmethod
    def _validate_artifact_versions(
        conn: sqlite3.Connection, work_id: str, version_ids: list[str]
    ) -> None:
        if not version_ids:
            return
        placeholders = ",".join("?" for _ in version_ids)
        rows = conn.execute(
            f"SELECT id FROM artifact_versions WHERE project_id = ? AND id IN ({placeholders})",
            (work_id, *version_ids),
        ).fetchall()
        if {str(row["id"]) for row in rows} != set(version_ids):
            raise MakingError(
                "ASSEMBLY_ARTIFACT_NOT_OWNED",
                "装配附件必须来自当前作品。",
                status_code=409,
            )

    def _context(self, conn: sqlite3.Connection, work_id: str) -> sqlite3.Row:
        row = conn.execute(
            """
            SELECT c.*, a.policy_revision_id, p.structure_policy
            FROM work_learning_contexts AS c
            JOIN assignments AS a ON a.id = c.assignment_id
            JOIN assignment_policy_revisions AS p ON p.id = a.policy_revision_id
            WHERE c.work_id = ?
            """,
            (work_id,),
        ).fetchone()
        if row is None:
            raise MakingError("MAKING_WORK_NOT_FOUND", "课堂项目不存在。", status_code=404)
        return row

    def _can_student_edit(self, conn: sqlite3.Connection, work_id: str) -> bool:
        try:
            self._require_student_editor(conn, work_id)
            return True
        except MakingError:
            return False

    def _require_student_editor(self, conn: sqlite3.Connection, work_id: str) -> None:
        row = conn.execute(
            """
            SELECT p.owner_subject, a.class_group_id
            FROM projects AS p
            JOIN work_learning_contexts AS c ON c.work_id = p.id
            JOIN assignments AS a ON a.id = c.assignment_id
            WHERE p.id = ?
            """,
            (work_id,),
        ).fetchone()
        if row is None:
            raise MakingError("MAKING_WORK_NOT_FOUND", "课堂项目不存在。", status_code=404)
        class_member = conn.execute(
            """
            SELECT role FROM class_memberships
            WHERE class_group_id = ? AND subject = ? AND active = 1
            """,
            (row["class_group_id"], self._actor),
        ).fetchone()
        if class_member is None or str(class_member["role"]) != "LEARNER":
            raise MakingError(
                "MAKING_STUDENT_EDITOR_REQUIRED",
                "只有当前项目的学生编辑成员可以修改制作记录。",
                status_code=403,
            )
        owner = str(row["owner_subject"] or _LOCAL_SUBJECT) == self._actor
        member = conn.execute(
            """
            SELECT role FROM work_memberships
            WHERE work_id = ? AND subject = ? AND active = 1
            """,
            (work_id, self._actor),
        ).fetchone()
        if not owner and (member is None or str(member["role"]) not in {"OWNER", "EDITOR"}):
            raise MakingError(
                "MAKING_STUDENT_EDITOR_REQUIRED",
                "只有项目所有者或编辑成员可以修改制作记录。",
                status_code=403,
            )

    @staticmethod
    def _next_version(conn: sqlite3.Connection, table: str, work_id: str) -> int:
        allowed = {
            "project_build_route_decisions",
            "project_structure_revisions",
            "project_assembly_records",
        }
        if table not in allowed:
            raise ValueError("invalid making table")
        return int(
            conn.execute(
                f"SELECT COALESCE(MAX(version), 0) + 1 FROM {table} WHERE work_id = ?",
                (work_id,),
            ).fetchone()[0]
        )

    def _checkpoint(
        self, conn: sqlite3.Connection, work_id: str, decision_id: str, now: str
    ) -> None:
        conn.execute(
            """
            INSERT INTO project_checkpoint_reviews (
              id, work_id, checkpoint, target_kind, target_revision_id,
              decision, reviewer_subject, comment, created_at
            ) VALUES (?, ?, 'BUILD_ROUTE_SELECTED', 'BUILD_ROUTE_DECISION', ?,
                      'APPROVED', ?, '学生已明确选择当前制作路径。', ?)
            """,
            (_id("checkpoint-review"), work_id, decision_id, self._actor, now),
        )

    def _journal(
        self,
        conn: sqlite3.Connection,
        work_id: str,
        kind: str,
        title: str,
        body: str,
        related_kind: str,
        related_id: str,
        now: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO project_process_journal (
              id, work_id, actor_subject, kind, title, body,
              related_kind, related_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _id("journal"),
                work_id,
                self._actor,
                kind,
                title,
                body,
                related_kind,
                related_id,
                now,
            ),
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


def _decision(row: sqlite3.Row) -> BuildRouteDecisionRecord:
    return BuildRouteDecisionRecord(
        id=str(row["id"]),
        workId=str(row["work_id"]),
        version=int(row["version"]),
        route=str(row["route"]),
        rationale=str(row["rationale"]),
        selectedBy=str(row["selected_by"]),
        policyRevisionId=_optional(row["policy_revision_id"]),
        simulationRunId=_optional(row["simulation_run_id"]),
        supersedesRevisionId=_optional(row["supersedes_revision_id"]),
        status=str(row["status"] or "CURRENT"),
        createdAt=str(row["created_at"]),
        invalidatedAt=_optional(row["invalidated_at"]),
        invalidationReason=_optional(row["invalidation_reason"]),
    )


def _structure(row: sqlite3.Row) -> StructureRevisionRecord:
    return StructureRevisionRecord(
        id=str(row["id"]),
        workId=str(row["work_id"]),
        buildRouteDecisionId=str(row["build_route_decision_id"]),
        version=int(row["version"]),
        cadIntentRevisionId=str(row["cad_intent_revision_id"]),
        artifactId=str(row["artifact_id"]),
        artifactVersionId=str(row["artifact_version_id"]),
        requirements=json.loads(str(row["requirements_json"])),
        mechanicalProfileRevisionIds=json.loads(
            str(row["mechanical_profile_revision_ids_json"])
        ),
        dimensions=json.loads(str(row["dimensions_json"])),
        interferenceChecks=json.loads(str(row["interference_checks_json"])),
        material=str(row["material"]),
        fabricationMethod=str(row["fabrication_method"]),
        manufacturingNotes=str(row["manufacturing_notes"]),
        status=str(row["status"]),
        digitalValidationOnly=bool(row["digital_validation_only"]),
        createdBy=str(row["created_by"]),
        createdAt=str(row["created_at"]),
        invalidatedAt=_optional(row["invalidated_at"]),
        invalidationReason=_optional(row["invalidation_reason"]),
    )


def _assembly(row: sqlite3.Row) -> AssemblyRecord:
    return AssemblyRecord(
        id=str(row["id"]),
        workId=str(row["work_id"]),
        buildRouteDecisionId=str(row["build_route_decision_id"]),
        structureRevisionId=_optional(row["structure_revision_id"]),
        version=int(row["version"]),
        wiringPlan=str(row["wiring_plan"]),
        fixingMethod=str(row["fixing_method"]),
        insulationPlan=str(row["insulation_plan"]),
        powerPlan=str(row["power_plan"]),
        assemblySteps=json.loads(str(row["assembly_steps_json"])),
        checklist=json.loads(str(row["checklist_json"])),
        fabricationConfirmed=bool(row["fabrication_confirmed"]),
        observations=json.loads(str(row["observations_json"])),
        reflection=str(row["reflection"]),
        evidenceArtifactVersionIds=json.loads(
            str(row["evidence_artifact_version_ids_json"])
        ),
        status=str(row["status"]),
        attestedBy=str(row["attested_by"]),
        createdAt=str(row["created_at"]),
        invalidatedAt=_optional(row["invalidated_at"]),
        invalidationReason=_optional(row["invalidation_reason"]),
    )


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _optional(value: object) -> str | None:
    return str(value) if value is not None else None


def invalidate_making_for_cad_revision(
    conn: sqlite3.Connection,
    *,
    work_id: str,
    cad_revision_id: str,
    now: str,
) -> None:
    """Invalidate only downstream making facts when a newer CAD revision is confirmed."""

    current = conn.execute(
        """
        SELECT s.cad_intent_revision_id
        FROM work_learning_contexts AS c
        JOIN project_structure_revisions AS s
          ON s.id = c.current_structure_revision_id
        WHERE c.work_id = ? AND s.status = 'READY'
        """,
        (work_id,),
    ).fetchone()
    if current is None or str(current["cad_intent_revision_id"]) == cad_revision_id:
        return
    reason = "CAD 已确认新的结构修订，需要重新完成尺寸、装配和实体验证。"
    conn.execute(
        """
        UPDATE project_structure_revisions
        SET status = 'STALE', invalidated_at = ?, invalidation_reason = ?
        WHERE work_id = ? AND status != 'STALE'
        """,
        (now, reason, work_id),
    )
    conn.execute(
        """
        UPDATE project_assembly_records
        SET status = 'STALE', invalidated_at = ?, invalidation_reason = ?
        WHERE work_id = ? AND status = 'CURRENT'
        """,
        (now, reason, work_id),
    )
    conn.execute(
        """
        UPDATE project_device_deployments
        SET status = 'STALE', invalidated_at = ?, invalidation_reason = ?,
            updated_at = ?
        WHERE work_id = ? AND status != 'STALE'
        """,
        (now, reason, now, work_id),
    )
    conn.execute(
        """
        UPDATE creator_evidence
        SET status = 'STALE', invalidated_at = ?, invalidation_reason = ?
        WHERE project_id = ? AND status = 'CURRENT'
          AND kind IN (
            'STRUCTURE_CHECK', 'DEPLOYMENT', 'PHYSICAL_BEHAVIOR',
            'USER_ACCEPTANCE', 'REPRODUCTION'
          )
        """,
        (now, reason, work_id),
    )
    conn.execute(
        """
        UPDATE project_submission_revisions SET status = 'SUPERSEDED'
        WHERE work_id = ? AND status != 'SUPERSEDED'
        """,
        (work_id,),
    )
    conn.execute(
        """
        UPDATE work_learning_contexts
        SET current_structure_revision_id = NULL,
            current_assembly_record_id = NULL,
            current_device_deployment_id = NULL,
            current_submission_revision_id = NULL,
            process_state = 'STRUCTURE_DESIGN', process_milestone = 'MAKING',
            revision = revision + 1, updated_at = ?
        WHERE work_id = ?
        """,
        (now, work_id),
    )
