"""Persistent Creator materialization jobs and the local outbox runner."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import uuid
from collections.abc import Awaitable, Callable, Mapping
from contextlib import suppress
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Any

from zhangwen.code_agent.board_api_contracts import resolve_board_api_contract
from zhangwen.code_agent.generator import validate_and_package_code
from zhangwen.code_agent.models import CodeRuntime
from zhangwen.code_agent.repository import CodeRepository
from zhangwen.code_agent.service import CodeGenerationService
from zhangwen.code_agent.validation import (
    run_esp_claw_lua_validation,
    run_micropython_validation,
)
from zhangwen.creator.models import CreatorJob, CreatorJobKind, CreatorJobStatus
from zhangwen.device_lab.scene import materialize_device_lab_scene
from zhangwen.llm.structured import StructuredLLMError
from zhangwen.specs.models import (
    SpecFile,
    SpecFileKind,
    SpecRun,
    SpecRunStatus,
    SpecValidation,
)


ProgressCallback = Callable[[int, str], None]
CreatorJobHandler = Callable[
    [CreatorJob, ProgressCallback],
    Awaitable[dict[str, Any]],
]
CodeGenerationFactory = Callable[[], tuple[Any, Any, str, Any]]


class CreatorJobExecutionError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


class CreatorJobWaitingConfirmation(CreatorJobExecutionError):
    """The runner consumed the job but a real downstream result is not ready."""


class CreatorJobRepository:
    """Own every durable Creator Job transition and its matching event."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)

    def queued_ids(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id FROM creator_jobs
                WHERE status = 'QUEUED'
                ORDER BY created_at ASC, id ASC
                """
            ).fetchall()
        return [str(row["id"]) for row in rows]

    def has_active_jobs(self) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM creator_jobs
                WHERE status IN ('QUEUED', 'RUNNING')
                LIMIT 1
                """
            ).fetchone()
        return row is not None

    def get(self, project_id: str, job_id: str) -> CreatorJob:
        with self._connect() as conn:
            return self._row(conn, project_id, job_id)

    def recover_interrupted(self) -> int:
        """Return interrupted RUNNING work to the queue on process startup."""

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                """
                SELECT * FROM creator_jobs
                WHERE status = 'RUNNING'
                ORDER BY created_at ASC, id ASC
                """
            ).fetchall()
            for row in rows:
                now = _now()
                conn.execute(
                    """
                    UPDATE creator_jobs
                    SET status = 'QUEUED', progress = 0,
                        message = ?, updated_at = ?, started_at = NULL,
                        completed_at = NULL
                    WHERE id = ? AND status = 'RUNNING'
                    """,
                    ("本地服务重启后已安全恢复排队。", now, str(row["id"])),
                )
                self._append_event(
                    conn,
                    str(row["project_id"]),
                    row,
                    CreatorJobStatus.QUEUED,
                    progress=0,
                    message="本地服务重启后已安全恢复排队。",
                    extra={"reason": "PROCESS_RESTART_RECOVERY"},
                )
            return len(rows)

    def mark_running(self, job_id: str) -> CreatorJob:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            now = _now()
            updated = conn.execute(
                """
                UPDATE creator_jobs
                SET status = 'RUNNING', progress = 1, message = ?,
                    updated_at = ?, started_at = ?, completed_at = NULL
                WHERE id = ? AND status = 'QUEUED'
                """,
                ("本地执行器已开始处理。", now, now, job_id),
            ).rowcount
            if updated != 1:
                raise CreatorJobExecutionError(
                    "CREATOR_JOB_NOT_QUEUED",
                    "Creator Job 已不在排队状态。",
                )
            row = self._row_by_id(conn, job_id)
            self._append_event(
                conn,
                row.work_id,
                row,
                CreatorJobStatus.RUNNING,
                progress=1,
                message="本地执行器已开始处理。",
            )
            return self._row_by_id(conn, job_id)

    def update_progress(self, job_id: str, progress: int, message: str) -> None:
        if not 1 <= progress <= 99:
            raise ValueError("Creator Job progress must be between 1 and 99")
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._row_by_id(conn, job_id)
            if row.status is not CreatorJobStatus.RUNNING:
                return
            if progress < row.progress:
                return
            now = _now()
            conn.execute(
                """
                UPDATE creator_jobs
                SET progress = ?, message = ?, updated_at = ?
                WHERE id = ? AND status = 'RUNNING'
                """,
                (progress, message, now, job_id),
            )
            self._append_event(
                conn,
                row.work_id,
                row,
                CreatorJobStatus.RUNNING,
                progress=progress,
                message=message,
            )

    def finish_success(self, job_id: str, result: dict[str, Any]) -> CreatorJob:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._row_by_id(conn, job_id)
            if row.status is CreatorJobStatus.CANCELED:
                return row
            if row.status is not CreatorJobStatus.RUNNING:
                raise CreatorJobExecutionError(
                    "CREATOR_JOB_NOT_RUNNING",
                    "Creator Job 已不在运行状态。",
                )
            now = _now()
            conn.execute(
                """
                UPDATE creator_jobs
                SET status = 'SUCCEEDED', progress = 100, message = ?,
                    result_json = ?, updated_at = ?, completed_at = ?
                WHERE id = ? AND status = 'RUNNING'
                """,
                (
                    "本地任务已完成。",
                    _dump(result),
                    now,
                    now,
                    job_id,
                ),
            )
            self._append_event(
                conn,
                row.work_id,
                row,
                CreatorJobStatus.SUCCEEDED,
                progress=100,
                message="本地任务已完成。",
                extra={"result": result},
            )
            return self._row_by_id(conn, job_id)

    def finish_failure(
        self,
        job_id: str,
        *,
        code: str,
        message: str,
        retryable: bool,
    ) -> CreatorJob:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._row_by_id(conn, job_id)
            if row.status is CreatorJobStatus.CANCELED:
                return row
            if row.status is not CreatorJobStatus.RUNNING:
                raise CreatorJobExecutionError(
                    "CREATOR_JOB_NOT_RUNNING",
                    "Creator Job 已不在运行状态。",
                )
            now = _now()
            result = {
                "error": {
                    "code": code,
                    "retryable": retryable,
                }
            }
            conn.execute(
                """
                UPDATE creator_jobs
                SET status = 'FAILED', message = ?, result_json = ?,
                    updated_at = ?, completed_at = ?
                WHERE id = ? AND status = 'RUNNING'
                """,
                (message, _dump(result), now, now, job_id),
            )
            self._append_event(
                conn,
                row.work_id,
                row,
                CreatorJobStatus.FAILED,
                progress=row.progress,
                message=message,
                extra={"error": result["error"]},
            )
            return self._row_by_id(conn, job_id)

    def finish_waiting(self, job_id: str, *, code: str, message: str) -> CreatorJob:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._row_by_id(conn, job_id)
            if row.status is CreatorJobStatus.CANCELED:
                return row
            if row.status is not CreatorJobStatus.RUNNING:
                raise CreatorJobExecutionError(
                    "CREATOR_JOB_NOT_RUNNING",
                    "Creator Job 已不在运行状态。",
                )
            now = _now()
            result = {"waiting": {"code": code}}
            conn.execute(
                """
                UPDATE creator_jobs
                SET status = 'WAITING_CONFIRMATION', message = ?,
                    result_json = ?, updated_at = ?
                WHERE id = ? AND status = 'RUNNING'
                """,
                (message, _dump(result), now, job_id),
            )
            self._append_event(
                conn,
                row.work_id,
                row,
                CreatorJobStatus.WAITING_CONFIRMATION,
                progress=row.progress,
                message=message,
                extra={"waiting": result["waiting"]},
            )
            return self._row_by_id(conn, job_id)

    def cancel(
        self,
        project_id: str,
        job_id: str,
        *,
        idempotency_key: str,
    ) -> tuple[CreatorJob, bool]:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            repeated_job_id = self._job_for_idempotency_key(
                conn,
                project_id,
                idempotency_key,
            )
            if repeated_job_id is not None:
                if repeated_job_id != job_id:
                    raise CreatorJobExecutionError(
                        "CREATOR_JOB_IDEMPOTENCY_KEY_REUSED",
                        "该幂等键已用于另一个 Creator Job。",
                    )
                return self._row(conn, project_id, job_id), True

            row = self._row(conn, project_id, job_id)
            if row.status in {
                CreatorJobStatus.SUCCEEDED,
                CreatorJobStatus.FAILED,
            }:
                raise CreatorJobExecutionError(
                    "CREATOR_JOB_NOT_CANCELABLE",
                    "已结束的 Creator Job 不能取消。",
                )
            now = _now()
            if row.status is not CreatorJobStatus.CANCELED:
                conn.execute(
                    """
                    UPDATE creator_jobs
                    SET status = 'CANCELED', message = ?,
                        updated_at = ?, completed_at = ?
                    WHERE id = ? AND project_id = ?
                    """,
                    ("用户已取消本地任务。", now, now, job_id, project_id),
                )
            self._append_event(
                conn,
                project_id,
                row,
                CreatorJobStatus.CANCELED,
                progress=row.progress,
                message="用户已取消本地任务。",
                extra={
                    "command": "CANCEL",
                    "idempotencyKey": idempotency_key,
                },
            )
            return self._row(conn, project_id, job_id), False

    def retry(
        self,
        project_id: str,
        job_id: str,
        *,
        idempotency_key: str,
    ) -> tuple[CreatorJob, bool]:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            repeated_job_id = self._job_for_idempotency_key(
                conn,
                project_id,
                idempotency_key,
            )
            if repeated_job_id is not None:
                if repeated_job_id != job_id:
                    raise CreatorJobExecutionError(
                        "CREATOR_JOB_IDEMPOTENCY_KEY_REUSED",
                        "该幂等键已用于另一个 Creator Job。",
                    )
                return self._row(conn, project_id, job_id), True

            row = self._row(conn, project_id, job_id)
            retryable = (
                row.status is CreatorJobStatus.WAITING_CONFIRMATION
                or (
                    row.status is CreatorJobStatus.FAILED
                    and bool((row.result or {}).get("error", {}).get("retryable"))
                )
            )
            if not retryable:
                raise CreatorJobExecutionError(
                    "CREATOR_JOB_NOT_RETRYABLE",
                    "只有可恢复失败或等待确认的 Creator Job 可以重试。",
                )
            now = _now()
            conn.execute(
                """
                UPDATE creator_jobs
                SET status = 'QUEUED', progress = 0, message = ?,
                    result_json = NULL, updated_at = ?, started_at = NULL,
                    completed_at = NULL
                WHERE id = ? AND project_id = ?
                """,
                ("已重新排队，等待本地执行器重试。", now, job_id, project_id),
            )
            if row.kind is CreatorJobKind.CODE_PREPARATION:
                conn.execute(
                    """
                    UPDATE creator_code_variant_bindings
                    SET validation_status = 'PENDING', failure_code = NULL,
                        failure_message = NULL, updated_at = ?
                    WHERE project_id = ? AND solution_revision_id = ?
                      AND validation_status = 'FAILED'
                    """,
                    (now, project_id, row.solution_revision_id),
                )
            self._append_event(
                conn,
                project_id,
                row,
                CreatorJobStatus.QUEUED,
                progress=0,
                message="已重新排队，等待本地执行器重试。",
                extra={
                    "command": "RETRY",
                    "idempotencyKey": idempotency_key,
                },
            )
            return self._row(conn, project_id, job_id), False

    def _job_for_idempotency_key(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        idempotency_key: str,
    ) -> str | None:
        rows = conn.execute(
            """
            SELECT payload_json FROM creator_events
            WHERE project_id = ? AND event_type = 'JOB'
            ORDER BY created_at DESC, id DESC
            """,
            (project_id,),
        ).fetchall()
        for row in rows:
            payload = json.loads(str(row["payload_json"]))
            if payload.get("idempotencyKey") == idempotency_key:
                value = payload.get("jobId")
                return str(value) if value is not None else None
        return None

    def _append_event(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        job: CreatorJob | sqlite3.Row,
        status: CreatorJobStatus,
        *,
        progress: int,
        message: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        job_id = str(job.id if isinstance(job, CreatorJob) else job["id"])
        kind = str(
            job.kind.value
            if isinstance(job, CreatorJob)
            else job["kind"]
        )
        solution_revision_id = str(
            job.solution_revision_id
            if isinstance(job, CreatorJob)
            else job["solution_revision_id"]
        )
        payload = {
            "jobId": job_id,
            "kind": kind,
            "status": status.value,
            "progress": progress,
            "message": message,
            "solutionRevisionId": solution_revision_id,
            **(extra or {}),
        }
        conn.execute(
            """
            INSERT INTO creator_events (
              id, project_id, event_type, payload_json, created_at
            ) VALUES (?, ?, 'JOB', ?, ?)
            """,
            (f"cevt_{uuid.uuid4().hex}", project_id, _dump(payload), _now()),
        )

    def _row(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        job_id: str,
    ) -> CreatorJob:
        row = conn.execute(
            """
            SELECT * FROM creator_jobs
            WHERE project_id = ? AND id = ?
            """,
            (project_id, job_id),
        ).fetchone()
        if row is None:
            raise CreatorJobExecutionError(
                "CREATOR_JOB_NOT_FOUND",
                "Creator Job 不存在。",
            )
        return _to_job(row)

    def _row_by_id(self, conn: sqlite3.Connection, job_id: str) -> CreatorJob:
        row = conn.execute(
            "SELECT * FROM creator_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            raise CreatorJobExecutionError(
                "CREATOR_JOB_NOT_FOUND",
                "Creator Job 不存在。",
            )
        return _to_job(row)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn


class CreatorJobRunner:
    """Single-concurrency local runner for the durable Creator outbox."""

    def __init__(
        self,
        db_path: Path,
        data_dir: Path,
        *,
        handlers: Mapping[CreatorJobKind, CreatorJobHandler] | None = None,
        code_generation_factory: CodeGenerationFactory | None = None,
    ) -> None:
        self.db_path = Path(db_path).resolve()
        self.data_dir = Path(data_dir).resolve()
        self._jobs = CreatorJobRepository(self.db_path)
        self._code_generation_factory = code_generation_factory
        defaults: dict[CreatorJobKind, CreatorJobHandler] = {
            CreatorJobKind.CODE_PREPARATION: self._prepare_code_context,
            CreatorJobKind.DIGITAL_PROTOTYPE: self._materialize_digital_prototype,
            CreatorJobKind.STRUCTURE_DRAFT: self._prepare_structure_intent,
        }
        self._handlers = {**defaults, **(handlers or {})}
        self._wake = asyncio.Event()
        self._shutdown = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._jobs.recover_interrupted()
        self._shutdown.clear()
        self._task = asyncio.create_task(
            self._run_loop(),
            name="creator-job-runner",
        )
        self._wake.set()

    async def stop(self) -> None:
        self._shutdown.set()
        self._wake.set()
        task = self._task
        self._task = None
        if task is None:
            return
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    def submit(self) -> None:
        self._wake.set()

    def get(self, project_id: str, job_id: str) -> CreatorJob:
        return self._jobs.get(project_id, job_id)

    def cancel(
        self,
        project_id: str,
        job_id: str,
        *,
        idempotency_key: str,
    ) -> tuple[CreatorJob, bool]:
        result = self._jobs.cancel(
            project_id,
            job_id,
            idempotency_key=idempotency_key,
        )
        self._wake.set()
        return result

    def retry(
        self,
        project_id: str,
        job_id: str,
        *,
        idempotency_key: str,
    ) -> tuple[CreatorJob, bool]:
        result = self._jobs.retry(
            project_id,
            job_id,
            idempotency_key=idempotency_key,
        )
        self._wake.set()
        return result

    async def wait_until_idle(self, *, timeout: float = 5.0) -> None:
        deadline = monotonic() + timeout
        while self._jobs.has_active_jobs():
            if monotonic() >= deadline:
                raise TimeoutError("Creator Job runner did not become idle")
            await asyncio.sleep(0.01)

    async def _run_loop(self) -> None:
        while not self._shutdown.is_set():
            self._wake.clear()
            queued_ids = self._jobs.queued_ids()
            if not queued_ids:
                await self._wake.wait()
                continue
            for job_id in queued_ids:
                if self._shutdown.is_set():
                    return
                try:
                    await self._execute(job_id)
                except asyncio.CancelledError:
                    raise
                except CreatorJobExecutionError:
                    continue

    async def _execute(self, job_id: str) -> None:
        job = self._jobs.mark_running(job_id)

        def progress(value: int, message: str) -> None:
            self._jobs.update_progress(job_id, value, message)

        handler = self._handlers[job.kind]
        try:
            result = await handler(job, progress)
            self._jobs.finish_success(job_id, result)
        except asyncio.CancelledError:
            # A process stop intentionally leaves RUNNING durable; next start
            # converts it back to QUEUED and records a recovery event.
            raise
        except CreatorJobWaitingConfirmation as exc:
            self._jobs.finish_waiting(
                job_id,
                code=exc.code,
                message=exc.message,
            )
        except CreatorJobExecutionError as exc:
            self._jobs.finish_failure(
                job_id,
                code=exc.code,
                message=exc.message,
                retryable=exc.retryable,
            )
        except Exception as exc:
            self._jobs.finish_failure(
                job_id,
                code="CREATOR_JOB_HANDLER_FAILED",
                message=f"本地任务执行失败（{type(exc).__name__}）。",
                retryable=True,
            )

    async def _prepare_code_context(
        self,
        job: CreatorJob,
        progress: ProgressCallback,
    ) -> dict[str, Any]:
        progress(15, "正在根据确认方案准备 USB 与 ESP-Claw 代码变体。")
        solution = self._solution(job)
        if self._code_generation_factory is None:
            self._fail_pending_code_variants(
                job,
                code="CREATOR_CODE_GENERATOR_UNAVAILABLE",
                message="代码生成器尚未配置，请配置模型后重试生成。",
            )
            raise CreatorJobExecutionError(
                "CREATOR_CODE_GENERATOR_UNAVAILABLE",
                "代码生成器尚未配置，请配置模型后重试生成。",
                retryable=True,
            )
        try:
            provider, config, api_key, model = self._code_generation_factory()
        except StructuredLLMError as exc:
            self._fail_pending_code_variants(
                job,
                code=str(exc.error.code),
                message=exc.error.message,
            )
            raise CreatorJobExecutionError(
                "CREATOR_CODE_MODEL_UNAVAILABLE",
                exc.error.message,
                retryable=True,
            ) from exc

        spec = self._creator_solution_spec(job, solution)
        bindings = self._pending_code_variant_rows(job)
        results: list[dict[str, Any]] = []
        failures: list[dict[str, str]] = []
        for index, binding in enumerate(bindings):
            runtime = CodeRuntime(str(binding["runtime"]))
            channel = str(binding["deployment_channel"])
            progress(
                25 + index * 30,
                f"正在生成 {channel} 的 {runtime.value} 代码草稿。",
            )
            try:
                component_ids = [
                    str(item.get("componentId"))
                    for item in json.loads(str(solution["bom_json"]))
                    if isinstance(item, dict) and item.get("componentId")
                ]
                board_contract = resolve_board_api_contract(component_ids, spec)
                draft = await CodeGenerationService(provider).generate(
                    spec=spec,
                    config=config,
                    api_key=api_key,
                    model=model,
                    board_contract=board_contract,
                    runtime=runtime,
                )
                generated = validate_and_package_code(
                    spec,
                    draft,
                    now=_now(),
                    board_contract_id=(
                        board_contract.id
                        if runtime is CodeRuntime.MICROPYTHON
                        and board_contract is not None
                        else None
                    ),
                    runtime=runtime,
                )
                test_result = await asyncio.to_thread(
                    run_micropython_validation
                    if runtime is CodeRuntime.MICROPYTHON
                    else run_esp_claw_lua_validation,
                    generated.files,
                    now=_now(),
                    **(
                        {
                            "board_contract_id": (
                                board_contract.id
                                if board_contract is not None
                                else None
                            )
                        }
                        if runtime is CodeRuntime.MICROPYTHON
                        else {}
                    ),
                )
                generated = replace(generated, test_result=test_result)
                code_repository = CodeRepository(self.db_path)
                code_run = code_repository.create_from_chat_draft(
                    project_id=job.work_id,
                    source_message_id=(
                        f"creator:{job.solution_revision_id}:{channel}"
                    ),
                    generated_by_expert_id=None,
                    generated=generated,
                    idempotency_scope=f"creator-code-variant-v1:{channel}",
                    spec_run_id=None,
                )
                code_run = code_repository.validate_code(
                    job.work_id,
                    code_run.id,
                    test_result,
                )
                self._complete_code_variant(
                    binding_id=str(binding["id"]),
                    code_run_id=code_run.id,
                    ready=code_run.status.value == "READY_FOR_REVIEW",
                    failure_message=code_run.staleReason,
                )
                if code_run.status.value == "READY_FOR_REVIEW":
                    results.append(
                        {
                            "deploymentChannel": channel,
                            "runtime": runtime.value,
                            "codeRunId": code_run.id,
                            "codeVersion": code_run.version,
                            "validationStatus": "READY_FOR_REVIEW",
                        }
                    )
                else:
                    failures.append(
                        {
                            "deploymentChannel": channel,
                            "code": "CREATOR_CODE_VALIDATION_FAILED",
                            "message": code_run.staleReason
                            or "本地静态或语法检查未通过。",
                        }
                    )
            except (StructuredLLMError, ValueError) as exc:
                code = (
                    str(exc.error.code)
                    if isinstance(exc, StructuredLLMError)
                    else "CREATOR_CODE_OUTPUT_INVALID"
                )
                message = (
                    exc.error.message
                    if isinstance(exc, StructuredLLMError)
                    else str(exc)
                )
                self._mark_code_variant_failed(
                    str(binding["id"]),
                    code=code,
                    message=message,
                )
                failures.append(
                    {
                        "deploymentChannel": channel,
                        "code": code,
                        "message": message,
                    }
                )

        if not results:
            raise CreatorJobExecutionError(
                "CREATOR_CODE_GENERATION_FAILED",
                "两个部署通道均未生成可确认的代码，请查看失败原因后重试。",
                retryable=True,
            )
        progress(90, "代码变体已通过本地检查，等待用户确认用于仿真。")
        return {
            "materialization": "CODE_VARIANTS_READY_FOR_REVIEW",
            "solutionRevisionId": job.solution_revision_id,
            "variants": results,
            "failures": failures,
            "requiresUserConfirmation": True,
        }

    def _creator_solution_spec(
        self,
        job: CreatorJob,
        solution: sqlite3.Row,
    ) -> SpecRun:
        now = _now()
        spec_id = f"creator-spec:{job.solution_revision_id}"
        solution_payload = {
            "name": str(solution["summary"]),
            "goal": str(solution["summary"]),
            "logic": str(solution["logic"]),
            "software": str(solution["software"]),
            "simulation": str(solution["simulation"]),
            "safety": str(solution["safety"]),
        }
        files = [
            SpecFile(
                id=f"{spec_id}:project",
                specRunId=spec_id,
                projectId=job.work_id,
                kind=SpecFileKind.PROJECT_SPEC,
                path="spec/project_spec.yaml",
                mimeType="application/yaml",
                content=json.dumps(solution_payload, ensure_ascii=False),
                createdAt=now,
            ),
            SpecFile(
                id=f"{spec_id}:bom",
                specRunId=spec_id,
                projectId=job.work_id,
                kind=SpecFileKind.BOM,
                path="spec/bom.yaml",
                mimeType="application/yaml",
                content=str(solution["bom_json"]),
                createdAt=now,
            ),
            SpecFile(
                id=f"{spec_id}:io",
                specRunId=spec_id,
                projectId=job.work_id,
                kind=SpecFileKind.IO_MAP,
                path="spec/io_map.yaml",
                mimeType="application/yaml",
                content=str(solution["io_map_json"]),
                createdAt=now,
            ),
        ]
        return SpecRun(
            id=spec_id,
            projectId=job.work_id,
            proposalId=f"creator-solution:{job.solution_revision_id}",
            version=int(solution["revision"]),
            status=SpecRunStatus.APPROVED,
            files=files,
            validation=SpecValidation(ok=True, checks=[]),
            createdAt=str(solution["created_at"]),
            updatedAt=str(solution["confirmed_at"] or now),
            confirmedAt=str(solution["confirmed_at"] or now),
        )

    def _pending_code_variant_rows(
        self, job: CreatorJob
    ) -> list[sqlite3.Row]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM creator_code_variant_bindings
                WHERE project_id = ? AND solution_revision_id = ?
                  AND validation_status IN ('PENDING', 'FAILED')
                ORDER BY CASE deployment_channel
                  WHEN 'USB_SERIAL' THEN 0 ELSE 1 END
                """,
                (job.work_id, job.solution_revision_id),
            ).fetchall()
        return list(rows)

    def _complete_code_variant(
        self,
        *,
        binding_id: str,
        code_run_id: str,
        ready: bool,
        failure_message: str | None,
    ) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE creator_code_variant_bindings
                SET code_run_id = ?, validation_status = ?,
                    failure_code = ?, failure_message = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    code_run_id,
                    "READY_FOR_REVIEW" if ready else "FAILED",
                    None if ready else "CREATOR_CODE_VALIDATION_FAILED",
                    None if ready else failure_message,
                    _now(),
                    binding_id,
                ),
            )

    def _mark_code_variant_failed(
        self,
        binding_id: str,
        *,
        code: str,
        message: str,
    ) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE creator_code_variant_bindings
                SET validation_status = 'FAILED', failure_code = ?,
                    failure_message = ?, updated_at = ?
                WHERE id = ?
                """,
                (code, message[:2000], _now(), binding_id),
            )

    def _fail_pending_code_variants(
        self,
        job: CreatorJob,
        *,
        code: str,
        message: str,
    ) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE creator_code_variant_bindings
                SET validation_status = 'FAILED', failure_code = ?,
                    failure_message = ?, updated_at = ?
                WHERE project_id = ? AND solution_revision_id = ?
                """,
                (code, message[:2000], _now(), job.work_id, job.solution_revision_id),
            )

    async def _materialize_digital_prototype(
        self,
        job: CreatorJob,
        progress: ProgressCallback,
    ) -> dict[str, Any]:
        progress(30, "正在根据当前方案生成数字原型场景。")
        scene = materialize_device_lab_scene(
            self.db_path,
            self.data_dir,
            job.work_id,
        )
        if scene is None:
            raise CreatorJobExecutionError(
                "CREATOR_DIGITAL_PROTOTYPE_UNAVAILABLE",
                "当前方案尚未绑定可投影的设备包，数字原型生成失败。",
            )
        progress(85, "数字原型场景已持久化，等待用户运行验收场景。")
        return {
            "materialization": "DEVICE_LAB_SCENE",
            "sceneRevision": scene.revision,
            "boardId": scene.boardId.value,
            "solutionRevisionId": job.solution_revision_id,
        }

    async def _prepare_structure_intent(
        self,
        job: CreatorJob,
        progress: ProgressCallback,
    ) -> dict[str, Any]:
        progress(40, "正在整理结构约束与 CAD 意图。")
        solution = self._solution(job)
        structure = str(solution["structure"]).strip()
        if structure in {"", "不需要结构", "不适用", "无"}:
            raise CreatorJobExecutionError(
                "CREATOR_STRUCTURE_NOT_REQUIRED",
                "当前方案不需要独立结构任务。",
            )
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            revision = conn.execute(
                """
                SELECT id, artifact_id, artifact_version_id
                FROM cad_intent_revisions
                WHERE project_id = ? AND status = 'CONFIRMED'
                  AND confirmed_at IS NOT NULL AND confirmed_at >= ?
                ORDER BY confirmed_at DESC, id DESC LIMIT 1
                """,
                (job.work_id, str(solution["confirmed_at"])),
            ).fetchone()
        if revision is None:
            raise CreatorJobWaitingConfirmation(
                "CREATOR_STRUCTURE_RESULT_REQUIRED",
                "结构意图已准备，等待受控 CAD Worker 产生并确认真实结构修订。",
            )
        progress(85, "已读取 CAD 服务持久化的确认结构修订。")
        return {
            "materialization": "CONFIRMED_CAD_REVISION",
            "solutionRevisionId": job.solution_revision_id,
            "structureRevisionId": str(revision["id"]),
            "artifactId": revision["artifact_id"],
            "artifactVersionId": revision["artifact_version_id"],
        }

    def _solution(self, job: CreatorJob) -> sqlite3.Row:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT * FROM creator_solution_revisions
                WHERE id = ? AND project_id = ? AND status = 'CONFIRMED'
                """,
                (job.solution_revision_id, job.work_id),
            ).fetchone()
        if row is None:
            raise CreatorJobExecutionError(
                "CREATOR_JOB_SOLUTION_STALE",
                "Job 绑定的方案已不再是当前确认方案。",
            )
        return row


def _to_job(row: sqlite3.Row) -> CreatorJob:
    raw_result = (
        json.loads(str(row["result_json"]))
        if row["result_json"] is not None
        else None
    )
    return CreatorJob(
        id=str(row["id"]),
        workId=str(row["project_id"]),
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


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _dump(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
