import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  CodeRuntime,
  CodeRunStatus,
  DeviceDeploymentChannel,
  DeviceOperationKind,
  DeviceOperationPhase,
  DeviceOperationStatus,
  DeviceSessionStatus,
  DeviceTerminalStatus,
  SupportedDeviceBoardId,
  type CodeRun,
  type DeviceOperation,
  type DeviceOperationStep,
  type DevicePort,
  type DeviceSession,
  type DeviceTerminalSnapshot,
  type EspClawEndpoint,
  type FirmwareCandidate,
  type FirmwareFlashPlan,
  type ProjectWorkspace,
  type SupportedDeviceBoardIdType,
  type WateringSmokeEvidence,
} from "@zhangwen/contracts";
import {
  cancelDeviceOperation,
  clearDeviceTerminal,
  connectDevice,
  deployCodeToDevice,
  disconnectDevice,
  takeoverDevice,
  evaluateWateringSmoke,
  flashFirmware,
  getCurrentCode,
  getCurrentDeviceSession,
  getDeviceTerminal,
  getDeviceOperation,
  getLatestDeviceOperation,
  inspectFirmware,
  listEspClawEndpoints,
  listDevicePorts,
  pairEspClawEndpoint,
  prepareFirmware,
  startDeviceTerminal,
  stopDeviceTerminal,
  unlockDeviceTerminal,
  writeDeviceTerminal,
} from "../../services/projectsApi";
import { ApiError } from "../../services/api";
import { getDeviceLabScene } from "../../services/deviceLabApi";
import { useHostAdapter } from "../../platform";
import { zhCN } from "../../i18n/zh-CN";

export interface DeviceVerifiedTarget {
  id: string;
  boardId: SupportedDeviceBoardIdType;
  channel: import("@zhangwen/contracts").DeviceDeploymentChannelType;
}

interface DevicesTabProps {
  workspace: ProjectWorkspace | null;
  professionalMode: boolean;
  refreshRevision: number;
  onOpenDeviceLab?: () => void;
  onVerifiedTargetChange?: (target: DeviceVerifiedTarget | null) => void;
  onOperationChange?: (operation: DeviceOperation | null) => void;
}

interface ScanError {
  title: string;
  message: string;
}

type ResultState = "complete" | "running" | "pending" | "warning" | "failed" | "unknown";

interface UploadResultItem {
  label: string;
  detail: string;
  state: ResultState;
}

interface UploadOutcome {
  summary: string;
  state: ResultState;
  items: [UploadResultItem, UploadResultItem, UploadResultItem];
  managementChannelWarning: boolean;
  warnings: string[];
}

interface ManagementRecoveryEvidence {
  operationId: string;
  portId: string;
}

interface PendingDeploymentRequest {
  schemaVersion: 2;
  operationId: string;
  codeRunId: string;
  channel: import("@zhangwen/contracts").DeviceDeploymentChannelType;
  targetId: string;
}

type CompatibleVerification = NonNullable<DeviceOperation["verification"]> & {
  deploymentOk?: boolean | null;
  restartOk?: boolean | null;
  runtimeInterruptedOk?: boolean | null;
  runtimeStartedOk?: boolean | null;
  managementChannelOk?: boolean | null;
  warnings?: string[];
};

const FIRMWARE_CONFIRMATION_PHRASE = "烧录固件";
const HARDWARE_RESET_CONFIRMATION_PHRASE = "确认硬件复位";
const PENDING_UPLOAD_STORAGE_PREFIX = "zhangwen:pending-device-upload:";
const OPERATION_POLL_INITIAL_DELAY_MS = 350;
const OPERATION_POLL_INTERVAL_MS = 500;
const OPERATION_POLL_RETRY_BASE_MS = 750;
const OPERATION_POLL_MAX_FAILURES = 4;
const TERMINAL_POLL_INTERVAL_MS = 500;

const SESSION_STATUS_LABELS: Record<string, string> = zhCN.deviceSessionStatuses;
const TERMINAL_STATUS_LABELS: Record<string, string> = zhCN.deviceTerminalStatuses;
const OPERATION_STATUS_LABELS: Record<string, string> = zhCN.deviceOperationStatuses;
const PHASE_LABELS: Record<string, string> = zhCN.deviceOperationPhases;

const TERMINAL_OPERATION_STATUSES = new Set<string>([
  DeviceOperationStatus.DRY_RUN_COMPLETE,
  DeviceOperationStatus.COMPLETED,
  DeviceOperationStatus.BLOCKED,
  DeviceOperationStatus.FAILED,
  DeviceOperationStatus.CANCELED,
  DeviceOperationStatus.TIMED_OUT,
]);

const UPLOAD_READY_SESSION_STATUSES = new Set<string>([
  DeviceSessionStatus.READY,
  DeviceSessionStatus.ATTACHED_UNVERIFIED,
  DeviceSessionStatus.RUNTIME_BUSY,
  DeviceSessionStatus.MANAGED,
]);

const FAILED_OPERATION_STATUSES = new Set<string>([
  DeviceOperationStatus.BLOCKED,
  DeviceOperationStatus.FAILED,
  DeviceOperationStatus.CANCELED,
  DeviceOperationStatus.TIMED_OUT,
]);

const PORT_STATUS_LABELS: Record<string, string> = {
  available: "可用",
  busy: "占用",
  connected: "已连接",
  unknown: "未知",
};

const BOARD_LABELS: Record<SupportedDeviceBoardIdType, string> = {
  [SupportedDeviceBoardId.DFROBOT_K10]: "DFRobot K10",
  [SupportedDeviceBoardId.XIAO_ESP32S3_SENSE]: "Seeed Studio XIAO ESP32S3 Sense",
};

const DEPLOYMENT_CHANNEL_LABELS: Record<
  import("@zhangwen/contracts").DeviceDeploymentChannelType,
  string
> = {
  [DeviceDeploymentChannel.USB_SERIAL]: "USB 串口",
  [DeviceDeploymentChannel.ESP_CLAW]: "ESP-Claw",
};

