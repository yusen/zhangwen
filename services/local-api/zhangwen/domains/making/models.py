"""Strict contracts for the two project-making routes."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, field_validator

from zhangwen.domains.classroom.models import (
    BuildRoute,
    ProjectLearningModel,
    ProjectProcessState,
    StructurePolicy,
)


class MakingRouteStatus(StrEnum):
    CURRENT = "CURRENT"
    SUPERSEDED = "SUPERSEDED"
    STALE = "STALE"


class StructureRevisionStatus(StrEnum):
    READY = "READY"
    BLOCKED = "BLOCKED"
    STALE = "STALE"


class AssemblyRecordStatus(StrEnum):
    CURRENT = "CURRENT"
    STALE = "STALE"


class ChooseBuildRouteRequest(ProjectLearningModel):
    route: BuildRoute
    rationale: str = Field(min_length=2, max_length=2000)
    idempotency_key: str = Field(
        alias="idempotencyKey", min_length=4, max_length=160
    )

    @field_validator("rationale", "idempotency_key")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        return value.strip()


class BuildRouteDecisionRecord(ProjectLearningModel):
    id: str
    work_id: str = Field(alias="workId")
    version: int = Field(ge=1)
    route: BuildRoute
    rationale: str
    selected_by: str = Field(alias="selectedBy")
    policy_revision_id: str | None = Field(alias="policyRevisionId")
    simulation_run_id: str | None = Field(alias="simulationRunId")
    supersedes_revision_id: str | None = Field(alias="supersedesRevisionId")
    status: MakingRouteStatus
    created_at: str = Field(alias="createdAt")
    invalidated_at: str | None = Field(alias="invalidatedAt")
    invalidation_reason: str | None = Field(alias="invalidationReason")


class StructureDimensionCheck(ProjectLearningModel):
    name: str = Field(min_length=1, max_length=160)
    expected_mm: float = Field(alias="expectedMm", gt=0, le=10_000)
    actual_mm: float = Field(alias="actualMm", gt=0, le=10_000)
    tolerance_mm: float = Field(alias="toleranceMm", ge=0, le=100)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        return value.strip()


class StructureInterferenceCheck(ProjectLearningModel):
    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$")
    label: str = Field(min_length=1, max_length=300)
    passed: bool
    note: str = Field(default="", max_length=1000)

    @field_validator("label", "note")
    @classmethod
    def _strip_interference_text(cls, value: str) -> str:
        return value.strip()


class CreateStructureRevisionRequest(ProjectLearningModel):
    build_route_decision_id: str = Field(alias="buildRouteDecisionId", min_length=1)
    cad_intent_revision_id: str = Field(alias="cadIntentRevisionId", min_length=1)
    requirements: list[str] = Field(min_length=1, max_length=40)
    mechanical_profile_revision_ids: list[str] = Field(
        alias="mechanicalProfileRevisionIds", max_length=40
    )
    dimensions: list[StructureDimensionCheck] = Field(min_length=1, max_length=80)
    interference_checks: list[StructureInterferenceCheck] = Field(
        alias="interferenceChecks", min_length=1, max_length=80
    )
    material: str = Field(min_length=1, max_length=200)
    fabrication_method: str = Field(
        alias="fabricationMethod", min_length=1, max_length=300
    )
    manufacturing_notes: str = Field(
        alias="manufacturingNotes", min_length=1, max_length=4000
    )
    idempotency_key: str = Field(
        alias="idempotencyKey", min_length=4, max_length=160
    )

    @field_validator(
        "build_route_decision_id",
        "cad_intent_revision_id",
        "material",
        "fabrication_method",
        "manufacturing_notes",
        "idempotency_key",
    )
    @classmethod
    def _strip_scalar(cls, value: str) -> str:
        return value.strip()

    @field_validator("requirements", "mechanical_profile_revision_ids")
    @classmethod
    def _normalize_list(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item.strip()]
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("items must be unique")
        return cleaned


class StructureRevisionRecord(ProjectLearningModel):
    id: str
    work_id: str = Field(alias="workId")
    build_route_decision_id: str = Field(alias="buildRouteDecisionId")
    version: int = Field(ge=1)
    cad_intent_revision_id: str = Field(alias="cadIntentRevisionId")
    artifact_id: str = Field(alias="artifactId")
    artifact_version_id: str = Field(alias="artifactVersionId")
    requirements: list[str]
    mechanical_profile_revision_ids: list[str] = Field(
        alias="mechanicalProfileRevisionIds"
    )
    dimensions: list[StructureDimensionCheck]
    interference_checks: list[StructureInterferenceCheck] = Field(
        alias="interferenceChecks"
    )
    material: str
    fabrication_method: str = Field(alias="fabricationMethod")
    manufacturing_notes: str = Field(alias="manufacturingNotes")
    status: StructureRevisionStatus
    digital_validation_only: bool = Field(alias="digitalValidationOnly")
    created_by: str = Field(alias="createdBy")
    created_at: str = Field(alias="createdAt")
    invalidated_at: str | None = Field(alias="invalidatedAt")
    invalidation_reason: str | None = Field(alias="invalidationReason")


class AssemblyChecklistItem(ProjectLearningModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,79}$")
    passed: bool
    note: str = Field(min_length=1, max_length=1000)

    @field_validator("note")
    @classmethod
    def _strip_note(cls, value: str) -> str:
        return value.strip()


class RecordAssemblyRequest(ProjectLearningModel):
    build_route_decision_id: str = Field(alias="buildRouteDecisionId", min_length=1)
    structure_revision_id: str | None = Field(alias="structureRevisionId")
    wiring_plan: str = Field(alias="wiringPlan", min_length=2, max_length=4000)
    fixing_method: str = Field(alias="fixingMethod", min_length=2, max_length=4000)
    insulation_plan: str = Field(alias="insulationPlan", min_length=2, max_length=4000)
    power_plan: str = Field(alias="powerPlan", min_length=2, max_length=4000)
    assembly_steps: list[str] = Field(alias="assemblySteps", min_length=2, max_length=80)
    checklist: list[AssemblyChecklistItem] = Field(min_length=4, max_length=80)
    fabrication_confirmed: bool = Field(alias="fabricationConfirmed")
    observations: list[str] = Field(min_length=1, max_length=80)
    reflection: str = Field(min_length=2, max_length=4000)
    evidence_artifact_version_ids: list[str] = Field(
        alias="evidenceArtifactVersionIds", max_length=30
    )
    attested_by_user: bool = Field(alias="attestedByUser")
    idempotency_key: str = Field(
        alias="idempotencyKey", min_length=4, max_length=160
    )

    @field_validator(
        "build_route_decision_id",
        "wiring_plan",
        "fixing_method",
        "insulation_plan",
        "power_plan",
        "reflection",
        "idempotency_key",
    )
    @classmethod
    def _strip_assembly_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("assembly_steps", "observations", "evidence_artifact_version_ids")
    @classmethod
    def _normalize_assembly_list(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item.strip()]
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("items must be unique")
        return cleaned


class AssemblyRecord(ProjectLearningModel):
    id: str
    work_id: str = Field(alias="workId")
    build_route_decision_id: str = Field(alias="buildRouteDecisionId")
    structure_revision_id: str | None = Field(alias="structureRevisionId")
    version: int = Field(ge=1)
    wiring_plan: str = Field(alias="wiringPlan")
    fixing_method: str = Field(alias="fixingMethod")
    insulation_plan: str = Field(alias="insulationPlan")
    power_plan: str = Field(alias="powerPlan")
    assembly_steps: list[str] = Field(alias="assemblySteps")
    checklist: list[AssemblyChecklistItem]
    fabrication_confirmed: bool = Field(alias="fabricationConfirmed")
    observations: list[str]
    reflection: str
    evidence_artifact_version_ids: list[str] = Field(
        alias="evidenceArtifactVersionIds"
    )
    status: AssemblyRecordStatus
    attested_by: str = Field(alias="attestedBy")
    created_at: str = Field(alias="createdAt")
    invalidated_at: str | None = Field(alias="invalidatedAt")
    invalidation_reason: str | None = Field(alias="invalidationReason")


class CadStructureCandidate(ProjectLearningModel):
    id: str
    summary: str
    artifact_id: str = Field(alias="artifactId")
    artifact_version_id: str = Field(alias="artifactVersionId")
    output_roles: list[str] = Field(alias="outputRoles")
    ready: bool
    confirmed_at: str | None = Field(alias="confirmedAt")


class MechanicalProfileRef(ProjectLearningModel):
    id: str
    profile_id: str = Field(alias="profileId")
    revision: str
    display_name: str = Field(alias="displayName")
    evidence_level: str = Field(alias="evidenceLevel")
    content_sha256: str = Field(alias="contentSha256")


class MakingWorkspace(ProjectLearningModel):
    structure_policy: StructurePolicy = Field(alias="structurePolicy")
    process_state: ProjectProcessState = Field(alias="processState")
    route_decisions: list[BuildRouteDecisionRecord] = Field(alias="routeDecisions")
    current_decision: BuildRouteDecisionRecord | None = Field(alias="currentDecision")
    structure_revisions: list[StructureRevisionRecord] = Field(
        alias="structureRevisions"
    )
    current_structure: StructureRevisionRecord | None = Field(alias="currentStructure")
    assembly_records: list[AssemblyRecord] = Field(alias="assemblyRecords")
    current_assembly: AssemblyRecord | None = Field(alias="currentAssembly")
    cad_candidates: list[CadStructureCandidate] = Field(alias="cadCandidates")
    mechanical_profiles: list[MechanicalProfileRef] = Field(alias="mechanicalProfiles")
    can_choose_route: bool = Field(alias="canChooseRoute")
    can_record_structure: bool = Field(alias="canRecordStructure")
    can_record_assembly: bool = Field(alias="canRecordAssembly")
    deployment_ready: bool = Field(alias="deploymentReady")
    blocked_reason: str | None = Field(alias="blockedReason")
