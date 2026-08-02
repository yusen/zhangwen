import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppShell } from "../components/layout/AppShell";

vi.mock("../hooks/useHealthCheck", () => ({
  useHealthCheck: () => ({ status: "ok" as const, version: "0.1.0" }),
}));

function mockAppFetch({
  keySaved,
  keepStreamOpen = false,
  pauseAfterProgress = false,
  progressEvents = [],
  terminalError = false,
  clarification = false,
  clarificationSourceConversationId = "conv_1",
  solutionCard = false,
  staleFirstChunk = false,
}: {
  keySaved: boolean;
  keepStreamOpen?: boolean;
  pauseAfterProgress?: boolean;
  progressEvents?: Array<{
    id: string;
    action: string;
    label: string;
    status: string;
    sequence: number;
    [key: string]: unknown;
  }>;
  terminalError?: boolean;
  clarification?: boolean;
  clarificationSourceConversationId?: string;
  solutionCard?: boolean;
  staleFirstChunk?: boolean;
}) {
  const encoder = new TextEncoder();
  let savedDraft = "";
  let completed = clarification;
  let assistantContent = clarification ? "我先了解一个关键需求。" : "你好";
  let assistantPayload: unknown = clarification ? clarificationPayload() : null;
  let clarificationFollowupContent: string | null = null;
  let clarificationFollowupConversationId = "conv_1";
  let streamCount = completed ? 1 : 0;

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    if (
      (url.endsWith("/api/projects") ||
        url.endsWith("/api/projects?includeArchived=true")) &&
      method === "GET"
    ) {
      return json({
        activeProjectId: "prj_1",
        projects: [
          {
            id: "prj_1",
            name: "测试项目",
            stage: "IDEA",
            activeExpertIds: ["expert_prj_1_smart_engineer"],
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
    if (url.endsWith("/api/projects/prj_1") && method === "GET") {
      return json({
        workspace: workspace({
          draft: savedDraft,
          completed,
          assistantContent,
          assistantPayload,
          assistantConversationId: clarificationSourceConversationId,
          followupAssistantContent: clarificationFollowupContent,
          followupAssistantConversationId: clarificationFollowupConversationId,
        }),
      });
    }
    if (url.endsWith("/api/projects/prj_1/experts/expert_prj_1_smart_engineer/activate")) {
      return json({
        workspace: workspace({
          draft: savedDraft,
          completed,
          assistantContent,
          assistantPayload,
          assistantConversationId: clarificationSourceConversationId,
          followupAssistantContent: clarificationFollowupContent,
          followupAssistantConversationId: clarificationFollowupConversationId,
        }),
      });
    }
    if (url.endsWith("/api/projects/prj_1/draft")) {
      savedDraft = JSON.parse(String(init?.body ?? "{}")).content ?? "";
      return json({
        workspace: workspace({
          draft: savedDraft,
          completed,
          assistantContent,
          assistantPayload,
          assistantConversationId: clarificationSourceConversationId,
          followupAssistantContent: clarificationFollowupContent,
          followupAssistantConversationId: clarificationFollowupConversationId,
        }),
      });
    }
    if (url.endsWith("/api/settings/llm") && method === "GET") {
      return json({
        config: {
          provider: "deepseek",
          baseUrl: "https://api.deepseek.com",
          defaultModel: "deepseek-v4-flash",
          thinkingMode: "AUTO",
          reasoningEffort: null,
          timeoutSeconds: 60,
          keySaved,
          maskedApiKey: keySaved ? "sk-****alue" : null,
          updatedAt: null,
        },
      });
    }
    if (url.endsWith("/api/llm/models")) {
      return json({
        models: [
          {
            id: "deepseek-v4-flash",
            label: "DeepSeek V4 Flash",
            provider: "deepseek",
            supportsThinking: true,
            supportsStreaming: true,
          },
        ],
      });
    }
    if (url.endsWith("/api/projects/prj_1/chat/stream")) {
      streamCount += 1;
      const body = JSON.parse(String(init?.body ?? "{}"));
      const requestTurnId =
        body.clientTurnId ?? body.turnContext?.turnId ?? `turn_${streamCount}`;
      const responseTurnId = `${requestTurnId}_response`;
      const responseConversationId =
        body.threadId ?? body.turnContext?.conversationId ?? "conv_1";
      const assistantMessageId =
        streamCount === 1 ? "msg_assistant" : `msg_assistant_${streamCount}`;
      const stream = new ReadableStream({
        start(controller) {
          window.setTimeout(() => {
            if (staleFirstChunk) {
              controller.enqueue(
                encoder.encode(
                  `event: chat.started\ndata: ${JSON.stringify({
                    requestId: "req_stale",
                    messageId: "msg_assistant_stale",
                    type: "START",
                    model: "deepseek-v4-flash",
                    projectId: "prj_1",
                    conversationId: "conv_stale",
                    requestTurnId: "turn_stale",
                    responseTurnId: "turn_stale_response",
                    userMessageId: "msg_user_stale",
                  })}\n\n`
                )
              );
              controller.enqueue(
                encoder.encode(
                  `event: chat.delta\ndata: ${JSON.stringify({
                    requestId: "req_stale",
                    messageId: "msg_assistant_stale",
                    type: "CONTENT_DELTA",
                    delta: "过期旧回复",
                    accumulatedContent: "过期旧回复",
                    model: "deepseek-v4-flash",
                    projectId: "prj_1",
                    conversationId: "conv_stale",
                    requestTurnId: "turn_stale",
                    responseTurnId: "turn_stale_response",
                    userMessageId: "msg_user_stale",
                  })}\n\n`
                )
              );
            }
            controller.enqueue(
              encoder.encode(
                `event: chat.started\ndata: ${JSON.stringify({
                  requestId: "req_1",
                  messageId: assistantMessageId,
                  type: "START",
                  model: "deepseek-v4-flash",
                  projectId: "prj_1",
                  conversationId: responseConversationId,
                  requestTurnId,
                  responseTurnId,
                  userMessageId: "msg_user",
                })}\n\n`
              )
            );
            progressEvents.forEach((progress) => {
              controller.enqueue(
                encoder.encode(
                  `event: chat.progress\ndata: ${JSON.stringify({
                    requestId: "req_1",
                    messageId: assistantMessageId,
                    type: "PROGRESS",
                    progress,
                    model: "deepseek-v4-flash",
                    projectId: "prj_1",
                    conversationId: responseConversationId,
                    requestTurnId,
                    responseTurnId,
                    userMessageId: "msg_user",
                  })}\n\n`
                )
              );
            });
            if (pauseAfterProgress) {
              return;
            }
            if (terminalError) {
              completed = true;
              assistantContent = "云端模型暂时不可用。";
              assistantPayload = null;
              controller.enqueue(
                encoder.encode(
                  `event: chat.error\ndata: ${JSON.stringify({
                    requestId: "req_1",
                    messageId: assistantMessageId,
                    type: "ERROR",
                    error: {
                      code: "SERVER_ERROR",
                      message: "云端模型暂时不可用。",
                      retryable: true,
                      userActions: [{ id: "retry", label: "重试" }],
                    },
                    model: "deepseek-v4-flash",
                    projectId: "prj_1",
                    conversationId: responseConversationId,
                    requestTurnId,
                    responseTurnId,
                    userMessageId: "msg_user",
                  })}\n\n`
                )
              );
              controller.close();
              return;
            }
            const deltaContent = clarification
              ? "已收到本轮需求确认。"
              : solutionCard
                ? "推荐实现方案已经生成，并已保存到产物。"
                : "你好";
            controller.enqueue(
              encoder.encode(
                `event: chat.delta\ndata: ${JSON.stringify({
                  requestId: "req_1",
                  messageId: assistantMessageId,
                  type: "CONTENT_DELTA",
                  delta: deltaContent,
                  accumulatedContent: deltaContent,
                  model: "deepseek-v4-flash",
                  projectId: "prj_1",
                  conversationId: responseConversationId,
                  requestTurnId,
                  responseTurnId,
                  userMessageId: "msg_user",
                })}\n\n`
              )
            );
            if (keepStreamOpen) {
              return;
            }
            const completedPayload = solutionCard ? solutionCardPayload() : null;
            if (clarification) {
              clarificationFollowupContent = deltaContent;
              clarificationFollowupConversationId = responseConversationId;
            } else {
              completed = true;
              assistantContent = deltaContent;
              assistantPayload = completedPayload;
            }
            controller.enqueue(
              encoder.encode(
                `event: chat.completed\ndata: ${JSON.stringify({
                  requestId: "req_1",
                  messageId: assistantMessageId,
                  type: "COMPLETED",
                  accumulatedContent: deltaContent,
                  structuredPayload: completedPayload,
                  model: "deepseek-v4-flash",
                  projectId: "prj_1",
                  conversationId: responseConversationId,
                  requestTurnId,
                  responseTurnId,
                  userMessageId: "msg_user",
                })}\n\n`
              )
            );
            controller.close();
          }, 0);
        },
      });
      return new Response(stream, {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      });
    }
    if (url.includes("/api/projects/prj_1/chat/cancel/")) {
      return json({ requestId: "req_1", canceled: true });
    }
    return json({}, 404);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function workspace({
  draft = "",
  completed = false,
  assistantContent = "你好",
  assistantPayload = null,
  assistantConversationId = "conv_1",
  followupAssistantContent = null,
  followupAssistantConversationId = "conv_1",
}: {
  draft?: string;
  completed?: boolean;
  assistantContent?: string;
  assistantPayload?: unknown;
  assistantConversationId?: string;
  followupAssistantContent?: string | null;
  followupAssistantConversationId?: string;
} = {}) {
  const structureSource = assistantConversationId !== "conv_1";
  const sourceExpertId = structureSource
    ? "expert_prj_1_structure_engineer"
    : "expert_prj_1_smart_engineer";
  const sourceExpertType = structureSource ? "structure_engineer" : "smart_engineer";
  const messages = completed
    ? [
        {
          id: "msg_user",
          role: "user",
          content: "你好",
          status: "COMPLETED",
          createdAt: "2026-07-08T00:00:00.000Z",
          updatedAt: "2026-07-08T00:00:00.000Z",
          model: "deepseek-v4-flash",
        },
        {
          id: "msg_assistant",
          role: "assistant",
          content: assistantContent,
          structuredPayload: assistantPayload,
          metadata: {
            projectExpertId: sourceExpertId,
            expertType: sourceExpertType,
            conversationId: assistantConversationId,
          },
          status: "COMPLETED",
          createdAt: "2026-07-08T00:00:00.000Z",
          updatedAt: "2026-07-08T00:00:00.000Z",
          model: "deepseek-v4-flash",
        },
        ...(followupAssistantContent
          ? [
              {
                id: "msg_assistant_followup",
                role: "assistant",
                content: followupAssistantContent,
                metadata: {
                  projectExpertId: sourceExpertId,
                  expertType: sourceExpertType,
                  conversationId: followupAssistantConversationId,
                },
                status: "COMPLETED",
                createdAt: "2026-07-08T00:00:01.000Z",
                updatedAt: "2026-07-08T00:00:01.000Z",
                model: "deepseek-v4-flash",
              },
            ]
          : []),
      ]
    : [];
  const experts = [
    {
      id: "expert_prj_1_smart_engineer",
      projectId: "prj_1",
      expertDefinitionId: "expert_def_smart_engineer",
      expertType: "smart_engineer",
      conversationId: "conv_1",
      privateMemoryId: "memory_prj_1_smart_engineer",
      status: "waiting_user",
      workspaceStatus: "awaiting_user",
      currentTask: "继续澄清创意",
      addedAt: "2026-07-08T00:00:00.000Z",
      removedAt: null,
    },
    ...(structureSource
      ? [
          {
            id: "expert_prj_1_structure_engineer",
            projectId: "prj_1",
            expertDefinitionId: "expert_def_structure_engineer",
            expertType: "structure_engineer",
            conversationId: assistantConversationId,
            privateMemoryId: "memory_prj_1_structure_engineer",
            status: "waiting_user",
            workspaceStatus: "awaiting_user",
            currentTask: "确认结构输入",
            addedAt: "2026-07-08T00:00:00.000Z",
            removedAt: null,
          },
        ]
      : []),
  ];
  return {
    project: {
      id: "prj_1",
      name: "测试项目",
      stage: "IDEA",
      profile: { initialIdea: "测试" },
      conversationId: "conv_1",
      activeExpertIds: ["expert_prj_1_smart_engineer"],
      activeExpertId: "expert_prj_1_smart_engineer",
      sharedContextId: "shared_prj_1",
      coordinatorStateId: "coord_prj_1",
      selectedModel: "deepseek-v4-flash",
      archivedAt: null,
      createdAt: "2026-07-08T00:00:00.000Z",
      updatedAt: "2026-07-08T00:00:00.000Z",
      lastOpenedAt: "2026-07-08T00:00:00.000Z",
      schemaVersion: 24,
    },
    conversation: {
      id: "conv_1",
      projectId: "prj_1",
      messages: structureSource ? [] : messages,
      updatedAt: "2026-07-08T00:00:00.000Z",
    },
    draft: {
      projectId: "prj_1",
      projectExpertId: "expert_prj_1_smart_engineer",
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
      ...(structureSource
        ? [
            {
              id: "expert_def_structure_engineer",
              type: "structure_engineer",
              name: "结构工程师",
              description: "外壳、尺寸、装配与制造",
              icon: "box",
              builtIn: true,
              skillIds: ["enclosure-design"],
              supportedArtifactTypes: ["cad_model"],
            },
          ]
        : []),
    ],
    expertConversations: [
      {
        id: "conv_1",
        projectId: "prj_1",
        projectExpertId: "expert_prj_1_smart_engineer",
        expertType: "smart_engineer",
        expertName: "智能工程师",
        messages: structureSource ? [] : messages,
        draft: {
          projectId: "prj_1",
          projectExpertId: "expert_prj_1_smart_engineer",
          content: draft,
          updatedAt: draft ? "2026-07-08T00:00:00.000Z" : null,
        },
        activeQuestionId: null,
        activeTurnId: null,
        updatedAt: "2026-07-08T00:00:00.000Z",
      },
      ...(structureSource
        ? [
            {
              id: assistantConversationId,
              projectId: "prj_1",
              projectExpertId: "expert_prj_1_structure_engineer",
              expertType: "structure_engineer",
              expertName: "结构工程师",
              messages,
              draft: {
                projectId: "prj_1",
                projectExpertId: "expert_prj_1_structure_engineer",
                content: "",
                updatedAt: null,
              },
              activeQuestionId: null,
              activeTurnId: null,
              updatedAt: "2026-07-08T00:00:00.000Z",
            },
          ]
        : []),
    ],
    sharedContext: {
      id: "shared_prj_1",
      projectId: "prj_1",
      revision: 1,
      goals: [],
      constraints: [],
      requirements: [],
      decisions: [],
      activeArtifactVersions: [],
      updatedAt: "2026-07-08T00:00:00.000Z",
    },
    coordinator: {
      id: "coord_prj_1",
      projectId: "prj_1",
      currentItem: null,
      expertStatuses: experts,
      conflicts: [],
      dependencies: [],
      updatedAt: "2026-07-08T00:00:00.000Z",
    },
  };
}

function clarificationPayload() {
  const questions = [
    {
      id: "product_form",
      text: "你希望它采用哪种形态？",
      mode: "single",
      allowCustomInput: true,
      required: true,
      options: [
        {
          id: "desktop_device",
          label: "桌面实体设备",
          value: "desktop_device",
          description: "适合松散放置器件，确认尺寸后直接生成盒体与上盖。",
        },
        { id: "recommended", label: "由掌问推荐", value: "recommended", recommended: true },
        { id: "custom", label: "其他，我来补充", value: "custom" },
      ],
    },
    {
      id: "reminder_method",
      text: "提醒方式希望以哪一种为主？",
      mode: "single",
      allowCustomInput: true,
      required: true,
      options: [
        { id: "light", label: "灯光提醒", value: "light" },
        { id: "sound", label: "声音提醒", value: "sound" },
      ],
    },
    {
      id: "data_tracking",
      text: "需要记录哪些数据或状态？",
      mode: "multiple",
      allowCustomInput: true,
      required: true,
      options: [
        { id: "event_log", label: "触发次数", value: "event_log" },
        { id: "status", label: "当前状态", value: "status" },
      ],
    },
  ];
  return {
    type: "clarification",
    summary: "我一次确认几个关键需求。",
    completeness: 20,
    question: questions[0],
    questions,
  };
}

function solutionCardPayload() {
  return {
    type: "solution_card",
    solutionId: "sol_1",
    artifactId: "artifact_solution_prj_1",
    artifactVersionId: "artifact_solution_prj_1_v1",
    version: 1,
    basedOnVersion: null,
    status: "DRAFT",
    title: "桌面饮水提醒器",
    summary: "ESP32 主控，通过 RGB LED 灯光提醒并记录每日饮水次数。",
    sections: [
      {
        id: "goal",
        title: "项目目标",
        content: "制作一个桌面饮水提醒器。",
        summary: "制作一个桌面饮水提醒器。",
      },
      {
        id: "functional_logic",
        title: "功能逻辑",
        content: "到达提醒时间后，RGB LED 闪烁 30 秒。",
        summary: "到达提醒时间后，RGB LED 闪烁 30 秒。",
      },
      {
        id: "hardware",
        title: "硬件方案",
        content: "ESP32 主控、RGB LED 模块、确认按键。",
        summary: "ESP32 主控、RGB LED 模块、确认按键。",
      },
      {
        id: "cost_difficulty_time",
        title: "成本、难度与时间",
        content: "预计成本约 79 元，难度入门，制作时间 1 天。",
        summary: "预计成本约 79 元，难度入门，制作时间 1 天。",
      },
    ],
    changeSummary: [],
    revision: null,
    actions: [
      { id: "confirm_solution", label: "确认方案", action: "confirm_solution" },
      { id: "modify_solution", label: "修改方案", action: "modify_solution" },
      { id: "open_solution_floating", label: "打开浮窗", action: "open_solution_floating" },
    ],
  };
}

async function openIdeatorChat() {
  await enableProfessionalMode();
  const strip = await screen.findByRole("group", { name: "项目智能体" });
  fireEvent.click(within(strip).getByRole("button", { name: /智能工程师/ }));
}

async function enableProfessionalMode() {
  if (screen.queryByRole("group", { name: "项目智能体" })) return;
  fireEvent.click(screen.getByRole("button", { name: "打开设置" }));
  const settings = screen.getByRole("dialog", { name: "设置" });
  const toggle = within(settings).getByRole("checkbox", { name: "专业模式" });
  if (!(toggle as HTMLInputElement).checked) fireEvent.click(toggle);
  fireEvent.click(within(settings).getByRole("button", { name: "关闭设置" }));
  await screen.findByRole("group", { name: "项目智能体" });
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("真实 LLM 主对话", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("未配置 Key 时禁止发送并提示设置", async () => {
    mockAppFetch({ keySaved: false });
    render(<AppShell />);

    await screen.findAllByText("测试项目");
    await openIdeatorChat();
    const textarea = screen.getByPlaceholderText("描述你想做的作品…");
    fireEvent.change(textarea, { target: { value: "你好" } });

    expect(await screen.findByText("请先在设置中配置 DeepSeek API Key。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "发送" })).toBeDisabled();
  });

  it("空内容流式回复显示专家头像和动态状态，首段内容出现后取消动画", async () => {
    mockAppFetch({ keySaved: true, keepStreamOpen: true });
    render(<AppShell />);

    await screen.findAllByText("测试项目");
    await openIdeatorChat();
    const textarea = screen.getByPlaceholderText("描述你想做的作品…");
    fireEvent.change(textarea, { target: { value: "你好" } });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "发送" })).not.toBeDisabled()
    );
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    const center = within(screen.getByTestId("center-chat"));
    expect(center.getByRole("img", { name: "智能工程师头像" })).toHaveTextContent("⚙");
    const generating = center.getByRole("status", {
      name: "智能工程师正在生成回复",
    });
    expect(generating).toHaveAttribute("aria-live", "polite");
    expect(generating).toHaveTextContent("智能工程师正在生成回复");
    expect(generating.querySelectorAll(".message-generation-dots i")).toHaveLength(3);

    await waitFor(() => expect(center.getAllByText("你好")).toHaveLength(2));
    expect(
      center.queryByRole("status", { name: "智能工程师正在生成回复" })
    ).not.toBeInTheDocument();
    expect(center.getByLabelText("当前模型")).toBeInTheDocument();
  });

  it("按真实进度顺序显示当前动作和已完成步骤，不暴露内部字段", async () => {
    mockAppFetch({
      keySaved: true,
      pauseAfterProgress: true,
      progressEvents: [
        {
          id: "context.read",
          action: "CONTEXT_READ",
          label: "正在读取项目上下文",
          status: "RUNNING",
          sequence: 1,
        },
        {
          id: "context.read",
          action: "CONTEXT_READ",
          label: "已读取项目上下文",
          status: "COMPLETED",
          sequence: 1,
        },
        {
          id: "tool.execute.1",
          action: "LOCAL_TOOL_EXECUTION",
          label: "正在执行本地工具",
          status: "RUNNING",
          sequence: 2,
          toolId: "internal.shell",
          command: "do-not-render --secret",
          path: "C:\\private\\project.py",
        },
      ],
    });
    render(<AppShell />);

    await screen.findAllByText("测试项目");
    await openIdeatorChat();
    const chatMessages = screen.getByTestId("chat-messages");
    let chatScrollTop = 0;
    const setChatScrollTop = vi.fn((value: number) => {
      chatScrollTop = value;
    });
    Object.defineProperty(chatMessages, "scrollHeight", {
      configurable: true,
      value: 640,
    });
    Object.defineProperty(chatMessages, "scrollTop", {
      configurable: true,
      get: () => chatScrollTop,
      set: setChatScrollTop,
    });
    fireEvent.change(screen.getByPlaceholderText("描述你想做的作品…"), {
      target: { value: "生成并校验代码" },
    });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "发送" })).not.toBeDisabled()
    );
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    const center = within(screen.getByTestId("center-chat"));
    const progress = await center.findByRole("status", {
      name: "智能工程师执行进度",
    });
    expect(progress).toHaveTextContent("已读取项目上下文");
    expect(progress).toHaveTextContent("正在执行本地工具");
    expect(progress.querySelectorAll(".message-action-progress-current")).toHaveLength(1);
    expect(progress.querySelectorAll(".message-action-progress-item")).toHaveLength(1);
    expect(progress.querySelectorAll(".message-generation-dots i")).toHaveLength(3);
    expect(center.queryByText("internal.shell")).not.toBeInTheDocument();
    expect(center.queryByText(/do-not-render/)).not.toBeInTheDocument();
    expect(center.queryByText(/private.*project\.py/)).not.toBeInTheDocument();
    await waitFor(() => expect(setChatScrollTop).toHaveBeenCalledWith(640));
  });

  it("回复完成后清除真实动作运行态", async () => {
    mockAppFetch({
      keySaved: true,
      progressEvents: [
        {
          id: "llm.request",
          action: "CLOUD_LLM_REQUEST",
          label: "正在请求云端 LLM",
          status: "RUNNING",
          sequence: 1,
        },
      ],
    });
    render(<AppShell />);

    await screen.findAllByText("测试项目");
    await openIdeatorChat();
    fireEvent.change(screen.getByPlaceholderText("描述你想做的作品…"), {
      target: { value: "完成状态测试" },
    });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "发送" })).not.toBeDisabled()
    );
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    const center = within(screen.getByTestId("center-chat"));
    await waitFor(() => expect(center.getAllByText("你好")).toHaveLength(2));
    expect(
      center.queryByRole("status", { name: "智能工程师执行进度" })
    ).not.toBeInTheDocument();
  });

  it("工具重试成功后不把早先失败显示为当前动作", async () => {
    mockAppFetch({
      keySaved: true,
      pauseAfterProgress: true,
      progressEvents: [
        {
          id: "tool.execute.1",
          action: "LOCAL_TOOL_EXECUTION",
          label: "本地工具执行受阻",
          status: "FAILED",
          sequence: 1,
        },
        {
          id: "tool.execute.2",
          action: "LOCAL_TOOL_EXECUTION",
          label: "已完成本地工具执行",
          status: "COMPLETED",
          sequence: 2,
        },
      ],
    });
    render(<AppShell />);

    await screen.findAllByText("测试项目");
    await openIdeatorChat();
    fireEvent.change(screen.getByPlaceholderText("描述你想做的作品…"), {
      target: { value: "重试工具" },
    });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "发送" })).not.toBeDisabled()
    );
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    const progress = await within(screen.getByTestId("center-chat")).findByRole(
      "status",
      { name: "智能工程师执行进度" },
    );
    expect(progress).toHaveTextContent("已完成本地工具执行");
    expect(progress).not.toHaveTextContent("本地工具执行受阻");
    expect(progress).toHaveAttribute("data-status", "completed");
    expect(progress.querySelectorAll(".message-generation-dots i")).toHaveLength(0);
  });

  it("回复失败后清除真实动作运行态并显示安全错误", async () => {
    mockAppFetch({
      keySaved: true,
      terminalError: true,
      progressEvents: [
        {
          id: "llm.request",
          action: "CLOUD_LLM_REQUEST",
          label: "正在请求云端 LLM",
          status: "RUNNING",
          sequence: 1,
        },
      ],
    });
    render(<AppShell />);

    await screen.findAllByText("测试项目");
    await openIdeatorChat();
    fireEvent.change(screen.getByPlaceholderText("描述你想做的作品…"), {
      target: { value: "失败状态测试" },
    });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "发送" })).not.toBeDisabled()
    );
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() =>
      expect(screen.getByTestId("center-chat")).toHaveTextContent(
        "云端模型暂时不可用。",
      ),
    );
    expect(
      screen.queryByRole("status", { name: "智能工程师执行进度" })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("status", { name: "智能工程师正在生成回复" })
    ).not.toBeInTheDocument();
  });

  it("生成中可以点击停止", async () => {
    const fetchMock = mockAppFetch({
      keySaved: true,
      keepStreamOpen: true,
      progressEvents: [
        {
          id: "llm.request",
          action: "CLOUD_LLM_REQUEST",
          label: "正在请求云端 LLM",
          status: "RUNNING",
          sequence: 1,
        },
      ],
    });
    render(<AppShell />);

    await screen.findAllByText("测试项目");
    await openIdeatorChat();
    const textarea = screen.getByPlaceholderText("描述你想做的作品…");
    fireEvent.change(textarea, { target: { value: "停止测试" } });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "发送" })).not.toBeDisabled()
    );
    fireEvent.click(screen.getByRole("button", { name: "发送" }));
    await screen.findByText("你好");
    expect(
      screen.getByRole("status", { name: "智能工程师执行进度" })
    ).toHaveTextContent("正在请求云端 LLM");
    fireEvent.click(screen.getByRole("button", { name: "停止" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/api/projects/prj_1/chat/cancel/"),
        expect.objectContaining({ method: "POST" })
      )
    );
    expect(
      screen.queryByRole("status", { name: "智能工程师执行进度" })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("status", { name: "智能工程师正在生成回复" })
    ).not.toBeInTheDocument();
  });

  it("把历史多问题逐个自然呈现，并按源消息会话只提交一次批量回答", async () => {
    const fetchMock = mockAppFetch({
      keySaved: true,
      clarification: true,
      clarificationSourceConversationId: "conv_source_message",
    });
    render(<AppShell />);

    await screen.findAllByText("测试项目");
    const center = within(screen.getByTestId("center-chat"));
    expect(await center.findByText("你希望它采用哪种形态？")).toBeInTheDocument();
    for (const forbidden of [
      "需求澄清",
      "需求完整度",
      "上一题",
      "下一题",
      "提交回答",
      "第 1/3 题",
    ]) {
      expect(center.queryByText(forbidden)).not.toBeInTheDocument();
    }
    expect(center.getByRole("button", { name: "按掌问建议继续" })).toBeInTheDocument();
    const input = screen.getByPlaceholderText("直接回答掌问，或继续描述你的想法…");
    fireEvent.click(center.getByRole("button", { name: "我自己说" }));
    expect(input).toHaveFocus();

    fireEvent.change(input, { target: { value: "桌面实体设备" } });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));
    expect(
      fetchMock.mock.calls.filter(([url]) =>
        String(url).endsWith("/api/projects/prj_1/chat/stream")
      )
    ).toHaveLength(0);
    expect(await center.findByText("提醒方式希望以哪一种为主？")).toBeInTheDocument();

    fireEvent.change(input, { target: { value: "灯光提醒" } });
    fireEvent.keyDown(input, { key: "Enter", code: "Enter" });
    expect(await center.findByText("需要记录哪些数据或状态？")).toBeInTheDocument();

    fireEvent.change(input, { target: { value: "触发次数和当前状态" } });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => {
      const calls = fetchMock.mock.calls.filter(([url]) =>
        String(url).endsWith("/api/projects/prj_1/chat/stream")
      );
      expect(calls).toHaveLength(1);
      const answerCall = calls[0];
      expect(answerCall).toBeDefined();
      const body = JSON.parse(String(answerCall?.[1]?.body));
      expect(body.clientTurnId).toEqual(expect.stringMatching(/^turn_/));
      expect(body).toMatchObject({
        content: expect.stringContaining("桌面实体设备"),
        projectExpertId: "expert_prj_1_structure_engineer",
        threadId: "conv_source_message",
        sourceMessageId: "msg_assistant",
        turnContext: {
          projectId: "prj_1",
          conversationId: "conv_source_message",
          replyToMessageId: "msg_assistant",
          currentIntent: "answer_question",
        },
        structuredAnswer: {
          type: "clarification_batch_answer",
          projectId: "prj_1",
          conversationId: "conv_source_message",
          sourceMessageId: "msg_assistant",
          answers: [
            { questionId: "product_form", selectedOptionIds: ["desktop_device"] },
            { questionId: "reminder_method", selectedOptionIds: ["light"] },
            { questionId: "data_tracking", selectedOptionIds: ["event_log", "status"] },
          ],
        },
      });
      expect(body.turnContext.turnId).toBe(body.clientTurnId);
      expect(body.structuredAnswer.clientTurnId).toBe(body.clientTurnId);
    });

    expect(await screen.findByText("已收到本轮需求确认。")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.queryByText("需要记录哪些数据或状态？")).not.toBeInTheDocument()
    );
    fireEvent.change(screen.getByPlaceholderText("描述你想做的作品…"), {
      target: { value: "继续完善结构" },
    });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "发送" })).not.toBeDisabled()
    );
  });

  it("取消自然澄清请求后撤销乐观提交并允许直接重试", async () => {
    const fetchMock = mockAppFetch({
      keySaved: true,
      clarification: true,
      clarificationSourceConversationId: "conv_source_message",
      keepStreamOpen: true,
    });
    render(<AppShell />);

    await screen.findAllByText("测试项目");
    const input = await screen.findByPlaceholderText(
      "直接回答掌问，或继续描述你的想法…"
    );
    for (const answer of [
      "桌面实体设备",
      "灯光提醒",
      "触发次数和当前状态",
    ]) {
      fireEvent.change(input, { target: { value: answer } });
      fireEvent.click(screen.getByRole("button", { name: "发送" }));
    }

    const stop = await screen.findByRole("button", { name: "停止" });
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.filter(([url]) =>
          String(url).endsWith("/api/projects/prj_1/chat/stream")
        )
      ).toHaveLength(1)
    );
    fireEvent.click(stop);

    const resumedInput = await screen.findByPlaceholderText("描述你想做的作品…");
    fireEvent.change(resumedInput, { target: { value: "继续按刚才的要求生成" } });
    expect(screen.getByRole("button", { name: "发送" })).not.toBeDisabled();
  });

  it("忽略旧 conversation 或旧 turn 的流式片段", async () => {
    mockAppFetch({ keySaved: true, staleFirstChunk: true });
    render(<AppShell />);

    await screen.findAllByText("测试项目");
    await openIdeatorChat();
    fireEvent.change(screen.getByPlaceholderText("描述你想做的作品…"), {
      target: { value: "检查过期响应" },
    });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("你好")).toBeInTheDocument();
    expect(screen.queryByText("过期旧回复")).not.toBeInTheDocument();
  });

  it("生成中切换专家只影响下一条消息，当前流仍写入原会话", async () => {
    const fetchMock = mockAppFetch({
      keySaved: true,
      clarificationSourceConversationId: "conv_structure",
    });
    const fallback = fetchMock.getMockImplementation();
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/projects/prj_1/chat/stream")) {
        const body = JSON.parse(String(init?.body ?? "{}"));
        const requestTurnId = body.clientTurnId;
        const base = {
          requestId: "req_1",
          messageId: "msg_bound_stream",
          model: "deepseek-v4-flash",
          projectId: "prj_1",
          conversationId: "conv_1",
          requestTurnId,
          responseTurnId: `${requestTurnId}_response`,
          userMessageId: "msg_bound_user",
        };
        const stream = new ReadableStream<Uint8Array>({
          start(controller) {
            window.setTimeout(() => {
              controller.enqueue(new TextEncoder().encode(
                `event: chat.started\ndata: ${JSON.stringify({ ...base, type: "START" })}\n\n`,
              ));
            }, 0);
            window.setTimeout(() => {
              controller.enqueue(new TextEncoder().encode(
                `event: chat.delta\ndata: ${JSON.stringify({
                  ...base,
                  type: "CONTENT_DELTA",
                  delta: "当前回复仍归属智能工程师",
                  accumulatedContent: "当前回复仍归属智能工程师",
                })}\n\n`,
              ));
            }, 40);
          },
        });
        return new Response(stream, {
          status: 200,
          headers: { "Content-Type": "text/event-stream" },
        });
      }
      if (!fallback) throw new Error(`未处理的测试请求：${url}`);
      return fallback(input, init);
    });

    render(<AppShell />);
    await screen.findAllByText("测试项目");
    await openIdeatorChat();
    fireEvent.change(screen.getByPlaceholderText("描述你想做的作品…"), {
      target: { value: "继续当前实现" },
    });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));
    const expertStrip = screen.getByRole("group", { name: "项目智能体" });
    fireEvent.click(within(expertStrip).getByRole("button", { name: /结构工程师/ }));

    expect(await screen.findByText("当前回复仍归属智能工程师")).toBeInTheDocument();
    expect(
      within(expertStrip).getByRole("button", { name: /结构工程师/ }),
    ).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: "停止" }));
  });

  it("方案生成后在中央显示紧凑方案卡并通过浮窗入口查看", async () => {
    mockAppFetch({ keySaved: true, solutionCard: true });
    render(<AppShell />);

    await screen.findAllByText("测试项目");
    await openIdeatorChat();
    fireEvent.change(screen.getByPlaceholderText("描述你想做的作品…"), {
      target: { value: "生成推荐实现方案" },
    });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByTestId("solution-card")).toBeInTheDocument();
    expect(screen.getByText("桌面饮水提醒器")).toBeInTheDocument();
    expect(screen.getByText(/方案 v1 · 待确认/)).toBeInTheDocument();
    expect(screen.queryByText("```")).not.toBeInTheDocument();

    expect(screen.queryByTestId("solution-card-sections")).not.toBeInTheDocument();
    expect(screen.queryByText("硬件方案")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "打开浮窗" })).toBeInTheDocument();
  });
});
