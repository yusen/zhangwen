import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DeviceLabWorkspace } from "../components/device-lab/DeviceLabWorkspace";
import * as deviceLabApi from "../services/deviceLabApi";

vi.mock("@wokwi/elements", () => ({}));
vi.mock("../services/deviceLabApi", () => ({
  applyParameterSet: vi.fn(),
  createDeviceLabRun: vi.fn(),
  fileToBase64: vi.fn(),
  getCurrentDeviceLabSession: vi.fn(),
  getDeviceLabScene: vi.fn(),
  getDeviceLabOperation: vi.fn(),
  installFirmwareApplication: vi.fn(),
  importFirmwareApplication: vi.fn(),
  listDeviceLabBoards: vi.fn(),
  listFirmwareApplications: vi.fn(),
  listParameterSets: vi.fn(),
  prepareFirmwareApplicationInstall: vi.fn(),
  readDeviceLabEvents: vi.fn(),
  saveParameterSet: vi.fn(),
  stopDeviceLabRun: vi.fn(),
  syncParameterSetToDevice: vi.fn(),
  updateDeviceLabChannel: vi.fn(),
}));

const k10 = "dfrobot/dfrobot_k10" as const;
const xiao = "seeedstudio/xiao_esp32s3_sense" as const;

describe("双板设备实验室", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    vi.mocked(deviceLabApi.listDeviceLabBoards).mockResolvedValue({
      boards: [
        {
          id: k10,
          displayName: "DFRobot K10",
          manufacturer: "DFRobot",
          chip: "esp32s3",
          flashSizeBytes: 16 * 1024 * 1024,
          psramSizeBytes: 8 * 1024 * 1024,
          legacyAliases: ["unihiker-k10"],
          peripherals: ["LCD", "RGB"],
          pinConflicts: [],
        },
        {
          id: xiao,
          displayName: "XIAO ESP32S3 Sense",
          manufacturer: "Seeed Studio",
          chip: "esp32s3",
          flashSizeBytes: 8 * 1024 * 1024,
          psramSizeBytes: 8 * 1024 * 1024,
          legacyAliases: [],
          peripherals: ["OV2640", "PDM microphone", "microSD"],
          pinConflicts: [{
            resources: ["microSD", "GPIO21 LED"],
            message: "microSD 启用时 GPIO21 LED 不可用。",
          }],
        },
      ],
      profiles: [profile(k10), profile(xiao)],
      qemu: { available: false, version: null, reason: "未安装" },
    });
    vi.mocked(deviceLabApi.listFirmwareApplications).mockResolvedValue({
      applications: [],
      curated: [
        { applicationId: "esp-claw-k10", displayName: "ESP-Claw K10", boardId: k10, sourceUrl: "https://example.test/k10", bundled: false },
        { applicationId: "esp-claw-xiao", displayName: "ESP-Claw XIAO", boardId: xiao, sourceUrl: "https://example.test/xiao", bundled: false },
      ],
    });
    vi.mocked(deviceLabApi.getDeviceLabScene).mockResolvedValue({
      scene: projectScene(),
      profile: projectProfile(),
    });
    vi.mocked(deviceLabApi.listParameterSets).mockResolvedValue({ parameterSets: [] });
    vi.mocked(deviceLabApi.getCurrentDeviceLabSession).mockRejectedValue(new Error("未连接"));
    vi.mocked(deviceLabApi.readDeviceLabEvents).mockResolvedValue([]);
    vi.mocked(deviceLabApi.createDeviceLabRun).mockResolvedValue({
      run: runningK10(),
      profile: projectProfile(),
    });
    vi.mocked(deviceLabApi.updateDeviceLabChannel).mockImplementation(async (_project, _run, channel, request) => ({
      run: {
        ...runningK10(),
        revision: 2,
        channelValues: { ...runningK10().channelValues, [channel]: request.value },
      },
      profile: projectProfile(),
    }));
  });

  it("根据已批准立项自动显示唯一主控、外设和接线，不提供手选板型", async () => {
    render(<DeviceLabWorkspace projectId="prj_lab" professionalMode={false} onBackToChat={vi.fn()} />);

    expect(await screen.findByText("方案 v3 · 4 个实物组件 · 待确认 IO")).toBeVisible();
    expect(screen.queryByRole("combobox", { name: "设备实验室板型" })).not.toBeInTheDocument();
    expect(screen.getByText("土壤湿度传感器")).toBeVisible();
    expect(screen.getByText("土壤湿度传感器（仿真输入）")).toBeVisible();
    expect(document.querySelector("wokwi-potentiometer")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "项目接线，共 1 条" })).toBeVisible();
    expect(document.querySelector('[data-confidence="PROPOSAL_DERIVED"] line')).toBeInTheDocument();
    expect(screen.queryByText(/通用 ESP32|M10|Raspberry Pi/i)).not.toBeInTheDocument();
    expect(screen.queryByText("ESP-Claw K10")).not.toBeInTheDocument();
  });

  it("数字原型只显示当前项目验收输入，并把调试收拢为单一面板", async () => {
    render(<DeviceLabWorkspace projectId="prj_lab" professionalMode={false} variant="prototype" />);

    expect(await screen.findByTestId("device-lab-circuit")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "调试" }));
    expect(screen.getByText("干燥时启动浇水")).toBeVisible();
    screen.getAllByLabelText("土壤湿度传感器（仿真输入）")
      .forEach((input) => expect(input).toBeDisabled());
    expect(screen.queryByLabelText("温度")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "执行器" }));
    expect(screen.getByText("当前方案没有可调试执行器。")).toBeVisible();
    expect(screen.queryAllByLabelText("土壤湿度传感器（仿真输入）")).toHaveLength(0);
  });

  it("功能仿真需要显式解锁执行器并可回到对话", async () => {
    const onBackToChat = vi.fn();
    render(
      <DeviceLabWorkspace
        projectId="prj_lab"
        professionalMode={false}
        solutionRevisionId="csolution_current"
        codeRunId="code_current"
        onBackToChat={onBackToChat}
      />,
    );
    await screen.findByLabelText("方案自动生成场景");

    fireEvent.click(screen.getByRole("button", { name: "启动仿真" }));
    await waitFor(() => expect(deviceLabApi.createDeviceLabRun).toHaveBeenCalledWith(
      "prj_lab",
      expect.objectContaining({
        target: "SIMULATOR",
        expectedSceneRevision: "a".repeat(64),
        expectedSolutionRevisionId: "csolution_current",
        codeRunId: "code_current",
      }),
    ));
    expect(screen.getByRole("button", { name: "应用 / 回滚到仿真" })).toBeVisible();
    const actuator = await screen.findByRole("slider", { name: /RGB 亮度/ });
    expect(actuator).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox", { name: "解锁调试" }));
    expect(actuator).toBeEnabled();
    fireEvent.change(actuator, { target: { value: "32" } });
    await waitFor(() => expect(deviceLabApi.updateDeviceLabChannel).toHaveBeenCalledWith(
      "prj_lab",
      expect.any(String),
      "rgb-brightness",
      expect.objectContaining({ value: 32, actuatorArmed: true }),
    ));

    fireEvent.click(screen.getByRole("button", { name: "返回对话" }));
    expect(onBackToChat).toHaveBeenCalledOnce();
  });

  it("模糊失败后重试同一仿真意图时复用幂等键", async () => {
    vi.mocked(deviceLabApi.createDeviceLabRun)
      .mockRejectedValueOnce(new Error("连接中断，结果未知"))
      .mockResolvedValue({
        run: runningK10(),
        profile: projectProfile(),
      });
    render(<DeviceLabWorkspace projectId="prj_lab" professionalMode={false} />);
    await screen.findByLabelText("方案自动生成场景");

    fireEvent.click(screen.getByRole("button", { name: "启动仿真" }));
    expect(await screen.findByText("连接中断，结果未知")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "启动仿真" }));

    await waitFor(() => expect(deviceLabApi.createDeviceLabRun).toHaveBeenCalledTimes(2));
    const firstKey = vi.mocked(deviceLabApi.createDeviceLabRun).mock.calls[0]?.[1].idempotencyKey;
    const retryKey = vi.mocked(deviceLabApi.createDeviceLabRun).mock.calls[1]?.[1].idempotencyKey;
    expect(firstKey).toMatch(/^device-lab-start-run:prj_lab-/);
    expect(retryKey).toBe(firstKey);
  });

  it("参数同步响应丢失后重试时复用同一个设备 operationId", async () => {
    vi.mocked(deviceLabApi.listParameterSets).mockResolvedValue({
      parameterSets: [parameterSetFixture()],
    });
    vi.mocked(deviceLabApi.getCurrentDeviceLabSession).mockResolvedValue({
      session: deviceSessionFixture(),
    });
    vi.mocked(deviceLabApi.syncParameterSetToDevice)
      .mockRejectedValueOnce(new Error("连接中断，设备结果未知"))
      .mockResolvedValue({
        operation: completedSyncOperation(),
        session: deviceSessionFixture(),
      });

    render(<DeviceLabWorkspace projectId="prj_lab" professionalMode={false} />);
    await screen.findByLabelText("方案自动生成场景");
    fireEvent.change(screen.getByLabelText("参数版本"), {
      target: { value: "parameter-set-1" },
    });
    fireEvent.click(screen.getByRole("checkbox", {
      name: /确认把所选版本同步到已连接设备/,
    }));

    const syncButton = screen.getByRole("button", { name: "同步 / 回滚到真机" });
    fireEvent.click(syncButton);
    expect(await screen.findByText("连接中断，设备结果未知")).toBeVisible();
    fireEvent.click(syncButton);

    await waitFor(() =>
      expect(deviceLabApi.syncParameterSetToDevice).toHaveBeenCalledTimes(2),
    );
    const firstId = vi.mocked(deviceLabApi.syncParameterSetToDevice)
      .mock.calls[0]?.[2].operationId;
    const retryId = vi.mocked(deviceLabApi.syncParameterSetToDevice)
      .mock.calls[1]?.[2].operationId;
    expect(firstId).toMatch(/^device-lab-sync-parameters:prj_lab-/);
    expect(retryId).toBe(firstId);
  });

  it("重新准备安装产生新令牌后仍复用同一设备 operationId", async () => {
    vi.mocked(deviceLabApi.listFirmwareApplications).mockResolvedValue({
      applications: [firmwareApplicationFixture()],
      curated: [],
    });
    vi.mocked(deviceLabApi.getCurrentDeviceLabSession).mockResolvedValue({
      session: deviceSessionFixture(),
    });
    vi.mocked(deviceLabApi.prepareFirmwareApplicationInstall)
      .mockResolvedValueOnce({ plan: installPlanFixture("token-first") })
      .mockResolvedValueOnce({ plan: installPlanFixture("token-second") });
    vi.mocked(deviceLabApi.installFirmwareApplication)
      .mockRejectedValue(new Error("连接中断，设备结果未知"));

    const firstMount = render(
      <DeviceLabWorkspace projectId="prj_lab" professionalMode />,
    );
    const firstApplication = await screen.findByText(/Test Runtime/);
    fireEvent.click(firstApplication.closest("article")!.querySelector("button")!);
    const firstConfirmation = await waitFor(() => {
      const element = document.querySelector(".device-lab-install-confirm");
      expect(element).not.toBeNull();
      return element as HTMLElement;
    });
    fireEvent.change(firstConfirmation.querySelector("input")!, {
      target: { value: "安装应用" },
    });
    fireEvent.click(firstConfirmation.querySelector("button")!);
    await waitFor(() =>
      expect(deviceLabApi.installFirmwareApplication).toHaveBeenCalledTimes(1),
    );
    firstMount.unmount();

    render(<DeviceLabWorkspace projectId="prj_lab" professionalMode />);
    const secondApplication = await screen.findByText(/Test Runtime/);
    fireEvent.click(secondApplication.closest("article")!.querySelector("button")!);
    const secondConfirmation = await waitFor(() => {
      const element = document.querySelector(".device-lab-install-confirm");
      expect(element).not.toBeNull();
      return element as HTMLElement;
    });
    fireEvent.change(secondConfirmation.querySelector("input")!, {
      target: { value: "安装应用" },
    });
    fireEvent.click(secondConfirmation.querySelector("button")!);

    await waitFor(() =>
      expect(deviceLabApi.installFirmwareApplication).toHaveBeenCalledTimes(2),
    );
    const firstRequest = vi.mocked(deviceLabApi.installFirmwareApplication)
      .mock.calls[0]![1];
    const secondRequest = vi.mocked(deviceLabApi.installFirmwareApplication)
      .mock.calls[1]![1];
    expect(firstRequest.confirmationToken).toBe("token-first");
    expect(secondRequest.confirmationToken).toBe("token-second");
    expect(secondRequest.operationId).toBe(firstRequest.operationId);
  });
});

