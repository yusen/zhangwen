"""Classroom Proposal V2 commands and deterministic facilitator."""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from zhangwen.auth.context import current_owner_subject
from zhangwen.domains.classroom.models import (
    Assignment,
    AssignmentPolicyRevision,
    CheckpointReview,
    CheckpointReviewDecision,
    ClassroomProposalWorkspace,
    LegacyProposalSection,
    ProcessJournalEntryKind,
    ProjectCheckpointKind,
    ProjectProcessMilestone,
    ProjectProcessState,
    ProjectProposalContentV2,
    ProjectProposalRevisionV2,
    ProjectProposalSourceKind,
    ProjectProposalStatus,
    ProposalFacilitatorState,
    StructurePolicy,
)
from zhangwen.domains.classroom.repository import (
    ClassroomAuthorizationError,
    ClassroomConflictError,
    ClassroomNotFoundError,
    ClassroomRepository,
    ClassroomValidationError,
)
from zhangwen.proposals.exporter import render_docx, render_markdown, render_pdf
from zhangwen.proposals.models import (
    ProposalExportFormat,
    ProposalSection,
    ProposalStatus,
    ProposalVersion,
)


class ProposalValidationError(ClassroomValidationError):
    code = "PROJECT_PROPOSAL_VALIDATION_ERROR"


class ProposalConflictError(ClassroomConflictError):
    code = "PROJECT_PROPOSAL_CONFLICT"


class ProposalNotFoundError(ClassroomNotFoundError):
    code = "PROJECT_PROPOSAL_NOT_FOUND"


@dataclass(frozen=True)
class ProposalExportResult:
    content: bytes
    media_type: str
    filename: str


_LOCAL_SUBJECT = "__local__"
_FACILITATOR_FIELDS = (
    "drivingQuestion",
    "usersAndContext",
    "researchFindings",
    "successCriteria",
    "functionalLogic",
    "hardwarePlan",
    "interfaceAndPowerPlan",
    "softwarePlan",
    "simulationPlan",
    "structureHypothesis",
    "materialsAndBudget",
    "teamAndSchedule",
    "risksAndSafety",
)
_LIST_FIELDS = {
    "researchFindings",
    "successCriteria",
    "risksAndSafety",
    "reflectionPrompts",
}
_CRITICAL_FIELDS = {
    "drivingQuestion",
    "successCriteria",
    "functionalLogic",
    "hardwarePlan",
    "interfaceAndPowerPlan",
    "softwarePlan",
    "simulationPlan",
    "structureHypothesis",
    "risksAndSafety",
}
_FIELD_LABELS = {
    "drivingQuestion": "驱动问题",
    "usersAndContext": "使用者与情境",
    "researchFindings": "调研发现",
    "successCriteria": "成功标准",
    "functionalLogic": "功能逻辑",
    "hardwarePlan": "硬件计划",
    "interfaceAndPowerPlan": "接口与供电",
    "softwarePlan": "软件计划",
    "simulationPlan": "仿真计划",
    "structureHypothesis": "结构设想",
    "materialsAndBudget": "材料与预算",
    "teamAndSchedule": "分工与进度",
    "risksAndSafety": "风险与安全",
}


