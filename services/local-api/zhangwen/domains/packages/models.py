"""Strict boundary models for the unified capability package platform."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


class PackageModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class PackageKind(StrEnum):
    SKILL_PACKAGE = "SKILL_PACKAGE"
    AGENT_PACKAGE = "AGENT_PACKAGE"
    DEVICE_PACKAGE = "DEVICE_PACKAGE"
    RUNTIME_PACKAGE = "RUNTIME_PACKAGE"
    SERVICE_PACKAGE = "SERVICE_PACKAGE"


class PackageRevisionStatus(StrEnum):
    DRAFT = "DRAFT"
    VALIDATING = "VALIDATING"
    VALID = "VALID"
    INVALID = "INVALID"
    PUBLISHED = "PUBLISHED"
    RETIRED = "RETIRED"


class PackageWorkspaceStatus(StrEnum):
    DRAFT = "DRAFT"
    VALID = "VALID"
    INVALID = "INVALID"
    PUBLISHED = "PUBLISHED"


class ShadowStatus(StrEnum):
    NOT_RUN = "NOT_RUN"
    PASSED = "PASSED"
    FAILED = "FAILED"


class ValidationStatus(StrEnum):
    NOT_RUN = "NOT_RUN"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"


class PackageValidationIssue(PackageModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,80}$")
    path: str | None = None
    message: str = Field(min_length=1, max_length=500)
    severity: Literal["WARNING", "ERROR"] = "ERROR"


class PackageValidationSummary(PackageModel):
    status: ValidationStatus = ValidationStatus.NOT_RUN
    issues: list[PackageValidationIssue] = Field(default_factory=list)
    checked_at: str | None = Field(default=None, alias="checkedAt")


class PackageManifestEntrypoints(PackageModel):
    prompt: str | None = None
    input_schema: str | None = Field(default=None, alias="inputSchema")
    output_schema: str | None = Field(default=None, alias="outputSchema")
    handler: str | None = None


class CapabilityPackageManifest(PackageModel):
    schema_version: int = Field(alias="schemaVersion", ge=1, le=10)
    id: str = Field(min_length=1, max_length=160)
    kind: PackageKind
    display_name: str = Field(alias="displayName", min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=80)
    channel: Literal["draft", "stable"]
    capabilities: list[str] = Field(default_factory=list, max_length=128)
    permissions: list[str] = Field(default_factory=list, max_length=64)
    risk_level: Literal["low", "medium", "high"] = Field(alias="riskLevel")
    confirmation_policy: Literal[
        "never", "before_external_effect", "always"
    ] = Field(alias="confirmationPolicy")
    entrypoints: PackageManifestEntrypoints
    compatibility: dict[str, JsonValue] = Field(default_factory=dict)
    evidence: dict[str, JsonValue] = Field(default_factory=dict)
    files: list[str] = Field(default_factory=list, max_length=256)


class CapabilityPackage(PackageModel):
    id: str
    kind: PackageKind
    slug: str
    display_name: str = Field(alias="displayName")
    owner_subject: str | None = Field(alias="ownerSubject")
    stable_revision_id: str | None = Field(alias="stableRevisionId")
    draft_revision_id: str | None = Field(alias="draftRevisionId")
    revision: int = Field(ge=1)
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class PackageRevision(PackageModel):
    id: str
    package_id: str = Field(alias="packageId")
    revision: int = Field(ge=1)
    status: PackageRevisionStatus
    manifest_artifact_id: str = Field(alias="manifestArtifactId")
    content_digest: str = Field(alias="contentDigest")
    schema_version: int = Field(alias="schemaVersion", ge=1)
    validation_summary: PackageValidationSummary = Field(alias="validationSummary")
    shadow_status: ShadowStatus = Field(alias="shadowStatus")
    created_at: str = Field(alias="createdAt")
    published_at: str | None = Field(alias="publishedAt")
    supersedes_revision_id: str | None = Field(alias="supersedesRevisionId")


class PackageWorkspaceFile(PackageModel):
    path: str
    content: str
    content_digest: str = Field(alias="contentDigest")
    revision: int = Field(ge=1)


class PackageWorkspace(PackageModel):
    id: str
    package_id: str = Field(alias="packageId")
    base_revision_id: str | None = Field(alias="baseRevisionId")
    draft_revision_id: str | None = Field(alias="draftRevisionId")
    revision: int = Field(ge=1)
    status: PackageWorkspaceStatus
    files: list[PackageWorkspaceFile]
    validation_summary: PackageValidationSummary = Field(alias="validationSummary")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class PackageListResponse(PackageModel):
    packages: list[CapabilityPackage]


class PackageDetailResponse(PackageModel):
    package: CapabilityPackage
    revisions: list[PackageRevision]


class PackageWorkspaceResponse(PackageModel):
    workspace: PackageWorkspace


class CreatePackageWorkspaceRequest(PackageModel):
    package_id: str | None = Field(default=None, alias="packageId", max_length=160)
    kind: PackageKind | None = None
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9]+(?:[-_.][a-z0-9]+)*$")
    display_name: str | None = Field(default=None, alias="displayName", max_length=120)

    @model_validator(mode="after")
    def existing_or_new_package(self) -> "CreatePackageWorkspaceRequest":
        creating = self.package_id is None
        if creating and (self.kind is None or self.slug is None or self.display_name is None):
            raise ValueError("New package workspaces require kind, slug and displayName")
        if not creating and any(
            value is not None for value in (self.kind, self.slug, self.display_name)
        ):
            raise ValueError("Existing package workspaces only accept packageId")
        return self


class PackageWorkspaceFileUpdate(PackageModel):
    path: str = Field(min_length=1, max_length=240)
    content: str = Field(max_length=80_000)
    expected_revision: int = Field(alias="expectedRevision", ge=0)


class SavePackageWorkspaceRequest(PackageModel):
    expected_revision: int = Field(alias="expectedRevision", ge=1)
    files: list[PackageWorkspaceFileUpdate] = Field(min_length=1, max_length=64)


class PackageInputSnapshot(PackageModel):
    id: str
    source_turn_id: str = Field(alias="sourceTurnId")
    work_id: str = Field(alias="workId")
    input: dict[str, JsonValue]
    execution_revision_set: dict[str, JsonValue] = Field(alias="executionRevisionSet")
    redacted: bool
    created_at: str = Field(alias="createdAt")


class PackageInputListResponse(PackageModel):
    inputs: list[PackageInputSnapshot]


class PackageReplayRequest(PackageModel):
    turn_id: str = Field(alias="turnId", min_length=1, max_length=160)


class PackageShadowRequest(PackageModel):
    turn_id: str = Field(alias="turnId", min_length=1, max_length=160)


class PackageRunDiagnostics(PackageModel):
    messages: list[str] = Field(default_factory=list)
    duration_ms: int = Field(alias="durationMs", ge=0)
    output_bytes: int = Field(alias="outputBytes", ge=0)
    external_effects_blocked: bool = Field(alias="externalEffectsBlocked")


class PackageReplayResult(PackageModel):
    id: str
    package_id: str = Field(alias="packageId")
    package_revision_id: str = Field(alias="packageRevisionId")
    input_snapshot: PackageInputSnapshot = Field(alias="inputSnapshot")
    output: dict[str, JsonValue]
    tool_plan: list[dict[str, JsonValue]] = Field(alias="toolPlan")
    diagnostics: PackageRunDiagnostics
    created_at: str = Field(alias="createdAt")


class PackageShadowResult(PackageModel):
    id: str
    package_id: str = Field(alias="packageId")
    baseline_revision_id: str = Field(alias="baselineRevisionId")
    candidate_revision_id: str = Field(alias="candidateRevisionId")
    input_snapshot: PackageInputSnapshot = Field(alias="inputSnapshot")
    baseline_output: dict[str, JsonValue] = Field(alias="baselineOutput")
    candidate_output: dict[str, JsonValue] = Field(alias="candidateOutput")
    output_diff: list[str] = Field(alias="outputDiff")
    tool_plan_diff: list[str] = Field(alias="toolPlanDiff")
    diagnostics: PackageRunDiagnostics
    status: Literal["PASSED", "FAILED"]
    created_at: str = Field(alias="createdAt")


class PublishPackageWorkspaceRequest(PackageModel):
    expected_revision: int = Field(alias="expectedRevision", ge=1)
    confirmed: bool = False


class RollbackPackageRequest(PackageModel):
    target_revision_id: str = Field(alias="targetRevisionId", min_length=1)
    expected_revision: int = Field(alias="expectedRevision", ge=1)
    confirmed: bool = False


class PackagePublishResponse(PackageModel):
    package: CapabilityPackage
    revision: PackageRevision


class PackagePlatformError(ValueError):
    code = "PACKAGE_PLATFORM_ERROR"
    status_code = 422
    retryable = False


class PackageNotFoundError(PackagePlatformError):
    code = "PACKAGE_NOT_FOUND"
    status_code = 404


class PackageWorkspaceNotFoundError(PackagePlatformError):
    code = "PACKAGE_WORKSPACE_NOT_FOUND"
    status_code = 404


class PackageConflictError(PackagePlatformError):
    code = "PACKAGE_REVISION_CONFLICT"
    status_code = 409
    retryable = True


class PackageValidationError(PackagePlatformError):
    code = "PACKAGE_VALIDATION_FAILED"
    status_code = 422


class PackageShadowRequiredError(PackagePlatformError):
    code = "PACKAGE_SHADOW_REQUIRED"
    status_code = 409
    retryable = True


class PackageConfirmationRequiredError(PackagePlatformError):
    code = "PACKAGE_CONFIRMATION_REQUIRED"
    status_code = 409
    retryable = True


class PackagePluginHostError(PackagePlatformError):
    code = "PACKAGE_PLUGIN_HOST_FAILED"
    status_code = 503
