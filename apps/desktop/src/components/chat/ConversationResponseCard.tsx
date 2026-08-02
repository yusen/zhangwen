import { useEffect, useState } from "react";
import {
  ClarificationQuestionMode,
  ConversationActionType,
  ConversationResponseType,
  CadRunStatus,
  CodeRunStatus,
  SolutionStatus,
  type ClarificationAnswer,
  type ClarificationOption,
  type CadArtifactMessage,
  type CodeArtifactMessage,
  type CodeRun,
  type ConversationAction,
  type ConversationClarificationQuestion,
  type ConversationResponse,
  type HardwareSelectionResponse,
  type SolutionCardMessage,
} from "@zhangwen/contracts";

interface ConversationResponseCardProps {
  messageId: string;
  payload: ConversationResponse;
  disabled?: boolean;
  locallyAnsweredQuestionIds?: Record<string, boolean>;
  clarificationDraft?: Record<string, ClarificationAnswer>;
  onClarificationDraftChange: (
    messageId: string,
    answer: ClarificationAnswer
  ) => void;
  onSubmitClarification: (
    messageId: string,
    questions: ConversationClarificationQuestion[]
  ) => void;
  onAction: (messageId: string, action: ConversationAction) => void;
  onOpenSolutionArtifact?: (artifactId?: string | null, versionId?: string | null) => void;
  onOpenHardwareSelection?: () => void;
  currentCodeRun?: CodeRun | null;
  professionalMode?: boolean;
  creatorWorkflow?: boolean;
}

export function ConversationResponseCard({
  messageId,
  payload,
  disabled = false,
  locallyAnsweredQuestionIds = {},
  clarificationDraft = {},
  onClarificationDraftChange,
  onSubmitClarification,
  onAction,
  onOpenSolutionArtifact,
  onOpenHardwareSelection,
  currentCodeRun = null,
  professionalMode = true,
  creatorWorkflow = false,
}: ConversationResponseCardProps) {
  if (payload.type === ConversationResponseType.CLARIFICATION) {
    const questions = payload.questions?.length ? payload.questions : [payload.question];
    return (
      <ClarificationGroupCard
        messageId={messageId}
        questions={questions}
        completeness={payload.completeness}
        disabled={disabled}
        locallyAnsweredQuestionIds={locallyAnsweredQuestionIds}
        draft={clarificationDraft}
        onDraftChange={onClarificationDraftChange}
        onSubmit={onSubmitClarification}
        professionalMode={professionalMode}
      />
    );
  }

  if (
    payload.type === ConversationResponseType.SOLUTION_CARD
  ) {
    return (
      <SolutionCard
        payload={payload}
        messageId={messageId}
        disabled={disabled}
        onAction={onAction}
        onOpenArtifact={onOpenSolutionArtifact}
        professionalMode={professionalMode}
        creatorWorkflow={creatorWorkflow}
      />
    );
  }

  if (payload.type === ConversationResponseType.CODE_ARTIFACT) {
    return (
      <CodeArtifactCard
        payload={currentCodeArtifactPayload(payload, currentCodeRun)}
        disabled={disabled}
        onOpenArtifact={onOpenSolutionArtifact}
        professionalMode={professionalMode}
      />
    );
  }

  if (payload.type === ConversationResponseType.CAD_ARTIFACT) {
    return (
      <CadArtifactCard
        payload={payload}
        disabled={disabled}
        onOpenArtifact={onOpenSolutionArtifact}
        professionalMode={professionalMode}
      />
    );
  }

  if (payload.type === ConversationResponseType.HARDWARE_SELECTION) {
    return (
      <HardwareSelectionCard
        payload={payload}
        disabled={disabled}
        onOpen={onOpenHardwareSelection}
      />
    );
  }

  if (
    payload.type === ConversationResponseType.NEXT_ACTION ||
    payload.type === ConversationResponseType.SOLUTION ||
    payload.type === ConversationResponseType.PROPOSAL_ACTION
  ) {
    return (
      <ActionCard
        messageId={messageId}
        actions={payload.actions}
        disabled={disabled}
        onAction={onAction}
        professionalMode={professionalMode}
        creatorWorkflow={creatorWorkflow}
      />
    );
  }

  if (payload.type === ConversationResponseType.SYSTEM_NOTICE && payload.actions?.length) {
    return (
      <ActionCard
        messageId={messageId}
        actions={payload.actions}
        disabled={disabled}
        onAction={onAction}
        professionalMode={professionalMode}
        creatorWorkflow={creatorWorkflow}
      />
    );
  }

  return null;
}

