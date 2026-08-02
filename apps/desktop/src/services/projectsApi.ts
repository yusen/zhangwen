import type {
  AnswerQuestionsRequest,
  AnswerQuestionsResponse,
  AddProjectExpertRequest,
  AgentPackageListResponse,
  AgentPackageResponse,
  ArchiveProjectRequest,
  ClaimLegacyProjectsRequest,
  ClaimLegacyProjectsResponse,
  ArtifactFileListResponse,
  ArtifactListResponse,
  ClarifyRequest,
  ClarifyResponse,
  AcceptCodeRequest,
  CadRunResponse,
  CadJobResponse,
  CreateCadJobRequest,
  ConfirmCadRequest,
  ConfirmLessonRequest,
  ConnectDeviceRequest,
  DisconnectDeviceRequest,
  TakeoverDeviceRequest,
  ConfirmSolutionRequest,
  ConfirmSolutionResponse,
  CreateProjectRequest,
  ConfirmProposalRequest,
  ConfirmProposalResponse,
  ConfirmSpecRequest,
  CodeRunResponse,
  DeployCodeRequest,
  DeviceOperationResponse,
  DeviceOperationCancelResponse,
  DeviceSessionResponse,
  DeviceTerminalRequest,
  DeviceTerminalResponse,
  DeviceTerminalUnlockRequest,
  DeviceTerminalUnlockResponse,
  DeviceTerminalWriteRequest,
  DuplicateProjectRequest,
  GenerateProposalRequest,
  GenerateCodeRequest,
  GenerateLessonRequest,
  GenerateSolutionRequest,
  GenerateSpecRequest,
  FirmwareFlashRequest,
  FirmwareCandidateResponse,
  FirmwareFlashPlanResponse,
  FirmwareInspectRequest,
  FirmwarePrepareRequest,
  EspClawEndpointListResponse,
  EspClawEndpointResponse,
  PairEspClawEndpointRequest,
  LessonRunResponse,
  AgentRegistryResponse,
  ApprovalRequest,
  CreateExecutionPlanRequest,
  ExecutionPlanResponse,
  CreateSkillRequest,
  ExportProjectPackageRequest,
  ExportProjectPackageResponse,
  PlanActionRequest,
  ImportProjectPackageRequest,
  ImportProjectPackageResponse,
  ModelRouteRequest,
  ModelRouteResponse,
  ListDevicePortsResponse,
  LegacyProjectClaimStatus,
  MvpReadinessResponse,
  ProjectListResponse,
  ProjectProgressResponse,
  ProjectWorkspaceResponse,
  PermanentDeleteProjectRequest,
  PermanentDeleteProjectResponse,
  ProposalExportFormat,
  ProposalListResponse,
  ProposalResponse,
  RejectProposalRequest,
  RejectProposalResponse,
  RejectCadRequest,
  RejectCodeRequest,
  ReviseCodeRequest,
  RejectLessonRequest,
  RejectSpecRequest,
  RemoveProjectExpertRequest,
  ResetAgentPackageFileRequest,
  RetryCadJobRequest,
  RollbackCodeRequest,
  RestoreSolutionResponse,
  UploadCodeRequest,
  ReviseSolutionRequest,
  ReviseSolutionResponse,
  ReviseProposalRequest,
  SkillRegistryResponse,
  SkillResponse,
  SaveDraftRequest,
  SuggestProjectRequest,
  SuggestProjectResponse,
  SpecRunResponse,
  SolutionListResponse,
  SolutionResponse,
  UpdateProjectRequest,
  UpdateProjectHardwareRequest,
  UpdateProjectHardwareResponse,
  UpdateAgentPackageFileRequest,
  UpdateSkillRequest,
  ValidateCodeRequest,
  WateringSmokeRequest,
  WateringSmokeResponse,
} from "@zhangwen/contracts";
import {
  apiFetch,
  apiGet,
  apiPatch,
  apiPost,
  apiPut,
  apiResponseError,
  apiUrl,
} from "./api";

