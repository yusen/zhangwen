import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  CadJobStatus,
  CadRunStatus,
  LessonRunStatus,
  PendingItemActionType,
  PendingItemKind,
  PendingItemPriority,
  PendingItemStatus,
  TaskStatus,
  type CadRun,
  type ExecutionPlan,
  type LessonRun,
  type PendingItem,
  type ProjectWorkspace,
  type SpecRun,
  type TaskNode,
} from "@zhangwen/contracts";
import {
  approveExecutionNode,
  confirmCad,
  confirmLesson,
  createCadJob,
  getCadJob,
  getCurrentCad,
  getCurrentExecutionPlan,
  getCurrentLesson,
  getCurrentSpec,
  rejectCad,
  rejectLesson,
} from "../../services/projectsApi";
import { ApiError } from "../../services/api";
import { useHostAdapter } from "../../platform";
import type { ProjectEngineeringState } from "../../hooks/useProjectEngineeringState";

interface ProjectConfirmationCardProps {
  workspace: ProjectWorkspace;
  onResolvePendingItem: (pendingItemId: string) => Promise<unknown>;
  onDismissPendingItem: (pendingItemId: string) => Promise<unknown>;
  onReloadProject: (projectId: string) => Promise<void>;
  onOpenArtifact: (artifactId?: string | null, versionId?: string | null) => void;
  refreshRevision?: number;
  engineeringState?: ProjectEngineeringState;
}

interface ConfirmationState {
  plan: ExecutionPlan | null;
  spec: SpecRun | null;
  cad: CadRun | null;
  lesson: LessonRun | null;
}

type ConfirmationItem =
  | { kind: "pending"; pending: PendingItem }
  | { kind: "plan"; plan: ExecutionPlan; node: TaskNode }
  | { kind: "cad"; cad: CadRun }
  | { kind: "lesson"; lesson: LessonRun };

const EMPTY_STATE: ConfirmationState = {
  plan: null,
  spec: null,
  cad: null,
  lesson: null,
};