export function DevicesTab({
  workspace,
  professionalMode,
  refreshRevision,
  onOpenDeviceLab,
  onVerifiedTargetChange,
  onOperationChange,
}: DevicesTabProps) {
  const { capabilities, unsupportedMessage } = useHostAdapter();
  const [ports, setPorts] = useState<DevicePort[]>([]);
  const [selectedBoardId, setSelectedBoardId] = useState<SupportedDeviceBoardIdType>(
    SupportedDeviceBoardId.DFROBOT_K10,
  );
  const [sceneBoard, setSceneBoard] = useState<{
    projectId: string;
    boardId: SupportedDeviceBoardIdType;
  } | null>(null);
  const [deploymentChannel, setDeploymentChannel] = useState<
    import("@zhangwen/contracts").DeviceDeploymentChannelType
  >(DeviceDeploymentChannel.USB_SERIAL);
  const [scanLoading, setScanLoading] = useState(false);
  const [scanError, setScanError] = useState<ScanError | null>(null);
  const [session, setSession] = useState<DeviceSession | null>(null);
  const [codeRun, setCodeRun] = useState<CodeRun | null>(null);
  const [operation, setOperation] = useState<DeviceOperation | null>(null);
  const [terminal, setTerminal] = useState<DeviceTerminalSnapshot | null>(null);
  const [terminalError, setTerminalError] = useState<string | null>(null);
  const [terminalBusy, setTerminalBusy] = useState(false);
  const [smokeBusy, setSmokeBusy] = useState(false);
  const [smokeError, setSmokeError] = useState<string | null>(null);
  const [pendingUploadRequest, setPendingUploadRequest] = useState<PendingDeploymentRequest | null>(null);
  const [espClawEndpoints, setEspClawEndpoints] = useState<EspClawEndpoint[]>([]);
  const [selectedEspClawEndpointId, setSelectedEspClawEndpointId] = useState("");
  const [espClawWebEndpointInput, setEspClawWebEndpointInput] = useState("");
  const [espClawMcpEndpointInput, setEspClawMcpEndpointInput] = useState("");
  const [espClawTrustedLanConfirmed, setEspClawTrustedLanConfirmed] = useState(false);
  const [espClawAdminModeConfirmed, setEspClawAdminModeConfirmed] = useState(false);
  const [espClawBoardConfirmed, setEspClawBoardConfirmed] = useState(false);
  const [espClawBusy, setEspClawBusy] = useState(false);
  const [espClawError, setEspClawError] = useState<string | null>(null);
  const [firmwareCandidate, setFirmwareCandidate] = useState<FirmwareCandidate | null>(null);
  const [firmwarePlan, setFirmwarePlan] = useState<FirmwareFlashPlan | null>(null);
  const [firmwareAddress, setFirmwareAddress] = useState("");
  const [flashRiskConfirmed, setFlashRiskConfirmed] = useState(false);
  const [flashPhrase, setFlashPhrase] = useState("");
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [hardwareResetRequired, setHardwareResetRequired] = useState(false);
  const [hardwareResetPhrase, setHardwareResetPhrase] = useState("");
  const [operationReadError, setOperationReadError] = useState<string | null>(null);
  const [operationPollingPaused, setOperationPollingPaused] = useState(false);
  const [operationReadBusy, setOperationReadBusy] = useState(false);
  const [pollRestartRevision, setPollRestartRevision] = useState(0);
  const [managementRecovery, setManagementRecovery] = useState<ManagementRecoveryEvidence | null>(null);
  const previousRefreshRevision = useRef(refreshRevision);
  const projectId = workspace?.project.id ?? null;
  const projectIdRef = useRef(projectId);
  projectIdRef.current = projectId;
  const projectUpdatedAt = workspace?.project.updatedAt ?? null;
  const preferredHardwareBoardId = useMemo(
    () => preferredProjectBoardId(workspace),
    [workspace],
  );
  const projectBoardId = preferredHardwareBoardId
    ?? (sceneBoard?.projectId === projectId ? sceneBoard.boardId : null);
  const pendingUploadOperationId = pendingUploadRequest?.operationId ?? null;
  const operationRunning = Boolean(
    operation && !TERMINAL_OPERATION_STATUSES.has(operation.status),
  );
  const sessionReady = Boolean(
    session && isUsbSerialSession(session) && UPLOAD_READY_SESSION_STATUSES.has(session.status),
  );
  const uploadOperation = operation?.kind === DeviceOperationKind.UPLOAD_CODE
    ? operation
    : null;
  const uploadOperationChannel = uploadOperation
    ? operationDeploymentChannel(uploadOperation)
    : null;
  const uploadOutcome = useMemo(
    () => (uploadOperation ? deriveDeploymentOutcome(uploadOperation) : null),
    [uploadOperation],
  );
  const selectedEspClawEndpoint = useMemo(
    () => espClawEndpoints.find((endpoint) => endpoint.id === selectedEspClawEndpointId) ?? null,
    [espClawEndpoints, selectedEspClawEndpointId],
  );
  const espClawReady = selectedEspClawEndpoint?.status === "READY"
    && endpointMatchesProjectBoard(selectedEspClawEndpoint, projectBoardId);
  const wateringSmokeEvidence = useMemo(
    () => runtimeEvidence(uploadOperation),
    [uploadOperation],
  );
  const isWateringProject = Boolean(
    acceptedWateringFiles(codeRun)
    || /浇花|土壤湿度|soil|pump/i.test(
      `${workspace?.project.name ?? ""} ${workspace?.project.profile.initialIdea ?? ""}`,
    ),
  );
  const managementChannelRecovered = Boolean(
    uploadOperation
      && sessionReady
      && session
      && managementRecovery?.operationId === uploadOperation.id
      && managementRecovery.portId === session.portId,
  );

  useEffect(() => {
    if (deploymentChannel === DeviceDeploymentChannel.ESP_CLAW) {
      onVerifiedTargetChange?.(
        espClawReady && selectedEspClawEndpoint
          ? {
              id: selectedEspClawEndpoint.id,
              boardId: selectedEspClawEndpoint.boardId,
              channel: DeviceDeploymentChannel.ESP_CLAW,
            }
          : null,
      );
      return;
    }
    onVerifiedTargetChange?.(
      sessionReady && session && isSupportedBoardId(session.board)
        ? {
            id: session.id,
            boardId: session.board,
            channel: DeviceDeploymentChannel.USB_SERIAL,
          }
        : null,
    );
  }, [
    deploymentChannel,
    espClawReady,
    onVerifiedTargetChange,
    selectedEspClawEndpoint,
    session,
    sessionReady,
  ]);

  useEffect(() => {
    onOperationChange?.(operation);
  }, [onOperationChange, operation]);

  const rememberPendingUpload = useCallback((request: PendingDeploymentRequest | null) => {
    if (!projectId) return;
    persistPendingUploadRequest(projectId, request);
    if (projectIdRef.current === projectId) setPendingUploadRequest(request);
  }, [projectId]);

  const scanPorts = useCallback(async () => {
    if (!projectId || !capabilities.serialScan) return;
    setScanLoading(true);
    setScanError(null);
    try {
      const response = await listDevicePorts(projectId);
      setPorts(response.ports);
    } catch (error) {
      setPorts([]);
      setScanError(classifyScanError(error));
    } finally {
      setScanLoading(false);
    }
  }, [capabilities.serialScan, projectId]);

  const refreshEspClawEndpoints = useCallback(async () => {
    if (!projectId) return;
    try {
      const response = await listEspClawEndpoints(projectId);
      setEspClawEndpoints(response.endpoints);
      setSelectedEspClawEndpointId((current) => {
        const eligible = response.endpoints.filter((endpoint) => (
          endpointMatchesProjectBoard(endpoint, projectBoardId)
        ));
        if (eligible.some((endpoint) => endpoint.id === current)) return current;
        return eligible.find((endpoint) => endpoint.status === "READY")?.id
          ?? eligible[0]?.id
          ?? "";
      });
      setEspClawError(null);
    } catch {
      setEspClawEndpoints([]);
      setSelectedEspClawEndpointId("");
    }
  }, [projectBoardId, projectId]);

  useEffect(() => {
    if (!projectId || preferredHardwareBoardId) return;
    const controller = new AbortController();
    void getDeviceLabScene(projectId, controller.signal)
      .then((response) => {
        setSceneBoard({ projectId, boardId: response.scene.boardId });
      })
      .catch(() => {
        if (!controller.signal.aborted) setSceneBoard(null);
      });
    return () => controller.abort();
  }, [preferredHardwareBoardId, projectId, projectUpdatedAt]);

  useEffect(() => {
    if (projectBoardId) setSelectedBoardId(projectBoardId);
  }, [projectBoardId, projectId]);

  useEffect(() => {
    if (!projectId) {
      setPorts([]);
      setScanError(null);
      setSession(null);
      setCodeRun(null);
      setOperation(null);
      setTerminal(null);
      setTerminalError(null);
      setTerminalBusy(false);
      setSmokeBusy(false);
      setSmokeError(null);
      setPendingUploadRequest(null);
      setDeploymentChannel(DeviceDeploymentChannel.USB_SERIAL);
      setEspClawEndpoints([]);
      setSelectedEspClawEndpointId("");
      setEspClawWebEndpointInput("");
      setEspClawMcpEndpointInput("");
      setEspClawTrustedLanConfirmed(false);
      setEspClawAdminModeConfirmed(false);
      setEspClawBoardConfirmed(false);
      setEspClawBusy(false);
      setEspClawError(null);
      setActionError(null);
      setOperationReadError(null);
      setOperationPollingPaused(false);
      setManagementRecovery(null);
      setFirmwareCandidate(null);
      setFirmwarePlan(null);
      return;
    }

    let canceled = false;
    const persistedRequest = readPendingUploadRequest(projectId);
    const persistedOperationId = persistedRequest?.operationId ?? null;
    setPendingUploadRequest(persistedRequest);
    if (persistedRequest) persistPendingUploadRequest(projectId, persistedRequest);
    setDeploymentChannel(
      persistedRequest?.channel ?? DeviceDeploymentChannel.USB_SERIAL,
    );
    setOperationReadError(null);
    setOperationPollingPaused(false);
    if (capabilities.serialScan) void scanPorts();
    void refreshEspClawEndpoints();
    const latestOperation = getLatestDeviceOperation(projectId).catch((reason: unknown) => {
      if (!canceled && !(reason instanceof ApiError && reason.status === 404)) {
        setActionError("读取最近设备操作失败，请检查本地服务后重试。");
      }
      return null;
    });
    const pendingOperation = persistedOperationId
      ? getDeviceOperation(projectId, persistedOperationId).catch(() => null)
      : Promise.resolve(null);
    void Promise.all([
      getCurrentDeviceSession(projectId).catch(() => null),
      getCurrentCode(projectId).catch(() => null),
      latestOperation,
      pendingOperation,
    ]).then(([sessionResponse, codeResponse, latestResponse, pendingResponse]) => {
      if (canceled) return;
      const matchingLatest = persistedOperationId
        && latestResponse?.operation.id === persistedOperationId
        ? latestResponse
        : null;
      const matchingPending = persistedOperationId
        && pendingResponse?.operation.id === persistedOperationId
        ? pendingResponse
        : null;
      const operationResponse = persistedOperationId
        ? matchingPending ?? matchingLatest
        : latestResponse;
      const operationSession = operationResponse
        && operationDeploymentChannel(operationResponse.operation) === DeviceDeploymentChannel.USB_SERIAL
        ? operationResponse.session
        : null;
      const currentUsbSession = sessionResponse?.session && isUsbSerialSession(sessionResponse.session)
        ? sessionResponse.session
        : null;
      setSession(currentUsbSession ?? operationSession ?? null);
      setCodeRun(codeResponse?.codeRun ?? null);
      setOperation(operationResponse?.operation ?? null);
      if (!persistedRequest && operationResponse?.operation.kind === DeviceOperationKind.UPLOAD_CODE) {
        setDeploymentChannel(operationDeploymentChannel(operationResponse.operation));
      }
      if (persistedOperationId) {
        if (operationResponse?.operation.id === persistedOperationId) {
          if (TERMINAL_OPERATION_STATUSES.has(operationResponse.operation.status)) {
            rememberPendingUpload(null);
          }
        } else {
          setOperationReadError(
            "上次上传状态尚未恢复。为避免重复写入，请重新读取状态后再继续。",
          );
          setOperationPollingPaused(true);
        }
      }
    });

    return () => {
      canceled = true;
    };
  }, [
    capabilities.serialScan,
    projectId,
    projectUpdatedAt,
    refreshEspClawEndpoints,
    rememberPendingUpload,
    scanPorts,
  ]);

  useEffect(() => {
    if (previousRefreshRevision.current === refreshRevision) return;
    previousRefreshRevision.current = refreshRevision;
    if (!projectId) return;

    let canceled = false;
    void getCurrentCode(projectId)
      .then((response) => {
        if (!canceled) setCodeRun(response.codeRun);
      })
      .catch(() => {
        if (!canceled) setCodeRun(null);
      });
    return () => {
      canceled = true;
    };
  }, [projectId, refreshRevision]);

  useEffect(() => {
    if (
      !projectId || !session?.id || !sessionReady ||
      !capabilities.serialConnection ||
      deploymentChannel !== DeviceDeploymentChannel.USB_SERIAL
    ) {
      setTerminal(null);
      setTerminalError(null);
      return;
    }
    if (operationRunning) {
      setTerminal((current) => current
        ? { ...current, status: DeviceTerminalStatus.STOPPED }
        : current);
      setTerminalError(null);
      return;
    }
    const sessionId = session.id;
    let canceled = false;
    let timer: number | null = null;

    const readTerminal = async () => {
      try {
        const response = await getDeviceTerminal(projectId, sessionId);
        if (canceled) return;
        setTerminal(response.terminal);
        setTerminalError(response.terminal.errorMessage);
      } catch {
        if (!canceled) setTerminalError("串口终端状态读取失败，请重新启动终端。");
      } finally {
        if (!canceled) timer = globalThis.setTimeout(readTerminal, TERMINAL_POLL_INTERVAL_MS);
      }
    };

    const begin = async () => {
      try {
        const response = await startDeviceTerminal(projectId, { sessionId });
        if (!canceled) {
          setTerminal(response.terminal);
          setTerminalError(response.terminal.errorMessage);
        }
      } catch {
        if (!canceled) setTerminalError("串口终端启动失败，请确认设备未被其他操作占用。");
      }
      if (!canceled) void readTerminal();
    };
    void begin();

    return () => {
      canceled = true;
      if (timer !== null) globalThis.clearTimeout(timer);
    };
  }, [
    capabilities.serialConnection,
    deploymentChannel,
    operationRunning,
    projectId,
    session?.id,
    sessionReady,
  ]);

  useEffect(() => {
    if (!projectId || !operationRunning || !operation) return;
    let canceled = false;
    let timer: number | null = null;
    let consecutiveFailures = 0;
    const poll = async () => {
      try {
        const response = await getDeviceOperation(projectId, operation.id);
        if (canceled) return;
        consecutiveFailures = 0;
        setOperationReadError(null);
        setOperationPollingPaused(false);
        setOperation(response.operation);
        if (operationDeploymentChannel(response.operation) === DeviceDeploymentChannel.USB_SERIAL) {
          setSession(response.session);
        }
        if (TERMINAL_OPERATION_STATUSES.has(response.operation.status)) {
          if (pendingUploadOperationId === response.operation.id) rememberPendingUpload(null);
        } else {
          timer = globalThis.setTimeout(poll, OPERATION_POLL_INTERVAL_MS);
        }
      } catch (reason) {
        if (canceled) return;
        consecutiveFailures += 1;
        if (consecutiveFailures >= OPERATION_POLL_MAX_FAILURES) {
          setOperationReadError("设备操作状态连续读取失败，自动读取已暂停。");
          setOperationPollingPaused(true);
          return;
        }
        const retryDelay = OPERATION_POLL_RETRY_BASE_MS * (2 ** (consecutiveFailures - 1));
        setOperationReadError(
          `设备操作状态读取失败，将在 ${formatRetryDelay(retryDelay)} 后重试。`,
        );
        timer = globalThis.setTimeout(poll, retryDelay);
      }
    };
    setOperationReadError(null);
    setOperationPollingPaused(false);
    timer = globalThis.setTimeout(poll, OPERATION_POLL_INITIAL_DELAY_MS);
    return () => {
      canceled = true;
      if (timer !== null) globalThis.clearTimeout(timer);
    };
  }, [
    operation?.id,
    operationRunning,
    pendingUploadOperationId,
    pollRestartRevision,
    projectId,
    rememberPendingUpload,
  ]);

  const retryOperationRead = useCallback(async () => {
    const operationId = pendingUploadOperationId ?? operation?.id;
    if (!projectId || !operationId) return;
    setOperationReadBusy(true);
    setOperationReadError(null);
    setOperationPollingPaused(false);
    try {
      const response = await getDeviceOperation(projectId, operationId);
      setOperation(response.operation);
      if (operationDeploymentChannel(response.operation) === DeviceDeploymentChannel.USB_SERIAL) {
        setSession(response.session);
      }
      if (TERMINAL_OPERATION_STATUSES.has(response.operation.status)) {
        if (pendingUploadOperationId === response.operation.id) rememberPendingUpload(null);
      } else {
        setPollRestartRevision((revision) => revision + 1);
      }
    } catch {
      setOperationReadError("重新读取设备操作状态失败，请检查本地服务后重试。");
      setOperationPollingPaused(true);
    } finally {
      setOperationReadBusy(false);
    }
  }, [operation?.id, pendingUploadOperationId, projectId, rememberPendingUpload]);

  const acceptedCode = useMemo(
    () => (codeRun?.status === CodeRunStatus.ACCEPTED ? codeRun : null),
    [codeRun],
  );
  const acceptedCodeRuntime = acceptedCode?.runtime ?? CodeRuntime.MICROPYTHON;
  const expectedCodeRuntime = deploymentChannel === DeviceDeploymentChannel.ESP_CLAW
    ? CodeRuntime.ESP_CLAW_LUA
    : CodeRuntime.MICROPYTHON;
  const compatibleAcceptedCode = acceptedCode && acceptedCodeRuntime === expectedCodeRuntime
    ? acceptedCode
    : null;
  const deploymentTargetId = deploymentChannel === DeviceDeploymentChannel.ESP_CLAW
    ? espClawReady ? selectedEspClawEndpoint?.id ?? null : null
    : sessionReady ? session?.id ?? null : null;
  const deploymentTargetReady = deploymentTargetId !== null;
  const codeCompatibilityMessage = acceptedCode && !compatibleAcceptedCode
    ? deploymentChannel === DeviceDeploymentChannel.ESP_CLAW
      ? "当前已接受代码是 MicroPython，不能通过 ESP-Claw 上传。请先生成并接受 ESP-Claw Lua 代码。"
      : "当前已接受代码是 ESP-Claw Lua，不能通过 USB 串口作为 MicroPython 上传。"
    : null;
  const pendingRetryBlockedReason = pendingUploadRequest
    ? deploymentChannel !== pendingUploadRequest.channel
      ? `待确认操作属于${DEPLOYMENT_CHANNEL_LABELS[pendingUploadRequest.channel]}，不能跨通道重试。`
      : acceptedCode?.id !== pendingUploadRequest.codeRunId
      ? "当前已接受代码与待确认上传不一致，不能重试。请先重新核对代码和设备。"
      : acceptedCodeRuntime !== expectedCodeRuntime
        ? "当前代码运行时与待确认通道不一致，不能重试。"
      : deploymentTargetId !== pendingUploadRequest.targetId
        ? "当前部署目标与待确认上传不一致或未就绪，不能重试。请先重新核对目标。"
        : null
    : null;

  const uploadFlowSteps = useMemo(() => {
    const uploadStarted = Boolean(
      uploadOperation && uploadOperationChannel === deploymentChannel,
    );
    const acceptedDetail = compatibleAcceptedCode
      ? `已接受 v${compatibleAcceptedCode.version} · ${runtimeLabel(expectedCodeRuntime)}`
      : codeCompatibilityMessage ?? "等待已接受代码";
    const targetLabel = deploymentChannel === DeviceDeploymentChannel.ESP_CLAW
      ? "配对 ESP-Claw"
      : "连接设备";
    const targetDetail = deploymentChannel === DeviceDeploymentChannel.ESP_CLAW
      ? espClawReady
        ? professionalMode
          ? `${selectedEspClawEndpoint?.webEndpoint ?? "ESP-Claw"} 已配对`
          : `${selectedEspClawEndpoint ? BOARD_LABELS[selectedEspClawEndpoint.boardId] : "ESP-Claw"} 已配对`
        : "配对可信局域网中的 ESP-Claw"
      : sessionReady
        ? `${session?.board ?? "设备"} 已连接`
        : "扫描并建立连接";
    return [
      {
        label: "选择已确认代码",
        detail: acceptedDetail,
        state: compatibleAcceptedCode ? "complete" : "current",
      },
      {
        label: targetLabel,
        detail: targetDetail,
        state: deploymentTargetReady
          ? "complete"
          : compatibleAcceptedCode ? "current" : "pending",
      },
      {
        label: "确认上传",
        detail: uploadStarted ? "正在部署代码" : "等待开始上传",
        state: uploadStarted
          ? "complete"
          : deploymentTargetReady && compatibleAcceptedCode
            ? "current"
            : "pending",
      },
      {
        label: "查看运行结果",
        detail: uploadOutcome?.summary ?? (operationRunning ? "上传进行中" : "上传后显示"),
        state: uploadOutcome?.state ?? (operationRunning ? "current" : "pending"),
      },
    ] as const;
  }, [
    codeCompatibilityMessage,
    compatibleAcceptedCode,
    deploymentChannel,
    deploymentTargetReady,
    espClawReady,
    expectedCodeRuntime,
    operationRunning,
    professionalMode,
    selectedEspClawEndpoint,
    session?.board,
    sessionReady,
    uploadOperation,
    uploadOperationChannel,
    uploadOutcome,
  ]);

  if (!workspace) {
    return (
      <div className="devices-tab" data-testid="devices-tab">
        <p className="tab-description">打开项目后扫描本机串口设备。</p>
      </div>
    );
  }

  return (
    <div className="devices-tab" data-testid="devices-tab">
      {onOpenDeviceLab && (
        <section className="device-section device-lab-entry" aria-label="设备实验室入口">
          <div>
            <strong>设备实验室</strong>
            <p>根据已确认立项自动生成项目实物场景，并图形化调试传感器、执行器和项目参数。</p>
          </div>
          <button type="button" className="device-primary-action" onClick={onOpenDeviceLab}>
            打开设备实验室
          </button>
        </section>
      )}
      {capabilities.host === "web" && (
        <section className="device-section" aria-label="浏览器开发模式">
          <div className="work-plan-header">
            <h4>浏览器开发模式</h4>
            <span className="work-plan-status">
              {capabilities.serialScan || capabilities.deviceUpload
                ? "Local Bridge 已授权"
                : "本地设备功能不可用"}
            </span>
          </div>
          <p className="tab-description" role="status">
            {capabilities.serialScan || capabilities.deviceUpload
              ? "本地操作由已配对的 Local Bridge 执行；只有授权的串口扫描和代码上传能力会开放。"
              : "当前页面可查看已有设备摘要；如需串口扫描、连接或代码上传，请使用掌问桌面端或先配对 Local Bridge。"}
          </p>
        </section>
      )}
      <section className="device-section" aria-label="代码上传方式">
        <div className="work-plan-header">
          <h4>代码上传</h4>
          <span className="work-plan-status">选择一种部署通道</span>
        </div>
        <div className="device-action-row device-deployment-channel" role="radiogroup" aria-label="代码上传方式">
          {Object.entries(DEPLOYMENT_CHANNEL_LABELS).map(([channel, label]) => {
            const typedChannel = channel as import("@zhangwen/contracts").DeviceDeploymentChannelType;
            return (
              <button
                key={channel}
                type="button"
                role="radio"
                aria-checked={deploymentChannel === typedChannel}
                className={deploymentChannel === typedChannel
                  ? "device-primary-action"
                  : "device-secondary-action"}
                disabled={operationRunning || Boolean(pendingUploadRequest)}
                onClick={() => {
                  setDeploymentChannel(typedChannel);
                  setActionError(null);
                  setOperationReadError(null);
                }}
              >
                {label}
              </button>
            );
          })}
        </div>
        <p className="tab-description">
          USB 串口用于 MicroPython 文件部署；ESP-Claw 用于已接受的受控 Lua 脚本，不会安装或刷写运行时固件。
        </p>
      </section>
      {deploymentChannel === DeviceDeploymentChannel.USB_SERIAL && (
      <section className="device-section device-serial-connection" aria-label="串口设备">
        <label className="device-board-selector">
          <span>精确板型</span>
          <select
            aria-label="串口连接板型"
            value={selectedBoardId}
            disabled={
              Boolean(projectBoardId)
              || Boolean(session && session.status !== DeviceSessionStatus.DISCONNECTED)
            }
            onChange={(event) => setSelectedBoardId(event.target.value as SupportedDeviceBoardIdType)}
          >
            {Object.entries(BOARD_LABELS).map(([id, label]) => (
              <option key={id} value={id}>{label}</option>
            ))}
          </select>
          <small>ESP32-S3 芯片信息不能区分这两块板；连接即表示你确认所选精确板型。</small>
        </label>
        <div className={`device-connection-card ${sessionReady ? "is-connected" : ""}`}>
          <div className="device-connection-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 3v12m0-12-2.5 2.5M12 3l2.5 2.5M7 9v3a3 3 0 0 0 3 3h5m0 0-2-2m2 2-2 2" />
              <circle cx="7" cy="7" r="1.5" />
              <rect x="15" y="13.5" width="3" height="3" rx=".5" />
            </svg>
          </div>
          <div className="device-connection-info">
            <strong>
              {session
                ? `${session.board}${session.portId ? ` (${session.portId})` : ""}`
                : "未连接设备"}
            </strong>
            <span>
              {session
                ? `USB 串口 · ${SESSION_STATUS_LABELS[session.status] ?? session.status}`
                : scanLoading ? "正在扫描串口…" : "扫描后选择设备"}
            </span>
          </div>
          <span className="device-connection-status">
            {sessionReady ? "已连接" : session ? SESSION_STATUS_LABELS[session.status] ?? session.status : "未连接"}
          </span>
          <div className="device-connection-actions">
            {session && capabilities.serialConnection && session.status !== DeviceSessionStatus.DISCONNECTED ? (
              <>
                {session.status !== DeviceSessionStatus.MANAGED && session.status !== DeviceSessionStatus.READY && (
                  <button
                    type="button"
                    className="device-secondary-action"
                    disabled={busy || operationRunning}
                    onClick={() => void takeover(
                      projectId,
                      session,
                      false,
                      null,
                      setSession,
                      setActionError,
                      setHardwareResetRequired,
                      setBusy,
                    )}
                  >
                    安全接管
                  </button>
                )}
                <button
                  type="button"
                  className="device-secondary-action"
                  disabled={busy || operationRunning}
                  onClick={() => void disconnect(projectId, session, setSession, setActionError, setBusy)}
                >
                  断开
                </button>
              </>
            ) : (
              <button
                type="button"
                className="device-secondary-action"
                onClick={() => void scanPorts()}
                disabled={scanLoading || !capabilities.serialScan}
                title={unsupportedMessage("serialScan") ?? undefined}
              >
                {scanLoading ? "扫描中…" : "扫描设备"}
              </button>
            )}
          </div>
        </div>

        {actionError && <p className="project-create-error" role="alert">{actionError}</p>}
        {session && hardwareResetRequired && (
          <div className="device-error" role="group" aria-label="硬件复位接管确认">
            <strong>Ctrl-C 未取得管理提示符</strong>
            <span>硬件复位可能让电机、继电器等执行器重新启动。请先确认现场安全，再输入“{HARDWARE_RESET_CONFIRMATION_PHRASE}”。本操作不擦除 Flash、不烧录固件。</span>
            <input
              value={hardwareResetPhrase}
              onChange={(event) => setHardwareResetPhrase(event.target.value)}
              aria-label="硬件复位确认短语"
            />
            <button
              type="button"
              className="device-danger-action"
              disabled={busy || hardwareResetPhrase !== HARDWARE_RESET_CONFIRMATION_PHRASE}
              onClick={() => void takeover(
                projectId,
                session,
                true,
                hardwareResetPhrase,
                setSession,
                setActionError,
                setHardwareResetRequired,
                setBusy,
              )}
            >
              复位、重枚举并在启动窗口接管
            </button>
          </div>
        )}
        {scanError && (
          <div className="device-error" role="alert">
            <strong>{scanError.title}</strong>
            <span>{scanError.message}</span>
          </div>
        )}
        {!sessionReady && ports.length > 0 && (
          <div className="device-port-list">
            {ports.map((port) => (
              <PortCard
                key={port.id}
                port={port}
                busy={busy || operationRunning}
                projectId={projectId}
                onConnect={setSession}
                onError={setActionError}
                onBusy={setBusy}
                canControl={capabilities.serialConnection}
                connected={sessionReady && session?.portId === port.id}
                professionalMode={professionalMode}
                boardId={selectedBoardId}
              />
            ))}
          </div>
        )}
      </section>
      )}

      {deploymentChannel === DeviceDeploymentChannel.ESP_CLAW && (
        <EspClawTargetPanel
          endpoints={espClawEndpoints}
          selectedEndpointId={selectedEspClawEndpointId}
          webEndpointInput={espClawWebEndpointInput}
          mcpEndpointInput={espClawMcpEndpointInput}
          boardId={selectedBoardId}
          trustedLanConfirmed={espClawTrustedLanConfirmed}
          adminModeConfirmed={espClawAdminModeConfirmed}
          boardConfirmed={espClawBoardConfirmed}
          boardLocked={Boolean(projectBoardId)}
          requiredBoardId={projectBoardId}
          busy={espClawBusy}
          operationRunning={operationRunning}
          error={espClawError}
          canControl={capabilities.deviceUpload}
          unsupportedReason={unsupportedMessage("deviceUpload")}
          professionalMode={professionalMode}
          onEndpointSelected={setSelectedEspClawEndpointId}
          onWebEndpointInput={setEspClawWebEndpointInput}
          onMcpEndpointInput={setEspClawMcpEndpointInput}
          onBoardChanged={setSelectedBoardId}
          onTrustedLanChanged={setEspClawTrustedLanConfirmed}
          onAdminModeChanged={setEspClawAdminModeConfirmed}
          onBoardConfirmedChanged={setEspClawBoardConfirmed}
          onPair={() => void pairEspClaw(
            projectId,
            espClawWebEndpointInput,
            espClawMcpEndpointInput,
            selectedBoardId,
            espClawTrustedLanConfirmed,
            espClawAdminModeConfirmed,
            espClawBoardConfirmed,
            setEspClawEndpoints,
            setSelectedEspClawEndpointId,
            setEspClawError,
            setEspClawBusy,
          )}
          onRefresh={() => void refreshEspClawEndpoints()}
        />
      )}

      <section className="device-section device-deployment" aria-label="项目代码上传">
        <ol className="device-upload-path" aria-label="上传流程">
          {uploadFlowSteps.map((step, index) => (
            <li key={step.label} data-state={step.state} title={step.detail}>
              <span aria-hidden="true">{index + 1}</span>
              <div>
                <strong>{step.label}</strong>
                <small>{step.detail}</small>
              </div>
            </li>
          ))}
        </ol>

        <div className="device-action-row device-upload-action">
          <button
            type="button"
            className="device-primary-action"
            disabled={
              busy || operationRunning || Boolean(pendingUploadOperationId) ||
              !capabilities.deviceUpload || !deploymentTargetReady ||
              !compatibleAcceptedCode
            }
            title={
              unsupportedMessage("deviceUpload")
              ?? codeCompatibilityMessage
              ?? undefined
            }
            onClick={() => {
              void startDeployment(
                projectId,
                deploymentChannel,
                deploymentTargetId,
                compatibleAcceptedCode,
                setSession,
                setOperation,
                rememberPendingUpload,
                setOperationReadError,
                setBusy,
              );
            }}
          >
            {operationRunning ? "上传中..." : "上传并运行"}
          </button>
        </div>
        {codeCompatibilityMessage && (
          <p className="project-create-error" role="status">{codeCompatibilityMessage}</p>
        )}
        {pendingUploadRequest && operation?.id !== pendingUploadRequest.operationId && (
          <div className="device-status-read-error" role="alert">
            <p>
              {pendingRetryBlockedReason
                ?? operationReadError
                ?? "上次上传结果尚未确认。再次上传保持锁定，请先恢复状态。"}
            </p>
            <div className="device-pending-upload-actions">
              <button
                type="button"
                className="device-secondary-action"
                disabled={busy}
                onClick={() => void recoverPendingUpload(
                  projectId,
                  pendingUploadRequest,
                  setSession,
                  setOperation,
                  rememberPendingUpload,
                  setOperationReadError,
                  setBusy,
                )}
              >
                恢复上传状态
              </button>
              <button
                type="button"
                className="device-primary-action"
                disabled={busy || Boolean(pendingRetryBlockedReason) || !capabilities.deviceUpload}
                title={pendingRetryBlockedReason ?? undefined}
                onClick={() => void retryPendingUploadRequest(
                  projectId,
                  pendingUploadRequest,
                  acceptedCode,
                  deploymentChannel,
                  deploymentTargetId,
                  setSession,
                  setOperation,
                  rememberPendingUpload,
                  setOperationReadError,
                  setBusy,
                )}
              >
                使用同一操作 ID 重试上传请求
              </button>
            </div>
          </div>
        )}
      </section>

      {deploymentChannel === DeviceDeploymentChannel.USB_SERIAL && (
      <SerialTerminalPanel
        projectId={projectId}
        sessionId={session?.id ?? null}
        professionalMode={professionalMode}
        terminal={terminal}
        error={terminalError}
        connected={sessionReady}
        disabled={!capabilities.serialConnection || terminalBusy || operationRunning}
        onStart={session && projectId ? () => {
          setTerminalBusy(true);
          setTerminalError(null);
          void startDeviceTerminal(projectId, { sessionId: session.id })
            .then((response) => setTerminal(response.terminal))
            .catch(() => setTerminalError("串口终端启动失败，请确认设备未被其他操作占用。"))
            .finally(() => setTerminalBusy(false));
        } : undefined}
        onStop={session && projectId ? () => {
          setTerminalBusy(true);
          void stopDeviceTerminal(projectId, { sessionId: session.id })
            .then((response) => setTerminal(response.terminal))
            .catch(() => setTerminalError("串口终端暂停失败。"))
            .finally(() => setTerminalBusy(false));
        } : undefined}
        onClear={session && projectId ? () => {
          setTerminalBusy(true);
          void clearDeviceTerminal(projectId, { sessionId: session.id })
            .then((response) => setTerminal(response.terminal))
            .catch(() => setTerminalError("串口终端清空失败。"))
            .finally(() => setTerminalBusy(false));
        } : undefined}
      />
      )}

      {deploymentChannel === DeviceDeploymentChannel.USB_SERIAL
        && isWateringProject
        && uploadOperationChannel === DeviceDeploymentChannel.USB_SERIAL
        && uploadOperation?.status === DeviceOperationStatus.COMPLETED
        && !uploadOperation.dryRun && (
        <section className="device-section device-smoke-evidence" aria-label="自动浇花运行核验">
          <div className="work-plan-header">
            <h4>运行结果核验</h4>
            <span className="work-plan-status">
              {wateringSmokeEvidence?.ok ? "证据已通过" : "等待场景证据"}
            </span>
          </div>
          <p className="tab-description">
            先保持传感器湿润，确认水泵关闭；再使用安全的干燥测试环境观察一次有限启动。掌问只读取日志，不会主动驱动水泵。
          </p>
          <button
            type="button"
            className="device-primary-action"
            disabled={smokeBusy || operationRunning || !sessionReady || !terminal?.output}
            onClick={() => {
              if (!projectId || !session) return;
              setSmokeBusy(true);
              setSmokeError(null);
              void evaluateWateringSmoke(projectId, {
                sessionId: session.id,
                operationId: uploadOperation.id,
              })
                .then((response) => setOperation(response.operation))
                .catch((error: unknown) => setSmokeError(
                  error instanceof Error ? error.message : "运行证据核验失败，请继续查看设备日志。",
                ))
                .finally(() => setSmokeBusy(false));
            }}
          >
            {smokeBusy ? "核验中..." : "核验运行证据"}
          </button>
          {smokeError && <p className="project-create-error" role="alert">{smokeError}</p>}
          {wateringSmokeEvidence && (
            <div className="device-smoke-result" role="status" aria-label="自动浇花冒烟测试结果">
              <strong>{wateringSmokeEvidence.summary}</strong>
              <ul>
                {wateringSmokeEvidence.observations.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </div>
          )}
        </section>
      )}

      {uploadOperation && uploadOperationChannel === deploymentChannel && (
        <OperationPanel
          operation={uploadOperation}
          professionalMode={professionalMode}
          managementChannelRecovered={
            deploymentChannel === DeviceDeploymentChannel.USB_SERIAL
              && managementChannelRecovered
          }
          onRescan={
            deploymentChannel === DeviceDeploymentChannel.USB_SERIAL
              && capabilities.serialScan
              ? () => void scanPorts()
              : undefined
          }
          onReconnect={
            deploymentChannel === DeviceDeploymentChannel.USB_SERIAL
              && capabilities.serialConnection
              && session?.portId
              && session.id === uploadOperation.sessionId
              ? () => {
                const recoveryPortId = session.portId;
                void connect(
                  projectId,
                  recoveryPortId,
                  selectedBoardId,
                  setSession,
                  setActionError,
                  setBusy,
                  (connectedSession) => {
                    if (
                      connectedSession.status === DeviceSessionStatus.READY
                      && connectedSession.portId === recoveryPortId
                    ) {
                      setManagementRecovery({
                        operationId: uploadOperation.id,
                        portId: recoveryPortId,
                      });
                    }
                  },
                );
              }
              : undefined
          }
          recoveryBusy={busy || scanLoading}
          pollingError={operationReadError}
          statusReadBusy={operationReadBusy}
          onRetryStatus={operationPollingPaused ? () => void retryOperationRead() : undefined}
          onCancel={
            uploadOperation.cancelable && operationRunning
              ? () => void cancelOperation(
                projectId,
                uploadOperation.id,
                setOperation,
                setSession,
                setActionError,
                rememberPendingUpload,
              )
              : undefined
          }
        />
      )}

      {professionalMode && (
        <section className="device-section device-firmware-section" aria-label="固件烧录">
          <div className="work-plan-header">
            <h4>固件烧录（独立高风险流程）</h4>
            <span className="work-plan-status">不会执行 Flash 擦除</span>
          </div>
          <label className="device-file-input">
            <span>固件文件</span>
            <input
              type="file"
              accept=".bin,application/octet-stream"
              disabled={busy || operationRunning || !capabilities.deviceFlash}
              onChange={(event) => void selectFirmware(
                projectId,
                event.currentTarget.files?.[0] ?? null,
                setFirmwareCandidate,
                setFirmwarePlan,
                setFirmwareAddress,
                setActionError,
                setBusy,
              )}
            />
          </label>
          {firmwareCandidate && (
            <div className="firmware-candidate">
              <dl className="professional-summary">
                <div><dt>文件</dt><dd>{firmwareCandidate.fileName}</dd></div>
                <div><dt>大小</dt><dd>{formatBytes(firmwareCandidate.sizeBytes)}</dd></div>
                <div><dt>SHA-256</dt><dd>{firmwareCandidate.sha256}</dd></div>
                <div><dt>目标芯片</dt><dd>{firmwareCandidate.targetChip ?? "未知"}</dd></div>
              </dl>
              {firmwareCandidate.warnings.map((warning) => (
                <p key={warning} className="device-firmware-warning">{warning}</p>
              ))}
              <label className="device-address-input">
                <span>写入地址</span>
                <input
                  value={firmwareAddress}
                  onChange={(event) => {
                    setFirmwareAddress(event.target.value);
                    setFirmwarePlan(null);
                  }}
                  placeholder="例如 0x0"
                  disabled={!firmwareCandidate.compatible}
                />
              </label>
              <button
                type="button"
                className="device-secondary-action"
                disabled={busy || operationRunning || !session || !firmwareCandidate.compatible}
                onClick={() => void prepareFlash(
                  projectId,
                  session,
                  firmwareCandidate,
                  firmwareAddress,
                  setFirmwarePlan,
                  setActionError,
                  setBusy,
                )}
              >
                生成烧录计划
              </button>
            </div>
          )}
          {firmwarePlan && (
            <div className="firmware-plan">
              <p>{firmwarePlan.summary}</p>
              <p>写入地址：0x{firmwarePlan.address.toString(16).toUpperCase()}</p>
              <label className="device-confirm">
                <input
                  type="checkbox"
                  checked={flashRiskConfirmed}
                  onChange={(event) => setFlashRiskConfirmed(event.target.checked)}
                />
                <span>我已确认板型、固件哈希、写入地址和覆盖区备份风险</span>
              </label>
              <label className="device-address-input">
                <span>输入“{FIRMWARE_CONFIRMATION_PHRASE}”</span>
                <input value={flashPhrase} onChange={(event) => setFlashPhrase(event.target.value)} />
              </label>
              <button
                type="button"
                className="device-danger-action"
                disabled={
                  busy || operationRunning || !session || !flashRiskConfirmed ||
                  flashPhrase !== FIRMWARE_CONFIRMATION_PHRASE
                }
                onClick={() => void startFlash(
                  projectId,
                  session,
                  firmwarePlan,
                  flashPhrase,
                  setSession,
                  setOperation,
                  setActionError,
                  setBusy,
                )}
              >
                烧录固件
              </button>
            </div>
          )}
        </section>
      )}

      {professionalMode && operation && !uploadOperation && (
        <OperationPanel
          operation={operation}
          professionalMode={professionalMode}
          managementChannelRecovered={false}
          pollingError={operationReadError}
          statusReadBusy={operationReadBusy}
          onRetryStatus={operationPollingPaused ? () => void retryOperationRead() : undefined}
          onCancel={
            operation.cancelable && operationRunning
              ? () => void cancelOperation(projectId, operation.id, setOperation, setSession, setActionError)
              : undefined
          }
        />
      )}

    </div>
  );
}

function EspClawTargetPanel({
  endpoints,
  selectedEndpointId,
  webEndpointInput,
  mcpEndpointInput,
  boardId,
  trustedLanConfirmed,
  adminModeConfirmed,
  boardConfirmed,
  boardLocked,
  requiredBoardId,
  busy,
  operationRunning,
  error,
  canControl,
  unsupportedReason,
  professionalMode,
  onEndpointSelected,
  onWebEndpointInput,
  onMcpEndpointInput,
  onBoardChanged,
  onTrustedLanChanged,
  onAdminModeChanged,
  onBoardConfirmedChanged,
  onPair,
  onRefresh,
}: {
  endpoints: EspClawEndpoint[];
  selectedEndpointId: string;
  webEndpointInput: string;
  mcpEndpointInput: string;
  boardId: SupportedDeviceBoardIdType;
  trustedLanConfirmed: boolean;
  adminModeConfirmed: boolean;
  boardConfirmed: boolean;
  boardLocked: boolean;
  requiredBoardId: SupportedDeviceBoardIdType | null;
  busy: boolean;
  operationRunning: boolean;
  error: string | null;
  canControl: boolean;
  unsupportedReason: string | null;
  professionalMode: boolean;
  onEndpointSelected: (endpointId: string) => void;
  onWebEndpointInput: (endpoint: string) => void;
  onMcpEndpointInput: (endpoint: string) => void;
  onBoardChanged: (boardId: SupportedDeviceBoardIdType) => void;
  onTrustedLanChanged: (confirmed: boolean) => void;
  onAdminModeChanged: (confirmed: boolean) => void;
  onBoardConfirmedChanged: (confirmed: boolean) => void;
  onPair: () => void;
  onRefresh: () => void;
}) {
  const boardEligibleEndpoints = requiredBoardId
    ? endpoints.filter((endpoint) => endpoint.boardId === requiredBoardId)
    : endpoints;
  const eligibleEndpoints = professionalMode
    ? boardEligibleEndpoints
    : boardEligibleEndpoints.filter((endpoint) => endpoint.status === "READY");
  const pairingReady = webEndpointInput.trim().length > 0
    && mcpEndpointInput.trim().length > 0
    && trustedLanConfirmed
    && adminModeConfirmed
    && boardConfirmed;
  return (
    <section className="device-section device-esp-claw-target" aria-label="ESP-Claw 部署目标">
      <div className="work-plan-header">
        <h4>ESP-Claw 目标</h4>
        <span className="work-plan-status">
          {eligibleEndpoints.some((endpoint) => endpoint.id === selectedEndpointId && endpoint.status === "READY")
            ? "已配对"
            : professionalMode ? "等待配对" : "暂无就绪目标"}
        </span>
      </div>
      {eligibleEndpoints.length > 0 && (
        <label className="device-board-selector">
          <span>{professionalMode ? "已配对 endpoint" : "已配对目标"}</span>
          <select
            aria-label="ESP-Claw endpoint"
            value={selectedEndpointId}
            disabled={busy || operationRunning}
            onChange={(event) => onEndpointSelected(event.target.value)}
          >
            {eligibleEndpoints.map((endpoint, index) => (
              <option key={endpoint.id} value={endpoint.id}>
                {professionalMode
                  ? `${endpoint.webEndpoint} · ${endpoint.mcpEndpoint} · `
                  : `ESP-Claw ${index + 1} · `}
                {BOARD_LABELS[endpoint.boardId]} · {endpoint.status === "READY" ? "就绪" : "异常"}
              </option>
            ))}
          </select>
        </label>
      )}
      {requiredBoardId && endpoints.length > 0 && boardEligibleEndpoints.length === 0 && (
        <p className="project-create-error" role="status">
          已配对目标均不是当前项目的 {BOARD_LABELS[requiredBoardId]}，不能用于本项目代码上传。
        </p>
      )}
      {!professionalMode && boardEligibleEndpoints.length > 0 && eligibleEndpoints.length === 0 && (
        <p className="project-create-error" role="status">
          当前没有就绪的 ESP-Claw 目标。请在专业模式检查或重新配对后再试。
        </p>
      )}
      {!professionalMode && endpoints.length === 0 && (
        <p className="tab-description" role="status">
          尚无已配对且就绪的 ESP-Claw 目标。请先在专业模式完成配对。
        </p>
      )}
      <div className="device-action-row">
        <button
          type="button"
          className="device-secondary-action"
          disabled={busy || operationRunning}
          onClick={onRefresh}
        >
          刷新已配对目标
        </button>
      </div>
      {professionalMode && (
        <>
          <fieldset disabled={busy || operationRunning || !canControl}>
            <legend>手动配对新的 ESP-Claw</legend>
            <label className="device-board-selector">
              <span>Web Console 地址</span>
              <input
                aria-label="ESP-Claw Web Console 地址"
                inputMode="url"
                autoComplete="off"
                placeholder="http://esp-claw.local"
                value={webEndpointInput}
                onChange={(event) => onWebEndpointInput(event.target.value)}
              />
              <small>请输入可信局域网中的 Web Console origin，例如 http://esp-claw.local；不要附带密码、令牌或其他凭据。</small>
            </label>
            <label className="device-board-selector">
              <span>MCP 完整地址</span>
              <input
                aria-label="ESP-Claw MCP 完整地址"
                inputMode="url"
                autoComplete="off"
                placeholder="http://esp-claw.local:port/mcp"
                value={mcpEndpointInput}
                onChange={(event) => onMcpEndpointInput(event.target.value)}
              />
              <small>MCP 服务可能使用独立端口和路径；请填写设备实际广播或显示的完整 URL，不自动发现或猜测端口。</small>
            </label>
            <label className="device-board-selector">
              <span>精确板型</span>
              <select
                aria-label="ESP-Claw 精确板型"
                value={boardId}
                disabled={boardLocked}
                onChange={(event) => onBoardChanged(event.target.value as SupportedDeviceBoardIdType)}
              >
                {Object.entries(BOARD_LABELS).map(([id, label]) => (
                  <option key={id} value={id}>{label}</option>
                ))}
              </select>
              {boardLocked && <small>板型来自当前项目已确认硬件，配对时不可改为另一块板。</small>}
            </label>
            <label>
              <input
                type="checkbox"
                checked={trustedLanConfirmed}
                onChange={(event) => onTrustedLanChanged(event.target.checked)}
              />
              我确认这两个地址均位于可信局域网，且未暴露到公网
            </label>
            <label>
              <input
                type="checkbox"
                checked={adminModeConfirmed}
                onChange={(event) => onAdminModeChanged(event.target.checked)}
              />
              我确认设备已主动开启 ESP-Claw Admin/开发模式
            </label>
            <label>
              <input
                type="checkbox"
                checked={boardConfirmed}
                onChange={(event) => onBoardConfirmedChanged(event.target.checked)}
              />
              我确认上方精确板型与实物一致
            </label>
            <button
              type="button"
              className="device-primary-action"
              disabled={!pairingReady}
              title={unsupportedReason ?? undefined}
              onClick={onPair}
            >
              {busy ? "配对中..." : "配对 ESP-Claw"}
            </button>
          </fieldset>
          <p className="tab-description">
            ESP-Claw 的 Web Console 与 MCP 服务可能不是同一 origin。配对只保存两个局域网地址与板型，不保存 Wi-Fi 密码或令牌。
          </p>
        </>
      )}
      {error && <p className="project-create-error" role="alert">{error}</p>}
      {!canControl && unsupportedReason && <p className="tab-description">{unsupportedReason}</p>}
    </section>
  );
}

function SerialTerminalPanel({
  projectId,
  sessionId,
  professionalMode,
  terminal,
  error,
  connected,
  disabled,
  onStart,
  onStop,
  onClear,
}: {
  projectId: string | null;
  sessionId: string | null;
  professionalMode: boolean;
  terminal: DeviceTerminalSnapshot | null;
  error: string | null;
  connected: boolean;
  disabled: boolean;
  onStart?: () => void;
  onStop?: () => void;
  onClear?: () => void;
}) {
  const outputRef = useRef<HTMLPreElement>(null);
  const [unlockPhrase, setUnlockPhrase] = useState("");
  const [unlockToken, setUnlockToken] = useState<string | null>(null);
  const [terminalInput, setTerminalInput] = useState("");
  const [inputBusy, setInputBusy] = useState(false);
  const [inputError, setInputError] = useState<string | null>(null);
  useEffect(() => {
    const element = outputRef.current;
    if (element) element.scrollTop = element.scrollHeight;
  }, [terminal?.revision]);
  const running = terminal?.status === DeviceTerminalStatus.RUNNING
    || terminal?.status === DeviceTerminalStatus.STARTING;
  const status = terminal
    ? TERMINAL_STATUS_LABELS[terminal.status] ?? terminal.status
    : connected ? "等待启动" : "等待设备连接";
  useEffect(() => {
    setUnlockPhrase("");
    setUnlockToken(null);
    setTerminalInput("");
    setInputError(null);
  }, [sessionId, terminal?.status]);

  return (
    <section className="device-section device-serial-logs" aria-label="串口终端">
      <div className="device-serial-terminal-header">
        <h4 className="device-serial-log-title"><span aria-hidden="true">›_</span> 串口终端</h4>
        <span className="device-terminal-status" role="status">
          {status} · {unlockToken ? "本次会话输入已解锁" : "只读"}
        </span>
      </div>
      <pre
        ref={outputRef}
        className="device-serial-terminal"
        role="log"
        aria-live="polite"
        aria-label="MicroPython 运行输出"
      >
        {terminal?.output || (connected
          ? "等待设备输出。上传并启动后，这里会显示 MicroPython 报错和运行信息。"
          : "等待设备连接。连接后可查看 MicroPython 报错和运行信息。")}
      </pre>
      {error && <p className="device-terminal-error" role="status">{error}</p>}
      {inputError && <p className="device-terminal-error" role="status">{inputError}</p>}
      <div className="device-terminal-actions">
        {running ? (
          <button type="button" className="device-secondary-action" disabled={disabled} onClick={onStop}>
            暂停读取
          </button>
        ) : (
          <button type="button" className="device-secondary-action" disabled={disabled || !connected} onClick={onStart}>
            开始读取
          </button>
        )}
        <button
          type="button"
          className="device-secondary-action"
          disabled={disabled || !terminal?.output}
          onClick={onClear}
        >
          清空终端
        </button>
      </div>
      {professionalMode && running && projectId && sessionId ? (
        <div className="device-terminal-input">
          {!unlockToken ? (
            <>
              <p>专业模式可按会话解锁 REPL。输入内容不会进入项目、日志、云同步或交付包。</p>
              <label>
                确认短语
                <input
                  value={unlockPhrase}
                  placeholder="输入“解锁终端输入”"
                  onChange={(event) => setUnlockPhrase(event.target.value)}
                />
              </label>
              <button
                type="button"
                disabled={inputBusy || unlockPhrase !== "解锁终端输入"}
                onClick={() => {
                  setInputBusy(true);
                  setInputError(null);
                  void unlockDeviceTerminal(projectId, {
                    sessionId,
                    confirmProfessionalMode: true,
                    confirmationPhrase: unlockPhrase,
                  }).then((response) => {
                    setUnlockToken(response.unlock.unlockToken);
                    setUnlockPhrase("");
                  }).catch((reason: unknown) => {
                    setInputError(reason instanceof Error ? reason.message : "终端输入解锁失败。");
                  }).finally(() => setInputBusy(false));
                }}
              >
                解锁本次会话输入
              </button>
            </>
          ) : (
            <form
              onSubmit={(event) => {
                event.preventDefault();
                const value = terminalInput.endsWith("\n")
                  ? terminalInput
                  : `${terminalInput}\r\n`;
                if (!value.trim()) return;
                setInputBusy(true);
                setInputError(null);
                void writeDeviceTerminal(projectId, {
                  sessionId,
                  unlockToken,
                  input: value,
                }).then((response) => {
                  setTerminalInput("");
                  if (response.terminal.status !== DeviceTerminalStatus.RUNNING) {
                    setUnlockToken(null);
                  }
                }).catch((reason: unknown) => {
                  setUnlockToken(null);
                  setInputError(reason instanceof Error ? reason.message : "终端输入发送失败，请重新解锁。");
                }).finally(() => setInputBusy(false));
              }}
            >
              <label>
                REPL 输入
                <input
                  value={terminalInput}
                  maxLength={500}
                  autoComplete="off"
                  spellCheck={false}
                  onChange={(event) => setTerminalInput(event.target.value)}
                />
              </label>
              <button type="submit" disabled={inputBusy || !terminalInput.trim()}>发送</button>
            </form>
          )}
        </div>
      ) : null}
    </section>
  );
}

function PortCard({
  port,
  busy,
  projectId,
  onConnect,
  onError,
  onBusy,
  canControl,
  connected,
  professionalMode,
  boardId,
}: {
  port: DevicePort;
  busy: boolean;
  projectId: string | null;
  onConnect: (session: DeviceSession | null) => void;
  onError: (error: string | null) => void;
  onBusy: (busy: boolean) => void;
  canControl: boolean;
  connected: boolean;
  professionalMode: boolean;
  boardId: SupportedDeviceBoardIdType;
}) {
  const primaryLabel = professionalMode
    ? port.portName || port.id
    : port.likelyBoard || port.product || port.manufacturer || "串口设备";
  const secondaryLabel = professionalMode
    ? port.description || port.label
    : port.product && port.product !== primaryLabel
      ? port.product
      : port.manufacturer && port.manufacturer !== primaryLabel
        ? port.manufacturer
        : null;
  return (
    <div className="device-port-card">
      <div>
        <strong>{primaryLabel}</strong>
        {secondaryLabel && secondaryLabel !== primaryLabel && <span>{secondaryLabel}</span>}
        <dl className={professionalMode ? "device-port-meta" : "device-port-summary"}>
          <div><dt>状态</dt><dd>{PORT_STATUS_LABELS[port.status] ?? "未知"}</dd></div>
          <div><dt>推测开发板</dt><dd>{port.likelyBoard || port.chip || "未知"}</dd></div>
          {professionalMode && (
            <>
              <div><dt>制造商</dt><dd>{port.manufacturer || "未知"}</dd></div>
              <div><dt>产品</dt><dd>{port.product || "未知"}</dd></div>
              <div><dt>VID/PID</dt><dd>{formatVidPid(port.vid, port.pid)}</dd></div>
              <div><dt>序列号</dt><dd>{port.serialNumber || "未知"}</dd></div>
            </>
          )}
        </dl>
      </div>
      {canControl ? (
        <button
          type="button"
          disabled={busy || !port.available || connected}
          onClick={() => void connect(projectId, port.id, boardId, onConnect, onError, onBusy)}
        >
          {connected ? "已连接" : "连接"}
        </button>
      ) : (
        <span className="device-scan-only">只读</span>
      )}
    </div>
  );
}

function OperationPanel({
  operation,
  professionalMode,
  managementChannelRecovered,
  onRescan,
  onReconnect,
  recoveryBusy = false,
  pollingError,
  statusReadBusy = false,
  onRetryStatus,
  onCancel,
}: {
  operation: DeviceOperation;
  professionalMode: boolean;
  managementChannelRecovered: boolean;
  onRescan?: () => void;
  onReconnect?: () => void;
  recoveryBusy?: boolean;
  pollingError?: string | null;
  statusReadBusy?: boolean;
  onRetryStatus?: () => void;
  onCancel?: () => void;
}) {
  const deploymentChannel = operationDeploymentChannel(operation);
  const uploadOutcome = operation.kind === DeviceOperationKind.UPLOAD_CODE
    ? deriveDeploymentOutcome(operation)
    : null;
  const showManagementRecovery = Boolean(
    uploadOutcome?.managementChannelWarning,
  );
  return (
    <section className="device-section device-operation" aria-label="最近设备操作">
      <div className="work-plan-header">
        <h4>{uploadOutcome ? "4. 部署结果" : "最近固件操作"}</h4>
        <span
          className={`work-plan-status ${uploadOutcome ? `device-result-status-${uploadOutcome.state}` : ""}`}
        >
          {uploadOutcome?.summary ?? OPERATION_STATUS_LABELS[operation.status] ?? operation.status}
        </span>
      </div>
      <div className="device-operation-progress">
        <progress max={100} value={operation.progress ?? 0} />
        <span>{PHASE_LABELS[operation.phase ?? "QUEUED"] ?? operation.phase}</span>
      </div>
      {pollingError && (
        <div className="device-status-read-error" role="alert">
          <p>{pollingError}</p>
          {onRetryStatus && (
            <button
              type="button"
              className="device-secondary-action"
              disabled={statusReadBusy}
              onClick={onRetryStatus}
            >
              {statusReadBusy ? "读取中..." : "重新读取状态"}
            </button>
          )}
        </div>
      )}
      {uploadOutcome && (
        <ul className="device-result-list" aria-label="部署结果摘要">
          {uploadOutcome.items.map((item) => (
            <li key={item.label} data-state={item.state}>
              <span className="device-result-mark" aria-hidden="true" />
              <div>
                <strong>{item.label}</strong>
                <p>{item.detail}</p>
              </div>
              <span className="device-result-label">{RESULT_STATE_LABELS[item.state]}</span>
            </li>
          ))}
        </ul>
      )}
      {showManagementRecovery && (
        <div
          className={`device-recovery-notice ${managementChannelRecovered ? "device-recovery-resolved" : ""}`}
          role={managementChannelRecovered ? "status" : "alert"}
        >
          <strong>
            {managementChannelRecovered ? "管理通道现已恢复" : "文件已部署，管理通道待恢复"}
          </strong>
          <p>
            {managementChannelRecovered
              ? "当前设备连接已经恢复；本次部署记录仍保留最初的重连警告。"
              : "文件写入与回读结果不受影响。请重新扫描并连接；仍无响应时，按设备 RST 后重试。"}
          </p>
          {!managementChannelRecovered && uploadOutcome && uploadOutcome.warnings.length > 0 && (
            <ul>
              {uploadOutcome.warnings.map((warning) => <li key={warning}>{warning}</li>)}
            </ul>
          )}
          {!managementChannelRecovered && (onRescan || onReconnect) && (
            <div className="device-recovery-actions">
              {onRescan && (
                <button
                  type="button"
                  className="device-secondary-action"
                  disabled={recoveryBusy}
                  onClick={onRescan}
                >
                  重新扫描
                </button>
              )}
              {onReconnect && (
                <button
                  type="button"
                  className="device-primary-action"
                  disabled={recoveryBusy}
                  onClick={onReconnect}
                >
                  重新连接
                </button>
              )}
            </div>
          )}
        </div>
      )}
      {operation.backup && (
        <p className="tab-description">
          {operation.backup.restorable ? "已保留" : "已记录"} {operation.backup.fileCount} 项备份
          {professionalMode ? `：${operation.backup.paths.join("、") || "无同名文件"}` : "。"}
        </p>
      )}
      {professionalMode && operation.verification && (
        <p className="tab-description">{operation.verification.summary}</p>
      )}
      {uploadOutcome && (
        <p className="device-result-boundary">
          {deploymentChannel === DeviceDeploymentChannel.ESP_CLAW
            ? "这里只核对 endpoint 握手、代码回读与 Lua 任务启动，不代表程序界面或业务效果已经验证。"
            : "这里只核对文件传输和主控正常启动路径，不代表程序界面或业务效果已经验证。"}
        </p>
      )}
      {professionalMode && (operation.steps?.length || operation.log || operation.errorCode) ? (
        <details className="device-operation-details">
          <summary>阶段与技术日志</summary>
          {operation.steps?.length ? (
            <ol className="device-operation-steps">
              {operation.steps.map((step, index) => (
                <li key={`${step.phase}-${index}`}>
                  <span>{PHASE_LABELS[step.phase] ?? step.phase}</span>
                  <strong>
                    {step.exitCode === null
                      ? OPERATION_STATUS_LABELS[step.status] ?? step.status
                      : `退出码 ${step.exitCode}`}
                  </strong>
                  <p>{step.summary}</p>
                </li>
              ))}
            </ol>
          ) : null}
          {operation.errorCode && <p className="project-create-error">{operation.errorCode}</p>}
          {operation.log && <pre className="device-log-preview">{operation.log}</pre>}
        </details>
      ) : null}
      {!professionalMode && operation.errorCode && !showManagementRecovery && (
        <p className="project-create-error">{operationFailureMessage(operation)}</p>
      )}
      {onCancel && (
        <button type="button" className="device-secondary-action" onClick={onCancel}>
          取消操作
        </button>
      )}
      {operation.artifactId && (
        <p className="tab-description">完整操作记录已同步到“产物”中的设备日志。</p>
      )}
    </section>
  );
}

const RESULT_STATE_LABELS: Record<ResultState, string> = {
  complete: "已完成",
  running: "进行中",
  pending: "待执行",
  warning: "待恢复",
  failed: "失败",
  unknown: "待确认",
};

const OPERATION_FAILURE_MESSAGES: Record<string, string> = {
  DEVICE_PORT_BUSY: "设备端口正被其他操作占用，请稍后重试。",
  DEVICE_PREFLIGHT_FAILED: "设备连接检查未通过，请重新连接后重试。",
  DEVICE_BACKUP_FAILED: "写入前备份未完成，代码没有继续上传。",
  DEVICE_UPLOAD_FAILED: "文件写入未完成，已停止本次部署。",
  DEVICE_READBACK_FAILED: "设备文件回读失败，无法确认写入结果。",
  DEVICE_READBACK_MISMATCH: "设备文件与上传内容不一致，校验未通过。",
  DEVICE_RUNTIME_INTERRUPT_FAILED: "正在运行的程序未响应安全中断；未写入文件，也未自动复位设备。",
  DEVICE_RUNTIME_START_FAILED: "文件处理后 Python 运行环境未启动；已尝试恢复备份。",
  DEVICE_RESTART_FAILED: "文件处理后主控重启未完成，请检查设备连接。",
  DEVICE_MAIN_START_FAILED: "旧版 main.py 启动命令未成功提交，请重新上传以使用正常启动复位。",
  DEVICE_RESTORE_FAILED: "自动恢复备份未完成，请保留当前备份并查看技术日志。",
  DEVICE_UPLOAD_TIMEOUT: "文件部署等待超时，请检查设备连接后重试。",
  DEVICE_OPERATION_TIMEOUT: "设备操作等待超时，请检查连接后重试。",
  DEVICE_OPERATION_CANCELED: "设备操作已取消。",
};

function operationFailureMessage(operation: DeviceOperation): string {
  const mappedMessage = operation.errorCode
    ? OPERATION_FAILURE_MESSAGES[operation.errorCode]
    : undefined;
  if (mappedMessage) return mappedMessage;
  if (operationDeploymentChannel(operation) === DeviceDeploymentChannel.ESP_CLAW) {
    const clawPhaseMessages: Partial<Record<DeviceOperationStep["phase"], string>> = {
      [DeviceOperationPhase.PREFLIGHT]: "ESP-Claw endpoint 能力握手或项目场景板型门禁未通过，未写入代码。",
      [DeviceOperationPhase.BACKUP]: "ESP-Claw 旧代码备份未完成，未继续写入。",
      [DeviceOperationPhase.TRANSFER]: "ESP-Claw 代码写入未完成，请检查已配对目标后重试。",
      [DeviceOperationPhase.VERIFY_FILES]: "ESP-Claw 代码回读校验未通过。",
      [DeviceOperationPhase.START_RUNTIME]: "ESP-Claw Lua 入口脚本未能启动；已尝试恢复备份。",
      [DeviceOperationPhase.VERIFY_RUNTIME]: "ESP-Claw Lua 异步任务未返回成功终态。",
      [DeviceOperationPhase.RESTORE]: "ESP-Claw 备份恢复未完成，请保留操作记录。",
    };
    return clawPhaseMessages[operation.phase ?? DeviceOperationPhase.QUEUED]
      ?? "ESP-Claw 代码部署未完成，请检查配对状态后重试。";
  }
  const phaseMessages: Partial<Record<DeviceOperationStep["phase"], string>> = {
    [DeviceOperationPhase.INTERRUPT_RUNTIME]: "正在运行的程序未能安全停止；未写入文件或复位设备。",
    [DeviceOperationPhase.BACKUP]: "设备文件备份未完成，代码没有继续上传。",
    [DeviceOperationPhase.TRANSFER]: "设备文件写入未完成，请检查连接后重试。",
    [DeviceOperationPhase.VERIFY_FILES]: "设备文件回读校验未通过。",
    [DeviceOperationPhase.START_RUNTIME]: "Python 运行环境未能启动；已尝试恢复备份。",
    [DeviceOperationPhase.RESTART]: "主控重启未完成，请检查设备连接。",
    [DeviceOperationPhase.RECONNECT]: "设备管理连接尚未恢复，请重新扫描并连接。",
    [DeviceOperationPhase.RESTORE]: "备份恢复未完成，请保留备份并查看技术日志。",
  };
  return phaseMessages[operation.phase ?? DeviceOperationPhase.QUEUED]
    ?? "设备操作未完成，请检查连接并按提示重试。";
}

function acceptedWateringFiles(codeRun: CodeRun | null): boolean {
  return Boolean(codeRun?.files.some((file) =>
    file.path === "src/drivers/soil_moisture.py"
    || file.path === "src/drivers/pump.py",
  ));
}

function runtimeEvidence(operation: DeviceOperation | null): WateringSmokeEvidence | null {
  const candidate = operation?.metadata?.runtimeEvidence;
  if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) return null;
  const value = candidate as Record<string, unknown>;
  if (
    typeof value.sessionId !== "string"
    || typeof value.operationId !== "string"
    || typeof value.checkedAt !== "string"
    || typeof value.sampleCount !== "number"
    || typeof value.continuousMoistureOk !== "boolean"
    || typeof value.wetPumpOffOk !== "boolean"
    || typeof value.dryLimitedRunOk !== "boolean"
    || typeof value.noUnhandledException !== "boolean"
    || typeof value.ok !== "boolean"
    || typeof value.summary !== "string"
    || !Array.isArray(value.observations)
    || !value.observations.every((item) => typeof item === "string")
  ) return null;
  return value as unknown as WateringSmokeEvidence;
}

