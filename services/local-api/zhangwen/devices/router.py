"""Device management HTTP routes."""

from __future__ import annotations

import base64
import binascii
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request

from zhangwen.code_agent.models import CodeRunStatus, CodeRuntime
from zhangwen.code_agent.repository import CodeRepository
from zhangwen.config import settings
from zhangwen.devices.models import (
    ConnectDeviceRequest,
    DeviceDeploymentRequest,
    DeviceOperationCancelResponse,
    DeviceOperationResponse,
    DeviceSessionResponse,
    DeviceTerminalRequest,
    DeviceTerminalResponse,
    DeviceTerminalUnlockRequest,
    DeviceTerminalUnlockResponse,
    DeviceTerminalWriteRequest,
    DisconnectDeviceRequest,
    EspClawDeploymentRequest,
    EspClawEndpointResponse,
    FirmwareCandidateResponse,
    FirmwareApplicationInstallPlanResponse,
    FirmwareApplicationInstallPrepareRequest,
    FirmwareApplicationInstallRequest,
    FirmwareFlashPlanResponse,
    FirmwareFlashRequest,
    FirmwareInspectRequest,
    FirmwarePrepareRequest,
    ListDevicePortsResponse,
    ListEspClawEndpointsResponse,
    PairEspClawEndpointRequest,
    TakeoverDeviceRequest,
    SyncParameterSetRequest,
    UploadCodeRequest,
    UsbSerialDeploymentRequest,
    WateringSmokeRequest,
    WateringSmokeResponse,
)
from zhangwen.devices.repository import DeviceRepository
from zhangwen.devices.serial_discovery import SerialDiscoveryError, list_serial_ports
from zhangwen.devices.service import DeviceOperationService, DeviceServiceError
from zhangwen.devices.transport import DeviceTransport, SubprocessDeviceTransport
from zhangwen.devices.espclaw import (
    EspClawDeploymentAdapter,
    HttpxEspClawDeploymentAdapter,
)
from zhangwen.host import require_desktop_host
from zhangwen.projects.models import ProjectStage
from zhangwen.projects.repository import ProjectRepository

router = APIRouter(prefix="/api/projects", tags=["devices"])

_transport_override: DeviceTransport | None = None
_default_transport: DeviceTransport | None = None
_espclaw_adapter_override: EspClawDeploymentAdapter | None = None
_default_espclaw_adapter: EspClawDeploymentAdapter | None = None
_services: dict[tuple[Path, int, int], DeviceOperationService] = {}


def configure_device_transport(transport: DeviceTransport | None) -> None:
    """Inject a deterministic transport for tests or a desktop-owned adapter."""

    global _default_transport, _transport_override
    _transport_override = transport
    _default_transport = None
    _services.clear()


def configure_espclaw_adapter(adapter: EspClawDeploymentAdapter | None) -> None:
    """Inject an ESP-Claw adapter; automated tests never touch the LAN."""

    global _default_espclaw_adapter, _espclaw_adapter_override
    _espclaw_adapter_override = adapter
    _default_espclaw_adapter = None
    _services.clear()


async def shutdown_device_services() -> None:
    """Release terminal readers owned by cached device services."""

    services = list(_services.values())
    _services.clear()
    for service in services:
        await service.shutdown()


@router.get("/{project_id}/devices/ports", response_model=ListDevicePortsResponse)
async def list_device_ports(project_id: str, request: Request) -> ListDevicePortsResponse:
    require_desktop_host(request, "serial_scan")
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        if _transport_override is not None:
            ports = await _service(repo).scan_ports()
        else:
            # Keep the existing monkeypatch seam and serial error mapping.  The
            # default scanner is only reached after the desktop host gate.
            ports = list_serial_ports()
    except SerialDiscoveryError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message, "retryable": True},
        ) from exc
    except DeviceServiceError as exc:
        raise _device_error(exc) from exc
    return ListDevicePortsResponse(
        ports=ports,
        scannedAt=datetime.now(UTC).isoformat(),
        count=len(ports),
    )


@router.get("/{project_id}/devices/session/current", response_model=DeviceSessionResponse)
async def get_current_session(project_id: str) -> DeviceSessionResponse:
    repo = _project_repo()
    repo.get_workspace(project_id)
    session = DeviceRepository(repo.db_path).get_current_session(project_id)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "DEVICE_SESSION_NOT_FOUND",
                "message": "当前项目还没有设备会话。",
                "retryable": False,
            },
        )
    return DeviceSessionResponse(session=session)


