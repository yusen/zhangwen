"""Project package boundary models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from zhangwen.artifacts.models import ArtifactKind, ArtifactStatus
from zhangwen.projects.models import ProjectStage, ProjectWorkspace


class ProjectPackageStatus(StrEnum):
    READY = "READY"
    EXPORTED = "EXPORTED"
    IMPORTED = "IMPORTED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class ProjectPackageItemKind(StrEnum):
    PROJECT = "PROJECT"
    ARTIFACT = "ARTIFACT"
    ARTIFACT_FILE = "ARTIFACT_FILE"
    MANIFEST = "MANIFEST"
    PRIVACY_REPORT = "PRIVACY_REPORT"


class ProjectPackageConflictStrategy(StrEnum):
    CREATE_COPY = "CREATE_COPY"
    FAIL_IF_EXISTS = "FAIL_IF_EXISTS"


class ProjectPackageArtifactSelection(BaseModel):
    includeDocuments: bool = True
    includeCode: bool = True
    includeCad: bool = True
    includeLessons: bool = True
    includeDeviceLogs: bool = False


class ProjectPackageArtifactSelectionPatch(BaseModel):
    includeDocuments: bool | None = None
    includeCode: bool | None = None
    includeCad: bool | None = None
    includeLessons: bool | None = None
    includeDeviceLogs: bool | None = None


class ProjectPackagePrivacyCheck(BaseModel):
    dimension: str
    severity: str = Field(pattern="^(PASS|WARNING|FAIL)$")
    message: str
    path: str | None = None


class ProjectPackagePrivacyReport(BaseModel):
    ok: bool
    checks: list[ProjectPackagePrivacyCheck]


class ProjectPackageManifestArtifact(BaseModel):
    artifactId: str
    versionId: str
    title: str
    kind: ArtifactKind
    sourceAgentId: str
    sourceEntityType: str | None = None
    sourceEntityId: str | None = None
    version: int
    status: ArtifactStatus
    path: str
    checksum: str
    files: list["ProjectPackageManifestFile"] = Field(default_factory=list)


class ProjectPackageManifestFile(BaseModel):
    artifactFileId: str
    role: str
    fileName: str
    path: str
    mimeType: str
    byteSize: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    triangleCount: int | None = Field(default=None, ge=0)
    bounds: dict[str, float] | None = None


class ProjectPackageManifest(BaseModel):
    schemaVersion: int = 2
    packageId: str
    packageVersion: int = 2
    status: ProjectPackageStatus
    projectId: str
    projectName: str
    projectStage: ProjectStage
    exportedAt: str
    itemKinds: list[ProjectPackageItemKind]
    artifactSelection: ProjectPackageArtifactSelection
    artifacts: list[ProjectPackageManifestArtifact]
    privacyReport: ProjectPackagePrivacyReport


class ProjectPackageRecord(BaseModel):
    id: str
    projectId: str
    status: ProjectPackageStatus
    title: str
    fileName: str
    manifest: ProjectPackageManifest
    privacyReport: ProjectPackagePrivacyReport
    artifactId: str | None = None
    artifactVersionId: str | None = None
    zipBase64: str | None = None
    createdAt: str
    importedAt: str | None = None


class ExportProjectPackageRequest(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    artifactSelection: ProjectPackageArtifactSelectionPatch | None = None


class ExportProjectPackageResponse(BaseModel):
    package: ProjectPackageRecord


class ImportProjectPackageRequest(BaseModel):
    zipBase64: str = Field(min_length=1)
    conflictStrategy: ProjectPackageConflictStrategy = (
        ProjectPackageConflictStrategy.CREATE_COPY
    )


class ImportProjectPackageResponse(BaseModel):
    package: ProjectPackageRecord
    workspace: ProjectWorkspace
