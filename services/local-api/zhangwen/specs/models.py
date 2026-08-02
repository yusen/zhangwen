"""Spec Agent boundary models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SpecFileKind(StrEnum):
    PROJECT_SPEC = "PROJECT_SPEC"
    BOM = "BOM"
    IO_MAP = "IO_MAP"


class SpecRunStatus(StrEnum):
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    STALE = "STALE"
    FAILED = "FAILED"


class SpecValidationCheck(BaseModel):
    dimension: str
    severity: str = Field(pattern="^(PASS|WARNING|FAIL)$")
    message: str
    details: str


class SpecValidation(BaseModel):
    ok: bool
    checks: list[SpecValidationCheck]


class SpecModuleDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1, max_length=120)
    responsibility: str = Field(min_length=1, max_length=1000)


class SpecIOSuggestionDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    pin: str = Field(pattern=r"^GPIO\d+(?:/GPIO\d+)?$")
    protocol: str = Field(min_length=1, max_length=40)
    componentId: str = Field(min_length=1, max_length=120)


class SpecContentDraft(BaseModel):
    """Project and IO content proposed by the cloud model."""

    model_config = ConfigDict(extra="forbid")

    projectName: str = Field(min_length=1, max_length=120)
    goal: str = Field(min_length=1, max_length=4000)
    modules: list[SpecModuleDraft] = Field(min_length=1, max_length=12)
    acceptance: list[str] = Field(min_length=1, max_length=12)
    risks: list[str] = Field(min_length=1, max_length=12)
    componentIds: list[str] = Field(min_length=1, max_length=12)
    ioSuggestions: list[SpecIOSuggestionDraft] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def _unique_entries(self) -> "SpecContentDraft":
        if len(set(self.componentIds)) != len(self.componentIds):
            raise ValueError("componentIds must be unique")
        module_ids = [module.id for module in self.modules]
        if len(set(module_ids)) != len(module_ids):
            raise ValueError("module ids must be unique")
        signals = [item.signal for item in self.ioSuggestions]
        pins = [item.pin for item in self.ioSuggestions]
        if len(set(signals)) != len(signals):
            raise ValueError("IO signals must be unique")
        if len(set(pins)) != len(pins):
            raise ValueError("IO pins must be unique")
        return self


class SpecFile(BaseModel):
    id: str
    specRunId: str
    projectId: str
    kind: SpecFileKind
    path: str
    mimeType: str
    content: str
    artifactId: str | None = None
    artifactVersionId: str | None = None
    createdAt: str


class SpecRun(BaseModel):
    id: str
    projectId: str
    proposalId: str
    version: int
    status: SpecRunStatus
    files: list[SpecFile]
    validation: SpecValidation
    staleReason: str | None = None
    createdAt: str
    updatedAt: str
    confirmedAt: str | None = None


class SpecRunResponse(BaseModel):
    spec: SpecRun


class GenerateSpecRequest(BaseModel):
    proposalId: str


class ConfirmSpecRequest(BaseModel):
    specRunId: str


class RejectSpecRequest(BaseModel):
    specRunId: str
    reason: str | None = Field(default=None, max_length=1000)