export function listProjects(
  options: { includeArchived?: boolean } = {}
): Promise<ProjectListResponse> {
  return apiGet<ProjectListResponse>(
    options.includeArchived ? "/api/projects?includeArchived=true" : "/api/projects"
  );
}

export function getLegacyProjectClaimStatus(): Promise<LegacyProjectClaimStatus> {
  return apiGet<LegacyProjectClaimStatus>("/api/projects/legacy-claim/status");
}

export function decideLegacyProjectClaim(
  request: ClaimLegacyProjectsRequest,
): Promise<ClaimLegacyProjectsResponse> {
  return apiPost<ClaimLegacyProjectsRequest, ClaimLegacyProjectsResponse>(
    "/api/projects/legacy-claim",
    request,
  );
}

export function createProject(
  request: CreateProjectRequest
): Promise<ProjectWorkspaceResponse> {
  return apiPost<CreateProjectRequest, ProjectWorkspaceResponse>(
    "/api/projects",
    request
  );
}

export function suggestProject(
  request: SuggestProjectRequest
): Promise<SuggestProjectResponse> {
  return apiPost<SuggestProjectRequest, SuggestProjectResponse>(
    "/api/projects/suggest",
    request
  );
}

export function getProject(projectId: string): Promise<ProjectWorkspaceResponse> {
  return apiGet<ProjectWorkspaceResponse>(`/api/projects/${projectId}`);
}

export function openProject(projectId: string): Promise<ProjectWorkspaceResponse> {
  return apiPost<Record<string, never>, ProjectWorkspaceResponse>(
    `/api/projects/${projectId}/open`,
    {}
  );
}

export function updateProject(
  projectId: string,
  request: UpdateProjectRequest
): Promise<ProjectWorkspaceResponse> {
  return apiPatch<UpdateProjectRequest, ProjectWorkspaceResponse>(
    `/api/projects/${projectId}`,
    request
  );
}

export function updateProjectHardware(
  projectId: string,
  request: UpdateProjectHardwareRequest
): Promise<UpdateProjectHardwareResponse> {
  return apiPut<UpdateProjectHardwareRequest, UpdateProjectHardwareResponse>(
    `/api/projects/${projectId}/hardware`,
    request
  );
}

export function activateProjectExpert(
  projectId: string,
  projectExpertId: string
): Promise<ProjectWorkspaceResponse> {
  return apiPost<Record<string, never>, ProjectWorkspaceResponse>(
    `/api/projects/${projectId}/experts/${projectExpertId}/activate`,
    {}
  );
}

export function addProjectExpert(
  projectId: string,
  request: AddProjectExpertRequest
): Promise<ProjectWorkspaceResponse> {
  return apiPost<AddProjectExpertRequest, ProjectWorkspaceResponse>(
    `/api/projects/${projectId}/experts`,
    request
  );
}

export function removeProjectExpert(
  projectId: string,
  projectExpertId: string,
  request: RemoveProjectExpertRequest
): Promise<ProjectWorkspaceResponse> {
  return apiPost<RemoveProjectExpertRequest, ProjectWorkspaceResponse>(
    `/api/projects/${projectId}/experts/${projectExpertId}/remove`,
    request
  );
}

export function archiveProject(
  projectId: string,
  request: ArchiveProjectRequest
): Promise<ProjectListResponse> {
  return apiPost<ArchiveProjectRequest, ProjectListResponse>(
    `/api/projects/${projectId}/archive`,
    request
  );
}

export function restoreProject(projectId: string): Promise<ProjectListResponse> {
  return apiPost<Record<string, never>, ProjectListResponse>(
    `/api/projects/${projectId}/restore`,
    {}
  );
}

export function duplicateProject(
  projectId: string,
  request: DuplicateProjectRequest = {},
): Promise<ProjectWorkspaceResponse> {
  return apiPost<DuplicateProjectRequest, ProjectWorkspaceResponse>(
    `/api/projects/${projectId}/duplicate`,
    request,
  );
}

export function permanentlyDeleteProject(
  projectId: string,
  request: PermanentDeleteProjectRequest,
): Promise<PermanentDeleteProjectResponse> {
  return apiPost<PermanentDeleteProjectRequest, PermanentDeleteProjectResponse>(
    `/api/projects/${projectId}/permanent-delete`,
    request,
  );
}

