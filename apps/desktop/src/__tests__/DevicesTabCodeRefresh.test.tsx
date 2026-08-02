import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import {
  CodeRuntime,
  CodeRunStatus,
  DeviceOperationKind,
  DeviceOperationPhase,
  DeviceOperationStatus,
  DeviceSessionStatus,
  DeviceTerminalStatus,
  type CodeRun,
  type DeviceOperation,
  type DeviceSession,
  type ProjectWorkspace,
  type SupportedDeviceBoardIdType,
} from "@zhangwen/contracts";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DevicesTab } from "../components/right-panel/DevicesTab";
import {
  createHostAdapter,
  HostAdapterProvider,
  platformCapabilities,
} from "../platform";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  globalThis.sessionStorage.clear();
});

describe("设备页代码版本刷新", () => {
  it("显示无硬件复位的安全接管、文件部署和 Python 启动结果", async () => {
    const currentSession = deviceSession(DeviceSessionStatus.READY);
    const operation = softwareRuntimeUploadOperation();
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/projects/prj_1/code/current")) {
        return json({ codeRun: codeRun(CodeRunStatus.ACCEPTED) });
      }
      if (url.endsWith("/api/projects/prj_1/devices/session/current")) {
        return json({ session: currentSession });
      }
      if (url.endsWith("/api/projects/prj_1/devices/operations/latest")) {
        return json({ operation, session: currentSession });
      }
      if (url.endsWith("/api/projects/prj_1/devices/terminal")) {
        return json({ terminal: null });
      }
      return json({}, 404);
    }));

    render(deviceTab(false));

    const result = await screen.findByRole("region", { name: "最近设备操作" });
    expect(result).toHaveTextContent("部署并启动完成 · 未复位硬件");
    expect(result).toHaveTextContent("安全停止程序");
    expect(result).toHaveTextContent("已通过 Ctrl-C 接管 MicroPython REPL");
    expect(result).toHaveTextContent("文件部署");
    expect(result).toHaveTextContent("Python 程序");
    expect(result).toHaveTextContent("main.py 已启动，未复位硬件");
    expect(result).not.toHaveTextContent("主控重启");
  });

  it("安全接管失败时明确说明未写入且未自动复位", async () => {
    const currentSession = deviceSession(DeviceSessionStatus.ERROR);
    const operation: DeviceOperation = {
      ...softwareRuntimeUploadOperation(),
      status: DeviceOperationStatus.FAILED,
      errorCode: "DEVICE_RUNTIME_INTERRUPT_FAILED",
      log: "MicroPython 上传未通过本地执行检查。",
      steps: [{
        ...operationStep(DeviceOperationPhase.INTERRUPT_RUNTIME, 71, "安全停止程序"),
        status: DeviceOperationStatus.FAILED,
      }],
      verification: {
        fileHashes: {},
        reconnectExitCode: null,
        runtimeExitCode: null,
        ok: false,
        summary: "安全停止失败。",
        deploymentOk: null,
        restartOk: null,
        runtimeInterruptedOk: false,
        runtimeStartedOk: null,
        managementChannelOk: null,
        warnings: [],
      },
      metadata: {},
    };
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/projects/prj_1/code/current")) {
        return json({ codeRun: codeRun(CodeRunStatus.ACCEPTED) });
      }
      if (url.endsWith("/api/projects/prj_1/devices/session/current")) {
        return json({ session: currentSession });
      }
      if (url.endsWith("/api/projects/prj_1/devices/operations/latest")) {
        return json({ operation, session: currentSession });
      }
      return json({}, 404);
    }));

    render(deviceTab(false));

    const result = await screen.findByRole("region", { name: "最近设备操作" });
    expect(result).toHaveTextContent("安全接管失败 · 未写入设备");
    expect(result).toHaveTextContent("未写入文件，也未自动复位设备");
    expect(result).not.toHaveTextContent("主控重启");
  });

  it("产物状态变化后重读当前代码，不重复扫描串口", async () => {
    let currentCode = codeRun(CodeRunStatus.READY_FOR_REVIEW);
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/projects/prj_1/code/current")) {
        return json({ codeRun: currentCode });
      }
      if (url.endsWith("/api/projects/prj_1/devices/session/current")) {
        return json({ detail: { code: "DEVICE_SESSION_NOT_FOUND" } }, 404);
      }
      if (url.endsWith("/api/projects/prj_1/devices/ports")) {
        return json({ ports: [], scannedAt: "2026-07-11T00:00:00Z", count: 0 });
      }
      return json({}, 404);
    });
    vi.stubGlobal("fetch", fetchMock);
    const adapter = createHostAdapter(platformCapabilities("tauri"));
    const renderDeviceTab = (refreshRevision: number) => (
      <HostAdapterProvider adapter={adapter}>
        <DevicesTab
          workspace={workspace()}
          professionalMode={false}
          refreshRevision={refreshRevision}
        />
      </HostAdapterProvider>
    );

    const view = render(renderDeviceTab(0));

    expect(await screen.findByText("等待已接受代码")).toBeInTheDocument();
    await waitFor(() => {
      expect(fetchMock.mock.calls.filter(([target]) =>
        String(target).endsWith("/devices/ports"),
      )).toHaveLength(1);
    });
    const initialScanCount = fetchMock.mock.calls.filter(([target]) =>
      String(target).endsWith("/devices/ports"),
    ).length;
    currentCode = codeRun(CodeRunStatus.ACCEPTED);
    view.rerender(renderDeviceTab(1));

    expect(await screen.findByText(/已接受 v1/)).toBeInTheDocument();
    await waitFor(() => {
      expect(fetchMock.mock.calls.filter(([target]) =>
        String(target).endsWith("/code/current"),
      )).toHaveLength(2);
    });
    expect(fetchMock.mock.calls.filter(([target]) =>
      String(target).endsWith("/devices/ports"),
    )).toHaveLength(initialScanCount);
  });

  it("兼容显示旧版部署、主控重启和管理通道结果，并提供明确恢复操作", async () => {
    let currentSession = deviceSession(DeviceSessionStatus.ERROR);
    const operation = legacyReconnectWarningOperation();
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/api/projects/prj_1/code/current")) {
        return json({ codeRun: codeRun(CodeRunStatus.ACCEPTED) });
      }
      if (url.endsWith("/api/projects/prj_1/devices/session/current")) {
        return json({ session: currentSession });
      }
      if (url.endsWith("/api/projects/prj_1/devices/operations/latest")) {
        return json({ operation, session: currentSession });
      }
      if (url.endsWith("/api/projects/prj_1/devices/ports")) {
        return json({ ports: [devicePort()], scannedAt: "2026-07-12T00:00:00Z", count: 1 });
      }
      if (url.endsWith("/api/projects/prj_1/devices/connect") && method === "POST") {
        currentSession = deviceSession(DeviceSessionStatus.READY);
        return json({ session: currentSession });
      }
      return json({}, 404);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(deviceTab(false));

    const flow = await screen.findByRole("list", { name: "上传流程" });
    expect(within(flow).getByText("选择已确认代码")).toBeInTheDocument();
    expect(within(flow).getByText("连接设备")).toBeInTheDocument();
    expect(within(flow).getByText("确认上传")).toBeInTheDocument();
    expect(within(flow).getByText("查看运行结果")).toBeInTheDocument();
    expect(screen.queryByText("COM98")).not.toBeInTheDocument();
    expect(screen.queryByText(/COM97/)).not.toBeInTheDocument();

    const result = await screen.findByRole("region", { name: "最近设备操作" });
    expect(result).toHaveTextContent("部署完成 · 通道待恢复");
    expect(result).toHaveTextContent("文件部署");
    expect(result).toHaveTextContent("主控重启");
    expect(result).toHaveTextContent("管理通道");
    expect(result).toHaveTextContent("文件已部署，管理通道待恢复");
    expect(result).toHaveTextContent("不代表程序界面或业务效果已经验证");
    expect(within(result).queryByText(/退出码 7/)).not.toBeInTheDocument();
    expect(within(result).queryByText("历史重连超时日志")).not.toBeInTheDocument();

    fireEvent.click(within(result).getByRole("button", { name: "重新扫描" }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.filter(([target]) =>
        String(target).endsWith("/devices/ports"),
      ).length).toBeGreaterThan(1);
    });

    fireEvent.click(within(result).getByRole("button", { name: "重新连接" }));
    expect(await within(result).findByText("管理通道现已恢复")).toBeInTheDocument();
  });

  it("专业模式保留退出码、技术日志和独立固件区", async () => {
    const currentSession = deviceSession(DeviceSessionStatus.ERROR);
    const operation = legacyReconnectWarningOperation();
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/projects/prj_1/code/current")) {
        return json({ codeRun: codeRun(CodeRunStatus.ACCEPTED) });
      }
      if (url.endsWith("/api/projects/prj_1/devices/session/current")) {
        return json({ session: currentSession });
      }
      if (url.endsWith("/api/projects/prj_1/devices/operations/latest")) {
        return json({ operation, session: currentSession });
      }
      if (url.endsWith("/api/projects/prj_1/devices/ports")) {
        return json({ ports: [devicePort()], scannedAt: "2026-07-12T00:00:00Z", count: 1 });
      }
      return json({}, 404);
    }));

    render(deviceTab(true));

    const result = await screen.findByRole("region", { name: "最近设备操作" });
    expect(within(result).getByText("阶段与技术日志")).toBeInTheDocument();
    expect(within(result).getByText("退出码 7")).toBeInTheDocument();
    expect(within(result).getByText("DEVICE_RECONNECT_TIMEOUT")).toBeInTheDocument();
    expect(within(result).getByText("历史重连超时日志")).toBeInTheDocument();
    expect(screen.getByText("COM98")).toBeInTheDocument();
    expect(screen.getByText(/COM97/)).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "固件烧录" })).toHaveTextContent(
      "独立高风险流程",
    );
  });

  it("普通模式把内部失败码映射为中文说明", async () => {
    const currentSession = deviceSession(DeviceSessionStatus.ERROR);
    const operation: DeviceOperation = {
      ...uploadOperation(DeviceOperationStatus.FAILED, false),
      errorCode: "DEVICE_READBACK_MISMATCH",
      phase: DeviceOperationPhase.VERIFY_FILES,
      steps: [
        operationStep(DeviceOperationPhase.TRANSFER, 0, "写入文件"),
        operationStep(DeviceOperationPhase.VERIFY_FILES, 3, "回读哈希不一致"),
      ],
      verification: {
        fileHashes: {},
        reconnectExitCode: null,
        runtimeExitCode: null,
        ok: false,
        summary: "回读哈希不一致。",
        deploymentOk: false,
        restartOk: null,
        managementChannelOk: null,
        warnings: [],
      },
    };
    mockDeviceState(operation, currentSession);

    render(deviceTab(false));

    const result = await screen.findByRole("region", { name: "最近设备操作" });
    expect(result).toHaveTextContent("设备文件与上传内容不一致，校验未通过。");
    expect(result).not.toHaveTextContent("DEVICE_READBACK_MISMATCH");
  });

  it("另一设备会话就绪时不自动宣称原操作管理通道已恢复", async () => {
    const operationSession = deviceSession(DeviceSessionStatus.ERROR);
    const otherSession = {
      ...deviceSession(DeviceSessionStatus.READY),
      id: "device_session_2",
      portId: "device_port_2",
    };
    const operation = legacyReconnectWarningOperation();
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/projects/prj_1/code/current")) {
        return json({ codeRun: codeRun(CodeRunStatus.ACCEPTED) });
      }
      if (url.endsWith("/api/projects/prj_1/devices/session/current")) {
        return json({ session: otherSession });
      }
      if (url.endsWith("/api/projects/prj_1/devices/operations/latest")) {
        return json({ operation, session: operationSession });
      }
      if (url.endsWith("/api/projects/prj_1/devices/ports")) {
        return json({ ports: [devicePort()], scannedAt: "2026-07-12T00:00:00Z", count: 1 });
      }
      return json({}, 404);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(deviceTab(false));

    const result = await screen.findByRole("region", { name: "最近设备操作" });
    expect(result).toHaveTextContent("文件已部署，管理通道待恢复");
    expect(within(result).queryByText("管理通道现已恢复")).not.toBeInTheDocument();
    expect(within(result).queryByRole("button", { name: "重新连接" })).not.toBeInTheDocument();
  });

  it("上传 POST 响应丢失后跨重挂载恢复幂等记录而不重复上传", async () => {
    const currentSession = deviceSession(DeviceSessionStatus.READY);
    let persistedOperation: DeviceOperation | null = null;
    let allowOperationRead = false;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/api/projects/prj_1/code/current")) {
        return json({ codeRun: codeRun(CodeRunStatus.ACCEPTED) });
      }
      if (url.endsWith("/api/projects/prj_1/devices/session/current")) {
        return json({ session: currentSession });
      }
      if (url.endsWith("/api/projects/prj_1/devices/operations/latest")) {
        return json({}, 404);
      }
      if (
        allowOperationRead
        && persistedOperation
        && url.endsWith(`/api/projects/prj_1/devices/operations/${persistedOperation.id}`)
      ) {
        return json({ operation: persistedOperation, session: currentSession });
      }
      if (url.endsWith("/api/projects/prj_1/devices/ports")) {
        return json({ ports: [devicePort()], scannedAt: "2026-07-12T00:00:00Z", count: 1 });
      }
      if (url.endsWith("/api/projects/prj_1/devices/deploy") && method === "POST") {
        const request = JSON.parse(String(init?.body ?? "{}")) as { operationId: string };
        persistedOperation = {
          ...uploadOperation(DeviceOperationStatus.COMPLETED, true),
          id: request.operationId,
        };
        throw new TypeError("response connection closed");
      }
      return json({}, 404);
    });
    vi.stubGlobal("fetch", fetchMock);

    const first = render(deviceTab(false));
    await screen.findByText(/已接受 v1/);
    fireEvent.click(screen.getByRole("button", { name: "上传并运行" }));

    expect(await screen.findByRole("button", { name: "恢复上传状态" })).toBeInTheDocument();
    expect(globalThis.sessionStorage).toHaveLength(1);
    const storedValue = globalThis.sessionStorage.key(0)
      ? globalThis.sessionStorage.getItem(globalThis.sessionStorage.key(0)!)
      : null;
    const storedRequest = JSON.parse(storedValue ?? "{}") as Record<string, unknown>;
    expect(Object.keys(storedRequest).sort()).toEqual([
      "channel",
      "codeRunId",
      "operationId",
      "schemaVersion",
      "targetId",
    ]);
    expect(storedRequest.channel).toBe("USB_SERIAL");
    expect(storedRequest.targetId).toBe(currentSession.id);
    expect(screen.getByRole("radio", { name: "ESP-Claw" })).toBeDisabled();
    expect(storedRequest.operationId).toMatch(/^upload-[A-Za-z0-9-]+$/);
    expect(storedValue).not.toContain("device_port_1");
    expect(storedValue).not.toContain("print(");

    allowOperationRead = true;
    first.unmount();
    render(deviceTab(false));

    const result = await screen.findByRole("region", { name: "最近设备操作" });
    expect(result).toHaveTextContent("部署并启动完成");
    expect(result).toHaveTextContent("代码运行");
    expect(result).toHaveTextContent("main.py 随正常启动流程运行");
    expect(globalThis.sessionStorage).toHaveLength(0);
    expect(fetchMock.mock.calls.filter(([target, request]) =>
      String(target).endsWith("/devices/deploy") && request?.method === "POST",
    )).toHaveLength(1);
  });

  it("首次请求未到服务端时使用同一操作 ID 重试上传", async () => {
    const currentSession = deviceSession(DeviceSessionStatus.READY);
    const uploadBodies: Array<Record<string, unknown> & { operationId: string }> = [];
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/api/projects/prj_1/code/current")) {
        return json({ codeRun: codeRun(CodeRunStatus.ACCEPTED) });
      }
      if (url.endsWith("/api/projects/prj_1/devices/session/current")) {
        return json({ session: currentSession });
      }
      if (url.endsWith("/api/projects/prj_1/devices/operations/latest")) {
        return json({}, 404);
      }
      if (url.includes("/api/projects/prj_1/devices/operations/")) {
        return json({}, 404);
      }
      if (url.endsWith("/api/projects/prj_1/devices/ports")) {
        return json({ ports: [devicePort()], scannedAt: "2026-07-12T00:00:00Z", count: 1 });
      }
      if (url.endsWith("/api/projects/prj_1/devices/deploy") && method === "POST") {
        const request = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown> & {
          operationId: string;
        };
        uploadBodies.push(request);
        if (uploadBodies.length === 1) throw new TypeError("request did not reach service");
        return json({
          operation: {
            ...uploadOperation(DeviceOperationStatus.COMPLETED, true),
            id: request.operationId,
          },
          session: currentSession,
        });
      }
      return json({}, 404);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(deviceTab(false));
    await screen.findByText(/已接受 v1/);
    fireEvent.click(screen.getByRole("button", { name: "上传并运行" }));

    const retryButton = await screen.findByRole("button", {
      name: "使用同一操作 ID 重试上传请求",
    });
    fireEvent.click(retryButton);

    const result = await screen.findByRole("region", { name: "最近设备操作" });
    expect(result).toHaveTextContent("部署并启动完成");
    expect(uploadBodies).toHaveLength(2);
    expect(uploadBodies[1]?.operationId).toBe(uploadBodies[0]?.operationId);
    expect(uploadBodies[0]).toMatchObject({
      channel: "USB_SERIAL",
      codeRunId: "code_1",
      sessionId: currentSession.id,
      dryRun: false,
      confirmWrite: true,
    });
    expect(uploadBodies[0]).not.toHaveProperty("endpointId");
    expect(globalThis.sessionStorage).toHaveLength(0);
  });

  it.each(["code", "session"] as const)(
    "当前 %s 已变化时禁用待确认上传重试",
    async (changedIdentity) => {
      let currentCode = codeRun(CodeRunStatus.ACCEPTED);
      let currentSession = deviceSession(DeviceSessionStatus.READY);
      let uploadCount = 0;
      const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";
        if (url.endsWith("/api/projects/prj_1/code/current")) {
          return json({ codeRun: currentCode });
        }
        if (url.endsWith("/api/projects/prj_1/devices/session/current")) {
          return json({ session: currentSession });
        }
        if (url.endsWith("/api/projects/prj_1/devices/operations/latest")) {
          return json({}, 404);
        }
        if (url.includes("/api/projects/prj_1/devices/operations/")) {
          return json({}, 404);
        }
        if (url.endsWith("/api/projects/prj_1/devices/ports")) {
          return json({ ports: [devicePort()], scannedAt: "2026-07-12T00:00:00Z", count: 1 });
        }
        if (url.endsWith("/api/projects/prj_1/devices/deploy") && method === "POST") {
          uploadCount += 1;
          throw new TypeError("request did not reach service");
        }
        return json({}, 404);
      });
      vi.stubGlobal("fetch", fetchMock);

      const first = render(deviceTab(false));
      await screen.findByText(/已接受 v1/);
      fireEvent.click(screen.getByRole("button", { name: "上传并运行" }));
      await screen.findByRole("button", { name: "使用同一操作 ID 重试上传请求" });
      first.unmount();

      if (changedIdentity === "code") {
        currentCode = { ...currentCode, id: "code_2" };
      } else {
        currentSession = { ...currentSession, id: "device_session_2" };
      }
      render(deviceTab(false));

      const retryButton = await screen.findByRole("button", {
        name: "使用同一操作 ID 重试上传请求",
      });
      expect(retryButton).toBeDisabled();
      expect(screen.getByRole("alert")).toHaveTextContent("不能重试");
      fireEvent.click(retryButton);
      expect(uploadCount).toBe(1);
    },
  );

  it("轮询连续失败后停止自动读取，并可手动重新读取状态", async () => {
    vi.useFakeTimers();
    const currentSession = deviceSession(DeviceSessionStatus.READY);
    const running = uploadOperation(DeviceOperationStatus.RUNNING, null);
    const completed = uploadOperation(DeviceOperationStatus.COMPLETED, true);
    let allowStatusRead = false;
    let operationReadCount = 0;
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/projects/prj_1/code/current")) {
        return json({ codeRun: codeRun(CodeRunStatus.ACCEPTED) });
      }
      if (url.endsWith("/api/projects/prj_1/devices/session/current")) {
        return json({ session: currentSession });
      }
      if (url.endsWith("/api/projects/prj_1/devices/operations/latest")) {
        return json({ operation: running, session: currentSession });
      }
      if (url.endsWith("/api/projects/prj_1/devices/operations/upload_1")) {
        operationReadCount += 1;
        return allowStatusRead
          ? json({ operation: completed, session: currentSession })
          : json({ detail: { code: "DEVICE_STATUS_UNAVAILABLE" } }, 503);
      }
      if (url.endsWith("/api/projects/prj_1/devices/ports")) {
        return json({ ports: [devicePort()], scannedAt: "2026-07-12T00:00:00Z", count: 1 });
      }
      return json({}, 404);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(deviceTab(false));
    await act(async () => {
      for (let index = 0; index < 12; index += 1) await Promise.resolve();
    });
    expect(screen.getByRole("region", { name: "最近设备操作" })).toHaveTextContent(
      "部署进行中",
    );
    await act(async () => {
      await vi.runAllTimersAsync();
    });

    expect(operationReadCount).toBe(4);
    const retryButton = screen.getByRole("button", { name: "重新读取状态" });
    expect(retryButton).toBeInTheDocument();

    allowStatusRead = true;
    await act(async () => {
      fireEvent.click(retryButton);
      await Promise.resolve();
    });

    const result = screen.getByRole("region", { name: "最近设备操作" });
    expect(result).toHaveTextContent("部署并启动完成");
    expect(operationReadCount).toBe(5);
  });

  it("重挂载后恢复最近进行中操作并继续轮询", async () => {
    const currentSession = deviceSession(DeviceSessionStatus.READY);
    const running = uploadOperation(DeviceOperationStatus.RUNNING, null);
    const completed = uploadOperation(DeviceOperationStatus.COMPLETED, true);
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/projects/prj_1/code/current")) {
        return json({ codeRun: codeRun(CodeRunStatus.ACCEPTED) });
      }
      if (url.endsWith("/api/projects/prj_1/devices/session/current")) {
        return json({ session: currentSession });
      }
      if (url.endsWith("/api/projects/prj_1/devices/operations/latest")) {
        return json({ operation: running, session: currentSession });
      }
      if (url.endsWith("/api/projects/prj_1/devices/operations/upload_1")) {
        return json({ operation: completed, session: currentSession });
      }
      if (url.endsWith("/api/projects/prj_1/devices/ports")) {
        return json({ ports: [devicePort()], scannedAt: "2026-07-12T00:00:00Z", count: 1 });
      }
      return json({}, 404);
    });
    vi.stubGlobal("fetch", fetchMock);

    const first = render(deviceTab(false));
    await waitFor(() => {
      expect(fetchMock.mock.calls.filter(([target]) =>
        String(target).endsWith("/devices/operations/latest"),
      )).toHaveLength(1);
    });
    first.unmount();
    render(deviceTab(false));

    await waitFor(() => {
      expect(fetchMock.mock.calls.filter(([target]) =>
        String(target).endsWith("/devices/operations/latest"),
      )).toHaveLength(2);
    });
    const result = await screen.findByRole("region", { name: "最近设备操作" });
    await waitFor(() => expect(result).toHaveTextContent("部署并启动完成"), { timeout: 2000 });
    expect(fetchMock.mock.calls.some(([target]) =>
      String(target).endsWith("/devices/operations/upload_1"),
    )).toBe(true);
  });

  it("只读串口终端持续显示 MicroPython 报错与运行信息", async () => {
    const currentSession = deviceSession(DeviceSessionStatus.READY);
    mockDeviceState(uploadOperation(DeviceOperationStatus.COMPLETED, true), currentSession);

    render(deviceTab(false));

    const terminalRegion = await screen.findByRole("region", { name: "串口终端" });
    const terminalOutput = within(terminalRegion).getByRole("log", {
      name: "MicroPython 运行输出",
    });
    await waitFor(() => {
      expect(terminalOutput).toHaveTextContent("SyntaxError: invalid syntax");
      expect(terminalOutput).toHaveTextContent("NameError: name 'missing_pin' isn't defined");
      expect(terminalOutput).toHaveTextContent("loop started");
    });
    expect(terminalRegion).toHaveTextContent("读取中 · 只读");
    expect(within(terminalRegion).getByRole("button", { name: "暂停读取" })).toBeEnabled();
    expect(within(terminalRegion).getByRole("button", { name: "清空终端" })).toBeEnabled();
    expect(terminalOutput).not.toHaveTextContent(/COM\d+/);
  });

  it("自动浇花上传后只读核验运行证据并显示四项结果", async () => {
    const currentSession = deviceSession(DeviceSessionStatus.READY);
    const completed = uploadOperation(DeviceOperationStatus.COMPLETED, true);
    const terminal = {
      sessionId: currentSession.id,
      status: DeviceTerminalStatus.RUNNING,
      output: [
        "ZW_WATER event=sample moisture=720 state=WET pump=OFF",
        "ZW_WATER event=sample moisture=710 state=WET pump=OFF",
        "ZW_WATER event=sample moisture=260 state=DRY pump=ON",
        "ZW_WATER event=pump_stop pump=OFF elapsed_ms=2400",
      ].join("\n"),
      revision: 4,
      startedAt: "2026-07-12T00:01:00Z",
      updatedAt: "2026-07-12T00:01:01Z",
      errorMessage: null,
    };
    const evidence = {
      sessionId: currentSession.id,
      operationId: completed.id,
      checkedAt: "2026-07-12T00:02:00Z",
      sampleCount: 3,
      continuousMoistureOk: true,
      wetPumpOffOk: true,
      dryLimitedRunOk: true,
      noUnhandledException: true,
      ok: true,
      summary: "自动浇花运行证据完整，设备冒烟测试通过。",
      observations: [
        "已识别 3 条湿度采样记录。",
        "湿润状态水泵保持关闭。",
        "干燥状态有限启动并在 3 秒内关闭。",
        "未发现未处理异常。",
      ],
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/api/projects/prj_1/code/current")) {
        return json({ codeRun: codeRun(CodeRunStatus.ACCEPTED) });
      }
      if (url.endsWith("/api/projects/prj_1/devices/session/current")) {
        return json({ session: currentSession });
      }
      if (url.endsWith("/api/projects/prj_1/devices/operations/latest")) {
        return json({ operation: completed, session: currentSession });
      }
      if (url.endsWith("/api/projects/prj_1/devices/ports")) {
        return json({ ports: [devicePort()], scannedAt: "2026-07-12T00:00:00Z", count: 1 });
      }
      if (url.endsWith("/api/projects/prj_1/devices/watering-smoke/evaluate") && method === "POST") {
        return json({
          evidence,
          operation: { ...completed, metadata: { ...completed.metadata, runtimeEvidence: evidence } },
        });
      }
      if (url.includes("/api/projects/prj_1/devices/terminal")) {
        return json({ terminal });
      }
      return json({}, 404);
    });
    vi.stubGlobal("fetch", fetchMock);
    const wateringWorkspace = workspace();
    wateringWorkspace.project.name = "自动浇花装置";

    render(deviceTab(false, wateringWorkspace));

    const button = await screen.findByRole("button", { name: "核验运行证据" });
    await waitFor(() => expect(button).toBeEnabled());
    fireEvent.click(button);

    const result = await screen.findByRole("status", { name: "自动浇花冒烟测试结果" });
    expect(result).toHaveTextContent("设备冒烟测试通过");
    expect(result).toHaveTextContent("湿润状态水泵保持关闭");
    expect(result).toHaveTextContent("干燥状态有限启动并在 3 秒内关闭");
  });

  it("把 USB 串口与 ESP-Claw 作为同级上传方式，并对 MicroPython 代码关闭 Claw 上传", async () => {
    const currentSession = deviceSession(DeviceSessionStatus.READY);
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/projects/prj_1/code/current")) {
        return json({ codeRun: codeRun(CodeRunStatus.ACCEPTED, CodeRuntime.MICROPYTHON) });
      }
      if (url.endsWith("/api/projects/prj_1/devices/session/current")) {
        return json({ session: currentSession });
      }
      if (url.endsWith("/api/projects/prj_1/devices/operations/latest")) {
        return json({}, 404);
      }
      if (url.endsWith("/api/projects/prj_1/devices/esp-claw/endpoints")) {
        return json({
          endpoints: [
            { ...espClawEndpoint(), id: "esp_claw_endpoint_error", status: "ERROR" },
            espClawEndpoint(),
          ],
        });
      }
      if (url.endsWith("/api/projects/prj_1/devices/ports")) {
        return json({ ports: [devicePort()], scannedAt: "2026-07-30T00:00:00Z", count: 1 });
      }
      return json({}, 404);
    }));

    render(deviceTab(false));

    const channels = await screen.findByRole("radiogroup", { name: "代码上传方式" });
    const usb = within(channels).getByRole("radio", { name: "USB 串口" });
    const claw = within(channels).getByRole("radio", { name: "ESP-Claw" });
    expect(usb).toHaveAttribute("aria-checked", "true");
    expect(claw).toHaveAttribute("aria-checked", "false");

    fireEvent.click(claw);

    const target = await screen.findByRole("region", { name: "ESP-Claw 部署目标" });
    expect(within(target).getByRole("combobox", { name: "ESP-Claw endpoint" })).toHaveValue(
      "esp_claw_endpoint_1",
    );
    expect(within(target).getByRole("combobox", { name: "ESP-Claw endpoint" }))
      .not.toHaveTextContent("http://esp-claw.local");
    expect(within(target).getByRole("combobox", { name: "ESP-Claw endpoint" }))
      .not.toHaveTextContent("异常");
    expect(within(target).queryByRole("group", { name: "手动配对新的 ESP-Claw" }))
      .not.toBeInTheDocument();
    expect(within(target).queryByRole("textbox", { name: "ESP-Claw Web Console 地址" }))
      .not.toBeInTheDocument();
    expect(within(target).queryByRole("textbox", { name: "ESP-Claw MCP 完整地址" }))
      .not.toBeInTheDocument();
    expect(within(target).queryByRole("combobox", { name: "ESP-Claw 精确板型" }))
      .not.toBeInTheDocument();
    expect(within(target).queryByRole("checkbox", { name: /可信局域网/ }))
      .not.toBeInTheDocument();
    expect(within(target).queryByRole("checkbox", { name: /Admin\/开发模式/ }))
      .not.toBeInTheDocument();
    expect(within(target).queryByRole("checkbox", { name: /精确板型与实物一致/ }))
      .not.toBeInTheDocument();
    expect(screen.getAllByText(/当前已接受代码是 MicroPython/).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "上传并运行" })).toBeDisabled();
    expect(screen.queryByRole("region", { name: "串口终端" })).not.toBeInTheDocument();
  });

  it("专业模式从项目已确认硬件锁定 XIAO 精确板型，不回退到 K10 默认值", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/projects/prj_1/code/current")) {
        return json({ codeRun: codeRun(CodeRunStatus.ACCEPTED, CodeRuntime.ESP_CLAW_LUA) });
      }
      if (url.endsWith("/api/projects/prj_1/devices/session/current")) return json({}, 404);
      if (url.endsWith("/api/projects/prj_1/devices/operations/latest")) return json({}, 404);
      if (url.endsWith("/api/projects/prj_1/devices/esp-claw/endpoints")) {
        return json({ endpoints: [] });
      }
      if (url.endsWith("/api/projects/prj_1/devices/ports")) {
        return json({ ports: [], scannedAt: "2026-07-30T00:00:00Z", count: 0 });
      }
      return json({}, 404);
    }));

    render(deviceTab(true, workspaceWithBoard("hw_seeed_xiao_esp32s3_sense")));

    const serialBoard = await screen.findByRole("combobox", { name: "串口连接板型" });
    expect(serialBoard).toHaveValue("seeedstudio/xiao_esp32s3_sense");
    expect(serialBoard).toBeDisabled();

    fireEvent.click(screen.getByRole("radio", { name: "ESP-Claw" }));
    const target = await screen.findByRole("region", { name: "ESP-Claw 部署目标" });
    const clawBoard = within(target).getByRole("combobox", { name: "ESP-Claw 精确板型" });
    expect(clawBoard).toHaveValue("seeedstudio/xiao_esp32s3_sense");
    expect(clawBoard).toBeDisabled();
  });

  it("K10 项目不会自动选择或部署到历史 XIAO ESP-Claw endpoint", async () => {
    let deployRequests = 0;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/projects/prj_1/code/current")) {
        return json({ codeRun: codeRun(CodeRunStatus.ACCEPTED, CodeRuntime.ESP_CLAW_LUA) });
      }
      if (url.endsWith("/api/projects/prj_1/devices/session/current")) return json({}, 404);
      if (url.endsWith("/api/projects/prj_1/devices/operations/latest")) return json({}, 404);
      if (url.endsWith("/api/projects/prj_1/devices/esp-claw/endpoints")) {
        return json({
          endpoints: [espClawEndpoint("seeedstudio/xiao_esp32s3_sense")],
        });
      }
      if (url.endsWith("/api/projects/prj_1/devices/deploy") && init?.method === "POST") {
        deployRequests += 1;
      }
      if (url.endsWith("/api/projects/prj_1/devices/ports")) {
        return json({ ports: [], scannedAt: "2026-07-30T00:00:00Z", count: 0 });
      }
      return json({}, 404);
    }));

    render(deviceTab(false, workspaceWithBoard("hw_seed_unihiker_k10")));
    fireEvent.click(await screen.findByRole("radio", { name: "ESP-Claw" }));
    const target = await screen.findByRole("region", { name: "ESP-Claw 部署目标" });

    expect(within(target).queryByRole("combobox", { name: "ESP-Claw endpoint" }))
      .not.toBeInTheDocument();
    expect(within(target).getByRole("status")).toHaveTextContent(
      "已配对目标均不是当前项目的 DFRobot K10",
    );
    const upload = screen.getByRole("button", { name: "上传并运行" });
    expect(upload).toBeDisabled();
    fireEvent.click(upload);
    expect(deployRequests).toBe(0);
  });

  it("preferred_hardware 缺失时使用项目 DeviceLabScene 锁定板型", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/projects/prj_1/device-lab/scene")) {
        return json({ scene: { boardId: "seeedstudio/xiao_esp32s3_sense" } });
      }
      if (url.endsWith("/api/projects/prj_1/code/current")) {
        return json({ codeRun: codeRun(CodeRunStatus.ACCEPTED, CodeRuntime.ESP_CLAW_LUA) });
      }
      if (url.endsWith("/api/projects/prj_1/devices/session/current")) return json({}, 404);
      if (url.endsWith("/api/projects/prj_1/devices/operations/latest")) return json({}, 404);
      if (url.endsWith("/api/projects/prj_1/devices/esp-claw/endpoints")) {
        return json({ endpoints: [] });
      }
      if (url.endsWith("/api/projects/prj_1/devices/ports")) {
        return json({ ports: [], scannedAt: "2026-07-30T00:00:00Z", count: 0 });
      }
      return json({}, 404);
    }));

    render(deviceTab(false));
    const serialBoard = await screen.findByRole("combobox", { name: "串口连接板型" });
    await waitFor(() => {
      expect(serialBoard).toHaveValue("seeedstudio/xiao_esp32s3_sense");
      expect(serialBoard).toBeDisabled();
    });
  });

  it("只在专业模式的已配对列表展示 Web Console 与 MCP 地址", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/projects/prj_1/code/current")) {
        return json({ codeRun: codeRun(CodeRunStatus.ACCEPTED, CodeRuntime.ESP_CLAW_LUA) });
      }
      if (url.endsWith("/api/projects/prj_1/devices/session/current")) return json({}, 404);
      if (url.endsWith("/api/projects/prj_1/devices/operations/latest")) return json({}, 404);
      if (url.endsWith("/api/projects/prj_1/devices/esp-claw/endpoints")) {
        return json({ endpoints: [espClawEndpoint()] });
      }
      if (url.endsWith("/api/projects/prj_1/devices/ports")) {
        return json({ ports: [], scannedAt: "2026-07-30T00:00:00Z", count: 0 });
      }
      return json({}, 404);
    }));

    render(deviceTab(true));
    fireEvent.click(await screen.findByRole("radio", { name: "ESP-Claw" }));
    const paired = screen.getByRole("combobox", { name: "ESP-Claw endpoint" });
    expect(paired).toHaveTextContent("http://esp-claw.local");
    expect(paired).toHaveTextContent("http://esp-claw.local:8080/mcp");
  });

  it("专业模式配对 ESP-Claw 时提交可信局域网、Admin 模式与精确板型确认", async () => {
    let pairBody: Record<string, unknown> | null = null;
    const endpoint = espClawEndpoint();
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/api/projects/prj_1/code/current")) {
        return json({ codeRun: codeRun(CodeRunStatus.ACCEPTED, CodeRuntime.ESP_CLAW_LUA) });
      }
      if (url.endsWith("/api/projects/prj_1/devices/session/current")) return json({}, 404);
      if (url.endsWith("/api/projects/prj_1/devices/operations/latest")) return json({}, 404);
      if (url.endsWith("/api/projects/prj_1/devices/ports")) {
        return json({ ports: [], scannedAt: "2026-07-30T00:00:00Z", count: 0 });
      }
      if (url.endsWith("/api/projects/prj_1/devices/esp-claw/endpoints") && method === "GET") {
        return json({ endpoints: [] });
      }
      if (url.endsWith("/api/projects/prj_1/devices/esp-claw/endpoints/pair") && method === "POST") {
        pairBody = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
        return json({ endpoint });
      }
      return json({}, 404);
    }));

    render(deviceTab(true));
    fireEvent.click(await screen.findByRole("radio", { name: "ESP-Claw" }));
    const target = await screen.findByRole("region", { name: "ESP-Claw 部署目标" });
    fireEvent.change(within(target).getByRole("textbox", { name: "ESP-Claw Web Console 地址" }), {
      target: { value: "http://esp-claw.local" },
    });
    fireEvent.change(within(target).getByRole("textbox", { name: "ESP-Claw MCP 完整地址" }), {
      target: { value: "http://esp-claw.local:8080/mcp" },
    });
    fireEvent.change(within(target).getByRole("combobox", { name: "ESP-Claw 精确板型" }), {
      target: { value: "seeedstudio/xiao_esp32s3_sense" },
    });
    fireEvent.click(within(target).getByRole("checkbox", { name: /可信局域网/ }));
    fireEvent.click(within(target).getByRole("checkbox", { name: /Admin\/开发模式/ }));
    fireEvent.click(within(target).getByRole("checkbox", { name: /精确板型与实物一致/ }));
    fireEvent.click(within(target).getByRole("button", { name: "配对 ESP-Claw" }));

    await waitFor(() => expect(pairBody).toEqual({
      pairingMode: "TRUSTED_LAN_MANUAL",
      webEndpoint: "http://esp-claw.local",
      mcpEndpoint: "http://esp-claw.local:8080/mcp",
      boardId: "seeedstudio/xiao_esp32s3_sense",
      confirmTrustedLan: true,
      confirmAdminMode: true,
      confirmBoardIdentity: true,
    }));
    expect(await within(target).findByRole("combobox", { name: "ESP-Claw endpoint" })).toHaveValue(
      endpoint.id,
    );
  });

  it("只用 ESP-Claw Lua 已接受代码发送 endpoint 部署 payload，结果不显示串口专属状态", async () => {
    let deployBody: Record<string, unknown> | null = null;
    const endpoint = espClawEndpoint();
    const syntheticSession = {
      ...deviceSession(DeviceSessionStatus.READY),
      id: "esp_claw_session_1",
      portId: `esp-claw:${endpoint.id}`,
      board: "DFRobot K10",
    };
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/api/projects/prj_1/code/current")) {
        return json({ codeRun: codeRun(CodeRunStatus.ACCEPTED, CodeRuntime.ESP_CLAW_LUA) });
      }
      if (url.endsWith("/api/projects/prj_1/devices/session/current")) return json({}, 404);
      if (url.endsWith("/api/projects/prj_1/devices/operations/latest")) return json({}, 404);
      if (url.endsWith("/api/projects/prj_1/devices/ports")) {
        return json({ ports: [], scannedAt: "2026-07-30T00:00:00Z", count: 0 });
      }
      if (url.endsWith("/api/projects/prj_1/devices/esp-claw/endpoints")) {
        return json({ endpoints: [endpoint] });
      }
      if (url.endsWith("/api/projects/prj_1/devices/deploy") && method === "POST") {
        deployBody = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
        return json({
          operation: espClawUploadOperation(String(deployBody.operationId)),
          session: syntheticSession,
        });
      }
      return json({}, 404);
    }));

    render(deviceTab(false));
    fireEvent.click(await screen.findByRole("radio", { name: "ESP-Claw" }));
    const upload = screen.getByRole("button", { name: "上传并运行" });
    await waitFor(() => expect(upload).toBeEnabled());
    fireEvent.click(upload);

    await waitFor(() => expect(deployBody).toMatchObject({
      channel: "ESP_CLAW",
      codeRunId: "code_1",
      endpointId: endpoint.id,
      confirmWrite: true,
    }));
    expect(deployBody).not.toHaveProperty("sessionId");
    expect(deployBody).not.toHaveProperty("dryRun");
    const result = await screen.findByRole("region", { name: "最近设备操作" });
    expect(result).toHaveTextContent("ESP-Claw 代码部署并启动完成");
    expect(result).toHaveTextContent("目标握手");
    expect(result).toHaveTextContent("代码发布");
    expect(result).toHaveTextContent("Lua 运行");
    expect(result).not.toHaveTextContent("MicroPython REPL");
    expect(result).not.toHaveTextContent("主控重启");
    expect(result).not.toHaveTextContent("管理通道");
    expect(screen.queryByRole("region", { name: "串口终端" })).not.toBeInTheDocument();
  });

  it("Web 获得 Local Bridge 授权后不再误报本地设备功能不可用", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/projects/prj_1/code/current")) {
        return json({ codeRun: codeRun(CodeRunStatus.ACCEPTED) });
      }
      if (url.endsWith("/api/projects/prj_1/devices/session/current")) {
        return json({ detail: { code: "DEVICE_SESSION_NOT_FOUND" } }, 404);
      }
      if (url.endsWith("/api/projects/prj_1/devices/operations/latest")) {
        return json({ operation: null, session: null });
      }
      if (url.endsWith("/api/projects/prj_1/devices/ports")) {
        return json({ ports: [], scannedAt: "2026-07-26T00:00:00Z", count: 0 });
      }
      return json({}, 404);
    }));
    const adapter = createHostAdapter({
      ...platformCapabilities("web"),
      serialScan: true,
      serialConnection: true,
      deviceUpload: true,
    });

    render(
      <HostAdapterProvider adapter={adapter}>
        <DevicesTab workspace={workspace()} professionalMode={false} refreshRevision={0} />
      </HostAdapterProvider>,
    );

    const region = screen.getByRole("region", { name: "浏览器开发模式" });
    expect(region).toHaveTextContent("Local Bridge 已授权");
    expect(region).toHaveTextContent("本地操作由已配对的 Local Bridge 执行");
    expect(region).not.toHaveTextContent("本地设备功能不可用");
  });
});

