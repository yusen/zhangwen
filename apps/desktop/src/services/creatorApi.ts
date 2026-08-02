import type {
  CreateCreatorWorkRequest,
  CreatorCommand,
  CreatorCommandRequest,
  CreatorCommandResponse,
  CreatorJobCommand,
  CreatorJobCommandRequest,
  CreatorJobCommandResponse,
  CreateCreatorDeliveryRequest,
  CreatorDeliveryRecord,
  CreatorWorkListResponse,
  CreatorWorkspaceResponse,
  CreatePhysicalRunRequest,
  DevicePackageRevision,
  PhysicalRunReport,
  ImportCreatorDeliveryRequest,
  ImportCreatorDeliveryResponse,
  CompleteReproductionRequest,
  ReproductionReport,
  CreatorImportContext,
  CompleteImportedReproductionRequest,
} from "@zhangwen/contracts";
import { apiGet, apiPost } from "./api";

export function listCreatorWorks(includeArchived = true): Promise<CreatorWorkListResponse> {
  return apiGet<CreatorWorkListResponse>(
    includeArchived ? "/api/creator/works?includeArchived=true" : "/api/creator/works",
  );
}

export function createCreatorWork(
  request: CreateCreatorWorkRequest,
): Promise<CreatorWorkspaceResponse> {
  return apiPost<CreateCreatorWorkRequest, CreatorWorkspaceResponse>(
    "/api/creator/works",
    request,
  );
}

export function getCreatorWorkspace(workId: string): Promise<CreatorWorkspaceResponse> {
  return apiGet<CreatorWorkspaceResponse>(`/api/creator/works/${encodeURIComponent(workId)}/workspace`);
}

export function executeCreatorCommand(
  workId: string,
  command: CreatorCommand,
  request: CreatorCommandRequest,
): Promise<CreatorCommandResponse> {
  return apiPost<CreatorCommandRequest, CreatorCommandResponse>(
    `/api/creator/works/${encodeURIComponent(workId)}/commands/${command}`,
    request,
  );
}

export function executeCreatorJobCommand(
  workId: string,
  jobId: string,
  command: CreatorJobCommand,
  request: CreatorJobCommandRequest,
): Promise<CreatorJobCommandResponse> {
  return apiPost<CreatorJobCommandRequest, CreatorJobCommandResponse>(
    `/api/creator/works/${encodeURIComponent(workId)}/jobs/${encodeURIComponent(jobId)}/commands/${command}`,
    request,
  );
}

export function listCreatorDevicePackages(): Promise<{ packages: DevicePackageRevision[] }> {
  return apiGet<{ packages: DevicePackageRevision[] }>("/api/creator/device-packages");
}

export function createCreatorPhysicalRun(
  workId: string,
  request: CreatePhysicalRunRequest,
): Promise<{ run: PhysicalRunReport }> {
  return apiPost<CreatePhysicalRunRequest, { run: PhysicalRunReport }>(
    `/api/creator/works/${encodeURIComponent(workId)}/physical-runs`,
    request,
  );
}

export function createCreatorDelivery(
  workId: string,
  request: CreateCreatorDeliveryRequest,
): Promise<{ delivery: CreatorDeliveryRecord }> {
  return apiPost<CreateCreatorDeliveryRequest, { delivery: CreatorDeliveryRecord }>(
    `/api/creator/works/${encodeURIComponent(workId)}/deliveries`,
    request,
  );
}

export function importCreatorDelivery(
  request: ImportCreatorDeliveryRequest,
): Promise<ImportCreatorDeliveryResponse> {
  return apiPost<ImportCreatorDeliveryRequest, ImportCreatorDeliveryResponse>(
    "/api/creator/deliveries/import",
    request,
  );
}

export function completeCreatorReproduction(
  workId: string,
  request: CompleteReproductionRequest,
): Promise<{ report: ReproductionReport; workspace: import("@zhangwen/contracts").CreatorWorkspace }> {
  return apiPost<
    CompleteReproductionRequest,
    { report: ReproductionReport; workspace: import("@zhangwen/contracts").CreatorWorkspace }
  >(
    `/api/creator/works/${encodeURIComponent(workId)}/reproductions`,
    request,
  );
}

export function getCreatorImportContext(
  workId: string,
): Promise<{ context: CreatorImportContext | null }> {
  return apiGet<{ context: CreatorImportContext | null }>(
    `/api/creator/works/${encodeURIComponent(workId)}/import-context`,
  );
}

export function completeImportedCreatorReproduction(
  workId: string,
  request: CompleteImportedReproductionRequest,
): Promise<{ report: ReproductionReport; workspace: import("@zhangwen/contracts").CreatorWorkspace }> {
  return apiPost<
    CompleteImportedReproductionRequest,
    { report: ReproductionReport; workspace: import("@zhangwen/contracts").CreatorWorkspace }
  >(
    `/api/creator/works/${encodeURIComponent(workId)}/reproduction-receipt`,
    request,
  );
}