class ClassroomProposalService:
    """Owns Proposal V2 lifecycle without letting model text advance checkpoints."""

    def __init__(self, data_dir: Path) -> None:
        self._classroom = ClassroomRepository(data_dir)
        self._db_path = self._classroom.db_path
        self._actor_subject = current_owner_subject() or _LOCAL_SUBJECT

    def get_workspace(self, work_id: str) -> ClassroomProposalWorkspace:
        overview = self._classroom.get_work_overview(work_id)
        assignment_detail = self._classroom.get_assignment_detail(
            overview.binding.assignment_id
        )
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM project_proposal_revisions_v2
                WHERE work_id = ? ORDER BY version DESC
                """,
                (work_id,),
            ).fetchall()
            review_rows = conn.execute(
                """
                SELECT * FROM project_checkpoint_reviews
                WHERE work_id = ? AND checkpoint = ?
                ORDER BY created_at ASC, id ASC
                """,
                (work_id, ProjectCheckpointKind.PROPOSAL_INSTRUCTOR_APPROVED.value),
            ).fetchall()
            current_id = overview.projection.project_process.current_proposal_revision_id
            current_row = next(
                (row for row in rows if str(row["id"]) == current_id), None
            )
            current = self._revision(current_row) if current_row is not None else None
            can_student_confirm = self._can_student_confirm(conn, work_id)
        return ClassroomProposalWorkspace(
            assignment=assignment_detail.assignment,
            policy=assignment_detail.policy,
            process=overview.projection.project_process,
            current=current,
            revisions=[self._revision(row) for row in rows],
            reviews=[self._review(row) for row in review_rows],
            facilitator=self._facilitator(
                assignment_detail.assignment,
                assignment_detail.policy,
                current.content if current is not None else self._empty_content(
                    assignment_detail.assignment
                ),
            ),
            canStudentConfirm=can_student_confirm,
            canReview=self._can_review(work_id),
        )

    def get_revision(self, work_id: str, revision_id: str) -> ProjectProposalRevisionV2:
        self._classroom.assert_work_access(work_id)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM project_proposal_revisions_v2
                WHERE id = ? AND work_id = ?
                """,
                (revision_id, work_id),
            ).fetchone()
        if row is None:
            raise ProposalNotFoundError("项目方案修订不存在。")
        return self._revision(row)

    def create_revision(
        self,
        *,
        work_id: str,
        content: ProjectProposalContentV2,
        source_kind: ProjectProposalSourceKind,
        source_proposal_id: str | None,
        base_revision_id: str | None,
        idempotency_key: str,
    ) -> ClassroomProposalWorkspace:
        self._classroom.assert_work_access(work_id, edit=True)
        assignment, policy = self._assignment_and_policy(work_id)
        normalized = self._normalize_content(content, assignment)
        normalized_json = self._content_json(normalized)
        marker = self._idempotency_marker(idempotency_key)
        now = _now()
        revision_id = _id("project-proposal")
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._require_student_editor(conn, work_id)
            replay = conn.execute(
                """
                SELECT related_id FROM project_process_journal
                WHERE work_id = ? AND related_kind = ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (work_id, marker),
            ).fetchone()
            if replay is not None:
                prior = self._revision_row(conn, work_id, str(replay["related_id"]))
                if str(prior["content_json"]) != normalized_json:
                    raise ProposalConflictError("同一请求键不能保存不同的方案内容。")
                return self.get_workspace(work_id)

            context = self._context_row(conn, work_id)
            current_id = _optional_str(context["current_proposal_revision_id"])
            if current_id != base_revision_id:
                raise ProposalConflictError("当前方案已形成新修订，请先重新读取。")
            current_row = (
                self._revision_row(conn, work_id, current_id)
                if current_id is not None
                else None
            )
            if current_row is not None and str(current_row["content_json"]) == normalized_json:
                return self.get_workspace(work_id)

            version = int(
                conn.execute(
                    """
                    SELECT COALESCE(MAX(version), 0) + 1
                    FROM project_proposal_revisions_v2 WHERE work_id = ?
                    """,
                    (work_id,),
                ).fetchone()[0]
            )
            if source_proposal_id is not None:
                legacy = conn.execute(
                    "SELECT 1 FROM proposals WHERE id = ? AND project_id = ?",
                    (source_proposal_id, work_id),
                ).fetchone()
                if legacy is None:
                    raise ProposalValidationError("旧版方案来源不存在或不属于当前项目。")
            if source_kind is ProjectProposalSourceKind.LEGACY_ADAPTER and not source_proposal_id:
                raise ProposalValidationError("旧版适配修订必须记录来源方案。")

            if current_row is not None and str(current_row["status"]) in {
                ProjectProposalStatus.DRAFT.value,
                ProjectProposalStatus.READY_FOR_REVIEW.value,
                ProjectProposalStatus.CHANGES_REQUESTED.value,
            }:
                conn.execute(
                    """
                    UPDATE project_proposal_revisions_v2 SET status = 'SUPERSEDED'
                    WHERE id = ?
                    """,
                    (current_id,),
                )
            conn.execute(
                """
                INSERT INTO project_proposal_revisions_v2 (
                  id, work_id, assignment_policy_revision_id, rubric_revision_id,
                  version, status, content_json, source_kind, source_proposal_id,
                  supersedes_revision_id, student_confirmed_by, student_confirmed_at,
                  stale_reason, created_by, created_at
                ) VALUES (?, ?, ?, ?, ?, 'DRAFT', ?, ?, ?, ?, NULL, NULL, NULL, ?, ?)
                """,
                (
                    revision_id,
                    work_id,
                    assignment.policy_revision_id,
                    assignment.rubric_revision_id,
                    version,
                    normalized_json,
                    source_kind.value,
                    source_proposal_id,
                    current_id,
                    self._actor_subject,
                    now,
                ),
            )
            conn.execute(
                """
                UPDATE work_learning_contexts
                SET current_proposal_revision_id = ?, process_milestone = 'PROPOSAL',
                    process_state = 'PROPOSAL_DRAFT', revision = revision + 1,
                    updated_at = ?
                WHERE work_id = ?
                """,
                (revision_id, now, work_id),
            )
            critical_change = current_row is not None and self._critical_change(
                self._content(current_row), normalized
            )
            if critical_change:
                self._invalidate_downstream(conn, work_id, now)
            self._journal(
                conn,
                work_id=work_id,
                kind=ProcessJournalEntryKind.PROPOSAL_REVISION,
                title=f"形成项目方案书 v{version}",
                body="关键实现字段发生变化，下游结果需要重新验证。"
                if critical_change
                else "已保存新的项目方案书修订。",
                related_kind=marker,
                related_id=revision_id,
                now=now,
            )
        return self.get_workspace(work_id)

    def answer_next_question(
        self,
        *,
        work_id: str,
        answer: str,
        base_revision_id: str | None,
        idempotency_key: str,
    ) -> ClassroomProposalWorkspace:
        clean_answer = answer.strip()
        if not clean_answer:
            raise ProposalValidationError("回答不能为空。")
        workspace = self.get_workspace(work_id)
        next_field = workspace.facilitator.next_field
        if next_field is None:
            raise ProposalValidationError("当前方案字段已经完整，请确认或直接修订。")
        content = workspace.current.content if workspace.current else self._empty_content(
            workspace.assignment
        )
        payload = content.model_dump(by_alias=True)
        payload[next_field] = (
            _answer_items(clean_answer) if next_field in _LIST_FIELDS else clean_answer
        )
        return self.create_revision(
            work_id=work_id,
            content=ProjectProposalContentV2.model_validate(payload),
            source_kind=ProjectProposalSourceKind.FACILITATOR_DRAFT,
            source_proposal_id=None,
            base_revision_id=base_revision_id,
            idempotency_key=idempotency_key,
        )

    def student_confirm(
        self, work_id: str, revision_id: str
    ) -> ClassroomProposalWorkspace:
        self._classroom.assert_work_access(work_id, edit=True)
        assignment, policy = self._assignment_and_policy(work_id)
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._require_student_editor(conn, work_id)
            context = self._context_row(conn, work_id)
            if str(context["current_proposal_revision_id"] or "") != revision_id:
                raise ProposalConflictError("只能确认当前方案修订。")
            row = self._revision_row(conn, work_id, revision_id)
            if (
                _optional_str(row["student_confirmed_by"]) == self._actor_subject
                and str(row["status"])
                in {
                    ProjectProposalStatus.READY_FOR_REVIEW.value,
                    ProjectProposalStatus.APPROVED.value,
                }
            ):
                return self.get_workspace(work_id)
            if str(row["status"]) not in {
                ProjectProposalStatus.DRAFT.value,
                ProjectProposalStatus.CHANGES_REQUESTED.value,
            }:
                raise ProposalConflictError("当前方案状态不能再次确认。")
            facilitator = self._facilitator(assignment, policy, self._content(row))
            if not facilitator.complete:
                missing = "、".join(
                    _FIELD_LABELS.get(item, item) for item in facilitator.missing_fields
                )
                raise ProposalValidationError(f"项目方案尚未完整：{missing}。")
            checkpoints = {
                ProjectCheckpointKind(item)
                for item in policy.required_checkpoints
            }
            instructor_required = (
                ProjectCheckpointKind.PROPOSAL_INSTRUCTOR_APPROVED in checkpoints
            )
            next_status = (
                ProjectProposalStatus.READY_FOR_REVIEW
                if instructor_required
                else ProjectProposalStatus.APPROVED
            )
            next_milestone = (
                ProjectProcessMilestone.PROPOSAL
                if instructor_required
                else ProjectProcessMilestone.SIMULATION
            )
            next_state = (
                ProjectProcessState.PROPOSAL_IN_REVIEW
                if instructor_required
                else ProjectProcessState.SIMULATION_DRAFT
            )
            conn.execute(
                """
                UPDATE project_proposal_revisions_v2
                SET status = ?, student_confirmed_by = ?, student_confirmed_at = ?
                WHERE id = ?
                """,
                (next_status.value, self._actor_subject, now, revision_id),
            )
            self._checkpoint(
                conn,
                work_id=work_id,
                checkpoint=ProjectCheckpointKind.PROPOSAL_STUDENT_CONFIRMED,
                revision_id=revision_id,
                decision=CheckpointReviewDecision.APPROVED,
                comment="学生已确认此方案修订。",
                now=now,
            )
            conn.execute(
                """
                UPDATE work_learning_contexts
                SET process_milestone = ?, process_state = ?, revision = revision + 1,
                    updated_at = ? WHERE work_id = ?
                """,
                (next_milestone.value, next_state.value, now, work_id),
            )
            self._journal(
                conn,
                work_id=work_id,
                kind=ProcessJournalEntryKind.DECISION,
                title="学生确认项目方案书",
                body="已固定当前方案内容，等待教师检查。"
                if instructor_required
                else "已固定当前方案内容，可以进入仿真。",
                related_kind="PROJECT_PROPOSAL_REVISION",
                related_id=revision_id,
                now=now,
            )
        return self.get_workspace(work_id)

    def review_proposal(
        self,
        *,
        work_id: str,
        revision_id: str,
        decision: CheckpointReviewDecision,
        comment: str,
    ) -> ClassroomProposalWorkspace:
        clean_comment = comment.strip()
        if not clean_comment:
            raise ProposalValidationError("教师评语不能为空。")
        self._classroom.assert_work_instructor(work_id)
        now = _now()
        normalized_decision = CheckpointReviewDecision(decision)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            context = self._context_row(conn, work_id)
            if str(context["current_proposal_revision_id"] or "") != revision_id:
                raise ProposalConflictError("教师只能评审当前方案修订。")
            row = self._revision_row(conn, work_id, revision_id)
            replay = conn.execute(
                """
                SELECT decision, comment FROM project_checkpoint_reviews
                WHERE work_id = ? AND checkpoint = ? AND target_revision_id = ?
                  AND reviewer_subject = ?
                ORDER BY created_at DESC, id DESC LIMIT 1
                """,
                (
                    work_id,
                    ProjectCheckpointKind.PROPOSAL_INSTRUCTOR_APPROVED.value,
                    revision_id,
                    self._actor_subject,
                ),
            ).fetchone()
            if (
                replay is not None
                and str(replay["decision"]) == normalized_decision.value
                and str(replay["comment"]) == clean_comment
            ):
                return self.get_workspace(work_id)
            if str(row["status"]) != ProjectProposalStatus.READY_FOR_REVIEW.value:
                raise ProposalConflictError("当前方案尚未由学生确认或已经完成评审。")
            approved = normalized_decision is CheckpointReviewDecision.APPROVED
            conn.execute(
                "UPDATE project_proposal_revisions_v2 SET status = ? WHERE id = ?",
                (
                    ProjectProposalStatus.APPROVED.value
                    if approved
                    else ProjectProposalStatus.CHANGES_REQUESTED.value,
                    revision_id,
                ),
            )
            self._checkpoint(
                conn,
                work_id=work_id,
                checkpoint=ProjectCheckpointKind.PROPOSAL_INSTRUCTOR_APPROVED,
                revision_id=revision_id,
                decision=normalized_decision,
                comment=clean_comment,
                now=now,
            )
            conn.execute(
                """
                UPDATE work_learning_contexts
                SET process_milestone = ?, process_state = ?, revision = revision + 1,
                    updated_at = ? WHERE work_id = ?
                """,
                (
                    ProjectProcessMilestone.SIMULATION.value
                    if approved
                    else ProjectProcessMilestone.PROPOSAL.value,
                    ProjectProcessState.SIMULATION_DRAFT.value
                    if approved
                    else ProjectProcessState.PROPOSAL_CHANGES_REQUESTED.value,
                    now,
                    work_id,
                ),
            )
            self._journal(
                conn,
                work_id=work_id,
                kind=ProcessJournalEntryKind.INSTRUCTOR_FEEDBACK,
                title="教师通过项目方案书" if approved else "教师退回项目方案书",
                body=clean_comment,
                related_kind="PROJECT_PROPOSAL_REVISION",
                related_id=revision_id,
                now=now,
            )
        return self.get_workspace(work_id)

    def import_legacy_proposal(
        self,
        *,
        work_id: str,
        legacy_proposal_id: str,
        base_revision_id: str | None,
        idempotency_key: str,
    ) -> ClassroomProposalWorkspace:
        self._classroom.assert_work_access(work_id, edit=True)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT sections_json FROM proposals WHERE id = ? AND project_id = ?",
                (legacy_proposal_id, work_id),
            ).fetchone()
        if row is None:
            raise ProposalNotFoundError("旧版六章节方案不存在。")
        raw_sections: Any = json.loads(str(row["sections_json"]))
        if not isinstance(raw_sections, list):
            raise ProposalValidationError("旧版方案章节格式无效。")
        sections = [LegacyProposalSection.model_validate(item) for item in raw_sections]
        by_id = {item.id: item.content for item in sections}
        assignment, _ = self._assignment_and_policy(work_id)
        content = ProjectProposalContentV2(
            drivingQuestion=assignment.driving_question,
            usersAndContext=by_id.get("project_overview", ""),
            researchFindings=_nonempty_items(by_id.get("requirements", "")),
            successCriteria=_nonempty_items(by_id.get("risks_acceptance", "")),
            functionalLogic=by_id.get("implementation_plan", ""),
            hardwarePlan=by_id.get("hardware_software_structure", ""),
            interfaceAndPowerPlan=by_id.get("hardware_software_structure", ""),
            softwarePlan=by_id.get("hardware_software_structure", ""),
            simulationPlan=by_id.get("risks_acceptance", ""),
            structureHypothesis=by_id.get("hardware_software_structure", ""),
            materialsAndBudget=by_id.get("cost_difficulty_schedule", ""),
            teamAndSchedule="\n".join(
                item
                for item in (
                    by_id.get("implementation_plan", ""),
                    by_id.get("cost_difficulty_schedule", ""),
                )
                if item
            ),
            risksAndSafety=_nonempty_items(by_id.get("risks_acceptance", "")),
            reflectionPrompts=[],
            legacySourceSections=sections,
        )
        return self.create_revision(
            work_id=work_id,
            content=content,
            source_kind=ProjectProposalSourceKind.LEGACY_ADAPTER,
            source_proposal_id=legacy_proposal_id,
            base_revision_id=base_revision_id,
            idempotency_key=idempotency_key,
        )

    def export_revision(
        self, work_id: str, revision_id: str, format: str
    ) -> ProposalExportResult:
        revision = self.get_revision(work_id, revision_id)
        proposal = self._legacy_export_view(revision)
        export_format = ProposalExportFormat(format)
        if export_format is ProposalExportFormat.DOCX:
            return ProposalExportResult(
                content=render_docx(proposal, document_title="项目方案书"),
                media_type=(
                    "application/vnd.openxmlformats-officedocument."
                    "wordprocessingml.document"
                ),
                filename=f"{revision.id}.docx",
            )
        if export_format is ProposalExportFormat.PDF:
            return ProposalExportResult(
                content=render_pdf(proposal, document_title="Project Proposal"),
                media_type="application/pdf",
                filename=f"{revision.id}.pdf",
            )
        return ProposalExportResult(
            content=render_markdown(proposal, document_title="项目方案书"),
            media_type="text/markdown; charset=utf-8",
            filename=f"{revision.id}.md",
        )

    def _assignment_and_policy(
        self, work_id: str
    ) -> tuple[Assignment, AssignmentPolicyRevision]:
        overview = self._classroom.get_work_overview(work_id)
        detail = self._classroom.get_assignment_detail(overview.binding.assignment_id)
        return detail.assignment, detail.policy

    def _can_review(self, work_id: str) -> bool:
        try:
            self._classroom.assert_work_instructor(work_id)
            return True
        except ClassroomAuthorizationError:
            return False

    def _can_student_confirm(self, conn: sqlite3.Connection, work_id: str) -> bool:
        try:
            self._require_student_editor(conn, work_id)
            return True
        except ClassroomAuthorizationError:
            return False

    def _require_student_editor(self, conn: sqlite3.Connection, work_id: str) -> None:
        row = conn.execute(
            """
            SELECT p.owner_subject, a.class_group_id
            FROM projects p
            JOIN work_learning_contexts wlc ON wlc.work_id = p.id
            JOIN assignments a ON a.id = wlc.assignment_id
            WHERE p.id = ?
            """,
            (work_id,),
        ).fetchone()
        if row is None:
            raise ProposalNotFoundError("课堂项目不存在。")
        class_role = conn.execute(
            """
            SELECT role FROM class_memberships
            WHERE class_group_id = ? AND subject = ? AND active = 1
            """,
            (row["class_group_id"], self._actor_subject),
        ).fetchone()
        if class_role is None or str(class_role["role"]) != "LEARNER":
            raise ClassroomAuthorizationError("只有当前项目的学生成员可以修改或确认方案。")
        owner = str(row["owner_subject"] or _LOCAL_SUBJECT) == self._actor_subject
        member = conn.execute(
            """
            SELECT role FROM work_memberships
            WHERE work_id = ? AND subject = ? AND active = 1
            """,
            (work_id, self._actor_subject),
        ).fetchone()
        if not owner and (member is None or str(member["role"]) not in {"OWNER", "EDITOR"}):
            raise ClassroomAuthorizationError("只有项目所有者或编辑成员可以修改方案。")

    def _facilitator(
        self,
        assignment: Assignment,
        policy: AssignmentPolicyRevision,
        content: ProjectProposalContentV2,
    ) -> ProposalFacilitatorState:
        payload = content.model_dump(by_alias=True)
        complete_fields = [
            field
            for field in _FACILITATOR_FIELDS
            if self._field_complete(field, payload.get(field), policy)
        ]
        missing = [field for field in _FACILITATOR_FIELDS if field not in complete_fields]
        next_field = missing[0] if missing else None
        return ProposalFacilitatorState(
            complete=not missing,
            completedFields=complete_fields,
            totalFields=len(_FACILITATOR_FIELDS),
            nextField=next_field,
            nextQuestion=self._question(next_field, assignment, policy),
            missingFields=missing,
        )

    @staticmethod
    def _field_complete(
        field: str, value: object, policy: AssignmentPolicyRevision
    ) -> bool:
        if isinstance(value, str):
            complete = bool(value.strip())
        elif isinstance(value, list):
            complete = bool(value) and all(
                isinstance(item, str) and bool(item.strip()) for item in value
            )
        else:
            complete = False
        if not complete:
            return False
        if field == "hardwarePlan":
            normalized = _alnum(str(value))
            return any(_alnum(target) in normalized for target in policy.allowed_chip_targets)
        if field == "risksAndSafety":
            normalized_items = {_alnum(str(item)) for item in value} if isinstance(value, list) else set()
            return all(
                any(_alnum(rule) in item or item in _alnum(rule) for item in normalized_items)
                for rule in policy.safety_rules
            )
        if field == "structureHypothesis":
            text = str(value)
            if policy.structure_policy is StructurePolicy.REQUIRED:
                return "不做结构" not in text and "无结构" not in text
            if policy.structure_policy is StructurePolicy.PROHIBITED:
                return "结构" in text or "裸板" in text
        return True

    @staticmethod
    def _question(
        field: str | None,
        assignment: Assignment,
        policy: AssignmentPolicyRevision,
    ) -> str | None:
        if field is None:
            return None
        questions = {
            "drivingQuestion": f"先用自己的话解释任务问题：{assignment.driving_question}",
            "usersAndContext": "谁会在什么情境下使用或观察这个项目？",
            "researchFindings": "你已经查到或观察到哪些会影响方案的事实？请每行写一条。",
            "successCriteria": "怎样才算成功？请写出可以直接观察或测量的标准，每行一条。",
            "functionalLogic": "从输入变化到系统判断和输出动作，完整逻辑是什么？",
            "hardwarePlan": "准备使用哪一种允许的芯片目标（"
            + "、".join(policy.allowed_chip_targets)
            + "）和哪些器件？",
            "interfaceAndPowerPlan": "各器件怎样连接、怎样供电，电压和接口约束是什么？",
            "softwarePlan": "MicroPython 程序需要哪些状态、函数和异常处理？",
            "simulationPlan": "准备在仿真中检查哪些正常、边界和故障场景？",
            "structureHypothesis": _structure_question(policy.structure_policy),
            "materialsAndBudget": "需要哪些材料，数量和预算上限是多少？",
            "teamAndSchedule": "谁负责什么，准备在哪些课时完成哪些检查点？",
            "risksAndSafety": "请逐条说明风险及应对，并覆盖课程安全规则："
            + "；".join(policy.safety_rules),
        }
        return questions[field]

    @staticmethod
    def _empty_content(assignment: Assignment) -> ProjectProposalContentV2:
        return ProjectProposalContentV2(drivingQuestion=assignment.driving_question)

    @staticmethod
    def _normalize_content(
        content: ProjectProposalContentV2, assignment: Assignment
    ) -> ProjectProposalContentV2:
        payload = content.model_dump(by_alias=True)
        payload["drivingQuestion"] = assignment.driving_question.strip()
        for key, value in list(payload.items()):
            if isinstance(value, str):
                payload[key] = value.strip()
            elif isinstance(value, list) and key != "legacySourceSections":
                payload[key] = [str(item).strip() for item in value if str(item).strip()]
        return ProjectProposalContentV2.model_validate(payload)

    @staticmethod
    def _critical_change(
        before: ProjectProposalContentV2, after: ProjectProposalContentV2
    ) -> bool:
        before_payload = before.model_dump(by_alias=True)
        after_payload = after.model_dump(by_alias=True)
        return any(before_payload.get(key) != after_payload.get(key) for key in _CRITICAL_FIELDS)

    @staticmethod
    def _invalidate_downstream(
        conn: sqlite3.Connection, work_id: str, now: str
    ) -> None:
        reason = "项目方案关键字段已形成新修订，需要重新验证下游结果。"
        conn.execute(
            """
            UPDATE creator_evidence
            SET status = 'STALE', invalidated_at = ?, invalidation_reason = ?
            WHERE project_id = ? AND status = 'CURRENT' AND kind != 'GOAL_CONFIRMATION'
            """,
            (now, reason, work_id),
        )
        conn.execute(
            """
            UPDATE project_submission_revisions SET status = 'SUPERSEDED'
            WHERE work_id = ? AND status != 'SUPERSEDED'
            """,
            (work_id,),
        )
        conn.execute(
            """
            UPDATE simulation_runs
            SET status = 'STALE', invalidated_at = ?, invalidation_reason = ?
            WHERE work_id = ? AND status NOT IN ('STALE', 'RUNNING')
            """,
            (now, reason, work_id),
        )
        conn.execute(
            """
            UPDATE project_build_route_decisions
            SET status = 'STALE', invalidated_at = ?, invalidation_reason = ?
            WHERE work_id = ? AND status = 'CURRENT'
            """,
            (now, reason, work_id),
        )
        conn.execute(
            """
            UPDATE project_structure_revisions
            SET status = 'STALE', invalidated_at = ?, invalidation_reason = ?
            WHERE work_id = ? AND status != 'STALE'
            """,
            (now, reason, work_id),
        )
        conn.execute(
            """
            UPDATE project_assembly_records
            SET status = 'STALE', invalidated_at = ?, invalidation_reason = ?
            WHERE work_id = ? AND status = 'CURRENT'
            """,
            (now, reason, work_id),
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
            UPDATE deployment_bundles
            SET status = 'STALE', invalidated_at = ?, invalidation_reason = ?
            WHERE work_id = ? AND status = 'CURRENT'
            """,
            (now, reason, work_id),
        )
        conn.execute(
            """
            UPDATE work_learning_contexts
            SET current_simulation_run_id = NULL,
                current_simulation_project_revision_id = NULL,
                current_build_route_decision_id = NULL,
                current_structure_revision_id = NULL,
                current_assembly_record_id = NULL,
                current_deployment_bundle_id = NULL,
                current_device_deployment_id = NULL
            WHERE work_id = ?
            """,
            (work_id,),
        )

    def _checkpoint(
        self,
        conn: sqlite3.Connection,
        *,
        work_id: str,
        checkpoint: ProjectCheckpointKind,
        revision_id: str,
        decision: CheckpointReviewDecision,
        comment: str,
        now: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO project_checkpoint_reviews (
              id, work_id, checkpoint, target_kind, target_revision_id,
              decision, reviewer_subject, comment, created_at
            ) VALUES (?, ?, ?, 'PROJECT_PROPOSAL_REVISION_V2', ?, ?, ?, ?, ?)
            """,
            (
                _id("checkpoint-review"),
                work_id,
                checkpoint.value,
                revision_id,
                decision.value,
                self._actor_subject,
                comment,
                now,
            ),
        )

    def _journal(
        self,
        conn: sqlite3.Connection,
        *,
        work_id: str,
        kind: ProcessJournalEntryKind,
        title: str,
        body: str,
        related_kind: str,
        related_id: str,
        now: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO project_process_journal (
              id, work_id, actor_subject, kind, title, body,
              related_kind, related_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _id("journal"),
                work_id,
                self._actor_subject,
                kind.value,
                title,
                body,
                related_kind,
                related_id,
                now,
            ),
        )

    @staticmethod
    def _revision(row: sqlite3.Row) -> ProjectProposalRevisionV2:
        return ProjectProposalRevisionV2(
            id=str(row["id"]),
            workId=str(row["work_id"]),
            assignmentPolicyRevisionId=_optional_str(
                row["assignment_policy_revision_id"]
            ),
            rubricRevisionId=_optional_str(row["rubric_revision_id"]),
            version=int(row["version"]),
            status=str(row["status"]),
            content=ProjectProposalContentV2.model_validate_json(
                str(row["content_json"])
            ),
            sourceKind=str(row["source_kind"]),
            sourceProposalId=_optional_str(row["source_proposal_id"]),
            supersedesRevisionId=_optional_str(row["supersedes_revision_id"]),
            studentConfirmedBy=_optional_str(row["student_confirmed_by"]),
            studentConfirmedAt=_optional_str(row["student_confirmed_at"]),
            staleReason=_optional_str(row["stale_reason"]),
            createdBy=str(row["created_by"]),
            createdAt=str(row["created_at"]),
        )

    @staticmethod
    def _review(row: sqlite3.Row) -> CheckpointReview:
        return CheckpointReview(
            id=str(row["id"]),
            workId=str(row["work_id"]),
            checkpoint=str(row["checkpoint"]),
            targetKind=str(row["target_kind"]),
            targetRevisionId=str(row["target_revision_id"]),
            decision=str(row["decision"]),
            reviewerSubject=str(row["reviewer_subject"]),
            comment=str(row["comment"]),
            createdAt=str(row["created_at"]),
        )

    @staticmethod
    def _content(row: sqlite3.Row) -> ProjectProposalContentV2:
        return ProjectProposalContentV2.model_validate_json(str(row["content_json"]))

    @staticmethod
    def _content_json(content: ProjectProposalContentV2) -> str:
        return json.dumps(
            content.model_dump(by_alias=True, mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @staticmethod
    def _idempotency_marker(idempotency_key: str) -> str:
        clean = idempotency_key.strip()
        if not clean or len(clean) > 80:
            raise ProposalValidationError("请求键长度必须为 1–80 个字符。")
        return f"PROPOSAL_IDEMPOTENCY:{clean}"

    @staticmethod
    def _context_row(conn: sqlite3.Connection, work_id: str) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM work_learning_contexts WHERE work_id = ?", (work_id,)
        ).fetchone()
        if row is None:
            raise ProposalNotFoundError("作品尚未绑定项目任务。")
        return row

    @staticmethod
    def _revision_row(
        conn: sqlite3.Connection, work_id: str, revision_id: str
    ) -> sqlite3.Row:
        row = conn.execute(
            """
            SELECT * FROM project_proposal_revisions_v2
            WHERE id = ? AND work_id = ?
            """,
            (revision_id, work_id),
        ).fetchone()
        if row is None:
            raise ProposalNotFoundError("项目方案修订不存在。")
        return row

    def _legacy_export_view(
        self, revision: ProjectProposalRevisionV2
    ) -> ProposalVersion:
        content = revision.content
        payload = content.model_dump(by_alias=True)
        sections = [
            ProposalSection(id=key, title=label, content=_export_text(payload.get(key)))
            for key, label in _FIELD_LABELS.items()
        ]
        sections.extend(
            ProposalSection(
                id=f"legacy_{item.id}",
                title=f"旧版原始章节：{item.title}",
                content=item.content,
            )
            for item in content.legacy_source_sections
        )
        legacy_status = {
            ProjectProposalStatus.APPROVED: ProposalStatus.APPROVED,
            ProjectProposalStatus.STALE: ProposalStatus.STALE,
            ProjectProposalStatus.SUPERSEDED: ProposalStatus.SUPERSEDED,
        }.get(revision.status, ProposalStatus.DRAFT)
        return ProposalVersion(
            id=revision.id,
            projectId=revision.work_id,
            solutionId=revision.id,
            solutionVersion=revision.version,
            version=revision.version,
            status=legacy_status,
            sections=sections,
            createdAt=revision.created_at,
            updatedAt=revision.created_at,
            confirmedAt=revision.student_confirmed_at,
            staleReason=revision.stale_reason,
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _optional_str(value: object) -> str | None:
    return str(value) if value is not None else None


def _answer_items(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[\n；;]+", value) if item.strip()]


def _nonempty_items(value: str) -> list[str]:
    return [value] if value.strip() else []


def _alnum(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def _structure_question(policy: StructurePolicy) -> str:
    if policy is StructurePolicy.REQUIRED:
        return "课程要求包含结构件；它要固定、保护或展示什么，怎样装配？"
    if policy is StructurePolicy.PROHIBITED:
        return "课程不制作结构件；裸板怎样固定、绝缘并保持可观察？"
    return "这个项目是否需要结构件？先写当前假设和判断依据，仿真后仍可选择。"


def _export_text(value: object) -> str:
    if isinstance(value, list):
        return "\n".join(f"- {item}" for item in value)
    return str(value or "")