@router.get(
    "/{project_id}/devices/terminal",
    response_model=DeviceTerminalResponse,
)
async def get_device_terminal(
    project_id: str,
    http_request: Request,
    session_id: str = Query(alias="sessionId"),
) -> DeviceTerminalResponse:
    require_desktop_host(http_request, "serial_connection")
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        terminal = _service(repo).get_terminal(project_id, session_id)
    except ValueError as exc:
        raise _unprocessable("DEVICE_SESSION_NOT_FOUND", str(exc)) from exc
    return DeviceTerminalResponse(terminal=terminal)


@router.post(
    "/{project_id}/devices/terminal/start",
    response_model=DeviceTerminalResponse,
)
async def start_device_terminal(
    project_id: str,
    request: DeviceTerminalRequest,
    http_request: Request,
) -> DeviceTerminalResponse:
    require_desktop_host(http_request, "serial_connection")
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        terminal = await _service(repo).start_terminal(project_id, request.sessionId)
    except (DeviceServiceError, ValueError) as exc:
        if isinstance(exc, DeviceServiceError):
            raise _device_error(exc) from exc
        raise _unprocessable("DEVICE_TERMINAL_START_FAILED", str(exc)) from exc
    return DeviceTerminalResponse(terminal=terminal)


@router.post(
    "/{project_id}/devices/terminal/stop",
    response_model=DeviceTerminalResponse,
)
async def stop_device_terminal(
    project_id: str,
    request: DeviceTerminalRequest,
    http_request: Request,
) -> DeviceTerminalResponse:
    require_desktop_host(http_request, "serial_connection")
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        terminal = await _service(repo).stop_terminal(project_id, request.sessionId)
    except ValueError as exc:
        raise _unprocessable("DEVICE_TERMINAL_STOP_FAILED", str(exc)) from exc
    return DeviceTerminalResponse(terminal=terminal)


@router.post(
    "/{project_id}/devices/terminal/clear",
    response_model=DeviceTerminalResponse,
)
async def clear_device_terminal(
    project_id: str,
    request: DeviceTerminalRequest,
    http_request: Request,
) -> DeviceTerminalResponse:
    require_desktop_host(http_request, "serial_connection")
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        terminal = _service(repo).clear_terminal(project_id, request.sessionId)
    except ValueError as exc:
        raise _unprocessable("DEVICE_TERMINAL_CLEAR_FAILED", str(exc)) from exc
    return DeviceTerminalResponse(terminal=terminal)


@router.post(
    "/{project_id}/devices/terminal/unlock",
    response_model=DeviceTerminalUnlockResponse,
)
async def unlock_device_terminal(
    project_id: str,
    request: DeviceTerminalUnlockRequest,
    http_request: Request,
) -> DeviceTerminalUnlockResponse:
    require_desktop_host(http_request, "serial_connection")
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        unlock = _service(repo).unlock_terminal_input(
            project_id,
            request.sessionId,
            confirm_professional_mode=request.confirmProfessionalMode,
            confirmation_phrase=request.confirmationPhrase,
        )
    except (DeviceServiceError, ValueError) as exc:
        if isinstance(exc, DeviceServiceError):
            raise _device_error(exc) from exc
        raise _unprocessable("DEVICE_TERMINAL_UNLOCK_FAILED", str(exc)) from exc
    return DeviceTerminalUnlockResponse(unlock=unlock)


@router.post(
    "/{project_id}/devices/terminal/write",
    response_model=DeviceTerminalResponse,
)
async def write_device_terminal(
    project_id: str,
    request: DeviceTerminalWriteRequest,
    http_request: Request,
) -> DeviceTerminalResponse:
    require_desktop_host(http_request, "serial_connection")
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        terminal = await _service(repo).write_terminal_input(
            project_id,
            request.sessionId,
            unlock_token=request.unlockToken,
            value=request.input,
        )
    except (DeviceServiceError, ValueError) as exc:
        if isinstance(exc, DeviceServiceError):
            raise _device_error(exc) from exc
        raise _unprocessable("DEVICE_TERMINAL_WRITE_FAILED", str(exc)) from exc
    return DeviceTerminalResponse(terminal=terminal)


