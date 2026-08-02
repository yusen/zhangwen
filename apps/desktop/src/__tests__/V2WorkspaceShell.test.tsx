import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { V2AppShell } from "../components/v2/V2AppShell";
import {
  artifactDisplaySummary,
  artifactDisplayTitle,
} from "../components/v2/pages/common";

const { mockSetHardware } = vi.hoisted(() => ({
  mockSetHardware: vi.fn(async () => ({ selectedHardwareWarnings: [] })),
}));

vi.mock("../components/layout/CenterChat", () => ({
  CenterChat: ({
    workspaceContext,
    onOpenHardwareSelection,
  }: {
    workspaceContext?: Record<string, unknown>;
    onOpenHardwareSelection?: () => void;
  }) => (
    <div
      data-testid="center-chat"
      data-workspace-context={JSON.stringify(workspaceContext ?? {})}
    >
      同一项目 AI 对话
      <button type="button" onClick={onOpenHardwareSelection}>选择并添加电子器件</button>
    </div>
  ),
}));

vi.mock("../components/projects/ProjectCreationDialog", () => ({
  ProjectCreationDialog: () => null,
}));

vi.mock("../components/hardware/HardwareSelectionDialog", () => ({
  selectedProjectHardwareIds: () => [],
  HardwareSelectionDialog: ({
    open,
    initialSelectedIds,
    onConfirm,
    onClose,
  }: {
    open: boolean;
    initialSelectedIds: string[];
    onConfirm: (selectedHardwareIds: string[]) => Promise<unknown> | unknown;
    onClose: () => void;
  }) => open ? (
    <div
      role="dialog"
      aria-label="添加项目电子器件"
      data-initial-selected-ids={initialSelectedIds.join(",")}
    >
      <button
        type="button"
        onClick={() => void Promise.resolve(onConfirm(["hw_seed_unihiker_k10", "hw_relay_module"]))}
      >
        添加到项目
      </button>
      <button type="button" onClick={onClose}>关闭器件选择器</button>
    </div>
  ) : null,
}));

vi.mock("../components/settings/SettingsDialog", () => ({
  SettingsDialog: () => null,
}));

vi.mock("../components/floating/FloatingWindow", () => ({
  FloatingWindow: ({ artifact }: { artifact?: { title?: string } }) => (
    <div data-testid="v2-artifact-floating-window">{artifact?.title}</div>
  ),
}));

vi.mock("../services/projectsApi", async (importOriginal) => {
  const original = await importOriginal<typeof import("../services/projectsApi")>();
  return {
    ...original,
    getArtifact: vi.fn(async () => ({ artifact: projectWorkspaceArtifact() })),
  };
});

vi.mock("../components/right-panel/DevicesTab", () => ({
  DevicesTab: () => <div data-testid="v2-real-device-workspace">真实设备工作台</div>,
}));

vi.mock("../components/device-lab/DeviceLabWorkspace", () => ({
  DeviceLabWorkspace: ({ onBackToChat }: { onBackToChat: () => void }) => (
    <div data-testid="device-lab-workspace">
      双板设备实验室
      <button type="button" onClick={onBackToChat}>返回对话</button>
    </div>
  ),
}));

vi.mock("../hooks/useLlmSettings", () => ({
  useLlmSettings: () => ({
    config: null,
    models: [],
    saving: false,
    testing: false,
    message: null,
    error: null,
    save: vi.fn(),
    clearKey: vi.fn(),
    test: vi.fn(),
  }),
}));

vi.mock("../hooks/useHealthCheck", () => ({
  useHealthCheck: () => ({
    status: "ok",
    version: "0.1.1",
    llmTestMode: "standard",
    usesPaidLlm: false,
  }),
}));

