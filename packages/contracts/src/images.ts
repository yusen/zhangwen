import type { ProjectReference } from './platform';

export interface ImageSettings {
  configured: boolean; baseUrl: string; model: string;
  responseFormat: 'auto' | 'b64_json';
}
export interface SaveImageSettings {
  baseUrl: string; model: string; apiKey?: string | null;
  responseFormat: 'auto' | 'b64_json';
}
export type ProjectImageKind = 'block' | 'concept';
export interface GenerateProjectImage {
  requestId: string; kind: ProjectImageKind; prompt: string;
  size: '1024x1024' | '1536x1024' | '1024x1536';
}
export interface ImageJob {
  requestId: string; kind: ProjectImageKind; prompt: string; size: GenerateProjectImage['size'];
  status: 'generating' | 'completed' | 'failed' | 'unknown';
  createdAt: string; message: string; referenceId?: string;
  source: { projectRevision: number; workflowRevision: number; fingerprint: string };
}
export interface ProjectImages { jobs: ImageJob[]; references: ProjectReference[] }
