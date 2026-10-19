"""Strict classroom and project-process boundary models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProjectLearningModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class OrganizationMembershipRole(StrEnum):
    ADMIN = "ADMIN"
    INSTRUCTOR = "INSTRUCTOR"
    LEARNER = "LEARNER"


class ClassMembershipRole(StrEnum):
    INSTRUCTOR = "INSTRUCTOR"
    TEACHING_ASSISTANT = "TEACHING_ASSISTANT"
    LEARNER = "LEARNER"


class WorkMembershipRole(StrEnum):
    OWNER = "OWNER"
    EDITOR = "EDITOR"
    VIEWER = "VIEWER"


class AssignmentCollaborationMode(StrEnum):
    INDIVIDUAL = "INDIVIDUAL"
    TEAM = "TEAM"


class StructurePolicy(StrEnum):
    OPTIONAL = "OPTIONAL"
    REQUIRED = "REQUIRED"
    PROHIBITED = "PROHIBITED"


class BuildRoute(StrEnum):
    WITH_STRUCTURE = "WITH_STRUCTURE"
    WITHOUT_STRUCTURE = "WITHOUT_STRUCTURE"


class ProjectProcessMilestone(StrEnum):
    PROPOSAL = "PROPOSAL"
    SIMULATION = "SIMULATION"
    MAKING = "MAKING"
    COMPLETE = "COMPLETE"


class ProjectProcessState(StrEnum):
    PROPOSAL_DRAFT = "PROPOSAL_DRAFT"
    PROPOSAL_READY_FOR_REVIEW = "PROPOSAL_READY_FOR_REVIEW"
    PROPOSAL_IN_REVIEW = "PROPOSAL_IN_REVIEW"
    PROPOSAL_CHANGES_REQUESTED = "PROPOSAL_CHANGES_REQUESTED"
    PROPOSAL_APPROVED = "PROPOSAL_APPROVED"
    SIMULATION_DRAFT = "SIMULATION_DRAFT"
    SIMULATION_READY = "SIMULATION_READY"
    SIMULATION_RUNNING = "SIMULATION_RUNNING"
    SIMULATION_CHANGES_REQUIRED = "SIMULATION_CHANGES_REQUIRED"
    SIMULATION_VALIDATED = "SIMULATION_VALIDATED"
    BUILD_ROUTE_REQUIRED = "BUILD_ROUTE_REQUIRED"
    STRUCTURE_DESIGN = "STRUCTURE_DESIGN"
    ASSEMBLY_IN_PROGRESS = "ASSEMBLY_IN_PROGRESS"
    DEVICE_DEPLOYMENT_READY = "DEVICE_DEPLOYMENT_READY"
    DEVICE_DEPLOYING = "DEVICE_DEPLOYING"
    PHYSICAL_OBSERVATION_REQUIRED = "PHYSICAL_OBSERVATION_REQUIRED"
    SUBMISSION_DRAFT = "SUBMISSION_DRAFT"
    SUBMISSION_IN_REVIEW = "SUBMISSION_IN_REVIEW"
    SUBMISSION_CHANGES_REQUESTED = "SUBMISSION_CHANGES_REQUESTED"
    COMPLETED = "COMPLETED"

    @property
    def milestone(self) -> ProjectProcessMilestone:
        if self in {
            self.PROPOSAL_DRAFT,
            self.PROPOSAL_READY_FOR_REVIEW,
            self.PROPOSAL_IN_REVIEW,
            self.PROPOSAL_CHANGES_REQUESTED,
            self.PROPOSAL_APPROVED,
        }:
            return ProjectProcessMilestone.PROPOSAL
        if self in {
            self.SIMULATION_DRAFT,
            self.SIMULATION_READY,
            self.SIMULATION_RUNNING,
            self.SIMULATION_CHANGES_REQUIRED,
            self.SIMULATION_VALIDATED,
        }:
            return ProjectProcessMilestone.SIMULATION
        if self is self.COMPLETED:
            return ProjectProcessMilestone.COMPLETE
        return ProjectProcessMilestone.MAKING


class ProjectCheckpointKind(StrEnum):
    PROPOSAL_STUDENT_CONFIRMED = "PROPOSAL_STUDENT_CONFIRMED"
    PROPOSAL_INSTRUCTOR_APPROVED = "PROPOSAL_INSTRUCTOR_APPROVED"
    SCHEMATIC_VALIDATED = "SCHEMATIC_VALIDATED"
    BEHAVIOR_SIMULATION_PASSED = "BEHAVIOR_SIMULATION_PASSED"
    BUILD_ROUTE_SELECTED = "BUILD_ROUTE_SELECTED"
    DEVICE_UPLOAD_VERIFIED = "DEVICE_UPLOAD_VERIFIED"
    PHYSICAL_BEHAVIOR_CONFIRMED = "PHYSICAL_BEHAVIOR_CONFIRMED"
    SUBMISSION_INSTRUCTOR_ACCEPTED = "SUBMISSION_INSTRUCTOR_ACCEPTED"


class ValidationLevel(StrEnum):
    SCHEMATIC_VALIDATED = "SCHEMATIC_VALIDATED"
    BEHAVIOR_SIMULATION_PASSED = "BEHAVIOR_SIMULATION_PASSED"
    FIRMWARE_BOOT_PASSED = "FIRMWARE_BOOT_PASSED"
    DEVICE_UPLOAD_VERIFIED = "DEVICE_UPLOAD_VERIFIED"
    PHYSICAL_BEHAVIOR_CONFIRMED = "PHYSICAL_BEHAVIOR_CONFIRMED"
    INSTRUCTOR_ACCEPTED = "INSTRUCTOR_ACCEPTED"


class ProjectProposalStatus(StrEnum):
    DRAFT = "DRAFT"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    STALE = "STALE"
    SUPERSEDED = "SUPERSEDED"


class ProjectProposalSourceKind(StrEnum):
    MANUAL = "MANUAL"
    FACILITATOR_DRAFT = "FACILITATOR_DRAFT"
    LEGACY_ADAPTER = "LEGACY_ADAPTER"


class CheckpointReviewDecision(StrEnum):
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"


class ProcessJournalEntryKind(StrEnum):
    IDEA = "IDEA"
    PROPOSAL_REVISION = "PROPOSAL_REVISION"
    TEST = "TEST"
    FAILURE = "FAILURE"
    DECISION = "DECISION"
    REFLECTION = "REFLECTION"
    INSTRUCTOR_FEEDBACK = "INSTRUCTOR_FEEDBACK"
    SUBMISSION = "SUBMISSION"


class SubmissionStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    ACCEPTED = "ACCEPTED"
    SUPERSEDED = "SUPERSEDED"


class InstructorReviewDecision(StrEnum):
    ACCEPTED = "ACCEPTED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"


class RubricAssessmentStatus(StrEnum):
    DRAFT = "DRAFT"
    FINALIZED = "FINALIZED"


class Organization(ProjectLearningModel):
    id: str
    name: str
    created_by_subject: str = Field(alias="createdBySubject")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class OrganizationMembership(ProjectLearningModel):
    organization_id: str = Field(alias="organizationId")
    subject: str
    role: OrganizationMembershipRole
    active: bool
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class Course(ProjectLearningModel):
    id: str
    organization_id: str = Field(alias="organizationId")
    title: str
    code: str
    description: str
    created_by_subject: str = Field(alias="createdBySubject")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class ClassGroup(ProjectLearningModel):
    id: str
    course_id: str = Field(alias="courseId")
    title: str
    term: str
    created_by_subject: str = Field(alias="createdBySubject")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class ClassMembership(ProjectLearningModel):
    class_group_id: str = Field(alias="classGroupId")
    subject: str
    role: ClassMembershipRole
    active: bool
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class WorkMembership(ProjectLearningModel):
    work_id: str = Field(alias="workId")
    subject: str
    role: WorkMembershipRole
    active: bool
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class RubricDimension(ProjectLearningModel):
    id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    max_score: float = Field(alias="maxScore", gt=0, le=1000)


class AssignmentPolicyRevision(ProjectLearningModel):
    id: str
    policy_id: str = Field(alias="policyId")
    revision: int = Field(ge=1)
    allowed_chip_targets: list[str] = Field(alias="allowedChipTargets")
    allowed_device_package_ids: list[str] = Field(
        default_factory=list, alias="allowedDevicePackageIds"
    )
    allowed_component_package_ids: list[str] = Field(
        default_factory=list, alias="allowedComponentPackageIds"
    )
    structure_policy: StructurePolicy = Field(alias="structurePolicy")
    required_checkpoints: list[ProjectCheckpointKind] = Field(
        alias="requiredCheckpoints"
    )
    submission_requirements: list[str] = Field(
        default_factory=list, alias="submissionRequirements"
    )
    safety_rules: list[str] = Field(alias="safetyRules")
    supersedes_revision_id: str | None = Field(alias="supersedesRevisionId")
    created_by_subject: str = Field(alias="createdBySubject")
    created_at: str = Field(alias="createdAt")


class RubricRevision(ProjectLearningModel):
    id: str
    rubric_id: str = Field(alias="rubricId")
    revision: int = Field(ge=1)
    dimensions: list[RubricDimension]
    supersedes_revision_id: str | None = Field(alias="supersedesRevisionId")
    created_by_subject: str = Field(alias="createdBySubject")
    created_at: str = Field(alias="createdAt")


class Assignment(ProjectLearningModel):
    id: str
    class_group_id: str = Field(alias="classGroupId")
    title: str
    driving_question: str = Field(alias="drivingQuestion")
    description: str
    collaboration_mode: AssignmentCollaborationMode = Field(
        alias="collaborationMode"
    )
    policy_revision_id: str = Field(alias="policyRevisionId")
    rubric_revision_id: str = Field(alias="rubricRevisionId")
    due_at: str | None = Field(alias="dueAt")
    created_by_subject: str = Field(alias="createdBySubject")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class WorkLearningBinding(ProjectLearningModel):
    work_id: str = Field(alias="workId")
    assignment_id: str = Field(alias="assignmentId")
    collaboration_mode: AssignmentCollaborationMode = Field(
        alias="collaborationMode"
    )
    process_milestone: ProjectProcessMilestone = Field(alias="processMilestone")
    process_state: ProjectProcessState = Field(alias="processState")
    revision: int = Field(ge=1)
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class LearningOrganizationRef(ProjectLearningModel):
    id: str
    name: str


class LearningCourseRef(ProjectLearningModel):
    id: str
    title: str


class LearningClassRef(ProjectLearningModel):
    id: str
    title: str


class LearningAssignmentRef(ProjectLearningModel):
    id: str
    title: str
    driving_question: str = Field(alias="drivingQuestion")


class WorkLearningContextSnapshot(ProjectLearningModel):
    organization: LearningOrganizationRef
    course: LearningCourseRef
    class_group: LearningClassRef = Field(alias="classGroup")
    assignment: LearningAssignmentRef
    collaboration_mode: AssignmentCollaborationMode = Field(
        alias="collaborationMode"
    )


class ProjectCheckpointSummary(ProjectLearningModel):
    kind: ProjectCheckpointKind
    label: str
    required: bool
    completed: bool


class ProjectProcessSnapshot(ProjectLearningModel):
    milestone: ProjectProcessMilestone
    state: ProjectProcessState
    current_proposal_revision_id: str | None = Field(
        alias="currentProposalRevisionId"
    )
    current_simulation_project_revision_id: str | None = Field(
        alias="currentSimulationProjectRevisionId"
    )
    current_submission_revision_id: str | None = Field(
        alias="currentSubmissionRevisionId"
    )
    build_route: BuildRoute | None = Field(alias="buildRoute")
    required_checkpoints: list[ProjectCheckpointSummary] = Field(
        alias="requiredCheckpoints"
    )
    revision: int = Field(ge=1)


class WorkLearningProjection(ProjectLearningModel):
    learning_context: WorkLearningContextSnapshot = Field(alias="learningContext")
    project_process: ProjectProcessSnapshot = Field(alias="projectProcess")


class LegacyProposalSection(ProjectLearningModel):
    id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=240)
    content: str = Field(max_length=12000)


class ProjectProposalContentV2(ProjectLearningModel):
    """A draft boundary: completeness is enforced only by student confirmation."""

    driving_question: str = Field(alias="drivingQuestion", default="", max_length=4000)
    users_and_context: str = Field(alias="usersAndContext", default="", max_length=12000)
    research_findings: list[str] = Field(alias="researchFindings", default_factory=list)
    success_criteria: list[str] = Field(alias="successCriteria", default_factory=list)
    functional_logic: str = Field(alias="functionalLogic", default="", max_length=12000)
    hardware_plan: str = Field(alias="hardwarePlan", default="", max_length=12000)
    interface_and_power_plan: str = Field(
        alias="interfaceAndPowerPlan", default="", max_length=12000
    )
    software_plan: str = Field(alias="softwarePlan", default="", max_length=12000)
    simulation_plan: str = Field(alias="simulationPlan", default="", max_length=12000)
    structure_hypothesis: str = Field(
        alias="structureHypothesis", default="", max_length=12000
    )
    materials_and_budget: str = Field(
        alias="materialsAndBudget", default="", max_length=12000
    )
    team_and_schedule: str = Field(alias="teamAndSchedule", default="", max_length=12000)
    risks_and_safety: list[str] = Field(alias="risksAndSafety", default_factory=list)
    reflection_prompts: list[str] = Field(alias="reflectionPrompts", default_factory=list)
    legacy_source_sections: list[LegacyProposalSection] = Field(
        alias="legacySourceSections", default_factory=list
    )

    @field_validator(
        "research_findings",
        "success_criteria",
        "risks_and_safety",
        "reflection_prompts",
    )
    @classmethod
    def _reject_blank_list_items(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value]
        if any(not item for item in normalized):
            raise ValueError("列表项不能为空。")
        return normalized


class ProjectProposalRevisionV2(ProjectLearningModel):
    id: str
    work_id: str = Field(alias="workId")
    assignment_policy_revision_id: str | None = Field(
        alias="assignmentPolicyRevisionId"
    )
    rubric_revision_id: str | None = Field(alias="rubricRevisionId")
    version: int = Field(ge=1)
    status: ProjectProposalStatus
    content: ProjectProposalContentV2
    source_kind: ProjectProposalSourceKind = Field(alias="sourceKind")
    source_proposal_id: str | None = Field(alias="sourceProposalId")
    supersedes_revision_id: str | None = Field(alias="supersedesRevisionId")
    student_confirmed_by: str | None = Field(alias="studentConfirmedBy")
    student_confirmed_at: str | None = Field(alias="studentConfirmedAt")
    stale_reason: str | None = Field(alias="staleReason")
    created_by: str = Field(alias="createdBy")
    created_at: str = Field(alias="createdAt")


class CheckpointReview(ProjectLearningModel):
    id: str
    work_id: str = Field(alias="workId")
    checkpoint: ProjectCheckpointKind
    target_kind: str = Field(alias="targetKind")
    target_revision_id: str = Field(alias="targetRevisionId")
    decision: CheckpointReviewDecision
    reviewer_subject: str = Field(alias="reviewerSubject")
    comment: str
    created_at: str = Field(alias="createdAt")


class ProposalFacilitatorState(ProjectLearningModel):
    identity: str = "掌问 · 问题引导师"
    complete: bool
    completed_fields: list[str] = Field(alias="completedFields")
    total_fields: int = Field(alias="totalFields", ge=1)
    next_field: str | None = Field(alias="nextField")
    next_question: str | None = Field(alias="nextQuestion")
    missing_fields: list[str] = Field(alias="missingFields")


class ClassroomProposalWorkspace(ProjectLearningModel):
    assignment: Assignment
    policy: AssignmentPolicyRevision
    process: ProjectProcessSnapshot
    current: ProjectProposalRevisionV2 | None
    revisions: list[ProjectProposalRevisionV2]
    reviews: list[CheckpointReview]
    facilitator: ProposalFacilitatorState
    can_student_confirm: bool = Field(alias="canStudentConfirm")
    can_review: bool = Field(alias="canReview")


class ProcessJournalEntry(ProjectLearningModel):
    id: str
    work_id: str = Field(alias="workId")
    actor_subject: str = Field(alias="actorSubject")
    kind: ProcessJournalEntryKind
    title: str
    body: str
    related_kind: str | None = Field(alias="relatedKind")
    related_id: str | None = Field(alias="relatedId")
    created_at: str = Field(alias="createdAt")


class BuildRouteDecision(ProjectLearningModel):
    id: str
    work_id: str = Field(alias="workId")
    version: int = Field(ge=1)
    route: BuildRoute
    rationale: str
    selected_by: str = Field(alias="selectedBy")
    policy_revision_id: str | None = Field(alias="policyRevisionId")
    supersedes_revision_id: str | None = Field(alias="supersedesRevisionId")
    created_at: str = Field(alias="createdAt")


class SubmissionRevision(ProjectLearningModel):
    id: str
    work_id: str = Field(alias="workId")
    version: int = Field(ge=1)
    status: SubmissionStatus
    proposal_revision_id: str = Field(alias="proposalRevisionId")
    simulation_run_id: str | None = Field(alias="simulationRunId")
    build_route_decision_id: str = Field(alias="buildRouteDecisionId")
    content: dict[str, object]
    submitted_by: str | None = Field(alias="submittedBy")
    submitted_at: str | None = Field(alias="submittedAt")
    supersedes_revision_id: str | None = Field(alias="supersedesRevisionId")
    created_by: str = Field(alias="createdBy")
    created_at: str = Field(alias="createdAt")


class InstructorReview(ProjectLearningModel):
    id: str
    work_id: str = Field(alias="workId")
    submission_revision_id: str = Field(alias="submissionRevisionId")
    decision: InstructorReviewDecision
    reviewer_subject: str = Field(alias="reviewerSubject")
    feedback: str
    created_at: str = Field(alias="createdAt")


class RubricAssessment(ProjectLearningModel):
    id: str
    work_id: str = Field(alias="workId")
    submission_revision_id: str = Field(alias="submissionRevisionId")
    rubric_revision_id: str = Field(alias="rubricRevisionId")
    reviewer_subject: str = Field(alias="reviewerSubject")
    scores: dict[str, float]
    total_score: float = Field(alias="totalScore", ge=0)
    status: RubricAssessmentStatus
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class LegacyLearningSources(ProjectLearningModel):
    work_id: str = Field(alias="workId")
    owner_subject: str | None = Field(alias="ownerSubject")
    account_persona: str | None = Field(alias="accountPersona")
    proposal_ids: list[str] = Field(alias="proposalIds")
    lesson_run_ids: list[str] = Field(alias="lessonRunIds")
    learning_context_bound: bool = Field(alias="learningContextBound")


class ClassroomCourseCard(ProjectLearningModel):
    organization: LearningOrganizationRef
    course: LearningCourseRef
    class_group: LearningClassRef = Field(alias="classGroup")
    role: OrganizationMembershipRole | ClassMembershipRole
    assignment_count: int = Field(alias="assignmentCount", ge=0)


class ClassroomProjectCard(ProjectLearningModel):
    work_id: str = Field(alias="workId")
    project_name: str = Field(alias="projectName")
    assignment_id: str = Field(alias="assignmentId")
    assignment_title: str = Field(alias="assignmentTitle")
    class_group_id: str = Field(alias="classGroupId")
    class_title: str = Field(alias="classTitle")
    milestone: ProjectProcessMilestone
    state: ProjectProcessState
    next_action_label: str = Field(alias="nextActionLabel")
    updated_at: str = Field(alias="updatedAt")


class ClassroomHome(ProjectLearningModel):
    course_cards: list[ClassroomCourseCard] = Field(alias="courseCards")
    project_cards: list[ClassroomProjectCard] = Field(alias="projectCards")
    teaching_classes: list[LearningClassRef] = Field(alias="teachingClasses")
    can_teach: bool = Field(alias="canTeach")


class AssignmentWorkSummary(ProjectLearningModel):
    work_id: str = Field(alias="workId")
    project_name: str = Field(alias="projectName")
    milestone: ProjectProcessMilestone
    state: ProjectProcessState
    member_count: int = Field(alias="memberCount", ge=0)
    updated_at: str = Field(alias="updatedAt")


class ClassroomAssignmentDetail(ProjectLearningModel):
    organization: Organization
    course: Course
    class_group: ClassGroup = Field(alias="classGroup")
    assignment: Assignment
    policy: AssignmentPolicyRevision
    rubric: RubricRevision
    works: list[AssignmentWorkSummary]


class ClassroomClassDetail(ProjectLearningModel):
    organization: Organization
    course: Course
    class_group: ClassGroup = Field(alias="classGroup")
    role: OrganizationMembershipRole | ClassMembershipRole
    assignments: list[Assignment]
    members: list[ClassMembership]


class ClassroomWorkOverview(ProjectLearningModel):
    project_name: str = Field(alias="projectName")
    binding: WorkLearningBinding
    projection: WorkLearningProjection
    members: list[WorkMembership]
    journal: list[ProcessJournalEntry]