function HardwareSelectionCard({
  payload,
  disabled,
  onOpen,
}: {
  payload: HardwareSelectionResponse;
  disabled: boolean;
  onOpen?: () => void;
}) {
  return (
    <article className="hardware-gap-chat-card" data-testid="hardware-selection-card">
      <header>
        <span aria-hidden="true">＋</span>
        <div>
          <h3>硬件待补充</h3>
          <p>{payload.summary}</p>
        </div>
      </header>
      <strong>当前规划还需要：</strong>
      <ul>
        {payload.missingCapabilities.map((capability) => (
          <li key={capability}>{capability}</li>
        ))}
      </ul>
      <button
        type="button"
        className="conversation-action"
        disabled={disabled || !onOpen}
        onClick={onOpen}
      >
        选择并添加电子器件
      </button>
    </article>
  );
}

const SOLUTION_STATUS_LABELS: Record<string, string> = {
  [SolutionStatus.DRAFT]: "待确认",
  [SolutionStatus.CONFIRMED]: "已确认",
  [SolutionStatus.SUPERSEDED]: "历史版本",
  [SolutionStatus.OUTDATED]: "已过期",
};

const CODE_STATUS_LABELS: Record<string, string> = {
  [CodeRunStatus.DRAFT]: "草稿",
  [CodeRunStatus.TESTING]: "验证中",
  [CodeRunStatus.READY_FOR_REVIEW]: "待确认",
  [CodeRunStatus.ACCEPTED]: "已接受",
  [CodeRunStatus.STALE]: "已过期",
  [CodeRunStatus.REJECTED]: "已退回",
  [CodeRunStatus.ROLLED_BACK]: "已回滚",
  [CodeRunStatus.FAILED]: "失败",
};

const CAD_STATUS_LABELS: Record<string, string> = {
  [CadRunStatus.DRAFT]: "草稿",
  [CadRunStatus.QUEUED]: "等待建模",
  [CadRunStatus.RUNNING]: "建模中",
  [CadRunStatus.VALIDATED]: "已校验",
  [CadRunStatus.READY_FOR_REVIEW]: "待确认",
  [CadRunStatus.APPROVED]: "已确认",
  [CadRunStatus.REJECTED]: "已退回",
  [CadRunStatus.STALE]: "已过期",
  [CadRunStatus.CANCELED]: "已取消",
  [CadRunStatus.FAILED]: "生成失败",
};

const ORDINARY_ADVANCE_ACTIONS = new Set<string>([
  ConversationActionType.GENERATE_SOLUTION,
  ConversationActionType.USE_RECOMMENDED_DEFAULTS,
  ConversationActionType.CONFIRM_SOLUTION,
  ConversationActionType.ACCEPT_SOLUTION_REVISION,
  ConversationActionType.GENERATE_PROJECT_PROPOSAL,
  ConversationActionType.CONFIRM_SOLUTION_AND_GENERATE_PROJECT_PROPOSAL,
  ConversationActionType.GENERATE_LESSON_VERSION,
  ConversationActionType.CONFIRM_SOLUTION_AND_GENERATE_LESSON_VERSION,
  ConversationActionType.CONFIRM_PROJECT_PROPOSAL,
  ConversationActionType.CONTINUE_PROJECT_IMPLEMENTATION,
]);

const CREATOR_DEPRECATED_CHAT_ACTIONS = new Set<string>([
  ConversationActionType.GENERATE_SOLUTION,
  ConversationActionType.USE_RECOMMENDED_DEFAULTS,
  ConversationActionType.CONTINUE_CLARIFICATION,
  ConversationActionType.CONFIRM_SOLUTION,
  ConversationActionType.ACCEPT_SOLUTION_REVISION,
  ConversationActionType.GENERATE_PROJECT_PROPOSAL,
  ConversationActionType.CONFIRM_SOLUTION_AND_GENERATE_PROJECT_PROPOSAL,
  ConversationActionType.GENERATE_LESSON_VERSION,
  ConversationActionType.CONFIRM_SOLUTION_AND_GENERATE_LESSON_VERSION,
  ConversationActionType.CONFIRM_PROJECT_PROPOSAL,
  ConversationActionType.CONTINUE_PROJECT_IMPLEMENTATION,
  ConversationActionType.VIEW_PROJECT_PROPOSAL,
]);

