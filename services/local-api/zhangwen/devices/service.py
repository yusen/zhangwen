"""Application service for controlled MicroPython and firmware operations."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
import secrets
import uuid
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from zhangwen.code_agent.models import CodeRun, CodeRunStatus
from zhangwen.code_agent.repository import CodeRepository
from zhangwen.code_agent.validation import is_uploadable_python_path
from zhangwen.devices.models import (
    DeviceBackupSummary,
    DeviceDeploymentChannel,
    DeviceOperation,
    DeviceOperationKind,
    DeviceOperationPhase,
    DeviceOperationStatus,
    DeviceOperationStep,
    DevicePort,
    DeviceSession,
    DeviceSessionStatus,
    DeviceTerminalSnapshot,
    DeviceTerminalStatus,
    DeviceTerminalUnlock,
    DeviceVerification,
    EspClawEndpoint,
    EspClawEndpointStatus,
    FirmwareApplicationInstallPlan,
    FirmwareCandidate,
    FirmwareFlashPlan,
    WateringSmokeEvidence,
)
from zhangwen.devices.repository import (
    DeviceDeploymentSessionMismatch,
    DeviceOperationIdempotencyConflict,
    DevicePortLeaseBusy,
    DeviceProjectLeaseBusy,
    DeviceRepository,
    DeviceSessionNotReady,
)
from zhangwen.devices.espclaw import (
    ESP_CLAW_STORAGE_BASE_PATH,
    EspClawAdapterCanceled,
    EspClawAdapterError,
    EspClawDeploymentAdapter,
    HttpxEspClawDeploymentAdapter,
    normalize_espclaw_mcp_endpoint,
    normalize_espclaw_web_endpoint,
)
from zhangwen.devices.transport import (
    DeviceIdentityRequirement,
    DeviceTransport,
    DeviceTransportCanceled,
    DeviceTransportError,
    DeviceTransportTimedOut,
    TransportResult,
    TransportSession,
)
from zhangwen.device_lab.models import SupportedDeviceBoardId
from zhangwen.device_lab.boards import normalize_board_id
from zhangwen.device_lab.applications import (
    ApplicationValidationError,
    validate_application_archive,
)
from zhangwen.device_lab.models import (
    FirmwareApplicationRecord,
    FirmwareImageSegment,
    ParameterSetRevision,
)
from zhangwen.device_lab.repository import DeviceLabRepository
from zhangwen.device_lab.service import DeviceLabError, DeviceLabService


MAX_FIRMWARE_BYTES = 32 * 1024 * 1024
MAX_FLASH_ADDRESS = 16 * 1024 * 1024 - 1
FIRMWARE_CANDIDATE_TTL = timedelta(minutes=10)
FIRMWARE_CONFIRMATION_TTL = timedelta(minutes=3)
FIRMWARE_CONFIRMATION_PHRASE = "烧录固件"
APPLICATION_INSTALL_CONFIRMATION_PHRASE = "安装应用"
HARDWARE_RESET_CONFIRMATION_PHRASE = "确认硬件复位"
MAX_TERMINAL_OUTPUT_CHARS = 64_000
MAX_TERMINAL_WRITE_BYTES = 512
TERMINAL_UNLOCK_TTL = timedelta(minutes=10)
TERMINAL_UNLOCK_CONFIRMATION_PHRASE = "解锁终端输入"
_OPERATION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{7,127}")
_ESPCLAW_PATH_SEGMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
_WATERING_LOG_FIELD = re.compile(r"\b([A-Za-z][A-Za-z0-9_]*)=([^\s]+)")
_UNHANDLED_RUNTIME_MARKERS = (
    "traceback",
    "unhandled exception",
    "uncaught exception",
    "fatal error",
)
_ESPCLAW_TERMINAL_JOB_STATES = frozenset(
    {
        "completed",
        "complete",
        "success",
        "succeeded",
        "done",
        "failed",
        "error",
        "canceled",
        "cancelled",
        "timeout",
        "stopped",
    }
)


class DeviceServiceError(RuntimeError):
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


class _FlowFailure(RuntimeError):
    def __init__(
        self,
        code: str,
        phase: DeviceOperationPhase,
        result: TransportResult,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.phase = phase
        self.result = result


class DeviceOperationService:
    """Coordinates policy, persistence and one injected transport instance."""

    def __init__(
        self,
        db_path: Path,
        data_dir: Path,
        transport: DeviceTransport,
        *,
        command_timeout_seconds: float = 30.0,
        upload_timeout_seconds: float = 120.0,
        flash_timeout_seconds: float = 300.0,
        espclaw_adapter: EspClawDeploymentAdapter | None = None,
        espclaw_poll_interval_seconds: float = 0.25,
    ) -> None:
        self._db_path = Path(db_path)
        self._data_dir = Path(data_dir)
        self._repo = DeviceRepository(self._db_path)
        self._transport = transport
        self._command_timeout = command_timeout_seconds
        self._upload_timeout = upload_timeout_seconds
        self._flash_timeout = flash_timeout_seconds
        self._espclaw = espclaw_adapter or HttpxEspClawDeploymentAdapter()
        self._espclaw_poll_interval = espclaw_poll_interval_seconds
        self._transport_sessions: dict[str, TransportSession] = {}
        self._identity_requirements: dict[str, DeviceIdentityRequirement] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._cancellations: dict[str, asyncio.Event] = {}
        self._port_locks: dict[str, asyncio.Lock] = {}
        self._states: dict[str, dict[str, object]] = {}
        self._candidates: dict[str, tuple[FirmwareCandidate, Path]] = {}
        self._confirmations: dict[str, tuple[str, str, int, datetime]] = {}
        self._application_confirmations: dict[str, tuple[str, str, datetime]] = {}
        self._terminal_tasks: dict[str, asyncio.Task[None]] = {}
        self._terminal_cancellations: dict[str, asyncio.Event] = {}
        self._terminal_output: dict[str, str] = {}
        self._terminal_status: dict[str, DeviceTerminalStatus] = {}
        self._terminal_revision: dict[str, int] = {}
        self._terminal_started_at: dict[str, str] = {}
        self._terminal_updated_at: dict[str, str] = {}
        self._terminal_errors: dict[str, str] = {}
        self._terminal_unlocks: dict[str, tuple[str, datetime]] = {}

    async def scan_ports(self) -> list[DevicePort]:
        return await self._transport.scan_ports()

    async def shutdown(self) -> None:
        """Cooperatively stop device work before the Sidecar event loop exits."""

        active = {
            operation_id: task
            for operation_id, task in self._tasks.items()
            if not task.done()
        }
        for operation_id in active:
            cancel = self._cancellations.get(operation_id)
            if cancel is not None:
                cancel.set()
        for session_id in list(self._terminal_tasks):
            await self._stop_terminal_handle(session_id)
        if not active:
            return

        shutdown_timeout = min(55.0, max(5.0, self._command_timeout * 8))
        _done, pending = await asyncio.wait(
            active.values(),
            timeout=shutdown_timeout,
        )
        pending_set = set(pending)
        for operation_id, task in active.items():
            if task not in pending_set:
                continue
            state = self._states.get(operation_id)
            if state is None:
                continue
            metadata = state.get("metadata")
            if (
                isinstance(metadata, dict)
                and metadata.get("channel")
                == DeviceDeploymentChannel.ESP_CLAW.value
            ):
                # Never Task.cancel() an ESP-Claw safety cleanup.  Preserve an
                # explicit unsafe result so a host-level loop shutdown cannot
                # be mistaken for a confirmed remote stop.
                self._mark_espclaw_cleanup_timeout(
                    state,
                    runtime_start_attempted=bool(metadata.get("jobName")),
                    wrote_any=True,
                )
                self._record_espclaw_recovery_verification(state)
                self._finish_state(
                    state,
                    status=DeviceOperationStatus.FAILED,
                    error_code="ESP_CLAW_EMERGENCY_STOP_UNCONFIRMED",
                    message=(
                        "Sidecar shutdown reached its safety deadline before ESP-Claw "
                        "stop and rollback were confirmed; manually stop actuators and inspect the device."
                    ),
                )
                try:
                    operation = self._repo.get_operation_by_id(operation_id)
                except ValueError:
                    continue
                self._persist(
                    operation.projectId,
                    operation_id,
                    state,
                    DeviceOperationStatus.FAILED,
                )
                self._repo.set_session_status(
                    operation.projectId,
                    operation.sessionId,
                    DeviceSessionStatus.ERROR,
                )

    def get_terminal(self, project_id: str, session_id: str) -> DeviceTerminalSnapshot:
        self._repo.get_session(project_id, session_id)
        return self._terminal_snapshot(session_id)

    async def start_terminal(
        self,
        project_id: str,
        session_id: str,
    ) -> DeviceTerminalSnapshot:
        if self._repo.has_active_espclaw_operation(project_id):
            raise DeviceServiceError(
                "DEVICE_OPERATION_ACTIVE",
                "ESP-Claw code deployment is active; the serial terminal remains locked.",
                status_code=409,
                retryable=True,
            )
        session = self._ready_session(project_id, session_id)
        current = self._terminal_tasks.get(session_id)
        if current is not None and not current.done():
            return self._terminal_snapshot(session_id)
        lock = self._port_locks.setdefault(session.portId, asyncio.Lock())
        if lock.locked():
            raise DeviceServiceError(
                "DEVICE_PORT_BUSY",
                "设备端口正在执行其他操作，暂时不能启动串口终端。",
                status_code=409,
                retryable=True,
            )
        cancel = asyncio.Event()
        self._terminal_cancellations[session_id] = cancel
        self._terminal_status[session_id] = DeviceTerminalStatus.STARTING
        self._terminal_started_at[session_id] = _now()
        self._touch_terminal(session_id)
        task = asyncio.create_task(
            self._monitor_terminal(project_id, session, cancel),
            name=f"device-terminal-{session_id}",
        )
        self._terminal_tasks[session_id] = task
        await asyncio.sleep(0)
        return self._terminal_snapshot(session_id)

    async def stop_terminal(
        self,
        project_id: str,
        session_id: str,
    ) -> DeviceTerminalSnapshot:
        self._repo.get_session(project_id, session_id)
        await self._stop_terminal_handle(session_id)
        return self._terminal_snapshot(session_id)

    def clear_terminal(self, project_id: str, session_id: str) -> DeviceTerminalSnapshot:
        self._repo.get_session(project_id, session_id)
        self._terminal_output[session_id] = ""
        self._touch_terminal(session_id)
        return self._terminal_snapshot(session_id)

    def unlock_terminal_input(
        self,
        project_id: str,
        session_id: str,
        *,
        confirm_professional_mode: bool,
        confirmation_phrase: str,
    ) -> DeviceTerminalUnlock:
        self._ready_session(project_id, session_id)
        if not confirm_professional_mode or (
            confirmation_phrase != TERMINAL_UNLOCK_CONFIRMATION_PHRASE
        ):
            raise DeviceServiceError(
                "DEVICE_TERMINAL_UNLOCK_CONFIRMATION_REQUIRED",
                "请在三师专业模式输入“解锁终端输入”。",
                status_code=409,
            )
        if self._terminal_status.get(session_id) is not DeviceTerminalStatus.RUNNING:
            raise DeviceServiceError(
                "DEVICE_TERMINAL_NOT_RUNNING",
                "请先启动只读串口终端，再解锁本次会话输入。",
                status_code=409,
                retryable=True,
            )
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + TERMINAL_UNLOCK_TTL
        self._terminal_unlocks[session_id] = (token, expires_at)
        return DeviceTerminalUnlock(
            sessionId=session_id,
            unlockToken=token,
            expiresAt=expires_at.isoformat(),
            maxBytesPerWrite=MAX_TERMINAL_WRITE_BYTES,
        )

    async def write_terminal_input(
        self,
        project_id: str,
        session_id: str,
        *,
        unlock_token: str,
        value: str,
    ) -> DeviceTerminalSnapshot:
        self._ready_session(project_id, session_id)
        unlock = self._terminal_unlocks.get(session_id)
        now = datetime.now(UTC)
        if (
            unlock is None
            or unlock[1] <= now
            or not secrets.compare_digest(unlock[0], unlock_token)
        ):
            self._terminal_unlocks.pop(session_id, None)
            raise DeviceServiceError(
                "DEVICE_TERMINAL_UNLOCK_REQUIRED",
                "终端输入尚未解锁或已过期，请重新确认。",
                status_code=409,
            )
        if self._terminal_status.get(session_id) is not DeviceTerminalStatus.RUNNING:
            raise DeviceServiceError(
                "DEVICE_TERMINAL_NOT_RUNNING",
                "串口终端未运行，不能发送输入。",
                status_code=409,
                retryable=True,
            )
        encoded = value.encode("utf-8")
        if not encoded or len(encoded) > MAX_TERMINAL_WRITE_BYTES:
            raise DeviceServiceError(
                "DEVICE_TERMINAL_INPUT_INVALID",
                f"单次终端输入必须为 1–{MAX_TERMINAL_WRITE_BYTES} 字节。",
            )
        if "\x00" in value or any(
            ord(char) < 32 and char not in {"\r", "\n", "\t"}
            for char in value
        ):
            raise DeviceServiceError(
                "DEVICE_TERMINAL_INPUT_INVALID",
                "终端输入包含不允许的控制字符。",
            )
        handle = self._transport_sessions.get(session_id)
        if handle is None:
            session = self._repo.get_session(project_id, session_id)
            handle = TransportSession(
                session.id,
                self._transport.resolve_port(session.portId),
            )
        result = await self._transport.write_terminal(handle, encoded)
        if result.exit_code != 0:
            raise DeviceServiceError(
                "DEVICE_TERMINAL_WRITE_FAILED",
                "终端输入未发送，请检查连接后重试。",
                status_code=409,
                retryable=True,
            )
        # Intentionally do not echo or persist the user input.
        return self._terminal_snapshot(session_id)

    def evaluate_watering_smoke(
        self,
        project_id: str,
        session_id: str,
        operation_id: str | None = None,
    ) -> tuple[WateringSmokeEvidence, DeviceOperation]:
        """Evaluate read-only runtime logs and persist sanitized deployment evidence.

        The method never drives a pump or changes GPIO state. The user first
        observes the wet/dry scenarios on the connected device; this boundary
        only parses the emitted ``ZW_WATER`` records and attaches the result to
        the already completed upload operation.
        """

        self._repo.get_session(project_id, session_id)
        operation = self._watering_upload_operation(project_id, session_id, operation_id)
        evidence = evaluate_watering_smoke_output(
            self._terminal_output.get(session_id, ""),
            session_id=session_id,
            operation_id=operation.id,
        )
        state = dict(self._state(operation.id, operation))
        metadata = state.get("metadata")
        normalized_metadata = dict(metadata) if isinstance(metadata, dict) else {}
        normalized_metadata["runtimeEvidence"] = evidence.model_dump(mode="json")
        state["metadata"] = normalized_metadata
        self._states[operation.id] = state
        self._repo.update_operation(
            project_id,
            operation.id,
            status=operation.status,
            log=_encode_state(state),
            completed_at=operation.completedAt,
        )
        updated = self._repo.sync_operation_artifact(project_id, operation.id)
        return evidence, updated

    def _watering_upload_operation(
        self,
        project_id: str,
        session_id: str,
        operation_id: str | None,
    ) -> DeviceOperation:
        if operation_id is not None:
            candidates = [self._repo.get_operation(project_id, operation_id)]
        else:
            candidates = self._repo.list_operations(project_id, limit=100)
        operation = next(
            (
                item
                for item in candidates
                if item.sessionId == session_id
                and item.kind == DeviceOperationKind.UPLOAD_CODE
                and item.status == DeviceOperationStatus.COMPLETED
                and not item.dryRun
            ),
            None,
        )
        if operation is None:
            raise DeviceServiceError(
                "DEVICE_SMOKE_UPLOAD_REQUIRED",
                "请先把已接受代码上传并运行，再根据设备日志核验浇花冒烟测试。",
                status_code=409,
            )
        return operation

    async def _monitor_terminal(
        self,
        project_id: str,
        session: DeviceSession,
        cancel: asyncio.Event,
    ) -> None:
        monitor_task = asyncio.current_task()
        lock = self._port_locks.setdefault(session.portId, asyncio.Lock())
        handle = self._transport_sessions.get(session.id)
        if handle is None:
            handle = TransportSession(session.id, self._transport.resolve_port(session.portId))
        try:
            async with lock:
                if cancel.is_set():
                    self._terminal_status[session.id] = DeviceTerminalStatus.STOPPED
                    self._touch_terminal(session.id)
                    return
                self._terminal_status[session.id] = DeviceTerminalStatus.RUNNING
                self._terminal_errors.pop(session.id, None)
                self._touch_terminal(session.id)
                result = await self._transport.monitor_terminal(
                    handle,
                    cancel=cancel,
                    on_output=lambda chunk: self._append_terminal_output(session.id, chunk),
                )
                if cancel.is_set():
                    self._terminal_status[session.id] = DeviceTerminalStatus.STOPPED
                elif result.exit_code == 0:
                    self._terminal_status[session.id] = DeviceTerminalStatus.STOPPED
                else:
                    self._terminal_status[session.id] = DeviceTerminalStatus.ERROR
                    self._terminal_errors[session.id] = "串口终端意外结束，请重新启动。"
                self._touch_terminal(session.id)
        except (DeviceTransportError, OSError, ValueError):
            self._terminal_status[session.id] = DeviceTerminalStatus.ERROR
            self._terminal_errors[session.id] = "串口终端无法读取设备输出。"
            self._touch_terminal(session.id)
        finally:
            current = self._terminal_tasks.get(session.id)
            if current is monitor_task:
                self._terminal_tasks.pop(session.id, None)
            self._terminal_cancellations.pop(session.id, None)

    async def _stop_terminal_handle(self, session_id: str) -> None:
        self._terminal_unlocks.pop(session_id, None)
        cancel = self._terminal_cancellations.get(session_id)
        task = self._terminal_tasks.get(session_id)
        if cancel is not None:
            cancel.set()
        if task is not None and not task.done():
            try:
                await asyncio.wait_for(task, timeout=min(self._command_timeout, 5.0))
            except TimeoutError:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._terminal_tasks.pop(session_id, None)
        self._terminal_cancellations.pop(session_id, None)
        self._terminal_status[session_id] = DeviceTerminalStatus.STOPPED
        self._touch_terminal(session_id)

    def _append_terminal_output(self, session_id: str, chunk: str) -> None:
        if not chunk:
            return
        clean = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", chunk)
        combined = self._terminal_output.get(session_id, "") + clean
        self._terminal_output[session_id] = combined[-MAX_TERMINAL_OUTPUT_CHARS:]
        self._touch_terminal(session_id)

    def _touch_terminal(self, session_id: str) -> None:
        self._terminal_revision[session_id] = self._terminal_revision.get(session_id, 0) + 1
        self._terminal_updated_at[session_id] = _now()

    def _terminal_snapshot(self, session_id: str) -> DeviceTerminalSnapshot:
        return DeviceTerminalSnapshot(
            sessionId=session_id,
            status=self._terminal_status.get(session_id, DeviceTerminalStatus.IDLE),
            output=self._terminal_output.get(session_id, ""),
            revision=self._terminal_revision.get(session_id, 0),
            startedAt=self._terminal_started_at.get(session_id),
            updatedAt=self._terminal_updated_at.get(session_id),
            errorMessage=self._terminal_errors.get(session_id),
        )

    async def _release_transport_handle(
        self,
        handle: TransportSession,
        cancel: asyncio.Event,
    ) -> None:
        try:
            await self._transport.disconnect(
                handle,
                cancel=cancel,
                timeout_seconds=self._command_timeout,
            )
        except (DeviceTransportError, TimeoutError):
            # The connection already failed; do not mask the original error.
            pass

    async def connect(
        self,
        project_id: str,
        port_id: str,
        *,
        board_id: SupportedDeviceBoardId,
        identity_requirement: DeviceIdentityRequirement | None = None,
    ) -> DeviceSession:
        self.require_project_board(project_id, board_id)
        try:
            port = self._transport.resolve_port(port_id)
        except (ValueError, DeviceTransportError) as exc:
            raise DeviceServiceError("DEVICE_PORT_NOT_FOUND", "未找到可连接的设备端口。") from exc
        lock = self._port_locks.setdefault(port.id, asyncio.Lock())
        if lock.locked():
            raise DeviceServiceError("DEVICE_PORT_BUSY", "设备端口正在执行其他操作。", status_code=409)
        cancel = asyncio.Event()
        async with lock:
            try:
                handle, result = await asyncio.wait_for(
                    self._transport.connect(
                        port,
                        cancel=cancel,
                        timeout_seconds=self._command_timeout,
                    ),
                    timeout=self._command_timeout,
                )
            except TimeoutError as exc:
                raise DeviceServiceError(
                    "DEVICE_CONNECTION_TIMEOUT",
                    "连接设备超时。",
                    status_code=408,
                    retryable=True,
                ) from exc
            except DeviceTransportError as exc:
                raise self._service_error(exc, "DEVICE_CONNECTION_FAILED") from exc
            if result.exit_code != 0:
                await self._release_transport_handle(handle, cancel)
                raise DeviceServiceError(
                    "DEVICE_CONNECTION_FAILED",
                    _connection_failure_message(result.output),
                    retryable=True,
                )
            session = self._repo.connect_port(
                project_id,
                port,
                board_id=board_id,
                status=DeviceSessionStatus.ATTACHED_UNVERIFIED,
                messages=[
                    ("INFO", f"发现设备：{port.label}。"),
                    ("INFO", "已附加串口，尚未执行设备代码或身份探测。"),
                ],
            )
            self._transport_sessions[session.id] = handle
            if identity_requirement is not None:
                self._identity_requirements[session.id] = identity_requirement
            return session

    def require_project_board(
        self,
        project_id: str,
        board_id: SupportedDeviceBoardId,
        *,
        mismatch_code: str = "DEVICE_PROJECT_BOARD_MISMATCH",
    ) -> SupportedDeviceBoardId:
        """Fail closed unless the target board matches the current project scene."""

        try:
            # Re-project from the approved proposal instead of relying on a
            # prior GET /device-lab/scene side effect or a stale cached row.
            scene = DeviceLabService(self._db_path, self._data_dir).get_scene(project_id)
        except DeviceLabError as exc:
            raise DeviceServiceError(
                "DEVICE_LAB_SCENE_REQUIRED",
                "Device access requires a project DeviceLabScene derived from an approved proposal; no default board is inferred.",
                status_code=409,
            ) from exc
        if scene.boardId != board_id:
            raise DeviceServiceError(
                mismatch_code,
                "The selected device board does not match the current project DeviceLabScene.",
                status_code=409,
            )
        return scene.boardId

    async def takeover_runtime(
        self,
        project_id: str,
        session_id: str,
        *,
        confirm_hardware_reset: bool = False,
        confirmation_phrase: str | None = None,
    ) -> DeviceSession:
        """Cooperatively acquire a MicroPython management prompt before probing.

        Hardware reset is a separate, explicit recovery branch.  It is never
        reached merely because Ctrl-C failed.
        """

        session = self._serial_session(project_id, session_id)
        if session.status in {
            DeviceSessionStatus.DISCONNECTED,
            DeviceSessionStatus.UPLOADING,
            DeviceSessionStatus.RESTARTING,
            DeviceSessionStatus.VERIFYING,
        }:
            raise DeviceServiceError(
                "DEVICE_SESSION_NOT_ATTACHABLE",
                "当前设备会话不能执行运行态接管。",
                status_code=409,
            )
        lock = self._port_locks.setdefault(session.portId, asyncio.Lock())
        if lock.locked():
            raise DeviceServiceError(
                "DEVICE_PORT_BUSY",
                "设备端口正在由另一个本地 Runner 使用。",
                status_code=409,
                retryable=True,
            )
        cancel = asyncio.Event()
        async with lock:
            handle = self._transport_sessions.get(session.id) or TransportSession(
                session.id,
                self._transport.resolve_port(session.portId),
            )
            self._repo.set_session_status(
                project_id, session.id, DeviceSessionStatus.RUNTIME_BUSY
            )
            try:
                interrupted = await self._transport.interrupt_runtime(
                    handle,
                    cancel=cancel,
                    timeout_seconds=self._command_timeout,
                )
            except DeviceTransportError as exc:
                raise self._service_error(
                    exc, "DEVICE_RUNTIME_INTERRUPT_FAILED"
                ) from exc
            if interrupted.exit_code != 0:
                if not confirm_hardware_reset:
                    raise DeviceServiceError(
                        "DEVICE_RUNTIME_BUSY",
                        "Ctrl-C 未取得管理提示符；设备仍保持运行。可在确认执行器安全后选择硬件复位接管。",
                        status_code=409,
                        retryable=True,
                    )
                if confirmation_phrase != HARDWARE_RESET_CONFIRMATION_PHRASE:
                    raise DeviceServiceError(
                        "DEVICE_HARD_RESET_CONFIRMATION_REQUIRED",
                        f"硬件复位前必须输入“{HARDWARE_RESET_CONFIRMATION_PHRASE}”。",
                        status_code=409,
                    )
                try:
                    reset = await self._transport.hard_reset(
                        handle,
                        cancel=cancel,
                        timeout_seconds=self._command_timeout,
                    )
                except DeviceTransportError as exc:
                    raise self._service_error(exc, "DEVICE_HARD_RESET_FAILED") from exc
                if reset.exit_code != 0:
                    raise DeviceServiceError(
                        "DEVICE_HARD_RESET_FAILED",
                        "硬件复位未成功，未继续执行身份探测或写入。",
                        status_code=409,
                        retryable=True,
                    )
                handle = await self._reattach_after_reset(handle, cancel)
                try:
                    interrupted = await self._transport.interrupt_runtime(
                        handle,
                        cancel=cancel,
                        timeout_seconds=self._command_timeout,
                    )
                except DeviceTransportError as exc:
                    raise self._service_error(
                        exc, "DEVICE_RESET_BREAK_IN_FAILED"
                    ) from exc
                if interrupted.exit_code != 0:
                    raise DeviceServiceError(
                        "DEVICE_RESET_BREAK_IN_FAILED",
                        "设备复位后未在启动窗口取得 MicroPython 管理提示符。",
                        status_code=409,
                        retryable=True,
                    )

            try:
                identity, probe = await self._transport.probe_identity(
                    handle,
                    cancel=cancel,
                    timeout_seconds=self._command_timeout,
                )
            except DeviceTransportError as exc:
                self._repo.set_session_status(
                    project_id,
                    session.id,
                    DeviceSessionStatus.ATTACHED_UNVERIFIED,
                )
                raise self._service_error(exc, "DEVICE_IDENTITY_PROBE_FAILED") from exc
            if probe.exit_code != 0:
                self._repo.set_session_status(
                    project_id,
                    session.id,
                    DeviceSessionStatus.ATTACHED_UNVERIFIED,
                )
                raise DeviceServiceError(
                    "DEVICE_IDENTITY_PROBE_FAILED",
                    "已取得管理提示符，但设备身份探测失败；写入保持禁止。",
                    status_code=409,
                    retryable=True,
                )
            requirement = self._identity_requirements.get(session.id)
            if requirement is not None and not requirement.matches(identity):
                self._repo.set_session_status(
                    project_id,
                    session.id,
                    DeviceSessionStatus.ATTACHED_UNVERIFIED,
                )
                raise DeviceServiceError(
                    "DEVICE_IDENTITY_MISMATCH",
                    "设备身份与项目目标不匹配；已在写入前停止。",
                    status_code=409,
                )
            self._transport_sessions[session.id] = handle
            return self._repo.set_session_status(
                project_id, session.id, DeviceSessionStatus.MANAGED
            )

    async def _reattach_after_reset(
        self,
        previous: TransportSession,
        cancel: asyncio.Event,
    ) -> TransportSession:
        await asyncio.sleep(0.35)
        try:
            ports = await self._transport.scan_ports()
        except DeviceTransportError as exc:
            raise self._service_error(exc, "DEVICE_REENUMERATION_FAILED") from exc
        replacement = _match_reenumerated_port(previous.port, ports)
        if replacement is None:
            raise DeviceServiceError(
                "DEVICE_REENUMERATION_TIMEOUT",
                "硬件复位后未找到同一设备端口。",
                status_code=409,
                retryable=True,
            )
        try:
            handle, attached = await self._transport.connect(
                replacement,
                cancel=cancel,
                timeout_seconds=self._command_timeout,
            )
        except DeviceTransportError as exc:
            raise self._service_error(exc, "DEVICE_REATTACH_FAILED") from exc
        if attached.exit_code != 0:
            raise DeviceServiceError(
                "DEVICE_REATTACH_FAILED",
                "设备端口已重枚举，但重新附加失败。",
                status_code=409,
                retryable=True,
            )
        return handle

    async def disconnect(self, project_id: str, session_id: str) -> DeviceSession:
        session = self._physical_serial_session(project_id, session_id)
        operations = [
            self._reconcile_orphaned_operation(project_id, operation)
            for operation in self._repo.list_operations(project_id, limit=100)
        ]
        if any(
            operation.sessionId == session_id
            and operation.status in {DeviceOperationStatus.QUEUED, DeviceOperationStatus.RUNNING}
            for operation in operations
        ):
            raise DeviceServiceError(
                "DEVICE_OPERATION_ACTIVE",
                "设备仍有进行中的操作，请先取消或等待完成。",
                status_code=409,
            )
        await self._stop_terminal_handle(session_id)
        handle = self._transport_sessions.get(session_id)
        if handle is None:
            handle = TransportSession(session.id, self._transport.resolve_port(session.portId))
        cancel = asyncio.Event()
        try:
            result = await self._transport.disconnect(
                handle,
                cancel=cancel,
                timeout_seconds=self._command_timeout,
            )
        except DeviceTransportError as exc:
            raise self._service_error(exc, "DEVICE_DISCONNECT_FAILED") from exc
        if result.exit_code != 0:
            raise DeviceServiceError("DEVICE_DISCONNECT_FAILED", "断开设备失败。")
        self._transport_sessions.pop(session_id, None)
        self._identity_requirements.pop(session_id, None)
        return self._repo.disconnect_session(project_id, session_id)

    async def start_upload(
        self,
        *,
        project_id: str,
        session_id: str,
        code_run_id: str,
        operation_id: str | None,
        confirm_write: bool,
    ) -> tuple[DeviceOperation, DeviceSession]:
        if not confirm_write:
            raise DeviceServiceError(
                "DEVICE_UPLOAD_CONFIRMATION_REQUIRED",
                "上传会覆盖设备同名文件，必须明确确认。",
            )
        operation_id = _validated_operation_id(operation_id)
        self._serial_session(project_id, session_id)
        fingerprint = _fingerprint("upload", project_id, session_id, code_run_id)
        if existing := self._existing_idempotent(project_id, operation_id, fingerprint):
            return existing, self._repo.get_session(project_id, existing.sessionId)

        code_repository = CodeRepository(self._db_path)
        current = code_repository.get_current_code(project_id)
        if current is None or current.id != code_run_id:
            raise DeviceServiceError(
                "DEVICE_CODE_REVISION_CONFLICT",
                "只能上传当前最新代码版本。",
                status_code=409,
                retryable=True,
            )
        if current.status != CodeRunStatus.ACCEPTED:
            raise DeviceServiceError(
                "DEVICE_REQUIRES_ACCEPTED_CODE",
                "只有当前已接受的代码版本可以上传。",
            )
        if _code_runtime_value(current) != "MICROPYTHON":
            raise DeviceServiceError(
                "DEVICE_USB_RUNTIME_REQUIRED",
                "USB serial deployment accepts only a MICROPYTHON CodeRun.",
            )
        files = _upload_files(current)
        await self._stop_terminal_handle(session_id)
        state = _initial_state(
            DeviceOperationKind.UPLOAD_CODE,
            fingerprint,
            metadata={
                "channel": DeviceDeploymentChannel.USB_SERIAL.value,
                "codeRunId": code_run_id,
                "targetId": session_id,
                "fileCount": len(files),
            },
        )
        operation, created = self._reserve_operation(
            project_id=project_id,
            session_id=session_id,
            operation_id=operation_id,
            kind=DeviceOperationKind.UPLOAD_CODE,
            command_label="mpremote",
            state=state,
            fingerprint=fingerprint,
        )
        session = self._repo.get_session(project_id, operation.sessionId)
        if not created:
            return operation, session
        self._states[operation_id] = state
        cancel = asyncio.Event()
        self._cancellations[operation_id] = cancel
        self._tasks[operation_id] = asyncio.create_task(
            self._execute_upload(project_id, session, operation_id, files, cancel),
            name=f"device-upload-{operation_id}",
        )
        return operation, session

    async def pair_espclaw_endpoint(
        self,
        *,
        project_id: str,
        web_endpoint: str,
        mcp_endpoint: str,
        board_id: SupportedDeviceBoardId,
        confirm_trusted_lan: bool,
        confirm_admin_mode: bool,
        confirm_board_identity: bool,
    ) -> EspClawEndpoint:
        if not (confirm_trusted_lan and confirm_admin_mode and confirm_board_identity):
            raise DeviceServiceError(
                "ESP_CLAW_PAIR_CONFIRMATION_REQUIRED",
                "Pairing requires explicit confirmation of trusted LAN, Admin Mode, and exact board identity.",
            )
        self.require_project_board(
            project_id,
            board_id,
            mismatch_code="ESP_CLAW_PROJECT_BOARD_MISMATCH",
        )
        try:
            normalized_web = normalize_espclaw_web_endpoint(web_endpoint)
            normalized_mcp = normalize_espclaw_mcp_endpoint(mcp_endpoint)
            if urlsplit(normalized_web).hostname != urlsplit(normalized_mcp).hostname:
                raise EspClawAdapterError(
                    "ESP_CLAW_ENDPOINT_HOST_MISMATCH",
                    "ESP-Claw Web Console and MCP endpoints must use the same hostname.",
                )
            handshake = await self._espclaw.handshake(
                normalized_web,
                normalized_mcp,
                cancel=asyncio.Event(),
                timeout_seconds=self._command_timeout,
            )
        except EspClawAdapterError as exc:
            raise DeviceServiceError(
                exc.code,
                str(exc),
                status_code=408 if exc.code == "ESP_CLAW_REQUEST_TIMEOUT" else 422,
                retryable=exc.retryable,
            ) from exc
        if handshake.storage_base_path != ESP_CLAW_STORAGE_BASE_PATH:
            raise DeviceServiceError(
                "ESP_CLAW_STORAGE_PATH_MISMATCH",
                "ESP-Claw storage base must be /fatfs.",
            )
        if not handshake.file_readback_capable:
            raise DeviceServiceError(
                "ESP_CLAW_FILE_READBACK_UNAVAILABLE",
                "ESP-Claw pairing requires a read-only Web File API probe before any deployment can write.",
            )
        if not handshake.reported_board_id:
            raise DeviceServiceError(
                "ESP_CLAW_BOARD_IDENTITY_REQUIRED",
                "ESP-Claw pairing requires a verifiable board identity handshake.",
                status_code=409,
            )
        try:
            reported_board = normalize_board_id(handshake.reported_board_id)
        except ValueError as exc:
            raise DeviceServiceError(
                "ESP_CLAW_BOARD_UNSUPPORTED",
                "ESP-Claw reported a board outside the two-board whitelist.",
                status_code=409,
            ) from exc
        if reported_board != board_id:
            raise DeviceServiceError(
                "ESP_CLAW_BOARD_MISMATCH",
                "ESP-Claw reported board does not match the explicitly confirmed board.",
                status_code=409,
            )
        return self._repo.pair_espclaw_endpoint(
            project_id=project_id,
            web_endpoint=normalized_web,
            mcp_endpoint=normalized_mcp,
            board_id=board_id,
            handshake=handshake,
        )

    def list_espclaw_endpoints(self, project_id: str) -> list[EspClawEndpoint]:
        return self._repo.list_espclaw_endpoints(project_id)

    async def start_espclaw_deployment(
        self,
        *,
        project_id: str,
        endpoint_id: str,
        code_run_id: str,
        operation_id: str | None,
        confirm_write: bool,
    ) -> tuple[DeviceOperation, DeviceSession]:
        if not confirm_write:
            raise DeviceServiceError(
                "DEVICE_UPLOAD_CONFIRMATION_REQUIRED",
                "ESP-Claw code deployment overwrites versioned runtime files and must be confirmed.",
            )
        if any(task is not None and not task.done() for task in self._terminal_tasks.values()):
            raise DeviceServiceError(
                "DEVICE_OPERATION_ACTIVE",
                "A serial terminal is active; stop it before ESP-Claw deployment.",
                status_code=409,
                retryable=True,
            )
        operation_id = _validated_operation_id(operation_id)
        try:
            endpoint = self._repo.get_espclaw_endpoint(project_id, endpoint_id)
            session_id = self._repo.get_espclaw_session_id(project_id, endpoint_id)
        except ValueError as exc:
            raise DeviceServiceError(
                "ESP_CLAW_ENDPOINT_NOT_PAIRED",
                "ESP-Claw target must be paired inside the current project.",
                status_code=404,
            ) from exc
        if endpoint.status != EspClawEndpointStatus.READY:
            raise DeviceServiceError(
                "ESP_CLAW_ENDPOINT_REPAIR_REQUIRED",
                "ESP-Claw endpoint is not READY and must be explicitly re-paired before deployment.",
                status_code=409,
            )
        self.require_project_board(
            project_id,
            endpoint.boardId,
            mismatch_code="ESP_CLAW_PROJECT_BOARD_MISMATCH",
        )

        code_repository = CodeRepository(self._db_path)
        current = code_repository.get_current_code(project_id)
        if current is None or current.id != code_run_id:
            raise DeviceServiceError(
                "DEVICE_CODE_REVISION_CONFLICT",
                "Only the current code version can be deployed.",
                status_code=409,
                retryable=True,
            )
        if current.status != CodeRunStatus.ACCEPTED:
            raise DeviceServiceError(
                "DEVICE_REQUIRES_ACCEPTED_CODE",
                "Only the current accepted code version can be deployed.",
            )
        if _code_runtime_value(current) != "ESP_CLAW_LUA":
            raise DeviceServiceError(
                "ESP_CLAW_CODE_RUNTIME_REQUIRED",
                "ESP-Claw deployment accepts only an accepted ESP_CLAW_LUA CodeRun.",
            )
        files, entrypoint = _espclaw_code_files(current)
        file_digest = hashlib.sha256()
        for path in sorted(files):
            file_digest.update(path.encode("utf-8"))
            file_digest.update(b"\0")
            file_digest.update(files[path])
        content_sha256 = file_digest.hexdigest()
        project_segment = hashlib.sha256(project_id.encode("utf-8")).hexdigest()[:12]
        version_path = (
            f"{ESP_CLAW_STORAGE_BASE_PATH}/scripts/zhangwen/{project_segment}/"
            f"v{current.version}-{content_sha256[:12]}"
        )
        remote_files = {
            f"{version_path}/{path.removeprefix('scripts/')}": content
            for path, content in files.items()
        }
        remote_entrypoint = f"{version_path}/{entrypoint.removeprefix('scripts/')}"
        runtime_entrypoint = remote_entrypoint.removeprefix(
            f"{ESP_CLAW_STORAGE_BASE_PATH}/scripts/"
        )
        # The managed name is project-stable, not endpoint-row-stable.  A
        # physical ESP-Claw device may be paired through IP and mDNS aliases;
        # both aliases must still address one exclusive/replace job.
        job_name = _espclaw_job_name(project_id)
        fingerprint = _fingerprint(
            "deploy",
            DeviceDeploymentChannel.ESP_CLAW.value,
            project_id,
            endpoint_id,
            code_run_id,
            content_sha256,
        )
        if existing := self._existing_idempotent(project_id, operation_id, fingerprint):
            return existing, self._repo.get_session(project_id, existing.sessionId)
        state = _initial_state(
            DeviceOperationKind.UPLOAD_CODE,
            fingerprint,
            metadata={
                "channel": DeviceDeploymentChannel.ESP_CLAW.value,
                "codeRunId": code_run_id,
                "targetId": endpoint_id,
                "boardId": endpoint.boardId.value,
                "versionPath": version_path,
                "entrypoint": runtime_entrypoint,
                "remoteEntrypoint": remote_entrypoint,
                "jobName": job_name,
                "webStoragePath": version_path.removeprefix(ESP_CLAW_STORAGE_BASE_PATH),
                "fileCount": len(remote_files),
                "firmwareOperation": False,
                "flashOperation": False,
            },
        )
        operation, created = self._reserve_operation(
            project_id=project_id,
            session_id=session_id,
            operation_id=operation_id,
            kind=DeviceOperationKind.UPLOAD_CODE,
            command_label="ESP-Claw Web Console + MCP Lua",
            state=state,
            fingerprint=fingerprint,
        )
        session = self._repo.get_session(project_id, operation.sessionId)
        if not created:
            return operation, session
        self._repo.record_espclaw_deployment(
            operation_id=operation_id,
            endpoint_id=endpoint_id,
            code_run_id=code_run_id,
            version_path=version_path,
            entrypoint_path=runtime_entrypoint,
            fingerprint=fingerprint,
        )
        self._states[operation_id] = state
        cancel = asyncio.Event()
        self._cancellations[operation_id] = cancel
        self._tasks[operation_id] = asyncio.create_task(
            self._execute_espclaw_deployment(
                project_id,
                session,
                endpoint,
                operation_id,
                version_path,
                remote_files,
                runtime_entrypoint,
                job_name,
                cancel,
            ),
            name=f"espclaw-deploy-{operation_id}",
        )
        return operation, session

    def prepare_application_install(
        self,
        *,
        project_id: str,
        session_id: str,
        application_id: str,
        board_id: SupportedDeviceBoardId,
        confirm_board_identity: bool,
    ) -> FirmwareApplicationInstallPlan:
        if not confirm_board_identity:
            raise DeviceServiceError(
                "DEVICE_BOARD_CONFIRMATION_REQUIRED",
                "安装应用前必须确认精确板型；不能把任意 ESP32-S3 当作受支持板。",
            )
        session = self._supported_session(project_id, session_id)
        if session.board != board_id.value:
            raise DeviceServiceError(
                "DEVICE_BOARD_MISMATCH",
                "设备会话板型与安装计划不一致。",
                status_code=409,
            )
        application, _archive_path = self._validated_application(project_id, application_id)
        if application.manifest.boardId != board_id:
            raise DeviceServiceError(
                "FIRMWARE_APPLICATION_BOARD_MISMATCH",
                "应用包板型与设备会话不一致。",
                status_code=409,
            )
        token = secrets.token_urlsafe(32)
        expires = _now_dt() + FIRMWARE_CONFIRMATION_TTL
        self._application_confirmations[token] = (application_id, session_id, expires)
        total_bytes = sum(segment.sizeBytes for segment in application.manifest.deviceImages)
        return FirmwareApplicationInstallPlan(
            applicationId=application_id,
            sessionId=session_id,
            boardId=board_id,
            segmentCount=len(application.manifest.deviceImages),
            totalBytes=total_bytes,
            confirmationToken=token,
            expiresAt=expires.isoformat(),
            summary=(
                f"将备份、写入并逐段回读验证 {len(application.manifest.deviceImages)} 个分区段，"
                "保留 NVS 与用户数据，不执行整片擦除。"
            ),
        )

    async def start_application_install(
        self,
        *,
        project_id: str,
        session_id: str,
        application_id: str,
        confirmation_token: str,
        operation_id: str | None,
        confirm_install: bool,
        confirmation_phrase: str | None,
    ) -> tuple[DeviceOperation, DeviceSession]:
        if not confirm_install or confirmation_phrase != APPLICATION_INSTALL_CONFIRMATION_PHRASE:
            raise DeviceServiceError(
                "DEVICE_APPLICATION_INSTALL_CONFIRMATION_REQUIRED",
                f"请输入确认短语“{APPLICATION_INSTALL_CONFIRMATION_PHRASE}”。",
            )
        operation_id = _validated_operation_id(operation_id)
        try:
            session = self._repo.get_session(project_id, session_id)
        except ValueError as exc:
            raise DeviceServiceError(
                "DEVICE_SESSION_NOT_FOUND",
                "设备会话不存在。",
                status_code=404,
            ) from exc
        self._assert_supported_board(project_id, session_id, session=session)
        application, archive_path = self._validated_application(
            project_id, application_id
        )
        if session.board != application.manifest.boardId.value:
            raise DeviceServiceError(
                "FIRMWARE_APPLICATION_BOARD_MISMATCH",
                "应用包板型与设备会话不一致。",
                status_code=409,
            )
        fingerprint = _fingerprint(
            "install-application",
            project_id,
            session_id,
            application.archiveSha256,
        )
        if existing := self._existing_idempotent(
            project_id, operation_id, fingerprint
        ):
            return existing, self._repo.get_session(
                project_id, existing.sessionId
            )

        confirmation = self._application_confirmations.get(confirmation_token)
        if confirmation is None:
            raise DeviceServiceError(
                "DEVICE_APPLICATION_INSTALL_CONFIRMATION_INVALID",
                "应用安装确认已失效。",
                status_code=409,
            )
        confirmed_application, confirmed_session, expires = confirmation
        if (
            expires <= _now_dt()
            or confirmed_application != application_id
            or confirmed_session != session_id
        ):
            raise DeviceServiceError(
                "DEVICE_APPLICATION_INSTALL_CONFIRMATION_INVALID",
                "应用安装确认与当前计划不匹配。",
                status_code=409,
            )
        session = self._supported_session(project_id, session_id)
        await self._stop_terminal_handle(session_id)
        images = self._materialize_application_images(
            operation_id,
            application,
            archive_path,
        )
        state = _initial_state(
            DeviceOperationKind.INSTALL_APPLICATION,
            fingerprint,
            metadata={
                "applicationId": application.id,
                "applicationVersion": application.manifest.version,
                "boardId": application.manifest.boardId.value,
                "archiveSha256": application.archiveSha256,
                "segmentCount": len(application.manifest.deviceImages),
                "preservesNvs": True,
                "fullErase": False,
            },
        )
        operation, created = self._reserve_operation(
            project_id=project_id,
            session_id=session_id,
            operation_id=operation_id,
            kind=DeviceOperationKind.INSTALL_APPLICATION,
            command_label="esptool write-flash (verified segments)",
            state=state,
            fingerprint=fingerprint,
        )
        session = self._repo.get_session(project_id, operation.sessionId)
        if not created:
            return operation, session
        self._application_confirmations.pop(confirmation_token, None)
        self._states[operation_id] = state
        cancel = asyncio.Event()
        self._cancellations[operation_id] = cancel
        self._tasks[operation_id] = asyncio.create_task(
            self._execute_application_install(
                project_id,
                session,
                operation_id,
                application,
                images,
                cancel,
            ),
            name=f"device-application-install-{operation_id}",
        )
        return operation, session

    async def start_parameter_sync(
        self,
        *,
        project_id: str,
        session_id: str,
        parameter_set_id: str,
        operation_id: str | None,
        confirm_sync: bool,
    ) -> tuple[DeviceOperation, DeviceSession]:
        if not confirm_sync:
            raise DeviceServiceError(
                "DEVICE_PARAMETER_SYNC_CONFIRMATION_REQUIRED",
                "参数同步会修改设备受控数据区，必须明确确认。",
            )
        session = self._serial_session(project_id, session_id)
        try:
            parameter_set = DeviceLabRepository(self._db_path).get_parameter_set(
                project_id,
                parameter_set_id,
            )
        except KeyError as exc:
            raise DeviceServiceError(
                "PARAMETER_SET_NOT_FOUND",
                "参数版本不存在。",
                status_code=404,
            ) from exc
        if session.board != parameter_set.boardId.value:
            raise DeviceServiceError(
                "PARAMETER_SET_BOARD_MISMATCH",
                "参数版本与设备会话板型不一致。",
                status_code=409,
            )
        payload = _parameter_payload(parameter_set)
        operation_id = _validated_operation_id(operation_id)
        fingerprint = _fingerprint(
            "sync-parameters",
            project_id,
            session_id,
            parameter_set.id,
            hashlib.sha256(payload).hexdigest(),
        )
        if existing := self._existing_idempotent(project_id, operation_id, fingerprint):
            return existing, self._repo.get_session(project_id, existing.sessionId)
        await self._stop_terminal_handle(session_id)
        state = _initial_state(
            DeviceOperationKind.SYNC_PARAMETERS,
            fingerprint,
            metadata={
                "parameterSetId": parameter_set.id,
                "parameterRevision": parameter_set.revision,
                "profileRevision": parameter_set.profileRevision,
                "boardId": parameter_set.boardId.value,
                "targetPath": ".zhangwen/parameters.json",
            },
        )
        operation, created = self._reserve_operation(
            project_id=project_id,
            session_id=session_id,
            operation_id=operation_id,
            kind=DeviceOperationKind.SYNC_PARAMETERS,
            command_label="mpremote staged parameter sync",
            state=state,
            fingerprint=fingerprint,
        )
        session = self._repo.get_session(project_id, operation.sessionId)
        if not created:
            return operation, session
        self._states[operation_id] = state
        cancel = asyncio.Event()
        self._cancellations[operation_id] = cancel
        self._tasks[operation_id] = asyncio.create_task(
            self._execute_parameter_sync(
                project_id,
                session,
                operation_id,
                payload,
                cancel,
            ),
            name=f"device-parameter-sync-{operation_id}",
        )
        return operation, session

    async def inspect_firmware(self, file_name: str, content: bytes) -> FirmwareCandidate:
        safe_name = Path(file_name).name
        if safe_name != file_name or not safe_name.lower().endswith(".bin"):
            raise DeviceServiceError("FIRMWARE_FILE_INVALID", "固件必须是单个 .bin 文件。")
        if not content or len(content) > MAX_FIRMWARE_BYTES:
            raise DeviceServiceError("FIRMWARE_SIZE_INVALID", "固件大小超出允许范围。")
        candidate_id = f"firmware_{uuid.uuid4().hex}"
        directory = self._candidate_directory(candidate_id)
        directory.mkdir(parents=True, exist_ok=False)
        path = directory / "firmware.bin"
        path.write_bytes(content)
        cancel = asyncio.Event()
        try:
            result = await self._transport.inspect_firmware(
                path,
                cancel=cancel,
                timeout_seconds=self._command_timeout,
            )
        except DeviceTransportError as exc:
            raise self._service_error(exc, "FIRMWARE_INSPECTION_FAILED") from exc
        sha256 = hashlib.sha256(content).hexdigest()
        target_chip = _optional_text(result.data.get("targetChip"))
        image_format = _optional_text(result.data.get("imageFormat"))
        default_address = _optional_int(result.data.get("defaultAddress"))
        warnings: list[str] = []
        if content[:1] != b"\xe9":
            warnings.append("固件缺少 ESP 镜像头标记。")
        compatible = (
            result.exit_code == 0
            and content[:1] == b"\xe9"
            and target_chip is not None
            and "ESP32-S3" in target_chip.upper()
        )
        if not compatible:
            warnings.append("固件未通过 ESP32-S3 本地兼容性检查，禁止烧录。")
        elif default_address is None:
            warnings.append("镜像不包含可信写入地址，准备烧录时必须显式填写。")
        candidate = FirmwareCandidate(
            id=candidate_id,
            fileName=safe_name,
            sizeBytes=len(content),
            sha256=sha256,
            targetChip=target_chip,
            imageFormat=image_format,
            defaultAddress=default_address,
            compatible=compatible,
            warnings=warnings,
            expiresAt=(_now_dt() + FIRMWARE_CANDIDATE_TTL).isoformat(),
        )
        self._candidates[candidate.id] = (candidate, path)
        return candidate

    def prepare_firmware(
        self,
        *,
        project_id: str,
        session_id: str,
        candidate_id: str,
        address: int | None,
    ) -> FirmwareFlashPlan:
        self._supported_session(project_id, session_id)
        candidate, _ = self._candidate(candidate_id)
        if not candidate.compatible:
            raise DeviceServiceError(
                "FIRMWARE_INCOMPATIBLE",
                "固件未通过板型兼容性检查。",
            )
        resolved_address = candidate.defaultAddress if address is None else address
        if resolved_address is None or resolved_address < 0 or resolved_address > MAX_FLASH_ADDRESS:
            raise DeviceServiceError("FIRMWARE_ADDRESS_INVALID", "固件写入地址无效。")
        if resolved_address % 0x1000 != 0:
            raise DeviceServiceError("FIRMWARE_ADDRESS_INVALID", "固件写入地址必须按 0x1000 对齐。")
        if resolved_address + candidate.sizeBytes > MAX_FLASH_ADDRESS + 1:
            raise DeviceServiceError("FIRMWARE_REGION_INVALID", "固件区域超出 K10 Flash 边界。")
        token = secrets.token_urlsafe(32)
        expires = _now_dt() + FIRMWARE_CONFIRMATION_TTL
        self._confirmations[token] = (candidate_id, session_id, resolved_address, expires)
        return FirmwareFlashPlan(
            candidate=candidate,
            sessionId=session_id,
            address=resolved_address,
            confirmationToken=token,
            expiresAt=expires.isoformat(),
            summary=(
                f"将校验并写入 {candidate.fileName}，SHA-256 {candidate.sha256[:12]}…；"
                "不执行 Flash 擦除。"
            ),
        )

    async def start_firmware_flash(
        self,
        *,
        project_id: str,
        session_id: str,
        candidate_id: str | None,
        confirmation_token: str | None,
        operation_id: str | None,
        address: int | None,
        confirm_flash: bool,
        confirmation_phrase: str | None = None,
    ) -> tuple[DeviceOperation, DeviceSession]:
        self._serial_session(project_id, session_id)
        validated_id = _validated_operation_id(operation_id)
        if candidate_id:
            candidate, path = self._candidate(candidate_id)
            idempotent_address = candidate.defaultAddress if address is None else address
            if idempotent_address is not None:
                fingerprint = _fingerprint(
                    "flash",
                    project_id,
                    session_id,
                    candidate.sha256,
                    str(idempotent_address),
                )
                if existing := self._existing_idempotent(project_id, validated_id, fingerprint):
                    return existing, self._repo.get_session(project_id, existing.sessionId)
        if not confirm_flash or not candidate_id or not confirmation_token:
            raise DeviceServiceError(
                "DEVICE_FLASH_CONFIRMATION_REQUIRED",
                "固件烧录需要独立确认令牌和明确确认。",
            )
        if confirmation_phrase != FIRMWARE_CONFIRMATION_PHRASE:
            raise DeviceServiceError(
                "DEVICE_FLASH_CONFIRMATION_PHRASE_REQUIRED",
                f"请输入确认短语“{FIRMWARE_CONFIRMATION_PHRASE}”。",
            )
        confirmation = self._confirmations.get(confirmation_token)
        if confirmation is None:
            raise DeviceServiceError("FIRMWARE_CONFIRMATION_INVALID", "固件确认已失效。", status_code=409)
        confirmed_candidate, confirmed_session, confirmed_address, expires = confirmation
        resolved_address = confirmed_address if address is None else address
        if (
            expires <= _now_dt()
            or confirmed_candidate != candidate_id
            or confirmed_session != session_id
            or confirmed_address != resolved_address
        ):
            raise DeviceServiceError("FIRMWARE_CONFIRMATION_INVALID", "固件确认与当前计划不匹配。", status_code=409)
        candidate, path = self._candidate(candidate_id)
        operation_id = validated_id
        fingerprint = _fingerprint(
            "flash",
            project_id,
            session_id,
            candidate.sha256,
            str(resolved_address),
        )
        if existing := self._existing_idempotent(project_id, operation_id, fingerprint):
            return existing, self._repo.get_session(project_id, existing.sessionId)
        await self._stop_terminal_handle(session_id)
        state = _initial_state(
            DeviceOperationKind.FLASH_FIRMWARE,
            fingerprint,
            metadata={
                "candidateId": candidate.id,
                "firmwareSha256": candidate.sha256,
                "address": resolved_address,
            },
        )
        operation, created = self._reserve_operation(
            project_id=project_id,
            session_id=session_id,
            operation_id=operation_id,
            kind=DeviceOperationKind.FLASH_FIRMWARE,
            command_label="esptool write-flash",
            state=state,
            fingerprint=fingerprint,
        )
        session = self._repo.get_session(project_id, operation.sessionId)
        if not created:
            return operation, session
        self._confirmations.pop(confirmation_token, None)
        self._states[operation_id] = state
        cancel = asyncio.Event()
        self._cancellations[operation_id] = cancel
        self._tasks[operation_id] = asyncio.create_task(
            self._execute_firmware(
                project_id,
                session,
                operation_id,
                candidate,
                path,
                resolved_address,
                cancel,
            ),
            name=f"device-flash-{operation_id}",
        )
        return operation, session

    def get_operation(self, project_id: str, operation_id: str) -> tuple[DeviceOperation, DeviceSession]:
        operation = self._repo.get_operation(project_id, operation_id)
        operation = self._persist_corrected_upload_outcome(project_id, operation)
        operation = self._reconcile_orphaned_operation(project_id, operation)
        return operation, self._repo.get_session(project_id, operation.sessionId)

    def get_latest_operation(
        self,
        project_id: str,
    ) -> tuple[DeviceOperation, DeviceSession] | None:
        operation = self._repo.get_latest_operation(project_id)
        if operation is None:
            return None
        operation = self._persist_corrected_upload_outcome(project_id, operation)
        operation = self._reconcile_orphaned_operation(project_id, operation)
        return operation, self._repo.get_session(project_id, operation.sessionId)

    async def wait(self, operation_id: str) -> None:
        task = self._tasks.get(operation_id)
        if task is not None:
            await asyncio.shield(task)

    async def cancel_operation(
        self,
        project_id: str,
        operation_id: str,
    ) -> tuple[DeviceOperation, DeviceSession]:
        operation = self._repo.get_operation(project_id, operation_id)
        if operation.status not in {DeviceOperationStatus.QUEUED, DeviceOperationStatus.RUNNING}:
            return operation, self._repo.get_session(project_id, operation.sessionId)
        cancel = self._cancellations.get(operation_id)
        if cancel is None:
            if (
                operation.metadata.get("channel")
                == DeviceDeploymentChannel.ESP_CLAW.value
            ):
                operation = self._fail_orphaned_espclaw_operation(
                    project_id,
                    operation,
                    reason="Cancellation was requested after the local ESP-Claw execution context was lost.",
                )
                return operation, self._repo.get_session(
                    project_id,
                    operation.sessionId,
                )
            state = self._state(operation_id, operation)
            self._finish_state(
                state,
                status=DeviceOperationStatus.CANCELED,
                error_code="DEVICE_OPERATION_CANCELED",
                message="设备操作已取消。",
            )
            operation = self._persist(project_id, operation_id, state, DeviceOperationStatus.CANCELED)
            session = self._repo.set_session_status(
                project_id,
                operation.sessionId,
                DeviceSessionStatus.ERROR,
            )
            return operation, session
        cancel.set()
        task = self._tasks.get(operation_id)
        if task is not None:
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=3.0)
            except TimeoutError:
                if operation.metadata.get("channel") == DeviceDeploymentChannel.ESP_CLAW.value:
                    # ESP-Claw cancellation may be inside bounded emergency-stop
                    # and rollback cleanup.  A second Task.cancel() could abort
                    # that safety work, so report the still-running state and
                    # let the cleanup task reach its explicit outcome.
                    return self.get_operation(project_id, operation_id)
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        return self.get_operation(project_id, operation_id)

    async def _execute_espclaw_deployment(
        self,
        project_id: str,
        session: DeviceSession,
        endpoint: EspClawEndpoint,
        operation_id: str,
        version_path: str,
        files: dict[str, bytes],
        entrypoint: str,
        job_name: str,
        cancel: asyncio.Event,
    ) -> None:
        state = self._states[operation_id]
        try:
            await asyncio.wait_for(
                self._espclaw_deployment_flow(
                    project_id,
                    endpoint,
                    operation_id,
                    version_path,
                    files,
                    entrypoint,
                    job_name,
                    cancel,
                    state,
                ),
                timeout=self._upload_timeout,
            )
        except TimeoutError:
            cancel.set()
            self._exception_step(state, TimeoutError())
            self._finish_state(
                state,
                status=DeviceOperationStatus.TIMED_OUT,
                error_code="ESP_CLAW_DEPLOYMENT_TIMEOUT",
                message=_espclaw_failure_message(
                    state,
                    "ESP-Claw code deployment timed out.",
                ),
            )
            self._persist(project_id, operation_id, state, DeviceOperationStatus.TIMED_OUT)
        except (EspClawAdapterCanceled, asyncio.CancelledError) as exc:
            self._exception_step(state, exc)
            self._finish_state(
                state,
                status=DeviceOperationStatus.CANCELED,
                error_code="DEVICE_OPERATION_CANCELED",
                message=_espclaw_failure_message(
                    state,
                    "ESP-Claw code deployment was canceled.",
                ),
            )
            self._persist(project_id, operation_id, state, DeviceOperationStatus.CANCELED)
        except _FlowFailure as exc:
            self._exception_step(state, exc)
            self._finish_state(
                state,
                status=DeviceOperationStatus.FAILED,
                error_code=exc.code,
                message=_espclaw_failure_message(
                    state,
                    "ESP-Claw code deployment failed verification.",
                ),
            )
            self._persist(project_id, operation_id, state, DeviceOperationStatus.FAILED)
        except EspClawAdapterError as exc:
            self._exception_step(state, exc)
            self._finish_state(
                state,
                status=DeviceOperationStatus.FAILED,
                error_code=exc.code,
                message=_espclaw_failure_message(
                    state,
                    "ESP-Claw rejected the controlled code deployment.",
                ),
            )
            self._persist(project_id, operation_id, state, DeviceOperationStatus.FAILED)
        except Exception as exc:
            self._exception_step(state, exc)
            self._finish_state(
                state,
                status=DeviceOperationStatus.FAILED,
                error_code="ESP_CLAW_DEPLOYMENT_INTERNAL_ERROR",
                message=_espclaw_failure_message(
                    state,
                    "ESP-Claw deployment encountered an unexpected local execution error.",
                ),
            )
            self._persist(project_id, operation_id, state, DeviceOperationStatus.FAILED)
        finally:
            metadata = state.get("metadata")
            unsafe = isinstance(metadata, dict) and (
                metadata.get("runtimeStopOk") is False
                or metadata.get("rollbackOk") is False
            )
            self._repo.set_session_status(
                project_id,
                session.id,
                DeviceSessionStatus.ERROR if unsafe else DeviceSessionStatus.READY,
            )
            self._tasks.pop(operation_id, None)
            self._cancellations.pop(operation_id, None)
            self._states.pop(operation_id, None)

    async def _espclaw_deployment_flow(
        self,
        project_id: str,
        endpoint: EspClawEndpoint,
        operation_id: str,
        version_path: str,
        files: dict[str, bytes],
        entrypoint: str,
        job_name: str,
        cancel: asyncio.Event,
        state: dict[str, object],
    ) -> None:
        self._running(project_id, operation_id, state, DeviceOperationPhase.PREFLIGHT, 8)
        handshake = await self._espclaw.handshake(
            endpoint.webEndpoint,
            endpoint.mcpEndpoint,
            cancel=cancel,
            timeout_seconds=self._command_timeout,
        )
        if handshake.storage_base_path != ESP_CLAW_STORAGE_BASE_PATH:
            raise EspClawAdapterError(
                "ESP_CLAW_STORAGE_PATH_MISMATCH",
                "ESP-Claw storage base changed after pairing.",
            )
        if not handshake.file_readback_capable:
            raise EspClawAdapterError(
                "ESP_CLAW_FILE_READBACK_UNAVAILABLE",
                "ESP-Claw Web File API readback probe failed before deployment.",
            )
        if not handshake.reported_board_id:
            raise EspClawAdapterError(
                "ESP_CLAW_BOARD_IDENTITY_REQUIRED",
                "ESP-Claw board identity handshake disappeared after pairing.",
            )
        try:
            reported = normalize_board_id(handshake.reported_board_id)
        except ValueError as exc:
            raise EspClawAdapterError(
                "ESP_CLAW_BOARD_UNSUPPORTED",
                "ESP-Claw reported an unsupported board.",
            ) from exc
        if reported != endpoint.boardId:
            raise EspClawAdapterError(
                "ESP_CLAW_BOARD_MISMATCH",
                "ESP-Claw board identity changed after pairing.",
            )
        self._step(
            state,
            DeviceOperationPhase.PREFLIGHT,
            TransportResult(0, "ESP-Claw status and MCP Lua tools verified"),
            "Revalidated paired ESP-Claw endpoint and Lua capabilities",
        )

        self._running(project_id, operation_id, state, DeviceOperationPhase.BACKUP, 20)
        backups: dict[str, bytes | None] = {}
        for path in sorted(files):
            backups[path] = await self._espclaw.read_file(
                endpoint.webEndpoint,
                path,
                cancel=cancel,
                timeout_seconds=self._command_timeout,
            )
        state["backup"] = self._write_espclaw_backups(
            operation_id,
            backups,
        ).model_dump(mode="json")
        self._step(
            state,
            DeviceOperationPhase.BACKUP,
            TransportResult(0, "existing remote files captured"),
            "Backed up same-path ESP-Claw files before writing",
        )

        wrote_any = False
        runtime_start_attempted = False
        try:
            self._running(project_id, operation_id, state, DeviceOperationPhase.TRANSFER, 38)
            for directory in _espclaw_directories(version_path, files):
                await self._espclaw.make_directory(
                    endpoint.webEndpoint,
                    directory,
                    cancel=cancel,
                    timeout_seconds=self._command_timeout,
                )
            for path in sorted(files):
                # Treat a started request as a potential write: the remote may
                # commit before the local HTTP request observes cancellation.
                wrote_any = True
                await self._espclaw.upload_file(
                    endpoint.webEndpoint,
                    path,
                    files[path],
                    cancel=cancel,
                    timeout_seconds=self._command_timeout,
                )
            self._step(
                state,
                DeviceOperationPhase.TRANSFER,
                TransportResult(0, "versioned Lua files uploaded"),
                "Uploaded accepted Lua CodeRun through ESP-Claw Web Console",
            )

            self._running(project_id, operation_id, state, DeviceOperationPhase.VERIFY_FILES, 62)
            hashes: dict[str, str] = {}
            for path in sorted(files):
                readback = await self._espclaw.read_file(
                    endpoint.webEndpoint,
                    path,
                    cancel=cancel,
                    timeout_seconds=self._command_timeout,
                )
                expected = hashlib.sha256(files[path]).hexdigest()
                actual = hashlib.sha256(readback or b"").hexdigest()
                hashes[path] = actual
                if readback is None or actual != expected:
                    raise _FlowFailure(
                        "ESP_CLAW_HASH_MISMATCH",
                        DeviceOperationPhase.VERIFY_FILES,
                        TransportResult(3, "ESP-Claw file readback hash mismatch"),
                    )
            self._step(
                state,
                DeviceOperationPhase.VERIFY_FILES,
                TransportResult(0, "all ESP-Claw files matched SHA-256"),
                "Verified every deployed ESP-Claw file by readback SHA-256",
            )

            self._running(project_id, operation_id, state, DeviceOperationPhase.START_RUNTIME, 78)
            # A request may reach the device before a local cancellation or
            # timeout is observed.  From this point, cleanup must stop by the
            # stable managed name even if no job id is returned locally.
            runtime_start_attempted = True
            job_id = await self._espclaw.run_lua_script(
                endpoint.mcpEndpoint,
                entrypoint,
                job_name,
                cancel=cancel,
                timeout_seconds=self._command_timeout,
            )
            metadata = state.setdefault("metadata", {})
            if isinstance(metadata, dict):
                metadata["jobId"] = job_id
            self._step(
                state,
                DeviceOperationPhase.START_RUNTIME,
                TransportResult(0, "lua_run_script_async accepted entrypoint"),
                "Started the versioned Lua entrypoint through MCP",
            )

            self._running(project_id, operation_id, state, DeviceOperationPhase.VERIFY_RUNTIME, 90)
            stable_running_probes = 0
            verified_job_state = ""
            while True:
                if cancel.is_set():
                    raise EspClawAdapterCanceled()
                job = await self._espclaw.get_async_job(
                    endpoint.mcpEndpoint,
                    job_id,
                    cancel=cancel,
                    timeout_seconds=self._command_timeout,
                )
                if job.ok is True:
                    verified_job_state = job.status
                    break
                if job.ok is False:
                    raise _FlowFailure(
                        "ESP_CLAW_RUNTIME_FAILED",
                        DeviceOperationPhase.VERIFY_RUNTIME,
                        TransportResult(4, "ESP-Claw Lua async job failed"),
                    )
                if job.status == "running":
                    stable_running_probes += 1
                    if stable_running_probes >= 2:
                        verified_job_state = "running"
                        break
                else:
                    stable_running_probes = 0
                await asyncio.sleep(self._espclaw_poll_interval)
            if isinstance(metadata, dict):
                metadata["runtimeJobState"] = verified_job_state
                metadata["longRunning"] = verified_job_state == "running"
            self._step(
                state,
                DeviceOperationPhase.VERIFY_RUNTIME,
                TransportResult(0, f"lua_get_async_job state={verified_job_state}"),
                "Verified ESP-Claw Lua job completion or a stable running state",
            )
        except BaseException as original:
            cleanup_timeout = min(
                60.0,
                max(5.0, self._command_timeout * (6 + min(len(backups), 30) * 2)),
            )
            metadata = state.setdefault("metadata", {})
            if isinstance(metadata, dict):
                if runtime_start_attempted:
                    metadata["runtimeStopOk"] = False
                if wrote_any:
                    metadata["rollbackOk"] = False
            cleanup_task = asyncio.create_task(
                self._recover_espclaw_deployment(
                    endpoint,
                    backups if wrote_any else {},
                    runtime_start_attempted=runtime_start_attempted,
                    job_name=job_name,
                    state=state,
                ),
                name=f"espclaw-safety-cleanup-{operation_id}",
            )
            try:
                await asyncio.wait_for(
                    asyncio.shield(cleanup_task),
                    timeout=cleanup_timeout,
                )
            except asyncio.CancelledError:
                # The deployment's main timeout may fire while an earlier user
                # cancellation is already performing safety cleanup.  Do not
                # let that second cancellation interrupt emergency stop or
                # rollback; wait only for the same bounded cleanup task.
                try:
                    await asyncio.wait_for(
                        asyncio.shield(cleanup_task),
                        timeout=cleanup_timeout,
                    )
                except TimeoutError:
                    self._mark_espclaw_cleanup_timeout(
                        state,
                        runtime_start_attempted=runtime_start_attempted,
                        wrote_any=wrote_any,
                    )
                    cleanup_task.cancel()
                    try:
                        await cleanup_task
                    except asyncio.CancelledError:
                        pass
            except TimeoutError:
                self._mark_espclaw_cleanup_timeout(
                    state,
                    runtime_start_attempted=runtime_start_attempted,
                    wrote_any=wrote_any,
                )
                cleanup_task.cancel()
                try:
                    await cleanup_task
                except asyncio.CancelledError:
                    pass
            self._record_espclaw_recovery_verification(state)
            metadata = state.get("metadata")
            if isinstance(metadata, dict) and metadata.get("runtimeStopOk") is False:
                raise EspClawAdapterError(
                    "ESP_CLAW_EMERGENCY_STOP_UNCONFIRMED",
                    "ESP-Claw Lua emergency stop could not be confirmed; manual actuator stop and inspection are required.",
                ) from original
            raise

        state["verification"] = DeviceVerification(
            fileHashes=hashes,
            runtimeExitCode=0,
            ok=True,
            summary="ESP-Claw Lua files were read back byte-for-byte and the asynchronous entrypoint completed or remained stably running.",
            deploymentOk=True,
            runtimeStartedOk=True,
            managementChannelOk=True,
            warnings=[
                "Deployment used the trusted-LAN Web Console and MCP only; no firmware, Flash, or esptool operation ran."
            ],
        ).model_dump(mode="json")
        self._finish_state(
            state,
            status=DeviceOperationStatus.COMPLETED,
            error_code=None,
            message="ESP-Claw Lua CodeRun deployed, read back, and started successfully.",
        )
        self._persist(project_id, operation_id, state, DeviceOperationStatus.COMPLETED)
        self._repo.touch_espclaw_endpoint(project_id, endpoint.id)

    async def _restore_espclaw_files(
        self,
        endpoint: str,
        backups: dict[str, bytes | None],
        state: dict[str, object],
    ) -> bool:
        cleanup_cancel = asyncio.Event()
        all_ok = True
        for path in sorted(backups, reverse=True):
            restored = False
            for _attempt in range(2):
                try:
                    expected = backups[path]
                    if expected is None:
                        await self._espclaw.delete_file(
                            endpoint,
                            path,
                            cancel=cleanup_cancel,
                            timeout_seconds=self._command_timeout,
                        )
                    else:
                        await self._espclaw.upload_file(
                            endpoint,
                            path,
                            expected,
                            cancel=cleanup_cancel,
                            timeout_seconds=self._command_timeout,
                        )
                    readback = await self._espclaw.read_file(
                        endpoint,
                        path,
                        cancel=cleanup_cancel,
                        timeout_seconds=self._command_timeout,
                    )
                    restored = (
                        readback is None
                        if expected is None
                        else readback == expected
                    )
                    if restored:
                        break
                except (EspClawAdapterError, TimeoutError):
                    continue
            all_ok = all_ok and restored
        self._step(
            state,
            DeviceOperationPhase.RESTORE,
            TransportResult(
                0 if all_ok else 5,
                (
                    "ESP-Claw rollback readback verified"
                    if all_ok
                    else "ESP-Claw rollback readback mismatch"
                ),
            ),
            (
                "Restored previous ESP-Claw files or removed new files and verified the result by readback"
                if all_ok
                else "ESP-Claw file rollback could not be confirmed; manual inspection is required"
            ),
        )
        return all_ok

    async def _recover_espclaw_deployment(
        self,
        endpoint: EspClawEndpoint,
        backups: dict[str, bytes | None],
        *,
        runtime_start_attempted: bool,
        job_name: str,
        state: dict[str, object],
    ) -> None:
        metadata = state.setdefault("metadata", {})
        if runtime_start_attempted:
            if isinstance(metadata, dict):
                # Fail closed if cleanup itself is interrupted before evidence
                # of a terminal job state is obtained.
                metadata["runtimeStopOk"] = False
            runtime_stop_ok = await self._stop_espclaw_job(
                endpoint.mcpEndpoint,
                job_name,
                state,
            )
            if isinstance(metadata, dict):
                metadata["runtimeStopOk"] = runtime_stop_ok
        if backups:
            if isinstance(metadata, dict):
                metadata["rollbackOk"] = False
            rollback_ok = await self._restore_espclaw_files(
                endpoint.webEndpoint,
                backups,
                state,
            )
            if isinstance(metadata, dict):
                metadata["rollbackOk"] = rollback_ok

    async def _stop_espclaw_job(
        self,
        endpoint: str,
        job_name: str,
        state: dict[str, object],
    ) -> bool:
        cleanup_cancel = asyncio.Event()
        last_status = ""
        try:
            await self._espclaw.stop_async_job(
                endpoint,
                job_name,
                cancel=cleanup_cancel,
                timeout_seconds=self._command_timeout,
            )
            for _attempt in range(3):
                job = await self._espclaw.get_async_job_by_name(
                    endpoint,
                    job_name,
                    cancel=cleanup_cancel,
                    timeout_seconds=self._command_timeout,
                )
                last_status = job.status.strip().casefold()
                if last_status in _ESPCLAW_TERMINAL_JOB_STATES:
                    self._step(
                        state,
                        DeviceOperationPhase.RESTORE,
                        TransportResult(0, f"lua_stop_async_job state={last_status}"),
                        "Stopped the managed ESP-Claw Lua job before file rollback",
                    )
                    return True
                await asyncio.sleep(self._espclaw_poll_interval)
        except (EspClawAdapterError, TimeoutError):
            pass
        self._step(
            state,
            DeviceOperationPhase.RESTORE,
            TransportResult(
                6,
                "lua_stop_async_job was not confirmed"
                + (f"; last state={last_status}" if last_status else ""),
            ),
            "ESP-Claw emergency stop was not confirmed"
            + (f" (last state={last_status})" if last_status else "")
            + "; manual actuator stop is required",
        )
        return False

    @staticmethod
    def _record_espclaw_recovery_verification(state: dict[str, object]) -> None:
        metadata = state.get("metadata")
        if not isinstance(metadata, dict):
            return
        warnings: list[str] = []
        if metadata.get("runtimeStopOk") is False:
            warnings.append(
                "ESP-Claw Lua emergency stop was not confirmed. Do not retry; manually stop actuators and inspect the device."
            )
        if metadata.get("rollbackOk") is False:
            warnings.append(
                "ESP-Claw file rollback was not confirmed. Do not retry until the remote files are inspected manually."
            )
        if metadata.get("cleanupTimedOut") is True:
            warnings.append("ESP-Claw bounded safety cleanup timed out.")
        if not warnings:
            return
        state["verification"] = DeviceVerification(
            ok=False,
            summary="ESP-Claw deployment recovery requires manual inspection.",
            deploymentOk=False,
            runtimeStartedOk=False,
            managementChannelOk=metadata.get("runtimeStopOk") is not False,
            warnings=warnings,
        ).model_dump(mode="json")

    @staticmethod
    def _mark_espclaw_cleanup_timeout(
        state: dict[str, object],
        *,
        runtime_start_attempted: bool,
        wrote_any: bool,
    ) -> None:
        metadata = state.setdefault("metadata", {})
        if not isinstance(metadata, dict):
            return
        if runtime_start_attempted:
            metadata["runtimeStopOk"] = False
        if wrote_any:
            metadata["rollbackOk"] = False
        metadata["cleanupTimedOut"] = True

    async def _execute_upload(
        self,
        project_id: str,
        session: DeviceSession,
        operation_id: str,
        files: dict[str, bytes],
        cancel: asyncio.Event,
    ) -> None:
        state = self._states[operation_id]
        lock = self._port_locks.setdefault(session.portId, asyncio.Lock())
        if lock.locked():
            self._finish_state(
                state,
                status=DeviceOperationStatus.BLOCKED,
                error_code="DEVICE_PORT_BUSY",
                message="设备端口正在执行其他操作。",
            )
            self._persist(project_id, operation_id, state, DeviceOperationStatus.BLOCKED)
            self._repo.set_session_status(project_id, session.id, DeviceSessionStatus.READY)
            return
        async with lock:
            try:
                await asyncio.wait_for(
                    self._upload_flow(project_id, session, operation_id, files, cancel, state),
                    timeout=self._upload_timeout,
                )
            except TimeoutError:
                cancel.set()
                self._exception_step(state, TimeoutError())
                _record_original_failure(state, "DEVICE_UPLOAD_TIMEOUT")
                self._finish_state(
                    state,
                    status=DeviceOperationStatus.TIMED_OUT,
                    error_code="DEVICE_UPLOAD_TIMEOUT",
                    message="MicroPython 上传超时。",
                )
                self._persist(project_id, operation_id, state, DeviceOperationStatus.TIMED_OUT)
                self._repo.set_session_status(project_id, session.id, DeviceSessionStatus.ERROR)
            except (DeviceTransportCanceled, asyncio.CancelledError) as exc:
                self._exception_step(state, exc)
                _record_original_failure(state, "DEVICE_OPERATION_CANCELED")
                self._finish_state(
                    state,
                    status=DeviceOperationStatus.CANCELED,
                    error_code="DEVICE_OPERATION_CANCELED",
                    message="MicroPython 上传已取消。",
                )
                self._persist(project_id, operation_id, state, DeviceOperationStatus.CANCELED)
                self._repo.set_session_status(
                    project_id,
                    session.id,
                    _session_status_after_cancellation(state),
                )
            except _FlowFailure as exc:
                self._exception_step(state, exc)
                _record_original_failure(state, exc.code)
                self._finish_state(
                    state,
                    status=DeviceOperationStatus.FAILED,
                    error_code=exc.code,
                    message="MicroPython 上传未通过本地执行检查。",
                )
                self._persist(project_id, operation_id, state, DeviceOperationStatus.FAILED)
                safe_status = (
                    DeviceSessionStatus.RUNTIME_BUSY
                    if exc.phase == DeviceOperationPhase.INTERRUPT_RUNTIME
                    else DeviceSessionStatus.ATTACHED_UNVERIFIED
                    if exc.phase == DeviceOperationPhase.PREFLIGHT
                    else DeviceSessionStatus.ERROR
                )
                self._repo.set_session_status(project_id, session.id, safe_status)
            except DeviceTransportError as exc:
                self._exception_step(state, exc)
                _record_original_failure(state, exc.code)
                self._finish_state(
                    state,
                    status=DeviceOperationStatus.FAILED,
                    error_code=exc.code,
                    message="MicroPython 传输失败。",
                )
                self._persist(project_id, operation_id, state, DeviceOperationStatus.FAILED)
                self._repo.set_session_status(project_id, session.id, DeviceSessionStatus.ERROR)
            except Exception as exc:
                self._exception_step(state, exc)
                _record_original_failure(state, "DEVICE_UPLOAD_INTERNAL_ERROR")
                self._finish_state(
                    state,
                    status=DeviceOperationStatus.FAILED,
                    error_code="DEVICE_UPLOAD_INTERNAL_ERROR",
                    message="MicroPython 上传遇到未预期的本地执行错误。",
                )
                self._persist(project_id, operation_id, state, DeviceOperationStatus.FAILED)
                self._repo.set_session_status(project_id, session.id, DeviceSessionStatus.ERROR)
            finally:
                self._tasks.pop(operation_id, None)
                self._cancellations.pop(operation_id, None)
                self._states.pop(operation_id, None)
        completed = self._repo.get_operation(project_id, operation_id)
        if completed.status == DeviceOperationStatus.COMPLETED:
            try:
                await self.start_terminal(project_id, session.id)
            except DeviceServiceError:
                # Deployment stays successful even if observing stdout cannot
                # start. The terminal snapshot exposes the independent error.
                pass

    async def _upload_flow(
        self,
        project_id: str,
        session: DeviceSession,
        operation_id: str,
        files: dict[str, bytes],
        cancel: asyncio.Event,
        state: dict[str, object],
    ) -> None:
        self._repo.set_session_status(
            project_id, session.id, DeviceSessionStatus.RUNTIME_BUSY
        )
        handle = self._transport_sessions.get(session.id)
        if handle is None:
            handle = TransportSession(
                session.id,
                self._transport.resolve_port(session.portId),
            )

        self._running(
            project_id,
            operation_id,
            state,
            DeviceOperationPhase.INTERRUPT_RUNTIME,
            5,
        )
        try:
            interrupted = await self._transport.interrupt_runtime(
                handle,
                cancel=cancel,
                timeout_seconds=self._command_timeout,
            )
        except DeviceTransportCanceled:
            raise
        except DeviceTransportError as exc:
            interrupted = TransportResult(
                exc.exit_code,
                "安全停止设备程序时传输未返回成功结果。",
            )
            self._step(
                state,
                DeviceOperationPhase.INTERRUPT_RUNTIME,
                interrupted,
                "安全停止正在运行的 MicroPython 程序",
            )
            raise _FlowFailure(
                "DEVICE_RUNTIME_INTERRUPT_FAILED",
                DeviceOperationPhase.INTERRUPT_RUNTIME,
                interrupted,
            ) from exc
        self._step(
            state,
            DeviceOperationPhase.INTERRUPT_RUNTIME,
            interrupted,
            "安全停止正在运行的 MicroPython 程序",
        )
        self._require_zero(
            interrupted,
            "DEVICE_RUNTIME_INTERRUPT_FAILED",
            DeviceOperationPhase.INTERRUPT_RUNTIME,
        )
        self._repo.set_session_status(
            project_id, session.id, DeviceSessionStatus.MANAGED
        )

        self._running(project_id, operation_id, state, DeviceOperationPhase.PREFLIGHT, 12)
        identity, probe = await self._transport.probe_identity(
            handle,
            cancel=cancel,
            timeout_seconds=self._command_timeout,
        )
        self._step(state, DeviceOperationPhase.PREFLIGHT, probe, "设备连接检查")
        self._require_zero(probe, "DEVICE_PREFLIGHT_FAILED", DeviceOperationPhase.PREFLIGHT)
        requirement = self._identity_requirements.get(session.id)
        if requirement is not None and not requirement.matches(identity):
            raise _FlowFailure(
                "DEVICE_IDENTITY_MISMATCH",
                DeviceOperationPhase.PREFLIGHT,
                TransportResult(4, "device identity does not match the project target"),
            )
        self._transport_sessions[session.id] = handle
        self._repo.set_session_status(
            project_id, session.id, DeviceSessionStatus.UPLOADING
        )

        self._running(project_id, operation_id, state, DeviceOperationPhase.BACKUP, 25)
        backup_result, backups = await self._transport.backup_files(
            handle,
            list(files),
            cancel=cancel,
            timeout_seconds=self._command_timeout,
        )
        self._step(state, DeviceOperationPhase.BACKUP, backup_result, "备份同名设备文件")
        self._require_zero(backup_result, "DEVICE_BACKUP_FAILED", DeviceOperationPhase.BACKUP)
        backup_summary = self._write_file_backup(operation_id, backups)
        state["backup"] = backup_summary.model_dump(mode="json")
        new_paths = [path for path in files if path not in backups]

        hashes: dict[str, str] = {}
        try:
            self._running(project_id, operation_id, state, DeviceOperationPhase.TRANSFER, 48)
            upload = await self._transport.upload_files(
                handle,
                files,
                cancel=cancel,
                timeout_seconds=self._command_timeout,
            )
            self._step(state, DeviceOperationPhase.TRANSFER, upload, "写入 MicroPython 文件")
            self._require_zero(upload, "DEVICE_UPLOAD_FAILED", DeviceOperationPhase.TRANSFER)

            self._running(project_id, operation_id, state, DeviceOperationPhase.VERIFY_FILES, 72)
            for path, expected in files.items():
                read_result, content = await self._transport.read_file(
                    handle,
                    path,
                    cancel=cancel,
                    timeout_seconds=self._command_timeout,
                )
                self._step(state, DeviceOperationPhase.VERIFY_FILES, read_result, f"回读 {path}")
                self._require_zero(
                    read_result,
                    "DEVICE_READBACK_FAILED",
                    DeviceOperationPhase.VERIFY_FILES,
                )
                if (
                    content is None
                    or hashlib.sha256(content).digest()
                    != hashlib.sha256(expected).digest()
                ):
                    mismatch = TransportResult(1, "readback hash mismatch")
                    self._step(state, DeviceOperationPhase.VERIFY_FILES, mismatch, f"校验 {path}")
                    raise _FlowFailure(
                        "DEVICE_READBACK_MISMATCH",
                        DeviceOperationPhase.VERIFY_FILES,
                        mismatch,
                    )
                hashes[path] = hashlib.sha256(content).hexdigest()

            self._running(
                project_id,
                operation_id,
                state,
                DeviceOperationPhase.START_RUNTIME,
                88,
            )
            started = await self._transport.start_runtime(
                handle,
                cancel=cancel,
                timeout_seconds=self._command_timeout,
            )
            self._step(
                state,
                DeviceOperationPhase.START_RUNTIME,
                started,
                "清理旧 Python 运行态并启动 main.py",
            )
            self._require_zero(
                started,
                "DEVICE_RUNTIME_START_FAILED",
                DeviceOperationPhase.START_RUNTIME,
            )
        except asyncio.CancelledError:
            self._exception_step(state, asyncio.CancelledError())
            _record_original_failure(state, "DEVICE_OPERATION_CANCELED")
            await self._restore_files(handle, backups, new_paths, state)
            raise
        except Exception as exc:
            self._exception_step(state, exc)
            _record_original_failure(state, _upload_error_code(exc))
            await self._restore_files(handle, backups, new_paths, state)
            raise

        # Starting main.py leaves the runtime busy again. Do not probe here;
        # the read-only terminal is the next explicit observer.
        self._transport_sessions.pop(session.id, None)
        metadata = state.setdefault("metadata", {})
        if isinstance(metadata, dict):
            metadata["launchMode"] = "MICROPYTHON_SOFT_RESET"
            metadata["hardwareResetPerformed"] = False
            metadata["postStartProbe"] = "TERMINAL_OBSERVATION_ONLY"

        verification = DeviceVerification(
            fileHashes=hashes,
            reconnectExitCode=None,
            runtimeExitCode=None,
            ok=True,
            summary="运行中程序已安全停止，文件回读一致，main.py 已在新的 Python 运行环境中启动。",
            deploymentOk=True,
            restartOk=None,
            runtimeInterruptedOk=True,
            runtimeStartedOk=True,
            managementChannelOk=None,
            warnings=[
                "本次未触发硬件 RST/EN、断电、Flash 擦除或固件烧录。",
                "已确认文件部署和 Python 启动路径；程序界面或业务效果请在串口终端观察。",
            ],
        )
        state["verification"] = verification.model_dump(mode="json")
        self._finish_state(
            state,
            status=DeviceOperationStatus.COMPLETED,
            error_code=None,
            message="MicroPython 文件已部署，main.py 已启动；未复位硬件。",
        )
        self._persist(project_id, operation_id, state, DeviceOperationStatus.COMPLETED)
        self._repo.set_session_status(
            project_id, session.id, DeviceSessionStatus.RUNTIME_BUSY
        )

    async def _execute_parameter_sync(
        self,
        project_id: str,
        session: DeviceSession,
        operation_id: str,
        payload: bytes,
        cancel: asyncio.Event,
    ) -> None:
        state = self._states[operation_id]
        lock = self._port_locks.setdefault(session.portId, asyncio.Lock())
        if lock.locked():
            self._finish_state(
                state,
                status=DeviceOperationStatus.BLOCKED,
                error_code="DEVICE_PORT_BUSY",
                message="设备端口正在执行其他操作。",
            )
            self._persist(project_id, operation_id, state, DeviceOperationStatus.BLOCKED)
            self._repo.set_session_status(project_id, session.id, DeviceSessionStatus.READY)
            return
        async with lock:
            try:
                await asyncio.wait_for(
                    self._parameter_sync_flow(
                        project_id,
                        session,
                        operation_id,
                        payload,
                        cancel,
                        state,
                    ),
                    timeout=self._upload_timeout,
                )
            except TimeoutError:
                cancel.set()
                self._finish_state(
                    state,
                    status=DeviceOperationStatus.TIMED_OUT,
                    error_code="DEVICE_PARAMETER_SYNC_TIMEOUT",
                    message="参数同步超时；已尝试恢复旧参数。",
                )
                self._persist(project_id, operation_id, state, DeviceOperationStatus.TIMED_OUT)
                self._repo.set_session_status(project_id, session.id, DeviceSessionStatus.ERROR)
            except (DeviceTransportCanceled, asyncio.CancelledError):
                self._finish_state(
                    state,
                    status=DeviceOperationStatus.CANCELED,
                    error_code="DEVICE_OPERATION_CANCELED",
                    message="参数同步已取消；已尝试恢复旧参数。",
                )
                self._persist(project_id, operation_id, state, DeviceOperationStatus.CANCELED)
                self._repo.set_session_status(project_id, session.id, DeviceSessionStatus.ERROR)
            except (_FlowFailure, DeviceTransportError) as exc:
                self._finish_state(
                    state,
                    status=DeviceOperationStatus.FAILED,
                    error_code=exc.code,
                    message="参数同步未通过暂存、提交或回读验证；已尝试恢复旧参数。",
                )
                self._persist(project_id, operation_id, state, DeviceOperationStatus.FAILED)
                self._repo.set_session_status(project_id, session.id, DeviceSessionStatus.ERROR)
            finally:
                self._tasks.pop(operation_id, None)
                self._cancellations.pop(operation_id, None)
                self._states.pop(operation_id, None)

    async def _parameter_sync_flow(
        self,
        project_id: str,
        session: DeviceSession,
        operation_id: str,
        payload: bytes,
        cancel: asyncio.Event,
        state: dict[str, object],
    ) -> None:
        final_path = ".zhangwen/parameters.json"
        staging_path = ".zhangwen/parameters.next.json"
        self._repo.set_session_status(project_id, session.id, DeviceSessionStatus.UPLOADING)
        self._running(project_id, operation_id, state, DeviceOperationPhase.PREFLIGHT, 6)
        handle, connected = await self._ensure_transport_session(session, cancel)
        self._step(state, DeviceOperationPhase.PREFLIGHT, connected, "参数同步前连接检查")
        self._require_zero(connected, "DEVICE_PREFLIGHT_FAILED", DeviceOperationPhase.PREFLIGHT)
        interrupted = await self._transport.interrupt_runtime(
            handle,
            cancel=cancel,
            timeout_seconds=self._command_timeout,
        )
        self._step(state, DeviceOperationPhase.INTERRUPT_RUNTIME, interrupted, "暂停运行时以提交参数")
        self._require_zero(
            interrupted,
            "DEVICE_RUNTIME_INTERRUPT_FAILED",
            DeviceOperationPhase.INTERRUPT_RUNTIME,
        )
        self._running(project_id, operation_id, state, DeviceOperationPhase.BACKUP, 20)
        backup_result, backups = await self._transport.backup_files(
            handle,
            [final_path, staging_path],
            cancel=cancel,
            timeout_seconds=self._command_timeout,
        )
        self._step(state, DeviceOperationPhase.BACKUP, backup_result, "备份旧参数与遗留暂存文件")
        self._require_zero(backup_result, "DEVICE_BACKUP_FAILED", DeviceOperationPhase.BACKUP)
        state["backup"] = self._write_file_backup(operation_id, backups).model_dump(mode="json")
        new_paths = [path for path in (final_path, staging_path) if path not in backups]
        expected_hash = hashlib.sha256(payload).hexdigest()
        try:
            self._running(project_id, operation_id, state, DeviceOperationPhase.TRANSFER, 40)
            staged = await self._transport.upload_files(
                handle,
                {staging_path: payload},
                cancel=cancel,
                timeout_seconds=self._command_timeout,
            )
            self._step(state, DeviceOperationPhase.TRANSFER, staged, "写入参数暂存文件")
            self._require_zero(staged, "DEVICE_PARAMETER_STAGE_FAILED", DeviceOperationPhase.TRANSFER)
            stage_read, staged_payload = await self._transport.read_file(
                handle,
                staging_path,
                cancel=cancel,
                timeout_seconds=self._command_timeout,
            )
            self._step(state, DeviceOperationPhase.VERIFY_FILES, stage_read, "回读参数暂存文件")
            self._require_zero(stage_read, "DEVICE_PARAMETER_STAGE_READBACK_FAILED", DeviceOperationPhase.VERIFY_FILES)
            if staged_payload is None or hashlib.sha256(staged_payload).hexdigest() != expected_hash:
                raise _FlowFailure(
                    "DEVICE_PARAMETER_STAGE_HASH_MISMATCH",
                    DeviceOperationPhase.VERIFY_FILES,
                    TransportResult(3, "staged parameter hash mismatch"),
                )

            self._running(project_id, operation_id, state, DeviceOperationPhase.TRANSFER, 65)
            committed = await self._transport.upload_files(
                handle,
                {final_path: payload},
                cancel=cancel,
                timeout_seconds=self._command_timeout,
            )
            self._step(state, DeviceOperationPhase.TRANSFER, committed, "提交运行时参数文件")
            self._require_zero(committed, "DEVICE_PARAMETER_COMMIT_FAILED", DeviceOperationPhase.TRANSFER)
            final_read, committed_payload = await self._transport.read_file(
                handle,
                final_path,
                cancel=cancel,
                timeout_seconds=self._command_timeout,
            )
            self._step(state, DeviceOperationPhase.VERIFY_FILES, final_read, "回读已提交参数")
            self._require_zero(final_read, "DEVICE_PARAMETER_READBACK_FAILED", DeviceOperationPhase.VERIFY_FILES)
            if committed_payload is None or hashlib.sha256(committed_payload).hexdigest() != expected_hash:
                raise _FlowFailure(
                    "DEVICE_PARAMETER_HASH_MISMATCH",
                    DeviceOperationPhase.VERIFY_FILES,
                    TransportResult(3, "committed parameter hash mismatch"),
                )
            removed = await self._transport.delete_files(
                handle,
                [staging_path],
                cancel=cancel,
                timeout_seconds=self._command_timeout,
            )
            self._step(state, DeviceOperationPhase.PROVISION, removed, "清理参数暂存文件")
            self._require_zero(removed, "DEVICE_PARAMETER_STAGE_CLEANUP_FAILED", DeviceOperationPhase.PROVISION)
            started = await self._transport.start_runtime(
                handle,
                cancel=cancel,
                timeout_seconds=self._command_timeout,
            )
            self._step(state, DeviceOperationPhase.START_RUNTIME, started, "重新启动受控 MicroPython 运行时")
            self._require_zero(started, "DEVICE_RUNTIME_START_FAILED", DeviceOperationPhase.START_RUNTIME)
        except asyncio.CancelledError:
            await self._restore_files(handle, backups, new_paths, state)
            raise
        except Exception:
            await self._restore_files(handle, backups, new_paths, state)
            raise

        state["verification"] = DeviceVerification(
            fileHashes={final_path: expected_hash},
            ok=True,
            deploymentOk=True,
            runtimeStartedOk=True,
            summary="参数已暂存、回读、提交并再次回读验证。",
            warnings=["参数同步不会保存 Wi-Fi 密码或令牌；执行器状态不会在重连后自动恢复。"],
        ).model_dump(mode="json")
        self._finish_state(
            state,
            status=DeviceOperationStatus.COMPLETED,
            error_code=None,
            message="参数版本已同步到设备受控数据区并通过回读校验。",
        )
        self._persist(project_id, operation_id, state, DeviceOperationStatus.COMPLETED)
        self._repo.set_session_status(project_id, session.id, DeviceSessionStatus.RUNTIME_BUSY)

    async def _execute_application_install(
        self,
        project_id: str,
        session: DeviceSession,
        operation_id: str,
        application: FirmwareApplicationRecord,
        images: list[tuple[FirmwareImageSegment, Path]],
        cancel: asyncio.Event,
    ) -> None:
        state = self._states[operation_id]
        lock = self._port_locks.setdefault(session.portId, asyncio.Lock())
        if lock.locked():
            self._finish_state(
                state,
                status=DeviceOperationStatus.BLOCKED,
                error_code="DEVICE_PORT_BUSY",
                message="设备端口正在执行其他操作。",
            )
            self._persist(project_id, operation_id, state, DeviceOperationStatus.BLOCKED)
            self._repo.set_session_status(project_id, session.id, DeviceSessionStatus.READY)
            return
        async with lock:
            try:
                await asyncio.wait_for(
                    self._application_install_flow(
                        project_id,
                        session,
                        operation_id,
                        application,
                        images,
                        cancel,
                        state,
                    ),
                    timeout=self._flash_timeout,
                )
            except TimeoutError:
                cancel.set()
                self._finish_state(
                    state,
                    status=DeviceOperationStatus.TIMED_OUT,
                    error_code="DEVICE_APPLICATION_INSTALL_TIMEOUT",
                    message="应用安装超时；已保留分区备份，需要人工检查设备状态。",
                )
                self._persist(project_id, operation_id, state, DeviceOperationStatus.TIMED_OUT)
                self._repo.set_session_status(project_id, session.id, DeviceSessionStatus.ERROR)
            except (DeviceTransportCanceled, asyncio.CancelledError):
                self._finish_state(
                    state,
                    status=DeviceOperationStatus.CANCELED,
                    error_code="DEVICE_OPERATION_CANCELED",
                    message="应用安装已取消；已尝试恢复所有已备份分区。",
                )
                self._persist(project_id, operation_id, state, DeviceOperationStatus.CANCELED)
                self._repo.set_session_status(project_id, session.id, DeviceSessionStatus.ERROR)
            except (_FlowFailure, DeviceTransportError) as exc:
                self._finish_state(
                    state,
                    status=DeviceOperationStatus.FAILED,
                    error_code=exc.code,
                    message="应用安装未通过写入或回读验证；已尝试恢复备份。",
                )
                self._persist(project_id, operation_id, state, DeviceOperationStatus.FAILED)
                self._repo.set_session_status(project_id, session.id, DeviceSessionStatus.ERROR)
            finally:
                self._tasks.pop(operation_id, None)
                self._cancellations.pop(operation_id, None)
                self._states.pop(operation_id, None)

    async def _application_install_flow(
        self,
        project_id: str,
        session: DeviceSession,
        operation_id: str,
        application: FirmwareApplicationRecord,
        images: list[tuple[FirmwareImageSegment, Path]],
        cancel: asyncio.Event,
        state: dict[str, object],
    ) -> None:
        self._repo.set_session_status(project_id, session.id, DeviceSessionStatus.UPLOADING)
        self._running(project_id, operation_id, state, DeviceOperationPhase.MANIFEST_VALIDATE, 4)
        self._step(
            state,
            DeviceOperationPhase.MANIFEST_VALIDATE,
            TransportResult(0, "stored archive and manifest hashes revalidated"),
            "重新校验应用包、双板身份、分区范围与受保护数据区",
        )
        self._running(project_id, operation_id, state, DeviceOperationPhase.PREFLIGHT, 8)
        handle, connected = await self._ensure_transport_session(session, cancel)
        self._step(state, DeviceOperationPhase.PREFLIGHT, connected, "应用安装前连接检查")
        self._require_zero(connected, "DEVICE_PREFLIGHT_FAILED", DeviceOperationPhase.PREFLIGHT)

        backups: list[tuple[FirmwareImageSegment, bytes]] = []
        try:
            self._running(project_id, operation_id, state, DeviceOperationPhase.BACKUP, 16)
            for segment, _path in images:
                result, content = await self._transport.backup_flash_region(
                    handle,
                    address=segment.address,
                    size=segment.sizeBytes,
                    cancel=cancel,
                    timeout_seconds=self._command_timeout,
                )
                self._step(
                    state,
                    DeviceOperationPhase.BACKUP,
                    result,
                    f"备份 0x{segment.address:x} 分区段",
                )
                self._require_zero(
                    result,
                    "DEVICE_APPLICATION_BACKUP_FAILED",
                    DeviceOperationPhase.BACKUP,
                )
                if content is None or len(content) != segment.sizeBytes:
                    raise _FlowFailure(
                        "DEVICE_APPLICATION_BACKUP_INCOMPLETE",
                        DeviceOperationPhase.BACKUP,
                        TransportResult(3, "flash backup size mismatch"),
                    )
                backups.append((segment, content))
            state["backup"] = self._write_flash_segment_backups(
                operation_id,
                backups,
            ).model_dump(mode="json")

            for index, (segment, path) in enumerate(images, start=1):
                progress = 25 + int((index - 1) / max(len(images), 1) * 45)
                self._running(
                    project_id,
                    operation_id,
                    state,
                    DeviceOperationPhase.WRITE_SEGMENTS,
                    progress,
                )
                written = await self._transport.flash_firmware(
                    handle,
                    path,
                    address=segment.address,
                    cancel=cancel,
                    timeout_seconds=self._command_timeout,
                )
                self._step(
                    state,
                    DeviceOperationPhase.WRITE_SEGMENTS,
                    written,
                    f"写入第 {index}/{len(images)} 段（未执行整片擦除）",
                )
                self._require_zero(
                    written,
                    "DEVICE_APPLICATION_WRITE_FAILED",
                    DeviceOperationPhase.WRITE_SEGMENTS,
                )
                self._running(
                    project_id,
                    operation_id,
                    state,
                    DeviceOperationPhase.VERIFY_SEGMENTS,
                    progress + 12,
                )
                verified = await self._transport.verify_firmware(
                    handle,
                    path,
                    address=segment.address,
                    cancel=cancel,
                    timeout_seconds=self._command_timeout,
                )
                self._step(
                    state,
                    DeviceOperationPhase.VERIFY_SEGMENTS,
                    verified,
                    f"回读验证第 {index}/{len(images)} 段",
                )
                self._require_zero(
                    verified,
                    "DEVICE_APPLICATION_VERIFY_FAILED",
                    DeviceOperationPhase.VERIFY_SEGMENTS,
                )
        except asyncio.CancelledError:
            if backups:
                await self._restore_flash_segments(handle, operation_id, backups, state)
            raise
        except Exception:
            if backups:
                await self._restore_flash_segments(handle, operation_id, backups, state)
            raise

        warnings = ["未执行整片擦除；导入校验已证明写入范围不覆盖 NVS 或用户数据分区。"]
        if application.manifest.debugProtocolVersion is None:
            warnings.append("应用未声明 zwdbg/1；安装完成后只提供串口启动观察，不声称图形化调参握手成功。")
        else:
            warnings.append("zwdbg/1 握手将在设备重新枚举后的显式调试会话中验证。")
        state["verification"] = DeviceVerification(
            ok=True,
            summary="所有应用分区段均完成备份、写入和 esptool 回读验证。",
            warnings=warnings,
        ).model_dump(mode="json")
        self._finish_state(
            state,
            status=DeviceOperationStatus.COMPLETED,
            error_code=None,
            message="应用分区写入与回读验证完成；请重新连接以验证运行时握手。",
        )
        self._persist(project_id, operation_id, state, DeviceOperationStatus.COMPLETED)
        self._repo.set_session_status(project_id, session.id, DeviceSessionStatus.READY)

    async def _restore_flash_segments(
        self,
        handle: TransportSession,
        operation_id: str,
        backups: list[tuple[FirmwareImageSegment, bytes]],
        state: dict[str, object],
    ) -> None:
        restore_cancel = asyncio.Event()
        root = self._backup_directory(operation_id)
        for index, (segment, content) in enumerate(backups):
            path = root / f"restore-{index:02d}-{segment.address:08x}.bin"
            if not path.is_file():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            result = await self._transport.flash_firmware(
                handle,
                path,
                address=segment.address,
                cancel=restore_cancel,
                timeout_seconds=self._command_timeout,
            )
            self._step(state, DeviceOperationPhase.RESTORE, result, f"恢复 0x{segment.address:x} 分区段")
            if result.exit_code != 0:
                return

            verified = await self._transport.verify_firmware(
                handle,
                path,
                address=segment.address,
                cancel=restore_cancel,
                timeout_seconds=self._command_timeout,
            )
            self._step(
                state,
                DeviceOperationPhase.RESTORE,
                verified,
                f"验证恢复 0x{segment.address:x} 分区段",
            )
            if verified.exit_code != 0:
                return

    async def _execute_firmware(
        self,
        project_id: str,
        session: DeviceSession,
        operation_id: str,
        candidate: FirmwareCandidate,
        path: Path,
        address: int,
        cancel: asyncio.Event,
    ) -> None:
        state = self._states[operation_id]
        lock = self._port_locks.setdefault(session.portId, asyncio.Lock())
        if lock.locked():
            self._finish_state(
                state,
                status=DeviceOperationStatus.BLOCKED,
                error_code="DEVICE_PORT_BUSY",
                message="设备端口正在执行其他操作。",
            )
            self._persist(project_id, operation_id, state, DeviceOperationStatus.BLOCKED)
            self._repo.set_session_status(project_id, session.id, DeviceSessionStatus.READY)
            return
        async with lock:
            try:
                await asyncio.wait_for(
                    self._firmware_flow(
                        project_id,
                        session,
                        operation_id,
                        candidate,
                        path,
                        address,
                        cancel,
                        state,
                    ),
                    timeout=self._flash_timeout,
                )
            except TimeoutError:
                cancel.set()
                self._finish_state(
                    state,
                    status=DeviceOperationStatus.TIMED_OUT,
                    error_code="DEVICE_FLASH_TIMEOUT",
                    message="固件烧录超时，设备可能需要手动恢复。",
                )
                self._persist(project_id, operation_id, state, DeviceOperationStatus.TIMED_OUT)
                self._repo.set_session_status(project_id, session.id, DeviceSessionStatus.ERROR)
            except (DeviceTransportCanceled, asyncio.CancelledError):
                self._finish_state(
                    state,
                    status=DeviceOperationStatus.CANCELED,
                    error_code="DEVICE_OPERATION_CANCELED",
                    message="固件烧录已取消，设备可能需要手动恢复。",
                )
                self._persist(project_id, operation_id, state, DeviceOperationStatus.CANCELED)
                self._repo.set_session_status(project_id, session.id, DeviceSessionStatus.ERROR)
            except (_FlowFailure, DeviceTransportError) as exc:
                code = exc.code
                self._finish_state(
                    state,
                    status=DeviceOperationStatus.FAILED,
                    error_code=code,
                    message="固件流程未通过本地执行或验证。",
                )
                self._persist(project_id, operation_id, state, DeviceOperationStatus.FAILED)
                self._repo.set_session_status(project_id, session.id, DeviceSessionStatus.ERROR)
            finally:
                self._tasks.pop(operation_id, None)
                self._cancellations.pop(operation_id, None)
                self._states.pop(operation_id, None)

    async def _firmware_flow(
        self,
        project_id: str,
        session: DeviceSession,
        operation_id: str,
        candidate: FirmwareCandidate,
        path: Path,
        address: int,
        cancel: asyncio.Event,
        state: dict[str, object],
    ) -> None:
        self._repo.set_session_status(project_id, session.id, DeviceSessionStatus.UPLOADING)
        self._running(project_id, operation_id, state, DeviceOperationPhase.PREFLIGHT, 5)
        handle, probe = await self._ensure_transport_session(session, cancel)
        self._step(state, DeviceOperationPhase.PREFLIGHT, probe, "固件烧录前连接检查")
        self._require_zero(probe, "DEVICE_PREFLIGHT_FAILED", DeviceOperationPhase.PREFLIGHT)

        self._running(project_id, operation_id, state, DeviceOperationPhase.BACKUP, 20)
        backup_result, backup = await self._transport.backup_flash_region(
            handle,
            address=address,
            size=candidate.sizeBytes,
            cancel=cancel,
            timeout_seconds=self._command_timeout,
        )
        self._step(state, DeviceOperationPhase.BACKUP, backup_result, "备份将覆盖的 Flash 区域")
        self._require_zero(backup_result, "DEVICE_FLASH_BACKUP_FAILED", DeviceOperationPhase.BACKUP)
        if backup is not None:
            state["backup"] = self._write_flash_backup(operation_id, backup).model_dump(mode="json")

        self._running(project_id, operation_id, state, DeviceOperationPhase.FLASH_WRITE, 55)
        flashed = await self._transport.flash_firmware(
            handle,
            path,
            address=address,
            cancel=cancel,
            timeout_seconds=self._command_timeout,
        )
        self._step(state, DeviceOperationPhase.FLASH_WRITE, flashed, "写入固件（未执行 Flash 擦除）")
        self._require_zero(flashed, "DEVICE_FLASH_FAILED", DeviceOperationPhase.FLASH_WRITE)

        self._running(project_id, operation_id, state, DeviceOperationPhase.VERIFY_RUNTIME, 85)
        verified = await self._transport.verify_firmware(
            handle,
            path,
            address=address,
            cancel=cancel,
            timeout_seconds=self._command_timeout,
        )
        self._step(state, DeviceOperationPhase.VERIFY_RUNTIME, verified, "固件写入后校验")
        self._require_zero(verified, "DEVICE_FLASH_VERIFY_FAILED", DeviceOperationPhase.VERIFY_RUNTIME)
        state["verification"] = DeviceVerification(
            runtimeExitCode=verified.exit_code,
            ok=True,
            summary="固件写入与 verify-flash 均返回退出码 0。",
        ).model_dump(mode="json")
        self._finish_state(
            state,
            status=DeviceOperationStatus.COMPLETED,
            error_code=None,
            message="固件烧录与写入后校验完成；未执行 Flash 擦除。",
        )
        self._persist(project_id, operation_id, state, DeviceOperationStatus.COMPLETED)
        self._repo.set_session_status(project_id, session.id, DeviceSessionStatus.READY)

    async def _ensure_transport_session(
        self,
        session: DeviceSession,
        cancel: asyncio.Event,
    ) -> tuple[TransportSession, TransportResult]:
        handle = self._transport_sessions.get(session.id)
        if handle is not None:
            return handle, TransportResult(0, "existing transport session")
        port = self._transport.resolve_port(session.portId)
        handle, result = await self._transport.connect(
            port,
            cancel=cancel,
            timeout_seconds=self._command_timeout,
        )
        if result.exit_code == 0:
            self._transport_sessions[session.id] = handle
        else:
            await self._release_transport_handle(handle, cancel)
        return handle, result

    async def _restore_files(
        self,
        handle: TransportSession,
        backups: dict[str, bytes],
        new_paths: list[str],
        state: dict[str, object],
    ) -> None:
        restore_cancel = asyncio.Event()
        restore_error_code: str | None = None
        try:
            result = await self._transport.upload_files(
                handle,
                backups,
                cancel=restore_cancel,
                timeout_seconds=self._command_timeout,
            )
            if result.exit_code == 0 and new_paths:
                result = await self._transport.delete_files(
                    handle,
                    new_paths,
                    cancel=restore_cancel,
                    timeout_seconds=self._command_timeout,
                )
            if result.exit_code != 0:
                restore_error_code = "DEVICE_RESTORE_FAILED"
        except DeviceTransportCanceled as exc:
            restore_error_code = "DEVICE_RESTORE_CANCELED"
            result = TransportResult(exc.exit_code, "restore canceled")
        except DeviceTransportTimedOut as exc:
            restore_error_code = "DEVICE_RESTORE_TIMEOUT"
            result = TransportResult(exc.exit_code, "restore timed out")
        except asyncio.CancelledError:
            restore_error_code = "DEVICE_RESTORE_CANCELED"
            result = TransportResult(None, "restore canceled")
        except TimeoutError:
            restore_error_code = "DEVICE_RESTORE_TIMEOUT"
            result = TransportResult(None, "restore timed out")
        except DeviceTransportError as exc:
            restore_error_code = exc.code or "DEVICE_RESTORE_FAILED"
            result = TransportResult(exc.exit_code, "restore transport error")
        except Exception:
            restore_error_code = "DEVICE_RESTORE_FAILED"
            result = TransportResult(None, "restore internal error")
        self._step(state, DeviceOperationPhase.RESTORE, result, "失败后恢复设备文件")
        _record_restore_failure(
            state,
            error_code=restore_error_code,
            exit_code=result.exit_code,
        )

    async def _reconnect_after_restart(
        self,
        previous_handle: TransportSession,
        cancel: asyncio.Event,
        state: dict[str, object],
    ) -> tuple[TransportSession | None, TransportResult]:
        last_handle: TransportSession | None = None
        last_result = TransportResult(None, "management reconnect not attempted")
        for attempt in range(1, 3):
            retry_nonzero = False
            try:
                last_handle, last_result = await asyncio.wait_for(
                    self._transport.connect(
                        previous_handle.port,
                        cancel=cancel,
                        timeout_seconds=self._command_timeout,
                    ),
                    timeout=self._command_timeout,
                )
                retry_nonzero = last_result.exit_code not in {None, 0}
            except DeviceTransportCanceled as exc:
                last_handle = None
                last_result = TransportResult(exc.exit_code, "management reconnect canceled")
            except DeviceTransportTimedOut as exc:
                last_handle = None
                last_result = TransportResult(exc.exit_code, "management reconnect timed out")
            except asyncio.CancelledError:
                last_handle = None
                last_result = TransportResult(None, "management reconnect canceled")
            except TimeoutError:
                last_handle = None
                last_result = TransportResult(None, "management reconnect timed out")
            except DeviceTransportError as exc:
                last_handle = None
                last_result = TransportResult(exc.exit_code, "management reconnect failed")
                retry_nonzero = exc.exit_code not in {None, 0}
            except Exception:
                last_handle = None
                last_result = TransportResult(None, "management reconnect internal error")

            self._step(
                state,
                DeviceOperationPhase.RECONNECT,
                last_result,
                f"重启后恢复管理通道（第 {attempt} 次）",
            )
            if last_result.exit_code == 0 or not retry_nonzero or attempt == 2:
                break
        return last_handle, last_result

    def _physical_serial_session(
        self,
        project_id: str,
        session_id: str,
    ) -> DeviceSession:
        try:
            session = self._repo.get_serial_session(project_id, session_id)
        except DeviceDeploymentSessionMismatch as exc:
            raise DeviceServiceError(
                "DEVICE_USB_SERIAL_SESSION_REQUIRED",
                "ESP-Claw endpoint sessions cannot be used by USB serial, terminal, Flash, application-install, or parameter-sync operations.",
                status_code=409,
            ) from exc
        except ValueError as exc:
            raise DeviceServiceError("DEVICE_SESSION_NOT_FOUND", "设备会话不存在。", status_code=404) from exc
        return session

    def _serial_session(self, project_id: str, session_id: str) -> DeviceSession:
        session = self._physical_serial_session(project_id, session_id)
        self._assert_supported_board(project_id, session_id, session=session)
        return session

    def _ready_session(self, project_id: str, session_id: str) -> DeviceSession:
        session = self._serial_session(project_id, session_id)
        if session.status not in {
            DeviceSessionStatus.READY,
            DeviceSessionStatus.ATTACHED_UNVERIFIED,
            DeviceSessionStatus.RUNTIME_BUSY,
            DeviceSessionStatus.MANAGED,
        }:
            raise DeviceServiceError("DEVICE_SESSION_NOT_READY", "设备会话未就绪。", status_code=409)
        return session

    def _supported_session(self, project_id: str, session_id: str) -> DeviceSession:
        return self._ready_session(project_id, session_id)

    def _assert_supported_board(
        self,
        project_id: str,
        session_id: str,
        *,
        session: DeviceSession | None = None,
    ) -> None:
        if session is None:
            try:
                session = self._repo.get_session(project_id, session_id)
            except ValueError as exc:
                raise DeviceServiceError(
                    "DEVICE_SESSION_NOT_FOUND",
                    "设备会话不存在。",
                    status_code=404,
                ) from exc
        try:
            board_id = SupportedDeviceBoardId(session.board)
        except ValueError as exc:
            raise DeviceServiceError(
                "DEVICE_BOARD_NOT_SUPPORTED",
                "旧项目板型不受支持；请显式迁移为 K10 或 XIAO ESP32S3 Sense。",
                status_code=409,
            ) from exc
        self.require_project_board(project_id, board_id)

    def _candidate(self, candidate_id: str) -> tuple[FirmwareCandidate, Path]:
        value = self._candidates.get(candidate_id)
        if value is None:
            raise DeviceServiceError("FIRMWARE_CANDIDATE_NOT_FOUND", "固件候选不存在或已过期。", status_code=404)
        candidate, path = value
        if datetime.fromisoformat(candidate.expiresAt) <= _now_dt() or not path.is_file():
            self._candidates.pop(candidate_id, None)
            raise DeviceServiceError("FIRMWARE_CANDIDATE_EXPIRED", "固件候选已过期。", status_code=409)
        return candidate, path

    def _candidate_directory(self, candidate_id: str) -> Path:
        return self._data_dir / "device-firmware-candidates" / candidate_id

    def _write_file_backup(self, operation_id: str, files: dict[str, bytes]) -> DeviceBackupSummary:
        root = self._backup_directory(operation_id)
        root.mkdir(parents=True, exist_ok=False)
        manifest: dict[str, dict[str, object]] = {}
        for path, content in files.items():
            name = hashlib.sha256(path.encode("utf-8")).hexdigest() + ".bak"
            (root / name).write_bytes(content)
            manifest[path] = {
                "file": name,
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        (root / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        return DeviceBackupSummary(
            backupId=operation_id,
            fileCount=len(files),
            paths=sorted(files),
            createdAt=_now(),
        )

    def _write_espclaw_backups(
        self,
        operation_id: str,
        files: dict[str, bytes | None],
    ) -> DeviceBackupSummary:
        root = self._backup_directory(operation_id)
        root.mkdir(parents=True, exist_ok=False)
        manifest: dict[str, dict[str, object]] = {}
        for path, content in files.items():
            if content is None:
                manifest[path] = {"existed": False}
                continue
            name = hashlib.sha256(path.encode("utf-8")).hexdigest() + ".espclaw.bak"
            (root / name).write_bytes(content)
            manifest[path] = {
                "existed": True,
                "file": name,
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        (root / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        return DeviceBackupSummary(
            backupId=operation_id,
            fileCount=len(files),
            paths=sorted(files),
            createdAt=_now(),
        )

    def _write_flash_backup(self, operation_id: str, content: bytes) -> DeviceBackupSummary:
        root = self._backup_directory(operation_id)
        root.mkdir(parents=True, exist_ok=False)
        (root / "flash-region.bin").write_bytes(content)
        (root / "manifest.json").write_text(
            json.dumps(
                {
                    "flash-region.bin": {
                        "size": len(content),
                        "sha256": hashlib.sha256(content).hexdigest(),
                    }
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return DeviceBackupSummary(
            backupId=operation_id,
            fileCount=1,
            paths=["flash-region.bin"],
            createdAt=_now(),
        )

    def _write_flash_segment_backups(
        self,
        operation_id: str,
        backups: list[tuple[FirmwareImageSegment, bytes]],
    ) -> DeviceBackupSummary:
        root = self._backup_directory(operation_id)
        root.mkdir(parents=True, exist_ok=False)
        manifest: dict[str, dict[str, object]] = {}
        paths: list[str] = []
        for index, (segment, content) in enumerate(backups):
            name = f"segment-{index:02d}-{segment.address:08x}.bin"
            (root / name).write_bytes(content)
            paths.append(name)
            manifest[name] = {
                "address": segment.address,
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        (root / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        return DeviceBackupSummary(
            backupId=operation_id,
            fileCount=len(paths),
            paths=paths,
            createdAt=_now(),
        )

    def _validated_application(
        self,
        project_id: str,
        application_id: str,
    ) -> tuple[FirmwareApplicationRecord, Path]:
        try:
            application, archive_path = DeviceLabRepository(self._db_path).get_application(
                project_id,
                application_id,
            )
        except KeyError as exc:
            raise DeviceServiceError(
                "FIRMWARE_APPLICATION_NOT_FOUND",
                "应用包不存在。",
                status_code=404,
            ) from exc
        try:
            archive = archive_path.read_bytes()
            checked = validate_application_archive(base64.b64encode(archive).decode("ascii"))
        except (OSError, ApplicationValidationError) as exc:
            raise DeviceServiceError(
                "FIRMWARE_APPLICATION_REVALIDATION_FAILED",
                "应用包存储内容已变化或重新校验失败。",
                status_code=409,
            ) from exc
        if (
            checked.archive_sha256 != application.archiveSha256
            or checked.manifest != application.manifest
        ):
            raise DeviceServiceError(
                "FIRMWARE_APPLICATION_REVALIDATION_FAILED",
                "应用包存储 Hash 或 manifest 与导入记录不一致。",
                status_code=409,
            )
        return application, archive_path

    def _materialize_application_images(
        self,
        operation_id: str,
        application: FirmwareApplicationRecord,
        archive_path: Path,
    ) -> list[tuple[FirmwareImageSegment, Path]]:
        root = self._data_dir / "device-application-candidates" / operation_id
        root.mkdir(parents=True, exist_ok=False)
        images: list[tuple[FirmwareImageSegment, Path]] = []
        with zipfile.ZipFile(archive_path) as package:
            for index, segment in enumerate(application.manifest.deviceImages):
                payload = package.read(segment.path)
                if (
                    len(payload) != segment.sizeBytes
                    or hashlib.sha256(payload).hexdigest() != segment.sha256
                ):
                    raise DeviceServiceError(
                        "FIRMWARE_APPLICATION_REVALIDATION_FAILED",
                        "应用镜像在准备安装时校验失败。",
                        status_code=409,
                    )
                path = root / f"segment-{index:02d}-{segment.address:08x}.bin"
                path.write_bytes(payload)
                images.append((segment, path))
        return images

    def _backup_directory(self, operation_id: str) -> Path:
        return self._data_dir / "device-backups" / operation_id

    def _existing_idempotent(
        self,
        project_id: str,
        operation_id: str,
        fingerprint: str,
    ) -> DeviceOperation | None:
        try:
            operation = self._repo.get_operation(project_id, operation_id)
        except ValueError:
            return None
        if operation.metadata.get("fingerprint") != fingerprint:
            raise DeviceServiceError(
                "DEVICE_IDEMPOTENCY_CONFLICT",
                "该 operationId 已用于不同设备操作。",
                status_code=409,
            )
        return operation

    def _reserve_operation(
        self,
        *,
        project_id: str,
        session_id: str,
        operation_id: str,
        kind: DeviceOperationKind,
        command_label: str,
        state: dict[str, object],
        fingerprint: str,
    ) -> tuple[DeviceOperation, bool]:
        try:
            return self._repo.reserve_operation(
                project_id=project_id,
                session_id=session_id,
                operation_id=operation_id,
                kind=kind,
                command_label=command_label,
                log=_encode_state(state),
                fingerprint=fingerprint,
                claimed_status=DeviceSessionStatus.UPLOADING,
            )
        except DeviceOperationIdempotencyConflict as exc:
            raise DeviceServiceError(
                "DEVICE_IDEMPOTENCY_CONFLICT",
                str(exc),
                status_code=409,
            ) from exc
        except DevicePortLeaseBusy as exc:
            raise DeviceServiceError(
                "DEVICE_PORT_BUSY",
                str(exc),
                status_code=409,
                retryable=True,
            ) from exc
        except DeviceProjectLeaseBusy as exc:
            raise DeviceServiceError(
                "DEVICE_OPERATION_ACTIVE",
                str(exc),
                status_code=409,
                retryable=True,
            ) from exc
        except DeviceDeploymentSessionMismatch as exc:
            raise DeviceServiceError(
                "DEVICE_DEPLOYMENT_SESSION_MISMATCH",
                str(exc),
                status_code=409,
            ) from exc
        except DeviceSessionNotReady as exc:
            raise DeviceServiceError(
                "DEVICE_SESSION_NOT_READY",
                "设备会话正在执行其他操作或尚未恢复就绪。",
                status_code=409,
                retryable=True,
            ) from exc
        except ValueError as exc:
            raise DeviceServiceError(
                "DEVICE_SESSION_NOT_FOUND",
                "设备会话不存在。",
                status_code=404,
            ) from exc

    def _reconcile_orphaned_operation(
        self,
        project_id: str,
        operation: DeviceOperation,
    ) -> DeviceOperation:
        if operation.status not in {
            DeviceOperationStatus.QUEUED,
            DeviceOperationStatus.RUNNING,
        }:
            return operation
        task = self._tasks.get(operation.id)
        if task is not None and not task.done():
            return operation

        if (
            operation.metadata.get("channel")
            == DeviceDeploymentChannel.ESP_CLAW.value
        ):
            return self._fail_orphaned_espclaw_operation(
                project_id,
                operation,
                reason="The local device service restarted while the ESP-Claw deployment was active.",
            )

        state = self._state(operation.id, operation)
        failure_evidence = _failure_evidence(state)
        failure_evidence["originalErrorCode"] = "DEVICE_OPERATION_INTERRUPTED"
        failure_evidence["interruptedPhase"] = operation.phase.value
        self._step(
            state,
            DeviceOperationPhase.COMPLETE,
            TransportResult(None, "local device service restarted"),
            "本地设备服务重启，原执行上下文已丢失",
        )
        self._finish_state(
            state,
            status=DeviceOperationStatus.FAILED,
            error_code="DEVICE_OPERATION_INTERRUPTED",
            message=(
                "本地设备服务已重启，未完成操作无法继续；已保留备份与步骤证据，"
                "请重新扫描并连接后检查设备状态。"
            ),
        )
        reconciled = self._persist(
            project_id,
            operation.id,
            state,
            DeviceOperationStatus.FAILED,
        )
        self._repo.set_session_status(
            project_id,
            operation.sessionId,
            DeviceSessionStatus.ERROR,
        )
        return reconciled

    def _fail_orphaned_espclaw_operation(
        self,
        project_id: str,
        operation: DeviceOperation,
        *,
        reason: str,
    ) -> DeviceOperation:
        """Persist an unsafe interrupted ESP-Claw operation without fake cancel."""

        state = self._state(operation.id, operation)
        metadata = state.setdefault("metadata", {})
        if isinstance(metadata, dict):
            metadata["runtimeStopOk"] = False
            metadata["orphanedExecution"] = True
        failure_evidence = _failure_evidence(state)
        failure_evidence["originalErrorCode"] = "DEVICE_OPERATION_INTERRUPTED"
        failure_evidence["interruptedPhase"] = operation.phase.value
        self._step(
            state,
            DeviceOperationPhase.RESTORE,
            TransportResult(6, "remote ESP-Claw Lua stop was not confirmed"),
            "Local execution context was lost; remote Lua may still be running",
        )
        self._record_espclaw_recovery_verification(state)
        self._finish_state(
            state,
            status=DeviceOperationStatus.FAILED,
            error_code="ESP_CLAW_EMERGENCY_STOP_UNCONFIRMED",
            message=(
                f"{reason} Remote emergency stop is unconfirmed; do not retry. "
                "Manually stop actuators and inspect the ESP-Claw device."
            ),
        )
        failed = self._persist(
            project_id,
            operation.id,
            state,
            DeviceOperationStatus.FAILED,
        )
        self._repo.set_session_status(
            project_id,
            operation.sessionId,
            DeviceSessionStatus.ERROR,
        )
        return failed

    def _persist_corrected_upload_outcome(
        self,
        project_id: str,
        operation: DeviceOperation,
    ) -> DeviceOperation:
        if (
            operation.kind != DeviceOperationKind.UPLOAD_CODE
            or operation.status != DeviceOperationStatus.COMPLETED
        ):
            return operation
        stored_status = self._repo.get_stored_operation_status(project_id, operation.id)
        if stored_status not in {
            DeviceOperationStatus.FAILED,
            DeviceOperationStatus.TIMED_OUT,
        }:
            return operation

        state = self._state(operation.id, operation)
        state["status"] = DeviceOperationStatus.COMPLETED.value
        self._repo.update_operation(
            project_id,
            operation.id,
            status=DeviceOperationStatus.COMPLETED,
            log=_encode_state(state),
            completed_at=operation.completedAt or _now(),
        )
        return self._repo.sync_operation_artifact(project_id, operation.id)

    def _running(
        self,
        project_id: str,
        operation_id: str,
        state: dict[str, object],
        phase: DeviceOperationPhase,
        progress: int,
    ) -> None:
        state["phase"] = phase.value
        state["progress"] = progress
        state["cancelable"] = True
        self._persist(project_id, operation_id, state, DeviceOperationStatus.RUNNING)

    @staticmethod
    def _step(
        state: dict[str, object],
        phase: DeviceOperationPhase,
        result: TransportResult,
        summary: str,
    ) -> None:
        status = (
            DeviceOperationStatus.COMPLETED
            if result.exit_code == 0
            else DeviceOperationStatus.FAILED
        )
        now = _now()
        step = DeviceOperationStep(
            phase=phase,
            status=status,
            exitCode=result.exit_code,
            summary=summary,
            startedAt=now,
            completedAt=now,
        )
        steps = state.setdefault("steps", [])
        assert isinstance(steps, list)
        steps.append(step.model_dump(mode="json"))

    @classmethod
    def _exception_step(
        cls,
        state: dict[str, object],
        exc: BaseException,
    ) -> None:
        phase_value = state.get("phase")
        try:
            phase = DeviceOperationPhase(str(phase_value))
        except ValueError:
            return
        steps = state.get("steps")
        if isinstance(steps, list) and any(
            isinstance(step, dict)
            and step.get("phase") == phase.value
            and step.get("status") == DeviceOperationStatus.FAILED.value
            for step in steps
        ):
            return
        exit_code = exc.exit_code if isinstance(exc, DeviceTransportError) else None
        cls._step(
            state,
            phase,
            TransportResult(exit_code, "transport raised before returning a result"),
            f"{phase.value} 阶段的本地传输未返回成功退出码",
        )

    @staticmethod
    def _require_zero(
        result: TransportResult,
        code: str,
        phase: DeviceOperationPhase,
    ) -> None:
        if result.exit_code != 0:
            raise _FlowFailure(code, phase, result)

    @staticmethod
    def _finish_state(
        state: dict[str, object],
        *,
        status: DeviceOperationStatus,
        error_code: str | None,
        message: str,
    ) -> None:
        state["phase"] = DeviceOperationPhase.COMPLETE.value
        state["progress"] = 100
        state["cancelable"] = False
        state["errorCode"] = error_code
        state["log"] = message
        state["status"] = status.value

    def _persist(
        self,
        project_id: str,
        operation_id: str,
        state: dict[str, object],
        status: DeviceOperationStatus,
    ) -> DeviceOperation:
        terminal = status not in {DeviceOperationStatus.QUEUED, DeviceOperationStatus.RUNNING}
        operation = self._repo.update_operation(
            project_id,
            operation_id,
            status=status,
            log=_encode_state(state),
            completed_at=_now() if terminal else None,
        )
        return (
            self._repo.sync_operation_artifact(project_id, operation_id)
            if terminal and operation.artifactId is None
            else operation
        )

    def _state(self, operation_id: str, operation: DeviceOperation) -> dict[str, object]:
        state = self._states.get(operation_id)
        if state is not None:
            return state
        return {
            "schema": "device-operation/v1",
            "log": operation.log,
            "phase": operation.phase.value,
            "progress": operation.progress,
            "errorCode": operation.errorCode,
            "steps": [step.model_dump(mode="json") for step in operation.steps],
            "backup": operation.backup.model_dump(mode="json") if operation.backup else None,
            "verification": (
                operation.verification.model_dump(mode="json") if operation.verification else None
            ),
            "cancelable": operation.cancelable,
            "metadata": operation.metadata,
        }

    @staticmethod
    def _service_error(exc: DeviceTransportError, fallback_code: str) -> DeviceServiceError:
        return DeviceServiceError(
            exc.code or fallback_code,
            str(exc),
            status_code=408 if isinstance(exc, DeviceTransportTimedOut) else 422,
            retryable=exc.retryable,
        )


def evaluate_watering_smoke_output(
    output: str,
    *,
    session_id: str,
    operation_id: str,
) -> WateringSmokeEvidence:
    """Build deterministic, sanitized evidence from structured watering logs."""

    events: list[dict[str, str]] = []
    for line in output.splitlines():
        if "ZW_WATER" not in line:
            continue
        fields = {
            key.casefold(): value.strip(",;[]()").upper()
            for key, value in _WATERING_LOG_FIELD.findall(line)
        }
        if fields:
            events.append(fields)

    samples = [
        item
        for item in events
        if "moisture" in item or "raw" in item or item.get("event") == "SAMPLE"
    ]
    continuous_ok = len(samples) >= 3
    wet_events = [item for item in events if item.get("state") == "WET"]
    wet_pump_off_ok = bool(wet_events) and all(
        item.get("pump") == "OFF" for item in wet_events
    )

    dry_on_seen = False
    dry_limited_ok = False
    for item in events:
        if item.get("state") == "DRY" and item.get("pump") == "ON":
            dry_on_seen = True
            continue
        if not dry_on_seen or item.get("pump") != "OFF":
            continue
        elapsed = _optional_int(item.get("elapsed_ms"))
        if elapsed is None:
            elapsed = _optional_int(item.get("duration_ms"))
        if elapsed is not None and 0 < elapsed <= 3_000:
            dry_limited_ok = True
            break

    normalized_output = output.casefold()
    no_unhandled = not any(
        marker in normalized_output for marker in _UNHANDLED_RUNTIME_MARKERS
    )
    ok = continuous_ok and wet_pump_off_ok and dry_limited_ok and no_unhandled
    observations = [
        f"已识别 {len(samples)} 条湿度采样记录。",
        "湿润状态水泵保持关闭。" if wet_pump_off_ok else "尚缺少湿润状态停泵证据。",
        "干燥状态有限启动并在 3 秒内关闭。"
        if dry_limited_ok
        else "尚缺少干燥状态启动后 3 秒内关闭的证据。",
        "未发现未处理异常。" if no_unhandled else "设备输出中发现未处理异常。",
    ]
    return WateringSmokeEvidence(
        sessionId=session_id,
        operationId=operation_id,
        checkedAt=_now(),
        sampleCount=len(samples),
        continuousMoistureOk=continuous_ok,
        wetPumpOffOk=wet_pump_off_ok,
        dryLimitedRunOk=dry_limited_ok,
        noUnhandledException=no_unhandled,
        ok=ok,
        summary=(
            "自动浇花运行证据完整，设备冒烟测试通过。"
            if ok
            else "自动浇花运行证据尚不完整，请按湿润、干燥场景继续观察设备日志。"
        ),
        observations=observations,
    )


def _failure_evidence(state: dict[str, object]) -> dict[str, object]:
    metadata = state.setdefault("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
        state["metadata"] = metadata
    evidence = metadata.get("failureEvidence")
    if not isinstance(evidence, dict):
        evidence = {}
        metadata["failureEvidence"] = evidence
    return evidence


def _connection_failure_message(output: str) -> str:
    normalized = output.casefold()
    if "in use by another program" in normalized or "access is denied" in normalized:
        return "串口正在被其他程序占用，请关闭串口监视器、Thonny 或残留的 mpremote 后重试。"
    if "could not enter raw repl" in normalized or "could not enter raw-paste mode" in normalized:
        return "已找到设备，但无法进入 MicroPython REPL。请按一次 RST/EN，并确认设备运行 MicroPython 后重试。"
    if "no device found" in normalized or "failed to access" in normalized:
        return "串口已失效或暂时不可访问，请重新插拔设备并重新扫描。"
    return "设备未响应安全的 MicroPython 身份探测，请确认串口未被占用并按 RST/EN 后重试。"


def _record_original_failure(state: dict[str, object], error_code: str) -> None:
    _failure_evidence(state)["originalErrorCode"] = error_code


def _record_restore_failure(
    state: dict[str, object],
    *,
    error_code: str | None,
    exit_code: int | None,
) -> None:
    evidence = _failure_evidence(state)
    evidence["restoreErrorCode"] = error_code
    evidence["restoreExitCode"] = exit_code
    evidence["restoreSucceeded"] = error_code is None and exit_code == 0


def _upload_error_code(exc: BaseException) -> str:
    if isinstance(exc, _FlowFailure):
        return exc.code
    if isinstance(exc, DeviceTransportError):
        return exc.code
    if isinstance(exc, TimeoutError):
        return "DEVICE_UPLOAD_TIMEOUT"
    return "DEVICE_UPLOAD_INTERNAL_ERROR"


def _session_status_after_cancellation(state: dict[str, object]) -> DeviceSessionStatus:
    evidence = _failure_evidence(state)
    if "restoreSucceeded" in evidence:
        return (
            DeviceSessionStatus.MANAGED
            if evidence.get("restoreSucceeded") is True
            else DeviceSessionStatus.ERROR
        )
    steps = state.get("steps")
    device_write_started = isinstance(steps, list) and any(
        isinstance(step, dict)
        and step.get("phase")
        in {
            DeviceOperationPhase.TRANSFER.value,
            DeviceOperationPhase.VERIFY_FILES.value,
            DeviceOperationPhase.START_RUNTIME.value,
            DeviceOperationPhase.RESTART.value,
            DeviceOperationPhase.RESTORE.value,
        }
        for step in steps
    )
    return (
        DeviceSessionStatus.ERROR
        if device_write_started
        else DeviceSessionStatus.RUNTIME_BUSY
    )


def _upload_files(code_run: CodeRun) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    reserved_runtime_modules = {"unihiker_k10.py", "k10_base.py"}
    for file in code_run.files:
        parsed = PurePosixPath(file.path)
        if not file.path.startswith("src/") or parsed.suffix != ".py":
            continue
        if not is_uploadable_python_path(file.path):
            raise DeviceServiceError(
                "DEVICE_CODE_PATH_INVALID",
                "代码只能包含受限 src/ MicroPython 文件树。",
            )
        remote = PurePosixPath(*parsed.parts[1:]).as_posix()
        if parsed.name.casefold() in reserved_runtime_modules:
            raise DeviceServiceError(
                "RESERVED_DEVICE_MODULE_NAME",
                "代码不能覆盖用于设备身份校验的 K10 固件模块。",
            )
        files[remote] = file.content.encode("utf-8")
    if "main.py" not in files:
        raise DeviceServiceError("DEVICE_MAIN_FILE_MISSING", "当前代码版本缺少 src/main.py。")
    return files


def _code_runtime_value(code_run: CodeRun) -> str:
    runtime = getattr(code_run, "runtime", None)
    value = getattr(runtime, "value", runtime)
    return str(value) if value is not None else ""


def _espclaw_job_name(project_id: str) -> str:
    """Return one managed Lua job name for every alias of a project device."""

    return "zhangwen_" + hashlib.sha256(project_id.encode("utf-8")).hexdigest()[:16]


def _espclaw_failure_message(state: dict[str, object], base: str) -> str:
    metadata = state.get("metadata")
    if not isinstance(metadata, dict):
        return base
    if metadata.get("runtimeStopOk") is False:
        return (
            f"{base} Emergency stop was not confirmed; do not retry. "
            "Manually stop actuators and inspect the device."
        )
    if metadata.get("rollbackOk") is False:
        return (
            f"{base} File rollback was not confirmed; do not retry until "
            "the ESP-Claw storage is inspected manually."
        )
    if metadata.get("rollbackOk") is True:
        if metadata.get("runtimeStopOk") is True:
            return f"{base} The managed Lua job was stopped and previous files were restored."
        return f"{base} Previous files were restored or newly written files were removed."
    return base


def _espclaw_code_files(code_run: CodeRun) -> tuple[dict[str, bytes], str]:
    entrypoint = str(getattr(code_run, "entrypoint", ""))
    if entrypoint != "scripts/main.lua":
        raise DeviceServiceError(
            "ESP_CLAW_ENTRYPOINT_INVALID",
            "ESP-Claw CodeRun entrypoint must be scripts/main.lua.",
        )
    files: dict[str, bytes] = {}
    for file in code_run.files:
        path = str(file.path)
        if path == "README.md":
            continue
        parsed = PurePosixPath(path)
        if (
            parsed.is_absolute()
            or not path.startswith("scripts/")
            or parsed.suffix.casefold() != ".lua"
            or any(part in {"", ".", ".."} for part in parsed.parts)
            or any(_ESPCLAW_PATH_SEGMENT.fullmatch(part) is None for part in parsed.parts)
            or str(getattr(file, "language", "")).casefold() != "lua"
        ):
            raise DeviceServiceError(
                "ESP_CLAW_CODE_PATH_INVALID",
                "ESP-Claw deployment accepts only safe scripts/**/*.lua files.",
            )
        files[path] = file.content.encode("utf-8")
    if entrypoint not in files:
        raise DeviceServiceError(
            "ESP_CLAW_ENTRYPOINT_MISSING",
            "ESP-Claw CodeRun is missing scripts/main.lua.",
        )
    if not files or len(files) > 30 or sum(len(content) for content in files.values()) > 1_200_000:
        raise DeviceServiceError(
            "ESP_CLAW_CODE_BUNDLE_INVALID",
            "ESP-Claw code bundle exceeds the controlled file-count or size limit.",
        )
    return files, entrypoint


def _espclaw_directories(version_path: str, files: dict[str, bytes]) -> list[str]:
    directories: set[str] = set()
    for path in [version_path, *(str(PurePosixPath(item).parent) for item in files)]:
        current = PurePosixPath(path)
        while str(current) not in {"/", ESP_CLAW_STORAGE_BASE_PATH}:
            directories.add(str(current))
            current = current.parent
    return sorted(directories, key=lambda item: (len(PurePosixPath(item).parts), item))


def _parameter_payload(parameter_set: ParameterSetRevision) -> bytes:
    return (
        json.dumps(
            {
                "schema": "zhangwen.device-parameters/v1",
                "boardId": parameter_set.boardId.value,
                "profileRevision": parameter_set.profileRevision,
                "parameterSetId": parameter_set.id,
                "revision": parameter_set.revision,
                "values": parameter_set.values,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _validated_operation_id(value: str | None) -> str:
    operation_id = value or f"device_operation_{uuid.uuid4().hex}"
    if not _OPERATION_ID.fullmatch(operation_id):
        raise DeviceServiceError(
            "DEVICE_OPERATION_ID_INVALID",
            "operationId 必须是 8-128 位安全标识。",
        )
    return operation_id


def _fingerprint(*values: str) -> str:
    return hashlib.sha256("\x1f".join(values).encode("utf-8")).hexdigest()


def _initial_state(
    kind: DeviceOperationKind,
    fingerprint: str,
    *,
    metadata: dict[str, object],
) -> dict[str, object]:
    return {
        "schema": "device-operation/v1",
        "log": "设备操作已排队。",
        "phase": DeviceOperationPhase.QUEUED.value,
        "progress": 0,
        "errorCode": None,
        "steps": [],
        "backup": None,
        "verification": None,
        "cancelable": True,
        "metadata": {"kind": kind.value, "fingerprint": fingerprint, **metadata},
    }


def _encode_state(state: dict[str, object]) -> str:
    return json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _optional_text(value: object) -> str | None:
    return str(value) if value is not None and str(value).strip() else None


def _optional_int(value: object, *, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _match_reenumerated_port(
    original: DevicePort, candidates: list[DevicePort]
) -> DevicePort | None:
    exact = next((item for item in candidates if item.id == original.id), None)
    if exact is not None:
        return exact
    if original.serialNumber:
        serial_match = next(
            (
                item
                for item in candidates
                if item.serialNumber and item.serialNumber == original.serialNumber
            ),
            None,
        )
        if serial_match is not None:
            return serial_match
    hardware_matches = [
        item
        for item in candidates
        if original.vid is not None
        and original.pid is not None
        and item.vid == original.vid
        and item.pid == original.pid
        and item.chip == original.chip
    ]
    return hardware_matches[0] if len(hardware_matches) == 1 else None


def _now_dt() -> datetime:
    return datetime.now(UTC)


def _now() -> str:
    return _now_dt().isoformat()
