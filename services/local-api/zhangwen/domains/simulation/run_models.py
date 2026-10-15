"""Contracts for immutable scenario runs over a fixed simulation revision set."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, field_validator

from zhangwen.domains.simulation.models import SimulationModel
from zhangwen.domains.simulation.runtime.models import (
    RuntimeEngineMode,
    RuntimeExecutionStatus,
)


class SimulationRunStatus(StrEnum):
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    CONFORMANCE_PASSED = "CONFORMANCE_PASSED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    CANCELED = "CANCELED"
    CRASHED = "CRASHED"
    STALE = "STALE"


class SimulationScenarioResultStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    CANCELED = "CANCELED"
    CRASHED = "CRASHED"


class SimulationAssertionStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    NOT_EVALUATED = "NOT_EVALUATED"


class SimulationRunRequest(SimulationModel):
    simulation_project_revision_id: str = Field(
        alias="simulationProjectRevisionId", min_length=1, max_length=300
    )
    engine_mode: RuntimeEngineMode = Field(alias="engineMode")
    reflections: dict[str, str] = Field(default_factory=dict)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=80)

    @field_validator("reflections")
    @classmethod
    def bounded_reflections(cls, value: dict[str, str]) -> dict[str, str]:
        if len(value) > 100:
            raise ValueError("reflection count exceeds scenario limit")
        normalized: dict[str, str] = {}
        for scenario_id, reflection in value.items():
            clean_id = scenario_id.strip()
            clean_reflection = reflection.strip()
            if not clean_id or len(clean_id) > 100 or len(clean_reflection) > 4000:
                raise ValueError("reflection is outside the bounded run contract")
            normalized[clean_id] = clean_reflection
        return normalized


class SimulationAssertionResult(SimulationModel):
    assertion_id: str = Field(alias="assertionId")
    target: str
    status: SimulationAssertionStatus
    expected: object
    observed: object | None
    explanation: str


class SimulationScenarioRunResult(SimulationModel):
    id: str
    scenario_id: str = Field(alias="scenarioId")
    title: str
    required: bool
    status: SimulationScenarioResultStatus
    seed: int
    reflection: str
    deterministic_digest: str | None = Field(alias="deterministicDigest")
    runtime_status: RuntimeExecutionStatus = Field(alias="runtimeStatus")
    native_core_verified: bool = Field(alias="nativeCoreVerified")
    evidence_eligible: bool = Field(alias="evidenceEligible")
    assertions: list[SimulationAssertionResult]
    serial_output: str = Field(alias="serialOutput")
    explanation: str


class SimulationRunRecord(SimulationModel):
    id: str
    work_id: str = Field(alias="workId")
    simulation_project_revision_id: str = Field(alias="simulationProjectRevisionId")
    status: SimulationRunStatus
    engine_mode: RuntimeEngineMode = Field(alias="engineMode")
    evidence_level: str = Field(alias="evidenceLevel", pattern=r"^L[01]$")
    evidence_eligible: bool = Field(alias="evidenceEligible")
    deterministic_digest: str | None = Field(alias="deterministicDigest")
    revision_set: dict[str, object] = Field(alias="revisionSet")
    scenarios: list[SimulationScenarioRunResult]
    explanation: str
    serial_output: str = Field(alias="serialOutput")
    error: dict[str, object] | None
    created_by: str = Field(alias="createdBy")
    created_at: str = Field(alias="createdAt")
    completed_at: str | None = Field(alias="completedAt")
    invalidation_reason: str | None = Field(alias="invalidationReason")


class SimulationRunWorkspace(SimulationModel):
    current: SimulationRunRecord | None
    runs: list[SimulationRunRecord]
    can_run: bool = Field(alias="canRun")

