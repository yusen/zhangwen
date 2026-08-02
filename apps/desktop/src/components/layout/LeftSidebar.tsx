import { useRef, useState } from "react";
import type { ProjectSummary, ProjectWorkspace, ZwError } from "@zhangwen/contracts";
import { ConfirmDialog } from "../shared/ConfirmDialog";
import { useDialogFocusTrap } from "../../hooks/useDialogFocusTrap";

interface LeftSidebarProps {
  workspace: ProjectWorkspace | null;
  projects: ProjectSummary[];
  archivedProjects: ProjectSummary[];
  activeProjectId: string | null;
  error: ZwError | null;
  onOpenProjectCreate: () => void;
  onOpenProject: (projectId: string) => Promise<unknown>;
  onArchiveProject: (projectId: string) => Promise<unknown>;
  onRestoreProject: (projectId: string) => Promise<unknown>;
  onPermanentDeleteProject: (
    projectId: string,
    confirmationName: string,
  ) => Promise<{ backupId: string }>;
  onDismissError: () => void;
  onRetryLoad: () => void;
  onCloseDrawer?: () => void;
}

export function LeftSidebar({
  workspace,
  projects,
  archivedProjects,
  activeProjectId,
  error,
  onOpenProjectCreate,
  onOpenProject,
  onArchiveProject,
  onRestoreProject,
  onPermanentDeleteProject,
  onDismissError,
  onRetryLoad,
  onCloseDrawer,
}: LeftSidebarProps) {
  const [archiveTarget, setArchiveTarget] = useState<ProjectSummary | null>(null);
  const [projectActionId, setProjectActionId] = useState<string | null>(null);
  const [projectActionError, setProjectActionError] = useState<string | null>(null);
  const [projectActionMessage, setProjectActionMessage] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ProjectSummary | null>(null);
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const deleteInputRef = useRef<HTMLInputElement>(null);
  const deleteDialogRef = useDialogFocusTrap<HTMLDivElement>(
    deleteTarget !== null,
    () => setDeleteTarget(null),
    {
      closeDisabled: projectActionId !== null,
      initialFocusRef: deleteInputRef,
    },
  );
  const resourceItems = buildProjectResources(workspace);
  const sortedProjects = [...projects].sort((left, right) =>
    (right.lastOpenedAt ?? right.updatedAt).localeCompare(
      left.lastOpenedAt ?? left.updatedAt
    )
  );
  const sortedArchivedProjects = [...archivedProjects].sort((left, right) =>
    right.updatedAt.localeCompare(left.updatedAt)
  );

  const confirmArchive = () => {
    if (!archiveTarget || projectActionId) return;
    const projectId = archiveTarget.id;
    setProjectActionId(projectId);
    setProjectActionError(null);
    setProjectActionMessage(null);
    void onArchiveProject(projectId)
      .catch((reason: unknown) => {
        setProjectActionError(
          reason instanceof Error ? reason.message : "归档项目失败，请稍后重试。"
        );
      })
      .finally(() => {
        setProjectActionId(null);
        setArchiveTarget(null);
      });
  };

  const restore = (projectId: string) => {
    if (projectActionId) return;
    setProjectActionId(projectId);
    setProjectActionError(null);
    setProjectActionMessage(null);
    void onRestoreProject(projectId)
      .catch((reason: unknown) => {
        setProjectActionError(
          reason instanceof Error ? reason.message : "恢复项目失败，请稍后重试。"
        );
      })
      .finally(() => setProjectActionId(null));
  };

  const permanentDelete = () => {
    if (
      !deleteTarget
      || deleteConfirmation !== deleteTarget.name
      || projectActionId
    ) return;
    const projectId = deleteTarget.id;
    setProjectActionId(projectId);
    setProjectActionError(null);
    setProjectActionMessage(null);
    void onPermanentDeleteProject(projectId, deleteConfirmation)
      .then((response) => {
        setProjectActionMessage(`项目已永久删除；可恢复备份：${response.backupId}`);
        setDeleteTarget(null);
        setDeleteConfirmation("");
      })
      .catch((reason: unknown) => {
        setProjectActionError(
          reason instanceof Error ? reason.message : "永久删除失败，项目未发生变化。"
        );
      })
      .finally(() => setProjectActionId(null));
  };

  return (
    <aside className="left-sidebar" data-testid="left-sidebar">
      <div className="sidebar-project-header">
        <h3 className="sidebar-heading">项目</h3>
        <button
          type="button"
          className="sidebar-new-project"
          aria-label="新建项目"
          onClick={onOpenProjectCreate}
        >
          ＋ 新建项目
        </button>
        {onCloseDrawer && (
          <button
            type="button"
            className="drawer-close"
            aria-label="关闭项目抽屉"
            onClick={onCloseDrawer}
          >
            ×
          </button>
        )}
      </div>
      <ul className="sidebar-project-list" aria-label="项目列表">
        {sortedProjects.map((project) => (
          <li key={project.id} className="sidebar-project-row">
            <button
              type="button"
              className={`sidebar-project-open ${
                project.id === activeProjectId ? "workspace-nav-active" : ""
              }`}
              onClick={() => void onOpenProject(project.id)}
            >
              <span>▣</span>
              <strong>{project.name}</strong>
            </button>
            <button
              type="button"
              className="sidebar-project-archive"
              aria-label={`归档项目 ${project.name}`}
              title="归档项目（可随时恢复）"
              disabled={projectActionId !== null}
              onClick={() => setArchiveTarget(project)}
            >
              归档
            </button>
          </li>
        ))}
      </ul>
      {sortedArchivedProjects.length > 0 && (
        <details className="sidebar-archived-projects">
          <summary>已归档项目（{sortedArchivedProjects.length}）</summary>
          <ul aria-label="已归档项目列表">
            {sortedArchivedProjects.map((project) => (
              <li key={project.id}>
                <span title={project.name}>{project.name}</span>
                <button
                  type="button"
                  aria-label={`恢复项目 ${project.name}`}
                  disabled={projectActionId !== null}
                  onClick={() => restore(project.id)}
                >
                  {projectActionId === project.id ? "恢复中..." : "恢复"}
                </button>
                <button
                  type="button"
                  className="danger-action"
                  aria-label={`永久删除项目 ${project.name}`}
                  disabled={projectActionId !== null}
                  onClick={() => {
                    setDeleteConfirmation("");
                    setDeleteTarget(project);
                  }}
                >
                  永久删除
                </button>
              </li>
            ))}
          </ul>
        </details>
      )}
      {projectActionError && (
        <p className="project-create-error" role="alert">
          {projectActionError}
        </p>
      )}
      {projectActionMessage && (
        <p className="project-package-message" role="status">
          {projectActionMessage}
        </p>
      )}
      {workspace ? (
        <div className="sidebar-section project-workspace-nav" aria-label="项目工作区">
          <h4 className="sidebar-subheading">项目资源</h4>
          <ul className="project-resource-list">
            {resourceItems.length === 0 ? (
              <li>暂无项目资源</li>
            ) : (
              resourceItems.map((item) => (
                <li key={item.label}>
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                </li>
              ))
            )}
          </ul>
        </div>
      ) : (
        <div className="sidebar-empty-state">
          <strong>尚未选择项目</strong>
          <span>请从左侧新建项目，或打开已有项目。</span>
        </div>
      )}

      {error && (
        <div className="sidebar-error" role="alert">
          <p>{error.message}</p>
          <div className="sidebar-error-actions">
            {error.retryable && (
              <button type="button" className="error-retry-btn" onClick={onRetryLoad}>
                重试
              </button>
            )}
            <button type="button" className="error-dismiss-btn" onClick={onDismissError}>
              关闭
            </button>
          </div>
        </div>
      )}
      <ConfirmDialog
        open={archiveTarget !== null}
        title="归档项目"
        message={
          archiveTarget
            ? `确定归档项目“${archiveTarget.name}”？项目会从当前列表移入归档，不会永久删除，可随时恢复。`
            : ""
        }
        confirmLabel="归档"
        loading={projectActionId === archiveTarget?.id}
        onConfirm={confirmArchive}
        onCancel={() => setArchiveTarget(null)}
      />
      {deleteTarget && (
        <div
          className="confirm-overlay"
          onClick={() => projectActionId === null && setDeleteTarget(null)}
        >
          <div
            className="confirm-dialog"
            ref={deleteDialogRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="permanent-delete-title"
            tabIndex={-1}
            onClick={(event) => event.stopPropagation()}
          >
            <h3 id="permanent-delete-title" className="confirm-title">永久删除项目</h3>
            <p className="confirm-message">
              系统会先创建可恢复备份。请输入完整项目名“{deleteTarget.name}”确认。
            </p>
            <label className="project-dialog-field">
              <span>项目名称</span>
              <input
                ref={deleteInputRef}
                aria-label="输入项目名称确认永久删除"
                value={deleteConfirmation}
                disabled={projectActionId !== null}
                onChange={(event) => setDeleteConfirmation(event.target.value)}
              />
            </label>
            <div className="confirm-actions">
              <button
                type="button"
                className="secondary-btn"
                disabled={projectActionId !== null}
                onClick={() => setDeleteTarget(null)}
              >
                取消
              </button>
              <button
                type="button"
                className="confirm-btn"
                disabled={
                  projectActionId !== null
                  || deleteConfirmation !== deleteTarget.name
                }
                onClick={permanentDelete}
              >
                {projectActionId === deleteTarget.id ? "正在备份并删除..." : "永久删除"}
              </button>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}

function buildProjectResources(workspace: ProjectWorkspace | null): Array<{
  label: string;
  value: string;
}> {
  if (!workspace) return [];
  const confirmedFacts = workspace.sharedContext?.confirmedFacts?.length ?? 0;
  const activeArtifacts =
    workspace.sharedContext?.activeArtifactVersions?.length ?? 0;
  const decisions = workspace.sharedContext?.decisions?.length ?? 0;
  const resources: Array<{ label: string; value: string }> = [];
  if (confirmedFacts > 0) {
    resources.push({ label: "已确认事实", value: `${confirmedFacts} 条` });
  }
  if (activeArtifacts > 0) {
    resources.push({ label: "项目产物", value: `${activeArtifacts} 个` });
  }
  if (decisions > 0) {
    resources.push({ label: "项目决策", value: `${decisions} 条` });
  }
  return resources;
}
