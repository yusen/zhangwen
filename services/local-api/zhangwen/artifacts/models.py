"""Artifact and floating window boundary models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ArtifactKind(StrEnum):
    DOCUMENT = "DOCUMENT"
    CODE = "CODE"
    IMAGE = "IMAGE"
    MODEL_3D = "MODEL_3D"
    DEVICE_LOG = "DEVICE_LOG"
    PACKAGE = "PACKAGE"
    REPORT = "REPORT"


class ArtifactStatus(StrEnum):
    DRAFT = "DRAFT"
    GENERATING = "GENERATING"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    STALE = "STALE"
    FAILED = "FAILED"
    ARCHIVED = "ARCHIVED"


class DomainArtifactStatus(StrEnum):
    DRAFT = "draft"
    PENDING_CONFIRMATION = "pending_confirmation"
    CONFIRMED = "confirmed"
    OUTDATED = "outdated"
    ARCHIVED = "archived"


class ArtifactPreviewKind(StrEnum):
    DOCUMENT = "DOCUMENT"
    CODE = "CODE"
    IMAGE = "IMAGE"
    MODEL_3D = "MODEL_3D"
    TEXT = "TEXT"


class FloatingWindowKind(StrEnum):
    DOCUMENT = "document"
    CODE = "code"
    MODEL_3D = "model3d"
    IMAGE = "image"
    TERMINAL = "terminal"
    WEB_PREVIEW = "web-preview"


class ArtifactDependency(BaseModel):
    artifactId: str
    versionId: str | None = None
    version: int | None = None
    kind: str
    label: str
    status: str
    relation: str | None = None
    required: bool = True


class ArtifactPreviewSection(BaseModel):
    id: str
    title: str
    content: str


class ArtifactPreview(BaseModel):
    kind: ArtifactPreviewKind
    summary: str
    sections: list[ArtifactPreviewSection] | None = None
    code: str | None = None
    language: str | None = None
    imageUrl: str | None = None
    modelUrl: str | None = None
    modelFileId: str | None = None
    placeholder: str | None = None


class ArtifactFile(BaseModel):
    id: str
    artifactId: str
    artifactVersionId: str
    projectId: str
    role: str
    fileName: str
    mimeType: str
    byteSize: int = Field(ge=0)
    sha256: str
    triangleCount: int | None = Field(default=None, ge=0)
    bounds: dict[str, object] | None = None
    createdAt: str


class ArtifactVersion(BaseModel):
    id: str
    artifactId: str
    projectId: str
    version: int
    status: ArtifactStatus
    domainStatus: DomainArtifactStatus | None = None
    mimeType: str
    preview: ArtifactPreview
    dependencies: list[ArtifactDependency] = Field(default_factory=list)
    producerTaskId: str | None = None
    sourceEntityType: str | None = None
    sourceEntityId: str | None = None
    checksum: str
    staleReason: str | None = None
    sharedContextRevision: int | None = None
    createdAt: str
    confirmedAt: str | None = None


class ArtifactDefinition(BaseModel):
    id: str
    projectId: str
    title: str
    kind: ArtifactKind
    status: ArtifactStatus
    domainStatus: DomainArtifactStatus | None = None
    sourceAgentId: str
    ownerExpertId: str | None = None
    ownerExpertType: str | None = None
    legacyOwnerExpert: str | None = None
    creatorLegacyExpert: str | None = None
    sourceConversationId: str | None = None
    sharedContextRevision: int | None = None
    currentVersionId: str | None = None
    versions: list[ArtifactVersion] = Field(default_factory=list)
    createdAt: str
    updatedAt: str


class ArtifactListResponse(BaseModel):
    artifacts: list[ArtifactDefinition]


class ArtifactResponse(BaseModel):
    artifact: ArtifactDefinition


class ArtifactFileListResponse(BaseModel):
    files: list[ArtifactFile]


class FloatingWindowBounds(BaseModel):
    x: int
    y: int
    width: int
    height: int


class FloatingWindowSpec(BaseModel):
    id: str
    kind: FloatingWindowKind
    title: str
    artifactId: str | None = None
    versionId: str | None = None
    initialBounds: FloatingWindowBounds | None = None
    singletonKey: str | None = None
    zIndex: int | None = None
    minimized: bool | None = None
    maximized: bool | None = None
