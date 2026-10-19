"""Code Agent boundary models."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CodeFileKind(StrEnum):
    MAIN = "MAIN"
    DRIVER = "DRIVER"
    CONFIG = "CONFIG"
    README = "README"
    TEST = "TEST"


class CodeRunStatus(StrEnum):
    DRAFT = "DRAFT"
    TESTING = "TESTING"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    ACCEPTED = "ACCEPTED"
    STALE = "STALE"
    REJECTED = "REJECTED"
    ROLLED_BACK = "ROLLED_BACK"
    FAILED = "FAILED"


class CodeRuntime(StrEnum):
    MICROPYTHON = "MICROPYTHON"
    ESP_CLAW_LUA = "ESP_CLAW_LUA"


class CodeRevisionSource(StrEnum):
    MODEL = "MODEL"
    USER = "USER"


class CodeValidationKind(StrEnum):
    STATIC = "STATIC"
    SYNTAX = "SYNTAX"
    SIMULATION = "SIMULATION"


class CodeValidationStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    NOT_RUN = "NOT_RUN"


class CodeFile(BaseModel):
    id: str
    codeRunId: str
    projectId: str
    kind: CodeFileKind
    path: str
    language: str
    content: str
    createdAt: str


class CodePatch(BaseModel):
    id: str
    codeRunId: str
    projectId: str
    baseSnapshotId: str | None = None
    summary: str
    diff: str
    createdAt: str


class CodeValidationCheck(BaseModel):
    kind: CodeValidationKind
    status: CodeValidationStatus
    command: str
    exitCode: int | None = None
    output: str


class CodeTestResult(BaseModel):
    ok: bool
    command: str
    output: str
    createdAt: str
    checks: list[CodeValidationCheck] = Field(default_factory=list)


class CodeContentFileDraft(BaseModel):
    """One provider candidate for a bounded device-runtime file set."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, max_length=200)
    language: Literal["python", "lua", "markdown"] = "python"
    content: str = Field(min_length=1, max_length=40000)


class CodeContentDraft(BaseModel):
    """Dynamic, upload-only runtime file set returned by the cloud model."""

    model_config = ConfigDict(extra="forbid")

    files: list[CodeContentFileDraft] = Field(min_length=1, max_length=30)
    summary: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def _unique_paths(self) -> "CodeContentDraft":
        paths = [file.path for file in self.files]
        if len(paths) != len(set(paths)):
            raise ValueError("代码文件路径不能重复。")
        return self


class ChatCodeFileDraft(BaseModel):
    """A provider candidate; local code enforces the final path and capability boundary."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, max_length=200)
    language: Literal["python", "lua", "markdown"]
    content: str = Field(max_length=40000)


class ChatCodeDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runtime: CodeRuntime = CodeRuntime.MICROPYTHON
    files: list[ChatCodeFileDraft] = Field(min_length=1, max_length=30)
    summary: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def _unique_paths(self) -> "ChatCodeDraft":
        paths = [file.path for file in self.files]
        if len(paths) != len(set(paths)):
            raise ValueError("代码文件路径不能重复。")
        return self


class CodeRun(BaseModel):
    id: str
    projectId: str
    specRunId: str | None = None
    version: int
    status: CodeRunStatus
    runtime: CodeRuntime = CodeRuntime.MICROPYTHON
    entrypoint: str = "src/main.py"
    workspaceRoot: str
    maxRetries: int
    retries: int
    files: list[CodeFile]
    patch: CodePatch
    testResult: CodeTestResult
    artifactId: str | None = None
    artifactVersionId: str | None = None
    hardwareSolutionVersion: int | None = None
    bomVersion: int | None = None
    ioMapVersion: int | None = None
    generatedByExpertId: str | None = None
    staleReason: str | None = None
    createdAt: str
    updatedAt: str
    acceptedAt: str | None = None
    revisionSource: CodeRevisionSource = CodeRevisionSource.MODEL
    requiresValidation: bool = False


class CodeRunResponse(BaseModel):
    codeRun: CodeRun


class GenerateCodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    specRunId: str
    runtime: CodeRuntime = CodeRuntime.MICROPYTHON


class ValidateCodeRequest(BaseModel):
    codeRunId: str = Field(min_length=1, max_length=100)


class ImportCodeMessageRequest(BaseModel):
    messageId: str = Field(min_length=1, max_length=100)


class AcceptCodeRequest(BaseModel):
    codeRunId: str


class RejectCodeRequest(BaseModel):
    codeRunId: str
    reason: str | None = Field(default=None, max_length=1000)


class RollbackCodeRequest(BaseModel):
    codeRunId: str


class EditableCodeFile(BaseModel):
    path: str = Field(min_length=1, max_length=200)
    content: str = Field(max_length=40000)


class ReviseCodeRequest(BaseModel):
    baseCodeRunId: str = Field(min_length=1, max_length=100)
    files: list[EditableCodeFile] = Field(min_length=1, max_length=30)
    summary: str = Field(min_length=1, max_length=1000)
