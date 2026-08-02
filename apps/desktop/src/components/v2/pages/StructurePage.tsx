import { useState } from "react";
import type {
  CadIntentResult,
  CadIntentWorkspace,
  ProjectState,
} from "@zhangwen/contracts";
import { V2CadViewport } from "../V2CadViewport";

export function StructurePage({
  state,
  professionalMode,
  workspace,
  busy,
  error,
  lastResult,
  onSubmit,
  onConfirm,
  onBuild,
  onUndo,
  decorativePlaceholder = true,
}: {
  state: ProjectState | null;
  professionalMode: boolean;
  workspace: CadIntentWorkspace | null;
  busy: boolean;
  error: string | null;
  lastResult: CadIntentResult | null;
  onSubmit: (prompt: string, mode: "draft" | "edit") => Promise<unknown>;
  onConfirm: (revisionId: string) => Promise<unknown>;
  onBuild: (revisionId: string) => Promise<unknown>;
  onUndo: (revisionId: string) => Promise<unknown>;
  decorativePlaceholder?: boolean;
}) {
  const [prompt, setPrompt] = useState("");
  const current = workspace?.currentRevision ?? null;
  const pending = workspace?.pendingRevision ?? null;
  const objectIndex = (pending ?? current)?.objectIndex ?? [];

  const submit = async () => {
    const value = prompt.trim();
    if (!value || busy) return;
    try {
      await onSubmit(value, current ? "edit" : "draft");
      setPrompt("");
    } catch {
      // The hook exposes the actionable error beside the command input.
    }
  };

  return (
    <div className={`v2-structure-layout ${professionalMode ? "is-professional" : "is-simple"}`}>
      <aside className="v2-object-tree">
        <span className="v2-card-label">{professionalMode ? "对象 / 特征" : "模型组成"}</span>
        <h2>{professionalMode ? "结构树" : "模型部件"}</h2>
        <ul>
          {objectIndex.map((item, index) => (
            <li key={item.id} className={index === 0 ? "is-active" : undefined}>
              <span>{item.type === "assembly" ? "◫" : "└"}</span> {item.label}
            </li>
          ))}
          {!objectIndex.length && <li className="v2-muted">生成 3D 方案后，这里会显示模型部件。</li>}
        </ul>
      </aside>
      <section className="v2-cad-stage" aria-label="3D 结构视口">
        <div className="v2-cad-toolbar"><span>整体</span><button type="button">适应视图</button><button type="button">爆炸图</button></div>
        <V2CadViewport
          revision={current}
          cadRun={workspace?.legacyCadRun ?? null}
          refreshKey={workspace?.jobs[0]?.updatedAt ?? ""}
          professionalMode={professionalMode}
          decorativePlaceholder={decorativePlaceholder}
        />
        <div className="v2-cad-command">
          <label htmlFor="v2-cad-intent">描述你想要的结构</label>
          <div>
            <input
              id="v2-cad-intent"
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void submit();
              }}
              placeholder={current ? "例如：把壁厚加到 2.5mm" : "例如：生成自动浇花装置外壳"}
              disabled={busy}
            />
            <button type="button" disabled={busy || !prompt.trim()} onClick={() => void submit()}>
              {busy ? "处理中…" : current ? "生成修改方案" : "生成 3D 方案"}
            </button>
          </div>
          {pending && (
            <article className="v2-cad-pending">
              <div><b>请确认本次修改</b><span>{pending.intentSummary}</span></div>
              <button type="button" disabled={busy} onClick={() => void onConfirm(pending.id).catch(() => undefined)}>确认并生成 3D</button>
            </article>
          )}
          {current && !pending && (
            <button
              type="button"
              disabled={busy}
              onClick={() => void onBuild(current.id).catch(() => undefined)}
            >
              {busy ? "生成中…" : "生成 3D 模型"}
            </button>
          )}
          {(error || lastResult?.message || lastResult?.missingFields?.length) && (
            <p className={error ? "v2-cad-message is-error" : "v2-cad-message"} role={error ? "alert" : undefined}>
              {error ?? lastResult?.message ?? `还需要：${lastResult?.missingFields?.join("、")}`}
            </p>
          )}
        </div>
        <div className="v2-cad-status">
          <span>{structureStatusLabel(state?.domains.structure.status)}</span>
          <span>{busy
            ? professionalMode ? "本地 CAD Worker 正在处理" : "正在生成 3D 模型"
            : current
              ? professionalMode ? "源码修订已纳入项目版本" : "当前方案已保存"
              : "等待你描述结构"}</span>
        </div>
      </section>
      {professionalMode && <aside className="v2-property-panel">
        <span className="v2-card-label">属性与约束</span>
        <h2>修订历史</h2>
        <div className="v2-cad-revisions">
          {(workspace?.revisions ?? []).slice(0, 5).map((item) => (
            <article key={item.id}>
              <div><b>{revisionStatusLabel(item.status)}</b><span>{item.intentSummary}</span></div>
              {item.status === "CONFIRMED" && item.id === current?.id && (
                <button type="button" disabled={busy} onClick={() => void onUndo(item.id).catch(() => undefined)}>撤销为新修订</button>
              )}
            </article>
          ))}
          {!workspace?.revisions.length && <p className="v2-muted">尚无结构修订。</p>}
        </div>
        <code>projectStateHash: {state?.projectionHash.slice(0, 12) ?? "—"}</code>
        <code>sourceSha256: {(pending ?? current)?.sourceSha256.slice(0, 12) ?? "—"}</code>
      </aside>}
    </div>
  );
}

function structureStatusLabel(status?: string): string {
  return ({
    completed: "3D 设计已完成",
    in_progress: "3D 设计进行中",
    not_started: "3D 设计未开始",
  } as Record<string, string>)[status ?? ""] ?? "3D 设计未开始";
}

function revisionStatusLabel(status: string): string {
  return ({
    PLANNED: "方案草稿",
    CONFIRMED: "已确认",
    REJECTED: "未采用",
    SUPERSEDED: "已替换",
  } as Record<string, string>)[status] ?? status;
}
