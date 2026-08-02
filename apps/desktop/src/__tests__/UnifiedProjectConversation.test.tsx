import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppShell } from "../components/layout/AppShell";
import {
  createHostAdapter,
  HostAdapterProvider,
  platformCapabilities,
} from "../platform";

vi.mock("../components/floating/MonacoCodeEditor", () => ({
  default: ({
    filePath,
    value,
    onChange,
    readOnly,
  }: {
    filePath: string;
    value: string;
    onChange: (value: string) => void;
    readOnly?: boolean;
  }) => (
    <textarea
      aria-label={`编辑 ${filePath}`}
      value={value}
      readOnly={readOnly}
      onChange={(event) => onChange(event.target.value)}
    />
  ),
}));

vi.mock("../hooks/useHealthCheck", () => ({
  useHealthCheck: () => ({ status: "ok" as const, version: "0.1.0" }),
}));

afterEach(() => vi.unstubAllGlobals());

describe("项目唯一对话与智能体路由", () => {
  it("左侧新建，合并智能体消息，并用 @ 路由到独立会话", async () => {
    const fetchMock = mockFetch();
    render(<AppShell />);

    const left = await screen.findByTestId("left-sidebar");
    expect(within(left).getByRole("button", { name: "新建项目" })).toBeInTheDocument();
    expect(within(screen.getByRole("banner")).getByRole("button", { name: "新建项目" })).toBeInTheDocument();

    expect(await screen.findByText("先确认使用场景")).toBeInTheDocument();
    expect(screen.getByText("可以使用 ESP32-S3")).toBeInTheDocument();
    expect(screen.getAllByTestId("center-chat")).toHaveLength(1);
    const center = screen.getByTestId("center-chat");
    expect(within(center).getAllByRole("img", { name: "掌问头像" })).toHaveLength(2);
    expect(screen.queryByRole("group", { name: "项目智能体" })).not.toBeInTheDocument();

    await enableProfessionalMode();
    expect(
      within(center).getByRole("img", { name: "问题引导师头像" }),
    ).toHaveTextContent("✦");
    expect(
      within(center).getByRole("img", { name: "智能工程师头像" }),
    ).toHaveTextContent("⚙");
    const roles = screen.getAllByText(/问题引导师|智能工程师/).map((node) => node.textContent);
    expect(roles).toContain("问题引导师");
    expect(roles).toContain("智能工程师");

    const strip = screen.getByRole("group", { name: "项目智能体" });
    expect(within(strip).getByRole("button", { name: /问题引导师/ })).toBeInTheDocument();
    expect(within(strip).getByRole("button", { name: /智能工程师/ })).toBeInTheDocument();

    const input = screen.getByPlaceholderText("描述你想做的作品…");
    fireEvent.change(input, { target: { value: "@智能工程师 设计接线" } });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(([target]) =>
        String(target).endsWith("/api/projects/prj_unified/chat/stream")
      );
      expect(call).toBeDefined();
      const request = JSON.parse(String(call?.[1]?.body ?? "{}"));
      expect(request).toMatchObject({
        content: "设计接线",
        projectExpertId: "expert_smart",
        threadId: "conv_smart",
        expertType: "smart_engineer",
      });
    });
  });

  it("设备页不依赖消息路由专家且 Web 设备动作仍受能力门禁", async () => {
    const fetchMock = mockFetch();
    render(
      <HostAdapterProvider adapter={createHostAdapter(platformCapabilities("web"))}>
        <AppShell />
      </HostAdapterProvider>,
    );

    await screen.findByText("统一对话项目", { selector: "strong" });
    fireEvent.click(screen.getByRole("tab", { name: "设备" }));
    const devices = await screen.findByTestId("devices-tab");
    expect(
      within(devices).queryByText(
        "设备控制需切换到智能工程师；当前专家只能读取设备摘要。",
      ),
    ).not.toBeInTheDocument();
    expect(within(devices).getByRole("button", { name: "扫描设备" })).toBeDisabled();

    await enableProfessionalMode();
    const strip = screen.getByRole("group", { name: "项目智能体" });
    fireEvent.click(within(strip).getByRole("button", { name: /智能工程师/ }));

    expect(
      within(strip).getByRole("button", { name: /智能工程师/ }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(
      within(devices).getByText(/请使用掌问桌面端或先配对 Local Bridge/),
    ).toBeInTheDocument();
    expect(within(devices).getByRole("button", { name: "上传并运行" })).toBeDisabled();
    expect(within(devices).queryByRole("button", { name: "连接" })).not.toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([target]) =>
        String(target).includes("/devices/ports"),
      ),
    ).toBe(false);
  });

  it("专业模式中编辑 Agent Skill 包，并保持主对话和公共知识入口", async () => {
    const fetchMock = mockFetch();
    render(<AppShell />);
    await screen.findByText("统一对话项目", { selector: "strong" });

    fireEvent.click(screen.getByRole("button", { name: "打开设置" }));
    const settings = screen.getByRole("dialog", { name: "设置" });
    expect(within(settings).queryByRole("button", { name: "智能体" })).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([target]) => String(target).endsWith("/api/agent-packages"))).toBe(false);

    fireEvent.click(within(settings).getByRole("checkbox", { name: "专业模式" }));
    fireEvent.click(within(settings).getByRole("button", { name: "智能体" }));
    expect(await within(settings).findByRole("region", { name: "智能体配置" })).toBeInTheDocument();
    expect(within(settings).getByText(/设置 → 智能体 → 打开行为项目/)).toBeInTheDocument();
    const capabilities = within(settings).getByRole("region", { name: "受控执行能力" });
    expect(within(capabilities).getByText("硬件选型")).toBeInTheDocument();
    expect(within(capabilities).getByText(/与上方 Markdown 行为项目分离/)).toBeInTheDocument();
    fireEvent.click(within(capabilities).getByRole("button", { name: "编辑描述" }));
    fireEvent.change(within(capabilities).getByRole("textbox", { name: "Skill 描述 硬件选型" }), {
      target: { value: "按 ACTIVE Hardware Skill 完成硬件选型" },
    });
    fireEvent.click(within(capabilities).getByRole("button", { name: "保存描述" }));
    expect(await within(settings).findByText("已保存“硬件选型”的执行能力描述。"))
      .toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([target, init]) =>
      String(target).endsWith("/api/skills/hardware-selection") && init?.method === "PATCH"
    )).toBe(true);
    fireEvent.click(within(settings).getByRole("button", { name: "打开 问题引导师行为项目" }));

    const behaviorWindow = await screen.findByRole("dialog", { name: "问题引导师 · 行为项目" });
    expect(screen.queryByRole("dialog", { name: "设置" })).not.toBeInTheDocument();
    expect(
      await within(behaviorWindow).findByText("主 SKILL.md", {}, { timeout: 3000 }),
    ).toBeInTheDocument();
    const editor = within(behaviorWindow).getByRole("textbox", { name: "编辑 SKILL.md" });
    fireEvent.change(editor, { target: { value: `${String((editor as HTMLTextAreaElement).value)}\n\n- 前端保存验证。` } });
    fireEvent.click(within(behaviorWindow).getByRole("button", { name: "保存全部" }));
    expect(await within(behaviorWindow).findByText(
      "已保存 1 个文件。下一次问题引导师回复开始生效。",
      {},
      { timeout: 3000 },
    ))
      .toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([target, init]) =>
      String(target).endsWith("/api/agent-packages/problem_guide/files") && init?.method === "PUT"
    )).toBe(true);
    expect(screen.getAllByTestId("center-chat")).toHaveLength(1);
    expect(within(behaviorWindow).getByText("manifest.json（系统只读）")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "打开设置" }));
    const reopenedSettings = screen.getByRole("dialog", { name: "设置" });
    fireEvent.click(within(reopenedSettings).getByRole("button", { name: "公共知识" }));
    expect(within(reopenedSettings).getByRole("region", { name: "公共知识库" })).toBeInTheDocument();
    expect(within(reopenedSettings).getByText("三位工程师共享")).toBeInTheDocument();
    expect(within(reopenedSettings).getByRole("button", { name: "新建 Hardware Skill" })).toBeInTheDocument();
  });
});

