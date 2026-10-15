"""Strict schemas for the Zhangwen-owned simulation project format."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SIMULATION_PROJECT_SCHEMA = "zhangwen.simulation-project/v1"
SIMULATION_CIRCUIT_SCHEMA = "zhangwen.circuit/v1"
SIMULATION_SCENARIO_SCHEMA = "zhangwen.simulation-scenarios/v1"


class SimulationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class SimulationChipFamily(StrEnum):
    ESP32S3 = "esp32s3"
    ESP32C3 = "esp32c3"


class SimulationEngineProfile(StrEnum):
    ZW_MPY_SIM = "ZW-MPY-SIM"


class SimulationDiagnosticSeverity(StrEnum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class CircuitSignalKind(StrEnum):
    POWER = "POWER"
    GROUND = "GROUND"
    DIGITAL = "DIGITAL"
    ANALOG = "ANALOG"
    PWM = "PWM"
    I2C = "I2C"
    UART = "UART"
    UNSPECIFIED = "UNSPECIFIED"


class SimulationLicenseNotice(SimulationModel):
    spdx: str = Field(min_length=1, max_length=120)
    source: str = Field(min_length=1, max_length=1000)
    attribution: str = Field(min_length=1, max_length=1000)


class SimulationBoardPin(SimulationModel):
    id: str = Field(pattern=r"^[A-Za-z0-9._-]+$", max_length=80)
    label: str = Field(min_length=1, max_length=120)
    capabilities: list[str]
    reserved: bool = False
    notes: list[str] = Field(default_factory=list)


class SimulationBoardProfile(SimulationModel):
    revision_id: str = Field(alias="revisionId", min_length=1, max_length=200)
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$", max_length=100)
    display_name: str = Field(alias="displayName", min_length=1, max_length=200)
    chip_family: SimulationChipFamily = Field(alias="chipFamily")
    description: str = Field(min_length=1, max_length=4000)
    pins: list[SimulationBoardPin] = Field(min_length=1)
    known_limitations: list[str] = Field(alias="knownLimitations")
    visual_asset: str = Field(alias="visualAsset", min_length=1, max_length=300)
    license: SimulationLicenseNotice

    @model_validator(mode="after")
    def unique_pins(self) -> SimulationBoardProfile:
        if len({pin.id for pin in self.pins}) != len(self.pins):
            raise ValueError("board pin ids must be unique")
        return self


class SimulationComponentPin(SimulationModel):
    id: str = Field(pattern=r"^[A-Za-z0-9._-]+$", max_length=80)
    label: str = Field(min_length=1, max_length=120)
    role: str = Field(min_length=1, max_length=80)
    required: bool = True


class SimulationComponentProfile(SimulationModel):
    revision_id: str = Field(alias="revisionId", min_length=1, max_length=200)
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$", max_length=100)
    display_name: str = Field(alias="displayName", min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=80)
    protocol: str = Field(min_length=1, max_length=80)
    pins: list[SimulationComponentPin] = Field(min_length=1)
    default_properties: dict[str, str | int | float | bool] = Field(
        alias="defaultProperties", default_factory=dict
    )
    property_schema: dict[str, object] = Field(
        alias="propertySchema", default_factory=dict
    )
    known_limitations: list[str] = Field(alias="knownLimitations")
    visual_asset: str = Field(alias="visualAsset", min_length=1, max_length=300)
    license: SimulationLicenseNotice

    @model_validator(mode="after")
    def unique_pins(self) -> SimulationComponentProfile:
        if len({pin.id for pin in self.pins}) != len(self.pins):
            raise ValueError("component pin ids must be unique")
        return self


class SimulationCatalogView(SimulationModel):
    boards: list[SimulationBoardProfile]
    components: list[SimulationComponentProfile]


class CircuitPoint(SimulationModel):
    x: float = Field(ge=-10000, le=10000)
    y: float = Field(ge=-10000, le=10000)


class CircuitBoardInstance(SimulationModel):
    id: str = Field(default="board", pattern=r"^[A-Za-z][A-Za-z0-9._-]*$")
    board_package_revision_id: str = Field(alias="boardPackageRevisionId")
    position: CircuitPoint
    rotation: Literal[0, 90, 180, 270] = 0
    properties: dict[str, str | int | float | bool] = Field(default_factory=dict)


class CircuitPartInstance(SimulationModel):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9._-]*$", max_length=100)
    component_package_revision_id: str = Field(alias="componentPackageRevisionId")
    position: CircuitPoint
    rotation: Literal[0, 90, 180, 270] = 0
    properties: dict[str, str | int | float | bool] = Field(default_factory=dict)
    read_only: bool = Field(alias="readOnly", default=False)


class CircuitEndpoint(SimulationModel):
    instance_id: str = Field(alias="instanceId", min_length=1, max_length=100)
    pin_id: str = Field(alias="pinId", min_length=1, max_length=80)


class CircuitNet(SimulationModel):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9._-]*$", max_length=100)
    endpoints: list[CircuitEndpoint] = Field(min_length=2, max_length=64)
    signal_kind: CircuitSignalKind = Field(
        alias="signalKind", default=CircuitSignalKind.UNSPECIFIED
    )
    label: str = Field(default="", max_length=200)
    color: str = Field(default="#0f766e", pattern=r"^#[0-9A-Fa-f]{6}$")
    route: list[CircuitPoint] = Field(default_factory=list, max_length=200)


class CircuitAnnotation(SimulationModel):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9._-]*$", max_length=100)
    text: str = Field(min_length=1, max_length=2000)
    position: CircuitPoint


class CircuitSourceCompatibility(SimulationModel):
    kind: Literal["WOKWI_DIAGRAM_V1"] = "WOKWI_DIAGRAM_V1"
    source_digest: str = Field(alias="sourceDigest", pattern=r"^[0-9a-f]{64}$")
    adapter_revision: str = Field(alias="adapterRevision", min_length=1, max_length=80)
    unknown_part_types: list[str] = Field(alias="unknownPartTypes", default_factory=list)


class CircuitDraftV1(SimulationModel):
    schema_id: Literal["zhangwen.circuit/v1"] = Field(
        alias="schema", default=SIMULATION_CIRCUIT_SCHEMA
    )
    board_instance: CircuitBoardInstance = Field(alias="boardInstance")
    parts: list[CircuitPartInstance] = Field(default_factory=list, max_length=256)
    nets: list[CircuitNet] = Field(default_factory=list, max_length=512)
    annotations: list[CircuitAnnotation] = Field(default_factory=list, max_length=256)
    source_compatibility: CircuitSourceCompatibility | None = Field(
        alias="sourceCompatibility", default=None
    )

    @property
    def schema(self) -> str:
        return self.schema_id

    @model_validator(mode="after")
    def unique_ids(self) -> CircuitDraftV1:
        instance_ids = [self.board_instance.id, *(part.id for part in self.parts)]
        if len(set(instance_ids)) != len(instance_ids):
            raise ValueError("circuit instance ids must be unique")
        if len({net.id for net in self.nets}) != len(self.nets):
            raise ValueError("circuit net ids must be unique")
        if len({item.id for item in self.annotations}) != len(self.annotations):
            raise ValueError("circuit annotation ids must be unique")
        return self


class SimulationCodeFile(SimulationModel):
    path: str = Field(min_length=1, max_length=240)
    content: str = Field(max_length=256_000)

    @field_validator("path")
    @classmethod
    def safe_relative_path(cls, value: str) -> str:
        normalized = value.replace("\\", "/")
        if (
            normalized.startswith("/")
            or ":" in normalized
            or any(part in {"", ".", ".."} for part in normalized.split("/"))
        ):
            raise ValueError("code path must be a normalized relative path")
        return normalized


class SimulationCodeBundleDraft(SimulationModel):
    files: list[SimulationCodeFile] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_files(self) -> SimulationCodeBundleDraft:
        paths = [item.path for item in self.files]
        if len(set(paths)) != len(paths):
            raise ValueError("code file paths must be unique")
        if "main.py" not in paths:
            raise ValueError("code bundle must contain main.py")
        if sum(len(item.content.encode("utf-8")) for item in self.files) > 1_000_000:
            raise ValueError("code bundle is too large")
        return self


class SimulationScenarioAction(SimulationModel):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9._-]*$", max_length=100)
    at_ms: int = Field(alias="atMs", ge=0, le=3_600_000)
    target: str = Field(min_length=1, max_length=200)
    value: str | int | float | bool


class SimulationScenarioAssertion(SimulationModel):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9._-]*$", max_length=100)
    at_ms: int = Field(alias="atMs", ge=0, le=3_600_000)
    target: str = Field(min_length=1, max_length=200)
    operator: Literal["EQUALS", "CONTAINS", "BETWEEN"]
    expected: str | int | float | bool | list[float]
    tolerance: float | None = Field(default=None, ge=0)


class SimulationScenario(SimulationModel):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9._-]*$", max_length=100)
    title: str = Field(min_length=1, max_length=240)
    required: bool = True
    seed: int = Field(ge=0, le=2**32 - 1)
    timeout_ms: int = Field(alias="timeoutMs", ge=1, le=3_600_000)
    max_events: int = Field(alias="maxEvents", ge=1, le=1_000_000)
    actions: list[SimulationScenarioAction] = Field(default_factory=list, max_length=1000)
    assertions: list[SimulationScenarioAssertion] = Field(
        default_factory=list, max_length=1000
    )
    reflection_prompt: str = Field(alias="reflectionPrompt", default="", max_length=2000)


class SimulationScenarioSuiteDraft(SimulationModel):
    schema_id: Literal["zhangwen.simulation-scenarios/v1"] = Field(
        alias="schema", default=SIMULATION_SCENARIO_SCHEMA
    )
    scenarios: list[SimulationScenario] = Field(default_factory=list, max_length=100)

    @property
    def schema(self) -> str:
        return self.schema_id

    @model_validator(mode="after")
    def unique_scenarios(self) -> SimulationScenarioSuiteDraft:
        if len({item.id for item in self.scenarios}) != len(self.scenarios):
            raise ValueError("scenario ids must be unique")
        return self


class SimulationProjectDraft(SimulationModel):
    schema_id: Literal["zhangwen.simulation-project/v1"] = Field(
        alias="schema", default=SIMULATION_PROJECT_SCHEMA
    )
    source_proposal_revision_id: str = Field(alias="sourceProposalRevisionId")
    board_package_revision_id: str = Field(alias="boardPackageRevisionId")
    runtime_package_revision_id: str = Field(alias="runtimePackageRevisionId")
    component_package_revision_ids: list[str] = Field(
        alias="componentPackageRevisionIds", default_factory=list
    )
    circuit: CircuitDraftV1
    code_bundle: SimulationCodeBundleDraft = Field(alias="codeBundle")
    scenario_suite: SimulationScenarioSuiteDraft = Field(alias="scenarioSuite")
    engine_profile: SimulationEngineProfile = Field(
        alias="engineProfile", default=SimulationEngineProfile.ZW_MPY_SIM
    )

    @property
    def schema(self) -> str:
        return self.schema_id

    @model_validator(mode="after")
    def linked_revisions_match(self) -> SimulationProjectDraft:
        if (
            self.circuit.board_instance.board_package_revision_id
            != self.board_package_revision_id
        ):
            raise ValueError("circuit board revision must match simulation project")
        return self


class SimulationStaticDiagnostic(SimulationModel):
    severity: SimulationDiagnosticSeverity
    code: str
    message: str
    target_id: str | None = Field(alias="targetId", default=None)


class SimulationStaticCompilation(SimulationModel):
    runnable: bool
    circuit_digest: str = Field(alias="circuitDigest")
    diagnostics: list[SimulationStaticDiagnostic]


class SimulationProjectRevision(SimulationProjectDraft):
    id: str
    work_id: str = Field(alias="workId")
    revision: int = Field(ge=1)
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    circuit_revision_id: str = Field(alias="circuitRevisionId")
    circuit_digest: str = Field(alias="circuitDigest", pattern=r"^[0-9a-f]{64}$")
    code_bundle_revision_id: str = Field(alias="codeBundleRevisionId")
    code_bundle_digest: str = Field(alias="codeBundleDigest", pattern=r"^[0-9a-f]{64}$")
    scenario_suite_revision_id: str = Field(alias="scenarioSuiteRevisionId")
    scenario_suite_digest: str = Field(
        alias="scenarioSuiteDigest", pattern=r"^[0-9a-f]{64}$"
    )
    supersedes_revision_id: str | None = Field(alias="supersedesRevisionId")
    created_by: str = Field(alias="createdBy")
    created_at: str = Field(alias="createdAt")


class SimulationWorkspace(SimulationModel):
    draft: SimulationProjectDraft | None
    draft_revision: int = Field(alias="draftRevision", ge=0)
    current: SimulationProjectRevision | None
    revisions: list[SimulationProjectRevision]
    catalog: SimulationCatalogView
    compilation: SimulationStaticCompilation
    can_edit: bool = Field(alias="canEdit")
