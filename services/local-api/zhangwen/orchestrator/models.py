"""Orchestrator Pydantic boundary models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class AgentCapability(StrEnum):
    ORCHESTRATE = "ORCHESTRATE"
    SPEC = "SPEC"
    CODE = "CODE"
    CAD = "CAD"
    DEPLOY = "DEPLOY"
    PUBLISH = "PUBLISH"
    LESSON = "LESSON"
    REVIEW = "REVIEW"


class TaskStatus(StrEnum):
    DISABLED = "DISABLED"
    QUEUED = "QUEUED"
    PLANNING = "PLANNING"
    RUNNING = "RUNNING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    PAUSED = "PAUSED"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


class AgentDefinition(BaseModel):
    id: str
    name: str
    description: str
    capabilities: list[AgentCapability]
    enabled: bool = True
    builtIn: bool = True


class AgentRegistryResponse(BaseModel):
    agents: list[AgentDefinition]


class TaskLogEntry(BaseModel):
    id: str
    level: str = Field(pattern="^(INFO|WARNING|ERROR)$")
    message: str
    createdAt: str


class TaskNode(BaseModel):
    id: str
    planId: str
    projectId: str
    agentId: str
    title: str
    description: str
    status: TaskStatus
    dependencies: list[str]
    attempts: int
    maxAttempts: int
    requiresApproval: bool
    logs: list[TaskLogEntry]
    createdAt: str
    updatedAt: str
    startedAt: str | None = None
    completedAt: str | None = None
    error: str | None = None


class ExecutionPlan(BaseModel):
    id: str
    projectId: str
    proposalId: str
    status: TaskStatus
    nodes: list[TaskNode]
    createdAt: str
    updatedAt: str
    startedAt: str | None = None
    completedAt: str | None = None


class ExecutionPlanResponse(BaseModel):
    plan: ExecutionPlan


class CreateExecutionPlanRequest(BaseModel):
    proposalId: str


class PlanActionRequest(BaseModel):
    nodeId: str | None = None


class ApprovalRequest(BaseModel):
    nodeId: str
    approved: bool
    comment: str | None = Field(default=None, max_length=1000)