function runtimeLabel(runtime: import("@zhangwen/contracts").CodeRuntimeType): string {
  return runtime === CodeRuntime.ESP_CLAW_LUA ? "ESP-Claw Lua" : "MicroPython";
}

function operationDeploymentChannel(
  operation: DeviceOperation,
): import("@zhangwen/contracts").DeviceDeploymentChannelType {
  return operation.metadata?.channel === DeviceDeploymentChannel.ESP_CLAW
    ? DeviceDeploymentChannel.ESP_CLAW
    : DeviceDeploymentChannel.USB_SERIAL;
}

function deriveDeploymentOutcome(operation: DeviceOperation): UploadOutcome {
  return operationDeploymentChannel(operation) === DeviceDeploymentChannel.ESP_CLAW
    ? deriveEspClawOutcome(operation)
    : deriveUploadOutcome(operation);
}

function deriveEspClawOutcome(operation: DeviceOperation): UploadOutcome {
  const preflightStep = findLastStep(operation.steps, DeviceOperationPhase.PREFLIGHT);
  const transferStep = findLastStep(operation.steps, DeviceOperationPhase.TRANSFER);
  const verifyFilesStep = findLastStep(operation.steps, DeviceOperationPhase.VERIFY_FILES);
  const startRuntimeStep = findLastStep(operation.steps, DeviceOperationPhase.START_RUNTIME);
  const verifyRuntimeStep = findLastStep(operation.steps, DeviceOperationPhase.VERIFY_RUNTIME);
  const verification = operation.verification as CompatibleVerification | null | undefined;
  const handshakeState = fallbackStepState(preflightStep, operation.status);
  const deploymentState = explicitResultState(verification?.deploymentOk)
    ?? combineDeploymentState(
      stepResultState(transferStep),
      stepResultState(verifyFilesStep),
      operation.status,
    );
  const runtimeState = explicitResultState(verification?.runtimeStartedOk)
    ?? combineDeploymentState(
      stepResultState(startRuntimeStep),
      stepResultState(verifyRuntimeStep),
      operation.status,
    );
  const items: UploadOutcome["items"] = [
    {
      label: "目标握手",
      state: handshakeState,
      detail: resultDetail(handshakeState, {
        complete: "ESP-Claw endpoint 能力握手通过，用户确认板型与项目场景一致",
        running: "正在验证 endpoint 能力与项目场景板型门禁",
        pending: "等待验证已配对目标",
        warning: "endpoint 握手结果需要人工核对",
        failed: "endpoint 能力握手或项目场景板型门禁失败，未写入代码",
        unknown: "缺少可核对的 endpoint 握手结果",
      }),
    },
    {
      label: "代码发布",
      state: deploymentState,
      detail: resultDetail(deploymentState, {
        complete: "受控路径写入并逐文件回读 SHA-256 一致",
        running: "正在备份、写入或回读 ESP-Claw 代码",
        pending: "等待目标握手通过",
        warning: "代码回读结果需要人工核对",
        failed: "代码写入或回读校验未通过",
        unknown: "缺少可核对的写入与回读结果",
      }),
    },
    {
      label: "Lua 运行",
      state: runtimeState,
      detail: resultDetail(runtimeState, {
        complete: "入口脚本已启动并返回可验证的异步任务终态",
        running: "正在启动入口脚本并等待任务结果",
        pending: "等待代码回读校验完成",
        warning: "Lua 任务结果需要人工核对",
        failed: "入口脚本或异步任务未成功完成",
        unknown: "缺少可核对的 Lua 运行结果",
      }),
    },
  ];
  const warnings = verification?.warnings?.filter((warning) => warning.trim().length > 0) ?? [];
  if (items.every((item) => item.state === "complete")) {
    return {
      summary: "ESP-Claw 代码部署并启动完成",
      state: "complete",
      items,
      managementChannelWarning: false,
      warnings,
    };
  }
  if (items.some((item) => item.state === "failed") || FAILED_OPERATION_STATUSES.has(operation.status)) {
    return {
      summary: handshakeState === "failed" ? "ESP-Claw 握手失败 · 未写入代码" : "ESP-Claw 部署或启动失败",
      state: "failed",
      items,
      managementChannelWarning: false,
      warnings,
    };
  }
  if (items.some((item) => item.state === "running") || operation.status === DeviceOperationStatus.RUNNING) {
    return {
      summary: "ESP-Claw 部署进行中",
      state: "running",
      items,
      managementChannelWarning: false,
      warnings,
    };
  }
  if (operation.status === DeviceOperationStatus.QUEUED) {
    return {
      summary: "等待 ESP-Claw 部署",
      state: "pending",
      items,
      managementChannelWarning: false,
      warnings,
    };
  }
  return {
    summary: "ESP-Claw 部署结果待确认",
    state: "unknown",
    items,
    managementChannelWarning: false,
    warnings,
  };
}

