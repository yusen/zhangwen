import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { act, within } from "@testing-library/react";
import { AppShell } from "../components/layout/AppShell";
import {
  createHostAdapter,
  HostAdapterProvider,
  platformCapabilities,
} from "../platform";

vi.mock("../hooks/useHealthCheck", () => ({
  useHealthCheck: () => ({ status: "ok" as const, version: "0.1.0" }),
}));

describe("项目主会话隔离", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("新建项目后中央进入初始专家线程，切回旧项目恢复旧消息", async () => {
    mockProjectIsolationFetch();
    render(<AppShell />);

    await screen.findAllByText("项目A");
    await openProblemGuideChat();
    expect(await screen.findByText("项目A历史消息")).toBeInTheDocument();
    const center = screen.getByTestId("center-chat");

    fireEvent.click(
      within(screen.getByTestId("left-sidebar")).getByRole("button", { name: "新建项目" }),
    );
    fireEvent.change(screen.getByLabelText("新项目创意"), {
      target: { value: "一个新创意" },
    });
    fireEvent.click(screen.getByRole("button", { name: "分析并推荐" }));
    const projectNameInput = await screen.findByLabelText("项目名称");
    await waitFor(() =>
      expect(projectNameInput).toHaveValue("一个新创意项目")
    );
    fireEvent.click(screen.getByRole("button", { name: "开始项目" }));

    await screen.findAllByText("项目B");
    await screen.findByTestId("chat-input");
    expect(screen.queryByTestId("project-center-overview")).not.toBeInTheDocument();
    const strip = screen.getByRole("group", { name: "项目智能体" });
    expect(within(strip).getByRole("button", { name: /问题引导师/ })).toBeInTheDocument();
    expect(screen.getByTestId("center-chat")).toBe(center);
    expect(screen.queryByText("项目A历史消息")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("切换项目"), {
      target: { value: "prj_a" },
    });

    await screen.findAllByText("项目A");
    await openProblemGuideChat();
    await waitFor(() => expect(screen.getByText("项目A历史消息")).toBeInTheDocument());
    expect(screen.getByTestId("center-chat")).toBe(center);
  }, 15_000);

  it("项目唯一时间线通过 @智能体 路由到独立云端会话", async () => {
    const fetchMock = mockProjectIsolationFetch();
    render(<AppShell />);

    await screen.findAllByText("项目A");
    await openProblemGuideChat();
    expect(await screen.findByText("项目A历史消息")).toBeInTheDocument();

    const problemInput = screen.getByPlaceholderText("描述你想做的作品…");
    fireEvent.change(problemInput, { target: { value: "@智能工程师 智能工程师任务" } });
    const strip = screen.getByRole("group", { name: "项目智能体" });
    expect(within(strip).getByRole("button", { name: /问题引导师/ })).toBeInTheDocument();
    expect(within(strip).getByRole("button", { name: /智能工程师/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([input, init]) => {
          const url = String(input);
          if (!url.endsWith("/api/projects/prj_a/chat/stream")) return false;
          const body = JSON.parse(String(init?.body ?? "{}"));
          return (
            body.content === "智能工程师任务" &&
            body.projectExpertId === "expert_prj_a_smart_engineer" &&
            body.threadId === "conv_prj_a_smart_engineer" &&
            body.expertType === "smart_engineer" &&
            body.turnContext?.threadId === "conv_prj_a_smart_engineer"
          );
        })
      ).toBe(true)
    );

    expect(screen.getByText("项目A历史消息")).toBeInTheDocument();
    expect(within(strip).getByRole("button", { name: /智能工程师/ })).toHaveAttribute("aria-pressed", "true");
  });

  it("项目创建后可以从中央输入区按需加入其余工程师", async () => {
    const fetchMock = mockProjectIsolationFetch();
    render(<AppShell />);

    await screen.findAllByText("项目A");
    await enableProfessionalMode();
    const center = screen.getByTestId("center-chat");
    const strip = await screen.findByRole("group", { name: "项目智能体" });
    expect(within(strip).queryByRole("button", { name: /结构工程师/ })).not.toBeInTheDocument();

    fireEvent.click(within(strip).getByRole("button", { name: /添加工程师/ }));
    const panel = screen.getByRole("region", { name: "添加项目工程师" });
    expect(within(panel).getByText(/只共享项目事实、产物和公共知识/)).toBeInTheDocument();
    fireEvent.click(within(panel).getByRole("button", { name: "添加结构工程师" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([input, init]) => {
          if (!String(input).endsWith("/api/projects/prj_a/experts")) return false;
          const body = JSON.parse(String(init?.body ?? "{}"));
          return body.expertType === "structure_engineer" && body.activate === true;
        }),
      ).toBe(true),
    );
    const refreshedStrip = await screen.findByRole("group", { name: "项目智能体" });
    expect(
      within(refreshedStrip).getByRole("button", { name: /结构工程师/ }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(within(refreshedStrip).queryByRole("button", { name: /添加工程师/ })).not.toBeInTheDocument();
    expect(screen.getByTestId("center-chat")).toBe(center);
  });

  it("Web Host 刷新后从 FastAPI 工作区恢复项目、线程、消息和草稿", async () => {
    mockProjectIsolationFetch();
    const first = render(
      <HostAdapterProvider adapter={createHostAdapter(platformCapabilities("web"))}>
        <AppShell />
      </HostAdapterProvider>
    );

    await screen.findAllByText("项目A");
    await openProblemGuideChat();
    expect(await screen.findByText("项目A历史消息")).toBeInTheDocument();
    const input = screen.getByPlaceholderText("描述你想做的作品…");
    fireEvent.change(input, { target: { value: "刷新后恢复的 Web 草稿" } });
    await waitFor(() => expect(input).toHaveValue("刷新后恢复的 Web 草稿"));
    await act(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 450));
    });

    first.unmount();
    render(
      <HostAdapterProvider adapter={createHostAdapter(platformCapabilities("web"))}>
        <AppShell />
      </HostAdapterProvider>
    );

    await screen.findAllByText("项目A");
    await openProblemGuideChat();
    expect(await screen.findByText("项目A历史消息")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("描述你想做的作品…")).toHaveValue(
      "刷新后恢复的 Web 草稿"
    );
  });
});

