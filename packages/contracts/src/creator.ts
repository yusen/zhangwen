/** Shared Creator V3 contracts. Server projections are authoritative. */

export const CreatorStage = {
  IDEA_SOLUTION: "IDEA_SOLUTION",
  DIGITAL_PROTOTYPE: "DIGITAL_PROTOTYPE",
  STRUCTURE_3D: "STRUCTURE_3D",
  PHYSICAL_RUN: "PHYSICAL_RUN",
} as const;
export type CreatorStage = (typeof CreatorStage)[keyof typeof CreatorStage];

export const CreatorPhase = {
  IDEA: "IDEA",
  GOAL_REVIEW: "GOAL_REVIEW",
  SOLUTION_REVIEW: "SOLUTION_REVIEW",
  DIGITAL_BUILDING: "DIGITAL_BUILDING",
  SIMULATING: "SIMULATING",
  SIMULATION_PASSED: "SIMULATION_PASSED",
  DEVICE_CONNECTED: "DEVICE_CONNECTED",
  DEPLOYED: "DEPLOYED",
  PHYSICAL_VALIDATING: "PHYSICAL_VALIDATING",
  PHYSICAL_PASSED: "PHYSICAL_PASSED",
  ACCEPTED: "ACCEPTED",
  DELIVERED: "DELIVERED",
} as const;
export type CreatorPhase = (typeof CreatorPhase)[keyof typeof CreatorPhase];

export type VerificationLevel = 0 | 1 | 2 | 3 | 4 | 5 | 6;

export const CreatorJobStatus = {
  QUEUED: "QUEUED",
  RUNNING: "RUNNING",
  WAITING_CONFIRMATION: "WAITING_CONFIRMATION",
  SUCCEEDED: "SUCCEEDED",
  FAILED: "FAILED",
  CANCELED: "CANCELED",
} as const;
export type CreatorJobStatus =
  (typeof CreatorJobStatus)[keyof typeof CreatorJobStatus];

export const CreatorJobKind = {
  CODE_PREPARATION: "CODE_PREPARATION",
  DIGITAL_PROTOTYPE: "DIGITAL_PROTOTYPE",
  STRUCTURE_DRAFT: "STRUCTURE_DRAFT",
} as const;
export type CreatorJobKind =
  (typeof CreatorJobKind)[keyof typeof CreatorJobKind];

export const CreatorJobCommand = {
  CANCEL: "CANCEL",
  RETRY: "RETRY",
} as const;
export type CreatorJobCommand =
  (typeof CreatorJobCommand)[keyof typeof CreatorJobCommand];

export const CreatorEvidenceStatus = {
  CURRENT: "CURRENT",
  STALE: "STALE",
  FAILED: "FAILED",
  SUPERSEDED: "SUPERSEDED",
} as const;
export type CreatorEvidenceStatus =
  (typeof CreatorEvidenceStatus)[keyof typeof CreatorEvidenceStatus];

export const CreatorEvidenceKind = {
  GOAL_CONFIRMATION: "GOAL_CONFIRMATION",
  STATIC_VALIDATION: "STATIC_VALIDATION",
  SIMULATION: "SIMULATION",
  DEVICE_CONNECTION: "DEVICE_CONNECTION",
  DEPLOYMENT: "DEPLOYMENT",
  PHYSICAL_BEHAVIOR: "PHYSICAL_BEHAVIOR",
  USER_ACCEPTANCE: "USER_ACCEPTANCE",
  REPRODUCTION: "REPRODUCTION",
  STRUCTURE_CHECK: "STRUCTURE_CHECK",
} as const;
export type CreatorEvidenceKind =
  (typeof CreatorEvidenceKind)[keyof typeof CreatorEvidenceKind];

export const CreatorCommand = {
  SAVE_GOAL: "SAVE_GOAL",
  CONFIRM_GOAL: "CONFIRM_GOAL",
  SAVE_SOLUTION: "SAVE_SOLUTION",
  CONFIRM_SOLUTION: "CONFIRM_SOLUTION",
  GENERATE_PROJECT_BOOK: "GENERATE_PROJECT_BOOK",
  RECORD_STATIC_VALIDATION: "RECORD_STATIC_VALIDATION",
  RECORD_SIMULATION: "RECORD_SIMULATION",
  RECORD_STRUCTURE_CHECK: "RECORD_STRUCTURE_CHECK",
  RECORD_DEVICE_CONNECTION: "RECORD_DEVICE_CONNECTION",
  RECORD_DEPLOYMENT: "RECORD_DEPLOYMENT",
  RECORD_PHYSICAL_BEHAVIOR: "RECORD_PHYSICAL_BEHAVIOR",
  ACCEPT_WORK: "ACCEPT_WORK",
  RECORD_REPRODUCTION: "RECORD_REPRODUCTION",
  ARCHIVE_WORK: "ARCHIVE_WORK",
} as const;
export type CreatorCommand = (typeof CreatorCommand)[keyof typeof CreatorCommand];

