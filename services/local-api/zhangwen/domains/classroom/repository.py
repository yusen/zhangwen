"""Same-database classroom and project-process repository."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from zhangwen.auth.context import current_owner_subject
from zhangwen.domains.classroom.models import (
    Assignment,
    AssignmentCollaborationMode,
    AssignmentPolicyRevision,
    AssignmentWorkSummary,
    BuildRoute,
    ClassGroup,
    ClassMembership,
    ClassMembershipRole,
    ClassroomAssignmentDetail,
    ClassroomClassDetail,
    ClassroomCourseCard,
    ClassroomHome,
    ClassroomProjectCard,
    ClassroomWorkOverview,
    Course,
    LearningAssignmentRef,
    LearningClassRef,
    LearningCourseRef,
    LearningOrganizationRef,
    LegacyLearningSources,
    Organization,
    OrganizationMembershipRole,
    ProcessJournalEntry,
    ProcessJournalEntryKind,
    ProjectCheckpointKind,
    ProjectCheckpointSummary,
    ProjectProcessMilestone,
    ProjectProcessSnapshot,
    ProjectProcessState,
    RubricDimension,
    RubricRevision,
    StructurePolicy,
    WorkLearningBinding,
    WorkLearningContextSnapshot,
    WorkLearningProjection,
    WorkMembership,
    WorkMembershipRole,
)
from zhangwen.projects.repository import ProjectRepository


_LOCAL_SUBJECT = "__local__"
_CHECKPOINT_LABELS: dict[ProjectCheckpointKind, str] = {
    ProjectCheckpointKind.PROPOSAL_STUDENT_CONFIRMED: "学生确认方案书",
    ProjectCheckpointKind.PROPOSAL_INSTRUCTOR_APPROVED: "方案书经教师通过",
    ProjectCheckpointKind.SCHEMATIC_VALIDATED: "电路静态检查通过",
    ProjectCheckpointKind.BEHAVIOR_SIMULATION_PASSED: "行为仿真场景通过",
    ProjectCheckpointKind.BUILD_ROUTE_SELECTED: "制作路径已选择",
    ProjectCheckpointKind.DEVICE_UPLOAD_VERIFIED: "代码上传与回读通过",
    ProjectCheckpointKind.PHYSICAL_BEHAVIOR_CONFIRMED: "实物行为经人工确认",
    ProjectCheckpointKind.SUBMISSION_INSTRUCTOR_ACCEPTED: "最终提交经教师通过",
}

_STATE_NEXT_ACTION: dict[ProjectProcessState, str] = {
    ProjectProcessState.PROPOSAL_DRAFT: "继续完善项目方案书",
    ProjectProcessState.PROPOSAL_READY_FOR_REVIEW: "确认并提交方案书检查",
    ProjectProcessState.PROPOSAL_IN_REVIEW: "等待教师检查方案书",
    ProjectProcessState.PROPOSAL_CHANGES_REQUESTED: "根据反馈修订方案书",
    ProjectProcessState.PROPOSAL_APPROVED: "开始搭建仿真项目",
    ProjectProcessState.SIMULATION_DRAFT: "完善电路、代码和测试场景",
    ProjectProcessState.SIMULATION_READY: "运行必测仿真场景",
    ProjectProcessState.SIMULATION_RUNNING: "查看当前仿真运行",
    ProjectProcessState.SIMULATION_CHANGES_REQUIRED: "修正仿真问题并重新验证",
    ProjectProcessState.SIMULATION_VALIDATED: "确认制作路径",
    ProjectProcessState.BUILD_ROUTE_REQUIRED: "选择包含结构件或不做结构件",
    ProjectProcessState.STRUCTURE_DESIGN: "完善结构与装配方案",
    ProjectProcessState.ASSEMBLY_IN_PROGRESS: "记录装配与安全检查",
    ProjectProcessState.DEVICE_DEPLOYMENT_READY: "选择设备并进入安全上传步骤",
    ProjectProcessState.DEVICE_DEPLOYING: "查看设备上传状态",
    ProjectProcessState.PHYSICAL_OBSERVATION_REQUIRED: "记录真实可观察结果",
    ProjectProcessState.SUBMISSION_DRAFT: "整理项目提交",
    ProjectProcessState.SUBMISSION_IN_REVIEW: "等待教师评审",
    ProjectProcessState.SUBMISSION_CHANGES_REQUESTED: "根据评审修改项目",
    ProjectProcessState.COMPLETED: "查看已完成项目过程",
}


class ClassroomError(RuntimeError):
    code = "CLASSROOM_ERROR"


class ClassroomAuthorizationError(ClassroomError):
    code = "CLASSROOM_FORBIDDEN"


class ClassroomNotFoundError(ClassroomError):
    code = "CLASSROOM_NOT_FOUND"


class ClassroomConflictError(ClassroomError):
    code = "CLASSROOM_CONFLICT"


class ClassroomValidationError(ClassroomError):
    code = "CLASSROOM_VALIDATION_ERROR"


class ClassroomRepository:
    """Stores teaching context around the existing project/Work rows."""

    def __init__(
        self,
        data_dir: Path,
        *,
        owner_subject: str | None = None,
    ) -> None:
        self._data_dir = Path(data_dir)
        self._projects = ProjectRepository(self._data_dir)
        self._db_path = self._projects.db_path
        subject = owner_subject if owner_subject is not None else current_owner_subject()
        self._actor_subject = subject or _LOCAL_SUBJECT

    @property
    def db_path(self) -> Path:
        return self._db_path

    def get_home(self) -> ClassroomHome:
        """Return only classes and Works visible to the current classroom subject."""

        with self._connect() as conn:
            course_rows = conn.execute(
                """
                SELECT o.id AS organization_id, o.name AS organization_name,
                       c.id AS course_id, c.title AS course_title,
                       g.id AS class_group_id, g.title AS class_title,
                       COALESCE(cm.role, om.role) AS actor_role,
                       (SELECT COUNT(*) FROM assignments a
                        WHERE a.class_group_id = g.id) AS assignment_count
                FROM class_groups g
                JOIN courses c ON c.id = g.course_id
                JOIN organizations o ON o.id = c.organization_id
                LEFT JOIN class_memberships cm
                  ON cm.class_group_id = g.id AND cm.subject = ? AND cm.active = 1
                LEFT JOIN organization_memberships om
                  ON om.organization_id = o.id AND om.subject = ? AND om.active = 1
                WHERE cm.subject IS NOT NULL
                   OR om.role IN ('ADMIN', 'INSTRUCTOR')
                ORDER BY c.updated_at DESC, g.updated_at DESC, g.id
                """,
                (self._actor_subject, self._actor_subject),
            ).fetchall()
            project_rows = conn.execute(
                """
                SELECT p.id AS work_id, p.name AS project_name,
                       a.id AS assignment_id, a.title AS assignment_title,
                       g.id AS class_group_id, g.title AS class_title,
                       wlc.process_milestone, wlc.process_state,
                       wlc.updated_at
                FROM work_learning_contexts wlc
                JOIN projects p ON p.id = wlc.work_id
                JOIN assignments a ON a.id = wlc.assignment_id
                JOIN class_groups g ON g.id = a.class_group_id
                LEFT JOIN work_memberships wm
                  ON wm.work_id = p.id AND wm.subject = ? AND wm.active = 1
                WHERE COALESCE(p.owner_subject, ?) = ? OR wm.subject IS NOT NULL
                ORDER BY wlc.updated_at DESC, p.id
                """,
                (self._actor_subject, _LOCAL_SUBJECT, self._actor_subject),
            ).fetchall()
            teaching_rows = conn.execute(
                """
                SELECT DISTINCT g.id, g.title
                FROM class_groups g
                JOIN courses c ON c.id = g.course_id
                LEFT JOIN class_memberships cm
                  ON cm.class_group_id = g.id AND cm.subject = ? AND cm.active = 1
                LEFT JOIN organization_memberships om
                  ON om.organization_id = c.organization_id
                 AND om.subject = ? AND om.active = 1
                WHERE cm.role IN ('INSTRUCTOR', 'TEACHING_ASSISTANT')
                   OR om.role IN ('ADMIN', 'INSTRUCTOR')
                ORDER BY g.title, g.id
                """,
                (self._actor_subject, self._actor_subject),
            ).fetchall()

        return ClassroomHome(
            courseCards=[
                ClassroomCourseCard(
                    organization=LearningOrganizationRef(
                        id=str(row["organization_id"]),
                        name=str(row["organization_name"]),
                    ),
                    course=LearningCourseRef(
                        id=str(row["course_id"]), title=str(row["course_title"])
                    ),
                    classGroup=LearningClassRef(
                        id=str(row["class_group_id"]), title=str(row["class_title"])
                    ),
                    role=str(row["actor_role"]),
                    assignmentCount=int(row["assignment_count"]),
                )
                for row in course_rows
            ],
            projectCards=[
                ClassroomProjectCard(
                    workId=str(row["work_id"]),
                    projectName=str(row["project_name"]),
                    assignmentId=str(row["assignment_id"]),
                    assignmentTitle=str(row["assignment_title"]),
                    classGroupId=str(row["class_group_id"]),
                    classTitle=str(row["class_title"]),
                    milestone=ProjectProcessMilestone(str(row["process_milestone"])),
                    state=ProjectProcessState(str(row["process_state"])),
                    nextActionLabel=_STATE_NEXT_ACTION[
                        ProjectProcessState(str(row["process_state"]))
                    ],
                    updatedAt=str(row["updated_at"]),
                )
                for row in project_rows
            ],
            teachingClasses=[
                LearningClassRef(id=str(row["id"]), title=str(row["title"]))
                for row in teaching_rows
            ],
            canTeach=bool(teaching_rows),
        )

    def get_class_detail(self, class_group_id: str) -> ClassroomClassDetail:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT g.*, c.id AS course_id, c.organization_id,
                       c.title AS course_title, c.code AS course_code,
                       c.description AS course_description,
                       c.created_by_subject AS course_created_by,
                       c.created_at AS course_created_at,
                       c.updated_at AS course_updated_at,
                       o.name AS organization_name,
                       o.created_by_subject AS organization_created_by,
                       o.created_at AS organization_created_at,
                       o.updated_at AS organization_updated_at,
                       COALESCE(cm.role, om.role) AS actor_role
                FROM class_groups g
                JOIN courses c ON c.id = g.course_id
                JOIN organizations o ON o.id = c.organization_id
                LEFT JOIN class_memberships cm
                  ON cm.class_group_id = g.id AND cm.subject = ? AND cm.active = 1
                LEFT JOIN organization_memberships om
                  ON om.organization_id = o.id AND om.subject = ? AND om.active = 1
                WHERE g.id = ? AND (
                  cm.subject IS NOT NULL OR om.role IN ('ADMIN', 'INSTRUCTOR')
                )
                """,
                (self._actor_subject, self._actor_subject, class_group_id),
            ).fetchone()
            if row is None:
                exists = conn.execute(
                    "SELECT 1 FROM class_groups WHERE id = ?", (class_group_id,)
                ).fetchone()
                if exists is None:
                    raise ClassroomNotFoundError("班级不存在。")
                raise ClassroomAuthorizationError("无权查看该班级。")
            assignments = conn.execute(
                "SELECT * FROM assignments WHERE class_group_id = ? ORDER BY updated_at DESC, id",
                (class_group_id,),
            ).fetchall()
            members = conn.execute(
                "SELECT * FROM class_memberships WHERE class_group_id = ? AND active = 1 ORDER BY role, subject",
                (class_group_id,),
            ).fetchall()
        return ClassroomClassDetail(
            organization=Organization(
                id=str(row["organization_id"]),
                name=str(row["organization_name"]),
                createdBySubject=str(row["organization_created_by"]),
                createdAt=str(row["organization_created_at"]),
                updatedAt=str(row["organization_updated_at"]),
            ),
            course=Course(
                id=str(row["course_id"]),
                organizationId=str(row["organization_id"]),
                title=str(row["course_title"]),
                code=str(row["course_code"]),
                description=str(row["course_description"]),
                createdBySubject=str(row["course_created_by"]),
                createdAt=str(row["course_created_at"]),
                updatedAt=str(row["course_updated_at"]),
            ),
            classGroup=_class_group(row),
            role=str(row["actor_role"]),
            assignments=[_assignment(item) for item in assignments],
            members=[_class_membership(item) for item in members],
        )

    def get_assignment_detail(self, assignment_id: str) -> ClassroomAssignmentDetail:
        with self._connect() as conn:
            assignment_row = self._assignment_access_row(conn, assignment_id)
            class_row = conn.execute(
                "SELECT * FROM class_groups WHERE id = ?",
                (assignment_row["class_group_id"],),
            ).fetchone()
            course_row = conn.execute(
                "SELECT * FROM courses WHERE id = ?", (class_row["course_id"],)
            ).fetchone()
            organization_row = conn.execute(
                "SELECT * FROM organizations WHERE id = ?",
                (course_row["organization_id"],),
            ).fetchone()
            policy_row = conn.execute(
                "SELECT * FROM assignment_policy_revisions WHERE id = ?",
                (assignment_row["policy_revision_id"],),
            ).fetchone()
            rubric_row = conn.execute(
                "SELECT * FROM rubric_revisions WHERE id = ?",
                (assignment_row["rubric_revision_id"],),
            ).fetchone()
            manager = self._is_class_manager(conn, str(assignment_row["class_group_id"]))
            work_rows = conn.execute(
                """
                SELECT wlc.work_id, p.name AS project_name,
                       wlc.process_milestone, wlc.process_state, wlc.updated_at,
                       (SELECT COUNT(*) FROM work_memberships wm
                        WHERE wm.work_id = wlc.work_id AND wm.active = 1) AS member_count
                FROM work_learning_contexts wlc
                JOIN projects p ON p.id = wlc.work_id
                LEFT JOIN work_memberships mine
                  ON mine.work_id = wlc.work_id AND mine.subject = ? AND mine.active = 1
                WHERE wlc.assignment_id = ?
                  AND (? = 1 OR COALESCE(p.owner_subject, ?) = ? OR mine.subject IS NOT NULL)
                ORDER BY wlc.updated_at DESC, wlc.work_id
                """,
                (
                    self._actor_subject,
                    assignment_id,
                    1 if manager else 0,
                    _LOCAL_SUBJECT,
                    self._actor_subject,
                ),
            ).fetchall()
        return ClassroomAssignmentDetail(
            organization=_organization(_present(organization_row)),
            course=_course(_present(course_row)),
            classGroup=_class_group(_present(class_row)),
            assignment=_assignment(assignment_row),
            policy=_assignment_policy(_present(policy_row)),
            rubric=_rubric_revision(_present(rubric_row)),
            works=[
                AssignmentWorkSummary(
                    workId=str(row["work_id"]),
                    projectName=str(row["project_name"]),
                    milestone=ProjectProcessMilestone(str(row["process_milestone"])),
                    state=ProjectProcessState(str(row["process_state"])),
                    memberCount=int(row["member_count"]),
                    updatedAt=str(row["updated_at"]),
                )
                for row in work_rows
            ],
        )

    def create_organization(
        self,
        *,
        name: str,
        idempotency_key: str,
    ) -> Organization:
        clean_name = _required_text(name, "机构名称", 200)
        clean_key = _required_text(idempotency_key, "幂等键", 200)
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                """
                SELECT * FROM organizations
                WHERE created_by_subject = ? AND idempotency_key = ?
                """,
                (self._actor_subject, clean_key),
            ).fetchone()
            if existing is not None:
                if str(existing["name"]) != clean_name:
                    raise ClassroomConflictError("同一幂等键不能创建不同机构。")
                return _organization(existing)
            organization_id = _id("org")
            conn.execute(
                """
                INSERT INTO organizations (
                  id, name, created_by_subject, idempotency_key, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    organization_id,
                    clean_name,
                    self._actor_subject,
                    clean_key,
                    now,
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO organization_memberships (
                  organization_id, subject, role, active, created_at, updated_at
                ) VALUES (?, ?, 'ADMIN', 1, ?, ?)
                """,
                (organization_id, self._actor_subject, now, now),
            )
            row = conn.execute(
                "SELECT * FROM organizations WHERE id = ?", (organization_id,)
            ).fetchone()
        return _organization(_present(row))

    def create_course(
        self,
        *,
        organization_id: str,
        title: str,
        code: str,
        description: str,
        idempotency_key: str,
    ) -> Course:
        clean_title = _required_text(title, "课程名称", 200)
        clean_code = code.strip()[:80]
        clean_description = description.strip()[:12000]
        clean_key = _required_text(idempotency_key, "幂等键", 200)
        now = _now()
        with self._connect() as conn:
            self._require_organization_manager(conn, organization_id)
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                """
                SELECT * FROM courses
                WHERE organization_id = ? AND idempotency_key = ?
                """,
                (organization_id, clean_key),
            ).fetchone()
            if existing is not None:
                if (
                    str(existing["title"]) != clean_title
                    or str(existing["code"]) != clean_code
                    or str(existing["description"]) != clean_description
                ):
                    raise ClassroomConflictError("同一幂等键不能创建不同课程。")
                return _course(existing)
            course_id = _id("course")
            conn.execute(
                """
                INSERT INTO courses (
                  id, organization_id, title, code, description,
                  created_by_subject, idempotency_key, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    course_id,
                    organization_id,
                    clean_title,
                    clean_code,
                    clean_description,
                    self._actor_subject,
                    clean_key,
                    now,
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM courses WHERE id = ?", (course_id,)
            ).fetchone()
        return _course(_present(row))

    def create_class_group(
        self,
        *,
        course_id: str,
        title: str,
        term: str,
        idempotency_key: str,
    ) -> ClassGroup:
        clean_title = _required_text(title, "班级名称", 200)
        clean_term = term.strip()[:120]
        clean_key = _required_text(idempotency_key, "幂等键", 200)
        now = _now()
        with self._connect() as conn:
            course = self._course_row(conn, course_id)
            self._require_organization_manager(conn, str(course["organization_id"]))
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                """
                SELECT * FROM class_groups
                WHERE course_id = ? AND idempotency_key = ?
                """,
                (course_id, clean_key),
            ).fetchone()
            if existing is not None:
                if (
                    str(existing["title"]) != clean_title
                    or str(existing["term"]) != clean_term
                ):
                    raise ClassroomConflictError("同一幂等键不能创建不同班级。")
                return _class_group(existing)
            class_group_id = _id("class")
            conn.execute(
                """
                INSERT INTO class_groups (
                  id, course_id, title, term, created_by_subject,
                  idempotency_key, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    class_group_id,
                    course_id,
                    clean_title,
                    clean_term,
                    self._actor_subject,
                    clean_key,
                    now,
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO class_memberships (
                  class_group_id, subject, role, active, created_at, updated_at
                ) VALUES (?, ?, 'INSTRUCTOR', 1, ?, ?)
                """,
                (class_group_id, self._actor_subject, now, now),
            )
            row = conn.execute(
                "SELECT * FROM class_groups WHERE id = ?", (class_group_id,)
            ).fetchone()
        return _class_group(_present(row))

    def add_class_member(
        self,
        *,
        class_group_id: str,
        subject: str,
        role: ClassMembershipRole,
    ) -> ClassMembership:
        clean_subject = _required_text(subject, "成员主体", 300)
        normalized_role = ClassMembershipRole(role)
        now = _now()
        with self._connect() as conn:
            organization_id = self._require_class_manager(conn, class_group_id)
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO class_memberships (
                  class_group_id, subject, role, active, created_at, updated_at
                ) VALUES (?, ?, ?, 1, ?, ?)
                ON CONFLICT(class_group_id, subject) DO UPDATE SET
                  role = excluded.role,
                  active = 1,
                  updated_at = excluded.updated_at
                """,
                (
                    class_group_id,
                    clean_subject,
                    normalized_role.value,
                    now,
                    now,
                ),
            )
            organization_role = (
                OrganizationMembershipRole.LEARNER
                if normalized_role is ClassMembershipRole.LEARNER
                else OrganizationMembershipRole.INSTRUCTOR
            )
            existing_org_role = conn.execute(
                """
                SELECT role FROM organization_memberships
                WHERE organization_id = ? AND subject = ?
                """,
                (organization_id, clean_subject),
            ).fetchone()
            if existing_org_role is None:
                conn.execute(
                    """
                    INSERT INTO organization_memberships (
                      organization_id, subject, role, active, created_at, updated_at
                    ) VALUES (?, ?, ?, 1, ?, ?)
                    """,
                    (
                        organization_id,
                        clean_subject,
                        organization_role.value,
                        now,
                        now,
                    ),
                )
            elif (
                str(existing_org_role["role"]) == "LEARNER"
                or organization_role is OrganizationMembershipRole.INSTRUCTOR
            ):
                conn.execute(
                    """
                    UPDATE organization_memberships
                    SET role = ?, active = 1, updated_at = ?
                    WHERE organization_id = ? AND subject = ?
                    """,
                    (
                        organization_role.value,
                        now,
                        organization_id,
                        clean_subject,
                    ),
                )
            row = conn.execute(
                """
                SELECT * FROM class_memberships
                WHERE class_group_id = ? AND subject = ?
                """,
                (class_group_id, clean_subject),
            ).fetchone()
        return _class_membership(_present(row))

    def create_assignment(
        self,
        *,
        class_group_id: str,
        title: str,
        driving_question: str,
        description: str,
        collaboration_mode: AssignmentCollaborationMode,
        structure_policy: StructurePolicy,
        allowed_chip_targets: list[str],
        required_checkpoints: list[ProjectCheckpointKind],
        safety_rules: list[str],
        rubric_dimensions: list[RubricDimension | dict[str, object]],
        due_at: str | None,
        idempotency_key: str,
        submission_requirements: list[str] | None = None,
    ) -> Assignment:
        clean_title = _required_text(title, "任务名称", 240)
        clean_question = _required_text(driving_question, "驱动问题", 4000)
        clean_description = description.strip()[:12000]
        clean_key = _required_text(idempotency_key, "幂等键", 200)
        normalized_mode = AssignmentCollaborationMode(collaboration_mode)
        normalized_structure = StructurePolicy(structure_policy)
        chips = [
            item.lower()
            for item in _unique_texts(allowed_chip_targets, "允许的芯片目标")
        ]
        if not chips or not set(chips).issubset({"esp32s3", "esp32c3"}):
            raise ClassroomValidationError("首版芯片目标只能是 esp32s3 或 esp32c3。")
        checkpoints = list(
            dict.fromkeys(
                ProjectCheckpointKind(item) for item in required_checkpoints
            )
        )
        if not checkpoints:
            raise ClassroomValidationError("项目任务至少需要一个检查点。")
        rules = _unique_texts(safety_rules, "安全规则")
        if not rules:
            raise ClassroomValidationError("项目任务至少需要一条安全规则。")
        requirements = _unique_texts(
            submission_requirements or [], "提交要求"
        )
        dimensions = [RubricDimension.model_validate(item) for item in rubric_dimensions]
        if not dimensions:
            raise ClassroomValidationError("评价量表至少需要一个维度。")
        if len({item.id for item in dimensions}) != len(dimensions):
            raise ClassroomValidationError("评价维度 ID 不能重复。")
        now = _now()
        with self._connect() as conn:
            organization_id = self._require_class_manager(conn, class_group_id)
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                """
                SELECT * FROM assignments
                WHERE class_group_id = ? AND idempotency_key = ?
                """,
                (class_group_id, clean_key),
            ).fetchone()
            if existing is not None:
                if (
                    str(existing["title"]) != clean_title
                    or str(existing["driving_question"]) != clean_question
                    or str(existing["collaboration_mode"]) != normalized_mode.value
                ):
                    raise ClassroomConflictError("同一幂等键不能创建不同项目任务。")
                return _assignment(existing)

            policy_id = _id("assignment_policy")
            policy_revision_id = _id("assignment_policy_revision")
            rubric_id = _id("rubric")
            rubric_revision_id = _id("rubric_revision")
            assignment_id = _id("assignment")
            conn.execute(
                """
                INSERT INTO assignment_policies (
                  id, organization_id, current_revision_id, created_at, updated_at
                ) VALUES (?, ?, NULL, ?, ?)
                """,
                (policy_id, organization_id, now, now),
            )
            conn.execute(
                """
                INSERT INTO assignment_policy_revisions (
                  id, policy_id, revision, allowed_chip_targets_json,
                  allowed_device_package_ids_json,
                  allowed_component_package_ids_json, structure_policy,
                  required_checkpoints_json, submission_requirements_json,
                  safety_rules_json, supersedes_revision_id,
                  created_by_subject, created_at
                ) VALUES (?, ?, 1, ?, '[]', '[]', ?, ?, ?, ?, NULL, ?, ?)
                """,
                (
                    policy_revision_id,
                    policy_id,
                    _dump(chips),
                    normalized_structure.value,
                    _dump([item.value for item in checkpoints]),
                    _dump(requirements),
                    _dump(rules),
                    self._actor_subject,
                    now,
                ),
            )
            conn.execute(
                """
                UPDATE assignment_policies
                SET current_revision_id = ? WHERE id = ?
                """,
                (policy_revision_id, policy_id),
            )
            conn.execute(
                """
                INSERT INTO rubrics (
                  id, organization_id, current_revision_id, created_at, updated_at
                ) VALUES (?, ?, NULL, ?, ?)
                """,
                (rubric_id, organization_id, now, now),
            )
            conn.execute(
                """
                INSERT INTO rubric_revisions (
                  id, rubric_id, revision, dimensions_json,
                  supersedes_revision_id, created_by_subject, created_at
                ) VALUES (?, ?, 1, ?, NULL, ?, ?)
                """,
                (
                    rubric_revision_id,
                    rubric_id,
                    _dump([item.model_dump(mode="json", by_alias=True) for item in dimensions]),
                    self._actor_subject,
                    now,
                ),
            )
            conn.execute(
                "UPDATE rubrics SET current_revision_id = ? WHERE id = ?",
                (rubric_revision_id, rubric_id),
            )
            conn.execute(
                """
                INSERT INTO assignments (
                  id, class_group_id, title, driving_question, description,
                  collaboration_mode, policy_revision_id, rubric_revision_id,
                  due_at, created_by_subject, idempotency_key, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    assignment_id,
                    class_group_id,
                    clean_title,
                    clean_question,
                    clean_description,
                    normalized_mode.value,
                    policy_revision_id,
                    rubric_revision_id,
                    due_at,
                    self._actor_subject,
                    clean_key,
                    now,
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM assignments WHERE id = ?", (assignment_id,)
            ).fetchone()
        return _assignment(_present(row))

    def get_assignment_policy_revision(
        self, revision_id: str
    ) -> AssignmentPolicyRevision:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM assignment_policy_revisions WHERE id = ?",
                (revision_id,),
            ).fetchone()
            if row is None:
                raise ClassroomNotFoundError("项目任务策略不存在。")
            organization_id = conn.execute(
                """
                SELECT organization_id FROM assignment_policies WHERE id = ?
                """,
                (row["policy_id"],),
            ).fetchone()
            if organization_id is None or not self._has_organization_membership(
                conn, str(organization_id["organization_id"])
            ):
                raise ClassroomAuthorizationError("无权查看该项目任务策略。")
        return _assignment_policy(row)

    def bind_work_to_assignment(
        self,
        *,
        assignment_id: str,
        work_id: str,
        collaboration_mode: AssignmentCollaborationMode,
    ) -> WorkLearningBinding:
        normalized_mode = AssignmentCollaborationMode(collaboration_mode)
        now = _now()
        with self._connect() as conn:
            assignment = self._assignment_access_row(conn, assignment_id)
            expected_mode = AssignmentCollaborationMode(
                str(assignment["collaboration_mode"])
            )
            if normalized_mode is not expected_mode:
                raise ClassroomValidationError("作品协作方式必须符合项目任务设置。")
            project = conn.execute(
                "SELECT id, owner_subject FROM projects WHERE id = ?",
                (work_id,),
            ).fetchone()
            if project is None:
                raise ClassroomNotFoundError("作品不存在。")
            owner_subject = str(project["owner_subject"] or _LOCAL_SUBJECT)
            class_group_id = str(assignment["class_group_id"])
            actor_can_manage = self._is_class_manager(conn, class_group_id)
            owner_is_learner = conn.execute(
                """
                SELECT 1 FROM class_memberships
                WHERE class_group_id = ? AND subject = ? AND active = 1
                  AND role = 'LEARNER'
                """,
                (class_group_id, owner_subject),
            ).fetchone()
            if owner_subject != self._actor_subject and not (
                actor_can_manage and owner_is_learner is not None
            ):
                raise ClassroomAuthorizationError("只能绑定自己的作品或本班学生作品。")
            if not actor_can_manage:
                membership = conn.execute(
                    """
                    SELECT 1 FROM class_memberships
                    WHERE class_group_id = ? AND subject = ? AND active = 1
                    """,
                    (class_group_id, self._actor_subject),
                ).fetchone()
                if membership is None:
                    raise ClassroomAuthorizationError("你不是该班级成员。")

            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT * FROM work_learning_contexts WHERE work_id = ?",
                (work_id,),
            ).fetchone()
            if existing is not None:
                if (
                    str(existing["assignment_id"]) != assignment_id
                    or str(existing["collaboration_mode"]) != normalized_mode.value
                ):
                    raise ClassroomConflictError("作品已经绑定到另一个项目任务。")
                return _work_binding(existing)
            conn.execute(
                """
                INSERT INTO work_learning_contexts (
                  work_id, assignment_id, collaboration_mode,
                  process_milestone, process_state,
                  current_proposal_revision_id, current_submission_revision_id,
                  revision, created_at, updated_at
                ) VALUES (?, ?, ?, 'PROPOSAL', 'PROPOSAL_DRAFT', NULL, NULL, 1, ?, ?)
                """,
                (work_id, assignment_id, normalized_mode.value, now, now),
            )
            conn.execute(
                """
                INSERT INTO work_memberships (
                  work_id, subject, role, active, created_at, updated_at
                ) VALUES (?, ?, 'OWNER', 1, ?, ?)
                ON CONFLICT(work_id, subject) DO UPDATE SET
                  role = 'OWNER', active = 1, updated_at = excluded.updated_at
                """,
                (work_id, owner_subject, now, now),
            )
            row = conn.execute(
                "SELECT * FROM work_learning_contexts WHERE work_id = ?",
                (work_id,),
            ).fetchone()
        return _work_binding(_present(row))

    def add_work_member(
        self,
        *,
        work_id: str,
        subject: str,
        role: WorkMembershipRole,
    ) -> WorkMembership:
        clean_subject = _required_text(subject, "作品成员主体", 300)
        normalized_role = WorkMembershipRole(role)
        if normalized_role is WorkMembershipRole.OWNER:
            raise ClassroomValidationError("作品所有者由 Work 事实决定，不能通过成员接口改写。")
        now = _now()
        with self._connect() as conn:
            self._require_work_edit(conn, work_id)
            context = conn.execute(
                """
                SELECT a.class_group_id
                FROM work_learning_contexts wlc
                JOIN assignments a ON a.id = wlc.assignment_id
                WHERE wlc.work_id = ?
                """,
                (work_id,),
            ).fetchone()
            if context is None:
                raise ClassroomNotFoundError("作品尚未绑定项目任务。")
            class_member = conn.execute(
                """
                SELECT 1 FROM class_memberships
                WHERE class_group_id = ? AND subject = ? AND active = 1
                """,
                (context["class_group_id"], clean_subject),
            ).fetchone()
            if class_member is None:
                raise ClassroomValidationError("作品成员必须先加入当前班级。")
            conn.execute(
                """
                INSERT INTO work_memberships (
                  work_id, subject, role, active, created_at, updated_at
                ) VALUES (?, ?, ?, 1, ?, ?)
                ON CONFLICT(work_id, subject) DO UPDATE SET
                  role = excluded.role, active = 1, updated_at = excluded.updated_at
                """,
                (work_id, clean_subject, normalized_role.value, now, now),
            )
            row = conn.execute(
                "SELECT * FROM work_memberships WHERE work_id = ? AND subject = ?",
                (work_id, clean_subject),
            ).fetchone()
        return _work_membership(_present(row))

    def get_work_learning_projection(
        self, work_id: str
    ) -> WorkLearningProjection:
        with self._connect() as conn:
            row = self._learning_row(conn, work_id)
            if row is None:
                raise ClassroomNotFoundError("作品尚未绑定项目任务。")
            self._require_work_access(conn, work_id)
            completed = self._checkpoint_completion(conn, work_id)
            required = [
                ProjectCheckpointKind(value)
                for value in json.loads(str(row["required_checkpoints_json"]))
            ]
            build_row = conn.execute(
                """
                SELECT d.route FROM project_build_route_decisions AS d
                JOIN work_learning_contexts AS c
                  ON c.current_build_route_decision_id = d.id
                WHERE d.work_id = ? AND c.work_id = ? AND d.status = 'CURRENT'
                """,
                (work_id, work_id),
            ).fetchone()
        return WorkLearningProjection(
            learningContext=WorkLearningContextSnapshot(
                organization=LearningOrganizationRef(
                    id=str(row["organization_id"]), name=str(row["organization_name"])
                ),
                course=LearningCourseRef(
                    id=str(row["course_id"]), title=str(row["course_title"])
                ),
                classGroup=LearningClassRef(
                    id=str(row["class_group_id"]), title=str(row["class_title"])
                ),
                assignment=LearningAssignmentRef(
                    id=str(row["assignment_id"]),
                    title=str(row["assignment_title"]),
                    drivingQuestion=str(row["driving_question"]),
                ),
                collaborationMode=AssignmentCollaborationMode(
                    str(row["collaboration_mode"])
                ),
            ),
            projectProcess=ProjectProcessSnapshot(
                milestone=ProjectProcessMilestone(str(row["process_milestone"])),
                state=ProjectProcessState(str(row["process_state"])),
                currentProposalRevisionId=row["current_proposal_revision_id"],
                currentSimulationProjectRevisionId=row[
                    "current_simulation_project_revision_id"
                ],
                currentSubmissionRevisionId=row["current_submission_revision_id"],
                buildRoute=(
                    BuildRoute(str(build_row["route"])) if build_row is not None else None
                ),
                requiredCheckpoints=[
                    ProjectCheckpointSummary(
                        kind=item,
                        label=_CHECKPOINT_LABELS[item],
                        required=True,
                        completed=completed.get(item, False),
                    )
                    for item in required
                ],
                revision=int(row["revision"]),
            ),
        )

    def optional_work_learning_projection(
        self, work_id: str
    ) -> WorkLearningProjection | None:
        with self._connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM work_learning_contexts WHERE work_id = ?", (work_id,)
            ).fetchone()
        if exists is None:
            return None
        return self.get_work_learning_projection(work_id)

    def append_journal_entry(
        self,
        *,
        work_id: str,
        kind: ProcessJournalEntryKind | str,
        title: str,
        body: str,
        related_kind: str | None = None,
        related_id: str | None = None,
    ) -> ProcessJournalEntry:
        normalized_kind = ProcessJournalEntryKind(kind)
        clean_title = _required_text(title, "日志标题", 240)
        clean_body = _required_text(body, "日志内容", 12000)
        now = _now()
        entry_id = _id("journal")
        with self._connect() as conn:
            self._require_work_edit(conn, work_id)
            conn.execute(
                """
                INSERT INTO project_process_journal (
                  id, work_id, actor_subject, kind, title, body,
                  related_kind, related_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry_id,
                    work_id,
                    self._actor_subject,
                    normalized_kind.value,
                    clean_title,
                    clean_body,
                    related_kind,
                    related_id,
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM project_process_journal WHERE id = ?", (entry_id,)
            ).fetchone()
        return _journal_entry(_present(row))

    def list_journal(self, work_id: str) -> list[ProcessJournalEntry]:
        with self._connect() as conn:
            self._require_work_access(conn, work_id)
            rows = conn.execute(
                """
                SELECT * FROM project_process_journal
                WHERE work_id = ? ORDER BY created_at DESC, id DESC
                """,
                (work_id,),
            ).fetchall()
        return [_journal_entry(row) for row in rows]

    def get_work_overview(self, work_id: str) -> ClassroomWorkOverview:
        projection = self.get_work_learning_projection(work_id)
        with self._connect() as conn:
            self._require_work_access(conn, work_id)
            project = conn.execute(
                "SELECT name FROM projects WHERE id = ?", (work_id,)
            ).fetchone()
            binding = conn.execute(
                "SELECT * FROM work_learning_contexts WHERE work_id = ?", (work_id,)
            ).fetchone()
            members = conn.execute(
                """
                SELECT * FROM work_memberships
                WHERE work_id = ? AND active = 1 ORDER BY role, subject
                """,
                (work_id,),
            ).fetchall()
            journal = conn.execute(
                """
                SELECT * FROM project_process_journal
                WHERE work_id = ? ORDER BY created_at DESC, id DESC
                """,
                (work_id,),
            ).fetchall()
        return ClassroomWorkOverview(
            projectName=str(_present(project)["name"]),
            binding=_work_binding(_present(binding)),
            projection=projection,
            members=[_work_membership(row) for row in members],
            journal=[_journal_entry(row) for row in journal],
        )

    def assert_work_access(self, work_id: str, *, edit: bool = False) -> None:
        with self._connect() as conn:
            if edit:
                self._require_work_edit(conn, work_id)
            else:
                self._require_work_access(conn, work_id)

    def assert_work_instructor(self, work_id: str) -> None:
        with self._connect() as conn:
            context = conn.execute(
                """
                SELECT a.class_group_id
                FROM work_learning_contexts wlc
                JOIN assignments a ON a.id = wlc.assignment_id
                WHERE wlc.work_id = ?
                """,
                (work_id,),
            ).fetchone()
            if context is None:
                raise ClassroomNotFoundError("作品尚未绑定项目任务。")
            if not self._is_class_manager(conn, str(context["class_group_id"])):
                raise ClassroomAuthorizationError("只有本班教师或助教可以评审。")

    def legacy_learning_sources(self, work_id: str) -> LegacyLearningSources:
        """Read legacy account/proposal/lesson references without creating new facts."""

        with self._connect() as conn:
            project = conn.execute(
                "SELECT id, owner_subject FROM projects WHERE id = ?", (work_id,)
            ).fetchone()
            if project is None:
                raise ClassroomNotFoundError("作品不存在。")
            owner_subject = (
                str(project["owner_subject"])
                if project["owner_subject"] is not None
                else None
            )
            owner_key = owner_subject or _LOCAL_SUBJECT
            if owner_key != self._actor_subject:
                self._require_work_access(conn, work_id)
            proposal_ids = [
                str(row["id"])
                for row in conn.execute(
                    "SELECT id FROM proposals WHERE project_id = ? ORDER BY version",
                    (work_id,),
                ).fetchall()
            ]
            lesson_run_ids = [
                str(row["id"])
                for row in conn.execute(
                    "SELECT id FROM lesson_runs WHERE project_id = ? ORDER BY version",
                    (work_id,),
                ).fetchall()
            ]
            bound = conn.execute(
                "SELECT 1 FROM work_learning_contexts WHERE work_id = ?", (work_id,)
            ).fetchone()
        return LegacyLearningSources(
            workId=work_id,
            ownerSubject=owner_subject,
            accountPersona=self._legacy_account_persona(owner_subject),
            proposalIds=proposal_ids,
            lessonRunIds=lesson_run_ids,
            learningContextBound=bound is not None,
        )

    def _legacy_account_persona(self, owner_subject: str | None) -> str | None:
        if owner_subject is None:
            return None
        auth_path = self._data_dir / "auth" / "zhangwen-auth.sqlite3"
        if not auth_path.exists():
            return None
        with sqlite3.connect(auth_path) as conn:
            conn.row_factory = sqlite3.Row
            try:
                row = conn.execute(
                    """
                    SELECT profile_json FROM local_accounts
                    WHERE id = ? OR cloud_subject = ?
                    ORDER BY id = ? DESC LIMIT 1
                    """,
                    (owner_subject, owner_subject, owner_subject),
                ).fetchone()
            except sqlite3.OperationalError:
                # Auth schema v1 had no persona/profile columns. Reading it must
                # not silently migrate a separate credentials database.
                return None
        if row is None or row["profile_json"] in {None, ""}:
            return None
        try:
            profile = json.loads(str(row["profile_json"]))
        except json.JSONDecodeError:
            return None
        value = profile.get("persona") if isinstance(profile, dict) else None
        return str(value) if isinstance(value, str) else None

    def _require_organization_manager(
        self, conn: sqlite3.Connection, organization_id: str
    ) -> None:
        row = conn.execute(
            """
            SELECT role FROM organization_memberships
            WHERE organization_id = ? AND subject = ? AND active = 1
            """,
            (organization_id, self._actor_subject),
        ).fetchone()
        if row is None or str(row["role"]) not in {"ADMIN", "INSTRUCTOR"}:
            raise ClassroomAuthorizationError("只有机构管理员或教师可以执行此操作。")

    def _require_class_manager(
        self, conn: sqlite3.Connection, class_group_id: str
    ) -> str:
        row = conn.execute(
            """
            SELECT c.organization_id
            FROM class_groups AS g
            JOIN courses AS c ON c.id = g.course_id
            WHERE g.id = ?
            """,
            (class_group_id,),
        ).fetchone()
        if row is None:
            raise ClassroomNotFoundError("班级不存在。")
        if not self._is_class_manager(conn, class_group_id):
            raise ClassroomAuthorizationError("只有本班教师或助教可以执行此操作。")
        return str(row["organization_id"])

    def _is_class_manager(
        self, conn: sqlite3.Connection, class_group_id: str
    ) -> bool:
        class_role = conn.execute(
            """
            SELECT role FROM class_memberships
            WHERE class_group_id = ? AND subject = ? AND active = 1
            """,
            (class_group_id, self._actor_subject),
        ).fetchone()
        if class_role is not None and str(class_role["role"]) in {
            "INSTRUCTOR",
            "TEACHING_ASSISTANT",
        }:
            return True
        organization_role = conn.execute(
            """
            SELECT om.role
            FROM class_groups AS g
            JOIN courses AS c ON c.id = g.course_id
            JOIN organization_memberships AS om
              ON om.organization_id = c.organization_id
            WHERE g.id = ? AND om.subject = ? AND om.active = 1
            """,
            (class_group_id, self._actor_subject),
        ).fetchone()
        return organization_role is not None and str(organization_role["role"]) in {
            "ADMIN",
            "INSTRUCTOR",
        }

    def _has_organization_membership(
        self, conn: sqlite3.Connection, organization_id: str
    ) -> bool:
        return (
            conn.execute(
                """
                SELECT 1 FROM organization_memberships
                WHERE organization_id = ? AND subject = ? AND active = 1
                """,
                (organization_id, self._actor_subject),
            ).fetchone()
            is not None
        )

    def _assignment_access_row(
        self, conn: sqlite3.Connection, assignment_id: str
    ) -> sqlite3.Row:
        row = conn.execute(
            """
            SELECT a.*, c.organization_id
            FROM assignments AS a
            JOIN class_groups AS g ON g.id = a.class_group_id
            JOIN courses AS c ON c.id = g.course_id
            WHERE a.id = ?
            """,
            (assignment_id,),
        ).fetchone()
        if row is None:
            raise ClassroomNotFoundError("项目任务不存在。")
        if not self._has_organization_membership(conn, str(row["organization_id"])):
            raise ClassroomAuthorizationError("无权访问该机构的项目任务。")
        class_member = conn.execute(
            """
            SELECT 1 FROM class_memberships
            WHERE class_group_id = ? AND subject = ? AND active = 1
            """,
            (row["class_group_id"], self._actor_subject),
        ).fetchone()
        if class_member is None and not self._is_class_manager(
            conn, str(row["class_group_id"])
        ):
            raise ClassroomAuthorizationError("你不是该班级成员。")
        return row

    def _require_work_access(self, conn: sqlite3.Connection, work_id: str) -> None:
        if not self._can_access_work(conn, work_id):
            raise ClassroomAuthorizationError("无权查看该作品的课堂过程。")

    def _require_work_edit(self, conn: sqlite3.Connection, work_id: str) -> None:
        if not self._can_edit_work(conn, work_id):
            raise ClassroomAuthorizationError("无权修改该作品的课堂过程。")

    def _can_access_work(self, conn: sqlite3.Connection, work_id: str) -> bool:
        row = conn.execute(
            """
            SELECT p.owner_subject, wlc.assignment_id, a.class_group_id
            FROM projects AS p
            LEFT JOIN work_learning_contexts AS wlc ON wlc.work_id = p.id
            LEFT JOIN assignments AS a ON a.id = wlc.assignment_id
            WHERE p.id = ?
            """,
            (work_id,),
        ).fetchone()
        if row is None:
            return False
        owner_key = str(row["owner_subject"] or _LOCAL_SUBJECT)
        if owner_key == self._actor_subject:
            return True
        member = conn.execute(
            """
            SELECT 1 FROM work_memberships
            WHERE work_id = ? AND subject = ? AND active = 1
            """,
            (work_id, self._actor_subject),
        ).fetchone()
        if member is not None:
            return True
        return row["class_group_id"] is not None and self._is_class_manager(
            conn, str(row["class_group_id"])
        )

    def _can_edit_work(self, conn: sqlite3.Connection, work_id: str) -> bool:
        row = conn.execute(
            "SELECT owner_subject FROM projects WHERE id = ?", (work_id,)
        ).fetchone()
        if row is None:
            return False
        if str(row["owner_subject"] or _LOCAL_SUBJECT) == self._actor_subject:
            return True
        member = conn.execute(
            """
            SELECT role FROM work_memberships
            WHERE work_id = ? AND subject = ? AND active = 1
            """,
            (work_id, self._actor_subject),
        ).fetchone()
        if member is not None and str(member["role"]) in {"OWNER", "EDITOR"}:
            return True
        context = conn.execute(
            """
            SELECT a.class_group_id
            FROM work_learning_contexts AS wlc
            JOIN assignments AS a ON a.id = wlc.assignment_id
            WHERE wlc.work_id = ?
            """,
            (work_id,),
        ).fetchone()
        return context is not None and self._is_class_manager(
            conn, str(context["class_group_id"])
        )

    @staticmethod
    def _checkpoint_completion(
        conn: sqlite3.Connection, work_id: str
    ) -> dict[ProjectCheckpointKind, bool]:
        context = conn.execute(
            """
            SELECT current_proposal_revision_id, current_build_route_decision_id,
                   current_submission_revision_id
            FROM work_learning_contexts WHERE work_id = ?
            """,
            (work_id,),
        ).fetchone()
        current_proposal_revision_id = (
            str(context["current_proposal_revision_id"])
            if context is not None and context["current_proposal_revision_id"] is not None
            else None
        )
        current_build_route_decision_id = (
            str(context["current_build_route_decision_id"])
            if context is not None
            and context["current_build_route_decision_id"] is not None
            else None
        )
        current_submission_revision_id = (
            str(context["current_submission_revision_id"])
            if context is not None
            and context["current_submission_revision_id"] is not None
            else None
        )
        rows = conn.execute(
            """
            SELECT checkpoint, decision, target_revision_id
            FROM project_checkpoint_reviews
            WHERE work_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (work_id,),
        ).fetchall()
        result: dict[ProjectCheckpointKind, bool] = {}
        for row in rows:
            try:
                checkpoint = ProjectCheckpointKind(str(row["checkpoint"]))
            except ValueError:
                continue
            if checkpoint in {
                ProjectCheckpointKind.PROPOSAL_STUDENT_CONFIRMED,
                ProjectCheckpointKind.PROPOSAL_INSTRUCTOR_APPROVED,
            } and str(row["target_revision_id"]) != current_proposal_revision_id:
                continue
            if (
                checkpoint is ProjectCheckpointKind.BUILD_ROUTE_SELECTED
                and str(row["target_revision_id"]) != current_build_route_decision_id
            ):
                continue
            if (
                checkpoint is ProjectCheckpointKind.SUBMISSION_INSTRUCTOR_ACCEPTED
                and str(row["target_revision_id"]) != current_submission_revision_id
            ):
                continue
            result.setdefault(checkpoint, str(row["decision"]) == "APPROVED")
        return result

    @staticmethod
    def _learning_row(
        conn: sqlite3.Connection, work_id: str
    ) -> sqlite3.Row | None:
        return conn.execute(
            """
            SELECT
              wlc.*,
              a.id AS assignment_id,
              a.title AS assignment_title,
              a.driving_question,
              a.policy_revision_id,
              g.id AS class_group_id,
              g.title AS class_title,
              c.id AS course_id,
              c.title AS course_title,
              o.id AS organization_id,
              o.name AS organization_name,
              apr.required_checkpoints_json
            FROM work_learning_contexts AS wlc
            JOIN assignments AS a ON a.id = wlc.assignment_id
            JOIN class_groups AS g ON g.id = a.class_group_id
            JOIN courses AS c ON c.id = g.course_id
            JOIN organizations AS o ON o.id = c.organization_id
            JOIN assignment_policy_revisions AS apr ON apr.id = a.policy_revision_id
            WHERE wlc.work_id = ?
            """,
            (work_id,),
        ).fetchone()

    @staticmethod
    def _course_row(conn: sqlite3.Connection, course_id: str) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
        if row is None:
            raise ClassroomNotFoundError("课程不存在。")
        return row

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


def _organization(row: sqlite3.Row) -> Organization:
    return Organization(
        id=str(row["id"]),
        name=str(row["name"]),
        createdBySubject=str(row["created_by_subject"]),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _course(row: sqlite3.Row) -> Course:
    return Course(
        id=str(row["id"]),
        organizationId=str(row["organization_id"]),
        title=str(row["title"]),
        code=str(row["code"]),
        description=str(row["description"]),
        createdBySubject=str(row["created_by_subject"]),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _class_group(row: sqlite3.Row) -> ClassGroup:
    return ClassGroup(
        id=str(row["id"]),
        courseId=str(row["course_id"]),
        title=str(row["title"]),
        term=str(row["term"]),
        createdBySubject=str(row["created_by_subject"]),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _class_membership(row: sqlite3.Row) -> ClassMembership:
    return ClassMembership(
        classGroupId=str(row["class_group_id"]),
        subject=str(row["subject"]),
        role=ClassMembershipRole(str(row["role"])),
        active=bool(row["active"]),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _work_membership(row: sqlite3.Row) -> WorkMembership:
    return WorkMembership(
        workId=str(row["work_id"]),
        subject=str(row["subject"]),
        role=WorkMembershipRole(str(row["role"])),
        active=bool(row["active"]),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _assignment(row: sqlite3.Row) -> Assignment:
    return Assignment(
        id=str(row["id"]),
        classGroupId=str(row["class_group_id"]),
        title=str(row["title"]),
        drivingQuestion=str(row["driving_question"]),
        description=str(row["description"]),
        collaborationMode=AssignmentCollaborationMode(str(row["collaboration_mode"])),
        policyRevisionId=str(row["policy_revision_id"]),
        rubricRevisionId=str(row["rubric_revision_id"]),
        dueAt=row["due_at"],
        createdBySubject=str(row["created_by_subject"]),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _assignment_policy(row: sqlite3.Row) -> AssignmentPolicyRevision:
    return AssignmentPolicyRevision(
        id=str(row["id"]),
        policyId=str(row["policy_id"]),
        revision=int(row["revision"]),
        allowedChipTargets=json.loads(str(row["allowed_chip_targets_json"])),
        allowedDevicePackageIds=json.loads(
            str(row["allowed_device_package_ids_json"])
        ),
        allowedComponentPackageIds=json.loads(
            str(row["allowed_component_package_ids_json"])
        ),
        structurePolicy=StructurePolicy(str(row["structure_policy"])),
        requiredCheckpoints=json.loads(str(row["required_checkpoints_json"])),
        submissionRequirements=json.loads(
            str(row["submission_requirements_json"])
        ),
        safetyRules=json.loads(str(row["safety_rules_json"])),
        supersedesRevisionId=row["supersedes_revision_id"],
        createdBySubject=str(row["created_by_subject"]),
        createdAt=str(row["created_at"]),
    )


def _rubric_revision(row: sqlite3.Row) -> RubricRevision:
    return RubricRevision(
        id=str(row["id"]),
        rubricId=str(row["rubric_id"]),
        revision=int(row["revision"]),
        dimensions=json.loads(str(row["dimensions_json"])),
        supersedesRevisionId=row["supersedes_revision_id"],
        createdBySubject=str(row["created_by_subject"]),
        createdAt=str(row["created_at"]),
    )


def _work_binding(row: sqlite3.Row) -> WorkLearningBinding:
    return WorkLearningBinding(
        workId=str(row["work_id"]),
        assignmentId=str(row["assignment_id"]),
        collaborationMode=AssignmentCollaborationMode(str(row["collaboration_mode"])),
        processMilestone=ProjectProcessMilestone(str(row["process_milestone"])),
        processState=ProjectProcessState(str(row["process_state"])),
        revision=int(row["revision"]),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _journal_entry(row: sqlite3.Row) -> ProcessJournalEntry:
    return ProcessJournalEntry(
        id=str(row["id"]),
        workId=str(row["work_id"]),
        actorSubject=str(row["actor_subject"]),
        kind=ProcessJournalEntryKind(str(row["kind"])),
        title=str(row["title"]),
        body=str(row["body"]),
        relatedKind=row["related_kind"],
        relatedId=row["related_id"],
        createdAt=str(row["created_at"]),
    )


def _required_text(value: str, label: str, maximum: int) -> str:
    clean = value.strip()
    if not clean:
        raise ClassroomValidationError(f"{label}不能为空。")
    if len(clean) > maximum:
        raise ClassroomValidationError(f"{label}过长。")
    return clean


def _unique_texts(values: list[str], label: str) -> list[str]:
    normalized = [item.strip() for item in values]
    if any(not item for item in normalized):
        raise ClassroomValidationError(f"{label}不能包含空项。")
    return list(dict.fromkeys(normalized))


def _present(row: sqlite3.Row | None) -> sqlite3.Row:
    if row is None:
        raise ClassroomNotFoundError("记录不存在。")
    return row


def _dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _now() -> str:
    return datetime.now(UTC).isoformat()