@router.post(
    "/{project_id}/devices/watering-smoke/evaluate",
    response_model=WateringSmokeResponse,
)
async def evaluate_watering_smoke(
    project_id: str,
    request: WateringSmokeRequest,
    http_request: Request,
) -> WateringSmokeResponse:
    require_desktop_host(http_request, "serial_connection")
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        evidence, operation = _service(repo).evaluate_watering_smoke(
            project_id,
            request.sessionId,
            request.operationId,
        )
    except DeviceServiceError as exc:
        raise _device_error(exc) from exc
    except ValueError as exc:
        raise _unprocessable("DEVICE_SMOKE_EVALUATION_FAILED", str(exc)) from exc
    return WateringSmokeResponse(evidence=evidence, operation=operation)


@router.post("/{project_id}/devices/connect", response_model=DeviceSessionResponse)
async def connect_device(
    project_id: str,
    request: ConnectDeviceRequest,
    http_request: Request,
) -> DeviceSessionResponse:
    require_desktop_host(http_request, "serial_connection")
    repo = _project_repo()
    repo.get_workspace(project_id)
    if not request.confirmBoardIdentity:
        raise _unprocessable(
            "DEVICE_BOARD_CONFIRMATION_REQUIRED",
            "串口无法仅凭 ESP32-S3 芯片确定精确板型，请确认所选 K10 或 XIAO Sense。",
        )
    try:
        service = _service(repo)
        service.require_project_board(project_id, request.boardId)
        if _transport_override is None and request.portId.startswith("mock_"):
            session = DeviceRepository(repo.db_path).connect_mock_port(
                project_id,
                request.portId,
                request.boardId,
            )
        else:
            session = await service.connect(
                project_id,
                request.portId,
                board_id=request.boardId,
            )
    except DeviceServiceError as exc:
        raise _device_error(exc) from exc
    except ValueError as exc:
        raise _unprocessable("DEVICE_PORT_NOT_FOUND", str(exc)) from exc
    _update_stage(repo, project_id, ProjectStage.READY_TO_UPLOAD)
    return DeviceSessionResponse(session=session)


@router.post("/{project_id}/devices/takeover", response_model=DeviceSessionResponse)
async def takeover_device_runtime(
    project_id: str,
    request: TakeoverDeviceRequest,
    http_request: Request,
) -> DeviceSessionResponse:
    require_desktop_host(http_request, "serial_connection")
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        session = await _service(repo).takeover_runtime(
            project_id,
            request.sessionId,
            confirm_hardware_reset=request.confirmHardwareReset,
            confirmation_phrase=request.confirmationPhrase,
        )
    except DeviceServiceError as exc:
        raise _device_error(exc) from exc
    except ValueError as exc:
        raise _unprocessable("DEVICE_SESSION_NOT_FOUND", str(exc)) from exc
    return DeviceSessionResponse(session=session)


@router.post("/{project_id}/devices/disconnect", response_model=DeviceSessionResponse)
async def disconnect_device(
    project_id: str,
    request: DisconnectDeviceRequest,
    http_request: Request,
) -> DeviceSessionResponse:
    require_desktop_host(http_request, "serial_connection")
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        session = await _service(repo).disconnect(project_id, request.sessionId)
    except (DeviceServiceError, ValueError) as exc:
        if isinstance(exc, DeviceServiceError):
            raise _device_error(exc) from exc
        raise _unprocessable("DEVICE_DISCONNECT_FAILED", str(exc)) from exc
    return DeviceSessionResponse(session=session)


@router.post(
    "/{project_id}/devices/esp-claw/endpoints/pair",
    response_model=EspClawEndpointResponse,
)
async def pair_espclaw_endpoint(
    project_id: str,
    request: PairEspClawEndpointRequest,
    http_request: Request,
) -> EspClawEndpointResponse:
    require_desktop_host(http_request, "device_upload")
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        endpoint = await _service(repo).pair_espclaw_endpoint(
            project_id=project_id,
            web_endpoint=request.webEndpoint,
            mcp_endpoint=request.mcpEndpoint,
            board_id=request.boardId,
            confirm_trusted_lan=request.confirmTrustedLan,
            confirm_admin_mode=request.confirmAdminMode,
            confirm_board_identity=request.confirmBoardIdentity,
        )
    except DeviceServiceError as exc:
        raise _device_error(exc) from exc
    return EspClawEndpointResponse(endpoint=endpoint)


@router.get(
    "/{project_id}/devices/esp-claw/endpoints",
    response_model=ListEspClawEndpointsResponse,
)
async def list_espclaw_endpoints(
    project_id: str,
    http_request: Request,
) -> ListEspClawEndpointsResponse:
    require_desktop_host(http_request, "device_upload")
    repo = _project_repo()
    repo.get_workspace(project_id)
    return ListEspClawEndpointsResponse(
        endpoints=_service(repo).list_espclaw_endpoints(project_id)
    )


