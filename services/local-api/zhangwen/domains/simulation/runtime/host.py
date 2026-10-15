"""Bounded supervisor for native and behavioral-reference simulation workers."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from zhangwen.domains.simulation.catalog import SimulationCatalog
from zhangwen.domains.simulation.compiler import compile_circuit
from zhangwen.domains.simulation.runtime.manifest import SimulationRuntimePackage
from zhangwen.domains.simulation.runtime.models import (
    RUNTIME_WORKER_PROTOCOL,
    NativeCoreState,
    RuntimeEngineMode,
    RuntimeErrorDetail,
    RuntimeExecutionRequest,
    RuntimeExecutionResult,
    RuntimeExecutionStatus,
    RuntimeResourceUsage,
)


_WORKER_PATH = Path(__file__).with_name("reference_worker.py").resolve()
MAX_WORKER_INPUT_BYTES = 2_000_000
MAX_WORKER_OUTPUT_BYTES = 2_000_000
_WORKER_SLOTS = threading.BoundedSemaphore(4)


class RuntimeCancellationToken:
    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def canceled(self) -> bool:
        return self._event.is_set()


class SimulationRuntimeHost:
    def __init__(
        self,
        data_dir: Path,
        *,
        popen_factory: Callable[..., Any] = subprocess.Popen,
        process_tree_terminator: Callable[[Any], None] | None = None,
        polling_interval_seconds: float = 0.05,
    ) -> None:
        self._data_dir = Path(data_dir)
        self.worker_root = (
            self._data_dir / "simulation-workers" / "zw-mpy-sim"
        ).resolve(strict=False)
        self._popen_factory = popen_factory
        self._terminate_tree = process_tree_terminator or _terminate_process_tree
        self._polling_interval_seconds = max(
            0.001, min(polling_interval_seconds, 0.1)
        )
        self._package = SimulationRuntimePackage.load_builtin()
        self._catalog = SimulationCatalog.load_builtin()

    @property
    def runtime_package(self) -> SimulationRuntimePackage:
        return self._package

    def reference_worker_command(self) -> tuple[str, ...]:
        if getattr(sys, "frozen", False):
            return (sys.executable, "simulation-reference-worker")
        return (
            sys.executable,
            "-I",
            "-B",
            "-X",
            "utf8",
            str(_WORKER_PATH),
        )

    def native_worker_command(self, executable: Path) -> tuple[str, ...]:
        return (str(Path(executable).resolve()), "--zhangwen-worker-v1")

    def execute(
        self,
        request: RuntimeExecutionRequest,
        *,
        cancellation: RuntimeCancellationToken | None = None,
    ) -> RuntimeExecutionResult:
        token = cancellation or RuntimeCancellationToken()
        if token.canceled:
            return self._failure(
                request.engine_mode,
                RuntimeExecutionStatus.CANCELED,
                "SIMULATION_CANCELED",
                "仿真在 Worker 启动前已取消。",
            )
        if request.runtime_package_revision_id != self._package.manifest.revision_id:
            return self._failure(
                request.engine_mode,
                RuntimeExecutionStatus.FAILED,
                "SIMULATION_RUNTIME_REVISION_MISMATCH",
                "请求固定的 runtime revision 与当前运行包不一致。",
            )
        quota_error = self._validate_quotas(request)
        if quota_error is not None:
            return quota_error
        compilation = compile_circuit(request.circuit, self._catalog)
        errors = [
            item for item in compilation.diagnostics if item.severity.value == "ERROR"
        ]
        if errors:
            return self._failure(
                request.engine_mode,
                RuntimeExecutionStatus.FAILED,
                "SIMULATION_STATIC_COMPILATION_FAILED",
                f"电路尚未通过静态编译：{errors[0].message}",
            )
        board = self._catalog.board(request.board_package_revision_id)
        if board is None:
            return self._failure(
                request.engine_mode,
                RuntimeExecutionStatus.FAILED,
                "SIM_BOARD_UNKNOWN",
                "运行请求引用了未知板型 revision。",
            )
        if request.engine_mode is RuntimeEngineMode.NATIVE_MICROPYTHON:
            native = self._package.status(self._data_dir).native_core
            if not native.verified:
                code = (
                    "MICROPYTHON_CORE_INTEGRITY_FAILED"
                    if native.status is NativeCoreState.INTEGRITY_FAILED
                    else "MICROPYTHON_CORE_UNAVAILABLE"
                )
                return self._failure(
                    request.engine_mode,
                    RuntimeExecutionStatus.FAILED,
                    code,
                    native.message,
                )
            executable = self._package.native_executable(self._data_dir)
            assert executable is not None
            command = self.native_worker_command(executable)
        else:
            command = self.reference_worker_command()
        payload = {
            "protocol": RUNTIME_WORKER_PROTOCOL,
            "request": request.model_dump(mode="json", by_alias=True),
            "boardProfile": board.model_dump(mode="json", by_alias=True),
            "componentProfiles": [
                item.model_dump(mode="json", by_alias=True)
                for item in self._catalog.components
            ],
        }
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > MAX_WORKER_INPUT_BYTES:
            return self._failure(
                request.engine_mode,
                RuntimeExecutionStatus.FAILED,
                "SIMULATION_WORKER_INPUT_LIMIT_EXCEEDED",
                "仿真 Worker 输入超过协议上限。",
            )
        if not _WORKER_SLOTS.acquire(
            timeout=max(0.1, request.limits.wall_timeout_ms / 1000)
        ):
            return self._failure(
                request.engine_mode,
                RuntimeExecutionStatus.FAILED,
                "SIMULATION_WORKER_CAPACITY_EXCEEDED",
                "仿真 Worker 并发队列已满，请稍后重试。",
                retryable=True,
            )
        try:
            return self._execute_worker(
                request=request,
                command=command,
                encoded=encoded,
                cancellation=token,
            )
        finally:
            _WORKER_SLOTS.release()

    def _execute_worker(
        self,
        *,
        request: RuntimeExecutionRequest,
        command: tuple[str, ...],
        encoded: str,
        cancellation: RuntimeCancellationToken,
    ) -> RuntimeExecutionResult:
        self.worker_root.mkdir(parents=True, exist_ok=True)
        startupinfo = None
        creationflags = 0
        start_new_session = os.name != "nt"
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = (
                subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
            )
        try:
            process = self._popen_factory(
                command,
                cwd=self.worker_root,
                env=_minimal_environment(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,
                startupinfo=startupinfo,
                creationflags=creationflags,
                start_new_session=start_new_session,
            )
        except OSError:
            return self._failure(
                request.engine_mode,
                RuntimeExecutionStatus.CRASHED,
                "SIMULATION_WORKER_START_FAILED",
                "隔离仿真 Worker 无法启动。",
                retryable=True,
            )
        deadline = time.monotonic() + request.limits.wall_timeout_ms / 1000
        worker_input: str | None = encoded
        while True:
            if cancellation.canceled:
                self._terminate_and_drain(process)
                return self._failure(
                    request.engine_mode,
                    RuntimeExecutionStatus.CANCELED,
                    "SIMULATION_CANCELED",
                    "仿真已取消，Worker 进程树已回收。",
                )
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self._terminate_and_drain(process)
                return self._failure(
                    request.engine_mode,
                    RuntimeExecutionStatus.TIMED_OUT,
                    "SIMULATION_WORKER_TIMEOUT",
                    "仿真 Worker 超过墙钟时限，进程树已回收。",
                    retryable=True,
                )
            try:
                stdout, _stderr = process.communicate(
                    worker_input,
                    timeout=min(self._polling_interval_seconds, remaining),
                )
                break
            except subprocess.TimeoutExpired:
                worker_input = None
                continue
            except OSError:
                self._terminate_and_drain(process)
                return self._failure(
                    request.engine_mode,
                    RuntimeExecutionStatus.CRASHED,
                    "SIMULATION_WORKER_IO_FAILED",
                    "仿真 Worker 通信失败，进程树已回收。",
                    retryable=True,
                )
        if process.returncode != 0:
            return self._failure(
                request.engine_mode,
                RuntimeExecutionStatus.CRASHED,
                "SIMULATION_WORKER_CRASHED",
                "仿真 Worker 异常退出；未采信其标准错误输出。",
                retryable=True,
            )
        if len(stdout.encode("utf-8")) > MAX_WORKER_OUTPUT_BYTES:
            return self._failure(
                request.engine_mode,
                RuntimeExecutionStatus.FAILED,
                "SIMULATION_WORKER_OUTPUT_LIMIT_EXCEEDED",
                "仿真 Worker 输出超过协议上限。",
            )
        try:
            result = RuntimeExecutionResult.model_validate_json(stdout)
        except ValueError:
            return self._failure(
                request.engine_mode,
                RuntimeExecutionStatus.FAILED,
                "SIMULATION_WORKER_PROTOCOL_INVALID",
                "仿真 Worker 输出未通过严格协议校验。",
            )
        if result.engine_mode is not request.engine_mode:
            return self._failure(
                request.engine_mode,
                RuntimeExecutionStatus.FAILED,
                "SIMULATION_WORKER_ENGINE_MISMATCH",
                "仿真 Worker 返回了与固定 engine mode 不一致的结果。",
            )
        if request.engine_mode is RuntimeEngineMode.BEHAVIORAL_REFERENCE and (
            result.native_core_verified or result.evidence_eligible
        ):
            return self._failure(
                request.engine_mode,
                RuntimeExecutionStatus.FAILED,
                "SIMULATION_WORKER_EVIDENCE_BOUNDARY_VIOLATION",
                "行为参考 Worker 越过了原生执行或 Evidence 边界。",
            )
        return result

    def _validate_quotas(
        self, request: RuntimeExecutionRequest
    ) -> RuntimeExecutionResult | None:
        maximum = self._package.manifest.maximum_limits
        values = request.limits.model_dump()
        maximum_values = maximum.model_dump()
        for key, value in values.items():
            if value > maximum_values[key]:
                return self._failure(
                    request.engine_mode,
                    RuntimeExecutionStatus.FAILED,
                    "SIMULATION_QUOTA_INVALID",
                    "请求的仿真资源上限超过 runtime package 许可范围。",
                )
        return None

    def _terminate_and_drain(self, process: Any) -> None:
        self._terminate_tree(process)
        try:
            process.communicate(None, timeout=1)
        except (OSError, subprocess.TimeoutExpired):
            pass

    @staticmethod
    def _failure(
        engine_mode: RuntimeEngineMode,
        status: RuntimeExecutionStatus,
        code: str,
        message: str,
        *,
        retryable: bool = False,
    ) -> RuntimeExecutionResult:
        return RuntimeExecutionResult(
            engineMode=engine_mode,
            status=status,
            runtimePackageRevisionId="runtime/zw-mpy-sim@1",
            nativeCoreVerified=False,
            evidenceEligible=False,
            deterministicDigest=None,
            serialOutput="",
            events=[],
            resourceUsage=RuntimeResourceUsage(
                instructions=0,
                events=0,
                outputBytes=0,
                peakHeapBytes=0,
                virtualTimeUs=0,
            ),
            error=RuntimeErrorDetail(
                code=code,
                message=message,
                retryable=retryable,
            ),
        )


def _minimal_environment() -> dict[str, str]:
    environment = {
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP"):
        value = os.environ.get(key)
        if value:
            environment[key] = value
    return environment


def _terminate_process_tree(process: Any) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
            timeout=3,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
