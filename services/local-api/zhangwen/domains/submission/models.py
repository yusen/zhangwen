"""Strict E9 submission, review, progress and sync contracts."""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator

from zhangwen.domains.classroom.models import (
    Assignment,
    InstructorReviewDecision,
    ProjectLearningModel,
    ProjectProcessState,
    RubricAssessmentStatus,
    RubricRevision,
    SubmissionStatus,
)


class SubmissionContent(ProjectLearningModel):
    title: str = Field(min_length=2, max_length=240)
    summary: str = Field(min_length=10, max_length=12_000)
    deliverables: list[str] = Field(min_length=1, max_length=80)
    process_reflection: str = Field(
        alias="processReflection", min_length=10, max_length=12_000
    )
    reproduction_steps: list[str] = Field(
        alias="reproductionSteps", min_length=1, max_length=80
    )
    known_limitations: list[str] = Field(
        alias="knownLimitations", default_factory=list, max_length=80
    )
    evidence_artifact_version_ids: list[str] = Field(
        alias="evidenceArtifactVersionIds", default_factory=list, max_length=40
    )

    @field_validator("title", "summary", "process_reflection")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator(
        "deliverables",
        "reproduction_steps",
        "known_limitations",
        "evidence_artifact_version_ids",
    )
    @classmethod
    def _normalize_lists(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item.strip()]
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("列表项不能重复。")
        return cleaned


class CreateSubmissionDraftRequest(ProjectLearningModel):
    content: SubmissionContent
    idempotency_key: str = Field(
        alias="idempotencyKey", min_length=4, max_length=160
    )

    @field_validator("idempotency_key")
    @classmethod
    def _strip_key(cls, value: str) -> str:
        return value.strip()


class SubmitSubmissionRequest(ProjectLearningModel):
    submission_revision_id: str = Field(alias="submissionRevisionId", min_length=1)
    attested_by_user: bool = Field(alias="attestedByUser")
    idempotency_key: str = Field(
        alias="idempotencyKey", min_length=4, max_length=160
    )

    @field_validator("submission_revision_id", "idempotency_key")
    @classmethod
    def _strip_submit_text(cls, value: str) -> str:
        return value.strip()


class SubmissionManifest(ProjectLearningModel):
    proposal_revision_id: str = Field(alias="proposalRevisionId")
    simulation_run_id: str = Field(alias="simulationRunId")
    build_route_decision_id: str = Field(alias="buildRouteDecisionId")
    structure_revision_id: str | None = Field(alias="structureRevisionId")
    assembly_record_id: str = Field(alias="assemblyRecordId")
    deployment_bundle_id: str | None = Field(alias="deploymentBundleId")
    device_deployment_id: str | None = Field(alias="deviceDeploymentId")
    physical_observation_id: str | None = Field(alias="physicalObservationId")
    rubric_revision_id: str = Field(alias="rubricRevisionId")
    artifact_version_ids: list[str] = Field(alias="artifactVersionIds")


class SubmissionRevisionRecord(ProjectLearningModel):
    id: str
    work_id: str = Field(alias="workId")
    version: int = Field(ge=1)
    status: SubmissionStatus
    proposal_revision_id: str = Field(alias="proposalRevisionId")
    simulation_run_id: str = Field(alias="simulationRunId")
    build_route_decision_id: str = Field(alias="buildRouteDecisionId")
    structure_revision_id: str | None = Field(alias="structureRevisionId")
    assembly_record_id: str = Field(alias="assemblyRecordId")
    deployment_bundle_id: str | None = Field(alias="deploymentBundleId")
    device_deployment_id: str | None = Field(alias="deviceDeploymentId")
    physical_observation_id: str | None = Field(alias="physicalObservationId")
    rubric_revision_id: str = Field(alias="rubricRevisionId")
    content: SubmissionContent
    manifest: SubmissionManifest
    manifest_sha256: str = Field(alias="manifestSha256", min_length=64, max_length=64)
    submitted_by: str | None = Field(alias="submittedBy")
    submitted_at: str | None = Field(alias="submittedAt")
    supersedes_revision_id: str | None = Field(alias="supersedesRevisionId")
    created_by: str = Field(alias="createdBy")
    created_at: str = Field(alias="createdAt")
    invalidated_at: str | None = Field(alias="invalidatedAt")
    invalidation_reason: str | None = Field(alias="invalidationReason")


