import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { LLMConfig, ModelConfig, ProjectWorkspace } from "@zhangwen/contracts";
import { CenterChat } from "../components/layout/CenterChat";

const streamHarness = vi.hoisted(() => ({
  onChunk: null as ((chunk: Record<string, unknown>) => void) | null,
  startProject: vi.fn(),
  stopProject: vi.fn(async () => undefined),
  startPendingItemResolution: vi.fn(async () => undefined),
}));

vi.mock("../hooks/useChatStream", () => ({
  useChatStream: ({ onChunk }: { onChunk: (chunk: Record<string, unknown>) => void }) => {
    streamHarness.onChunk = onChunk;
    return {
      startProject: streamHarness.startProject,
      stopProject: streamHarness.stopProject,
      startPendingItemResolution: streamHarness.startPendingItemResolution,
    };
  },
}));

describe("立项书浮窗与确认后的专家交接", () => {
  beforeEach(() => {
    streamHarness.onChunk = null;
    streamHarness.startProject.mockReset();
    streamHarness.stopProject.mockClear();
    streamHarness.startPendingItemResolution.mockClear();
    vi.stubGlobal("fetch", vi.fn(async () => json({}, 404)));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("查看立项书直接打开对应产物浮窗，不发送聊天动作", async () => {
    const onOpenArtifact = vi.fn();
    render(
      <CenterChat
        config={config()}
        workspace={workspace()}
        selectedExpertId="expert_guide"
        models={models()}
        professionalMode={true}
        draftSaving={false}
        onOpenSettings={vi.fn()}
        onOpenArtifact={onOpenArtifact}
        onSaveDraft={vi.fn(async () => undefined)}
        onSelectExpert={vi.fn()}
        onSelectModel={vi.fn(async () => undefined)}
        onReloadProject={vi.fn(async () => undefined)}
      />,
    );

    const center = screen.getByTestId("center-chat");
    const input = screen.getByPlaceholderText("描述你想做的作品…");
    fireEvent.change(input, { target: { value: "保留当前对话草稿" } });
    fireEvent.click(screen.getByRole("button", { name: "查看立项书" }));

    expect(onOpenArtifact).toHaveBeenCalledWith(
      "artifact_proposal_prj_handoff",
      "artifact_version_proposal_proposal_1",
    );
    expect(streamHarness.startProject).not.toHaveBeenCalled();
    expect(screen.queryByText(/立项书可以在右侧/)).not.toBeInTheDocument();
    expect(screen.getAllByTestId("center-chat")).toHaveLength(1);
    expect(screen.getByTestId("center-chat")).toBe(center);
    expect(input).toHaveValue("保留当前对话草稿");
  });

  it("确认立项书后跳过 Spec，并自动切换到已有智能工程师执行", async () => {
    const onReloadProject = vi.fn(async () => undefined);
    const onSelectExpert = vi.fn();
    const onAddExpert = vi.fn();
    render(
      <CenterChat
        config={config()}
        workspace={workspace()}
        selectedExpertId="expert_guide"
        models={models()}
        professionalMode={false}
        draftSaving={false}
        onOpenSettings={vi.fn()}
        onOpenArtifact={vi.fn()}
        onSaveDraft={vi.fn(async () => undefined)}
        onAddExpert={onAddExpert}
        onSelectExpert={onSelectExpert}
        onSelectModel={vi.fn(async () => undefined)}
        onReloadProject={onReloadProject}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "确认立项书" }));

    await waitFor(() => expect(streamHarness.startProject).toHaveBeenCalledTimes(1));
    const firstRequest = streamHarness.startProject.mock.calls[0]?.[1];
    expect(firstRequest).toMatchObject({
      projectExpertId: "expert_guide",
      threadId: "conv_guide",
      conversationAction: "confirm_project_proposal",
    });
    emitTurn({
      conversationId: "conv_guide",
      requestTurnId: String(firstRequest.clientTurnId),
      content: "已确认立项书 v1，正在交接给智能工程师执行。",
      payload: {
        type: "proposal_action",
        message: "已确认立项书 v1，正在交接给智能工程师执行。",
        proposalId: "proposal_1",
        proposalVersion: 1,
        actions: [
          { id: "view_project_proposal", label: "查看立项书", action: "view_project_proposal" },
        ],
        handoff: {
          automatic: true,
          targetExpert: "smart_engineer",
          label: "已交接给智能工程师",
          prompt: "立项书已确认，请基于当前已确认立项书直接开始项目实现。",
        },
      },
    });

    expect(
      await screen.findByText("已确认立项书 v1，正在交接给智能工程师执行。"),
    ).toBeInTheDocument();
    await waitFor(() => expect(onReloadProject).toHaveBeenCalledWith("prj_handoff"));
    await waitFor(() => expect(streamHarness.startProject).toHaveBeenCalledTimes(2));
    const handoffRequest = streamHarness.startProject.mock.calls[1]?.[1];
    expect(handoffRequest).toMatchObject({
      content: "立项书已确认，请基于当前已确认立项书直接开始项目实现。",
      projectExpertId: "expert_smart",
      threadId: "conv_smart",
      expertType: "smart_engineer",
      automaticHandoff: true,
      handoffLabel: "已交接给智能工程师",
    });
    expect(onSelectExpert).toHaveBeenCalledWith("expert_smart");
    expect(onAddExpert).not.toHaveBeenCalled();
    expect(screen.queryByText("已交接给智能工程师")).not.toBeInTheDocument();
    expect(screen.getByRole("status", { name: "掌问正在生成回复" })).toBeInTheDocument();
    expect(screen.queryByText(/确认 Spec/)).not.toBeInTheDocument();
  });
});

