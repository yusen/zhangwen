import { useEffect, useState } from "react";
import {
  ModelRouteStrategy,
  MvpReadinessStatus,
  SkillPermission,
  TaskStatus,
  type ExecutionPlan,
  type ModelRouteResult,
  type PendingItem,
  type ProjectProgressSnapshot,
  type ProjectReadinessDimension,
  type ProjectWorkspace,
  type SkillDefinition,
} from "@zhangwen/contracts";
import {
  getCurrentExecutionPlan,
  listSkills,
  routeModel,
} from "../../services/projectsApi";
import { useHostAdapter } from "../../platform";
import type { ProjectEngineeringState } from "../../hooks/useProjectEngineeringState";
import { LoadingSkeleton } from "../shared/LoadingSkeleton";
import { ErrorRetry } from "../shared/ErrorRetry";
import { zhCN } from "../../i18n/zh-CN";

interface WorkTabProps {
  workspace: ProjectWorkspace | null;
  professionalMode: boolean;
  refreshRevision: number;
  onConfirmationChanged: () => void;
  onOpenArtifact: (artifactId?: string | null, versionId?: string | null) => void;
  engineeringState?: ProjectEngineeringState;
  progress?: ProjectProgressSnapshot | null;
  progressLoading?: boolean;
  progressError?: string | null;
}

export function WorkTab({
  workspace,
  professionalMode,
  refreshRevision,
  engineeringState,
  progress,
  progressLoading = false,
  progressError = null,
}: WorkTabProps) {
  const { capabilities } = useHostAdapter();
  const [fallbackPlan, setFallbackPlan] = useState<ExecutionPlan | null>(null);
  const [skills, setSkills] = useState<SkillDefinition[]>([]);
  const [route, setRoute] = useState<ModelRouteResult | null>(null);
  const projectId = workspace?.project.id ?? null;
  const projectUpdatedAt = workspace?.project.updatedAt ?? null;
  const plan = engineeringState?.data.plan ?? fallbackPlan;

  useEffect(() => {
    if (engineeringState || !projectId) {
      setFallbackPlan(null);
      return;
    }

    let canceled = false;
    void getCurrentExecutionPlan(projectId)
      .then((response) => {
        if (!canceled) setFallbackPlan(response.plan);
      })
      .catch(() => {
        if (!canceled) setFallbackPlan(null);
      });

    return () => {
      canceled = true;
    };
  }, [engineeringState, projectId, projectUpdatedAt, refreshRevision]);

  const awaitingNode = plan?.nodes.find(
    (node) => node.status === TaskStatus.AWAITING_APPROVAL,
  ) ?? null;
  const failedNode = plan?.nodes.find(
    (node) => node.status === TaskStatus.FAILED,
  ) ?? null;
  const activeTask = awaitingNode ?? failedNode ?? plan?.nodes.find(
    (node) => node.status !== TaskStatus.COMPLETED,
  ) ?? null;
  const highlightedPendingItem =
    workspace?.coordinator?.currentPendingItem ??
    workspace?.sharedContext?.currentPendingItem ??
    null;
  const pendingItems = workspace?.coordinator?.pendingItems ?? [];
  const currentNeed = progress?.currentAction?.title
    ?? highlightedPendingItem?.title
    ?? workspace?.coordinator?.currentItem?.title
    ?? activeTask?.title
    ?? "可以继续在中央对话推进项目";

  useEffect(() => {
    if (!professionalMode) return;

    let canceled = false;
    void listSkills()
      .then((response) => {
        if (!canceled) setSkills(response.skills);
      })
      .catch(() => {
        if (!canceled) setSkills([]);
      });
    void routeModel({
      agentId: activeTask?.agentId ?? "orchestrator",
      taskKind: activeTask?.agentId?.replace("-agent", "") ?? "orchestrate",
      strategy: ModelRouteStrategy.BALANCED,
    })
      .then((response) => {
        if (!canceled) setRoute(response.route);
      })
      .catch(() => {
        if (!canceled) setRoute(null);
      });

    return () => {
      canceled = true;
    };
  }, [professionalMode, activeTask?.agentId]);

  if (!workspace) {
    return (
      <div className="work-tab" data-testid="work-tab">
        <h3 className="tab-title">工作状态</h3>
        <p className="tab-description">创建或打开项目后显示基础状态。</p>
      </div>
    );
  }

  return (
    <div className="work-tab" data-testid="work-tab">
      {engineeringState?.error && (
        <ErrorRetry
          message={engineeringState.error}
          onRetry={() => void engineeringState.refresh()}
          retryLabel="重新读取"
        />
      )}

      <ProjectOverview
        workspace={workspace}
        currentNeed={currentNeed}
        currentDescription={progress?.currentAction?.description}
        currentPendingItem={highlightedPendingItem}
        pendingItems={pendingItems}
        plan={plan}
      />

      {professionalMode && (
        <details className="work-secondary-details">
          <summary>工程详情</summary>
          {capabilities.host === "web" && (
            <section className="work-plan-card" aria-label="浏览器宿主能力">
              <div className="work-plan-header">
                <h4>浏览器宿主能力</h4>
                <span className="work-plan-status">本地执行受限</span>
              </div>
              <p className="tab-description">
                浏览器不能执行 Shell、串口、Flash 或本地 CAD。
              </p>
            </section>
          )}
          <ProfessionalPanel skills={skills} route={route} />
        </details>
      )}

      <section className="work-readiness-section" aria-label="MVP 交付就绪度">
        {progressLoading && !progress && (
          <LoadingSkeleton variant="list" lines={3} />
        )}
        {progressError && (
          <ErrorRetry message={progressError} />
        )}
        {progress && (
          <ReadinessSummary
            dimensions={progress.readinessSummary}
          />
        )}
      </section>
    </div>
  );
}

