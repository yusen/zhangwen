import { useCallback, useEffect, useRef, useState } from "react";
import {
  ConversationResponseType,
  type ChatMessage,
  type ClarificationAnswer,
  type ClarificationBatchAnswer,
  type ConversationClarificationQuestion,
  type ExpertConversation,
  type ProjectWorkspace,
} from "@zhangwen/contracts";

interface UseClarificationOptions {
  projectId: string | null;
  workspace: ProjectWorkspace | null;
  activeExpertConversation: ExpertConversation | null;
  configKeySaved: boolean;
  messages: ChatMessage[];
  onOpenSettings: () => void;
  onSend: (text: string, metadata: Record<string, unknown>) => void;
}

export interface ClarificationState {
  answeredCards: Record<string, boolean>;
  clarificationDrafts: Record<string, Record<string, ClarificationAnswer>>;
  optimisticClarificationKeys: ReadonlySet<string>;
  activeClarificationMessage: ChatMessage | null;
  activeClarificationQuestion: ConversationClarificationQuestion | null;
  hasPendingClarification: boolean;
  setAnsweredCards: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
  handleClarificationDraftChange: (messageId: string, answer: ClarificationAnswer) => void;
  handleSubmitClarification: (messageId: string, questions: ConversationClarificationQuestion[]) => void;
  answerActiveClarification: (
    text: string | null,
    useRecommendation?: boolean,
  ) => "advanced" | "submitted" | "unavailable";
  settleOptimisticClarification: (turnId: string | null | undefined, succeeded: boolean) => void;
  resetClarificationState: () => void;
}

/**
 * Manages clarification card drafts, optimistic answers, and batch submission.
 * Extracted from CenterChat to isolate clarification state.
 */
