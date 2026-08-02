import { useEffect, useRef } from "react";
import {
  ChatMessageStatus,
  ChatRole,
  ExpertType,
  LLMErrorCode,
  type ChatMessage,
  type ExpertConversation,
  type LLMError,
} from "@zhangwen/contracts";

const AUTOMATIC_RECOVERY_LABEL = "已按原需求自动重试";
const MAX_AUTOMATIC_LOCAL_RECOVERY_ATTEMPTS = 3;

export { AUTOMATIC_RECOVERY_LABEL, MAX_AUTOMATIC_LOCAL_RECOVERY_ATTEMPTS };

interface UseAutomaticRecoveryOptions {
  messages: ChatMessage[];
  expertConversations: ExpertConversation[];
  configKeySaved: boolean;
  streaming: boolean;
  onRecovery: (message: ChatMessage, actionId: string, recoveryLabel?: string) => void;
}

/**
 * Detects LOCAL_OUTPUT_REJECTED failures from the smart engineer and
 * automatically retries up to MAX_AUTOMATIC_LOCAL_RECOVERY_ATTEMPTS times.
 * Extracted from CenterChat to isolate recovery side-effects.
 */
export function useAutomaticRecovery({
  messages,
  expertConversations,
  configKeySaved,
  streaming,
  onRecovery,
}: UseAutomaticRecoveryOptions): void {
  const attemptedRef = useRef<Set<string>>(new Set());

  // Clear attempts when project changes (detected by message list identity change)
  const firstMessageId = messages[0]?.id ?? null;
  const projectKeyRef = useRef<string | null>(null);
  const currentProjectKey = `${firstMessageId ?? "empty"}`;
  if (projectKeyRef.current !== currentProjectKey) {
    projectKeyRef.current = currentProjectKey;
    attemptedRef.current.clear();
  }

  const candidate =
    configKeySaved && !streaming
      ? findAutomaticLocalRecoveryCandidate(messages, expertConversations)
      : null;

  useEffect(() => {
    if (!candidate) return;
    if (attemptedRef.current.has(candidate.id)) return;
    attemptedRef.current.add(candidate.id);
    onRecovery(candidate, "retry", AUTOMATIC_RECOVERY_LABEL);
  }, [candidate, onRecovery]);
}

// --- Pure utility functions (exported for use in MessageBubble and CenterChat) ---

export function findAutomaticLocalRecoveryCandidate(
  messages: ChatMessage[],
  expertConversations: ExpertConversation[],
): ChatMessage | null {
  const candidate = messages[messages.length - 1];
  if (
    !candidate
    || candidate.role !== ChatRole.ASSISTANT
    || candidate.status !== ChatMessageStatus.FAILED
    || candidate.error?.code !== LLMErrorCode.LOCAL_OUTPUT_REJECTED
  ) {
    return null;
  }
  const conversation = expertConversations.find(
    (item) =>
      item.projectExpertId === candidate.metadata?.projectExpertId
      || item.id === candidate.metadata?.conversationId,
  );
  const expertType = candidate.metadata?.expertType ?? conversation?.expertType;
  if (expertType !== ExpertType.SMART_ENGINEER) return null;
  if (hasRecoveryForMessage(messages, candidate.id)) return null;
  const source = findRecoverySourceMessage(messages, candidate);
  if (!source) return null;
  if (
    automaticLocalRecoveryAttemptCount(messages, candidate)
    >= MAX_AUTOMATIC_LOCAL_RECOVERY_ATTEMPTS
  ) return null;
  return candidate;
}

