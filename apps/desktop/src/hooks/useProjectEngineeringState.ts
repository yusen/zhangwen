import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  CadJobStatus,
  type CadRun,
  type CodeRun,
  type ExecutionPlan,
  type LessonRun,
  type SpecRun,
} from "@zhangwen/contracts";
import { ApiError } from "../services/api";
import {
  getCadJob,
  getCurrentCad,
  getCurrentCode,
  getCurrentExecutionPlan,
  getCurrentLesson,
  getCurrentSpec,
} from "../services/projectsApi";

export interface ProjectEngineeringSnapshot {
  plan: ExecutionPlan | null;
  spec: SpecRun | null;
  code: CodeRun | null;
  cad: CadRun | null;
  lesson: LessonRun | null;
}

export interface ProjectEngineeringState {
  data: ProjectEngineeringSnapshot;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

interface SnapshotState {
  projectId: string | null;
  data: ProjectEngineeringSnapshot;
  loading: boolean;
  error: string | null;
}

const EMPTY_SNAPSHOT: ProjectEngineeringSnapshot = {
  plan: null,
  spec: null,
  code: null,
  cad: null,
  lesson: null,
};

const ACTIVE_CAD_JOB_STATUSES = new Set<string>([
  CadJobStatus.QUEUED,
  CadJobStatus.RUNNING,
  CadJobStatus.CANCEL_REQUESTED,
]);

export function useProjectEngineeringState(
  projectId: string | null,
  refreshRevision: number,
  projectUpdatedAt?: string | null,
): ProjectEngineeringState {
  const requestSequence = useRef(0);
  const [pollError, setPollError] = useState<string | null>(null);
  const [state, setState] = useState<SnapshotState>({
    projectId: null,
    data: EMPTY_SNAPSHOT,
    loading: false,
    error: null,
  });

  const refresh = useCallback(async () => {
    if (!projectId) {
      requestSequence.current += 1;
      setState({
        projectId: null,
        data: EMPTY_SNAPSHOT,
        loading: false,
        error: null,
      });
      return;
    }

    const sequence = ++requestSequence.current;
    setState((current) => ({
      projectId,
      data: current.projectId === projectId ? current.data : EMPTY_SNAPSHOT,
      loading: true,
      error: null,
    }));
    setPollError(null);

    const results = await Promise.allSettled([
      getCurrentExecutionPlan(projectId),
      getCurrentSpec(projectId),
      getCurrentCode(projectId),
      getCurrentCad(projectId),
      getCurrentLesson(projectId),
    ]);
    if (sequence !== requestSequence.current) return;

    setState((current) => {
      const previous = current.projectId === projectId ? current.data : EMPTY_SNAPSHOT;
      const errors: string[] = [];
      const data: ProjectEngineeringSnapshot = {
        plan: readResult(results[0], "plan", "执行计划", previous.plan, errors),
        spec: readResult(results[1], "spec", "工程规格", previous.spec, errors),
        code: readResult(results[2], "codeRun", "代码状态", previous.code, errors),
        cad: readResult(results[3], "cadRun", "CAD 状态", previous.cad, errors),
        lesson: readResult(results[4], "lessonRun", "教案状态", previous.lesson, errors),
      };
      return {
        projectId,
        data,
        loading: false,
        error: errors.length > 0
          ? `工程状态读取失败：${errors.join("；")}。已保留最近一次有效状态。`
          : null,
      };
    });
  }, [projectId]);

  useEffect(() => {
    void refresh();
  }, [projectUpdatedAt, refresh, refreshRevision]);

  const visibleState = state.projectId === projectId
    ? state
    : {
        projectId,
        data: EMPTY_SNAPSHOT,
        loading: Boolean(projectId),
        error: null,
      };
  const activeCadJobId = visibleState.data.cad?.latestJob?.id ?? null;
  const activeCadJobStatus = visibleState.data.cad?.latestJob?.status ?? null;

  useEffect(() => {
    if (
      !projectId ||
      !activeCadJobId ||
      !activeCadJobStatus ||
      !ACTIVE_CAD_JOB_STATUSES.has(activeCadJobStatus)
    ) {
      return;
    }

    const controller = new AbortController();
    let stopped = false;
    let timer = 0;
    const poll = async () => {
      try {
        const response = await getCadJob(projectId, activeCadJobId, controller.signal);
        if (stopped) return;
        setPollError(null);
        if (ACTIVE_CAD_JOB_STATUSES.has(response.cadJob.status)) {
          timer = window.setTimeout(() => void poll(), 700);
          return;
        }
        await refresh();
      } catch (reason) {
        if (stopped || controller.signal.aborted) return;
        setPollError(
          reason instanceof Error ? reason.message : "CAD 任务状态刷新失败，请重试。",
        );
        timer = window.setTimeout(() => void poll(), 1500);
      }
    };
    timer = window.setTimeout(() => void poll(), 350);
    return () => {
      stopped = true;
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [activeCadJobId, activeCadJobStatus, projectId, refresh]);

  return useMemo(
    () => ({
      data: visibleState.data,
      loading: visibleState.loading,
      error: visibleState.error ?? pollError,
      refresh,
    }),
    [pollError, refresh, visibleState.data, visibleState.error, visibleState.loading],
  );
}

function readResult<TResponse, TKey extends keyof TResponse>(
  result: PromiseSettledResult<TResponse>,
  key: TKey,
  label: string,
  previous: TResponse[TKey] | null,
  errors: string[],
): TResponse[TKey] | null {
  if (result.status === "fulfilled") return result.value[key] ?? null;
  if (result.reason instanceof ApiError && result.reason.status === 404) return null;
  errors.push(`${label}${errorMessage(result.reason)}`);
  return previous;
}

function errorMessage(reason: unknown): string {
  if (!(reason instanceof Error)) return "不可用";
  const message = reason.message.trim();
  return message ? `（${message}）` : "不可用";
}
