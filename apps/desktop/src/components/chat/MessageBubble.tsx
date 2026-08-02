import { memo } from "react";
import {
  ChatMessageStatus,
  ChatRole,
  ConversationResponseType,
  type ChatMessage,
  type ChatProgress,
  type ClarificationAnswer,
  type ConversationAction,
  type ConversationClarificationQuestion,
  type CodeRun,
  type ProjectWorkspace,
} from "@zhangwen/contracts";
import { MessageMarkdown } from "./MessageMarkdown";
import { ConversationResponseCard } from "./ConversationResponseCard";
import { MessageRecoveryPanel } from "./MessageRecoveryPanel";
import { MessageActionProgress } from "./MessageActionProgress";
import {
  MAX_AUTOMATIC_LOCAL_RECOVERY_ATTEMPTS,
  hasAutomaticRecoveryForMessage,
  isAutomaticLocalRecoveryExhausted,
  findRecoverySourceMessage,
} from "../../hooks/useAutomaticRecovery";

export interface ExpertPresentation {
  name: string;
  glyph: string;
  semanticType: string;
}

interface MessageBubbleProps {
  message: ChatMessage;
  expert: ExpertPresentation;
  workspace: ProjectWorkspace;
  streaming: boolean;
  progress: ChatProgress[];
  answeredCards: Record<string, boolean>;
  clarificationDraft: Record<string, ClarificationAnswer>;
  automaticRecoveryCandidateId: string | null;
  messages: ChatMessage[];
  expertConversations: { projectExpertId: string; id: string; expertType: string }[];
  engineeringCodeRun: CodeRun | null;
  professionalMode: boolean;
  creatorWorkflow?: boolean;
  onClarificationDraftChange: (messageId: string, answer: ClarificationAnswer) => void;
  onSubmitClarification: (messageId: string, questions: ConversationClarificationQuestion[]) => void;
  onAction: (messageId: string, action: ConversationAction) => void;
  onRecoveryAction: (message: ChatMessage, actionId: string) => void;
  onOpenSolutionArtifact: (artifactId?: string | null, versionId?: string | null) => void;
  onOpenHardwareSelection?: () => void;
  onImportPython?: (messageId: string) => void;
  onRetryKickoff?: () => void;
}

/**
 * Renders a single chat message bubble with avatar, expert name, content,
 * progress indicators, error recovery, and structured payload cards.
 * Memoized to avoid re-rendering unchanged messages during streaming.
 */
