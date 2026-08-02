"""Strict Creator V3 HTTP and projection models."""

from __future__ import annotations

from enum import IntEnum, StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CreatorModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class CreatorStage(StrEnum):
    IDEA_SOLUTION = "IDEA_SOLUTION"
    DIGITAL_PROTOTYPE = "DIGITAL_PROTOTYPE"
    STRUCTURE_3D = "STRUCTURE_3D"
    PHYSICAL_RUN = "PHYSICAL_RUN"


class CreatorPhase(StrEnum):
    IDEA = "IDEA"
    GOAL_REVIEW = "GOAL_REVIEW"
    SOLUTION_REVIEW = "SOLUTION_REVIEW"
    DIGITAL_BUILDING = "DIGITAL_BUILDING"
    SIMULATING = "SIMULATING"
    SIMULATION_PASSED = "SIMULATION_PASSED"
    DEVICE_CONNECTED = "DEVICE_CONNECTED"
    DEPLOYED = "DEPLOYED"
    PHYSICAL_VALIDATING = "PHYSICAL_VALIDATING"
    PHYSICAL_PASSED = "PHYSICAL_PASSED"
    ACCEPTED = "ACCEPTED"
    DELIVERED = "DELIVERED"


class VerificationLevel(IntEnum):
    UNVERIFIED = 0
    GOAL_CONFIRMED = 1
    STATIC_VALIDATED = 2
    SIMULATION_PASSED = 3
    DEVICE_CONNECTED = 4
    PHYSICAL_PASSED = 5
    USER_ACCEPTED = 6


class CreatorJobStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


class CreatorJobKind(StrEnum):
    CODE_PREPARATION = "CODE_PREPARATION"
    DIGITAL_PROTOTYPE = "DIGITAL_PROTOTYPE"
    STRUCTURE_DRAFT = "STRUCTURE_DRAFT"


class CreatorJobCommand(StrEnum):
    CANCEL = "CANCEL"
    RETRY = "RETRY"


class EvidenceStatus(StrEnum):
    CURRENT = "CURRENT"
    STALE = "STALE"
    FAILED = "FAILED"
    SUPERSEDED = "SUPERSEDED"


class EvidenceKind(StrEnum):
    GOAL_CONFIRMATION = "GOAL_CONFIRMATION"
    STATIC_VALIDATION = "STATIC_VALIDATION"
    SIMULATION = "SIMULATION"
    DEVICE_CONNECTION = "DEVICE_CONNECTION"
    DEPLOYMENT = "DEPLOYMENT"
    PHYSICAL_BEHAVIOR = "PHYSICAL_BEHAVIOR"
    USER_ACCEPTANCE = "USER_ACCEPTANCE"
    REPRODUCTION = "REPRODUCTION"
    STRUCTURE_CHECK = "STRUCTURE_CHECK"


class CreatorCommand(StrEnum):
    SAVE_GOAL = "SAVE_GOAL"
    CONFIRM_GOAL = "CONFIRM_GOAL"
    SAVE_SOLUTION = "SAVE_SOLUTION"
    CONFIRM_SOLUTION = "CONFIRM_SOLUTION"
    GENERATE_PROJECT_BOOK = "GENERATE_PROJECT_BOOK"
    RECORD_STATIC_VALIDATION = "RECORD_STATIC_VALIDATION"
    RECORD_SIMULATION = "RECORD_SIMULATION"
    RECORD_STRUCTURE_CHECK = "RECORD_STRUCTURE_CHECK"
    RECORD_DEVICE_CONNECTION = "RECORD_DEVICE_CONNECTION"
    RECORD_DEPLOYMENT = "RECORD_DEPLOYMENT"
    RECORD_PHYSICAL_BEHAVIOR = "RECORD_PHYSICAL_BEHAVIOR"
    ACCEPT_WORK = "ACCEPT_WORK"
    RECORD_REPRODUCTION = "RECORD_REPRODUCTION"
    ARCHIVE_WORK = "ARCHIVE_WORK"