export const CreatorRevisionSourceType = {
  CONVERSATION: "CONVERSATION",
  PROFESSIONAL_EDIT: "PROFESSIONAL_EDIT",
  LEGACY_PROJECTION: "LEGACY_PROJECTION",
  SYSTEM_MIGRATION: "SYSTEM_MIGRATION",
} as const;
export type CreatorRevisionSourceType =
  (typeof CreatorRevisionSourceType)[keyof typeof CreatorRevisionSourceType];

export interface ConversationProjectDraftV1 {
  schemaVersion: 1;
  useScenario: string;
  observableBehavior: string;
  constraints: string[];
  successCriteria: string[];
  missingFields: string[];
}

export interface CreatorProjectionReceipt {
  id: string;
  workId: string;
  sourceType: CreatorRevisionSourceType;
  sourceMessageId: string;
  sourceTurnId: string | null;
  draftHash: string;
  status: "APPLIED" | "DUPLICATE" | "CONFLICT" | "REJECTED";
  goalRevisionId: string | null;
  solutionRevisionId: string | null;
  message: string | null;
  createdAt: string;
}

export interface ProjectBookProjection {
  status: "EMPTY" | "CURRENT" | "STALE" | "GOAL_ONLY" | "SYNCHRONIZED";
  bookId?: string | null;
  revision?: number | null;
  goalRevisionId: string | null;
  solutionRevisionId: string | null;
  sections?: Array<{ id: string; title: string; content: string }>;
  generatedAt?: string | null;
  updatedAt: string | null;
}

export interface ConversationProjectionStatus {
  status: "IDLE" | "CURRENT" | "CONFLICT" | "FAILED";
  receiptId: string | null;
  sourceMessageId: string | null;
  message: string | null;
}

export interface CreatorRevisionBase {
  id: string;
  workId: string;
  revision: number;
  status: "DRAFT" | "CONFIRMED" | "SUPERSEDED";
  sourceType: CreatorRevisionSourceType;
  sourceMessageId: string | null;
  sourceTurnId: string | null;
  baseRevisionId: string | null;
  projectionReceiptId: string | null;
  createdAt: string;
  confirmedAt: string | null;
}

export interface GoalRevision extends CreatorRevisionBase {
  statement: string;
  observableBehavior: string;
  constraints: string[];
  successCriteria: string[];
}

export interface SolutionRevision extends CreatorRevisionBase {
  summary: string;
  logic: string;
  hardware: string;
  software: string;
  structure: string;
  simulation: string;
  safety: string;
  bom: Array<{ componentId: string; name: string; quantity: number }>;
  ioMap: Array<{ signal: string; pin: string; purpose: string }>;
}

export interface AcceptanceScenario {
  id: string;
  workId: string;
  title: string;
  required: boolean;
  simulationExpected: string;
  physicalExpected: string;
  createdAt: string;
}

export interface CreatorJob {
  id: string;
  workId: string;
  solutionRevisionId: string;
  kind: CreatorJobKind;
  status: CreatorJobStatus;
  progress: number;
  message: string | null;
  result: Record<string, unknown> | null;
  createdAt: string;
  updatedAt: string;
  startedAt: string | null;
  completedAt: string | null;
}

