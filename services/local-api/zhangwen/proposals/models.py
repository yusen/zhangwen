"""Proposal Pydantic boundary models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ProposalStatus(StrEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    STALE = "STALE"
    SUPERSEDED = "SUPERSEDED"


class ProposalExportFormat(StrEnum):
    MARKDOWN = "MARKDOWN"
    DOCX = "DOCX"
    PDF = "PDF"


class ProposalSection(BaseModel):
    id: str
    title: str
    content: str


class ProposalContentDraft(BaseModel):
    """Fixed six-section content returned by the cloud model."""

    model_config = ConfigDict(extra="forbid")

    projectOverview: str = Field(min_length=1, max_length=12000)
    requirements: str = Field(min_length=1, max_length=12000)
    hardwareSoftwareStructure: str = Field(min_length=1, max_length=12000)
    implementationPlan: str = Field(min_length=1, max_length=12000)
    costDifficultySchedule: str = Field(min_length=1, max_length=12000)
    risksAcceptance: str = Field(min_length=1, max_length=12000)


class ProposalVersion(BaseModel):
    id: str
    projectId: str
    solutionId: str
    solutionVersion: int
    version: int
    status: ProposalStatus
    sections: list[ProposalSection]
    createdAt: str
    updatedAt: str
    confirmedAt: str | None = None
    staleReason: str | None = None


class ProposalListResponse(BaseModel):
    proposals: list[ProposalVersion]


class ProposalResponse(BaseModel):
    proposal: ProposalVersion


class GenerateProposalRequest(BaseModel):
    solutionId: str


class ReviseProposalRequest(BaseModel):
    proposalId: str
    revisionMessage: str = Field(min_length=1, max_length=4000)


class ConfirmProposalRequest(BaseModel):
    proposalId: str


class ConfirmProposalResponse(BaseModel):
    proposal: ProposalVersion


class RejectProposalRequest(BaseModel):
    proposalId: str
    reason: str | None = Field(default=None, max_length=1000)


class RejectProposalResponse(BaseModel):
    proposal: ProposalVersion