class CreatorRevisionSourceType(StrEnum):
    CONVERSATION = "CONVERSATION"
    PROFESSIONAL_EDIT = "PROFESSIONAL_EDIT"
    LEGACY_PROJECTION = "LEGACY_PROJECTION"
    SYSTEM_MIGRATION = "SYSTEM_MIGRATION"


class ConversationProjectDraftV1(CreatorModel):
    schema_version: Literal[1] = Field(default=1, alias="schemaVersion")
    use_scenario: str = Field(alias="useScenario", min_length=1, max_length=4000)
    observable_behavior: str = Field(
        alias="observableBehavior", min_length=1, max_length=4000
    )
    constraints: list[str] = Field(default_factory=list, max_length=64)
    success_criteria: list[str] = Field(
        alias="successCriteria", default_factory=list, max_length=64
    )
    missing_fields: list[str] = Field(
        alias="missingFields", default_factory=list, max_length=64
    )


class CreatorProjectionReceipt(CreatorModel):
    id: str
    work_id: str = Field(alias="workId")
    source_type: CreatorRevisionSourceType = Field(alias="sourceType")
    source_message_id: str = Field(alias="sourceMessageId")
    source_turn_id: str | None = Field(alias="sourceTurnId")
    draft_hash: str = Field(alias="draftHash")
    status: Literal["APPLIED", "DUPLICATE", "CONFLICT", "REJECTED"]
    goal_revision_id: str | None = Field(alias="goalRevisionId")
    solution_revision_id: str | None = Field(alias="solutionRevisionId")
    message: str | None
    created_at: str = Field(alias="createdAt")


class ProjectBookSection(CreatorModel):
    id: str
    title: str
    content: str


class ProjectBookProjection(CreatorModel):
    status: Literal[
        "EMPTY", "CURRENT", "STALE", "GOAL_ONLY", "SYNCHRONIZED"
    ]
    book_id: str | None = Field(default=None, alias="bookId")
    revision: int | None = None
    goal_revision_id: str | None = Field(alias="goalRevisionId")
    solution_revision_id: str | None = Field(alias="solutionRevisionId")
    sections: list[ProjectBookSection] = Field(default_factory=list)
    generated_at: str | None = Field(default=None, alias="generatedAt")
    updated_at: str | None = Field(alias="updatedAt")


class ConversationProjectionStatus(CreatorModel):
    status: Literal["IDLE", "CURRENT", "CONFLICT", "FAILED"]
    receipt_id: str | None = Field(alias="receiptId")
    source_message_id: str | None = Field(alias="sourceMessageId")
    message: str | None


class CreatorRevisionBase(CreatorModel):
    id: str
    work_id: str = Field(alias="workId")
    revision: int = Field(ge=1)
    status: Literal["DRAFT", "CONFIRMED", "SUPERSEDED"]
    source_type: CreatorRevisionSourceType = Field(
        default=CreatorRevisionSourceType.SYSTEM_MIGRATION,
        alias="sourceType",
    )
    source_message_id: str | None = Field(default=None, alias="sourceMessageId")
    source_turn_id: str | None = Field(default=None, alias="sourceTurnId")
    base_revision_id: str | None = Field(default=None, alias="baseRevisionId")
    projection_receipt_id: str | None = Field(
        default=None, alias="projectionReceiptId"
    )
    created_at: str = Field(alias="createdAt")
    confirmed_at: str | None = Field(alias="confirmedAt")


class GoalRevision(CreatorRevisionBase):
    statement: str
    observable_behavior: str = Field(alias="observableBehavior")
    constraints: list[str]
    success_criteria: list[str] = Field(alias="successCriteria")


class BomItem(CreatorModel):
    component_id: str = Field(alias="componentId")
    name: str
    quantity: int = Field(ge=1, le=999)


class IoMapItem(CreatorModel):
    signal: str
    pin: str
    purpose: str