function deviceTab(
  professionalMode: boolean,
  currentWorkspace: ProjectWorkspace = workspace(),
) {
  const adapter = createHostAdapter(platformCapabilities("tauri"));
  return (
    <HostAdapterProvider adapter={adapter}>
      <DevicesTab
        workspace={currentWorkspace}
        professionalMode={professionalMode}
        refreshRevision={0}
      />
    </HostAdapterProvider>
  );
}

function mockDeviceState(operation: DeviceOperation, session: DeviceSession) {
  const terminal = {
    sessionId: session.id,
    status: DeviceTerminalStatus.RUNNING,
    output: [
      "Traceback (most recent call last):",
      "  File \"main.py\", line 3",
      "SyntaxError: invalid syntax",
      "NameError: name 'missing_pin' isn't defined",
      "loop started",
    ].join("\n"),
    revision: 4,
    startedAt: "2026-07-12T00:01:00Z",
    updatedAt: "2026-07-12T00:01:01Z",
    errorMessage: null,
  };
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.endsWith("/api/projects/prj_1/code/current")) {
      return json({ codeRun: codeRun(CodeRunStatus.ACCEPTED) });
    }
    if (url.endsWith("/api/projects/prj_1/devices/session/current")) {
      return json({ session });
    }
    if (url.endsWith("/api/projects/prj_1/devices/operations/latest")) {
      return json({ operation, session });
    }
    if (url.endsWith("/api/projects/prj_1/devices/ports")) {
      return json({ ports: [devicePort()], scannedAt: "2026-07-12T00:00:00Z", count: 1 });
    }
    if (url.includes("/api/projects/prj_1/devices/terminal")) {
      return json({ terminal });
    }
    return json({}, 404);
  }));
}

