"""Audited Skill Runtime and Tool Runner boundaries.

Real serial, firmware and filesystem adapters are intentionally not registered here.
Applications must register a bounded handler and satisfy the Skill confirmation policy.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import sqlite3
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from zhangwen.llm.contracts import (
    ChatMessageStatus,
    ChatProgressAction,
    ChatProgressEmitter,
    ChatProgressStatus,
)
from zhangwen.skills.models import (
    JsonSchemaObject,
    SkillConfirmationPolicy,
    SkillDefinition,
    SkillPermission,
    SkillRunResult,
    SkillRunStatus,
    ToolRunStatus,
)
from zhangwen.skills.repository import SkillRepository
from zhangwen.projects.models import ExpertType


ToolHandler = Callable[[dict[str, object]], Awaitable[dict[str, object]]]
TerminalFailureHandler = Callable[[int, str], None]

LOCAL_EXECUTION_PENDING_TITLE = "确认本地执行"
LOCAL_EXECUTION_PENDING_DESCRIPTION = "该操作可能产生本地或外部影响，确认后才能执行。"
LOCAL_EXECUTION_PENDING_REASON = "本地执行需要用户明确授权。"


class SkillAuthorizationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class SkillAuthorizationContext:
    pending_item_id: str
    project_id: str
    skill_run_id: str
    skill_id: str
    owner_expert: ExpertType
    conversation_id: str
    request_message_id: str
    response_message_id: str
    status: SkillRunStatus


class CadBuildEnqueueRequest(BaseModel):
    """Only identifiers owned by the local service may reach the CAD queue."""

    model_config = ConfigDict(extra="forbid")

    projectId: str = Field(min_length=1, max_length=120)
    cadRunId: str = Field(min_length=1, max_length=120)
    clientRequestId: str | None = Field(default=None, min_length=1, max_length=240)


class CadBuildEnqueueResult(BaseModel):
    """Stable Tool output independent of the eventual worker implementation."""

    model_config = ConfigDict(extra="forbid")

    cadJobId: str = Field(min_length=1, max_length=120)
    cadRunId: str = Field(min_length=1, max_length=120)
    status: str = Field(pattern="^(QUEUED|RUNNING|SUCCEEDED)$")


CadBuildEnqueueValue = CadBuildEnqueueResult | dict[str, object]


_TOOL_REQUIRED_PERMISSIONS: dict[str, frozenset[SkillPermission]] = {
    "cad.build": frozenset(
        {
            SkillPermission.RUN_CAD,
            SkillPermission.WRITE_ARTIFACT,
        }
    ),
}


def validate_skill_permissions(skill: SkillDefinition) -> None:
    """Require every registered tool to be covered by the skill's permissions."""

    required: set[SkillPermission] = set()
    for tool_id in skill.requiredTools:
        required.update(_TOOL_REQUIRED_PERMISSIONS.get(tool_id, ()))
    missing = sorted(
        permission.value
        for permission in required.difference(skill.permissions)
    )
    if missing:
        raise ValueError(
            f"Skill {skill.id} lacks required permissions: {', '.join(missing)}"
        )


class CadBuildEnqueueHandler(Protocol):
    def __call__(
        self,
        request: CadBuildEnqueueRequest,
    ) -> CadBuildEnqueueValue | Awaitable[CadBuildEnqueueValue]: ...


def cad_build_tool_handler(enqueue: CadBuildEnqueueHandler) -> ToolHandler:
    """Adapt a trusted application enqueue function to the generic ToolRunner."""

    async def handler(payload: dict[str, object]) -> dict[str, object]:
        request = CadBuildEnqueueRequest.model_validate(payload)
        raw_result = enqueue(request)
        if inspect.isawaitable(raw_result):
            raw_result = await raw_result
        result = CadBuildEnqueueResult.model_validate(raw_result)
        if result.cadRunId != request.cadRunId:
            raise ValueError("cad.build returned a different cadRunId")
        return result.model_dump(mode="json")

    return handler


