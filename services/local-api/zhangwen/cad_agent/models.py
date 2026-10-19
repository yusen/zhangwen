"""CAD Agent boundary models."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from zhangwen.cad_agent.profile_repository import MechanicalProfileSnapshot
from zhangwen.cad_engine.models import DeclarativeGeometry


class CadTemplateKind(StrEnum):
    COMPONENT_MOUNT = "COMPONENT_MOUNT"
    FREEFORM_STRUCTURE = "FREEFORM_STRUCTURE"
    UNIHIKER_K10_PHOTO_ALBUM = "UNIHIKER_K10_PHOTO_ALBUM"
    SENSOR_BRACKET = "SENSOR_BRACKET"
    MCU_MOUNT = "MCU_MOUNT"
    MOTOR_MOUNT = "MOTOR_MOUNT"
    SERVO_MOUNT = "SERVO_MOUNT"
    SIMPLE_ENCLOSURE = "SIMPLE_ENCLOSURE"
    PANEL_CUTOUT = "PANEL_CUTOUT"
    BOX_WITH_LID = "BOX_WITH_LID"


SUPPORTED_TEMPLATE_REVISIONS: dict[CadTemplateKind, str] = {
    CadTemplateKind.COMPONENT_MOUNT: "component-mount.v1",
    CadTemplateKind.FREEFORM_STRUCTURE: "freeform-structure.v1",
    CadTemplateKind.UNIHIKER_K10_PHOTO_ALBUM: "unihiker-k10-photo-album.v1",
    CadTemplateKind.BOX_WITH_LID: "box-with-lid.v1",
}


class CadFileKind(StrEnum):
    STEP = "STEP"
    STL = "STL"
    PARAMETERS = "PARAMETERS"


class CadJobStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELED = "CANCELED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    INTERRUPTED = "INTERRUPTED"


class CadJobPhase(StrEnum):
    QUEUED = "QUEUED"
    VALIDATING = "VALIDATING"
    RESOLVING_PROFILES = "RESOLVING_PROFILES"
    LAYOUT = "LAYOUT"
    BUILDING = "BUILDING"
    EXPORTING = "EXPORTING"
    VALIDATING_OUTPUTS = "VALIDATING_OUTPUTS"
    STORING_ARTIFACTS = "STORING_ARTIFACTS"
    COMPLETED = "COMPLETED"
    CANCELED = "CANCELED"
    FAILED = "FAILED"


class CadOutputRole(StrEnum):
    STEP_ASSEMBLY = "STEP_ASSEMBLY"
    STEP_PRINTABLE_PARTS = "STEP_PRINTABLE_PARTS"
    STL_PRINTABLE_PARTS = "STL_PRINTABLE_PARTS"
    GLB_PREVIEW = "GLB_PREVIEW"
    PARAMETERS = "PARAMETERS"
    PROFILE_SNAPSHOTS = "PROFILE_SNAPSHOTS"
    VALIDATION_REPORT = "VALIDATION_REPORT"
    GEOMETRY_SUMMARY = "GEOMETRY_SUMMARY"
    MANIFEST = "MANIFEST"


class CadMountSurface(StrEnum):
    BASE_FLOOR = "base_floor"
    LID_INNER = "lid_inner"
    LID_OUTER = "lid_outer"
    FRONT_INNER = "front_inner"
    BACK_INNER = "back_inner"
    LEFT_INNER = "left_inner"
    RIGHT_INNER = "right_inner"
    EXTERNAL = "external"


class CadRunStatus(StrEnum):
    DRAFT = "DRAFT"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    VALIDATED = "VALIDATED"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    STALE = "STALE"
    CANCELED = "CANCELED"
    FAILED = "FAILED"


class CadOutputFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    relativePath: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,159}$")
    fileName: str = Field(min_length=1, max_length=160)
    role: CadOutputRole
    mimeType: str = Field(min_length=1, max_length=120)
    byteSize: int = Field(ge=0, le=128 * 1024 * 1024)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    triangleCount: int | None = Field(default=None, ge=0)
    bounds: dict[str, float] | None = None


class CadWorkerManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schemaVersion: Literal["1.0"]
    engineId: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    engineVersion: str = Field(min_length=1, max_length=160)
    designId: str = Field(min_length=1, max_length=120)
    specSha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    files: list[CadOutputFile] = Field(min_length=1, max_length=12)


class CadWorkerResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest: CadWorkerManifest
    validation: dict[str, Any]
    geometrySummary: dict[str, Any]


class CadJobFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    role: CadOutputRole
    fileName: str
    mimeType: str
    byteSize: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    triangleCount: int | None = Field(default=None, ge=0)
    bounds: dict[str, float] | None = None


class CadJobManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schemaVersion: Literal["1.0"]
    engineId: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    engineVersion: str = Field(min_length=1, max_length=160)
    designId: str = Field(min_length=1, max_length=120)
    specSha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CadJobResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest: CadJobManifest
    files: list[CadJobFile] = Field(min_length=1, max_length=12)
    validation: dict[str, Any]
    geometrySummary: dict[str, Any]


class CadParameter(BaseModel):
    name: str
    label: str
    unit: str = Field(pattern="^(mm|count)$")
    value: float
    min: float
    max: float


class CadValidationCheck(BaseModel):
    dimension: str
    severity: str = Field(pattern="^(PASS|WARNING|FAIL)$")
    message: str
    details: str


class CadValidation(BaseModel):
    ok: bool
    checks: list[CadValidationCheck]


class CadDesignDraft(BaseModel):
    """Allowed template and numeric parameters selected by the cloud model."""

    model_config = ConfigDict(extra="forbid")

    templateKind: CadTemplateKind
    parameters: dict[str, float] = Field(min_length=1, max_length=32)
    rationale: str = Field(min_length=1, max_length=1000)


class CadVector3(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float
    y: float
    z: float


class CadComponentDraft(BaseModel):
    """A component placement without executable model or filesystem fields."""

    model_config = ConfigDict(extra="forbid")

    instanceId: str = Field(min_length=1, max_length=120)
    hardwareId: str | None = Field(default=None, min_length=1, max_length=120)
    profileId: str | None = Field(default=None, min_length=1, max_length=120)
    mountSurface: CadMountSurface | None = None
    rotationDeg: float = Field(default=0, ge=-360, le=360)
    offsetMm: CadVector3 | None = None


class CadResolvedComponent(CadComponentDraft):
    """Component identity resolved from a confirmed hardware/profile link."""

    model_config = ConfigDict(extra="forbid")

    hardwareId: str = Field(min_length=1, max_length=120)
    profileId: str = Field(min_length=1, max_length=120)
    resolvedProfileId: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,119}$")
    resolvedProfileRevision: str = Field(min_length=1, max_length=160)
    resolvedProfileSha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def _reject_executable_keys(value: Any) -> Any:
    """Reject executable, path and network selectors at every nested boundary."""

    forbidden = {
        "args",
        "cadquerycode",
        "code",
        "command",
        "entrypoint",
        "env",
        "filepath",
        "module",
        "outputpath",
        "path",
        "python",
        "pythoncode",
        "script",
        "scriptpath",
        "sourcepath",
        "url",
    }
    if isinstance(value, dict):
        for key, child in value.items():
            normalized_key = "".join(
                character for character in str(key) if character.isalnum()
            ).lower()
            if normalized_key in forbidden:
                raise ValueError(f"CAD 字段 {key} 不允许由调用方提供。")
            _reject_executable_keys(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _reject_executable_keys(child)
    return value


class CadDraft(BaseModel):
    """Strict declaration emitted by the structure engineer."""

    model_config = ConfigDict(extra="forbid")

    specRunId: str | None = Field(default=None, min_length=1, max_length=120)
    intakeSnapshotSha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    templateKind: CadTemplateKind
    templateRevision: str | None = Field(default=None, min_length=1, max_length=160)
    parameters: dict[str, float] = Field(default_factory=dict, max_length=32)
    components: list[CadComponentDraft] = Field(default_factory=list, max_length=64)
    geometry: DeclarativeGeometry | None = None
    constraints: dict[str, float | int | str | bool] = Field(
        default_factory=dict, max_length=32
    )
    summary: str = Field(min_length=1, max_length=2000)
    requestedOutputs: list[CadOutputRole] = Field(default_factory=list, max_length=12)

    @model_validator(mode="before")
    @classmethod
    def _validate_safe_values(cls, value: Any) -> Any:
        return _reject_executable_keys(value)

    @model_validator(mode="after")
    def _validate_template_geometry(self) -> "CadDraft":
        if self.templateKind is CadTemplateKind.FREEFORM_STRUCTURE:
            if self.geometry is None:
                raise ValueError("FREEFORM_STRUCTURE requires declarative geometry")
            if self.components or self.parameters:
                raise ValueError("FREEFORM_STRUCTURE cannot include hardware or template parameters")
        elif self.templateKind is CadTemplateKind.UNIHIKER_K10_PHOTO_ALBUM:
            if self.parameters:
                raise ValueError("UNIHIKER_K10_PHOTO_ALBUM cannot include parameters")
            if self.components:
                raise ValueError("UNIHIKER_K10_PHOTO_ALBUM cannot include components")
            if self.geometry is not None:
                raise ValueError("UNIHIKER_K10_PHOTO_ALBUM uses local fixed geometry")
        elif self.geometry is not None:
            raise ValueError("declarative geometry is available only to FREEFORM_STRUCTURE")
        return self


class CadBuildSpec(CadDraft):
    """Server-materialized immutable specification consumed by a CAD worker."""

    model_config = ConfigDict(extra="forbid")

    jobId: str = Field(min_length=1, max_length=120)
    projectId: str = Field(min_length=1, max_length=120)
    templateRevision: str = Field(min_length=1, max_length=160)
    components: list[CadResolvedComponent] = Field(default_factory=list, max_length=64)
    profileSnapshots: list[MechanicalProfileSnapshot] = Field(
        default_factory=list,
        max_length=64,
    )
    sizingEvidence: "CadSizingEvidence | None" = None

    @model_validator(mode="before")
    @classmethod
    def _validate_safe_values(cls, value: Any) -> Any:
        return _reject_executable_keys(value)


class CadSizingEvidence(BaseModel):
    """Server-owned evidence for resolved enclosure dimensions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: Literal["AUTO", "MIXED", "EXPLICIT"]
    requiredParameters: dict[Literal["width", "height", "depth"], float]
    autoResolvedParameters: list[Literal["width", "height", "depth"]] = Field(
        default_factory=list,
        max_length=3,
    )


