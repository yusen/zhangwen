import { useEffect, useMemo, useState } from "react";
import {
  CreatorCommand,
  type CreatorWorkspace,
} from "@zhangwen/contracts";

interface IdeaSolutionStageProps {
  workspace: CreatorWorkspace;
  professionalMode: boolean;
  onCommand: (command: CreatorCommand, payload: Record<string, unknown>) => Promise<void>;
  onOpenHardwareSelection: () => void;
}

interface GoalDraft {
  statement: string;
  observableBehavior: string;
  constraints: string;
  successCriteria: string;
}

interface SolutionDraft {
  summary: string;
  logic: string;
  hardware: string;
  software: string;
  structure: string;
  simulation: string;
  safety: string;
  bom: string;
  ioMap: string;
  scenarios: string;
}

export default function IdeaSolutionStage({
  workspace,
  professionalMode,
  onCommand,
  onOpenHardwareSelection,
}: IdeaSolutionStageProps) {
  const goalRevision =
    workspace.draftGoal ?? workspace.confirmedGoal ?? workspace.currentGoal;
  const solutionRevision =
    workspace.draftSolution ??
    workspace.confirmedSolution ??
    workspace.currentSolution;
  const [goal, setGoal] = useState<GoalDraft>(() => goalFromWorkspace(workspace));
  const [solution, setSolution] = useState<SolutionDraft>(() => solutionFromWorkspace(workspace));
  const [editingGoal, setEditingGoal] = useState(false);
  const [editingSolution, setEditingSolution] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setGoal(goalFromWorkspace(workspace));
    setEditingGoal(false);
  }, [goalRevision?.id, workspace.workId]);

  useEffect(() => {
    setSolution(solutionFromWorkspace(workspace));
    setEditingSolution(false);
  }, [solutionRevision?.id, workspace.workId]);

  const goalValid = useMemo(
    () => Boolean(goal.statement.trim() && goal.observableBehavior.trim() && splitLines(goal.successCriteria).length),
    [goal],
  );
  const solutionValid = useMemo(
    () => [solution.summary, solution.logic, solution.hardware, solution.software, solution.simulation, solution.safety]
      .every((value) => Boolean(value.trim())) && solutionScenarios(solution.scenarios, goal.successCriteria).length > 0,
    [goal.successCriteria, solution],
  );

  const run = async (label: string, command: CreatorCommand, payload: Record<string, unknown>) => {
    setBusy(label);
    setError(null);
    try {
      await onCommand(command, payload);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存失败，请刷新作品后重试。");
    } finally {
      setBusy(null);
    }
  };

  const goalPayload = {
    statement: goal.statement.trim(),
    observableBehavior: goal.observableBehavior.trim(),
    constraints: splitLines(goal.constraints),
    successCriteria: splitLines(goal.successCriteria),
  };
  const solutionPayload = {
    summary: solution.summary.trim(),
    logic: solution.logic.trim(),
    hardware: solution.hardware.trim(),
    software: solution.software.trim(),
    structure: solution.structure.trim() || "不需要结构",
    simulation: solution.simulation.trim(),
    safety: solution.safety.trim(),
    bom: parseBom(solution.bom),
    ioMap: parseIoMap(solution.ioMap),
    acceptanceScenarios: solutionScenarios(solution.scenarios, goal.successCriteria),
  };

  return (
    <div className="creator-stage-content" data-testid="creator-stage-idea">
      <section className="creator-stage-hero">
        <span>从想法到可执行方案</span>
        <h2>{goalRevision?.statement ?? workspace.initialIdea}</h2>
        <p>{goalRevision?.observableBehavior ?? "继续与掌问对话，明确作品可观察行为。"}</p>
      </section>

      {error ? <div className="creator-error" role="alert">{error}</div> : null}
      {workspace.conversationProjectionStatus.status === "CONFLICT" ? (
        <div className="creator-error" role="status">
          对话产生了新的候选目标，但未覆盖三师专业模式中的人工草稿。请在专业模式中比较后保存。
        </div>
      ) : null}

      <section className="creator-stage-card creator-editor-card">
        <header>
          <div><h3>作品目标</h3><p>把对话结论整理为能观察、能验收的目标。</p></div>
          <span>{goalRevision?.status === "CONFIRMED" ? `已确认 v${goalRevision.revision}` : "将随方案一并确认"}</span>
        </header>
        {professionalMode && editingGoal ? (
          <div className="creator-form-grid">
            <Field label="目标陈述" value={goal.statement} onChange={(statement) => setGoal((current) => ({ ...current, statement }))} />
            <Field label="可观察行为" value={goal.observableBehavior} onChange={(observableBehavior) => setGoal((current) => ({ ...current, observableBehavior }))} />
            <Field label="约束（每行一项）" value={goal.constraints} rows={3} onChange={(constraints) => setGoal((current) => ({ ...current, constraints }))} />
            <Field label="成功标准（每行一项）" value={goal.successCriteria} rows={3} required onChange={(successCriteria) => setGoal((current) => ({ ...current, successCriteria }))} />
            <div className="creator-form-actions">
              <button type="button" disabled={Boolean(busy) || !goalValid} onClick={() => void run("正在保存目标…", CreatorCommand.SAVE_GOAL, goalPayload)}>保存草稿</button>
            </div>
          </div>
        ) : (
          <>
            <div className="creator-solution-grid creator-goal-summary">
              <div><strong>使用场景</strong><p>{goalRevision?.statement ?? workspace.initialIdea}</p></div>
              <div><strong>可观察行为</strong><p>{goalRevision?.observableBehavior ?? "等待对话整理"}</p></div>
              <div><strong>约束</strong><ul>{goalRevision?.constraints.length ? goalRevision.constraints.map((item) => <li key={item}>{item}</li>) : <li>暂无明确约束</li>}</ul></div>
              <div><strong>成功标准</strong><ul>{goalRevision?.successCriteria.length ? goalRevision.successCriteria.map((item) => <li key={item}>{item}</li>) : <li>等待对话补充</li>}</ul></div>
            </div>
            <p className="creator-projection-meta">
              {goalRevision?.sourceType === "CONVERSATION" ? "已从对话自动同步" : "当前稳定版本"}
              {goalRevision?.createdAt ? ` · ${new Date(goalRevision.createdAt).toLocaleString("zh-CN")}` : ""}
            </p>
            <div className="creator-form-actions">
              <button type="button" onClick={focusCreatorChat}>要求修改</button>
              {professionalMode && <button type="button" onClick={() => setEditingGoal(true)}>编辑并保存新草稿</button>}
            </div>
          </>
        )}
      </section>

      <section className="creator-stage-card creator-editor-card">
        <header>
          <div><h3>当前实施方案</h3><p>一套方案同时覆盖逻辑、硬件、软件、结构、仿真、安全与验收。</p></div>
          <span>{solutionRevision?.status === "CONFIRMED" ? `已冻结 v${solutionRevision.revision}` : "形成中"}</span>
        </header>
        {professionalMode && editingSolution ? (
          <div className="creator-form-grid">
            <Field label="方案摘要" value={solution.summary} onChange={(summary) => setSolution((current) => ({ ...current, summary }))} />
            <Field label="工作逻辑" value={solution.logic} rows={4} onChange={(logic) => setSolution((current) => ({ ...current, logic }))} />
            <Field label="硬件与供电" value={solution.hardware} rows={4} onChange={(hardware) => setSolution((current) => ({ ...current, hardware }))} />
            <button type="button" className="creator-inline-action" onClick={onOpenHardwareSelection}>选择并添加电子器件</button>
            <Field label="软件与代码" value={solution.software} rows={4} onChange={(software) => setSolution((current) => ({ ...current, software }))} />
            <Field label="3D 结构（无需求填写“不需要结构”）" value={solution.structure} rows={3} onChange={(structure) => setSolution((current) => ({ ...current, structure }))} />
            <Field label="仿真方法与覆盖边界" value={solution.simulation} rows={4} onChange={(simulation) => setSolution((current) => ({ ...current, simulation }))} />
            <Field label="安全与恢复" value={solution.safety} rows={4} onChange={(safety) => setSolution((current) => ({ ...current, safety }))} />
            <Field label="BOM（每行：器件 ID | 名称 | 数量）" value={solution.bom} rows={4} onChange={(bom) => setSolution((current) => ({ ...current, bom }))} />
            <Field label="IO（每行：信号 | 引脚 | 用途）" value={solution.ioMap} rows={4} onChange={(ioMap) => setSolution((current) => ({ ...current, ioMap }))} />
            <Field label="验收场景（每行：标题 | 仿真预期 | 真机预期）" value={solution.scenarios} rows={5} required onChange={(scenarios) => setSolution((current) => ({ ...current, scenarios }))} />
            <div className="creator-form-actions">
              <button type="button" disabled={Boolean(busy) || !solutionValid} onClick={() => void run("正在保存方案…", CreatorCommand.SAVE_SOLUTION, solutionPayload)}>保存方案草稿</button>
              <button type="button" className="creator-primary-button" disabled={Boolean(busy) || !goalValid || !solutionValid} onClick={() => void run("正在确认方案…", CreatorCommand.CONFIRM_SOLUTION, solutionPayload)}>确认并建立数字原型</button>
            </div>
          </div>
        ) : solutionRevision ? (
          <>
            <p>{solutionRevision.summary}</p>
            <div className="creator-solution-grid">
              <div><strong>工作逻辑</strong><p>{solutionRevision.logic}</p></div>
              <div><strong>硬件与供电</strong><p>{solutionRevision.hardware}</p></div>
              <div><strong>软件与运行时</strong><p>{solutionRevision.software}</p></div>
              <div><strong>结构</strong><p>{solutionRevision.structure}</p></div>
              <div><strong>仿真边界</strong><p>{solutionRevision.simulation}</p></div>
              <div><strong>安全与恢复</strong><p>{solutionRevision.safety}</p></div>
              <div><strong>BOM</strong>{solutionRevision.bom.length ? <ul>{solutionRevision.bom.map((item) => <li key={item.componentId}>{item.name} × {item.quantity}</li>)}</ul> : <p>等待器件方案同步</p>}</div>
              <div><strong>IO</strong>{solutionRevision.ioMap.length ? <ul>{solutionRevision.ioMap.map((item) => <li key={`${item.signal}:${item.pin}`}>{item.signal} · {item.pin} · {item.purpose}</li>)}</ul> : <p>等待引脚检查</p>}</div>
              <div><strong>验收场景</strong>{workspace.acceptanceScenarios.length ? <ul>{workspace.acceptanceScenarios.map((item) => <li key={item.id}>{item.title}</li>)}</ul> : <p>等待验收场景同步</p>}</div>
            </div>
            <p className="creator-projection-meta">
              {solutionRevision.sourceType === "LEGACY_PROJECTION" ? "已与立项书同步" : "方案修订"}
              {` · v${solutionRevision.revision}`}
            </p>
            <div className="creator-form-actions">
              <button type="button" onClick={focusCreatorChat}>要求修改</button>
              <button type="button" onClick={onOpenHardwareSelection}>选择并添加电子器件</button>
              {solutionRevision.status !== "CONFIRMED" && (
                <button type="button" className="creator-primary-button" disabled={Boolean(busy) || !goalValid || !solutionValid} onClick={() => void run("正在确认方案…", CreatorCommand.CONFIRM_SOLUTION, solutionPayload)}>确认方案并建立数字原型</button>
              )}
              {professionalMode && <button type="button" onClick={() => setEditingSolution(true)}>编辑并保存新草稿</button>}
            </div>
            {solutionRevision.status === "CONFIRMED" ? (
              <div className="creator-project-book">
                <div>
                  <strong>立项书（可选产物）</strong>
                  <span>不影响方案确认和数字原型，可随时按当前版本生成。</span>
                </div>
                <button
                  type="button"
                  disabled={Boolean(busy)}
                  onClick={() => void run(
                    workspace.projectBookProjection.status === "CURRENT" ? "正在重新生成立项书…" : "正在生成立项书…",
                    CreatorCommand.GENERATE_PROJECT_BOOK,
                    {},
                  )}
                >
                  {workspace.projectBookProjection.status === "CURRENT" ? "重新生成立项书" : "生成立项书"}
                </button>
                {workspace.projectBookProjection.status === "STALE" ? (
                  <p role="status">已有立项书绑定旧方案版本，请按当前方案重新生成。</p>
                ) : null}
                {workspace.projectBookProjection.status === "CURRENT" ? (
                  <details>
                    <summary>查看立项书 v{workspace.projectBookProjection.revision ?? 1}</summary>
                    {(workspace.projectBookProjection.sections ?? []).map((section) => (
                      <section key={section.id}>
                        <h4>{section.title}</h4>
                        <p>{section.content}</p>
                      </section>
                    ))}
                  </details>
                ) : null}
              </div>
            ) : null}
          </>
        ) : (
          <div className="creator-blocked-note">
            <strong>正在从对话整理方案</strong>
            <span>关键信息齐全后，工作逻辑、硬件、代码依据与验收场景会自动同步到这里，无需在对话中再次确认。</span>
            <button type="button" className="creator-inline-action" onClick={onOpenHardwareSelection}>选择并添加电子器件</button>
          </div>
        )}
      </section>
      {busy ? <div className="creator-toast" role="status">{busy}</div> : null}
    </div>
  );
}

