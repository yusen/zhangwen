import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppShell } from "../components/layout/AppShell";
import {
  createHostAdapter,
  detectHost,
  HostAdapterProvider,
  platformCapabilities,
  UnsupportedHostCapabilityError,
  clearActiveBridgeLease,
  setActiveBridgeLease,
} from "../platform";

vi.mock("../hooks/useHealthCheck", () => ({
  useHealthCheck: () => ({ status: "ok" as const, version: "0.1.0" }),
}));

afterEach(() => {
  clearActiveBridgeLease(false);
  vi.unstubAllGlobals();
});

describe("统一平台能力层", () => {
  it("无 Tauri Runtime 时识别 Web 并关闭所有本地执行能力", () => {
    const host = detectHost({} as Window);
    const capabilities = platformCapabilities(host);

    expect(capabilities).toEqual({
      host: "web",
      browserUpload: true,
      nativeFilePicker: false,
      localFileRead: false,
      localFileWrite: false,
      credentialStore: false,
      nativeWindow: false,
      shellExecution: false,
      localToolExecution: false,
      serialScan: false,
      serialConnection: false,
      deviceUpload: false,
      deviceFlash: false,
      localCadExecution: false,
      experimentalWebSerial: false,
    });
  });

  it("Tauri Host 通过同一 Adapter 暴露当前已有能力", () => {
    const host = detectHost({ __TAURI_INTERNALS__: {} } as unknown as Window);
    const capabilities = platformCapabilities(host);
    expect(capabilities.host).toBe("tauri");
    expect(capabilities.credentialStore).toBe(true);
    expect(capabilities.serialScan).toBe(true);
    expect(capabilities.localToolExecution).toBe(true);
    expect(capabilities.localCadExecution).toBe(true);
  });

  it("Web 配对短期 Bridge 后只开启项目 CAD、串口与上传，不开放 Shell、凭据或 Flash", () => {
    setActiveBridgeLease({
      token: "bridge-test-token",
      id: "bridge-test",
      projectId: "project-test",
      origin: "http://localhost:5173",
      capabilities: ["cad.local", "device.serial", "device.upload"],
      expiresAt: new Date(Date.now() + 60_000).toISOString(),
    });

    const capabilities = platformCapabilities("web");
    expect(capabilities.serialScan).toBe(true);
    expect(capabilities.serialConnection).toBe(true);
    expect(capabilities.deviceUpload).toBe(true);
    expect(capabilities.localCadExecution).toBe(true);
    expect(capabilities.deviceFlash).toBe(false);
    expect(capabilities.shellExecution).toBe(false);
    expect(capabilities.credentialStore).toBe(false);
  });

  it("实验 Web Serial 只暴露浏览器直连标识，不冒充完整本地 Runner", () => {
    vi.stubGlobal("isSecureContext", true);
    Object.defineProperty(globalThis.navigator, "serial", {
      configurable: true,
      value: {},
    });
    const capabilities = platformCapabilities("web");
    expect(capabilities.experimentalWebSerial).toBe(true);
    expect(capabilities.serialScan).toBe(false);
    expect(capabilities.deviceUpload).toBe(false);
    expect(capabilities.localCadExecution).toBe(false);
    Reflect.deleteProperty(globalThis.navigator, "serial");
  });

  it("explicit Web configuration wins over injected Tauri globals", () => {
    const host = detectHost(
      { __TAURI_INTERNALS__: {} } as unknown as Window,
      "web"
    );

    expect(host).toBe("web");
    expect(platformCapabilities(host).serialScan).toBe(false);
  });

  it("Host Adapter 对 Web 不支持能力显式失败而非静默吞掉", () => {
    const adapter = createHostAdapter(platformCapabilities("web"));
    expect(() => adapter.require("shellExecution")).toThrow(
      UnsupportedHostCapabilityError
    );
    expect(() => adapter.require("localToolExecution")).toThrow(
      "当前浏览器模式不支持受控本地工具执行"
    );
    expect(() => adapter.require("serialConnection")).toThrow(
      "当前浏览器模式不支持本地串口连接"
    );
    expect(() => adapter.require("deviceFlash")).toThrow(
      "当前浏览器模式不支持固件烧录"
    );
    expect(() => adapter.require("localCadExecution")).toThrow(
      "当前浏览器模式不支持本地 CAD 执行"
    );
  });

  it("Web Host 可渲染且设备/CAD/密钥操作受能力门禁", async () => {
    const fetchMock = mockWebFetch();
    render(
      <HostAdapterProvider adapter={createHostAdapter(platformCapabilities("web"))}>
        <AppShell />
      </HostAdapterProvider>
    );

    await screen.findAllByText("Web 测试项目");
    expect(screen.getByTestId("center-chat")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "设备" }));
    const devices = await screen.findByTestId("devices-tab");
    expect(within(devices).getByRole("region", { name: "浏览器开发模式" })).toBeInTheDocument();
    expect(within(devices).getByRole("button", { name: "扫描设备" })).toBeDisabled();
    expect(within(devices).queryByRole("button", { name: "连接" })).not.toBeInTheDocument();
    expect(within(devices).queryByRole("button", { name: "上传 Dry Run" })).not.toBeInTheDocument();
    expect(within(devices).queryByRole("button", { name: "固件 Dry Run" })).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([input]) => String(input).includes("/devices/ports"))).toBe(false);

    fireEvent.click(screen.getByLabelText("打开设置"));
    expect(screen.queryByPlaceholderText("输入 DeepSeek API Key")).not.toBeInTheDocument();
    expect(screen.getByText(/浏览器不会读取或保存模型密钥/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("checkbox", { name: "专业模式" }));
    fireEvent.click(screen.getByLabelText("关闭设置"));
    fireEvent.click(screen.getByRole("tab", { name: "工作" }));
    fireEvent.click(await screen.findByText("工程详情"));
    const hostCapabilities = screen.getByRole("region", { name: "浏览器宿主能力" });
    expect(within(hostCapabilities).getByText("本地执行受限")).toBeInTheDocument();
    expect(within(hostCapabilities).getByText(/浏览器不能执行 Shell、串口、Flash 或本地 CAD/)).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "结构件 CAD" })).not.toBeInTheDocument();
    expect(screen.getAllByTestId("center-chat")).toHaveLength(1);
  });
});