async function openProblemGuideChat() {
  await enableProfessionalMode();
  const strip = await screen.findByRole("group", { name: "项目智能体" });
  fireEvent.click(within(strip).getByRole("button", { name: /问题引导师/ }));
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

function mockProjectIsolationFetch() {
  let activeProjectId = "prj_a";
  const projects = [summary("prj_a", "项目A")];
  const activeExpertTypes: Record<string, string> = {
    prj_a: "problem_guide",
    prj_b: "problem_guide",
  };
  const projectExpertTypes: Record<string, string[]> = {
    prj_a: ["problem_guide", "smart_engineer"],
    prj_b: ["problem_guide"],
  };
  const drafts: Record<string, string> = {
    "prj_a:problem_guide": "A草稿",
    "prj_b:problem_guide": "",
  };

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";

      if (url.endsWith("/api/settings/llm") && method === "GET") {
        return json({
          config: {
            provider: "deepseek",
            baseUrl: "https://api.deepseek.com",
            defaultModel: "deepseek-v4-flash",
            thinkingMode: "AUTO",
            reasoningEffort: null,
            timeoutSeconds: 60,
            keySaved: true,
            maskedApiKey: "sk-****alue",
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
      if (
        (url.endsWith("/api/projects") ||
          url.endsWith("/api/projects?includeArchived=true")) &&
        method === "GET"
      ) {
        return json({ activeProjectId, projects });
      }
      if (url.endsWith("/api/projects/suggest") && method === "POST") {
        const body = JSON.parse(String(init?.body ?? "{}"));
        const idea = String(body.text ?? body.initialIdea ?? "");
        return json({
          suggestion: {
            name: "一个新创意项目",
            initialIdea: idea,
            recommendedExpertTypes: ["problem_guide"],
            availableExperts: expertDefinitions(),
            initialExpert: "problem_guide",
            routerResult: {
              intent: "clarify_project_idea",
              projectName: "一个新创意项目",
              initialExpert: "problem_guide",
              recommendedExperts: ["problem_guide"],
              confidence: 0.4,
              reason: "当前想法还比较宽泛，建议先由问题引导师帮助你进一步梳理。",
              requiresClarification: true,
            },
            reason: "当前想法还比较宽泛，建议先由问题引导师帮助你进一步梳理。",
            confidence: 0.4,
            requiresClarification: true,
          },
        });
      }
      if (url.endsWith("/api/projects") && method === "POST") {
        activeProjectId = "prj_b";
        activeExpertTypes.prj_b = "problem_guide";
        projectExpertTypes.prj_b = ["problem_guide"];
        projects.unshift(summary("prj_b", "项目B"));
        return json({ workspace: workspace("prj_b", "项目B", drafts["prj_b:problem_guide"] ?? "", activeExpertTypes, projectExpertTypes) });
      }

      const projectId = projectIdFromUrl(url);
      if (projectId && url.endsWith("/experts") && method === "POST") {
        const body = JSON.parse(String(init?.body ?? "{}"));
        const expertType = String(body.expertType ?? "problem_guide");
        projectExpertTypes[projectId] = projectExpertTypes[projectId] ?? ["problem_guide"];
        if (!projectExpertTypes[projectId].includes(expertType)) {
          projectExpertTypes[projectId].push(expertType);
        }
        if (body.activate) {
          activeExpertTypes[projectId] = expertType;
        }
        return json({
          workspace: workspace(
            projectId,
            projectName(projectId),
            drafts[`${projectId}:${activeExpertTypes[projectId]}`] ?? "",
            activeExpertTypes,
            projectExpertTypes
          ),
        });
      }
      const activateMatch = url.match(/\/api\/projects\/([^/]+)\/experts\/([^/]+)\/activate$/);
      if (activateMatch && method === "POST") {
        const activateProjectId = activateMatch[1];
        const activateExpertId = activateMatch[2];
        if (!activateProjectId || !activateExpertId) {
          return json({}, 404);
        }
        activeExpertTypes[activateProjectId] = expertTypeFromExpertId(activateExpertId);
        return json({
          workspace: workspace(
            activateProjectId,
            projectName(activateProjectId),
            drafts[`${activateProjectId}:${activeExpertTypes[activateProjectId]}`] ?? "",
            activeExpertTypes,
            projectExpertTypes
          ),
        });
      }
      if (projectId && url.endsWith("/open") && method === "POST") {
        activeProjectId = projectId;
        return json({
          workspace: workspace(
            projectId,
            projectName(projectId),
            drafts[`${projectId}:${activeExpertTypes[projectId]}`] ?? "",
            activeExpertTypes,
            projectExpertTypes
          ),
        });
      }
      if (projectId && url.endsWith("/draft") && method === "PUT") {
        const body = JSON.parse(String(init?.body ?? "{}"));
        const expertType = body.projectExpertId
          ? expertTypeFromExpertId(String(body.projectExpertId))
          : activeExpertTypes[projectId];
        drafts[`${projectId}:${expertType}`] = body.content ?? "";
        return json({
          workspace: workspace(
            projectId,
            projectName(projectId),
            drafts[`${projectId}:${activeExpertTypes[projectId]}`] ?? "",
            activeExpertTypes,
            projectExpertTypes
          ),
        });
      }
      if (projectId && url.endsWith("/chat/stream") && method === "POST") {
        return streamResponse();
      }
      if (projectId && method === "GET") {
        return json({
          workspace: workspace(
            projectId,
            projectName(projectId),
            drafts[`${projectId}:${activeExpertTypes[projectId]}`] ?? "",
            activeExpertTypes,
            projectExpertTypes
          ),
        });
      }
      return json({}, 404);
    });

  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function summary(id: string, name: string) {
  return {
    id,
    name,
    stage: "IDEA",
    activeExpertIds: [expertId(id)],
    selectedModel: "deepseek-v4-flash",
    messageCount: id === "prj_a" ? 1 : 0,
    draftUpdatedAt: null,
    archivedAt: null,
    updatedAt: "2026-07-08T00:00:00.000Z",
    lastOpenedAt: "2026-07-08T00:00:00.000Z",
  };
}

function workspace(
  id: string,
  name: string,
  draft: string,
  activeExpertTypes: Record<string, string> = { [id]: "problem_guide" },
  projectExpertTypes: Record<string, string[]> = { [id]: ["problem_guide"] }
) {
  const messages =
    id === "prj_a"
      ? [
          {
            id: "msg_a",
            role: "assistant",
            content: "项目A历史消息",
            status: "COMPLETED",
            createdAt: "2026-07-08T00:00:00.000Z",
            updatedAt: "2026-07-08T00:00:00.000Z",
            model: "deepseek-v4-flash",
          },
        ]
      : [];
  const activeExpertType = activeExpertTypes[id] ?? "problem_guide";
  const selectedExpertTypes = projectExpertTypes[id] ?? ["problem_guide"];
  const experts = selectedExpertTypes.map((expertType) => ({
    id: expertId(id, expertType),
    projectId: id,
    expertDefinitionId: `expert_def_${expertType}`,
    expertType,
    conversationId: conversationId(id, expertType),
    privateMemoryId: `memory_${id}_${expertType}`,
    status: expertType === activeExpertType ? "working" : "idle",
    workspaceStatus: expertType === activeExpertType ? "in_progress" : "not_started",
    currentTask: expertType === "problem_guide" ? "继续澄清创意" : "等待任务",
    addedAt: "2026-07-08T00:00:00.000Z",
    removedAt: null,
  }));
  const activeExpert = experts.find((expert) => expert.expertType === activeExpertType) ?? experts[0];
  return {
    project: {
      id,
      name,
      stage: "IDEA",
      profile: { initialIdea: "" },
      conversationId: activeExpert?.conversationId ?? conversationId(id),
      activeExpertIds: experts.map((expert) => expert.id),
      activeExpertId: activeExpert?.id ?? null,
      sharedContextId: `shared_${id}`,
      coordinatorStateId: `coord_${id}`,
      selectedModel: "deepseek-v4-flash",
      archivedAt: null,
      createdAt: "2026-07-08T00:00:00.000Z",
      updatedAt: "2026-07-08T00:00:00.000Z",
      lastOpenedAt: "2026-07-08T00:00:00.000Z",
      schemaVersion: 22,
    },
    conversation: {
      id: activeExpert?.conversationId ?? conversationId(id),
      projectId: id,
      messages: activeExpert?.expertType === "problem_guide" ? messages : [],
      updatedAt: "2026-07-08T00:00:00.000Z",
    },
    draft: {
      projectId: id,
      projectExpertId: activeExpert?.id ?? null,
      content: draft,
      updatedAt: draft ? "2026-07-08T00:00:00.000Z" : null,
    },
    experts,
    expertDefinitions: expertDefinitions(),
    expertConversations: experts.map((expert) => ({
        id: expert.conversationId,
        projectId: id,
        projectExpertId: expert.id,
        expertType: expert.expertType,
        expertName: expertDefinitions().find((definition) => definition.type === expert.expertType)?.name ?? expert.expertType,
        messages: expert.expertType === "problem_guide" ? messages : [],
        draft: {
          projectId: id,
          projectExpertId: expert.id,
          content: draft,
          updatedAt: draft ? "2026-07-08T00:00:00.000Z" : null,
        },
        activeQuestionId: null,
        activeTurnId: null,
        updatedAt: "2026-07-08T00:00:00.000Z",
      })),
    sharedContext: {
      id: `shared_${id}`,
      projectId: id,
      revision: 1,
      goals: [],
      constraints: [],
      requirements: [],
      decisions: [],
      activeArtifactVersions: [],
      updatedAt: "2026-07-08T00:00:00.000Z",
    },
    coordinator: {
      id: `coord_${id}`,
      projectId: id,
      currentItem: null,
      expertStatuses: experts,
      conflicts: [],
      dependencies: [],
      updatedAt: "2026-07-08T00:00:00.000Z",
    },
  };
}

function expertDefinitions() {
  return [
    {
      id: "expert_def_problem_guide",
      type: "problem_guide",
      name: "问题引导师",
      description: "梳理问题、需求和项目方案",
      icon: "spark",
      builtIn: true,
      skillIds: ["idea-understanding"],
      supportedArtifactTypes: ["requirements"],
    },
    {
      id: "expert_def_smart_engineer",
      type: "smart_engineer",
      name: "智能工程师",
      description: "硬件、软件、IoT 和 AI 部署",
      icon: "cpu",
      builtIn: true,
      skillIds: ["hardware-selection"],
      supportedArtifactTypes: ["hardware_solution", "micropython_project"],
    },
    {
      id: "expert_def_structure_engineer",
      type: "structure_engineer",
      name: "结构工程师",
      description: "结构和外壳",
      icon: "box",
      builtIn: true,
      skillIds: ["parametric-modeling"],
      supportedArtifactTypes: ["cad_model"],
    },
  ];
}

function expertId(projectId: string, expertType = "problem_guide") {
  return `expert_${projectId}_${expertType}`;
}

function conversationId(projectId: string, expertType = "problem_guide") {
  return `conv_${projectId}_${expertType}`;
}

function expertTypeFromExpertId(projectExpertId: string) {
  return projectExpertId.replace(/^expert_[^_]+_[^_]+_/, "");
}

function projectName(projectId: string) {
  return projectId === "prj_b" ? "项目B" : "项目A";
}

function projectIdFromUrl(url: string) {
  return url.match(/\/api\/projects\/([^/]+)/)?.[1];
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function streamResponse(): Response {
  return new Response(
    new ReadableStream({
      start(controller) {
        controller.close();
      },
    }),
    { status: 200, headers: { "Content-Type": "text/event-stream" } }
  );
}