export function saveProjectDraft(
  projectId: string,
  request: SaveDraftRequest
): Promise<ProjectWorkspaceResponse> {
  return apiPut<SaveDraftRequest, ProjectWorkspaceResponse>(
    `/api/projects/${projectId}/draft`,
    request
  );
}

export function resolvePendingItem(
  projectId: string,
  pendingItemId: string
): Promise<ProjectWorkspaceResponse> {
  return apiPost<Record<string, never>, ProjectWorkspaceResponse>(
    `/api/projects/${projectId}/pending-items/${pendingItemId}/resolve`,
    {}
  );
}

export function dismissPendingItem(
  projectId: string,
  pendingItemId: string
): Promise<ProjectWorkspaceResponse> {
  return apiPost<Record<string, never>, ProjectWorkspaceResponse>(
    `/api/projects/${projectId}/pending-items/${pendingItemId}/dismiss`,
    {}
  );
}

/* ── ZW-015 Project Packages ── */

export function exportProjectPackage(
  projectId: string,
  request: ExportProjectPackageRequest
): Promise<ExportProjectPackageResponse> {
  return apiPost<ExportProjectPackageRequest, ExportProjectPackageResponse>(
    `/api/projects/${projectId}/package/export`,
    request
  );
}

export function importProjectPackage(
  request: ImportProjectPackageRequest
): Promise<ImportProjectPackageResponse> {
  return apiPost<ImportProjectPackageRequest, ImportProjectPackageResponse>(
    "/api/projects/package/import",
    request
  );
}

/* ── ZW-016 MVP Readiness ── */

export function getMvpReadiness(
  projectId: string
): Promise<MvpReadinessResponse> {
  return apiGet<MvpReadinessResponse>(
    `/api/projects/${projectId}/mvp/readiness`
  );
}

export function getProjectProgress(
  projectId: string
): Promise<ProjectProgressResponse> {
  return apiGet<ProjectProgressResponse>(`/api/projects/${projectId}/progress`);
}

/* ── ZW-004 Clarification ── */

export function clarifyProject(
  projectId: string,
  request: ClarifyRequest
): Promise<ClarifyResponse> {
  return apiPost<ClarifyRequest, ClarifyResponse>(
    `/api/projects/${projectId}/clarify`,
    request
  );
}

export function answerClarification(
  projectId: string,
  request: AnswerQuestionsRequest
): Promise<AnswerQuestionsResponse> {
  return apiPost<AnswerQuestionsRequest, AnswerQuestionsResponse>(
    `/api/projects/${projectId}/clarify/answer`,
    request
  );
}

/* ── ZW-004 Solution ── */

export function listSolutions(
  projectId: string
): Promise<SolutionListResponse> {
  return apiGet<SolutionListResponse>(
    `/api/projects/${projectId}/solution`
  );
}

export function getCurrentSolution(
  projectId: string
): Promise<SolutionResponse> {
  return apiGet<SolutionResponse>(
    `/api/projects/${projectId}/solution/current`
  );
}

export function generateSolution(
  projectId: string,
  request?: GenerateSolutionRequest
): Promise<SolutionResponse> {
  return apiPost<GenerateSolutionRequest | Record<string, never>, SolutionResponse>(
    `/api/projects/${projectId}/solution/generate`,
    request ?? {}
  );
}

export function confirmSolution(
  projectId: string,
  request: ConfirmSolutionRequest
): Promise<ConfirmSolutionResponse> {
  return apiPost<ConfirmSolutionRequest, ConfirmSolutionResponse>(
    `/api/projects/${projectId}/solution/confirm`,
    request
  );
}

export function reviseSolution(
  projectId: string,
  request: ReviseSolutionRequest
): Promise<ReviseSolutionResponse> {
  return apiPost<ReviseSolutionRequest, ReviseSolutionResponse>(
    `/api/projects/${projectId}/solution/revise`,
    request
  );
}

