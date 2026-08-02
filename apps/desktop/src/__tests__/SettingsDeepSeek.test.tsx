import { render, screen, fireEvent, within } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { AppShell } from "../components/layout/AppShell";

vi.mock("../hooks/useHealthCheck", () => ({
  useHealthCheck: () => ({
    status: "ok" as const,
    version: "0.1.0",
    llmTestMode: "paid" as const,
    usesPaidLlm: true,
  }),
}));

const defaultConfig = {
  provider: "deepseek",
  baseUrl: "https://api.deepseek.com",
  defaultModel: "deepseek-v4-flash",
  thinkingMode: "AUTO",
  reasoningEffort: null,
  timeoutSeconds: 60,
  keySaved: false,
  maskedApiKey: null,
  updatedAt: null,
  customModels: [],
};

const models = [
  {
    id: "deepseek-v4-flash",
    label: "DeepSeek V4 Flash",
    provider: "deepseek",
    supportsThinking: true,
    supportsStreaming: true,
  },
  {
    id: "deepseek-v4-pro",
    label: "DeepSeek V4 Pro",
    provider: "deepseek",
    supportsThinking: true,
    supportsStreaming: true,
  },
  {
    id: "qwen3.7-max",
    label: "Qwen 3.7 Max",
    provider: "qwen",
    supportsThinking: true,
    supportsStreaming: true,
  },
  {
    id: "qwen-plus",
    label: "Qwen Plus",
    provider: "qwen",
    supportsThinking: true,
    supportsStreaming: true,
  },
  {
    id: "glm-5.2",
    label: "GLM-5.2",
    provider: "glm",
    supportsThinking: true,
    supportsStreaming: true,
  },
  {
    id: "glm-5.1",
    label: "GLM-5.1",
    provider: "glm",
    supportsThinking: true,
    supportsStreaming: true,
  },
  {
    id: "kimi-k3",
    label: "Kimi K3",
    provider: "kimi",
    supportsThinking: true,
    supportsStreaming: true,
  },
  {
    id: "kimi-k2.7-code",
    label: "Kimi K2.7 Code",
    provider: "kimi",
    supportsThinking: true,
    supportsStreaming: true,
    isCustom: false,
  },
  {
    id: "kimi-k2.7-code-highspeed",
    label: "Kimi K2.7 Code Highspeed",
    provider: "kimi",
    supportsThinking: true,
    supportsStreaming: true,
  },
];