function creatorVisibleActions(
  actions: ConversationAction[],
  creatorWorkflow: boolean,
): ConversationAction[] {
  return creatorWorkflow
    ? actions.filter((action) => !CREATOR_DEPRECATED_CHAT_ACTIONS.has(action.action))
    : actions;
}

function ordinaryPrimaryAction(
  actions: ConversationAction[],
): ConversationAction | undefined {
  return (
    actions.find((action) => action.recommended && !action.disabled) ??
    actions.find(
      (action) =>
        !action.disabled && ORDINARY_ADVANCE_ACTIONS.has(action.action),
    ) ??
    actions.find((action) => !action.disabled) ??
    actions[0]
  );
}

function CadArtifactCard({
  payload,
  disabled,
  onOpenArtifact,
  professionalMode,
}: {
  payload: CadArtifactMessage;
  disabled: boolean;
  onOpenArtifact?: (artifactId?: string | null, versionId?: string | null) => void;
  professionalMode: boolean;
}) {
  const statusLabel = CAD_STATUS_LABELS[payload.status] ?? payload.status;
  return (
    <article
      className="cad-artifact-chat-card"
      data-display-mode={professionalMode ? "professional" : "simple"}
      data-testid="cad-artifact-card"
    >
      <header>
        <div>
          <h3>{professionalMode ? payload.title : "3D 模型准备好了"}</h3>
          {professionalMode && <p>版本 v{payload.version} · {statusLabel}</p>}
        </div>
        {professionalMode && <span>{statusLabel}</span>}
      </header>
      <p>{payload.summary}</p>
      <button
        type="button"
        disabled={disabled || !payload.artifactId || !payload.artifactVersionId}
        onClick={() => onOpenArtifact?.(payload.artifactId, payload.artifactVersionId)}
      >
        {professionalMode ? "打开 3D 模型" : "查看 3D"}
      </button>
    </article>
  );
}

function CodeArtifactCard({
  payload,
  disabled,
  onOpenArtifact,
  professionalMode,
}: {
  payload: CodeArtifactMessage;
  disabled: boolean;
  onOpenArtifact?: (artifactId?: string | null, versionId?: string | null) => void;
  professionalMode: boolean;
}) {
  const statusLabel = CODE_STATUS_LABELS[payload.status] ?? payload.status;
  return (
    <article
      className="code-artifact-chat-card"
      data-display-mode={professionalMode ? "professional" : "simple"}
      data-testid="code-artifact-card"
    >
      <header>
        <div>
          <h3>{professionalMode ? payload.title : "代码准备好了"}</h3>
          {professionalMode && <p>版本 v{payload.version} · {statusLabel}</p>}
        </div>
        {professionalMode && <span>{statusLabel}</span>}
      </header>
      <p>{payload.summary}</p>
      {professionalMode && (
        <>
          <ul aria-label="代码文件列表">
            {payload.files.map((file) => (
              <li key={file.path}>
                <code>{file.path}</code>
                <span>{file.language}</span>
              </li>
            ))}
          </ul>
          <p className="code-visibility-note">
            未保存修改仅保留在编辑器；保存后此卡片同步更新
          </p>
        </>
      )}
      <button
        type="button"
        disabled={disabled || !payload.artifactId}
        onClick={() => onOpenArtifact?.(payload.artifactId, payload.artifactVersionId)}
      >
        {professionalMode ? "打开代码编辑器" : "查看代码"}
      </button>
    </article>
  );
}

function currentCodeArtifactPayload(
  payload: CodeArtifactMessage,
  currentCodeRun: CodeRun | null,
): CodeArtifactMessage {
  if (
    !payload.artifactId ||
    !currentCodeRun?.artifactId ||
    currentCodeRun.artifactId !== payload.artifactId
  ) {
    return payload;
  }
  return {
    ...payload,
    codeRunId: currentCodeRun.id,
    artifactVersionId: currentCodeRun.artifactVersionId,
    version: currentCodeRun.version,
    status: currentCodeRun.status,
    runtime: currentCodeRun.runtime,
    entrypoint: currentCodeRun.entrypoint,
    summary: currentCodeRun.patch.summary,
    files: currentCodeRun.files.map((file) => ({
      path: file.path,
      language: file.language,
    })),
  };
}

