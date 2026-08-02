import type { ProjectVersion } from "@zhangwen/contracts";
import { stageLabel } from "./labels";

interface ProjectDrawerProject {
  id: string;
  name: string;
  stage: string;
}

interface ProjectDrawerProps {
  projects: ProjectDrawerProject[];
  activeProjectId: string | null;
  versions: ProjectVersion[];
  onSelectProject: (projectId: string) => void;
  onCreateProject: () => void;
  onClose: () => void;
}

export function ProjectDrawer({
  projects,
  activeProjectId,
  versions,
  onSelectProject,
  onCreateProject,
  onClose,
}: ProjectDrawerProps) {
  return (
    <>
      <div className="zw-drawer-backdrop" onClick={onClose} aria-hidden="true" />
      <aside className="zw-project-drawer" role="dialog" aria-modal="true" aria-label="项目与版本">
        <div className="zw-drawer-head">
          <strong>项目与版本</strong>
          <button type="button" className="zw-drawer-close" aria-label="关闭项目面板" onClick={onClose}>×</button>
        </div>
        <div className="zw-drawer-body">
          <section className="zw-drawer-sec" aria-label="项目">
            <span>项目</span>
            <button type="button" className="zw-new-project" onClick={onCreateProject}>＋ 新建项目</button>
            {projects.map((project) => (
              <button
                key={project.id}
                type="button"
                className={`zw-drawer-proj ${project.id === activeProjectId ? "is-active" : ""}`}
                onClick={() => onSelectProject(project.id)}
              >
                <span className="zw-sq" aria-hidden="true">{project.name.slice(0, 1)}</span>
                <span>
                  <strong>{project.name}</strong>
                  <small>{stageLabel(project.stage)}</small>
                </span>
              </button>
            ))}
          </section>
          <section className="zw-drawer-sec" aria-label="版本">
            <span>版本</span>
            {versions.slice(0, 6).map((version) => (
              <button key={version.id} type="button" className="zw-drawer-ver">
                <b>V{version.version}</b>
                <small>{new Date(version.createdAt).toLocaleDateString()}</small>
              </button>
            ))}
            {!versions.length && <p className="zw-drawer-note">确认项目修改后会形成保存记录。</p>}
          </section>
        </div>
      </aside>
    </>
  );
}
