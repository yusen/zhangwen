import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type {
  LLMConfig,
  ModelConfig,
  ProjectKickoffStatus,
  ProjectWorkspace,
} from "@zhangwen/contracts";
import { CenterChat } from "../components/layout/CenterChat";

describe("project kickoff", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("automatically streams the creation idea without appending another user message", async () => {
    const fetchMock = installStreamMock();
    const onReloadProject = vi.fn(async () => undefined);

    renderCenter(workspace("READY"), onReloadProject);

    await waitFor(() => expect(streamCalls(fetchMock)).toHaveLength(1));
    const request = requestBody(fetchMock);
    expect(request).toMatchObject({
      content: "做一个 K10 环境提醒器",
      projectExpertId: "expert_guide",
      threadId: "conv_guide",
      clientTurnId: "kickoff:prj_kickoff",
      kickoffTurnId: "turn_kickoff",
      retryKickoff: false,
    });
    expect(screen.getAllByText("做一个 K10 环境提醒器")).toHaveLength(1);
    expect(document.querySelector(".chat-message:first-child")).toHaveClass(
      "chat-message-user"
    );
    expect(await screen.findByText("创意分析完成")).toBeInTheDocument();
    await waitFor(() => expect(onReloadProject).toHaveBeenCalledWith("prj_kickoff"));
    expect(streamCalls(fetchMock)).toHaveLength(1);
  });

  it("retries a failed kickoff with the same persisted turn", async () => {
    const fetchMock = installStreamMock();
    renderCenter(workspace("FAILED"), vi.fn(async () => undefined));

    expect(streamCalls(fetchMock)).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "重试分析" }));

    await waitFor(() => expect(streamCalls(fetchMock)).toHaveLength(1));
    expect(requestBody(fetchMock)).toMatchObject({
      content: "做一个 K10 环境提醒器",
      clientTurnId: "kickoff:prj_kickoff",
      kickoffTurnId: "turn_kickoff",
      retryKickoff: true,
    });
    expect(screen.getAllByText("做一个 K10 环境提醒器")).toHaveLength(1);
    expect(await screen.findByText("创意分析完成")).toBeInTheDocument();
  });

  it("keeps retry available when the first request fails before backend claim", async () => {
    let streamAttempt = 0;
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (!String(input).includes("/chat/stream")) return json({}, 404);
      streamAttempt += 1;
      if (streamAttempt === 1) throw new Error("sidecar unavailable");
      return installStreamResponse();
    });
    vi.stubGlobal("fetch", fetchMock);
    renderCenter(workspace("READY"), vi.fn(async () => undefined));

    await waitFor(() => expect(streamCalls(fetchMock)).toHaveLength(1));
    expect(
      await screen.findAllByText("掌问本地服务未连接，请关闭应用后重新启动。")
    ).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "重试分析" }));

    await waitFor(() => expect(streamCalls(fetchMock)).toHaveLength(2));
    const retryInit = streamCalls(fetchMock)[1]?.[1] as RequestInit | undefined;
    expect(JSON.parse(String(retryInit?.body))).toMatchObject({
      kickoffTurnId: "turn_kickoff",
      retryKickoff: true,
    });
    expect(await screen.findByText("创意分析完成")).toBeInTheDocument();
  });
});

function renderCenter(
  value: ProjectWorkspace,
  onReloadProject: (projectId: string) => Promise<void>
) {
  return render(
    <CenterChat
      config={config()}
      workspace={value}
      selectedExpertId="expert_guide"
      models={models()}
      professionalMode={false}
      draftSaving={false}
      onOpenSettings={vi.fn()}
      onOpenArtifact={vi.fn()}
      onSaveDraft={vi.fn(async () => undefined)}
      onSelectExpert={vi.fn()}
      onSelectModel={vi.fn(async () => undefined)}
      onReloadProject={onReloadProject}
    />
  );
}

