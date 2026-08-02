import { useCallback, useEffect, useState } from "react";
import {
  CreatorJobCommand,
  type CreateCreatorWorkRequest,
  type CreatorCommand,
  type CreatorCommandRequest,
  type CreatorWorkSummary,
  type CreatorWorkspace,
} from "@zhangwen/contracts";
import {
  createCreatorWork,
  executeCreatorCommand,
  executeCreatorJobCommand,
  getCreatorWorkspace,
  listCreatorWorks,
} from "../../services/creatorApi";

interface CreatorWorksState {
  works: CreatorWorkSummary[];
  workspace: CreatorWorkspace | null;
  loading: boolean;
  error: string | null;
}

export function useCreatorWorks() {
  const [state, setState] = useState<CreatorWorksState>({
    works: [],
    workspace: null,
    loading: true,
    error: null,
  });

  const refresh = useCallback(async () => {
    try {
      const response = await listCreatorWorks(true);
      setState((current) => ({ ...current, works: response.works, loading: false, error: null }));
      return response;
    } catch (error) {
      setState((current) => ({
        ...current,
        loading: false,
        error: error instanceof Error ? error.message : "作品列表加载失败。",
      }));
      throw error;
    }
  }, []);

  useEffect(() => {
    let active = true;

    async function restoreActiveWork() {
      try {
        const response = await listCreatorWorks(true);
        if (!active) return;

        const activeWork = response.activeWorkId
          ? response.works.find((work) => (
              work.id === response.activeWorkId && work.archivedAt === null
            ))
          : undefined;
        if (!activeWork) {
          setState((current) => ({
            ...current,
            works: response.works,
            workspace: null,
            loading: false,
            error: null,
          }));
          return;
        }

        try {
          const workspaceResponse = await getCreatorWorkspace(activeWork.id);
          if (!active) return;
          const workspace = workspaceResponse.workspace;
          setState((current) => ({
            ...current,
            works: response.works,
            workspace: (
              workspace.workId === activeWork.id && workspace.archivedAt === null
                ? workspace
                : null
            ),
            loading: false,
            error: null,
          }));
        } catch (error) {
          if (!active) return;
          setState((current) => ({
            ...current,
            works: response.works,
            workspace: null,
            loading: false,
            error: error instanceof Error ? error.message : "上次打开的作品恢复失败。",
          }));
        }
      } catch (error) {
        if (!active) return;
        setState((current) => ({
          ...current,
          workspace: null,
          loading: false,
          error: error instanceof Error ? error.message : "作品列表加载失败。",
        }));
      }
    }

    void restoreActiveWork();
    return () => { active = false; };
  }, []);

  const open = useCallback(async (workId: string) => {
    setState((current) => ({ ...current, loading: true, error: null }));
    try {
      const response = await getCreatorWorkspace(workId);
      setState((current) => ({ ...current, workspace: response.workspace, loading: false }));
      return response.workspace;
    } catch (error) {
      setState((current) => ({
        ...current,
        loading: false,
        error: error instanceof Error ? error.message : "作品打开失败。",
      }));
      throw error;
    }
  }, []);

  useEffect(() => {
    const workspace = state.workspace;
    if (
      !workspace
      || !workspace.jobs.some((job) => (
        job.status === "QUEUED"
        || job.status === "RUNNING"
      ))
    ) {
      return undefined;
    }
    let active = true;
    let polling = false;
    const timer = globalThis.setInterval(() => {
      if (polling) return;
      polling = true;
      void getCreatorWorkspace(workspace.workId)
        .then((response) => {
          if (
            active
            && response.workspace.workId === workspace.workId
            && response.workspace.archivedAt === null
          ) {
            setState((current) => ({
              ...current,
              workspace: response.workspace,
              error: null,
            }));
          }
        })
        .catch(() => undefined)
        .finally(() => {
          polling = false;
        });
    }, 750);
    return () => {
      active = false;
      globalThis.clearInterval(timer);
    };
  }, [state.workspace]);

  const create = useCallback(async (request: CreateCreatorWorkRequest) => {
    const response = await createCreatorWork(request);
    setState((current) => ({ ...current, workspace: response.workspace, error: null }));
    await refresh();
    setState((current) => ({ ...current, workspace: response.workspace }));
    return response.workspace;
  }, [refresh]);

  const command = useCallback(async (
    workId: string,
    commandName: CreatorCommand,
    request: CreatorCommandRequest,
  ) => {
    const response = await executeCreatorCommand(workId, commandName, request);
    setState((current) => ({ ...current, workspace: response.workspace, error: null }));
    void refresh();
    return response;
  }, [refresh]);

  const cancelJob = useCallback(async (
    workId: string,
    jobId: string,
    idempotencyKey: string,
  ) => {
    const response = await executeCreatorJobCommand(
      workId,
      jobId,
      CreatorJobCommand.CANCEL,
      { idempotencyKey },
    );
    setState((current) => ({
      ...current,
      workspace: response.workspace,
      error: null,
    }));
    return response;
  }, []);

  const retryJob = useCallback(async (
    workId: string,
    jobId: string,
    idempotencyKey: string,
  ) => {
    const response = await executeCreatorJobCommand(
      workId,
      jobId,
      CreatorJobCommand.RETRY,
      { idempotencyKey },
    );
    setState((current) => ({
      ...current,
      workspace: response.workspace,
      error: null,
    }));
    return response;
  }, []);

  const close = useCallback(() => {
    setState((current) => ({ ...current, workspace: null }));
  }, []);

  return { ...state, refresh, open, create, command, cancelJob, retryJob, close };
}