vi.mock("../hooks/useV2Artifacts", () => ({
  useV2Artifacts: () => ({
    artifacts: [
      {
        id: "artifact_code",
        projectId: "prj_v2",
        title: "电子相册代码",
        kind: "CODE",
        status: "DRAFT",
        sourceAgentId: "code-agent",
        currentVersionId: "artifact_code_v1",
        versions: [{
          id: "artifact_code_v1",
          artifactId: "artifact_code",
          projectId: "prj_v2",
          version: 1,
          status: "DRAFT",
          mimeType: "text/x-python",
          preview: { kind: "CODE", summary: "K10 电子相册主程序", code: "print('album')", language: "python" },
          dependencies: [],
          producerTaskId: null,
          sourceEntityType: "code_run",
          sourceEntityId: "code_1",
          checksum: "a".repeat(64),
          staleReason: null,
          createdAt: "2026-07-26T00:00:00Z",
          confirmedAt: null,
        }],
        createdAt: "2026-07-26T00:00:00Z",
        updatedAt: "2026-07-26T00:00:00Z",
      },
      {
        id: "artifact_proposal",
        projectId: "prj_v2",
        title: "电子相册立项书",
        kind: "DOCUMENT",
        status: "APPROVED",
        sourceAgentId: "proposal-agent",
        currentVersionId: "artifact_proposal_v1",
        versions: [{
          id: "artifact_proposal_v1",
          artifactId: "artifact_proposal",
          projectId: "prj_v2",
          version: 1,
          status: "APPROVED",
          mimeType: "text/markdown",
          preview: { kind: "DOCUMENT", summary: "已确认立项书" },
          dependencies: [],
          producerTaskId: null,
          sourceEntityType: "proposal",
          sourceEntityId: "proposal_1",
          checksum: "b".repeat(64),
          staleReason: null,
          createdAt: "2026-07-26T00:00:00Z",
          confirmedAt: "2026-07-26T00:00:00Z",
        }],
        createdAt: "2026-07-26T00:00:00Z",
        updatedAt: "2026-07-26T00:00:00Z",
      },
    ],
    loading: false,
    error: null,
    refresh: vi.fn(),
  }),
}));

vi.mock("../hooks/useProjectProgress", () => ({
  useProjectProgress: () => ({
    progress: {
      readinessSummary: [
        { id: "HARDWARE", label: "硬件", status: "READY", message: "K10 已确认" },
        { id: "CODE", label: "代码", status: "NEEDS_ACTION", message: "代码草稿待确认" },
      ],
    },
    loading: false,
    error: null,
    refresh: vi.fn(),
  }),
}));

const projectWorkspace = {
  project: {
    id: "prj_v2",
    name: "自由结构浇花装置",
    stage: "IMPLEMENTING",
    profile: { initialIdea: "做一个不被固定选项限制的自动浇花装置" },
    activeExpertId: "expert_problem",
    selectedModel: "deepseek-v4-flash",
    conversationId: "conv_v2",
    archivedAt: null,
    createdAt: "2026-07-26T00:00:00Z",
    updatedAt: "2026-07-26T00:00:00Z",
    lastOpenedAt: null,
    schemaVersion: 27,
  },
  conversation: { id: "conv_v2", projectId: "prj_v2", messages: [], updatedAt: "2026-07-26T00:00:00Z" },
  draft: { projectId: "prj_v2", content: "", updatedAt: null },
  experts: [
    { id: "expert_problem", expertType: "problem_guide" },
    { id: "expert_engineering", expertType: "smart_engineer" },
    { id: "expert_structure", expertType: "structure_engineer" },
  ],
  expertConversations: [],
  sharedContext: {
    confirmedFacts: [],
    activeArtifactVersions: [],
  },
  coordinator: { pendingItems: [] },
};

vi.mock("../hooks/useProjects", () => ({
  useProjects: () => ({
    activeWorkspace: projectWorkspace,
    activeProjectId: "prj_v2",
    projects: [{ id: "prj_v2", name: "自由结构浇花装置", stage: "IMPLEMENTING" }],
    draftSaving: false,
    draftSaveError: null,
    open: vi.fn(),
    create: vi.fn(),
    addExpert: vi.fn(),
    activateExpert: vi.fn(),
    setModel: vi.fn(),
    setHardware: mockSetHardware,
    saveDraft: vi.fn(),
    loadWorkspace: vi.fn(),
    dismissPending: vi.fn(),
  }),
}));