function deriveUploadOutcome(operation: DeviceOperation): UploadOutcome {
  if (operation.dryRun) {
    return {
      summary: "模拟检查完成",
      state: "unknown",
      managementChannelWarning: false,
      warnings: [],
      items: [
        { label: "文件部署", detail: "Dry Run 未写入设备", state: "unknown" },
        { label: "安全停止程序", detail: "Dry Run 未操作设备程序", state: "unknown" },
        { label: "Python 程序", detail: "Dry Run 未启动 main.py", state: "unknown" },
      ],
    };
  }

  const verification = operation.verification as CompatibleVerification | null | undefined;
  const softwareRuntimeStart = operation.metadata?.launchMode === "MICROPYTHON_SOFT_RESET"
    || operation.phase === DeviceOperationPhase.INTERRUPT_RUNTIME
    || operation.phase === DeviceOperationPhase.START_RUNTIME
    || operation.steps?.some((step) => (
      step.phase === DeviceOperationPhase.INTERRUPT_RUNTIME
      || step.phase === DeviceOperationPhase.START_RUNTIME
    )) === true;
  const normalBootReset = operation.metadata?.launchMode === "NORMAL_BOOT_RESET";
  const interruptStep = findLastStep(operation.steps, DeviceOperationPhase.INTERRUPT_RUNTIME);
  const transferStep = findLastStep(operation.steps, DeviceOperationPhase.TRANSFER);
  const verifyStep = findLastStep(operation.steps, DeviceOperationPhase.VERIFY_FILES);
  const restartStep = findLastStep(operation.steps, DeviceOperationPhase.RESTART);
  const startRuntimeStep = findLastStep(operation.steps, DeviceOperationPhase.START_RUNTIME);
  const reconnectStep = findLastStep(operation.steps, DeviceOperationPhase.RECONNECT);

  const transferState = stepResultState(transferStep);
  const verifyState = stepResultState(verifyStep);
  const deploymentState = explicitResultState(verification?.deploymentOk)
    ?? combineDeploymentState(transferState, verifyState, operation.status);
  const interruptState = explicitResultState(verification?.runtimeInterruptedOk)
    ?? fallbackStepState(interruptStep, operation.status);
  const runtimeStartState = explicitResultState(verification?.runtimeStartedOk)
    ?? fallbackStepState(startRuntimeStep, operation.status);
  const restartState = explicitResultState(verification?.restartOk)
    ?? fallbackStepState(restartStep, operation.status);
  const managementState = explicitManagementState(verification?.managementChannelOk)
    ?? reconnectResultState(verification?.reconnectExitCode, reconnectStep, operation.status);

  if (softwareRuntimeStart) {
    const items: UploadOutcome["items"] = [
      {
        label: "安全停止程序",
        state: interruptState,
        detail: resultDetail(interruptState, {
          complete: "已通过 Ctrl-C 接管 MicroPython REPL",
          running: "正在安全停止原程序",
          pending: "等待接管设备程序",
          warning: "程序停止结果需要人工核对",
          failed: "程序未响应，未写入文件或复位设备",
          unknown: "缺少安全停止结果",
        }),
      },
      {
        label: "文件部署",
        state: deploymentState,
        detail: resultDetail(deploymentState, {
          complete: "写入并回读 SHA-256 一致",
          running: "正在写入或回读文件",
          pending: "等待开始文件传输",
          warning: "文件结果需要人工核对",
          failed: "写入或回读校验未通过",
          unknown: "缺少可核对的写入与回读结果",
        }),
      },
      {
        label: "Python 程序",
        state: runtimeStartState,
        detail: resultDetail(runtimeStartState, {
          complete: "main.py 已启动，未复位硬件",
          running: "正在清理旧运行态并启动 main.py",
          pending: "等待文件校验完成",
          warning: "程序启动结果需要人工核对",
          failed: "Python 运行环境未启动",
          unknown: "缺少可核对的启动结果",
        }),
      },
    ];
    const warnings = verification?.warnings?.filter((warning) => warning.trim().length > 0) ?? [];
    if (items.every((item) => item.state === "complete")) {
      return {
        summary: "部署并启动完成 · 未复位硬件",
        state: "complete",
        items,
        managementChannelWarning: false,
        warnings,
      };
    }
    if (items.some((item) => item.state === "failed") || FAILED_OPERATION_STATUSES.has(operation.status)) {
      return {
        summary: interruptState === "failed" ? "安全接管失败 · 未写入设备" : "部署或启动失败",
        state: "failed",
        items,
        managementChannelWarning: false,
        warnings,
      };
    }
    if (items.some((item) => item.state === "running") || operation.status === DeviceOperationStatus.RUNNING) {
      return { summary: "部署进行中", state: "running", items, managementChannelWarning: false, warnings };
    }
    return { summary: "部署结果待确认", state: "unknown", items, managementChannelWarning: false, warnings };
  }

  const items: UploadOutcome["items"] = [
    {
      label: "文件部署",
      state: deploymentState,
      detail: resultDetail(deploymentState, {
        complete: "写入并回读 SHA-256 一致",
        running: "正在写入或回读文件",
        pending: "等待开始文件传输",
        warning: "文件结果需要人工核对",
        failed: "写入或回读校验未通过",
        unknown: "缺少可核对的写入与回读结果",
      }),
    },
    {
      label: "主控重启",
      state: restartState,
      detail: resultDetail(restartState, {
        complete: normalBootReset ? "主控已进入正常启动路径" : "主控重启阶段退出码为 0",
        running: "正在重启主控",
        pending: "等待文件校验完成",
        warning: "重启结果需要人工核对",
        failed: "主控重启未完成",
        unknown: "缺少可核对的重启结果",
      }),
    },
    normalBootReset ? {
      label: "代码运行",
      state: deploymentState === "complete" && restartState === "complete"
        ? "complete"
        : restartState,
      detail: deploymentState === "complete" && restartState === "complete"
        ? "main.py 随正常启动流程运行"
        : "等待主控完成正常启动",
    } : {
      label: "管理通道",
      state: managementState,
      detail: managementState === "warning"
        ? deploymentState === "complete" && restartState === "complete"
          ? "文件已部署，管理连接尚未恢复"
          : "管理连接尚未恢复"
        : resultDetail(managementState, {
          complete: "重启后管理连接已恢复",
          running: "正在等待管理连接恢复",
          pending: "等待主控重启完成",
          warning: "管理连接尚未恢复",
          failed: "管理连接恢复失败",
          unknown: "未提供重连结果",
        }),
    },
  ];

  const managementChannelWarning = !normalBootReset
    && deploymentState === "complete"
    && restartState === "complete"
    && managementState === "warning";
  const warnings = verification?.warnings?.filter((warning) => warning.trim().length > 0) ?? [];

  if (managementChannelWarning) {
    return {
      summary: "部署完成 · 通道待恢复",
      state: "warning",
      items,
      managementChannelWarning,
      warnings,
    };
  }
  if (deploymentState === "failed") {
    return { summary: "文件部署失败", state: "failed", items, managementChannelWarning, warnings };
  }
  if (deploymentState === "complete" && restartState === "failed") {
    return { summary: "主控重启失败", state: "failed", items, managementChannelWarning, warnings };
  }
  if (items.every((item) => item.state === "complete")) {
    return {
      summary: normalBootReset ? "部署并启动完成" : "部署完成",
      state: "complete",
      items,
      managementChannelWarning,
      warnings,
    };
  }
  if (items.some((item) => item.state === "running") || operation.status === DeviceOperationStatus.RUNNING) {
    return { summary: "部署进行中", state: "running", items, managementChannelWarning, warnings };
  }
  if (FAILED_OPERATION_STATUSES.has(operation.status)) {
    return { summary: "操作失败", state: "failed", items, managementChannelWarning, warnings };
  }
  if (operation.status === DeviceOperationStatus.QUEUED) {
    return { summary: "等待执行", state: "pending", items, managementChannelWarning, warnings };
  }
  return { summary: "部署结果待确认", state: "unknown", items, managementChannelWarning, warnings };
}