export function ProjectConfirmationCard({
  workspace,
  onResolvePendingItem,
  onDismissPendingItem,
  onReloadProject,
  onOpenArtifact,
  refreshRevision = 0,
  engineeringState,
}: ProjectConfirmationCardProps) {
  const projectId = workspace.project.id;
  const { capabilities, unsupportedMessage } = useHostAdapter();
  const [state, setState] = useState<ConfirmationState>(EMPTY_STATE);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const reloadProjectRef = useRef(onReloadProject);

  useEffect(() => {
    reloadProjectRef.current = onReloadProject;
  }, [onReloadProject]);

  const refresh = useCallback(async () => {
    if (engineeringState) {
      await engineeringState.refresh();
      return;
    }
    const results = await Promise.allSettled([
      getCurrentExecutionPlan(projectId),
      getCurrentSpec(projectId),
      getCurrentCad(projectId),
      getCurrentLesson(projectId),
    ]);
    setState({
      plan: settledValue(results[0], "plan"),
      spec: settledValue(results[1], "spec"),
      cad: settledValue(results[2], "cadRun"),
      lesson: settledValue(results[3], "lessonRun"),
    });
  }, [engineeringState, projectId]);

  useEffect(() => {
    if (engineeringState) return;
    let canceled = false;
    setState(EMPTY_STATE);
    setError(null);
    void Promise.allSettled([
      getCurrentExecutionPlan(projectId),
      getCurrentSpec(projectId),
      getCurrentCad(projectId),
      getCurrentLesson(projectId),
    ]).then((results) => {
      if (canceled) return;
      setState({
        plan: settledValue(results[0], "plan"),
        spec: settledValue(results[1], "spec"),
        cad: settledValue(results[2], "cadRun"),
        lesson: settledValue(results[3], "lessonRun"),
      });
    });
    return () => {
      canceled = true;
    };
  }, [engineeringState, projectId, refreshRevision, workspace.project.updatedAt]);

  const effectiveState = engineeringState?.data ?? state;
  const activeCadRunId = effectiveState.cad?.id ?? null;
  const activeCadJobId = effectiveState.cad?.latestJob?.id ?? null;
  useEffect(() => {
    if (engineeringState) return;
    if (
      !activeCadRunId ||
      !activeCadJobId ||
      !isActiveCadJob(effectiveState.cad?.latestJob?.status)
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
        if (isActiveCadJob(response.cadJob.status)) {
          setState((current) => {
            if (!current.cad || current.cad.id !== activeCadRunId) return current;
            return {
              ...current,
              cad: {
                ...current.cad,
                status: cadRunStatusForJob(response.cadJob.status, current.cad.status),
                latestJob: response.cadJob,
              },
            };
          });
          timer = window.setTimeout(() => void poll(), 700);
          return;
        }

        await reloadProjectRef.current(projectId);
        if (stopped) return;
        setError(null);
        await refresh();
      } catch (reason) {
        if (stopped || controller.signal.aborted) return;
        setError(reason instanceof Error ? reason.message : "CAD 任务状态刷新失败，请重试。");
        timer = window.setTimeout(() => void poll(), 1500);
      }
    };

    timer = window.setTimeout(() => void poll(), 350);
    return () => {
      stopped = true;
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [activeCadJobId, activeCadRunId, effectiveState.cad?.latestJob?.status, engineeringState, projectId, refresh]);

  const item = useMemo(
    () => currentConfirmation(workspace, effectiveState),
    [effectiveState, workspace],
  );
  if (!item) {
    if (!engineeringState?.error) return null;
    return (
      <section className="project-confirmation-card" role="region" aria-label="待确认状态">
        <div className="project-confirmation-heading">
          <small>工程状态</small>
          <h3>待确认事项读取失败</h3>
        </div>
        <p>{engineeringState.error}</p>
        <div className="project-confirmation-actions">
          <button type="button" onClick={() => void engineeringState.refresh()}>
            重新读取
          </button>
        </div>
      </section>
    );
  }

  const content = confirmationContent(item);
  const runAction = async (confirmed: boolean) => {
    if (busy) return;
    if (confirmed && item.kind === "pending" && !capabilities.localToolExecution) {
      setError(`${unsupportedMessage("localToolExecution")} 请在桌面模式确认授权。`);
      return;
    }
    if (item.kind === "cad" && item.cad.status === CadRunStatus.DRAFT && !capabilities.localCadExecution) {
      setError(`${unsupportedMessage("localCadExecution")} 请在桌面模式开始本地建模。`);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await performConfirmation(
        projectId,
        item,
        confirmed,
        onResolvePendingItem,
        onDismissPendingItem,
      );
      await onReloadProject(projectId);
      await refresh();
    } catch (reason) {
      if (reason instanceof ApiError && reason.code === "CAD_INTAKE_REVISED") {
        await onReloadProject(projectId);
        await refresh();
        setError("CAD 结构输入已更新，请使用当前对话中的最新草稿。");
      } else {
        setError(reason instanceof Error ? reason.message : "确认操作失败，请重试。");
      }
    } finally {
      setBusy(false);
    }
  };

  const cad = item.kind === "cad" ? item.cad : null;
  const cadExecutionBlocked =
    cad?.status === CadRunStatus.DRAFT && !capabilities.localCadExecution;
  const cadPreviewBlocked = Boolean(cad?.artifactId && !capabilities.localCadExecution);
  const localExecutionBlocked =
    item.kind === "pending" && !capabilities.localToolExecution;
  const engineeringStateBlocked = Boolean(
    engineeringState?.error && item.kind !== "pending",
  );
  return (
    <section className="central-confirmation-card" aria-label="待你确认">
      <div className="central-confirmation-heading">
        <div>
          <span>待你确认</span>
          <small>{content.kindLabel}</small>
        </div>
        <strong>{content.title}</strong>
      </div>
      <p>{content.description}</p>
      {content.reason && <small className="central-confirmation-reason">{content.reason}</small>}
      <div className="central-confirmation-actions">
        {cad?.artifactId && (
          <button
            type="button"
            className="central-confirmation-secondary"
            disabled={busy || cadPreviewBlocked || engineeringStateBlocked}
            title={cadPreviewBlocked ? unsupportedMessage("localCadExecution") ?? undefined : undefined}
            onClick={() => onOpenArtifact(cad.artifactId, cad.artifactVersionId)}
          >
            查看 3D 模型
          </button>
        )}
        <button
          type="button"
          className="central-confirmation-secondary"
          disabled={busy || engineeringStateBlocked}
          onClick={() => void runAction(false)}
        >
          {content.rejectLabel}
        </button>
        <button
          type="button"
          className="central-confirmation-primary"
          disabled={busy || cadExecutionBlocked || localExecutionBlocked || engineeringStateBlocked}
          onClick={() => void runAction(true)}
        >
          {busy ? "处理中..." : content.confirmLabel}
        </button>
      </div>
      {cadExecutionBlocked && (
        <p className="tab-description" role="status">
          {unsupportedMessage("localCadExecution")} 请在桌面模式开始本地建模。
        </p>
      )}
      {localExecutionBlocked && (
        <p className="tab-description" role="status">
          {unsupportedMessage("localToolExecution")} 请在桌面模式确认授权。
        </p>
      )}
      {cadPreviewBlocked && (
        <p className="tab-description" role="status">
          {unsupportedMessage("localCadExecution")} 当前浏览器不能读取 CAD 二进制模型。
        </p>
      )}
      {engineeringState?.error && (
        <div className="project-create-error" role="alert">
          <span>{engineeringState.error}</span>
          <button
            type="button"
            className="link-button"
            onClick={() => void engineeringState.refresh()}
          >
            重新读取
          </button>
        </div>
      )}
      {error && <p className="project-create-error" role="alert">{error}</p>}
    </section>
  );
}

function isActiveCadJob(status?: string | null): boolean {
  return (
    status === CadJobStatus.QUEUED ||
    status === CadJobStatus.RUNNING ||
    status === CadJobStatus.CANCEL_REQUESTED
  );
}

function cadRunStatusForJob(status: string, fallback: CadRun["status"]): CadRun["status"] {
  if (status === CadJobStatus.QUEUED) return CadRunStatus.QUEUED;
  if (status === CadJobStatus.RUNNING || status === CadJobStatus.CANCEL_REQUESTED) {
    return CadRunStatus.RUNNING;
  }
  if (status === CadJobStatus.CANCELED) return CadRunStatus.CANCELED;
  if (
    status === CadJobStatus.FAILED ||
    status === CadJobStatus.TIMED_OUT ||
    status === CadJobStatus.INTERRUPTED
  ) {
    return CadRunStatus.FAILED;
  }
  return fallback;
}

function currentConfirmation(
  workspace: ProjectWorkspace,
  state: ConfirmationState,
): ConfirmationItem | null {
  const pendingCandidates = [
    workspace.coordinator?.currentPendingItem,
    workspace.sharedContext?.currentPendingItem,
    ...(workspace.coordinator?.pendingItems ?? []),
  ];
  const pending = pendingCandidates.find(isLocalExecutionApproval);
  if (pending) return { kind: "pending", pending };
  const node = state.plan?.nodes.find(
    (candidate) => candidate.status === TaskStatus.AWAITING_APPROVAL,
  );
  if (state.plan && node) return { kind: "plan", plan: state.plan, node };
  if (
    state.cad?.status === CadRunStatus.DRAFT ||
    state.cad?.status === CadRunStatus.READY_FOR_REVIEW
  ) {
    return { kind: "cad", cad: state.cad };
  }
  if (state.lesson?.status === LessonRunStatus.READY_FOR_REVIEW) {
    return { kind: "lesson", lesson: state.lesson };
  }
  return null;
}

function isLocalExecutionApproval(
  pending: PendingItem | null | undefined,
): pending is PendingItem {
  return Boolean(
    pending?.status === PendingItemStatus.OPEN &&
      pending.priority === PendingItemPriority.CONFIRMATION &&
      pending.kind === PendingItemKind.LOCAL_EXECUTION_AUTHORIZATION &&
      pending.actionType === PendingItemActionType.RESUME_SKILL_RUN &&
      pending.authorizationId,
  );
}

function confirmationContent(
  item: ConfirmationItem,
) {
  switch (item.kind) {
    case "pending":
      return {
        kindLabel: "本地执行授权",
        title: "授权本地执行",
        description: "该操作可能产生本地或外部影响，确认后才能继续。",
        reason: "该操作需要你的明确授权，本地执行器不会绕过此确认点。",
        confirmLabel: item.pending.options?.[0] ?? "确认授权",
        rejectLabel: item.pending.options?.[1] ?? "暂不执行",
      };
    case "plan":
      return {
        kindLabel: "执行计划",
        title: item.node.title,
        description: item.node.description,
        reason: "确认后执行计划继续；退回后该节点停止推进。",
        confirmLabel: "确认继续",
        rejectLabel: "退回",
      };
    case "cad":
      if (item.cad.status === CadRunStatus.DRAFT) {
        return {
          kindLabel: "结构建模草稿",
          title: `开始建模 CAD v${item.cad.version}`,
          description: "结构工程师已固化尺寸、安装面和机械约束。确认后由本地受限 CAD Worker 生成真实模型。",
          reason: "建模只使用受信模板和机械档案，不执行模型生成的 Python 或文件路径。",
          confirmLabel: "开始建模",
          rejectLabel: "退回草稿",
        };
      }
      return {
        kindLabel: "结构件 CAD",
        title: `确认 CAD v${item.cad.version}`,
        description: "真实 STEP、STL 与 GLB 已生成并通过几何校验。请先查看 3D 模型，再确认是否作为当前结构版本。",
        reason: null,
        confirmLabel: "确认 CAD",
        rejectLabel: "退回 CAD",
      };
    case "lesson":
      return {
        kindLabel: "课程教案",
        title: `确认教案 v${item.lesson.version}`,
        description: `当前教案包含 ${item.lesson.files.length} 份材料，共 ${item.lesson.lessonHours} 课时。`,
        reason: null,
        confirmLabel: "确认教案",
        rejectLabel: "退回教案",
      };
  }
}

async function performConfirmation(
  projectId: string,
  item: ConfirmationItem,
  confirmed: boolean,
  resolvePending: ProjectConfirmationCardProps["onResolvePendingItem"],
  dismissPending: ProjectConfirmationCardProps["onDismissPendingItem"],
) {
  switch (item.kind) {
    case "pending":
      return confirmed
        ? resolvePending(item.pending.id)
        : dismissPending(item.pending.id);
    case "plan":
      return approveExecutionNode(projectId, item.plan.id, {
        nodeId: item.node.id,
        approved: confirmed,
      });
    case "cad":
      if (item.cad.status === CadRunStatus.DRAFT) {
        return confirmed
          ? createCadJob(projectId, {
              cadRunId: item.cad.id,
              clientRequestId: `cad-start-${item.cad.id}`,
            })
          : rejectCad(projectId, {
              cadRunId: item.cad.id,
              reason: "用户在中央对话退回结构建模草稿。",
            });
      }
      return confirmed
        ? confirmCad(projectId, { cadRunId: item.cad.id })
        : rejectCad(projectId, {
            cadRunId: item.cad.id,
            reason: "用户在中央对话退回结构件 CAD。",
          });
    case "lesson":
      return confirmed
        ? confirmLesson(projectId, { lessonRunId: item.lesson.id })
        : rejectLesson(projectId, {
            lessonRunId: item.lesson.id,
            reason: "用户在中央对话退回课程教案。",
          });
  }
}

function settledValue<T extends object, K extends keyof T>(
  result: PromiseSettledResult<T>,
  key: K,
): T[K] | null {
  return result.status === "fulfilled" ? result.value[key] : null;
}