function SolutionCard({
  payload,
  messageId,
  disabled,
  onAction,
  onOpenArtifact,
  professionalMode,
  creatorWorkflow,
}: {
  payload: SolutionCardMessage;
  messageId: string;
  disabled: boolean;
  onAction: (messageId: string, action: ConversationAction) => void;
  onOpenArtifact?: (artifactId?: string | null, versionId?: string | null) => void;
  professionalMode: boolean;
  creatorWorkflow: boolean;
}) {
  const statusLabel = SOLUTION_STATUS_LABELS[payload.status] ?? payload.status;
  const actions = creatorVisibleActions(payload.actions, creatorWorkflow);

  const handleAction = (action: ConversationAction) => {
    if (
      (action.action === ConversationActionType.VIEW_SOLUTION ||
        action.action === ConversationActionType.OPEN_SOLUTION_FLOATING) &&
      onOpenArtifact &&
      payload.artifactId
    ) {
      onOpenArtifact(payload.artifactId, payload.artifactVersionId);
      return;
    }
    onAction(messageId, action);
  };

  return (
    <article
      className="solution-chat-card"
      data-display-mode={professionalMode ? "professional" : "simple"}
      data-testid="solution-card"
    >
      <header className="solution-chat-header">
        <div>
          <h3>{payload.title}</h3>
          {professionalMode && (
            <p>
              方案 v{payload.version} · {statusLabel}
              {payload.basedOnVersion ? ` · 基于 v${payload.basedOnVersion}` : ""}
            </p>
          )}
        </div>
        {professionalMode && (
          <span className="solution-chat-badge">{statusLabel}</span>
        )}
      </header>

      <p className="solution-chat-summary">{payload.summary}</p>

      <div className="solution-card-actions" role="group" aria-label="方案操作">
        {(professionalMode
          ? actions
          : [ordinaryPrimaryAction(actions)].filter(
              (action): action is ConversationAction => Boolean(action),
            )
        ).map((action) => (
          <button
            key={action.id}
            type="button"
            className="conversation-action"
            onClick={() => handleAction(action)}
            disabled={disabled || action.disabled}
          >
            <strong>{action.label}</strong>
            {action.recommended && <em>掌问推荐</em>}
          </button>
        ))}
      </div>
    </article>
  );
}

interface ClarificationGroupCardProps {
  messageId: string;
  questions: ConversationClarificationQuestion[];
  completeness: number;
  disabled: boolean;
  locallyAnsweredQuestionIds: Record<string, boolean>;
  draft: Record<string, ClarificationAnswer>;
  onDraftChange: (
    messageId: string,
    answer: ClarificationAnswer
  ) => void;
  onSubmit: (
    messageId: string,
    questions: ConversationClarificationQuestion[]
  ) => void;
  professionalMode: boolean;
}