export const MessageBubble = memo(function MessageBubble({
  message: msg,
  expert,
  workspace,
  streaming,
  progress: messageProgress,
  answeredCards,
  clarificationDraft,
  automaticRecoveryCandidateId,
  messages,
  expertConversations,
  engineeringCodeRun,
  professionalMode,
  creatorWorkflow = false,
  onClarificationDraftChange,
  onSubmitClarification,
  onAction,
  onRecoveryAction,
  onOpenSolutionArtifact,
  onOpenHardwareSelection,
  onImportPython,
  onRetryKickoff,
}: MessageBubbleProps) {
  const isAssistant = msg.role === ChatRole.ASSISTANT;

  // Recovery event (user message that is a retry)
  if (!isAssistant && msg.metadata?.recoveryOfMessageId) {
    if (!professionalMode) return null;
    return (
      <div className="message-recovery-event" role="status">
        <strong>{msg.metadata.recoveryLabel ?? "已按原需求重新生成"}</strong>
        <span>原需求、已确认参数和专家上下文均已保留</span>
      </div>
    );
  }

  // Automatic handoff event
  if (!isAssistant && msg.metadata?.automaticHandoff) {
    if (!professionalMode) return null;
    return (
      <div className="expert-handoff-event" role="status">
        <strong>{msg.metadata.handoffLabel ?? "已完成专家交接"}</strong>
        <span>接收方将基于已确认立项书继续</span>
      </div>
    );
  }

  const isGenerating =
    isAssistant &&
    msg.status === ChatMessageStatus.STREAMING &&
    !msg.content &&
    messageProgress.length === 0;
  const isKickoffMessage = msg.id === workspace.kickoff?.assistantMessageId;
  const kickoffPlaceholder =
    isKickoffMessage &&
    msg.status === ChatMessageStatus.READY
      ? "正在分析项目创意..."
      : "";
  const isAutomaticRecoveryPending = automaticRecoveryCandidateId === msg.id;
  const wasAutomaticallyRecovered = hasAutomaticRecoveryForMessage(messages, msg.id);
  const automaticRecoveryExhausted = isAutomaticLocalRecoveryExhausted(
    messages,
    msg,
    expertConversations as never[],
  );

  return (
    <div
      className={`chat-message chat-message-${msg.role}`}
      data-expert-type={isAssistant ? expert.semanticType : undefined}
    >
      {isAssistant && (
        <span
          className="message-avatar"
          role="img"
          aria-label={`${expert.name}头像`}
        >
          {expert.glyph}
        </span>
      )}
      <div className="message-body">
        <span className="message-role">
          {isAssistant ? expert.name : "你"}
        </span>
        {(msg.content || kickoffPlaceholder) && (
          <MessageMarkdown
            messageId={msg.id}
            content={msg.content || kickoffPlaceholder}
            onImportPython={isAssistant ? onImportPython : undefined}
          />
        )}
        {isGenerating && (
          <div
            className="message-generation-status"
            role="status"
            aria-live="polite"
            aria-label={`${expert.name}正在生成回复`}
          >
            <span>{expert.name}正在生成回复</span>
            <span className="message-generation-dots" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
          </div>
        )}
        {isAssistant &&
          msg.status === ChatMessageStatus.STREAMING &&
          messageProgress.length > 0 && (
            <MessageActionProgress
              expertName={expert.name}
              progress={messageProgress}
              professionalMode={professionalMode}
            />
          )}
        {msg.error && (
          isKickoffMessage
            ? <p className="message-error">{msg.error.message}</p>
            : isAutomaticRecoveryPending || wasAutomaticallyRecovered
              ? (
                professionalMode ? (
                  <p
                    className="message-recovery-auto"
                    role="status"
                    aria-live="polite"
                  >
                    {wasAutomaticallyRecovered
                      ? "本次生成未通过本地校验，已按原需求自动重试。"
                      : "本次生成未通过本地校验，正在按原需求自动重试。"}
                  </p>
                ) : null
              )
            : automaticRecoveryExhausted
              ? (
                <p
                  className="message-recovery-auto"
                  role="status"
                  aria-live="polite"
                >
                  {`已自动按原需求重试 ${MAX_AUTOMATIC_LOCAL_RECOVERY_ATTEMPTS} 次，仍未通过本地校验。系统已停止自动请求以避免重复调用；原需求仍保留，可在下方补充要求后继续。`}
                </p>
              )
            : (
              <MessageRecoveryPanel
                error={msg.error}
                disabled={streaming}
                canRecover={findRecoverySourceMessage(messages, msg) !== null}
                onAction={(actionId) => onRecoveryAction(msg, actionId)}
              />
            )
        )}
        {isKickoffMessage &&
          (workspace.kickoff?.retryable || workspace.kickoff?.status === "READY") &&
          (msg.status === ChatMessageStatus.FAILED ||
            msg.status === ChatMessageStatus.CANCELED) && (
            <button
              type="button"
              className="secondary-btn"
              onClick={onRetryKickoff}
            >
              重试分析
            </button>
          )}
        {msg.structuredPayload &&
          msg.structuredPayload.type !==
            ConversationResponseType.CLARIFICATION && (
            <ConversationResponseCard
              messageId={msg.id}
              payload={msg.structuredPayload}
              disabled={streaming}
              locallyAnsweredQuestionIds={answeredCards}
              clarificationDraft={clarificationDraft}
              onClarificationDraftChange={onClarificationDraftChange}
              onSubmitClarification={onSubmitClarification}
              onAction={onAction}
              onOpenSolutionArtifact={onOpenSolutionArtifact}
              onOpenHardwareSelection={onOpenHardwareSelection}
              currentCodeRun={engineeringCodeRun}
              professionalMode={professionalMode}
              creatorWorkflow={creatorWorkflow}
            />
          )}
      </div>
    </div>
  );
});