class ToolRunner:
    def __init__(self, db_path: Path, handlers: dict[str, ToolHandler] | None = None) -> None:
        self._db_path = db_path
        self._handlers: dict[str, ToolHandler] = {}
        for tool_id, handler in (handlers or {}).items():
            self.register(tool_id, handler)

    def register(self, tool_id: str, handler: ToolHandler) -> None:
        if not tool_id.strip():
            raise ValueError("tool_id is required")
        if not inspect.iscoroutinefunction(handler):
            raise ValueError("Tool handlers must be async functions")
        self._handlers[tool_id] = handler

    @classmethod
    def with_cad_build(
        cls,
        db_path: Path,
        enqueue: CadBuildEnqueueHandler,
    ) -> "ToolRunner":
        return cls(db_path, {"cad.build": cad_build_tool_handler(enqueue)})

    async def run(
        self,
        *,
        project_id: str,
        skill_run_id: str,
        tool_id: str,
        payload: dict[str, object],
        timeout_ms: int,
        max_retries: int,
        backoff_ms: int,
        progress_emitter: ChatProgressEmitter | None = None,
        on_terminal_failure: TerminalFailureHandler | None = None,
    ) -> tuple[dict[str, object], int]:
        handler = self._handlers.get(tool_id)
        if handler is None:
            raise ValueError(f"Tool is not registered: {tool_id}")
        last_error: Exception | None = None
        for attempt in range(max_retries + 1):
            run_id = _id("toolrun")
            started = _now()
            self._insert_tool_run(
                run_id=run_id,
                project_id=project_id,
                skill_run_id=skill_run_id,
                tool_id=tool_id,
                payload=payload,
                timeout_ms=timeout_ms,
                retry_count=attempt,
                created_at=started,
            )
            progress_id = (
                progress_emitter.next_id("tool.execute")
                if progress_emitter is not None
                else None
            )
            if progress_emitter is not None and progress_id is not None:
                progress_emitter.emit(
                    progress_id=progress_id,
                    action=ChatProgressAction.LOCAL_TOOL_EXECUTION,
                    status=ChatProgressStatus.RUNNING,
                )
            try:
                result = await asyncio.wait_for(
                    handler(payload),
                    timeout=timeout_ms / 1000,
                )
                if not isinstance(result, dict):
                    raise ValueError("Tool output must be an object")
                self._finish_tool_run(run_id, ToolRunStatus.COMPLETED, result, None)
                if progress_emitter is not None and progress_id is not None:
                    progress_emitter.emit(
                        progress_id=progress_id,
                        action=ChatProgressAction.LOCAL_TOOL_EXECUTION,
                        status=ChatProgressStatus.COMPLETED,
                    )
                return result, attempt
            except asyncio.CancelledError:
                self._finish_tool_run(
                    run_id,
                    ToolRunStatus.FAILED,
                    None,
                    "Tool execution canceled",
                )
                if on_terminal_failure is not None:
                    on_terminal_failure(attempt, "Tool execution canceled")
                if progress_emitter is not None and progress_id is not None:
                    progress_emitter.emit(
                        progress_id=progress_id,
                        action=ChatProgressAction.LOCAL_TOOL_EXECUTION,
                        status=ChatProgressStatus.FAILED,
                    )
                raise
            except Exception as exc:
                last_error = exc
                self._finish_tool_run(run_id, ToolRunStatus.FAILED, None, str(exc))
                terminal_failure = attempt >= max_retries
                if terminal_failure and on_terminal_failure is not None:
                    on_terminal_failure(attempt, str(exc))
                if progress_emitter is not None and progress_id is not None:
                    progress_emitter.emit(
                        progress_id=progress_id,
                        action=ChatProgressAction.LOCAL_TOOL_EXECUTION,
                        status=ChatProgressStatus.FAILED,
                    )
                if not terminal_failure and backoff_ms:
                    try:
                        await asyncio.sleep(backoff_ms / 1000)
                    except asyncio.CancelledError:
                        if on_terminal_failure is not None:
                            on_terminal_failure(attempt, "Tool execution canceled")
                        raise
        raise RuntimeError(str(last_error or "Tool execution failed"))

    def _insert_tool_run(
        self,
        *,
        run_id: str,
        project_id: str,
        skill_run_id: str,
        tool_id: str,
        payload: dict[str, object],
        timeout_ms: int,
        retry_count: int,
        created_at: str,
    ) -> None:
        with _connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO tool_runs (
                  id, project_id, skill_run_id, tool_id, status, input_json,
                  output_json, error, retry_count, timeout_ms, created_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, NULL)
                """,
                (
                    run_id,
                    project_id,
                    skill_run_id,
                    tool_id,
                    ToolRunStatus.RUNNING.value,
                    json.dumps(payload, ensure_ascii=False),
                    retry_count,
                    timeout_ms,
                    created_at,
                ),
            )

    def _finish_tool_run(
        self,
        run_id: str,
        status: ToolRunStatus,
        output: dict[str, object] | None,
        error: str | None,
    ) -> None:
        with _connect(self._db_path) as conn:
            conn.execute(
                """
                UPDATE tool_runs
                SET status = ?, output_json = ?, error = ?, completed_at = ?
                WHERE id = ?
                """,
                (
                    status.value,
                    json.dumps(output, ensure_ascii=False) if output is not None else None,
                    error,
                    _now(),
                    run_id,
                ),
            )


class SkillRuntime:
    def __init__(self, db_path: Path, tool_runner: ToolRunner | None = None) -> None:
        self._db_path = db_path
        self._repository = SkillRepository(db_path)
        self._tool_runner = tool_runner or ToolRunner(db_path)

    @classmethod
    def with_cad_build(
        cls,
        db_path: Path,
        enqueue: CadBuildEnqueueHandler,
    ) -> "SkillRuntime":
        """Composition point for the user-confirmed CAD Job application service."""

        return cls(db_path, ToolRunner.with_cad_build(db_path, enqueue))

    async def run(
        self,
        *,
        project_id: str,
        skill_id: str,
        payload: dict[str, object],
        expert_run_id: str | None = None,
        confirmed: bool = False,
        requesting_expert: ExpertType | None = None,
        progress_emitter: ChatProgressEmitter | None = None,
    ) -> SkillRunResult:
        skill = self._skill(skill_id)
        if requesting_expert is not None and skill.ownerExpert != requesting_expert:
            raise ValueError(
                f"Skill {skill.id} belongs to {skill.ownerExpert.value}, not {requesting_expert.value}"
            )
        if not skill.enabled:
            raise ValueError("Skill is disabled")
        payload_project_id = payload.get("projectId")
        if payload_project_id is not None and payload_project_id != project_id:
            raise ValueError("Skill input projectId does not match the requested project")
        _validate_schema(payload, skill.inputSchema, path="input")
        validate_skill_permissions(skill)
        confirmation_required = skill.confirmationPolicy in {
            SkillConfirmationPolicy.ALWAYS,
            SkillConfirmationPolicy.BEFORE_EXTERNAL_EFFECT,
        }
        run_id = _id("skillrun")
        now = _now()
        initial_status = (
            SkillRunStatus.AWAITING_CONFIRMATION
            if confirmation_required and not confirmed
            else SkillRunStatus.RUNNING
        )
        self._insert_skill_run(
            run_id=run_id,
            project_id=project_id,
            expert_run_id=expert_run_id,
            skill=skill,
            payload=payload,
            status=initial_status,
            confirmation_required=confirmation_required,
            confirmed=confirmed,
            created_at=now,
        )
        authorization_progress_id = None
        if confirmation_required and progress_emitter is not None:
            authorization_progress_id = progress_emitter.next_id("local.authorization")
            progress_emitter.emit(
                progress_id=authorization_progress_id,
                action=ChatProgressAction.LOCAL_EXECUTION_AUTHORIZATION,
                status=(
                    ChatProgressStatus.WAITING
                    if initial_status == SkillRunStatus.AWAITING_CONFIRMATION
                    else ChatProgressStatus.COMPLETED
                ),
            )
        if initial_status == SkillRunStatus.AWAITING_CONFIRMATION:
            return _skill_result(
                run_id,
                project_id,
                skill,
                initial_status,
                confirmation_required=True,
            )

        return await self._execute_skill_run(
            run_id=run_id,
            project_id=project_id,
            skill=skill,
            payload=payload,
            confirmation_required=confirmation_required,
            progress_emitter=progress_emitter,
        )

    def bind_authorization(
        self,
        *,
        project_id: str,
        pending_item_id: str,
        skill_run_id: str,
    ) -> SkillAuthorizationContext:
        now = _now()
        with _connect(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT s.project_id, s.status, s.confirmation_required,
                       s.skill_id, s.owner_expert_type, s.expert_run_id,
                       e.conversation_id, e.request_message_id, e.response_message_id,
                       p.status AS pending_status, p.priority, p.title, p.reason
                FROM skill_runs s
                JOIN expert_runs e ON e.id = s.expert_run_id
                JOIN conversations c
                  ON c.id = e.conversation_id AND c.project_id = s.project_id
                JOIN messages request_message
                  ON request_message.id = e.request_message_id
                 AND request_message.project_id = s.project_id
                 AND request_message.conversation_id = e.conversation_id
                 AND request_message.role = 'user'
                JOIN messages response_message
                  ON response_message.id = e.response_message_id
                 AND response_message.project_id = s.project_id
                 AND response_message.conversation_id = e.conversation_id
                 AND response_message.role = 'assistant'
                JOIN project_pending_items p ON p.id = ? AND p.project_id = s.project_id
                WHERE s.id = ? AND s.project_id = ?
                """,
                (pending_item_id, skill_run_id, project_id),
            ).fetchone()
            if row is None:
                raise SkillAuthorizationError(
                    "SKILL_AUTHORIZATION_CONTEXT_INVALID",
                    "本地执行授权缺少可恢复的运行上下文。",
                )
            if (
                row["status"] != SkillRunStatus.AWAITING_CONFIRMATION.value
                or not bool(row["confirmation_required"])
                or row["pending_status"] != "open"
                or row["priority"] != "confirmation"
                or row["title"] != LOCAL_EXECUTION_PENDING_TITLE
                or row["reason"] != LOCAL_EXECUTION_PENDING_REASON
                or not row["conversation_id"]
                or not row["request_message_id"]
                or not row["response_message_id"]
                or not row["owner_expert_type"]
            ):
                raise SkillAuthorizationError(
                    "SKILL_AUTHORIZATION_CONTEXT_INVALID",
                    "本地执行授权状态无效，不能恢复执行。",
                )
            conn.execute(
                """
                INSERT INTO skill_run_authorizations (
                  pending_item_id, project_id, skill_run_id, created_at,
                  claimed_at, completed_at
                ) VALUES (?, ?, ?, ?, NULL, NULL)
                """,
                (pending_item_id, project_id, skill_run_id, now),
            )
        return self.authorization_context(
            project_id=project_id,
            pending_item_id=pending_item_id,
        )

    def fail_unbound_authorization(
        self,
        *,
        project_id: str,
        skill_run_id: str,
    ) -> None:
        """Close a confirmation run that cannot be tied to persisted chat state."""

        with _connect(self._db_path) as conn:
            updated = conn.execute(
                """
                UPDATE skill_runs
                SET status = ?, error = ?, completed_at = ?
                WHERE id = ? AND project_id = ? AND status = ?
                  AND NOT EXISTS (
                    SELECT 1 FROM skill_run_authorizations
                    WHERE skill_run_id = skill_runs.id
                  )
                """,
                (
                    SkillRunStatus.FAILED.value,
                    "Skill authorization could not be bound to persisted chat messages",
                    _now(),
                    skill_run_id,
                    project_id,
                    SkillRunStatus.AWAITING_CONFIRMATION.value,
                ),
            )
        if updated.rowcount != 1:
            raise SkillAuthorizationError(
                "SKILL_AUTHORIZATION_CONTEXT_INVALID",
                "本地执行授权状态无效，不能安全关闭。",
            )

    def has_authorization(self, *, project_id: str, pending_item_id: str) -> bool:
        with _connect(self._db_path) as conn:
            return (
                conn.execute(
                    """
                    SELECT 1 FROM skill_run_authorizations
                    WHERE project_id = ? AND pending_item_id = ?
                    """,
                    (project_id, pending_item_id),
                ).fetchone()
                is not None
            )

    def authorization_context(
        self,
        *,
        project_id: str,
        pending_item_id: str,
    ) -> SkillAuthorizationContext:
        with _connect(self._db_path) as conn:
            row = self._authorization_row(conn, project_id, pending_item_id)
        return self._authorization_context(row)

    async def resume_authorized(
        self,
        *,
        project_id: str,
        pending_item_id: str,
        progress_emitter: ChatProgressEmitter | None = None,
    ) -> SkillRunResult:
        row, claimed = self._claim_authorization(project_id, pending_item_id)
        context = self._authorization_context(row)
        if not claimed:
            if context.status in {SkillRunStatus.COMPLETED, SkillRunStatus.FAILED}:
                return self._result_from_authorization_row(row)
            raise SkillAuthorizationError(
                "SKILL_AUTHORIZATION_IN_PROGRESS",
                "本地执行已由另一请求启动，请等待当前执行完成。",
            )

        try:
            skill = self._skill(context.skill_id)
        except ValueError as exc:
            self._fail_claimed_authorization(
                context,
                "Skill definition changed after authorization",
            )
            raise SkillAuthorizationError(
                "SKILL_AUTHORIZATION_CONTEXT_INVALID",
                "本地执行能力已变化，请重新发起操作。",
            ) from exc
        if not skill.enabled or skill.ownerExpert != context.owner_expert:
            self._fail_claimed_authorization(
                context,
                "Skill definition changed after authorization",
            )
            raise SkillAuthorizationError(
                "SKILL_AUTHORIZATION_CONTEXT_INVALID",
                "本地执行能力已变化，请重新发起操作。",
            )
        try:
            raw_payload = row["input_json"]
            if not isinstance(raw_payload, str):
                raise ValueError("Skill input is not serialized JSON")
            payload = json.loads(raw_payload)
            if not isinstance(payload, dict):
                raise ValueError("Skill input is not an object")
            _validate_schema(payload, skill.inputSchema, path="input")
            validate_skill_permissions(skill)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            self._fail_claimed_authorization(context, str(exc))
            raise SkillAuthorizationError(
                "SKILL_AUTHORIZATION_CONTEXT_INVALID",
                "本地执行权限或输入已变化，请重新发起操作。",
            ) from exc

        emitter = progress_emitter or ChatProgressEmitter()
        emitter.emit(
            progress_id=emitter.next_id("local.authorization"),
            action=ChatProgressAction.LOCAL_EXECUTION_AUTHORIZATION,
            status=ChatProgressStatus.COMPLETED,
        )
        try:
            return await self._execute_skill_run(
                run_id=context.skill_run_id,
                project_id=context.project_id,
                skill=skill,
                payload=payload,
                confirmation_required=True,
                progress_emitter=emitter,
            )
        finally:
            self._mark_authorization_completed(context)

    def dismiss_authorization(
        self,
        *,
        project_id: str,
        pending_item_id: str,
    ) -> bool:
        now = _now()
        with _connect(self._db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                row = conn.execute(
                    """
                    SELECT a.claimed_at, a.completed_at, a.skill_run_id, s.status
                    FROM skill_run_authorizations a
                    JOIN skill_runs s ON s.id = a.skill_run_id
                    WHERE a.project_id = ? AND a.pending_item_id = ?
                    """,
                    (project_id, pending_item_id),
                ).fetchone()
                if row is None:
                    conn.commit()
                    return False
                if row["claimed_at"] is not None and row["completed_at"] is None:
                    raise SkillAuthorizationError(
                        "SKILL_AUTHORIZATION_IN_PROGRESS",
                        "本地执行已经开始，不能再撤销授权。",
                    )
                if row["completed_at"] is None:
                    conn.execute(
                        """
                        UPDATE skill_runs
                        SET status = ?, error = ?, completed_at = ?
                        WHERE id = ? AND status = ?
                        """,
                        (
                            SkillRunStatus.FAILED.value,
                            "Skill execution authorization dismissed",
                            now,
                            row["skill_run_id"],
                            SkillRunStatus.AWAITING_CONFIRMATION.value,
                        ),
                    )
                    conn.execute(
                        """
                        UPDATE skill_run_authorizations
                        SET claimed_at = COALESCE(claimed_at, ?), completed_at = ?
                        WHERE project_id = ? AND pending_item_id = ?
                        """,
                        (now, now, project_id, pending_item_id),
                    )
                    conn.execute(
                        """
                        UPDATE project_pending_items
                        SET status = 'dismissed', is_highlighted = 0, updated_at = ?
                        WHERE project_id = ? AND id = ? AND status = 'open'
                        """,
                        (now, project_id, pending_item_id),
                    )
                conn.commit()
                return True
            except Exception:
                conn.rollback()
                raise

    async def _execute_skill_run(
        self,
        *,
        run_id: str,
        project_id: str,
        skill: SkillDefinition,
        payload: dict[str, object],
        confirmation_required: bool,
        progress_emitter: ChatProgressEmitter | None,
    ) -> SkillRunResult:

        retry_count = 0
        failure_recorded = False

        def record_terminal_failure(failed_retries: int, error: str) -> None:
            nonlocal failure_recorded, retry_count
            retry_count += failed_retries
            self._finish_skill_run(
                run_id,
                SkillRunStatus.FAILED,
                None,
                error,
                retry_count,
            )
            failure_recorded = True

        try:
            tool_outputs: dict[str, object] = {}
            for tool_id in skill.requiredTools:
                tool_output, retries = await self._tool_runner.run(
                    project_id=project_id,
                    skill_run_id=run_id,
                    tool_id=tool_id,
                    payload=payload,
                    timeout_ms=skill.timeoutPolicy.timeoutMs,
                    max_retries=skill.retryPolicy.maxRetries,
                    backoff_ms=skill.retryPolicy.backoffMs,
                    progress_emitter=progress_emitter,
                    on_terminal_failure=record_terminal_failure,
                )
                tool_outputs[tool_id] = tool_output
                retry_count += retries
            output = _default_skill_output(skill, payload, tool_outputs)
            _validate_schema(output, skill.outputSchema, path="output")
            self._finish_skill_run(
                run_id,
                SkillRunStatus.COMPLETED,
                output,
                None,
                retry_count,
            )
            return _skill_result(
                run_id,
                project_id,
                skill,
                SkillRunStatus.COMPLETED,
                output=output,
                retry_count=retry_count,
                confirmation_required=confirmation_required,
            )
        except asyncio.CancelledError:
            if not failure_recorded:
                self._finish_skill_run(
                    run_id,
                    SkillRunStatus.FAILED,
                    None,
                    "Skill execution canceled",
                    retry_count,
                )
            raise
        except Exception as exc:
            if not failure_recorded:
                self._finish_skill_run(
                    run_id,
                    SkillRunStatus.FAILED,
                    None,
                    str(exc),
                    retry_count,
                )
            return _skill_result(
                run_id,
                project_id,
                skill,
                SkillRunStatus.FAILED,
                error=str(exc),
                retry_count=retry_count,
                confirmation_required=confirmation_required,
            )

    def _claim_authorization(
        self,
        project_id: str,
        pending_item_id: str,
    ) -> tuple[sqlite3.Row, bool]:
        now = _now()
        with _connect(self._db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._authorization_row(conn, project_id, pending_item_id)
                context = self._authorization_context(row)
                skill_status = context.status
                if row["completed_at"] is not None:
                    conn.commit()
                    return row, False
                if row["claimed_at"] is not None:
                    if skill_status in {SkillRunStatus.COMPLETED, SkillRunStatus.FAILED}:
                        conn.execute(
                            """
                            UPDATE skill_run_authorizations SET completed_at = ?
                            WHERE project_id = ? AND pending_item_id = ?
                            """,
                            (now, project_id, pending_item_id),
                        )
                        conn.commit()
                        with _connect(self._db_path) as read_conn:
                            return self._authorization_row(
                                read_conn, project_id, pending_item_id
                            ), False
                    conn.commit()
                    return row, False
                if (
                    skill_status != SkillRunStatus.AWAITING_CONFIRMATION
                    or not bool(row["confirmation_required"])
                    or row["pending_status"] != "open"
                    or row["priority"] != "confirmation"
                    or row["title"] != LOCAL_EXECUTION_PENDING_TITLE
                    or row["reason"] != LOCAL_EXECUTION_PENDING_REASON
                    or row["response_message_status"]
                    != ChatMessageStatus.COMPLETED.value
                ):
                    raise SkillAuthorizationError(
                        "SKILL_AUTHORIZATION_NOT_RESUMABLE",
                        "该授权记录不能安全恢复，请重新发起操作。",
                    )
                claimed = conn.execute(
                    """
                    UPDATE skill_run_authorizations SET claimed_at = ?
                    WHERE project_id = ? AND pending_item_id = ? AND claimed_at IS NULL
                    """,
                    (now, project_id, pending_item_id),
                )
                if claimed.rowcount != 1:
                    conn.commit()
                    return row, False
                updated = conn.execute(
                    """
                    UPDATE skill_runs
                    SET status = ?, confirmed_at = ?, error = NULL, completed_at = NULL
                    WHERE id = ? AND project_id = ? AND status = ?
                    """,
                    (
                        SkillRunStatus.RUNNING.value,
                        now,
                        row["skill_run_id"],
                        project_id,
                        SkillRunStatus.AWAITING_CONFIRMATION.value,
                    ),
                )
                if updated.rowcount != 1:
                    raise SkillAuthorizationError(
                        "SKILL_AUTHORIZATION_NOT_RESUMABLE",
                        "该授权记录已变化，不能重复执行。",
                    )
                conn.execute(
                    """
                    UPDATE project_pending_items
                    SET status = 'resolved', is_highlighted = 0, updated_at = ?
                    WHERE project_id = ? AND id = ? AND status = 'open'
                    """,
                    (now, project_id, pending_item_id),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        with _connect(self._db_path) as conn:
            return self._authorization_row(conn, project_id, pending_item_id), True

    def _authorization_row(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        pending_item_id: str,
    ) -> sqlite3.Row:
        row = conn.execute(
            """
            SELECT a.pending_item_id, a.project_id, a.skill_run_id,
                   a.claimed_at, a.completed_at,
                   s.skill_id, s.owner_expert_type, s.status AS skill_status,
                   s.input_json, s.output_json, s.error, s.retry_count,
                   s.confirmation_required,
                   e.conversation_id, e.request_message_id, e.response_message_id,
                   response_message.status AS response_message_status,
                   p.status AS pending_status, p.priority, p.title, p.reason
            FROM skill_run_authorizations a
            JOIN skill_runs s ON s.id = a.skill_run_id AND s.project_id = a.project_id
            JOIN expert_runs e ON e.id = s.expert_run_id AND e.project_id = a.project_id
            JOIN conversations c
              ON c.id = e.conversation_id AND c.project_id = a.project_id
            JOIN messages request_message
              ON request_message.id = e.request_message_id
             AND request_message.project_id = a.project_id
             AND request_message.conversation_id = e.conversation_id
             AND request_message.role = 'user'
            JOIN messages response_message
              ON response_message.id = e.response_message_id
             AND response_message.project_id = a.project_id
             AND response_message.conversation_id = e.conversation_id
             AND response_message.role = 'assistant'
            JOIN project_pending_items p
              ON p.id = a.pending_item_id AND p.project_id = a.project_id
            WHERE a.project_id = ? AND a.pending_item_id = ?
            """,
            (project_id, pending_item_id),
        ).fetchone()
        if row is None:
            raise SkillAuthorizationError(
                "SKILL_AUTHORIZATION_NOT_FOUND",
                "没有找到可恢复的本地执行授权。",
            )
        return row

    @staticmethod
    def _authorization_context(row: sqlite3.Row) -> SkillAuthorizationContext:
        try:
            required_text: dict[str, str] = {}
            for key in (
                "pending_item_id",
                "project_id",
                "skill_run_id",
                "skill_id",
                "owner_expert_type",
                "conversation_id",
                "request_message_id",
                "response_message_id",
                "skill_status",
            ):
                value = row[key]
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"Missing authorization context field: {key}")
                required_text[key] = value
            return SkillAuthorizationContext(
                pending_item_id=required_text["pending_item_id"],
                project_id=required_text["project_id"],
                skill_run_id=required_text["skill_run_id"],
                skill_id=required_text["skill_id"],
                owner_expert=ExpertType(required_text["owner_expert_type"]),
                conversation_id=required_text["conversation_id"],
                request_message_id=required_text["request_message_id"],
                response_message_id=required_text["response_message_id"],
                status=SkillRunStatus(required_text["skill_status"]),
            )
        except (IndexError, KeyError, TypeError, ValueError) as exc:
            raise SkillAuthorizationError(
                "SKILL_AUTHORIZATION_CONTEXT_INVALID",
                "本地执行授权上下文无效。",
            ) from exc

    def _result_from_authorization_row(self, row: sqlite3.Row) -> SkillRunResult:
        context = self._authorization_context(row)
        output = json.loads(str(row["output_json"])) if row["output_json"] else None
        return _skill_result(
            context.skill_run_id,
            context.project_id,
            self._skill(context.skill_id),
            context.status,
            output=output,
            error=str(row["error"]) if row["error"] is not None else None,
            retry_count=int(row["retry_count"]),
            confirmation_required=bool(row["confirmation_required"]),
        )

    def _fail_claimed_authorization(
        self,
        context: SkillAuthorizationContext,
        error: str,
    ) -> None:
        self._finish_skill_run(
            context.skill_run_id,
            SkillRunStatus.FAILED,
            None,
            error,
            0,
        )
        self._mark_authorization_completed(context)

    def _mark_authorization_completed(
        self,
        context: SkillAuthorizationContext,
    ) -> None:
        with _connect(self._db_path) as conn:
            conn.execute(
                """
                UPDATE skill_run_authorizations
                SET completed_at = COALESCE(completed_at, ?)
                WHERE project_id = ? AND pending_item_id = ? AND claimed_at IS NOT NULL
                """,
                (_now(), context.project_id, context.pending_item_id),
            )

    def _skill(self, skill_id: str) -> SkillDefinition:
        skill = next(
            (item for item in self._repository.list_skills() if item.id == skill_id),
            None,
        )
        if skill is None:
            raise ValueError("Skill not found")
        return skill

    def _insert_skill_run(
        self,
        *,
        run_id: str,
        project_id: str,
        expert_run_id: str | None,
        skill: SkillDefinition,
        payload: dict[str, object],
        status: SkillRunStatus,
        confirmation_required: bool,
        confirmed: bool,
        created_at: str,
    ) -> None:
        with _connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO skill_runs (
                  id, project_id, expert_run_id, skill_id, owner_expert_type,
                  status, input_json, output_json, error, retry_count,
                  confirmation_required, confirmed_at, created_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, 0, ?, ?, ?, NULL)
                """,
                (
                    run_id,
                    project_id,
                    expert_run_id,
                    skill.id,
                    skill.ownerExpert.value,
                    status.value,
                    json.dumps(payload, ensure_ascii=False),
                    1 if confirmation_required else 0,
                    created_at if confirmed else None,
                    created_at,
                ),
            )

    def _finish_skill_run(
        self,
        run_id: str,
        status: SkillRunStatus,
        output: dict[str, object] | None,
        error: str | None,
        retry_count: int,
    ) -> None:
        with _connect(self._db_path) as conn:
            conn.execute(
                """
                UPDATE skill_runs
                SET status = ?, output_json = ?, error = ?, retry_count = ?, completed_at = ?
                WHERE id = ?
                """,
                (
                    status.value,
                    json.dumps(output, ensure_ascii=False) if output is not None else None,
                    error,
                    retry_count,
                    _now(),
                    run_id,
                ),
            )


def _default_skill_output(
    skill: SkillDefinition,
    payload: dict[str, object],
    tool_outputs: dict[str, object],
) -> dict[str, object]:
    if skill.requiredTools == ["cad.build"] and "cad.build" in tool_outputs:
        return dict(tool_outputs["cad.build"])
    properties = skill.outputSchema.properties or {}
    if {"artifactType", "summary", "content"}.issubset(properties):
        return {
            "artifactType": skill.artifactTypes[0] if skill.artifactTypes else skill.id,
            "summary": f"{skill.name}执行完成",
            "content": {"input": payload, "tools": tool_outputs},
        }
    if "content" in properties:
        return {"content": json.dumps({"input": payload, "tools": tool_outputs}, ensure_ascii=False)}
    return {"input": payload, "tools": tool_outputs}


def _validate_schema(value: object, schema: JsonSchemaObject, *, path: str) -> None:
    expected = schema.type
    if expected == "object":
        if not isinstance(value, dict):
            raise ValueError(f"{path} must be an object")
        required = schema.required or []
        for name in required:
            if name not in value:
                raise ValueError(f"{path}.{name} is required")
        for name, child in (schema.properties or {}).items():
            if name in value:
                _validate_schema(value[name], child, path=f"{path}.{name}")
    elif expected == "array":
        if not isinstance(value, list):
            raise ValueError(f"{path} must be an array")
        if schema.items is not None:
            for index, item in enumerate(value):
                _validate_schema(item, schema.items, path=f"{path}[{index}]")
    elif expected == "string" and not isinstance(value, str):
        raise ValueError(f"{path} must be a string")
    elif expected == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
        raise ValueError(f"{path} must be an integer")
    elif expected == "number" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
        raise ValueError(f"{path} must be a number")
    elif expected == "boolean" and not isinstance(value, bool):
        raise ValueError(f"{path} must be a boolean")
    if schema.enum is not None and value not in schema.enum:
        raise ValueError(f"{path} must be one of {schema.enum}")


def _skill_result(
    run_id: str,
    project_id: str,
    skill: SkillDefinition,
    status: SkillRunStatus,
    *,
    output: dict[str, object] | None = None,
    error: str | None = None,
    confirmation_required: bool = False,
    retry_count: int = 0,
) -> SkillRunResult:
    return SkillRunResult(
        id=run_id,
        projectId=project_id,
        skillId=skill.id,
        ownerExpert=skill.ownerExpert,
        status=status,
        output=output,
        error=error,
        confirmationRequired=confirmation_required,
        retryCount=retry_count,
    )


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"
