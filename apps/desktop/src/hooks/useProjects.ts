import { useCallback, useEffect, useRef, useState } from "react";
import type {
  LLMModelId,
  ExpertType,
  ProjectListResponse,
  ProjectSummary,
  ProjectWorkspace,
  RouterOutput,
  ZwError,
} from "@zhangwen/contracts";
import {
  archiveProject,
  addProjectExpert,
  activateProjectExpert,
  createProject,
  dismissPendingItem,
  duplicateProject,
  exportProjectPackage,
  getProject,
  importProjectPackage,
  listProjects,
  openProject,
  permanentlyDeleteProject,
  removeProjectExpert,
  resolvePendingItem,
  restoreProject,
  saveProjectDraft,
  updateProject,
  updateProjectHardware,
} from "../services/projectsApi";

interface WorkspaceState {
  projects: ProjectSummary[];
  archivedProjects: ProjectSummary[];
  activeProjectId: string | null;
  activeWorkspace: ProjectWorkspace | null;
  loading: boolean;
  error: ZwError | null;
  draftSaving: boolean;
  draftSaveError: string | null;
}

const initialState: WorkspaceState = {
  projects: [],
  archivedProjects: [],
  activeProjectId: null,
  activeWorkspace: null,
  loading: true,
  error: null,
  draftSaving: false,
  draftSaveError: null,
};

export interface CreateProjectFromIdeaInput {
  idea: string;
  projectName: string;
  selectedHardwareIds: string[];
  initialExpert: ExpertType;
  participatingExperts: ExpertType[];
  routerResult?: RouterOutput;
  expertSelectionMode: "auto" | "manual";
  idempotencyKey?: string;
}