export function restorePreviousSolution(
  projectId: string
): Promise<RestoreSolutionResponse> {
  return apiPost<Record<string, never>, RestoreSolutionResponse>(
    `/api/projects/${projectId}/solution/restore-previous`,
    {}
  );
}

/* ── ZW-006 Proposal ── */

export function listProposals(
  projectId: string
): Promise<ProposalListResponse> {
  return apiGet<ProposalListResponse>(
    `/api/projects/${projectId}/proposal`
  );
}

export function getCurrentProposal(
  projectId: string
): Promise<ProposalResponse> {
  return apiGet<ProposalResponse>(
    `/api/projects/${projectId}/proposal/current`
  );
}

export function generateProposal(
  projectId: string,
  request: GenerateProposalRequest
): Promise<ProposalResponse> {
  return apiPost<GenerateProposalRequest, ProposalResponse>(
    `/api/projects/${projectId}/proposal/generate`,
    request
  );
}

export function reviseProposal(
  projectId: string,
  request: ReviseProposalRequest
): Promise<ProposalResponse> {
  return apiPost<ReviseProposalRequest, ProposalResponse>(
    `/api/projects/${projectId}/proposal/revise`,
    request
  );
}

export function confirmProposal(
  projectId: string,
  request: ConfirmProposalRequest
): Promise<ConfirmProposalResponse> {
  return apiPost<ConfirmProposalRequest, ConfirmProposalResponse>(
    `/api/projects/${projectId}/proposal/confirm`,
    request
  );
}

export function rejectProposal(
  projectId: string,
  request: RejectProposalRequest
): Promise<RejectProposalResponse> {
  return apiPost<RejectProposalRequest, RejectProposalResponse>(
    `/api/projects/${projectId}/proposal/reject`,
    request
  );
}

export function proposalExportUrl(
  projectId: string,
  proposalId: string,
  format: ProposalExportFormat
): string {
  return apiUrl(
    `/api/projects/${projectId}/proposal/${proposalId}/export?format=${format}`
  );
}

/* ── ZW-009 Artifacts ── */

export function listArtifacts(
  projectId: string
): Promise<ArtifactListResponse> {
  return apiGet<ArtifactListResponse>(
    `/api/projects/${projectId}/artifacts`
  );
}

export function getArtifact(
  projectId: string,
  artifactId: string
): Promise<import("@zhangwen/contracts").ArtifactResponse> {
  return apiGet<import("@zhangwen/contracts").ArtifactResponse>(
    `/api/projects/${projectId}/artifacts/${artifactId}`
  );
}

export function listArtifactFiles(
  projectId: string,
  artifactId: string,
  versionId: string,
  signal?: AbortSignal,
): Promise<ArtifactFileListResponse> {
  return apiGet<ArtifactFileListResponse>(
    `/api/projects/${projectId}/artifacts/${artifactId}/versions/${versionId}/files`,
    signal,
  );
}

export async function downloadArtifactFile(
  projectId: string,
  artifactId: string,
  versionId: string,
  fileId: string,
  signal?: AbortSignal,
): Promise<ArrayBuffer> {
  const path = `/api/projects/${projectId}/artifacts/${artifactId}/versions/${versionId}/files/${fileId}`;
  const response = await apiFetch(path, { signal });
  if (!response.ok) throw await apiResponseError(path, response);
  return response.arrayBuffer();
}

/* ── ZW-010 Spec Agent ── */

export function getCurrentSpec(
  projectId: string
): Promise<SpecRunResponse> {
  return apiGet<SpecRunResponse>(
    `/api/projects/${projectId}/spec/current`
  );
}

export function generateSpec(
  projectId: string,
  request: GenerateSpecRequest
): Promise<SpecRunResponse> {
  return apiPost<GenerateSpecRequest, SpecRunResponse>(
    `/api/projects/${projectId}/spec/generate`,
    request
  );
}

export function confirmSpec(
  projectId: string,
  request: ConfirmSpecRequest
): Promise<SpecRunResponse> {
  return apiPost<ConfirmSpecRequest, SpecRunResponse>(
    `/api/projects/${projectId}/spec/confirm`,
    request
  );
}