function Field({ label, value, onChange, rows = 2, required = false }: { label: string; value: string; onChange: (value: string) => void; rows?: number; required?: boolean }) {
  return <label className="creator-field"><span>{label}{required ? " *" : ""}</span><textarea value={value} rows={rows} required={required} onChange={(event) => onChange(event.target.value)} /></label>;
}

function goalFromWorkspace(workspace: CreatorWorkspace): GoalDraft {
  const current =
    workspace.draftGoal ?? workspace.confirmedGoal ?? workspace.currentGoal;
  return {
    statement: current?.statement ?? workspace.initialIdea,
    observableBehavior: current?.observableBehavior === "待整理" ? "" : current?.observableBehavior ?? "",
    constraints: (current?.constraints ?? []).join("\n"),
    successCriteria: (current?.successCriteria ?? []).join("\n"),
  };
}

function solutionFromWorkspace(workspace: CreatorWorkspace): SolutionDraft {
  const current =
    workspace.draftSolution ??
    workspace.confirmedSolution ??
    workspace.currentSolution;
  return {
    summary: current?.summary ?? "",
    logic: current?.logic ?? "",
    hardware: current?.hardware ?? "",
    software: current?.software ?? "",
    structure: current?.structure ?? "不需要结构",
    simulation: current?.simulation ?? "",
    safety: current?.safety ?? "",
    bom: (current?.bom ?? []).map((item) => `${item.componentId} | ${item.name} | ${item.quantity}`).join("\n"),
    ioMap: (current?.ioMap ?? []).map((item) => `${item.signal} | ${item.pin} | ${item.purpose}`).join("\n"),
    scenarios: workspace.acceptanceScenarios.map((item) => `${item.title} | ${item.simulationExpected} | ${item.physicalExpected}`).join("\n"),
  };
}