export function useProjects(defaultModel?: LLMModelId) {
  const [state, setState] = useState<WorkspaceState>(initialState);
  const loadTokenRef = useRef(0);

  const applyList = useCallback((response: ProjectListResponse) => {
    setState((prev) => ({
      ...prev,
      projects: response.projects.filter((project) => !project.archivedAt),
      archivedProjects: response.projects.filter((project) => Boolean(project.archivedAt)),
      activeProjectId: response.activeProjectId,
      loading: false,
      error: null,
    }));
    return response;
  }, []);

  const refreshList = useCallback(async () => {
    const response = await listProjects({ includeArchived: true });
    applyList(response);
    return response;
  }, [applyList]);

  const loadWorkspace = useCallback(async (projectId: string) => {
    const loadToken = ++loadTokenRef.current;
    const response = await getProject(projectId);
    setState((prev) => {
      if (
        loadToken !== loadTokenRef.current ||
        (prev.activeProjectId !== projectId && prev.activeProjectId !== null)
      ) {
        return prev;
      }
      return {
        ...prev,
        activeProjectId: projectId,
        activeWorkspace: response.workspace,
        loading: false,
        error: null,
      };
    });
    return response.workspace;
  }, []);

  useEffect(() => {
    let canceled = false;
    async function load() {
      try {
        const response = await listProjects({ includeArchived: true });
        if (canceled) return;
        applyList(response);
        if (response.activeProjectId) {
          const workspace = await getProject(response.activeProjectId);
          if (!canceled) {
            setState((prev) => ({
              ...prev,
              activeWorkspace: workspace.workspace,
              loading: false,
            }));
          }
        }
      } catch (error) {
        if (!canceled) {
          setState((prev) => ({
            ...prev,
            loading: false,
            error: toZwError(error),
          }));
        }
      }
    }
    void load();
    return () => {
      canceled = true;
    };
  }, [applyList]);

  const create = useCallback(
    async (input: CreateProjectFromIdeaInput) => {
      const response = await createProject({
        name: input.projectName,
        initialIdea: input.idea,
        selectedHardwareIds: input.selectedHardwareIds,
        selectedExpertTypes: input.participatingExperts,
        initialExpert: input.initialExpert,
        routerResult: input.routerResult,
        expertSelectionMode: input.expertSelectionMode,
        idempotencyKey: input.idempotencyKey,
        selectedModel: defaultModel,
      });
      loadTokenRef.current += 1;
      setState((prev) => ({
        ...prev,
        activeProjectId: response.workspace.project.id,
        activeWorkspace: response.workspace,
        loading: false,
        error: null,
      }));
      await refreshList();
      setState((prev) => ({
        ...prev,
        activeProjectId: response.workspace.project.id,
        activeWorkspace: response.workspace,
      }));
      return response.workspace;
    },
    [defaultModel, refreshList]
  );

  const open = useCallback(async (projectId: string) => {
    const response = await openProject(projectId);
    setState((prev) => ({
      ...prev,
      activeProjectId: projectId,
      activeWorkspace: response.workspace,
    }));
    void refreshList();
    return response.workspace;
  }, [refreshList]);

  const rename = useCallback(async (projectId: string, name: string) => {
    const response = await updateProject(projectId, { name });
    setState((prev) => ({
      ...prev,
      activeWorkspace: response.workspace,
    }));
    await refreshList();
    return response.workspace;
  }, [refreshList]);

  const setModel = useCallback(async (projectId: string, selectedModel: LLMModelId) => {
    const response = await updateProject(projectId, { selectedModel });
    setState((prev) => ({
      ...prev,
      activeWorkspace: response.workspace,
    }));
    await refreshList();
    return response.workspace;
  }, [refreshList]);

  const setHardware = useCallback(
    async (projectId: string, selectedHardwareIds: string[]) => {
      const response = await updateProjectHardware(projectId, {
        selectedHardwareIds,
      });
      setState((prev) => ({
        ...prev,
        activeWorkspace:
          prev.activeProjectId === projectId
            ? response.workspace
            : prev.activeWorkspace,
      }));
      void refreshList();
      return response;
    },
    [refreshList],
  );

  const activateExpert = useCallback(async (projectId: string, projectExpertId: string) => {
    const response = await activateProjectExpert(projectId, projectExpertId);
    setState((prev) => ({
      ...prev,
      activeProjectId: projectId,
      activeWorkspace: response.workspace,
    }));
    void refreshList();
    return response.workspace;
  }, [refreshList]);

  const addExpert = useCallback(
    async (projectId: string, expertType: ExpertType, activate = false) => {
      const response = await addProjectExpert(projectId, { expertType, activate });
      setState((prev) => ({
        ...prev,
        activeProjectId: projectId,
        activeWorkspace: response.workspace,
      }));
      void refreshList();
      return response.workspace;
    },
    [refreshList]
  );

  const removeExpert = useCallback(
    async (projectId: string, projectExpertId: string) => {
      const response = await removeProjectExpert(projectId, projectExpertId, {
        confirmImpact: true,
      });
      setState((prev) => ({
        ...prev,
        activeProjectId: projectId,
        activeWorkspace: response.workspace,
      }));
      void refreshList();
      return response.workspace;
    },
    [refreshList]
  );

  const archive = useCallback(async (projectId: string) => {
    const response = await archiveProject(projectId, { archived: true });
    loadTokenRef.current += 1;
    setState((prev) => ({
      ...prev,
      projects: response.projects,
      activeProjectId: response.activeProjectId,
      activeWorkspace:
        prev.activeProjectId === projectId ? null : prev.activeWorkspace,
    }));
    if (response.activeProjectId) {
      await loadWorkspace(response.activeProjectId);
    }
    await refreshList();
  }, [loadWorkspace, refreshList]);

  const restore = useCallback(async (projectId: string) => {
    const response = await restoreProject(projectId);
    loadTokenRef.current += 1;
    setState((prev) => ({
      ...prev,
      projects: response.projects,
      activeProjectId: response.activeProjectId,
      activeWorkspace:
        prev.activeProjectId === response.activeProjectId
          ? prev.activeWorkspace
          : null,
    }));
    if (response.activeProjectId) {
      await loadWorkspace(response.activeProjectId);
    }
    await refreshList();
  }, [loadWorkspace, refreshList]);

  const duplicate = useCallback(async (projectId: string, name?: string) => {
    const response = await duplicateProject(projectId, name ? { name } : {});
    loadTokenRef.current += 1;
    setState((prev) => ({
      ...prev,
      activeProjectId: response.workspace.project.id,
      activeWorkspace: response.workspace,
      loading: false,
      error: null,
    }));
    await refreshList();
    setState((prev) => ({
      ...prev,
      activeProjectId: response.workspace.project.id,
      activeWorkspace: response.workspace,
    }));
    return response.workspace;
  }, [refreshList]);

  const permanentDelete = useCallback(async (
    projectId: string,
    confirmationName: string,
  ) => {
    const response = await permanentlyDeleteProject(projectId, { confirmationName });
    applyList({
      projects: response.projects,
      activeProjectId: response.activeProjectId ?? null,
    });
    return response;
  }, [applyList]);

  const saveDraft = useCallback(async (
    projectId: string,
    content: string,
    projectExpertId?: string | null
  ) => {
    setState((prev) => ({ ...prev, draftSaving: true, draftSaveError: null }));
    try {
      const response = await saveProjectDraft(projectId, { content, projectExpertId });
      setState((prev) => ({
        ...prev,
        activeWorkspace:
          prev.activeProjectId === projectId
            ? response.workspace
            : prev.activeWorkspace,
        draftSaving: false,
        draftSaveError: null,
      }));
      void refreshList();
      return response.workspace;
    } catch {
      const message = "草稿保存失败，请检查本地服务后重试。";
      setState((prev) => ({
        ...prev,
        draftSaving: false,
        draftSaveError: message,
      }));
      throw new Error(message);
    }
  }, [refreshList]);

  const resolvePending = useCallback(
    async (projectId: string, pendingItemId: string) => {
      const response = await resolvePendingItem(projectId, pendingItemId);
      setState((prev) => ({
        ...prev,
        activeWorkspace:
          prev.activeProjectId === projectId
            ? response.workspace
            : prev.activeWorkspace,
      }));
      void refreshList();
      return response.workspace;
    },
    [refreshList]
  );

  const dismissPending = useCallback(
    async (projectId: string, pendingItemId: string) => {
      const response = await dismissPendingItem(projectId, pendingItemId);
      setState((prev) => ({
        ...prev,
        activeWorkspace:
          prev.activeProjectId === projectId
            ? response.workspace
            : prev.activeWorkspace,
      }));
      void refreshList();
      return response.workspace;
    },
    [refreshList]
  );

  const exportPackage = useCallback(async (projectId: string) => {
    const response = await exportProjectPackage(projectId, {});
    void refreshList();
    return response.package;
  }, [refreshList]);

  const importPackage = useCallback(async (zipBase64: string) => {
    const response = await importProjectPackage({
      zipBase64,
      conflictStrategy: "CREATE_COPY",
    });
    await refreshList();
    setState((prev) => ({
      ...prev,
      activeProjectId: response.workspace.project.id,
      activeWorkspace: response.workspace,
      loading: false,
      error: null,
    }));
    return response;
  }, [refreshList]);

  const replaceWorkspace = useCallback((workspace: ProjectWorkspace) => {
    setState((prev) => ({
      ...prev,
      activeWorkspace: workspace,
      activeProjectId: workspace.project.id,
    }));
  }, []);

  const dismissError = useCallback(() => {
    setState((prev) => ({ ...prev, error: null }));
  }, []);

  return {
    ...state,
    create,
    open,
    rename,
    setModel,
    setHardware,
    activateExpert,
    addExpert,
    removeExpert,
    archive,
    restore,
    duplicate,
    permanentDelete,
    saveDraft,
    resolvePending,
    dismissPending,
    exportPackage,
    importPackage,
    refreshList,
    loadWorkspace,
    replaceWorkspace,
    dismissError,
  };
}

function toZwError(error: unknown): ZwError {
  return {
    code: "SIDECAR_UNAVAILABLE",
    message: error instanceof Error ? error.message : "本地服务不可用。",
    userActions: [{ id: "retry", label: "重试" }],
    retryable: true,
  };
}