export function isAutomaticLocalRecoveryExhausted(
  messages: ChatMessage[],
  candidate: ChatMessage,
  expertConversations: ExpertConversation[],
): boolean {
  if (
    candidate.role !== ChatRole.ASSISTANT
    || candidate.status !== ChatMessageStatus.FAILED
    || candidate.error?.code !== LLMErrorCode.LOCAL_OUTPUT_REJECTED
    || hasRecoveryForMessage(messages, candidate.id)
  ) return false;
  const conversation = expertConversations.find(
    (item) =>
      item.projectExpertId === candidate.metadata?.projectExpertId
      || item.id === candidate.metadata?.conversationId,
  );
  const expertType = candidate.metadata?.expertType ?? conversation?.expertType;
  return expertType === ExpertType.SMART_ENGINEER
    && automaticLocalRecoveryAttemptCount(messages, candidate)
      >= MAX_AUTOMATIC_LOCAL_RECOVERY_ATTEMPTS;
}

export function automaticLocalRecoveryAttemptCount(
  messages: ChatMessage[],
  failedMessage: ChatMessage,
): number {
  let attempts = 0;
  let currentFailure: ChatMessage | null = failedMessage;
  const visitedFailureIds = new Set<string>();

  while (currentFailure && !visitedFailureIds.has(currentFailure.id)) {
    visitedFailureIds.add(currentFailure.id);
    const source = findRecoverySourceMessage(messages, currentFailure);
    const previousFailureId = source?.metadata?.recoveryOfMessageId;
    if (
      !source
      || source.metadata?.recoveryLabel !== AUTOMATIC_RECOVERY_LABEL
      || !previousFailureId
    ) break;
    attempts += 1;
    currentFailure = messages.find(
      (message) =>
        message.id === previousFailureId
        && message.role === ChatRole.ASSISTANT,
    ) ?? null;
  }

  return attempts;
}

export function hasRecoveryForMessage(messages: ChatMessage[], messageId: string): boolean {
  return messages.some(
    (message) =>
      message.role === ChatRole.USER
      && message.metadata?.recoveryOfMessageId === messageId,
  );
}

export function hasAutomaticRecoveryForMessage(
  messages: ChatMessage[],
  messageId: string,
): boolean {
  return messages.some(
    (message) =>
      message.role === ChatRole.USER
      && message.metadata?.recoveryOfMessageId === messageId
      && message.metadata.recoveryLabel === AUTOMATIC_RECOVERY_LABEL,
  );
}

export function findRecoverySourceMessage(
  messages: ChatMessage[],
  failedMessage: ChatMessage,
): ChatMessage | null {
  const metadata = failedMessage.metadata;
  const turnIds = new Set(
    [metadata?.parentTurnId, metadata?.requestTurnId, metadata?.clientTurnId]
      .filter((value): value is string => Boolean(value)),
  );
  const exact = [...messages].reverse().find((message) => {
    if (message.role !== ChatRole.USER) return false;
    if (
      metadata?.conversationId
      && message.metadata?.conversationId !== metadata.conversationId
    ) return false;
    return [
      message.metadata?.turnId,
      message.metadata?.requestTurnId,
      message.metadata?.clientTurnId,
    ].some((value) => value !== undefined && turnIds.has(value));
  });
  if (exact) return exact;
  const failedIndex = messages.findIndex((message) => message.id === failedMessage.id);
  for (let index = failedIndex - 1; index >= 0; index -= 1) {
    const candidate = messages[index];
    if (
      candidate?.role === ChatRole.USER
      && (
        !metadata?.conversationId
        || candidate.metadata?.conversationId === metadata.conversationId
      )
    ) return candidate;
  }
  return null;
}

export function isInterruptedGeneration(error: LLMError): boolean {
  return error.code === LLMErrorCode.GENERATION_INTERRUPTED
    || error.message.includes("上次生成被中断")
    || error.message.includes("回复流已提前结束");
}

export function interruptedGenerationError(): LLMError {
  return {
    code: LLMErrorCode.GENERATION_INTERRUPTED,
    message: "生成流提前结束。原需求已保留，可继续生成。",
    retryable: true,
    userActions: [
      { id: "retry", label: "继续生成" },
      { id: "revise_request", label: "修改原需求" },
    ],
  };
}

export function recoveryEventLabel(error: LLMError | undefined): string {
  return isInterruptedGeneration(error ?? interruptedGenerationError())
    ? "已继续上一条生成"
    : "已按原需求重新生成";
}
