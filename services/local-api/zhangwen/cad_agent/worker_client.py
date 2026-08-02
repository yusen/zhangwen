"""Fixed-command subprocess client for one deterministic CAD Job."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from zhangwen.cad_agent.models import CadBuildSpec, CadJobPhase, CadWorkerResult
from zhangwen.cad_agent.process_limits import WindowsJobObject
from zhangwen.cad_agent.worker_protocol import (
    MAX_REQUEST_BYTES,
    WorkerEvent,
    canonical_json_bytes,
)


MAX_STREAM_BYTES = 64 * 1024
WALL_TIMEOUT_SECONDS = 180
PROCESS_MEMORY_BYTES = 1024 * 1024 * 1024
PROCESS_CPU_SECONDS = 120
CANCEL_WAIT_SECONDS = 5

ProgressCallback = Callable[[CadJobPhase, int], None | Awaitable[None]]


class CadWorkerError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


@dataclass
class _RunningWorker:
    process: asyncio.subprocess.Process
    job_object: WindowsJobObject


class CadWorkerClient:
    def __init__(self) -> None:
        self._service_root = Path(__file__).resolve().parents[2]
        self._running: dict[str, _RunningWorker] = {}
        self._lock = asyncio.Lock()

    async def run(
        self,
        job_id: str,
        *,
        request: CadBuildSpec,
        staging_dir: Path,
        on_progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        if request.jobId != job_id:
            raise CadWorkerError(
                "CAD_JOB_ID_MISMATCH",
                "CAD Job 与固化构建规范的标识不一致。",
                retryable=False,
            )
        request_bytes = canonical_json_bytes(request)
        if len(request_bytes) > MAX_REQUEST_BYTES:
            raise CadWorkerError(
                "CAD_REQUEST_TOO_LARGE",
                "CAD 构建规范超过 256 KiB 上限。",
                retryable=False,
            )
        resolved_staging = staging_dir.resolve(strict=True)
        if not resolved_staging.is_dir():
            raise CadWorkerError(
                "CAD_STAGING_INVALID",
                "CAD staging 目录无效。",
                retryable=False,
            )
        async with self._lock:
            if self._running:
                raise CadWorkerError(
                    "CAD_WORKER_BUSY",
                    "已有 CAD Worker 正在运行。",
                    retryable=True,
                )
            process = await asyncio.create_subprocess_exec(
                *_worker_command(job_id),
                cwd=resolved_staging,
                env=_worker_environment(self._service_root, resolved_staging),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=MAX_STREAM_BYTES + 1024,
            )
            try:
                job_object = WindowsJobObject(
                    process.pid,
                    memory_bytes=PROCESS_MEMORY_BYTES,
                    cpu_seconds=PROCESS_CPU_SECONDS,
                )
            except Exception as exc:
                process.kill()
                await process.wait()
                raise CadWorkerError(
                    "CAD_WORKER_LIMIT_SETUP_FAILED",
                    "无法为 CAD Worker 建立资源边界。",
                    retryable=False,
                ) from exc
            running = _RunningWorker(process=process, job_object=job_object)
            self._running[job_id] = running

        if process.stdin is None:
            await self.cancel(job_id)
            raise CadWorkerError(
                "CAD_WORKER_PROTOCOL_INVALID",
                "CAD Worker stdin 不可用。",
                retryable=False,
            )
        try:
            process.stdin.write(request_bytes)
            await process.stdin.drain()
            process.stdin.close()
        except (BrokenPipeError, ConnectionError, OSError) as exc:
            await self.cancel(job_id)
            raise CadWorkerError(
                "CAD_REQUEST_WRITE_FAILED",
                "无法将固化构建规范传入 CAD Worker。",
                retryable=True,
            ) from exc

        events: list[dict[str, Any]] = []
        stderr_chunks: list[bytes] = []
        stdout_task = asyncio.create_task(
            _consume_stdout(process.stdout, job_id, events, on_progress)
        )
        stderr_task = asyncio.create_task(
            _consume_stderr(process.stderr, stderr_chunks)
        )
        try:
            await asyncio.wait_for(
                asyncio.gather(process.wait(), stdout_task, stderr_task),
                timeout=WALL_TIMEOUT_SECONDS,
            )
        except TimeoutError as exc:
            await self.cancel(job_id)
            raise CadWorkerError(
                "CAD_WORKER_TIMED_OUT",
                "CAD Worker 超过 180 秒运行上限。",
                retryable=True,
            ) from exc
        except Exception:
            await self.cancel(job_id)
            raise
        finally:
            async with self._lock:
                active = self._running.pop(job_id, None)
            if active is not None:
                active.job_object.close()

        error_event = next(
            (event for event in reversed(events) if event.get("event") == "ERROR"),
            None,
        )
        if error_event is not None:
            payload = error_event.get("payload")
            details = payload if isinstance(payload, dict) else {}
            raise CadWorkerError(
                str(details.get("code") or "CAD_WORKER_FAILED"),
                str(details.get("message") or "CAD Worker 执行失败。"),
                retryable=bool(details.get("retryable", False)),
            )
        result_event = next(
            (event for event in reversed(events) if event.get("event") == "RESULT"),
            None,
        )
        if process.returncode != 0 or result_event is None:
            diagnostic = b"".join(stderr_chunks).decode("utf-8", errors="replace").strip()
            raise CadWorkerError(
                "CAD_WORKER_EXITED",
                diagnostic[-1000:] or f"CAD Worker 退出码为 {process.returncode}。",
                retryable=True,
            )
        payload = result_event.get("payload")
        if not isinstance(payload, dict):
            raise CadWorkerError(
                "CAD_WORKER_PROTOCOL_INVALID",
                "CAD Worker RESULT payload 无效。",
                retryable=False,
            )
        try:
            return CadWorkerResult.model_validate(payload).model_dump(mode="json")
        except ValidationError as exc:
            raise CadWorkerError(
                "CAD_WORKER_PROTOCOL_INVALID",
                "CAD Worker RESULT payload 不符合严格契约。",
                retryable=False,
            ) from exc

    async def cancel(self, job_id: str) -> bool:
        async with self._lock:
            running = self._running.get(job_id)
        if running is None:
            return False
        running.job_object.close()
        if running.process.returncode is None:
            running.process.kill()
            try:
                await asyncio.wait_for(
                    running.process.wait(),
                    timeout=CANCEL_WAIT_SECONDS,
                )
            except TimeoutError as exc:
                raise CadWorkerError(
                    "CAD_WORKER_CANCEL_TIMED_OUT",
                    "CAD Worker 在取消后 5 秒内未退出。",
                    retryable=True,
                ) from exc
        return True


async def _consume_stdout(
    stream: asyncio.StreamReader | None,
    job_id: str,
    events: list[dict[str, Any]],
    on_progress: ProgressCallback | None,
) -> None:
    if stream is None:
        raise CadWorkerError(
            "CAD_WORKER_PROTOCOL_INVALID",
            "CAD Worker stdout 不可用。",
            retryable=False,
        )
    total = 0
    expected_sequence = 1
    while line := await stream.readline():
        total += len(line)
        if total > MAX_STREAM_BYTES:
            raise CadWorkerError(
                "CAD_WORKER_OUTPUT_LIMIT",
                "CAD Worker 协议输出超过 64 KiB。",
                retryable=False,
            )
        try:
            raw_event = json.loads(line)
            event_model = WorkerEvent.model_validate(raw_event)
            event = event_model.model_dump(mode="json")
        except (json.JSONDecodeError, ValidationError) as exc:
            raise CadWorkerError(
                "CAD_WORKER_PROTOCOL_INVALID",
                "CAD Worker 输出了无效 NDJSON。",
                retryable=False,
            ) from exc
        if not isinstance(event, dict) or event.get("jobId") != job_id:
            raise CadWorkerError(
                "CAD_WORKER_PROTOCOL_INVALID",
                "CAD Worker 事件 Job ID 不匹配。",
                retryable=False,
            )
        if event.get("sequence") != expected_sequence:
            raise CadWorkerError(
                "CAD_WORKER_PROTOCOL_INVALID",
                "CAD Worker 事件顺序无效。",
                retryable=False,
            )
        expected_sequence += 1
        events.append(event)
        if event.get("event") == "PROGRESS" and on_progress is not None:
            payload = event.get("payload")
            if not isinstance(payload, dict):
                raise CadWorkerError(
                    "CAD_WORKER_PROTOCOL_INVALID",
                    "CAD Worker PROGRESS payload 无效。",
                    retryable=False,
                )
            phase = CadJobPhase(str(payload.get("phase")))
            progress = int(payload.get("progress"))
            result = on_progress(phase, progress)
            if isinstance(result, Awaitable):
                await result


async def _consume_stderr(
    stream: asyncio.StreamReader | None,
    chunks: list[bytes],
) -> None:
    if stream is None:
        return
    total = 0
    while chunk := await stream.read(4096):
        total += len(chunk)
        if total > MAX_STREAM_BYTES:
            raise CadWorkerError(
                "CAD_WORKER_LOG_LIMIT",
                "CAD Worker 日志超过 64 KiB。",
                retryable=False,
            )
        chunks.append(chunk)


def _worker_command(job_id: str) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "cad-worker", job_id]
    return [_python_executable(), "-m", "zhangwen.cad_engine.worker", job_id]


def _worker_environment(service_root: Path, staging_dir: Path) -> dict[str, str]:
    allowed = {
        name: value
        for name in (
            "SYSTEMROOT",
            "WINDIR",
            "TEMP",
            "TMP",
        )
        if (value := os.environ.get(name))
    }
    allowed.update(
        {
            "PYTHONUTF8": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": _trusted_python_path(service_root),
            "PATH": _trusted_runtime_path(),
            "HOME": str(staging_dir),
            "USERPROFILE": str(staging_dir),
            "APPDATA": str(staging_dir),
            "LOCALAPPDATA": str(staging_dir),
        }
    )
    if sys.prefix != sys.base_prefix:
        allowed["VIRTUAL_ENV"] = sys.prefix
    return allowed


def _trusted_runtime_path() -> str:
    directories = [
        str(Path(sys.executable).resolve().parent),
        str(Path(_python_executable()).resolve().parent),
    ]
    system_root = os.environ.get("SYSTEMROOT") or os.environ.get("WINDIR")
    if system_root:
        directories.append(str(Path(system_root) / "System32"))
    return os.pathsep.join(dict.fromkeys(directories))


def _trusted_python_path(service_root: Path) -> str:
    paths = [str(service_root)]
    site_packages = Path(sys.prefix) / "Lib" / "site-packages"
    if site_packages.is_dir():
        paths.append(str(site_packages.resolve()))
    return os.pathsep.join(paths)


def _python_executable() -> str:
    base_executable = getattr(sys, "_base_executable", None)
    if isinstance(base_executable, str) and Path(base_executable).is_file():
        return base_executable
    return sys.executable
