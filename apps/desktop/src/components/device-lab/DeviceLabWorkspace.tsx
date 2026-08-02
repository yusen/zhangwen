import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import "@wokwi/elements";
import {
  SupportedDeviceBoardId,
  type DeviceBoardCapability,
  type DeviceBoardListResponse,
  type DeviceLabChannel,
  type DeviceLabEvent,
  type DeviceLabProfileV1,
  type DeviceLabRun,
  type DeviceLabSceneV1,
  type DeviceOperation,
  type DeviceSession,
  type FirmwareApplicationInstallPlan,
  type FirmwareApplicationListResponse,
  type ParameterSetRevision,
} from "@zhangwen/contracts";
import {
  applyParameterSet,
  createDeviceLabRun,
  fileToBase64,
  getCurrentDeviceLabSession,
  getDeviceLabScene,
  getDeviceLabOperation,
  installFirmwareApplication,
  importFirmwareApplication,
  listDeviceLabBoards,
  listFirmwareApplications,
  listParameterSets,
  prepareFirmwareApplicationInstall,
  readDeviceLabEvents,
  saveParameterSet,
  stopDeviceLabRun,
  syncParameterSetToDevice,
  updateDeviceLabChannel,
} from "../../services/deviceLabApi";
import { StableIntentKeyStore } from "../../utils/stableIntentKey";

export interface DeviceLabWorkspaceProps {
  projectId: string;
  professionalMode: boolean;
  solutionRevisionId?: string | null;
  codeRunId?: string | null;
  embedded?: boolean;
  variant?: "cards" | "prototype";
  codeVersionLabel?: string;
  focusMode?: boolean;
  onFocusModeChange?: (focused: boolean) => void;
  mobileView?: "code" | "simulation" | "terminal" | "debug";
  onBackToChat?: () => void;
  onSceneChange?: (scene: DeviceLabSceneV1 | null) => void;
  onRunChange?: (run: DeviceLabRun | null) => void;
}