export interface CodeVariantBinding {
  id: string;
  workId: string;
  solutionRevisionId: string;
  deploymentChannel: import("./enums.js").DeviceDeploymentChannel;
  runtime: import("./enums.js").CodeRuntime;
  codeRunId: string | null;
  devicePackageId: string | null;
  validationStatus: "PENDING" | "READY_FOR_REVIEW" | "FAILED" | "ACCEPTED";
  failureCode: string | null;
  failureMessage: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface CreatorJobCommandRequest {
  idempotencyKey: string;
}

export interface CreatorJobResponse {
  job: CreatorJob;
}

export interface CreatorJobCommandResponse {
  command: CreatorJobCommand;
  repeated: boolean;
  job: CreatorJob;
  workspace: CreatorWorkspace;
}

export interface ParameterRevision {
  id: string;
  workId: string;
  boardId: string;
  profileRevision: string;
  revision: number;
  label: string;
  values: Record<string, number | boolean | string>;
  createdAt: string;
}

export interface EvidenceRecord {
  id: string;
  workId: string;
  kind: CreatorEvidenceKind;
  status: CreatorEvidenceStatus;
  passed: boolean;
  summary: string;
  bindings: Record<string, string>;
  sourceId: string | null;
  recordedAt: string;
  invalidatedAt: string | null;
  invalidationReason: string | null;
}

export interface CreatorStageSummary {
  stage: CreatorStage;
  label: string;
  status: "NOT_STARTED" | "ACTIVE" | "READY" | "PASSED" | "BLOCKED" | "NOT_APPLICABLE";
  detail: string;
}

export interface CreatorNextAction {
  id: string;
  label: string;
  command: CreatorCommand | null;
  stage: CreatorStage;
  enabled: boolean;
  blockedReason: string | null;
  riskLevel: "LOW" | "MEDIUM" | "HIGH";
}

export interface CreatorWorkSummary {
  id: string;
  name: string;
  initialIdea: string;
  phase: CreatorPhase;
  stage: CreatorStage;
  verificationLevel: VerificationLevel;
  verificationLabel: string;
  nextActionLabel: string;
  archivedAt: string | null;
  updatedAt: string;
  legacy: boolean;
}

export interface CreatorWorkspace {
  schemaVersion: 1;
  workId: string;
  projectId: string;
  projectVersion: number;
  name: string;
  initialIdea: string;
  phase: CreatorPhase;
  activeStage: CreatorStage;
  verificationLevel: VerificationLevel;
  verificationLabel: string;
  stages: CreatorStageSummary[];
  confirmedGoal: GoalRevision | null;
  draftGoal: GoalRevision | null;
  confirmedSolution: SolutionRevision | null;
  draftSolution: SolutionRevision | null;
  projectBookProjection: ProjectBookProjection;
  conversationProjectionStatus: ConversationProjectionStatus;
  currentGoal: GoalRevision | null;
  currentSolution: SolutionRevision | null;
  acceptanceScenarios: AcceptanceScenario[];
  jobs: CreatorJob[];
  codeVariants: CodeVariantBinding[];
  parameterRevisions: ParameterRevision[];
  evidence: EvidenceRecord[];
  nextAction: CreatorNextAction;
  archivedAt: string | null;
  updatedAt: string;
  legacy: boolean;
  needsOrganization: boolean;
}

export interface CreateCreatorWorkRequest {
  name?: string;
  initialIdea: string;
  idempotencyKey: string;
  selectedHardwareIds?: string[];
}

export interface CreatorWorkListResponse {
  works: CreatorWorkSummary[];
  activeWorkId: string | null;
}

export interface CreatorWorkspaceResponse {
  workspace: CreatorWorkspace;
}

export interface CreatorCommandRequest {
  baseProjectVersion: number;
  idempotencyKey: string;
  payload: Record<string, unknown>;
}

export interface CreatorCommandResponse {
  commandId: string;
  command: CreatorCommand;
  repeated: boolean;
  workspace: CreatorWorkspace;
}

interface CreatorEventEnvelope {
  id: string;
  createdAt: string;
}

export interface CreatorOperationalEvent extends CreatorEventEnvelope {
  workId: string;
  type: "COMMAND" | "PROJECTION" | "EVIDENCE" | "JOB" | "DEVICE" | "TELEMETRY";
  payload: Record<string, unknown>;
}

interface CreatorMetricBase {
  schemaVersion: 1;
  triggerId: string;
}

export type CreatorMetricPayload =
  | (CreatorMetricBase & {
      metric: "WORK_CREATED";
      origin: "CREATOR" | "LEGACY";
    })
  | (CreatorMetricBase & {
      metric: "GOAL_CONFIRMED";
      revision: number;
    })
  | (CreatorMetricBase & {
      metric: "SOLUTION_CONFIRMED";
      revision: number;
      capabilityClass: "SENSING" | "RESPONSE" | "VISION_AUDIO" | "MIXED";
    })
  | (CreatorMetricBase & {
      metric: "DIGITAL_BEHAVIOR_OBSERVED";
      elapsedMs: number;
    })
  | (CreatorMetricBase & {
      metric: "SIMULATION_FINISHED";
      passed: boolean;
      requiredScenarioCount: number;
      passedRequiredScenarioCount: number;
      failureCategory: "PARAMETER" | "LOGIC" | "IO" | "CAPABILITY" | "UNKNOWN" | "NONE";
    })
  | (CreatorMetricBase & {
      metric: "FIRST_DEPLOYMENT_FINISHED";
      passed: boolean;
      channel: "USB_SERIAL" | "ESP_CLAW";
      recoveryRequired: boolean;
    })
  | (CreatorMetricBase & {
      metric: "PHYSICAL_BEHAVIOR_FINISHED";
      passedScenarioCount: number;
      comparedScenarioCount: number;
      simulationConsistent: boolean;
    })
  | (CreatorMetricBase & {
      metric: "RECOVERY_FINISHED";
      action: "USB_UPLOAD" | "ESP_CLAW_UPLOAD" | "PARAMETER_SYNC" | "SIMULATION";
      passed: boolean;
    })
  | (CreatorMetricBase & {
      metric: "WORK_ACCEPTED";
      elapsedMs: number;
    })
  | (CreatorMetricBase & {
      metric: "DELIVERY_EXPORTED";
      variant: "SHARE" | "REPRODUCIBLE" | "TEMPLATE";
      requiredEvidenceCount: number;
      currentEvidenceCount: number;
      coverageRatio: number;
    })
  | (CreatorMetricBase & {
      metric: "REPRODUCTION_FINISHED";
      passed: boolean;
    })
  | (CreatorMetricBase & {
      metric: "LEGACY_MIGRATION_FINISHED";
      fromSchemaVersion: number;
      migratedRowCount: number;
      zeroDataLoss: boolean;
      passed: boolean;
    });

export interface CreatorMetricEvent extends CreatorEventEnvelope {
  type: "METRIC";
  payload: CreatorMetricPayload;
}

export type CreatorEvent = CreatorOperationalEvent | CreatorMetricEvent;

export interface DevicePackageRevision {
  id: string;
  version: string;
  displayName: string;
  boardProfileId: string;
  capabilities: string[];
  deploymentChannels: string[];
  interactiveConsoleChannels?: string[];
  simulationModes: string[];
  source: string;
}

export interface PhysicalScenarioResult {
  scenarioId: string;
  observed: boolean;
  note: string;
}

export interface CreatePhysicalRunRequest {
  deploymentOperationId: string;
  targetId: string;
  emergencyStopVerified: boolean;
  scenarioResults: PhysicalScenarioResult[];
  idempotencyKey: string;
}

export interface PhysicalRunReport {
  id: string;
  workId: string;
  solutionRevisionId: string;
  deploymentOperationId: string;
  targetId: string;
  operator: string;
  passed: boolean;
  emergencyStopVerified: boolean;
  scenarioResults: PhysicalScenarioResult[];
  createdAt: string;
}

export const CreatorDeliveryVariant = {
  SHARE: "SHARE",
  REPRODUCIBLE: "REPRODUCIBLE",
  TEMPLATE: "TEMPLATE",
} as const;
export type CreatorDeliveryVariant =
  (typeof CreatorDeliveryVariant)[keyof typeof CreatorDeliveryVariant];

export interface CreatorDeliveryFile {
  path: string;
  byteSize: number;
  sha256: string;
}

export interface CreatorDeliveryManifestV1 {
  schemaVersion: 1;
  deliveryId: string;
  variant: CreatorDeliveryVariant;
  sourceWorkId: string;
  sourceProjectVersion: number;
  createdAt: string;
  goalRevisionId: string;
  solutionRevisionId: string;
  devicePackages: Array<{ id: string; version: string }>;
  versionBindings: Record<string, string>;
  evidenceKinds: CreatorEvidenceKind[];
  maturity: Record<string, "MVP" | "CONTROLLED_BETA" | "TECH_PREVIEW">;
  files: CreatorDeliveryFile[];
  privacyOk: boolean;
}

export interface CreateCreatorDeliveryRequest {
  variant: CreatorDeliveryVariant;
  title?: string;
  idempotencyKey: string;
}

export interface CreatorDeliveryRecord {
  id: string;
  workId: string;
  variant: CreatorDeliveryVariant;
  status: "EXPORTED" | "IMPORTED";
  title: string;
  fileName: string;
  packageSha256: string;
  manifest: CreatorDeliveryManifestV1;
  privacyReport: { ok?: boolean; checks?: Array<Record<string, unknown>> };
  zipBase64: string | null;
  createdAt: string;
}

export interface ImportCreatorDeliveryRequest {
  zipBase64: string;
  idempotencyKey: string;
}

export interface ImportCreatorDeliveryResponse {
  importId: string;
  sourceDeliveryId: string;
  packageSha256: string;
  workspace: CreatorWorkspace;
}

export interface CreatorImportContext {
  importId: string;
  sourceWorkId: string;
  sourceDeliveryId: string;
  importer: string;
  packageSha256: string;
}

export interface CompleteImportedReproductionRequest {
  summary: string;
}

export interface CompleteReproductionRequest {
  importId: string;
  reproducedWorkId: string;
  summary: string;
}

export interface ReproductionReport {
  id: string;
  sourceWorkId: string;
  deliveryId: string;
  importId: string;
  reproducedWorkId: string;
  operator: string;
  packageSha256: string;
  passed: boolean;
  createdAt: string;
}
