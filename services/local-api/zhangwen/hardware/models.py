"""Hardware component Pydantic boundary models."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class HardwareCategory(StrEnum):
    MCU = "MCU"
    SENSOR = "SENSOR"
    ACTUATOR = "ACTUATOR"
    DISPLAY = "DISPLAY"
    POWER = "POWER"
    STRUCTURE = "STRUCTURE"


class HardwareComponentStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class HardwareSkillStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    INVALID = "INVALID"


class HardwareSkillSourceKind(StrEnum):
    BUNDLED = "BUNDLED"
    MIGRATED = "MIGRATED"
    UPLOAD = "UPLOAD"
    DIALOGUE = "DIALOGUE"
    MANUAL = "MANUAL"


class HardwareRuleOperator(StrEnum):
    RANGE_OVERLAP = "range-overlap"
    SUM_LTE = "sum-lte"
    UNIQUE = "unique"
    CONTAINS_ANY = "contains-any"
    REQUIRED_IF = "required-if"


class ValidationSeverity(StrEnum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


class HardwareMediaAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    role: Literal["cover", "gallery"]
    alt: str = Field(..., min_length=1, max_length=160)
    contentType: Literal["image/jpeg", "image/png", "image/webp"]
    sha256: str = Field(..., pattern=r"^[a-f0-9]{64}$")
    sourceUrl: str = Field(..., min_length=1, max_length=2048)
    attribution: str = Field(..., min_length=1, max_length=200)
    license: str = Field(..., min_length=1, max_length=500)
    url: str = ""


class ElectricalProps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    voltage: float = Field(..., ge=0)
    voltageMin: float | None = Field(default=None, ge=0)
    voltageMax: float | None = Field(default=None, ge=0)
    supplyVoltages: list[float] = Field(default_factory=list, max_length=8)
    logicLevel: float = Field(..., ge=0)
    peakCurrent: float = Field(..., ge=0)
    communicationProtocol: str = Field(default="GPIO", min_length=1, max_length=100)
    i2cAddress: Optional[str] = None
    supportedMCUs: list[str] = Field(default_factory=list)
    driverName: Optional[str] = None
    firmwareRequirement: Optional[str] = None

    @field_validator("supplyVoltages")
    @classmethod
    def normalize_supply_voltages(cls, values: list[float]) -> list[float]:
        if any(value <= 0 for value in values):
            raise ValueError("外设电源轨必须大于 0V。")
        return sorted(set(values))

    @model_validator(mode="after")
    def validate_voltage_range(self) -> ElectricalProps:
        minimum = self.voltage if self.voltageMin is None else self.voltageMin
        maximum = self.voltage if self.voltageMax is None else self.voltageMax
        if minimum > maximum:
            raise ValueError("voltageMin 不能大于 voltageMax。")
        if not minimum <= self.voltage <= maximum:
            raise ValueError("推荐 voltage 必须位于 voltageMin/voltageMax 范围内。")
        return self


class HardwareComponent(BaseModel):
    id: str
    name: str
    category: HardwareCategory
    status: HardwareComponentStatus
    electrical: ElectricalProps
    stock: int = 0
    price: float = 0.0
    ageRecommendation: Optional[int] = None
    safetyTags: list[str] = Field(default_factory=list)
    notes: str = ""
    createdAt: str
    updatedAt: str
    skillName: str = ""
    skillRevision: str = ""
    verificationStatus: str = "UNVERIFIED"
    media: list[HardwareMediaAsset] = Field(default_factory=list)


class CreateComponentRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    category: HardwareCategory
    electrical: ElectricalProps
    stock: int = Field(default=0, ge=0)
    price: float = Field(default=0.0, ge=0.0)
    ageRecommendation: Optional[int] = Field(default=None, ge=0)
    safetyTags: list[str] = Field(default_factory=list)
    notes: str = ""


class UpdateComponentRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    category: Optional[HardwareCategory] = None
    electrical: Optional[ElectricalProps] = None
    stock: Optional[int] = Field(default=None, ge=0)
    price: Optional[float] = Field(default=None, ge=0.0)
    ageRecommendation: Optional[int] = Field(default=None, ge=0)
    safetyTags: Optional[list[str]] = None
    notes: Optional[str] = None


class ComponentListResponse(BaseModel):
    components: list[HardwareComponent]


class ComponentResponse(BaseModel):
    component: HardwareComponent


class HardwareComponentPackageFile(BaseModel):
    path: str
    title: str
    kind: Literal["entry", "reference"]
    content: str
    overridden: bool = False


class HardwareComponentPackageDetail(BaseModel):
    componentId: str = Field(
        ...,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$",
    )
    componentName: str
    revision: str
    files: list[HardwareComponentPackageFile]


class HardwareComponentPackageResponse(BaseModel):
    package: HardwareComponentPackageDetail


class UpdateHardwareComponentPackageFileRequest(BaseModel):
    path: str
    content: str
    expectedRevision: str


class HardwareSkillDiagnostic(BaseModel):
    path: str
    code: str
    message: str
    severity: Literal["warning", "error"]


class HardwareSkillFile(BaseModel):
    path: str
    title: str
    kind: Literal["entry", "reference", "model", "example", "test"]
    content: str
    editable: bool = True


class HardwareSkillSpecification(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    schema_: Literal["zhangwen.hardware-skill/v1"] = Field(
        default="zhangwen.hardware-skill/v1",
        alias="schema",
    )
    componentId: str
    name: str = Field(..., min_length=1, max_length=100)
    category: HardwareCategory
    electrical: ElectricalProps
    stock: int = Field(default=0, ge=0)
    price: float = Field(default=0.0, ge=0.0)
    ageRecommendation: Optional[int] = Field(default=None, ge=0)
    safetyTags: list[str] = Field(default_factory=list)
    notes: str = ""
    verificationStatus: str = Field(default="UNVERIFIED", min_length=1, max_length=100)
    sourceIds: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name 不能为空。")
        return normalized


class HardwareSkillRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1, max_length=100)
    operator: HardwareRuleOperator
    severity: ValidationSeverity
    message: str = Field(..., min_length=1, max_length=500)
    params: dict[str, Any]


class HardwareSkillSummary(BaseModel):
    skillName: str
    componentId: str
    displayName: str
    description: str
    category: HardwareCategory
    status: HardwareSkillStatus
    sourceKind: HardwareSkillSourceKind
    revision: str
    verificationStatus: str
    updatedAt: str
    diagnostics: list[HardwareSkillDiagnostic] = Field(default_factory=list)
    media: list[HardwareMediaAsset] = Field(default_factory=list)


class HardwareSkillDetail(HardwareSkillSummary):
    files: list[HardwareSkillFile]
    specification: HardwareSkillSpecification
    rules: list[HardwareSkillRule]
    mechanicalProfile: dict[str, Any] | None = None


class HardwareSkillListResponse(BaseModel):
    skills: list[HardwareSkillSummary]


class HardwareCatalogRefreshResponse(BaseModel):
    skills: list[HardwareSkillSummary]
    refreshedAt: str


class HardwareSkillResponse(BaseModel):
    skill: HardwareSkillDetail


class UpdateHardwareSkillFileRequest(BaseModel):
    path: str
    content: str
    expectedRevision: str


class HardwareSkillFileUpdate(BaseModel):
    path: str
    content: str


class UpdateHardwareSkillFilesRequest(BaseModel):
    updates: list[HardwareSkillFileUpdate] = Field(min_length=1, max_length=8)
    expectedRevision: str


class HardwareSkillDraftSource(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    mediaType: str = Field(..., min_length=1, max_length=100)
    content: str


class HardwareSkillDraft(BaseModel):
    id: str
    status: Literal["DRAFT"] = "DRAFT"
    revision: str
    sources: list[dict[str, str]]
    files: list[HardwareSkillFile]
    specification: Optional[HardwareSkillSpecification]
    rules: list[HardwareSkillRule]
    missingQuestions: list[str]
    diagnostics: list[HardwareSkillDiagnostic]
    canConfirm: bool


class HardwareSkillDraftResponse(BaseModel):
    draft: HardwareSkillDraft


class CreateHardwareSkillDraftRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = Field(default=None, max_length=4_000)
    sources: list[HardwareSkillDraftSource] = Field(default_factory=list, max_length=8)


class ContinueHardwareSkillDraftRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=40_000)
    expectedRevision: str = Field(..., min_length=1, max_length=128)


class ConfirmHardwareSkillDraftRequest(BaseModel):
    expectedRevision: str = Field(..., min_length=1, max_length=128)


class ValidationCheck(BaseModel):
    dimension: str
    severity: ValidationSeverity
    message: str
    details: str


class ValidationResult(BaseModel):
    checks: list[ValidationCheck]
    overall: ValidationSeverity
    message: str


class ValidateCombinationRequest(BaseModel):
    componentIds: list[str]


class ValidateCombinationResponse(BaseModel):
    result: ValidationResult
