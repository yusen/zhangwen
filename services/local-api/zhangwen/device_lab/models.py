"""Strict HTTP and persistence models for the two-board device lab."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from zhangwen.domains.orchestration.models import ExecutionRevisionSet
from zhangwen.domains.works.models import WorkRunRevisionBindings


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SupportedDeviceBoardId(StrEnum):
    XIAO_ESP32S3_SENSE = "seeedstudio/xiao_esp32s3_sense"
    DFROBOT_K10 = "dfrobot/dfrobot_k10"


class DeviceBoardPinConflict(StrictModel):
    resources: list[str]
    message: str


class DeviceBoardCapability(StrictModel):
    id: SupportedDeviceBoardId
    displayName: str
    manufacturer: str
    chip: Literal["esp32s3"] = "esp32s3"
    flashSizeBytes: int = Field(gt=0)
    psramSizeBytes: int = Field(ge=0)
    legacyAliases: list[str] = Field(default_factory=list)
    peripherals: list[str] = Field(default_factory=list)
    pinConflicts: list[DeviceBoardPinConflict] = Field(default_factory=list)


class DeviceLabChannel(StrictModel):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9._-]*$")
    label: str = Field(min_length=1, max_length=80)
    kind: Literal["sensor-input", "telemetry", "actuator", "parameter"]
    valueType: Literal["number", "boolean", "string"]
    control: Literal["slider", "number", "switch", "waveform", "media"]
    unit: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    defaultValue: float | bool | str
    writable: bool = False
    requiresArm: bool = False
    safeValue: float | bool | str | None = None
    componentId: str | None = Field(default=None, min_length=1, max_length=160)
    source: Literal["board-profile", "project-scene"] = "board-profile"


class DeviceLabProfileV1(StrictModel):
    schemaVersion: Literal["zhangwen.device-lab-profile/v1"] = (
        "zhangwen.device-lab-profile/v1"
    )
    boardId: SupportedDeviceBoardId
    revision: str
    channels: list[DeviceLabChannel]


class DeviceLabSceneSource(StrictModel):
    proposalId: str
    proposalVersion: int = Field(ge=1)
    proposalConfirmedAt: str
    projectionPurpose: Literal["PHYSICAL_BOARD", "WORK_FUNCTIONAL"] = (
        "PHYSICAL_BOARD"
    )
    simulationProxyPackageId: str | None = Field(
        default=None,
        min_length=1,
        max_length=240,
    )
    hardwareFactId: str | None = None
    hardwareFactUpdatedAt: str | None = None
    specRunId: str | None = None
    specVersion: int | None = Field(default=None, ge=1)
    specConfirmedAt: str | None = None


class DeviceLabSceneComponent(StrictModel):
    id: str = Field(min_length=1, max_length=160)
    name: str = Field(min_length=1, max_length=160)
    category: Literal[
        "MCU",
        "SENSOR",
        "ACTUATOR",
        "DISPLAY",
        "POWER",
        "STRUCTURE",
        "ONBOARD",
        "SERVICE",
    ]
    role: Literal["controller", "onboard", "external", "service"]
    source: Literal[
        "project-hardware", "approved-spec", "approved-proposal", "board-profile"
    ]
    simulation: Literal["FUNCTIONAL", "VISUAL_ONLY"]
    builtIn: bool = False
    protocol: str | None = Field(default=None, max_length=100)


class DeviceLabSceneConnection(StrictModel):
    id: str = Field(min_length=1, max_length=180)
    fromComponentId: str = Field(min_length=1, max_length=160)
    toComponentId: str = Field(min_length=1, max_length=160)
    protocol: str = Field(min_length=1, max_length=100)
    signal: str = Field(min_length=1, max_length=100)
    pin: str | None = Field(default=None, max_length=40)
    confidence: Literal["CONFIRMED", "PROPOSAL_DERIVED"]
    note: str = Field(min_length=1, max_length=300)


class DeviceLabProjectTestCase(StrictModel):
    id: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=240)
    inputChannelIds: list[str] = Field(default_factory=list, max_length=32)
    expectedBehavior: str = Field(min_length=1, max_length=1000)
    source: Literal["acceptance-scenario", "scene-default"]


class DigitalPrototypeBindingV1(StrictModel):
    schemaVersion: Literal["zhangwen.digital-prototype-binding/v1"] = (
        "zhangwen.digital-prototype-binding/v1"
    )
    solutionRevisionId: str | None = None
    codeRunId: str | None = None
    parameterSetId: str | None = None
    componentPackVersion: str = "wokwi-elements@1.9.2+zhangwen-v1"
    simulationCapability: Literal[
        "FUNCTIONAL", "FIRMWARE", "UART_BOOT_CHECK"
    ] = "FUNCTIONAL"
    layoutVersion: Literal["auto-v1"] = "auto-v1"


class DeviceLabSceneV1(StrictModel):
    schemaVersion: Literal["zhangwen.device-lab-scene/v1"] = (
        "zhangwen.device-lab-scene/v1"
    )
    projectId: str
    revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    boardId: SupportedDeviceBoardId
    status: Literal["READY", "NEEDS_IO_CONFIRMATION"]
    source: DeviceLabSceneSource
    binding: DigitalPrototypeBindingV1 | None = None
    components: list[DeviceLabSceneComponent] = Field(min_length=1, max_length=64)
    connections: list[DeviceLabSceneConnection] = Field(default_factory=list, max_length=128)
    testCases: list[DeviceLabProjectTestCase] = Field(default_factory=list, max_length=64)
    warnings: list[str] = Field(default_factory=list, max_length=20)
    generatedAt: str


class DeviceLabSceneResponse(StrictModel):
    scene: DeviceLabSceneV1
    profile: DeviceLabProfileV1


class QemuRuntimeStatus(StrictModel):
    available: bool
    version: str | None = None
    reason: str | None = None


class DeviceBoardListResponse(StrictModel):
    boards: list[DeviceBoardCapability]
    profiles: list[DeviceLabProfileV1]
    qemu: QemuRuntimeStatus


class FirmwareImageSegment(StrictModel):
    path: str = Field(min_length=1, max_length=240)
    address: int = Field(ge=0)
    sizeBytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    kind: Literal["bootloader", "partition-table", "application"]


class FirmwareSimulationImage(StrictModel):
    path: str = Field(min_length=1, max_length=240)
    sizeBytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class FirmwareApplicationManifestV1(StrictModel):
    schemaVersion: Literal["zhangwen.firmware-application/v1"]
    applicationId: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    displayName: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=80)
    runtime: Literal["micropython", "esp-claw", "esp-idf"]
    boardId: SupportedDeviceBoardId
    chip: Literal["esp32s3"]
    flashSizeBytes: int = Field(gt=0)
    psramSizeBytes: int = Field(ge=0)
    sourceUrl: str | None = Field(default=None, max_length=500)
    sourceRevision: str | None = Field(default=None, max_length=120)
    debugProtocolVersion: Literal["zwdbg/1"] | None = None
    deviceImages: list[FirmwareImageSegment] = Field(min_length=1, max_length=16)
    elfImage: FirmwareSimulationImage | None = None
    simulationImage: FirmwareSimulationImage | None = None


class FirmwareApplicationRecord(StrictModel):
    id: str
    projectId: str
    manifest: FirmwareApplicationManifestV1
    archiveSha256: str
    simulationCapability: Literal["FULL", "UART_ONLY", "NONE"]
    importedAt: str


class CuratedFirmwareApplication(StrictModel):
    applicationId: str
    displayName: str
    boardId: SupportedDeviceBoardId
    sourceUrl: str
    bundled: bool = False


class FirmwareApplicationListResponse(StrictModel):
    applications: list[FirmwareApplicationRecord]
    curated: list[CuratedFirmwareApplication]


class ImportFirmwareApplicationRequest(StrictModel):
    zipBase64: str = Field(min_length=4)


class FirmwareApplicationResponse(StrictModel):
    application: FirmwareApplicationRecord


class DeviceLabTarget(StrEnum):
    SIMULATOR = "SIMULATOR"
    DEVICE = "DEVICE"


class DeviceLabEngine(StrEnum):
    FUNCTIONAL_MODEL = "FUNCTIONAL_MODEL"
    QEMU_ESP32S3 = "QEMU_ESP32S3"
    WOKWI_CLOUD = "WOKWI_CLOUD"


class WokwiRunBindingV1(StrictModel):
    schemaVersion: Literal["zhangwen.wokwi-run-binding/v1"] = (
        "zhangwen.wokwi-run-binding/v1"
    )
    projectRevisionId: str = Field(min_length=1, max_length=160)
    sourceSceneRevision: str = Field(pattern=r"^[a-f0-9]{64}$")
    sourceCodeRunId: str = Field(min_length=1, max_length=160)
    diagramArtifactId: str = Field(min_length=1, max_length=160)
    diagramArtifactVersionId: str | None = Field(
        default=None, min_length=1, max_length=240
    )
    diagramSha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    firmwareArtifactId: str = Field(min_length=1, max_length=160)
    firmwareArtifactVersionId: str | None = Field(
        default=None, min_length=1, max_length=240
    )
    firmwareSha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    elfArtifactId: str | None = Field(default=None, min_length=1, max_length=160)
    runtimePackageRevisionId: str = Field(min_length=1, max_length=160)
    devicePackageRevisionId: str = Field(min_length=1, max_length=160)
    firmwareBaseRevision: str = Field(min_length=1, max_length=160)
    compatibilitySummary: str = Field(default="", max_length=500)
    profile: DeviceLabProfileV1 | None = None
    controlBindings: list["WokwiControlBinding"] = Field(
        default_factory=list, max_length=64
    )
    gpioBindings: list["WokwiGpioBinding"] = Field(
        default_factory=list, max_length=64
    )


class WokwiControlBinding(StrictModel):
    channelId: str = Field(min_length=1, max_length=80)
    partId: str = Field(min_length=1, max_length=80)
    control: str = Field(min_length=1, max_length=80)


class WokwiGpioBinding(StrictModel):
    channelId: str = Field(min_length=1, max_length=80)
    partId: str = Field(min_length=1, max_length=80)
    pin: str = Field(min_length=1, max_length=40)


class DeviceLabRunStatus(StrEnum):
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


LabValue = float | bool | str


class DeviceLabScenarioResult(StrictModel):
    scenarioId: str = Field(min_length=1, max_length=160)
    passed: bool


class DeviceLabRun(StrictModel):
    id: str
    projectId: str
    boardId: SupportedDeviceBoardId
    target: DeviceLabTarget
    engine: DeviceLabEngine
    status: DeviceLabRunStatus
    applicationId: str | None = None
    parameterSetId: str | None = None
    actuatorArmed: bool = False
    channelValues: dict[str, LabValue]
    revision: int = Field(ge=1)
    startedAt: str
    updatedAt: str
    errorMessage: str | None = None
    revisionBindings: WorkRunRevisionBindings | None = None
    executionRevisionSet: ExecutionRevisionSet | None = None
    wokwiBinding: WokwiRunBindingV1 | None = None
    scenarioResults: list[DeviceLabScenarioResult] = Field(default_factory=list)
    resultPassed: bool | None = None
    resultSummary: str | None = None
    resultIdempotencyKey: str | None = None
    resultRequestHash: str | None = None
    # V29 runs created before project-scene projection remain readable. New runs
    # always persist the exact proposal-derived scene snapshot here.
    scene: DeviceLabSceneV1 | None = None


class CreateDeviceLabRunRequest(StrictModel):
    idempotencyKey: str = Field(
        min_length=8, max_length=160, pattern=r"^[A-Za-z0-9._:-]+$"
    )
    target: DeviceLabTarget = DeviceLabTarget.SIMULATOR
    engine: DeviceLabEngine = DeviceLabEngine.FUNCTIONAL_MODEL
    applicationId: str | None = None
    parameterSetId: str | None = None
    expectedSceneRevision: str | None = Field(
        default=None,
        pattern=r"^[a-f0-9]{64}$",
    )
    expectedSolutionRevisionId: str | None = Field(
        default=None,
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    codeRunId: str | None = Field(
        default=None,
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )


class DeviceLabRunResponse(StrictModel):
    run: DeviceLabRun
    profile: DeviceLabProfileV1


class UpdateDeviceLabChannelRequest(StrictModel):
    value: LabValue
    expectedRevision: int = Field(ge=1)
    actuatorArmed: bool = False
    commandId: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")


class DeviceLabEvent(StrictModel):
    revision: int = Field(ge=1)
    type: Literal["state", "telemetry", "log", "ack", "error"]
    channelId: str | None = None
    value: LabValue | None = None
    message: str
    commandId: str | None = None
    createdAt: str


class ParameterSetRevision(StrictModel):
    id: str
    projectId: str
    boardId: SupportedDeviceBoardId
    profileRevision: str
    revision: int = Field(ge=1)
    label: str
    values: dict[str, LabValue]
    createdAt: str


class SaveParameterSetRequest(StrictModel):
    idempotencyKey: str = Field(
        min_length=8, max_length=160, pattern=r"^[A-Za-z0-9._:-]+$"
    )
    boardId: SupportedDeviceBoardId
    profileRevision: str
    label: str = Field(min_length=1, max_length=100)
    values: dict[str, LabValue]


class ParameterSetListResponse(StrictModel):
    parameterSets: list[ParameterSetRevision]


class ParameterSetResponse(StrictModel):
    parameterSet: ParameterSetRevision


class ApplyParameterSetRequest(StrictModel):
    parameterSetId: str
    expectedRevision: int = Field(ge=1)