function installStreamMock() {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (!url.includes("/api/projects/prj_kickoff/chat/stream")) {
      return json({}, 404);
    }
    expect(init?.method).toBe("POST");
    return installStreamResponse();
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function installStreamResponse() {
  const chunks = [
    {
      requestId: "req_kickoff",
      messageId: "msg_assistant",
      requestTurnId: "turn_kickoff",
      responseTurnId: "turn_kickoff_response",
      type: "START",
      projectId: "prj_kickoff",
      conversationId: "conv_guide",
      userMessageId: "msg_user",
      model: "deepseek-v4-flash",
    },
    {
      requestId: "req_kickoff",
      messageId: "msg_assistant",
      requestTurnId: "turn_kickoff",
      responseTurnId: "turn_kickoff_response",
      type: "COMPLETED",
      projectId: "prj_kickoff",
      conversationId: "conv_guide",
      userMessageId: "msg_user",
      accumulatedContent: "创意分析完成",
      model: "deepseek-v4-flash",
    },
  ];
  return new Response(
    chunks.map((chunk) => `data: ${JSON.stringify(chunk)}\n\n`).join(""),
    { status: 200, headers: { "Content-Type": "text/event-stream" } }
  );
}

function requestBody(fetchMock: ReturnType<typeof installStreamMock>) {
  const init = streamCalls(fetchMock)[0]?.[1] as RequestInit | undefined;
  return JSON.parse(String(init?.body ?? "{}"));
}

function streamCalls(fetchMock: { mock: { calls: [unknown, RequestInit?][] } }) {
  return fetchMock.mock.calls.filter(([input]) =>
    String(input).includes("/chat/stream")
  );
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function workspace(status: ProjectKickoffStatus): ProjectWorkspace {
  const failed = status === "FAILED";
  const messages = [
    {
      id: "msg_user",
      role: "user",
      content: "做一个 K10 环境提醒器",
      metadata: {
        projectExpertId: "expert_guide",
        expertType: "problem_guide",
        conversationId: "conv_guide",
        clientTurnId: "kickoff:prj_kickoff",
        requestTurnId: "turn_kickoff",
      },
      status: "COMPLETED",
      createdAt: "2026-07-12T00:00:00Z",
      updatedAt: "2026-07-12T00:00:00Z",
    },
    {
      id: "msg_assistant",
      role: "assistant",
      content: failed ? "网络不可用" : "",
      metadata: {
        projectExpertId: "expert_guide",
        expertType: "problem_guide",
        conversationId: "conv_guide",
        clientTurnId: "kickoff:prj_kickoff",
        requestTurnId: "turn_kickoff",
        responseTurnId: "turn_kickoff_response",
      },
      status: failed ? "FAILED" : "READY",
      createdAt: "2026-07-12T00:00:00Z",
      updatedAt: "2026-07-12T00:00:00Z",
      model: "deepseek-v4-flash",
      error: failed
        ? {
            code: "NETWORK_UNAVAILABLE",
            message: "网络不可用",
            retryable: true,
            userActions: [{ id: "retry", label: "重试" }],
          }
        : undefined,
    },
  ];
  return {
    project: {
      id: "prj_kickoff",
      name: "K10 环境提醒器",
      stage: "IDEA",
      profile: { initialIdea: "做一个 K10 环境提醒器" },
      conversationId: "conv_guide",
      activeExpertIds: ["expert_guide"],
      activeExpertId: "expert_guide",
      sharedContextId: "shared_kickoff",
      coordinatorStateId: "coord_kickoff",
      selectedModel: "deepseek-v4-flash",
      archivedAt: null,
      createdAt: "2026-07-12T00:00:00Z",
      updatedAt: "2026-07-12T00:00:00Z",
      lastOpenedAt: "2026-07-12T00:00:00Z",
      schemaVersion: 24,
    },
    conversation: {
      id: "conv_guide",
      projectId: "prj_kickoff",
      messages,
      updatedAt: "2026-07-12T00:00:00Z",
    },
    draft: {
      projectId: "prj_kickoff",
      projectExpertId: null,
      content: "",
      updatedAt: null,
    },
    experts: [
      {
        id: "expert_guide",
        projectId: "prj_kickoff",
        expertDefinitionId: "expert_def_problem_guide",
        expertType: "problem_guide",
        conversationId: "conv_guide",
        privateMemoryId: "memory_guide",
        status: "working",
        workspaceStatus: "in_progress",
        currentTask: "分析项目创意",
        addedAt: "2026-07-12T00:00:00Z",
        removedAt: null,
      },
    ],
    expertDefinitions: [
      {
        id: "expert_def_problem_guide",
        type: "problem_guide",
        name: "问题引导师",
        description: "分析项目创意",
        icon: "spark",
        builtIn: true,
        skillIds: [],
        supportedArtifactTypes: [],
      },
    ],
    expertConversations: [
      {
        id: "conv_guide",
        projectId: "prj_kickoff",
        projectExpertId: "expert_guide",
        expertType: "problem_guide",
        expertName: "问题引导师",
        messages,
        draft: {
          projectId: "prj_kickoff",
          projectExpertId: "expert_guide",
          content: "",
          updatedAt: null,
        },
        activeQuestionId: null,
        activeTurnId: "turn_kickoff",
        updatedAt: "2026-07-12T00:00:00Z",
      },
    ],
    kickoff: {
      turnId: "turn_kickoff",
      responseTurnId: "turn_kickoff_response",
      clientTurnId: "kickoff:prj_kickoff",
      userMessageId: "msg_user",
      assistantMessageId: "msg_assistant",
      projectExpertId: "expert_guide",
      conversationId: "conv_guide",
      expertType: "problem_guide",
      content: "做一个 K10 环境提醒器",
      status,
      retryable: failed,
    },
  } as unknown as ProjectWorkspace;
}

function config(): LLMConfig {
  return {
    provider: "deepseek",
    baseUrl: "https://api.deepseek.com",
    defaultModel: "deepseek-v4-flash",
    thinkingMode: "AUTO",
    reasoningEffort: null,
    timeoutSeconds: 60,
    keySaved: true,
    maskedApiKey: "sk-****",
    updatedAt: null,
  };
}

function models(): ModelConfig[] {
  return [
    {
      id: "deepseek-v4-flash",
      label: "DeepSeek V4 Flash",
      provider: "deepseek",
      supportsThinking: true,
      supportsStreaming: true,
    },
  ];
}
