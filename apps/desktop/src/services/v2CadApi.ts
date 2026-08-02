import type {
  CadBuildResult,
  CadIntentPromptRequest,
  CadIntentResult,
  CadIntentRevision,
  CadIntentWorkspace,
  ToolJob,
} from "@zhangwen/contracts";
import { apiGet, apiPost } from "./api";

export function getV2CadWorkspace(
  projectId: string,
  signal?: AbortSignal,
): Promise<{ workspace: CadIntentWorkspace }> {
  return apiGet<{ workspace: CadIntentWorkspace }>(
    `/api/v2/projects/${projectId}/cad/workspace`,
    signal,
  );
}

export function submitV2CadIntent(
  projectId: string,
  request: CadIntentPromptRequest,
): Promise<{ job: ToolJob; result: CadIntentResult }> {
  return apiPost<CadIntentPromptRequest, { job: ToolJob; result: CadIntentResult }>(
    `/api/v2/projects/${projectId}/cad/intent`,
    request,
  );
}

export function confirmV2CadRevision(
  projectId: string,
  revisionId: string,
): Promise<{ revision: CadIntentRevision }> {
  return apiPost<Record<string, never>, { revision: CadIntentRevision }>(
    `/api/v2/projects/${projectId}/cad/revisions/${revisionId}/confirm`,
    {},
  );
}

export function buildV2CadRevision(
  projectId: string,
  revisionId: string,
): Promise<{ result: CadBuildResult }> {
  return apiPost<Record<string, never>, { result: CadBuildResult }>(
    `/api/v2/projects/${projectId}/cad/revisions/${revisionId}/build`,
    {},
  );
}

export function undoV2CadRevision(
  projectId: string,
  revisionId: string,
  baseProjectVersion: number,
): Promise<{ revision: CadIntentRevision }> {
  return apiPost<{ baseProjectVersion: number }, { revision: CadIntentRevision }>(
    `/api/v2/projects/${projectId}/cad/revisions/${revisionId}/undo`,
    { baseProjectVersion },
  );
}