function findLastStep(
  steps: DeviceOperationStep[] | undefined,
  phase: DeviceOperationStep["phase"],
): DeviceOperationStep | undefined {
  if (!steps) return undefined;
  for (let index = steps.length - 1; index >= 0; index -= 1) {
    if (steps[index]?.phase === phase) return steps[index];
  }
  return undefined;
}

function stepResultState(step: DeviceOperationStep | undefined): ResultState | null {
  if (!step) return null;
  if (step.exitCode === 0) return "complete";
  if (step.exitCode !== null) return "failed";
  if (step.status === DeviceOperationStatus.RUNNING) return "running";
  if (step.status === DeviceOperationStatus.QUEUED) return "pending";
  if (FAILED_OPERATION_STATUSES.has(step.status)) return "failed";
  return "unknown";
}

function explicitResultState(value: boolean | null | undefined): ResultState | null {
  if (value === true) return "complete";
  if (value === false) return "failed";
  return null;
}

function explicitManagementState(value: boolean | null | undefined): ResultState | null {
  if (value === true) return "complete";
  if (value === false) return "warning";
  return null;
}

function combineDeploymentState(
  transfer: ResultState | null,
  verify: ResultState | null,
  operationStatus: DeviceOperation["status"],
): ResultState {
  if (transfer === "failed" || verify === "failed") return "failed";
  if (transfer === "complete" && verify === "complete") return "complete";
  if (transfer === "running" || verify === "running") return "running";
  if (operationStatus === DeviceOperationStatus.QUEUED) return "pending";
  return transfer ?? verify ?? "unknown";
}