class InstructorAnnotation(ProjectLearningModel):
    section: str = Field(min_length=1, max_length=160)
    comment: str = Field(min_length=2, max_length=4000)

    @field_validator("section", "comment")
    @classmethod
    def _strip_annotation(cls, value: str) -> str:
        return value.strip()


class ReviewSubmissionRequest(ProjectLearningModel):
    submission_revision_id: str = Field(alias="submissionRevisionId", min_length=1)
    decision: InstructorReviewDecision
    feedback: str = Field(min_length=2, max_length=12_000)
    annotations: list[InstructorAnnotation] = Field(default_factory=list, max_length=80)
    scores: dict[str, float] = Field(min_length=1, max_length=80)
    idempotency_key: str = Field(
        alias="idempotencyKey", min_length=4, max_length=160
    )

    @field_validator("submission_revision_id", "feedback", "idempotency_key")
    @classmethod
    def _strip_review_text(cls, value: str) -> str:
        return value.strip()


class InstructorReviewRecord(ProjectLearningModel):
    id: str
    work_id: str = Field(alias="workId")
    submission_revision_id: str = Field(alias="submissionRevisionId")
    decision: InstructorReviewDecision
    reviewer_subject: str = Field(alias="reviewerSubject")
    feedback: str
    annotations: list[InstructorAnnotation]
    created_at: str = Field(alias="createdAt")


class RubricAssessmentRecord(ProjectLearningModel):
    id: str
    work_id: str = Field(alias="workId")
    submission_revision_id: str = Field(alias="submissionRevisionId")
    rubric_revision_id: str = Field(alias="rubricRevisionId")
    instructor_review_id: str = Field(alias="instructorReviewId")
    reviewer_subject: str = Field(alias="reviewerSubject")
    scores: dict[str, float]
    total_score: float = Field(alias="totalScore", ge=0)
    status: RubricAssessmentStatus
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class ReviewSubmissionResult(ProjectLearningModel):
    submission: SubmissionRevisionRecord
    review: InstructorReviewRecord
    assessment: RubricAssessmentRecord


class ContributionKind(StrEnum):
    PLANNING = "PLANNING"
    CODE = "CODE"
    CIRCUIT = "CIRCUIT"
    TEST = "TEST"
    MAKING = "MAKING"
    DOCUMENTATION = "DOCUMENTATION"
    REFLECTION = "REFLECTION"


class RecordContributionRequest(ProjectLearningModel):
    kind: ContributionKind
    summary: str = Field(min_length=2, max_length=4000)
    related_kind: str | None = Field(alias="relatedKind", default=None, max_length=120)
    related_id: str | None = Field(alias="relatedId", default=None, max_length=300)
    idempotency_key: str = Field(
        alias="idempotencyKey", min_length=4, max_length=160
    )

    @field_validator("summary", "idempotency_key")
    @classmethod
    def _strip_contribution_text(cls, value: str) -> str:
        return value.strip()


class TeamContributionRecord(ProjectLearningModel):
    id: str
    work_id: str = Field(alias="workId")
    kind: ContributionKind
    contributor_subject: str = Field(alias="contributorSubject")
    summary: str
    related_kind: str | None = Field(alias="relatedKind")
    related_id: str | None = Field(alias="relatedId")
    work_revision: int = Field(alias="workRevision", ge=1)
    created_at: str = Field(alias="createdAt")


class SyncMutationKind(StrEnum):
    JOURNAL_APPEND = "JOURNAL_APPEND"
    CONTRIBUTION_RECORD = "CONTRIBUTION_RECORD"


class ClassroomSyncMutation(ProjectLearningModel):
    operation_id: str = Field(
        alias="operationId", pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,159}$"
    )
    work_id: str = Field(alias="workId", min_length=1)
    kind: SyncMutationKind
    base_work_revision: int = Field(alias="baseWorkRevision", ge=1)
    payload: dict[str, Any]

    @field_validator("payload")
    @classmethod
    def _bound_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        try:
            encoded = json.dumps(
                value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
            ).encode("utf-8")
        except (TypeError, ValueError, RecursionError) as exc:
            raise ValueError("离线操作内容必须是有限 JSON。") from exc
        if len(encoded) > 64 * 1024:
            raise ValueError("单条离线操作不能超过 64 KiB。")
        return value


class ApplySyncBatchRequest(ProjectLearningModel):
    device_id: str = Field(alias="deviceId", min_length=4, max_length=200)
    operations: list[ClassroomSyncMutation] = Field(min_length=1, max_length=50)


