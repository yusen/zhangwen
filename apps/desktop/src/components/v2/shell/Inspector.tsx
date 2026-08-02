import { useEffect, useState, type ReactNode } from "react";
import type {
  ArtifactDefinition,
  CadIntentWorkspace,
  ProjectState,
  ProjectWorkspace,
  ToolJob,
} from "@zhangwen/contracts";
import { DevicesTab } from "../../right-panel/DevicesTab";
import { artifactKindLabel, artifactStatusLabel } from "./labels";
import { artifactDisplayTitle } from "../pages/common";

export type InspectorTab = "work" | "artifacts" | "device";

interface InspectorProps {
  open: boolean;
  contextLabel: string;
  contextHint: string;
  tab: InspectorTab;
  onTabChange: (tab: InspectorTab) => void;
  changeSetPanel: ReactNode;
  pendingChangeCount: number;
  facts: ProjectState["facts"];
  professionalMode: boolean;
  artifacts: ArtifactDefinition[];
  onOpenArtifact: (artifactId: string, versionId?: string | null) => void;
  jobs: NonNullable<CadIntentWorkspace["jobs"]>;
  workspace: ProjectWorkspace | null;
  deviceRefreshRevision: number;
  onOpenDeviceLab: () => void;
}

const TABS: Array<{ id: InspectorTab; label: string }> = [
  { id: "work", label: "工作" },
  { id: "artifacts", label: "产物" },
  { id: "device", label: "设备" },
];

export function Inspector({
  open,
  contextLabel,
  contextHint,
  tab,
  onTabChange,
  changeSetPanel,
  pendingChangeCount,
  facts,
  professionalMode,
  artifacts,
  onOpenArtifact,
  jobs,
  workspace,
  deviceRefreshRevision,
  onOpenDeviceLab,
}: InspectorProps) {
  const [deviceVisited, setDeviceVisited] = useState(tab === "device");
  const runningJobs = jobs.filter(
    (job) => job.status === "RUNNING" || job.status === "QUEUED",
  );

  useEffect(() => {
    if (tab === "device") setDeviceVisited(true);
  }, [tab]);

  return (
    <aside className="zw-inspector" aria-label="项目侧栏" hidden={!open}>
      <div className="zw-inspector-head">
        <section className="zw-inspector-ctx" aria-label="当前工作内容">
          <span>当前工作</span>
          <strong>{contextLabel}</strong>
          <p>{contextHint}</p>
        </section>
        <nav className="zw-inspector-tabs" aria-label="右侧功能">
          {TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              aria-current={tab === item.id ? "page" : undefined}
              onClick={() => onTabChange(item.id)}
            >
              {item.label}
              {item.id === "work" && (pendingChangeCount + runningJobs.length) > 0 && (
                <span className="zw-bdg">{pendingChangeCount + runningJobs.length}</span>
              )}
            </button>
          ))}
        </nav>
      </div>
      <div className="zw-inspector-body">
        <div hidden={tab !== "work"}>
          {changeSetPanel ?? (
            <section className="zw-work-summary">
              <strong>项目内容已同步</strong>
              <p>有需要你确认的修改时，会显示在这里。</p>
            </section>
          )}
          <section className="zw-work-summary">
            <strong>已整理 {facts.length} 项信息</strong>
            <p>目标、约束和已选硬件会自动用于后续代码与 3D 设计。</p>
          </section>
          {professionalMode && facts.length > 0 && (
            <ul className="zw-inspector-list">
              {facts.map((fact) => (
                <li key={fact.id}>
                  <span>{fact.label || fact.key}<small>{fact.key}</small></span>
                  <strong>{fact.displayValue || "已确认"}</strong>
                </li>
              ))}
            </ul>
          )}
          {(professionalMode || runningJobs.length > 0) && (
            <section className="v2-job-content" aria-label="本地任务" role="region">
              {jobs.length ? jobs.map((job) => (
                <article key={job.id}>
                  <strong>{jobLabel(job)}</strong>
                  <span>{jobStatusLabel(job)} · {job.progress}%</span>
                  {job.error && <p>{job.error.message}</p>}
                </article>
              )) : (
                <>
                  <strong>没有正在运行的本地任务</strong>
                  <p>生成 3D 或上传代码时，进度会显示在这里。</p>
                </>
              )}
            </section>
          )}
        </div>
        <div hidden={tab !== "artifacts"}>
          {artifacts.length ? (
            <div className="zw-inspector-arts">
              {artifacts.map((artifact) => (
                <button
                  key={artifact.id}
                  type="button"
                  className="zw-inspector-art"
                  onClick={() => onOpenArtifact(artifact.id, artifact.currentVersionId)}
                >
                  <strong>{artifactDisplayTitle(artifact.title, professionalMode)}</strong>
                  <span>
                    {artifactKindLabel(artifact.kind)} · {artifactStatusLabel(artifact.status)}
                    {professionalMode ? ` · ${artifact.versions.length} 个版本` : ""}
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <p className="zw-inspector-empty">代码、文档和 3D 模型生成后会出现在这里。</p>
          )}
        </div>
        {deviceVisited && (
          <div className="zw-inspector-device" hidden={tab !== "device"}>
            <DevicesTab
              workspace={workspace}
              professionalMode={professionalMode}
              refreshRevision={deviceRefreshRevision}
              onOpenDeviceLab={onOpenDeviceLab}
            />
          </div>
        )}
      </div>
    </aside>
  );
}

function jobLabel(job: ToolJob): string {
  return {
    CAD_INTENT: "准备 3D 方案",
    CAD_BUILD: "生成 3D 模型",
    DEVICE_TAKEOVER: "连接设备",
    DEVICE_UPLOAD: "上传代码",
  }[job.kind];
}

function jobStatusLabel(job: ToolJob): string {
  return {
    QUEUED: "等待中",
    RUNNING: "进行中",
    WAITING_CONFIRMATION: "等待确认",
    SUCCEEDED: "已完成",
    FAILED: "未完成",
    CANCELED: "已取消",
  }[job.status];
}