function devicePort() {
  return {
    id: "device_port_1",
    label: "COM98",
    transport: "system-serial",
    portName: "COM98",
    portType: "USB_SERIAL",
    description: "USB Serial COM97",
    manufacturer: "测试制造商",
    product: "测试设备",
    vid: null,
    pid: null,
    likelyBoard: "行空板 K10",
    status: "available",
    chip: "ESP32-S3",
    serialNumber: null,
    available: true,
  };
}

function deviceSession(
  status: DeviceSession["status"],
  logs: DeviceSession["logs"] = [],
): DeviceSession {
  return {
    id: "device_session_1",
    projectId: "prj_1",
    portId: "device_port_1",
    board: "行空板 K10",
    status,
    connectedAt: "2026-07-12T00:00:00Z",
    lastSeenAt: "2026-07-12T00:00:00Z",
    logs,
  };
}

function espClawEndpoint(
  boardId: SupportedDeviceBoardIdType = "dfrobot/dfrobot_k10",
) {
  return {
    id: "esp_claw_endpoint_1",
    projectId: "prj_1",
    webEndpoint: "http://esp-claw.local",
    mcpEndpoint: "http://esp-claw.local:8080/mcp",
    boardId,
    status: "READY",
    storageBasePath: "/fatfs",
    capabilities: ["write_file", "read_file", "lua_run_script_async"],
    pairedAt: "2026-07-30T00:00:00Z",
    lastSeenAt: "2026-07-30T00:01:00Z",
  } as const;
}