function profile(boardId: typeof k10 | typeof xiao) {
  return {
    schemaVersion: "zhangwen.device-lab-profile/v1" as const,
    boardId,
    revision: `${boardId}-v1`,
    channels: [
      {
        id: "temperature",
        label: "温度",
        kind: "sensor-input" as const,
        valueType: "number" as const,
        control: "slider" as const,
        unit: "°C",
        minimum: -20,
        maximum: 80,
        step: 1,
        defaultValue: 25,
        writable: true,
        requiresArm: false,
        safeValue: null,
        source: "board-profile" as const,
      },
      {
        id: "rgb-brightness",
        label: "RGB 亮度",
        kind: "actuator" as const,
        valueType: "number" as const,
        control: "slider" as const,
        unit: "%",
        minimum: 0,
        maximum: 100,
        step: 1,
        defaultValue: 0,
        writable: true,
        requiresArm: true,
        safeValue: 0,
        source: "board-profile" as const,
      },
      {
        id: "sample-rate",
        label: "采样频率",
        kind: "parameter" as const,
        valueType: "number" as const,
        control: "number" as const,
        unit: "Hz",
        minimum: 1,
        maximum: 20,
        step: 1,
        defaultValue: 5,
        writable: true,
        requiresArm: false,
        safeValue: null,
        source: "board-profile" as const,
      },
    ],
  };
}

