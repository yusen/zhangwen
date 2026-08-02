"""MVP readiness boundary models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class MvpReadinessStatus(StrEnum):
    READY = "READY"
    NEEDS_ACTION = "NEEDS_ACTION"
    BLOCKED = "BLOCKED"


class MvpReadinessItemId(StrEnum):
    PROJECT_BASELINE = "PROJECT_BASELINE"
    SOLUTION = "SOLUTION"
    PROPOSAL = "PROPOSAL"
    EXECUTION_PLAN = "EXECUTION_PLAN"
    SPEC = "SPEC"
    CODE = "CODE"
    DEVICE_DRY_RUN = "DEVICE_DRY_RUN"
    CAD = "CAD"
    LESSON = "LESSON"
    PACKAGE = "PACKAGE"
    ARTIFACTS = "ARTIFACTS"
    SECURITY = "SECURITY"


class MvpReadinessItem(BaseModel):
    id: MvpReadinessItemId
    label: str
    status: MvpReadinessStatus
    required: bool
    message: str
    evidence: list[str]


class MvpReadinessReport(BaseModel):
    projectId: str
    overallStatus: MvpReadinessStatus
    readyCount: int
    totalCount: int
    generatedAt: str
    items: list[MvpReadinessItem]
    externalValidationRequired: list[str]
    manualAcceptance: list[str]


class MvpReadinessResponse(BaseModel):
    readiness: MvpReadinessReport
