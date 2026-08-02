"""Creator V3 command boundary and rebuildable workspace projection."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import ValidationError

from zhangwen.creator.metrics import (
    DigitalBehaviorObservedMetric,
    FirstDeploymentFinishedMetric,
    GoalConfirmedMetric,
    PhysicalBehaviorFinishedMetric,
    SimulationFinishedMetric,
    SolutionConfirmedMetric,
    WorkAcceptedMetric,
    WorkCreatedMetric,
    append_creator_metric,
    metric_trigger_id,
)
from zhangwen.creator.models import (
    AcceptanceCommandPayload,
    AcceptanceScenario,
    ArchiveWorkPayload,
    CodeVariantBinding,
    CreatorCommand,
    CreatorCommandRequest,
    CreatorCommandResponse,
    CreatorJob,
    CreatorJobKind,
    CreatorNextAction,
    CreatorPhase,
    CreatorProjectionReceipt,
    CreatorRevisionSourceType,
    CreatorStage,
    CreatorStageSummary,
    CreatorWorkSummary,
    CreatorWorkspace,
    ConversationProjectDraftV1,
    ConversationProjectionStatus,
    CreatePhysicalRunRequest,
    EvidenceCommandPayload,
    EvidenceKind,
    EvidenceRecord,
    EvidenceStatus,
    EmptyCommandPayload,
    GoalCommandPayload,
    GoalRevision,
    ParameterRevision,
    PhysicalRunReport,
    ProjectBookProjection,
    SolutionCommandPayload,
    SolutionRevision,
    VerificationLevel,
)
from zhangwen.projects.errors import ProjectError
from zhangwen.projects.models import ExpertType
from zhangwen.projects.repository import ProjectRepository


class CreatorError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


_LEVEL_LABELS = {
    VerificationLevel.UNVERIFIED: "尚未验证",
    VerificationLevel.GOAL_CONFIRMED: "目标已确认",
    VerificationLevel.STATIC_VALIDATED: "静态检查通过",
    VerificationLevel.SIMULATION_PASSED: "功能仿真通过",
    VerificationLevel.DEVICE_CONNECTED: "设备已连接",
    VerificationLevel.PHYSICAL_PASSED: "真机运行通过",
    VerificationLevel.USER_ACCEPTED: "用户验收通过",
}

_COMMAND_EVIDENCE = {
    CreatorCommand.RECORD_STATIC_VALIDATION: EvidenceKind.STATIC_VALIDATION,
    CreatorCommand.RECORD_SIMULATION: EvidenceKind.SIMULATION,
    CreatorCommand.RECORD_STRUCTURE_CHECK: EvidenceKind.STRUCTURE_CHECK,
    CreatorCommand.RECORD_DEVICE_CONNECTION: EvidenceKind.DEVICE_CONNECTION,
    CreatorCommand.RECORD_DEPLOYMENT: EvidenceKind.DEPLOYMENT,
    CreatorCommand.RECORD_PHYSICAL_BEHAVIOR: EvidenceKind.PHYSICAL_BEHAVIOR,
    CreatorCommand.RECORD_REPRODUCTION: EvidenceKind.REPRODUCTION,
}

_STRUCTURE_FILE_MIME_TYPES = {
    "GLB_PREVIEW": "model/gltf-binary",
    "STL_PRINTABLE_PARTS": "model/stl",
    "STEP_ASSEMBLY": "model/step",
    "STEP_PRINTABLE_PARTS": "model/step",
    "MANIFEST": "application/json",
}


class CreatorRepository:
    def __init__(self, data_dir: Path) -> None:
        self._data_dir = Path(data_dir).resolve()
        self._projects = ProjectRepository(self._data_dir)
        self._db_path = self._projects.db_path

    def create_work(
        self,
        *,
        name: str | None,
        initial_idea: str,
        idempotency_key: str,
        selected_hardware_ids: list[str],
    ) -> CreatorWorkspace:
        def initialize_creator_work(
            conn: sqlite3.Connection,
            project_id: str,
            now: str,
        ) -> None:
            conn.execute(
                """
                INSERT INTO creator_work_state (
                  project_id, creator_version, origin, last_stage, created_at, updated_at
                ) VALUES (?, 0, 'CREATOR', 'IDEA_SOLUTION', ?, ?)
                """,
                (project_id, now, now),
            )
            append_creator_metric(
                conn,
                project_id,
                WorkCreatedMetric(
                    triggerId=metric_trigger_id(
                        metric="WORK_CREATED",
                        project_id=project_id,
                        source_key=idempotency_key,
                    ),
                    origin="CREATOR",
                ),
            )

        workspace = self._projects.create_project_from_idea(
            idea=initial_idea,
            project_name=name or self._projects.suggest_project(initial_idea).name,
            initial_expert=ExpertType.PROBLEM_GUIDE,
            participating_experts=[
                ExpertType.PROBLEM_GUIDE,
                ExpertType.SMART_ENGINEER,
                ExpertType.STRUCTURE_ENGINEER,
            ],
            idempotency_key=idempotency_key,
            selected_hardware_ids=selected_hardware_ids,
            after_create=initialize_creator_work,
        )
        # Idempotent replays created by earlier builds may have committed the
        # project immediately before Creator state. Repair only that historical
        # partial shape; new works are initialized atomically above.
        with self._connect() as conn:
            has_state = conn.execute(
                "SELECT 1 FROM creator_work_state WHERE project_id = ?",
                (workspace.project.id,),
            ).fetchone()
            if has_state is None:
                initialize_creator_work(conn, workspace.project.id, _now())
        return self.workspace(workspace.project.id)

    def list_works(
        self, *, include_archived: bool = False
    ) -> tuple[list[CreatorWorkSummary], str | None]:
        projects, active = self._projects.list_projects(include_archived=include_archived)
        summaries: list[CreatorWorkSummary] = []
        for project in projects:
            projected = self.workspace(project.id)
            summaries.append(
                CreatorWorkSummary(
                    id=projected.work_id,
                    name=projected.name,
                    initialIdea=projected.initial_idea,
                    phase=projected.phase,
                    stage=projected.active_stage,
                    verificationLevel=projected.verification_level,
                    verificationLabel=projected.verification_label,
                    nextActionLabel=projected.next_action.label,
                    archivedAt=projected.archived_at,
                    updatedAt=projected.updated_at,
                    legacy=projected.legacy,
                )
            )
        return summaries, active

    def workspace(self, project_id: str) -> CreatorWorkspace:
        self._projects.assert_project_access(project_id)
        with self._connect() as conn:
            self._ensure_work_state(conn, project_id, origin="LEGACY")
            projected = self._project(conn, project_id)
            conn.commit()
            return projected

    def project_conversation_draft(
        self,
        project_id: str,
        *,
        source_message_id: str,
        source_turn_id: str | None,
        draft: ConversationProjectDraftV1,
    ) -> CreatorProjectionReceipt:
        """Project one validated conversation draft exactly once.

        Conversation candidates never overwrite an in-progress professional
        draft. In that case a durable conflict receipt is returned so the UI
        can offer a diff instead of silently losing manual work.
        """

        self._projects.assert_project_access(project_id)
        canonical = draft.model_dump(by_alias=True, mode="json")
        draft_hash = hashlib.sha256(
            json.dumps(
                canonical,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        with self._connect() as conn:
            self._ensure_work_state(conn, project_id, origin="LEGACY")
            existing = conn.execute(
                """
                SELECT * FROM creator_projection_receipts
                WHERE project_id = ? AND source_message_id = ?
                """,
                (project_id, source_message_id),
            ).fetchone()
            if existing is not None:
                return self._projection_receipt_model(existing)

            now = _now()
            receipt_id = _id("projection")
            active_draft = conn.execute(
                """
                SELECT * FROM creator_goal_revisions
                WHERE project_id = ? AND status = 'DRAFT'
                ORDER BY revision DESC LIMIT 1
                """,
                (project_id,),
            ).fetchone()
            if (
                active_draft is not None
                and str(active_draft["source_type"]) == "PROFESSIONAL_EDIT"
            ):
                conn.execute(
                    """
                    INSERT INTO creator_projection_receipts (
                      id, project_id, source_type, source_message_id,
                      source_turn_id, draft_hash, status, goal_revision_id,
                      solution_revision_id, message, created_at
                    ) VALUES (?, ?, 'CONVERSATION', ?, ?, ?, 'CONFLICT',
                              NULL, NULL, ?, ?)
                    """,
                    (
                        receipt_id,
                        project_id,
                        source_message_id,
                        source_turn_id,
                        draft_hash,
                        "对话候选未覆盖三师专业模式中的人工草稿。",
                        now,
                    ),
                )
                conn.commit()
                row = conn.execute(
                    "SELECT * FROM creator_projection_receipts WHERE id = ?",
                    (receipt_id,),
                ).fetchone()
                assert row is not None
                return self._projection_receipt_model(row)

            base = conn.execute(
                """
                SELECT id FROM creator_goal_revisions
                WHERE project_id = ? AND status IN ('CONFIRMED', 'DRAFT')
                ORDER BY revision DESC LIMIT 1
                """,
                (project_id,),
            ).fetchone()
            conn.execute(
                """
                UPDATE creator_goal_revisions SET status = 'SUPERSEDED'
                WHERE project_id = ? AND status = 'DRAFT'
                """,
                (project_id,),
            )
            goal_id = _id("goal")
            revision = self._next_revision(
                conn, "creator_goal_revisions", project_id
            )
            conn.execute(
                """
                INSERT INTO creator_goal_revisions (
                  id, project_id, revision, status, statement,
                  observable_behavior, constraints_json,
                  success_criteria_json, source_message_id, created_at,
                  confirmed_at, source_type, source_turn_id,
                  base_revision_id, projection_receipt_id
                ) VALUES (?, ?, ?, 'DRAFT', ?, ?, ?, ?, ?, ?, NULL,
                          'CONVERSATION', ?, ?, ?)
                """,
                (
                    goal_id,
                    project_id,
                    revision,
                    draft.use_scenario,
                    draft.observable_behavior,
                    _dump(draft.constraints),
                    _dump(draft.success_criteria),
                    source_message_id,
                    now,
                    source_turn_id,
                    str(base["id"]) if base is not None else None,
                    receipt_id,
                ),
            )
            conn.execute(
                """
                INSERT INTO creator_projection_receipts (
                  id, project_id, source_type, source_message_id,
                  source_turn_id, draft_hash, status, goal_revision_id,
                  solution_revision_id, message, created_at
                ) VALUES (?, ?, 'CONVERSATION', ?, ?, ?, 'APPLIED',
                          ?, NULL, NULL, ?)
                """,
                (
                    receipt_id,
                    project_id,
                    source_message_id,
                    source_turn_id,
                    draft_hash,
                    goal_id,
                    now,
                ),
            )
            next_version = self._current_version(conn, project_id) + 1
            conn.execute(
                """
                UPDATE creator_work_state
                SET creator_version = ?, updated_at = ? WHERE project_id = ?
                """,
                (next_version, now, project_id),
            )
            self._append_event(
                conn,
                project_id,
                "PROJECTION",
                {
                    "source": "CONVERSATION",
                    "sourceMessageId": source_message_id,
                    "sourceTurnId": source_turn_id,
                    "projectionReceiptId": receipt_id,
                    "goalRevisionId": goal_id,
                },
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM creator_projection_receipts WHERE id = ?",
                (receipt_id,),
            ).fetchone()
            assert row is not None
            return self._projection_receipt_model(row)

    def events(self, project_id: str, *, after: str | None = None) -> list[dict[str, Any]]:
        self._projects.assert_project_access(project_id)
        with self._connect() as conn:
            if after:
                rows = conn.execute(
                    """
                    SELECT * FROM creator_events
                    WHERE project_id = ? AND created_at > ?
                    ORDER BY created_at ASC, id ASC LIMIT 500
                    """,
                    (project_id, after),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM creator_events
                    WHERE project_id = ? ORDER BY created_at ASC, id ASC LIMIT 500
                    """,
                    (project_id,),
                ).fetchall()
            events: list[dict[str, Any]] = []
            for row in rows:
                event = {
                    "id": str(row["id"]),
                    "type": str(row["event_type"]),
                    "createdAt": str(row["created_at"]),
                    "payload": json.loads(str(row["payload_json"])),
                }
                if event["type"] != "METRIC":
                    event["workId"] = project_id
                events.append(event)
            return events

    def create_physical_run(
        self, project_id: str, request: CreatePhysicalRunRequest,
        *, operator_subject: str = "local-dev-subject",
    ) -> PhysicalRunReport:
        """Persist one immutable, operator-observed physical acceptance run.

        The report binds to a verified deployment and never drives the device.
        """

        self._projects.assert_project_access(project_id)
        request_hash = _hash(
            {
                **request.model_dump(
                    mode="json", by_alias=True, exclude={"idempotency_key"}
                ),
                "operatorSubject": operator_subject,
            }
        )
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT * FROM creator_physical_runs "
                "WHERE project_id = ? AND idempotency_key = ?",
                (project_id, request.idempotency_key),
            ).fetchone()
            if existing is not None:
                if str(existing["request_hash"]) != request_hash:
                    raise CreatorError(
                        "CREATOR_IDEMPOTENCY_KEY_REUSED",
                        "该幂等键已绑定到不同的实物验收请求。",
                        status_code=409,
                    )
                return self._physical_run_from_row(existing)
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT * FROM creator_physical_runs "
                "WHERE project_id = ? AND idempotency_key = ?",
                (project_id, request.idempotency_key),
            ).fetchone()
            if existing is not None:
                if str(existing["request_hash"]) != request_hash:
                    raise CreatorError(
                        "CREATOR_IDEMPOTENCY_KEY_REUSED",
                        "该幂等键已绑定到不同的实物验收请求。",
                        status_code=409,
                    )
                return self._physical_run_from_row(existing)
            self._refresh_stale_evidence(conn, project_id)
            solution = conn.execute(
                """
                SELECT id FROM creator_solution_revisions
                WHERE project_id = ? AND status = 'CONFIRMED'
                ORDER BY revision DESC LIMIT 1
                """,
                (project_id,),
            ).fetchone()
            if solution is None:
                raise CreatorError(
                    "CREATOR_SOLUTION_REQUIRED", "请先确认当前实施方案。", status_code=409
                )
            solution_id = str(solution["id"])
            operation, operation_state = self._validated_deployment_operation(
                conn, project_id, request.deployment_operation_id
            )
            metadata = operation_state["metadata"]
            assert isinstance(metadata, dict)
            if str(metadata.get("targetId", "")) != request.target_id:
                raise CreatorError(
                    "CREATOR_PHYSICAL_TARGET_MISMATCH",
                    "实物验收目标与已验证部署目标不一致。",
                    status_code=409,
                )
            deployment_evidence = conn.execute(
                """
                SELECT 1 FROM creator_evidence
                WHERE project_id = ? AND kind = 'DEPLOYMENT' AND status = 'CURRENT'
                  AND passed = 1 AND source_id = ?
                LIMIT 1
                """,
                (project_id, str(operation["id"])),
            ).fetchone()
            if deployment_evidence is None:
                raise CreatorError(
                    "CREATOR_DEPLOYMENT_EVIDENCE_REQUIRED",
                    "请先把当前部署回读结果记录为有效证据。",
                    status_code=409,
                )

            scenario_rows = conn.execute(
                """
                SELECT id, required FROM creator_acceptance_scenarios
                WHERE project_id = ? AND solution_revision_id = ?
                """,
                (project_id, solution_id),
            ).fetchall()
            known = {str(row["id"]): bool(row["required"]) for row in scenario_rows}
            required = {scenario_id for scenario_id, value in known.items() if value}
            supplied = [item.scenario_id for item in request.scenario_results]
            if len(supplied) != len(set(supplied)) or any(item not in known for item in supplied):
                raise CreatorError(
                    "CREATOR_PHYSICAL_SCENARIOS_INVALID",
                    "实物验收包含重复或不属于当前方案的场景。",
                    status_code=409,
                )
            results = {item.scenario_id: item.observed for item in request.scenario_results}
            passed = (
                required.issubset(results)
                and all(results[scenario_id] for scenario_id in required)
                and request.emergency_stop_verified
            )
            run_id = _id("physical_run")
            now = _now()
            conn.execute(
                """
                INSERT INTO creator_physical_runs (
                  id, project_id, solution_revision_id, deployment_operation_id,
                  target_id, operator, status, emergency_stop_verified,
                  scenario_results_json, created_at, idempotency_key,
                  request_hash, operator_subject
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    project_id,
                    solution_id,
                    str(operation["id"]),
                    request.target_id,
                    request.operator,
                    "PASSED" if passed else "FAILED",
                    1 if request.emergency_stop_verified else 0,
                    _dump(
                        [
                            item.model_dump(mode="json", by_alias=True)
                            for item in request.scenario_results
                        ]
                    ),
                    now,
                    request.idempotency_key,
                    request_hash,
                    operator_subject,
                ),
            )
            self._append_event(
                conn,
                project_id,
                "DEVICE",
                {
                    "physicalRunId": run_id,
                    "deploymentOperationId": str(operation["id"]),
                    "status": "PASSED" if passed else "FAILED",
                },
            )
            conn.commit()
            return PhysicalRunReport(
                id=run_id,
                workId=project_id,
                solutionRevisionId=solution_id,
                deploymentOperationId=str(operation["id"]),
                targetId=request.target_id,
                operator=request.operator,
                passed=passed,
                emergencyStopVerified=request.emergency_stop_verified,
                scenarioResults=request.scenario_results,
                createdAt=now,
            )

    @staticmethod
    def _physical_run_from_row(row: sqlite3.Row) -> PhysicalRunReport:
        return PhysicalRunReport(
            id=str(row["id"]),
            workId=str(row["project_id"]),
            solutionRevisionId=str(row["solution_revision_id"]),
            deploymentOperationId=str(row["deployment_operation_id"]),
            targetId=str(row["target_id"]),
            operator=str(row["operator"]),
            passed=str(row["status"]) == "PASSED",
            emergencyStopVerified=bool(row["emergency_stop_verified"]),
            scenarioResults=json.loads(str(row["scenario_results_json"])),
            createdAt=str(row["created_at"]),
        )

    def validate_command_source(
        self,
        project_id: str,
        command: CreatorCommand,
        payload: dict[str, Any],
    ) -> None:
        """Validate local evidence against persisted platform facts.

        Repository state-machine tests may exercise transitions directly, but
        the HTTP boundary must never accept a caller-authored success string as
        proof of a scene check or simulator run.
        """

        if command not in {
            CreatorCommand.RECORD_STATIC_VALIDATION,
            CreatorCommand.RECORD_SIMULATION,
            CreatorCommand.RECORD_STRUCTURE_CHECK,
            CreatorCommand.RECORD_DEVICE_CONNECTION,
            CreatorCommand.RECORD_DEPLOYMENT,
            CreatorCommand.RECORD_PHYSICAL_BEHAVIOR,
            CreatorCommand.RECORD_REPRODUCTION,
        }:
            return
        try:
            parsed = EvidenceCommandPayload.model_validate(payload)
        except ValidationError as exc:
            raise CreatorError(
                "CREATOR_COMMAND_PAYLOAD_INVALID",
                "命令参数不完整或包含未知字段。",
            ) from exc
        if not parsed.source_id:
            raise CreatorError(
                "CREATOR_EVIDENCE_SOURCE_REQUIRED",
                "验证证据必须绑定真实的本地场景或运行记录。",
                status_code=409,
            )
        self._projects.assert_project_access(project_id)
        with self._connect() as conn:
            solution = conn.execute(
                """
                SELECT id FROM creator_solution_revisions
                WHERE project_id = ? AND status = 'CONFIRMED'
                ORDER BY revision DESC LIMIT 1
                """,
                (project_id,),
            ).fetchone()
            if solution is None:
                raise CreatorError(
                    "CREATOR_SOLUTION_REQUIRED",
                    "请先确认当前实施方案。",
                    status_code=409,
                )
            solution_id = str(solution["id"])
            if command is CreatorCommand.RECORD_REPRODUCTION:
                row = conn.execute(
                    """
                    SELECT status FROM creator_reproductions
                    WHERE id = ? AND source_project_id = ?
                    """,
                    (parsed.source_id, project_id),
                ).fetchone()
                if row is None or str(row["status"]) != "PASSED":
                    raise CreatorError(
                        "CREATOR_REPRODUCTION_NOT_VERIFIED",
                        "复现证据必须来自通过校验的第二用户导入与验收记录。",
                        status_code=409,
                    )
                return
            if command is CreatorCommand.RECORD_DEVICE_CONNECTION:
                self._validate_device_connection_source(
                    conn, project_id, solution_id, parsed
                )
                return
            if command is CreatorCommand.RECORD_DEPLOYMENT:
                operation, state = self._validated_deployment_operation(
                    conn, project_id, parsed.source_id
                )
                metadata = state["metadata"]
                assert isinstance(metadata, dict)
                connection = conn.execute(
                    """
                    SELECT source_id FROM creator_evidence
                    WHERE project_id = ? AND kind = 'DEVICE_CONNECTION'
                      AND status = 'CURRENT' AND passed = 1
                    LIMIT 1
                    """,
                    (project_id,),
                ).fetchone()
                if connection is None or str(connection["source_id"]) != str(
                    metadata.get("targetId", "")
                ):
                    raise CreatorError(
                        "CREATOR_DEPLOYMENT_TARGET_MISMATCH",
                        "部署目标与当前已确认设备连接不一致。",
                        status_code=409,
                    )
                if parsed.bindings.get("codeRunId") not in {
                    None,
                    str(metadata.get("codeRunId", "")),
                }:
                    raise CreatorError(
                        "CREATOR_DEPLOYMENT_CODE_MISMATCH",
                        "部署证据与设备实际运行的代码版本不一致。",
                        status_code=409,
                    )
                return
            if command is CreatorCommand.RECORD_PHYSICAL_BEHAVIOR:
                row = conn.execute(
                    """
                    SELECT solution_revision_id, deployment_operation_id, status
                    FROM creator_physical_runs
                    WHERE id = ? AND project_id = ?
                    """,
                    (parsed.source_id, project_id),
                ).fetchone()
                if (
                    row is None
                    or str(row["solution_revision_id"]) != solution_id
                    or str(row["status"]) != "PASSED"
                ):
                    raise CreatorError(
                        "CREATOR_PHYSICAL_RUN_NOT_PASSED",
                        "真机行为证据必须来自当前方案下已通过的实物验收会话。",
                        status_code=409,
                    )
                deployment = conn.execute(
                    """
                    SELECT 1 FROM creator_evidence
                    WHERE project_id = ? AND kind = 'DEPLOYMENT' AND status = 'CURRENT'
                      AND passed = 1 AND source_id = ?
                    """,
                    (project_id, str(row["deployment_operation_id"])),
                ).fetchone()
                if deployment is None:
                    raise CreatorError(
                        "CREATOR_PHYSICAL_DEPLOYMENT_STALE",
                        "实物验收绑定的部署已不是当前有效部署。",
                        status_code=409,
                    )
                return
            if command is CreatorCommand.RECORD_STRUCTURE_CHECK:
                if parsed.bindings.get("solutionRevisionId") != solution_id:
                    raise CreatorError(
                        "CREATOR_STRUCTURE_SOLUTION_MISMATCH",
                        "结构检查必须绑定当前方案版本。",
                        status_code=409,
                    )
                if parsed.bindings.get("structureRevisionId") != parsed.source_id:
                    raise CreatorError(
                        "CREATOR_STRUCTURE_REVISION_MISMATCH",
                        "结构检查绑定的修订与真实 CAD 来源不一致。",
                        status_code=409,
                    )
                row = conn.execute(
                    """
                    SELECT id, artifact_id, artifact_version_id FROM cad_intent_revisions
                    WHERE id = ? AND project_id = ? AND status = 'CONFIRMED'
                    """,
                    (parsed.source_id, project_id),
                ).fetchone()
                if row is None or not row["artifact_id"] or not row["artifact_version_id"]:
                    raise CreatorError(
                        "CREATOR_STRUCTURE_REVISION_NOT_READY",
                        "结构修订尚未确认或没有真实 CAD 产物。",
                        status_code=409,
                    )
                files = conn.execute(
                    """
                    SELECT role, file_name, storage_key, mime_type, byte_size, sha256
                    FROM artifact_files
                    WHERE project_id = ? AND artifact_id = ? AND artifact_version_id = ?
                    """,
                    (
                        project_id,
                        str(row["artifact_id"]),
                        str(row["artifact_version_id"]),
                    ),
                ).fetchall()
                roles = {str(item["role"]) for item in files}
                required = {"GLB_PREVIEW", "STL_PRINTABLE_PARTS", "MANIFEST"}
                has_step = bool({"STEP_ASSEMBLY", "STEP_PRINTABLE_PARTS"} & roles)
                if parsed.passed and (not required.issubset(roles) or not has_step):
                    raise CreatorError(
                        "CREATOR_STRUCTURE_OUTPUTS_INCOMPLETE",
                        "结构产物必须包含经校验的 GLB、STL、STEP 和 manifest。",
                        status_code=409,
                    )
                if parsed.passed:
                    required_roles = required | (
                        {"STEP_ASSEMBLY"}
                        if "STEP_ASSEMBLY" in roles
                        else {"STEP_PRINTABLE_PARTS"}
                    )
                    invalid_roles = {
                        role
                        for role in required_roles
                        if not any(
                            str(item["role"]) == role
                            and self._artifact_file_is_valid(item)
                            for item in files
                        )
                    }
                    if invalid_roles:
                        raise CreatorError(
                            "CREATOR_STRUCTURE_OUTPUTS_INVALID",
                            "结构产物文件的元数据、Hash 或本地存储路径校验失败。",
                            status_code=409,
                        )
                return
            if command is CreatorCommand.RECORD_STATIC_VALIDATION:
                row = conn.execute(
                    """
                    SELECT scene_json FROM device_lab_scenes
                    WHERE project_id = ? AND revision = ?
                    ORDER BY rowid DESC LIMIT 1
                    """,
                    (project_id, parsed.source_id),
                ).fetchone()
                if row is None:
                    raise CreatorError(
                        "CREATOR_SCENE_EVIDENCE_NOT_FOUND",
                        "数字原型场景不存在或不属于当前作品。",
                        status_code=409,
                    )
                scene = json.loads(str(row["scene_json"]))
                if _scene_solution_revision_id(scene) != solution_id:
                    raise CreatorError(
                        "CREATOR_SCENE_SOLUTION_MISMATCH",
                        "数字原型场景不是由当前方案生成的，请重新物化。",
                        status_code=409,
                    )
                if parsed.passed and scene.get("status") != "READY":
                    raise CreatorError(
                        "CREATOR_SCENE_IO_UNCONFIRMED",
                        "场景仍有未确认 IO，不能记录静态检查通过。",
                        status_code=409,
                    )
                return

            row = conn.execute(
                """
                SELECT target, status, state_json FROM device_lab_runs
                WHERE project_id = ? AND id = ?
                """,
                (project_id, parsed.source_id),
            ).fetchone()
            if row is None or str(row["target"]) != "SIMULATOR":
                raise CreatorError(
                    "CREATOR_SIMULATION_EVIDENCE_NOT_FOUND",
                    "找不到当前作品的本地仿真会话。",
                    status_code=409,
                )
            if str(row["status"]) != "STOPPED":
                raise CreatorError(
                    "CREATOR_SIMULATION_NOT_STOPPED",
                    "仿真必须先安全停止，才能记录验收结果。",
                    status_code=409,
                )
            run = json.loads(str(row["state_json"]))
            if _scene_solution_revision_id(run.get("scene", {})) != solution_id:
                raise CreatorError(
                    "CREATOR_SIMULATION_SOLUTION_MISMATCH",
                    "仿真会话没有绑定当前方案。",
                    status_code=409,
                )
            if parsed.passed:
                expected = {
                    str(item["id"])
                    for item in conn.execute(
                        "SELECT id FROM creator_acceptance_scenarios WHERE project_id = ? AND required = 1",
                        (project_id,),
                    ).fetchall()
                }
                actual = {
                    item for item in parsed.bindings.get("scenarioIds", "").split(",") if item
                }
                if not expected or not expected.issubset(actual):
                    raise CreatorError(
                        "CREATOR_SIMULATION_SCENARIOS_INCOMPLETE",
                        "所有必需仿真场景都确认后才能记录通过。",
                        status_code=409,
                    )

    def _validate_device_connection_source(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        solution_id: str,
        payload: EvidenceCommandPayload,
    ) -> None:
        scene_row = conn.execute(
            """
            SELECT board_id FROM device_lab_scenes
            WHERE project_id = ? AND proposal_id = ?
            ORDER BY created_at DESC LIMIT 1
            """,
            (project_id, solution_id),
        ).fetchone()
        if scene_row is None:
            raise CreatorError(
                "CREATOR_DEVICE_SCENE_REQUIRED",
                "连接真机前必须先由当前方案建立数字原型。",
                status_code=409,
            )
        endpoint = conn.execute(
            """
            SELECT e.board_id, e.status, s.status AS session_status
            FROM espclaw_endpoints AS e
            JOIN device_sessions AS s ON s.id = e.session_id
            WHERE e.project_id = ? AND e.id = ?
            """,
            (project_id, payload.source_id),
        ).fetchone()
        if endpoint is not None:
            ready = (
                str(endpoint["status"]) == "READY"
                and str(endpoint["session_status"])
                in {"READY", "RUNTIME_BUSY", "MANAGED"}
            )
            board_id = str(endpoint["board_id"])
            channel = "ESP_CLAW"
        else:
            session = conn.execute(
                """
                SELECT board, status, port_id FROM device_sessions
                WHERE project_id = ? AND id = ?
                """,
                (project_id, payload.source_id),
            ).fetchone()
            ready = bool(
                session is not None
                and not str(session["port_id"]).startswith("esp-claw:")
                and str(session["status"])
                in {"READY", "RUNTIME_BUSY", "MANAGED"}
            )
            board_id = str(session["board"]) if session is not None else ""
            channel = "USB_SERIAL"
        if not ready:
            raise CreatorError(
                "CREATOR_DEVICE_CONNECTION_NOT_READY",
                "设备连接不存在、已断开或尚未完成身份确认。",
                status_code=409,
            )
        if board_id != str(scene_row["board_id"]):
            raise CreatorError(
                "CREATOR_DEVICE_BOARD_MISMATCH",
                "真实设备与当前数字原型的设备包不一致。",
                status_code=409,
            )
        if payload.bindings.get("channel") not in {None, channel}:
            raise CreatorError(
                "CREATOR_DEVICE_CHANNEL_MISMATCH",
                "设备连接通道与真实连接不一致。",
                status_code=409,
            )

    def _validated_deployment_operation(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        operation_id: str | None,
    ) -> tuple[sqlite3.Row, dict[str, Any]]:
        row = conn.execute(
            """
            SELECT id, session_id, kind, status, dry_run, log
            FROM device_operations WHERE project_id = ? AND id = ?
            """,
            (project_id, operation_id),
        ).fetchone()
        if (
            row is None
            or str(row["kind"]) != "UPLOAD_CODE"
            or str(row["status"]) != "COMPLETED"
            or bool(row["dry_run"])
        ):
            raise CreatorError(
                "CREATOR_DEPLOYMENT_NOT_VERIFIED",
                "部署证据必须来自已完成的真实代码上传。",
                status_code=409,
            )
        try:
            state = json.loads(str(row["log"]))
        except (json.JSONDecodeError, TypeError) as exc:
            raise CreatorError(
                "CREATOR_DEPLOYMENT_STATE_INVALID",
                "部署操作缺少可验证的本地状态。",
                status_code=409,
            ) from exc
        if not isinstance(state, dict) or state.get("schema") != "device-operation/v1":
            raise CreatorError(
                "CREATOR_DEPLOYMENT_STATE_INVALID",
                "部署操作缺少可验证的本地状态。",
                status_code=409,
            )
        verification = state.get("verification")
        metadata = state.get("metadata")
        if (
            not isinstance(verification, dict)
            or verification.get("ok") is not True
            or verification.get("deploymentOk") is False
            or not isinstance(metadata, dict)
            or metadata.get("channel") not in {"USB_SERIAL", "ESP_CLAW"}
            or not metadata.get("targetId")
            or not metadata.get("codeRunId")
        ):
            raise CreatorError(
                "CREATOR_DEPLOYMENT_READBACK_REQUIRED",
                "部署尚未完成文件回读和运行时验证。",
                status_code=409,
            )
        return row, state

    def _artifact_file_is_valid(self, row: sqlite3.Row) -> bool:
        role = str(row["role"])
        expected_mime_type = _STRUCTURE_FILE_MIME_TYPES.get(role)
        storage_key = str(row["storage_key"] or "")
        file_name = str(row["file_name"] or "")
        mime_type = str(row["mime_type"] or "")
        sha256 = str(row["sha256"] or "")
        try:
            byte_size = int(row["byte_size"])
        except (TypeError, ValueError):
            return False
        if (
            expected_mime_type is None
            or mime_type != expected_mime_type
            or byte_size <= 0
            or len(sha256) != 64
            or any(character not in "0123456789abcdef" for character in sha256)
        ):
            return False
        relative = PurePosixPath(storage_key)
        if (
            relative.is_absolute()
            or not relative.parts
            or any(part in {"", ".", ".."} for part in relative.parts)
            or "\\" in storage_key
            or relative.name != file_name
        ):
            return False
        root = (self._data_dir / "artifact-files").resolve()
        candidate = root.joinpath(*relative.parts)
        try:
            current = candidate
            while current != root.parent:
                if current.is_symlink() or getattr(
                    current, "is_junction", lambda: False
                )():
                    return False
                if current == root:
                    break
                current = current.parent
            resolved = candidate.resolve(strict=True)
            if root not in resolved.parents or not resolved.is_file():
                return False
            if resolved.stat().st_size != byte_size:
                return False
            digest = hashlib.sha256()
            with resolved.open("rb") as artifact_file:
                for chunk in iter(lambda: artifact_file.read(1024 * 1024), b""):
                    digest.update(chunk)
            return digest.hexdigest() == sha256
        except (OSError, RuntimeError, ValueError):
            return False

    def replay_command(
        self,
        project_id: str,
        command: CreatorCommand,
        request: CreatorCommandRequest,
        *, authenticated_subject: str | None = None,
    ) -> CreatorCommandResponse | None:
        """Resolve historical retries before volatile source validation."""

        self._projects.assert_project_access(project_id)
        request_hash = _hash(
            {
                "command": command.value,
                "baseProjectVersion": request.base_project_version,
                "payload": request.payload,
                "authenticatedSubject": authenticated_subject
                if command is CreatorCommand.ACCEPT_WORK
                else None,
            }
        )
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT * FROM creator_commands "
                "WHERE project_id = ? AND idempotency_key = ?",
                (project_id, request.idempotency_key),
            ).fetchone()
        if existing is None:
            return None
        if (
            str(existing["command"]) != command.value
            or str(existing["request_hash"]) != request_hash
        ):
            raise CreatorError(
                "CREATOR_IDEMPOTENCY_KEY_REUSED",
                "该幂等键已用于不同命令。",
                status_code=409,
            )
        return CreatorCommandResponse(
            commandId=str(existing["id"]),
            command=command,
            repeated=True,
            workspace=self.workspace(project_id),
        )

    def execute(
        self,
        project_id: str,
        command: CreatorCommand,
        request: CreatorCommandRequest,
        *, authenticated_subject: str | None = None,
    ) -> CreatorCommandResponse:
        self._projects.assert_project_access(project_id)
        request_hash = _hash(
            {
                "command": command.value,
                "baseProjectVersion": request.base_project_version,
                "payload": request.payload,
                "authenticatedSubject": authenticated_subject
                if command is CreatorCommand.ACCEPT_WORK
                else None,
            }
        )
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._ensure_work_state(conn, project_id, origin="LEGACY")
            existing = conn.execute(
                """
                SELECT * FROM creator_commands
                WHERE project_id = ? AND idempotency_key = ?
                """,
                (project_id, request.idempotency_key),
            ).fetchone()
            if existing is not None:
                if (
                    str(existing["command"]) != command.value
                    or str(existing["request_hash"]) != request_hash
                ):
                    raise CreatorError(
                        "CREATOR_IDEMPOTENCY_KEY_REUSED",
                        "该幂等键已用于不同命令，请刷新作品后重试。",
                        status_code=409,
                    )
                conn.rollback()
                return CreatorCommandResponse(
                    commandId=str(existing["id"]),
                    command=command,
                    repeated=True,
                    workspace=self.workspace(project_id),
                )
            self._refresh_stale_evidence(conn, project_id)

            current_version = self._current_version(conn, project_id)
            if request.base_project_version != current_version:
                raise CreatorError(
                    "CREATOR_VERSION_CONFLICT",
                    f"基础版本 {request.base_project_version} 已过期，当前版本为 {current_version}。",
                    status_code=409,
                )

            try:
                self._apply(
                    conn, project_id, command, request.payload,
                    authenticated_subject=authenticated_subject,
                )
            except ValidationError as exc:
                raise CreatorError(
                    "CREATOR_COMMAND_PAYLOAD_INVALID",
                    "命令参数不完整或包含未知字段。",
                ) from exc

            next_version = current_version + 1
            now = _now()
            conn.execute(
                """
                UPDATE creator_work_state
                SET creator_version = ?, updated_at = ? WHERE project_id = ?
                """,
                (next_version, now, project_id),
            )
            projected = self._project(conn, project_id)
            command_id = _id("ccmd")
            response_stub = {
                "commandId": command_id,
                "command": command.value,
                "projectVersion": projected.project_version,
            }
            conn.execute(
                """
                INSERT INTO creator_commands (
                  id, project_id, command, idempotency_key, request_hash,
                  base_project_version, result_project_version, response_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    command_id,
                    project_id,
                    command.value,
                    request.idempotency_key,
                    request_hash,
                    current_version,
                    next_version,
                    _dump(response_stub),
                    now,
                ),
            )
            self._append_event(
                conn,
                project_id,
                "COMMAND",
                {
                    "commandId": command_id,
                    "command": command.value,
                    "projectVersion": next_version,
                },
            )
            self._append_command_metrics(
                conn,
                project_id,
                command,
                request.payload,
                command_id=command_id,
                projected=projected,
            )
            conn.commit()
            return CreatorCommandResponse(
                commandId=command_id,
                command=command,
                repeated=False,
                workspace=projected,
            )

    def _apply(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        command: CreatorCommand,
        payload: dict[str, Any],
        *, authenticated_subject: str | None = None,
    ) -> None:
        if command in {CreatorCommand.SAVE_GOAL, CreatorCommand.CONFIRM_GOAL}:
            parsed = GoalCommandPayload.model_validate(payload)
            self._create_goal(
                conn,
                project_id,
                parsed,
                confirmed=command is CreatorCommand.CONFIRM_GOAL,
            )
            return
        if command in {CreatorCommand.SAVE_SOLUTION, CreatorCommand.CONFIRM_SOLUTION}:
            parsed = SolutionCommandPayload.model_validate(payload)
            if command is CreatorCommand.CONFIRM_SOLUTION:
                self._confirm_current_goal_for_solution(conn, project_id)
            self._create_solution(
                conn,
                project_id,
                parsed,
                confirmed=command is CreatorCommand.CONFIRM_SOLUTION,
            )
            return
        if command is CreatorCommand.GENERATE_PROJECT_BOOK:
            EmptyCommandPayload.model_validate(payload)
            self._generate_project_book(conn, project_id)
            return
        if command in _COMMAND_EVIDENCE:
            parsed = EvidenceCommandPayload.model_validate(payload)
            kind = _COMMAND_EVIDENCE[command]
            self._assert_evidence_prerequisite(conn, project_id, kind)
            self._record_evidence(conn, project_id, kind, parsed)
            return
        if command is CreatorCommand.ACCEPT_WORK:
            parsed = AcceptanceCommandPayload.model_validate(payload)
            if not authenticated_subject:
                raise CreatorError(
                    "CREATOR_AUTHENTICATED_SUBJECT_REQUIRED",
                    "最终验收必须由已认证账户签署。",
                    status_code=401,
                )
            if parsed.actor.strip().casefold() in {
                "system",
                "ai",
                "model",
                "assistant",
                "掌问",
            }:
                raise CreatorError(
                    "CREATOR_HUMAN_ACCEPTANCE_REQUIRED",
                    "最终验收必须由明确的人类操作者确认，不能由系统或模型代签。",
                    status_code=409,
                )
            if not self._current_pass(conn, project_id, EvidenceKind.PHYSICAL_BEHAVIOR):
                raise CreatorError(
                    "CREATOR_PHYSICAL_EVIDENCE_REQUIRED",
                    "真机行为尚未通过，不能进行最终验收。",
                    status_code=409,
                )
            self._record_evidence(
                conn,
                project_id,
                EvidenceKind.USER_ACCEPTANCE,
                EvidenceCommandPayload(
                    passed=True,
                    summary=parsed.summary,
                    sourceId=parsed.actor,
                    bindings={
                        "actor": parsed.actor,
                        "actorSubject": authenticated_subject,
                    },
                ),
            )
            return
        if command is CreatorCommand.ARCHIVE_WORK:
            parsed = ArchiveWorkPayload.model_validate(payload)
            now = _now()
            conn.execute(
                "UPDATE projects SET archived_at = ?, updated_at = ? WHERE id = ?",
                (now if parsed.archived else None, now, project_id),
            )
            return
        raise CreatorError("CREATOR_COMMAND_UNSUPPORTED", "不支持的作品命令。")

    def _create_goal(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        payload: GoalCommandPayload,
        *,
        confirmed: bool,
    ) -> None:
        now = _now()
        revision = self._next_revision(conn, "creator_goal_revisions", project_id)
        if confirmed:
            conn.execute(
                """
                UPDATE creator_goal_revisions SET status = 'SUPERSEDED'
                WHERE project_id = ? AND status IN ('DRAFT', 'CONFIRMED')
                """,
                (project_id,),
            )
        else:
            conn.execute(
                """
                UPDATE creator_goal_revisions SET status = 'SUPERSEDED'
                WHERE project_id = ? AND status = 'DRAFT'
                """,
                (project_id,),
            )
        goal_id = _id("goal")
        conn.execute(
            """
            INSERT INTO creator_goal_revisions (
              id, project_id, revision, status, statement, observable_behavior,
              constraints_json, success_criteria_json, source_message_id,
              created_at, confirmed_at, source_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PROFESSIONAL_EDIT')
            """,
            (
                goal_id,
                project_id,
                revision,
                "CONFIRMED" if confirmed else "DRAFT",
                payload.statement,
                payload.observable_behavior,
                _dump(payload.constraints),
                _dump(payload.success_criteria),
                payload.source_message_id,
                now,
                now if confirmed else None,
            ),
        )
        if confirmed:
            self._invalidate(conn, project_id, "目标版本已更新。")
            self._insert_evidence(
                conn,
                project_id,
                EvidenceKind.GOAL_CONFIRMATION,
                passed=True,
                summary="用户已确认作品目标和成功标准。",
                source_id=goal_id,
                bindings={"goalRevisionId": goal_id},
            )

    def _confirm_current_goal_for_solution(
        self,
        conn: sqlite3.Connection,
        project_id: str,
    ) -> sqlite3.Row:
        """Confirm the current conversation goal as the solution baseline.

        Creator exposes one user confirmation for the complete plan. A newer
        draft goal therefore wins over an older confirmed goal and is
        confirmed inside the same command transaction as the solution.
        """

        draft = conn.execute(
            """
            SELECT * FROM creator_goal_revisions
            WHERE project_id = ? AND status = 'DRAFT'
            ORDER BY revision DESC LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        if draft is None:
            confirmed = self._confirmed_goal(conn, project_id)
            if confirmed is None:
                raise CreatorError(
                    "CREATOR_GOAL_REQUIRED",
                    "当前方案缺少可绑定的作品目标，请先完成问题引导。",
                    status_code=409,
                )
            return confirmed

        goal_id = str(draft["id"])
        now = _now()
        conn.execute(
            """
            UPDATE creator_goal_revisions SET status = 'SUPERSEDED'
            WHERE project_id = ? AND status = 'CONFIRMED'
            """,
            (project_id,),
        )
        conn.execute(
            """
            UPDATE creator_goal_revisions
            SET status = 'CONFIRMED', confirmed_at = ?
            WHERE id = ?
            """,
            (now, goal_id),
        )
        self._invalidate(conn, project_id, "方案确认采用了新的目标基准。")
        self._insert_evidence(
            conn,
            project_id,
            EvidenceKind.GOAL_CONFIRMATION,
            passed=True,
            summary="用户确认完整方案时同步确认了作品目标和成功标准。",
            source_id=goal_id,
            bindings={"goalRevisionId": goal_id},
        )
        confirmed = self._confirmed_goal(conn, project_id)
        assert confirmed is not None
        return confirmed

    def _create_solution(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        payload: SolutionCommandPayload,
        *,
        confirmed: bool,
    ) -> None:
        now = _now()
        revision = self._next_revision(conn, "creator_solution_revisions", project_id)
        target_status = "CONFIRMED" if confirmed else "DRAFT"
        superseded_statuses = ("DRAFT", "CONFIRMED") if confirmed else ("DRAFT",)
        placeholders = ",".join("?" for _ in superseded_statuses)
        conn.execute(
            f"""
            UPDATE creator_solution_revisions SET status = 'SUPERSEDED'
            WHERE project_id = ? AND status IN ({placeholders})
            """,
            (project_id, *superseded_statuses),
        )
        solution_id = _id("csolution")
        conn.execute(
            """
            INSERT INTO creator_solution_revisions (
              id, project_id, revision, status, summary, logic, hardware, software,
              structure, simulation, safety, bom_json, io_map_json,
              source_proposal_id, created_at, confirmed_at, source_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      'PROFESSIONAL_EDIT')
            """,
            (
                solution_id,
                project_id,
                revision,
                target_status,
                payload.summary,
                payload.logic,
                payload.hardware,
                payload.software,
                payload.structure,
                payload.simulation,
                payload.safety,
                _dump([item.model_dump(by_alias=True) for item in payload.bom]),
                _dump([item.model_dump(by_alias=True) for item in payload.io_map]),
                payload.source_proposal_id,
                now,
                now if confirmed else None,
            ),
        )
        if confirmed:
            conn.execute(
                "DELETE FROM creator_acceptance_scenarios WHERE project_id = ?",
                (project_id,),
            )
            for scenario in payload.acceptance_scenarios:
                conn.execute(
                    """
                    INSERT INTO creator_acceptance_scenarios (
                      id, project_id, solution_revision_id, title, required,
                      simulation_expected, physical_expected, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        _id("scenario"),
                        project_id,
                        solution_id,
                        scenario.title,
                        1 if scenario.required else 0,
                        scenario.simulation_expected,
                        scenario.physical_expected,
                        now,
                    ),
                )
            self._invalidate(
                conn,
                project_id,
                "实施方案版本已更新。",
                exclude={EvidenceKind.GOAL_CONFIRMATION},
            )
            self._queue_job(
                conn,
                project_id,
                solution_id,
                CreatorJobKind.CODE_PREPARATION,
            )
            for channel, runtime in (
                ("USB_SERIAL", "MICROPYTHON"),
                ("ESP_CLAW", "ESP_CLAW_LUA"),
            ):
                conn.execute(
                    """
                    INSERT INTO creator_code_variant_bindings (
                      id, project_id, solution_revision_id,
                      deployment_channel, runtime, code_run_id,
                      device_package_id, validation_status,
                      failure_code, failure_message, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, NULL, NULL, 'PENDING',
                              NULL, NULL, ?, ?)
                    ON CONFLICT(solution_revision_id, deployment_channel)
                    DO UPDATE SET runtime = excluded.runtime,
                                  code_run_id = NULL,
                                  validation_status = 'PENDING',
                                  failure_code = NULL,
                                  failure_message = NULL,
                                  updated_at = excluded.updated_at
                    """,
                    (
                        _id("variant"),
                        project_id,
                        solution_id,
                        channel,
                        runtime,
                        now,
                        now,
                    ),
                )
            self._queue_job(
                conn,
                project_id,
                solution_id,
                CreatorJobKind.DIGITAL_PROTOTYPE,
            )
            if payload.structure.strip() not in {"", "不需要结构", "不适用"}:
                self._queue_job(
                    conn,
                    project_id,
                    solution_id,
                    CreatorJobKind.STRUCTURE_DRAFT,
                )

    def _queue_job(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        solution_revision_id: str,
        kind: CreatorJobKind,
    ) -> str:
        job_id = _id("cjob")
        now = _now()
        conn.execute(
            """
            INSERT INTO creator_jobs (
              id, project_id, solution_revision_id, kind, status, progress,
              message, result_json, created_at, updated_at, started_at, completed_at
            ) VALUES (?, ?, ?, ?, 'QUEUED', 0, NULL, NULL, ?, ?, NULL, NULL)
            ON CONFLICT(solution_revision_id, kind) DO NOTHING
            """,
            (job_id, project_id, solution_revision_id, kind.value, now, now),
        )
        row = conn.execute(
            """
            SELECT id, status FROM creator_jobs
            WHERE solution_revision_id = ? AND kind = ?
            """,
            (solution_revision_id, kind.value),
        ).fetchone()
        assert row is not None
        persisted_job_id = str(row["id"])
        if persisted_job_id == job_id:
            self._append_event(
                conn,
                project_id,
                "JOB",
                {
                    "jobId": persisted_job_id,
                    "kind": kind.value,
                    "status": str(row["status"]),
                    "solutionRevisionId": solution_revision_id,
                },
            )
        return persisted_job_id

    def _generate_project_book(
        self,
        conn: sqlite3.Connection,
        project_id: str,
    ) -> None:
        goal = self._goal_revision(conn, project_id, "CONFIRMED")
        solution = self._solution_revision(conn, project_id, "CONFIRMED")
        if goal is None or solution is None:
            raise CreatorError(
                "CREATOR_CONFIRMED_SOLUTION_REQUIRED",
                "请先确认当前作品目标和实施方案，再生成立项书。",
                status_code=409,
            )
        scenarios = self._scenarios(conn, project_id)
        previous = conn.execute(
            """
            SELECT payload_json FROM creator_events
            WHERE project_id = ? AND event_type = 'PROJECT_BOOK_GENERATED'
            ORDER BY created_at DESC, id DESC LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        previous_payload = (
            json.loads(str(previous["payload_json"])) if previous is not None else {}
        )
        revision = int(previous_payload.get("revision", 0)) + 1
        now = _now()
        sections = [
            {
                "id": "goal",
                "title": "项目目标",
                "content": (
                    f"{goal.statement}\n\n可观察行为：{goal.observable_behavior}"
                ),
            },
            {
                "id": "constraints",
                "title": "约束与成功标准",
                "content": "\n".join(
                    [
                        *[f"约束：{item}" for item in goal.constraints],
                        *[f"成功标准：{item}" for item in goal.success_criteria],
                    ]
                )
                or "暂无额外约束。",
            },
            {
                "id": "solution",
                "title": "实施方案",
                "content": (
                    f"{solution.summary}\n\n工作逻辑：{solution.logic}\n\n"
                    f"硬件与供电：{solution.hardware}\n\n"
                    f"软件与运行时：{solution.software}"
                ),
            },
            {
                "id": "prototype",
                "title": "结构、仿真与安全",
                "content": (
                    f"结构：{solution.structure}\n\n"
                    f"仿真：{solution.simulation}\n\n"
                    f"安全：{solution.safety}"
                ),
            },
            {
                "id": "acceptance",
                "title": "验收场景",
                "content": "\n".join(
                    f"{index}. {scenario.title}：{scenario.simulation_expected}"
                    for index, scenario in enumerate(scenarios, start=1)
                )
                or "等待方案补充验收场景。",
            },
        ]
        self._append_event(
            conn,
            project_id,
            "PROJECT_BOOK_GENERATED",
            {
                "bookId": _id("project_book"),
                "revision": revision,
                "goalRevisionId": goal.id,
                "solutionRevisionId": solution.id,
                "sections": sections,
                "generatedAt": now,
            },
        )

    def _assert_evidence_prerequisite(
        self, conn: sqlite3.Connection, project_id: str, kind: EvidenceKind
    ) -> None:
        required: EvidenceKind | None = {
            EvidenceKind.STATIC_VALIDATION: EvidenceKind.GOAL_CONFIRMATION,
            EvidenceKind.SIMULATION: EvidenceKind.STATIC_VALIDATION,
            EvidenceKind.DEVICE_CONNECTION: EvidenceKind.SIMULATION,
            EvidenceKind.DEPLOYMENT: EvidenceKind.DEVICE_CONNECTION,
            EvidenceKind.PHYSICAL_BEHAVIOR: EvidenceKind.DEPLOYMENT,
            EvidenceKind.REPRODUCTION: EvidenceKind.USER_ACCEPTANCE,
        }.get(kind)
        if kind is EvidenceKind.STATIC_VALIDATION and not self._confirmed_solution(
            conn, project_id
        ):
            raise CreatorError(
                "CREATOR_SOLUTION_REQUIRED", "请先确认完整实施方案。", status_code=409
            )
        if kind is EvidenceKind.STRUCTURE_CHECK and not self._confirmed_solution(
            conn, project_id
        ):
            raise CreatorError(
                "CREATOR_SOLUTION_REQUIRED", "请先确认完整实施方案。", status_code=409
            )
        if required is not None and not self._current_pass(conn, project_id, required):
            raise CreatorError(
                "CREATOR_EVIDENCE_PREREQUISITE_MISSING",
                f"缺少当前有效的 {required.value} 证据。",
                status_code=409,
            )

    def _record_evidence(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        kind: EvidenceKind,
        payload: EvidenceCommandPayload,
    ) -> None:
        bindings = self._current_bindings(conn, project_id)
        bindings.update(payload.bindings)
        conn.execute(
            """
            UPDATE creator_evidence SET status = 'SUPERSEDED'
            WHERE project_id = ? AND kind = ? AND status IN ('CURRENT', 'FAILED')
            """,
            (project_id, kind.value),
        )
        self._insert_evidence(
            conn,
            project_id,
            kind,
            passed=payload.passed,
            summary=payload.summary,
            source_id=payload.source_id,
            bindings=bindings,
        )

    def _insert_evidence(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        kind: EvidenceKind,
        *,
        passed: bool,
        summary: str,
        source_id: str | None,
        bindings: dict[str, str],
    ) -> None:
        now = _now()
        evidence_id = _id("evidence")
        conn.execute(
            """
            INSERT INTO creator_evidence (
              id, project_id, kind, status, passed, summary, bindings_json,
              source_id, recorded_at, invalidated_at, invalidation_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
            """,
            (
                evidence_id,
                project_id,
                kind.value,
                EvidenceStatus.CURRENT.value if passed else EvidenceStatus.FAILED.value,
                1 if passed else 0,
                summary,
                _dump(bindings),
                source_id,
                now,
            ),
        )
        self._append_event(
            conn,
            project_id,
            "EVIDENCE",
            {"evidenceId": evidence_id, "kind": kind.value, "passed": passed},
        )

    def _invalidate(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        reason: str,
        *,
        exclude: set[EvidenceKind] | None = None,
    ) -> None:
        excluded = {item.value for item in (exclude or set())}
        rows = conn.execute(
            """
            SELECT id, kind FROM creator_evidence
            WHERE project_id = ? AND status = 'CURRENT'
            """,
            (project_id,),
        ).fetchall()
        now = _now()
        for row in rows:
            if str(row["kind"]) in excluded:
                continue
            conn.execute(
                """
                UPDATE creator_evidence
                SET status = 'STALE', invalidated_at = ?, invalidation_reason = ?
                WHERE id = ?
                """,
                (now, reason, str(row["id"])),
            )

    def _project(self, conn: sqlite3.Connection, project_id: str) -> CreatorWorkspace:
        project = conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise CreatorError("CREATOR_WORK_NOT_FOUND", "作品不存在。", status_code=404)
        state = conn.execute(
            "SELECT * FROM creator_work_state WHERE project_id = ?", (project_id,)
        ).fetchone()
        assert state is not None
        self._sync_confirmed_legacy_plan(
            conn,
            project_id,
            initial_idea=str(project["initial_idea"]),
        )
        state = conn.execute(
            "SELECT * FROM creator_work_state WHERE project_id = ?", (project_id,)
        ).fetchone()
        assert state is not None
        confirmed_goal = self._goal_revision(conn, project_id, "CONFIRMED")
        draft_goal = self._goal_revision(conn, project_id, "DRAFT")
        if confirmed_goal is None and draft_goal is None:
            draft_goal = self._legacy_goal(project_id, str(project["initial_idea"]))
        goal = confirmed_goal or draft_goal
        confirmed_solution = self._solution_revision(conn, project_id, "CONFIRMED")
        draft_solution = self._solution_revision(conn, project_id, "DRAFT")
        if confirmed_solution is None and draft_solution is None:
            legacy_solution = self._solution(conn, project_id)
            if legacy_solution is not None:
                if legacy_solution.status == "CONFIRMED":
                    confirmed_solution = legacy_solution
                else:
                    draft_solution = legacy_solution
        solution = confirmed_solution or draft_solution
        scenarios = self._scenarios(conn, project_id)
        jobs = self._jobs(conn, project_id)
        code_variants = self._code_variants(conn, project_id)
        parameter_revisions = self._parameter_revisions(conn, project_id)
        self._refresh_stale_evidence(conn, project_id)
        evidence = self._evidence(conn, project_id)
        current_kinds = {
            item.kind
            for item in evidence
            if item.status is EvidenceStatus.CURRENT and item.passed
        }
        level = self._level(goal, current_kinds)
        phase = self._phase(goal, solution, current_kinds)
        stage = self._stage(phase)
        next_action = self._next_action(goal, solution, current_kinds, level)
        return CreatorWorkspace(
            workId=project_id,
            projectId=project_id,
            projectVersion=self._current_version(conn, project_id),
            name=str(project["name"]),
            initialIdea=str(project["initial_idea"]),
            phase=phase,
            activeStage=stage,
            verificationLevel=level,
            verificationLabel=_LEVEL_LABELS[level],
            stages=self._stage_summaries(level, stage, solution, current_kinds),
            confirmedGoal=confirmed_goal,
            draftGoal=draft_goal,
            confirmedSolution=confirmed_solution,
            draftSolution=draft_solution,
            projectBookProjection=self._project_book_projection(
                conn, project_id, confirmed_goal, confirmed_solution
            ),
            conversationProjectionStatus=self._conversation_projection_status(
                conn, project_id
            ),
            currentGoal=goal,
            currentSolution=solution,
            acceptanceScenarios=scenarios,
            jobs=jobs,
            codeVariants=code_variants,
            parameterRevisions=parameter_revisions,
            evidence=evidence,
            nextAction=next_action,
            archivedAt=project["archived_at"],
            updatedAt=max(
                str(project["updated_at"]),
                str(state["updated_at"]),
                *(item.updated_at for item in jobs),
                *(item.created_at for item in parameter_revisions),
            ),
            legacy=str(state["origin"]) == "LEGACY",
            needsOrganization=str(state["origin"]) == "LEGACY"
            and not self._confirmed_goal(conn, project_id),
        )

    def _sync_confirmed_legacy_plan(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        *,
        initial_idea: str,
    ) -> None:
        """Project a confirmed chat-era plan into Creator exactly once.

        Creator and the established three-expert conversation share the same
        project. A confirmed recommendation/proposal therefore cannot remain a
        draft goal in Creator or require a second user confirmation.
        """

        creator_goal = self._confirmed_goal(conn, project_id)
        creator_solution = self._confirmed_solution(conn, project_id)
        if creator_goal is not None and creator_solution is not None:
            return

        legacy_solution = conn.execute(
            """
            SELECT * FROM solutions
            WHERE project_id = ? AND status = 'CONFIRMED'
            ORDER BY version DESC, confirmed_at DESC LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        approved_proposal = conn.execute(
            """
            SELECT * FROM proposals
            WHERE project_id = ? AND status = 'APPROVED'
            ORDER BY version DESC, confirmed_at DESC LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        if legacy_solution is None and approved_proposal is None:
            return

        legacy_sections = _section_map(
            legacy_solution["sections_json"] if legacy_solution is not None else None
        )
        proposal_sections = _section_map(
            approved_proposal["sections_json"] if approved_proposal is not None else None
        )
        source_id = str(
            approved_proposal["id"]
            if approved_proposal is not None
            else legacy_solution["id"]
        )
        source_version = int(
            approved_proposal["version"]
            if approved_proposal is not None
            else legacy_solution["version"]
        )
        source_created_at = str(
            approved_proposal["created_at"]
            if approved_proposal is not None
            else legacy_solution["created_at"]
        )
        source_confirmed_at = str(
            approved_proposal["confirmed_at"]
            if approved_proposal is not None
            else legacy_solution["confirmed_at"]
        )
        goal_summary = _first_text(
            legacy_sections,
            "goal",
            fallback=_first_text(
                proposal_sections,
                "project_overview",
                fallback=initial_idea,
            ),
        )

        changed = False
        if creator_goal is None:
            conn.execute(
                """
                UPDATE creator_goal_revisions SET status = 'SUPERSEDED'
                WHERE project_id = ? AND status IN ('DRAFT', 'CONFIRMED')
                """,
                (project_id,),
            )
            goal_id = _id("goal")
            goal_revision = max(
                source_version,
                self._next_revision(conn, "creator_goal_revisions", project_id),
            )
            success = _first_text(
                proposal_sections,
                "risks_acceptance",
                fallback=goal_summary,
            )
            constraints = _first_text(
                proposal_sections,
                "requirements",
                fallback=_first_text(legacy_sections, "risks", fallback=""),
            )
            conn.execute(
                """
                INSERT INTO creator_goal_revisions (
                  id, project_id, revision, status, statement, observable_behavior,
                  constraints_json, success_criteria_json, source_message_id,
                  created_at, confirmed_at, source_type
                ) VALUES (?, ?, ?, 'CONFIRMED', ?, ?, ?, ?, ?, ?, ?,
                          'LEGACY_PROJECTION')
                """,
                (
                    goal_id,
                    project_id,
                    goal_revision,
                    _clip(initial_idea or goal_summary, 4000),
                    _clip(goal_summary, 4000),
                    _dump([_clip(constraints, 4000)] if constraints else []),
                    _dump([_clip(success, 4000)]),
                    f"legacy-plan:{source_id}",
                    source_created_at,
                    source_confirmed_at,
                ),
            )
            self._invalidate(conn, project_id, "已确认立项书同步了作品目标。")
            self._insert_evidence(
                conn,
                project_id,
                EvidenceKind.GOAL_CONFIRMATION,
                passed=True,
                summary=f"已从确认的立项书/方案 v{source_version} 同步作品目标。",
                source_id=source_id,
                bindings={"goalRevisionId": goal_id, "sourcePlanId": source_id},
            )
            changed = True

        if creator_solution is None:
            conn.execute(
                """
                UPDATE creator_solution_revisions SET status = 'SUPERSEDED'
                WHERE project_id = ? AND status IN ('DRAFT', 'CONFIRMED')
                """,
                (project_id,),
            )
            solution_id = _id("csolution")
            solution_revision = max(
                source_version,
                self._next_revision(conn, "creator_solution_revisions", project_id),
            )
            proposal_implementation = _first_text(
                proposal_sections,
                "implementation_plan",
                fallback=_first_text(legacy_sections, "implementation_steps", fallback=""),
            )
            hardware_software_structure = _first_text(
                proposal_sections,
                "hardware_software_structure",
                fallback=goal_summary,
            )
            safety = _first_text(
                proposal_sections,
                "risks_acceptance",
                fallback=_first_text(legacy_sections, "risks", fallback=goal_summary),
            )
            values = {
                "summary": goal_summary,
                "logic": _first_text(
                    legacy_sections,
                    "functional_logic",
                    "logic",
                    fallback=_first_text(
                        proposal_sections,
                        "requirements",
                        fallback=goal_summary,
                    ),
                ),
                "hardware": _first_text(
                    legacy_sections,
                    "hardware",
                    fallback=hardware_software_structure,
                ),
                "software": _first_text(
                    legacy_sections,
                    "software",
                    fallback=hardware_software_structure,
                ),
                "structure": _first_text(
                    legacy_sections,
                    "structure",
                    fallback=hardware_software_structure,
                ),
                "simulation": proposal_implementation or goal_summary,
                "safety": safety,
            }
            conn.execute(
                """
                INSERT INTO creator_solution_revisions (
                  id, project_id, revision, status, summary, logic, hardware, software,
                  structure, simulation, safety, bom_json, io_map_json,
                  source_proposal_id, created_at, confirmed_at, source_type
                ) VALUES (?, ?, ?, 'CONFIRMED', ?, ?, ?, ?, ?, ?, ?, '[]', '[]',
                          ?, ?, ?, 'LEGACY_PROJECTION')
                """,
                (
                    solution_id,
                    project_id,
                    solution_revision,
                    *(_clip(values[key], 12000) for key in (
                        "summary",
                        "logic",
                        "hardware",
                        "software",
                        "structure",
                        "simulation",
                        "safety",
                    )),
                    str(approved_proposal["id"]) if approved_proposal is not None else None,
                    source_created_at,
                    source_confirmed_at,
                ),
            )
            conn.execute(
                "DELETE FROM creator_acceptance_scenarios WHERE project_id = ?",
                (project_id,),
            )
            conn.execute(
                """
                INSERT INTO creator_acceptance_scenarios (
                  id, project_id, solution_revision_id, title, required,
                  simulation_expected, physical_expected, created_at
                ) VALUES (?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (
                    _id("scenario"),
                    project_id,
                    solution_id,
                    "按已确认立项书完成核心行为",
                    _clip(proposal_implementation or goal_summary, 2000),
                    _clip(safety or goal_summary, 2000),
                    source_created_at,
                ),
            )
            self._invalidate(
                conn,
                project_id,
                "已确认立项书同步了当前方案。",
                exclude={EvidenceKind.GOAL_CONFIRMATION},
            )
            changed = True

        if changed:
            next_version = self._current_version(conn, project_id) + 1
            now = _now()
            conn.execute(
                """
                UPDATE creator_work_state
                SET creator_version = ?, updated_at = ? WHERE project_id = ?
                """,
                (next_version, now, project_id),
            )
            self._append_event(
                conn,
                project_id,
                "PROJECTION",
                {
                    "source": "CONFIRMED_LEGACY_PLAN",
                    "sourcePlanId": source_id,
                    "sourcePlanVersion": source_version,
                },
            )

    def _goal_revision(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        status: str,
    ) -> GoalRevision | None:
        row = conn.execute(
            """
            SELECT * FROM creator_goal_revisions
            WHERE project_id = ? AND status = ?
            ORDER BY revision DESC LIMIT 1
            """,
            (project_id, status),
        ).fetchone()
        return self._goal_model(row) if row is not None else None

    def _legacy_goal(
        self, project_id: str, initial_idea: str
    ) -> GoalRevision | None:
        if not initial_idea.strip():
            return None
        return GoalRevision(
            id=f"legacy-goal:{project_id}",
            workId=project_id,
            revision=1,
            status="DRAFT",
            sourceType=CreatorRevisionSourceType.LEGACY_PROJECTION,
            sourceMessageId=None,
            sourceTurnId=None,
            baseRevisionId=None,
            projectionReceiptId=None,
            statement=initial_idea,
            observableBehavior="待整理",
            constraints=[],
            successCriteria=[],
            createdAt="1970-01-01T00:00:00+00:00",
            confirmedAt=None,
        )

    def _goal_model(self, row: sqlite3.Row) -> GoalRevision:
        return GoalRevision(
            id=str(row["id"]),
            workId=str(row["project_id"]),
            revision=int(row["revision"]),
            status=str(row["status"]),
            sourceType=str(row["source_type"]),
            sourceMessageId=row["source_message_id"],
            sourceTurnId=row["source_turn_id"],
            baseRevisionId=row["base_revision_id"],
            projectionReceiptId=row["projection_receipt_id"],
            statement=str(row["statement"]),
            observableBehavior=str(row["observable_behavior"]),
            constraints=_load_list(row["constraints_json"]),
            successCriteria=_load_list(row["success_criteria_json"]),
            createdAt=str(row["created_at"]),
            confirmedAt=row["confirmed_at"],
        )

    def _goal(
        self, conn: sqlite3.Connection, project_id: str, initial_idea: str
    ) -> GoalRevision | None:
        return (
            self._goal_revision(conn, project_id, "CONFIRMED")
            or self._goal_revision(conn, project_id, "DRAFT")
            or self._legacy_goal(project_id, initial_idea)
        )

    def _solution_revision(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        status: str,
    ) -> SolutionRevision | None:
        row = conn.execute(
            """
            SELECT * FROM creator_solution_revisions
            WHERE project_id = ? AND status = ?
            ORDER BY revision DESC LIMIT 1
            """,
            (project_id, status),
        ).fetchone()
        return self._solution_model(row) if row is not None else None

    def _solution(
        self, conn: sqlite3.Connection, project_id: str
    ) -> SolutionRevision | None:
        row = conn.execute(
            """
            SELECT * FROM creator_solution_revisions
            WHERE project_id = ? AND status IN ('CONFIRMED', 'DRAFT')
            ORDER BY CASE status WHEN 'CONFIRMED' THEN 0 ELSE 1 END, revision DESC
            LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        if row is not None:
            return self._solution_model(row)
        legacy = conn.execute(
            """
            SELECT * FROM solutions
            WHERE project_id = ? AND status IN ('DRAFT', 'CONFIRMED')
            ORDER BY version DESC LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        if legacy is None:
            return None
        sections = json.loads(str(legacy["sections_json"]))
        by_id = {str(item.get("id", "")): str(item.get("content", "")) for item in sections}
        summary = next((str(item.get("content", "")) for item in sections if item.get("content")), "历史方案")
        return SolutionRevision(
            id=f"legacy-solution:{legacy['id']}",
            workId=project_id,
            revision=int(legacy["version"]),
            status="CONFIRMED" if str(legacy["status"]) == "CONFIRMED" else "DRAFT",
            sourceType=CreatorRevisionSourceType.LEGACY_PROJECTION,
            sourceMessageId=None,
            sourceTurnId=None,
            baseRevisionId=None,
            projectionReceiptId=None,
            summary=summary,
            logic=by_id.get("logic", summary),
            hardware=by_id.get("hardware", "待整理"),
            software=by_id.get("software", "待整理"),
            structure=by_id.get("structure", "待整理"),
            simulation=by_id.get("simulation", "待整理"),
            safety=by_id.get("safety", "待整理"),
            bom=[],
            ioMap=[],
            createdAt=str(legacy["created_at"]),
            confirmedAt=legacy["confirmed_at"],
        )

    def _solution_model(self, row: sqlite3.Row) -> SolutionRevision:
        return SolutionRevision(
            id=str(row["id"]),
            workId=str(row["project_id"]),
            revision=int(row["revision"]),
            status=str(row["status"]),
            sourceType=str(row["source_type"]),
            sourceMessageId=row["source_message_id"],
            sourceTurnId=row["source_turn_id"],
            baseRevisionId=row["base_revision_id"],
            projectionReceiptId=row["projection_receipt_id"],
            summary=str(row["summary"]),
            logic=str(row["logic"]),
            hardware=str(row["hardware"]),
            software=str(row["software"]),
            structure=str(row["structure"]),
            simulation=str(row["simulation"]),
            safety=str(row["safety"]),
            bom=json.loads(str(row["bom_json"])),
            ioMap=json.loads(str(row["io_map_json"])),
            createdAt=str(row["created_at"]),
            confirmedAt=row["confirmed_at"],
        )

    def _project_book_projection(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        goal: GoalRevision | None,
        solution: SolutionRevision | None,
    ) -> ProjectBookProjection:
        row = conn.execute(
            """
            SELECT payload_json, created_at FROM creator_events
            WHERE project_id = ? AND event_type = 'PROJECT_BOOK_GENERATED'
            ORDER BY created_at DESC, id DESC LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        if row is None:
            return ProjectBookProjection(
                status="EMPTY",
                bookId=None,
                revision=None,
                goalRevisionId=goal.id if goal is not None else None,
                solutionRevisionId=solution.id if solution is not None else None,
                sections=[],
                generatedAt=None,
                updatedAt=None,
            )
        payload = json.loads(str(row["payload_json"]))
        current = (
            goal is not None
            and solution is not None
            and payload.get("goalRevisionId") == goal.id
            and payload.get("solutionRevisionId") == solution.id
        )
        return ProjectBookProjection(
            status="CURRENT" if current else "STALE",
            bookId=payload.get("bookId"),
            revision=payload.get("revision"),
            goalRevisionId=payload.get("goalRevisionId"),
            solutionRevisionId=payload.get("solutionRevisionId"),
            sections=payload.get("sections", []),
            generatedAt=payload.get("generatedAt"),
            updatedAt=str(row["created_at"]),
        )

    def _conversation_projection_status(
        self,
        conn: sqlite3.Connection,
        project_id: str,
    ) -> ConversationProjectionStatus:
        row = conn.execute(
            """
            SELECT * FROM creator_projection_receipts
            WHERE project_id = ? AND source_type = 'CONVERSATION'
            ORDER BY created_at DESC, id DESC LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        if row is None:
            return ConversationProjectionStatus(
                status="IDLE",
                receiptId=None,
                sourceMessageId=None,
                message=None,
            )
        receipt_status = str(row["status"])
        status = {
            "APPLIED": "CURRENT",
            "DUPLICATE": "CURRENT",
            "CONFLICT": "CONFLICT",
            "REJECTED": "FAILED",
        }[receipt_status]
        return ConversationProjectionStatus(
            status=status,
            receiptId=str(row["id"]),
            sourceMessageId=str(row["source_message_id"]),
            message=row["message"],
        )

    def _projection_receipt_model(
        self, row: sqlite3.Row
    ) -> CreatorProjectionReceipt:
        return CreatorProjectionReceipt(
            id=str(row["id"]),
            workId=str(row["project_id"]),
            sourceType=str(row["source_type"]),
            sourceMessageId=str(row["source_message_id"]),
            sourceTurnId=row["source_turn_id"],
            draftHash=str(row["draft_hash"]),
            status=str(row["status"]),
            goalRevisionId=row["goal_revision_id"],
            solutionRevisionId=row["solution_revision_id"],
            message=row["message"],
            createdAt=str(row["created_at"]),
        )

    def _scenarios(
        self, conn: sqlite3.Connection, project_id: str
    ) -> list[AcceptanceScenario]:
        rows = conn.execute(
            """
            SELECT * FROM creator_acceptance_scenarios
            WHERE project_id = ? ORDER BY created_at ASC, id ASC
            """,
            (project_id,),
        ).fetchall()
        return [
            AcceptanceScenario(
                id=str(row["id"]),
                workId=project_id,
                title=str(row["title"]),
                required=bool(row["required"]),
                simulationExpected=str(row["simulation_expected"]),
                physicalExpected=str(row["physical_expected"]),
                createdAt=str(row["created_at"]),
            )
            for row in rows
        ]

    def _jobs(self, conn: sqlite3.Connection, project_id: str) -> list[CreatorJob]:
        rows = conn.execute(
            """
            SELECT * FROM creator_jobs
            WHERE project_id = ? ORDER BY created_at DESC, id DESC
            """,
            (project_id,),
        ).fetchall()
        result: list[CreatorJob] = []
        for row in rows:
            raw_result = (
                json.loads(str(row["result_json"]))
                if row["result_json"] is not None
                else None
            )
            result.append(
                CreatorJob(
                    id=str(row["id"]),
                    workId=project_id,
                    solutionRevisionId=str(row["solution_revision_id"]),
                    kind=str(row["kind"]),
                    status=str(row["status"]),
                    progress=int(row["progress"]),
                    message=row["message"],
                    result=raw_result if isinstance(raw_result, dict) else None,
                    createdAt=str(row["created_at"]),
                    updatedAt=str(row["updated_at"]),
                    startedAt=row["started_at"],
                    completedAt=row["completed_at"],
                )
            )
        return result

    def _code_variants(
        self, conn: sqlite3.Connection, project_id: str
    ) -> list[CodeVariantBinding]:
        rows = conn.execute(
            """
            SELECT * FROM creator_code_variant_bindings
            WHERE project_id = ?
            ORDER BY CASE deployment_channel
              WHEN 'USB_SERIAL' THEN 0 ELSE 1 END, updated_at DESC
            """,
            (project_id,),
        ).fetchall()
        return [
            CodeVariantBinding(
                id=str(row["id"]),
                workId=project_id,
                solutionRevisionId=str(row["solution_revision_id"]),
                deploymentChannel=str(row["deployment_channel"]),
                runtime=str(row["runtime"]),
                codeRunId=row["code_run_id"],
                devicePackageId=row["device_package_id"],
                validationStatus=str(row["validation_status"]),
                failureCode=row["failure_code"],
                failureMessage=row["failure_message"],
                createdAt=str(row["created_at"]),
                updatedAt=str(row["updated_at"]),
            )
            for row in rows
        ]

    def _parameter_revisions(
        self, conn: sqlite3.Connection, project_id: str
    ) -> list[ParameterRevision]:
        rows = conn.execute(
            """
            SELECT * FROM device_parameter_sets
            WHERE project_id = ? ORDER BY created_at DESC, revision DESC, id DESC
            """,
            (project_id,),
        ).fetchall()
        return [
            ParameterRevision(
                id=str(row["id"]),
                workId=project_id,
                boardId=str(row["board_id"]),
                profileRevision=str(row["profile_revision"]),
                revision=int(row["revision"]),
                label=str(row["label"]),
                values=json.loads(str(row["values_json"])),
                createdAt=str(row["created_at"]),
            )
            for row in rows
        ]

    def _evidence(
        self, conn: sqlite3.Connection, project_id: str
    ) -> list[EvidenceRecord]:
        rows = conn.execute(
            """
            SELECT * FROM creator_evidence
            WHERE project_id = ? ORDER BY recorded_at DESC, id DESC
            """,
            (project_id,),
        ).fetchall()
        return [
            EvidenceRecord(
                id=str(row["id"]),
                workId=project_id,
                kind=str(row["kind"]),
                status=str(row["status"]),
                passed=bool(row["passed"]),
                summary=str(row["summary"]),
                bindings=json.loads(str(row["bindings_json"])),
                sourceId=row["source_id"],
                recordedAt=str(row["recorded_at"]),
                invalidatedAt=row["invalidated_at"],
                invalidationReason=row["invalidation_reason"],
            )
            for row in rows
        ]

    def _level(
        self,
        goal: GoalRevision | None,
        current_kinds: set[EvidenceKind],
    ) -> VerificationLevel:
        if goal is None or goal.status != "CONFIRMED":
            return VerificationLevel.UNVERIFIED
        level = VerificationLevel.GOAL_CONFIRMED
        ladder = (
            (EvidenceKind.STATIC_VALIDATION, VerificationLevel.STATIC_VALIDATED),
            (EvidenceKind.SIMULATION, VerificationLevel.SIMULATION_PASSED),
            (EvidenceKind.DEVICE_CONNECTION, VerificationLevel.DEVICE_CONNECTED),
            (EvidenceKind.PHYSICAL_BEHAVIOR, VerificationLevel.PHYSICAL_PASSED),
            (EvidenceKind.USER_ACCEPTANCE, VerificationLevel.USER_ACCEPTED),
        )
        for kind, candidate in ladder:
            if kind not in current_kinds:
                break
            level = candidate
        return level

    def _phase(
        self,
        goal: GoalRevision | None,
        solution: SolutionRevision | None,
        current: set[EvidenceKind],
    ) -> CreatorPhase:
        if EvidenceKind.REPRODUCTION in current:
            return CreatorPhase.DELIVERED
        if EvidenceKind.USER_ACCEPTANCE in current:
            return CreatorPhase.ACCEPTED
        if EvidenceKind.PHYSICAL_BEHAVIOR in current:
            return CreatorPhase.PHYSICAL_PASSED
        if EvidenceKind.DEPLOYMENT in current:
            return CreatorPhase.DEPLOYED
        if EvidenceKind.DEVICE_CONNECTION in current:
            return CreatorPhase.DEVICE_CONNECTED
        if EvidenceKind.SIMULATION in current:
            return CreatorPhase.SIMULATION_PASSED
        if EvidenceKind.STATIC_VALIDATION in current:
            return CreatorPhase.SIMULATING
        if solution is not None and solution.status == "CONFIRMED":
            return CreatorPhase.DIGITAL_BUILDING
        if solution is not None:
            return CreatorPhase.SOLUTION_REVIEW
        if goal is not None and goal.status == "CONFIRMED":
            return CreatorPhase.SOLUTION_REVIEW
        if goal is not None:
            return CreatorPhase.GOAL_REVIEW
        return CreatorPhase.IDEA

    def _stage(self, phase: CreatorPhase) -> CreatorStage:
        if phase in {CreatorPhase.IDEA, CreatorPhase.GOAL_REVIEW, CreatorPhase.SOLUTION_REVIEW}:
            return CreatorStage.IDEA_SOLUTION
        if phase in {
            CreatorPhase.DIGITAL_BUILDING,
            CreatorPhase.SIMULATING,
            CreatorPhase.SIMULATION_PASSED,
        }:
            return CreatorStage.DIGITAL_PROTOTYPE
        return CreatorStage.PHYSICAL_RUN

    def _next_action(
        self,
        goal: GoalRevision | None,
        solution: SolutionRevision | None,
        current: set[EvidenceKind],
        level: VerificationLevel,
    ) -> CreatorNextAction:
        if solution is None or solution.status != "CONFIRMED":
            return CreatorNextAction(
                id="confirm-solution",
                label="确认方案并建立数字原型",
                command=CreatorCommand.CONFIRM_SOLUTION,
                stage=CreatorStage.IDEA_SOLUTION,
                enabled=solution is not None and goal is not None,
                blockedReason=(
                    None
                    if solution is not None and goal is not None
                    else "问题引导师正在自动形成推荐方案。"
                ),
                riskLevel="LOW",
            )
        if EvidenceKind.STATIC_VALIDATION not in current:
            return CreatorNextAction(
                id="static-validation",
                label="检查方案并建立数字原型",
                command=CreatorCommand.RECORD_STATIC_VALIDATION,
                stage=CreatorStage.DIGITAL_PROTOTYPE,
                enabled=True,
                blockedReason=None,
                riskLevel="LOW",
            )
        if EvidenceKind.SIMULATION not in current:
            return CreatorNextAction(
                id="run-simulation",
                label="运行必需仿真场景",
                command=CreatorCommand.RECORD_SIMULATION,
                stage=CreatorStage.DIGITAL_PROTOTYPE,
                enabled=True,
                blockedReason=None,
                riskLevel="LOW",
            )
        if EvidenceKind.DEVICE_CONNECTION not in current:
            return CreatorNextAction(
                id="connect-device",
                label="连接并确认真实设备",
                command=CreatorCommand.RECORD_DEVICE_CONNECTION,
                stage=CreatorStage.PHYSICAL_RUN,
                enabled=level >= VerificationLevel.SIMULATION_PASSED,
                blockedReason=None,
                riskLevel="HIGH",
            )
        if EvidenceKind.DEPLOYMENT not in current:
            return CreatorNextAction(
                id="deploy-device",
                label="运行到设备",
                command=CreatorCommand.RECORD_DEPLOYMENT,
                stage=CreatorStage.PHYSICAL_RUN,
                enabled=True,
                blockedReason=None,
                riskLevel="HIGH",
            )
        if EvidenceKind.PHYSICAL_BEHAVIOR not in current:
            return CreatorNextAction(
                id="physical-validation",
                label="运行真机验收场景",
                command=CreatorCommand.RECORD_PHYSICAL_BEHAVIOR,
                stage=CreatorStage.PHYSICAL_RUN,
                enabled=True,
                blockedReason=None,
                riskLevel="HIGH",
            )
        if EvidenceKind.USER_ACCEPTANCE not in current:
            return CreatorNextAction(
                id="accept-work",
                label="确认作品验收",
                command=CreatorCommand.ACCEPT_WORK,
                stage=CreatorStage.PHYSICAL_RUN,
                enabled=True,
                blockedReason=None,
                riskLevel="MEDIUM",
            )
        if EvidenceKind.REPRODUCTION not in current:
            return CreatorNextAction(
                id="reproduce-work",
                label="生成并复现交付包",
                command=CreatorCommand.RECORD_REPRODUCTION,
                stage=CreatorStage.PHYSICAL_RUN,
                enabled=True,
                blockedReason=None,
                riskLevel="LOW",
            )
        return CreatorNextAction(
            id="delivered",
            label="作品已完成并可复现",
            command=None,
            stage=CreatorStage.PHYSICAL_RUN,
            enabled=False,
            blockedReason=None,
            riskLevel="LOW",
        )

    def _stage_summaries(
        self,
        level: VerificationLevel,
        active: CreatorStage,
        solution: SolutionRevision | None,
        current: set[EvidenceKind],
    ) -> list[CreatorStageSummary]:
        structure_not_applicable = solution is not None and solution.structure.strip() in {
            "",
            "不需要结构",
            "无",
        }
        result: list[CreatorStageSummary] = []
        definitions = (
            (CreatorStage.IDEA_SOLUTION, "创意与方案", level >= 1, "目标与当前方案"),
            (CreatorStage.DIGITAL_PROTOTYPE, "数字原型", level >= 3, "仿真、参数与日志"),
            (CreatorStage.STRUCTURE_3D, "3D 结构", EvidenceKind.STRUCTURE_CHECK in current, "结构版本与制造检查"),
            (CreatorStage.PHYSICAL_RUN, "实物运行", level >= 5, "连接、部署与真机验证"),
        )
        for stage, label, passed, detail in definitions:
            if stage is CreatorStage.STRUCTURE_3D and structure_not_applicable:
                status = "NOT_APPLICABLE"
                detail = "当前方案不需要独立结构件。"
            elif passed:
                status = "PASSED"
            elif stage is active:
                status = "ACTIVE"
            elif stage is CreatorStage.PHYSICAL_RUN and level < 3:
                status = "BLOCKED"
                detail = "功能仿真通过后才解锁真实操作。"
            else:
                status = "READY" if stage is CreatorStage.STRUCTURE_3D else "NOT_STARTED"
            result.append(
                CreatorStageSummary(stage=stage, label=label, status=status, detail=detail)
            )
        return result

    def _confirmed_goal(self, conn: sqlite3.Connection, project_id: str) -> sqlite3.Row | None:
        return conn.execute(
            """
            SELECT * FROM creator_goal_revisions
            WHERE project_id = ? AND status = 'CONFIRMED'
            ORDER BY revision DESC LIMIT 1
            """,
            (project_id,),
        ).fetchone()

    def _confirmed_solution(
        self, conn: sqlite3.Connection, project_id: str
    ) -> sqlite3.Row | None:
        return conn.execute(
            """
            SELECT * FROM creator_solution_revisions
            WHERE project_id = ? AND status = 'CONFIRMED'
            ORDER BY revision DESC LIMIT 1
            """,
            (project_id,),
        ).fetchone()

    def _current_pass(
        self, conn: sqlite3.Connection, project_id: str, kind: EvidenceKind
    ) -> bool:
        return conn.execute(
            """
            SELECT 1 FROM creator_evidence
            WHERE project_id = ? AND kind = ? AND status = 'CURRENT' AND passed = 1
            LIMIT 1
            """,
            (project_id, kind.value),
        ).fetchone() is not None

    def _current_bindings(
        self, conn: sqlite3.Connection, project_id: str
    ) -> dict[str, str]:
        result: dict[str, str] = {}
        goal = self._confirmed_goal(conn, project_id)
        solution = self._confirmed_solution(conn, project_id)
        if goal is not None:
            result["goalRevisionId"] = str(goal["id"])
        if solution is not None:
            result["solutionRevisionId"] = str(solution["id"])
        scene = conn.execute(
            """
            SELECT revision FROM device_lab_scenes
            WHERE project_id = ? ORDER BY created_at DESC, revision DESC LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        if scene is not None:
            result["sceneRevision"] = str(scene["revision"])
        code = conn.execute(
            """
            SELECT id FROM code_runs
            WHERE project_id = ? AND status = 'ACCEPTED'
            ORDER BY version DESC, updated_at DESC LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        if code is not None:
            result["codeRevisionId"] = str(code["id"])
        structure = conn.execute(
            """
            SELECT id FROM cad_intent_revisions
            WHERE project_id = ? AND status = 'CONFIRMED'
            ORDER BY created_at DESC, id DESC LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        if structure is not None:
            result["structureRevisionId"] = str(structure["id"])
        parameter = conn.execute(
            """
            SELECT id FROM device_parameter_sets
            WHERE project_id = ? ORDER BY revision DESC LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        if parameter is not None:
            result["parameterRevisionId"] = str(parameter["id"])
        return result

    def _refresh_stale_evidence(
        self, conn: sqlite3.Connection, project_id: str
    ) -> None:
        """Invalidate proof that no longer describes the current project inputs.

        Code, scene, structure and parameter revisions may be created by other
        bounded local services. Creator therefore compares immutable evidence
        bindings whenever it projects or mutates a work, instead of trusting a
        once-passed result forever.
        """

        dependency_keys: dict[EvidenceKind, tuple[str, ...]] = {
            EvidenceKind.STATIC_VALIDATION: ("sceneRevision",),
            EvidenceKind.SIMULATION: (
                "sceneRevision",
                "codeRevisionId",
                "parameterRevisionId",
            ),
            EvidenceKind.STRUCTURE_CHECK: ("structureRevisionId",),
            EvidenceKind.DEVICE_CONNECTION: (
                "sceneRevision",
                "codeRevisionId",
                "parameterRevisionId",
            ),
            EvidenceKind.DEPLOYMENT: (
                "sceneRevision",
                "codeRevisionId",
                "parameterRevisionId",
            ),
            EvidenceKind.PHYSICAL_BEHAVIOR: (
                "sceneRevision",
                "codeRevisionId",
                "parameterRevisionId",
                "structureRevisionId",
            ),
            EvidenceKind.USER_ACCEPTANCE: (
                "sceneRevision",
                "codeRevisionId",
                "parameterRevisionId",
                "structureRevisionId",
            ),
            EvidenceKind.REPRODUCTION: (
                "sceneRevision",
                "codeRevisionId",
                "parameterRevisionId",
                "structureRevisionId",
            ),
        }
        current = self._current_bindings(conn, project_id)
        rows = conn.execute(
            """
            SELECT id, kind, bindings_json FROM creator_evidence
            WHERE project_id = ? AND status = 'CURRENT' AND passed = 1
            """,
            (project_id,),
        ).fetchall()
        now = _now()
        labels = {
            "sceneRevision": "digital prototype",
            "codeRevisionId": "code",
            "parameterRevisionId": "parameter set",
            "structureRevisionId": "structure",
        }
        for row in rows:
            try:
                kind = EvidenceKind(str(row["kind"]))
            except ValueError:
                continue
            recorded = json.loads(str(row["bindings_json"]))
            changed = [
                key
                for key in dependency_keys.get(kind, ())
                if (key in current or key in recorded)
                and recorded.get(key) != current.get(key)
            ]
            if not changed:
                continue
            reason = "Dependencies changed: " + ", ".join(labels[key] for key in changed)
            conn.execute(
                """
                UPDATE creator_evidence
                SET status = 'STALE', invalidated_at = ?, invalidation_reason = ?
                WHERE id = ? AND status = 'CURRENT'
                """,
                (now, reason, str(row["id"])),
            )

    def _ensure_work_state(
        self, conn: sqlite3.Connection, project_id: str, *, origin: str
    ) -> None:
        now = _now()
        conn.execute(
            """
            INSERT OR IGNORE INTO creator_work_state (
              project_id, creator_version, origin, last_stage, created_at, updated_at
            ) VALUES (?, 0, ?, 'IDEA_SOLUTION', ?, ?)
            """,
            (project_id, origin, now, now),
        )

    def _current_version(self, conn: sqlite3.Connection, project_id: str) -> int:
        row = conn.execute(
            """
            SELECT MAX(version) AS version FROM project_versions WHERE project_id = ?
            """,
            (project_id,),
        ).fetchone()
        v2_version = int(row["version"] or 0) if row is not None else 0
        creator = conn.execute(
            "SELECT creator_version FROM creator_work_state WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        return max(v2_version, int(creator["creator_version"] if creator else 0))

    def _next_revision(
        self, conn: sqlite3.Connection, table: str, project_id: str
    ) -> int:
        if table not in {"creator_goal_revisions", "creator_solution_revisions"}:
            raise ValueError("Unsupported revision table")
        row = conn.execute(
            f"SELECT COALESCE(MAX(revision), 0) + 1 AS revision FROM {table} WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        return int(row["revision"])

    def _append_event(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        conn.execute(
            """
            INSERT INTO creator_events (id, project_id, event_type, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (_id("cevt"), project_id, event_type, _dump(payload), _now()),
        )

    def _append_command_metrics(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        command: CreatorCommand,
        payload: dict[str, Any],
        *,
        command_id: str,
        projected: CreatorWorkspace,
    ) -> None:
        """Project strict metrics from facts inside the command transaction."""

        trigger = lambda metric, suffix="": metric_trigger_id(
            metric=metric,
            project_id=project_id,
            source_key=f"{command_id}:{suffix}",
        )
        if command is CreatorCommand.CONFIRM_GOAL and projected.current_goal is not None:
            append_creator_metric(
                conn,
                project_id,
                GoalConfirmedMetric(
                    triggerId=trigger("GOAL_CONFIRMED"),
                    revision=projected.current_goal.revision,
                ),
            )
            return
        if (
            command is CreatorCommand.CONFIRM_SOLUTION
            and projected.current_solution is not None
        ):
            append_creator_metric(
                conn,
                project_id,
                SolutionConfirmedMetric(
                    triggerId=trigger("SOLUTION_CONFIRMED"),
                    revision=projected.current_solution.revision,
                    capabilityClass="MIXED",
                ),
            )
            return
        if command is CreatorCommand.RECORD_SIMULATION:
            passed = bool(payload.get("passed"))
            bindings = payload.get("bindings")
            binding_values = bindings if isinstance(bindings, dict) else {}
            scenario_ids = {
                item
                for item in str(binding_values.get("scenarioIds", "")).split(",")
                if item
            }
            required_rows = conn.execute(
                """
                SELECT id FROM creator_acceptance_scenarios
                WHERE project_id = ? AND required = 1
                """,
                (project_id,),
            ).fetchall()
            required_ids = {str(row["id"]) for row in required_rows}
            raw_failure = str(
                binding_values.get(
                    "failureCategory",
                    "NONE" if passed else "UNKNOWN",
                )
            ).upper()
            failure_category = (
                raw_failure
                if raw_failure
                in {"PARAMETER", "LOGIC", "IO", "CAPABILITY", "UNKNOWN", "NONE"}
                else "UNKNOWN"
            )
            append_creator_metric(
                conn,
                project_id,
                SimulationFinishedMetric(
                    triggerId=trigger("SIMULATION_FINISHED"),
                    passed=passed,
                    requiredScenarioCount=len(required_ids),
                    passedRequiredScenarioCount=(
                        len(required_ids & scenario_ids) if passed else 0
                    ),
                    failureCategory=failure_category,
                ),
            )
            if passed and not self._has_metric(
                conn,
                project_id,
                "DIGITAL_BEHAVIOR_OBSERVED",
            ):
                append_creator_metric(
                    conn,
                    project_id,
                    DigitalBehaviorObservedMetric(
                        triggerId=metric_trigger_id(
                            metric="DIGITAL_BEHAVIOR_OBSERVED",
                            project_id=project_id,
                            source_key="first-observed-digital-behavior",
                        ),
                        elapsedMs=self._elapsed_since_work_created_ms(
                            conn, project_id
                        ),
                    ),
                )
            return
        if command is CreatorCommand.RECORD_DEPLOYMENT:
            bindings = payload.get("bindings")
            binding_values = bindings if isinstance(bindings, dict) else {}
            channel = str(binding_values.get("channel", "")).upper()
            source_id = payload.get("sourceId")
            operation_state: dict[str, Any] = {}
            if source_id:
                operation = conn.execute(
                    """
                    SELECT log FROM device_operations
                    WHERE project_id = ? AND id = ?
                    """,
                    (project_id, str(source_id)),
                ).fetchone()
                if operation is not None:
                    decoded = json.loads(str(operation["log"]))
                    if isinstance(decoded, dict):
                        operation_state = decoded
                        metadata = decoded.get("metadata")
                        if isinstance(metadata, dict):
                            channel = str(metadata.get("channel", channel)).upper()
            if channel not in {"USB_SERIAL", "ESP_CLAW"}:
                channel = "USB_SERIAL"
            if not self._has_metric(
                conn,
                project_id,
                "FIRST_DEPLOYMENT_FINISHED",
                channel=channel,
            ):
                append_creator_metric(
                    conn,
                    project_id,
                    FirstDeploymentFinishedMetric(
                        triggerId=metric_trigger_id(
                            metric="FIRST_DEPLOYMENT_FINISHED",
                            project_id=project_id,
                            source_key=f"first-deployment:{channel}",
                        ),
                        passed=bool(payload.get("passed")),
                        channel=channel,
                        recoveryRequired=bool(operation_state.get("backup")),
                    ),
                )
            return
        if command is CreatorCommand.RECORD_PHYSICAL_BEHAVIOR:
            source_id = payload.get("sourceId")
            run = (
                conn.execute(
                    """
                    SELECT scenario_results_json FROM creator_physical_runs
                    WHERE project_id = ? AND id = ?
                    """,
                    (project_id, str(source_id)),
                ).fetchone()
                if source_id
                else None
            )
            results = (
                json.loads(str(run["scenario_results_json"]))
                if run is not None
                else []
            )
            observed = [
                item
                for item in results
                if isinstance(item, dict) and bool(item.get("observed"))
            ]
            bindings = payload.get("bindings")
            binding_values = bindings if isinstance(bindings, dict) else {}
            append_creator_metric(
                conn,
                project_id,
                PhysicalBehaviorFinishedMetric(
                    triggerId=trigger("PHYSICAL_BEHAVIOR_FINISHED"),
                    passedScenarioCount=len(observed),
                    comparedScenarioCount=len(results),
                    simulationConsistent=str(
                        binding_values.get("simulationConsistent", "false")
                    ).casefold()
                    == "true",
                ),
            )
            return
        if command is CreatorCommand.ACCEPT_WORK:
            append_creator_metric(
                conn,
                project_id,
                WorkAcceptedMetric(
                    triggerId=trigger("WORK_ACCEPTED"),
                    elapsedMs=self._elapsed_since_work_created_ms(conn, project_id),
                ),
            )

    def _elapsed_since_work_created_ms(
        self, conn: sqlite3.Connection, project_id: str
    ) -> int:
        row = conn.execute(
            "SELECT created_at FROM creator_work_state WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        if row is None:
            return 0
        try:
            created_at = datetime.fromisoformat(str(row["created_at"]))
            return max(
                0,
                int((datetime.now(UTC) - created_at).total_seconds() * 1000),
            )
        except ValueError:
            return 0

    def _has_metric(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        metric: str,
        *,
        channel: str | None = None,
    ) -> bool:
        rows = conn.execute(
            """
            SELECT payload_json FROM creator_events
            WHERE project_id = ? AND event_type = 'METRIC'
            """,
            (project_id,),
        ).fetchall()
        for row in rows:
            payload = json.loads(str(row["payload_json"]))
            if payload.get("metric") != metric:
                continue
            if channel is None or payload.get("channel") == channel:
                return True
        return False

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _scene_solution_revision_id(scene: object) -> str:
    if not isinstance(scene, dict):
        return ""
    binding = scene.get("binding")
    if isinstance(binding, dict):
        solution_revision_id = str(binding.get("solutionRevisionId") or "")
        if solution_revision_id:
            return solution_revision_id
    source = scene.get("source")
    return str(source.get("proposalId") or "") if isinstance(source, dict) else ""


def _section_map(value: object | None) -> dict[str, str]:
    if value is None:
        return {}
    try:
        loaded = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(loaded, list):
        return {}
    return {
        str(item.get("id", "")): str(item.get("content", "")).strip()
        for item in loaded
        if isinstance(item, dict) and str(item.get("id", "")).strip()
    }


def _first_text(
    sections: dict[str, str],
    *keys: str,
    fallback: str,
) -> str:
    for key in keys:
        value = sections.get(key, "").strip()
        if value:
            return value
    return fallback.strip()


def _clip(value: str, limit: int) -> str:
    text = value.strip()
    return text if len(text) <= limit else text[:limit].rstrip()


def _hash(value: Any) -> str:
    return hashlib.sha256(_dump(value).encode("utf-8")).hexdigest()


def _load_list(value: object) -> list[str]:
    loaded = json.loads(str(value))
    return [str(item) for item in loaded] if isinstance(loaded, list) else []