@router.post("/{project_id}/devices/deploy", response_model=DeviceOperationResponse)
async def deploy_code(
    project_id: str,
    request: DeviceDeploymentRequest,
    http_request: Request,
) -> DeviceOperationResponse:
    """Deploy the accepted CodeRun through one explicit peer channel."""

    require_desktop_host(http_request, "device_upload")
    repo = _project_repo()
    repo.get_workspace(project_id)
    if isinstance(request, UsbSerialDeploymentRequest):
        if request.dryRun:
            try:
                code_run = CodeRepository(repo.db_path).get_code(project_id, request.codeRunId)
                if code_run.status != CodeRunStatus.ACCEPTED:
                    raise ValueError("Only accepted code can enter a device deployment dry run.")
                if code_run.runtime != CodeRuntime.MICROPYTHON:
                    raise ValueError("USB serial deployment requires a MICROPYTHON CodeRun.")
                operation, session = _service(repo).upload_code_dry_run(
                    project_id=project_id,
                    session_id=request.sessionId,
                    code_run=code_run,
                )
            except DeviceServiceError as exc:
                raise _device_error(exc) from exc
            except ValueError as exc:
                code = (
                    "DEVICE_USB_RUNTIME_REQUIRED"
                    if "MICROPYTHON CodeRun" in str(exc)
                    else "DEVICE_UPLOAD_DRY_RUN_FAILED"
                )
                raise _unprocessable(code, str(exc)) from exc
        else:
            try:
                operation, session = await _service(repo).start_upload(
                    project_id=project_id,
                    session_id=request.sessionId,
                    code_run_id=request.codeRunId,
                    operation_id=request.operationId,
                    confirm_write=request.confirmWrite,
                )
            except DeviceServiceError as exc:
                raise _device_error(exc) from exc
    elif isinstance(request, EspClawDeploymentRequest):
        try:
            operation, session = await _service(repo).start_espclaw_deployment(
                project_id=project_id,
                endpoint_id=request.endpointId,
                code_run_id=request.codeRunId,
                operation_id=request.operationId,
                confirm_write=request.confirmWrite,
            )
        except DeviceServiceError as exc:
            raise _device_error(exc) from exc
    else:  # pragma: no cover - Pydantic's discriminated union closes this boundary.
        raise _unprocessable("DEVICE_DEPLOYMENT_CHANNEL_INVALID", "Unknown deployment channel.")
    _update_stage(repo, project_id, ProjectStage.READY_TO_UPLOAD)
    return DeviceOperationResponse(operation=operation, session=session)


@router.post("/{project_id}/devices/upload", response_model=DeviceOperationResponse)
async def upload_code(
    project_id: str,
    request: UploadCodeRequest,
    http_request: Request,
) -> DeviceOperationResponse:
    require_desktop_host(http_request, "device_upload")
    repo = _project_repo()
    repo.get_workspace(project_id)
    if request.dryRun:
        try:
            code_run = CodeRepository(repo.db_path).get_code(project_id, request.codeRunId)
            if code_run.status != CodeRunStatus.ACCEPTED:
                raise ValueError("只有已接受的代码草稿可以进入设备上传 Dry Run。")
            if code_run.runtime != CodeRuntime.MICROPYTHON:
                raise _unprocessable(
                    "DEVICE_USB_RUNTIME_REQUIRED",
                    "USB serial deployment requires a MICROPYTHON CodeRun.",
                )
            operation, session = _service(repo).upload_code_dry_run(
                project_id=project_id,
                session_id=request.sessionId,
                code_run=code_run,
            )
        except DeviceServiceError as exc:
            raise _device_error(exc) from exc
        except ValueError as exc:
            code = (
                "DEVICE_REQUIRES_ACCEPTED_CODE"
                if "已接受的代码草稿" in str(exc)
                else "DEVICE_UPLOAD_DRY_RUN_FAILED"
            )
            raise _unprocessable(code, str(exc)) from exc
        _update_stage(repo, project_id, ProjectStage.READY_TO_UPLOAD)
        return DeviceOperationResponse(operation=operation, session=session)

    try:
        operation, session = await _service(repo).start_upload(
            project_id=project_id,
            session_id=request.sessionId,
            code_run_id=request.codeRunId,
            operation_id=request.operationId,
            confirm_write=request.confirmWrite,
        )
    except DeviceServiceError as exc:
        raise _device_error(exc) from exc
    return DeviceOperationResponse(operation=operation, session=session)


