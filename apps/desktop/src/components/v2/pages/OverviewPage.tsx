import {
  ArtifactStatus,
  type ArtifactDefinition,
  type CapabilityCoverage,
  type ProjectState,
  type ProjectVersion,
  type ProjectWorkspace,
  type ProjectWorkspaceKind,
} from "@zhangwen/contracts";
import { humanFactLabel, humanFactValue } from "./common";

export function OverviewPage({
  workspace,
  state,
  coverage,
  artifacts,
  versions,
  professionalMode,
  onOpenWorkspace,
}: {
  workspace: ProjectWorkspace;
  state: ProjectState | null;
  coverage: CapabilityCoverage | null;
  artifacts: ArtifactDefinition[];
  versions: ProjectVersion[];
  professionalMode: boolean;
  onOpenWorkspace: (kind: ProjectWorkspaceKind) => void;
}) {
  const pending = workspace.coordinator?.pendingItems ?? [];
  const pendingCode = artifacts.filter(
    (item) => item.kind === "CODE" && item.status !== ArtifactStatus.APPROVED,
  ).length;
  const latestVersion = versions[0]?.version ?? null;
  const structureActive = state?.domains.structure.status === "in_progress";
  return (
    <>
      <div className="v2-page-grid v2-overview-grid">
        <section className="v2-hero-card">
          <span className="v2-card-label">原始创意</span>
          <h2>{workspace.project.name}</h2>
          <p>{workspace.project.profile.initialIdea}</p>
          <div className="v2-recommendation">
            <span>当前推荐方案</span>
            <strong>{state?.currentRecommendation ?? "正在根据已确认信息形成当前方案"}</strong>
          </div>
        </section>
        <section className="v2-metric-card">
          <span>{professionalMode ? "能力覆盖" : "项目准备度"}</span>
          <strong>{coverage?.coveragePercent ?? 0}<small>%</small></strong>
          <div className="v2-progress-track"><i style={{ width: `${coverage?.coveragePercent ?? 0}%` }} /></div>
          <p>{coverage?.missing.length
            ? professionalMode
              ? `${coverage.missing.length} 项能力缺口，项目处于探索模式。`
              : `还有 ${coverage.missing.length} 项需要补充，请在对话中继续确认。`
            : professionalMode
              ? "当前关键能力均有受信来源。"
              : "制作所需的信息已准备好。"}</p>
        </section>
        <section className="v2-list-card">
          <div className="v2-section-heading"><span>已确认信息</span><b>{state?.facts.length ?? 0}</b></div>
          <ul>
            {(state?.facts ?? []).slice(0, 6).map((fact) => (
              <li key={fact.id} className="v2-fact-row">
                <span>
                  {fact.label || humanFactLabel(fact.key)}
                  {professionalMode && <small>{fact.key}</small>}
                </span>
                <strong>{fact.displayValue || humanFactValue(fact.value)}</strong>
              </li>
            ))}
            {!state?.facts.length && <li className="v2-muted">继续对话后，目标、约束和成功标准会出现在这里。</li>}
          </ul>
        </section>
        <section className="v2-list-card">
          <div className="v2-section-heading"><span>下一步要确认</span><b>{pending.length}</b></div>
          <ul>
            {pending.slice(0, 6).map((item) => (
              <li key={item.id}><span>{item.title}</span><strong>{priorityLabel(item.priority)}</strong></li>
            ))}
            {!pending.length && <li className="v2-muted">目前没有需要你处理的问题。</li>}
          </ul>
        </section>
      </div>
      <div className="v2-next-strip">
        <button type="button" className="v2-next-card" onClick={() => onOpenWorkspace("engineering")}>
          <span className="v2-nc-top"><span className="v2-nc-ic is-eng" aria-hidden="true">⌘</span>制作</span>
          <strong>{pendingCode ? `${pendingCode} 份代码待确认` : "硬件、代码和设备"}</strong>
          <p>核对器件和代码，连接设备后安全上传。</p>
          <span className="v2-nc-go">开始制作 →</span>
        </button>
        <button type="button" className="v2-next-card" onClick={() => onOpenWorkspace("structure")}>
          <span className="v2-nc-top"><span className="v2-nc-ic is-str" aria-hidden="true">◇</span>3D 结构</span>
          <strong>{structureActive ? "3D 设计进行中" : "设计产品外形"}</strong>
          <p>直接描述外壳、孔位和尺寸，生成可预览模型。</p>
          <span className="v2-nc-go">设计结构 →</span>
        </button>
        <button type="button" className="v2-next-card" onClick={() => onOpenWorkspace("delivery")}>
          <span className="v2-nc-top"><span className="v2-nc-ic is-del" aria-hidden="true">↗</span>成果</span>
          <strong>{latestVersion
            ? professionalMode
              ? `已形成 V${latestVersion} 项目版本`
              : "已保存项目进度"
            : professionalMode
              ? "尚未创建项目版本"
              : "等待首份成果"}</strong>
          <p>集中查看方案、代码、3D 模型和验证结果。</p>
          <span className="v2-nc-go">查看成果 →</span>
        </button>
      </div>
    </>
  );
}

function priorityLabel(priority: string): string {
  return ({ HIGH: "优先处理", MEDIUM: "建议确认", LOW: "稍后确认" } as Record<string, string>)[priority]
    ?? "待确认";
}
