import type {
  ApplyParameterSetRequest,
  CreateDeviceLabRunRequest,
  DeviceBoardListResponse,
  DeviceLabEvent,
  DeviceLabSceneResponse,
  DeviceLabRunResponse,
  FirmwareApplicationListResponse,
  FirmwareApplicationInstallPlanResponse,
  FirmwareApplicationInstallPrepareRequest,
  FirmwareApplicationInstallRequest,
  FirmwareApplicationResponse,
  ImportFirmwareApplicationRequest,
  ParameterSetListResponse,
  ParameterSetResponse,
  SaveParameterSetRequest,
  SyncParameterSetRequest,
  UpdateDeviceLabChannelRequest,
  DeviceOperationResponse,
  DeviceSessionResponse,
} from "@zhangwen/contracts";
import { apiFetch, apiGet, apiPost, apiPut } from "./api";

export function listDeviceLabBoards(signal?: AbortSignal): Promise<DeviceBoardListResponse> {
  return apiGet("/api/device-lab/boards", signal);
}

export function getDeviceLabScene(
  projectId: string,
  signal?: AbortSignal,
): Promise<DeviceLabSceneResponse> {
  return apiGet(`/api/projects/${projectId}/device-lab/scene`, signal);
}

export function listFirmwareApplications(
  projectId: string,
  signal?: AbortSignal,
): Promise<FirmwareApplicationListResponse> {
  return apiGet(`/api/projects/${projectId}/device-lab/applications`, signal);
}

export function importFirmwareApplication(
  projectId: string,
  request: ImportFirmwareApplicationRequest,
): Promise<FirmwareApplicationResponse> {
  return apiPost(`/api/projects/${projectId}/device-lab/applications/import`, request);
}

export function getCurrentDeviceLabSession(
  projectId: string,
  signal?: AbortSignal,
): Promise<DeviceSessionResponse> {
  return apiGet(`/api/projects/${projectId}/devices/session/current`, signal);
}

export function prepareFirmwareApplicationInstall(
  projectId: string,
  request: FirmwareApplicationInstallPrepareRequest,
): Promise<FirmwareApplicationInstallPlanResponse> {
  return apiPost(`/api/projects/${projectId}/device-lab/applications/prepare-install`, request);
}

export function installFirmwareApplication(
  projectId: string,
  request: FirmwareApplicationInstallRequest,
): Promise<DeviceOperationResponse> {
  return apiPost(`/api/projects/${projectId}/device-lab/applications/install`, request);
}

export function syncParameterSetToDevice(
  projectId: string,
  parameterSetId: string,
  request: SyncParameterSetRequest,
): Promise<DeviceOperationResponse> {
  return apiPost(
    `/api/projects/${projectId}/device-lab/parameter-sets/${parameterSetId}/sync`,
    request,
  );
}

export function getDeviceLabOperation(
  projectId: string,
  operationId: string,
): Promise<DeviceOperationResponse> {
  return apiGet(`/api/projects/${projectId}/devices/operations/${operationId}`);
}

export function createDeviceLabRun(
  projectId: string,
  request: CreateDeviceLabRunRequest,
): Promise<DeviceLabRunResponse> {
  return apiPost(`/api/projects/${projectId}/device-lab/runs`, request);
}

export function getDeviceLabRun(projectId: string, runId: string): Promise<DeviceLabRunResponse> {
  return apiGet(`/api/projects/${projectId}/device-lab/runs/${runId}`);
}

export function updateDeviceLabChannel(
  projectId: string,
  runId: string,
  channelId: string,
  request: UpdateDeviceLabChannelRequest,
): Promise<DeviceLabRunResponse> {
  return apiPut(
    `/api/projects/${projectId}/device-lab/runs/${runId}/channels/${encodeURIComponent(channelId)}`,
    request,
  );
}

export function stopDeviceLabRun(projectId: string, runId: string): Promise<DeviceLabRunResponse> {
  return apiPost(`/api/projects/${projectId}/device-lab/runs/${runId}/stop`, {});
}

export function listParameterSets(
  projectId: string,
  signal?: AbortSignal,
): Promise<ParameterSetListResponse> {
  return apiGet(`/api/projects/${projectId}/device-lab/parameter-sets`, signal);
}

export function saveParameterSet(
  projectId: string,
  request: SaveParameterSetRequest,
): Promise<ParameterSetResponse> {
  return apiPost(`/api/projects/${projectId}/device-lab/parameter-sets`, request);
}

export function applyParameterSet(
  projectId: string,
  runId: string,
  request: ApplyParameterSetRequest,
): Promise<DeviceLabRunResponse> {
  return apiPost(`/api/projects/${projectId}/device-lab/runs/${runId}/apply-parameters`, request);
}

export async function readDeviceLabEvents(
  projectId: string,
  runId: string,
  afterRevision: number,
  signal?: AbortSignal,
): Promise<DeviceLabEvent[]> {
  const response = await apiFetch(
    `/api/projects/${projectId}/device-lab/runs/${runId}/events?afterRevision=${afterRevision}`,
    { signal },
  );
  if (!response.ok) return [];
  const text = await response.text();
  return text
    .split(/\r?\n/)
    .filter((line) => line.startsWith("data: ") && line !== "data: {}")
    .map((line) => JSON.parse(line.slice(6)) as DeviceLabEvent);
}

export async function fileToBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  const chunkSize = 0x8000;
  let binary = "";
  for (let index = 0; index < bytes.length; index += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(index, index + chunkSize));
  }
  return globalThis.btoa(binary);
}