@router.get(
    "/{project_id}/devices/operations/latest",
    response_model=DeviceOperationResponse,
)
async def get_latest_device_operation(project_id: str) -> DeviceOperationResponse:
    repo = _project_repo()
    repo.get_workspace(project_id)
    result = _service(repo).get_latest_operation(project_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "DEVICE_OPERATION_NOT_FOUND",
                "message": "当前项目还没有设备操作记录。",
                "retryable": False,
            },
        )
    operation, session = result
    return DeviceOperationResponse(operation=operation, session=session)


@router.get(
    "/{project_id}/devices/operations/{operation_id}",
    response_model=DeviceOperationResponse,
)
async def get_device_operation(project_id: str, operation_id: str) -> DeviceOperationResponse:
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        operation, session = _service(repo).get_operation(project_id, operation_id)
    except (DeviceServiceError, ValueError) as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "DEVICE_OPERATION_NOT_FOUND",
                "message": str(exc),
                "retryable": False,
            },
        ) from exc
    return DeviceOperationResponse(operation=operation, session=session)


@router.post(
    "/{project_id}/devices/operations/{operation_id}/cancel",
    response_model=DeviceOperationCancelResponse,
)
async def cancel_device_operation(
    project_id: str,
    operation_id: str,
    http_request: Request,
) -> DeviceOperationCancelResponse:
    require_desktop_host(http_request, "device_upload")
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        operation, session = await _service(repo).cancel_operation(project_id, operation_id)
    except (DeviceServiceError, ValueError) as exc:
        if isinstance(exc, DeviceServiceError):
            raise _device_error(exc) from exc
        raise HTTPException(
            status_code=404,
            detail={
                "code": "DEVICE_OPERATION_NOT_FOUND",
                "message": str(exc),
                "retryable": False,
            },
        ) from exc
    return DeviceOperationCancelResponse(operation=operation, session=session)


@router.post(
    "/{project_id}/device-lab/applications/prepare-install",
    response_model=FirmwareApplicationInstallPlanResponse,
)
async def prepare_application_install(
    project_id: str,
    request: FirmwareApplicationInstallPrepareRequest,
    http_request: Request,
) -> FirmwareApplicationInstallPlanResponse:
    require_desktop_host(http_request, "device_flash")
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        plan = _service(repo).prepare_application_install(
            project_id=project_id,
            session_id=request.sessionId,
            application_id=request.applicationId,
            board_id=request.boardId,
            confirm_board_identity=request.confirmBoardIdentity,
        )
    except DeviceServiceError as exc:
        raise _device_error(exc) from exc
    return FirmwareApplicationInstallPlanResponse(plan=plan)


@router.post(
    "/{project_id}/device-lab/applications/install",
    response_model=DeviceOperationResponse,
)
async def install_application(
    project_id: str,
    request: FirmwareApplicationInstallRequest,
    http_request: Request,
) -> DeviceOperationResponse:
    require_desktop_host(http_request, "device_flash")
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        operation, session = await _service(repo).start_application_install(
            project_id=project_id,
            session_id=request.sessionId,
            application_id=request.applicationId,
            confirmation_token=request.confirmationToken,
            operation_id=request.operationId,
            confirm_install=request.confirmInstall,
            confirmation_phrase=request.confirmationPhrase,
        )
    except DeviceServiceError as exc:
        raise _device_error(exc) from exc
    return DeviceOperationResponse(operation=operation, session=session)


@router.post(
    "/{project_id}/device-lab/parameter-sets/{parameter_set_id}/sync",
    response_model=DeviceOperationResponse,
)
async def sync_parameter_set(
    project_id: str,
    parameter_set_id: str,
    request: SyncParameterSetRequest,
    http_request: Request,
) -> DeviceOperationResponse:
    require_desktop_host(http_request, "device_upload")
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        operation, session = await _service(repo).start_parameter_sync(
            project_id=project_id,
            session_id=request.sessionId,
            parameter_set_id=parameter_set_id,
            operation_id=request.operationId,
            confirm_sync=request.confirmSync,
        )
    except DeviceServiceError as exc:
        raise _device_error(exc) from exc
    return DeviceOperationResponse(operation=operation, session=session)


