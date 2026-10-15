"""SQLite persistence for immutable Turn plans and revision pins."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from zhangwen.domains.events.store import RealtimeEventStore
from zhangwen.domains.orchestration.models import (
    ExecutionRevisionBinding,
    ExecutionRevisionSet,
    InternalUnit,
    InvocationFallback,
    InvocationFallbackCode,
    InvocationPlan,
    InvocationStep,
    InvocationStepStatus,
    UnifiedTurn,
    UnifiedTurnStatus,
)
from zhangwen.domains.orchestration.resolver import ResolvedUnitRevision
from zhangwen.domains.packages.privacy import redact_replay_input
from zhangwen.settings.models import RuntimeModelSelection


class TurnNotFoundError(LookupError):
    pass


class TurnConflictError(ValueError):
    pass


class TurnRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._events = RealtimeEventStore(self._db_path)

    def start(
        self,
        *,
        work_id: str,
        idempotency_key: str,
        message: str,
        intent: str,
        work_snapshot: dict[str, object],
        resolutions: list[ResolvedUnitRevision],
        runtime_selection: RuntimeModelSelection,
    ) -> tuple[UnifiedTurn, bool]:
        turn_id = _id("turn")
        revision_set_id = _id("revision_set")
        plan_id = _id("invocation_plan")
        now = _now()
        bindings = _unique_bindings(resolutions)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                """
                SELECT id, user_message FROM unified_turns
                WHERE work_id = ? AND idempotency_key = ?
                """,
                (work_id, idempotency_key),
            ).fetchone()
            if existing is not None:
                if str(existing["user_message"]) != message:
                    raise TurnConflictError(
                        "同一幂等键不能提交不同的作品补充。"
                    )
                return self._get(conn, str(existing["id"])), False

            conn.execute(
                """
                INSERT INTO execution_revision_sets (
                  id, work_id, owner_kind, owner_id, bindings_json, created_at,
                  provider_configuration_id,
                  provider_configuration_revision_id,
                  routing_profile_revision_id, model, model_workload
                ) VALUES (?, ?, 'TURN', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    revision_set_id,
                    work_id,
                    turn_id,
                    _dump([item.model_dump(mode="json", by_alias=True) for item in bindings]),
                    now,
                    runtime_selection.provider_configuration_id,
                    runtime_selection.provider_configuration_revision_id,
                    runtime_selection.routing_profile_revision_id,
                    str(runtime_selection.model),
                    runtime_selection.workload.value,
                ),
            )
            conn.execute(
                """
                INSERT INTO unified_turns (
                  id, work_id, idempotency_key, user_message, status,
                  assistant_response, natural_status, revision_set_id,
                  created_at, updated_at, completed_at
                ) VALUES (?, ?, ?, ?, 'RUNNING', NULL, ?, ?, ?, ?, NULL)
                """,
                (
                    turn_id,
                    work_id,
                    idempotency_key,
                    message,
                    "掌问正在整理这次补充。",
                    revision_set_id,
                    now,
                    now,
                ),
            )
            replay_input, redacted = redact_replay_input(
                {
                    "userMessage": message,
                    "intent": intent,
                    "workSnapshot": work_snapshot,
                }
            )
            conn.execute(
                """
                INSERT INTO package_input_snapshots (
                  id, source_turn_id, work_id, input_json,
                  execution_revision_set_json, redacted, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _id("package_input"),
                    turn_id,
                    work_id,
                    _dump(replay_input),
                    _dump(
                        {
                            "id": revision_set_id,
                            "bindings": [
                                item.model_dump(mode="json", by_alias=True)
                                for item in bindings
                            ],
                            "providerConfigurationId": (
                                runtime_selection.provider_configuration_id
                            ),
                            "providerConfigurationRevisionId": (
                                runtime_selection.provider_configuration_revision_id
                            ),
                            "routingProfileRevisionId": (
                                runtime_selection.routing_profile_revision_id
                            ),
                            "model": str(runtime_selection.model),
                            "modelWorkload": runtime_selection.workload.value,
                            "createdAt": now,
                        }
                    ),
                    1 if redacted else 0,
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO invocation_plans (
                  id, turn_id, work_id, intent, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'RUNNING', ?, ?)
                """,
                (plan_id, turn_id, work_id, intent, now, now),
            )
            for position, resolution in enumerate(resolutions):
                conn.execute(
                    """
                    INSERT INTO invocation_steps (
                      id, plan_id, position, unit, status,
                      agent_package_revision_id, skill_revision_ids_json,
                      output_summary, fallback_code, fallback_message,
                      started_at, completed_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, 'QUEUED', ?, ?, NULL, NULL, NULL,
                              NULL, NULL, ?, ?)
                    """,
                    (
                        _id("invocation_step"),
                        plan_id,
                        position,
                        resolution.unit.value,
                        resolution.agent_binding.package_revision_id,
                        _dump(
                            [
                                item.package_revision_id
                                for item in resolution.skill_bindings
                            ]
                        ),
                        now,
                        now,
                    ),
                )
            self._events.append_work_event(
                conn,
                work_id=work_id,
                event_type="turn.started",
                source_event_id=f"{turn_id}:started",
                payload={
                    "turnId": turn_id,
                    "status": UnifiedTurnStatus.RUNNING.value,
                    "unitCount": len(resolutions),
                },
            )
            return self._get(conn, turn_id), True

    def finalize(
        self,
        turn_id: str,
        *,
        status: UnifiedTurnStatus,
        assistant_response: str,
        natural_status: str,
        outcomes: list["StepOutcome"],
    ) -> UnifiedTurn:
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT work_id FROM unified_turns WHERE id = ?",
                (turn_id,),
            ).fetchone()
            if row is None:
                raise TurnNotFoundError("Turn 不存在。")
            plan_row = conn.execute(
                "SELECT id FROM invocation_plans WHERE turn_id = ?",
                (turn_id,),
            ).fetchone()
            assert plan_row is not None
            plan_id = str(plan_row["id"])
            step_rows = conn.execute(
                """
                SELECT id, unit FROM invocation_steps
                WHERE plan_id = ? ORDER BY position ASC
                """,
                (plan_id,),
            ).fetchall()
            if len(step_rows) != len(outcomes):
                raise TurnConflictError("Invocation outcome count does not match the pinned plan")
            for step_row, outcome in zip(step_rows, outcomes, strict=True):
                if str(step_row["unit"]) != outcome.unit.value:
                    raise TurnConflictError(
                        "Invocation outcome order does not match the pinned plan"
                    )
                fallback = outcome.fallback
                conn.execute(
                    """
                    UPDATE invocation_steps
                    SET status = ?, output_summary = ?, fallback_code = ?,
                        fallback_message = ?, started_at = ?, completed_at = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        outcome.status.value,
                        outcome.output_summary,
                        fallback.code.value if fallback is not None else None,
                        fallback.natural_message if fallback is not None else None,
                        outcome.started_at,
                        outcome.completed_at,
                        now,
                        str(step_row["id"]),
                    ),
                )
            conn.execute(
                "UPDATE invocation_plans SET status = ?, updated_at = ? WHERE id = ?",
                (status.value, now, plan_id),
            )
            conn.execute(
                """
                UPDATE unified_turns
                SET status = ?, assistant_response = ?, natural_status = ?,
                    updated_at = ?, completed_at = ?
                WHERE id = ?
                """,
                (status.value, assistant_response, natural_status, now, now, turn_id),
            )
            self._events.append_work_event(
                conn,
                work_id=str(row["work_id"]),
                event_type=(
                    "turn.completed"
                    if status is UnifiedTurnStatus.COMPLETED
                    else "turn.degraded"
                    if status is UnifiedTurnStatus.DEGRADED
                    else "turn.failed"
                ),
                source_event_id=f"{turn_id}:final",
                payload={
                    "turnId": turn_id,
                    "status": status.value,
                    "fallbackCount": sum(
                        1 for outcome in outcomes if outcome.fallback is not None
                    ),
                },
            )
            return self._get(conn, turn_id)

    def get(self, turn_id: str) -> UnifiedTurn:
        with self._connect() as conn:
            return self._get(conn, turn_id)

    def find_by_idempotency(
        self,
        work_id: str,
        idempotency_key: str,
    ) -> UnifiedTurn | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id FROM unified_turns
                WHERE work_id = ? AND idempotency_key = ?
                """,
                (work_id, idempotency_key),
            ).fetchone()
            return self._get(conn, str(row["id"])) if row is not None else None

    def list(self, work_id: str) -> list[UnifiedTurn]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id FROM unified_turns
                WHERE work_id = ? ORDER BY created_at ASC, id ASC
                """,
                (work_id,),
            ).fetchall()
            return [self._get(conn, str(row["id"])) for row in rows]

    def _get(self, conn: sqlite3.Connection, turn_id: str) -> UnifiedTurn:
        turn_row = conn.execute(
            "SELECT * FROM unified_turns WHERE id = ?", (turn_id,)
        ).fetchone()
        if turn_row is None:
            raise TurnNotFoundError("Turn 不存在。")
        plan_row = conn.execute(
            "SELECT * FROM invocation_plans WHERE turn_id = ?", (turn_id,)
        ).fetchone()
        revision_row = conn.execute(
            "SELECT * FROM execution_revision_sets WHERE id = ?",
            (turn_row["revision_set_id"],),
        ).fetchone()
        assert plan_row is not None and revision_row is not None
        step_rows = conn.execute(
            """
            SELECT * FROM invocation_steps
            WHERE plan_id = ? ORDER BY position ASC
            """,
            (plan_row["id"],),
        ).fetchall()
        revision_set = ExecutionRevisionSet(
            id=str(revision_row["id"]),
            bindings=[
                ExecutionRevisionBinding.model_validate(item)
                for item in json.loads(str(revision_row["bindings_json"]))
            ],
            providerConfigurationId=revision_row["provider_configuration_id"],
            providerConfigurationRevisionId=revision_row[
                "provider_configuration_revision_id"
            ],
            routingProfileRevisionId=revision_row["routing_profile_revision_id"],
            model=revision_row["model"],
            modelWorkload=revision_row["model_workload"],
            createdAt=str(revision_row["created_at"]),
        )
        plan = InvocationPlan(
            id=str(plan_row["id"]),
            intent=str(plan_row["intent"]),
            status=UnifiedTurnStatus(str(plan_row["status"])),
            revisionSet=revision_set,
            steps=[_step_from_row(row) for row in step_rows],
            createdAt=str(plan_row["created_at"]),
            updatedAt=str(plan_row["updated_at"]),
        )
        return UnifiedTurn(
            id=str(turn_row["id"]),
            workId=str(turn_row["work_id"]),
            idempotencyKey=str(turn_row["idempotency_key"]),
            userMessage=str(turn_row["user_message"]),
            status=UnifiedTurnStatus(str(turn_row["status"])),
            assistantResponse=turn_row["assistant_response"],
            naturalStatus=str(turn_row["natural_status"]),
            invocationPlan=plan,
            createdAt=str(turn_row["created_at"]),
            updatedAt=str(turn_row["updated_at"]),
            completedAt=turn_row["completed_at"],
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


class StepOutcome:
    def __init__(
        self,
        *,
        unit: InternalUnit,
        status: InvocationStepStatus,
        output_summary: str | None,
        fallback: InvocationFallback | None,
        started_at: str,
        completed_at: str,
    ) -> None:
        self.unit = unit
        self.status = status
        self.output_summary = output_summary
        self.fallback = fallback
        self.started_at = started_at
        self.completed_at = completed_at


def _step_from_row(row: sqlite3.Row) -> InvocationStep:
    fallback = None
    if row["fallback_code"] is not None:
        fallback = InvocationFallback(
            code=InvocationFallbackCode(str(row["fallback_code"])),
            naturalMessage=str(row["fallback_message"]),
        )
    return InvocationStep(
        id=str(row["id"]),
        position=int(row["position"]),
        unit=InternalUnit(str(row["unit"])),
        status=InvocationStepStatus(str(row["status"])),
        agentPackageRevisionId=str(row["agent_package_revision_id"]),
        skillRevisionIds=json.loads(str(row["skill_revision_ids_json"])),
        outputSummary=row["output_summary"],
        fallback=fallback,
        startedAt=row["started_at"],
        completedAt=row["completed_at"],
    )


def _unique_bindings(
    resolutions: list[ResolvedUnitRevision],
) -> list[ExecutionRevisionBinding]:
    result: dict[tuple[str, str], ExecutionRevisionBinding] = {}
    for resolution in resolutions:
        for binding in resolution.bindings:
            result[(binding.package_kind.value, binding.package_id)] = binding
    return list(result.values())


def _dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _now() -> str:
    return datetime.now(UTC).isoformat()