class SyncReceiptStatus(StrEnum):
    APPLIED = "APPLIED"
    DUPLICATE = "DUPLICATE"
    CONFLICT = "CONFLICT"
    REJECTED = "REJECTED"


class ClassroomSyncReceipt(ProjectLearningModel):
    operation_id: str = Field(alias="operationId")
    work_id: str = Field(alias="workId")
    status: SyncReceiptStatus
    result_ref: str | None = Field(alias="resultRef")
    server_work_revision: int = Field(alias="serverWorkRevision", ge=1)
    conflict_reason: str | None = Field(alias="conflictReason")


class ApplySyncBatchResult(ProjectLearningModel):
    receipts: list[ClassroomSyncReceipt]


class RedactedEvidenceSummary(ProjectLearningModel):
    id: str
    kind: str
    status: str
    passed: bool
    label: str
    source_id: None = Field(alias="sourceId", default=None)
    recorded_at: str = Field(alias="recordedAt")


class ProjectSubmissionWorkspace(ProjectLearningModel):
    work_revision: int = Field(alias="workRevision", ge=1)
    process_state: ProjectProcessState = Field(alias="processState")
    rubric: RubricRevision
    submission_requirements: list[str] = Field(alias="submissionRequirements")
    submissions: list[SubmissionRevisionRecord]
    current_submission: SubmissionRevisionRecord | None = Field(
        alias="currentSubmission"
    )
    reviews: list[InstructorReviewRecord]
    current_review: InstructorReviewRecord | None = Field(alias="currentReview")
    assessments: list[RubricAssessmentRecord]
    contributions: list[TeamContributionRecord]
    sync_receipts: list[ClassroomSyncReceipt] = Field(alias="syncReceipts")
    redacted_evidence: list[RedactedEvidenceSummary] = Field(
        alias="redactedEvidence"
    )
    can_edit: bool = Field(alias="canEdit")
    can_submit: bool = Field(alias="canSubmit")
    can_review: bool = Field(alias="canReview")
    blocking_reasons: list[str] = Field(alias="blockingReasons")


class AssignmentProgressWork(ProjectLearningModel):
    work_id: str = Field(alias="workId")
    project_name: str = Field(alias="projectName")
    state: ProjectProcessState
    checkpoints: list[dict[str, object]]
    needs_help: list[str] = Field(alias="needsHelp")
    review_pending: bool = Field(alias="reviewPending")
    member_count: int = Field(alias="memberCount", ge=0)
    contribution_count: int = Field(alias="contributionCount", ge=0)
    updated_at: str = Field(alias="updatedAt")


class CheckpointCount(ProjectLearningModel):
    kind: str
    label: str
    completed: int = Field(ge=0)
    total: int = Field(ge=0)


class AssignmentProgressOverview(ProjectLearningModel):
    assignment_id: str = Field(alias="assignmentId")
    works: list[AssignmentProgressWork]
    checkpoint_counts: list[CheckpointCount] = Field(alias="checkpointCounts")


class CopyAssignmentRequest(ProjectLearningModel):
    target_class_group_id: str = Field(alias="targetClassGroupId", min_length=1)
    title: str = Field(min_length=2, max_length=240)
    idempotency_key: str = Field(
        alias="idempotencyKey", min_length=4, max_length=160
    )


class CourseExportBundle(ProjectLearningModel):
    schema_name: str = Field(alias="schema")
    exported_at: str = Field(alias="exportedAt")
    course: dict[str, object]
    classes: list[dict[str, object]]
    assignments: list[dict[str, object]]
    work_summaries: list[dict[str, object]] = Field(alias="workSummaries")
    redacted_evidence: list[dict[str, object]] = Field(alias="redactedEvidence")


class EvidenceResetRequest(ProjectLearningModel):
    confirmation: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=4, max_length=4000)
    idempotency_key: str = Field(
        alias="idempotencyKey", min_length=4, max_length=160
    )

    @field_validator("confirmation", "reason", "idempotency_key")
    @classmethod
    def _strip_reset_text(cls, value: str) -> str:
        return value.strip()


class EvidenceResetRecord(ProjectLearningModel):
    id: str
    work_id: str = Field(alias="workId")
    reason: str
    requested_by: str = Field(alias="requestedBy")
    invalidated_evidence_count: int = Field(
        alias="invalidatedEvidenceCount", ge=0
    )
    created_at: str = Field(alias="createdAt")


class CopyAssignmentResult(ProjectLearningModel):
    assignment: Assignment
