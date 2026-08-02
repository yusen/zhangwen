"""Project boundary models."""

from __future__ import annotations

from enum import IntEnum, StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

from zhangwen.llm.contracts import ChatMessage, LLMModelSelection


class ProjectPersistenceVersion(IntEnum):
    V1 = 1
    V2 = 2
    V3 = 3
    V4 = 4
    V5 = 5
    V6 = 6
    V7 = 7
    V8 = 8
    V9 = 9
    V10 = 10
    V11 = 11
    V12 = 12
    V13 = 13
    V14 = 14
    V15 = 15
    V16 = 16
    V17 = 17
    V18 = 18
    V19 = 19
    V20 = 20
    V21 = 21
    V22 = 22
    V23 = 23
    V24 = 24
    V25 = 25
    V26 = 26
    V27 = 27
    V28 = 28
    V29 = 29
    V30 = 30
    V31 = 31


class ExpertType(StrEnum):
    STRUCTURE_ENGINEER = "structure_engineer"
    PROBLEM_GUIDE = "problem_guide"
    SMART_ENGINEER = "smart_engineer"
    # Legacy v18 transition values kept so old rows can be read during migration.
    QUESTION_GUIDE = "question_guide"
    INTELLIGENT_ENGINEER = "intelligent_engineer"
    # Legacy UX-002 values kept so old rows can be read during migration.
    IDEATOR = "ideator"
    OPEN_HARDWARE_DESIGNER = "open_hardware_designer"
    STRUCTURE_DESIGNER = "structure_designer"
    THREE_D_STRUCTURE_DESIGNER = "three_d_structure_designer"
    EDUCATOR = "educator"


class ExpertWorkspaceStatus(StrEnum):
    NOT_STARTED = "not_started"
    WAITING_DEPENDENCY = "waiting_dependency"
    IN_PROGRESS = "in_progress"
    AWAITING_USER = "awaiting_user"
    COMPLETED = "completed"
    OUTDATED = "outdated"


class ProjectExpertStatus(StrEnum):
    IDLE = "idle"
    WAITING_USER = "waiting_user"
    WORKING = "working"
    BLOCKED = "blocked"
    COMPLETED = "completed"


class CoordinatorSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    BLOCKING = "blocking"


