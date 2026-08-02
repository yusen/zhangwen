/**
 * 掌问 V2 Project Kernel、Capability 与本地主机共享契约。
 *
 * 本文件只描述跨进程边界；关系表和领域仓储仍是权威事实源，ProjectState
 * 是可重建投影，不是第二套可直接编辑的 JSON 真值。
 */

export const ProjectWorkspaceKind = {
  OVERVIEW: "overview",
  ENGINEERING: "engineering",
  STRUCTURE: "structure",
  DELIVERY: "delivery",
} as const;
export type ProjectWorkspaceKind =
  (typeof ProjectWorkspaceKind)[keyof typeof ProjectWorkspaceKind];

export const ProjectMode = {
  STANDARD: "STANDARD",
  EXPLORATION: "EXPLORATION",
  PLAN_ONLY: "PLAN_ONLY",
} as const;
export type ProjectMode = (typeof ProjectMode)[keyof typeof ProjectMode];

export const ChangeSetStatus = {
  DRAFT: "DRAFT",
  VALIDATING: "VALIDATING",
  READY: "READY",
  CONFIRMED: "CONFIRMED",
  COMMITTED: "COMMITTED",
  REJECTED: "REJECTED",
  CANCELED: "CANCELED",
} as const;
export type ChangeSetStatus =
  (typeof ChangeSetStatus)[keyof typeof ChangeSetStatus];

export const ChangeSetRiskLevel = {
  LOW: "LOW",
  MEDIUM: "MEDIUM",
  HIGH: "HIGH",
} as const;
export type ChangeSetRiskLevel =
  (typeof ChangeSetRiskLevel)[keyof typeof ChangeSetRiskLevel];

export const ChangeSetConfirmationPolicy = {
  AUTO: "AUTO",
  USER: "USER",
  EXPLICIT_RISK: "EXPLICIT_RISK",
} as const;
export type ChangeSetConfirmationPolicy =
  (typeof ChangeSetConfirmationPolicy)[keyof typeof ChangeSetConfirmationPolicy];

export const CapabilityKind = {
  RESOURCE: "RESOURCE",
  PROCEDURE: "PROCEDURE",
  EXECUTION: "EXECUTION",
  COMPOSITE: "COMPOSITE",
} as const;
export type CapabilityKind =
  (typeof CapabilityKind)[keyof typeof CapabilityKind];

export const CapabilityStatus = {
  SUGGESTED: "SUGGESTED",
  DRAFT: "DRAFT",
  VERIFIED: "VERIFIED",
  DEPRECATED: "DEPRECATED",
  INVALID: "INVALID",
} as const;
export type CapabilityStatus =
  (typeof CapabilityStatus)[keyof typeof CapabilityStatus];

export const ToolJobKind = {
  CAD_INTENT: "CAD_INTENT",
  CAD_BUILD: "CAD_BUILD",
  DEVICE_TAKEOVER: "DEVICE_TAKEOVER",
  DEVICE_UPLOAD: "DEVICE_UPLOAD",
} as const;
export type ToolJobKind = (typeof ToolJobKind)[keyof typeof ToolJobKind];

export const ToolJobStatus = {
  QUEUED: "QUEUED",
  RUNNING: "RUNNING",
  WAITING_CONFIRMATION: "WAITING_CONFIRMATION",
  SUCCEEDED: "SUCCEEDED",
  FAILED: "FAILED",
  CANCELED: "CANCELED",
} as const;
export type ToolJobStatus =
  (typeof ToolJobStatus)[keyof typeof ToolJobStatus];

export const HostCapability = {
  CAD_LOCAL: "cad.local",
  DEVICE_SERIAL: "device.serial",
  DEVICE_UPLOAD: "device.upload",
} as const;
export type HostCapability =
  (typeof HostCapability)[keyof typeof HostCapability];

export interface ProjectStateDomainSummary {
  status: string;
  revision: string | null;
  activeArtifactIds: string[];
  pendingItems: string[];
}

export interface ProjectState {
  schemaVersion: 1;
  projectId: string;
  projectVersion: number;
  projectionHash: string;
  projectedAt: string;
  mode: ProjectMode;
  stage: string;
  currentRecommendation: string | null;
  facts: Array<{
    id: string;
    key: string;
    label: string;
    value: unknown;
    displayValue: string;
    revision: number;
  }>;
  domains: {
    problemGuide: ProjectStateDomainSummary;
    engineering: ProjectStateDomainSummary;
    structure: ProjectStateDomainSummary;
    delivery: ProjectStateDomainSummary;
  };
  capabilityCoverage: CapabilityCoverage;
}

export type ChangeOperationKind =
  | "SET_PROJECT_MODE"
  | "UPSERT_FACT"
  | "REMOVE_FACT"
  | "BIND_CAPABILITY"
  | "UNBIND_CAPABILITY"
  | "MARK_ARTIFACT_OUTDATED";

export interface ChangeOperation {
  op: ChangeOperationKind;
  path: string;
  value?: unknown;
  previousHash?: string | null;
}

export interface ChangeSetValidationResult {
  code: string;
  severity: "PASS" | "WARNING" | "FAIL";
  message: string;
}

