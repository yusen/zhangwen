import { useCallback, useEffect, useState } from "react";
import type {
  CadIntentPromptRequest,
  CadIntentResult,
  CadIntentWorkspace,
} from "@zhangwen/contracts";
import {
  buildV2CadRevision,
  confirmV2CadRevision,
  getV2CadWorkspace,
  submitV2CadIntent,
  undoV2CadRevision,
} from "../services/v2CadApi";

interface CadWorkspaceState {
  workspace: CadIntentWorkspace | null;
  loading: boolean;
  busy: boolean;
  error: string | null;
  lastResult: CadIntentResult | null;
}

export function useV2CadWorkspace(projectId: string | null) {
  const [revision, setRevision] = useState(0);
  const [state, setState] = useState<CadWorkspaceState>({
    workspace: null,
    loading: false,
    busy: false,
    error: null,
    lastResult: null,
  });

  const refresh = useCallback(() => setRevision((value) => value + 1), []);

  useEffect(() => {
    if (!projectId) {
      setState((current) => ({ ...current, workspace: null, loading: false }));
      return;
    }
    const controller = new AbortController();
    setState((current) => ({ ...current, loading: true, error: null }));
    void getV2CadWorkspace(projectId, controller.signal)
      .then(({ workspace }) =>
        setState((current) => ({ ...current, workspace, loading: false })),
      )
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setState((current) => ({
          ...current,
          loading: false,
          error: error instanceof Error ? error.message : "CAD 工作区加载失败。",
        }));
      });
    return () => controller.abort();
  }, [projectId, revision]);

  const run = useCallback(
    async (operation: () => Promise<CadIntentResult>) => {
      setState((current) => ({ ...current, busy: true, error: null }));
      try {
        const result = await operation();
        setState((current) => ({ ...current, busy: false, lastResult: result }));
        refresh();
        return result;
      } catch (error: unknown) {
        const message = error instanceof Error ? error.message : "CAD 操作失败。";
        setState((current) => ({ ...current, busy: false, error: message }));
        throw error;
      }
    },
    [refresh],
  );

  const submit = useCallback(
    (request: CadIntentPromptRequest) => {
      if (!projectId) return Promise.reject(new Error("请先选择项目。"));
      return run(async () => (await submitV2CadIntent(projectId, request)).result);
    },
    [projectId, run],
  );

  const confirm = useCallback(
    (revisionId: string) => {
      if (!projectId) return Promise.reject(new Error("请先选择项目。"));
      return run(async () => ({
        kind: "revision_confirmed",
        revision: (await confirmV2CadRevision(projectId, revisionId)).revision,
      }));
    },
    [projectId, run],
  );

  const confirmAndBuild = useCallback(
    (revisionId: string) => {
      if (!projectId) return Promise.reject(new Error("请先选择项目。"));
      return run(async () => {
        await confirmV2CadRevision(projectId, revisionId);
        return (await buildV2CadRevision(projectId, revisionId)).result;
      });
    },
    [projectId, run],
  );

  const build = useCallback(
    (revisionId: string) => {
      if (!projectId) return Promise.reject(new Error("请先选择项目。"));
      return run(async () => (await buildV2CadRevision(projectId, revisionId)).result);
    },
    [projectId, run],
  );

  const undo = useCallback(
    (revisionId: string, baseProjectVersion: number) => {
      if (!projectId) return Promise.reject(new Error("请先选择项目。"));
      return run(async () => ({
        kind: "undo_planned",
        revision: (
          await undoV2CadRevision(projectId, revisionId, baseProjectVersion)
        ).revision,
      }));
    },
    [projectId, run],
  );

  return { ...state, refresh, submit, confirm, confirmAndBuild, build, undo };
}