@router.post(
    "/{project_id}/devices/firmware/inspect",
    response_model=FirmwareCandidateResponse,
)
async def inspect_firmware(
    project_id: str,
    request: FirmwareInspectRequest,
    http_request: Request,
) -> FirmwareCandidateResponse:
    require_desktop_host(http_request, "device_flash")
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        content = base64.b64decode(request.contentBase64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise _unprocessable("FIRMWARE_CONTENT_INVALID", "固件内容不是有效 Base64。") from exc
    try:
        candidate = await _service(repo).inspect_firmware(request.fileName, content)
    except DeviceServiceError as exc:
        raise _device_error(exc) from exc
    return FirmwareCandidateResponse(candidate=candidate)


@router.post(
    "/{project_id}/devices/firmware/prepare",
    response_model=FirmwareFlashPlanResponse,
)
async def prepare_firmware(
    project_id: str,
    request: FirmwarePrepareRequest,
    http_request: Request,
) -> FirmwareFlashPlanResponse:
    require_desktop_host(http_request, "device_flash")
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        plan = _service(repo).prepare_firmware(
            project_id=project_id,
            session_id=request.sessionId,
            candidate_id=request.candidateId,
            address=request.address,
        )
    except DeviceServiceError as exc:
        raise _device_error(exc) from exc
    return FirmwareFlashPlanResponse(plan=plan)


@router.post("/{project_id}/devices/flash", response_model=DeviceOperationResponse)
async def flash_firmware(
    project_id: str,
    request: FirmwareFlashRequest,
    http_request: Request,
) -> DeviceOperationResponse:
    require_desktop_host(http_request, "device_flash")
    if not request.confirmFlash:
        raise _unprocessable(
            "DEVICE_FLASH_CONFIRMATION_REQUIRED",
            "固件烧录必须显式确认。",
        )
    repo = _project_repo()
    repo.get_workspace(project_id)
    if request.dryRun:
        try:
            operation, session = _service(repo).firmware_flash_dry_run(
                project_id=project_id,
                session_id=request.sessionId,
            )
        except DeviceServiceError as exc:
            raise _device_error(exc) from exc
        except ValueError as exc:
            raise _unprocessable("DEVICE_FLASH_DRY_RUN_FAILED", str(exc)) from exc
        return DeviceOperationResponse(operation=operation, session=session)

    try:
        operation, session = await _service(repo).start_firmware_flash(
            project_id=project_id,
            session_id=request.sessionId,
            candidate_id=request.candidateId,
            confirmation_token=request.confirmationToken,
            operation_id=request.operationId,
            address=request.address,
            confirm_flash=request.confirmFlash,
            confirmation_phrase=request.confirmationPhrase,
        )
    except DeviceServiceError as exc:
        raise _device_error(exc) from exc
    return DeviceOperationResponse(operation=operation, session=session)


def _project_repo() -> ProjectRepository:
    return ProjectRepository(settings.data_dir)


def _service(repo: ProjectRepository) -> DeviceOperationService:
    global _default_espclaw_adapter, _default_transport
    transport = _transport_override
    if transport is None:
        # Lambda preserves the existing router-level scan seam while ensuring
        # the real adapter never chooses an executable or argv from the client.
        if _default_transport is None:
            _default_transport = SubprocessDeviceTransport(scanner=lambda: list_serial_ports())
        transport = _default_transport
    espclaw_adapter = _espclaw_adapter_override
    if espclaw_adapter is None:
        if _default_espclaw_adapter is None:
            _default_espclaw_adapter = HttpxEspClawDeploymentAdapter()
        espclaw_adapter = _default_espclaw_adapter
    key = (repo.db_path.resolve(), id(transport), id(espclaw_adapter))
    service = _services.get(key)
    if service is None:
        service = DeviceOperationService(
            repo.db_path,
            settings.data_dir,
            transport,
            espclaw_adapter=espclaw_adapter,
        )
        _services[key] = service
    return service


def get_device_operation_service() -> DeviceOperationService:
    """Return the one process-wide executor for trusted in-process adapters."""

    return _service(_project_repo())


def _device_error(exc: DeviceServiceError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={
            "code": exc.code,
            "message": exc.message,
            "retryable": exc.retryable,
        },
    )


def _unprocessable(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={"code": code, "message": message, "retryable": False},
    )


def _update_stage(repo: ProjectRepository, project_id: str, stage: ProjectStage) -> None:
    now = datetime.now(UTC).isoformat()
    with repo._connect() as conn:
        conn.execute(
            "UPDATE projects SET stage = ?, updated_at = ? WHERE id = ?",
            (stage.value, now, project_id),
        )
