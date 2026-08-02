import type {
  Capability,
  CapabilityCoverage,
  ChangeSet,
  CreateChangeSetRequest,
  ProjectRelease,
  ProjectState,
  ProjectVersion,
} from "@zhangwen/contracts";
import { apiGet, apiPost } from "./api";

export interface V2ProjectData {
  state: ProjectState;
  changeSets: ChangeSet[];
  versions: ProjectVersion[];
  releases: ProjectRelease[];
  capabilities: Capability[];
  coverage: CapabilityCoverage;
}

export async function getV2ProjectData(
  projectId: string,
  signal?: AbortSignal,
): Promise<V2ProjectData> {
  const [state, changeSets, versions, releases, capabilities, coverage] =
    await Promise.all([
      apiGet<{ state: ProjectState }>(`/api/v2/projects/${projectId}/state`, signal),
      apiGet<{ changeSets: ChangeSet[] }>(
        `/api/v2/projects/${projectId}/changesets`,
        signal,
      ),
      apiGet<{ versions: ProjectVersion[] }>(
        `/api/v2/projects/${projectId}/versions`,
        signal,
      ),
      apiGet<{ releases: ProjectRelease[] }>(
        `/api/v2/projects/${projectId}/releases`,
        signal,
      ),
      apiGet<{ capabilities: Capability[] }>(
        `/api/v2/projects/${projectId}/capabilities`,
        signal,
      ),
      apiGet<{ coverage: CapabilityCoverage }>(
        `/api/v2/projects/${projectId}/capability-coverage`,
        signal,
      ),
    ]);
  return {
    state: state.state,
    changeSets: changeSets.changeSets,
    versions: versions.versions,
    releases: releases.releases,
    capabilities: capabilities.capabilities,
    coverage: coverage.coverage,
  };
}

export function createV2ChangeSet(
  projectId: string,
  request: CreateChangeSetRequest,
): Promise<{ changeSet: ChangeSet }> {
  return apiPost<CreateChangeSetRequest, { changeSet: ChangeSet }>(
    `/api/v2/projects/${projectId}/changesets`,
    request,
  );
}

export function confirmV2ChangeSet(
  projectId: string,
  changeSetId: string,
): Promise<{ changeSet: ChangeSet }> {
  return apiPost<Record<string, never>, { changeSet: ChangeSet }>(
    `/api/v2/projects/${projectId}/changesets/${changeSetId}/confirm`,
    {},
  );
}

export function commitV2ChangeSet(
  projectId: string,
  changeSetId: string,
): Promise<{ version: ProjectVersion }> {
  return apiPost<Record<string, never>, { version: ProjectVersion }>(
    `/api/v2/projects/${projectId}/changesets/${changeSetId}/commit`,
    {},
  );
}