function ProjectOverview({
  workspace,
  currentNeed,
  currentDescription,
  currentPendingItem,
  pendingItems,
  plan,
}: {
  workspace: ProjectWorkspace;
  currentNeed: string;
  currentDescription?: string;
  currentPendingItem: PendingItem | null;
  pendingItems: PendingItem[];
  plan: ExecutionPlan | null;
}) {
  return (
    <section className="work-overview" aria-label="项目总览">
      <div className="work-focus-card">
        <span className="work-current-label">当前需要处理</span>
        <strong>{currentNeed}</strong>
        {currentDescription ? (
          <small>{currentDescription}</small>
        ) : currentPendingItem?.description ? (
          <small>{currentPendingItem.description}</small>
        ) : workspace.coordinator?.currentItem?.description ? (
          <small>{workspace.coordinator.currentItem.description}</small>
        ) : null}
      </div>
      <CompactTaskSummary
        plan={plan}
        pendingItems={pendingItems}
        currentPendingItemId={currentPendingItem?.id ?? null}
      />
    </section>
  );
}

function CompactTaskSummary({
  plan,
  pendingItems,
  currentPendingItemId,
}: {
  plan: ExecutionPlan | null;
  pendingItems: PendingItem[];
  currentPendingItemId: string | null;
}) {
  const waitingItems = pendingItems
    .filter((item) => item.id !== currentPendingItemId)
    .map((item) => ({
      id: `pending-${item.id}`,
      title: item.title,
      detail: item.reason,
      status: "待处理",
    }));
  const activeNodes = (plan?.nodes ?? [])
    .filter(
      (node) =>
        node.status !== TaskStatus.COMPLETED &&
        node.status !== TaskStatus.CANCELED,
    )
    .map((node) => ({
      id: `task-${node.id}`,
      title: node.title,
      detail: node.description,
      status: zhCN.taskStatuses[node.status as keyof typeof zhCN.taskStatuses] ?? node.status,
    }));
  const activeItems = [...waitingItems, ...activeNodes].slice(0, 3);
  const recentlyCompleted = (plan?.nodes ?? [])
    .filter((node) => node.status === TaskStatus.COMPLETED)
    .sort((left, right) =>
      (right.completedAt ?? right.updatedAt).localeCompare(
        left.completedAt ?? left.updatedAt,
      ),
    )[0] ?? null;

  return (
    <section className="work-task-summary" aria-label="任务摘要">
      <div className="work-plan-header">
        <h4>任务摘要</h4>
        {activeItems.length > 0 && <span>{activeItems.length} 项进行中或等待</span>}
      </div>
      {activeItems.length > 0 ? (
        <ul>
          {activeItems.map((item) => (
            <li key={item.id}>
              <div>
                <strong>{item.title}</strong>
                <small>{item.detail}</small>
              </div>
              <span>{item.status}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="tab-description">暂无进行中或等待任务。</p>
      )}
      <div className="work-recent-completion">
        <span>最近完成</span>
        {recentlyCompleted ? (
          <>
            <strong>{recentlyCompleted.title}</strong>
            <small>{recentlyCompleted.description}</small>
          </>
        ) : (
          <small>完成任务后会在这里显示摘要。</small>
        )}
      </div>
    </section>
  );
}

function ReadinessSummary({ dimensions }: { dimensions: ProjectReadinessDimension[] }) {
  const completed = dimensions.filter((item) => item.status === MvpReadinessStatus.READY).length;
  const progress = `${(completed / Math.max(dimensions.length, 1)) * 100}%`;

  return (
    <div className="mvp-readiness-card">
      <div className="mvp-readiness-head">
        <h4>MVP 交付就绪度</h4>
        <strong>{completed} / {dimensions.length}</strong>
      </div>
      <div
        className="mvp-readiness-bar"
        role="progressbar"
        aria-label="MVP 交付进度"
        aria-valuemin={0}
        aria-valuemax={dimensions.length}
        aria-valuenow={completed}
      >
        <span style={{ width: progress }} />
      </div>
      <ul className="mvp-readiness-list" aria-label="MVP 就绪检查项">
        {dimensions.map((item) => {
          const ready = item.status === MvpReadinessStatus.READY;
          const statusLabel = ready
            ? "已就绪"
            : item.status === MvpReadinessStatus.BLOCKED ? "已阻塞" : "待处理";
          return (
          <li key={item.id} data-ready={ready ? "true" : "false"} title={item.message}>
            <span aria-hidden="true">{ready ? "✓" : ""}</span>
            <span>{item.label} · {statusLabel}</span>
          </li>
          );
        })}
      </ul>
    </div>
  );
}

function ProfessionalPanel({
  skills,
  route,
}: {
  skills: SkillDefinition[];
  route: ModelRouteResult | null;
}) {
  const enabled = skills.filter((skill) => skill.enabled).length;
  const highRisk = skills.filter((skill) =>
    skill.permissions.some((permission) =>
      permission === SkillPermission.RUN_SHELL ||
      permission === SkillPermission.USE_DEVICE ||
      permission === SkillPermission.RUN_CAD,
    ),
  ).length;

  return (
    <div className="professional-panel" data-testid="professional-panel">
      <dl className="professional-summary">
        <div>
          <dt>Skill</dt>
          <dd>{enabled}/{skills.length} 启用</dd>
        </div>
        <div>
          <dt>高危权限</dt>
          <dd>{highRisk}</dd>
        </div>
        <div>
          <dt>模型路由</dt>
          <dd>{route ? `${route.provider} · ${route.model}` : "未加载"}</dd>
        </div>
        <div>
          <dt>策略</dt>
          <dd>
            {route
              ? zhCN.modelRouteStrategies[route.strategy as keyof typeof zhCN.modelRouteStrategies] ?? route.strategy
              : "均衡"}
          </dd>
        </div>
      </dl>
    </div>
  );
}