function espClawUploadOperation(operationId: string): DeviceOperation {
  return {
    id: operationId,
    projectId: "prj_1",
    sessionId: "esp_claw_session_1",
    kind: DeviceOperationKind.UPLOAD_CODE,
    status: DeviceOperationStatus.COMPLETED,
    dryRun: false,
    commandLabel: "ESP-Claw 代码部署",
    log: "",
    artifactId: "artifact_device_log_claw_1",
    artifactVersionId: "artifact_device_log_claw_v1",
    createdAt: "2026-07-30T00:00:00Z",
    completedAt: "2026-07-30T00:01:00Z",
    phase: DeviceOperationPhase.COMPLETE,
    progress: 100,
    errorCode: null,
    cancelable: false,
    steps: [
      operationStep(DeviceOperationPhase.PREFLIGHT, 0, "endpoint 能力握手与项目场景板型门禁通过"),
      operationStep(DeviceOperationPhase.BACKUP, 0, "备份旧代码"),
      operationStep(DeviceOperationPhase.TRANSFER, 0, "写入版本目录"),
      operationStep(DeviceOperationPhase.VERIFY_FILES, 0, "逐文件回读 SHA-256"),
      operationStep(DeviceOperationPhase.START_RUNTIME, 0, "启动 scripts/main.lua"),
      operationStep(DeviceOperationPhase.VERIFY_RUNTIME, 0, "异步任务成功"),
    ],
    backup: {
      backupId: "backup_claw_1",
      fileCount: 1,
      paths: ["scripts/main.lua"],
      createdAt: "2026-07-30T00:00:00Z",
      restorable: true,
    },
    verification: {
      fileHashes: { "scripts/main.lua": "a".repeat(64) },
      reconnectExitCode: null,
      runtimeExitCode: 0,
      ok: true,
      summary: "ESP-Claw 文件回读与 Lua 异步任务验证通过。",
      deploymentOk: true,
      restartOk: null,
      runtimeStartedOk: true,
      managementChannelOk: null,
      warnings: [],
    },
    metadata: {
      channel: "ESP_CLAW",
      codeRunId: "code_1",
      targetId: "esp_claw_endpoint_1",
      boardId: "dfrobot/dfrobot_k10",
      versionPath: "/fatfs/zhangwen/code_1",
      entrypoint: "scripts/main.lua",
    },
  };
}

