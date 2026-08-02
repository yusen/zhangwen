"""Device management boundary models."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from zhangwen.device_lab.models import SupportedDeviceBoardId


class DeviceSessionStatus(StrEnum):
    DISCONNECTED = "DISCONNECTED"
    DISCOVERED = "DISCOVERED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    ATTACHED_UNVERIFIED = "ATTACHED_UNVERIFIED"
    RUNTIME_BUSY = "RUNTIME_BUSY"
    MANAGED = "MANAGED"
    UPLOADING = "UPLOADING"
    RESTARTING = "RESTARTING"
    VERIFYING = "VERIFYING"
    READY = "READY"
    ERROR = "ERROR"


class DeviceOperationKind(StrEnum):
    UPLOAD_CODE = "UPLOAD_CODE"
    FLASH_FIRMWARE = "FLASH_FIRMWARE"
    INSTALL_APPLICATION = "INSTALL_APPLICATION"
    SYNC_PARAMETERS = "SYNC_PARAMETERS"
    BACKUP_FILES = "BACKUP_FILES"
    REPL_LOG = "REPL_LOG"


class DeviceDeploymentChannel(StrEnum):
    """Peer code-deployment channels exposed by the device workspace."""

    USB_SERIAL = "USB_SERIAL"
    ESP_CLAW = "ESP_CLAW"


class EspClawEndpointStatus(StrEnum):
    READY = "READY"
    ERROR = "ERROR"


class DeviceOperationStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    DRY_RUN_COMPLETE = "DRY_RUN_COMPLETE"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"
    TIMED_OUT = "TIMED_OUT"


class DeviceTerminalStatus(StrEnum):
    IDLE = "IDLE"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class DeviceOperationPhase(StrEnum):
    QUEUED = "QUEUED"
    PREFLIGHT = "PREFLIGHT"
    INTERRUPT_RUNTIME = "INTERRUPT_RUNTIME"
    BACKUP = "BACKUP"
    TRANSFER = "TRANSFER"
    VERIFY_FILES = "VERIFY_FILES"
    START_RUNTIME = "START_RUNTIME"
    RESTART = "RESTART"
    RECONNECT = "RECONNECT"
    VERIFY_RUNTIME = "VERIFY_RUNTIME"
    FIRMWARE_VALIDATE = "FIRMWARE_VALIDATE"
    MANIFEST_VALIDATE = "MANIFEST_VALIDATE"
    WRITE_SEGMENTS = "WRITE_SEGMENTS"
    VERIFY_SEGMENTS = "VERIFY_SEGMENTS"
    PROVISION = "PROVISION"
    RUNTIME_HANDSHAKE = "RUNTIME_HANDSHAKE"
    FLASH_WRITE = "FLASH_WRITE"
    RESTORE = "RESTORE"
    COMPLETE = "COMPLETE"


class SerialPortType(StrEnum):
    USB = "usb"
    PCI = "pci"
    BLUETOOTH = "bluetooth"
    UNKNOWN = "unknown"


class SerialPortStatus(StrEnum):
    AVAILABLE = "available"
    BUSY = "busy"
    CONNECTED = "connected"
    UNKNOWN = "unknown"


class DevicePort(BaseModel):
    id: str
    label: str
    transport: str = "system-serial"
    portName: str
    portType: SerialPortType = SerialPortType.UNKNOWN
    description: str | None = None
    manufacturer: str | None = None
    product: str | None = None
    vid: int | None = None
    pid: int | None = None
    likelyBoard: str | None = None
    status: SerialPortStatus = SerialPortStatus.UNKNOWN
    chip: str = "Unknown"
    serialNumber: str | None = None
    available: bool = True


class DeviceLogEntry(BaseModel):
    id: str
    level: str
    message: str
    createdAt: str


class DeviceSession(BaseModel):
    id: str
    projectId: str
    portId: str
    # New sessions store a canonical SupportedDeviceBoardId value.  Historical
    # sessions remain readable so the UI can explain that operations are blocked.
    board: str
    status: DeviceSessionStatus
    connectedAt: str | None = None
    lastSeenAt: str
    logs: list[DeviceLogEntry]


class DeviceOperationStep(BaseModel):
    """Sanitized evidence for one local transport command or phase."""

    phase: DeviceOperationPhase
    status: DeviceOperationStatus
    exitCode: int | None = None
    summary: str = ""
    startedAt: str | None = None
    completedAt: str | None = None


class DeviceBackupSummary(BaseModel):
    """Metadata only; backup bytes never enter SQLite or an Artifact."""

    backupId: str
    fileCount: int
    paths: list[str]
    createdAt: str
    restorable: bool = True


class DeviceVerification(BaseModel):
    fileHashes: dict[str, str] = Field(default_factory=dict)
    reconnectExitCode: int | None = None
    runtimeExitCode: int | None = None
    ok: bool = False
    summary: str = ""
    deploymentOk: bool | None = None
    restartOk: bool | None = None
    runtimeInterruptedOk: bool | None = None
    runtimeStartedOk: bool | None = None
    managementChannelOk: bool | None = None
    warnings: list[str] = Field(default_factory=list)


class FirmwareCandidate(BaseModel):
    id: str
    fileName: str
    sizeBytes: int
    sha256: str
    targetChip: str | None = None
    imageFormat: str | None = None
    defaultAddress: int | None = None
    compatible: bool = False
    warnings: list[str] = Field(default_factory=list)
    expiresAt: str


class FirmwareFlashPlan(BaseModel):
    candidate: FirmwareCandidate
    sessionId: str
    address: int
    confirmationToken: str
    expiresAt: str
    summary: str


class DeviceOperation(BaseModel):
    id: str
    projectId: str
    sessionId: str
    kind: DeviceOperationKind
    status: DeviceOperationStatus
    dryRun: bool
    commandLabel: str
    log: str
    artifactId: str | None = None
    artifactVersionId: str | None = None
    createdAt: str
    completedAt: str | None = None
    phase: DeviceOperationPhase = DeviceOperationPhase.QUEUED
    progress: int = 0
    errorCode: str | None = None
    steps: list[DeviceOperationStep] = Field(default_factory=list)
    backup: DeviceBackupSummary | None = None
    verification: DeviceVerification | None = None
    cancelable: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ListDevicePortsResponse(BaseModel):
    ports: list[DevicePort]
    scannedAt: str
    count: int


class ConnectDeviceRequest(BaseModel):
    portId: str
    boardId: SupportedDeviceBoardId
    confirmBoardIdentity: bool = False
    operationId: str | None = None


class DisconnectDeviceRequest(BaseModel):
    sessionId: str
    operationId: str | None = None


class TakeoverDeviceRequest(BaseModel):
    sessionId: str
    confirmHardwareReset: bool = False
    confirmationPhrase: str | None = None


class DeviceSessionResponse(BaseModel):
    session: DeviceSession


class DeviceTerminalRequest(BaseModel):
    sessionId: str


class DeviceTerminalSnapshot(BaseModel):
    sessionId: str
    status: DeviceTerminalStatus
    output: str = ""
    revision: int = 0
    startedAt: str | None = None
    updatedAt: str | None = None
    errorMessage: str | None = None


class DeviceTerminalResponse(BaseModel):
    terminal: DeviceTerminalSnapshot


class DeviceTerminalUnlockRequest(BaseModel):
    sessionId: str
    confirmProfessionalMode: bool = False
    confirmationPhrase: str = Field(min_length=1, max_length=80)


class DeviceTerminalUnlock(BaseModel):
    sessionId: str
    unlockToken: str
    expiresAt: str
    maxBytesPerWrite: int = Field(gt=0, le=512)


class DeviceTerminalUnlockResponse(BaseModel):
    unlock: DeviceTerminalUnlock


class DeviceTerminalWriteRequest(BaseModel):
    sessionId: str
    unlockToken: str = Field(min_length=16, max_length=256)
    input: str = Field(min_length=1, max_length=512)


class WateringSmokeRequest(BaseModel):
    sessionId: str
    operationId: str | None = None


class WateringSmokeEvidence(BaseModel):
    sessionId: str
    operationId: str
    checkedAt: str
    sampleCount: int = Field(ge=0)
    continuousMoistureOk: bool
    wetPumpOffOk: bool
    dryLimitedRunOk: bool
    noUnhandledException: bool
    ok: bool
    summary: str
    observations: list[str] = Field(default_factory=list)


class WateringSmokeResponse(BaseModel):
    evidence: WateringSmokeEvidence
    operation: DeviceOperation


class UploadCodeRequest(BaseModel):
    codeRunId: str
    sessionId: str
    dryRun: bool = True
    operationId: str | None = None
    confirmWrite: bool = False


class UsbSerialDeploymentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: Literal[DeviceDeploymentChannel.USB_SERIAL]
    codeRunId: str = Field(min_length=1, max_length=128)
    sessionId: str = Field(min_length=1, max_length=128)
    dryRun: bool = False
    operationId: str | None = None
    confirmWrite: bool = False


class EspClawDeploymentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: Literal[DeviceDeploymentChannel.ESP_CLAW]
    codeRunId: str = Field(min_length=1, max_length=128)
    endpointId: str = Field(min_length=1, max_length=128)
    operationId: str | None = None
    confirmWrite: bool = False


DeviceDeploymentRequest = Annotated[
    UsbSerialDeploymentRequest | EspClawDeploymentRequest,
    Field(discriminator="channel"),
]


class PairEspClawEndpointRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    webEndpoint: str = Field(min_length=1, max_length=300)
    mcpEndpoint: str = Field(min_length=1, max_length=300)
    pairingMode: Literal["TRUSTED_LAN_MANUAL"] = "TRUSTED_LAN_MANUAL"
    boardId: SupportedDeviceBoardId
    confirmTrustedLan: bool = False
    confirmAdminMode: bool = False
    confirmBoardIdentity: bool = False


class EspClawEndpoint(BaseModel):
    id: str
    projectId: str
    webEndpoint: str
    mcpEndpoint: str
    boardId: SupportedDeviceBoardId
    status: EspClawEndpointStatus
    storageBasePath: Literal["/fatfs"] = "/fatfs"
    capabilities: list[str] = Field(default_factory=list)
    pairedAt: str
    lastSeenAt: str


class EspClawEndpointResponse(BaseModel):
    endpoint: EspClawEndpoint


class ListEspClawEndpointsResponse(BaseModel):
    endpoints: list[EspClawEndpoint]


class FirmwareFlashRequest(BaseModel):
    sessionId: str
    dryRun: bool = True
    confirmFlash: bool = False
    candidateId: str | None = None
    confirmationToken: str | None = None
    operationId: str | None = None
    address: int | None = None
    confirmationPhrase: str | None = None


class FirmwareInspectRequest(BaseModel):
    fileName: str
    contentBase64: str


class FirmwarePrepareRequest(BaseModel):
    sessionId: str
    candidateId: str
    address: int | None = None


class DeviceOperationResponse(BaseModel):
    operation: DeviceOperation
    session: DeviceSession


class DeviceOperationCancelResponse(BaseModel):
    operation: DeviceOperation
    session: DeviceSession


class FirmwareCandidateResponse(BaseModel):
    candidate: FirmwareCandidate


class FirmwareFlashPlanResponse(BaseModel):
    plan: FirmwareFlashPlan


class FirmwareApplicationInstallPrepareRequest(BaseModel):
    sessionId: str
    applicationId: str
    boardId: SupportedDeviceBoardId
    confirmBoardIdentity: bool = False


class FirmwareApplicationInstallPlan(BaseModel):
    applicationId: str
    sessionId: str
    boardId: SupportedDeviceBoardId
    segmentCount: int = Field(gt=0)
    totalBytes: int = Field(gt=0)
    confirmationToken: str
    expiresAt: str
    summary: str


class FirmwareApplicationInstallPlanResponse(BaseModel):
    plan: FirmwareApplicationInstallPlan


class FirmwareApplicationInstallRequest(BaseModel):
    sessionId: str
    applicationId: str
    confirmationToken: str
    operationId: str | None = None
    confirmInstall: bool = False
    confirmationPhrase: str | None = None


class SyncParameterSetRequest(BaseModel):
    sessionId: str
    operationId: str | None = None
    confirmSync: bool = False
