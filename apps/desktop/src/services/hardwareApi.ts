import type {
  ComponentListResponse,
  ComponentResponse,
  HardwareComponentPackageResponse,
  HardwareSkillDraftResponse,
  HardwareCatalogRefreshResponse,
  HardwareSkillListResponse,
  HardwareSkillResponse,
  BoardProfileListResponse,
  BoardProfileResponse,
  ConfirmMechanicalProfileLinkRequest,
  GenerateMechanicalProfilePreviewRequest,
  MechanicalProfileLinkResponse,
  MechanicalProfileListResponse,
  MechanicalProfilePreviewGenerationResponse,
  RemoveMechanicalProfileLinkResponse,
  ResetBoardProfileRequest,
  UpdateBoardProfileRequest,
  CreateComponentRequest,
  CreateHardwareSkillDraftRequest,
  ContinueHardwareSkillDraftRequest,
  ConfirmHardwareSkillDraftRequest,
  UpdateComponentRequest,
  UpdateHardwareComponentPackageFileRequest,
  UpdateHardwareSkillFileRequest,
  UpdateHardwareSkillFilesRequest,
  ValidateCombinationResponse,
} from "@zhangwen/contracts";
import { apiDelete, apiFetch, apiGet, apiPost, apiPut } from "./api";

export function listHardware(
  category?: string,
  search?: string,
): Promise<ComponentListResponse> {
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  if (search) params.set("search", search);
  const query = params.toString();
  return apiGet<ComponentListResponse>(
    `/api/hardware${query ? `?${query}` : ""}`,
  );
}

export function getHardware(componentId: string): Promise<ComponentResponse> {
  return apiGet<ComponentResponse>(`/api/hardware/${componentId}`);
}

export function createHardware(
  request: CreateComponentRequest,
): Promise<ComponentResponse> {
  return apiPost<CreateComponentRequest, ComponentResponse>(
    "/api/hardware",
    request,
  );
}

export function updateHardware(
  componentId: string,
  request: UpdateComponentRequest,
): Promise<ComponentResponse> {
  return apiPut<UpdateComponentRequest, ComponentResponse>(
    `/api/hardware/${componentId}`,
    request,
  );
}

export function archiveHardware(
  componentId: string,
): Promise<ComponentResponse> {
  return apiDelete<ComponentResponse>(`/api/hardware/${componentId}`);
}

export function getHardwareComponentPackage(
  componentId: string,
): Promise<HardwareComponentPackageResponse> {
  return apiGet<HardwareComponentPackageResponse>(
    `/api/hardware/components/${encodeURIComponent(componentId)}/package`,
  );
}

export function updateHardwareComponentPackageFile(
  componentId: string,
  request: UpdateHardwareComponentPackageFileRequest,
): Promise<HardwareComponentPackageResponse> {
  return apiPut<
    UpdateHardwareComponentPackageFileRequest,
    HardwareComponentPackageResponse
  >(
    `/api/hardware/components/${encodeURIComponent(componentId)}/package/files`,
    request,
  );
}

export function listHardwareSkills(): Promise<HardwareSkillListResponse> {
  return apiGet<HardwareSkillListResponse>("/api/hardware/skills");
}

export function refreshHardwareCatalog(): Promise<HardwareCatalogRefreshResponse> {
  return apiPost<Record<string, never>, HardwareCatalogRefreshResponse>(
    "/api/hardware/catalog/refresh",
    {},
  );
}

export function getHardwareSkill(skillName: string): Promise<HardwareSkillResponse> {
  return apiGet<HardwareSkillResponse>(
    `/api/hardware/skills/${encodeURIComponent(skillName)}`,
  );
}

export function updateHardwareSkillFile(
  skillName: string,
  request: UpdateHardwareSkillFileRequest,
): Promise<HardwareSkillResponse> {
  return apiPut<UpdateHardwareSkillFileRequest, HardwareSkillResponse>(
    `/api/hardware/skills/${encodeURIComponent(skillName)}/files`,
    request,
  );
}

