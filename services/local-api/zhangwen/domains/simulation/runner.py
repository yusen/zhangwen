"""Scenario runner and immutable Work Run/Evidence integration for E6."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from zhangwen.auth.context import current_owner_subject
from zhangwen.domains.classroom.repository import ClassroomRepository
from zhangwen.domains.events.runtime import TelemetryHub, telemetry_hub
from zhangwen.domains.events.store import RealtimeEventStore
from zhangwen.domains.simulation.digest import canonical_digest, canonical_json
from zhangwen.domains.simulation.models import (
    CircuitDraftV1,
    SimulationCodeBundleDraft,
    SimulationProjectRevision,
    SimulationScenario,
    SimulationScenarioAssertion,
    SimulationScenarioSuiteDraft,
)
from zhangwen.domains.simulation.run_models import (
    SimulationAssertionResult,
    SimulationAssertionStatus,
    SimulationRunRecord,
    SimulationRunRequest,
    SimulationRunStatus,
    SimulationRunWorkspace,
    SimulationScenarioResultStatus,
    SimulationScenarioRunResult,
)
from zhangwen.domains.simulation.runtime.host import SimulationRuntimeHost
from zhangwen.domains.simulation.runtime.models import (
    RuntimeEngineMode,
    RuntimeEvent,
    RuntimeExecutionRequest,
    RuntimeExecutionResult,
    RuntimeExecutionStatus,
    RuntimeResourceLimits,
)
from zhangwen.domains.simulation.service import (
    SimulationConflictError,
    SimulationNotFoundError,
    SimulationValidationError,
)


_LOCAL_SUBJECT = "__local__"


class RuntimeHostPort(Protocol):
    def execute(
        self, request: RuntimeExecutionRequest, **kwargs: object
    ) -> RuntimeExecutionResult: ...


class SimulationRunService:
    """Runs a fixed revision set and writes only to the existing Work fact stores."""

    def __init__(
        self,
        data_dir: Path,
        *,
        runtime_host: RuntimeHostPort | None = None,
        telemetry: TelemetryHub | None = None,
    ) -> None:
        self._data_dir = Path(data_dir)
        self._classroom = ClassroomRepository(self._data_dir)
        self._db_path = self._classroom.db_path
        self._runtime = runtime_host or SimulationRuntimeHost(self._data_dir)
        self._telemetry = telemetry or telemetry_hub()
        self._events = RealtimeEventStore(self._db_path)
        self._actor_subject = current_owner_subject() or _LOCAL_SUBJECT

    def get_workspace(self, work_id: str) -> SimulationRunWorkspace:
        self._classroom.assert_work_access(work_id)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM simulation_runs WHERE work_id = ? "
                "ORDER BY created_at DESC, id DESC",
                (work_id,),
            ).fetchall()
            records = [self._record(conn, row) for row in rows]
            context = conn.execute(
                "SELECT current_simulation_run_id FROM work_learning_contexts "
                "WHERE work_id = ?",
                (work_id,),
            ).fetchone()
        current_id = str(context[0]) if context is not None and context[0] else None
        current = next((item for item in records if item.id == current_id), None)
        can_run = False
        try:
            self._classroom.assert_work_access(work_id, edit=True)
            can_run = True
        except Exception:
            can_run = False
        return SimulationRunWorkspace(current=current, runs=records, canRun=can_run)

    def run(
        self,
        *,
        work_id: str,
        request: SimulationRunRequest,
    ) -> SimulationRunRecord:
        self._classroom.assert_work_access(work_id, edit=True)
        key = request.idempotency_key.strip()
        request_digest = canonical_digest(
            {
                "simulationProjectRevisionId": request.simulation_project_revision_id,
                "engineMode": request.engine_mode.value,
                "reflections": request.reflections,
            }
        )
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT * FROM simulation_runs WHERE work_id = ? AND idempotency_key = ?",
                (work_id, key),
            ).fetchone()
            if existing is not None:
                if str(existing["request_digest"]) != request_digest:
                    raise SimulationConflictError(
                        "同一请求键已经绑定另一组仿真参数。"
                    )
                return self._record(conn, existing)
            revision = self._current_revision(conn, work_id, request)
            required = [item for item in revision.scenario_suite.scenarios if item.required]
            if not required:
                raise SimulationValidationError("正式运行至少需要一个必测场景。")
            missing_reflections = [
                item.title
                for item in required
                if item.reflection_prompt and not request.reflections.get(item.id, "").strip()
            ]
            if missing_reflections:
                raise SimulationValidationError(
                    "请先完成必测场景反思：" + "、".join(missing_reflections)
                )
            running = conn.execute(
                "SELECT id FROM simulation_runs WHERE work_id = ? AND status = 'RUNNING'",
                (work_id,),
            ).fetchone()
            if running is not None:
                raise SimulationConflictError("当前作品已有一个运行中的场景集合。")
            run_id = _id("simulation-run")
            revision_set = self._revision_set(revision)
            conn.execute(
                """
                INSERT INTO simulation_runs (
                  id, work_id, simulation_project_revision_id, status,
                  engine_mode, evidence_level, evidence_eligible,
                  request_json, request_digest, revision_set_json,
                  deterministic_digest, explanation, serial_output, error_json,
                  idempotency_key, created_by, created_at, started_at,
                  completed_at, invalidated_at, invalidation_reason
                ) VALUES (?, ?, ?, 'RUNNING', ?, 'L0', 0, ?, ?, ?, NULL,
                          ?, '', NULL, ?, ?, ?, ?, NULL, NULL, NULL)
                """,
                (
                    run_id,
                    work_id,
                    revision.id,
                    request.engine_mode.value,
                    canonical_json(request),
                    request_digest,
                    json.dumps(revision_set, ensure_ascii=False, separators=(",", ":")),
                    "正在运行固定版本的必测场景。",
                    key,
                    self._actor_subject,
                    now,
                    now,
                ),
            )
            conn.execute(
                """
                UPDATE work_learning_contexts
                SET current_simulation_run_id = ?, process_milestone = 'SIMULATION',
                    process_state = 'SIMULATION_RUNNING', revision = revision + 1,
                    updated_at = ?
                WHERE work_id = ?
                """,
                (run_id, now, work_id),
            )
            self._journal(
                conn,
                work_id,
                "TEST",
                "开始运行验证场景",
                "本次运行已固定方案、电路、代码、场景、组件、板型和运行时版本。",
                run_id,
                now,
            )
            self._events.append_work_event(
                conn,
                work_id=work_id,
                event_type="work.simulation.run.started",
                source_event_id=f"{run_id}:started",
                payload={
                    "runId": run_id,
                    "simulationProjectRevisionId": revision.id,
                    "engineMode": request.engine_mode.value,
                    "status": "RUNNING",
                },
            )

        scenario_results = [
            self._run_scenario(
                run_id=run_id,
                revision=revision,
                scenario=scenario,
                reflection=request.reflections.get(scenario.id, "").strip(),
                engine_mode=request.engine_mode,
            )
            for scenario in revision.scenario_suite.scenarios
        ]
        return self._finalize(
            work_id=work_id,
            run_id=run_id,
            revision=revision,
            engine_mode=request.engine_mode,
            revision_set=revision_set,
            scenario_results=scenario_results,
        )

    def _run_scenario(
        self,
        *,
        run_id: str,
        revision: SimulationProjectRevision,
        scenario: SimulationScenario,
        reflection: str,
        engine_mode: RuntimeEngineMode,
    ) -> SimulationScenarioRunResult:
        limits = RuntimeResourceLimits(
            wallTimeoutMs=min(10_000, max(100, scenario.timeout_ms)),
            maxVirtualTimeUs=min(3_600_000_000, max(1_000, scenario.timeout_ms * 1000)),
            maxInstructions=250_000,
            maxEvents=min(100_000, scenario.max_events),
            maxOutputBytes=128_000,
            maxHeapBytes=32_000_000,
        )
        runtime_request = RuntimeExecutionRequest(
            engineMode=engine_mode,
            boardPackageRevisionId=revision.board_package_revision_id,
            runtimePackageRevisionId=revision.runtime_package_revision_id,
            circuit=revision.circuit,
            codeBundle=revision.code_bundle,
            seed=scenario.seed,
            limits=limits,
            scenarioActions=scenario.actions,
        )
        try:
            runtime_result = self._runtime.execute(runtime_request)
        except Exception as exc:
            runtime_result = SimulationRuntimeHost._failure(
                engine_mode,
                RuntimeExecutionStatus.CRASHED,
                "SIMULATION_RUNNER_HOST_ERROR",
                f"仿真 Host 异常结束：{exc.__class__.__name__}。",
                retryable=True,
            )
        assertion_results = [
            evaluate_assertion(item, runtime_result) for item in scenario.assertions
        ]
        scenario_status = _scenario_status(runtime_result, assertion_results)
        explanation = _scenario_explanation(
            scenario,
            scenario_status,
            assertion_results,
            runtime_result,
        )
        result = SimulationScenarioRunResult(
            id=_id("scenario-result"),
            scenarioId=scenario.id,
            title=scenario.title,
            required=scenario.required,
            status=scenario_status,
            seed=scenario.seed,
            reflection=reflection,
            deterministicDigest=runtime_result.deterministic_digest,
            runtimeStatus=runtime_result.status,
            nativeCoreVerified=runtime_result.native_core_verified,
            evidenceEligible=runtime_result.evidence_eligible,
            assertions=assertion_results,
            serialOutput=runtime_result.serial_output,
            explanation=explanation,
        )
        for event in runtime_result.events[:64]:
            try:
                self._telemetry.publish(
                    work_id=revision.work_id,
                    payload={
                        "kind": event.kind,
                        "source": event.source,
                        "virtualTimeUs": event.virtual_time_us,
                        "runId": run_id,
                        "scenarioId": scenario.id,
                        "value": event.payload,
                    },
                )
            except ValueError:
                continue
        return result

    def _finalize(
        self,
        *,
        work_id: str,
        run_id: str,
        revision: SimulationProjectRevision,
        engine_mode: RuntimeEngineMode,
        revision_set: dict[str, object],
        scenario_results: list[SimulationScenarioRunResult],
    ) -> SimulationRunRecord:
        required = [item for item in scenario_results if item.required]
        status = _run_status(required, engine_mode)
        eligible = bool(
            status is SimulationRunStatus.PASSED
            and required
            and all(
                item.native_core_verified and item.evidence_eligible
                for item in required
            )
        )
        if status is SimulationRunStatus.PASSED and not eligible:
            status = SimulationRunStatus.CONFORMANCE_PASSED
        evidence_level = "L1" if eligible else "L0"
        semantic = {
            "revisionSet": revision_set,
            "engineMode": engine_mode.value,
            "scenarios": [
                {
                    "scenarioId": item.scenario_id,
                    "status": item.status.value,
                    "deterministicDigest": item.deterministic_digest,
                    "assertions": [
                        assertion.model_dump(mode="json", by_alias=True)
                        for assertion in item.assertions
                    ],
                }
                for item in scenario_results
            ],
        }
        deterministic_digest = canonical_digest(semantic)
        serial_output = "".join(item.serial_output for item in scenario_results)
        explanation = _run_explanation(status, eligible, required)
        error = next(
            (
                {"code": "SIMULATION_SCENARIO_FAILED", "message": item.explanation}
                for item in required
                if item.status is not SimulationScenarioResultStatus.PASSED
            ),
            None,
        )
        completed_at = _now()
        process_state = (
            "BUILD_ROUTE_REQUIRED"
            if eligible
            else "SIMULATION_READY"
            if status is SimulationRunStatus.CONFORMANCE_PASSED
            else "SIMULATION_CHANGES_REQUIRED"
        )
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            for item in scenario_results:
                conn.execute(
                    """
                    INSERT INTO simulation_scenario_results (
                      id, run_id, scenario_id, title, required, status, seed,
                      reflection, deterministic_digest, assertion_results_json,
                      runtime_result_json, explanation, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.id,
                        run_id,
                        item.scenario_id,
                        item.title,
                        1 if item.required else 0,
                        item.status.value,
                        item.seed,
                        item.reflection,
                        item.deterministic_digest,
                        json.dumps(
                            [
                                assertion.model_dump(mode="json", by_alias=True)
                                for assertion in item.assertions
                            ],
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                        item.model_dump_json(by_alias=True),
                        item.explanation,
                        completed_at,
                    ),
                )
            conn.execute(
                """
                UPDATE simulation_runs
                SET status = ?, evidence_level = ?, evidence_eligible = ?,
                    deterministic_digest = ?, explanation = ?, serial_output = ?,
                    error_json = ?, completed_at = ?
                WHERE id = ? AND status = 'RUNNING'
                """,
                (
                    status.value,
                    evidence_level,
                    1 if eligible else 0,
                    deterministic_digest,
                    explanation,
                    serial_output,
                    json.dumps(error, ensure_ascii=False) if error else None,
                    completed_at,
                    run_id,
                ),
            )
            conn.execute(
                """
                UPDATE work_learning_contexts
                SET process_state = ?, process_milestone = ?,
                    revision = revision + 1, updated_at = ?
                WHERE work_id = ? AND current_simulation_run_id = ?
                """,
                (
                    process_state,
                    "MAKING" if eligible else "SIMULATION",
                    completed_at,
                    work_id,
                    run_id,
                ),
            )
            if eligible:
                self._record_l1_evidence(
                    conn,
                    work_id=work_id,
                    run_id=run_id,
                    revision=revision,
                    revision_set=revision_set,
                    now=completed_at,
                )
            self._journal(
                conn,
                work_id,
                "REFLECTION" if status in {
                    SimulationRunStatus.PASSED,
                    SimulationRunStatus.CONFORMANCE_PASSED,
                } else "FAILURE",
                "验证场景运行完成",
                explanation,
                run_id,
                completed_at,
            )
            self._events.append_work_event(
                conn,
                work_id=work_id,
                event_type="work.simulation.run.completed",
                source_event_id=f"{run_id}:completed",
                payload={
                    "runId": run_id,
                    "status": status.value,
                    "evidenceLevel": evidence_level,
                    "evidenceEligible": eligible,
                    "deterministicDigest": deterministic_digest,
                },
            )
            row = conn.execute(
                "SELECT * FROM simulation_runs WHERE id = ?", (run_id,)
            ).fetchone()
            assert row is not None
            record = self._record(conn, row)
        self._telemetry.publish(
            work_id=work_id,
            payload={
                "kind": "SIMULATION_RUN_COMPLETED",
                "runId": run_id,
                "status": status.value,
                "evidenceLevel": evidence_level,
            },
        )
        return record

    def _current_revision(
        self,
        conn: sqlite3.Connection,
        work_id: str,
        request: SimulationRunRequest,
    ) -> SimulationProjectRevision:
        context = conn.execute(
            """
            SELECT current_simulation_project_revision_id, process_state
            FROM work_learning_contexts WHERE work_id = ?
            """,
            (work_id,),
        ).fetchone()
        if context is None or context["current_simulation_project_revision_id"] is None:
            raise SimulationNotFoundError("当前作品还没有可运行的仿真版本。")
        if str(context["current_simulation_project_revision_id"]) != (
            request.simulation_project_revision_id
        ):
            raise SimulationConflictError("只能运行作品当前固定的仿真版本。")
        evidence = conn.execute(
            """
            SELECT 1 FROM creator_evidence
            WHERE project_id = ? AND kind = 'STATIC_VALIDATION'
              AND status = 'CURRENT' AND passed = 1 AND source_id = ?
            """,
            (work_id, request.simulation_project_revision_id),
        ).fetchone()
        if evidence is None:
            raise SimulationValidationError("电路静态检查未通过，不能开始场景运行。")
        row = conn.execute(
            "SELECT * FROM simulation_project_revisions WHERE id = ? AND work_id = ?",
            (request.simulation_project_revision_id, work_id),
        ).fetchone()
        if row is None:
            raise SimulationConflictError("仿真版本已经变化，请重新读取。")
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
    def _revision_set(revision: SimulationProjectRevision) -> dict[str, object]:
        return {
            "proposalRevisionId": revision.source_proposal_revision_id,
            "simulationProjectRevisionId": revision.id,
            "simulationProjectDigest": revision.digest,
            "circuitRevisionId": revision.circuit_revision_id,
            "circuitDigest": revision.circuit_digest,
            "codeBundleRevisionId": revision.code_bundle_revision_id,
            "codeBundleDigest": revision.code_bundle_digest,
            "scenarioSuiteRevisionId": revision.scenario_suite_revision_id,
            "scenarioSuiteDigest": revision.scenario_suite_digest,
            "boardPackageRevisionId": revision.board_package_revision_id,
            "componentPackageRevisionIds": revision.component_package_revision_ids,
            "runtimePackageRevisionId": revision.runtime_package_revision_id,
            "engineProfile": revision.engine_profile.value,
        }

    def _record_l1_evidence(
        self,
        conn: sqlite3.Connection,
        *,
        work_id: str,
        run_id: str,
        revision: SimulationProjectRevision,
        revision_set: dict[str, object],
        now: str,
    ) -> None:
        conn.execute(
            """
            UPDATE creator_evidence SET status = 'SUPERSEDED'
            WHERE project_id = ? AND kind = 'SIMULATION'
              AND status IN ('CURRENT', 'FAILED')
            """,
            (work_id,),
        )
        bindings = {
            key: json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            if isinstance(value, list)
            else str(value)
            for key, value in revision_set.items()
        }
        bindings.update({"simulationRunId": run_id, "evidenceLevel": "L1"})
        conn.execute(
            """
            INSERT INTO creator_evidence (
              id, project_id, kind, status, passed, summary, bindings_json,
              source_id, recorded_at, invalidated_at, invalidation_reason
            ) VALUES (?, ?, 'SIMULATION', 'CURRENT', 1, ?, ?, ?, ?, NULL, NULL)
            """,
            (
                _id("evidence"),
                work_id,
                "固定原生 MicroPython 运行时的全部必测场景和反思已通过。",
                json.dumps(bindings, ensure_ascii=False, separators=(",", ":")),
                run_id,
                now,
            ),
        )

    def _record(self, conn: sqlite3.Connection, row: sqlite3.Row) -> SimulationRunRecord:
        scenario_rows = conn.execute(
            "SELECT runtime_result_json FROM simulation_scenario_results "
            "WHERE run_id = ? ORDER BY created_at, scenario_id",
            (row["id"],),
        ).fetchall()
        scenarios = [
            SimulationScenarioRunResult.model_validate_json(str(item[0]))
            for item in scenario_rows
        ]
        return SimulationRunRecord(
            id=str(row["id"]),
            workId=str(row["work_id"]),
            simulationProjectRevisionId=str(row["simulation_project_revision_id"]),
            status=str(row["status"]),
            engineMode=str(row["engine_mode"]),
            evidenceLevel=str(row["evidence_level"]),
            evidenceEligible=bool(row["evidence_eligible"]),
            deterministicDigest=_optional_str(row["deterministic_digest"]),
            revisionSet=json.loads(str(row["revision_set_json"])),
            scenarios=scenarios,
            explanation=str(row["explanation"]),
            serialOutput=str(row["serial_output"]),
            error=json.loads(str(row["error_json"])) if row["error_json"] else None,
            createdBy=str(row["created_by"]),
            createdAt=str(row["created_at"]),
            completedAt=_optional_str(row["completed_at"]),
            invalidationReason=_optional_str(row["invalidation_reason"]),
        )

    def _journal(
        self,
        conn: sqlite3.Connection,
        work_id: str,
        kind: str,
        title: str,
        body: str,
        run_id: str,
        now: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO project_process_journal (
              id, work_id, actor_subject, kind, title, body,
              related_kind, related_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'SIMULATION_RUN', ?, ?)
            """,
            (_id("journal"), work_id, self._actor_subject, kind, title, body, run_id, now),
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


def evaluate_assertion(
    assertion: SimulationScenarioAssertion,
    runtime_result: RuntimeExecutionResult,
) -> SimulationAssertionResult:
    if runtime_result.status is not RuntimeExecutionStatus.COMPLETED:
        return SimulationAssertionResult(
            assertionId=assertion.id,
            target=assertion.target,
            status=SimulationAssertionStatus.NOT_EVALUATED,
            expected=assertion.expected,
            observed=None,
            explanation="运行未正常完成，因此没有采信该断言。",
        )
    observed = _observe(assertion, runtime_result)
    passed = _compare(assertion, observed)
    return SimulationAssertionResult(
        assertionId=assertion.id,
        target=assertion.target,
        status=(
            SimulationAssertionStatus.PASSED
            if passed
            else SimulationAssertionStatus.FAILED
        ),
        expected=assertion.expected,
        observed=observed,
        explanation=(
            f"已观察到 {observed!r}，符合预期。"
            if passed
            else f"观察到 {observed!r}，与预期 {assertion.expected!r} 不符。"
        ),
    )


def _observe(
    assertion: SimulationScenarioAssertion,
    runtime_result: RuntimeExecutionResult,
) -> object | None:
    target = assertion.target
    cutoff = assertion.at_ms * 1000
    events = [item for item in runtime_result.events if item.virtual_time_us <= cutoff]
    if target == "serial":
        return runtime_result.serial_output
    if target.startswith("pin:"):
        pin_id = target.removeprefix("pin:").upper()
        matching = [
            item
            for item in events
            if item.source.upper() == pin_id and item.kind in {"PIN_WRITE", "PIN_READ", "PIN_INPUT"}
        ]
        return matching[-1].payload.get("value") if matching else None
    if target.startswith("display:"):
        part_id = target.removeprefix("display:")
        matching = [
            item for item in events if item.kind == "DISPLAY_FRAME" and item.source == part_id
        ]
        if not matching:
            return None
        operations = matching[-1].payload.get("operations", [])
        if not isinstance(operations, list):
            return None
        return " ".join(
            str(item.get("text", ""))
            for item in operations
            if isinstance(item, dict) and item.get("op") == "text"
        )
    if target.startswith("event:"):
        _, kind, source = (target.split(":", 2) + [""])[:3]
        matching = [
            item for item in events if item.kind == kind and (not source or item.source == source)
        ]
        return matching[-1].payload if matching else None
    if target.startswith("component:"):
        reference = target.removeprefix("component:")
        part_id, separator, property_name = reference.rpartition(".")
        if not separator:
            return None
        matching = [item for item in events if item.source == part_id and property_name in item.payload]
        return matching[-1].payload.get(property_name) if matching else None
    return None


def _compare(assertion: SimulationScenarioAssertion, observed: object | None) -> bool:
    expected = assertion.expected
    if assertion.operator == "CONTAINS":
        if isinstance(observed, str):
            return str(expected) in observed
        if isinstance(observed, (list, dict)):
            return expected in observed
        return False
    if assertion.operator == "BETWEEN":
        if (
            not isinstance(expected, list)
            or len(expected) != 2
            or not isinstance(observed, (int, float))
        ):
            return False
        return float(expected[0]) <= float(observed) <= float(expected[1])
    if (
        assertion.tolerance is not None
        and isinstance(expected, (int, float))
        and isinstance(observed, (int, float))
    ):
        return abs(float(observed) - float(expected)) <= assertion.tolerance
    return observed == expected


def _scenario_status(
    runtime_result: RuntimeExecutionResult,
    assertions: list[SimulationAssertionResult],
) -> SimulationScenarioResultStatus:
    mapping = {
        RuntimeExecutionStatus.TIMED_OUT: SimulationScenarioResultStatus.TIMED_OUT,
        RuntimeExecutionStatus.CANCELED: SimulationScenarioResultStatus.CANCELED,
        RuntimeExecutionStatus.CRASHED: SimulationScenarioResultStatus.CRASHED,
    }
    if runtime_result.status in mapping:
        return mapping[runtime_result.status]
    if runtime_result.status is not RuntimeExecutionStatus.COMPLETED:
        return SimulationScenarioResultStatus.FAILED
    if any(item.status is not SimulationAssertionStatus.PASSED for item in assertions):
        return SimulationScenarioResultStatus.FAILED
    return SimulationScenarioResultStatus.PASSED


def _run_status(
    required: list[SimulationScenarioRunResult],
    engine_mode: RuntimeEngineMode,
) -> SimulationRunStatus:
    for status, run_status in (
        (SimulationScenarioResultStatus.TIMED_OUT, SimulationRunStatus.TIMED_OUT),
        (SimulationScenarioResultStatus.CANCELED, SimulationRunStatus.CANCELED),
        (SimulationScenarioResultStatus.CRASHED, SimulationRunStatus.CRASHED),
    ):
        if any(item.status is status for item in required):
            return run_status
    if any(item.status is not SimulationScenarioResultStatus.PASSED for item in required):
        return SimulationRunStatus.FAILED
    return (
        SimulationRunStatus.PASSED
        if engine_mode is RuntimeEngineMode.NATIVE_MICROPYTHON
        else SimulationRunStatus.CONFORMANCE_PASSED
    )


def _scenario_explanation(
    scenario: SimulationScenario,
    status: SimulationScenarioResultStatus,
    assertions: list[SimulationAssertionResult],
    runtime_result: RuntimeExecutionResult,
) -> str:
    if runtime_result.error is not None:
        return f"{scenario.title}未完成：{runtime_result.error.message}"
    failed = [item for item in assertions if item.status is not SimulationAssertionStatus.PASSED]
    if failed:
        return f"{scenario.title}有 {len(failed)} 个检查未满足；请查看观察值后修正。"
    return f"{scenario.title}的 {len(assertions)} 个检查均满足。"


def _run_explanation(
    status: SimulationRunStatus,
    eligible: bool,
    required: list[SimulationScenarioRunResult],
) -> str:
    if eligible:
        return f"{len(required)} 个必测场景均由已校验原生 MicroPython core 执行并通过，已形成正式行为验证记录。"
    if status is SimulationRunStatus.CONFORMANCE_PASSED:
        return (
            f"{len(required)} 个必测场景的一致性检查通过；当前执行层不可生成 L1，"
            "作品仍停留在可运行仿真状态。"
        )
    failed = sum(item.status is not SimulationScenarioResultStatus.PASSED for item in required)
    return f"必测场景中有 {failed} 个未通过；未生成行为仿真证据。"


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _optional_str(value: object) -> str | None:
    return str(value) if value is not None else None
