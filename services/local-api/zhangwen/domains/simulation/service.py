"""Draft and immutable revision service for Zhangwen simulation projects."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from zhangwen.auth.context import current_owner_subject
from zhangwen.domains.classroom.repository import (
    ClassroomAuthorizationError,
    ClassroomConflictError,
    ClassroomNotFoundError,
    ClassroomRepository,
    ClassroomValidationError,
)
from zhangwen.domains.simulation.catalog import SimulationCatalog
from zhangwen.domains.simulation.compiler import compile_circuit
from zhangwen.domains.simulation.digest import canonical_digest, canonical_json
from zhangwen.domains.simulation.models import (
    CircuitBoardInstance,
    CircuitDraftV1,
    SimulationCodeBundleDraft,
    SimulationCodeFile,
    SimulationDiagnosticSeverity,
    SimulationProjectDraft,
    SimulationProjectRevision,
    SimulationScenarioSuiteDraft,
    SimulationStaticCompilation,
    SimulationStaticDiagnostic,
    SimulationWorkspace,
)
from zhangwen.domains.simulation.wokwi_adapter import (
    WokwiImportError,
    import_wokwi_diagram,
)


class SimulationValidationError(ClassroomValidationError):
    code = "SIMULATION_PROJECT_VALIDATION_ERROR"


class SimulationConflictError(ClassroomConflictError):
    code = "SIMULATION_PROJECT_CONFLICT"


class SimulationNotFoundError(ClassroomNotFoundError):
    code = "SIMULATION_PROJECT_NOT_FOUND"


_LOCAL_SUBJECT = "__local__"
_RUNTIME_REVISION = "runtime/zw-mpy-sim@1"


class SimulationProjectService:
    """Persists drafts and immutable revision sets; it never starts a Run."""

    def __init__(self, data_dir: Path) -> None:
        self._classroom = ClassroomRepository(data_dir)
        self._db_path = self._classroom.db_path
        self._actor_subject = current_owner_subject() or _LOCAL_SUBJECT
        self._catalog = SimulationCatalog.load_builtin()

    def get_workspace(self, work_id: str) -> SimulationWorkspace:
        self._classroom.assert_work_access(work_id)
        with self._connect() as conn:
            draft_row = conn.execute(
                "SELECT * FROM simulation_project_drafts WHERE work_id = ?",
                (work_id,),
            ).fetchone()
            revision_rows = conn.execute(
                """
                SELECT * FROM simulation_project_revisions
                WHERE work_id = ? ORDER BY revision DESC
                """,
                (work_id,),
            ).fetchall()
            context = conn.execute(
                """
                SELECT current_proposal_revision_id,
                       current_simulation_project_revision_id
                FROM work_learning_contexts WHERE work_id = ?
                """,
                (work_id,),
            ).fetchone()
            if context is None:
                raise SimulationNotFoundError("作品尚未绑定项目任务。")
            draft = (
                SimulationProjectDraft.model_validate_json(str(draft_row["payload_json"]))
                if draft_row is not None
                else None
            )
            revisions = [self._revision(conn, row) for row in revision_rows]
            current_id = _optional_str(
                context["current_simulation_project_revision_id"]
            )
            current = next((item for item in revisions if item.id == current_id), None)
            compilation = self._compile_workspace_draft(
                draft,
                current_proposal_revision_id=_optional_str(
                    context["current_proposal_revision_id"]
                ),
            )
            can_edit = self._can_student_edit(conn, work_id)
        return SimulationWorkspace(
            draft=draft,
            draftRevision=int(draft_row["revision"]) if draft_row is not None else 0,
            current=current,
            revisions=revisions,
            catalog=self._catalog.view(),
            compilation=compilation,
            canEdit=can_edit,
        )

    def create_draft(
        self,
        *,
        work_id: str,
        board_package_revision_id: str,
        idempotency_key: str,
    ) -> SimulationWorkspace:
        key = _idempotency_key(idempotency_key)
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._require_student_editor(conn, work_id)
            proposal_id = self._approved_proposal_revision(conn, work_id)
            board = self._allowed_board(conn, work_id, board_package_revision_id)
            draft = SimulationProjectDraft(
                sourceProposalRevisionId=proposal_id,
                boardPackageRevisionId=board.revision_id,
                runtimePackageRevisionId=_RUNTIME_REVISION,
                componentPackageRevisionIds=[],
                circuit=CircuitDraftV1(
                    boardInstance=CircuitBoardInstance(
                        id="board",
                        boardPackageRevisionId=board.revision_id,
                        position={"x": 80, "y": 120},
                    )
                ),
                codeBundle=SimulationCodeBundleDraft(
                    files=[
                        SimulationCodeFile(
                            path="main.py",
                            content=(
                                "# 掌问自研 MicroPython 行为仿真草稿\n"
                                "from machine import Pin\n\n"
                                "# 根据当前电路补充项目逻辑。\n"
                            ),
                        )
                    ]
                ),
                scenarioSuite=SimulationScenarioSuiteDraft(),
            )
            request_digest = canonical_digest(
                {
                    "operation": "create",
                    "proposal": proposal_id,
                    "board": board.revision_id,
                }
            )
            existing = conn.execute(
                "SELECT * FROM simulation_project_drafts WHERE work_id = ?",
                (work_id,),
            ).fetchone()
            if existing is not None and str(existing["last_idempotency_key"]) == key:
                if str(existing["last_request_digest"]) != request_digest:
                    raise SimulationConflictError("同一请求键不能建立不同的仿真草稿。")
                return self.get_workspace(work_id)
            if existing is None:
                conn.execute(
                    """
                    INSERT INTO simulation_project_drafts (
                      work_id, revision, source_proposal_revision_id, payload_json,
                      last_idempotency_key, last_request_digest,
                      created_by, created_at, updated_at
                    ) VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        work_id,
                        proposal_id,
                        canonical_json(draft),
                        key,
                        request_digest,
                        self._actor_subject,
                        now,
                        now,
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE simulation_project_drafts
                    SET revision = revision + 1, source_proposal_revision_id = ?,
                        payload_json = ?, last_idempotency_key = ?,
                        last_request_digest = ?, updated_at = ?
                    WHERE work_id = ?
                    """,
                    (
                        proposal_id,
                        canonical_json(draft),
                        key,
                        request_digest,
                        now,
                        work_id,
                    ),
                )
            self._journal(
                conn,
                work_id,
                "建立自研仿真草稿",
                f"已按 {board.display_name} 建立电路、代码和场景草稿；尚未执行代码。",
                "SIMULATION_PROJECT_DRAFT",
                work_id,
                now,
            )
        return self.get_workspace(work_id)

    def update_draft(
        self,
        *,
        work_id: str,
        draft: SimulationProjectDraft,
        base_draft_revision: int,
        idempotency_key: str,
    ) -> SimulationWorkspace:
        key = _idempotency_key(idempotency_key)
        normalized = self._normalize_and_validate_draft(draft)
        request_digest = canonical_digest(normalized)
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._require_student_editor(conn, work_id)
            proposal_id = self._approved_proposal_revision(conn, work_id)
            if normalized.source_proposal_revision_id != proposal_id:
                raise SimulationConflictError("方案已形成新修订，请重新建立仿真草稿。")
            self._allowed_board(conn, work_id, normalized.board_package_revision_id)
            self._validate_allowed_components(conn, work_id, normalized)
            row = self._draft_row(conn, work_id)
            if str(row["last_idempotency_key"]) == key:
                if str(row["last_request_digest"]) != request_digest:
                    raise SimulationConflictError("同一请求键不能保存不同的仿真草稿。")
                return self.get_workspace(work_id)
            if int(row["revision"]) != base_draft_revision:
                raise SimulationConflictError("仿真草稿已更新，请先重新读取。")
            conn.execute(
                """
                UPDATE simulation_project_drafts
                SET revision = revision + 1, payload_json = ?,
                    last_idempotency_key = ?, last_request_digest = ?, updated_at = ?
                WHERE work_id = ?
                """,
                (canonical_json(normalized), key, request_digest, now, work_id),
            )
        return self.get_workspace(work_id)

    def import_wokwi_diagram(
        self,
        *,
        work_id: str,
        diagram_json: str,
        base_draft_revision: int,
        idempotency_key: str,
    ) -> SimulationWorkspace:
        try:
            imported = import_wokwi_diagram(diagram_json)
        except WokwiImportError as exc:
            raise SimulationValidationError(str(exc)) from exc
        workspace = self.get_workspace(work_id)
        if workspace.draft is None:
            raise SimulationNotFoundError("请先建立掌问仿真草稿。")
        component_ids = sorted(
            {
                item.component_package_revision_id
                for item in imported.circuit.parts
                if not item.read_only
            }
        )
        draft = workspace.draft.model_copy(
            update={
                "board_package_revision_id": imported.board_package_revision_id,
                "component_package_revision_ids": component_ids,
                "circuit": imported.circuit,
            }
        )
        return self.update_draft(
            work_id=work_id,
            draft=draft,
            base_draft_revision=base_draft_revision,
            idempotency_key=idempotency_key,
        )

    def save_revision(
        self,
        *,
        work_id: str,
        base_draft_revision: int,
        idempotency_key: str,
    ) -> SimulationWorkspace:
        key = _idempotency_key(idempotency_key)
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._require_student_editor(conn, work_id)
            replay = conn.execute(
                """
                SELECT * FROM simulation_project_revisions
                WHERE work_id = ? AND idempotency_key = ?
                """,
                (work_id, key),
            ).fetchone()
            if replay is not None:
                return self.get_workspace(work_id)
            proposal_id = self._approved_proposal_revision(conn, work_id)
            row = self._draft_row(conn, work_id)
            if int(row["revision"]) != base_draft_revision:
                raise SimulationConflictError("仿真草稿已更新，请先重新读取。")
            draft = SimulationProjectDraft.model_validate_json(str(row["payload_json"]))
            normalized = self._normalize_and_validate_draft(draft)
            if normalized.source_proposal_revision_id != proposal_id:
                raise SimulationConflictError("方案已形成新修订，请重新建立仿真草稿。")
            self._allowed_board(conn, work_id, normalized.board_package_revision_id)
            self._validate_allowed_components(conn, work_id, normalized)
            compilation = compile_circuit(normalized.circuit, self._catalog)
            revision = int(
                conn.execute(
                    """
                    SELECT COALESCE(MAX(revision), 0) + 1
                    FROM simulation_project_revisions WHERE work_id = ?
                    """,
                    (work_id,),
                ).fetchone()[0]
            )
            previous = conn.execute(
                """
                SELECT id FROM simulation_project_revisions
                WHERE work_id = ? ORDER BY revision DESC LIMIT 1
                """,
                (work_id,),
            ).fetchone()
            circuit_id = _id("simulation-circuit")
            code_id = _id("simulation-code")
            scenario_id = _id("simulation-scenarios")
            project_id = _id("simulation-project")
            circuit_digest = canonical_digest(normalized.circuit)
            code_digest = canonical_digest(normalized.code_bundle)
            scenario_digest = canonical_digest(normalized.scenario_suite)
            manifest = {
                "schema": normalized.schema,
                "sourceProposalRevisionId": proposal_id,
                "boardPackageRevisionId": normalized.board_package_revision_id,
                "runtimePackageRevisionId": normalized.runtime_package_revision_id,
                "componentPackageRevisionIds": normalized.component_package_revision_ids,
                "circuitRevisionId": circuit_id,
                "circuitDigest": circuit_digest,
                "codeBundleRevisionId": code_id,
                "codeBundleDigest": code_digest,
                "scenarioSuiteRevisionId": scenario_id,
                "scenarioSuiteDigest": scenario_digest,
                "engineProfile": normalized.engine_profile.value,
            }
            project_digest = canonical_digest(manifest)
            request_digest = canonical_digest(
                {"draftRevision": base_draft_revision, "manifest": manifest}
            )
            conn.execute(
                """
                INSERT INTO simulation_circuit_revisions (
                  id, work_id, revision, schema_id, payload_json, digest,
                  created_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    circuit_id,
                    work_id,
                    revision,
                    normalized.circuit.schema,
                    canonical_json(normalized.circuit),
                    circuit_digest,
                    self._actor_subject,
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO simulation_code_bundle_revisions (
                  id, work_id, revision, payload_json, digest,
                  runtime_package_revision_id, created_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    code_id,
                    work_id,
                    revision,
                    canonical_json(normalized.code_bundle),
                    code_digest,
                    normalized.runtime_package_revision_id,
                    self._actor_subject,
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO simulation_scenario_suite_revisions (
                  id, work_id, revision, schema_id, payload_json, digest,
                  created_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scenario_id,
                    work_id,
                    revision,
                    normalized.scenario_suite.schema,
                    canonical_json(normalized.scenario_suite),
                    scenario_digest,
                    self._actor_subject,
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO simulation_project_revisions (
                  id, work_id, revision, schema_id, source_proposal_revision_id,
                  board_package_revision_id, runtime_package_revision_id,
                  component_package_revision_ids_json, circuit_revision_id,
                  code_bundle_revision_id, scenario_suite_revision_id,
                  engine_profile, digest, supersedes_revision_id,
                  idempotency_key, request_digest, created_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    work_id,
                    revision,
                    normalized.schema,
                    proposal_id,
                    normalized.board_package_revision_id,
                    normalized.runtime_package_revision_id,
                    json.dumps(normalized.component_package_revision_ids),
                    circuit_id,
                    code_id,
                    scenario_id,
                    normalized.engine_profile.value,
                    project_digest,
                    str(previous["id"]) if previous is not None else None,
                    key,
                    request_digest,
                    self._actor_subject,
                    now,
                ),
            )
            self._invalidate_for_simulation_revision(
                conn,
                work_id=work_id,
                project_revision_id=project_id,
                proposal_revision_id=proposal_id,
                circuit_revision_id=circuit_id,
                code_revision_id=code_id,
                scenario_revision_id=scenario_id,
                runtime_revision_id=normalized.runtime_package_revision_id,
                component_revision_ids=normalized.component_package_revision_ids,
                compilation=compilation,
                now=now,
            )
            conn.execute(
                """
                UPDATE work_learning_contexts
                SET current_simulation_project_revision_id = ?,
                    process_milestone = 'SIMULATION', process_state = ?,
                    revision = revision + 1, updated_at = ?
                WHERE work_id = ?
                """,
                (
                    project_id,
                    "SIMULATION_READY" if compilation.runnable else "SIMULATION_DRAFT",
                    now,
                    work_id,
                ),
            )
            self._journal(
                conn,
                work_id,
                f"保存自研仿真版本 v{revision}",
                "已固定电路、代码与场景版本；静态检查通过，但尚未执行 MicroPython。"
                if compilation.runnable
                else "已固定草稿版本；静态错误仍会阻止后续运行。",
                "SIMULATION_PROJECT_REVISION",
                project_id,
                now,
            )
        return self.get_workspace(work_id)

    def _invalidate_for_simulation_revision(
        self,
        conn: sqlite3.Connection,
        *,
        work_id: str,
        project_revision_id: str,
        proposal_revision_id: str,
        circuit_revision_id: str,
        code_revision_id: str,
        scenario_revision_id: str,
        runtime_revision_id: str,
        component_revision_ids: list[str],
        compilation: SimulationStaticCompilation,
        now: str,
    ) -> None:
        reason = "电路、代码、场景或运行时版本集合已经变化，需要重新验证下游结果。"
        conn.execute(
            """
            UPDATE creator_evidence
            SET status = 'STALE', invalidated_at = ?, invalidation_reason = ?
            WHERE project_id = ? AND status = 'CURRENT'
              AND kind IN (
                'STATIC_VALIDATION', 'SIMULATION', 'STRUCTURE_CHECK',
                'DEVICE_CONNECTION', 'DEPLOYMENT', 'PHYSICAL_BEHAVIOR',
                'USER_ACCEPTANCE', 'REPRODUCTION'
              )
            """,
            (now, reason, work_id),
        )
        conn.execute(
            """
            UPDATE simulation_runs
            SET status = 'STALE', invalidated_at = ?, invalidation_reason = ?
            WHERE work_id = ? AND status NOT IN ('STALE', 'RUNNING')
            """,
            (now, reason, work_id),
        )
        conn.execute(
            """
            UPDATE project_build_route_decisions
            SET status = 'STALE', invalidated_at = ?, invalidation_reason = ?
            WHERE work_id = ? AND status = 'CURRENT'
            """,
            (now, reason, work_id),
        )
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
            UPDATE deployment_bundles
            SET status = 'STALE', invalidated_at = ?, invalidation_reason = ?
            WHERE work_id = ? AND status = 'CURRENT'
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
            SET current_simulation_run_id = NULL,
                current_build_route_decision_id = NULL,
                current_structure_revision_id = NULL,
                current_assembly_record_id = NULL,
                current_deployment_bundle_id = NULL,
                current_device_deployment_id = NULL
            WHERE work_id = ?
            """,
            (work_id,),
        )
        bindings = {
            "proposalRevisionId": proposal_revision_id,
            "simulationProjectRevisionId": project_revision_id,
            "circuitRevisionId": circuit_revision_id,
            "codeBundleRevisionId": code_revision_id,
            "scenarioSuiteRevisionId": scenario_revision_id,
            "runtimePackageRevisionId": runtime_revision_id,
            "componentPackageRevisionIds": json.dumps(
                component_revision_ids, ensure_ascii=False, separators=(",", ":")
            ),
            "evidenceLevel": "L0",
        }
        passed = compilation.runnable
        conn.execute(
            """
            INSERT INTO creator_evidence (
              id, project_id, kind, status, passed, summary, bindings_json,
              source_id, recorded_at, invalidated_at, invalidation_reason
            ) VALUES (?, ?, 'STATIC_VALIDATION', ?, ?, ?, ?, ?, ?, NULL, NULL)
            """,
            (
                _id("evidence"),
                work_id,
                "CURRENT" if passed else "FAILED",
                1 if passed else 0,
                (
                    "电路静态检查通过；该结果只属于 L0，不代表代码已经执行。"
                    if passed
                    else "电路静态检查未通过，不能执行正式场景。"
                ),
                json.dumps(bindings, ensure_ascii=False, separators=(",", ":")),
                project_revision_id,
                now,
            ),
        )

    def _normalize_and_validate_draft(
        self, draft: SimulationProjectDraft
    ) -> SimulationProjectDraft:
        component_ids = sorted(
            {
                part.component_package_revision_id
                for part in draft.circuit.parts
                if not part.read_only
            }
        )
        normalized = draft.model_copy(
            update={"component_package_revision_ids": component_ids}
        )
        if normalized.runtime_package_revision_id != _RUNTIME_REVISION:
            raise SimulationValidationError("E4 只允许固定的掌问行为运行时目标。")
        return normalized

    def _compile_workspace_draft(
        self,
        draft: SimulationProjectDraft | None,
        *,
        current_proposal_revision_id: str | None,
    ) -> SimulationStaticCompilation:
        if draft is None:
            return SimulationStaticCompilation(
                runnable=False,
                circuitDigest="",
                diagnostics=[
                    SimulationStaticDiagnostic(
                        severity="INFO",
                        code="SIM_DRAFT_NOT_CREATED",
                        message="方案通过后可建立第一份自研仿真草稿。",
                        targetId=None,
                    )
                ],
            )
        compilation = compile_circuit(draft.circuit, self._catalog)
        if draft.source_proposal_revision_id == current_proposal_revision_id:
            return compilation
        return compilation.model_copy(
            update={
                "runnable": False,
                "diagnostics": [
                    SimulationStaticDiagnostic(
                        severity=SimulationDiagnosticSeverity.ERROR,
                        code="SIM_SOURCE_PROPOSAL_STALE",
                        message="项目方案已形成新修订，请重新建立仿真草稿。",
                        targetId=draft.source_proposal_revision_id,
                    ),
                    *compilation.diagnostics,
                ],
            }
        )

    def _approved_proposal_revision(
        self, conn: sqlite3.Connection, work_id: str
    ) -> str:
        row = conn.execute(
            """
            SELECT wlc.current_proposal_revision_id, proposal.status
            FROM work_learning_contexts AS wlc
            LEFT JOIN project_proposal_revisions_v2 AS proposal
              ON proposal.id = wlc.current_proposal_revision_id
            WHERE wlc.work_id = ?
            """,
            (work_id,),
        ).fetchone()
        if (
            row is None
            or row["current_proposal_revision_id"] is None
            or str(row["status"] or "") != "APPROVED"
        ):
            raise SimulationValidationError("当前项目方案书尚未通过，不能建立正式仿真草稿。")
        return str(row["current_proposal_revision_id"])

    def _allowed_board(
        self, conn: sqlite3.Connection, work_id: str, revision_id: str
    ):
        board = self._catalog.board(revision_id)
        if board is None:
            raise SimulationValidationError("板型 revision 不在已审核目录中。")
        row = conn.execute(
            """
            SELECT policy.allowed_chip_targets_json
            FROM work_learning_contexts AS wlc
            JOIN assignments AS assignment ON assignment.id = wlc.assignment_id
            JOIN assignment_policy_revisions AS policy
              ON policy.id = assignment.policy_revision_id
            WHERE wlc.work_id = ?
            """,
            (work_id,),
        ).fetchone()
        if row is None:
            raise SimulationNotFoundError("作品尚未绑定项目任务。")
        allowed = set(json.loads(str(row["allowed_chip_targets_json"])))
        if board.chip_family.value not in allowed:
            raise SimulationValidationError("当前任务不允许使用这个 ESP32 芯片目标。")
        return board

    def _validate_allowed_components(
        self,
        conn: sqlite3.Connection,
        work_id: str,
        draft: SimulationProjectDraft,
    ) -> None:
        row = conn.execute(
            """
            SELECT policy.allowed_component_package_ids_json
            FROM work_learning_contexts AS wlc
            JOIN assignments AS assignment ON assignment.id = wlc.assignment_id
            JOIN assignment_policy_revisions AS policy
              ON policy.id = assignment.policy_revision_id
            WHERE wlc.work_id = ?
            """,
            (work_id,),
        ).fetchone()
        allowed = set(json.loads(str(row[0]))) if row is not None else set()
        if allowed:
            disallowed = sorted(set(draft.component_package_revision_ids) - allowed)
            if disallowed:
                raise SimulationValidationError(
                    f"当前任务不允许这些组件 revision：{'、'.join(disallowed)}。"
                )

    def _revision(
        self, conn: sqlite3.Connection, row: sqlite3.Row
    ) -> SimulationProjectRevision:
        circuit_row = conn.execute(
            "SELECT * FROM simulation_circuit_revisions WHERE id = ?",
            (row["circuit_revision_id"],),
        ).fetchone()
        code_row = conn.execute(
            "SELECT * FROM simulation_code_bundle_revisions WHERE id = ?",
            (row["code_bundle_revision_id"],),
        ).fetchone()
        scenario_row = conn.execute(
            "SELECT * FROM simulation_scenario_suite_revisions WHERE id = ?",
            (row["scenario_suite_revision_id"],),
        ).fetchone()
        if circuit_row is None or code_row is None or scenario_row is None:
            raise SimulationValidationError("仿真 revision set 缺少不可变子版本。")
        return SimulationProjectRevision(
            id=str(row["id"]),
            workId=str(row["work_id"]),
            revision=int(row["revision"]),
            schema=str(row["schema_id"]),
            sourceProposalRevisionId=str(row["source_proposal_revision_id"]),
            boardPackageRevisionId=str(row["board_package_revision_id"]),
            runtimePackageRevisionId=str(row["runtime_package_revision_id"]),
            componentPackageRevisionIds=json.loads(
                str(row["component_package_revision_ids_json"])
            ),
            circuit=CircuitDraftV1.model_validate_json(str(circuit_row["payload_json"])),
            codeBundle=SimulationCodeBundleDraft.model_validate_json(
                str(code_row["payload_json"])
            ),
            scenarioSuite=SimulationScenarioSuiteDraft.model_validate_json(
                str(scenario_row["payload_json"])
            ),
            engineProfile=str(row["engine_profile"]),
            digest=str(row["digest"]),
            circuitRevisionId=str(circuit_row["id"]),
            circuitDigest=str(circuit_row["digest"]),
            codeBundleRevisionId=str(code_row["id"]),
            codeBundleDigest=str(code_row["digest"]),
            scenarioSuiteRevisionId=str(scenario_row["id"]),
            scenarioSuiteDigest=str(scenario_row["digest"]),
            supersedesRevisionId=_optional_str(row["supersedes_revision_id"]),
            createdBy=str(row["created_by"]),
            createdAt=str(row["created_at"]),
        )

    @staticmethod
    def _draft_row(conn: sqlite3.Connection, work_id: str) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM simulation_project_drafts WHERE work_id = ?",
            (work_id,),
        ).fetchone()
        if row is None:
            raise SimulationNotFoundError("掌问仿真草稿尚未建立。")
        return row

    def _can_student_edit(self, conn: sqlite3.Connection, work_id: str) -> bool:
        try:
            self._require_student_editor(conn, work_id)
            self._approved_proposal_revision(conn, work_id)
            return True
        except (ClassroomAuthorizationError, ClassroomValidationError):
            return False

    def _require_student_editor(self, conn: sqlite3.Connection, work_id: str) -> None:
        row = conn.execute(
            """
            SELECT project.owner_subject, assignment.class_group_id
            FROM projects AS project
            JOIN work_learning_contexts AS context ON context.work_id = project.id
            JOIN assignments AS assignment ON assignment.id = context.assignment_id
            WHERE project.id = ?
            """,
            (work_id,),
        ).fetchone()
        if row is None:
            raise SimulationNotFoundError("课堂项目不存在。")
        class_role = conn.execute(
            """
            SELECT role FROM class_memberships
            WHERE class_group_id = ? AND subject = ? AND active = 1
            """,
            (row["class_group_id"], self._actor_subject),
        ).fetchone()
        if class_role is None or str(class_role["role"]) != "LEARNER":
            raise ClassroomAuthorizationError("只有当前项目的学生成员可以修改仿真草稿。")
        owner = str(row["owner_subject"] or _LOCAL_SUBJECT) == self._actor_subject
        member = conn.execute(
            """
            SELECT role FROM work_memberships
            WHERE work_id = ? AND subject = ? AND active = 1
            """,
            (work_id, self._actor_subject),
        ).fetchone()
        if not owner and (member is None or str(member["role"]) not in {"OWNER", "EDITOR"}):
            raise ClassroomAuthorizationError("只有项目所有者或编辑成员可以修改仿真草稿。")

    def _journal(
        self,
        conn: sqlite3.Connection,
        work_id: str,
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
            ) VALUES (?, ?, ?, 'TEST', ?, ?, ?, ?, ?)
            """,
            (
                _id("journal"),
                work_id,
                self._actor_subject,
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


def _idempotency_key(value: str) -> str:
    clean = value.strip()
    if not clean or len(clean) > 80:
        raise SimulationValidationError("请求键长度必须为 1–80 个字符。")
    return clean


def _optional_str(value: object) -> str | None:
    return str(value) if value is not None else None


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _now() -> str:
    return datetime.now(UTC).isoformat()
