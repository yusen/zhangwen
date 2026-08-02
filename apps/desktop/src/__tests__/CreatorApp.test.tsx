import { useEffect, useState } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { CreatorWorkSummary, CreatorWorkspace } from "@zhangwen/contracts";
import { CreatorApp } from "../creator/CreatorApp";
import { ApiError } from "../services/api";

const mocks = vi.hoisted(() => ({
  creatorOpen: vi.fn(async () => workspaceFixture()),
  creatorCreate: vi.fn(),
  creatorRefresh: vi.fn(),
  creatorCommand: vi.fn(),
  creatorCancelJob: vi.fn(),
  creatorClose: vi.fn(),
  projectOpen: vi.fn(),
  getCurrentCode: vi.fn(),
  listDevicePackages: vi.fn(async () => ({ packages: [] })),
  chatMounts: 0,
  workspace: null as CreatorWorkspace | null,
  works: [] as CreatorWorkSummary[],
}));

vi.mock("../creator/state/useCreatorWorks", () => ({
  useCreatorWorks: () => ({
    works: mocks.works,
    workspace: mocks.workspace,
    loading: false,
    error: null,
    open: mocks.creatorOpen,
    create: mocks.creatorCreate,
    refresh: mocks.creatorRefresh,
    close: mocks.creatorClose,
    command: mocks.creatorCommand,
    cancelJob: mocks.creatorCancelJob,
  }),
}));

vi.mock("../services/creatorApi", async (importOriginal) => ({
  ...await importOriginal<typeof import("../services/creatorApi")>(),
  listCreatorDevicePackages: mocks.listDevicePackages,
}));

vi.mock("../services/projectsApi", async (importOriginal) => ({
  ...await importOriginal<typeof import("../services/projectsApi")>(),
  getCurrentCode: mocks.getCurrentCode,
}));