function legacyReconnectWarningOperation() {
  return {
    id: "upload_legacy_1",
    projectId: "prj_1",
    sessionId: "device_session_1",
    kind: DeviceOperationKind.UPLOAD_CODE,
    status: DeviceOperationStatus.FAILED,
    dryRun: false,
    commandLabel: "MicroPython 文件上传",
    log: "历史重连超时日志",
    artifactId: "artifact_device_log_1",
    artifactVersionId: "artifact_device_log_v1",
    createdAt: "2026-07-12T00:00:00Z",
    completedAt: "2026-07-12T00:01:00Z",
    phase: DeviceOperationPhase.RECONNECT,
    progress: 100,
    errorCode: "DEVICE_RECONNECT_TIMEOUT",
    cancelable: false,
    steps: [
      operationStep(DeviceOperationPhase.TRANSFER, 0, "写入文件"),
      operationStep(DeviceOperationPhase.VERIFY_FILES, 0, "回读文件"),
      operationStep(DeviceOperationPhase.RESTART, 0, "主控重启"),
      operationStep(DeviceOperationPhase.RECONNECT, 7, "管理通道重连超时"),
    ],
    backup: {
      backupId: "backup_1",
      fileCount: 1,
      paths: ["main.py"],
      createdAt: "2026-07-12T00:00:00Z",
      restorable: true,
    },
    verification: {
      fileHashes: { "main.py": "a".repeat(64) },
      reconnectExitCode: 7,
      runtimeExitCode: null,
      ok: true,
      summary: "文件回读一致，历史管理通道重连超时。",
    },
  };
}