function ClarificationGroupCard({
  messageId,
  questions,
  completeness,
  disabled,
  locallyAnsweredQuestionIds,
  draft,
  onDraftChange,
  onSubmit,
  professionalMode,
}: ClarificationGroupCardProps) {
  const [activeQuestionIndex, setActiveQuestionIndex] = useState(() => {
    const firstPendingIndex = questions.findIndex(
      (question) =>
        question.required &&
        !question.answered &&
        !locallyAnsweredQuestionIds[`${messageId}:${question.id}`],
    );
    return firstPendingIndex >= 0 ? firstPendingIndex : 0;
  });
  useEffect(() => {
    const nextPendingIndex = questions.findIndex((question) => {
      const locallyAnswered = Boolean(
        locallyAnsweredQuestionIds[`${messageId}:${question.id}`],
      );
      return (
        !question.answered &&
        !locallyAnswered &&
        !isQuestionComplete(
          question,
          question.answer ?? draft[question.id],
          locallyAnswered,
        )
      );
    });
    if (nextPendingIndex >= 0) {
      setActiveQuestionIndex(nextPendingIndex);
    }
  }, [draft, locallyAnsweredQuestionIds, messageId, questions]);
  const requiredQuestions = questions.filter((question) => question.required);
  const requiredCount = requiredQuestions.length;
  const completedCount = requiredQuestions.filter((question) =>
    isQuestionComplete(
      question,
      question.answer ?? draft[question.id],
      Boolean(locallyAnsweredQuestionIds[`${messageId}:${question.id}`])
    )
  ).length;
  const submitted = requiredQuestions.every(
    (question) =>
      question.answered ||
      locallyAnsweredQuestionIds[`${messageId}:${question.id}`]
  );
  const canSubmit = requiredCount > 0 && completedCount === requiredCount;
  const progressPercent =
    requiredCount > 0 ? Math.round((completedCount / requiredCount) * 100) : 0;
  const safeQuestionIndex = Math.min(
    Math.max(activeQuestionIndex, 0),
    Math.max(questions.length - 1, 0),
  );
  const activeQuestion = questions[safeQuestionIndex];
  const activeAnswer = activeQuestion
    ? activeQuestion.answer ?? draft[activeQuestion.id]
    : undefined;
  const activeQuestionComplete = activeQuestion
    ? isQuestionComplete(
        activeQuestion,
        activeAnswer,
        Boolean(
          locallyAnsweredQuestionIds[`${messageId}:${activeQuestion.id}`],
        ),
      )
    : false;
  const isLastQuestion = safeQuestionIndex === questions.length - 1;

  if (!activeQuestion) return null;

  return (
    <article className="clarification-group-card" data-testid="clarification-group-card">
      {professionalMode && (
        <>
          <header className="clarification-group-header">
            <div className="clarification-group-title">
              <span className="clarification-type-tag">需求澄清</span>
              <strong>请确认当前关键问题</strong>
            </div>
            <span
              className={submitted ? "answered-badge" : "clarification-progress"}
              role="status"
              aria-live="polite"
            >
              {submitted ? "已提交" : `${completedCount}/${requiredCount} 已完成`}
            </span>
          </header>

          <div
            className="clarification-progress-track"
            role="progressbar"
            aria-label="澄清完成进度"
            aria-valuemin={0}
            aria-valuemax={requiredCount}
            aria-valuenow={completedCount}
            aria-valuetext={`${completedCount}/${requiredCount} 已完成`}
          >
            <span style={{ width: `${progressPercent}%` }} />
          </div>
          <p className="clarification-completeness">
            需求完整度 {completeness}%
          </p>
        </>
      )}

      <div className="clarification-question-list">
        <ClarificationQuestionRow
          key={activeQuestion.id}
          messageId={messageId}
          question={activeQuestion}
          index={safeQuestionIndex + 1}
          answer={activeAnswer}
          disabled={
            disabled ||
            submitted ||
            Boolean(
              activeQuestion.answered ||
              locallyAnsweredQuestionIds[`${messageId}:${activeQuestion.id}`]
            )
          }
          onChange={onDraftChange}
        />
      </div>

      <div className="clarification-group-navigation">
        {professionalMode && questions.length > 1 && (
          <button
            type="button"
            className="secondary-btn clarification-nav-button"
            onClick={() => setActiveQuestionIndex((current) => current - 1)}
            disabled={disabled || submitted || safeQuestionIndex === 0}
          >
            上一题
          </button>
        )}
        {professionalMode && questions.length > 1 && (
          <span className="clarification-question-position" aria-live="polite">
            第 {safeQuestionIndex + 1}/{questions.length} 题
          </span>
        )}
        {isLastQuestion ? (
          <button
            type="button"
            className="clarification-group-submit"
            onClick={() => onSubmit(messageId, questions)}
            disabled={disabled || submitted || !canSubmit}
          >
            {submitted ? "本轮回答已提交" : "提交选择"}
          </button>
        ) : professionalMode ? (
          <button
            type="button"
            className="primary-action clarification-nav-button"
            onClick={() => setActiveQuestionIndex((current) => current + 1)}
            disabled={
              disabled ||
              submitted ||
              (activeQuestion.required && !activeQuestionComplete)
            }
          >
            下一题
          </button>
        ) : null}
      </div>
    </article>
  );
}

