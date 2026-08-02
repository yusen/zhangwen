import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ChatMessageStatus,
  ChatRole,
  ConversationIntent,
  type ChatMessage,
  type ChatProgress,
  type ConversationTurnContext,
  type ConversationAction,
  type LLMConfig,
  type LLMModelId,
  type ModelConfig,
  type PersistedChatRequest,
  type ProjectStreamChunk,
  type ProjectKickoff,
  type ProjectWorkspace,
  type ExpertConversation,
  type ExpertDefinition,
  type ExpertType,
} from "@zhangwen/contracts";
import {
  ConversationActionType,
  ConversationResponseType,
  StreamChunkType,
} from "@zhangwen/contracts";
import { useChatStream } from "../../hooks/useChatStream";
import { useDraftPersistence } from "../../hooks/useDraftPersistence";
import { useClarification, clarificationDraftKey } from "../../hooks/useClarification";
import {
  useAutomaticRecovery,
  findAutomaticLocalRecoveryCandidate,
  findRecoverySourceMessage,
  interruptedGenerationError,
  recoveryEventLabel,
} from "../../hooks/useAutomaticRecovery";
import { ChatInput } from "../chat/ChatInput";
import { MessageList } from "../chat/MessageList";
import { ClarificationDock } from "../chat/ClarificationDock";
import { DraftSaveIndicator } from "../chat/DraftSaveIndicator";
import { ProjectConfirmationCard } from "../chat/ProjectConfirmationCard";
import { useHostAdapter } from "../../platform";
import {
  DEFAULT_THREE_EXPERT_DEFINITIONS,
  THREE_EXPERT_TYPES,
  getExpertDisplayName,
} from "../../utils/experts";
import { importMessageCode } from "../../services/projectsApi";
import type { ProjectEngineeringState } from "../../hooks/useProjectEngineeringState";
import type { ExpertPresentation } from "../chat/MessageBubble";

interface CenterChatProps {
  rootElement?: "main" | "div";
  config: LLMConfig | null;
  workspace: ProjectWorkspace | null;
  selectedExpertId: string | null;
  models: ModelConfig[];
  professionalMode: boolean;
  creatorWorkflow?: boolean;
  draftSaving: boolean;
  draftSaveError?: string | null;
  onOpenSettings: () => void;
  onOpenArtifact: (artifactId?: string | null, versionId?: string | null) => void;
  onOpenHardwareSelection?: () => void;
  onSaveDraft: (
    projectId: string,
    content: string,
    projectExpertId?: string | null
  ) => Promise<unknown>;
  onSelectExpert: (projectExpertId: string) => void;
  onAddExpert?: (expertType: ExpertType) => Promise<ExpertConversation | null>;
  onSelectModel: (projectId: string, model: LLMModelId) => Promise<unknown>;
  onReloadProject: (projectId: string) => Promise<void>;
  onDismissPendingItem?: (pendingItemId: string) => Promise<unknown>;
  confirmationRefreshRevision?: number;
  engineeringState?: ProjectEngineeringState;
  onStreamingChange?: (streaming: boolean) => void;
  onInteractionControlsChange?: (controls: CenterChatInteractionControls | null) => void;
  workspaceContext?: Pick<
    ConversationTurnContext,
    "workspaceKind" | "workspaceView" | "projectVersion"
  >;
}

export interface CenterChatInteractionControls {
  stopStreaming: () => Promise<void>;
  flushDraft: () => Promise<void>;
}

interface ActiveStreamScope {
  projectId: string;
  conversationId: string | null;
  requestId: string | null;
  requestTurnId: string | null;
  assistantMessageId: string | null;
  resolvingPendingItem: boolean;
  conversationAction?: string;
}

interface AutomaticExpertHandoff {
  projectId: string;
  targetExpert: ExpertType;
  label: string;
  prompt: string;
}

