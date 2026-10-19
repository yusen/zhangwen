"""Skill Registry and Model Router boundary models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field
from typing import Self

from zhangwen.llm.contracts import LLMModelSelection, LLMProviderId
from zhangwen.projects.models import ExpertType


class SkillOrigin(StrEnum):
    BUILT_IN = "BUILT_IN"
    USER = "USER"


class SkillPermission(StrEnum):
    READ_PROJECT = "READ_PROJECT"
    WRITE_ARTIFACT = "WRITE_ARTIFACT"
    RUN_MODEL = "RUN_MODEL"
    USE_DEVICE = "USE_DEVICE"
    RUN_CAD = "RUN_CAD"
    RUN_SHELL = "RUN_SHELL"


class SkillRiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SkillConfirmationPolicy(StrEnum):
    NEVER = "never"
    BEFORE_EXTERNAL_EFFECT = "before_external_effect"
    ALWAYS = "always"


class SkillRunStatus(StrEnum):
    QUEUED = "queued"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ToolRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TimeoutPolicy(BaseModel):
    timeoutMs: int = Field(default=30_000, ge=100, le=300_000)


class RetryPolicy(BaseModel):
    maxRetries: int = Field(default=1, ge=0, le=5)
    backoffMs: int = Field(default=100, ge=0, le=10_000)


class ModelRouteStrategy(StrEnum):
    BALANCED = "BALANCED"
    COST_FIRST = "COST_FIRST"
    QUALITY_FIRST = "QUALITY_FIRST"
    FAST_FIRST = "FAST_FIRST"


class JsonSchemaObject(BaseModel):
    type: str
    properties: dict[str, Self] | None = None
    required: list[str] | None = None
    items: Self | None = None
    enum: list[str] | None = None
    description: str | None = None


class SkillDefinition(BaseModel):
    id: str
    name: str
    description: str
    origin: SkillOrigin
    enabled: bool
    ownerExpert: ExpertType
    inputSchema: JsonSchemaObject
    outputSchema: JsonSchemaObject
    requiredTools: list[str] = Field(default_factory=list)
    riskLevel: SkillRiskLevel = SkillRiskLevel.LOW
    confirmationPolicy: SkillConfirmationPolicy = SkillConfirmationPolicy.NEVER
    timeoutPolicy: TimeoutPolicy = Field(default_factory=TimeoutPolicy)
    retryPolicy: RetryPolicy = Field(default_factory=RetryPolicy)
    artifactTypes: list[str] = Field(default_factory=list)
    permissions: list[SkillPermission]
    createdAt: str
    updatedAt: str


class SkillRegistryResponse(BaseModel):
    skills: list[SkillDefinition]


class CreateSkillRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=1000)
    inputSchema: JsonSchemaObject | None = None
    outputSchema: JsonSchemaObject | None = None
    permissions: list[SkillPermission] = Field(default_factory=list)
    ownerExpert: ExpertType = ExpertType.PROBLEM_GUIDE


class UpdateSkillRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, min_length=1, max_length=1000)
    enabled: bool | None = None
    permissions: list[SkillPermission] | None = None


class SkillResponse(BaseModel):
    skill: SkillDefinition


class SkillRunRequest(BaseModel):
    projectId: str = Field(min_length=1)
    input: dict[str, object] = Field(default_factory=dict)
    expertRunId: str | None = None
    confirmed: bool = False
    requestingExpert: ExpertType | None = None


class SkillRunResult(BaseModel):
    id: str
    projectId: str
    skillId: str
    ownerExpert: ExpertType
    status: SkillRunStatus
    output: dict[str, object] | None = None
    error: str | None = None
    confirmationRequired: bool = False
    retryCount: int = 0


class SkillRunResponse(BaseModel):
    run: SkillRunResult


class ModelRouteRequest(BaseModel):
    agentId: str
    taskKind: str
    strategy: ModelRouteStrategy = ModelRouteStrategy.BALANCED


class ModelRouteResult(BaseModel):
    provider: LLMProviderId
    model: LLMModelSelection
    strategy: ModelRouteStrategy
    retryCount: int
    fallbackModel: LLMModelSelection | None
    providerConfigurationId: str | None = None
    providerConfigurationRevisionId: str | None = None
    routingProfileRevisionId: str | None = None
    fallbackProviderConfigurationId: str | None = None
    workload: str | None = None
    costTier: str = Field(pattern="^(LOW|MEDIUM|HIGH)$")
    qualityTier: str = Field(pattern="^(STANDARD|HIGH)$")
    reasoning: str


class ModelRouteResponse(BaseModel):
    route: ModelRouteResult
