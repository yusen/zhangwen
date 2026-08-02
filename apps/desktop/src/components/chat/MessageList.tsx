import { memo } from "react";
import {
  type ChatMessage,
  type ChatProgress,
  type ClarificationAnswer,
  type ConversationAction,
  type ConversationClarificationQuestion,
  type CodeRun,
  type ProjectWorkspace,
} from "@zhangwen/contracts";
import { MessageBubble, type ExpertPresentation } from "./MessageBubble";

interface MessageListProps {
  messages: ChatMessage[];
  workspace: ProjectWorkspace;
  streaming: boolean;
  progressByMessageId: Record<string, ChatProgress[]>;
  answeredCards: Record<string, boolean>;
  clarificationDrafts: Record<string, Record<string, ClarificationAnswer>>;
  clarificationDraftKeyPrefix: string;
  automaticRecoveryCandidateId: string | null;
  expertConversations: { projectExpertId: string; id: string; expertType: string }[];
  engineeringCodeRun: CodeRun | null;
  professionalMode: boolean;
  creatorWorkflow?: boolean;
  getExpertPresentation: (message: ChatMessage) => ExpertPresentation;
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
 * Renders the ordered list of project messages.
 * Each message is rendered via MessageBubble which is individually memoized.
 * Extracted from CenterChat to isolate message list rendering.
 */
export const MessageList = memo(function MessageList({
  messages,
  workspace,
  streaming,
  progressByMessageId,
  answeredCards,
  clarificationDrafts,
  clarificationDraftKeyPrefix,
  automaticRecoveryCandidateId,
  expertConversations,
  engineeringCodeRun,
  professionalMode,
  creatorWorkflow = false,
  getExpertPresentation,
  onClarificationDraftChange,
  onSubmitClarification,
  onAction,
  onRecoveryAction,
  onOpenSolutionArtifact,
  onOpenHardwareSelection,
  onImportPython,
  onRetryKickoff,
}: MessageListProps) {
  return (
    <>
      {messages.map((msg) => (
        <MessageBubble
          key={msg.id}
          message={msg}
          expert={getExpertPresentation(msg)}
          workspace={workspace}
          streaming={streaming}
          progress={progressByMessageId[msg.id] ?? []}
          answeredCards={answeredCards}
          clarificationDraft={
            clarificationDrafts[`${clarificationDraftKeyPrefix}:${msg.id}`] ?? {}
          }
          automaticRecoveryCandidateId={automaticRecoveryCandidateId}
          messages={messages}
          expertConversations={expertConversations}
          engineeringCodeRun={engineeringCodeRun}
          professionalMode={professionalMode}
          creatorWorkflow={creatorWorkflow}
          onClarificationDraftChange={onClarificationDraftChange}
          onSubmitClarification={onSubmitClarification}
          onAction={onAction}
          onRecoveryAction={onRecoveryAction}
          onOpenSolutionArtifact={onOpenSolutionArtifact}
          onOpenHardwareSelection={onOpenHardwareSelection}
          onImportPython={onImportPython}
          onRetryKickoff={onRetryKickoff}
        />
      ))}
    </>
  );
});