function projectProfile() {
  const base = profile(k10);
  return {
    ...base,
    revision: `${base.revision}+scene-${"a".repeat(16)}`,
    channels: [
      ...base.channels,
      {
        id: "project.soil.input",
        label: "土壤湿度传感器（仿真输入）",
        kind: "sensor-input" as const,
        valueType: "number" as const,
        control: "slider" as const,
        unit: null,
        minimum: 0,
        maximum: 100,
        step: 1,
        defaultValue: 50,
        writable: true,
        requiresArm: false,
        safeValue: null,
        componentId: "hw_soil",
        source: "project-scene" as const,
      },
    ],
  };
}

function runningK10() {
  return {
    id: "lab-run-0001",
    projectId: "prj_lab",
    boardId: k10,
    target: "SIMULATOR" as const,
    engine: "FUNCTIONAL_MODEL" as const,
    status: "RUNNING" as const,
    applicationId: null,
    parameterSetId: null,
    actuatorArmed: false,
    channelValues: {
      temperature: 25,
      "rgb-brightness": 0,
      "sample-rate": 5,
      "project.soil.input": 50,
    },
    revision: 1,
    startedAt: "2026-07-30T00:00:00Z",
    updatedAt: "2026-07-30T00:00:00Z",
    errorMessage: null,
    scene: projectScene(),
  };
}