export function rejectSpec(
  projectId: string,
  request: RejectSpecRequest
): Promise<SpecRunResponse> {
  return apiPost<RejectSpecRequest, SpecRunResponse>(
    `/api/projects/${projectId}/spec/reject`,
    request
  );
}

/* ── ZW-011 Code Agent ── */

export function getCurrentCode(
  projectId: string
): Promise<CodeRunResponse> {
  return apiGet<CodeRunResponse>(
    `/api/projects/${projectId}/code/current`
  );
}

export function getCode(
  projectId: string,
  codeRunId: string
): Promise<CodeRunResponse> {
  return apiGet<CodeRunResponse>(
    `/api/projects/${projectId}/code/${codeRunId}`
  );
}

export function importMessageCode(
  projectId: string,
  messageId: string,
): Promise<CodeRunResponse> {
  return apiPost<{ messageId: string }, CodeRunResponse>(
    `/api/projects/${projectId}/code/import-message`,
    { messageId },
  );
}

export function reviseCode(
  projectId: string,
  codeRunId: string,
  request: ReviseCodeRequest
): Promise<CodeRunResponse> {
  return apiPut<ReviseCodeRequest, CodeRunResponse>(
    `/api/projects/${projectId}/code/${codeRunId}`,
    request
  );
}

export function validateCode(
  projectId: string,
  request: ValidateCodeRequest
): Promise<CodeRunResponse> {
  return apiPost<ValidateCodeRequest, CodeRunResponse>(
    `/api/projects/${projectId}/code/validate`,
    request
  );
}

export function generateCode(
  projectId: string,
  request: GenerateCodeRequest
): Promise<CodeRunResponse> {
  return apiPost<GenerateCodeRequest, CodeRunResponse>(
    `/api/projects/${projectId}/code/generate`,
    request
  );
}

export function acceptCode(
  projectId: string,
  request: AcceptCodeRequest
): Promise<CodeRunResponse> {
  return apiPost<AcceptCodeRequest, CodeRunResponse>(
    `/api/projects/${projectId}/code/accept`,
    request
  );
}

export function rejectCode(
  projectId: string,
  request: RejectCodeRequest
): Promise<CodeRunResponse> {
  return apiPost<RejectCodeRequest, CodeRunResponse>(
    `/api/projects/${projectId}/code/reject`,
    request
  );
}

export function rollbackCode(
  projectId: string,
  request: RollbackCodeRequest
): Promise<CodeRunResponse> {
  return apiPost<RollbackCodeRequest, CodeRunResponse>(
    `/api/projects/${projectId}/code/rollback`,
    request
  );
}

/* ── ZW-013 CAD Agent ── */

export function createCadJob(
  projectId: string,
  request: CreateCadJobRequest,
): Promise<CadJobResponse> {
  return apiPost<CreateCadJobRequest, CadJobResponse>(
    `/api/projects/${projectId}/cad/jobs`,
    request,
  );
}

export function getCadJob(
  projectId: string,
  jobId: string,
  signal?: AbortSignal,
): Promise<CadJobResponse> {
  return apiGet<CadJobResponse>(
    `/api/projects/${projectId}/cad/jobs/${jobId}`,
    signal,
  );
}

export async function cancelCadJob(
  projectId: string,
  jobId: string,
): Promise<CadJobResponse> {
  const path = `/api/projects/${projectId}/cad/jobs/${jobId}/cancel`;
  const response = await apiFetch(path, { method: "POST" });
  if (!response.ok) throw await apiResponseError(path, response);
  return response.json() as Promise<CadJobResponse>;
}

export function retryCadJob(
  projectId: string,
  jobId: string,
  request: RetryCadJobRequest = {},
): Promise<CadJobResponse> {
  return apiPost<RetryCadJobRequest, CadJobResponse>(
    `/api/projects/${projectId}/cad/jobs/${jobId}/retry`,
    request,
  );
}

export function getCadRun(
  projectId: string,
  cadRunId: string,
  signal?: AbortSignal,
): Promise<CadRunResponse> {
  return apiGet<CadRunResponse>(
    `/api/projects/${projectId}/cad/runs/${cadRunId}`,
    signal,
  );
}