function ClarificationQuestionRow({
  messageId,
  question,
  index,
  answer,
  disabled,
  onChange,
}: {
  messageId: string;
  question: ConversationClarificationQuestion;
  index: number;
  answer?: ClarificationAnswer;
  disabled: boolean;
  onChange: (messageId: string, answer: ClarificationAnswer) => void;
}) {
  const options = question.options ?? [];
  const selectedIds = answer?.selectedOptionIds ?? [];
  const selectedSet = new Set(selectedIds);
  const customActive = Boolean(
    answer && answer.selectedOptionIds.length === 0 && answer.textInput !== undefined
  );
  const answerLabel = formatQuestionAnswer(question, answer);

  const selectOption = (option: ClarificationOption) => {
    if (disabled) return;
    if (option.id === "custom") {
      onChange(messageId, {
        questionId: question.id,
        selectedOptionIds: [],
        textInput: "",
      });
      return;
    }
    const isMultiple = question.mode === ClarificationQuestionMode.MULTIPLE;
    const nextIds = isMultiple
      ? selectedSet.has(option.id)
        ? selectedIds.filter((id) => id !== option.id)
        : [...selectedIds, option.id]
      : [option.id];
    onChange(messageId, {
      questionId: question.id,
      selectedOptionIds: nextIds,
      usedRecommendation: option.recommended || undefined,
    });
  };

  const updateText = (textInput: string) => {
    onChange(messageId, {
      questionId: question.id,
      selectedOptionIds: [],
      textInput,
    });
  };

  return (
    <section
      className="clarification-question-row"
      data-testid={`clarification-question-${question.id}`}
    >
      <div className="clarification-question-title">
        <span>{index}</span>
        <p>{question.text}</p>
        {!question.required && <small>选填</small>}
      </div>

      {disabled && answerLabel ? (
        <p className="conversation-answer">你的选择：{answerLabel}</p>
      ) : null}

      {question.mode !== ClarificationQuestionMode.TEXT && (
        <div className="conversation-options" role="group" aria-label={question.text}>
          {options.map((option) => {
            const selected =
              option.id === "custom" ? customActive : selectedSet.has(option.id);
            const descriptionId = option.description
              ? `clarification-option-description-${messageId}-${question.id}-${option.id}`
              : undefined;
            return (
              <button
                key={option.id}
                type="button"
                className={`conversation-option ${selected ? "conversation-option-selected" : ""}`}
                aria-label={option.label}
                aria-describedby={descriptionId}
                aria-pressed={selected}
                onClick={() => selectOption(option)}
                disabled={disabled}
              >
                <span className="conversation-option-copy">
                  <strong>{option.label}</strong>
                  {option.description && (
                    <span
                      id={descriptionId}
                      className="conversation-option-description"
                    >
                      {option.description}
                    </span>
                  )}
                </span>
                {option.recommended && <em>掌问推荐</em>}
              </button>
            );
          })}
        </div>
      )}

      {(question.mode === ClarificationQuestionMode.TEXT || customActive) && !disabled && (
        <textarea
          className="clarification-custom-input"
          aria-label={`${question.text} 自定义回答`}
          value={answer?.textInput ?? ""}
          onChange={(event) => updateText(event.target.value)}
          rows={2}
          placeholder="请输入你的回答"
        />
      )}
    </section>
  );
}

function isQuestionComplete(
  question: ConversationClarificationQuestion,
  answer: ClarificationAnswer | undefined,
  locallyAnswered: boolean
): boolean {
  if (question.answered || locallyAnswered) return true;
  if (!answer) return false;
  return answer.selectedOptionIds.length > 0 || Boolean(answer.textInput?.trim());
}

function formatQuestionAnswer(
  question: ConversationClarificationQuestion,
  answer: ClarificationAnswer | undefined
): string | null {
  if (!answer) return null;
  const labels = (question.options ?? [])
    .filter((option) => answer.selectedOptionIds.includes(option.id))
    .map((option) => option.label);
  return labels.join("、") || answer.textInput?.trim() || null;
}

interface ActionCardProps {
  messageId: string;
  actions: ConversationAction[];
  disabled: boolean;
  onAction: (messageId: string, action: ConversationAction) => void;
  professionalMode: boolean;
  creatorWorkflow: boolean;
}

function ActionCard({
  messageId,
  actions,
  disabled,
  onAction,
  professionalMode,
  creatorWorkflow,
}: ActionCardProps) {
  const permittedActions = creatorVisibleActions(actions, creatorWorkflow);
  const visibleActions = professionalMode
    ? permittedActions
    : [ordinaryPrimaryAction(permittedActions)].filter(
        (action): action is ConversationAction => Boolean(action),
      );
  if (!visibleActions.length) return null;
  return (
    <div className="conversation-card" data-testid="conversation-action-card">
      <div className="conversation-actions" role="group" aria-label="下一步操作">
        {visibleActions.map((action) => (
          <button
            key={action.id}
            type="button"
            className="conversation-action"
            onClick={() => onAction(messageId, action)}
            disabled={disabled || action.disabled}
          >
            <strong>{action.label}</strong>
            {action.recommended && <em>掌问推荐</em>}
          </button>
        ))}
      </div>
    </div>
  );
}