function uploadOperation(
  status: DeviceOperation["status"],
  completed: boolean | null,
): DeviceOperation {
  const complete = completed === true;
  return {
    id: "upload_1",
    projectId: "prj_1",
    sessionId: "device_session_1",
    kind: DeviceOperationKind.UPLOAD_CODE,
    status,
    dryRun: false,
    commandLabel: "MicroPython 文件上传",
    log: "",
    artifactId: complete ? "artifact_device_log_1" : null,
    artifactVersionId: complete ? "artifact_device_log_v1" : null,
    createdAt: "2026-07-12T00:00:00Z",
    completedAt: complete ? "2026-07-12T00:01:00Z" : null,
    phase: complete ? DeviceOperationPhase.COMPLETE : DeviceOperationPhase.TRANSFER,
    progress: complete ? 100 : 40,
    errorCode: null,
    cancelable: !complete,
    steps: complete ? [
      operationStep(DeviceOperationPhase.TRANSFER, 0, "写入文件"),
      operationStep(DeviceOperationPhase.VERIFY_FILES, 0, "回读文件"),
      operationStep(DeviceOperationPhase.RESTART, 0, "重启主控并运行 main.py"),
    ] : [{
      ...operationStep(DeviceOperationPhase.TRANSFER, null, "正在写入文件"),
      status: DeviceOperationStatus.RUNNING,
      completedAt: null,
    }],
    backup: null,
    verification: {
      fileHashes: complete ? { "main.py": "a".repeat(64) } : {},
      reconnectExitCode: null,
      runtimeExitCode: null,
      ok: complete,
      summary: complete ? "文件回读一致，主控已通过正常启动复位运行 main.py。" : "正在部署。",
      deploymentOk: completed,
      restartOk: completed,
      managementChannelOk: null,
      warnings: [],
    },
    metadata: complete
      ? {
          launchMode: "NORMAL_BOOT_RESET",
          postResetProbe: "SKIPPED_TO_PRESERVE_MAIN",
        }
      : {},
  };
}