export function getCurrentCad(
  projectId: string
): Promise<CadRunResponse> {
  return apiGet<CadRunResponse>(
    `/api/projects/${projectId}/cad/current`
  );
}

export function confirmCad(
  projectId: string,
  request: ConfirmCadRequest
): Promise<CadRunResponse> {
  return apiPost<ConfirmCadRequest, CadRunResponse>(
    `/api/projects/${projectId}/cad/confirm`,
    request
  );
}

export function rejectCad(
  projectId: string,
  request: RejectCadRequest
): Promise<CadRunResponse> {
  return apiPost<RejectCadRequest, CadRunResponse>(
    `/api/projects/${projectId}/cad/reject`,
    request
  );
}

/* ── ZW-014 Lesson Agent ── */

export function getCurrentLesson(
  projectId: string
): Promise<LessonRunResponse> {
  return apiGet<LessonRunResponse>(
    `/api/projects/${projectId}/lesson/current`
  );
}

export function generateLesson(
  projectId: string,
  request: GenerateLessonRequest
): Promise<LessonRunResponse> {
  return apiPost<GenerateLessonRequest, LessonRunResponse>(
    `/api/projects/${projectId}/lesson/generate`,
    request
  );
}

export function confirmLesson(
  projectId: string,
  request: ConfirmLessonRequest
): Promise<LessonRunResponse> {
  return apiPost<ConfirmLessonRequest, LessonRunResponse>(
    `/api/projects/${projectId}/lesson/confirm`,
    request
  );
}

export function rejectLesson(
  projectId: string,
  request: RejectLessonRequest
): Promise<LessonRunResponse> {
  return apiPost<RejectLessonRequest, LessonRunResponse>(
    `/api/projects/${projectId}/lesson/reject`,
    request
  );
}

/* ── ZW-012 Devices ── */

export function listDevicePorts(
  projectId: string
): Promise<ListDevicePortsResponse> {
  return apiGet<ListDevicePortsResponse>(
    `/api/projects/${projectId}/devices/ports`,
  );
}

export function getCurrentDeviceSession(
  projectId: string
): Promise<DeviceSessionResponse> {
  return apiGet<DeviceSessionResponse>(
    `/api/projects/${projectId}/devices/session/current`
  );
}

export function getDeviceTerminal(
  projectId: string,
  sessionId: string,
): Promise<DeviceTerminalResponse> {
  return apiGet<DeviceTerminalResponse>(
    `/api/projects/${projectId}/devices/terminal?sessionId=${encodeURIComponent(sessionId)}`,
  );
}

export function startDeviceTerminal(
  projectId: string,
  request: DeviceTerminalRequest,
): Promise<DeviceTerminalResponse> {
  return apiPost<DeviceTerminalRequest, DeviceTerminalResponse>(
    `/api/projects/${projectId}/devices/terminal/start`,
    request,
  );
}

export function stopDeviceTerminal(
  projectId: string,
  request: DeviceTerminalRequest,
): Promise<DeviceTerminalResponse> {
  return apiPost<DeviceTerminalRequest, DeviceTerminalResponse>(
    `/api/projects/${projectId}/devices/terminal/stop`,
    request,
  );
}

export function clearDeviceTerminal(
  projectId: string,
  request: DeviceTerminalRequest,
): Promise<DeviceTerminalResponse> {
  return apiPost<DeviceTerminalRequest, DeviceTerminalResponse>(
    `/api/projects/${projectId}/devices/terminal/clear`,
    request,
  );
}

export function unlockDeviceTerminal(
  projectId: string,
  request: DeviceTerminalUnlockRequest,
): Promise<DeviceTerminalUnlockResponse> {
  return apiPost<DeviceTerminalUnlockRequest, DeviceTerminalUnlockResponse>(
    `/api/projects/${projectId}/devices/terminal/unlock`,
    request,
  );
}

export function writeDeviceTerminal(
  projectId: string,
  request: DeviceTerminalWriteRequest,
): Promise<DeviceTerminalResponse> {
  return apiPost<DeviceTerminalWriteRequest, DeviceTerminalResponse>(
    `/api/projects/${projectId}/devices/terminal/write`,
    request,
  );
}