function mockFetch(
  config = defaultConfig,
  options: { saveError?: { code: string; message: string } } = {},
) {
  let savedDraft = "设置草稿";
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    if (
      (url.endsWith("/api/projects") ||
        url.endsWith("/api/projects?includeArchived=true")) &&
      method === "GET"
    ) {
      return json({
        activeProjectId: "prj_settings",
        projects: [
          {
            id: "prj_settings",
            name: "设置测试项目",
            stage: "IDEA",
            activeExpertIds: ["expert_settings_smart_engineer"],
            selectedModel: "deepseek-v4-flash",
            messageCount: 0,
            draftUpdatedAt: null,
            archivedAt: null,
            updatedAt: "2026-07-08T00:00:00.000Z",
            lastOpenedAt: "2026-07-08T00:00:00.000Z",
          },
        ],
      });
    }
    if (url.endsWith("/api/projects/prj_settings") && method === "GET") {
      return json({ workspace: workspace(savedDraft) });
    }
    if (url.endsWith("/api/projects/prj_settings/experts/expert_settings_smart_engineer/activate")) {
      return json({ workspace: workspace(savedDraft) });
    }
    if (url.endsWith("/api/projects/prj_settings/draft") && method === "PUT") {
      savedDraft = JSON.parse(String(init?.body ?? "{}")).content ?? "";
      return json({ workspace: workspace(savedDraft) });
    }
    if (url.endsWith("/api/settings/llm") && (!init || init.method === undefined)) {
      return json({ config });
    }
    if (url.endsWith("/api/llm/models")) {
      return json({ models });
    }
    if (url.endsWith("/api/settings/llm") && init?.method === "PUT") {
      if (options.saveError) {
        return json({ detail: options.saveError }, 409);
      }
      const { apiKey: _apiKey, ...savedConfig } = JSON.parse(String(init.body));
      return json({
        config: {
          ...config,
          ...savedConfig,
          keySaved: true,
          maskedApiKey: "sk-****alue",
        },
      });
    }
    if (url.endsWith("/api/settings/llm/test")) {
      return json({
        ok: true,
        message: "DeepSeek 连接测试成功。",
        provider: "deepseek",
        model: "deepseek-v4-flash",
      });
    }
    if (url.endsWith("/api/settings/llm/api-key")) {
      return json({ config: { ...config, keySaved: false, maskedApiKey: null } });
    }
    return json({}, 404);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function workspace(draft: string) {
  const experts = [
    {
      id: "expert_settings_smart_engineer",
      projectId: "prj_settings",
      expertDefinitionId: "expert_def_smart_engineer",
      expertType: "smart_engineer",
      conversationId: "conv_settings_smart_engineer",
      privateMemoryId: "memory_settings_smart_engineer",
      status: "waiting_user",
      workspaceStatus: "awaiting_user",
      currentTask: "继续澄清创意",
      addedAt: "2026-07-08T00:00:00.000Z",
      removedAt: null,
    },
  ];
  return {
    project: {
      id: "prj_settings",
      name: "设置测试项目",
      stage: "IDEA",
      profile: { initialIdea: "测试设置浮窗" },
      conversationId: "conv_settings_smart_engineer",
      activeExpertIds: ["expert_settings_smart_engineer"],
      activeExpertId: "expert_settings_smart_engineer",
      sharedContextId: "shared_settings",
      coordinatorStateId: "coord_settings",
      selectedModel: "deepseek-v4-flash",
      archivedAt: null,
      createdAt: "2026-07-08T00:00:00.000Z",
      updatedAt: "2026-07-08T00:00:00.000Z",
      lastOpenedAt: "2026-07-08T00:00:00.000Z",
      schemaVersion: 22,
    },
    conversation: {
      id: "conv_settings_smart_engineer",
      projectId: "prj_settings",
      messages: [],
      updatedAt: "2026-07-08T00:00:00.000Z",
    },
    draft: {
      projectId: "prj_settings",
      projectExpertId: "expert_settings_smart_engineer",
      content: draft,
      updatedAt: draft ? "2026-07-08T00:00:00.000Z" : null,
    },
    experts,
    expertDefinitions: [
      {
        id: "expert_def_smart_engineer",
        type: "smart_engineer",
        name: "智能工程师",
        description: "硬件、软件、IoT、数据与 AI 部署",
        icon: "cpu",
        builtIn: true,
        skillIds: ["hardware-selection"],
        supportedArtifactTypes: ["hardware_solution", "micropython_project"],
      },
    ],
    expertConversations: [
      {
        id: "conv_settings_smart_engineer",
        projectId: "prj_settings",
        projectExpertId: "expert_settings_smart_engineer",
        expertType: "smart_engineer",
        expertName: "智能工程师",
        messages: [],
        draft: {
          projectId: "prj_settings",
          projectExpertId: "expert_settings_smart_engineer",
          content: draft,
          updatedAt: draft ? "2026-07-08T00:00:00.000Z" : null,
        },
        activeQuestionId: null,
        activeTurnId: null,
        updatedAt: "2026-07-08T00:00:00.000Z",
      },
    ],
    sharedContext: {
      id: "shared_settings",
      projectId: "prj_settings",
      revision: 1,
      goals: [],
      constraints: [],
      requirements: [],
      decisions: [],
      activeArtifactVersions: [],
      updatedAt: "2026-07-08T00:00:00.000Z",
    },
    coordinator: {
      id: "coord_settings",
      projectId: "prj_settings",
      currentItem: null,
      expertStatuses: experts,
      conflicts: [],
      dependencies: [],
      updatedAt: "2026-07-08T00:00:00.000Z",
    },
  };
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("DeepSeek 设置浮窗", () => {
  beforeEach(() => {
    mockFetch();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("点击右上角齿轮打开设置浮窗，关闭后主对话仍存在且草稿保留", async () => {
    render(<AppShell />);
    await screen.findAllByText("设置测试项目");
    const textarea = screen.getByPlaceholderText("描述你想做的作品…");
    fireEvent.change(textarea, { target: { value: "保留这个草稿" } });

    fireEvent.click(screen.getByLabelText("打开设置"));

    expect(await screen.findByTestId("settings-dialog")).toBeInTheDocument();
    expect(screen.getAllByTestId("center-chat")).toHaveLength(1);
    expect(screen.getByPlaceholderText("描述你想做的作品…")).toHaveValue(
      "保留这个草稿"
    );
    const professionalMode = screen.getByRole("checkbox", { name: "专业模式" });
    expect(professionalMode).not.toBeChecked();
    fireEvent.click(professionalMode);

    fireEvent.click(screen.getByLabelText("关闭设置"));
    expect(screen.queryByTestId("settings-dialog")).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText("描述你想做的作品…")).toHaveValue(
      "保留这个草稿"
    );
    expect(screen.getByLabelText("当前模型")).toBeInTheDocument();
  });

  it("模型服务统一显示为云端 LLM，不区分免费或付费模式", async () => {
    render(<AppShell />);
    await screen.findAllByText("设置测试项目");

    fireEvent.click(screen.getByLabelText("打开设置"));

    const settings = await screen.findByRole("dialog", { name: "设置" });

    expect(within(settings).getByText("云端 LLM")).toBeInTheDocument();
    expect(within(settings).getByText("待配置")).toBeInTheDocument();
    expect(within(settings).getByRole("button", { name: "测试云端连接" }))
      .toBeInTheDocument();
    expect(within(settings).queryByText(/免费测试|付费测试|Fake/)).not.toBeInTheDocument();
    expect(within(settings).queryByText("DeepSeek")).not.toBeInTheDocument();
    expect(within(settings).getByPlaceholderText("输入服务密钥")).toBeInTheDocument();
    expect(within(settings).queryByPlaceholderText(/DeepSeek|Qwen|GLM|Kimi/))
      .not.toBeInTheDocument();
    expect(within(settings).queryByLabelText("API Base URL")).not.toBeInTheDocument();
    expect(within(settings).queryByLabelText("默认模型")).not.toBeInTheDocument();
    expect(within(settings).queryByLabelText("思考模式")).not.toBeInTheDocument();

    expect(within(settings).getByRole("button", { name: "模型与界面" }))
      .toHaveAttribute("aria-current", "page");
    fireEvent.click(within(settings).getByRole("checkbox", { name: "专业模式" }));

    expect(within(settings).queryByText(/免费测试|付费测试|Fake/)).not.toBeInTheDocument();
    expect(within(settings).getByLabelText("API Base URL")).toBeInTheDocument();
    expect(within(settings).getByLabelText("默认模型")).toBeInTheDocument();
    expect(within(settings).getByLabelText("思考模式")).toBeInTheDocument();
  });

  it("Escape 关闭设置并把焦点归还打开按钮", async () => {
    render(<AppShell />);
    await screen.findAllByText("设置测试项目");

    const openSettings = screen.getByLabelText("打开设置");
    fireEvent.click(openSettings);
    expect(await screen.findByRole("dialog", { name: "设置" })).toBeInTheDocument();
    expect(screen.getByLabelText("关闭设置")).toHaveFocus();

    fireEvent.keyDown(document, { key: "Escape" });

    expect(screen.queryByRole("dialog", { name: "设置" })).not.toBeInTheDocument();
    expect(openSettings).toHaveFocus();
  });

  it("保存后只显示掩码 Key，并可切换 Flash 与 Pro", async () => {
    render(<AppShell />);
    fireEvent.click(screen.getByLabelText("打开设置"));
    fireEvent.click(screen.getByRole("checkbox", { name: "专业模式" }));

    const modelSelect = await screen.findByDisplayValue("DeepSeek V4 Flash");
    fireEvent.change(modelSelect, { target: { value: "deepseek-v4-pro" } });
    fireEvent.change(screen.getByPlaceholderText("输入 DeepSeek API Key"), {
      target: { value: "sk-test-secret-value" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存" }));

    await screen.findByText("设置已保存。");
    expect(screen.getByText("已保存：sk-****alue")).toBeInTheDocument();
    expect(screen.queryByDisplayValue("sk-test-secret-value")).not.toBeInTheDocument();
  });

  it("测试连接状态正确显示", async () => {
    render(<AppShell />);
    fireEvent.click(screen.getByLabelText("打开设置"));
    fireEvent.click(
      await screen.findByRole("button", {
        name: "测试云端连接",
      })
    );

    expect(await screen.findByText("云端 LLM 连接测试成功。")).toBeInTheDocument();
  });

  it("专业模式可选择千问、GLM 和 Kimi，并只显示对应模型", async () => {
    render(<AppShell />);
    fireEvent.click(screen.getByLabelText("打开设置"));
    fireEvent.click(screen.getByRole("checkbox", { name: "专业模式" }));

    const providerSelect = await screen.findByLabelText("服务商");
    expect(within(providerSelect).getByRole("option", { name: "千问（Qwen）" })).toBeInTheDocument();
    expect(within(providerSelect).getByRole("option", { name: "智谱 GLM" })).toBeInTheDocument();
    expect(within(providerSelect).getByRole("option", { name: "Kimi" })).toBeInTheDocument();

    fireEvent.change(providerSelect, { target: { value: "qwen" } });
    expect(screen.getByLabelText("API Base URL")).toHaveValue(
      "https://dashscope.aliyuncs.com/compatible-mode/v1",
    );
    expect(screen.getByLabelText("默认模型")).toHaveValue("qwen3.7-max");
    expect(screen.queryByRole("option", { name: "DeepSeek V4 Pro" })).not.toBeInTheDocument();

    fireEvent.change(providerSelect, { target: { value: "kimi" } });
    expect(screen.getByLabelText("API Base URL")).toHaveValue("https://api.moonshot.cn/v1");
    expect(screen.getByLabelText("默认模型")).toHaveValue("kimi-k3");
    expect(within(screen.getByLabelText("默认模型")).getByRole("option", {
      name: "Kimi K2.7 Code",
    })).toBeInTheDocument();
    expect(within(screen.getByLabelText("默认模型")).getByRole("option", {
      name: "Kimi K2.7 Code Highspeed",
    })).toBeInTheDocument();
  });

  it("专业模式可添加并保存当前服务商的自定义模型", async () => {
    const fetchMock = mockFetch();
    render(<AppShell />);
    fireEvent.click(screen.getByLabelText("打开设置"));
    fireEvent.click(screen.getByRole("checkbox", { name: "专业模式" }));
    fireEvent.change(await screen.findByLabelText("服务商"), {
      target: { value: "kimi" },
    });
    fireEvent.click(screen.getByText("高级参数"));
    fireEvent.change(screen.getByLabelText("自定义模型 ID"), {
      target: { value: "kimi-preview-custom" },
    });

    fireEvent.click(screen.getByRole("button", { name: "添加模型" }));

    expect(screen.getByLabelText("默认模型")).toHaveValue("kimi-preview-custom");
    expect(within(screen.getByLabelText("默认模型")).getByRole("option", {
      name: "kimi-preview-custom（自定义）",
    })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "保存" }));
    await screen.findByText("设置已保存。");
    const saveRequest = fetchMock.mock.calls.find((call) => (
      String(call[0]).endsWith("/api/settings/llm") && call[1]?.method === "PUT"
    ));
    const body = JSON.parse(String(saveRequest?.[1]?.body));
    expect(body.defaultModel).toBe("kimi-preview-custom");
    expect(body.customModels).toContainEqual(expect.objectContaining({
      id: "kimi-preview-custom",
      provider: "kimi",
      isCustom: true,
    }));
  });

  it("千问保存失败时显示服务端原因并保留尚未保存的 API Key", async () => {
    mockFetch(defaultConfig, {
      saveError: {
        code: "DESKTOP_CAPABILITY_MISMATCH",
        message: "桌面窗口与本地服务会话不一致，请重新启动应用。",
      },
    });
    render(<AppShell />);
    fireEvent.click(screen.getByLabelText("打开设置"));
    fireEvent.click(screen.getByRole("checkbox", { name: "专业模式" }));
    fireEvent.change(await screen.findByLabelText("服务商"), {
      target: { value: "qwen" },
    });
    const keyInput = screen.getByPlaceholderText("输入 千问（Qwen） API Key");
    fireEvent.change(keyInput, { target: { value: "sk-qwen-unsaved" } });

    fireEvent.click(screen.getByRole("button", { name: "保存" }));

    expect(
      await screen.findByText("桌面窗口与本地服务会话不一致，请重新启动应用。"),
    ).toBeInTheDocument();
    expect(keyInput).toHaveValue("sk-qwen-unsaved");
    expect(screen.queryByText("设置已保存。")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "测试云端连接" }));
    expect(
      await screen.findByText(
        "当前表单连接测试成功；请先保存设置，之后对话才会使用该配置。",
      ),
    ).toBeInTheDocument();
  });
});