function softwareRuntimeUploadOperation(): DeviceOperation {
  return {
    ...uploadOperation(DeviceOperationStatus.COMPLETED, true),
    steps: [
      operationStep(DeviceOperationPhase.INTERRUPT_RUNTIME, 0, "安全停止程序"),
      operationStep(DeviceOperationPhase.TRANSFER, 0, "写入文件"),
      operationStep(DeviceOperationPhase.VERIFY_FILES, 0, "回读文件"),
      operationStep(DeviceOperationPhase.START_RUNTIME, 0, "启动 main.py"),
    ],
    verification: {
      fileHashes: { "main.py": "a".repeat(64) },
      reconnectExitCode: null,
      runtimeExitCode: null,
      ok: true,
      summary: "文件已部署，main.py 已启动。",
      deploymentOk: true,
      restartOk: null,
      runtimeInterruptedOk: true,
      runtimeStartedOk: true,
      managementChannelOk: null,
      warnings: ["本次未触发硬件 RST/EN。"],
    },
    metadata: {
      launchMode: "MICROPYTHON_SOFT_RESET",
      hardwareResetPerformed: false,
      postStartProbe: "TERMINAL_OBSERVATION_ONLY",
    },
  };
}

function operationStep(
  phase: DeviceOperationPhase,
  exitCode: number | null,
  summary: string,
) {
  return {
    phase,
    status: exitCode === null ? DeviceOperationStatus.RUNNING : DeviceOperationStatus.COMPLETED,
    exitCode,
    summary,
    startedAt: "2026-07-12T00:00:00Z",
    completedAt: exitCode === null ? null : "2026-07-12T00:00:10Z",
  };
}