export function CenterChat({
  rootElement = "main",
  config,
  workspace,
  selectedExpertId,
  models,
  professionalMode,
  creatorWorkflow = false,
  draftSaving,
  draftSaveError = null,
  onOpenSettings,
  onOpenArtifact,
  onOpenHardwareSelection,
  onSaveDraft,
  onSelectExpert,
  onAddExpert,
  onSelectModel,
  onReloadProject,
  onDismissPendingItem = async () => undefined,
  confirmationRefreshRevision = 0,
  engineeringState,
  onStreamingChange,
  onInteractionControlsChange,
  workspaceContext,
}: CenterChatProps) {
  const { capabilities } = useHostAdapter();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [progressByMessageId, setProgressByMessageId] = useState<
    Record<string, ChatProgress[]>
  >({});
  const [automaticHandoff, setAutomaticHandoff] =
    useState<AutomaticExpertHandoff | null>(null);
  const [automaticHandoffError, setAutomaticHandoffError] = useState<string | null>(null);
  const activeProjectIdRef = useRef<string | null>(null);
  const activeStreamScopeRef = useRef<ActiveStreamScope | null>(null);
  const activeAssistantIdRef = useRef<string | null>(null);
  const latestPendingTurnIdRef = useRef<string | null>(null);
  const streamingRef = useRef(false);
  const followLatestMessageRef = useRef(true);
  const pendingResolutionRef = useRef(false);
  const attemptedKickoffRef = useRef<Set<string>>(new Set());
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const scrollByProjectRef = useRef<Record<string, number>>({});

  const expertConversations = useMemo(
    () => (workspace?.expertConversations ?? []).filter(
      (conversation) => !conversation.archivedLegacyThread,
    ),
    [workspace?.expertConversations],
  );
  const activeExpertConversation =
    expertConversations.find(
      (conversation) => conversation.projectExpertId === selectedExpertId
    ) ?? expertConversations[0] ?? null;
  const projectId = workspace?.project.id ?? null;
  const selectedModel = workspace?.project.selectedModel;

  const {
    draft,
    updateDraft,
    flushDraft,
    isDirty,
  } = useDraftPersistence({
    projectId,
    workspaceDraftContent: workspace?.draft.content ?? "",
    workspaceDraftUpdatedAt: workspace?.draft.updatedAt,
    onSaveDraft,
  });

  const handleSendRef = useRef<(text: string, metadata: Record<string, unknown>) => void>();
  const {
    answeredCards,
    clarificationDrafts,
    activeClarificationMessage,
    activeClarificationQuestion,
    hasPendingClarification,
    handleClarificationDraftChange,
    handleSubmitClarification,
    answerActiveClarification,
    settleOptimisticClarification,
    resetClarificationState,
  } = useClarification({
    projectId,
    workspace,
    activeExpertConversation,
    configKeySaved: Boolean(config?.keySaved),
    messages,
    onOpenSettings,
    onSend: (text, metadata) => handleSendRef.current?.(text, metadata),
  });

  const disabledReason = !workspace
    ? "\u8bf7\u5148\u521b\u5efa\u6216\u6253\u5f00\u4e00\u4e2a\u9879\u76ee\u3002"
    : !activeExpertConversation
    ? "\u5f53\u524d\u4e13\u5bb6\u5de5\u4f5c\u533a\u5c1a\u672a\u51c6\u5907\u597d\u3002"
    : professionalMode && hasPendingClarification
    ? "\u8bf7\u5148\u5b8c\u6210\u4e0a\u65b9\u5168\u90e8\u5fc5\u7b54\u95ee\u9898\u3002"
    : config?.keySaved
      ? null
      : capabilities.credentialStore
        ? "\u8bf7\u5148\u5728\u8bbe\u7f6e\u4e2d\u914d\u7f6e DeepSeek API Key\u3002"
        : "\u540e\u7aef\u5c1a\u672a\u914d\u7f6e\u6a21\u578b\u670d\u52a1\uff0c\u8bf7\u5728\u672c\u5730\u540e\u7aef\u914d\u7f6e\u540e\u91cd\u8bd5\u3002";

  useEffect(() => {
    activeProjectIdRef.current = projectId;
    activeStreamScopeRef.current = null;
    activeAssistantIdRef.current = null;
    latestPendingTurnIdRef.current = null;
    pendingResolutionRef.current = false;
    resetClarificationState();
    setProgressByMessageId({});
    setAutomaticHandoff(null);
    setAutomaticHandoffError(null);
    setMessages(mergeProjectMessages(expertConversations));
    setStreaming(false);
  }, [projectId]);

  useEffect(() => {
    const key = projectId ?? "no-project";
    const element = messagesContainerRef.current;
    if (!element) return;
    const saved = scrollByProjectRef.current[key];
    window.requestAnimationFrame(() => {
      element.scrollTop = saved ?? element.scrollHeight;
    });
    return () => {
      scrollByProjectRef.current[key] = element.scrollTop;
    };
  }, [projectId]);

  useEffect(() => {
    if (!projectId || streamingRef.current) return;
    setMessages(mergeProjectMessages(expertConversations));
  }, [projectId, workspace?.expertConversations]);

  useEffect(() => {
    streamingRef.current = streaming;
    onStreamingChange?.(streaming);
  }, [streaming, onStreamingChange]);

  useEffect(() => {
    if (!streaming || !followLatestMessageRef.current) return;
    const element = messagesContainerRef.current;
    if (!element) return;
    const frame = window.requestAnimationFrame(() => {
      element.scrollTop = element.scrollHeight;
    });
    return () => window.cancelAnimationFrame(frame);
  }, [messages, progressByMessageId, streaming]);

  const handleMessagesScroll = useCallback(() => {
    const element = messagesContainerRef.current;
    if (!element) return;
    const distanceFromBottom =
      element.scrollHeight - element.scrollTop - element.clientHeight;
    followLatestMessageRef.current = distanceFromBottom <= 48;
  }, []);

  const clearMessageProgress = useCallback((messageId: string | null) => {
    if (!messageId) return;
    setProgressByMessageId((current) => {
      if (!current[messageId]) return current;
      const next = { ...current };
      delete next[messageId];
      return next;
    });
  }, []);

  const handleChunk = useCallback(
    (chunk: ProjectStreamChunk) => {
      const scope = activeStreamScopeRef.current;
      if (!scope || chunk.projectId !== scope.projectId) return;
      if (scope.requestId && chunk.requestId !== scope.requestId) return;
      if (scope.conversationId && chunk.conversationId !== scope.conversationId) return;
      if (scope.requestTurnId && chunk.requestTurnId && chunk.requestTurnId !== scope.requestTurnId) return;
      const targetConversation = expertConversations.find(
        (conversation) => conversation.id === chunk.conversationId
      );
      const resolvingPendingItem = scope.resolvingPendingItem;
      const targetId = scope.assistantMessageId ?? chunk.messageId;
      if (chunk.type === StreamChunkType.START && resolvingPendingItem) {
        activeAssistantIdRef.current = chunk.messageId;
        latestPendingTurnIdRef.current = chunk.requestTurnId ?? null;
        followLatestMessageRef.current = true;
        setStreaming(true);
        if (targetConversation) onSelectExpert(targetConversation.projectExpertId);
      }
      if (chunk.type === StreamChunkType.START) {
        activeStreamScopeRef.current = {
          ...scope,
          conversationId: chunk.conversationId,
          requestId: chunk.requestId,
          requestTurnId: chunk.requestTurnId ?? scope.requestTurnId,
          assistantMessageId: chunk.messageId,
        };
      }
      if (latestPendingTurnIdRef.current && chunk.requestTurnId !== latestPendingTurnIdRef.current) return;

      if (chunk.type === StreamChunkType.START) {
        activeAssistantIdRef.current = chunk.messageId;
        setProgressByMessageId((current) => {
          const pendingProgress = current[targetId] ?? current[chunk.messageId];
          const next = { ...current };
          delete next[targetId];
          delete next[chunk.messageId];
          if (pendingProgress?.length) next[chunk.messageId] = pendingProgress;
          return next;
        });
        setMessages((prev) =>
          prev.map((message) =>
            message.id === targetId
              ? { ...message, id: chunk.messageId, model: chunk.model, metadata: { ...message.metadata, projectExpertId: targetConversation?.projectExpertId, expertType: targetConversation?.expertType, conversationId: chunk.conversationId, requestTurnId: chunk.requestTurnId, responseTurnId: chunk.responseTurnId }, status: ChatMessageStatus.STREAMING }
              : message
          )
        );
        return;
      }
      if (chunk.type === StreamChunkType.PROGRESS && chunk.progress) {
        const progressEvent = chunk.progress;
        setProgressByMessageId((current) => {
          const existing = current[targetId] ?? [];
          const nextProgress = [...existing.filter((p) => p.id !== progressEvent.id), progressEvent].sort((l, r) => l.sequence - r.sequence);
          return { ...current, [targetId]: nextProgress };
        });
        return;
      }
      if (chunk.type === StreamChunkType.CONTENT_DELTA || chunk.type === StreamChunkType.REASONING_DELTA) {
        setMessages((prev) =>
          prev.map((message) =>
            message.id === targetId
              ? { ...message, content: chunk.accumulatedContent ?? message.content, structuredPayload: chunk.structuredPayload ?? message.structuredPayload, reasoningContent: chunk.accumulatedReasoning ?? message.reasoningContent, usage: chunk.usage ?? message.usage, updatedAt: new Date().toISOString() }
              : message
          )
        );
        return;
      }
      if (chunk.type === StreamChunkType.COMPLETED) {
        if (!resolvingPendingItem) settleOptimisticClarification(chunk.requestTurnId ?? latestPendingTurnIdRef.current, true);
        setMessages((prev) =>
          prev.map((message) =>
            message.id === targetId
              ? { ...message, content: chunk.accumulatedContent ?? message.content, structuredPayload: chunk.structuredPayload ?? message.structuredPayload, reasoningContent: chunk.accumulatedReasoning ?? message.reasoningContent, status: ChatMessageStatus.COMPLETED, usage: chunk.usage ?? message.usage, updatedAt: new Date().toISOString() }
              : message
          )
        );
        setStreaming(false);
        const handoff = scope.conversationAction === ConversationActionType.CONFIRM_PROJECT_PROPOSAL && chunk.structuredPayload?.type === ConversationResponseType.PROPOSAL_ACTION ? chunk.structuredPayload.handoff : undefined;
        if (handoff?.automatic) {
          setAutomaticHandoff({ projectId: chunk.projectId, targetExpert: handoff.targetExpert, label: handoff.label, prompt: handoff.prompt });
          setAutomaticHandoffError(null);
        }
        clearMessageProgress(targetId);
        pendingResolutionRef.current = false;
        activeStreamScopeRef.current = null;
        activeAssistantIdRef.current = null;
        latestPendingTurnIdRef.current = null;
        void onReloadProject(chunk.projectId);
        return;
      }
      if (chunk.type === StreamChunkType.ERROR || chunk.type === StreamChunkType.CANCELED) {
        if (!resolvingPendingItem) settleOptimisticClarification(chunk.requestTurnId ?? latestPendingTurnIdRef.current, false);
        setMessages((prev) =>
          prev.map((message) =>
            message.id === targetId
              ? { ...message, status: resolvingPendingItem ? ChatMessageStatus.COMPLETED : chunk.type === StreamChunkType.CANCELED ? ChatMessageStatus.CANCELED : ChatMessageStatus.FAILED, error: resolvingPendingItem ? undefined : chunk.error, content: message.content, updatedAt: new Date().toISOString() }
              : message
          )
        );
        setStreaming(false);
        clearMessageProgress(targetId);
        if (!resolvingPendingItem) pendingResolutionRef.current = false;
        activeAssistantIdRef.current = null;
        activeStreamScopeRef.current = null;
        latestPendingTurnIdRef.current = null;
        void onReloadProject(chunk.projectId);
      }
    },
    [clearMessageProgress, expertConversations, onReloadProject, onSelectExpert, settleOptimisticClarification]
  );

  const { startProject, stopProject, startPendingItemResolution } = useChatStream({
    onChunk: (chunk) => handleChunk(chunk as ProjectStreamChunk),
    onDone: () => {
      const scope = activeStreamScopeRef.current;
      const completedProjectId = scope?.projectId ?? activeProjectIdRef.current;
      const incompleteAssistantId = scope?.assistantMessageId ?? activeAssistantIdRef.current;
      const resolvingPendingItem = scope?.resolvingPendingItem ?? pendingResolutionRef.current;
      if (!resolvingPendingItem) settleOptimisticClarification(latestPendingTurnIdRef.current, false);
      clearMessageProgress(incompleteAssistantId);
      if (incompleteAssistantId) {
        setMessages((current) =>
          current.map((message) =>
            message.id === incompleteAssistantId
              ? { ...message, status: resolvingPendingItem ? ChatMessageStatus.COMPLETED : ChatMessageStatus.FAILED, content: message.content, error: resolvingPendingItem ? undefined : interruptedGenerationError() }
              : message
          )
        );
      }
      setStreaming(false);
      pendingResolutionRef.current = false;
      activeStreamScopeRef.current = null;
      activeAssistantIdRef.current = null;
      latestPendingTurnIdRef.current = null;
      if (resolvingPendingItem && completedProjectId) void onReloadProject(completedProjectId);
    },
    onError: (message) => {
      const scope = activeStreamScopeRef.current;
      const failedProjectId = scope?.projectId ?? activeProjectIdRef.current;
      const failedAssistantId = scope?.assistantMessageId ?? activeAssistantIdRef.current;
      const failedTurnId = latestPendingTurnIdRef.current;
      const resolvingPendingItem = scope?.resolvingPendingItem ?? pendingResolutionRef.current;
      if (!resolvingPendingItem) settleOptimisticClarification(failedTurnId, false);
      clearMessageProgress(failedAssistantId);
      setMessages((prev) =>
        prev.map((item) =>
          item.id === failedAssistantId
            ? { ...item, status: resolvingPendingItem ? ChatMessageStatus.COMPLETED : ChatMessageStatus.FAILED, content: item.content, error: resolvingPendingItem ? undefined : { code: "SIDECAR_UNAVAILABLE", message, retryable: true, userActions: [{ id: "retry", label: "\u91cd\u65b0\u751f\u6210" }] } }
            : item
        )
      );
      setStreaming(false);
      pendingResolutionRef.current = false;
      activeStreamScopeRef.current = null;
      activeAssistantIdRef.current = null;
      latestPendingTurnIdRef.current = null;
      if (failedProjectId) void onReloadProject(failedProjectId);
    },
  });

  const handleResolvePendingItem = useCallback(
    async (pendingItemId: string) => {
      if (!projectId) throw new Error("\u8bf7\u5148\u6253\u5f00\u9879\u76ee\u540e\u518d\u786e\u8ba4\u672c\u5730\u6267\u884c\u3002");
      pendingResolutionRef.current = true;
      activeStreamScopeRef.current = { projectId, conversationId: null, requestId: null, requestTurnId: null, assistantMessageId: null, resolvingPendingItem: true };
      followLatestMessageRef.current = true;
      setStreaming(true);
      await startPendingItemResolution(projectId, pendingItemId);
    },
    [projectId, startPendingItemResolution]
  );

  const startKickoff = useCallback(
    (kickoff: ProjectKickoff, retry: boolean) => {
      if (!workspace || !selectedModel) return;
      if (!config?.keySaved) { if (retry) onOpenSettings(); return; }
      const targetConversation = expertConversations.find((c) => c.id === kickoff.conversationId);
      if (!targetConversation) return;
      activeProjectIdRef.current = workspace.project.id;
      activeStreamScopeRef.current = { projectId: workspace.project.id, conversationId: kickoff.conversationId, requestId: null, requestTurnId: kickoff.turnId, assistantMessageId: kickoff.assistantMessageId, resolvingPendingItem: false };
      activeAssistantIdRef.current = kickoff.assistantMessageId;
      pendingResolutionRef.current = false;
      clearMessageProgress(kickoff.assistantMessageId);
      latestPendingTurnIdRef.current = kickoff.turnId;
      followLatestMessageRef.current = true;
      onSelectExpert(kickoff.projectExpertId);
      setMessages((current) =>
        current.map((message) =>
          message.id === kickoff.assistantMessageId
            ? { ...message, content: retry ? "" : message.content, error: undefined, status: ChatMessageStatus.STREAMING, updatedAt: new Date().toISOString() }
            : message
        )
      );
      setStreaming(true);
      void startProject(workspace.project.id, { content: kickoff.content, model: selectedModel, abortPrevious: false, projectExpertId: kickoff.projectExpertId, threadId: kickoff.conversationId, expertType: kickoff.expertType, clientTurnId: kickoff.clientTurnId, kickoffTurnId: kickoff.turnId, retryKickoff: retry, turnContext: { projectId: workspace.project.id, conversationId: kickoff.conversationId, threadId: kickoff.conversationId, expertType: kickoff.expertType, turnId: kickoff.turnId, currentStage: workspace.project.stage, currentIntent: ConversationIntent.DESCRIBE_IDEA } });
    },
    [config?.keySaved, expertConversations, onOpenSettings, onSelectExpert, clearMessageProgress, selectedModel, startProject, workspace]
  );

  useEffect(() => {
    const kickoff = workspace?.kickoff;
    if (!kickoff || kickoff.status !== "READY" || !config?.keySaved) return;
    const attemptKey = `${workspace.project.id}:${kickoff.turnId}`;
    if (attemptedKickoffRef.current.has(attemptKey)) return;
    attemptedKickoffRef.current.add(attemptKey);
    startKickoff(kickoff, false);
  }, [config?.keySaved, startKickoff, workspace?.kickoff, workspace?.project.id]);

  const handleSend = useCallback(
    (text: string, metadata: Partial<PersistedChatRequest> = {}, forcedConversation?: ExpertConversation) => {
      const trimmed = text.trim();
      if (!trimmed) return;
      if (
        !professionalMode &&
        activeClarificationQuestion &&
        !metadata.structuredAnswer &&
        !metadata.conversationAction &&
        !forcedConversation
      ) {
        const result = answerActiveClarification(trimmed);
        if (result !== "unavailable") updateDraft("");
        return;
      }
      const mentionTarget = findMentionedExpert(text, expertConversations);
      const explicitTarget = expertConversations.find((c) => c.projectExpertId === metadata.projectExpertId);
      const targetConversation = forcedConversation ?? mentionTarget ?? explicitTarget ?? activeExpertConversation;
      if (!workspace || !selectedModel || !targetConversation) return;
      if (!config?.keySaved) { onOpenSettings(); return; }
      const sendProjectId = workspace.project.id;
      const sendConversationId = targetConversation.id;
      const sendExpertId = targetConversation.projectExpertId;
      const cleanContent = stripLeadingMention(trimmed, targetConversation.expertName);
      onSelectExpert(sendExpertId);
      const clientTurnId = metadata.clientTurnId ?? createClientTurnId();
      const explicitQuestionId = metadata.questionId;
      const explicitMessageId = metadata.sourceMessageId;
      const structuredAnswer = metadata.structuredAnswer;
      const replyToQuestionIds = structuredAnswer?.type === "clarification_batch_answer" ? structuredAnswer.answers.map((a) => a.questionId) : explicitQuestionId ? [explicitQuestionId] : undefined;
      const turnContext = { ...(metadata.turnContext ?? {}), ...workspaceContext, projectId: sendProjectId, conversationId: sendConversationId, threadId: sendConversationId, expertType: targetConversation.expertType, turnId: clientTurnId, replyToMessageId: explicitMessageId, replyToQuestionId: explicitQuestionId, replyToQuestionIds, currentStage: workspace.project.stage, currentIntent: inferConversationIntent(metadata, false), activeQuestionId: explicitQuestionId };
      const now = new Date().toISOString();
      const userMsg: ChatMessage = { id: `pending_user_${clientTurnId}`, role: ChatRole.USER, content: cleanContent, metadata: { projectExpertId: sendExpertId, expertType: targetConversation.expertType, conversationId: sendConversationId, turnId: clientTurnId, clientTurnId, requestTurnId: clientTurnId, replyToMessageId: explicitMessageId, replyToQuestionId: explicitQuestionId, actionType: metadata.conversationAction, automaticHandoff: metadata.automaticHandoff, handoffLabel: metadata.handoffLabel, recoveryOfMessageId: metadata.recoveryOfMessageId, recoveryLabel: metadata.recoveryLabel }, status: ChatMessageStatus.COMPLETED, createdAt: now, updatedAt: now, model: selectedModel };
      const assistantMsg: ChatMessage = { id: `pending_assistant_${clientTurnId}`, role: ChatRole.ASSISTANT, content: "", metadata: { projectExpertId: sendExpertId, expertType: targetConversation.expertType, conversationId: sendConversationId, parentTurnId: clientTurnId, clientTurnId, requestTurnId: clientTurnId }, status: ChatMessageStatus.STREAMING, createdAt: now, updatedAt: now, model: selectedModel };
      activeAssistantIdRef.current = assistantMsg.id;
      activeStreamScopeRef.current = { projectId: sendProjectId, conversationId: sendConversationId, requestId: null, requestTurnId: clientTurnId, assistantMessageId: assistantMsg.id, resolvingPendingItem: false, conversationAction: metadata.conversationAction };
      pendingResolutionRef.current = false;
      clearMessageProgress(assistantMsg.id);
      latestPendingTurnIdRef.current = clientTurnId;
      followLatestMessageRef.current = true;
      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      updateDraft("");
      setStreaming(true);
      void startProject(sendProjectId, { content: cleanContent, model: selectedModel, abortPrevious: true, projectExpertId: sendExpertId, threadId: sendConversationId, expertType: targetConversation.expertType, ...metadata, clientTurnId, turnContext, structuredAnswer, sourceMessageId: explicitMessageId, questionId: explicitQuestionId, textInput: metadata.textInput });
    },
    [activeClarificationQuestion, answerActiveClarification, config?.keySaved, onOpenSettings, onSelectExpert, professionalMode, selectedModel, startProject, updateDraft, workspace, workspaceContext, activeExpertConversation, clearMessageProgress, expertConversations]
  );

  handleSendRef.current = (text, metadata) => handleSend(text, metadata as Partial<PersistedChatRequest>);

  const handleMessageRecoveryAction = useCallback(
    (message: ChatMessage, actionId: string, recoveryLabel?: string) => {
      if (actionId === "open_settings") { onOpenSettings(); return; }
      const source = findRecoverySourceMessage(messages, message);
      if (!source) return;
      const targetConversation = expertConversations.find((c) => c.projectExpertId === message.metadata?.projectExpertId || c.id === message.metadata?.conversationId);
      if (!targetConversation) return;
      onSelectExpert(targetConversation.projectExpertId);
      if (actionId === "revise_request") {
        updateDraft(source.content);
        window.requestAnimationFrame(() => { textareaRef.current?.focus(); textareaRef.current?.setSelectionRange(source.content.length, source.content.length); });
        return;
      }
      if (actionId === "retry") {
        handleSend(source.content, { recoveryOfMessageId: message.id, recoveryLabel: recoveryLabel ?? recoveryEventLabel(message.error) }, targetConversation);
      }
    },
    [expertConversations, handleSend, messages, onOpenSettings, onSelectExpert, updateDraft]
  );

  useAutomaticRecovery({ messages, expertConversations, configKeySaved: Boolean(config?.keySaved), streaming, onRecovery: handleMessageRecoveryAction });

  const automaticRecoveryCandidate = config?.keySaved && !streaming ? findAutomaticLocalRecoveryCandidate(messages, expertConversations) : null;

  useEffect(() => {
    if (!automaticHandoff || streaming) return;
    let canceled = false;
    const run = async () => {
      try {
        const target = expertConversations.find((c) => c.expertType === automaticHandoff.targetExpert) ?? null;
        if (canceled || automaticHandoff.projectId !== activeProjectIdRef.current) return;
        if (!target) throw new Error("\u9879\u76ee\u4e2d\u6ca1\u6709\u53ef\u63a5\u6536\u4ea4\u63a5\u7684\u667a\u80fd\u5de5\u7a0b\u5e08\u3002");
        setAutomaticHandoff(null);
        handleSend(automaticHandoff.prompt, { automaticHandoff: true, handoffLabel: automaticHandoff.label }, target);
      } catch (error) {
        if (canceled) return;
        setAutomaticHandoff(null);
        setAutomaticHandoffError(error instanceof Error ? `\u81ea\u52a8\u4ea4\u63a5\u672a\u5b8c\u6210\uff1a${error.message}` : "\u81ea\u52a8\u4ea4\u63a5\u672a\u5b8c\u6210\uff0c\u8bf7\u9009\u62e9\u667a\u80fd\u5de5\u7a0b\u5e08\u7ee7\u7eed\u3002");
      }
    };
    void run();
    return () => { canceled = true; };
  }, [automaticHandoff, expertConversations, handleSend, streaming]);

  const handleStop = useCallback(async () => {
    const scope = activeStreamScopeRef.current;
    const stoppingProjectId = scope?.projectId ?? projectId;
    if (!stoppingProjectId) return;
    const canceledTurnId = latestPendingTurnIdRef.current;
    const canceledAssistantId = scope?.assistantMessageId ?? activeAssistantIdRef.current;
    const resolvingPendingItem = scope?.resolvingPendingItem ?? pendingResolutionRef.current;
    if (!resolvingPendingItem) settleOptimisticClarification(canceledTurnId, false);
    clearMessageProgress(canceledAssistantId);
    setStreaming(false);
    setMessages((prev) =>
      prev.map((message) =>
        message.id === canceledAssistantId
          ? { ...message, status: resolvingPendingItem ? ChatMessageStatus.COMPLETED : ChatMessageStatus.CANCELED }
          : message
      )
    );
    activeStreamScopeRef.current = null;
    activeAssistantIdRef.current = null;
    latestPendingTurnIdRef.current = null;
    pendingResolutionRef.current = false;
    await stopProject(stoppingProjectId);
  }, [clearMessageProgress, projectId, settleOptimisticClarification, stopProject]);

  useEffect(() => {
    if (!onInteractionControlsChange) return;
    onInteractionControlsChange({ stopStreaming: handleStop, flushDraft });
    return () => onInteractionControlsChange(null);
  }, [flushDraft, handleStop, onInteractionControlsChange]);

  const handleAction = (messageId: string, action: ConversationAction) => {
    const source = messages.find((m) => m.id === messageId);
    if (action.action === ConversationActionType.VIEW_PROJECT_PROPOSAL && workspace) {
      const proposalId = source?.structuredPayload?.type === ConversationResponseType.PROPOSAL_ACTION ? source.structuredPayload.proposalId : undefined;
      onOpenArtifact(`artifact_proposal_${workspace.project.id}`, proposalId ? `artifact_version_proposal_${proposalId}` : undefined);
      return;
    }
    handleSend(action.label, { sourceMessageId: messageId, projectExpertId: source?.metadata?.projectExpertId, conversationAction: action.action });
  };

  const handleImportMessageCode = useCallback(
    async (messageId: string) => {
      const currentProjectId = workspace?.project.id;
      if (!currentProjectId) return;
      const response = await importMessageCode(currentProjectId, messageId);
      await onReloadProject(currentProjectId);
      if (response.codeRun.artifactId) onOpenArtifact(response.codeRun.artifactId, response.codeRun.artifactVersionId);
    },
    [onOpenArtifact, onReloadProject, workspace?.project.id]
  );

  const getExpertPresentation = useCallback(
    (msg: ChatMessage): ExpertPresentation => professionalMode
      ? messageExpertPresentation(workspace!, msg)
      : { name: "掌问", glyph: "问", semanticType: "problem_guide" },
    [professionalMode, workspace]
  );

  const clarificationDraftKeyPrefix = projectId ?? "no-project";
  const RootElement = rootElement;

  return (
    <RootElement className="center-chat" data-testid="center-chat">
      <div className="chat-messages" data-testid="chat-messages" ref={messagesContainerRef} onScroll={handleMessagesScroll}>
        {!workspace ? (
          <div className="chat-empty-state">
            <h2>{"\u5f00\u59cb\u4e00\u4e2a\u521b\u5ba2\u9879\u76ee"}</h2>
            <p>{"\u8bf7\u4ece\u5de6\u4fa7\u65b0\u5efa\u9879\u76ee\uff0c\u6216\u9009\u62e9\u5df2\u6709\u9879\u76ee\u7ee7\u7eed\u5bf9\u8bdd\u3002"}</p>
          </div>
        ) : (
          <>
            {professionalMode && (
              <div className="chat-project-toolbar" aria-label={"\u4e13\u4e1a\u6a21\u5f0f\u6a21\u578b\u8bbe\u7f6e"}>
                <span>{"\u5f53\u524d\u6a21\u578b"}</span>
                <select aria-label={"\u5f53\u524d\u6a21\u578b"} value={selectedModel} onChange={(event) => void onSelectModel(workspace.project.id, event.target.value as LLMModelId)}>
                  {models.map((model) => (<option key={model.id} value={model.id}>{model.label}</option>))}
                </select>
              </div>
            )}
            {messages.length === 0 && (
              <div className="chat-empty-state chat-empty-state-project">
                <h2>{workspace.project.name}</h2>
                <p>{professionalMode
                  ? "这是项目唯一对话。可选择下方专家，或输入 @专家 指定谁来回复。"
                  : "这是项目唯一对话。掌问会根据当前任务自动协助澄清、实现和结构设计。"}</p>
              </div>
            )}
            <MessageList
              messages={messages}
              workspace={workspace}
              streaming={streaming}
              progressByMessageId={progressByMessageId}
              answeredCards={answeredCards}
              clarificationDrafts={clarificationDrafts}
              clarificationDraftKeyPrefix={clarificationDraftKeyPrefix}
              automaticRecoveryCandidateId={automaticRecoveryCandidate?.id ?? null}
              expertConversations={expertConversations}
              engineeringCodeRun={engineeringState?.data.code ?? null}
              professionalMode={professionalMode}
              creatorWorkflow={creatorWorkflow}
              getExpertPresentation={getExpertPresentation}
              onClarificationDraftChange={handleClarificationDraftChange}
              onSubmitClarification={handleSubmitClarification}
              onAction={handleAction}
              onRecoveryAction={(msg, actionId) => handleMessageRecoveryAction(msg, actionId)}
              onOpenSolutionArtifact={onOpenArtifact}
              onOpenHardwareSelection={onOpenHardwareSelection}
              onImportPython={handleImportMessageCode}
              onRetryKickoff={workspace.kickoff ? () => startKickoff(workspace.kickoff as ProjectKickoff, true) : undefined}
            />
            {automaticHandoffError && (<p className="expert-handoff-error" role="alert">{automaticHandoffError}</p>)}
            <ProjectConfirmationCard
              workspace={workspace}
              onResolvePendingItem={handleResolvePendingItem}
              onDismissPendingItem={onDismissPendingItem}
              onReloadProject={onReloadProject}
              onOpenArtifact={onOpenArtifact}
              refreshRevision={confirmationRefreshRevision}
              engineeringState={engineeringState}
            />
          </>
        )}
      </div>
      {workspace && activeClarificationMessage && (
        <ClarificationDock
          message={activeClarificationMessage}
          streaming={streaming}
          professionalMode={professionalMode}
          answeredCards={answeredCards}
          clarificationDraft={clarificationDrafts[clarificationDraftKey(clarificationDraftKeyPrefix, activeClarificationMessage.id)] ?? {}}
          onClarificationDraftChange={handleClarificationDraftChange}
          onSubmitClarification={handleSubmitClarification}
          onAction={handleAction}
          onOpenSolutionArtifact={onOpenArtifact}
          onOpenHardwareSelection={onOpenHardwareSelection}
        />
      )}
      <DraftSaveIndicator
        draftSaveError={draftSaveError}
        draftSaving={draftSaving}
        isDirty={isDirty}
        hasSavedDraft={Boolean(workspace?.draft.updatedAt)}
        onRetry={() => void flushDraft().catch(() => undefined)}
      />
      {workspace && (
        <ChatInput
          value={draft}
          onChange={updateDraft}
          onSend={handleSend}
          onStop={handleStop}
          disabledReason={disabledReason}
          streaming={streaming}
          inputRef={textareaRef}
          experts={professionalMode ? expertOptions(workspace) : []}
          availableExperts={professionalMode && onAddExpert ? availableExpertOptions(workspace) : []}
          selectedExpertId={professionalMode ? activeExpertConversation?.projectExpertId ?? null : null}
          onSelectExpert={professionalMode ? onSelectExpert : undefined}
          onAddExpert={professionalMode ? onAddExpert : undefined}
          activeQuestion={professionalMode ? null : activeClarificationQuestion?.text ?? null}
          onUseRecommendation={
            !professionalMode && activeClarificationQuestion
              ? () => {
                  const result = answerActiveClarification(null, true);
                  if (result !== "unavailable") updateDraft("");
                }
              : undefined
          }
        />
      )}
    </RootElement>
  );
}

