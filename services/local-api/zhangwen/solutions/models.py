"""Solution Pydantic boundary models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class SolutionStatus(StrEnum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    SUPERSEDED = "SUPERSEDED"
    OUTDATED = "OUTDATED"


class SolutionSection(BaseModel):
    id: str
    title: str
    content: str


class SolutionVersion(BaseModel):
    id: str
    projectId: str
    version: int
    basedOnVersion: int | None = None
    status: SolutionStatus
    changeSummary: list[str] = Field(default_factory=list)
    sections: list[SolutionSection]
    artifactId: str | None = None
    artifactVersionId: str | None = None
    createdAt: str
    confirmedAt: str | None = None


class SolutionSectionChange(BaseModel):
    sectionId: str
    sectionTitle: str
    changeType: str
    before: object | None = None
    after: object | None = None
    reason: str


class SolutionRevision(BaseModel):
    id: str
    projectId: str
    baseSolutionId: str
    baseVersion: int
    newSolutionId: str
    newVersion: int
    userRequest: str
    changedSections: list[SolutionSectionChange]
    preservedSections: list[str]
    impactSummary: list[str]
    createdAt: str


class SolutionListResponse(BaseModel):
    solutions: list[SolutionVersion]


class SolutionResponse(BaseModel):
    solution: SolutionVersion


class GenerateSolutionRequest(BaseModel):
    revisionMessage: str | None = None
    componentIds: list[str] = Field(default_factory=list)


class ReviseSolutionRequest(BaseModel):
    baseSolutionId: str | None = None
    userInstruction: str = Field(min_length=1, max_length=4000)


class ReviseSolutionResponse(BaseModel):
    solution: SolutionVersion
    revision: SolutionRevision


class RestoreSolutionResponse(BaseModel):
    solution: SolutionVersion


class ConfirmSolutionRequest(BaseModel):
    solutionId: str


class ConfirmSolutionResponse(BaseModel):
    solution: SolutionVersion
