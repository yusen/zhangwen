import { useState } from "react";
import {
  type ArtifactDefinition,
  type ProjectState,
} from "@zhangwen/contracts";
import { artifactKindLabel, artifactStatusLabel } from "../shell/labels";

export { artifactKindLabel, artifactStatusLabel };

/* ============ 页头（四工作区统一模式） ============ */

export function WorkspaceHeader({
  title,
  subtitle,
  state,
  professionalMode,
  onOpenAi,
  onOpenJobs,
}: {
  title: string;
  subtitle: string;
  state: ProjectState | null;
  professionalMode: boolean;
  onOpenAi: () => void;
  onOpenJobs: () => void;
}) {
  return (
    <header className="v2-workspace-header">
      <div>
        {(!state || professionalMode) && (
          <span className="v2-eyebrow">
            {state ? `项目版本 V${state.projectVersion}` : "正在同步"}
          </span>
        )}
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
      <div className="v2-header-actions">
        <button type="button" onClick={onOpenJobs}>查看进度</button>
        <button type="button" className="v2-primary-button" onClick={onOpenAi}>返回对话</button>
      </div>
    </header>
  );
}

/* ============ 工程页通用面板 ============ */

export function EngineeringPanel({ title, lead, items, empty }: { title: string; lead: string; items: string[]; empty: string }) {
  return (
    <section className="v2-engineering-panel">
      <div><span className="v2-card-label">当前内容</span><h2>{title}</h2><p>{lead}</p></div>
      <div className="v2-engineering-list">
        {items.map((item) => <article key={item}><i aria-hidden="true" /><span>{item}</span></article>)}
        {!items.length && <div className="v2-page-empty">{empty}</div>}
      </div>
    </section>
  );
}

export function CodeUploadGuide({
  hasAcceptedCode,
  onOpenDevice,
}: {
  hasAcceptedCode: boolean;
  onOpenDevice: () => void;
}) {
  return (
    <section className="v2-engineering-panel v2-artifact-workspace" aria-label="代码上传流程">
      <div>
        <span className="v2-card-label">上传到设备</span>
        <h2>先确认代码，再连接设备</h2>
        <p>先确认代码，再进入设备页扫描连接并上传。进入设备页不会自动扫描、连接或上传。</p>
        <button type="button" className="v2-primary-button" onClick={onOpenDevice}>
          进入设备页
        </button>
      </div>
      <div className="v2-engineering-list">
        <article>
          <i aria-hidden="true" />
          <span>
            <strong>1. 验证并接受代码</strong><br />
            {hasAcceptedCode
              ? "已有已接受代码，可以继续进入设备页。"
              : "当前代码尚未确认；请先打开代码详情，完成检查并确认使用。"}
          </span>
        </article>
        <article>
          <i aria-hidden="true" />
          <span>
            <strong>2. 扫描、连接并上传</strong><br />
            只会上传你已确认的代码，连接和上传前都会再次征得你的确认。
          </span>
        </article>
      </div>
    </section>
  );
}

/* ============ 产物工作台（代码页 / 交付页共用） ============ */