export function updateHardwareSkillFiles(
  skillName: string,
  request: UpdateHardwareSkillFilesRequest,
): Promise<HardwareSkillResponse> {
  return apiPut<UpdateHardwareSkillFilesRequest, HardwareSkillResponse>(
    `/api/hardware/skills/${encodeURIComponent(skillName)}/files/batch`,
    request,
  );
}

export function createHardwareSkillDraft(
  request: CreateHardwareSkillDraftRequest,
): Promise<HardwareSkillDraftResponse> {
  return apiPost<CreateHardwareSkillDraftRequest, HardwareSkillDraftResponse>(
    "/api/hardware/skills/drafts",
    request,
  );
}

export function continueHardwareSkillDraft(
  draftId: string,
  request: ContinueHardwareSkillDraftRequest,
): Promise<HardwareSkillDraftResponse> {
  return apiPost<ContinueHardwareSkillDraftRequest, HardwareSkillDraftResponse>(
    `/api/hardware/skills/drafts/${encodeURIComponent(draftId)}/messages`,
    request,
  );
}

export function confirmHardwareSkillDraft(
  draftId: string,
  request: ConfirmHardwareSkillDraftRequest,
): Promise<HardwareSkillResponse> {
  return apiPost<ConfirmHardwareSkillDraftRequest, HardwareSkillResponse>(
    `/api/hardware/skills/drafts/${encodeURIComponent(draftId)}/confirm`,
    request,
  );
}

export async function deleteHardwareSkillDraft(draftId: string): Promise<void> {
  const response = await apiFetch(
    `/api/hardware/skills/drafts/${encodeURIComponent(draftId)}`,
    { method: "DELETE" },
  );
  if (!response.ok) {
    throw new Error(`取消 Hardware Skill 草稿失败（HTTP ${response.status}）。`);
  }
}

export function validateHardware(
  componentIds: string[],
): Promise<ValidateCombinationResponse> {
  return apiPost<{ componentIds: string[] }, ValidateCombinationResponse>(
    "/api/hardware/validate",
    { componentIds },
  );
}

export function listBoardProfiles(): Promise<BoardProfileListResponse> {
  return apiGet<BoardProfileListResponse>("/api/hardware/board-profiles");
}

export function getBoardProfile(profileId: string): Promise<BoardProfileResponse> {
  return apiGet<BoardProfileResponse>(`/api/hardware/board-profiles/${profileId}`);
}

export function updateBoardProfile(
  profileId: string,
  request: UpdateBoardProfileRequest,
): Promise<BoardProfileResponse> {
  return apiPut<UpdateBoardProfileRequest, BoardProfileResponse>(
    `/api/hardware/board-profiles/${profileId}`,
    request,
  );
}

export function resetBoardProfile(
  profileId: string,
  request: ResetBoardProfileRequest,
): Promise<BoardProfileResponse> {
  return apiPost<ResetBoardProfileRequest, BoardProfileResponse>(
    `/api/hardware/board-profiles/${profileId}/reset`,
    request,
  );
}

export function listMechanicalProfiles(): Promise<MechanicalProfileListResponse> {
  return apiGet<MechanicalProfileListResponse>("/api/hardware/mechanical-profiles");
}

export function generateMechanicalProfilePreview(
  profileId: string,
  request: GenerateMechanicalProfilePreviewRequest,
): Promise<MechanicalProfilePreviewGenerationResponse> {
  return apiPost<
    GenerateMechanicalProfilePreviewRequest,
    MechanicalProfilePreviewGenerationResponse
  >(
    `/api/hardware/mechanical-profiles/${encodeURIComponent(profileId)}/preview`,
    request,
  );
}

export function confirmMechanicalProfileLink(
  componentId: string,
  request: ConfirmMechanicalProfileLinkRequest,
): Promise<MechanicalProfileLinkResponse> {
  return apiPut<ConfirmMechanicalProfileLinkRequest, MechanicalProfileLinkResponse>(
    `/api/hardware/${encodeURIComponent(componentId)}/mechanical-profile-link`,
    request,
  );
}

export function removeMechanicalProfileLink(
  componentId: string,
): Promise<RemoveMechanicalProfileLinkResponse> {
  return apiDelete<RemoveMechanicalProfileLinkResponse>(
    `/api/hardware/${encodeURIComponent(componentId)}/mechanical-profile-link`,
  );
}