function emitTurn({
  conversationId,
  requestTurnId,
  content,
  payload,
}: {
  conversationId: string;
  requestTurnId: string;
  content: string;
  payload: unknown;
}): void {
  const common = {
    requestId: `request_${requestTurnId}`,
    messageId: `assistant_${requestTurnId}`,
    requestTurnId,
    responseTurnId: `response_${requestTurnId}`,
    projectId: "prj_handoff",
    conversationId,
    userMessageId: `user_${requestTurnId}`,
    model: "deepseek-v4-flash",
  };
  act(() => {
    streamHarness.onChunk?.({ ...common, type: "START" });
    streamHarness.onChunk?.({
      ...common,
      type: "COMPLETED",
      accumulatedContent: content,
      structuredPayload: payload,
    });
  });
}

function workspace(): ProjectWorkspace {
  const proposalPayload = {
    type: "proposal_action",
    message: "立项书 v1 待确认。",
    proposalId: "proposal_1",
    proposalVersion: 1,
    actions: [
      { id: "view_project_proposal", label: "查看立项书", action: "view_project_proposal" },
      { id: "confirm_project_proposal", label: "确认立项书", action: "confirm_project_proposal" },
    ],
  };
  const guideMessages = [{
    id: "assistant_proposal",
    role: "assistant",
    content: "立项书已经生成，请确认。",
    structuredPayload: proposalPayload,
    metadata: {
      projectExpertId: "expert_guide",
      expertType: "problem_guide",
      conversationId: "conv_guide",
    },
    status: "COMPLETED",
    createdAt: "2026-07-16T00:00:00Z",
    updatedAt: "2026-07-16T00:00:00Z",
    model: "deepseek-v4-flash",
  }];
  const emptyDraft = {
    projectId: "prj_handoff",
    projectExpertId: null,
    content: "",
    updatedAt: null,
  };
  return {
    project: {
      id: "prj_handoff",
      name: "自动浇花器",
      stage: "PROPOSAL_DRAFT",
      profile: { initialIdea: "做一个自动浇花器" },
      conversationId: "conv_guide",
      activeExpertIds: ["expert_guide", "expert_smart"],
      activeExpertId: "expert_guide",
      sharedContextId: "shared_handoff",
      coordinatorStateId: "coord_handoff",
      selectedModel: "deepseek-v4-flash",
      archivedAt: null,
      createdAt: "2026-07-16T00:00:00Z",
      updatedAt: "2026-07-16T00:00:00Z",
      lastOpenedAt: "2026-07-16T00:00:00Z",
      schemaVersion: 24,
    },
    conversation: {
      id: "conv_guide",
      projectId: "prj_handoff",
      messages: guideMessages,
      updatedAt: "2026-07-16T00:00:00Z",
    },
    draft: emptyDraft,
    experts: [
      projectExpert("expert_guide", "problem_guide", "conv_guide"),
      projectExpert("expert_smart", "smart_engineer", "conv_smart"),
    ],
    expertConversations: [
      expertConversation("expert_guide", "problem_guide", "问题引导师", "conv_guide", guideMessages),
      expertConversation("expert_smart", "smart_engineer", "智能工程师", "conv_smart", []),
    ],
  } as unknown as ProjectWorkspace;
}

function projectExpert(id: string, expertType: string, conversationId: string) {
  return {
    id,
    projectId: "prj_handoff",
    expertDefinitionId: `definition_${expertType}`,
    expertType,
    conversationId,
    privateMemoryId: `memory_${expertType}`,
    status: "waiting_user",
    workspaceStatus: "awaiting_user",
    currentTask: "继续项目",
    addedAt: "2026-07-16T00:00:00Z",
    removedAt: null,
  };
}

function expertConversation(
  projectExpertId: string,
  expertType: string,
  expertName: string,
  id: string,
  messages: unknown[],
) {
  return {
    id,
    projectId: "prj_handoff",
    projectExpertId,
    expertType,
    expertName,
    messages,
    draft: {
      projectId: "prj_handoff",
      projectExpertId,
      content: "",
      updatedAt: null,
    },
    updatedAt: "2026-07-16T00:00:00Z",
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

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