async function enableProfessionalMode() {
  if (screen.queryByRole("group", { name: "项目智能体" })) return;
  fireEvent.click(screen.getByRole("button", { name: "打开设置" }));
  const settings = screen.getByRole("dialog", { name: "设置" });
  const toggle = within(settings).getByRole("checkbox", { name: "专业模式" });
  if (!(toggle as HTMLInputElement).checked) fireEvent.click(toggle);
  fireEvent.click(within(settings).getByRole("button", { name: "关闭设置" }));
  await screen.findByRole("group", { name: "项目智能体" });
}

function mockFetch() {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    if (url.endsWith("/api/settings/llm")) {
      return json({ config: { provider: "deepseek", baseUrl: "https://api.deepseek.com", defaultModel: "deepseek-v4-flash", thinkingMode: "AUTO", reasoningEffort: null, timeoutSeconds: 60, keySaved: true, maskedApiKey: "***", updatedAt: null } });
    }
    if (url.endsWith("/api/llm/models")) return json({ models: [] });
    if (
      (url.endsWith("/api/projects") ||
        url.endsWith("/api/projects?includeArchived=true")) &&
      (init?.method ?? "GET") === "GET"
    ) {
      return json({ activeProjectId: "prj_unified", projects: [{ id: "prj_unified", name: "统一对话项目", stage: "IDEA", activeExpertIds: ["expert_guide", "expert_smart"], selectedModel: "deepseek-v4-flash", messageCount: 2, draftUpdatedAt: null, archivedAt: null, updatedAt: "2026-07-11T00:00:00Z", lastOpenedAt: "2026-07-11T00:00:00Z" }] });
    }
    if (url.endsWith("/api/projects/prj_unified")) return json({ workspace: workspace() });
    if (url.endsWith("/api/projects/prj_unified/chat/stream")) {
      return new Response(new ReadableStream({ start(controller) { controller.close(); } }), { status: 200, headers: { "Content-Type": "text/event-stream" } });
    }
    if (url.endsWith("/api/projects/prj_unified/draft")) return json({ workspace: workspace() });
    if (url.endsWith("/api/skills") && method === "GET") return json({ skills: [skillDefinition()] });
    if (url.endsWith("/api/skills/hardware-selection") && method === "PATCH") {
      const request = JSON.parse(String(init?.body ?? "{}"));
      return json({ skill: { ...skillDefinition(), description: request.description } });
    }
    if (url.endsWith("/api/agent-packages") && method === "GET") return json({ packages: [agentPackageSummary()] });
    if (url.endsWith("/api/agent-packages/problem_guide") && method === "GET") return json({ package: agentPackage() });
    if (url.endsWith("/api/agent-packages/problem_guide/files") && method === "PUT") {
      const request = JSON.parse(String(init?.body ?? "{}"));
      return json({ package: agentPackage(request.content, "revision-2", true) });
    }
    if (url.endsWith("/api/hardware/skills")) return json({ skills: [] });
    if (url.includes("/api/hardware")) return json({ components: [] });
    return json({}, 404);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function skillDefinition() {
  return {
    id: "hardware-selection",
    name: "硬件选型",
    description: "从公共硬件知识库选型",
    origin: "BUILT_IN",
    enabled: true,
    ownerExpert: "problem_guide",
    inputSchema: { type: "object" },
    outputSchema: { type: "object" },
    timeoutPolicy: { timeoutMs: 30000 },
    retryPolicy: { maxRetries: 1, backoffMs: 100 },
    permissions: ["READ_PROJECT"],
    createdAt: "2026-07-11T00:00:00Z",
    updatedAt: "2026-07-11T00:00:00Z",
  };
}

function agentPackageSummary() {
  const detail = agentPackage();
  const { files: _files, ...summary } = detail;
  return summary;
}

function agentPackage(
  content = "---\nname: problem-guide\ndescription: 澄清项目目标和约束。\n---\n\n# 问题引导师\n\n先确认需求。",
  revision = "revision-1",
  overridden = false
) {
  return {
    expertType: "problem_guide",
    skillName: "problem-guide",
    displayName: "问题引导师",
    description: "澄清项目目标和约束。",
    icon: "spark",
    entryFile: "SKILL.md",
    skillIds: ["hardware-selection"],
    supportedArtifactTypes: ["requirements"],
    capabilityBoundaries: ["不操作设备"],
    fileCount: 2,
    overridden,
    revision,
    validationIssues: [],
    files: [
      { path: "SKILL.md", title: "主 SKILL.md", kind: "entry", content, editable: true, overridden },
      { path: "references/DISCOVERY.md", title: "需求发现方法", kind: "reference", content: "# 需求发现", editable: true, overridden: false },
    ],
  };
}

function workspace() {
  const message = (id: string, content: string, expertType: string, createdAt: string) => ({ id, role: "assistant", content, metadata: { expertType }, status: "COMPLETED", createdAt, updatedAt: createdAt, model: "deepseek-v4-flash" });
  const experts = [
    { id: "expert_guide", projectId: "prj_unified", expertDefinitionId: "expert_def_problem_guide", expertType: "problem_guide", conversationId: "conv_guide", privateMemoryId: "mem_guide", status: "working", addedAt: "2026-07-11T00:00:00Z" },
    { id: "expert_smart", projectId: "prj_unified", expertDefinitionId: "expert_def_smart_engineer", expertType: "smart_engineer", conversationId: "conv_smart", privateMemoryId: "mem_smart", status: "idle", addedAt: "2026-07-11T00:00:00Z" },
  ];
  const definitions = [
    { id: "expert_def_problem_guide", type: "problem_guide", name: "问题引导师", description: "澄清", icon: "spark", builtIn: true, skillIds: [], supportedArtifactTypes: [] },
    { id: "expert_def_smart_engineer", type: "smart_engineer", name: "智能工程师", description: "实现", icon: "cpu", builtIn: true, skillIds: [], supportedArtifactTypes: [] },
  ];
  return {
    project: { id: "prj_unified", name: "统一对话项目", stage: "IDEA", profile: { initialIdea: "测试" }, conversationId: "conv_guide", activeExpertIds: experts.map((item) => item.id), activeExpertId: "expert_guide", selectedModel: "deepseek-v4-flash", archivedAt: null, createdAt: "2026-07-11T00:00:00Z", updatedAt: "2026-07-11T00:00:00Z", lastOpenedAt: "2026-07-11T00:00:00Z", schemaVersion: 22 },
    conversation: { id: "conv_guide", projectId: "prj_unified", messages: [], updatedAt: "2026-07-11T00:00:00Z" },
    draft: { projectId: "prj_unified", content: "", updatedAt: null },
    experts,
    expertDefinitions: definitions,
    expertConversations: [
      { id: "conv_guide", projectId: "prj_unified", projectExpertId: "expert_guide", expertType: "problem_guide", expertName: "问题引导师", messages: [message("msg_guide", "先确认使用场景", "problem_guide", "2026-07-11T00:00:01Z")], draft: { projectId: "prj_unified", content: "", updatedAt: null } },
      { id: "conv_smart", projectId: "prj_unified", projectExpertId: "expert_smart", expertType: "smart_engineer", expertName: "智能工程师", messages: [message("msg_smart", "可以使用 ESP32-S3", "smart_engineer", "2026-07-11T00:00:02Z")], draft: { projectId: "prj_unified", content: "", updatedAt: null } },
    ],
    sharedContext: null,
    coordinator: null,
  };
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}