export function DeviceLabWorkspace({
  projectId,
  professionalMode,
  solutionRevisionId = null,
  codeRunId = null,
  embedded = false,
  variant = "cards",
  codeVersionLabel,
  focusMode = false,
  onFocusModeChange,
  mobileView = "simulation",
  onBackToChat,
  onSceneChange,
  onRunChange,
}: DeviceLabWorkspaceProps) {
  const [catalog, setCatalog] = useState<DeviceBoardListResponse | null>(null);
  const [scene, setScene] = useState<DeviceLabSceneV1 | null>(null);
  const [profile, setProfile] = useState<DeviceLabProfileV1 | null>(null);
  const [applications, setApplications] = useState<FirmwareApplicationListResponse | null>(null);
  const [parameterSets, setParameterSets] = useState<ParameterSetRevision[]>([]);
  const [deviceSession, setDeviceSession] = useState<DeviceSession | null>(null);
  const [deviceOperation, setDeviceOperation] = useState<DeviceOperation | null>(null);
  const [installPlan, setInstallPlan] = useState<FirmwareApplicationInstallPlan | null>(null);
  const [installPhrase, setInstallPhrase] = useState("");
  const [syncConfirmed, setSyncConfirmed] = useState(false);
  const [run, setRun] = useState<DeviceLabRun | null>(null);
  const [events, setEvents] = useState<DeviceLabEvent[]>([]);
  const [actuatorArmed, setActuatorArmed] = useState(false);
  const [parameterLabel, setParameterLabel] = useState("调试参数");
  const [selectedParameterSet, setSelectedParameterSet] = useState("");
  const [debugOpen, setDebugOpen] = useState(false);
  const [debugSection, setDebugSection] = useState<"sensors" | "actuators" | "parameters">("sensors");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement | null>(null);
  const intentKeys = useRef(new StableIntentKeyStore("device-lab"));
  const lastEventRevision = events.at(-1)?.revision ?? 0;
  const boardId = scene?.boardId ?? null;
  const board = useMemo(
    () => boardId ? catalog?.boards.find((item) => item.id === boardId) ?? null : null,
    [boardId, catalog?.boards],
  );
  const selectedRevision = useMemo(
    () => parameterSets.find((item) => item.id === selectedParameterSet) ?? null,
    [parameterSets, selectedParameterSet],
  );
  const parameterComparison = useMemo(() => {
    if (!selectedRevision || !profile || !run) return [];
    return profile.channels
      .filter((channel) => channel.kind === "parameter")
      .map((channel) => ({
        id: channel.id,
        label: channel.label,
        current: run.channelValues[channel.id],
        saved: selectedRevision.values[channel.id],
      }))
      .filter((item) => item.current !== item.saved);
  }, [profile, run, selectedRevision]);
  const prototypeChannels = useMemo(() => {
    const channels = profile?.channels ?? [];
    const inputIds = new Set(
      (scene?.testCases ?? []).flatMap((testCase) => testCase.inputChannelIds),
    );
    const sensors = channels.filter((channel) => (
      channel.kind === "sensor-input"
      && (
        inputIds.has(channel.id)
        || (!inputIds.size && channel.source === "project-scene")
      )
    ));
    const componentIds = new Set(
      sensors.map((channel) => channel.componentId).filter((value): value is string => Boolean(value)),
    );
    const actuators = channels.filter((channel) => (
      channel.kind === "actuator"
      && (
        channel.source === "project-scene"
        || (typeof channel.componentId === "string" && componentIds.has(channel.componentId))
      )
    ));
    const parameters = channels.filter((channel) => (
      channel.kind === "parameter"
      && (
        channel.source === "project-scene"
        || (channel.id === "sample-interval-ms" && sensors.length > 0)
        || (typeof channel.componentId === "string" && componentIds.has(channel.componentId))
      )
    ));
    return { sensors, actuators, parameters };
  }, [profile?.channels, scene?.testCases]);

  useEffect(() => {
    onSceneChange?.(scene);
  }, [onSceneChange, scene]);

  useEffect(() => {
    onRunChange?.(run);
  }, [onRunChange, run]);

  useEffect(() => {
    const controller = new AbortController();
    setScene(null);
    setProfile(null);
    setRun(null);
    setEvents([]);
    setError(null);
    Promise.all([
      listDeviceLabBoards(controller.signal),
      getDeviceLabScene(projectId, controller.signal),
      listFirmwareApplications(projectId, controller.signal),
      listParameterSets(projectId, controller.signal),
      getCurrentDeviceLabSession(projectId, controller.signal)
        .then((response) => response.session)
        .catch(() => null),
    ]).then(([nextCatalog, nextScene, nextApplications, nextParameters, nextSession]) => {
      setCatalog(nextCatalog);
      setScene(nextScene.scene);
      setProfile(nextScene.profile);
      setApplications(nextApplications);
      setParameterSets(nextParameters.parameterSets);
      setDeviceSession(nextSession);
    }).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(errorMessage(reason));
    });
    return () => controller.abort();
  }, [codeRunId, projectId, solutionRevisionId]);

  useEffect(() => {
    if (!run || run.status !== "RUNNING") return undefined;
    const controller = new AbortController();
    const timer = globalThis.setInterval(() => {
      void readDeviceLabEvents(projectId, run.id, lastEventRevision, controller.signal)
        .then((items) => setEvents((current) => mergeEvents(current, items)))
        .catch(() => undefined);
    }, 1000);
    return () => {
      controller.abort();
      globalThis.clearInterval(timer);
    };
  }, [lastEventRevision, projectId, run]);

  useEffect(() => {
    if (!deviceOperation || !["QUEUED", "RUNNING"].includes(deviceOperation.status)) return undefined;
    const timer = globalThis.setInterval(() => {
      void getDeviceLabOperation(projectId, deviceOperation.id)
        .then((response) => setDeviceOperation(response.operation))
        .catch(() => undefined);
    }, 800);
    return () => globalThis.clearInterval(timer);
  }, [deviceOperation, projectId]);

  const start = async () => {
    if (!scene) return;
    setBusy(true);
    setError(null);
    setEvents([]);
    const request = {
      target: "SIMULATOR" as const,
      parameterSetId: selectedParameterSet || null,
      expectedSceneRevision: scene.revision,
      expectedSolutionRevisionId: solutionRevisionId,
      codeRunId,
    };
    const intentScope = `start-run:${projectId}`;
    try {
      const response = await createDeviceLabRun(projectId, {
        ...request,
        idempotencyKey: intentKeys.current.key(intentScope, request),
      });
      intentKeys.current.complete(intentScope);
      setRun(response.run);
      setProfile(response.profile);
      if (response.run.scene) setScene(response.run.scene);
      const initial = await readDeviceLabEvents(projectId, response.run.id, 0);
      setEvents(initial);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  };

  const stop = async () => {
    if (!run) return;
    setBusy(true);
    try {
      const response = await stopDeviceLabRun(projectId, run.id);
      setRun(response.run);
      setProfile(response.profile);
      setActuatorArmed(false);
      const nextEvents = await readDeviceLabEvents(
        projectId,
        run.id,
        lastEventRevision,
      );
      setEvents((current) => mergeEvents(current, nextEvents));
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  };

  const setChannel = async (channel: DeviceLabChannel, value: number | boolean | string) => {
    if (!run) return;
    setError(null);
    try {
      const response = await updateDeviceLabChannel(projectId, run.id, channel.id, {
        value,
        expectedRevision: run.revision,
        actuatorArmed,
        commandId: commandId(channel.id),
      });
      setRun(response.run);
      setProfile(response.profile);
    } catch (reason) {
      setError(errorMessage(reason));
    }
  };

  const saveParameters = async () => {
    if (!profile || !run || !boardId) return;
    setBusy(true);
    try {
      const values: Record<string, number | boolean | string> = {};
      profile.channels
        .filter((channel) => channel.kind === "parameter")
        .forEach((channel) => {
          const value = run.channelValues[channel.id];
          if (value !== undefined) values[channel.id] = value;
        });
      const request = {
        boardId,
        profileRevision: profile.revision,
        label: parameterLabel,
        values,
      };
      const intentScope = `save-parameters:${projectId}`;
      const response = await saveParameterSet(projectId, {
        ...request,
        idempotencyKey: intentKeys.current.key(intentScope, request),
      });
      intentKeys.current.complete(intentScope);
      setParameterSets((current) => [response.parameterSet, ...current]);
      setSelectedParameterSet(response.parameterSet.id);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  };

  const applyParameters = async () => {
    if (!run || !selectedParameterSet) return;
    setBusy(true);
    try {
      const response = await applyParameterSet(projectId, run.id, {
        parameterSetId: selectedParameterSet,
        expectedRevision: run.revision,
      });
      setRun(response.run);
      setProfile(response.profile);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  };

  const importApplication = async (file: File) => {
    setBusy(true);
    setError(null);
    try {
      await importFirmwareApplication(projectId, { zipBase64: await fileToBase64(file) });
      setApplications(await listFirmwareApplications(projectId));
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  const prepareInstall = async (applicationId: string) => {
    if (!boardId || !deviceSession || deviceSession.board !== boardId) {
      setError("请先在右侧设备页连接并确认与立项实物场景一致的精确板型。");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const response = await prepareFirmwareApplicationInstall(projectId, {
        sessionId: deviceSession.id,
        applicationId,
        boardId,
        confirmBoardIdentity: true,
      });
      setInstallPlan(response.plan);
      setInstallPhrase("");
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  };

  const installApplication = async () => {
    if (!installPlan || !deviceSession) return;
    setBusy(true);
    setError(null);
    const request = {
      sessionId: deviceSession.id,
      applicationId: installPlan.applicationId,
      confirmationToken: installPlan.confirmationToken,
      confirmInstall: true,
      confirmationPhrase: installPhrase,
    };
    const semanticIntent = {
      sessionId: request.sessionId,
      applicationId: request.applicationId,
      confirmInstall: request.confirmInstall,
    };
    const intentScope = `install-application:${projectId}`;
    try {
      const response = await installFirmwareApplication(projectId, {
        ...request,
        operationId: intentKeys.current.key(intentScope, semanticIntent),
      });
      intentKeys.current.complete(intentScope);
      setDeviceOperation(response.operation);
      setInstallPlan(null);
      setInstallPhrase("");
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  };

  const syncParameters = async () => {
    if (!boardId || !selectedParameterSet || !deviceSession || !syncConfirmed) return;
    if (deviceSession.board !== boardId) {
      setError("参数版本与当前设备会话板型不一致。");
      return;
    }
    setBusy(true);
    setError(null);
    const request = {
      sessionId: deviceSession.id,
      parameterSetId: selectedParameterSet,
      confirmSync: true,
    };
    const intentScope = `sync-parameters:${projectId}`;
    try {
      const response = await syncParameterSetToDevice(projectId, selectedParameterSet, {
        sessionId: request.sessionId,
        operationId: intentKeys.current.key(intentScope, request),
        confirmSync: request.confirmSync,
      });
      intentKeys.current.complete(intentScope);
      setDeviceOperation(response.operation);
      setSyncConfirmed(false);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  };

  const restart = async () => {
    if (run?.status === "RUNNING") {
      await stop();
    }
    await start();
  };

  if (variant === "prototype") {
    return (
      <main className="device-lab-workspace device-lab-prototype" aria-label="数字原型仿真" data-testid="device-lab-workspace">
        <header className="device-lab-prototype-toolbar">
          <div className="device-lab-prototype-binding">
            <strong>{codeVersionLabel ?? "等待代码版本"}</strong>
            <span>{run ? engineLabel(run) : "功能仿真"}</span>
          </div>
          <label>
            参数
            <select aria-label="参数版本" value={selectedParameterSet} onChange={(event) => setSelectedParameterSet(event.target.value)}>
              <option value="">默认</option>
              {parameterSets.filter(
                (item) => item.boardId === boardId && item.profileRevision === profile?.revision,
              ).map((item) => (
                <option key={item.id} value={item.id}>v{item.revision}</option>
              ))}
            </select>
          </label>
          <div className="device-lab-prototype-actions">
            <button type="button" disabled={busy || !catalog || !scene || run?.status === "RUNNING"} onClick={() => void start()}>▶ 启动</button>
            <button type="button" disabled={busy || run?.status !== "RUNNING"} onClick={() => void stop()}>Ⅱ 暂停</button>
            <button type="button" disabled={busy || !scene} onClick={() => void restart()}>↻ 重启</button>
            <button type="button" className="is-danger" disabled={busy || run?.status !== "RUNNING"} onClick={() => void stop()}>■ 安全停止</button>
            <button
              type="button"
              aria-expanded={debugOpen || mobileView === "debug"}
              aria-controls="device-lab-debug-panel"
              onClick={() => setDebugOpen((current) => !current)}
            >
              调试
            </button>
            {onFocusModeChange ? (
              <button type="button" aria-pressed={focusMode} onClick={() => onFocusModeChange(!focusMode)}>
                {focusMode ? "退出专注" : "专注模式"}
              </button>
            ) : null}
          </div>
        </header>

        {error ? <div className="device-lab-alert" role="alert">{error}</div> : null}
        {scene?.warnings.map((warning) => (
          <div key={warning} className="device-lab-alert is-warning" role="status">{warning}</div>
        ))}

        <div className="device-lab-prototype-body">
          <div className="device-lab-prototype-surface">
            <section className={`device-lab-prototype-canvas${mobileView === "simulation" ? " is-mobile-active" : ""}`} aria-label="器件和连线画布">
              {board && scene ? <BoardCanvas board={board} scene={scene} run={run} /> : (
                <div className="device-lab-prototype-empty">
                  <strong>正在从已确认方案创建场景</strong>
                  <span>器件、IO 与供电来自方案，不需要重新搭建。</span>
                </div>
              )}
              <span className="device-lab-capability-badge">
                {run?.engine === "QEMU_ESP32S3" ? "固件仿真" : "功能仿真"}
              </span>
            </section>
            <section className={`device-lab-prototype-terminal${mobileView === "terminal" ? " is-mobile-active" : ""}`} aria-label="UART 与事件终端">
              <header><strong>UART / 事件</strong><span>{run?.status ?? "STOPPED"}</span></header>
              <ol>
                {events.length ? events.slice(-100).map((event) => (
                  <li key={`${event.revision}-${event.type}`}>
                    <time>{String(event.revision).padStart(4, "0")}</time>
                    <span>{event.type}</span>
                    <code>{event.message}</code>
                  </li>
                )) : <li><code>启动仿真后显示 UART 与功能模型事件。</code></li>}
              </ol>
            </section>
          </div>

          <aside
            id="device-lab-debug-panel"
            className={`device-lab-debug-panel${debugOpen ? " is-open" : ""}${mobileView === "debug" ? " is-mobile-active" : ""}`}
            aria-label="项目调试"
            aria-hidden={!debugOpen && mobileView !== "debug"}
          >
            <header>
              <div>
                <strong>项目调试</strong>
                <span>内容由当前方案与验收场景生成</span>
              </div>
              <button type="button" aria-label="关闭调试面板" onClick={() => setDebugOpen(false)}>×</button>
            </header>
            <nav aria-label="调试类型">
              {([
                ["sensors", "项目输入"],
                ["actuators", "执行器"],
                ["parameters", "参数"],
              ] as const).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  aria-pressed={debugSection === id}
                  onClick={() => setDebugSection(id)}
                >
                  {label}
                </button>
              ))}
            </nav>
            <div className="device-lab-debug-content">
              {debugSection === "sensors" ? (
                <>
                  <div className="device-lab-test-cases">
                    <strong>{scene?.testCases?.length ?? 0} 个项目验收场景</strong>
                    {(scene?.testCases ?? []).map((testCase) => (
                      <article key={testCase.id}>
                        <span>{testCase.title}</span>
                        <p>{testCase.expectedBehavior}</p>
                      </article>
                    ))}
                  </div>
                  <ChannelList channels={prototypeChannels.sensors} run={run} onChange={setChannel} emptyMessage="当前方案没有需要人工注入的传感器输入。" />
                </>
              ) : null}
              {debugSection === "actuators" ? (
                <>
                  <label className="device-lab-arm">
                    <input
                      type="checkbox"
                      checked={actuatorArmed}
                      disabled={!run || run.status !== "RUNNING"}
                      onChange={(event) => setActuatorArmed(event.target.checked)}
                    />
                    解锁执行器调试
                  </label>
                  <p className="device-lab-note">停止或断线后自动回到安全值。</p>
                  <ChannelList channels={prototypeChannels.actuators} run={run} disabled={!actuatorArmed} onChange={setChannel} emptyMessage="当前方案没有可调试执行器。" />
                </>
              ) : null}
              {debugSection === "parameters" ? (
                <>
                  <ChannelList channels={prototypeChannels.parameters} run={run} onChange={setChannel} emptyMessage="当前方案没有可保存参数。" />
                  <label className="device-lab-parameter-label">
                    版本说明
                    <input value={parameterLabel} maxLength={100} onChange={(event) => setParameterLabel(event.target.value)} />
                  </label>
                  <div className="device-lab-inline-actions">
                    <button type="button" disabled={!run || busy} onClick={() => void saveParameters()}>保存新版本</button>
                    <button type="button" disabled={!run || !selectedParameterSet || busy} onClick={() => void applyParameters()}>应用到仿真</button>
                  </div>
                </>
              ) : null}
            </div>
          </aside>
        </div>
      </main>
    );
  }

  return (
    <main className="device-lab-workspace" aria-label="设备实验室" data-testid="device-lab-workspace">
      <header className={`device-lab-header${embedded ? " is-embedded" : ""}`}>
        <div>
          <span className="v2-eyebrow">方案驱动 · 双板设备实验室</span>
          <h1>项目实物仿真</h1>
          <p>根据已确认方案、项目硬件和 IO Map 自动创建整套实物场景。</p>
        </div>
        <div className="device-lab-header-actions">
          {!embedded && onBackToChat ? <button type="button" className="zw-secondary-btn" onClick={onBackToChat}>返回对话</button> : null}
          {run?.status === "RUNNING" ? (
            <button type="button" className="zw-danger-btn" disabled={busy} onClick={() => void stop()}>安全停止</button>
          ) : (
            <button type="button" className="zw-primary-btn" disabled={busy || !catalog || !scene} onClick={() => void start()}>启动仿真</button>
          )}
        </div>
      </header>

      {error && <div className="device-lab-alert" role="alert">{error}</div>}
      {scene?.warnings.map((warning) => (
        <div key={warning} className="device-lab-alert is-warning" role="status">{warning}</div>
      ))}

      <section className="device-lab-toolbar" aria-label="仿真目标">
        <div className="device-lab-scene-source" aria-label="方案自动生成场景">
          <span>自动生成场景</span>
          <strong>{board?.displayName ?? "等待已确认方案"}</strong>
          <small>
            {scene
              ? `方案 v${scene.source.proposalVersion} · ${scene.components.length} 个实物组件 · ${scene.status === "READY" ? "接线已确认" : "待确认 IO"}`
              : "不允许在实验室中手动替换主控板"}
          </small>
        </div>
        <label>
          参数版本
          <select aria-label="参数版本" value={selectedParameterSet} onChange={(event) => setSelectedParameterSet(event.target.value)}>
            <option value="">默认参数</option>
            {parameterSets.filter(
              (item) => item.boardId === boardId && item.profileRevision === profile?.revision,
            ).map((item) => (
              <option key={item.id} value={item.id}>v{item.revision} · {item.label}</option>
            ))}
          </select>
        </label>
        <span className="device-lab-engine">
          {run ? engineLabel(run) : "等待启动"}
          {professionalMode && catalog ? ` · QEMU ${catalog.qemu.available ? catalog.qemu.version : "未安装"}` : ""}
        </span>
        <span className="device-lab-device-session">
          {deviceSession ? `真机：${deviceSession.board}` : "真机：未连接"}
        </span>
      </section>

      <div className="device-lab-grid">
        <section className="device-lab-card device-lab-canvas" aria-label="板卡仿真画布">
          {board && scene && <BoardCanvas board={board} scene={scene} run={run} />}
          <p className="device-lab-disclaimer">
            {run?.engine === "QEMU_ESP32S3"
              ? "固件运行由本地 ESP32-S3 QEMU 承担，板载外设由功能桥接器提供。"
              : "当前为本地功能模型，不代表固件执行、总线时序或真实电气行为。"}
          </p>
        </section>

        <section className="device-lab-card" aria-label="传感器输入">
          <h2>传感器输入</h2>
          <ChannelList
            channels={profile?.channels.filter((channel) => channel.kind === "sensor-input") ?? []}
            run={run}
            onChange={setChannel}
          />
        </section>

        <section className="device-lab-card" aria-label="执行器调试">
          <div className="device-lab-card-title">
            <h2>执行器调试</h2>
            <label className="device-lab-arm">
              <input
                type="checkbox"
                checked={actuatorArmed}
                disabled={!run || run.status !== "RUNNING"}
                onChange={(event) => setActuatorArmed(event.target.checked)}
              />
              解锁调试
            </label>
          </div>
          <ChannelList
            channels={profile?.channels.filter((channel) => channel.kind === "actuator") ?? []}
            run={run}
            disabled={!actuatorArmed}
            onChange={setChannel}
          />
          <p className="device-lab-note">停止、断线或重开会话后，执行器不会自动恢复输出。</p>
        </section>

        <section className="device-lab-card" aria-label="参数保存">
          <div className="device-lab-card-title"><h2>参数版本</h2><span>先保存，再明确应用</span></div>
          <ChannelList
            channels={profile?.channels.filter((channel) => channel.kind === "parameter") ?? []}
            run={run}
            onChange={setChannel}
          />
          <label className="device-lab-parameter-label">
            版本说明
            <input value={parameterLabel} maxLength={100} onChange={(event) => setParameterLabel(event.target.value)} />
          </label>
          <div className="device-lab-inline-actions">
            <button type="button" disabled={!run || busy} onClick={() => void saveParameters()}>保存新版本</button>
            <button type="button" disabled={!run || !selectedParameterSet || busy} onClick={() => void applyParameters()}>应用 / 回滚到仿真</button>
          </div>
          {selectedRevision && run && (
            <div className="device-lab-parameter-compare" aria-label="参数版本比较">
              <strong>当前状态 ↔ v{selectedRevision.revision}</strong>
              {parameterComparison.length ? (
                <ul>{parameterComparison.map((item) => (
                  <li key={item.id}>
                    <span>{item.label}</span>
                    <code>{String(item.current)} → {String(item.saved)}</code>
                  </li>
                ))}</ul>
              ) : <span>参数一致</span>}
            </div>
          )}
          <label className="device-lab-confirm-row">
            <input
              type="checkbox"
              checked={syncConfirmed}
              disabled={!selectedParameterSet || !deviceSession || deviceSession.board !== boardId}
              onChange={(event) => setSyncConfirmed(event.target.checked)}
            />
            确认把所选版本同步到已连接设备的受控数据区
          </label>
          <button
            type="button"
            className="device-lab-sync-button"
            disabled={!syncConfirmed || busy}
            onClick={() => void syncParameters()}
          >
            同步 / 回滚到真机
          </button>
        </section>

        <section className="device-lab-card device-lab-events" aria-label="调试事件">
          <h2>运行事件</h2>
          {events.length ? (
            <ol>{events.slice(-12).reverse().map((event) => (
              <li key={`${event.revision}-${event.type}`}><span>{event.type}</span><strong>{event.message}</strong></li>
            ))}</ol>
          ) : <p>启动后显示传感器、执行器和运行状态。</p>}
        </section>

        {professionalMode && <section className="device-lab-card device-lab-applications" aria-label="设备运行时初始化与恢复">
          <div className="device-lab-card-title"><h2>运行时初始化 / 恢复</h2><span>独立于日常代码上传</span></div>
          <p className="device-lab-note">这里只安装或恢复固定 ESP-Claw / ESP-IDF 运行时；项目代码请在右侧“设备”页选择 ESP-Claw 上传。</p>
          <div className="device-lab-app-list">
            {applications?.curated.filter((item) => item.boardId === boardId).map((item) => (
              <article key={item.applicationId}><strong>{item.displayName}</strong><span>{item.bundled ? "已内置" : "等待导入已验证应用包"}</span></article>
            ))}
            {applications?.applications.filter((item) => item.manifest.boardId === boardId).map((item) => (
              <article key={item.id}>
                <strong>{item.manifest.displayName} {item.manifest.version}</strong>
                <span>{item.simulationCapability === "FULL" ? "可固件级仿真" : "仅安装或 UART 检查"}</span>
                <button type="button" disabled={busy || deviceSession?.board !== boardId} onClick={() => void prepareInstall(item.id)}>准备安装</button>
              </article>
            ))}
          </div>
          {installPlan && (
            <div className="device-lab-install-confirm" role="group" aria-label="应用安装确认">
              <strong>{installPlan.summary}</strong>
              <span>{installPlan.segmentCount} 段 · {installPlan.totalBytes} bytes</span>
              <label>
                输入“安装应用”
                <input value={installPhrase} onChange={(event) => setInstallPhrase(event.target.value)} />
              </label>
              <button type="button" disabled={busy || installPhrase !== "安装应用"} onClick={() => void installApplication()}>确认安装</button>
            </div>
          )}
          <input
            ref={fileInput}
            type="file"
            accept=".zip,.zwapp"
            aria-label="导入运行时应用包"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void importApplication(file);
            }}
          />
          <p className="device-lab-note">只接受双板 manifest；不会执行整片擦除，也不会保存 Wi-Fi 密码。</p>
          {deviceOperation && (
            <p className="device-lab-operation" role="status">
              {deviceOperation.kind} · {deviceOperation.status} · {deviceOperation.progress}% · {deviceOperation.log}
            </p>
          )}
        </section>}
      </div>
    </main>
  );
}

function BoardCanvas({
  board,
  scene,
  run,
}: {
  board: DeviceBoardCapability;
  scene: DeviceLabSceneV1;
  run: DeviceLabRun | null;
}) {
  const k10 = board.id === SupportedDeviceBoardId.DFROBOT_K10;
  const visibleComponents = scene.components.filter((item) => item.role !== "onboard");
  const positions = circuitPositions(visibleComponents);
  const visibleConnections = scene.connections.filter(
    (item) => item.protocol !== "BOARD_INTERNAL"
      && positions.has(item.fromComponentId)
      && positions.has(item.toComponentId),
  );
  return (
    <div className="device-lab-circuit" data-testid="device-lab-circuit">
      <svg className="device-lab-wire-layer" viewBox="0 0 1000 620" role="img" aria-label={`项目接线，共 ${visibleConnections.length} 条`}>
        <defs>
          <marker id="device-lab-wire-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth">
            <path d="M0,0 L8,4 L0,8 z" />
          </marker>
        </defs>
        {visibleConnections.map((connection) => {
          const from = positions.get(connection.fromComponentId);
          const to = positions.get(connection.toComponentId);
          if (!from || !to) return null;
          const mqtt = connection.protocol === "MQTT";
          return (
            <g
              key={connection.id}
              className={`device-lab-wire${connection.confidence === "PROPOSAL_DERIVED" ? " is-pending" : ""}${mqtt ? " is-network" : ""}`}
              data-confidence={connection.confidence}
              data-protocol={connection.protocol}
            >
              <line
                x1={from.x * 10}
                y1={from.y * 6.2}
                x2={to.x * 10}
                y2={to.y * 6.2}
                markerEnd="url(#device-lab-wire-arrow)"
              />
              <text x={(from.x + to.x) * 5} y={(from.y + to.y) * 3.1 - 6}>
                {connection.pin ? `${connection.signal} · ${connection.pin}` : connection.signal}
              </text>
            </g>
          );
        })}
      </svg>

      {visibleComponents.map((component) => {
        const position = positions.get(component.id);
        if (!position) return null;
        const style = {
          "--circuit-x": `${position.x}%`,
          "--circuit-y": `${position.y}%`,
        } as CSSProperties;
        if (component.role === "controller") {
          return (
            <article key={component.id} className={`device-lab-circuit-node is-controller ${k10 ? "is-k10" : "is-xiao"}`} style={style}>
              <div className="device-lab-board-screen">
                <span>{k10 ? "240 × 320 LCD" : "XIAO S3 Sense"}</span>
                <strong>{run?.status === "RUNNING" ? "RUNNING" : "STOPPED"}</strong>
              </div>
              <div className="device-lab-board-elements" aria-label="Wokwi Elements 板载交互">
                {k10 ? (
                  <>
                    <wokwi-pushbutton color="green" label="A" />
                    <wokwi-pushbutton color="blue" label="B" />
                    <wokwi-led color="red" value={Number(run?.channelValues["rgb-brightness"] ?? 0) > 0} />
                    <wokwi-led color="green" value={Number(run?.channelValues["rgb-brightness"] ?? 0) > 0} />
                    <wokwi-led color="blue" value={Number(run?.channelValues["rgb-brightness"] ?? 0) > 0} />
                  </>
                ) : (
                  <>
                    <wokwi-slide-switch value={Boolean(run?.channelValues["sd-mounted"] ?? true)} />
                    <wokwi-led color="yellow" value={Boolean(run?.channelValues["user-led"] ?? false)} />
                  </>
                )}
              </div>
              <strong>{board.displayName}</strong>
              <span>{board.peripherals.slice(0, 3).join(" · ")}</span>
            </article>
          );
        }
        return (
          <article
            key={component.id}
            className={`device-lab-circuit-node is-${component.category.toLowerCase()}`}
            style={style}
            data-simulation={component.simulation}
          >
            <ExternalComponentVisual component={component} />
            <strong>{component.name}</strong>
            <span>{component.protocol ?? "待确认接口"}</span>
          </article>
        );
      })}

      <div className="device-lab-wire-legend" aria-label="接线图例">
        <span><i className="is-confirmed" />已确认</span>
        <span><i className="is-pending" />待确认</span>
        {visibleConnections.some((item) => item.protocol === "MQTT") ? <span><i className="is-network" />本地消息</span> : null}
      </div>
      {board.pinConflicts.map((conflict) => <small className="device-lab-pin-conflict" key={conflict.message}>{conflict.message}</small>)}
    </div>
  );
}

interface CircuitPoint {
  x: number;
  y: number;
}

function circuitPositions(
  components: DeviceLabSceneV1["components"],
): Map<string, CircuitPoint> {
  const result = new Map<string, CircuitPoint>();
  const controller = components.find((item) => item.role === "controller");
  if (controller) result.set(controller.id, { x: 50, y: 42 });
  const sensors = components.filter((item) => item.category === "SENSOR");
  const outputs = components.filter((item) => ["ACTUATOR", "DISPLAY"].includes(item.category));
  const power = components.filter((item) => item.category === "POWER");
  const services = components.filter((item) => item.category === "SERVICE");
  const structures = components.filter((item) => item.category === "STRUCTURE");
  placeCircuitColumn(result, sensors, 13, 17, 69);
  placeCircuitColumn(result, outputs, 84, 15, 68);
  placeCircuitColumn(result, power, 70, 82, 90);
  placeCircuitColumn(result, services, 28, 83, 91);
  placeCircuitColumn(result, structures, 50, 86, 92);
  return result;
}

function placeCircuitColumn(
  positions: Map<string, CircuitPoint>,
  components: DeviceLabSceneV1["components"],
  x: number,
  startY: number,
  endY: number,
): void {
  components.forEach((component, index) => {
    const ratio = components.length <= 1 ? 0.5 : index / (components.length - 1);
    positions.set(component.id, { x, y: startY + ((endY - startY) * ratio) });
  });
}

function ExternalComponentVisual({
  component,
}: {
  component: DeviceLabSceneV1["components"][number];
}) {
  const name = component.name.toLocaleLowerCase();
  if (component.category === "SENSOR") return <wokwi-potentiometer />;
  if (component.category === "ACTUATOR" && /servo|舵机/i.test(name)) return <wokwi-servo />;
  if (component.category === "ACTUATOR" && /led|灯|rgb/i.test(name)) return <wokwi-led color="green" />;
  if (component.category === "DISPLAY" && /oled|ssd1306/i.test(name)) return <wokwi-ssd1306 />;
  if (component.category === "POWER") return <span className="device-lab-visual-placeholder" aria-hidden="true">5V</span>;
  if (component.category === "SERVICE") return <span className="device-lab-visual-placeholder is-service" aria-hidden="true">MQTT</span>;
  if (component.category === "ACTUATOR") return <span className="device-lab-visual-placeholder" aria-hidden="true">OUT</span>;
  return <span className="device-lab-visual-placeholder" aria-hidden="true">IO</span>;
}

function ChannelList({
  channels,
  run,
  disabled = false,
  emptyMessage = "当前板型没有这类通道。",
  onChange,
}: {
  channels: DeviceLabChannel[];
  run: DeviceLabRun | null;
  disabled?: boolean;
  emptyMessage?: string;
  onChange: (channel: DeviceLabChannel, value: number | boolean | string) => Promise<void>;
}) {
  if (!channels.length) return <p className="device-lab-empty-channel">{emptyMessage}</p>;
  return <div className="device-lab-channels">{channels.map((channel) => {
    const value = run?.channelValues[channel.id] ?? channel.defaultValue;
    const inputDisabled = disabled || !run || run.status !== "RUNNING";
    return (
      <label key={channel.id}>
        <span>{channel.label}<small>{channel.unit ?? ""}</small></span>
        {channel.valueType === "boolean" ? (
          <input type="checkbox" checked={Boolean(value)} disabled={inputDisabled} onChange={(event) => void onChange(channel, event.target.checked)} />
        ) : channel.valueType === "string" ? (
          <select value={String(value)} disabled={inputDisabled} onChange={(event) => void onChange(channel, event.target.value)}>
            {channel.id === "fault-mode" ? (
              <><option value="none">无故障</option><option value="sensor-disconnected">传感器断线</option><option value="noisy-input">输入噪声</option><option value="stalled-input">输入冻结</option></>
            ) : (
              <><option value="color-bars">彩条测试图</option><option value="classroom">教室样例</option><option value="dark">暗场样例</option></>
            )}
          </select>
        ) : (
          <div className="device-lab-number-control">
            {channel.control === "slider" || channel.control === "waveform" ? (
              <input
                type="range"
                min={channel.minimum ?? undefined}
                max={channel.maximum ?? undefined}
                step={channel.step ?? undefined}
                value={Number(value)}
                disabled={inputDisabled}
                onChange={(event) => void onChange(channel, Number(event.target.value))}
              />
            ) : null}
            <input
              type="number"
              aria-label={channel.label}
              min={channel.minimum ?? undefined}
              max={channel.maximum ?? undefined}
              step={channel.step ?? undefined}
              value={Number(value)}
              disabled={inputDisabled}
              onChange={(event) => void onChange(channel, Number(event.target.value))}
            />
          </div>
        )}
      </label>
    );
  })}</div>;
}

function engineLabel(run: DeviceLabRun): string {
  if (run.status === "STOPPED") return "已安全停止";
  return run.engine === "QEMU_ESP32S3" ? "ESP32-S3 QEMU 固件仿真" : "双板功能模型";
}

function commandId(channelId: string): string {
  return `lab-${channelId}-${globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`}`;
}

function mergeEvents(current: DeviceLabEvent[], incoming: DeviceLabEvent[]): DeviceLabEvent[] {
  const byRevision = new Map(current.map((event) => [event.revision, event]));
  incoming.forEach((event) => byRevision.set(event.revision, event));
  return [...byRevision.values()].sort((left, right) => left.revision - right.revision).slice(-512);
}

function errorMessage(reason: unknown): string {
  return reason instanceof Error ? reason.message : "设备实验室操作失败，请重试。";
}