export function evaluateWateringSmoke(
  projectId: string,
  request: WateringSmokeRequest,
): Promise<WateringSmokeResponse> {
  return apiPost<WateringSmokeRequest, WateringSmokeResponse>(
    `/api/projects/${projectId}/devices/watering-smoke/evaluate`,
    request,
  );
}

export function getLatestDeviceOperation(
  projectId: string,
): Promise<DeviceOperationResponse> {
  return apiGet<DeviceOperationResponse>(
    `/api/projects/${projectId}/devices/operations/latest`,
  );
}

export function connectDevice(
  projectId: string,
  request: ConnectDeviceRequest
): Promise<DeviceSessionResponse> {
  return apiPost<ConnectDeviceRequest, DeviceSessionResponse>(
    `/api/projects/${projectId}/devices/connect`,
    request
  );
}

export function disconnectDevice(
  projectId: string,
  request: DisconnectDeviceRequest,
): Promise<DeviceSessionResponse> {
  return apiPost<DisconnectDeviceRequest, DeviceSessionResponse>(
    `/api/projects/${projectId}/devices/disconnect`,
    request,
  );
}

export function takeoverDevice(
  projectId: string,
  request: TakeoverDeviceRequest,
): Promise<DeviceSessionResponse> {
  return apiPost<TakeoverDeviceRequest, DeviceSessionResponse>(
    `/api/projects/${projectId}/devices/takeover`,
    request,
  );
}

export function uploadCodeToDevice(
  projectId: string,
  request: UploadCodeRequest
): Promise<DeviceOperationResponse> {
  return apiPost<UploadCodeRequest, DeviceOperationResponse>(
    `/api/projects/${projectId}/devices/upload`,
    request
  );
}

export function deployCodeToDevice(
  projectId: string,
  request: DeployCodeRequest,
): Promise<DeviceOperationResponse> {
  return apiPost<DeployCodeRequest, DeviceOperationResponse>(
    `/api/projects/${projectId}/devices/deploy`,
    request,
  );
}

export function listEspClawEndpoints(
  projectId: string,
): Promise<EspClawEndpointListResponse> {
  return apiGet<EspClawEndpointListResponse>(
    `/api/projects/${projectId}/devices/esp-claw/endpoints`,
  );
}

export function pairEspClawEndpoint(
  projectId: string,
  request: PairEspClawEndpointRequest,
): Promise<EspClawEndpointResponse> {
  return apiPost<PairEspClawEndpointRequest, EspClawEndpointResponse>(
    `/api/projects/${projectId}/devices/esp-claw/endpoints/pair`,
    request,
  );
}

export function getDeviceOperation(
  projectId: string,
  operationId: string,
): Promise<DeviceOperationResponse> {
  return apiGet<DeviceOperationResponse>(
    `/api/projects/${projectId}/devices/operations/${operationId}`,
  );
}

export function cancelDeviceOperation(
  projectId: string,
  operationId: string,
): Promise<DeviceOperationCancelResponse> {
  return apiPost<Record<string, never>, DeviceOperationCancelResponse>(
    `/api/projects/${projectId}/devices/operations/${operationId}/cancel`,
    {},
  );
}

export function inspectFirmware(
  projectId: string,
  request: FirmwareInspectRequest,
): Promise<FirmwareCandidateResponse> {
  return apiPost<FirmwareInspectRequest, FirmwareCandidateResponse>(
    `/api/projects/${projectId}/devices/firmware/inspect`,
    request,
  );
}

export function prepareFirmware(
  projectId: string,
  request: FirmwarePrepareRequest,
): Promise<FirmwareFlashPlanResponse> {
  return apiPost<FirmwarePrepareRequest, FirmwareFlashPlanResponse>(
    `/api/projects/${projectId}/devices/firmware/prepare`,
    request,
  );
}

export function flashFirmware(
  projectId: string,
  request: FirmwareFlashRequest
): Promise<DeviceOperationResponse> {
  return apiPost<FirmwareFlashRequest, DeviceOperationResponse>(
    `/api/projects/${projectId}/devices/flash`,
    request
  );
}