class SolutionRevision(CreatorRevisionBase):
    summary: str
    logic: str
    hardware: str
    software: str
    structure: str
    simulation: str
    safety: str
    bom: list[BomItem]
    io_map: list[IoMapItem] = Field(alias="ioMap")


class AcceptanceScenario(CreatorModel):
    id: str
    work_id: str = Field(alias="workId")
    title: str
    required: bool
    simulation_expected: str = Field(alias="simulationExpected")
    physical_expected: str = Field(alias="physicalExpected")
    created_at: str = Field(alias="createdAt")


class CreatorJob(CreatorModel):
    id: str
    work_id: str = Field(alias="workId")
    solution_revision_id: str = Field(alias="solutionRevisionId")
    kind: CreatorJobKind
    status: CreatorJobStatus
    progress: int = Field(ge=0, le=100)
    message: str | None
    result: dict[str, Any] | None
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    started_at: str | None = Field(alias="startedAt")
    completed_at: str | None = Field(alias="completedAt")


class CodeVariantBinding(CreatorModel):
    id: str
    work_id: str = Field(alias="workId")
    solution_revision_id: str = Field(alias="solutionRevisionId")
    deployment_channel: Literal["USB_SERIAL", "ESP_CLAW"] = Field(
        alias="deploymentChannel"
    )
    runtime: Literal["MICROPYTHON", "ESP_CLAW_LUA"]
    code_run_id: str | None = Field(alias="codeRunId")
    device_package_id: str | None = Field(alias="devicePackageId")
    validation_status: Literal[
        "PENDING", "READY_FOR_REVIEW", "FAILED", "ACCEPTED"
    ] = Field(alias="validationStatus")
    failure_code: str | None = Field(alias="failureCode")
    failure_message: str | None = Field(alias="failureMessage")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class CreatorJobCommandRequest(CreatorModel):
    idempotency_key: str = Field(
        alias="idempotencyKey",
        min_length=8,
        max_length=160,
    )


class ParameterRevision(CreatorModel):
    id: str
    work_id: str = Field(alias="workId")
    board_id: str = Field(alias="boardId")
    profile_revision: str = Field(alias="profileRevision")
    revision: int = Field(ge=1)
    label: str
    values: dict[str, float | bool | str]
    created_at: str = Field(alias="createdAt")


class EvidenceRecord(CreatorModel):
    id: str
    work_id: str = Field(alias="workId")
    kind: EvidenceKind
    status: EvidenceStatus
    passed: bool
    summary: str
    bindings: dict[str, str]
    source_id: str | None = Field(alias="sourceId")
    recorded_at: str = Field(alias="recordedAt")
    invalidated_at: str | None = Field(alias="invalidatedAt")
    invalidation_reason: str | None = Field(alias="invalidationReason")


class CreatorStageSummary(CreatorModel):
    stage: CreatorStage
    label: str
    status: Literal[
        "NOT_STARTED", "ACTIVE", "READY", "PASSED", "BLOCKED", "NOT_APPLICABLE"
    ]
    detail: str


class CreatorNextAction(CreatorModel):
    id: str
    label: str
    command: CreatorCommand | None
    stage: CreatorStage
    enabled: bool
    blocked_reason: str | None = Field(alias="blockedReason")
    risk_level: Literal["LOW", "MEDIUM", "HIGH"] = Field(alias="riskLevel")


class CreatorWorkSummary(CreatorModel):
    id: str
    name: str
    initial_idea: str = Field(alias="initialIdea")
    phase: CreatorPhase
    stage: CreatorStage
    verification_level: VerificationLevel = Field(alias="verificationLevel")
    verification_label: str = Field(alias="verificationLabel")
    next_action_label: str = Field(alias="nextActionLabel")
    archived_at: str | None = Field(alias="archivedAt")
    updated_at: str = Field(alias="updatedAt")
    legacy: bool