function parameterSetFixture() {
  return {
    id: "parameter-set-1",
    projectId: "prj_lab",
    boardId: k10,
    profileRevision: projectProfile().revision,
    revision: 1,
    label: "已验证参数",
    values: { "sample-rate": 5 },
    sourceRunId: "lab-run-0001",
    createdAt: "2026-07-30T00:00:00Z",
  };
}

function deviceSessionFixture() {
  return {
    id: "device-session-1",
    projectId: "prj_lab",
    portId: "serial-port-1",
    board: k10,
    status: "READY" as const,
    connectedAt: "2026-07-30T00:00:00Z",
    lastSeenAt: "2026-07-30T00:00:00Z",
    logs: [],
  };
}

function completedSyncOperation() {
  return {
    id: "device-lab-sync-parameters-prj_lab-fixed",
    projectId: "prj_lab",
    sessionId: "device-session-1",
    kind: "SYNC_PARAMETERS" as const,
    status: "COMPLETED" as const,
    dryRun: false,
    commandLabel: "mpremote staged parameter sync",
    log: "参数已同步",
    artifactId: null,
    artifactVersionId: null,
    createdAt: "2026-07-30T00:00:00Z",
    completedAt: "2026-07-30T00:00:01Z",
    phase: "COMPLETE" as const,
    progress: 100,
    errorCode: null,
    steps: [],
    backup: null,
    verification: null,
    cancelable: false,
    metadata: {},
  };
}