export function useClarification({
  projectId,
  workspace,
  activeExpertConversation,
  configKeySaved,
  messages,
  onOpenSettings,
  onSend,
}: UseClarificationOptions): ClarificationState {
  const [answeredCards, setAnsweredCards] = useState<Record<string, boolean>>({});
  const [clarificationDrafts, setClarificationDrafts] = useState<
    Record<string, Record<string, ClarificationAnswer>>
  >({});
  const optimisticClarificationKeysByTurnRef = useRef<Record<string, string[]>>({});
  const failedClarificationKeysRef = useRef<Set<string>>(new Set());

  const optimisticClarificationKeys = new Set(
    Object.values(optimisticClarificationKeysByTurnRef.current).flat(),
  );

  const activeClarificationMessage = findLatestPendingClarification(
    messages,
    answeredCards,
    optimisticClarificationKeys,
  );
  const hasPendingClarification = activeClarificationMessage !== null;
  const activeQuestions = clarificationQuestions(activeClarificationMessage);
  const activeDraftKey = activeClarificationMessage
    ? clarificationDraftKey(projectId, activeClarificationMessage.id)
    : null;
  const activeDraft = activeDraftKey
    ? clarificationDrafts[activeDraftKey] ?? {}
    : {};
  const activeClarificationQuestion =
    activeQuestions.find((question) => {
      const answerKey = activeClarificationMessage
        ? `${activeClarificationMessage.id}:${question.id}`
        : "";
      return (
        !question.answered &&
        !answeredCards[answerKey] &&
        !isClarificationAnswerComplete(activeDraft[question.id])
      );
    }) ?? null;

  const settleOptimisticClarification = useCallback(
    (turnId: string | null | undefined, succeeded: boolean) => {
      if (!turnId) return;
      const keys = optimisticClarificationKeysByTurnRef.current[turnId];
      if (!keys) return;
      delete optimisticClarificationKeysByTurnRef.current[turnId];
      if (succeeded) return;
      // Do not restore the card from stale client messages. The structured
      // answer may already have committed before the follow-up LLM failed.
      // Reconcile only after the project workspace is reloaded from storage.
      keys.forEach((key) => failedClarificationKeysRef.current.add(key));
    },
    [],
  );

  useEffect(() => {
    const failedKeys = failedClarificationKeysRef.current;
    if (failedKeys.size === 0) return;
    const persistedMessages =
      workspace?.expertConversations?.flatMap(
        (conversation) => conversation.messages,
      ) ?? [];
    if (persistedMessages.length === 0) return;

    setAnsweredCards((current) => {
      const next = { ...current };
      let changed = false;
      for (const key of [...failedKeys]) {
        const separator = key.lastIndexOf(":");
        if (separator <= 0) continue;
        const messageId = key.slice(0, separator);
        const questionId = key.slice(separator + 1);
        const source = persistedMessages.find(
          (message) => message.id === messageId,
        );
        if (!source) continue;
        const questions = clarificationQuestions(source);
        const persistedQuestion = questions.find(
          (question) => question.id === questionId,
        );
        if (!persistedQuestion) continue;
        if (!persistedQuestion.answered && next[key]) {
          delete next[key];
          changed = true;
        }
        failedKeys.delete(key);
      }
      return changed ? next : current;
    });
  }, [workspace?.expertConversations]);

  const resetClarificationState = useCallback(() => {
    setAnsweredCards({});
    setClarificationDrafts({});
    optimisticClarificationKeysByTurnRef.current = {};
    failedClarificationKeysRef.current.clear();
  }, []);

  const handleClarificationDraftChange = useCallback(
    (messageId: string, answer: ClarificationAnswer) => {
      const key = clarificationDraftKey(projectId, messageId);
      setClarificationDrafts((current) => ({
        ...current,
        [key]: {
          ...(current[key] ?? {}),
          [answer.questionId]: answer,
        },
      }));
    },
    [projectId],
  );

  const submitClarification = useCallback(
    (
      messageId: string,
      questions: ConversationClarificationQuestion[],
      draftAnswers: Record<string, ClarificationAnswer>,
    ): boolean => {
      if (!workspace || !activeExpertConversation) return false;
      if (!configKeySaved) {
        onOpenSettings();
        return false;
      }
      const requiredComplete = questions
        .filter((question) => question.required && !question.answered)
        .every((question) => isClarificationAnswerComplete(draftAnswers[question.id]));
      if (!requiredComplete) return false;
      const answers = questions
        .filter((question) => !question.answered)
        .map((question) => draftAnswers[question.id])
        .filter((answer): answer is ClarificationAnswer =>
          isClarificationAnswerComplete(answer)
        );
      if (answers.length === 0) return false;

      const source = messages.find((message) => message.id === messageId);
      const clientTurnId = createClientTurnId();
      const structuredAnswer: ClarificationBatchAnswer = {
        type: "clarification_batch_answer",
        projectId: workspace.project.id,
        conversationId:
          source?.metadata?.conversationId ?? activeExpertConversation.id,
        sourceMessageId: messageId,
        clientTurnId,
        answers,
      };
      const content = [
        "已完成本轮需求确认：",
        ...questions.map((question) => {
          const answer = question.answer ?? draftAnswers[question.id];
          return `${question.text}：${formatClarificationAnswer(question, answer)}`;
        }),
      ].join("\n");

      const optimisticAnswerKeys = answers.map(
        (answer) => `${messageId}:${answer.questionId}`
      );
      optimisticClarificationKeysByTurnRef.current[clientTurnId] =
        optimisticAnswerKeys;
      setAnsweredCards((current) => ({
        ...current,
        ...Object.fromEntries(
          optimisticAnswerKeys.map((answerKey) => [answerKey, true])
        ),
      }));
      onSend(content, {
        clientTurnId,
        projectExpertId: source?.metadata?.projectExpertId,
        sourceMessageId: messageId,
        structuredAnswer,
      });
      return true;
    },
    [
      activeExpertConversation,
      configKeySaved,
      messages,
      onOpenSettings,
      onSend,
      projectId,
      workspace,
    ],
  );

  const handleSubmitClarification = useCallback(
    (messageId: string, questions: ConversationClarificationQuestion[]) => {
      const key = clarificationDraftKey(projectId, messageId);
      submitClarification(messageId, questions, clarificationDrafts[key] ?? {});
    },
    [clarificationDrafts, projectId, submitClarification],
  );

  const answerActiveClarification = useCallback(
    (
      text: string | null,
      useRecommendation = false,
    ): "advanced" | "submitted" | "unavailable" => {
      if (!activeClarificationMessage || !activeClarificationQuestion) {
        return "unavailable";
      }
      const answer = clarificationAnswerFromNaturalInput(
        activeClarificationQuestion,
        text,
        useRecommendation,
      );
      if (!isClarificationAnswerComplete(answer)) return "unavailable";

      const key = clarificationDraftKey(projectId, activeClarificationMessage.id);
      const mergedDraft = {
        ...(clarificationDrafts[key] ?? {}),
        [activeClarificationQuestion.id]: answer,
      };
      setClarificationDrafts((current) => ({
        ...current,
        [key]: mergedDraft,
      }));

      const allRequiredComplete = activeQuestions
        .filter((question) => question.required && !question.answered)
        .every((question) =>
          isClarificationAnswerComplete(mergedDraft[question.id])
        );
      if (
        allRequiredComplete &&
        submitClarification(
          activeClarificationMessage.id,
          activeQuestions,
          mergedDraft,
        )
      ) {
        return "submitted";
      }
      return "advanced";
    },
    [
      activeClarificationMessage,
      activeClarificationQuestion,
      activeQuestions,
      clarificationDrafts,
      projectId,
      submitClarification,
    ],
  );

  return {
    answeredCards,
    clarificationDrafts,
    optimisticClarificationKeys,
    activeClarificationMessage,
    activeClarificationQuestion,
    hasPendingClarification,
    setAnsweredCards,
    handleClarificationDraftChange,
    handleSubmitClarification,
    answerActiveClarification,
    settleOptimisticClarification,
    resetClarificationState,
  };
}

