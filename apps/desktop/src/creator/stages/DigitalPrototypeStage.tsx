import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from "react";
import {
  CreatorCommand,
  DeviceDeploymentChannel,
  type CodeVariantBinding,
  type CreatorWorkspace,
  type DeviceLabRun,
  type DeviceLabSceneV1,
} from "@zhangwen/contracts";
import { DeviceLabWorkspace } from "../../components/device-lab/DeviceLabWorkspace";

const CodeArtifactEditor = lazy(
  () => import("../../components/floating/CodeArtifactEditor")
    .then((module) => ({ default: module.CodeArtifactEditor })),
);

type PrototypeMobileView = "code" | "simulation" | "terminal" | "debug";

export default function DigitalPrototypeStage({
  workspace,
  professionalMode,
  focusMode = false,
  onFocusModeChange,
  onCommand,
}: {
  workspace: CreatorWorkspace;
  professionalMode: boolean;
  focusMode?: boolean;
  onFocusModeChange?: (focused: boolean) => void;
  onCommand: (command: CreatorCommand, payload: Record<string, unknown>) => Promise<void>;
}) {
  const [scene, setScene] = useState<DeviceLabSceneV1 | null>(null);
  const [run, setRun] = useState<DeviceLabRun | null>(null);
  const [checkedScenarios, setCheckedScenarios] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mobileView, setMobileView] = useState<PrototypeMobileView>("simulation");
  const availableVariants = useMemo(
    () => workspace.codeVariants.filter((item) => item.codeRunId !== null),
    [workspace.codeVariants],
  );
  const [selectedVariantId, setSelectedVariantId] = useState(
    availableVariants[0]?.id ?? workspace.codeVariants[0]?.id ?? "",
  );
  const selectedVariant = useMemo(
    () => workspace.codeVariants.find((item) => item.id === selectedVariantId)
      ?? availableVariants[0]
      ?? workspace.codeVariants[0]
      ?? null,
    [availableVariants, selectedVariantId, workspace.codeVariants],
  );
  const staticPassed = workspace.evidence.some(
    (item) => item.kind === "STATIC_VALIDATION" && item.status === "CURRENT" && item.passed,
  );
  const simulationPassed = workspace.evidence.some(
    (item) => item.kind === "SIMULATION" && item.status === "CURRENT" && item.passed,
  );
  const requiredScenarios = useMemo(
    () => workspace.acceptanceScenarios.filter((item) => item.required),
    [workspace.acceptanceScenarios],
  );
  const allRequiredChecked = requiredScenarios.every(
    (item) => checkedScenarios.includes(item.id),
  );
  const onSceneChange = useCallback((next: DeviceLabSceneV1 | null) => setScene(next), []);
  const onRunChange = useCallback((next: DeviceLabRun | null) => {
    setRun(next);
    if (next?.status === "RUNNING") setCheckedScenarios([]);
  }, []);

  useEffect(() => {
    if (!workspace.codeVariants.some((item) => item.id === selectedVariantId)) {
      setSelectedVariantId(availableVariants[0]?.id ?? workspace.codeVariants[0]?.id ?? "");
    }
  }, [availableVariants, selectedVariantId, workspace.codeVariants]);

  const recordStatic = async () => {
    if (!scene) return;
    setBusy(true);
    setError(null);
    try {
      await onCommand(CreatorCommand.RECORD_STATIC_VALIDATION, {
        passed: scene.status === "READY",
        summary: scene.status === "READY"
          ? `数字原型场景 ${scene.revision.slice(0, 8)} 的板型、器件与 IO 静态检查通过。`
          : "数字原型已生成，但仍有 IO 需要确认。",
        sourceId: scene.revision,
        bindings: {
          sceneRevision: scene.revision,
          solutionRevisionId: scene.binding?.solutionRevisionId ?? "",
          codeRunId: scene.binding?.codeRunId ?? "",
        },
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "静态检查记录失败。");
    } finally {
      setBusy(false);
    }
  };

  const recordSimulation = async (passed: boolean) => {
    if (!run || run.status !== "STOPPED") return;
    setBusy(true);
    setError(null);
    try {
      await onCommand(CreatorCommand.RECORD_SIMULATION, {
        passed,
        summary: passed
          ? `仿真会话 ${run.id} 已安全停止，所有必需场景由用户逐项确认通过。`
          : `仿真会话 ${run.id} 已停止，至少一个必需场景未通过，留在当前阶段修复。`,
        sourceId: run.id,
        bindings: {
          sceneRevision: run.scene?.revision ?? "unknown",
          solutionRevisionId: run.scene?.binding?.solutionRevisionId ?? "",
          codeRunId: run.scene?.binding?.codeRunId ?? "",
          parameterSetId: run.parameterSetId ?? "default",
          scenarioIds: checkedScenarios.slice().sort().join(","),
        },
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "仿真验收记录失败。");
    } finally {
      setBusy(false);
    }
  };

  if (!workspace.confirmedSolution) {
    return (
      <div className="creator-stage-content" data-testid="creator-stage-digital">
        <section className="creator-stage-hero">
          <span>先仿真，再做实物</span>
          <h2>数字原型</h2>
          <p>确认方案后，掌问会自动生成代码变体，并从 BOM、IO、设备包和验收场景创建项目专属仿真。</p>
        </section>
        <section className="creator-stage-card creator-empty-canvas">
          <div aria-hidden="true" className="creator-orbit">◎</div>
          <h3>等待方案确认</h3>
          <p>这里不会要求你重新手工搭电路或重复填写方案。</p>
        </section>
      </div>
    );
  }

  return (
    <div className="creator-prototype-workspace" data-testid="creator-stage-digital">
      <nav className="creator-prototype-mobile-nav" aria-label="数字原型工作区">
        {([
          ["code", "代码"],
          ["simulation", "仿真"],
          ["terminal", "终端"],
          ["debug", "调试"],
        ] as const).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={mobileView === id ? "is-active" : ""}
            onClick={() => setMobileView(id)}
          >
            {label}
          </button>
        ))}
      </nav>

      {error ? <div className="creator-error" role="alert">{error}</div> : null}
      <div className="creator-prototype-grid">
        <section className={`creator-prototype-code${mobileView === "code" ? " is-mobile-active" : ""}`} aria-label="代码版本">
          <header>
            <div>
              <strong>代码</strong>
              <span>{professionalMode ? "可编辑并保存新版本" : "普通模式只读"}</span>
            </div>
            <div className="creator-code-variant-tabs" role="tablist" aria-label="部署代码变体">
              {workspace.codeVariants.map((variant) => (
                <button
                  key={variant.id}
                  type="button"
                  role="tab"
                  aria-selected={variant.id === selectedVariant?.id}
                  className={variant.id === selectedVariant?.id ? "is-active" : ""}
                  onClick={() => setSelectedVariantId(variant.id)}
                >
                  {variantLabel(variant)}
                  <small>{variant.validationStatus}</small>
                </button>
              ))}
            </div>
          </header>
          <div className="creator-prototype-code-editor">
            {selectedVariant?.codeRunId ? (
              <Suspense fallback={<div className="creator-loading">正在加载代码编辑器…</div>}>
                <CodeArtifactEditor
                  projectId={workspace.projectId}
                  codeRunId={selectedVariant.codeRunId}
                  readOnly={!professionalMode}
                  onCodeRunChanged={() => undefined}
                />
              </Suspense>
            ) : (
              <CodeVariantState variant={selectedVariant} />
            )}
          </div>
        </section>

        <section className={`creator-prototype-simulation${mobileView !== "code" ? " is-mobile-active" : ""}`} aria-label="仿真与终端">
          <DeviceLabWorkspace
            projectId={workspace.projectId}
            professionalMode={professionalMode}
            solutionRevisionId={workspace.confirmedSolution.id}
            codeRunId={selectedVariant?.codeRunId ?? null}
            embedded
            variant="prototype"
            mobileView={mobileView}
            codeVersionLabel={selectedVariant
              ? `${variantLabel(selectedVariant)} · ${selectedVariant.validationStatus}`
              : "等待代码生成"}
            focusMode={focusMode}
            onFocusModeChange={onFocusModeChange}
            onSceneChange={onSceneChange}
            onRunChange={onRunChange}
          />
        </section>
      </div>

      <details className="creator-prototype-validation" open={mobileView === "debug"}>
        <summary>检查与验收</summary>
        <div className="creator-validation-strip">
          <div>
            <strong>场景静态检查</strong>
            <span>{staticPassed ? "当前绑定已通过" : scene?.status === "READY" ? "场景已就绪" : "等待场景或 IO"}</span>
          </div>
          <button type="button" disabled={busy || !scene || staticPassed} onClick={() => void recordStatic()}>
            {staticPassed ? "已通过" : "记录静态检查"}
          </button>
        </div>
        <div className="creator-scenario-checklist">
          <header>
            <div><h3>必需仿真场景</h3><p>安全停止后逐项确认观察结果。</p></div>
            <span>{simulationPassed ? "已通过" : "待验收"}</span>
          </header>
          {requiredScenarios.map((scenario) => (
            <label key={scenario.id}>
              <input
                type="checkbox"
                checked={checkedScenarios.includes(scenario.id)}
                disabled={run?.status !== "STOPPED" || simulationPassed}
                onChange={(event) => setCheckedScenarios((current) => (
                  event.target.checked
                    ? [...current, scenario.id]
                    : current.filter((id) => id !== scenario.id)
                ))}
              />
              <span>
                <strong>{scenario.title}</strong>
                <small>{scenario.simulationExpected}</small>
              </span>
            </label>
          ))}
          <footer>
            <button type="button" disabled={busy || run?.status !== "STOPPED" || simulationPassed} onClick={() => void recordSimulation(false)}>记录未通过</button>
            <button type="button" className="creator-primary-button" disabled={busy || run?.status !== "STOPPED" || !allRequiredChecked || simulationPassed} onClick={() => void recordSimulation(true)}>
              {simulationPassed ? "仿真已通过" : "确认全部场景通过"}
            </button>
          </footer>
        </div>
      </details>
    </div>
  );
}

function variantLabel(variant: CodeVariantBinding): string {
  return variant.deploymentChannel === DeviceDeploymentChannel.USB_SERIAL
    ? "USB · MicroPython"
    : "ESP-Claw · Lua";
}

function CodeVariantState({ variant }: { variant: CodeVariantBinding | null }) {
  if (!variant) {
    return (
      <div className="creator-prototype-empty">
        <strong>尚未建立代码变体</strong>
        <span>确认方案后会自动创建 USB 与 ESP‑Claw 两个变体。</span>
      </div>
    );
  }
  return (
    <div className={`creator-prototype-empty is-${variant.validationStatus.toLowerCase()}`}>
      <strong>{variant.validationStatus === "FAILED" ? "代码生成失败" : "正在准备代码"}</strong>
      <span>{variant.failureMessage ?? "本地执行器将生成并进行静态与语法检查。"}</span>
    </div>
  );
}