export function ArtifactWorkspace({
  title,
  lead,
  artifacts,
  loading,
  error,
  empty,
  onOpenArtifact,
  professionalMode,
}: {
  title: string;
  lead: string;
  artifacts: ArtifactDefinition[];
  loading: boolean;
  error: string | null;
  empty: string;
  onOpenArtifact?: (artifactId: string, versionId?: string | null) => void;
  professionalMode: boolean;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = artifacts.find((item) => item.id === selectedId) ?? artifacts[0] ?? null;
  const version = selected?.versions.find((item) => item.id === selected.currentVersionId)
    ?? selected?.versions[0]
    ?? null;
  return (
    <section className="v2-artifact-workspace">
      <header><span className="v2-card-label">成果列表</span><h2>{title}</h2><p>{lead}</p></header>
      {loading && <div className="v2-page-empty">正在读取项目成果…</div>}
      {error && <div className="v2-page-empty" role="alert">{error}</div>}
      {!loading && !error && !artifacts.length && <div className="v2-page-empty">{empty}</div>}
      {!!artifacts.length && (
        <div className="v2-artifact-layout">
          <nav aria-label={`${title}产物列表`}>
            {artifacts.map((artifact) => (
              <button
                key={artifact.id}
                type="button"
                aria-current={selected?.id === artifact.id ? "page" : undefined}
                onClick={() => setSelectedId(artifact.id)}
              >
                <strong>{artifactDisplayTitle(artifact.title, professionalMode)}</strong>
                <span>
                  {artifactStatusLabel(artifact.status)}
                  {professionalMode ? ` · ${artifact.versions.length} 个版本` : ""}
                </span>
              </button>
            ))}
          </nav>
          {selected && (
            <article className="v2-artifact-preview">
              <div><span>{artifactKindLabel(selected.kind)}</span><b>{artifactStatusLabel(selected.status)}</b></div>
              <h3>{artifactDisplayTitle(selected.title, professionalMode)}</h3>
              <p>{artifactDisplaySummary(version?.preview.summary, professionalMode)}</p>
              {version?.preview.sections?.map((section) => (
                <section key={section.id}><h4>{section.title}</h4><p>{section.content}</p></section>
              ))}
              {version?.preview.code && <pre><code>{version.preview.code}</code></pre>}
              {onOpenArtifact && version && (
                <button
                  type="button"
                  className="v2-primary-button"
                  onClick={() => onOpenArtifact(selected.id, version.id)}
                >
                  打开代码详情并验证
                </button>
              )}
            </article>
          )}
        </div>
      )}
    </section>
  );
}

/* ============ 硬件与事实辅助 ============ */

export interface PreferredHardwareItem {
  id: string;
  name: string;
  skillName: string | null;
  skillRevision: string | null;
}

export function preferredHardware(state: ProjectState | null): PreferredHardwareItem[] {
  const fact = state?.facts.find((item) => item.key === "preferred_hardware");
  if (!fact || typeof fact.value !== "object" || fact.value === null) return [];
  const components = (fact.value as { components?: unknown }).components;
  if (!Array.isArray(components)) return [];
  return components.flatMap((component) => {
    if (typeof component !== "object" || component === null) return [];
    const value = component as Record<string, unknown>;
    const id = typeof value.id === "string"
      ? value.id
      : typeof value.componentId === "string"
        ? value.componentId
        : "";
    if (!id) return [];
    return [{
      id,
      name: typeof value.name === "string" && value.name.trim() ? value.name : id,
      skillName: typeof value.skillName === "string" ? value.skillName : null,
      skillRevision: typeof value.skillRevision === "string" ? value.skillRevision : null,
    }];
  });
}

export function humanFactValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (value === null || value === undefined) return "—";
  if (Array.isArray(value)) return value.map(humanFactValue).join("、") || "—";
  if (typeof value === "object") {
    const record = value as Record<string, unknown>;
    const selected = record.selectedOptionIds;
    const text = record.textInput;
    const parts = Array.isArray(selected) ? selected.map(String) : [];
    if (typeof text === "string" && text.trim()) parts.push(text.trim());
    return parts.join("、") || "已确认";
  }
  return String(value);
}

export function humanFactLabel(key: string): string {
  if (/^q_\d+$/.test(key)) return `需求确认 ${key.slice(2)}`;
  return ({
    preferred_hardware: "项目硬件",
    delivery_track: "交付路线",
    project_mode: "项目模式",
  } as Record<string, string>)[key] ?? key.replaceAll("_", " ");
}

export function artifactDisplayTitle(title: string, professionalMode: boolean): string {
  if (professionalMode) return title;
  return title
    .replace(/^V\d+\s*/i, "")
    .replace(/MicroPython\s*工程代码/gi, "设备程序")
    .replace(/\bCAD\b/gi, "3D");
}

export function artifactDisplaySummary(summary: string | undefined, professionalMode: boolean): string {
  if (!summary) return "当前成果尚无可预览内容。";
  if (professionalMode) return summary;
  return summary
    .replace(/ZW-CAD-intent/gi, "结构设计工具")
    .replace(/本地构建校验/g, "生成检查")
    .replace(/\bCAD\b/gi, "3D");
}