function workspace(): ProjectWorkspace {
  const draft = {
    projectId: "prj_1",
    projectExpertId: "expert_smart",
    content: "",
    updatedAt: null,
  };
  return {
    project: {
      id: "prj_1",
      name: "K10 项目",
      stage: "IDEA",
      profile: { initialIdea: "测试 MicroPython 上传" },
      conversationId: "conv_1",
      activeExpertIds: ["expert_smart"],
      activeExpertId: "expert_smart",
      sharedContextId: null,
      coordinatorStateId: null,
      selectedModel: "deepseek-v4-flash",
      archivedAt: null,
      createdAt: "2026-07-11T00:00:00Z",
      updatedAt: "2026-07-11T00:00:00Z",
      lastOpenedAt: "2026-07-11T00:00:00Z",
      schemaVersion: 24,
    },
    conversation: {
      id: "conv_1",
      projectId: "prj_1",
      messages: [],
      updatedAt: "2026-07-11T00:00:00Z",
    },
    draft,
    experts: [{
      id: "expert_smart",
      projectId: "prj_1",
      expertDefinitionId: "expert_def_smart_engineer",
      expertType: "smart_engineer",
      conversationId: "conv_1",
      privateMemoryId: "memory_1",
      status: "waiting_user",
      workspaceStatus: "awaiting_user",
      currentTask: null,
      addedAt: "2026-07-11T00:00:00Z",
      removedAt: null,
    }],
  };
}

function workspaceWithBoard(componentId: string): ProjectWorkspace {
  return {
    ...workspace(),
    sharedContext: {
      id: "shared_context_1",
      projectId: "prj_1",
      revision: 1,
      goals: [],
      constraints: [],
      requirements: [],
      decisions: [],
      confirmedFacts: [{
        id: "fact_hardware_1",
        projectId: "prj_1",
        field: "preferred_hardware",
        key: "preferred_hardware",
        value: { components: [{ id: componentId }] },
        status: "confirmed",
        confirmed: true,
        updatedAt: "2026-07-30T00:00:00Z",
      }],
      activeArtifactVersions: [],
      updatedAt: "2026-07-30T00:00:00Z",
    },
  };
}

function codeRun(
  status: CodeRun["status"],
  runtime: CodeRun["runtime"] = CodeRuntime.MICROPYTHON,
): CodeRun {
  const acceptedAt = status === CodeRunStatus.ACCEPTED
    ? "2026-07-11T00:00:00Z"
    : null;
  return {
    id: "code_1",
    projectId: "prj_1",
    specRunId: null,
    version: 1,
    status,
    runtime,
    entrypoint: runtime === CodeRuntime.ESP_CLAW_LUA ? "scripts/main.lua" : "src/main.py",
    workspaceRoot: "workspace://prj_1/code/v1",
    maxRetries: 2,
    retries: 0,
    files: [],
    patch: {
      id: "patch_1",
      codeRunId: "code_1",
      projectId: "prj_1",
      baseSnapshotId: null,
      summary: "K10 MicroPython 代码",
      diff: "",
      createdAt: "2026-07-11T00:00:00Z",
    },
    testResult: {
      ok: true,
      command: "micropython-local-validation",
      output: "通过",
      createdAt: "2026-07-11T00:00:00Z",
      checks: [],
    },
    artifactId: "artifact_code_prj_1",
    artifactVersionId: "artifact_version_code_1",
    hardwareSolutionVersion: 1,
    bomVersion: 1,
    ioMapVersion: 1,
    generatedByExpertId: "expert_smart",
    staleReason: null,
    createdAt: "2026-07-11T00:00:00Z",
    updatedAt: "2026-07-11T00:00:00Z",
    acceptedAt,
    revisionSource: "USER",
    requiresValidation: false,
  };
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