vi.mock("../hooks/useProjects", () => ({
  useProjects: () => ({
    activeWorkspace: null,
    draftSaving: false,
    draftSaveError: null,
    open: mocks.projectOpen,
    duplicate: vi.fn(),
    activateExpert: vi.fn(),
    saveDraft: vi.fn(),
    setModel: vi.fn(),
    loadWorkspace: vi.fn(),
    dismissPending: vi.fn(),
    setHardware: vi.fn(),
  }),
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

vi.mock("../components/settings/SettingsDialog", () => ({
  SettingsDialog: () => <div role="dialog">Creator 设置</div>,
}));

vi.mock("../components/hardware/HardwareSelectionDialog", () => ({
  selectedProjectHardwareIds: () => [],
  HardwareSelectionDialog: ({ open }: { open: boolean }) => open ? <div role="dialog">真实器件选择器</div> : null,
}));

vi.mock("../components/device-lab/DeviceLabWorkspace", () => ({
  DeviceLabWorkspace: () => <div data-testid="mock-device-lab">设备实验室</div>,
}));

vi.mock("../hooks/useV2CadWorkspace", () => ({
  useV2CadWorkspace: () => ({ workspace: null, loading: false, busy: false, error: null, lastResult: null, submit: vi.fn(), confirmAndBuild: vi.fn(), build: vi.fn(), undo: vi.fn() }),
}));

vi.mock("../hooks/useV2ProjectData", () => ({
  useV2ProjectData: () => ({ data: null, loading: false, error: null, refresh: vi.fn() }),
}));

vi.mock("../components/layout/CenterChat", () => ({
  CenterChat: ({ professionalMode }: { professionalMode: boolean }) => {
    const [draft, setDraft] = useState("");
    useEffect(() => {
      mocks.chatMounts += 1;
    }, []);
    return <label>持续对话<span>{professionalMode ? "三师路由已展开" : "统一掌问入口"}</span><input aria-label="对话草稿" value={draft} onChange={(event) => setDraft(event.target.value)} /></label>;
  },
}));

vi.mock("../components/floating/CodeArtifactEditor", () => ({
  CodeArtifactEditor: ({ codeRunId }: { codeRunId: string }) => (
    <div data-testid="creator-code-editor">真实代码编辑器 · {codeRunId}</div>
  ),
}));

describe("CreatorApp M2 shell", () => {
  beforeEach(() => {
    mocks.workspace = null;
    mocks.works = [];
    mocks.chatMounts = 0;
    vi.clearAllMocks();
    mocks.getCurrentCode.mockRejectedValue(new ApiError("代码不存在", 404, "CODE_RUN_NOT_FOUND"));
  });

  it("shows the real works home and opens a selected work", async () => {
    mocks.works = [workFixture()];
    render(<CreatorApp />);

    expect(screen.getByRole("heading", { name: "我的作品" })).toBeInTheDocument();
    expect(screen.getByText("自动浇花伙伴")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /自动浇花伙伴/ }));

    await waitFor(() => expect(mocks.projectOpen).toHaveBeenCalledWith("prj_creator"));
    expect(mocks.creatorOpen).toHaveBeenCalledWith("prj_creator");
  });

  it("opens the controlled import flow and explains verification reset", () => {
    render(<CreatorApp />);

    const trigger = screen.getByRole("button", { name: "导入作品包" });
    trigger.focus();
    fireEvent.click(trigger);

    const dialog = screen.getByRole("dialog", { name: "导入作品包" });
    expect(dialog).toBeInTheDocument();
    expect(screen.getByText(/原作品的验证等级不会继承/)).toBeInTheDocument();
    expect(screen.getByLabelText("作品包文件")).toHaveAttribute(
      "accept",
      ".zip,.zwcreator.zip,application/zip",
    );
    expect(screen.queryByLabelText("导入者 / 复现者")).not.toBeInTheDocument();
    expect(screen.getByText(/当前已认证账户签署；更改显示名不会改变签署主体/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "校验并导入" })).toBeDisabled();
    expect(screen.getByLabelText("作品包文件")).toHaveFocus();
    expect(trigger.closest(".creator-home-header")).toHaveAttribute("inert");

    fireEvent.keyDown(screen.getByLabelText("作品包文件"), { key: "Tab", shiftKey: true });
    expect(screen.getByRole("button", { name: "取消" })).toHaveFocus();
    fireEvent.keyDown(screen.getByRole("button", { name: "取消" }), { key: "Tab" });
    expect(screen.getByLabelText("作品包文件")).toHaveFocus();

    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "导入作品包" })).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
    expect(trigger.closest(".creator-home-header")).not.toHaveAttribute("inert");
  });

  it("loads the real device package catalog and restores focus after closing", async () => {
    render(<CreatorApp />);

    const trigger = screen.getByRole("button", { name: "打开设备包目录" });
    trigger.focus();
    fireEvent.click(trigger);

    const dialog = screen.getByRole("dialog", { name: "可验证的硬件能力" });
    await waitFor(() => expect(mocks.listDevicePackages).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("还没有可用设备包")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "关闭" })).toHaveFocus();

    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "可验证的硬件能力" })).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("keeps one chat instance mounted while switching all four stages", async () => {
    mocks.workspace = workspaceFixture();
    render(<CreatorApp />);

    expect(await screen.findByRole("button", { name: /^创意与方案，/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /数字原型/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /3D 结构/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /实物运行/ })).toBeInTheDocument();
    expect(screen.queryByText("工作 / 产物 / 设备")).not.toBeInTheDocument();

    const draft = screen.getByRole("textbox", { name: "对话草稿" });
    fireEvent.change(draft, { target: { value: "保留这段草稿" } });
    fireEvent.click(screen.getByRole("button", { name: /数字原型/ }));
    expect(
      await screen.findByTestId("creator-stage-digital", {}, { timeout: 5_000 }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /3D 结构/ }));
    expect(
      await screen.findByTestId("creator-stage-structure", {}, { timeout: 5_000 }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /实物运行/ }));
    expect(
      await screen.findByTestId("creator-stage-physical", {}, { timeout: 5_000 }),
    ).toBeInTheDocument();

    expect(screen.getByRole("textbox", { name: "对话草稿" })).toHaveValue("保留这段草稿");
    expect(mocks.chatMounts).toBe(1);
  });

  it("retains the three-expert professional mode without remounting the conversation", () => {
    mocks.workspace = workspaceFixture();
    render(<CreatorApp />);

    const switchButton = screen.getByRole("switch", { name: "三师专业模式" });
    expect(switchButton).toHaveAttribute("aria-checked", "false");
    expect(screen.getByText("统一掌问入口")).toBeInTheDocument();

    fireEvent.click(switchButton);

    expect(switchButton).toHaveAttribute("aria-checked", "true");
    expect(screen.getByText("三师路由已展开")).toBeInTheDocument();
    expect(screen.getByText("三师专业模式")).toBeInTheDocument();
    expect(mocks.chatMounts).toBe(1);
  });

  it("keeps the chat mounted while opening Creator tool drawers and restores focus", async () => {
    mocks.workspace = workspaceFixture();
    render(<CreatorApp />);

    const draft = screen.getByRole("textbox", { name: "对话草稿" });
    fireEvent.change(draft, { target: { value: "抽屉关闭后继续编辑" } });
    const trigger = screen.getByRole("button", { name: "打开图形调试" });
    trigger.focus();
    fireEvent.click(trigger);

    const drawer = screen.getByRole("dialog", { name: "图形调试" });
    expect(screen.getByRole("button", { name: "关闭" })).toHaveFocus();
    expect(trigger.closest(".creator-workbench-body")).toHaveAttribute("inert");
    fireEvent.keyDown(drawer, { key: "Escape" });

    expect(screen.queryByRole("dialog", { name: "图形调试" })).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
    expect(screen.getByRole("textbox", { name: "对话草稿" })).toHaveValue("抽屉关闭后继续编辑");
    expect(mocks.chatMounts).toBe(1);
  });

  it("renders persisted jobs and immutable parameter revisions from the workspace projection", async () => {
    mocks.workspace = {
      ...workspaceFixture(),
      jobs: [{
        id: "cjob_1",
        workId: "prj_creator",
        solutionRevisionId: "csolution_1",
        kind: "CODE_PREPARATION",
        status: "QUEUED",
        progress: 0,
        message: "等待本地执行器",
        result: null,
        createdAt: "2026-07-31T00:01:00Z",
        updatedAt: "2026-07-31T00:01:00Z",
        startedAt: null,
        completedAt: null,
      }],
      parameterRevisions: [{
        id: "param_1",
        workId: "prj_creator",
        boardId: "dfrobot/dfrobot_k10",
        profileRevision: "zwdbg/1",
        revision: 1,
        label: "室内阈值",
        values: { threshold: 42, enabled: true },
        createdAt: "2026-07-31T00:02:00Z",
      }],
    };
    render(<CreatorApp />);

    fireEvent.click(screen.getByRole("button", { name: "打开代码工作区" }));
    expect(await screen.findByText("已排队 · 0%")).toBeInTheDocument();
    expect(screen.getByText("等待本地执行器")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "取消任务" }));
    await waitFor(() => expect(mocks.creatorCancelJob).toHaveBeenCalledWith(
      "prj_creator",
      "cjob_1",
      expect.stringMatching(/^creator-app-cancel-job:/),
    ));
    fireEvent.click(screen.getByRole("button", { name: "关闭" }));

    fireEvent.click(screen.getByRole("button", { name: "打开参数版本" }));
    expect(screen.getByText("P1")).toBeInTheDocument();
    expect(screen.getByText("室内阈值")).toBeInTheDocument();
    expect(screen.getByText("threshold=42 · enabled=true")).toBeInTheDocument();
  });

  it("opens a real current CodeRun or an explicit not-generated state", async () => {
    mocks.workspace = workspaceFixture();
    const { unmount } = render(<CreatorApp />);

    fireEvent.click(screen.getByRole("button", { name: "打开代码工作区" }));
    expect(await screen.findByRole("heading", { name: "尚未生成代码" })).toBeInTheDocument();
    expect(screen.getByText(/代码准备任务会自动生成部署变体/)).toBeInTheDocument();
    unmount();

    mocks.getCurrentCode.mockReset();
    mocks.getCurrentCode.mockResolvedValue({
      codeRun: {
        id: "code_7",
        projectId: "prj_creator",
        specRunId: "spec_1",
        artifactId: "artifact_code",
        artifactVersionId: "artifact_code_v7",
        version: 7,
        status: "READY_FOR_REVIEW",
        runtime: "MICROPYTHON",
        entrypoint: "src/main.py",
        files: [{
          id: "code_file_7",
          codeRunId: "code_7",
          projectId: "prj_creator",
          kind: "SOURCE",
          path: "src/main.py",
          language: "python",
          content: "print('hello')\n",
          createdAt: "2026-07-31T00:00:00Z",
        }],
        workspaceRoot: "workspace://prj_creator/code/code_7",
        testResult: {
          ok: true,
          checks: [],
          testedAt: "2026-07-31T00:00:00Z",
        },
        patch: {
          id: "patch_7",
          codeRunId: "code_7",
          projectId: "prj_creator",
          baseSnapshotId: null,
          summary: "初始代码",
          diff: "",
          createdAt: "2026-07-31T00:00:00Z",
        },
        staleReason: null,
        createdAt: "2026-07-31T00:00:00Z",
        updatedAt: "2026-07-31T00:00:00Z",
        acceptedAt: null,
      },
    });
    render(<CreatorApp />);
    fireEvent.click(screen.getByRole("button", { name: "打开代码工作区" }));

    expect(await screen.findByTestId("creator-code-editor")).toHaveTextContent("code_7");
    expect(screen.getByText(/真实代码版本 v7/)).toBeInTheDocument();
  });

  it.each([390, 720, 1280])("renders the Creator hierarchy at %ipx", async (width) => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: width });
    mocks.workspace = workspaceFixture();
    const { container } = render(<CreatorApp />);
    expect(container.querySelector(".creator-workbench-body")).toBeInTheDocument();
    expect(container.querySelector(".creator-chat-pane")).toBeInTheDocument();
    expect(container.querySelector(".creator-stage-pane")).toBeInTheDocument();
    expect(container.querySelectorAll("main")).toHaveLength(1);
    expect(screen.getByText("构建数字原型 · 数字原型")).toBeInTheDocument();
    expect(await screen.findByTestId("creator-stage-digital")).toBeInTheDocument();
  });

  it("uses one solution confirmation for the projected goal and solution", async () => {
    const base = workspaceFixture();
    const draftGoal = {
      ...base.currentGoal!,
      status: "DRAFT" as const,
      confirmedAt: null,
    };
    const draftSolution: NonNullable<CreatorWorkspace["draftSolution"]> = {
      id: "solution_draft_single_confirm",
      workId: base.workId,
      revision: 1,
      status: "DRAFT",
      sourceType: "CONVERSATION",
      sourceMessageId: "message_solution",
      sourceTurnId: "turn_solution",
      baseRevisionId: null,
      projectionReceiptId: "receipt_solution",
      summary: "自动浇花方案",
      logic: "土壤干燥时启动水泵，湿润后停止。",
      hardware: "K10、湿度传感器、MOSFET 驱动、水泵和独立电源。",
      software: "MicroPython 本地控制。",
      structure: "防溅控制盒。",
      simulation: "注入干燥、湿润与断线。",
      safety: "超时停机，断线归零。",
      bom: [],
      ioMap: [],
      createdAt: "2026-08-02T00:00:00Z",
      confirmedAt: null,
    };
    mocks.workspace = {
      ...base,
      phase: "SOLUTION_REVIEW",
      activeStage: "IDEA_SOLUTION",
      confirmedGoal: null,
      draftGoal,
      currentGoal: draftGoal,
      confirmedSolution: null,
      draftSolution,
      currentSolution: draftSolution,
      acceptanceScenarios: [{
        id: "scenario_single_confirm",
        workId: base.workId,
        title: "干燥启动并在湿润后停止",
        required: true,
        simulationExpected: "水泵先启动再停止",
        physicalExpected: "真机安全完成浇水",
        createdAt: "2026-08-02T00:00:00Z",
      }],
    };
    render(<CreatorApp />);

    expect(screen.queryByRole("button", { name: "确认目标" })).not.toBeInTheDocument();
    fireEvent.click(
      await screen.findByRole("button", { name: "确认方案并建立数字原型" }),
    );

    await waitFor(() => expect(mocks.creatorCommand).toHaveBeenCalled());
    expect(mocks.creatorCommand.mock.calls[0]?.[1]).toBe("CONFIRM_SOLUTION");
  });

  it("opens the real local hardware selector instead of sending a fake chat turn", async () => {
    mocks.workspace = workspaceFixture();
    render(<CreatorApp />);
    fireEvent.click(await screen.findByRole("button", { name: /^创意与方案，/ }));
    fireEvent.click(await screen.findByRole("button", { name: "选择并添加电子器件" }));
    expect(screen.getByText("真实器件选择器")).toBeInTheDocument();
  });

  it("treats the project book as an optional artifact after solution confirmation", async () => {
    const base = workspaceFixture();
    const solution: NonNullable<CreatorWorkspace["confirmedSolution"]> = {
      id: "solution_confirmed_1",
      workId: base.workId,
      revision: 1,
      status: "CONFIRMED",
      sourceType: "CONVERSATION",
      sourceMessageId: "message_solution",
      sourceTurnId: "turn_solution",
      baseRevisionId: null,
      projectionReceiptId: "receipt_solution",
      summary: "自动浇花方案",
      logic: "土壤干燥时启动，湿润后停止。",
      hardware: "K10、土壤湿度传感器、MOSFET 驱动、水泵和独立电源。",
      software: "MicroPython 本地控制循环。",
      structure: "防溅控制盒。",
      simulation: "注入干燥、湿润与断线。",
      safety: "超时停机并在断线后归零。",
      bom: [],
      ioMap: [],
      createdAt: "2026-08-01T00:00:00Z",
      confirmedAt: "2026-08-01T00:01:00Z",
    };
    mocks.workspace = {
      ...base,
      phase: "DIGITAL_BUILDING",
      activeStage: "IDEA_SOLUTION",
      confirmedSolution: solution,
      currentSolution: solution,
      projectBookProjection: {
        status: "EMPTY",
        goalRevisionId: base.confirmedGoal?.id ?? null,
        solutionRevisionId: solution.id,
        updatedAt: null,
      },
    };
    render(<CreatorApp />);

    const generate = await screen.findByRole("button", { name: "生成立项书" });
    expect(screen.getByText(/不影响方案确认和数字原型/)).toBeVisible();
    fireEvent.click(generate);

    await waitFor(() => expect(mocks.creatorCommand).toHaveBeenCalled());
    expect(mocks.creatorCommand.mock.calls[0]?.[1]).toBe("GENERATE_PROJECT_BOOK");
    expect(mocks.creatorCommand.mock.calls[0]?.[2].payload).toEqual({});
  });
});

