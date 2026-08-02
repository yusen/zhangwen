import { memo } from "react";
import {
  ConversationResponseType,
  type ChatMessage,
  type ClarificationAnswer,
  type ConversationAction,
  type ConversationClarificationQuestion,
} from "@zhangwen/contracts";
import { ConversationResponseCard } from "./ConversationResponseCard";

interface ClarificationDockProps {
  message: ChatMessage;
  streaming: boolean;
  professionalMode: boolean;
  answeredCards: Record<string, boolean>;
  clarificationDraft: Record<string, ClarificationAnswer>;
  onClarificationDraftChange: (messageId: string, answer: ClarificationAnswer) => void;
  onSubmitClarification: (messageId: string, questions: ConversationClarificationQuestion[]) => void;
  onAction: (messageId: string, action: ConversationAction) => void;
  onOpenSolutionArtifact: (artifactId?: string | null, versionId?: string | null) => void;
  onOpenHardwareSelection?: () => void;
}

/**
 * Sticky bottom dock that displays the latest pending clarification card
 * above the input area. Only renders when there is an active clarification
 * payload of type CLARIFICATION.
 * Extracted from CenterChat to isolate clarification dock rendering.
 */
export const ClarificationDock = memo(function ClarificationDock({
  message,
  streaming,
  professionalMode,
  answeredCards,
  clarificationDraft,
  onClarificationDraftChange,
  onSubmitClarification,
  onAction,
  onOpenSolutionArtifact,
  onOpenHardwareSelection,
}: ClarificationDockProps) {
  const payload = message.structuredPayload;
  if (payload?.type !== ConversationResponseType.CLARIFICATION) return null;

  return (
    <section
      className="clarification-dock"
      role="region"
      aria-label="待完成需求澄清"
      data-source-message-id={message.id}
    >
      <ConversationResponseCard
        key={message.id}
        messageId={message.id}
        payload={payload}
        disabled={streaming}
        locallyAnsweredQuestionIds={answeredCards}
        clarificationDraft={clarificationDraft}
        onClarificationDraftChange={onClarificationDraftChange}
        onSubmitClarification={onSubmitClarification}
        onAction={onAction}
        onOpenSolutionArtifact={onOpenSolutionArtifact}
        onOpenHardwareSelection={onOpenHardwareSelection}
        professionalMode={professionalMode}
      />
    </section>
  );
});
