"""Strict unified Work contracts for the local API boundary."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from zhangwen.domains.classroom.models import (
    ProjectProcessSnapshot,
    WorkLearningContextSnapshot,
)
from zhangwen.domains.orchestration.models import ExecutionRevisionSet


class WorkModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class WorkDisplayMode(StrEnum):
    CREATION = "CREATION"
    PROFESSIONAL = "PROFESSIONAL"
    DEVELOPER = "DEVELOPER"


class WorkJourneyMilestone(StrEnum):
    CLARIFY = "CLARIFY"
    TRY = "TRY"
    MAKE = "MAKE"
    COMPLETE = "COMPLETE"


class WorkState(StrEnum):
    IDEA_CAPTURE = "IDEA_CAPTURE"
    DISCOVERY_IN_PROGRESS = "DISCOVERY_IN_PROGRESS"
    PLAN_READY = "PLAN_READY"
    PLAN_CONFIRMED = "PLAN_CONFIRMED"
    PROTOTYPE_PREPARING = "PROTOTYPE_PREPARING"
    PROTOTYPE_READY = "PROTOTYPE_READY"
    PROTOTYPE_TESTING = "PROTOTYPE_TESTING"
    PROTOTYPE_VALIDATED = "PROTOTYPE_VALIDATED"
    MATERIALS_PREPARING = "MATERIALS_PREPARING"
    DEVICE_CONNECTING = "DEVICE_CONNECTING"
    STRUCTURE_PREPARING = "STRUCTURE_PREPARING"
    DEPLOYMENT_READY = "DEPLOYMENT_READY"
    DEPLOYING = "DEPLOYING"
    PHYSICAL_TESTING = "PHYSICAL_TESTING"
    USER_ACCEPTANCE = "USER_ACCEPTANCE"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    ARCHIVED = "ARCHIVED"


class WorkTaskStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


class WorkTaskKind(StrEnum):
    CODE_PREPARATION = "CODE_PREPARATION"
    DIGITAL_PROTOTYPE = "DIGITAL_PROTOTYPE"
    STRUCTURE_DRAFT = "STRUCTURE_DRAFT"


class WorkTrustStatus(StrEnum):
    NOT_VERIFIED = "NOT_VERIFIED"
    CHECKING = "CHECKING"
    VERIFIED = "VERIFIED"
    NEEDS_ATTENTION = "NEEDS_ATTENTION"
    ACCEPTED = "ACCEPTED"


class WorkRunStatus(StrEnum):
    READY = "READY"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    STALE = "STALE"


class WorkRunScenarioStatus(StrEnum):
    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"


class WorkIntentSource(StrEnum):
    FREEFORM = "FREEFORM"
    TEMPLATE_SEED = "TEMPLATE_SEED"
    IMPORT = "IMPORT"


class CanvasNodeKind(StrEnum):
    WORK = "WORK"
    INPUT = "INPUT"
    BEHAVIOR = "BEHAVIOR"
    OUTPUT = "OUTPUT"
    PHYSICAL_ACTION = "PHYSICAL_ACTION"
    SERVICE = "SERVICE"
    STRUCTURE = "STRUCTURE"
    DEVICE = "DEVICE"
    POWER = "POWER"


class CanvasTrustState(StrEnum):
    CONFIRMED = "CONFIRMED"
    VERIFIED = "VERIFIED"
    DEFAULTED = "DEFAULTED"
    CANDIDATE = "CANDIDATE"
    NEEDS_CONFIRMATION = "NEEDS_CONFIRMATION"
    UNSUPPORTED = "UNSUPPORTED"


class CanvasEdgeActiveState(StrEnum):
    ACTIVE = "ACTIVE"
    PROPOSED = "PROPOSED"
    BLOCKED = "BLOCKED"


class CanvasGenerationStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


class CanvasGenerationStep(StrEnum):
    UNDERSTAND_INTENT = "UNDERSTAND_INTENT"
    EXTRACT_CAPABILITIES = "EXTRACT_CAPABILITIES"
    MATCH_PACKAGES = "MATCH_PACKAGES"
    VALIDATE_LOCALLY = "VALIDATE_LOCALLY"
    BUILD_CANVAS = "BUILD_CANVAS"


class WorkSceneKind(StrEnum):
    PLANT = "PLANT"
    DESK = "DESK"
    ROOM = "ROOM"
    DEVICE = "DEVICE"
    DISPLAY = "DISPLAY"
    MOTION = "MOTION"
    GENERIC = "GENERIC"


class WorkSceneStateKind(StrEnum):
    IDLE = "IDLE"
    TRIGGERED = "TRIGGERED"
    DECIDING = "DECIDING"
    ACTING = "ACTING"
    RESULT = "RESULT"
    FAULT = "FAULT"


class WorkIdentity(WorkModel):
    id: str
    name: str
    initial_idea: str = Field(alias="initialIdea")
    archived_at: str | None = Field(alias="archivedAt")
    updated_at: str = Field(alias="updatedAt")


class WorkNextAction(WorkModel):
    id: str
    label: str
    action_name: str = Field(alias="actionName")
    enabled: bool
    blocked_reason: str | None = Field(alias="blockedReason")
    risk_level: Literal["LOW", "MEDIUM", "HIGH"] = Field(alias="riskLevel")


class WorkPlanSummary(WorkModel):
    solution_revision_id: str = Field(alias="solutionRevisionId")
    source_proposal_id: str | None = Field(alias="sourceProposalId")
    title: str
    summary: str
    logic: str
    hardware: str
    software: str
    structure: str | None
    simulation: str
    safety: str


class WorkPreviewSummary(WorkModel):
    kind: Literal["PLAN", "DIGITAL", "PHYSICAL", "DELIVERY"]
    title: str
    summary: str


class WorkTaskSummary(WorkModel):
    id: str
    kind: WorkTaskKind
    label: str
    status: WorkTaskStatus
    message: str | None


class WorkDeviceSummary(WorkModel):
    id: str
    name: str
    natural_status: str = Field(alias="naturalStatus")
    attention_required: bool = Field(alias="attentionRequired")


class WorkServiceSummary(WorkModel):
    id: str
    name: str
    natural_status: str = Field(alias="naturalStatus")
    attention_required: bool = Field(alias="attentionRequired")


class WorkEvidenceSummary(WorkModel):
    status: WorkTrustStatus
    label: str
    attention_required: bool = Field(alias="attentionRequired")


class WorkIntent(WorkModel):
    id: str
    work_id: str = Field(alias="workId")
    revision: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=4000)
    users: list[str] = Field(max_length=32)
    environments: list[str] = Field(max_length=32)
    inputs: list[str] = Field(max_length=64)
    behaviors: list[str] = Field(max_length=64)
    outputs: list[str] = Field(max_length=64)
    physical_actions: list[str] = Field(alias="physicalActions", max_length=64)
    service_needs: list[str] = Field(alias="serviceNeeds", max_length=32)
    structure_needs: list[str] = Field(alias="structureNeeds", max_length=32)
    constraints: list[str] = Field(max_length=64)
    unknowns: list[str] = Field(max_length=32)
    critical_question: str | None = Field(
        default=None, alias="criticalQuestion", max_length=500
    )
    confidence: float = Field(ge=0, le=1)
    source: WorkIntentSource
    created_at: str = Field(alias="createdAt")


class CanvasNode(WorkModel):
    id: str = Field(min_length=1, max_length=240)
    kind: CanvasNodeKind
    title: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=1000)
    capability: str = Field(min_length=1, max_length=240)
    trust_state: CanvasTrustState = Field(alias="trustState")
    package_candidate_ids: list[str] = Field(
        alias="packageCandidateIds", max_length=32
    )
    evidence_refs: list[str] = Field(alias="evidenceRefs", max_length=64)
    stage_affinity: WorkJourneyMilestone = Field(alias="stageAffinity")
    optional: bool


class CanvasEdge(WorkModel):
    id: str = Field(min_length=1, max_length=300)
    source_node_id: str = Field(alias="sourceNodeId")
    target_node_id: str = Field(alias="targetNodeId")
    relation: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=160)
    active_state: CanvasEdgeActiveState = Field(alias="activeState")


class WorkSceneEnvironment(WorkModel):
    kind: Literal["INDOOR", "OUTDOOR", "DESKTOP", "HOME", "GENERIC"]
    label: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=500)


class WorkSceneSubject(WorkModel):
    kind: Literal[
        "PLANTER", "REMINDER", "LIGHT", "DISPLAY", "MACHINE", "SOFTWARE", "GENERIC"
    ]
    label: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=500)


class WorkSceneActor(WorkModel):
    id: str = Field(min_length=1, max_length=160)
    kind: Literal["PERSON", "PLANT", "PET", "ENVIRONMENT", "DEVICE"]
    label: str = Field(min_length=1, max_length=120)
    role: str = Field(min_length=1, max_length=240)


class WorkSceneVisualPart(WorkModel):
    id: str = Field(min_length=1, max_length=160)
    role: Literal[
        "SUBJECT", "INPUT", "DECISION", "ACTION", "RESULT", "POWER", "STRUCTURE", "SERVICE"
    ]
    label: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=500)
    node_ids: list[str] = Field(alias="nodeIds", min_length=1, max_length=32)
    optional: bool


class WorkSceneState(WorkModel):
    id: str = Field(min_length=1, max_length=160)
    kind: WorkSceneStateKind
    label: str = Field(min_length=1, max_length=120)
    narrative: str = Field(min_length=1, max_length=500)
    active_part_ids: list[str] = Field(alias="activePartIds", max_length=32)


class WorkSceneTransition(WorkModel):
    id: str = Field(min_length=1, max_length=200)
    from_state_id: str = Field(alias="fromStateId")
    to_state_id: str = Field(alias="toStateId")
    label: str = Field(min_length=1, max_length=160)
    edge_ids: list[str] = Field(alias="edgeIds", min_length=1, max_length=64)


class WorkSceneCamera(WorkModel):
    composition: Literal["CENTERED", "LEFT_CONTEXT", "RIGHT_CONTEXT", "WIDE_CONTEXT"]
    aspect_ratio: Literal["4:3", "16:9"] = Field(alias="aspectRatio")
    focus_part_id: str = Field(alias="focusPartId")


class WorkSceneGeneration(WorkModel):
    source: Literal["PROJECT_LLM", "LOCAL_COMPATIBILITY"]
    provider_configuration_revision_id: str | None = Field(
        default=None,
        alias="providerConfigurationRevisionId",
        max_length=200,
    )
    routing_profile_revision_id: str | None = Field(
        default=None,
        alias="routingProfileRevisionId",
        max_length=200,
    )
    model: str | None = Field(default=None, min_length=1, max_length=128)


class WorkSceneSpec(WorkModel):
    schema_version: Literal[1] = Field(default=1, alias="schemaVersion")
    kind: WorkSceneKind
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=1000)
    environment: WorkSceneEnvironment
    subject: WorkSceneSubject
    actors: list[WorkSceneActor] = Field(max_length=16)
    visual_parts: list[WorkSceneVisualPart] = Field(
        alias="visualParts", min_length=1, max_length=64
    )
    states: list[WorkSceneState] = Field(min_length=6, max_length=12)
    transitions: list[WorkSceneTransition] = Field(max_length=32)
    camera: WorkSceneCamera
    accessibility_narrative: str = Field(
        alias="accessibilityNarrative", min_length=1, max_length=1500
    )
    generation: WorkSceneGeneration | None = None
    source_canvas_id: str = Field(alias="sourceCanvasId")
    source_canvas_revision: int = Field(alias="sourceCanvasRevision", ge=1)


class CanvasSpec(WorkModel):
    id: str
    work_id: str = Field(alias="workId")
    revision: int = Field(ge=1)
    work_intent: WorkIntent = Field(alias="workIntent")
    nodes: list[CanvasNode] = Field(min_length=1, max_length=128)
    edges: list[CanvasEdge] = Field(max_length=256)
    scene: WorkSceneSpec | None = None
    natural_status: str = Field(alias="naturalStatus", min_length=1, max_length=500)
    created_at: str = Field(alias="createdAt")

    @model_validator(mode="after")
    def validate_scene_references(self) -> "CanvasSpec":
        scene = self.scene
        if scene is None:
            return self
        if (
            scene.source_canvas_id != self.id
            or scene.source_canvas_revision != self.revision
        ):
            raise ValueError("scene source must match canvas id and revision")
        node_ids = {node.id for node in self.nodes}
        for part in scene.visual_parts:
            if any(node_id not in node_ids for node_id in part.node_ids):
                raise ValueError("scene visual part references unknown canvas node")
        part_ids = {part.id for part in scene.visual_parts}
        state_ids = {state.id for state in scene.states}
        edge_ids = {edge.id for edge in self.edges}
        if scene.camera.focus_part_id not in part_ids:
            raise ValueError("scene camera references unknown visual part")
        for state in scene.states:
            if any(part_id not in part_ids for part_id in state.active_part_ids):
                raise ValueError("scene state references unknown visual part")
        for transition in scene.transitions:
            if transition.from_state_id not in state_ids or transition.to_state_id not in state_ids:
                raise ValueError("scene transition references unknown state")
            if any(edge_id not in edge_ids for edge_id in transition.edge_ids):
                raise ValueError("scene transition references unknown canvas edge")
        return self


class CanvasNodePosition(WorkModel):
    node_id: str = Field(alias="nodeId")
    x: float = Field(ge=-100_000, le=100_000)
    y: float = Field(ge=-100_000, le=100_000)
    user_positioned: bool = Field(alias="userPositioned")


class CanvasViewport(WorkModel):
    x: float = Field(ge=-100_000, le=100_000)
    y: float = Field(ge=-100_000, le=100_000)
    zoom: float = Field(ge=0.25, le=3)


class CanvasLayout(WorkModel):
    id: str
    work_id: str = Field(alias="workId")
    canvas_spec_id: str = Field(alias="canvasSpecId")
    revision: int = Field(ge=1)
    algorithm_version: str = Field(alias="algorithmVersion", min_length=1, max_length=80)
    positions: list[CanvasNodePosition] = Field(min_length=1, max_length=128)
    viewport: CanvasViewport
    collapsed_node_ids: list[str] = Field(alias="collapsedNodeIds", max_length=128)
    updated_at: str = Field(alias="updatedAt")


class CanvasGeneration(WorkModel):
    id: str
    work_id: str = Field(alias="workId")
    status: CanvasGenerationStatus
    current_step: CanvasGenerationStep | None = Field(alias="currentStep")
    completed_steps: list[CanvasGenerationStep] = Field(
        alias="completedSteps", max_length=5
    )
    progress: int = Field(ge=0, le=100)
    natural_status: str = Field(alias="naturalStatus", min_length=1, max_length=500)
    error_code: str | None = Field(default=None, alias="errorCode", max_length=120)
    retryable: bool
    canvas_spec_id: str | None = Field(default=None, alias="canvasSpecId")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    completed_at: str | None = Field(alias="completedAt")


class WorkBuildRecoveryAction(WorkModel):
    id: str
    label: str
    action_name: str = Field(alias="actionName")


class WorkBuildStep(WorkModel):
    id: str
    kind: Literal[
        "MATERIALS",
        "STRUCTURE",
        "DEVICE",
        "COMMUNICATION",
        "DEPLOYMENT",
        "OBSERVATION",
        "ACCEPTANCE",
    ]
    title: str
    description: str
    status: Literal[
        "BLOCKED", "READY", "ACTIVE", "WAITING_USER", "COMPLETED", "SKIPPED"
    ]
    natural_status: str = Field(alias="naturalStatus")
    required: bool
    attention_required: bool = Field(alias="attentionRequired")


class WorkBuildJourney(WorkModel):
    status: Literal[
        "NOT_READY", "IN_PROGRESS", "WAITING_USER", "BLOCKED", "COMPLETED"
    ]
    natural_status: str = Field(alias="naturalStatus")
    current_step_id: str | None = Field(alias="currentStepId")
    steps: list[WorkBuildStep]
    recovery_action: WorkBuildRecoveryAction | None = Field(alias="recoveryAction")
    requires_human_acceptance: Literal[True] = Field(
        default=True, alias="requiresHumanAcceptance"
    )


class WorkAcceptanceScenario(WorkModel):
    id: str
    title: str
    expected_behavior: str = Field(alias="expectedBehavior")
    required: bool


class AcceptWorkRequest(WorkModel):
    idempotency_key: str = Field(
        alias="idempotencyKey",
        min_length=8,
        max_length=160,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    actor: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=4000)


class RecordWorkDeviceConnectionRequest(WorkModel):
    idempotency_key: str = Field(
        alias="idempotencyKey",
        min_length=8,
        max_length=160,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    source_id: str = Field(alias="sourceId", min_length=1, max_length=160)
    channel: Literal["USB_SERIAL", "ESP_CLAW"]


class RecordWorkDeploymentRequest(WorkModel):
    idempotency_key: str = Field(
        alias="idempotencyKey",
        min_length=8,
        max_length=160,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    operation_id: str = Field(alias="operationId", min_length=1, max_length=160)
    code_run_id: str | None = Field(default=None, alias="codeRunId", max_length=160)


class ObserveWorkScenarioResult(WorkModel):
    scenario_id: str = Field(alias="scenarioId", min_length=1, max_length=160)
    observed: bool
    note: str = Field(default="", max_length=2000)


class ObserveWorkRequest(WorkModel):
    idempotency_key: str = Field(
        alias="idempotencyKey",
        min_length=8,
        max_length=160,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    deployment_operation_id: str = Field(
        alias="deploymentOperationId", min_length=1, max_length=160
    )
    target_id: str = Field(alias="targetId", min_length=1, max_length=160)
    operator: str = Field(min_length=1, max_length=200)
    emergency_stop_verified: bool = Field(alias="emergencyStopVerified")
    scenario_results: list[ObserveWorkScenarioResult] = Field(
        alias="scenarioResults", min_length=1, max_length=64
    )


class WorkDeliveryCard(WorkModel):
    title: str
    introduction: str
    story: str
    included: list[str]
    reproduction_guide: list[str] = Field(alias="reproductionGuide")


class WorkDeliveryOption(WorkModel):
    kind: Literal["SHARE", "REPRODUCIBLE", "TEMPLATE"]
    label: str
    description: str
    available: bool
    unavailable_reason: str | None = Field(alias="unavailableReason")


class WorkDeliveryTechnicalDetails(WorkModel):
    package_sha256: str = Field(alias="packageSha256", pattern=r"^[0-9a-f]{64}$")
    source_project_version: int = Field(alias="sourceProjectVersion", ge=0)
    goal_revision_id: str = Field(alias="goalRevisionId")
    solution_revision_id: str = Field(alias="solutionRevisionId")
    file_count: int = Field(alias="fileCount", ge=0)
    file_hashes: dict[str, str] = Field(alias="fileHashes")
    version_bindings: dict[str, str] = Field(alias="versionBindings")
    privacy_ok: bool = Field(alias="privacyOk")
    manifest: dict[str, Any]


class WorkDeliveryRecord(WorkModel):
    id: str
    kind: Literal["SHARE", "REPRODUCIBLE", "TEMPLATE"]
    label: str
    title: str
    file_name: str = Field(alias="fileName")
    byte_size: int = Field(alias="byteSize", ge=0)
    created_at: str = Field(alias="createdAt")
    technical: WorkDeliveryTechnicalDetails


class WorkImportedCopy(WorkModel):
    import_id: str = Field(alias="importId")
    source_work_id: str = Field(alias="sourceWorkId")
    source_delivery_id: str = Field(alias="sourceDeliveryId")
    natural_status: str = Field(alias="naturalStatus")
    physical_verification_reset: Literal[True] = Field(
        default=True, alias="physicalVerificationReset"
    )


class WorkReproductionSummary(WorkModel):
    passed: bool
    natural_status: str = Field(alias="naturalStatus")
    completed_at: str | None = Field(alias="completedAt")
    independent_tester_required: Literal[True] = Field(
        default=True, alias="independentTesterRequired"
    )


class WorkMigrationPreservationItem(WorkModel):
    category: Literal[
        "WORK",
        "PROPOSALS",
        "CONVERSATION",
        "CODE",
        "WOKWI",
        "DEVICE_LAB",
        "LESSONS",
        "RESULTS",
        "DEVICES",
        "DELIVERIES",
    ]
    label: str
    count: int = Field(ge=0)
    preserved: Literal[True] = True
    mapping_status: Literal["PRESERVED_IN_PLACE"] = Field(
        default="PRESERVED_IN_PLACE", alias="mappingStatus"
    )
    source_tables: list[str] = Field(alias="sourceTables", min_length=1)
    content_sha256: str = Field(alias="contentSha256", pattern=r"^[a-f0-9]{64}$")


class WorkMigrationReport(WorkModel):
    schema_version: Literal["zhangwen.work-migration-report/v2"] = Field(
        default="zhangwen.work-migration-report/v2", alias="schemaVersion"
    )
    work_id: str = Field(alias="workId")
    source: Literal["LEGACY_PROJECT", "CREATOR_WORK", "IMPORTED_PACKAGE"]
    database_schema_version: int = Field(alias="databaseSchemaVersion", ge=1)
    report_sha256: str = Field(alias="reportSha256", pattern=r"^[a-f0-9]{64}$")
    natural_status: str = Field(alias="naturalStatus")
    needs_review: bool = Field(alias="needsReview")
    original_data_unchanged: Literal[True] = Field(
        default=True, alias="originalDataUnchanged"
    )
    items: list[WorkMigrationPreservationItem]
    retired_capabilities: list[
        Literal["WOKWI_CLOUD_RUNTIME", "LEGACY_QUICK_CREATE"]
    ] = Field(alias="retiredCapabilities")
    compatibility_imports: list[Literal["WOKWI_DIAGRAM_V1"]] = Field(
        alias="compatibilityImports"
    )
    warnings: list[str]


class WorkDatabaseProtection(WorkModel):
    automatic_backup_enabled: Literal[True] = Field(
        default=True, alias="automaticBackupEnabled"
    )
    backup_available: bool = Field(alias="backupAvailable")
    last_backup_at: str | None = Field(alias="lastBackupAt")
    integrity_status: Literal["OK", "NEEDS_ATTENTION"] = Field(
        alias="integrityStatus"
    )
    restore_mode: Literal["RESTART_REQUIRED"] = Field(alias="restoreMode")
    natural_status: str = Field(alias="naturalStatus")


class WorkDeliveryOverview(WorkModel):
    status: Literal["PREPARING", "READY", "EXPORTED", "IMPORTED_COPY", "REPRODUCED"]
    natural_status: str = Field(alias="naturalStatus")
    ready_to_export: bool = Field(alias="readyToExport")
    card: WorkDeliveryCard
    options: list[WorkDeliveryOption]
    deliveries: list[WorkDeliveryRecord]
    imported_copy: WorkImportedCopy | None = Field(alias="importedCopy")
    reproduction: WorkReproductionSummary
    migration: WorkMigrationReport
    database_protection: WorkDatabaseProtection = Field(alias="databaseProtection")


class CreateWorkDeliveryRequest(WorkModel):
    idempotency_key: str = Field(
        alias="idempotencyKey",
        min_length=8,
        max_length=160,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    kind: Literal["SHARE", "REPRODUCIBLE", "TEMPLATE"]
    title: str | None = Field(default=None, max_length=120)


class ImportWorkDeliveryRequest(WorkModel):
    idempotency_key: str = Field(
        alias="idempotencyKey",
        min_length=8,
        max_length=160,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    zip_base64: str = Field(alias="zipBase64", min_length=1)
    importer: str = Field(default="已认证用户", min_length=1, max_length=200)


class CompleteWorkReproductionRequest(WorkModel):
    operator: str = Field(default="已认证用户", min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=4000)


class WorkReproductionReport(WorkModel):
    id: str
    source_work_id: str = Field(alias="sourceWorkId")
    delivery_id: str = Field(alias="deliveryId")
    import_id: str = Field(alias="importId")
    reproduced_work_id: str = Field(alias="reproducedWorkId")
    operator: str
    package_sha256: str = Field(alias="packageSha256", pattern=r"^[0-9a-f]{64}$")
    passed: bool
    created_at: str = Field(alias="createdAt")


class WorkRecoveryPoint(WorkModel):
    file_name: str = Field(alias="fileName")
    kind: Literal["PRE_MIGRATION", "CORRUPT_QUARANTINE", "OTHER"]
    byte_size: int = Field(alias="byteSize", ge=0)
    created_at: str = Field(alias="createdAt")
    integrity_status: Literal["OK", "NEEDS_ATTENTION", "NOT_APPLICABLE"] = Field(
        alias="integrityStatus"
    )


class WorkMigrationAudit(WorkModel):
    id: str
    from_version: int = Field(alias="fromVersion", ge=0)
    to_version: int = Field(alias="toVersion", ge=0)
    status: str
    backup_available: bool = Field(alias="backupAvailable")
    applied_at: str = Field(alias="appliedAt")


class WorkRecoveryOverview(WorkModel):
    schema_version: int = Field(alias="schemaVersion", ge=0)
    database_integrity: Literal["OK"] = Field(alias="databaseIntegrity")
    natural_status: str = Field(alias="naturalStatus")
    restore_mode: Literal["RESTART_REQUIRED"] = Field(alias="restoreMode")
    recovery_points: list[WorkRecoveryPoint] = Field(alias="recoveryPoints")
    migration_audits: list[WorkMigrationAudit] = Field(alias="migrationAudits")


class WorkRunScenario(WorkModel):
    id: str
    title: str
    expected_behavior: str = Field(alias="expectedBehavior")
    required: bool
    status: WorkRunScenarioStatus


class WorkRunChannel(WorkModel):
    id: str
    label: str
    kind: Literal["INPUT", "OUTPUT", "PARAMETER", "FAULT"]
    value_type: Literal["number", "boolean", "string"] = Field(alias="valueType")
    value: float | bool | str
    unit: str | None
    minimum: float | None
    maximum: float | None
    step: float | None
    writable: bool


class WorkRunRevisionBindings(WorkModel):
    solution_revision_id: str = Field(alias="solutionRevisionId")
    code_run_id: str | None = Field(alias="codeRunId")
    parameter_set_id: str | None = Field(alias="parameterSetId")
    scene_revision: str = Field(alias="sceneRevision")
    structure_revision_id: str | None = Field(alias="structureRevisionId")
    canvas_spec_revision_id: str | None = Field(
        default=None, alias="canvasSpecRevisionId"
    )


class WorkRunRecoveryAction(WorkModel):
    id: str
    label: str
    action_name: Literal["retry_digital_run"] = Field(alias="actionName")


class WorkRunLog(WorkModel):
    revision: int = Field(ge=1)
    type: Literal["state", "telemetry", "log", "ack", "error"]
    message: str
    channel_id: str | None = Field(alias="channelId")
    value: float | bool | str | None
    created_at: str = Field(alias="createdAt")


class WorkWokwiRunSummary(WorkModel):
    diagram_sha256: str = Field(alias="diagramSha256", pattern=r"^[a-f0-9]{64}$")
    firmware_sha256: str = Field(alias="firmwareSha256", pattern=r"^[a-f0-9]{64}$")
    firmware_base_revision: str = Field(alias="firmwareBaseRevision")
    diagram_artifact_version_id: str | None = Field(alias="diagramArtifactVersionId")
    firmware_artifact_version_id: str | None = Field(alias="firmwareArtifactVersionId")
    runtime_package_revision_id: str = Field(alias="runtimePackageRevisionId")
    device_package_revision_id: str = Field(alias="devicePackageRevisionId")
    compatibility_summary: str = Field(alias="compatibilitySummary")


class WorkDigitalRun(WorkModel):
    id: str
    work_id: str = Field(alias="workId")
    status: WorkRunStatus
    natural_status: str = Field(alias="naturalStatus")
    behavior: str
    result_summary: str | None = Field(alias="resultSummary")
    recovery_action: WorkRunRecoveryAction | None = Field(alias="recoveryAction")
    scenarios: list[WorkRunScenario]
    inputs: list[WorkRunChannel]
    outputs: list[WorkRunChannel]
    advanced_controls: list[WorkRunChannel] = Field(alias="advancedControls")
    revision_bindings: WorkRunRevisionBindings = Field(alias="revisionBindings")
    execution_revision_set: ExecutionRevisionSet | None = Field(
        alias="executionRevisionSet"
    )
    engine: Literal["FUNCTIONAL_MODEL", "QEMU_ESP32S3", "WOKWI_CLOUD"]
    wokwi: WorkWokwiRunSummary | None = None
    logs: list[WorkRunLog]
    revision: int = Field(ge=1)
    started_at: str = Field(alias="startedAt")
    updated_at: str = Field(alias="updatedAt")


class WorkSnapshot(WorkModel):
    schema_version: Literal[1, 2] = Field(default=1, alias="schemaVersion")
    work: WorkIdentity
    milestone: WorkJourneyMilestone
    state: WorkState
    natural_status: str = Field(alias="naturalStatus")
    progress_summary: str = Field(alias="progressSummary")
    next_action: WorkNextAction = Field(alias="nextAction")
    current_plan: WorkPlanSummary | None = Field(alias="currentPlan")
    current_preview: WorkPreviewSummary | None = Field(alias="currentPreview")
    current_tasks: list[WorkTaskSummary] = Field(alias="currentTasks")
    current_devices: list[WorkDeviceSummary] = Field(alias="currentDevices")
    current_services: list[WorkServiceSummary] = Field(alias="currentServices")
    current_evidence_summary: WorkEvidenceSummary = Field(
        alias="currentEvidenceSummary"
    )
    current_digital_run: WorkDigitalRun | None = Field(
        default=None, alias="currentDigitalRun"
    )
    current_build_journey: WorkBuildJourney = Field(alias="currentBuildJourney")
    current_acceptance_scenarios: list[WorkAcceptanceScenario] = Field(
        default_factory=list, alias="currentAcceptanceScenarios"
    )
    current_delivery: WorkDeliveryOverview | None = Field(
        default=None, alias="currentDelivery"
    )
    current_canvas: CanvasSpec | None = Field(default=None, alias="currentCanvas")
    current_canvas_layout: CanvasLayout | None = Field(
        default=None, alias="currentCanvasLayout"
    )
    current_canvas_generation: CanvasGeneration | None = Field(
        default=None, alias="currentCanvasGeneration"
    )
    learning_context: WorkLearningContextSnapshot | None = Field(
        default=None, alias="learningContext"
    )
    project_process: ProjectProcessSnapshot | None = Field(
        default=None, alias="projectProcess"
    )
    available_advanced_tools: list[str] = Field(alias="availableAdvancedTools")
    revision: int = Field(ge=0)

    @model_validator(mode="after")
    def _validate_schema_projection(self) -> WorkSnapshot:
        has_learning_projection = (
            self.learning_context is not None and self.project_process is not None
        )
        if self.schema_version == 2 and not has_learning_projection:
            raise ValueError("WorkSnapshot V2 必须包含课堂上下文和项目过程。")
        if self.schema_version == 1 and (
            self.learning_context is not None or self.project_process is not None
        ):
            raise ValueError("WorkSnapshot V1 不能携带 V2 项目过程投影。")
        return self


class WorkSummary(WorkModel):
    work: WorkIdentity
    milestone: WorkJourneyMilestone
    state: WorkState
    natural_status: str = Field(alias="naturalStatus")
    next_action: WorkNextAction = Field(alias="nextAction")
    revision: int = Field(ge=0)


class WorkListResponse(WorkModel):
    works: list[WorkSummary]
    active_work_id: str | None = Field(alias="activeWorkId")


class WorkSnapshotResponse(WorkModel):
    snapshot: WorkSnapshot


class WorkBuildJourneyResponse(WorkModel):
    journey: WorkBuildJourney


class WorkDeliveryOverviewResponse(WorkModel):
    delivery: WorkDeliveryOverview


class WorkMigrationReportResponse(WorkModel):
    report: WorkMigrationReport


class WorkDeliveryResponse(WorkModel):
    delivery: WorkDeliveryRecord
    zip_base64: str = Field(alias="zipBase64")
    overview: WorkDeliveryOverview


class ImportWorkDeliveryResponse(WorkModel):
    import_id: str = Field(alias="importId")
    source_delivery_id: str = Field(alias="sourceDeliveryId")
    package_sha256: str = Field(alias="packageSha256", pattern=r"^[0-9a-f]{64}$")
    snapshot: WorkSnapshot
    overview: WorkDeliveryOverview


class WorkReproductionResponse(WorkModel):
    report: WorkReproductionReport
    source_snapshot: WorkSnapshot = Field(alias="sourceSnapshot")
    imported_snapshot: WorkSnapshot = Field(alias="importedSnapshot")


class WorkRecoveryOverviewResponse(WorkModel):
    recovery: WorkRecoveryOverview


class CanvasGenerationSeed(WorkModel):
    source: WorkIntentSource = WorkIntentSource.FREEFORM
    template_seed_id: str | None = Field(
        default=None, alias="templateSeedId", min_length=1, max_length=160
    )
    reference_names: list[str] = Field(
        default_factory=list, alias="referenceNames", max_length=16
    )
    environment_hint: str | None = Field(
        default=None, alias="environmentHint", min_length=1, max_length=120
    )
    selected_inventory_item_ids: list[str] = Field(
        default_factory=list, alias="selectedInventoryItemIds", max_length=32
    )
    network_preference: Literal[
        "OFFLINE_FIRST", "LOCAL_ONLY", "HOME_LAN", "EXTERNAL_EXISTING"
    ] = Field(default="OFFLINE_FIRST", alias="networkPreference")


class CreateWorkRequest(WorkModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    initial_idea: str = Field(alias="initialIdea", min_length=1, max_length=4000)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=8, max_length=160)
    canvas_seed: CanvasGenerationSeed | None = Field(
        default=None, alias="canvasSeed"
    )


class StartCanvasGenerationRequest(CanvasGenerationSeed):
    idempotency_key: str = Field(
        alias="idempotencyKey",
        min_length=8,
        max_length=160,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )


class CanvasGenerationCommandRequest(WorkModel):
    idempotency_key: str = Field(
        alias="idempotencyKey",
        min_length=8,
        max_length=160,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )


class SaveCanvasLayoutRequest(WorkModel):
    idempotency_key: str = Field(
        alias="idempotencyKey",
        min_length=8,
        max_length=160,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    expected_revision: int = Field(alias="expectedRevision", ge=1)
    positions: list[CanvasNodePosition] = Field(min_length=1, max_length=128)
    viewport: CanvasViewport
    collapsed_node_ids: list[str] = Field(alias="collapsedNodeIds", max_length=128)


class ConfirmCanvasProposalRequest(WorkModel):
    idempotency_key: str = Field(
        alias="idempotencyKey",
        min_length=8,
        max_length=160,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    canvas_spec_id: str = Field(alias="canvasSpecId", min_length=1, max_length=240)
    expected_canvas_revision: int = Field(alias="expectedCanvasRevision", ge=1)


class CanvasGenerationResponse(WorkModel):
    generation: CanvasGeneration
    snapshot: WorkSnapshot


class CanvasLayoutResponse(WorkModel):
    layout: CanvasLayout
    snapshot: WorkSnapshot


class ConfirmCanvasProposalResponse(WorkModel):
    snapshot: WorkSnapshot


class StartWorkRunRequest(WorkModel):
    idempotency_key: str = Field(
        alias="idempotencyKey",
        min_length=8,
        max_length=160,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    parameter_set_id: str | None = Field(
        default=None, alias="parameterSetId", max_length=160
    )
    engine: Literal["FUNCTIONAL_MODEL"] = "FUNCTIONAL_MODEL"


class UpdateWorkRunControlRequest(WorkModel):
    value: float | bool | str
    expected_revision: int = Field(alias="expectedRevision", ge=1)
    command_id: str = Field(
        alias="commandId",
        min_length=8,
        max_length=128,
        pattern=r"^[A-Za-z0-9._-]+$",
    )


class CompleteWorkRunScenarioRequest(WorkModel):
    scenario_id: str = Field(alias="scenarioId", min_length=1, max_length=160)
    passed: bool


class CompleteWorkRunRequest(WorkModel):
    idempotency_key: str = Field(
        alias="idempotencyKey",
        min_length=8,
        max_length=160,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    scenario_results: list[CompleteWorkRunScenarioRequest] = Field(
        alias="scenarioResults", min_length=1, max_length=64
    )


class WorkRunResponse(WorkModel):
    run: WorkDigitalRun
    snapshot: WorkSnapshot


class WorkRunListResponse(WorkModel):
    runs: list[WorkDigitalRun]