// --- Pure utility functions ---

export function findLatestPendingClarification(
  messages: ChatMessage[],
  locallyAnsweredQuestionIds: Record<string, boolean>,
  optimisticKeys: ReadonlySet<string>,
): ChatMessage | null {
  for (const message of [...messages].reverse()) {
    const payload = message.structuredPayload;
    if (payload?.type !== ConversationResponseType.CLARIFICATION) continue;
    const questions = payload.questions?.length
      ? payload.questions
      : [payload.question];
    const requiredQuestions = questions.filter((question) => question.required);
    const trackedQuestions = requiredQuestions.length > 0
      ? requiredQuestions
      : questions;
    if (
      trackedQuestions.some((question) => {
        const key = `${message.id}:${question.id}`;
        return (
          !optimisticKeys.has(key) &&
          !question.answered &&
          !locallyAnsweredQuestionIds[key]
        );
      })
    ) {
      return message;
    }
  }
  return null;
}

export function clarificationDraftKey(activeDraftKey: string | null, messageId: string): string {
  return `${activeDraftKey ?? "no-project"}:${messageId}`;
}

export function isClarificationAnswerComplete(
  answer: ClarificationAnswer | undefined
): answer is ClarificationAnswer {
  return Boolean(
    answer &&
    (answer.selectedOptionIds.length > 0 || answer.textInput?.trim())
  );
}

export function formatClarificationAnswer(
  question: ConversationClarificationQuestion,
  answer: ClarificationAnswer | undefined
): string {
  if (!answer) return "未填写";
  const labels = (question.options ?? [])
    .filter((option) => answer.selectedOptionIds.includes(option.id))
    .map((option) => option.label);
  return labels.join("、") || answer.textInput?.trim() || "未填写";
}

export function clarificationAnswerFromNaturalInput(
  question: ConversationClarificationQuestion,
  text: string | null,
  useRecommendation: boolean,
): ClarificationAnswer | undefined {
  const normalizedText = text?.trim() ?? "";
  const options = question.options ?? [];
  if (useRecommendation) {
    const recommended = options.filter((option) => option.recommended);
    const selected =
      question.mode === "multiple"
        ? (recommended.length ? recommended : options.slice(0, 1))
        : [recommended[0] ?? options[0]].filter(
            (option): option is NonNullable<typeof option> => Boolean(option),
          );
    if (selected.length === 0) return undefined;
    return {
      questionId: question.id,
      selectedOptionIds: selected.map((option) => option.id),
      usedRecommendation: true,
    };
  }
  if (!normalizedText) return undefined;

  const normalized = normalizeAnswerText(normalizedText);
  const matched = options.filter((option) => {
    const candidates = [option.label, option.value, option.id]
      .filter((value): value is string => Boolean(value))
      .map(normalizeAnswerText);
    return candidates.some(
      (candidate) =>
        candidate === normalized ||
        (candidate.length > 1 && normalized.includes(candidate)),
    );
  });
  if (matched.length > 0) {
    return {
      questionId: question.id,
      selectedOptionIds:
        question.mode === "multiple"
          ? matched.map((option) => option.id)
          : [matched[0]!.id],
      usedRecommendation: matched.some((option) => option.recommended) || undefined,
    };
  }
  return {
    questionId: question.id,
    selectedOptionIds: [],
    textInput: normalizedText,
  };
}

function clarificationQuestions(
  message: ChatMessage | null,
): ConversationClarificationQuestion[] {
  const payload = message?.structuredPayload;
  if (payload?.type !== ConversationResponseType.CLARIFICATION) return [];
  return payload.questions?.length ? payload.questions : [payload.question];
}

function normalizeAnswerText(value: string): string {
  return value.toLocaleLowerCase("zh-CN").replace(/[\s，。！？、；：,.!?;:]/g, "");
}

function createClientTurnId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `turn_${crypto.randomUUID().replaceAll("-", "")}`;
  }
  return `turn_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}