function fallbackStepState(
  step: DeviceOperationStep | undefined,
  operationStatus: DeviceOperation["status"],
): ResultState {
  return stepResultState(step)
    ?? (operationStatus === DeviceOperationStatus.QUEUED ? "pending" : "unknown");
}

function reconnectResultState(
  reconnectExitCode: number | null | undefined,
  reconnectStep: DeviceOperationStep | undefined,
  operationStatus: DeviceOperation["status"],
): ResultState {
  if (reconnectExitCode === 0) return "complete";
  if (typeof reconnectExitCode === "number") return "warning";
  const stepState = stepResultState(reconnectStep);
  if (stepState === "failed") return "warning";
  if (stepState) return stepState;
  return operationStatus === DeviceOperationStatus.QUEUED ? "pending" : "unknown";
}

function resultDetail(state: ResultState, details: Record<ResultState, string>): string {
  return details[state];
}

function classifyScanError(error: unknown): ScanError {
  const message = error instanceof Error ? error.message : "未知扫描错误。";
  if (message.includes("DESKTOP_CAPABILITY_MISMATCH")) {
    return {
      title: "本地会话已失效",
      message: "请关闭旧掌问窗口，然后通过 start-local.bat 重新启动完整本地应用。",
    };
  }
  if (message.includes("SERIAL_SERVICE_UNAVAILABLE")) return { title: "串口服务不可用", message };
  if (message.includes("SIDECAR") || message.includes("Failed to fetch")) {
    return { title: "Sidecar 未启动", message: "请确认桌面后端服务已启动后重试。" };
  }
  if (message.includes("SERIAL_SYSTEM_API_FAILED")) return { title: "系统 API 调用失败", message };
  if (message.includes("SERIAL_PERMISSION_DENIED")) return { title: "权限不足", message };
  return { title: "未知扫描错误", message };
}