vi.mock("../hooks/useV2ProjectData", () => ({
  useV2ProjectData: () => ({
    data: {
      state: {
        schemaVersion: 1,
        projectId: "prj_v2",
        projectVersion: 2,
        projectionHash: "a".repeat(64),
        projectedAt: "2026-07-26T00:00:00Z",
        mode: "EXPLORATION",
        stage: "IMPLEMENTING",
        currentRecommendation: "K10 + 湿度传感器 + 独立泵电源",
        facts: [
          {
            id: "fact_q1",
            key: "q_1",
            label: "你希望如何获取照片？",
            value: { selectedOptionIds: ["camera"], textInput: null },
            displayValue: "用板载摄像头拍摄",
            revision: 1,
          },
          {
            id: "fact_hardware",
            key: "preferred_hardware",
            label: "项目硬件",
            value: { components: [{ id: "hw_seed_unihiker_k10", name: "行空板 K10", skillName: "UNIHIKER K10", skillRevision: "1" }] },
            displayValue: "行空板 K10 · 硬件组合校验通过。",
            revision: 2,
          },
        ],
        domains: {
          problemGuide: { status: "completed", revision: null, activeArtifactIds: [], pendingItems: [] },
          engineering: { status: "in_progress", revision: null, activeArtifactIds: [], pendingItems: [] },
          structure: { status: "in_progress", revision: null, activeArtifactIds: [], pendingItems: [] },
          delivery: { status: "not_started", revision: null, activeArtifactIds: [], pendingItems: [] },
        },
        capabilityCoverage: { mode: "EXPLORATION", coveragePercent: 75, verifiedCapabilityIds: [], missing: [{ requirement: "pump", reason: "待验证" }] },
      },
      coverage: { mode: "EXPLORATION", coveragePercent: 75, verifiedCapabilityIds: [], missing: [{ requirement: "pump", reason: "待验证" }] },
      changeSets: [{ id: "change_committed", status: "COMMITTED" }],
      versions: [{
        id: "pver_baseline",
        projectId: "prj_v2",
        version: 1,
        stateHash: "a".repeat(64),
        changeSetId: null,
        capabilitySnapshotHash: "b".repeat(64),
        artifactVersionIds: ["artifact_code_v1", "artifact_proposal_v1"],
        validationSummary: [{ code: "V1_BASELINE_IMPORTED", severity: "PASS", message: "已导入" }],
        createdAt: "2026-07-26T00:00:00Z",
      }],
      releases: [],
      capabilities: [],
    },
    loading: false,
    error: null,
    refresh: vi.fn(),
  }),
}));

vi.mock("../hooks/useV2CadWorkspace", () => ({
  useV2CadWorkspace: () => ({
    workspace: {
      currentRevision: null,
      pendingRevision: null,
      revisions: [],
      legacyCadRun: null,
      jobs: [],
    },
    loading: false,
    busy: false,
    error: null,
    lastResult: null,
    refresh: vi.fn(),
    submit: vi.fn(),
    confirm: vi.fn(),
    confirmAndBuild: vi.fn(),
    build: vi.fn(),
    undo: vi.fn(),
  }),
}));

