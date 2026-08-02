import type { ExpertType } from "./types";

export type DomainEvent =
  | {
      type: "shared_fact.confirmed";
      projectId: string;
      factId: string;
      occurredAt: string;
    }
  | {
      type: "artifact.confirmed";
      projectId: string;
      artifactId: string;
      version: number;
      occurredAt: string;
    }
  | {
      type: "artifact.outdated";
      projectId: string;
      artifactId: string;
      reason: string;
      occurredAt: string;
    }
  | {
      type: "handoff.proposed";
      projectId: string;
      handoffId: string;
      fromExpert: ExpertType;
      toExpert: ExpertType;
      occurredAt: string;
    }
  | {
      type: "pending_item.resolved";
      projectId: string;
      pendingItemId: string;
      occurredAt: string;
    };