function formatVidPid(vid?: number | null, pid?: number | null) {
  if (vid == null && pid == null) return "未知";
  const vidText = vid == null ? "未知" : `0x${vid.toString(16).padStart(4, "0").toUpperCase()}`;
  const pidText = pid == null ? "未知" : `0x${pid.toString(16).padStart(4, "0").toUpperCase()}`;
  return `${vidText}/${pidText}`;
}

function isUsbSerialSession(session: DeviceSession): boolean {
  return !session.portId.startsWith("esp-claw:");
}

function endpointMatchesProjectBoard(
  endpoint: EspClawEndpoint,
  projectBoardId: SupportedDeviceBoardIdType | null,
): boolean {
  return projectBoardId === null || endpoint.boardId === projectBoardId;
}

function preferredProjectBoardId(
  workspace: ProjectWorkspace | null,
): SupportedDeviceBoardIdType | null {
  const fact = workspace?.sharedContext?.confirmedFacts?.find((item) => (
    (item.field === "preferred_hardware" || item.key === "preferred_hardware")
    && (item.confirmed || item.status === "confirmed")
  ));
  if (!fact || typeof fact.value !== "object" || fact.value === null) return null;
  const components = (fact.value as { components?: unknown }).components;
  if (!Array.isArray(components)) return null;
  const boards = new Set<SupportedDeviceBoardIdType>();
  for (const component of components) {
    if (!component || typeof component !== "object" || !("id" in component)) continue;
    const id = String((component as { id: unknown }).id);
    if (id === "hw_seeed_xiao_esp32s3_sense" || id === SupportedDeviceBoardId.XIAO_ESP32S3_SENSE) {
      boards.add(SupportedDeviceBoardId.XIAO_ESP32S3_SENSE);
    }
    if (
      id === "hw_seed_unihiker_k10"
      || id === "unihiker-k10"
      || id === SupportedDeviceBoardId.DFROBOT_K10
    ) {
      boards.add(SupportedDeviceBoardId.DFROBOT_K10);
    }
  }
  return boards.size === 1 ? [...boards][0] ?? null : null;
}

async function pairEspClaw(
  projectId: string | null,
  webEndpoint: string,
  mcpEndpoint: string,
  boardId: SupportedDeviceBoardIdType,
  confirmTrustedLan: boolean,
  confirmAdminMode: boolean,
  confirmBoardIdentity: boolean,
  setEndpoints: (endpoints: EspClawEndpoint[] | ((current: EspClawEndpoint[]) => EspClawEndpoint[])) => void,
  setSelectedEndpointId: (endpointId: string) => void,
  setError: (error: string | null) => void,
  setBusy: (busy: boolean) => void,
) {
  if (!projectId) return;
  setBusy(true);
  setError(null);
  try {
    const response = await pairEspClawEndpoint(projectId, {
      pairingMode: "TRUSTED_LAN_MANUAL",
      webEndpoint: webEndpoint.trim(),
      mcpEndpoint: mcpEndpoint.trim(),
      boardId,
      confirmTrustedLan,
      confirmAdminMode,
      confirmBoardIdentity,
    });
    setEndpoints((current) => [
      ...current.filter((item) => item.id !== response.endpoint.id),
      response.endpoint,
    ]);
    setSelectedEndpointId(response.endpoint.id);
  } catch (error) {
    setError(error instanceof Error ? error.message : "ESP-Claw 配对失败，请检查可信局域网和设备 Admin 模式。");
  } finally {
    setBusy(false);
  }
}

async function connect(
  projectId: string | null,
  portId: string,
  boardId: SupportedDeviceBoardIdType,
  setSession: (session: DeviceSession | null) => void,
  setError: (error: string | null) => void,
  setBusy: (busy: boolean) => void,
  onConnected?: (session: DeviceSession) => void,
) {
  if (!projectId) return;
  setBusy(true);
  setError(null);
  try {
    const response = await connectDevice(projectId, {
      portId,
      boardId,
      confirmBoardIdentity: true,
    });
    setSession(response.session);
    onConnected?.(response.session);
  } catch (error) {
    setError(error instanceof Error ? error.message : "连接设备失败。");
  } finally {
    setBusy(false);
  }
}

async function disconnect(
  projectId: string | null,
  session: DeviceSession,
  setSession: (session: DeviceSession | null) => void,
  setError: (error: string | null) => void,
  setBusy: (busy: boolean) => void,
) {
  if (!projectId) return;
  setBusy(true);
  setError(null);
  try {
    const response = await disconnectDevice(projectId, { sessionId: session.id });
    setSession(response.session);
  } catch (error) {
    setError(error instanceof Error ? error.message : "断开设备失败。");
  } finally {
    setBusy(false);
  }
}

async function takeover(
  projectId: string | null,
  session: DeviceSession,
  confirmHardwareReset: boolean,
  confirmationPhrase: string | null,
  setSession: (session: DeviceSession | null) => void,
  setError: (error: string | null) => void,
  setHardwareResetRequired: (required: boolean) => void,
  setBusy: (busy: boolean) => void,
) {
  if (!projectId) return;
  setBusy(true);
  setError(null);
  try {
    const response = await takeoverDevice(projectId, {
      sessionId: session.id,
      confirmHardwareReset,
      confirmationPhrase: confirmationPhrase ?? undefined,
    });
    setSession(response.session);
    setHardwareResetRequired(false);
  } catch (error) {
    setHardwareResetRequired(
      error instanceof ApiError && error.code === "DEVICE_RUNTIME_BUSY",
    );
    setError(error instanceof Error ? error.message : "设备运行态接管失败。");
  } finally {
    setBusy(false);
  }
}