export interface ChangeSet {
  id: string;
  projectId: string;
  baseProjectVersion: number;
  authorType: "USER" | "EXPERT" | "SYSTEM";
  ownerDomain: "problem_guide" | "engineering" | "structure" | "delivery";
  intentSummary: string;
  operations: ChangeOperation[];
  affectedFacts: string[];
  affectedArtifacts: string[];
  capabilityBindings: string[];
  validationResults: ChangeSetValidationResult[];
  riskLevel: ChangeSetRiskLevel;
  confirmationPolicy: ChangeSetConfirmationPolicy;
  status: ChangeSetStatus;
  createdAt: string;
  committedAt: string | null;
}

export interface CreateChangeSetRequest {
  baseProjectVersion: number;
  authorType?: "USER" | "EXPERT" | "SYSTEM";
  ownerDomain: ChangeSet["ownerDomain"];
  intentSummary: string;
  operations: ChangeOperation[];
  idempotencyKey: string;
}

export interface Capability {
  id: string;
  kind: CapabilityKind;
  status: CapabilityStatus;
  name: string;
  version: string;
  sourceType: string;
  sourceId: string;
  revision: string;
  hostRequirements: HostCapability[];
  riskLevel: ChangeSetRiskLevel;
  metadata: Record<string, unknown>;
}

export interface CapabilityCoverage {
  mode: ProjectMode;
  coveragePercent: number;
  verifiedCapabilityIds: string[];
  missing: Array<{ requirement: string; reason: string }>;
}

export interface ProjectVersion {
  id: string;
  projectId: string;
  version: number;
  stateHash: string;
  changeSetId: string | null;
  capabilitySnapshotHash: string;
  artifactVersionIds: string[];
  validationSummary: ChangeSetValidationResult[];
  createdAt: string;
}

export interface ProjectRelease {
  id: string;
  projectId: string;
  projectVersionId: string;
  name: string;
  manifestHash: string;
  artifactVersionIds: string[];
  unverifiedItems: string[];
  notes: string;
  createdAt: string;
}

export interface ToolJob {
  id: string;
  projectId: string;
  kind: ToolJobKind;
  status: ToolJobStatus;
  requestHash: string;
  hostLeaseId: string | null;
  progress: number;
  resultArtifactIds: string[];
  error: { code: string; message: string } | null;
  createdAt: string;
  updatedAt: string;
}

export interface HostCapabilityLease {
  id: string;
  projectId: string;
  origin: string;
  capabilities: HostCapability[];
  issuedAt: string;
  expiresAt: string;
  revokedAt: string | null;
}

export interface CadObjectIndexEntry {
  id: string;
  type:
    | "assembly"
    | "part"
    | "feature"
    | "constraint"
    | "reference"
    | "hardware_reference";
  label: string;
  parentId?: string | null;
}

export interface CadIntentRevision {
  id: string;
  projectId: string;
  parentRevisionId: string | null;
  toolJobId: string;
  changeSetId: string;
  projectVersionId: string | null;
  intentSummary: string;
  routeAction: string;
  status: "PLANNED" | "CONFIRMED" | "REJECTED" | "FAILED";
  sourceSha256: string;
  objectIndex: CadObjectIndexEntry[];
  artifactId: string | null;
  artifactVersionId: string | null;
  createdAt: string;
  confirmedAt: string | null;
}

export interface CadIntentWorkspace {
  currentRevision: CadIntentRevision | null;
  pendingRevision: CadIntentRevision | null;
  revisions: CadIntentRevision[];
  legacyCadRun: import("./api.js").CadRun | null;
  jobs: ToolJob[];
}

export interface ProjectStructureFact {
  key: string;
  label: string;
  displayValue: string;
  revision: number;
}

export interface ProjectStructureHardware {
  id: string;
  name: string;
  skillName?: string | null;
  skillRevision?: string | null;
}

export interface ProjectStructureMechanicalProfile {
  hardwareId: string;
  profileId: string;
  revision: string;
  displayName: string;
  evidenceLevel: string;
  representation: string;
  contentSha256: string;
  geometry: Record<string, unknown>;
}

export interface ProjectStructureArtifact {
  artifactId: string;
  title: string;
  kind: string;
  status: string;
  currentVersionId?: string | null;
  version?: number | null;
  summary?: string | null;
}

export interface ProjectStructureContext {
  schemaVersion: 1;
  projectId: string;
  projectVersion: number;
  projectionHash: string;
  contextSha256: string;
  projectName: string;
  initialIdea: string;
  currentRecommendation?: string | null;
  stage: string;
  mode: string;
  confirmedFacts: ProjectStructureFact[];
  selectedHardware: ProjectStructureHardware[];
  mechanicalProfiles: ProjectStructureMechanicalProfile[];
  upstreamArtifacts: ProjectStructureArtifact[];
  currentCadRevision?: {
    id: string;
    sourceSha256: string;
    objectIndex: CadObjectIndexEntry[];
  } | null;
}

export interface CadIntentPromptRequest {
  prompt: string;
  mode: "route" | "draft" | "edit";
  baseProjectVersion: number;
  currentRevisionId?: string | null;
}

export interface CadIntentResult {
  kind: string;
  status?: string;
  message?: string;
  route?: Record<string, unknown>;
  capabilityGap?: Record<string, unknown> | null;
  missingFields?: string[];
  revision?: CadIntentRevision;
}

export interface CadBuildResult extends CadIntentResult {
  kind: "CadBuildResult";
  status: "artifact_exports";
  artifactId: string;
  artifactVersionId: string;
  modelFileId: string;
  sourceSha256: string;
  fileCount: number;
  meshValidationStatus?: string | null;
}