describe("V2 对话中心工作台", () => {
  it("普通模式从硬件待补充卡片打开本地器件选择器并保持主对话挂载", async () => {
    mockSetHardware.mockClear();
    render(<V2AppShell />);

    const centerChat = screen.getByTestId("center-chat");
    fireEvent.click(screen.getByRole("button", { name: "选择并添加电子器件" }));

    const dialog = screen.getByRole("dialog", { name: "添加项目电子器件" });
    expect(dialog).toBeInTheDocument();
    expect(screen.getByTestId("center-chat")).toBe(centerChat);
    expect(centerChat.closest(".zw-stage-chat")).not.toHaveAttribute("hidden");

    fireEvent.click(within(dialog).getByRole("button", { name: "添加到项目" }));
    await waitFor(() => {
      expect(mockSetHardware).toHaveBeenCalledWith(
        "prj_v2",
        ["hw_seed_unihiker_k10", "hw_relay_module"],
      );
    });
  });

  it("普通模式提供对话与双板实验室，切换工作区仍保持同一个 AI 对话挂载", () => {
    render(<V2AppShell />);

    const rail = screen.getByRole("navigation", { name: "主导航" });
    expect(within(rail).getByRole("button", { name: "对话" })).toHaveAttribute("aria-current", "page");
    for (const label of ["概览", "工程", "结构", "交付"]) {
      expect(within(rail).queryByRole("button", { name: label })).not.toBeInTheDocument();
    }
    for (const label of ["对话", "设备实验室", "项目", "连接", "设置"]) {
      expect(within(rail).getByText(label)).toBeVisible();
    }
    const centerChat = screen.getByTestId("center-chat");
    const chatMount = () => centerChat.closest(".zw-stage-chat");
    fireEvent.click(within(rail).getByRole("button", { name: "设备实验室" }));
    expect(screen.getByTestId("device-lab-workspace")).toBeInTheDocument();
    expect(screen.getByTestId("center-chat")).toBe(centerChat);
    expect(chatMount()).toHaveAttribute("hidden", "");
    fireEvent.click(screen.getByRole("button", { name: "返回对话" }));
    expect(chatMount()).not.toHaveAttribute("hidden");

    fireEvent.click(screen.getByRole("button", { name: "专业视图" }));
    fireEvent.click(screen.getByRole("button", { name: "打开侧栏" }));
    expect(within(rail).getByRole("button", { name: "工程" })).toBeInTheDocument();
    expect(within(rail).getByRole("button", { name: "结构" })).toBeInTheDocument();
    expect(within(rail).getByRole("button", { name: "交付" })).toBeInTheDocument();
    for (const label of ["对话", "设备实验室", "概览", "工程", "结构", "交付", "项目", "连接", "设置"]) {
      expect(within(rail).getByText(label)).toBeVisible();
    }

    expect(screen.queryByRole("navigation", { name: "工作区" })).not.toBeInTheDocument();

    expect(chatMount()).not.toHaveAttribute("hidden");
    expect(screen.getByRole("region", { name: "当前工作内容" })).toHaveTextContent("项目概览");

    fireEvent.click(within(rail).getByRole("button", { name: "概览" }));
    expect(chatMount()).toHaveAttribute("hidden", "");
    expect(screen.getAllByText("你希望如何获取照片？").length).toBeGreaterThan(0);
    expect(screen.getAllByText("用板载摄像头拍摄").length).toBeGreaterThan(0);
    expect(screen.queryByText(/selectedOptionIds/)).not.toBeInTheDocument();

    fireEvent.click(within(rail).getByRole("button", { name: "工程" }));
    expect(screen.getByRole("region", { name: "当前工作内容" })).toHaveTextContent("工程 · 硬件");
    expect(screen.getByTestId("center-chat")).toHaveAttribute("data-workspace-context", expect.stringContaining('"workspaceKind":"engineering"'));
    expect(screen.getByText("硬件与供电")).toBeInTheDocument();
    expect(screen.getAllByText(/行空板 K10/).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "代码" }));
    expect(screen.getByRole("region", { name: "当前工作内容" })).toHaveTextContent("工程 · 代码");
    expect(screen.getByTestId("center-chat")).toHaveAttribute("data-workspace-context", expect.stringContaining('"workspaceView":"code"'));
    expect(screen.getAllByText("电子相册代码").length).toBeGreaterThan(0);
    expect(screen.getByText("print('album')")).toBeInTheDocument();
    fireEvent.click(within(screen.getByRole("navigation", { name: "工程实现二级导航" })).getByRole("button", { name: "设备" }));
    expect(screen.getByTestId("v2-real-device-workspace")).toBeInTheDocument();
    expect(within(screen.getByRole("navigation", { name: "右侧功能" })).getByRole("button", { name: "设备" }))
      .toHaveAttribute("aria-current", "page");

    fireEvent.click(within(rail).getByRole("button", { name: "结构" }));
    expect(screen.getByRole("region", { name: "当前工作内容" })).toHaveTextContent("结构设计");
    expect(screen.getByLabelText("3D 结构视口")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "描述你想要的结构" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "生成 3D 方案" })).toBeDisabled();

    fireEvent.click(within(rail).getByRole("button", { name: "交付" }));
    expect(screen.getByRole("region", { name: "当前工作内容" })).toHaveTextContent("成果交付");
    expect(screen.getByText("当前交付基线")).toBeInTheDocument();
    expect(screen.getByText("项目版本 V1")).toBeInTheDocument();
    expect(screen.getAllByText("电子相册立项书").length).toBeGreaterThan(0);

    fireEvent.click(within(rail).getByRole("button", { name: "对话" }));
    expect(screen.getByTestId("center-chat")).toBe(centerChat);
    expect(chatMount()).not.toHaveAttribute("hidden");
  });

  it("提供项目与版本滑出面板、专业信息分层、工作页签与状态栏", () => {
    render(<V2AppShell />);
    const rail = screen.getByRole("navigation", { name: "主导航" });
    expect(screen.getByText("实现中")).toBeInTheDocument();
    expect(screen.queryByText("V2 · 实现中")).not.toBeInTheDocument();

    fireEvent.click(within(rail).getByRole("button", { name: "项目与版本" }));
    const drawer = screen.getByRole("dialog", { name: "项目与版本" });
    expect(within(drawer).getByRole("button", { name: /新建项目/ })).toBeInTheDocument();
    expect(within(drawer).getByText("自由结构浇花装置")).toBeInTheDocument();
    expect(within(drawer).getByRole("button", { name: /V1/ })).toBeInTheDocument();
    fireEvent.click(within(drawer).getByRole("button", { name: "关闭项目面板" }));
    expect(screen.queryByRole("dialog", { name: "项目与版本" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "专业视图" }));
    fireEvent.click(within(rail).getByRole("button", { name: "结构" }));
    expect(screen.getByText(/projectStateHash:/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "打开侧栏" }));
    fireEvent.click(within(screen.getByRole("navigation", { name: "右侧功能" })).getByRole("button", { name: /工作/ }));
    expect(screen.getByRole("region", { name: "本地任务" })).toHaveTextContent("没有正在运行的本地任务");

    expect(screen.getByRole("contentinfo")).toHaveTextContent("云端 LLM");
    expect(within(screen.getByRole("contentinfo")).getByRole("button", { name: /本地任务/ })).toBeInTheDocument();
  });

  it("概览下一步入口呈现真实进度并跳转到对应工作区", () => {
    render(<V2AppShell />);
    const rail = screen.getByRole("navigation", { name: "主导航" });

    fireEvent.click(screen.getByRole("button", { name: "专业视图" }));
    fireEvent.click(within(rail).getByRole("button", { name: "概览" }));
    expect(screen.getByText("1 份代码待确认")).toBeInTheDocument();
    expect(screen.getByText("3D 设计进行中")).toBeInTheDocument();
    expect(screen.getByText("已形成 V1 项目版本")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /开始制作/ }));
    expect(within(rail).getByRole("button", { name: "工程" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByText("硬件与供电")).toBeInTheDocument();

    fireEvent.click(within(rail).getByRole("button", { name: "概览" }));
    fireEvent.click(screen.getByRole("button", { name: /查看成果/ }));
    expect(within(rail).getByRole("button", { name: "交付" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByText("当前交付基线")).toBeInTheDocument();
  });

  it("状态栏显示本地服务健康，右侧项目侧栏可折叠再展开且保持挂载", () => {
    render(<V2AppShell />);

    expect(screen.getByRole("contentinfo")).toHaveTextContent("本地服务正常");
    const inspector = document.querySelector(".zw-inspector");
    expect(inspector).not.toBeNull();
    expect(inspector).not.toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "打开侧栏" }));
    expect(screen.getByRole("complementary", { name: "项目侧栏" })).toBe(inspector);
    expect(inspector).toBeVisible();
  });

  it("窗口收窄时自动收起右侧栏，让主对话保持可用", () => {
    let viewportListener: ((event: MediaQueryListEvent) => void) | undefined;
    const media = {
      matches: false,
      media: "(max-width: 860px)",
      onchange: null,
      addEventListener: vi.fn((_type: string, listener: EventListenerOrEventListenerObject) => {
        if (typeof listener === "function") {
          viewportListener = listener as (event: MediaQueryListEvent) => void;
        }
      }),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(() => true),
    } as unknown as MediaQueryList;
    vi.stubGlobal("matchMedia", vi.fn(() => media));

    const view = render(<V2AppShell />);
    fireEvent.click(screen.getByRole("button", { name: "打开侧栏" }));
    expect(screen.getByRole("complementary", { name: "项目侧栏" })).toBeVisible();

    act(() => {
      viewportListener?.({ matches: true } as MediaQueryListEvent);
    });
    expect(document.querySelector(".zw-inspector")).not.toBeVisible();

    view.unmount();
    vi.unstubAllGlobals();
  });

  it("简洁模式只保留工作、产物、设备三项，并隐藏内部工程术语", () => {
    render(<V2AppShell />);

    fireEvent.click(screen.getByRole("button", { name: "打开侧栏" }));
    const tabs = screen.getByRole("navigation", { name: "右侧功能" });
    expect(within(tabs).getAllByRole("button").map((button) => button.textContent)).toEqual([
      "工作",
      "产物",
      "设备",
    ]);
    expect(screen.queryByText(/Change Set|CAD Intent|Project Version|Release|projectStateHash|sourceSha256|云端 LLM/))
      .not.toBeInTheDocument();
    expect(screen.getByText("已整理 2 项信息")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "待确认修改" })).not.toBeInTheDocument();
    expect(artifactDisplayTitle("V2 结构 CAD 模型", false)).toBe("结构 3D 模型");
    expect(artifactDisplaySummary("已由 ZW-CAD-intent 生成并通过本地构建校验。", false))
      .toBe("已由 结构设计工具 生成并通过生成检查。");
    expect(artifactDisplayTitle("V2 结构 CAD 模型", true)).toBe("V2 结构 CAD 模型");
  });

  it("代码存在后先提示确认代码，并由明确按钮进入受门禁保护的设备页", () => {
    render(<V2AppShell />);

    fireEvent.click(screen.getByRole("button", { name: "专业视图" }));
    fireEvent.click(within(screen.getByRole("navigation", { name: "主导航" })).getByRole("button", { name: "工程" }));
    fireEvent.click(screen.getByRole("button", { name: "代码" }));

    const flow = screen.getByRole("region", { name: "代码上传流程" });
    expect(within(flow).getByText("先确认代码，再进入设备页扫描连接并上传。进入设备页不会自动扫描、连接或上传。"))
      .toBeInTheDocument();
    expect(within(flow).getByText(/当前代码尚未确认/)).toBeInTheDocument();
    expect(within(flow).getByText(/只会上传你已确认的代码/)).toBeInTheDocument();
    expect(screen.queryByTestId("v2-real-device-workspace")).not.toBeInTheDocument();

    fireEvent.click(within(flow).getByRole("button", { name: "进入设备页" }));

    expect(screen.getByTestId("v2-real-device-workspace")).toBeInTheDocument();
    expect(within(screen.getByRole("navigation", { name: "右侧功能" })).getByRole("button", { name: "设备" }))
      .toHaveAttribute("aria-current", "page");
  });

  it("从 V2 代码页面打开原有验证接受浮窗", async () => {
    render(<V2AppShell />);

    fireEvent.click(screen.getByRole("button", { name: "专业视图" }));
    fireEvent.click(within(screen.getByRole("navigation", { name: "主导航" })).getByRole("button", { name: "工程" }));
    fireEvent.click(screen.getByRole("button", { name: "代码" }));
    fireEvent.click(screen.getByRole("button", { name: "打开代码详情并验证" }));

    expect(await screen.findByTestId("v2-artifact-floating-window")).toHaveTextContent("电子相册代码");
    expect(screen.getByTestId("center-chat")).toBeInTheDocument();
  });
});

function projectWorkspaceArtifact() {
  return {
    id: "artifact_code",
    projectId: "prj_v2",
    title: "电子相册代码",
    kind: "CODE",
    status: "DRAFT",
    sourceAgentId: "code-agent",
    currentVersionId: "artifact_code_v1",
    versions: [{
      id: "artifact_code_v1",
      artifactId: "artifact_code",
      projectId: "prj_v2",
      version: 1,
      status: "DRAFT",
      mimeType: "text/x-python",
      preview: { kind: "CODE", summary: "K10 电子相册主程序", code: "print('album')", language: "python" },
      dependencies: [],
      producerTaskId: null,
      sourceEntityType: "code",
      sourceEntityId: "code_1",
      checksum: "a".repeat(64),
      staleReason: null,
      createdAt: "2026-07-26T00:00:00Z",
      confirmedAt: null,
    }],
    createdAt: "2026-07-26T00:00:00Z",
    updatedAt: "2026-07-26T00:00:00Z",
  };
}