async function startDeployment(
  projectId: string | null,
  channel: import("@zhangwen/contracts").DeviceDeploymentChannelType,
  targetId: string | null,
  acceptedCode: CodeRun | null,
  setSession: (session: DeviceSession | null) => void,
  setOperation: (operation: DeviceOperation | null) => void,
  setPendingRequest: (request: PendingDeploymentRequest | null) => void,
  setError: (error: string | null) => void,
  setBusy: (busy: boolean) => void,
) {
  if (!projectId || !targetId || !acceptedCode) return;
  const operationId = createOperationId("upload");
  const pendingRequest: PendingDeploymentRequest = {
    schemaVersion: 2,
    operationId,
    codeRunId: acceptedCode.id,
    channel,
    targetId,
  };
  setBusy(true);
  setError(null);
  setPendingRequest(pendingRequest);
  try {
    const response = await deployCodeToDevice(
      projectId,
      channel === DeviceDeploymentChannel.ESP_CLAW
        ? {
            channel,
            codeRunId: acceptedCode.id,
            endpointId: targetId,
            operationId,
            confirmWrite: true,
          }
        : {
            channel,
            codeRunId: acceptedCode.id,
            sessionId: targetId,
            dryRun: false,
            operationId,
            confirmWrite: true,
          },
    );
    if (
      response.operation.id !== operationId
      || operationDeploymentChannel(response.operation) !== channel
    ) {
      setError("本地服务返回了不匹配的部署操作；为避免跨目标写入，本次操作保持锁定。");
      return;
    }
    setOperation(response.operation);
    if (channel === DeviceDeploymentChannel.USB_SERIAL) setSession(response.session);
    setPendingRequest(
      TERMINAL_OPERATION_STATUSES.has(response.operation.status) ? null : pendingRequest,
    );
  } catch (error) {
    try {
      const recovered = await getDeviceOperation(projectId, operationId);
      if (recovered.operation.id === operationId) {
        if (operationDeploymentChannel(recovered.operation) !== channel) {
          setError("恢复到的部署通道与原请求不一致，本次操作保持锁定。");
          return;
        }
        setOperation(recovered.operation);
        if (channel === DeviceDeploymentChannel.USB_SERIAL) setSession(recovered.session);
        setPendingRequest(
          TERMINAL_OPERATION_STATUSES.has(recovered.operation.status) ? null : pendingRequest,
        );
        return;
      }
    } catch {
      // Keep the operation locked until the user explicitly reconciles its persisted state.
    }
    setError(
      "上传请求结果尚未确认。为避免重复写入，已暂停再次上传；请先恢复上传状态。",
    );
  } finally {
    setBusy(false);
  }
}

async function recoverPendingUpload(
  projectId: string | null,
  pendingRequest: PendingDeploymentRequest,
  setSession: (session: DeviceSession | null) => void,
  setOperation: (operation: DeviceOperation | null) => void,
  setPendingRequest: (request: PendingDeploymentRequest | null) => void,
  setError: (error: string | null) => void,
  setBusy: (busy: boolean) => void,
) {
  if (!projectId) return;
  setBusy(true);
  setError(null);
  try {
    const response = await getDeviceOperation(projectId, pendingRequest.operationId);
    if (response.operation.id !== pendingRequest.operationId) {
      setError("尚未找到本次上传记录。再次上传仍保持锁定，请稍后重试恢复状态。");
      return;
    }
    if (operationDeploymentChannel(response.operation) !== pendingRequest.channel) {
      setError("恢复到的操作属于另一部署通道，不能作为本次上传继续处理。");
      return;
    }
    setOperation(response.operation);
    if (pendingRequest.channel === DeviceDeploymentChannel.USB_SERIAL) {
      setSession(response.session);
    }
    setPendingRequest(
      TERMINAL_OPERATION_STATUSES.has(response.operation.status) ? null : pendingRequest,
    );
  } catch (error) {
    setError(error instanceof Error ? error.message : "恢复上传状态失败，请稍后重试。");
  } finally {
    setBusy(false);
  }
}

async function retryPendingUploadRequest(
  projectId: string | null,
  pendingRequest: PendingDeploymentRequest,
  acceptedCode: CodeRun | null,
  channel: import("@zhangwen/contracts").DeviceDeploymentChannelType,
  targetId: string | null,
  setSession: (session: DeviceSession | null) => void,
  setOperation: (operation: DeviceOperation | null) => void,
  setPendingRequest: (request: PendingDeploymentRequest | null) => void,
  setError: (error: string | null) => void,
  setBusy: (busy: boolean) => void,
) {
  if (!projectId) return;
  if (
    acceptedCode?.id !== pendingRequest.codeRunId
    || channel !== pendingRequest.channel
    || targetId !== pendingRequest.targetId
    || (acceptedCode.runtime ?? CodeRuntime.MICROPYTHON) !== (
      channel === DeviceDeploymentChannel.ESP_CLAW
        ? CodeRuntime.ESP_CLAW_LUA
        : CodeRuntime.MICROPYTHON
    )
  ) {
    setError("当前代码、部署通道或目标已经变化，不能重试待确认上传。请先重新核对。");
    return;
  }
  setBusy(true);
  setError(null);
  try {
    const response = await deployCodeToDevice(
      projectId,
      channel === DeviceDeploymentChannel.ESP_CLAW
        ? {
            channel,
            codeRunId: pendingRequest.codeRunId,
            endpointId: pendingRequest.targetId,
            operationId: pendingRequest.operationId,
            confirmWrite: true,
          }
        : {
            channel,
            codeRunId: pendingRequest.codeRunId,
            sessionId: pendingRequest.targetId,
            dryRun: false,
            operationId: pendingRequest.operationId,
            confirmWrite: true,
          },
    );
    if (response.operation.id !== pendingRequest.operationId) {
      setError("本地服务返回了不匹配的设备操作，重试保持锁定。请重新读取状态。");
      return;
    }
    if (operationDeploymentChannel(response.operation) !== pendingRequest.channel) {
      setError("本地服务返回了另一部署通道的操作，重试保持锁定。");
      return;
    }
    setOperation(response.operation);
    if (channel === DeviceDeploymentChannel.USB_SERIAL) setSession(response.session);
    setPendingRequest(
      TERMINAL_OPERATION_STATUSES.has(response.operation.status) ? null : pendingRequest,
    );
  } catch {
    setError("同一设备操作的重试结果仍未确认，上传保持锁定。请重新读取状态。");
  } finally {
    setBusy(false);
  }
}

async function selectFirmware(
  projectId: string | null,
  file: File | null,
  setCandidate: (candidate: FirmwareCandidate | null) => void,
  setPlan: (plan: FirmwareFlashPlan | null) => void,
  setAddress: (address: string) => void,
  setError: (error: string | null) => void,
  setBusy: (busy: boolean) => void,
) {
  if (!projectId || !file) return;
  setBusy(true);
  setError(null);
  setPlan(null);
  try {
    const response = await inspectFirmware(projectId, {
      fileName: file.name,
      contentBase64: await fileToBase64(file),
    });
    setCandidate(response.candidate);
    setAddress(
      response.candidate.defaultAddress === null
        ? ""
        : `0x${response.candidate.defaultAddress.toString(16).toUpperCase()}`,
    );
  } catch (error) {
    setCandidate(null);
    setError(error instanceof Error ? error.message : "固件检查失败。");
  } finally {
    setBusy(false);
  }
}

async function prepareFlash(
  projectId: string | null,
  session: DeviceSession | null,
  candidate: FirmwareCandidate,
  addressText: string,
  setPlan: (plan: FirmwareFlashPlan | null) => void,
  setError: (error: string | null) => void,
  setBusy: (busy: boolean) => void,
) {
  if (!projectId || !session) return;
  const address = parseAddress(addressText);
  if (address === null) {
    setError("请输入有效的十六进制或十进制固件地址。");
    return;
  }
  setBusy(true);
  setError(null);
  try {
    const response = await prepareFirmware(projectId, {
      sessionId: session.id,
      candidateId: candidate.id,
      address,
    });
    setPlan(response.plan);
  } catch (error) {
    setPlan(null);
    setError(error instanceof Error ? error.message : "生成固件计划失败。");
  } finally {
    setBusy(false);
  }
}

async function startFlash(
  projectId: string | null,
  session: DeviceSession | null,
  plan: FirmwareFlashPlan,
  confirmationPhrase: string,
  setSession: (session: DeviceSession | null) => void,
  setOperation: (operation: DeviceOperation | null) => void,
  setError: (error: string | null) => void,
  setBusy: (busy: boolean) => void,
) {
  if (!projectId || !session) return;
  setBusy(true);
  setError(null);
  try {
    const response = await flashFirmware(projectId, {
      sessionId: session.id,
      dryRun: false,
      confirmFlash: true,
      candidateId: plan.candidate.id,
      confirmationToken: plan.confirmationToken,
      confirmationPhrase,
      operationId: createOperationId("firmware"),
      address: plan.address,
    });
    setOperation(response.operation);
    setSession(response.session);
  } catch (error) {
    setError(error instanceof Error ? error.message : "固件烧录启动失败。");
  } finally {
    setBusy(false);
  }
}

async function cancelOperation(
  projectId: string | null,
  operationId: string,
  setOperation: (operation: DeviceOperation | null) => void,
  setSession: (session: DeviceSession | null) => void,
  setError: (error: string | null) => void,
  setPendingRequest?: (request: PendingDeploymentRequest | null) => void,
) {
  if (!projectId) return;
  setError(null);
  try {
    const response = await cancelDeviceOperation(projectId, operationId);
    setOperation(response.operation);
    if (operationDeploymentChannel(response.operation) === DeviceDeploymentChannel.USB_SERIAL) {
      setSession(response.session);
    }
    if (TERMINAL_OPERATION_STATUSES.has(response.operation.status)) {
      setPendingRequest?.(null);
    }
  } catch (error) {
    setError(error instanceof Error ? error.message : "取消设备操作失败。");
  }
}

function pendingUploadStorageKey(projectId: string): string {
  return `${PENDING_UPLOAD_STORAGE_PREFIX}${projectId}`;
}

function readPendingUploadRequest(projectId: string): PendingDeploymentRequest | null {
  try {
    const raw = globalThis.sessionStorage?.getItem(pendingUploadStorageKey(projectId));
    if (!raw) return null;
    const value = JSON.parse(raw) as Record<string, unknown>;
    if (
      value.schemaVersion === 2
      && typeof value.operationId === "string"
      && /^upload-[A-Za-z0-9-]{1,128}$/.test(value.operationId)
      && isSafeLocalId(value.codeRunId)
      && isDeploymentChannel(value.channel)
      && isSafeLocalId(value.targetId)
    ) {
      return {
        schemaVersion: 2,
        operationId: value.operationId,
        codeRunId: value.codeRunId,
        channel: value.channel,
        targetId: value.targetId,
      };
    }
    if (
      value.schemaVersion === 1
      && typeof value.operationId === "string"
      && /^upload-[A-Za-z0-9-]{1,128}$/.test(value.operationId)
      && isSafeLocalId(value.codeRunId)
      && isSafeLocalId(value.sessionId)
    ) {
      return {
        schemaVersion: 2,
        operationId: value.operationId,
        codeRunId: value.codeRunId,
        channel: DeviceDeploymentChannel.USB_SERIAL,
        targetId: value.sessionId,
      };
    }
    globalThis.sessionStorage.removeItem(pendingUploadStorageKey(projectId));
  } catch {
    // Session storage may be unavailable in a restricted desktop webview.
  }
  return null;
}

function persistPendingUploadRequest(
  projectId: string,
  request: PendingDeploymentRequest | null,
): void {
  try {
    const key = pendingUploadStorageKey(projectId);
    if (request) globalThis.sessionStorage?.setItem(key, JSON.stringify(request));
    else globalThis.sessionStorage?.removeItem(key);
  } catch {
    // In-memory locking remains active for the current mount when storage is unavailable.
  }
}

function isDeploymentChannel(
  value: unknown,
): value is import("@zhangwen/contracts").DeviceDeploymentChannelType {
  return value === DeviceDeploymentChannel.USB_SERIAL
    || value === DeviceDeploymentChannel.ESP_CLAW;
}

function isSupportedBoardId(value: string): value is SupportedDeviceBoardIdType {
  return value === SupportedDeviceBoardId.DFROBOT_K10
    || value === SupportedDeviceBoardId.XIAO_ESP32S3_SENSE;
}

function isSafeLocalId(value: unknown): value is string {
  return typeof value === "string" && /^[A-Za-z0-9][A-Za-z0-9_-]{0,159}$/.test(value);
}

function formatRetryDelay(delayMs: number): string {
  return delayMs < 1000 ? `${delayMs} 毫秒` : `${delayMs / 1000} 秒`;
}

function createOperationId(prefix: string): string {
  const suffix = typeof globalThis.crypto?.randomUUID === "function"
    ? globalThis.crypto.randomUUID()
    : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  return `${prefix}-${suffix}`;
}

async function fileToBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
  }
  return globalThis.btoa(binary);
}

function parseAddress(value: string): number | null {
  const trimmed = value.trim();
  if (!/^(?:0x[0-9a-f]+|\d+)$/i.test(trimmed)) return null;
  const parsed = Number.parseInt(trimmed, trimmed.toLowerCase().startsWith("0x") ? 16 : 10);
  return Number.isSafeInteger(parsed) && parsed >= 0 ? parsed : null;
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}