function firmwareApplicationFixture() {
  return {
    id: "application-test-runtime",
    projectId: "prj_lab",
    manifest: {
      schemaVersion: "zhangwen.firmware-application/v1" as const,
      applicationId: "test-runtime",
      displayName: "Test Runtime",
      version: "1.0.0",
      runtime: "esp-claw" as const,
      boardId: k10,
      chip: "esp32s3" as const,
      flashSizeBytes: 16 * 1024 * 1024,
      psramSizeBytes: 8 * 1024 * 1024,
      deviceImages: [{
        path: "firmware.bin",
        address: 0x10000,
        sizeBytes: 1024,
        sha256: "b".repeat(64),
        kind: "application" as const,
      }],
    },
    archiveSha256: "c".repeat(64),
    simulationCapability: "NONE" as const,
    importedAt: "2026-07-30T00:00:00Z",
  };
}

function installPlanFixture(confirmationToken: string) {
  return {
    applicationId: "application-test-runtime",
    sessionId: "device-session-1",
    boardId: k10,
    segmentCount: 1,
    totalBytes: 1024,
    confirmationToken,
    expiresAt: "2026-07-30T00:05:00Z",
    summary: "Test install",
  };
}

function projectScene() {
  return {
    schemaVersion: "zhangwen.device-lab-scene/v1" as const,
    projectId: "prj_lab",
    revision: "a".repeat(64),
    boardId: k10,
    status: "NEEDS_IO_CONFIRMATION" as const,
    source: {
      proposalId: "proposal_1",
      proposalVersion: 3,
      proposalConfirmedAt: "2026-07-30T00:00:00Z",
      hardwareFactId: "fact_1",
      hardwareFactUpdatedAt: "2026-07-30T00:00:00Z",
      specRunId: null,
      specVersion: null,
      specConfirmedAt: null,
    },
    components: [
      { id: "hw_seed_unihiker_k10", name: "DFRobot K10", category: "MCU" as const, role: "controller" as const, source: "project-hardware" as const, simulation: "FUNCTIONAL" as const, builtIn: false, protocol: "GPIO/I2C" },
      { id: "hw_soil", name: "土壤湿度传感器", category: "SENSOR" as const, role: "external" as const, source: "project-hardware" as const, simulation: "FUNCTIONAL" as const, builtIn: false, protocol: "ADC" },
      { id: "hw_seed_unihiker_k10:onboard:1", name: "LCD", category: "ONBOARD" as const, role: "onboard" as const, source: "board-profile" as const, simulation: "FUNCTIONAL" as const, builtIn: true, protocol: "BOARD_INTERNAL" },
      { id: "hw_seed_unihiker_k10:onboard:2", name: "RGB", category: "ONBOARD" as const, role: "onboard" as const, source: "board-profile" as const, simulation: "FUNCTIONAL" as const, builtIn: true, protocol: "BOARD_INTERNAL" },
    ],
    connections: [
      { id: "derived:soil", fromComponentId: "hw_seed_unihiker_k10", toComponentId: "hw_soil", protocol: "ADC", signal: "soil", pin: null, confidence: "PROPOSAL_DERIVED" as const, note: "待确认" },
    ],
    testCases: [{
      id: "scenario-dry",
      title: "干燥时启动浇水",
      inputChannelIds: ["project.soil.input"],
      expectedBehavior: "土壤变干后水泵启动。",
      source: "acceptance-scenario" as const,
    }],
    warnings: ["立项中的外接器件已生成实物场景，但未确认的 IO 脚位不会被当作真实接线。"],
    generatedAt: "2026-07-30T00:00:00Z",
  };
}