class CadJobError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=2000)
    retryable: bool = False


class CadJob(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    projectId: str
    cadRunId: str
    clientRequestId: str | None = None
    status: CadJobStatus
    phase: CadJobPhase
    progress: int = Field(ge=0, le=100)
    sourceMessageId: str | None = None
    projectExpertId: str | None = None
    specRunId: str | None = None
    requestHash: str
    request: CadBuildSpec
    result: CadJobResult | None = None
    error: CadJobError | None = None
    createdAt: str
    startedAt: str | None = None
    completedAt: str | None = None


class CadFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    cadRunId: str
    projectId: str
    kind: CadFileKind | None = None
    role: CadOutputRole | None = None
    path: str = ""
    fileName: str = ""
    artifactFileId: str | None = None
    storageKey: str | None = None
    mimeType: str
    content: str | None = None
    byteSize: int = Field(default=0, ge=0)
    sha256: str | None = None
    bounds: dict[str, Any] | None = None
    triangleCount: int | None = Field(default=None, ge=0)
    artifactId: str | None = None
    artifactVersionId: str | None = None
    createdAt: str


class CadRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    projectId: str
    specRunId: str | None = None
    templateKind: CadTemplateKind
    version: int
    status: CadRunStatus
    commandLabel: str
    parameters: list[CadParameter]
    validation: CadValidation
    files: list[CadFile]
    artifactId: str | None = None
    artifactVersionId: str | None = None
    sourceMessageId: str | None = None
    generatedByExpertId: str | None = None
    engineId: str = "template-dry-run"
    engineVersion: str | None = None
    designState: dict[str, Any] | None = None
    latestJob: CadJob | None = None
    staleReason: str | None = None
    createdAt: str
    updatedAt: str
    confirmedAt: str | None = None


class CadRunResponse(BaseModel):
    cadRun: CadRun


class GenerateCadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    specRunId: str
    templateKind: CadTemplateKind | None = None
    parameters: dict[str, float] | None = None


class ConfirmCadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cadRunId: str


class RejectCadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cadRunId: str
    reason: str | None = Field(default=None, max_length=1000)
