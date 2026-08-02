import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import {
  type ChatMessage,
  ExpertType,
  LLMErrorCode,
  type LLMConfig,
  type LLMError,
  type ModelConfig,
  type ProjectWorkspace,
} from "@zhangwen/contracts";
import { CenterChat } from "../components/layout/CenterChat";

const ORIGINAL_REQUEST = "创建一个 80×50×25 mm、带两个 M3 安装孔的传感器外壳";

const streamHarness = vi.hoisted(() => ({
  startProject: vi.fn(),
  stopProject: vi.fn(async () => undefined),
  startPendingItemResolution: vi.fn(async () => undefined),
}));

vi.mock("../hooks/useChatStream", () => ({
  useChatStream: () => ({
    startProject: streamHarness.startProject,
    stopProject: streamHarness.stopProject,
    startPendingItemResolution: streamHarness.startPendingItemResolution,
  }),
}));

describe("生成失败恢复", () => {
  beforeEach(() => {
    streamHarness.startProject.mockReset();
    streamHarness.stopProject.mockClear();
    streamHarness.startPendingItemResolution.mockClear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("本地校验失败时说明原需求无需修改并在同一专家会话重试", async () => {
    renderChat(localConstraintError());

    expect(screen.getByText("生成结果未通过本地校验")).toBeInTheDocument();
    expect(screen.getAllByText(/原需求本身不需要修改/)).toHaveLength(2);
    expect(screen.queryByRole("button", { name: "修改原需求" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "按原需求重试" }));

    await waitFor(() => expect(streamHarness.startProject).toHaveBeenCalledTimes(1));
    expect(streamHarness.startProject.mock.calls[0]?.[1]).toMatchObject({
      content: ORIGINAL_REQUEST,
      projectExpertId: "expert_structure",
      threadId: "conv_structure",
      expertType: "structure_engineer",
      recoveryOfMessageId: "assistant_failed",
    });
    expect(screen.queryByText("已按原需求重新生成")).not.toBeInTheDocument();
    expect(screen.getByRole("status", { name: "掌问正在生成回复" })).toBeInTheDocument();
    expect(screen.getAllByText(ORIGINAL_REQUEST)).toHaveLength(1);
  });

  it("智能工程师首次本地校验失败时提醒一句并自动按原需求重试", async () => {
    renderChat(localConstraintError(), {
      strictMode: true,
      workspace: workspace(localConstraintError(), ExpertType.SMART_ENGINEER),
    });

    expect(screen.queryByRole("button", { name: "按原需求重试" })).not.toBeInTheDocument();
    expect(screen.queryByText(/本次生成未通过本地校验，.*按原需求自动重试/)).not.toBeInTheDocument();

    await waitFor(() => expect(streamHarness.startProject).toHaveBeenCalledTimes(1));
    expect(streamHarness.startProject.mock.calls[0]?.[1]).toMatchObject({
      content: ORIGINAL_REQUEST,
      projectExpertId: "expert_smart",
      threadId: "conv_smart",
      expertType: ExpertType.SMART_ENGINEER,
      recoveryOfMessageId: "assistant_failed",
      recoveryLabel: "已按原需求自动重试",
    });
    expect(screen.queryByText("已按原需求自动重试")).not.toBeInTheDocument();
    expect(screen.getAllByRole("main")).toHaveLength(1);
  });

  it.each([1, 2])(
    "智能工程师已有 %i 次自动重试失败时继续按原需求重试且不要求确认",
    async (automaticRecoveryFailures) => {
      renderChat(localConstraintError(), {
        strictMode: true,
        workspace: workspace(
          localConstraintError(),
          ExpertType.SMART_ENGINEER,
          automaticRecoveryFailures,
        ),
      });

      expect(screen.queryByRole("button", { name: "按原需求重试" })).not.toBeInTheDocument();
      await waitFor(() => expect(streamHarness.startProject).toHaveBeenCalledTimes(1));
      expect(streamHarness.startProject.mock.calls[0]?.[1]).toMatchObject({
        content: ORIGINAL_REQUEST,
        projectExpertId: "expert_smart",
        threadId: "conv_smart",
        expertType: ExpertType.SMART_ENGINEER,
        recoveryOfMessageId: `assistant_recovery_failed_${automaticRecoveryFailures}`,
        recoveryLabel: "已按原需求自动重试",
      });
      expect(screen.getAllByRole("main")).toHaveLength(1);
    },
  );

  it("智能工程师连续自动重试达到上限后停止请求且不恢复确认按钮", () => {
    renderChat(localConstraintError(), {
      workspace: workspace(
        localConstraintError(),
        ExpertType.SMART_ENGINEER,
        3,
      ),
    });

    expect(streamHarness.startProject).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "按原需求重试" })).not.toBeInTheDocument();
    expect(screen.getByText(/已自动按原需求重试 3 次，仍未通过本地校验/)).toBeInTheDocument();
    expect(screen.getByText(/系统已停止自动请求以避免重复调用/)).toBeInTheDocument();
    expect(screen.getAllByRole("main")).toHaveLength(1);
  });

  it("云端结构不完整时可重新生成或直接打开模型设置", () => {
    const onOpenSettings = vi.fn();
    renderChat({
      code: LLMErrorCode.LLM_OUTPUT_INVALID,
      message: "云端返回的结构化内容连续两次不完整。原需求已保留，可直接重新生成；若反复出现，请检查模型设置。",
      retryable: true,
      userActions: [
        { id: "retry", label: "重新生成" },
        { id: "open_settings", label: "检查模型设置" },
      ],
    }, { onOpenSettings });

    expect(screen.getByText("云端结构化输出不完整")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重新生成" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "检查模型设置" }));
    expect(onOpenSettings).toHaveBeenCalledTimes(1);
  });

  it("兼容历史中断错误并提供继续生成按钮", async () => {
    renderChat({
      code: LLMErrorCode.UNKNOWN,
      message: "上次生成被中断，可重试。",
      retryable: true,
      userActions: [{ id: "retry", label: "重试" }],
    });

    expect(screen.getByText("生成过程已中断")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "修改原需求" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "继续生成" }));

    await waitFor(() => expect(streamHarness.startProject).toHaveBeenCalledTimes(1));
    expect(streamHarness.startProject.mock.calls[0]?.[1]).toMatchObject({
      content: ORIGINAL_REQUEST,
      recoveryOfMessageId: "assistant_failed",
      recoveryLabel: "已继续上一条生成",
    });
  });
});