class CreatorWorkspace(CreatorModel):
    schema_version: Literal[1] = Field(default=1, alias="schemaVersion")
    work_id: str = Field(alias="workId")
    project_id: str = Field(alias="projectId")
    project_version: int = Field(alias="projectVersion", ge=0)
    name: str
    initial_idea: str = Field(alias="initialIdea")
    phase: CreatorPhase
    active_stage: CreatorStage = Field(alias="activeStage")
    verification_level: VerificationLevel = Field(alias="verificationLevel")
    verification_label: str = Field(alias="verificationLabel")
    stages: list[CreatorStageSummary]
    confirmed_goal: GoalRevision | None = Field(default=None, alias="confirmedGoal")
    draft_goal: GoalRevision | None = Field(default=None, alias="draftGoal")
    confirmed_solution: SolutionRevision | None = Field(
        default=None, alias="confirmedSolution"
    )
    draft_solution: SolutionRevision | None = Field(
        default=None, alias="draftSolution"
    )
    project_book_projection: ProjectBookProjection = Field(
        alias="projectBookProjection"
    )
    conversation_projection_status: ConversationProjectionStatus = Field(
        alias="conversationProjectionStatus"
    )
    current_goal: GoalRevision | None = Field(alias="currentGoal")
    current_solution: SolutionRevision | None = Field(alias="currentSolution")
    acceptance_scenarios: list[AcceptanceScenario] = Field(alias="acceptanceScenarios")
    jobs: list[CreatorJob]
    code_variants: list[CodeVariantBinding] = Field(alias="codeVariants")
    parameter_revisions: list[ParameterRevision] = Field(alias="parameterRevisions")
    evidence: list[EvidenceRecord]
    next_action: CreatorNextAction = Field(alias="nextAction")
    archived_at: str | None = Field(alias="archivedAt")
    updated_at: str = Field(alias="updatedAt")
    legacy: bool
    needs_organization: bool = Field(alias="needsOrganization")


class CreateCreatorWorkRequest(CreatorModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    initial_idea: str = Field(alias="initialIdea", min_length=1, max_length=4000)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=8, max_length=160)
    selected_hardware_ids: list[str] = Field(
        default_factory=list, alias="selectedHardwareIds", max_length=64
    )