export const flashFirmwareDryRun = flashFirmware;

/* ── ZW-007 Orchestrator ── */

export function listAgents(): Promise<AgentRegistryResponse> {
  return apiGet<AgentRegistryResponse>("/api/agents");
}

export function getCurrentExecutionPlan(
  projectId: string
): Promise<ExecutionPlanResponse> {
  return apiGet<ExecutionPlanResponse>(
    `/api/projects/${projectId}/execution-plan/current`
  );
}

export function createExecutionPlan(
  projectId: string,
  request: CreateExecutionPlanRequest
): Promise<ExecutionPlanResponse> {
  return apiPost<CreateExecutionPlanRequest, ExecutionPlanResponse>(
    `/api/projects/${projectId}/execution-plan`,
    request
  );
}

export function startExecutionPlan(
  projectId: string,
  planId: string
): Promise<ExecutionPlanResponse> {
  return apiPost<Record<string, never>, ExecutionPlanResponse>(
    `/api/projects/${projectId}/execution-plan/${planId}/start`,
    {}
  );
}

export function pauseExecutionPlan(
  projectId: string,
  planId: string
): Promise<ExecutionPlanResponse> {
  return apiPost<Record<string, never>, ExecutionPlanResponse>(
    `/api/projects/${projectId}/execution-plan/${planId}/pause`,
    {}
  );
}

export function resumeExecutionPlan(
  projectId: string,
  planId: string
): Promise<ExecutionPlanResponse> {
  return apiPost<Record<string, never>, ExecutionPlanResponse>(
    `/api/projects/${projectId}/execution-plan/${planId}/resume`,
    {}
  );
}

export function retryExecutionPlan(
  projectId: string,
  planId: string,
  request: PlanActionRequest
): Promise<ExecutionPlanResponse> {
  return apiPost<PlanActionRequest, ExecutionPlanResponse>(
    `/api/projects/${projectId}/execution-plan/${planId}/retry`,
    request
  );
}

export function approveExecutionNode(
  projectId: string,
  planId: string,
  request: ApprovalRequest
): Promise<ExecutionPlanResponse> {
  return apiPost<ApprovalRequest, ExecutionPlanResponse>(
    `/api/projects/${projectId}/execution-plan/${planId}/approve`,
    request
  );
}

/* ── ZW-008 Skills and Model Router ── */

export function listSkills(): Promise<SkillRegistryResponse> {
  return apiGet<SkillRegistryResponse>("/api/skills");
}

export function listAgentPackages(): Promise<AgentPackageListResponse> {
  return apiGet<AgentPackageListResponse>("/api/agent-packages");
}

export function getAgentPackage(
  expertType: string
): Promise<AgentPackageResponse> {
  return apiGet<AgentPackageResponse>(`/api/agent-packages/${expertType}`);
}

export function updateAgentPackageFile(
  expertType: string,
  request: UpdateAgentPackageFileRequest
): Promise<AgentPackageResponse> {
  return apiPut<UpdateAgentPackageFileRequest, AgentPackageResponse>(
    `/api/agent-packages/${expertType}/files`,
    request
  );
}

export function resetAgentPackageFile(
  expertType: string,
  request: ResetAgentPackageFileRequest
): Promise<AgentPackageResponse> {
  return apiPost<ResetAgentPackageFileRequest, AgentPackageResponse>(
    `/api/agent-packages/${expertType}/files/reset`,
    request
  );
}

export function createSkill(
  request: CreateSkillRequest
): Promise<SkillResponse> {
  return apiPost<CreateSkillRequest, SkillResponse>("/api/skills", request);
}

export function updateSkill(
  skillId: string,
  request: UpdateSkillRequest
): Promise<SkillResponse> {
  return apiPatch<UpdateSkillRequest, SkillResponse>(
    `/api/skills/${skillId}`,
    request
  );
}

export function routeModel(
  request: ModelRouteRequest
): Promise<ModelRouteResponse> {
  return apiPost<ModelRouteRequest, ModelRouteResponse>(
    "/api/model-router/route",
    request
  );
}
