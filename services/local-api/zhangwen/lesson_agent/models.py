"""Lesson Agent boundary models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class LessonDocumentKind(StrEnum):
    TEACHER_GUIDE = "TEACHER_GUIDE"
    STUDENT_WORKSHEET = "STUDENT_WORKSHEET"
    RUBRIC = "RUBRIC"
    SAFETY_NOTES = "SAFETY_NOTES"


class LessonRunStatus(StrEnum):
    DRAFT = "DRAFT"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    STALE = "STALE"
    FAILED = "FAILED"


class LessonContentDraft(BaseModel):
    """Fixed four-document content returned by the cloud model."""

    model_config = ConfigDict(extra="forbid")

    teacherGuide: str = Field(min_length=1, max_length=50000)
    studentWorksheet: str = Field(min_length=1, max_length=50000)
    rubric: str = Field(min_length=1, max_length=50000)
    safetyNotes: str = Field(min_length=1, max_length=50000)


class LessonFile(BaseModel):
    id: str
    lessonRunId: str
    projectId: str
    kind: LessonDocumentKind
    title: str
    path: str
    mimeType: str
    content: str
    artifactId: str | None = None
    artifactVersionId: str | None = None
    createdAt: str


class LessonRun(BaseModel):
    id: str
    projectId: str
    specRunId: str
    proposalId: str
    version: int
    status: LessonRunStatus
    gradeBand: str
    lessonHours: int
    files: list[LessonFile]
    staleReason: str | None = None
    createdAt: str
    updatedAt: str
    confirmedAt: str | None = None


class LessonRunResponse(BaseModel):
    lessonRun: LessonRun


class GenerateLessonRequest(BaseModel):
    specRunId: str
    gradeBand: str | None = Field(default=None, max_length=40)
    lessonHours: int | None = Field(default=None, ge=1, le=8)


class ConfirmLessonRequest(BaseModel):
    lessonRunId: str


class RejectLessonRequest(BaseModel):
    lessonRunId: str
    reason: str | None = Field(default=None, max_length=1000)
