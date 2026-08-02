"""Typed HTTP boundary models for the V2 Project Kernel."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class V2Model(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ProjectMode(StrEnum):
    STANDARD = "STANDARD"
    EXPLORATION = "EXPLORATION"
    PLAN_ONLY = "PLAN_ONLY"


class ChangeSetStatus(StrEnum):
    DRAFT = "DRAFT"
    VALIDATING = "VALIDATING"
    READY = "READY"
    CONFIRMED = "CONFIRMED"
    COMMITTED = "COMMITTED"
    REJECTED = "REJECTED"
    CANCELED = "CANCELED"


class ChangeSetRiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ChangeSetConfirmationPolicy(StrEnum):
    AUTO = "AUTO"
    USER = "USER"
    EXPLICIT_RISK = "EXPLICIT_RISK"


class CapabilityKind(StrEnum):
    RESOURCE = "RESOURCE"
    PROCEDURE = "PROCEDURE"
    EXECUTION = "EXECUTION"
    COMPOSITE = "COMPOSITE"


class CapabilityStatus(StrEnum):
    SUGGESTED = "SUGGESTED"
    DRAFT = "DRAFT"
    VERIFIED = "VERIFIED"
    DEPRECATED = "DEPRECATED"
    INVALID = "INVALID"


class ChangeOperation(V2Model):
    op: Literal[
        "SET_PROJECT_MODE",
        "UPSERT_FACT",
        "REMOVE_FACT",
        "BIND_CAPABILITY",
        "UNBIND_CAPABILITY",
        "MARK_ARTIFACT_OUTDATED",
    ]
    path: str = Field(min_length=1, max_length=240)
    value: Any | None = None
    previous_hash: str | None = Field(default=None, alias="previousHash")

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        if not value.startswith("/") or ".." in value or "\\" in value:
            raise ValueError("Change operation path must be a normalized project path")
        return value


class ChangeSetValidationResult(V2Model):
    code: str
    severity: Literal["PASS", "WARNING", "FAIL"]
    message: str


class CreateChangeSetRequest(V2Model):
    base_project_version: int = Field(alias="baseProjectVersion", ge=0)
    author_type: Literal["USER", "EXPERT", "SYSTEM"] = Field(
        default="USER", alias="authorType"
    )
    owner_domain: Literal[
        "problem_guide", "engineering", "structure", "delivery"
    ] = Field(alias="ownerDomain")
    intent_summary: str = Field(alias="intentSummary", min_length=1, max_length=500)
    operations: list[ChangeOperation] = Field(min_length=1, max_length=100)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=8, max_length=160)


class CreateReleaseRequest(V2Model):
    project_version_id: str | None = Field(default=None, alias="projectVersionId")
    name: str = Field(min_length=1, max_length=120)
    notes: str = Field(default="", max_length=4000)


class ProjectStateResponse(V2Model):
    state: dict[str, Any]


class ChangeSetResponse(V2Model):
    change_set: dict[str, Any] = Field(alias="changeSet")


class ChangeSetListResponse(V2Model):
    change_sets: list[dict[str, Any]] = Field(alias="changeSets")


class ProjectVersionListResponse(V2Model):
    versions: list[dict[str, Any]]


class ProjectReleaseListResponse(V2Model):
    releases: list[dict[str, Any]]


class CapabilityListResponse(V2Model):
    capabilities: list[dict[str, Any]]


class CapabilityCoverageResponse(V2Model):
    coverage: dict[str, Any]
