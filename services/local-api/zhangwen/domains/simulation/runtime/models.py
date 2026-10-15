"""Strict contracts for the ZW-MPY-SIM runtime package and worker protocol."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from zhangwen.domains.simulation.models import (
    CircuitDraftV1,
    SimulationCodeBundleDraft,
    SimulationModel,
    SimulationScenarioAction,
)


RUNTIME_MANIFEST_SCHEMA = "zhangwen.simulation-runtime-manifest/v1"
RUNTIME_STATUS_SCHEMA = "zhangwen.simulation-runtime-status/v1"
RUNTIME_REQUEST_SCHEMA = "zhangwen.simulation-runtime-request/v1"
RUNTIME_RESULT_SCHEMA = "zhangwen.simulation-runtime-result/v1"
RUNTIME_WORKER_PROTOCOL = "zhangwen.micropython-worker/v1"


class RuntimeEngineMode(StrEnum):
    NATIVE_MICROPYTHON = "NATIVE_MICROPYTHON"
    BEHAVIORAL_REFERENCE = "BEHAVIORAL_REFERENCE"


class RuntimeExecutionStatus(StrEnum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    CANCELED = "CANCELED"
    CRASHED = "CRASHED"


class NativeCoreState(StrEnum):
    VERIFIED = "VERIFIED"
    NOT_PROVISIONED = "NOT_PROVISIONED"
    MISSING = "MISSING"
    INTEGRITY_FAILED = "INTEGRITY_FAILED"
    PLATFORM_UNSUPPORTED = "PLATFORM_UNSUPPORTED"


class MicroPythonSourcePin(SimulationModel):
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    upstream_tag: str = Field(alias="upstreamTag", min_length=1, max_length=80)
    upstream_commit: str = Field(
        alias="upstreamCommit", pattern=r"^[0-9a-f]{40}$"
    )
    source_archive_url: str = Field(alias="sourceArchiveUrl", min_length=1)
    source_archive_sha256: str = Field(
        alias="sourceArchiveSha256", pattern=r"^[0-9a-f]{64}$"
    )
    license_spdx: Literal["MIT"] = Field(alias="licenseSpdx")
    host_port: Literal["ports/windows"] = Field(alias="hostPort")
    upstream_host_port_status: Literal["EXPERIMENTAL_COMMUNITY_SUPPORTED"] = Field(
        alias="upstreamHostPortStatus"
    )


class NativeRuntimeDistribution(SimulationModel):
    platform: str = Field(min_length=1, max_length=80)
    relative_path: str = Field(alias="relativePath", min_length=1, max_length=240)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    worker_protocol: Literal["zhangwen.micropython-worker/v1"] = Field(
        alias="workerProtocol"
    )


class BehavioralReferenceDescriptor(SimulationModel):
    implementation: Literal["restricted-cpython-reference/v1"]
    worker_protocol: Literal["zhangwen.micropython-worker/v1"] = Field(
        alias="workerProtocol"
    )
    evidence_eligible: Literal[False] = Field(alias="evidenceEligible")
    purpose: str = Field(min_length=1, max_length=1000)


class RuntimeQuotaEnvelope(SimulationModel):
    wall_timeout_ms: int = Field(alias="wallTimeoutMs", ge=100, le=10_000)
    max_virtual_time_us: int = Field(
        alias="maxVirtualTimeUs", ge=1_000, le=3_600_000_000
    )
    max_instructions: int = Field(alias="maxInstructions", ge=100, le=2_000_000)
    max_events: int = Field(alias="maxEvents", ge=1, le=100_000)
    max_output_bytes: int = Field(alias="maxOutputBytes", ge=128, le=1_000_000)
    max_heap_bytes: int = Field(alias="maxHeapBytes", ge=1_000_000, le=64_000_000)


class SimulationRuntimeManifest(SimulationModel):
    schema_id: Literal["zhangwen.simulation-runtime-manifest/v1"] = Field(
        alias="schema"
    )
    revision_id: Literal["runtime/zw-mpy-sim@1"] = Field(alias="revisionId")
    worker_protocol: Literal["zhangwen.micropython-worker/v1"] = Field(
        alias="workerProtocol"
    )
    host_patch_revision: Literal["zhangwen-micropython-host/v1"] = Field(
        alias="hostPatchRevision"
    )
    micropython: MicroPythonSourcePin
    native_distributions: list[NativeRuntimeDistribution] = Field(
        alias="nativeDistributions"
    )
    behavioral_reference: BehavioralReferenceDescriptor = Field(
        alias="behavioralReference"
    )
    supported_apis: list[str] = Field(alias="supportedApis", min_length=1)
    supported_components: list[str] = Field(
        alias="supportedComponents", min_length=1
    )
    explicitly_unsupported: list[str] = Field(
        alias="explicitlyUnsupported", min_length=1
    )
    default_limits: RuntimeQuotaEnvelope = Field(alias="defaultLimits")
    maximum_limits: RuntimeQuotaEnvelope = Field(alias="maximumLimits")
    license_notice_paths: list[str] = Field(alias="licenseNoticePaths", min_length=1)


class NativeCoreVerification(SimulationModel):
    status: NativeCoreState
    verified: bool
    platform: str
    relative_path: str | None = Field(alias="relativePath")
    expected_sha256: str | None = Field(alias="expectedSha256")
    actual_sha256: str | None = Field(alias="actualSha256")
    message: str


class SimulationRuntimeStatus(SimulationModel):
    schema_id: Literal["zhangwen.simulation-runtime-status/v1"] = Field(
        alias="schema", default=RUNTIME_STATUS_SCHEMA
    )
    runtime_package_revision_id: Literal["runtime/zw-mpy-sim@1"] = Field(
        alias="runtimePackageRevisionId"
    )
    micropython_version: str = Field(alias="micropythonVersion")
    upstream_commit: str = Field(alias="upstreamCommit")
    worker_protocol: str = Field(alias="workerProtocol")
    native_core: NativeCoreVerification = Field(alias="nativeCore")
    behavioral_reference_available: bool = Field(
        alias="behavioralReferenceAvailable"
    )
    behavioral_reference_evidence_eligible: Literal[False] = Field(
        alias="behavioralReferenceEvidenceEligible"
    )
    supported_apis: list[str] = Field(alias="supportedApis")
    supported_components: list[str] = Field(alias="supportedComponents")
    explicitly_unsupported: list[str] = Field(alias="explicitlyUnsupported")
    known_limitations: list[str] = Field(alias="knownLimitations")

    @property
    def schema(self) -> str:
        return self.schema_id

class RuntimeResourceLimits(RuntimeQuotaEnvelope):
    pass


class RuntimeExecutionRequest(SimulationModel):
    schema_id: Literal["zhangwen.simulation-runtime-request/v1"] = Field(
        alias="schema", default=RUNTIME_REQUEST_SCHEMA
    )
    engine_mode: RuntimeEngineMode = Field(alias="engineMode")
    board_package_revision_id: str = Field(alias="boardPackageRevisionId")
    runtime_package_revision_id: Literal["runtime/zw-mpy-sim@1"] = Field(
        alias="runtimePackageRevisionId"
    )
    circuit: CircuitDraftV1
    code_bundle: SimulationCodeBundleDraft = Field(alias="codeBundle")
    seed: int = Field(ge=0, le=2**32 - 1)
    limits: RuntimeResourceLimits
    uart_inputs: dict[str, str] = Field(alias="uartInputs", default_factory=dict)
    scenario_actions: list[SimulationScenarioAction] = Field(
        alias="scenarioActions", default_factory=list, max_length=1000
    )

    @model_validator(mode="after")
    def revisions_match(self) -> RuntimeExecutionRequest:
        if (
            self.circuit.board_instance.board_package_revision_id
            != self.board_package_revision_id
        ):
            raise ValueError("runtime circuit board revision must match request")
        return self

    @property
    def schema(self) -> str:
        return self.schema_id


class RuntimeErrorDetail(SimulationModel):
    code: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=1000)
    retryable: bool = False


class RuntimeEvent(SimulationModel):
    sequence: int = Field(ge=1)
    virtual_time_us: int = Field(alias="virtualTimeUs", ge=0)
    kind: str = Field(min_length=1, max_length=100)
    source: str = Field(min_length=1, max_length=160)
    payload: dict[str, object] = Field(default_factory=dict)


class RuntimeResourceUsage(SimulationModel):
    instructions: int = Field(ge=0)
    events: int = Field(ge=0)
    output_bytes: int = Field(alias="outputBytes", ge=0)
    peak_heap_bytes: int = Field(alias="peakHeapBytes", ge=0)
    virtual_time_us: int = Field(alias="virtualTimeUs", ge=0)


class RuntimeExecutionResult(SimulationModel):
    schema_id: Literal["zhangwen.simulation-runtime-result/v1"] = Field(
        alias="schema", default=RUNTIME_RESULT_SCHEMA
    )
    engine_mode: RuntimeEngineMode = Field(alias="engineMode")
    status: RuntimeExecutionStatus
    runtime_package_revision_id: Literal["runtime/zw-mpy-sim@1"] = Field(
        alias="runtimePackageRevisionId"
    )
    native_core_verified: bool = Field(alias="nativeCoreVerified")
    evidence_eligible: bool = Field(alias="evidenceEligible", default=False)
    deterministic_digest: str | None = Field(
        alias="deterministicDigest", default=None, pattern=r"^[0-9a-f]{64}$"
    )
    serial_output: str = Field(alias="serialOutput", max_length=1_000_000)
    events: list[RuntimeEvent]
    resource_usage: RuntimeResourceUsage = Field(alias="resourceUsage")
    error: RuntimeErrorDetail | None

    @property
    def schema(self) -> str:
        return self.schema_id
