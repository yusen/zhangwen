import { HealthIndicator } from "../health/HealthIndicator";
import {
  type AuthAccount,
  type Project,
  type ProjectProgressSnapshot,
  type ProjectSummary,
} from "@zhangwen/contracts";
import type { HealthState } from "../../hooks/useHealthCheck";
import { zhCN } from "../../i18n/zh-CN";

interface TopBarProps {
  account?: AuthAccount;
  onLogout?: () => Promise<void> | void;
  health: HealthState;
  sidebarCollapsed: boolean;
  onToggleSidebar: () => void;
  onOpenSettings: () => void;
  onOpenProjectCreate: () => void;
  onOpenProjectTools: () => void;
  onOpenProject: (projectId: string) => Promise<unknown>;
  projects: ProjectSummary[];
  activeProjectId: string | null;
  project: Project | null;
  progress?: ProjectProgressSnapshot | null;
}

export function TopBar({
  account,
  onLogout,
  health,
  sidebarCollapsed,
  onToggleSidebar,
  onOpenSettings,
  onOpenProjectCreate,
  onOpenProjectTools,
  onOpenProject,
  projects,
  activeProjectId,
  project,
  progress,
}: TopBarProps) {
  const sortedProjects = [...projects].sort((left, right) => {
    const leftTime = left.lastOpenedAt ?? left.updatedAt;
    const rightTime = right.lastOpenedAt ?? right.updatedAt;
    return rightTime.localeCompare(leftTime);
  });

  return (
    <header className="top-bar">
      <div className="top-bar-left">
        <button
          className="sidebar-toggle"
          onClick={onToggleSidebar}
          aria-label={sidebarCollapsed ? "展开侧栏" : "折叠侧栏"}
        >
          ☰
        </button>
        <img className="brand-logo" src="/app-logo.png" alt="掌问 Logo" />
        <span className="brand-name">{zhCN.product.name}</span>
        <span className="brand-subtitle">{zhCN.product.subtitle}</span>
      </div>
      <div className="top-bar-center">
        <select
          className="project-switch"
          aria-label="切换项目"
          value={activeProjectId ?? ""}
          disabled={sortedProjects.length === 0}
          onChange={(event) => {
            if (event.target.value) void onOpenProject(event.target.value);
          }}
        >
          <option value="">未选择项目</option>
          {sortedProjects.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
        <span className="project-stage">
          阶段：{progress?.stageLabel ?? (project ? zhCN.projectStages[project.stage as keyof typeof zhCN.projectStages] ?? project.stage : "未开始")}
        </span>
      </div>
      <div className="top-bar-right">
        <HealthIndicator status={health.status} />
        <button
          type="button"
          className="top-bar-icon-command"
          aria-label="新建项目"
          title="新建项目"
          onClick={onOpenProjectCreate}
        >
          +
        </button>
        <button
          type="button"
          className="top-bar-icon-command"
          aria-label="项目工具"
          title="项目工具"
          disabled={!project}
          onClick={onOpenProjectTools}
        >
          ⋯
        </button>
        <div className="top-bar-account" aria-label="当前账号">
          <span
            className="user-avatar"
            title={account?.displayName ?? "用户"}
            aria-hidden="true"
          >
            {account?.displayName.trim().slice(0, 1) || "👤"}
          </span>
          {account && (
            <span className="top-bar-account-name" title={account.username}>
              {account.displayName}
            </span>
          )}
          {onLogout && (
            <button
              type="button"
              className="top-bar-logout"
              aria-label="退出登录"
              title="退出登录"
              onClick={() => void onLogout()}
            >
              退出
            </button>
          )}
        </div>
        <button
          className="settings-gear"
          aria-label="打开设置"
          title="设置"
          onClick={onOpenSettings}
        >
          ⚙
        </button>
      </div>
    </header>
  );
}