class SharedFactStatus(StrEnum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class HandoffStatus(StrEnum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class PendingItemPriority(StrEnum):
    SAFETY = "safety"
    BLOCKING = "blocking"
    CONFLICT = "conflict"
    CONFIRMATION = "confirmation"
    MISSING_INPUT = "missing_input"
    NORMAL = "normal"


class PendingItemStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class PendingItemKind(StrEnum):
    GENERAL = "general"
    LOCAL_EXECUTION_AUTHORIZATION = "local_execution_authorization"


class PendingItemActionType(StrEnum):
    RESUME_SKILL_RUN = "resume_skill_run"


class DomainTaskStatus(StrEnum):
    QUEUED = "queued"
    READY = "ready"
    RUNNING = "running"
    BLOCKED = "blocked"
    AWAITING_USER = "awaiting_user"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProjectStage(StrEnum):
    IDEA = "IDEA"
    CLARIFYING = "CLARIFYING"
    SOLUTION_DRAFT = "SOLUTION_DRAFT"
    SOLUTION_CONFIRMED = "SOLUTION_CONFIRMED"
    PROPOSAL_DRAFT = "PROPOSAL_DRAFT"
    PROPOSAL_CONFIRMED = "PROPOSAL_CONFIRMED"
    EXECUTION_PLANNED = "EXECUTION_PLANNED"
    IMPLEMENTING = "IMPLEMENTING"
    VALIDATING = "VALIDATING"
    READY_TO_UPLOAD = "READY_TO_UPLOAD"
    DEVICE_VERIFIED = "DEVICE_VERIFIED"
    READY_TO_PUBLISH = "READY_TO_PUBLISH"
    PUBLISHED = "PUBLISHED"


class ProjectProgressStatus(StrEnum):
    READY = "READY"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    BLOCKED = "BLOCKED"
    COMPLETE = "COMPLETE"


class ProjectProgressConsistency(StrEnum):
    CONSISTENT = "CONSISTENT"
    REPAIRED = "REPAIRED"
    NEEDS_ATTENTION = "NEEDS_ATTENTION"


class ProjectProfile(BaseModel):
    initialIdea: str = ""


class Project(BaseModel):
    id: str
    name: str
    stage: ProjectStage
    profile: ProjectProfile
    conversationId: str
    activeExpertIds: list[str] = Field(default_factory=list)
    activeExpertId: str | None = None
    sharedContextId: str | None = None
    coordinatorStateId: str | None = None
    selectedModel: LLMModelSelection
    archivedAt: str | None = None
    createdAt: str
    updatedAt: str
    lastOpenedAt: str | None = None
    schemaVersion: ProjectPersistenceVersion = ProjectPersistenceVersion.V31


class ProjectSummary(BaseModel):
    id: str
    name: str
    stage: ProjectStage
    activeExpertIds: list[str] = Field(default_factory=list)
    selectedModel: LLMModelSelection
    messageCount: int
    draftUpdatedAt: str | None = None
    archivedAt: str | None = None
    updatedAt: str
    lastOpenedAt: str | None = None


class Conversation(BaseModel):
    id: str
    projectId: str
    messages: list[ChatMessage]
    updatedAt: str


class Draft(BaseModel):
    projectId: str
    content: str = ""
    updatedAt: str | None = None
    projectExpertId: str | None = None


class ExpertDefinition(BaseModel):
    id: str
    type: ExpertType
    name: str
    description: str
    icon: str
    builtIn: bool
    skillIds: list[str] = Field(default_factory=list)
    supportedArtifactTypes: list[str] = Field(default_factory=list)


class ProjectExpert(BaseModel):
    id: str
    projectId: str
    expertDefinitionId: str
    expertType: ExpertType
    legacyExpertType: ExpertType | str | None = None
    archivedLegacyThread: bool = False
    conversationId: str
    privateMemoryId: str
    status: ProjectExpertStatus
    workspaceStatus: ExpertWorkspaceStatus | None = None
    currentTask: str | None = None
    addedAt: str
    removedAt: str | None = None


class SharedFact(BaseModel):
    id: str
    projectId: str | None = None
    field: str
    key: str | None = None
    value: object
    status: SharedFactStatus = SharedFactStatus.PROPOSED
    sourceType: str = "user"
    sourceId: str | None = None
    sourceExpertId: str | None = None
    proposedBy: ExpertType | str | None = None
    confirmed: bool = False
    confirmedBy: str | None = None
    confirmedAt: str | None = None
    supersededBy: str | None = None
    affectsArtifactIds: list[str] = Field(default_factory=list)
    createdAt: str | None = None
    updatedAt: str


class SharedDecision(BaseModel):
    id: str
    projectId: str | None = None
    title: str
    value: object
    status: SharedFactStatus = SharedFactStatus.PROPOSED
    reason: str = ""
    sourceExpertId: str | None = None
    proposedBy: ExpertType | str | None = None
    affectedArtifactIds: list[str] = Field(default_factory=list)
    createdAt: str | None = None
    updatedAt: str | None = None
    confirmedBy: str | None = None
    confirmedAt: str | None = None


class ProjectDecision(SharedDecision):
    projectId: str


class PendingItem(BaseModel):
    id: str
    projectId: str
    title: str
    description: str
    priority: PendingItemPriority
    reason: str
    affectedExperts: list[ExpertType] = Field(default_factory=list)
    options: list[str] = Field(default_factory=list)
    status: PendingItemStatus
    kind: PendingItemKind = PendingItemKind.GENERAL
    actionType: PendingItemActionType | None = None
    authorizationId: str | None = None
    isHighlighted: bool = False
    criticalPath: bool = False
    createdAt: str
    updatedAt: str | None = None


class ProjectTask(BaseModel):
    id: str
    projectId: str
    title: str
    description: str
    ownerExpert: ExpertType
    status: DomainTaskStatus
    dependencyTaskIds: list[str] = Field(default_factory=list)
    artifactIds: list[str] = Field(default_factory=list)
    currentPendingItemId: str | None = None
    createdAt: str
    updatedAt: str | None = None


class RouterOutput(BaseModel):
    intent: str
    projectName: str
    initialExpert: ExpertType
    recommendedExperts: list[ExpertType] = Field(default_factory=list)
    confidence: float
    reason: str
    requiresClarification: bool = False


class Handoff(BaseModel):
    id: str
    projectId: str
    fromExpert: ExpertType
    toExpert: ExpertType
    handoffType: str
    status: HandoffStatus
    summary: str | None = None
    confirmedRequirements: list[str] = Field(default_factory=list)
    sharedFactIds: list[str] = Field(default_factory=list)
    relatedArtifacts: list[str] = Field(default_factory=list)
    requiredOutputs: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    openQuestions: list[str] = Field(default_factory=list)
    currentPendingItemId: str | None = None
    createdAt: str
    updatedAt: str | None = None


class ActiveArtifactVersion(BaseModel):
    artifactId: str
    artifactVersionId: str | None = None
    artifactType: str
    version: int | None = None
    ownerExpertId: str | None = None
    status: str


class ProjectSharedContext(BaseModel):
    id: str
    projectId: str
    revision: int
    goals: list[SharedFact] = Field(default_factory=list)
    constraints: list[SharedFact] = Field(default_factory=list)
    requirements: list[SharedFact] = Field(default_factory=list)
    decisions: list[ProjectDecision] = Field(default_factory=list)
    confirmedFacts: list[SharedFact] = Field(default_factory=list)
    openQuestions: list[SharedFact] = Field(default_factory=list)
    currentPendingItem: PendingItem | None = None
    activeArtifactVersions: list[ActiveArtifactVersion] = Field(default_factory=list)
    deliveryTrack: Literal["project", "lesson"] = "project"
    updatedAt: str


class CoordinatorItem(BaseModel):
    id: str
    title: str
    description: str
    targetExpertId: str | None = None
    targetArtifactId: str | None = None
    actionLabel: str | None = None
    severity: CoordinatorSeverity


class CoordinatorIssue(BaseModel):
    id: str
    title: str
    description: str
    severity: CoordinatorSeverity
    relatedExpertIds: list[str] = Field(default_factory=list)
    relatedArtifactIds: list[str] = Field(default_factory=list)


class ProjectCoordinatorState(BaseModel):
    id: str
    projectId: str
    currentItem: CoordinatorItem | None = None
    currentPendingItem: PendingItem | None = None
    pendingItems: list[PendingItem] = Field(default_factory=list)
    expertStatuses: list[ProjectExpert] = Field(default_factory=list)
    conflicts: list[CoordinatorIssue] = Field(default_factory=list)
    dependencies: list[CoordinatorIssue] = Field(default_factory=list)
    updatedAt: str


class ExpertConversation(BaseModel):
    id: str
    projectId: str
    projectExpertId: str
    expertType: ExpertType
    legacyExpertType: ExpertType | str | None = None
    archivedLegacyThread: bool = False
    expertName: str
    messages: list[ChatMessage]
    draft: Draft
    activeQuestionId: str | None = None
    activeTurnId: str | None = None
    updatedAt: str


class ProjectKickoff(BaseModel):
    turnId: str
    responseTurnId: str
    clientTurnId: str
    userMessageId: str
    assistantMessageId: str
    projectExpertId: str
    conversationId: str
    expertType: ExpertType
    content: str
    status: Literal[
        "READY", "PENDING", "STREAMING", "COMPLETED", "FAILED", "CANCELED"
    ]
    retryable: bool = False


class ProjectWorkspace(BaseModel):
    project: Project
    conversation: Conversation
    draft: Draft
    experts: list[ProjectExpert] = Field(default_factory=list)
    expertDefinitions: list[ExpertDefinition] = Field(default_factory=list)
    expertConversations: list[ExpertConversation] = Field(default_factory=list)
    sharedContext: ProjectSharedContext | None = None
    coordinator: ProjectCoordinatorState | None = None
    kickoff: ProjectKickoff | None = None


class CreateProjectRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    initialIdea: str = Field(default="", max_length=4000)
    selectedModel: LLMModelSelection | None = None
    selectedExpertTypes: list[ExpertType] | None = None
    initialExpert: ExpertType | None = None
    routerResult: RouterOutput | None = None
    expertSelectionMode: Literal["auto", "manual"] = "auto"
    idempotencyKey: str | None = Field(default=None, max_length=120)
    selectedHardwareIds: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("selectedHardwareIds")
    @classmethod
    def _validate_selected_hardware_ids(cls, value: list[str]) -> list[str]:
        return normalize_selected_hardware_ids(value)


class SuggestProjectRequest(BaseModel):
    initialIdea: str | None = Field(default=None, max_length=4000)
    text: str | None = Field(default=None, max_length=4000)
    userSelectedExpert: ExpertType | None = None
    useModelRouting: bool = False
    selectedHardwareIds: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("selectedHardwareIds")
    @classmethod
    def _validate_selected_hardware_ids(cls, value: list[str]) -> list[str]:
        return normalize_selected_hardware_ids(value)


def normalize_selected_hardware_ids(values: list[str] | None) -> list[str]:
    normalized = list(values or [])
    if len(normalized) > 12:
        raise ValueError("最多可选择 12 个已有硬件。")
    if any(not value or value != value.strip() for value in normalized):
        raise ValueError("硬件 ID 不能为空或包含首尾空格。")
    if len(set(normalized)) != len(normalized):
        raise ValueError("硬件 ID 不能重复。")
    return normalized


class SuggestedProject(BaseModel):
    name: str
    initialIdea: str
    recommendedExpertTypes: list[ExpertType]
    availableExperts: list[ExpertDefinition]
    initialExpert: ExpertType
    routerResult: RouterOutput
    reason: str
    confidence: float
    requiresClarification: bool
    selectedHardwareWarnings: list[str] = Field(default_factory=list, max_length=12)


class SuggestProjectResponse(BaseModel):
    suggestion: SuggestedProject


class UpdateProjectRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    selectedModel: LLMModelSelection | None = None


class UpdateProjectHardwareRequest(BaseModel):
    selectedHardwareIds: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("selectedHardwareIds")
    @classmethod
    def _validate_selected_hardware_ids(cls, value: list[str]) -> list[str]:
        return normalize_selected_hardware_ids(value)


class ArchiveProjectRequest(BaseModel):
    archived: bool = True


class DuplicateProjectRequest(BaseModel):
    name: str | None = Field(default=None, max_length=120)

    @field_validator("name")
    @classmethod
    def _normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("副本名称不能为空。")
        return normalized


class PermanentDeleteProjectRequest(BaseModel):
    confirmationName: str = Field(min_length=1, max_length=120)


class PermanentDeleteProjectResponse(BaseModel):
    deletedProjectId: str
    backupId: str
    backupCreatedAt: str
    projects: list[ProjectSummary]
    activeProjectId: str | None = None


class AddProjectExpertRequest(BaseModel):
    expertType: ExpertType
    activate: bool = False


class RemoveProjectExpertRequest(BaseModel):
    confirmImpact: bool = False


class SaveDraftRequest(BaseModel):
    content: str = Field(default="", max_length=20000)
    projectExpertId: str | None = None


class ProjectListResponse(BaseModel):
    projects: list[ProjectSummary]
    activeProjectId: str | None = None


class LegacyProjectClaimStatusResponse(BaseModel):
    unclaimedProjectCount: int = Field(ge=0)
    decisionRecorded: bool


class LegacyProjectClaimRequest(BaseModel):
    claimAll: bool


class LegacyProjectClaimResponse(BaseModel):
    claimedProjectCount: int = Field(ge=0)
    decisionRecorded: bool = True


class ProjectWorkspaceResponse(BaseModel):
    workspace: ProjectWorkspace


class UpdateProjectHardwareResponse(BaseModel):
    workspace: ProjectWorkspace
    selectedHardwareWarnings: list[str] = Field(default_factory=list, max_length=12)


class ClarificationAnswerInput(BaseModel):
    questionId: str = Field(min_length=1, max_length=200)
    selectedOptionIds: list[str] = Field(default_factory=list, max_length=20)
    textInput: str | None = Field(default=None, max_length=4000)
    usedRecommendation: bool | None = None


class SingleChoiceAnswerInput(BaseModel):
    type: Literal["single_choice_answer"]
    projectId: str
    conversationId: str
    questionId: str
    optionId: str
    optionValue: str
    optionLabel: str
    clientTurnId: str


class MultipleChoiceAnswerInput(BaseModel):
    type: Literal["multiple_choice_answer"]
    projectId: str
    conversationId: str
    questionId: str
    optionIds: list[str]
    optionValues: list[str]
    optionLabels: list[str]
    clientTurnId: str


class TextQuestionAnswerInput(BaseModel):
    type: Literal["text_question_answer"]
    projectId: str
    conversationId: str
    questionId: str
    text: str
    clientTurnId: str


class ClarificationBatchAnswerInput(BaseModel):
    type: Literal["clarification_batch_answer"]
    projectId: str
    conversationId: str
    sourceMessageId: str
    clientTurnId: str
    answers: list[ClarificationAnswerInput] = Field(min_length=1, max_length=20)


StructuredQuestionAnswerInput = Annotated[
    SingleChoiceAnswerInput
    | MultipleChoiceAnswerInput
    | TextQuestionAnswerInput
    | ClarificationBatchAnswerInput,
    Field(discriminator="type"),
]


class PersistedChatRequest(BaseModel):
    content: str = Field(min_length=1, max_length=20000)
    model: LLMModelSelection | None = None
    abortPrevious: bool = False
    projectExpertId: str | None = None
    threadId: str | None = None
    expertType: ExpertType | None = None
    clientTurnId: str | None = None
    kickoffTurnId: str | None = None
    retryKickoff: bool = False
    turnContext: dict | None = None
    structuredAnswer: StructuredQuestionAnswerInput | None = None
    conversationAction: str | None = None
    sourceMessageId: str | None = None
    questionId: str | None = None
    selectedOptionIds: list[str] | None = None
    textInput: str | None = None
    automaticHandoff: bool = False
    handoffLabel: str | None = Field(default=None, max_length=120)
    recoveryOfMessageId: str | None = Field(default=None, min_length=1, max_length=160)
    recoveryLabel: str | None = Field(default=None, min_length=1, max_length=120)