function mergeProjectMessages(conversations: ExpertConversation[]): ChatMessage[] {
  return conversations
    .flatMap((conversation) =>
      conversation.messages.map((message) => ({
        ...message,
        metadata: { ...message.metadata, projectExpertId: message.metadata?.projectExpertId ?? conversation.projectExpertId, expertType: message.metadata?.expertType ?? conversation.expertType, conversationId: message.metadata?.conversationId ?? conversation.id },
      }))
    )
    .sort((left, right) => left.createdAt.localeCompare(right.createdAt));
}

function findMentionedExpert(text: string, conversations: ExpertConversation[]): ExpertConversation | null {
  return conversations.find((c) => new RegExp(`^@${escapeRegExp(c.expertName)}(?:\\s|$)`).test(text.trim())) ?? null;
}

function stripLeadingMention(text: string, expertName: string): string {
  const stripped = text.replace(new RegExp(`^@${escapeRegExp(expertName)}(?:\\s+|$)`), "").trim();
  return stripped || text;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

type ExpertSemanticType = "problem_guide" | "smart_engineer" | "structure_engineer" | "assistant";

function messageExpertPresentation(workspace: ProjectWorkspace, message: ChatMessage): ExpertPresentation {
  const projectExpert = (workspace.experts ?? []).find((e) => e.id === message.metadata?.projectExpertId);
  const semanticType = normalizeExpertType(message.metadata?.expertType ?? projectExpert?.expertType);
  const definition = (workspace.expertDefinitions ?? []).find((c) => c.id === projectExpert?.expertDefinitionId || c.type === message.metadata?.expertType || c.type === semanticType);
  const fallbackDefinition = DEFAULT_THREE_EXPERT_DEFINITIONS.find((c) => c.type === semanticType);
  const icon = definition?.icon ?? fallbackDefinition?.icon ?? "spark";
  return { name: getExpertDisplayName(message.metadata?.expertType ?? projectExpert?.expertType, definition?.name ?? fallbackDefinition?.name ?? "\u638c\u95ee"), glyph: expertAvatarGlyph(icon), semanticType };
}

function normalizeExpertType(expertType: ExpertType | string | undefined): ExpertSemanticType {
  if (expertType === "problem_guide" || expertType === "question_guide" || expertType === "ideator" || expertType === "educator") return "problem_guide";
  if (expertType === "smart_engineer" || expertType === "intelligent_engineer" || expertType === "open_hardware_designer") return "smart_engineer";
  if (expertType === "structure_engineer" || expertType === "structure_designer" || expertType === "three_d_structure_designer") return "structure_engineer";
  return "assistant";
}

function expertAvatarGlyph(icon: string): string {
  if (icon === "cpu") return "\u2699";
  if (icon === "box") return "\u25c7";
  return "\u2726";
}

function expertOptions(workspace: ProjectWorkspace) {
  const definitionMap = new Map((workspace.expertDefinitions ?? []).map((d) => [d.type, d]));
  return (workspace.experts ?? []).filter((e) => !e.archivedLegacyThread && !e.removedAt).map((expert) => ({ id: expert.id, type: expert.expertType, name: getExpertDisplayName(expert.expertType, definitionMap.get(expert.expertType)?.name), icon: definitionMap.get(expert.expertType)?.icon ?? "spark" }));
}

function availableExpertOptions(workspace: ProjectWorkspace) {
  const activeTypes = new Set((workspace.experts ?? []).filter((e) => !e.archivedLegacyThread && !e.removedAt).map((e) => e.expertType));
  const definitions = new Map<ExpertType, ExpertDefinition>();
  for (const d of [...(workspace.expertDefinitions ?? []), ...DEFAULT_THREE_EXPERT_DEFINITIONS]) { if (!definitions.has(d.type)) definitions.set(d.type, d); }
  return THREE_EXPERT_TYPES.filter((type) => !activeTypes.has(type)).map((type) => { const d = definitions.get(type); return { id: d?.id ?? `definition_${type}`, type, name: getExpertDisplayName(type, d?.name), icon: d?.icon ?? "spark" }; });
}

function createClientTurnId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return `turn_${crypto.randomUUID().replaceAll("-", "")}`;
  return `turn_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

function inferConversationIntent(metadata: Partial<PersistedChatRequest>, hasActiveTextQuestion: boolean) {
  if (metadata.conversationAction === "generate_solution") return ConversationIntent.GENERATE_SOLUTION;
  if (metadata.conversationAction === "modify_solution") return ConversationIntent.REVISE_SOLUTION;
  if (metadata.conversationAction === "confirm_solution") return ConversationIntent.CONFIRM_SOLUTION;
  if (metadata.conversationAction === "generate_project_proposal" || metadata.conversationAction === "confirm_solution_and_generate_project_proposal" || metadata.conversationAction === "generate_lesson_version" || metadata.conversationAction === "confirm_solution_and_generate_lesson_version") return ConversationIntent.GENERATE_PROPOSAL;
  if (metadata.questionId || metadata.structuredAnswer || hasActiveTextQuestion) return ConversationIntent.ANSWER_QUESTION;
  return ConversationIntent.DESCRIBE_IDEA;
}