function mockWebFetch() {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.endsWith("/api/settings/llm")) {
      return json({ config: llmConfig() });
    }
    if (url.endsWith("/api/llm/models")) {
      return json({ models: [] });
    }
    if (
      url.endsWith("/api/projects") ||
      url.endsWith("/api/projects?includeArchived=true")
    ) {
      return json({ activeProjectId: "prj_web", projects: [summary()] });
    }
    if (url.endsWith("/api/projects/prj_web")) {
      return json({ workspace: workspace() });
    }
    return json({}, 404);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function llmConfig() {
  return {
    provider: "deepseek",
    baseUrl: "https://api.deepseek.com",
    defaultModel: "deepseek-v4-flash",
    thinkingMode: "AUTO",
    reasoningEffort: null,
    timeoutSeconds: 60,
    keySaved: false,
    maskedApiKey: null,
    updatedAt: null,
  };
}

function summary() {
  return {
    id: "prj_web",
    name: "Web 测试项目",
    stage: "IDEA",
    activeExpertIds: ["expert_web"],
    selectedModel: "deepseek-v4-flash",
    messageCount: 0,
    draftUpdatedAt: null,
    archivedAt: null,
    updatedAt: "2026-07-10T00:00:00Z",
    lastOpenedAt: "2026-07-10T00:00:00Z",
  };
}

function workspace() {
  const expert = {
    id: "expert_web",
    projectId: "prj_web",
    expertDefinitionId: "expert_def_problem_guide",
    expertType: "problem_guide",
    conversationId: "conv_web",
    privateMemoryId: "memory_web",
    status: "waiting_user",
    workspaceStatus: "awaiting_user",
    currentTask: null,
    addedAt: "2026-07-10T00:00:00Z",
    removedAt: null,
  };
  const draft = { projectId: "prj_web", projectExpertId: "expert_web", content: "", updatedAt: null };
  return {
    project: {
      id: "prj_web",
      name: "Web 测试项目",
      stage: "IDEA",
      profile: { initialIdea: "测试 Web Host" },
      conversationId: "conv_web",
      activeExpertIds: ["expert_web"],
      activeExpertId: "expert_web",
      sharedContextId: null,
      coordinatorStateId: null,
      selectedModel: "deepseek-v4-flash",
      archivedAt: null,
      createdAt: "2026-07-10T00:00:00Z",
      updatedAt: "2026-07-10T00:00:00Z",
      lastOpenedAt: "2026-07-10T00:00:00Z",
      schemaVersion: 22,
    },
    conversation: { id: "conv_web", projectId: "prj_web", messages: [], updatedAt: "2026-07-10T00:00:00Z" },
    draft,
    experts: [expert],
    expertDefinitions: [{ id: "expert_def_problem_guide", type: "problem_guide", name: "问题引导师", description: "需求澄清", icon: "spark", builtIn: true, skillIds: [], supportedArtifactTypes: [] }],
    expertConversations: [{ id: "conv_web", projectId: "prj_web", projectExpertId: "expert_web", expertType: "problem_guide", expertName: "问题引导师", messages: [], draft, updatedAt: "2026-07-10T00:00:00Z" }],
    sharedContext: null,
    coordinator: null,
  };
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}
