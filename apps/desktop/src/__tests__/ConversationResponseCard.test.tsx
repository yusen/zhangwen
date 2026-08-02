import { fireEvent, render, screen, within } from "@testing-library/react";
import {
  CodeRuntime,
  CadRunStatus,
  CodeRunStatus,
  ConversationActionType,
  ConversationResponseType,
  SolutionStatus,
  type CadArtifactMessage,
  type CodeArtifactMessage,
  type CodeRun,
  type SolutionCardMessage,
} from "@zhangwen/contracts";
import { describe, expect, it, vi } from "vitest";
import { ConversationResponseCard } from "../components/chat/ConversationResponseCard";

describe("结构化代码产物卡", () => {
  it("显示服务端代码版本与文件，并从主对话打开代码浮窗", () => {
    const onOpenArtifact = vi.fn();
    const payload: CodeArtifactMessage = {
      type: ConversationResponseType.CODE_ARTIFACT,
      codeRunId: "code_2",
      artifactId: "artifact_code_1",
      artifactVersionId: "artifact_version_2",
      version: 2,
      status: CodeRunStatus.DRAFT,
      runtime: CodeRuntime.MICROPYTHON,
      entrypoint: "src/main.py",
      title: "MicroPython 工程代码",
      summary: "用户保存的屏幕绘制版本",
      files: [
        { path: "src/main.py", language: "python" },
        { path: "README.md", language: "markdown" },
      ],
    };

    render(
      <ConversationResponseCard
        messageId="message_1"
        payload={payload}
        onClarificationDraftChange={vi.fn()}
        onSubmitClarification={vi.fn()}
        onAction={vi.fn()}
        onOpenSolutionArtifact={onOpenArtifact}
      />,
    );

    const card = screen.getByTestId("code-artifact-card");
    expect(within(card).getByText("版本 v2 · 草稿")).toBeInTheDocument();
    expect(within(card).getByText("src/main.py")).toBeInTheDocument();
    fireEvent.click(within(card).getByRole("button", { name: "打开代码编辑器" }));
    expect(onOpenArtifact).toHaveBeenCalledWith("artifact_code_1", "artifact_version_2");
  });

  it("代码编辑保存新版本后同步中央代码卡片并打开最新产物版本", () => {
    const onOpenArtifact = vi.fn();
    const payload: CodeArtifactMessage = {
      type: ConversationResponseType.CODE_ARTIFACT,
      codeRunId: "code_1",
      artifactId: "artifact_code_1",
      artifactVersionId: "artifact_version_1",
      version: 1,
      status: CodeRunStatus.READY_FOR_REVIEW,
      runtime: CodeRuntime.MICROPYTHON,
      entrypoint: "src/main.py",
      title: "MicroPython 工程代码",
      summary: "智能工程师生成的初始版本",
      files: [{ path: "src/main.py", language: "python" }],
    };
    const currentCodeRun: CodeRun = {
      id: "code_2",
      projectId: "prj_1",
      specRunId: "spec_1",
      version: 2,
      status: CodeRunStatus.DRAFT,
      runtime: CodeRuntime.MICROPYTHON,
      entrypoint: "src/main.py",
      workspaceRoot: "workspace://prj_1/code/v2",
      maxRetries: 2,
      retries: 0,
      files: [
        {
          id: "code_file_2",
          codeRunId: "code_2",
          projectId: "prj_1",
          kind: "MAIN",
          path: "src/main.py",
          language: "python",
          content: "print('updated')\n",
          createdAt: "2026-07-18T00:00:00Z",
        },
        {
          id: "code_file_config_2",
          codeRunId: "code_2",
          projectId: "prj_1",
          kind: "CONFIG",
          path: "src/config.py",
          language: "python",
          content: "UPDATED = True\n",
          createdAt: "2026-07-18T00:00:00Z",
        },
      ],
      patch: {
        id: "patch_2",
        codeRunId: "code_2",
        projectId: "prj_1",
        baseSnapshotId: "code_1",
        summary: "用户调整了主控显示逻辑",
        diff: "+print('updated')",
        createdAt: "2026-07-18T00:00:00Z",
      },
      testResult: {
        ok: false,
        command: "not-run-user-edit",
        output: "等待验证",
        createdAt: "2026-07-18T00:00:00Z",
        checks: [],
      },
      artifactId: "artifact_code_1",
      artifactVersionId: "artifact_version_2",
      hardwareSolutionVersion: 1,
      bomVersion: 1,
      ioMapVersion: 1,
      generatedByExpertId: "expert_smart",
      staleReason: null,
      createdAt: "2026-07-18T00:00:00Z",
      updatedAt: "2026-07-18T00:00:00Z",
      acceptedAt: null,
      revisionSource: "USER",
      requiresValidation: true,
    };

    render(
      <ConversationResponseCard
        messageId="message_1"
        payload={payload}
        currentCodeRun={currentCodeRun}
        onClarificationDraftChange={vi.fn()}
        onSubmitClarification={vi.fn()}
        onAction={vi.fn()}
        onOpenSolutionArtifact={onOpenArtifact}
      />,
    );

    const card = screen.getByTestId("code-artifact-card");
    expect(within(card).getByText("版本 v2 · 草稿")).toBeInTheDocument();
    expect(within(card).getByText("用户调整了主控显示逻辑")).toBeInTheDocument();
    expect(within(card).getByText("src/config.py")).toBeInTheDocument();
    fireEvent.click(within(card).getByRole("button", { name: "打开代码编辑器" }));
    expect(onOpenArtifact).toHaveBeenCalledWith("artifact_code_1", "artifact_version_2");
  });

  it("中央方案卡保持紧凑并把完整方案统一打开到产物浮窗", () => {
    const onOpenArtifact = vi.fn();
    const onAction = vi.fn();
    const payload: SolutionCardMessage = {
      type: ConversationResponseType.SOLUTION_CARD,
      solutionId: "solution_1",
      artifactId: "artifact_solution_1",
      artifactVersionId: "artifact_version_solution_1",
      version: 1,
      status: SolutionStatus.DRAFT,
      title: "推荐实现方案",
      summary: "使用 K10、环境传感器和本地提醒逻辑完成课堂作品。",
      sections: [
        { id: "goal", title: "项目目标", content: "完整目标内容" },
        { id: "hardware", title: "硬件组成", content: "完整硬件内容" },
      ],
      changeSummary: ["核心硬件已调整"],
      actions: [
        {
          id: "view",
          label: "查看完整方案",
          action: ConversationActionType.VIEW_SOLUTION,
        },
        {
          id: "proposal",
          label: "生成立项书",
          action: ConversationActionType.CONFIRM_SOLUTION_AND_GENERATE_PROJECT_PROPOSAL,
        },
        {
          id: "lesson",
          label: "生成教案版本",
          action: ConversationActionType.CONFIRM_SOLUTION_AND_GENERATE_LESSON_VERSION,
        },
      ],
    };

    render(
      <ConversationResponseCard
        messageId="message_solution"
        payload={payload}
        onClarificationDraftChange={vi.fn()}
        onSubmitClarification={vi.fn()}
        onAction={onAction}
        onOpenSolutionArtifact={onOpenArtifact}
      />,
    );

    const card = screen.getByTestId("solution-card");
    expect(within(card).getByText(payload.summary)).toBeInTheDocument();
    expect(within(card).queryByText("完整目标内容")).not.toBeInTheDocument();
    expect(within(card).queryByText("核心硬件已调整")).not.toBeInTheDocument();
    expect(within(card).queryByRole("button", { name: /展开完整方案/ }))
      .not.toBeInTheDocument();

    fireEvent.click(within(card).getByRole("button", { name: "查看完整方案" }));
    expect(onOpenArtifact).toHaveBeenCalledWith(
      "artifact_solution_1",
      "artifact_version_solution_1",
    );
    expect(onAction).not.toHaveBeenCalled();

    expect(within(card).getByRole("button", { name: "生成立项书" })).toBeInTheDocument();
    fireEvent.click(within(card).getByRole("button", { name: "生成教案版本" }));
    expect(onAction).toHaveBeenCalledWith(
      "message_solution",
      expect.objectContaining({
        action: ConversationActionType.CONFIRM_SOLUTION_AND_GENERATE_LESSON_VERSION,
      }),
    );
  });

  it("Creator 会隐藏历史消息中的重复确认和立项书动作", () => {
    const payload: SolutionCardMessage = {
      type: ConversationResponseType.SOLUTION_CARD,
      solutionId: "legacy_solution",
      artifactId: "legacy_artifact",
      artifactVersionId: "legacy_version",
      version: 1,
      status: SolutionStatus.DRAFT,
      title: "历史推荐方案",
      summary: "历史消息仍可查看，但不再承担 Creator 的确认入口。",
      sections: [],
      actions: [
        {
          id: "confirm",
          label: "确认方案",
          action: ConversationActionType.CONFIRM_SOLUTION,
        },
        {
          id: "book",
          label: "生成立项书",
          action: ConversationActionType.GENERATE_PROJECT_PROPOSAL,
        },
        {
          id: "continue",
          label: "继续补充需求",
          action: ConversationActionType.CONTINUE_CLARIFICATION,
        },
        {
          id: "view",
          label: "查看完整方案",
          action: ConversationActionType.VIEW_SOLUTION,
        },
      ],
    };

    render(
      <ConversationResponseCard
        messageId="legacy_message"
        payload={payload}
        creatorWorkflow
        onClarificationDraftChange={vi.fn()}
        onSubmitClarification={vi.fn()}
        onAction={vi.fn()}
      />,
    );

    const card = screen.getByTestId("solution-card");
    expect(within(card).queryByRole("button", { name: "确认方案" })).not.toBeInTheDocument();
    expect(within(card).queryByRole("button", { name: "生成立项书" })).not.toBeInTheDocument();
    expect(within(card).queryByRole("button", { name: "继续补充需求" })).not.toBeInTheDocument();
    expect(within(card).getByRole("button", { name: "查看完整方案" })).toBeInTheDocument();
  });

  it("普通模式的代码与 3D 结果只保留摘要和一个查看动作", () => {
    const onOpenArtifact = vi.fn();
    const commonProps = {
      onClarificationDraftChange: vi.fn(),
      onSubmitClarification: vi.fn(),
      onAction: vi.fn(),
      onOpenSolutionArtifact: onOpenArtifact,
      professionalMode: false,
    };
    const codePayload: CodeArtifactMessage = {
      type: ConversationResponseType.CODE_ARTIFACT,
      codeRunId: "code_simple",
      artifactId: "artifact_code_simple",
      artifactVersionId: "artifact_version_code_simple",
      version: 7,
      status: CodeRunStatus.READY_FOR_REVIEW,
      runtime: CodeRuntime.MICROPYTHON,
      entrypoint: "src/main.py",
      title: "MicroPython 工程代码",
      summary: "已按当前方案准备板载摄像头与相册展示逻辑。",
      files: [{ path: "src/main.py", language: "python" }],
    };
    const cadPayload: CadArtifactMessage = {
      type: ConversationResponseType.CAD_ARTIFACT,
      cadRunId: "cad_simple",
      artifactId: "artifact_cad_simple",
      artifactVersionId: "artifact_version_cad_simple",
      version: 3,
      status: CadRunStatus.DRAFT,
      title: "电子相册外壳",
      summary: "已按模板生成带屏幕开口和支撑结构的可编辑模型。",
    };

    const { rerender } = render(
      <ConversationResponseCard
        messageId="message_code_simple"
        payload={codePayload}
        {...commonProps}
      />,
    );
    let card = screen.getByTestId("code-artifact-card");
    expect(within(card).getByText("代码准备好了")).toBeInTheDocument();
    expect(within(card).getByRole("button", { name: "查看代码" })).toBeInTheDocument();
    expect(within(card).queryByText(/版本 v7/)).not.toBeInTheDocument();
    expect(within(card).queryByText("src/main.py")).not.toBeInTheDocument();

    rerender(
      <ConversationResponseCard
        messageId="message_cad_simple"
        payload={cadPayload}
        {...commonProps}
      />,
    );
    card = screen.getByTestId("cad-artifact-card");
    expect(within(card).getByText("3D 模型准备好了")).toBeInTheDocument();
    expect(within(card).getByRole("button", { name: "查看 3D" })).toBeInTheDocument();
    expect(within(card).queryByText(/版本 v3/)).not.toBeInTheDocument();
  });
});
