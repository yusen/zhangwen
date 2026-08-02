import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  CreatorCommand,
  CreatorDeliveryVariant,
  DeviceOperationKind,
  DeviceOperationStatus,
  type CreatorCommand as CreatorCommandType,
  type CreatorWorkspace,
  type DeviceOperation,
  type DevicePackageRevision,
  type CreatorDeliveryRecord,
  type CreatorImportContext,
  type ReproductionReport,
  type ProjectWorkspace,
} from "@zhangwen/contracts";
import {
  DevicesTab,
  type DeviceVerifiedTarget,
} from "../../components/right-panel/DevicesTab";
import {
  createCreatorPhysicalRun,
  createCreatorDelivery,
  completeImportedCreatorReproduction,
  getCreatorImportContext,
  listCreatorDevicePackages,
} from "../../services/creatorApi";
import { StableIntentKeyStore } from "../../utils/stableIntentKey";

interface PhysicalRunStageProps {
  workspace: CreatorWorkspace;
  projectWorkspace: ProjectWorkspace | null;
  professionalMode: boolean;
  onCommand: (
    command: CreatorCommandType,
    payload: Record<string, unknown>,
  ) => Promise<void>;
}

export default function PhysicalRunStage({
  workspace,
  projectWorkspace,
  professionalMode,
  onCommand,
}: PhysicalRunStageProps) {
  const stage = workspace.stages.find((item) => item.stage === "PHYSICAL_RUN");
  const [packages, setPackages] = useState<DevicePackageRevision[]>([]);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [target, setTarget] = useState<DeviceVerifiedTarget | null>(null);
  const [operation, setOperation] = useState<DeviceOperation | null>(null);
  const [observedScenarios, setObservedScenarios] = useState<Set<string>>(new Set());
  const [emergencyStopVerified, setEmergencyStopVerified] = useState(false);
  const [deliveries, setDeliveries] = useState<CreatorDeliveryRecord[]>([]);
  const [importContext, setImportContext] = useState<CreatorImportContext | null>(null);
  const [reproductionReport, setReproductionReport] = useState<ReproductionReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const intentKeys = useRef(new StableIntentKeyStore("creator-physical"));
  const simulationPassed = workspace.verificationLevel >= 3;
  const connectionEvidence = currentEvidence(workspace, "DEVICE_CONNECTION");
  const deploymentEvidence = currentEvidence(workspace, "DEPLOYMENT");
  const physicalEvidence = currentEvidence(workspace, "PHYSICAL_BEHAVIOR");
  const acceptanceEvidence = currentEvidence(workspace, "USER_ACCEPTANCE");
  const completedDeployment = operation?.kind === DeviceOperationKind.UPLOAD_CODE
    && operation.status === DeviceOperationStatus.COMPLETED
    && !operation.dryRun
    && operation.verification?.ok
    ? operation
    : null;
  const operationTargetId = typeof completedDeployment?.metadata?.targetId === "string"
    ? completedDeployment.metadata.targetId
    : null;
  const requiredScenarios = useMemo(
    () => workspace.acceptanceScenarios.filter((item) => item.required),
    [workspace.acceptanceScenarios],
  );
  const allRequiredObserved = requiredScenarios.every((item) => observedScenarios.has(item.id));

  useEffect(() => {
    const controller = new AbortController();
    void listCreatorDevicePackages()
      .then((response) => {
        if (!controller.signal.aborted) setPackages(response.packages);
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setCatalogError(reason instanceof Error ? reason.message : "设备包目录读取失败。");
        }
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void getCreatorImportContext(workspace.workId)
      .then((response) => {
        if (!controller.signal.aborted) setImportContext(response.context);
      })
      .catch(() => {
        if (!controller.signal.aborted) setImportContext(null);
      });
    return () => controller.abort();
  }, [workspace.workId]);

  useEffect(() => {
    setObservedScenarios(new Set());
    setEmergencyStopVerified(false);
  }, [deploymentEvidence?.id]);

  const recordConnection = useCallback(async () => {
    if (!target) return;
    setBusy(true);
    setError(null);
    try {
      await onCommand(CreatorCommand.RECORD_DEVICE_CONNECTION, {
        passed: true,
        summary: `已通过 ${target.channel === "ESP_CLAW" ? "ESP-Claw" : "USB 串口"}确认真实设备身份与当前方案匹配。`,
        sourceId: target.id,
        bindings: { channel: target.channel, devicePackageId: target.boardId },
      });
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }, [onCommand, target]);

  const recordDeployment = useCallback(async () => {
    if (!completedDeployment || !operationTargetId) return;
    setBusy(true);
    setError(null);
    try {
      await onCommand(CreatorCommand.RECORD_DEPLOYMENT, {
        passed: true,
        summary: "代码已写入、逐文件回读并完成运行时启动验证；这不会代替真机行为验收。",
        sourceId: completedDeployment.id,
        bindings: {
          channel: String(completedDeployment.metadata?.channel ?? ""),
          codeRunId: String(completedDeployment.metadata?.codeRunId ?? ""),
          targetId: operationTargetId,
        },
      });
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }, [completedDeployment, onCommand, operationTargetId]);

  const recordPhysicalRun = useCallback(async () => {
    if (!completedDeployment || !operationTargetId || !allRequiredObserved) return;
    setBusy(true);
    setError(null);
    const request = {
      deploymentOperationId: completedDeployment.id,
      targetId: operationTargetId,
      emergencyStopVerified,
      scenarioResults: workspace.acceptanceScenarios.map((item) => ({
        scenarioId: item.id,
        observed: observedScenarios.has(item.id),
        note: observedScenarios.has(item.id) ? "操作者已在真机上逐项观察。" : "未观察。",
      })),
    };
    const intentScope = `physical-run:${workspace.workId}`;
    try {
      const response = await createCreatorPhysicalRun(workspace.workId, {
        ...request,
        idempotencyKey: intentKeys.current.key(intentScope, request),
      });
      intentKeys.current.complete(intentScope);
      if (!response.run.passed) {
        setError("实物验收尚未覆盖全部必需场景或急停条件。");
        return;
      }
      await onCommand(CreatorCommand.RECORD_PHYSICAL_BEHAVIOR, {
        passed: true,
        summary: "当前方案的全部必需场景已在真机逐项观察通过，并确认急停入口可用。",
        sourceId: response.run.id,
        bindings: {
          deploymentOperationId: completedDeployment.id,
        },
      });
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }, [
    allRequiredObserved,
    completedDeployment,
    emergencyStopVerified,
    observedScenarios,
    onCommand,
    operationTargetId,
    workspace.acceptanceScenarios,
    workspace.workId,
  ]);

  const acceptWork = useCallback(async () => {
    if (!physicalEvidence) return;
    setBusy(true);
    setError(null);
    try {
      await onCommand(CreatorCommand.ACCEPT_WORK, {
        accepted: true,
        summary: "我已对照目标、仿真、部署恢复和真机行为结果，明确接受当前作品版本。",
      });
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }, [onCommand, physicalEvidence]);

  const createDelivery = useCallback(async (
    variant: (typeof CreatorDeliveryVariant)[keyof typeof CreatorDeliveryVariant],
  ) => {
    setBusy(true);
    setError(null);
    const request = { variant };
    const intentScope = `delivery:${workspace.workId}:${variant}`;
    try {
      const response = await createCreatorDelivery(workspace.workId, {
        ...request,
        idempotencyKey: intentKeys.current.key(intentScope, request),
      });
      intentKeys.current.complete(intentScope);
      setDeliveries((current) => [response.delivery, ...current.filter((item) => item.variant !== variant)]);
      downloadDelivery(response.delivery);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }, [workspace.workId]);

  const submitReproductionReceipt = useCallback(async () => {
    if (!importContext) return;
    setBusy(true);
    setError(null);
    try {
      const response = await completeImportedCreatorReproduction(workspace.workId, {
        summary: "第二位测试用户已从可复现包导入，并在副本中重新完成数字、设备、真机和用户验收。",
      });
      setReproductionReport(response.report);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }, [importContext, workspace.workId]);

  return (
    <div className="creator-stage-content" data-testid="creator-stage-physical">
      <section className="creator-stage-hero">
        <span>带确认点的真实操作</span>
        <h2>实物运行</h2>
        <p>{stage?.detail}</p>
      </section>

      {!simulationPassed ? (
        <section className="creator-stage-card creator-empty-canvas">
          <div aria-hidden="true" className="creator-device-pulse">●</div>
          <h3>仿真通过后解锁真实操作</h3>
          <p>你仍可查看所需设备包和风险，但扫描、部署、执行器调试与验收保持关闭。</p>
        </section>
      ) : projectWorkspace ? (
        <>
          <section className="creator-stage-card creator-embedded-device" aria-label="运行到设备">
            <DevicesTab
              workspace={projectWorkspace}
              professionalMode={professionalMode}
              refreshRevision={workspace.projectVersion}
              onVerifiedTargetChange={setTarget}
              onOperationChange={setOperation}
            />
          </section>

          <section className="creator-stage-card creator-device-evidence" aria-label="实物证据进度">
            <h3>上传后的设备闭环</h3>
            <ol>
              <li className={connectionEvidence ? "done" : "active"}><strong>1. 设备身份</strong><span>{connectionEvidence ? "已形成等级 4 连接证据" : target ? "身份已就绪，等待记录" : "选择 USB 或 ESP-Claw 并完成身份确认"}</span></li>
              <li className={deploymentEvidence ? "done" : connectionEvidence ? "active" : ""}><strong>2. 运行到设备</strong><span>{deploymentEvidence ? "写入与回读已记录，等级仍为 4" : "上传完成后单独记录部署证据"}</span></li>
              <li className={physicalEvidence ? "done" : deploymentEvidence ? "active" : ""}><strong>3. 真机行为</strong><span>{physicalEvidence ? "全部必需场景已通过，达到等级 5" : "部署成功不等于作品行为通过"}</span></li>
            </ol>
            {target && !connectionEvidence ? <button type="button" className="creator-primary-button" disabled={busy} onClick={() => void recordConnection()}>记录设备身份与方案匹配</button> : null}
            {completedDeployment && connectionEvidence && !deploymentEvidence ? <button type="button" className="creator-primary-button" disabled={busy || operationTargetId !== connectionEvidence.sourceId} onClick={() => void recordDeployment()}>记录部署回读证据</button> : null}
            {error ? <p className="creator-error" role="alert">{error}</p> : null}
          </section>

          <section className="creator-stage-card creator-physical-debug" aria-label="真机图形调试边界">
            <div className="creator-stage-card-heading"><div><span>图形调试</span><h3>真机数据与安全控制</h3></div><strong>zwdbg/1</strong></div>
            <div className="creator-physical-debug-grid">
              <article><h4>传感器原始值</h4><p>只读。当前固件完成调试协议握手后才显示实时值；不会用仿真值冒充真机遥测。</p></article>
              <article><h4>校准与参数</h4><p>修改会创建不可变参数版本，随后由用户明确同步；设备端采用暂存、提交与回读恢复链路。</p></article>
              <article><h4>执行器</h4><p>握手缺失时保持锁定；可用时仍受设备包限幅、刷新率、急停、看门狗和断线安全值约束。</p></article>
            </div>
          </section>

          <details className="creator-stage-card creator-device-packages" aria-label="设备包与维护信息">
            <summary>设备包、能力与维护信息</summary>
            <div className="creator-stage-card-heading">
              <div><span>设备包目录</span><h3>能力由服务端设备包声明</h3></div>
              <strong>{packages.length} 个代理验证包</strong>
            </div>
            {catalogError ? <p className="creator-error" role="alert">{catalogError}</p> : null}
            <div className="creator-package-grid">
              {packages.map((item) => (
                <article key={`${item.id}-${item.version}`}>
                  <h4>{item.displayName}</h4>
                  <p>{item.deploymentChannels.map(channelLabel).join(" · ")}</p>
                  <small>
                    {item.version} · {item.capabilities.join(" / ")}
                    {item.interactiveConsoleChannels?.length
                      ? ` · 可交互终端：${item.interactiveConsoleChannels.map(channelLabel).join(" / ")}`
                      : " · 运行日志只读"}
                  </small>
                </article>
              ))}
            </div>
          </details>

          {deploymentEvidence && completedDeployment && deploymentEvidence.sourceId === completedDeployment.id && !physicalEvidence ? (
            <section className="creator-stage-card creator-physical-checklist" aria-label="真机验收场景">
              <div className="creator-stage-card-heading"><div><span>独立于上传结果</span><h3>逐项观察真机行为</h3></div><strong>{observedScenarios.size}/{workspace.acceptanceScenarios.length}</strong></div>
              {workspace.acceptanceScenarios.map((item) => (
                <label key={item.id}>
                  <input type="checkbox" checked={observedScenarios.has(item.id)} onChange={(event) => setObservedScenarios((current) => toggleSet(current, item.id, event.target.checked))} />
                  <span><strong>{item.title}{item.required ? "（必需）" : ""}</strong><small>{item.physicalExpected}</small></span>
                </label>
              ))}
              <label><input type="checkbox" checked={emergencyStopVerified} onChange={(event) => setEmergencyStopVerified(event.target.checked)} /><span><strong>已确认急停入口和断线安全状态</strong><small>重新连接后不会自动恢复运动、加热、泵或高亮输出。</small></span></label>
              <p>真机验收将由当前已认证账户签署；界面不会暴露底层身份标识。</p>
              <button type="button" className="creator-primary-button" disabled={busy || !allRequiredObserved || !emergencyStopVerified} onClick={() => void recordPhysicalRun()}>{busy ? "正在保存不可变验收记录…" : "保存真机验收并记录等级 5"}</button>
            </section>
          ) : null}

          {physicalEvidence && !acceptanceEvidence ? (
            <section className="creator-stage-card creator-user-acceptance" aria-label="用户最终验收">
              <div className="creator-stage-card-heading"><div><span>等级 5 → 6</span><h3>由你明确接受当前作品</h3></div><strong>不会自动确认</strong></div>
              <p>请对照目标、全部场景、当前代码/参数/结构版本、真机结果和仍未覆盖的限制。确认后才生成等级 6 用户验收证据。</p>
              <p>最终验收将由当前已认证账户签署；更改显示名不会改变签署主体。</p>
              <button type="button" className="creator-primary-button" disabled={busy} onClick={() => void acceptWork()}>明确接受当前作品版本</button>
            </section>
          ) : null}

          {acceptanceEvidence ? (
            <section className="creator-stage-card creator-delivery-panel" aria-label="证据与交付">
              <div className="creator-stage-card-heading"><div><span>等级 6 · 隐私扫描与完整性校验</span><h3>生成作品交付包</h3></div><strong>设备日志默认排除</strong></div>
              <div className="creator-delivery-grid">
                <article><h4>查看分享包</h4><p>面向浏览与展示，排除代码和设备日志。</p><button type="button" disabled={busy} onClick={() => void createDelivery(CreatorDeliveryVariant.SHARE)}>生成并下载</button></article>
                <article><h4>可复现项目包</h4><p>包含代码、参数、结构和复现指南；导入后验证等级重置。</p><button type="button" disabled={busy} onClick={() => void createDelivery(CreatorDeliveryVariant.REPRODUCIBLE)}>生成并下载</button></article>
                <article><h4>创作模板包</h4><p>保留可复用目标、方案与产物，不继承原作品证据。</p><button type="button" disabled={busy} onClick={() => void createDelivery(CreatorDeliveryVariant.TEMPLATE)}>生成并下载</button></article>
              </div>
              {deliveries.length ? <ul className="creator-delivery-results">{deliveries.map((item) => <li key={item.id}><strong>{item.title}</strong><span>{item.fileName}</span><code>SHA-256 {item.packageSha256}</code></li>)}</ul> : null}
            </section>
          ) : null}

          {acceptanceEvidence && importContext ? (
            <section className="creator-stage-card creator-reproduction-receipt" aria-label="第二用户复现回执">
              <div className="creator-stage-card-heading"><div><span>受控复现</span><h3>向原作品提交第二用户复现回执</h3></div><strong>当前已认证账户</strong></div>
              <p>只有导入副本重新达到等级 6，且复现者不同于原验收者，服务端才会把原作品标记为“可复现交付”。</p>
              {reproductionReport ? <div className="creator-success"><strong>复现回执已验证</strong><code>SHA-256 {reproductionReport.packageSha256}</code></div> : <button type="button" className="creator-primary-button" disabled={busy} onClick={() => void submitReproductionReceipt()}>提交复现回执</button>}
            </section>
          ) : null}
        </>
      ) : (
        <section className="creator-stage-card creator-empty-canvas"><h3>正在恢复作品设备上下文</h3><p>作品数据尚未加载完成，真实操作保持关闭。</p></section>
      )}
    </div>
  );
}

function currentEvidence(workspace: CreatorWorkspace, kind: CreatorWorkspace["evidence"][number]["kind"]) {
  return workspace.evidence.find((item) => item.kind === kind && item.status === "CURRENT" && item.passed) ?? null;
}

function toggleSet(current: Set<string>, id: string, checked: boolean): Set<string> {
  const next = new Set(current);
  if (checked) next.add(id);
  else next.delete(id);
  return next;
}

function channelLabel(value: string): string {
  if (value === "USB_SERIAL") return "USB 串口";
  if (value === "ESP_CLAW") return "ESP-Claw";
  return value;
}

function errorMessage(reason: unknown): string {
  return reason instanceof Error ? reason.message : "设备证据操作失败，请检查本地服务后重试。";
}

function downloadDelivery(delivery: CreatorDeliveryRecord): void {
  if (!delivery.zipBase64) return;
  const binary = globalThis.atob(delivery.zipBase64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  const url = URL.createObjectURL(new Blob([bytes], { type: "application/zip" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = delivery.fileName;
  anchor.click();
  URL.revokeObjectURL(url);
}