function renderChat(
  error: LLMError,
  overrides: {
    onOpenSettings?: () => void;
    onSelectExpert?: (projectExpertId: string) => void;
    strictMode?: boolean;
    workspace?: ProjectWorkspace;
  } = {},
) {
  const chatWorkspace = overrides.workspace ?? workspace(error);
  const element = (
    <CenterChat
      config={config()}
      workspace={chatWorkspace}
      selectedExpertId={chatWorkspace.project.activeExpertId ?? null}
      models={models()}
      professionalMode={false}
      draftSaving={false}
      onOpenSettings={overrides.onOpenSettings ?? vi.fn()}
      onOpenArtifact={vi.fn()}
      onSaveDraft={vi.fn(async () => undefined)}
      onSelectExpert={overrides.onSelectExpert ?? vi.fn()}
      onSelectModel={vi.fn(async () => undefined)}
      onReloadProject={vi.fn(async () => undefined)}
    />
  );
  return render(
    overrides.strictMode
      ? <StrictMode>{element}</StrictMode>
      : element,
  );
}

function workspace(
  error: LLMError,
  expertType: ExpertType = ExpertType.STRUCTURE_ENGINEER,
  automaticRecoveryFailures = 0,
): ProjectWorkspace {
  const isSmartEngineer = expertType === ExpertType.SMART_ENGINEER;
  const expertId = isSmartEngineer ? "expert_smart" : "expert_structure";
  const conversationId = isSmartEngineer ? "conv_smart" : "conv_structure";
  const expertName = isSmartEngineer ? "智能工程师" : "结构工程师";
  const initialMessages: ChatMessage[] = [
    {
      id: "user_source",
      role: "user",
      content: ORIGINAL_REQUEST,
      metadata: {
        projectExpertId: expertId,
        expertType,
        conversationId,
        turnId: "turn_source",
        clientTurnId: "turn_source",
        requestTurnId: "turn_source",
      },
      status: "COMPLETED",
      createdAt: "2026-07-17T00:00:00Z",
      updatedAt: "2026-07-17T00:00:00Z",
      model: "deepseek-v4-flash",
    },
    {
      id: "assistant_failed",
      role: "assistant",
      content: "",
      metadata: {
        projectExpertId: expertId,
        expertType,
        conversationId,
        parentTurnId: "turn_source",
        requestTurnId: "turn_source",
      },
      status: "FAILED",
      error,
      createdAt: "2026-07-17T00:00:01Z",
      updatedAt: "2026-07-17T00:00:01Z",
      model: "deepseek-v4-flash",
    },
  ];
  const messages = [...initialMessages];
  let previousFailureId = "assistant_failed";
  for (let attempt = 1; attempt <= automaticRecoveryFailures; attempt += 1) {
    const turnId = `turn_auto_recovery_${attempt}`;
    messages.push(
      {
        id: `user_auto_recovery_${attempt}`,
        role: "user",
        content: ORIGINAL_REQUEST,
        metadata: {
          projectExpertId: expertId,
          expertType,
          conversationId,
          turnId,
          clientTurnId: turnId,
          requestTurnId: turnId,
          recoveryOfMessageId: previousFailureId,
          recoveryLabel: "已按原需求自动重试",
        },
        status: "COMPLETED",
        createdAt: `2026-07-17T00:00:${attempt * 2}.000Z`,
        updatedAt: `2026-07-17T00:00:${attempt * 2}.000Z`,
        model: "deepseek-v4-flash",
      },
      {
        id: `assistant_recovery_failed_${attempt}`,
        role: "assistant",
        content: "",
        metadata: {
          projectExpertId: expertId,
          expertType,
          conversationId,
          parentTurnId: turnId,
          requestTurnId: turnId,
        },
        status: "FAILED",
        error,
        createdAt: `2026-07-17T00:00:${attempt * 2 + 1}.000Z`,
        updatedAt: `2026-07-17T00:00:${attempt * 2 + 1}.000Z`,
        model: "deepseek-v4-flash",
      },
    );
    previousFailureId = `assistant_recovery_failed_${attempt}`;
  }
  return {
    project: {
      id: "prj_recovery",
      name: isSmartEngineer ? "智能恢复测试" : "结构恢复测试",
      stage: "IMPLEMENTATION",
      profile: { initialIdea: ORIGINAL_REQUEST },
      conversationId,
      activeExpertIds: [expertId],
      activeExpertId: expertId,
      sharedContextId: "shared_recovery",
      coordinatorStateId: "coord_recovery",
      selectedModel: "deepseek-v4-flash",
      archivedAt: null,
      createdAt: "2026-07-17T00:00:00Z",
      updatedAt: "2026-07-17T00:00:01Z",
      lastOpenedAt: "2026-07-17T00:00:01Z",
      schemaVersion: 24,
    },
    conversation: {
      id: conversationId,
      projectId: "prj_recovery",
      messages,
      updatedAt: "2026-07-17T00:00:01Z",
    },
    draft: {
      projectId: "prj_recovery",
      projectExpertId: null,
      content: "",
      updatedAt: null,
    },
    experts: [{
      id: expertId,
      projectId: "prj_recovery",
      expertDefinitionId: `definition_${expertType}`,
      expertType,
      conversationId,
      privateMemoryId: "memory_structure",
      status: "waiting_user",
      workspaceStatus: "awaiting_user",
      currentTask: isSmartEngineer ? "生成实现" : "生成结构",
      addedAt: "2026-07-17T00:00:00Z",
      removedAt: null,
    }],
    expertConversations: [{
      id: conversationId,
      projectId: "prj_recovery",
      projectExpertId: expertId,
      expertType,
      expertName,
      messages,
      draft: {
        projectId: "prj_recovery",
        projectExpertId: "expert_structure",
        content: "",
        updatedAt: null,
      },
      updatedAt: automaticRecoveryFailures > 0
        ? `2026-07-17T00:00:${automaticRecoveryFailures * 2 + 1}.000Z`
        : "2026-07-17T00:00:01Z",
    }],
  } as unknown as ProjectWorkspace;
}

function localConstraintError(): LLMError {
  return {
    code: LLMErrorCode.LOCAL_OUTPUT_REJECTED,
    message: "生成结果未通过当前工程约束或安全边界，未写入工程产物。原需求本身不需要修改，可按原需求重新生成。",
    retryable: true,
    userActions: [
      { id: "retry", label: "按原需求重试" },
    ],
  };
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
  return [{
    id: "deepseek-v4-flash",
    label: "DeepSeek V4 Flash",
    provider: "deepseek",
    supportsThinking: true,
    supportsStreaming: true,
  }];
}
