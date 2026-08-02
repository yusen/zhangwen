export type ExpertType =
  | "problem_guide"
  | "smart_engineer"
  | "structure_engineer";

export type LegacyExpertType =
  | "ideator"
  | "educator"
  | "open_hardware_designer"
  | "three_d_structure_designer";

export type ArtifactStatus =
  | "draft"
  | "pending_confirmation"
  | "confirmed"
  | "outdated"
  | "archived";

export type TaskStatus =
  | "queued"
  | "ready"
  | "running"
  | "blocked"
  | "awaiting_user"
  | "completed"
  | "failed"
  | "cancelled";

export type PendingPriority =
  | "safety"
  | "blocking"
  | "conflict"
  | "confirmation"
  | "missing_input"
  | "normal";

export interface SharedFact {
  id: string;
  projectId: string;
  key: string;
  value: unknown;
  status: "proposed" | "confirmed" | "superseded" | "rejected";
  sourceType: "user" | "expert" | "artifact" | "device";
  sourceId?: string;
  proposedBy?: ExpertType;
  confirmedBy?: "user" | "system_rule";
  affectsArtifactIds: string[];
  createdAt: string;
  updatedAt: string;
}

export interface ArtifactRef {
  artifactId: string;
  version: number;
  type: string;
  ownerExpert: ExpertType;
  status: ArtifactStatus;
}

export interface ProjectDecision {
  id: string;
  projectId: string;
  title: string;
  value: unknown;
  reason: string;
  proposedBy?: ExpertType;
  confirmedBy: "user" | "system_rule";
  affectedArtifactIds: string[];
  createdAt: string;
}

export interface PendingItem {
  id: string;
  projectId: string;
  title: string;
  description: string;
  priority: PendingPriority;
  reason: string;
  affectedExperts: ExpertType[];
  options?: string[];
  status: "open" | "resolved" | "dismissed";
  isHighlighted: boolean;
  createdAt: string;
}

export interface ProjectSharedContext {
  projectId: string;
  projectName: string;
  summary: string;
  targetUsers: string[];
  scenarios: string[];
  goals: string[];
  functions: string[];
  constraints: {
    budget?: string;
    size?: string;
    time?: string;
    safety: string[];
    platform: string[];
  };
  confirmedFacts: SharedFact[];
  decisions: ProjectDecision[];
  devices: string[];
  artifacts: ArtifactRef[];
  participatingExperts: ExpertType[];
  currentExpert?: ExpertType;
  currentPendingItem?: PendingItem;
}
