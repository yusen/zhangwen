import type { ArtifactStatus, ExpertType } from "./types";

export interface ArtifactDependency {
  upstreamArtifactId: string;
  upstreamVersion: number;
  relation:
    | "requires"
    | "derived_from"
    | "dimension_source"
    | "interface_contract"
    | "content_source";
}

export interface Artifact {
  id: string;
  projectId: string;
  ownerExpert: ExpertType;
  legacyOwnerExpert?: string;
  type: string;
  title: string;
  version: number;
  status: ArtifactStatus;
  storageUri?: string;
  content?: unknown;
  dependencies: ArtifactDependency[];
  createdAt: string;
  updatedAt: string;
}