function focusCreatorChat(): void {
  const composer = document.querySelector<HTMLTextAreaElement>(
    ".creator-chat-pane .chat-textarea",
  );
  composer?.focus();
}

function splitLines(value: string): string[] {
  return value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
}

function parseBom(value: string): Array<{ componentId: string; name: string; quantity: number }> {
  return splitLines(value).map((line) => {
    const [componentId = "", name = "", quantity = "1"] = line.split("|").map((item) => item.trim());
    return { componentId, name: name || componentId, quantity: Math.max(1, Number.parseInt(quantity, 10) || 1) };
  }).filter((item) => item.componentId && item.name);
}

function parseIoMap(value: string): Array<{ signal: string; pin: string; purpose: string }> {
  return splitLines(value).map((line) => {
    const [signal = "", pin = "", purpose = ""] = line.split("|").map((item) => item.trim());
    return { signal, pin, purpose };
  }).filter((item) => item.signal && item.pin && item.purpose);
}

function parseScenarios(value: string): Array<{ title: string; required: true; simulationExpected: string; physicalExpected: string }> {
  return splitLines(value).map((line) => {
    const [title = "", simulationExpected = "", physicalExpected = ""] = line.split("|").map((item) => item.trim());
    return { title, required: true as const, simulationExpected, physicalExpected };
  }).filter((item) => item.title && item.simulationExpected && item.physicalExpected);
}

function solutionScenarios(
  value: string,
  successCriteria: string,
): Array<{ title: string; required: true; simulationExpected: string; physicalExpected: string }> {
  const explicit = parseScenarios(value);
  if (explicit.length) return explicit;
  return splitLines(successCriteria).map((criterion) => ({
    title: criterion,
    required: true as const,
    simulationExpected: criterion,
    physicalExpected: criterion,
  }));
}