function workFixture(): CreatorWorkSummary {
  return {
    id: "prj_creator",
    name: "自动浇花伙伴",
    initialIdea: "土壤干燥时自动浇水",
    phase: "GOAL_REVIEW",
    stage: "IDEA_SOLUTION",
    verificationLevel: 0,
    verificationLabel: "尚未验证",
    nextActionLabel: "确认作品目标",
    archivedAt: null,
    updatedAt: "2026-07-31T00:00:00Z",
    legacy: false,
  };
}

function workspaceFixture(): CreatorWorkspace {
  const goal: NonNullable<CreatorWorkspace["currentGoal"]> = {
    id: "goal_1",
    workId: "prj_creator",
    revision: 1,
    status: "CONFIRMED",
    sourceType: "PROFESSIONAL_EDIT",
    sourceMessageId: null,
    sourceTurnId: null,
    baseRevisionId: null,
    projectionReceiptId: null,
    statement: "制作自动浇花伙伴",
    observableBehavior: "土壤干燥时启动水泵",
    constraints: ["水泵默认关闭"],
    successCriteria: ["达到阈值后停止"],
    createdAt: "2026-07-31T00:00:00Z",
    confirmedAt: "2026-07-31T00:01:00Z",
  };
  return {
    schemaVersion: 1,
    workId: "prj_creator",
    projectId: "prj_creator",
    projectVersion: 2,
    name: "自动浇花伙伴",
    initialIdea: "土壤干燥时自动浇水",
    phase: "DIGITAL_BUILDING",
    activeStage: "DIGITAL_PROTOTYPE",
    verificationLevel: 1,
    verificationLabel: "目标已确认",
    stages: [
      { stage: "IDEA_SOLUTION", label: "创意与方案", status: "PASSED", detail: "目标与当前方案" },
      { stage: "DIGITAL_PROTOTYPE", label: "数字原型", status: "ACTIVE", detail: "仿真、参数与日志" },
      { stage: "STRUCTURE_3D", label: "3D 结构", status: "READY", detail: "结构版本与制造检查" },
      { stage: "PHYSICAL_RUN", label: "实物运行", status: "BLOCKED", detail: "功能仿真通过后才解锁真实操作。" },
    ],
    confirmedGoal: goal,
    draftGoal: null,
    confirmedSolution: null,
    draftSolution: null,
    projectBookProjection: {
      status: "GOAL_ONLY",
      goalRevisionId: goal.id,
      solutionRevisionId: null,
      updatedAt: goal.confirmedAt,
    },
    conversationProjectionStatus: {
      status: "IDLE",
      receiptId: null,
      sourceMessageId: null,
      message: null,
    },
    currentGoal: goal,
    currentSolution: null,
    acceptanceScenarios: [],
    evidence: [],
    jobs: [],
    codeVariants: [],
    parameterRevisions: [],
    nextAction: {
      id: "confirm-solution",
      label: "确认完整方案",
      command: "CONFIRM_SOLUTION",
      stage: "IDEA_SOLUTION",
      enabled: false,
      blockedReason: "正在形成一套当前方案。",
      riskLevel: "LOW",
    },
    archivedAt: null,
    updatedAt: "2026-07-31T00:01:00Z",
    legacy: false,
    needsOrganization: false,
  };
}
