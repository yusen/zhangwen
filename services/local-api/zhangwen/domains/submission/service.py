"""Submission, teacher review, classroom progress and offline sync services."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from zhangwen.auth.context import current_owner_subject
from zhangwen.domains.classroom.models import (
    Assignment,
    InstructorReviewDecision,
    ProcessJournalEntryKind,
    ProjectCheckpointKind,
    ProjectProcessState,
    RubricAssessmentStatus,
    RubricRevision,
    SubmissionStatus,
)
from zhangwen.domains.classroom.repository import ClassroomRepository
from zhangwen.domains.simulation.digest import canonical_digest
from zhangwen.domains.submission.models import (
    ApplySyncBatchRequest,
    ApplySyncBatchResult,
    AssignmentProgressOverview,
    AssignmentProgressWork,
    CheckpointCount,
    ClassroomSyncMutation,
    ClassroomSyncReceipt,
    ContributionKind,
    CopyAssignmentRequest,
    CourseExportBundle,
    CreateSubmissionDraftRequest,
    EvidenceResetRecord,
    EvidenceResetRequest,
    InstructorReviewRecord,
    ProjectSubmissionWorkspace,
    RecordContributionRequest,
    RedactedEvidenceSummary,
    ReviewSubmissionRequest,
    ReviewSubmissionResult,
    RubricAssessmentRecord,
    SubmissionManifest,
    SubmissionRevisionRecord,
    SyncMutationKind,
    TeamContributionRecord,
)


_LOCAL_SUBJECT = "__local__"
_REAL_EVIDENCE_KINDS = {
    "DEPLOYMENT",
    "PHYSICAL_BEHAVIOR",
    "USER_ACCEPTANCE",
    "REPRODUCTION",
}
_EVIDENCE_LABELS = {
    "GOAL_CONFIRMATION": "目标已经确认",
    "STATIC_VALIDATION": "电路静态检查已有记录",
    "SIMULATION": "仿真场景已通过",
    "DEVICE_CONNECTION": "设备连接已有记录",
    "DEPLOYMENT": "代码上传与回读已有记录",
    "PHYSICAL_BEHAVIOR": "实物观察已由用户确认",
    "USER_ACCEPTANCE": "用户验收已有记录",
    "REPRODUCTION": "复现检查已有记录",
    "STRUCTURE_CHECK": "装配与安全检查已有记录",
}
_CHECKPOINT_LABELS = {
    ProjectCheckpointKind.PROPOSAL_STUDENT_CONFIRMED: "学生确认方案书",
    ProjectCheckpointKind.PROPOSAL_INSTRUCTOR_APPROVED: "方案书经教师通过",
    ProjectCheckpointKind.SCHEMATIC_VALIDATED: "电路静态检查通过",
    ProjectCheckpointKind.BEHAVIOR_SIMULATION_PASSED: "行为仿真场景通过",
    ProjectCheckpointKind.BUILD_ROUTE_SELECTED: "制作路径已选择",
    ProjectCheckpointKind.DEVICE_UPLOAD_VERIFIED: "代码上传与回读通过",
    ProjectCheckpointKind.PHYSICAL_BEHAVIOR_CONFIRMED: "实物行为经人工确认",
    ProjectCheckpointKind.SUBMISSION_INSTRUCTOR_ACCEPTED: "最终提交经教师通过",
}


class ProjectSubmissionError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 422,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable


class ProjectSubmissionService:
    """Pins one Work revision set and keeps student and teacher commands separate."""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = Path(data_dir)
        self._classroom = ClassroomRepository(self._data_dir)
        self._db_path = self._classroom.db_path
        self._actor = current_owner_subject() or _LOCAL_SUBJECT

    def get_workspace(self, work_id: str) -> ProjectSubmissionWorkspace:
        self._classroom.assert_work_access(work_id)
        with self._connect() as conn:
            context = self._context(conn, work_id)
            submission_rows = conn.execute(
                "SELECT * FROM project_submission_revisions WHERE work_id = ? "
                "ORDER BY version DESC, created_at DESC, id DESC",
                (work_id,),
            ).fetchall()
            review_rows = conn.execute(
                "SELECT * FROM project_instructor_reviews WHERE work_id = ? "
                "ORDER BY created_at DESC, id DESC",
                (work_id,),
            ).fetchall()
            assessment_rows = conn.execute(
                "SELECT * FROM project_rubric_assessments WHERE work_id = ? "
                "ORDER BY updated_at DESC, id DESC",
                (work_id,),
            ).fetchall()
            contribution_rows = conn.execute(
                "SELECT * FROM project_team_contributions WHERE work_id = ? "
                "ORDER BY created_at DESC, id DESC",
                (work_id,),
            ).fetchall()
            sync_rows = conn.execute(
                "SELECT * FROM classroom_sync_inbox "
                "WHERE work_id = ? AND actor_subject = ? "
                "ORDER BY received_at DESC, id DESC LIMIT 50",
                (work_id, self._actor),
            ).fetchall()
            evidence_rows = conn.execute(
                "SELECT id, kind, status, passed, recorded_at FROM creator_evidence "
                "WHERE project_id = ? ORDER BY recorded_at DESC, id DESC",
                (work_id,),
            ).fetchall()
            rubric_row = conn.execute(
                "SELECT * FROM rubric_revisions WHERE id = ?",
                (context["rubric_revision_id"],),
            ).fetchone()
            can_edit = self._can_student_edit(conn, work_id)
            can_review = self._is_instructor(conn, work_id)
            blockers = self._submission_blockers(conn, work_id, context)

        submissions = [_submission(row) for row in submission_rows if row["manifest_sha256"]]
        reviews = [_review(row) for row in review_rows]
        assessments = [
            _assessment(row)
            for row in assessment_rows
            if row["instructor_review_id"] is not None
        ]
        current_id = _optional(context["current_submission_revision_id"])
        current_submission = next(
            (item for item in submissions if item.id == current_id), None
        )
        current_review = next(
            (
                item
                for item in reviews
                if current_submission is not None
                and item.submission_revision_id == current_submission.id
            ),
            None,
        )
        can_submit = bool(
            can_edit
            and current_submission is not None
            and current_submission.status is SubmissionStatus.DRAFT
            and not blockers
        )
        return ProjectSubmissionWorkspace(
            workRevision=int(context["revision"]),
            processState=str(context["process_state"]),
            rubric=_rubric(_present(rubric_row)),
            submissionRequirements=json.loads(
                str(context["submission_requirements_json"])
            ),
            submissions=submissions,
            currentSubmission=current_submission,
            reviews=reviews,
            currentReview=current_review,
            assessments=assessments,
            contributions=[_contribution(row) for row in contribution_rows],
            syncReceipts=[_sync_receipt(row) for row in sync_rows],
            redactedEvidence=[_redacted_evidence(row) for row in evidence_rows],
            canEdit=can_edit,
            canSubmit=can_submit,
            canReview=bool(
                can_review
                and current_submission is not None
                and current_submission.status is SubmissionStatus.SUBMITTED
            ),
            blockingReasons=blockers,
        )

    def create_draft(
        self, *, work_id: str, request: CreateSubmissionDraftRequest
    ) -> SubmissionRevisionRecord:
        now = _now()
        request_payload = request.model_dump(mode="json", by_alias=True)
        request_digest = canonical_digest(request_payload)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._require_student_editor(conn, work_id)
            context = self._context(conn, work_id)
            existing = conn.execute(
                "SELECT * FROM project_submission_revisions "
                "WHERE work_id = ? AND idempotency_key = ?",
                (work_id, request.idempotency_key),
            ).fetchone()
            if existing is not None:
                self._assert_digest(existing, request_digest, "提交草稿")
                return _submission(existing)

            current = self._current_submission_row(conn, context)
            if current is not None and str(current["status"]) in {
                SubmissionStatus.SUBMITTED.value,
                SubmissionStatus.ACCEPTED.value,
            }:
                raise ProjectSubmissionError(
                    "SUBMISSION_REVIEW_PENDING",
                    "当前提交仍在评审或已经通过，不能覆盖学生事实。",
                    status_code=409,
                )
            blockers = self._submission_blockers(conn, work_id, context)
            if blockers:
                raise ProjectSubmissionError(
                    "SUBMISSION_PREREQUISITES_INCOMPLETE",
                    blockers[0],
                    status_code=409,
                )
            self._validate_artifact_versions(
                conn, work_id, request.content.evidence_artifact_version_ids
            )
            manifest = self._current_manifest(
                conn,
                work_id,
                context,
                artifact_version_ids=request.content.evidence_artifact_version_ids,
            )
            manifest_json = manifest.model_dump(mode="json", by_alias=True)
            manifest_sha256 = canonical_digest(manifest_json)
            version = int(
                conn.execute(
                    "SELECT COALESCE(MAX(version), 0) + 1 "
                    "FROM project_submission_revisions WHERE work_id = ?",
                    (work_id,),
                ).fetchone()[0]
            )
            previous_id = str(current["id"]) if current is not None else None
            if current is not None:
                conn.execute(
                    "UPDATE project_submission_revisions "
                    "SET status = 'SUPERSEDED', invalidated_at = ?, "
                    "invalidation_reason = ? WHERE id = ?",
                    (now, "学生创建了新的提交修订。", previous_id),
                )
            submission_id = _id("submission")
            conn.execute(
                """
                INSERT INTO project_submission_revisions (
                  id, work_id, version, status, proposal_revision_id,
                  simulation_run_id, build_route_decision_id, content_json,
                  submitted_by, submitted_at, supersedes_revision_id,
                  created_by, created_at, structure_revision_id,
                  assembly_record_id, deployment_bundle_id,
                  device_deployment_id, physical_observation_id,
                  rubric_revision_id, manifest_json, manifest_sha256,
                  idempotency_key, request_digest,
                  invalidated_at, invalidation_reason
                ) VALUES (?, ?, ?, 'DRAFT', ?, ?, ?, ?, NULL, NULL, ?, ?, ?,
                          ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
                """,
                (
                    submission_id,
                    work_id,
                    version,
                    manifest.proposal_revision_id,
                    manifest.simulation_run_id,
                    manifest.build_route_decision_id,
                    _dump(request.content.model_dump(mode="json", by_alias=True)),
                    previous_id,
                    self._actor,
                    now,
                    manifest.structure_revision_id,
                    manifest.assembly_record_id,
                    manifest.deployment_bundle_id,
                    manifest.device_deployment_id,
                    manifest.physical_observation_id,
                    manifest.rubric_revision_id,
                    _dump(manifest_json),
                    manifest_sha256,
                    request.idempotency_key,
                    request_digest,
                ),
            )
            next_revision = int(context["revision"]) + 1
            conn.execute(
                """
                UPDATE work_learning_contexts
                SET current_submission_revision_id = ?,
                    process_state = 'SUBMISSION_DRAFT', process_milestone = 'MAKING',
                    revision = ?, updated_at = ?
                WHERE work_id = ?
                """,
                (submission_id, next_revision, now, work_id),
            )
            self._journal(
                conn,
                work_id,
                self._actor,
                "SUBMISSION",
                "整理项目提交",
                "学生创建了固定当前方案、仿真与制作版本的提交草稿。",
                "submission_revision",
                submission_id,
                now,
            )
            self._outbox(
                conn,
                work_id,
                "SUBMISSION_DRAFTED",
                next_revision,
                {"submissionRevisionId": submission_id, "version": version},
                now,
            )
            row = conn.execute(
                "SELECT * FROM project_submission_revisions WHERE id = ?",
                (submission_id,),
            ).fetchone()
            conn.commit()
        return _submission(_present(row))

    def submit(
        self, *, work_id: str, request: SubmitSubmissionRequest
    ) -> SubmissionRevisionRecord:
        if not request.attested_by_user:
            raise ProjectSubmissionError(
                "SUBMISSION_USER_ATTESTATION_REQUIRED",
                "提交必须由当前学生明确确认，不能由模型或后台代签。",
                status_code=409,
            )
        now = _now()
        request_digest = canonical_digest(
            request.model_dump(mode="json", by_alias=True)
        )
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._require_student_editor(conn, work_id)
            replay = self._submission_command_replay(
                conn,
                work_id,
                request.idempotency_key,
                request_digest,
                expected_command="SUBMIT",
            )
            if replay is not None:
                return _submission(
                    self._submission_row(conn, work_id, replay["submissionRevisionId"])
                )
            context = self._context(conn, work_id)
            row = self._submission_row(
                conn, work_id, request.submission_revision_id
            )
            if _optional(context["current_submission_revision_id"]) != str(row["id"]):
                if str(row["status"]) == SubmissionStatus.SUPERSEDED.value:
                    raise ProjectSubmissionError(
                        "SUBMISSION_REVISION_SET_STALE",
                        "方案、仿真或制作版本已经变化，请创建新的提交草稿。",
                        status_code=409,
                    )
                raise ProjectSubmissionError(
                    "SUBMISSION_NOT_CURRENT",
                    "只能提交当前草稿修订。",
                    status_code=409,
                )
            if str(row["status"]) != SubmissionStatus.DRAFT.value:
                raise ProjectSubmissionError(
                    "SUBMISSION_NOT_DRAFT",
                    "当前修订不是可提交的草稿。",
                    status_code=409,
                )
            blockers = self._submission_blockers(conn, work_id, context)
            if blockers:
                raise ProjectSubmissionError(
                    "SUBMISSION_PREREQUISITES_INCOMPLETE",
                    blockers[0],
                    status_code=409,
                )
            current_manifest = self._current_manifest(
                conn,
                work_id,
                context,
                artifact_version_ids=json.loads(str(row["manifest_json"]))[
                    "artifactVersionIds"
                ],
            )
            if canonical_digest(
                current_manifest.model_dump(mode="json", by_alias=True)
            ) != str(row["manifest_sha256"]):
                raise ProjectSubmissionError(
                    "SUBMISSION_REVISION_SET_STALE",
                    "方案、仿真或制作版本已经变化，请创建新的提交草稿。",
                    status_code=409,
                )
            conn.execute(
                "UPDATE project_submission_revisions "
                "SET status = 'SUBMITTED', submitted_by = ?, submitted_at = ? "
                "WHERE id = ?",
                (self._actor, now, row["id"]),
            )
            next_revision = int(context["revision"]) + 1
            conn.execute(
                """
                UPDATE work_learning_contexts
                SET process_state = 'SUBMISSION_IN_REVIEW', process_milestone = 'MAKING',
                    revision = ?, updated_at = ? WHERE work_id = ?
                """,
                (next_revision, now, work_id),
            )
            self._journal(
                conn,
                work_id,
                self._actor,
                "SUBMISSION",
                "提交教师评审",
                "学生明确确认并提交了当前项目版本。",
                "submission_revision",
                str(row["id"]),
                now,
            )
            self._outbox(
                conn,
                work_id,
                "SUBMISSION_SUBMITTED",
                next_revision,
                {"submissionRevisionId": str(row["id"])},
                now,
            )
            response = {"submissionRevisionId": str(row["id"])}
            self._store_submission_command(
                conn,
                work_id,
                str(row["id"]),
                "SUBMIT",
                request.idempotency_key,
                request_digest,
                response,
                now,
            )
            updated = conn.execute(
                "SELECT * FROM project_submission_revisions WHERE id = ?",
                (row["id"],),
            ).fetchone()
            conn.commit()
        return _submission(_present(updated))

    def review(
        self, *, work_id: str, request: ReviewSubmissionRequest
    ) -> ReviewSubmissionResult:
        now = _now()
        request_digest = canonical_digest(
            request.model_dump(mode="json", by_alias=True)
        )
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._require_instructor(conn, work_id)
            replay = self._submission_command_replay(
                conn,
                work_id,
                request.idempotency_key,
                request_digest,
                expected_command="REVIEW",
            )
            if replay is not None:
                submission = self._submission_row(
                    conn, work_id, replay["submissionRevisionId"]
                )
                review = conn.execute(
                    "SELECT * FROM project_instructor_reviews WHERE id = ?",
                    (replay["reviewId"],),
                ).fetchone()
                assessment = conn.execute(
                    "SELECT * FROM project_rubric_assessments WHERE id = ?",
                    (replay["assessmentId"],),
                ).fetchone()
                return ReviewSubmissionResult(
                    submission=_submission(submission),
                    review=_review(_present(review)),
                    assessment=_assessment(_present(assessment)),
                )

            context = self._context(conn, work_id)
            submission = self._submission_row(
                conn, work_id, request.submission_revision_id
            )
            if _optional(context["current_submission_revision_id"]) != str(
                submission["id"]
            ):
                raise ProjectSubmissionError(
                    "SUBMISSION_REVIEW_NOT_CURRENT",
                    "教师只能评审当前明确提交的修订。",
                    status_code=409,
                )
            if str(submission["status"]) != SubmissionStatus.SUBMITTED.value:
                raise ProjectSubmissionError(
                    "SUBMISSION_REVIEW_STATUS_INVALID",
                    "只有正在评审的提交可以作出教师决定。",
                    status_code=409,
                )
            rubric_row = conn.execute(
                "SELECT * FROM rubric_revisions WHERE id = ?",
                (submission["rubric_revision_id"],),
            ).fetchone()
            rubric = _rubric(_present(rubric_row))
            total_score = self._validate_scores(rubric, request.scores)
            review_id = _id("instructor-review")
            assessment_id = _id("rubric-assessment")
            conn.execute(
                """
                INSERT INTO project_instructor_reviews (
                  id, work_id, submission_revision_id, decision,
                  reviewer_subject, feedback, created_at,
                  annotations_json, idempotency_key, request_digest
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review_id,
                    work_id,
                    submission["id"],
                    request.decision.value,
                    self._actor,
                    request.feedback,
                    now,
                    _dump(
                        [
                            item.model_dump(mode="json", by_alias=True)
                            for item in request.annotations
                        ]
                    ),
                    request.idempotency_key,
                    request_digest,
                ),
            )
            conn.execute(
                """
                INSERT INTO project_rubric_assessments (
                  id, work_id, submission_revision_id, rubric_revision_id,
                  reviewer_subject, scores_json, total_score, status,
                  created_at, updated_at, instructor_review_id,
                  dimension_feedback_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'FINALIZED', ?, ?, ?, ?)
                """,
                (
                    assessment_id,
                    work_id,
                    submission["id"],
                    rubric.id,
                    self._actor,
                    _dump(request.scores),
                    total_score,
                    now,
                    now,
                    review_id,
                    _dump(
                        {
                            item.section: item.comment
                            for item in request.annotations
                        }
                    ),
                ),
            )
            accepted = request.decision is InstructorReviewDecision.ACCEPTED
            submission_status = (
                SubmissionStatus.ACCEPTED.value
                if accepted
                else SubmissionStatus.CHANGES_REQUESTED.value
            )
            process_state = (
                ProjectProcessState.COMPLETED.value
                if accepted
                else ProjectProcessState.SUBMISSION_CHANGES_REQUESTED.value
            )
            process_milestone = "COMPLETE" if accepted else "MAKING"
            conn.execute(
                "UPDATE project_submission_revisions SET status = ? WHERE id = ?",
                (submission_status, submission["id"]),
            )
            next_revision = int(context["revision"]) + 1
            conn.execute(
                """
                UPDATE work_learning_contexts
                SET process_state = ?, process_milestone = ?, revision = ?, updated_at = ?
                WHERE work_id = ?
                """,
                (process_state, process_milestone, next_revision, now, work_id),
            )
            if accepted:
                conn.execute(
                    """
                    INSERT INTO project_checkpoint_reviews (
                      id, work_id, checkpoint, target_kind, target_revision_id,
                      decision, reviewer_subject, comment, created_at
                    ) VALUES (?, ?, 'SUBMISSION_INSTRUCTOR_ACCEPTED',
                              'SUBMISSION_REVISION', ?, 'APPROVED', ?, ?, ?)
                    """,
                    (
                        _id("checkpoint-review"),
                        work_id,
                        submission["id"],
                        self._actor,
                        request.feedback,
                        now,
                    ),
                )
            self._journal(
                conn,
                work_id,
                self._actor,
                "INSTRUCTOR_FEEDBACK",
                "教师通过项目提交" if accepted else "教师退回项目提交",
                request.feedback,
                "submission_revision",
                str(submission["id"]),
                now,
            )
            self._outbox(
                conn,
                work_id,
                "SUBMISSION_ACCEPTED" if accepted else "SUBMISSION_CHANGES_REQUESTED",
                next_revision,
                {
                    "submissionRevisionId": str(submission["id"]),
                    "reviewId": review_id,
                },
                now,
            )
            response = {
                "submissionRevisionId": str(submission["id"]),
                "reviewId": review_id,
                "assessmentId": assessment_id,
            }
            self._store_submission_command(
                conn,
                work_id,
                str(submission["id"]),
                "REVIEW",
                request.idempotency_key,
                request_digest,
                response,
                now,
            )
            updated_submission = conn.execute(
                "SELECT * FROM project_submission_revisions WHERE id = ?",
                (submission["id"],),
            ).fetchone()
            review_row = conn.execute(
                "SELECT * FROM project_instructor_reviews WHERE id = ?",
                (review_id,),
            ).fetchone()
            assessment_row = conn.execute(
                "SELECT * FROM project_rubric_assessments WHERE id = ?",
                (assessment_id,),
            ).fetchone()
            conn.commit()
        return ReviewSubmissionResult(
            submission=_submission(_present(updated_submission)),
            review=_review(_present(review_row)),
            assessment=_assessment(_present(assessment_row)),
        )

    def record_contribution(
        self, *, work_id: str, request: RecordContributionRequest
    ) -> TeamContributionRecord:
        now = _now()
        digest = canonical_digest(request.model_dump(mode="json", by_alias=True))
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._require_student_editor(conn, work_id)
            existing = conn.execute(
                "SELECT * FROM project_team_contributions "
                "WHERE work_id = ? AND contributor_subject = ? AND idempotency_key = ?",
                (work_id, self._actor, request.idempotency_key),
            ).fetchone()
            if existing is not None:
                self._assert_digest(existing, digest, "贡献记录")
                return _contribution(existing)
            context = self._context(conn, work_id)
            row = self._insert_contribution(
                conn,
                work_id,
                request,
                work_revision=int(context["revision"]) + 1,
                now=now,
            )
            conn.commit()
        return _contribution(row)

    def apply_sync_batch(self, request: ApplySyncBatchRequest) -> ApplySyncBatchResult:
        receipts: list[ClassroomSyncReceipt] = []
        device_digest = _sha256(request.device_id)
        for operation in request.operations:
            receipts.append(self._apply_sync_operation(operation, device_digest))
        return ApplySyncBatchResult(receipts=receipts)

    def reset_physical_evidence(
        self, *, work_id: str, request: EvidenceResetRequest
    ) -> EvidenceResetRecord:
        if request.confirmation != "重置真实证据":
            raise ProjectSubmissionError(
                "EVIDENCE_RESET_CONFIRMATION_REQUIRED",
                "请输入“重置真实证据”后再继续。",
                status_code=409,
            )
        now = _now()
        digest = canonical_digest(request.model_dump(mode="json", by_alias=True))
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._require_student_editor(conn, work_id)
            existing = conn.execute(
                "SELECT * FROM project_evidence_resets "
                "WHERE work_id = ? AND requested_by = ? AND idempotency_key = ?",
                (work_id, self._actor, request.idempotency_key),
            ).fetchone()
            if existing is not None:
                self._assert_digest(existing, digest, "真实证据重置")
                return _evidence_reset(existing)
            context = self._context(conn, work_id)
            placeholders = ",".join("?" for _ in _REAL_EVIDENCE_KINDS)
            count = int(
                conn.execute(
                    f"SELECT COUNT(*) FROM creator_evidence "
                    f"WHERE project_id = ? AND status = 'CURRENT' "
                    f"AND kind IN ({placeholders})",
                    (work_id, *sorted(_REAL_EVIDENCE_KINDS)),
                ).fetchone()[0]
            )
            if count == 0 and context["current_device_deployment_id"] is None:
                raise ProjectSubmissionError(
                    "EVIDENCE_RESET_NOTHING_CURRENT",
                    "当前没有可重置的真实设备或实物观察证据。",
                    status_code=409,
                )
            reason = f"学生主动重置真实证据：{request.reason}"
            conn.execute(
                f"""
                UPDATE creator_evidence
                SET status = 'STALE', invalidated_at = ?, invalidation_reason = ?
                WHERE project_id = ? AND status = 'CURRENT'
                  AND kind IN ({placeholders})
                """,
                (now, reason, work_id, *sorted(_REAL_EVIDENCE_KINDS)),
            )
            conn.execute(
                """
                UPDATE project_device_deployments
                SET status = 'STALE', invalidated_at = ?, invalidation_reason = ?,
                    updated_at = ?
                WHERE work_id = ? AND status != 'STALE'
                """,
                (now, reason, now, work_id),
            )
            conn.execute(
                """
                UPDATE project_submission_revisions
                SET status = 'SUPERSEDED', invalidated_at = ?, invalidation_reason = ?
                WHERE work_id = ? AND status != 'SUPERSEDED'
                """,
                (now, reason, work_id),
            )
            next_revision = int(context["revision"]) + 1
            next_state = (
                "DEVICE_DEPLOYMENT_READY"
                if context["current_assembly_record_id"] is not None
                else "ASSEMBLY_IN_PROGRESS"
            )
            conn.execute(
                """
                UPDATE work_learning_contexts
                SET current_device_deployment_id = NULL,
                    current_submission_revision_id = NULL,
                    process_state = ?, process_milestone = 'MAKING',
                    revision = ?, updated_at = ? WHERE work_id = ?
                """,
                (next_state, next_revision, now, work_id),
            )
            reset_id = _id("evidence-reset")
            conn.execute(
                """
                INSERT INTO project_evidence_resets (
                  id, work_id, reason, requested_by, invalidated_evidence_count,
                  idempotency_key, request_digest, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    reset_id,
                    work_id,
                    request.reason,
                    self._actor,
                    count,
                    request.idempotency_key,
                    digest,
                    now,
                ),
            )
            self._journal(
                conn,
                work_id,
                self._actor,
                "DECISION",
                "重置真实设备证据",
                request.reason,
                "evidence_reset",
                reset_id,
                now,
            )
            self._outbox(
                conn,
                work_id,
                "PHYSICAL_EVIDENCE_RESET",
                next_revision,
                {"resetId": reset_id, "invalidatedCount": count},
                now,
            )
            row = conn.execute(
                "SELECT * FROM project_evidence_resets WHERE id = ?",
                (reset_id,),
            ).fetchone()
            conn.commit()
        return _evidence_reset(_present(row))

    def _apply_sync_operation(
        self, operation: ClassroomSyncMutation, device_digest: str
    ) -> ClassroomSyncReceipt:
        now = _now()
        payload_digest = canonical_digest(operation.payload)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT * FROM classroom_sync_inbox "
                "WHERE actor_subject = ? AND operation_id = ?",
                (self._actor, operation.operation_id),
            ).fetchone()
            if existing is not None:
                replay_matches = (
                    str(existing["work_id"]) == operation.work_id
                    and str(existing["device_id_sha256"]) == device_digest
                    and str(existing["mutation_kind"]) == operation.kind.value
                    and int(existing["base_work_revision"])
                    == operation.base_work_revision
                    and str(existing["payload_sha256"]) == payload_digest
                )
                if not replay_matches:
                    return ClassroomSyncReceipt(
                        operationId=operation.operation_id,
                        workId=operation.work_id,
                        status="REJECTED",
                        resultRef=None,
                        serverWorkRevision=int(existing["server_work_revision"]),
                        conflictReason="同一离线操作编号不能提交不同内容。",
                    )
                return ClassroomSyncReceipt(
                    operationId=operation.operation_id,
                    workId=str(existing["work_id"]),
                    status="DUPLICATE",
                    resultRef=_optional(existing["result_ref"]),
                    serverWorkRevision=int(existing["server_work_revision"]),
                    conflictReason=_optional(existing["conflict_reason"]),
                )
            self._require_student_editor(conn, operation.work_id)
            context = self._context(conn, operation.work_id)
            server_revision = int(context["revision"])
            if operation.base_work_revision != server_revision:
                reason = (
                    "作品在离线期间已经产生新修订；请读取最新过程后明确重试，"
                    "系统不会静默合并。"
                )
                row = self._insert_sync_inbox(
                    conn,
                    operation,
                    device_digest,
                    payload_digest,
                    status="CONFLICT",
                    result_ref=None,
                    server_revision=server_revision,
                    conflict_reason=reason,
                    now=now,
                )
                conn.commit()
                return _sync_receipt(row)

            next_revision = server_revision + 1
            try:
                if operation.kind is SyncMutationKind.JOURNAL_APPEND:
                    result_ref = self._apply_synced_journal(
                        conn, operation, next_revision, now
                    )
                else:
                    payload = dict(operation.payload)
                    payload["idempotencyKey"] = f"sync:{operation.operation_id}"
                    request = RecordContributionRequest.model_validate(payload)
                    result_ref = str(
                        self._insert_contribution(
                            conn,
                            operation.work_id,
                            request,
                            work_revision=next_revision,
                            now=now,
                        )["id"]
                    )
            except (ValidationError, ValueError, KeyError) as exc:
                reason = "离线操作内容不符合当前课堂契约。"
                row = self._insert_sync_inbox(
                    conn,
                    operation,
                    device_digest,
                    payload_digest,
                    status="REJECTED",
                    result_ref=None,
                    server_revision=server_revision,
                    conflict_reason=reason,
                    now=now,
                )
                conn.commit()
                _ = exc
                return _sync_receipt(row)

            row = self._insert_sync_inbox(
                conn,
                operation,
                device_digest,
                payload_digest,
                status="APPLIED",
                result_ref=result_ref,
                server_revision=next_revision,
                conflict_reason=None,
                now=now,
            )
            conn.commit()
            return _sync_receipt(row)

    def _apply_synced_journal(
        self,
        conn: sqlite3.Connection,
        operation: ClassroomSyncMutation,
        next_revision: int,
        now: str,
    ) -> str:
        kind = ProcessJournalEntryKind(str(operation.payload["kind"]))
        title = _required_text(operation.payload.get("title"), "日志标题", 240)
        body = _required_text(operation.payload.get("body"), "日志内容", 12_000)
        entry_id = _id("journal")
        self._journal(
            conn,
            operation.work_id,
            self._actor,
            kind.value,
            title,
            body,
            "offline_operation",
            operation.operation_id,
            now,
            entry_id=entry_id,
        )
        conn.execute(
            "UPDATE work_learning_contexts SET revision = ?, updated_at = ? "
            "WHERE work_id = ?",
            (next_revision, now, operation.work_id),
        )
        self._outbox(
            conn,
            operation.work_id,
            "JOURNAL_SYNCED",
            next_revision,
            {"journalEntryId": entry_id, "kind": kind.value},
            now,
        )
        return entry_id

    def _insert_contribution(
        self,
        conn: sqlite3.Connection,
        work_id: str,
        request: RecordContributionRequest,
        *,
        work_revision: int,
        now: str,
    ) -> sqlite3.Row:
        digest = canonical_digest(request.model_dump(mode="json", by_alias=True))
        contribution_id = _id("contribution")
        conn.execute(
            """
            INSERT INTO project_team_contributions (
              id, work_id, kind, contributor_subject, summary,
              related_kind, related_id, idempotency_key, request_digest,
              work_revision, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                contribution_id,
                work_id,
                request.kind.value,
                self._actor,
                request.summary,
                request.related_kind,
                request.related_id,
                request.idempotency_key,
                digest,
                work_revision,
                now,
            ),
        )
        conn.execute(
            "UPDATE work_learning_contexts SET revision = ?, updated_at = ? "
            "WHERE work_id = ?",
            (work_revision, now, work_id),
        )
        self._outbox(
            conn,
            work_id,
            "CONTRIBUTION_RECORDED",
            work_revision,
            {"contributionId": contribution_id, "kind": request.kind.value},
            now,
        )
        row = conn.execute(
            "SELECT * FROM project_team_contributions WHERE id = ?",
            (contribution_id,),
        ).fetchone()
        return _present(row)

    def _insert_sync_inbox(
        self,
        conn: sqlite3.Connection,
        operation: ClassroomSyncMutation,
        device_digest: str,
        payload_digest: str,
        *,
        status: str,
        result_ref: str | None,
        server_revision: int,
        conflict_reason: str | None,
        now: str,
    ) -> sqlite3.Row:
        receipt_id = _id("sync-receipt")
        conn.execute(
            """
            INSERT INTO classroom_sync_inbox (
              id, operation_id, actor_subject, work_id, device_id_sha256,
              mutation_kind, base_work_revision, payload_sha256, status,
              result_ref, server_work_revision, conflict_reason, received_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                receipt_id,
                operation.operation_id,
                self._actor,
                operation.work_id,
                device_digest,
                operation.kind.value,
                operation.base_work_revision,
                payload_digest,
                status,
                result_ref,
                server_revision,
                conflict_reason,
                now,
            ),
        )
        row = conn.execute(
            "SELECT * FROM classroom_sync_inbox WHERE id = ?", (receipt_id,)
        ).fetchone()
        return _present(row)

    def _context(self, conn: sqlite3.Connection, work_id: str) -> sqlite3.Row:
        row = conn.execute(
            """
            SELECT c.*, p.owner_subject, a.class_group_id,
                   a.rubric_revision_id, a.policy_revision_id,
                   policy.required_checkpoints_json,
                   policy.submission_requirements_json
            FROM work_learning_contexts AS c
            JOIN projects AS p ON p.id = c.work_id
            JOIN assignments AS a ON a.id = c.assignment_id
            JOIN assignment_policy_revisions AS policy
              ON policy.id = a.policy_revision_id
            WHERE c.work_id = ?
            """,
            (work_id,),
        ).fetchone()
        if row is None:
            raise ProjectSubmissionError(
                "SUBMISSION_WORK_NOT_FOUND",
                "课堂项目不存在。",
                status_code=404,
            )
        return row

    def _current_submission_row(
        self, conn: sqlite3.Connection, context: sqlite3.Row
    ) -> sqlite3.Row | None:
        current_id = context["current_submission_revision_id"]
        if current_id is None:
            return None
        return conn.execute(
            "SELECT * FROM project_submission_revisions WHERE id = ?",
            (current_id,),
        ).fetchone()

    def _submission_row(
        self, conn: sqlite3.Connection, work_id: str, submission_id: str
    ) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM project_submission_revisions WHERE work_id = ? AND id = ?",
            (work_id, submission_id),
        ).fetchone()
        if row is None or row["manifest_sha256"] is None:
            raise ProjectSubmissionError(
                "SUBMISSION_NOT_FOUND", "提交修订不存在。", status_code=404
            )
        return row

    def _current_manifest(
        self,
        conn: sqlite3.Connection,
        work_id: str,
        context: sqlite3.Row,
        *,
        artifact_version_ids: list[str],
    ) -> SubmissionManifest:
        proposal_id = _required_pointer(
            context["current_proposal_revision_id"], "当前方案书"
        )
        run_id = _required_pointer(context["current_simulation_run_id"], "当前仿真")
        route_id = _required_pointer(
            context["current_build_route_decision_id"], "当前制作路径"
        )
        assembly_id = _required_pointer(
            context["current_assembly_record_id"], "当前装配记录"
        )
        structure_id = _optional(context["current_structure_revision_id"])
        deployment_bundle_id = _optional(context["current_deployment_bundle_id"])
        device_deployment_id = _optional(context["current_device_deployment_id"])
        observation_id: str | None = None
        if device_deployment_id is not None:
            observation = conn.execute(
                "SELECT id FROM physical_observations "
                "WHERE work_id = ? AND deployment_id = ? AND passed = 1 "
                "ORDER BY created_at DESC, id DESC LIMIT 1",
                (work_id, device_deployment_id),
            ).fetchone()
            observation_id = _optional(observation["id"]) if observation else None
        return SubmissionManifest(
            proposalRevisionId=proposal_id,
            simulationRunId=run_id,
            buildRouteDecisionId=route_id,
            structureRevisionId=structure_id,
            assemblyRecordId=assembly_id,
            deploymentBundleId=deployment_bundle_id,
            deviceDeploymentId=device_deployment_id,
            physicalObservationId=observation_id,
            rubricRevisionId=str(context["rubric_revision_id"]),
            artifactVersionIds=sorted(artifact_version_ids),
        )

    def _submission_blockers(
        self, conn: sqlite3.Connection, work_id: str, context: sqlite3.Row
    ) -> list[str]:
        blockers: list[str] = []
        facts = self._fact_completion(conn, work_id, context)
        if not facts[ProjectCheckpointKind.PROPOSAL_INSTRUCTOR_APPROVED]:
            blockers.append("项目方案书尚未通过教师检查。")
        if not facts[ProjectCheckpointKind.BEHAVIOR_SIMULATION_PASSED]:
            blockers.append("当前仿真版本尚未正式通过。")
        if not facts[ProjectCheckpointKind.BUILD_ROUTE_SELECTED]:
            blockers.append("尚未选择当前制作路径。")
        assembly_id = _optional(context["current_assembly_record_id"])
        assembly = (
            conn.execute(
                "SELECT status FROM project_assembly_records WHERE id = ?",
                (assembly_id,),
            ).fetchone()
            if assembly_id
            else None
        )
        if assembly is None or str(assembly["status"]) != "CURRENT":
            blockers.append("当前装配与安全检查尚未完成。")
        required = [
            ProjectCheckpointKind(value)
            for value in json.loads(str(context["required_checkpoints_json"]))
        ]
        for checkpoint in required:
            if checkpoint is ProjectCheckpointKind.SUBMISSION_INSTRUCTOR_ACCEPTED:
                continue
            if not facts.get(checkpoint, False):
                label = _CHECKPOINT_LABELS[checkpoint]
                message = f"任务要求的“{label}”尚未满足。"
                if message not in blockers:
                    blockers.append(message)
        return blockers

    @staticmethod
    def _fact_completion(
        conn: sqlite3.Connection, work_id: str, context: sqlite3.Row
    ) -> dict[ProjectCheckpointKind, bool]:
        proposal_id = _optional(context["current_proposal_revision_id"])
        proposal = (
            conn.execute(
                "SELECT status, student_confirmed_by FROM project_proposal_revisions_v2 "
                "WHERE id = ?",
                (proposal_id,),
            ).fetchone()
            if proposal_id
            else None
        )
        run_id = _optional(context["current_simulation_run_id"])
        run = (
            conn.execute(
                "SELECT status, evidence_eligible FROM simulation_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
            if run_id
            else None
        )
        route_id = _optional(context["current_build_route_decision_id"])
        route = (
            conn.execute(
                "SELECT status FROM project_build_route_decisions WHERE id = ?",
                (route_id,),
            ).fetchone()
            if route_id
            else None
        )
        deployment_id = _optional(context["current_device_deployment_id"])
        deployment = (
            conn.execute(
                "SELECT status, evidence_eligible FROM project_device_deployments "
                "WHERE id = ?",
                (deployment_id,),
            ).fetchone()
            if deployment_id
            else None
        )
        observation = (
            conn.execute(
                "SELECT id FROM physical_observations "
                "WHERE work_id = ? AND deployment_id = ? AND passed = 1 "
                "ORDER BY created_at DESC, id DESC LIMIT 1",
                (work_id, deployment_id),
            ).fetchone()
            if deployment_id
            else None
        )
        static_ready = conn.execute(
            "SELECT 1 FROM creator_evidence WHERE project_id = ? "
            "AND kind = 'STATIC_VALIDATION' AND status = 'CURRENT' AND passed = 1 "
            "LIMIT 1",
            (work_id,),
        ).fetchone()
        submission_id = _optional(context["current_submission_revision_id"])
        accepted = (
            conn.execute(
                "SELECT 1 FROM project_submission_revisions WHERE id = ? "
                "AND status = 'ACCEPTED'",
                (submission_id,),
            ).fetchone()
            if submission_id
            else None
        )
        proposal_confirmed = bool(
            proposal is not None and proposal["student_confirmed_by"] is not None
        )
        proposal_approved = bool(
            proposal is not None and str(proposal["status"]) == "APPROVED"
        )
        return {
            ProjectCheckpointKind.PROPOSAL_STUDENT_CONFIRMED: proposal_confirmed,
            ProjectCheckpointKind.PROPOSAL_INSTRUCTOR_APPROVED: proposal_approved,
            ProjectCheckpointKind.SCHEMATIC_VALIDATED: static_ready is not None,
            ProjectCheckpointKind.BEHAVIOR_SIMULATION_PASSED: bool(
                run is not None
                and str(run["status"]) == "PASSED"
                and bool(run["evidence_eligible"])
            ),
            ProjectCheckpointKind.BUILD_ROUTE_SELECTED: bool(
                route is not None and str(route["status"]) == "CURRENT"
            ),
            ProjectCheckpointKind.DEVICE_UPLOAD_VERIFIED: bool(
                deployment is not None
                and str(deployment["status"]) == "COMPLETED"
                and bool(deployment["evidence_eligible"])
            ),
            ProjectCheckpointKind.PHYSICAL_BEHAVIOR_CONFIRMED: observation is not None,
            ProjectCheckpointKind.SUBMISSION_INSTRUCTOR_ACCEPTED: accepted is not None,
        }

    @staticmethod
    def _validate_artifact_versions(
        conn: sqlite3.Connection, work_id: str, version_ids: list[str]
    ) -> None:
        if not version_ids:
            return
        placeholders = ",".join("?" for _ in version_ids)
        rows = conn.execute(
            f"SELECT id FROM artifact_versions WHERE project_id = ? "
            f"AND id IN ({placeholders})",
            (work_id, *version_ids),
        ).fetchall()
        if {str(row["id"]) for row in rows} != set(version_ids):
            raise ProjectSubmissionError(
                "SUBMISSION_ARTIFACT_NOT_OWNED",
                "提交附件必须来自当前作品。",
                status_code=409,
            )

    @staticmethod
    def _validate_scores(rubric: RubricRevision, scores: dict[str, float]) -> float:
        dimensions = {item.id: item for item in rubric.dimensions}
        if set(scores) != set(dimensions):
            raise ProjectSubmissionError(
                "RUBRIC_SCORES_INCOMPLETE",
                "教师必须按当前量表的每个维度评分。",
                status_code=409,
            )
        for dimension_id, value in scores.items():
            if value < 0 or value > dimensions[dimension_id].max_score:
                raise ProjectSubmissionError(
                    "RUBRIC_SCORE_OUT_OF_RANGE",
                    f"“{dimensions[dimension_id].title}”评分超出量表范围。",
                    status_code=409,
                )
        return float(sum(scores.values()))

    def _submission_command_replay(
        self,
        conn: sqlite3.Connection,
        work_id: str,
        idempotency_key: str,
        request_digest: str,
        *,
        expected_command: str,
    ) -> dict[str, str] | None:
        row = conn.execute(
            "SELECT * FROM project_submission_commands "
            "WHERE work_id = ? AND actor_subject = ? AND idempotency_key = ?",
            (work_id, self._actor, idempotency_key),
        ).fetchone()
        if row is None:
            return None
        if (
            str(row["request_digest"]) != request_digest
            or str(row["command"]) != expected_command
        ):
            raise ProjectSubmissionError(
                "SUBMISSION_IDEMPOTENCY_CONFLICT",
                "同一幂等键不能用于不同提交操作。",
                status_code=409,
            )
        return {
            str(key): str(value)
            for key, value in json.loads(str(row["response_json"])).items()
        }

    def _store_submission_command(
        self,
        conn: sqlite3.Connection,
        work_id: str,
        submission_id: str,
        command: str,
        idempotency_key: str,
        request_digest: str,
        response: dict[str, str],
        now: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO project_submission_commands (
              id, work_id, submission_revision_id, command, actor_subject,
              idempotency_key, request_digest, response_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _id("submission-command"),
                work_id,
                submission_id,
                command,
                self._actor,
                idempotency_key,
                request_digest,
                _dump(response),
                now,
            ),
        )

    @staticmethod
    def _assert_digest(row: sqlite3.Row, digest: str, label: str) -> None:
        if str(row["request_digest"]) != digest:
            raise ProjectSubmissionError(
                "SUBMISSION_IDEMPOTENCY_CONFLICT",
                f"同一幂等键不能保存不同{label}。",
                status_code=409,
            )

    def _can_student_edit(self, conn: sqlite3.Connection, work_id: str) -> bool:
        try:
            self._require_student_editor(conn, work_id)
            return True
        except ProjectSubmissionError:
            return False

    def _require_student_editor(self, conn: sqlite3.Connection, work_id: str) -> None:
        context = self._context(conn, work_id)
        class_member = conn.execute(
            "SELECT role FROM class_memberships "
            "WHERE class_group_id = ? AND subject = ? AND active = 1",
            (context["class_group_id"], self._actor),
        ).fetchone()
        if class_member is None or str(class_member["role"]) != "LEARNER":
            raise ProjectSubmissionError(
                "SUBMISSION_STUDENT_EDITOR_REQUIRED",
                "只有当前项目的学生编辑成员可以修改提交事实。",
                status_code=403,
            )
        owner = str(context["owner_subject"] or _LOCAL_SUBJECT) == self._actor
        member = conn.execute(
            "SELECT role FROM work_memberships "
            "WHERE work_id = ? AND subject = ? AND active = 1",
            (work_id, self._actor),
        ).fetchone()
        if not owner and (member is None or str(member["role"]) not in {"OWNER", "EDITOR"}):
            raise ProjectSubmissionError(
                "SUBMISSION_STUDENT_EDITOR_REQUIRED",
                "只有项目所有者或学生编辑成员可以修改提交事实。",
                status_code=403,
            )

    def _is_instructor(self, conn: sqlite3.Connection, work_id: str) -> bool:
        context = self._context(conn, work_id)
        row = conn.execute(
            """
            SELECT 1
            FROM assignments AS a
            JOIN class_groups AS g ON g.id = a.class_group_id
            JOIN courses AS course ON course.id = g.course_id
            LEFT JOIN class_memberships AS cm
              ON cm.class_group_id = g.id AND cm.subject = ? AND cm.active = 1
            LEFT JOIN organization_memberships AS om
              ON om.organization_id = course.organization_id
             AND om.subject = ? AND om.active = 1
            WHERE a.id = ?
              AND (cm.role IN ('INSTRUCTOR', 'TEACHING_ASSISTANT')
                   OR om.role IN ('ADMIN', 'INSTRUCTOR'))
            """,
            (self._actor, self._actor, context["assignment_id"]),
        ).fetchone()
        return row is not None

    def _require_instructor(self, conn: sqlite3.Connection, work_id: str) -> None:
        if not self._is_instructor(conn, work_id):
            raise ProjectSubmissionError(
                "SUBMISSION_INSTRUCTOR_REQUIRED",
                "只有本班教师或助教可以评审具体提交。",
                status_code=403,
            )

    @staticmethod
    def _journal(
        conn: sqlite3.Connection,
        work_id: str,
        actor: str,
        kind: str,
        title: str,
        body: str,
        related_kind: str,
        related_id: str,
        now: str,
        *,
        entry_id: str | None = None,
    ) -> None:
        conn.execute(
            """
            INSERT INTO project_process_journal (
              id, work_id, actor_subject, kind, title, body,
              related_kind, related_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry_id or _id("journal"),
                work_id,
                actor,
                kind,
                title,
                body,
                related_kind,
                related_id,
                now,
            ),
        )

    @staticmethod
    def _outbox(
        conn: sqlite3.Connection,
        work_id: str,
        event_type: str,
        revision: int,
        redacted_payload: dict[str, object],
        now: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO classroom_sync_outbox (
              id, work_id, event_type, aggregate_revision,
              redacted_payload_json, status, attempts, created_at
            ) VALUES (?, ?, ?, ?, ?, 'PENDING', 0, ?)
            """,
            (
                _id("classroom-outbox"),
                work_id,
                event_type,
                revision,
                _dump(redacted_payload),
                now,
            ),
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


class ClassroomPortfolioService:
    """Teacher-only factual progress, redacted export and assignment copy."""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = Path(data_dir)
        self._classroom = ClassroomRepository(self._data_dir)
        self._db_path = self._classroom.db_path
        self._actor = current_owner_subject() or _LOCAL_SUBJECT

    def get_assignment_progress(
        self, assignment_id: str
    ) -> AssignmentProgressOverview:
        with self._connect() as conn:
            assignment = self._require_assignment_manager(conn, assignment_id)
            required = [
                ProjectCheckpointKind(value)
                for value in json.loads(str(assignment["required_checkpoints_json"]))
            ]
            work_rows = conn.execute(
                """
                SELECT c.work_id, p.name AS project_name, c.process_state,
                       c.updated_at,
                       (SELECT COUNT(*) FROM work_memberships wm
                        WHERE wm.work_id = c.work_id AND wm.active = 1) AS member_count,
                       (SELECT COUNT(*) FROM project_team_contributions tc
                        WHERE tc.work_id = c.work_id) AS contribution_count
                FROM work_learning_contexts AS c
                JOIN projects AS p ON p.id = c.work_id
                WHERE c.assignment_id = ?
                ORDER BY c.updated_at DESC, c.work_id
                """,
                (assignment_id,),
            ).fetchall()
            service = ProjectSubmissionService(self._data_dir)
            works: list[AssignmentProgressWork] = []
            completed_counts = {item: 0 for item in required}
            for row in work_rows:
                context = service._context(conn, str(row["work_id"]))
                facts = service._fact_completion(conn, str(row["work_id"]), context)
                checkpoint_rows: list[dict[str, object]] = []
                for checkpoint in required:
                    completed = facts.get(checkpoint, False)
                    if completed:
                        completed_counts[checkpoint] += 1
                    checkpoint_rows.append(
                        {
                            "kind": checkpoint.value,
                            "label": _CHECKPOINT_LABELS[checkpoint],
                            "completed": completed,
                        }
                    )
                state = ProjectProcessState(str(row["process_state"]))
                needs_help: list[str] = []
                if state in {
                    ProjectProcessState.PROPOSAL_CHANGES_REQUESTED,
                    ProjectProcessState.SIMULATION_CHANGES_REQUIRED,
                    ProjectProcessState.SUBMISSION_CHANGES_REQUESTED,
                }:
                    needs_help.append("教师已提出修改要求")
                conflict = conn.execute(
                    "SELECT 1 FROM classroom_sync_inbox WHERE work_id = ? "
                    "AND status = 'CONFLICT' LIMIT 1",
                    (row["work_id"],),
                ).fetchone()
                if conflict is not None:
                    needs_help.append("有离线修改需要人工处理")
                review_pending = state is ProjectProcessState.SUBMISSION_IN_REVIEW
                works.append(
                    AssignmentProgressWork(
                        workId=str(row["work_id"]),
                        projectName=str(row["project_name"]),
                        state=state,
                        checkpoints=checkpoint_rows,
                        needsHelp=needs_help,
                        reviewPending=review_pending,
                        memberCount=int(row["member_count"]),
                        contributionCount=int(row["contribution_count"]),
                        updatedAt=str(row["updated_at"]),
                    )
                )
        return AssignmentProgressOverview(
            assignmentId=assignment_id,
            works=works,
            checkpointCounts=[
                CheckpointCount(
                    kind=checkpoint.value,
                    label=_CHECKPOINT_LABELS[checkpoint],
                    completed=completed_counts[checkpoint],
                    total=len(works),
                )
                for checkpoint in required
            ],
        )

    def export_course(self, course_id: str) -> CourseExportBundle:
        with self._connect() as conn:
            course = self._require_course_manager(conn, course_id)
            class_rows = conn.execute(
                "SELECT id, title, term FROM class_groups WHERE course_id = ? "
                "ORDER BY title, id",
                (course_id,),
            ).fetchall()
            assignment_rows = conn.execute(
                """
                SELECT a.id, a.class_group_id, a.title, a.driving_question,
                       a.description, a.collaboration_mode, a.due_at,
                       policy.structure_policy, policy.allowed_chip_targets_json,
                       policy.required_checkpoints_json,
                       policy.submission_requirements_json,
                       policy.safety_rules_json, rubric.dimensions_json
                FROM assignments AS a
                JOIN assignment_policy_revisions AS policy
                  ON policy.id = a.policy_revision_id
                JOIN rubric_revisions AS rubric ON rubric.id = a.rubric_revision_id
                JOIN class_groups AS g ON g.id = a.class_group_id
                WHERE g.course_id = ?
                ORDER BY a.created_at, a.id
                """,
                (course_id,),
            ).fetchall()
            work_rows = conn.execute(
                """
                SELECT c.work_id, c.assignment_id, c.process_state, c.updated_at
                FROM work_learning_contexts AS c
                JOIN assignments AS a ON a.id = c.assignment_id
                JOIN class_groups AS g ON g.id = a.class_group_id
                WHERE g.course_id = ? ORDER BY c.work_id
                """,
                (course_id,),
            ).fetchall()
            aliases = {
                str(row["work_id"]): f"project-{index:03d}"
                for index, row in enumerate(work_rows, start=1)
            }
            evidence_rows = conn.execute(
                """
                SELECT e.project_id, e.kind, e.status, e.passed, e.recorded_at
                FROM creator_evidence AS e
                JOIN work_learning_contexts AS c ON c.work_id = e.project_id
                JOIN assignments AS a ON a.id = c.assignment_id
                JOIN class_groups AS g ON g.id = a.class_group_id
                WHERE g.course_id = ? ORDER BY e.recorded_at, e.id
                """,
                (course_id,),
            ).fetchall()
        return CourseExportBundle(
            schema="zhangwen.classroom-course-export/v1",
            exportedAt=_now(),
            course={
                "id": str(course["id"]),
                "title": str(course["title"]),
                "code": str(course["code"]),
                "description": str(course["description"]),
            },
            classes=[
                {
                    "id": str(row["id"]),
                    "title": str(row["title"]),
                    "term": str(row["term"]),
                }
                for row in class_rows
            ],
            assignments=[
                {
                    "id": str(row["id"]),
                    "classGroupId": str(row["class_group_id"]),
                    "title": str(row["title"]),
                    "drivingQuestion": str(row["driving_question"]),
                    "description": str(row["description"]),
                    "collaborationMode": str(row["collaboration_mode"]),
                    "dueAt": _optional(row["due_at"]),
                    "structurePolicy": str(row["structure_policy"]),
                    "allowedChipTargets": json.loads(
                        str(row["allowed_chip_targets_json"])
                    ),
                    "requiredCheckpoints": json.loads(
                        str(row["required_checkpoints_json"])
                    ),
                    "submissionRequirements": json.loads(
                        str(row["submission_requirements_json"])
                    ),
                    "safetyRules": json.loads(str(row["safety_rules_json"])),
                    "rubricDimensions": json.loads(str(row["dimensions_json"])),
                }
                for row in assignment_rows
            ],
            workSummaries=[
                {
                    "workAlias": aliases[str(row["work_id"])],
                    "assignmentId": str(row["assignment_id"]),
                    "state": str(row["process_state"]),
                    "updatedAt": str(row["updated_at"]),
                }
                for row in work_rows
            ],
            redactedEvidence=[
                {
                    "workAlias": aliases[str(row["project_id"])],
                    "kind": str(row["kind"]),
                    "status": str(row["status"]),
                    "passed": bool(row["passed"]),
                    "label": _EVIDENCE_LABELS.get(str(row["kind"]), "过程证据已有记录"),
                    "recordedAt": str(row["recorded_at"]),
                }
                for row in evidence_rows
            ],
        )

    def copy_assignment(
        self, assignment_id: str, request: CopyAssignmentRequest
    ) -> Assignment:
        with self._connect() as conn:
            self._require_assignment_manager(conn, assignment_id)
            self._require_class_manager(conn, request.target_class_group_id)
        detail = self._classroom.get_assignment_detail(assignment_id)
        return self._classroom.create_assignment(
            class_group_id=request.target_class_group_id,
            title=request.title,
            driving_question=detail.assignment.driving_question,
            description=detail.assignment.description,
            collaboration_mode=detail.assignment.collaboration_mode,
            structure_policy=detail.policy.structure_policy,
            allowed_chip_targets=detail.policy.allowed_chip_targets,
            required_checkpoints=detail.policy.required_checkpoints,
            safety_rules=detail.policy.safety_rules,
            submission_requirements=detail.policy.submission_requirements,
            rubric_dimensions=detail.rubric.dimensions,
            due_at=detail.assignment.due_at,
            idempotency_key=request.idempotency_key,
        )

    def _require_assignment_manager(
        self, conn: sqlite3.Connection, assignment_id: str
    ) -> sqlite3.Row:
        row = conn.execute(
            """
            SELECT a.*, g.course_id, course.organization_id,
                   policy.required_checkpoints_json
            FROM assignments AS a
            JOIN class_groups AS g ON g.id = a.class_group_id
            JOIN courses AS course ON course.id = g.course_id
            JOIN assignment_policy_revisions AS policy
              ON policy.id = a.policy_revision_id
            WHERE a.id = ?
            """,
            (assignment_id,),
        ).fetchone()
        if row is None:
            raise ProjectSubmissionError(
                "ASSIGNMENT_NOT_FOUND", "项目任务不存在。", status_code=404
            )
        if not self._has_manager_role(
            conn, str(row["class_group_id"]), str(row["organization_id"])
        ):
            raise ProjectSubmissionError(
                "ASSIGNMENT_INSTRUCTOR_REQUIRED",
                "只有本班教师或助教可以查看班级过程。",
                status_code=403,
            )
        return row

    def _require_course_manager(
        self, conn: sqlite3.Connection, course_id: str
    ) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM courses WHERE id = ?", (course_id,)
        ).fetchone()
        if row is None:
            raise ProjectSubmissionError(
                "COURSE_NOT_FOUND", "课程不存在。", status_code=404
            )
        organization_manager = conn.execute(
            "SELECT 1 FROM organization_memberships "
            "WHERE organization_id = ? AND subject = ? AND active = 1 "
            "AND role IN ('ADMIN', 'INSTRUCTOR')",
            (row["organization_id"], self._actor),
        ).fetchone()
        class_manager = conn.execute(
            """
            SELECT 1 FROM class_memberships AS cm
            JOIN class_groups AS g ON g.id = cm.class_group_id
            WHERE g.course_id = ? AND cm.subject = ? AND cm.active = 1
              AND cm.role IN ('INSTRUCTOR', 'TEACHING_ASSISTANT') LIMIT 1
            """,
            (course_id, self._actor),
        ).fetchone()
        if organization_manager is None and class_manager is None:
            raise ProjectSubmissionError(
                "COURSE_INSTRUCTOR_REQUIRED",
                "只有课程教师可以导出脱敏课堂数据。",
                status_code=403,
            )
        return row

    def _require_class_manager(
        self, conn: sqlite3.Connection, class_group_id: str
    ) -> sqlite3.Row:
        row = conn.execute(
            """
            SELECT g.*, course.organization_id
            FROM class_groups AS g
            JOIN courses AS course ON course.id = g.course_id
            WHERE g.id = ?
            """,
            (class_group_id,),
        ).fetchone()
        if row is None:
            raise ProjectSubmissionError(
                "CLASS_NOT_FOUND", "班级不存在。", status_code=404
            )
        if not self._has_manager_role(
            conn, class_group_id, str(row["organization_id"])
        ):
            raise ProjectSubmissionError(
                "CLASS_INSTRUCTOR_REQUIRED",
                "只有目标班级教师可以复制任务。",
                status_code=403,
            )
        return row

    def _has_manager_role(
        self, conn: sqlite3.Connection, class_group_id: str, organization_id: str
    ) -> bool:
        class_role = conn.execute(
            "SELECT 1 FROM class_memberships "
            "WHERE class_group_id = ? AND subject = ? AND active = 1 "
            "AND role IN ('INSTRUCTOR', 'TEACHING_ASSISTANT')",
            (class_group_id, self._actor),
        ).fetchone()
        organization_role = conn.execute(
            "SELECT 1 FROM organization_memberships "
            "WHERE organization_id = ? AND subject = ? AND active = 1 "
            "AND role IN ('ADMIN', 'INSTRUCTOR')",
            (organization_id, self._actor),
        ).fetchone()
        return class_role is not None or organization_role is not None

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


def _submission(row: sqlite3.Row) -> SubmissionRevisionRecord:
    manifest = json.loads(str(row["manifest_json"]))
    return SubmissionRevisionRecord(
        id=str(row["id"]),
        workId=str(row["work_id"]),
        version=int(row["version"]),
        status=str(row["status"]),
        proposalRevisionId=str(row["proposal_revision_id"]),
        simulationRunId=str(row["simulation_run_id"]),
        buildRouteDecisionId=str(row["build_route_decision_id"]),
        structureRevisionId=_optional(row["structure_revision_id"]),
        assemblyRecordId=str(row["assembly_record_id"]),
        deploymentBundleId=_optional(row["deployment_bundle_id"]),
        deviceDeploymentId=_optional(row["device_deployment_id"]),
        physicalObservationId=_optional(row["physical_observation_id"]),
        rubricRevisionId=str(row["rubric_revision_id"]),
        content=json.loads(str(row["content_json"])),
        manifest=manifest,
        manifestSha256=str(row["manifest_sha256"]),
        submittedBy=_optional(row["submitted_by"]),
        submittedAt=_optional(row["submitted_at"]),
        supersedesRevisionId=_optional(row["supersedes_revision_id"]),
        createdBy=str(row["created_by"]),
        createdAt=str(row["created_at"]),
        invalidatedAt=_optional(row["invalidated_at"]),
        invalidationReason=_optional(row["invalidation_reason"]),
    )


def _review(row: sqlite3.Row) -> InstructorReviewRecord:
    return InstructorReviewRecord(
        id=str(row["id"]),
        workId=str(row["work_id"]),
        submissionRevisionId=str(row["submission_revision_id"]),
        decision=str(row["decision"]),
        reviewerSubject=str(row["reviewer_subject"]),
        feedback=str(row["feedback"]),
        annotations=json.loads(str(row["annotations_json"])),
        createdAt=str(row["created_at"]),
    )


def _assessment(row: sqlite3.Row) -> RubricAssessmentRecord:
    return RubricAssessmentRecord(
        id=str(row["id"]),
        workId=str(row["work_id"]),
        submissionRevisionId=str(row["submission_revision_id"]),
        rubricRevisionId=str(row["rubric_revision_id"]),
        instructorReviewId=str(row["instructor_review_id"]),
        reviewerSubject=str(row["reviewer_subject"]),
        scores=json.loads(str(row["scores_json"])),
        totalScore=float(row["total_score"]),
        status=RubricAssessmentStatus(str(row["status"])),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _rubric(row: sqlite3.Row) -> RubricRevision:
    return RubricRevision(
        id=str(row["id"]),
        rubricId=str(row["rubric_id"]),
        revision=int(row["revision"]),
        dimensions=json.loads(str(row["dimensions_json"])),
        supersedesRevisionId=_optional(row["supersedes_revision_id"]),
        createdBySubject=str(row["created_by_subject"]),
        createdAt=str(row["created_at"]),
    )


def _contribution(row: sqlite3.Row) -> TeamContributionRecord:
    return TeamContributionRecord(
        id=str(row["id"]),
        workId=str(row["work_id"]),
        kind=ContributionKind(str(row["kind"])),
        contributorSubject=str(row["contributor_subject"]),
        summary=str(row["summary"]),
        relatedKind=_optional(row["related_kind"]),
        relatedId=_optional(row["related_id"]),
        workRevision=int(row["work_revision"]),
        createdAt=str(row["created_at"]),
    )


def _sync_receipt(row: sqlite3.Row) -> ClassroomSyncReceipt:
    return ClassroomSyncReceipt(
        operationId=str(row["operation_id"]),
        workId=str(row["work_id"]),
        status=str(row["status"]),
        resultRef=_optional(row["result_ref"]),
        serverWorkRevision=int(row["server_work_revision"]),
        conflictReason=_optional(row["conflict_reason"]),
    )


def _redacted_evidence(row: sqlite3.Row) -> RedactedEvidenceSummary:
    kind = str(row["kind"])
    return RedactedEvidenceSummary(
        id=str(row["id"]),
        kind=kind,
        status=str(row["status"]),
        passed=bool(row["passed"]),
        label=_EVIDENCE_LABELS.get(kind, "过程证据已有记录"),
        sourceId=None,
        recordedAt=str(row["recorded_at"]),
    )


def _evidence_reset(row: sqlite3.Row) -> EvidenceResetRecord:
    return EvidenceResetRecord(
        id=str(row["id"]),
        workId=str(row["work_id"]),
        reason=str(row["reason"]),
        requestedBy=str(row["requested_by"]),
        invalidatedEvidenceCount=int(row["invalidated_evidence_count"]),
        createdAt=str(row["created_at"]),
    )


def _required_pointer(value: object, label: str) -> str:
    if value is None:
        raise ProjectSubmissionError(
            "SUBMISSION_REVISION_SET_INCOMPLETE",
            f"{label}缺失，不能固定提交版本。",
            status_code=409,
        )
    return str(value)


def _required_text(value: object, label: str, limit: int) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label}不能为空。")
    if len(text) > limit:
        raise ValueError(f"{label}过长。")
    return text


def _present(row: sqlite3.Row | None) -> sqlite3.Row:
    if row is None:
        raise ProjectSubmissionError(
            "SUBMISSION_DATA_INCOMPLETE", "课堂提交数据不完整。", status_code=409
        )
    return row


def _optional(value: object) -> str | None:
    return str(value) if value is not None else None


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