class CreatorCommandRequest(CreatorModel):
    base_project_version: int = Field(alias="baseProjectVersion", ge=0)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=8, max_length=160)
    payload: dict[str, Any]

    @field_validator("payload")
    @classmethod
    def validate_payload_size(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > 100:
            raise ValueError("命令参数过多。")
        return value


class EmptyCommandPayload(CreatorModel):
    pass


class GoalCommandPayload(CreatorModel):
    statement: str = Field(min_length=1, max_length=4000)
    observable_behavior: str = Field(
        alias="observableBehavior", min_length=1, max_length=4000
    )
    constraints: list[str] = Field(default_factory=list, max_length=64)
    success_criteria: list[str] = Field(
        alias="successCriteria", min_length=1, max_length=64
    )
    source_message_id: str | None = Field(default=None, alias="sourceMessageId")


class AcceptanceScenarioInput(CreatorModel):
    title: str = Field(min_length=1, max_length=300)
    required: bool = True
    simulation_expected: str = Field(
        alias="simulationExpected", min_length=1, max_length=2000
    )
    physical_expected: str = Field(
        alias="physicalExpected", min_length=1, max_length=2000
    )


class SolutionCommandPayload(CreatorModel):
    summary: str = Field(min_length=1, max_length=4000)
    logic: str = Field(min_length=1, max_length=12000)
    hardware: str = Field(min_length=1, max_length=12000)
    software: str = Field(min_length=1, max_length=12000)
    structure: str = Field(default="不需要结构", max_length=12000)
    simulation: str = Field(min_length=1, max_length=12000)
    safety: str = Field(min_length=1, max_length=12000)
    bom: list[BomItem] = Field(default_factory=list, max_length=256)
    io_map: list[IoMapItem] = Field(default_factory=list, alias="ioMap", max_length=256)
    acceptance_scenarios: list[AcceptanceScenarioInput] = Field(
        default_factory=list, alias="acceptanceScenarios", max_length=64
    )
    source_proposal_id: str | None = Field(default=None, alias="sourceProposalId")


class EvidenceCommandPayload(CreatorModel):
    passed: bool
    summary: str = Field(min_length=1, max_length=4000)
    source_id: str | None = Field(default=None, alias="sourceId")
    bindings: dict[str, str] = Field(default_factory=dict, max_length=32)


class PhysicalScenarioResult(CreatorModel):
    scenario_id: str = Field(alias="scenarioId", min_length=1, max_length=128)
    observed: bool
    note: str = Field(default="", max_length=2000)


class CreatePhysicalRunRequest(CreatorModel):
    idempotency_key: str = Field(
        alias="idempotencyKey", min_length=8, max_length=160,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    deployment_operation_id: str = Field(
        alias="deploymentOperationId", min_length=1, max_length=128
    )
    target_id: str = Field(alias="targetId", min_length=1, max_length=128)
    operator: str = Field(default="已认证用户", min_length=1, max_length=200)
    emergency_stop_verified: bool = Field(alias="emergencyStopVerified")
    scenario_results: list[PhysicalScenarioResult] = Field(
        alias="scenarioResults", min_length=1, max_length=64
    )


class PhysicalRunReport(CreatorModel):
    id: str
    work_id: str = Field(alias="workId")
    solution_revision_id: str = Field(alias="solutionRevisionId")
    deployment_operation_id: str = Field(alias="deploymentOperationId")
    target_id: str = Field(alias="targetId")
    operator: str
    passed: bool
    emergency_stop_verified: bool = Field(alias="emergencyStopVerified")
    scenario_results: list[PhysicalScenarioResult] = Field(alias="scenarioResults")
    created_at: str = Field(alias="createdAt")


class PhysicalRunResponse(CreatorModel):
    run: PhysicalRunReport


class CreatorDeliveryVariant(StrEnum):
    SHARE = "SHARE"
    REPRODUCIBLE = "REPRODUCIBLE"
    TEMPLATE = "TEMPLATE"


class CreatorDeliveryFile(CreatorModel):
    path: str
    byte_size: int = Field(alias="byteSize", ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CreatorDeliveryManifestV1(CreatorModel):
    schema_version: Literal[1] = Field(default=1, alias="schemaVersion")
    delivery_id: str = Field(alias="deliveryId")
    variant: CreatorDeliveryVariant
    source_work_id: str = Field(alias="sourceWorkId")
    source_project_version: int = Field(alias="sourceProjectVersion", ge=0)
    created_at: str = Field(alias="createdAt")
    goal_revision_id: str = Field(alias="goalRevisionId")
    solution_revision_id: str = Field(alias="solutionRevisionId")
    device_packages: list[dict[str, str]] = Field(alias="devicePackages")
    version_bindings: dict[str, str] = Field(alias="versionBindings")
    evidence_kinds: list[EvidenceKind] = Field(alias="evidenceKinds")
    maturity: dict[str, Literal["MVP", "CONTROLLED_BETA", "TECH_PREVIEW"]]
    files: list[CreatorDeliveryFile]
    privacy_ok: bool = Field(alias="privacyOk")


class CreateCreatorDeliveryRequest(CreatorModel):
    idempotency_key: str = Field(
        alias="idempotencyKey", min_length=8, max_length=160,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    variant: CreatorDeliveryVariant
    title: str | None = Field(default=None, max_length=120)


class CreatorDeliveryRecord(CreatorModel):
    id: str
    work_id: str = Field(alias="workId")
    variant: CreatorDeliveryVariant
    status: Literal["EXPORTED", "IMPORTED"]
    title: str
    file_name: str = Field(alias="fileName")
    package_sha256: str = Field(alias="packageSha256", pattern=r"^[0-9a-f]{64}$")
    manifest: CreatorDeliveryManifestV1
    privacy_report: dict[str, Any] = Field(alias="privacyReport")
    zip_base64: str | None = Field(default=None, alias="zipBase64")
    created_at: str = Field(alias="createdAt")


class CreatorDeliveryResponse(CreatorModel):
    delivery: CreatorDeliveryRecord


class ImportCreatorDeliveryRequest(CreatorModel):
    idempotency_key: str = Field(
        alias="idempotencyKey", min_length=8, max_length=160,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    zip_base64: str = Field(alias="zipBase64", min_length=1)
    importer: str = Field(default="已认证用户", min_length=1, max_length=200)


class ImportCreatorDeliveryResponse(CreatorModel):
    import_id: str = Field(alias="importId")
    source_delivery_id: str = Field(alias="sourceDeliveryId")
    package_sha256: str = Field(alias="packageSha256", pattern=r"^[0-9a-f]{64}$")
    workspace: CreatorWorkspace


class CreatorImportContext(CreatorModel):
    import_id: str = Field(alias="importId")
    source_work_id: str = Field(alias="sourceWorkId")
    source_delivery_id: str = Field(alias="sourceDeliveryId")
    importer: str
    package_sha256: str = Field(alias="packageSha256")


class CreatorImportContextResponse(CreatorModel):
    context: CreatorImportContext | None


class CompleteImportedReproductionRequest(CreatorModel):
    operator: str = Field(default="已认证用户", min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=4000)


class CompleteReproductionRequest(CreatorModel):
    import_id: str = Field(alias="importId", min_length=1, max_length=128)
    reproduced_work_id: str = Field(alias="reproducedWorkId", min_length=1, max_length=128)
    operator: str = Field(default="已认证用户", min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=4000)


class ReproductionReport(CreatorModel):
    id: str
    source_work_id: str = Field(alias="sourceWorkId")
    delivery_id: str = Field(alias="deliveryId")
    import_id: str = Field(alias="importId")
    reproduced_work_id: str = Field(alias="reproducedWorkId")
    operator: str
    package_sha256: str = Field(alias="packageSha256")
    passed: bool
    created_at: str = Field(alias="createdAt")


class ReproductionResponse(CreatorModel):
    report: ReproductionReport
    workspace: CreatorWorkspace


class AcceptanceCommandPayload(CreatorModel):
    accepted: Literal[True]
    summary: str = Field(min_length=1, max_length=4000)
    actor: str = Field(default="已认证用户", min_length=1, max_length=200)


class ArchiveWorkPayload(CreatorModel):
    archived: bool


class CreatorWorkListResponse(CreatorModel):
    works: list[CreatorWorkSummary]
    active_work_id: str | None = Field(alias="activeWorkId")


class CreatorWorkspaceResponse(CreatorModel):
    workspace: CreatorWorkspace


class CreatorJobResponse(CreatorModel):
    job: CreatorJob


class CreatorJobCommandResponse(CreatorModel):
    command: CreatorJobCommand
    repeated: bool
    job: CreatorJob
    workspace: CreatorWorkspace


class CreatorCommandResponse(CreatorModel):
    command_id: str = Field(alias="commandId")
    command: CreatorCommand
    repeated: bool
    workspace: CreatorWorkspace


class DevicePackageRevision(CreatorModel):
    id: str
    version: str
    display_name: str = Field(alias="displayName")
    board_profile_id: str = Field(alias="boardProfileId")
    capabilities: list[str]
    deployment_channels: list[str] = Field(alias="deploymentChannels")
    interactive_console_channels: list[str] = Field(
        alias="interactiveConsoleChannels"
    )
    simulation_modes: list[str] = Field(alias="simulationModes")
    source: str


class DevicePackageListResponse(CreatorModel):
    packages: list[DevicePackageRevision]
