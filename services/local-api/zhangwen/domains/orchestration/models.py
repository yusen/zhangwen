"""Strict unified Turn and Invocation Plan boundary models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class OrchestrationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class PackageKind(StrEnum):
    SKILL_PACKAGE = "SKILL_PACKAGE"
    AGENT_PACKAGE = "AGENT_PACKAGE"
    DEVICE_PACKAGE = "DEVICE_PACKAGE"
    RUNTIME_PACKAGE = "RUNTIME_PACKAGE"
    SERVICE_PACKAGE = "SERVICE_PACKAGE"


class InternalUnit(StrEnum):
    DISCOVERY_ROLE = "DISCOVERY_ROLE"
    ENGINEERING_ROLE = "ENGINEERING_ROLE"
    STRUCTURE_ROLE = "STRUCTURE_ROLE"


class UnifiedTurnStatus(StrEnum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"


class InvocationStepStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FALLBACK = "FALLBACK"
    FAILED = "FAILED"


class InvocationFallbackCode(StrEnum):
    UNIT_UNAVAILABLE = "UNIT_UNAVAILABLE"
    OUTPUT_INVALID = "OUTPUT_INVALID"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    INTERNAL_FAILURE = "INTERNAL_FAILURE"


class ExecutionRevisionBinding(OrchestrationModel):
    package_kind: PackageKind = Field(alias="packageKind")
    package_id: str = Field(alias="packageId", min_length=1, max_length=200)
    package_revision_id: str = Field(
        alias="packageRevisionId", min_length=1, max_length=200
    )


class ExecutionRevisionSet(OrchestrationModel):
    id: str
    bindings: list[ExecutionRevisionBinding]
    provider_configuration_id: str | None = Field(
        default=None,
        alias="providerConfigurationId",
    )
    provider_configuration_revision_id: str | None = Field(
        default=None,
        alias="providerConfigurationRevisionId",
    )
    routing_profile_revision_id: str | None = Field(
        default=None,
        alias="routingProfileRevisionId",
    )
    model: str | None = None
    model_workload: str | None = Field(default=None, alias="modelWorkload")
    created_at: str = Field(alias="createdAt")


class InvocationFallback(OrchestrationModel):
    code: InvocationFallbackCode
    natural_message: str = Field(alias="naturalMessage", min_length=1, max_length=500)


class InvocationStep(OrchestrationModel):
    id: str
    position: int = Field(ge=0)
    unit: InternalUnit
    status: InvocationStepStatus
    agent_package_revision_id: str = Field(alias="agentPackageRevisionId")
    skill_revision_ids: list[str] = Field(alias="skillRevisionIds")
    output_summary: str | None = Field(alias="outputSummary", max_length=1000)
    fallback: InvocationFallback | None
    started_at: str | None = Field(alias="startedAt")
    completed_at: str | None = Field(alias="completedAt")


class InvocationPlan(OrchestrationModel):
    id: str
    intent: str = Field(min_length=1, max_length=120)
    status: UnifiedTurnStatus
    revision_set: ExecutionRevisionSet = Field(alias="revisionSet")
    steps: list[InvocationStep]
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class UnifiedTurn(OrchestrationModel):
    id: str
    work_id: str = Field(alias="workId")
    idempotency_key: str = Field(alias="idempotencyKey")
    user_message: str = Field(alias="userMessage")
    status: UnifiedTurnStatus
    assistant_response: str | None = Field(alias="assistantResponse")
    natural_status: str = Field(alias="naturalStatus")
    invocation_plan: InvocationPlan = Field(alias="invocationPlan")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    completed_at: str | None = Field(alias="completedAt")


class CreateUnifiedTurnRequest(OrchestrationModel):
    message: str = Field(min_length=1, max_length=4000)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=8, max_length=160)


class UnifiedTurnResponse(OrchestrationModel):
    turn: UnifiedTurn


class UnifiedConversationResponse(OrchestrationModel):
    turns: list[UnifiedTurn]
