/**
 * 掌问共享契约 — API 请求/响应类型
 */
import type {
  AgentCapability,
  ArtifactKind,
  ArtifactPreviewKind,
  ArtifactStatus,
  CadFileKind,
  CadJobPhase,
  CadJobStatus,
  CadMountSurface,
  CadOutputRole,
  CadRunStatus,
  CadTemplateKind,
  ChatMessageStatus,
  ChatProgressAction,
  ChatProgressStatus,
  ChatRole,
  ClarificationQuestionMode,
  ClarificationQuestionType,
  CodeFileKind,
  CodeRevisionSource,
  CodeRunStatus,
  CodeValidationKind,
  CodeValidationStatus,
  ConversationAnswerType,
  ConversationActionType,
  ConversationIntent,
  ConversationResponseType,
  CoordinatorSeverity,
  DeviceOperationKind,
  DeviceOperationPhase,
  DeviceOperationStatus,
  DeviceSessionStatus,
  DeviceTerminalStatus,
  DomainArtifactStatus,
  DomainTaskStatus,
  ExpertType,
  ExpertWorkspaceStatus,
  FloatingWindowKind,
  HardwareCategory,
  HardwareComponentStatus,
  HardwareRuleOperator,
  HardwareSkillSourceKind,
  HardwareSkillStatus,
  HandoffStatus,
  LLMErrorCode,
  LLMModelId,
  LessonDocumentKind,
  LessonRunStatus,
  MvpReadinessItemId,
  MvpReadinessStatus,
  ProjectPackageConflictStrategy,
  ProjectPackageItemKind,
  ProjectPackageStatus,
  ProjectPersistenceVersion,
  ProjectProgressConsistency,
  ProjectProgressStatus,
  ProjectExpertStatus,
  ProjectStage,
  ProjectWorkflowState,
  PendingItemPriority,
  PendingItemStatus,
  PendingItemKind,
  PendingItemActionType,
  LLMProviderId,
  ModelRouteStrategy,
  ProposalExportFormat,
  ProposalStatus,
  SharedFactStatus,
  SkillConfirmationPolicy,
  SkillOrigin,
  SkillPermission,
  SkillRiskLevel,
  SpecFileKind,
  SpecRunStatus,
  SolutionStatus,
  SerialPortStatus,
  SerialPortType,
  StreamChunkType,
  TaskStatus,
  TechnicalLevel,
  ThinkingMode,
  BudgetPreference,
  UserPersona,
  ValidationSeverity,
} from "./enums.js";

/** 健康检查响应 */
export interface HealthResponse {
  status: "ok" | "degraded" | "error";
  version: string;
  uptimeSeconds: number;
  llmTestMode?: "standard" | "fake" | "paid";
  usesPaidLlm?: boolean;
}

/** 统一错误结构 */
export interface ZwError {
  code: string;
  message: string;
  userActions: UserAction[];
  technicalDetails?: string;
  retryable: boolean;
}

export interface UserAction {
  id: string;
  label: string;
}

export interface TokenUsage {
  promptTokens?: number;
  completionTokens?: number;
  totalTokens?: number;
}

export interface ChatMessageMetadata {
  turnId?: string;
  parentTurnId?: string;
  clientTurnId?: string;
  requestTurnId?: string;
  replyToMessageId?: MessageId;
  replyToQuestionId?: string;
  replyToQuestionIds?: string[];
  answerType?: ConversationAnswerType;
  answerOptionIds?: string[];
  clarificationAnswers?: ClarificationAnswer[];
  actionType?: ConversationActionType | string;
  projectExpertId?: string;
  expertType?: ExpertType;
  conversationId?: ConversationId;
  automaticHandoff?: boolean;
  handoffLabel?: string;
  recoveryOfMessageId?: MessageId;
  recoveryLabel?: string;
}

export interface ConversationClarificationQuestion {
  id: string;
  text: string;
  mode: ClarificationQuestionMode;
  options?: ClarificationOption[];
  allowCustomInput: boolean;
  required: boolean;
  answered?: boolean;
  answer?: ClarificationAnswer;
}

export interface ConversationAction {
  id: string;
  label: string;
  action: ConversationActionType;
  description?: string;
  recommended?: boolean;
  disabled?: boolean;
}

export interface ClarificationResponse {
  type: typeof ConversationResponseType.CLARIFICATION;
  summary?: string;
  question: ConversationClarificationQuestion;
  questions?: ConversationClarificationQuestion[];
  completeness: number;
  projectDraft?: import("./creator.js").ConversationProjectDraftV1;
}

export interface NextActionResponse {
  type: typeof ConversationResponseType.NEXT_ACTION;
  message: string;
  actions: ConversationAction[];
  projectDraft?: import("./creator.js").ConversationProjectDraftV1;
}

export interface SolutionConversationResponse {
  type: typeof ConversationResponseType.SOLUTION;
  message: string;
  solutionId?: string;
  solutionVersion?: number;
  actions: ConversationAction[];
}

export interface ProposalActionResponse {
  type: typeof ConversationResponseType.PROPOSAL_ACTION;
  message: string;
  proposalId?: string;
  proposalVersion?: number;
  actions: ConversationAction[];
  handoff?: ConversationExpertHandoff;
}

export interface ConversationExpertHandoff {
  automatic: true;
  targetExpert: ExpertType;
  label: string;
  prompt: string;
}

export interface SystemNoticeResponse {
  type: typeof ConversationResponseType.SYSTEM_NOTICE;
  severity: "info" | "warning" | "error";
  message: string;
  actions?: ConversationAction[];
}

/** 三师识别到能力缺口后，引导用户打开本地项目硬件选择器。 */
export interface HardwareSelectionResponse {
  type: typeof ConversationResponseType.HARDWARE_SELECTION;
  summary: string;
  missingCapabilities: string[];
}

export interface SolutionCardSection {
  id: string;
  title: string;
  content: string;
  summary?: string;
}

export interface SolutionSectionChange {
  sectionId: string;
  sectionTitle: string;
  changeType: "updated" | "added" | "removed";
  before?: unknown;
  after?: unknown;
  reason: string;
}

export interface SolutionRevision {
  id: string;
  projectId: ProjectId;
  baseSolutionId: string;
  baseVersion: number;
  newSolutionId: string;
  newVersion: number;
  userRequest: string;
  changedSections: SolutionSectionChange[];
  preservedSections: string[];
  impactSummary: string[];
  createdAt: string;
}

export interface SolutionCardMessage {
  type: typeof ConversationResponseType.SOLUTION_CARD;
  solutionId: string;
  artifactId?: string | null;
  artifactVersionId?: string | null;
  version: number;
  basedOnVersion?: number | null;
  status: SolutionStatus;
  title: string;
  summary: string;
  sections: SolutionCardSection[];
  changeSummary?: string[];
  revision?: SolutionRevision | null;
  actions: ConversationAction[];
}

export interface CodeArtifactMessageFile {
  path: string;
  language: string;
}

export interface CodeArtifactMessage {
  type: typeof ConversationResponseType.CODE_ARTIFACT;
  codeRunId: string;
  artifactId: string | null;
  artifactVersionId: string | null;
  version: number;
  status: CodeRunStatus;
  runtime: import("./enums.js").CodeRuntime;
  entrypoint: string;
  title: string;
  summary: string;
  files: CodeArtifactMessageFile[];
}

/** 结构工程师生成的 CAD 产物在中央对话中的轻量投影。 */
export interface CadArtifactMessage {
  type: typeof ConversationResponseType.CAD_ARTIFACT;
  cadRunId: string;
  artifactId: string | null;
  artifactVersionId: string | null;
  version: number;
  status: CadRunStatus;
  title: string;
  summary: string;
}

export type ConversationResponse =
  | ClarificationResponse
  | NextActionResponse
  | SolutionConversationResponse
  | SolutionCardMessage
  | CodeArtifactMessage
  | CadArtifactMessage
  | HardwareSelectionResponse
  | ProposalActionResponse
  | SystemNoticeResponse;

export interface RequirementCompleteness {
  requiredFields: string[];
  completedFields: string[];
  missingFields: string[];
  blockingFields: string[];
  score: number;
  readyForSolution: boolean;
}

export interface ConversationTurnContext {
  projectId: ProjectId;
  conversationId: ConversationId;
  threadId?: ConversationId;
  expertType?: ExpertType;
  turnId: string;
  parentTurnId?: string;
  replyToMessageId?: MessageId;
  replyToQuestionId?: string;
  replyToQuestionIds?: string[];
  currentStage: ProjectStage;
  currentIntent: ConversationIntent;
  activeQuestionId?: string;
  activeSolutionId?: string;
  activeSolutionVersion?: number;
  activeProposalId?: string;
  activeArtifactId?: string;
  /** V2 页面导航上下文，只用于聚焦回复，不授予本地执行权限。 */
  workspaceKind?: "overview" | "engineering" | "structure" | "delivery";
  workspaceView?: string;
  projectVersion?: number;
}

export interface ConversationStatePatch {
  stage?: ProjectStage;
  workflowState?: ProjectWorkflowState;
  activeQuestionId?: string | null;
  activeSolutionId?: string | null;
  activeSolutionVersion?: number | null;
  activeProposalId?: string | null;
  activeArtifactId?: string | null;
  completeness?: RequirementCompleteness;
}

export interface ConversationResponseEnvelope {
  projectId: ProjectId;
  conversationId: ConversationId;
  requestTurnId: string;
  responseTurnId: string;
  responseType:
    | "clarification"
    | "next_action"
    | "solution_card"
    | "solution_revision"
    | "proposal_card"
    | "cad_artifact"
    | "status"
    | "error";
  content: ConversationResponse | unknown;
  statePatch: ConversationStatePatch;
}

export interface LLMError {
  code: LLMErrorCode;
  message: string;
  retryable: boolean;
  userActions: UserAction[];
  providerStatus?: number;
}

export interface ModelConfig {
  id: LLMModelId;
  label: string;
  provider: LLMProviderId;
  supportsThinking: boolean;
  supportsStreaming: boolean;
  isCustom?: boolean;
}

export interface LLMConfig {
  provider: LLMProviderId;
  baseUrl: string;
  defaultModel: LLMModelId;
  customModels?: ModelConfig[];
  thinkingMode: ThinkingMode;
  reasoningEffort: "high" | "max" | null;
  timeoutSeconds: number;
  keySaved: boolean;
  maskedApiKey: string | null;
  updatedAt: string | null;
}

export interface SaveLLMConfigRequest {
  provider: LLMProviderId;
  baseUrl: string;
  defaultModel: LLMModelId;
  customModels?: ModelConfig[];
  thinkingMode: ThinkingMode;
  reasoningEffort?: "high" | "max" | null;
  timeoutSeconds: number;
  apiKey?: string;
}

export interface LLMConfigResponse {
  config: LLMConfig;
}

export interface ModelsResponse {
  models: ModelConfig[];
}

export interface ConnectionTestRequest {
  config?: SaveLLMConfigRequest;
  apiKey?: string;
}

export interface ConnectionTestResult {
  ok: boolean;
  message: string;
  provider: LLMProviderId;
  model: LLMModelId;
  latencyMs?: number;
  error?: LLMError;
}

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  structuredPayload?: ConversationResponse | null;
  metadata?: ChatMessageMetadata | null;
  reasoningContent?: string;
  status: ChatMessageStatus;
  createdAt: string;
  updatedAt: string;
  model?: LLMModelId;
  error?: LLMError;
  usage?: TokenUsage;
}

export interface ChatRequest {
  messages: ChatMessage[];
  model?: LLMModelId;
  abortPrevious?: boolean;
}

export interface ChatResponse {
  message: ChatMessage;
  usage?: TokenUsage;
  finishReason?: string;
}

export interface ChatProgress {
  id: string;
  action: ChatProgressAction;
  label: string;
  status: ChatProgressStatus;
  sequence: number;
}

interface StreamChunkBase {
  requestId: string;
  messageId: string;
  requestTurnId?: string;
  responseTurnId?: string;
  delta?: string;
  accumulatedContent?: string;
  accumulatedReasoning?: string;
  model?: LLMModelId;
  error?: LLMError;
  usage?: TokenUsage;
  structuredPayload?: ConversationResponse | null;
  envelope?: ConversationResponseEnvelope | null;
}

export type StreamChunk =
  | (StreamChunkBase & {
      type: "PROGRESS";
      progress: ChatProgress;
    })
  | (StreamChunkBase & {
      type: Exclude<StreamChunkType, "PROGRESS">;
      progress?: never;
    });

export interface CancelChatResponse {
  requestId: string;
  canceled: boolean;
}

export type ProjectId = string;
export type ConversationId = string;
export type MessageId = string;

export interface ProjectProfile {
  initialIdea: string;
}

export interface ExpertDefinition {
  id: string;
  type: ExpertType;
  name: string;
  description: string;
  icon: string;
  builtIn: boolean;
  skillIds: string[];
  supportedArtifactTypes: string[];
}

export interface ProjectExpert {
  id: string;
  projectId: ProjectId;
  expertDefinitionId: string;
  expertType: ExpertType;
  legacyExpertType?: ExpertType | string | null;
  archivedLegacyThread?: boolean;
  conversationId: ConversationId;
  privateMemoryId: string;
  status: ProjectExpertStatus;
  workspaceStatus?: ExpertWorkspaceStatus | null;
  currentTask?: string | null;
  addedAt: string;
  removedAt?: string | null;
}

export interface SharedFact {
  id: string;
  projectId?: ProjectId;
  field: string;
  key?: string;
  value: unknown;
  status?: SharedFactStatus;
  sourceType?: "user" | "expert" | "artifact" | "device" | "system";
  sourceId?: string | null;
  sourceExpertId?: string | null;
  proposedBy?: ExpertType | string | null;
  confirmed: boolean;
  confirmedBy?: "user" | "system_rule" | string | null;
  confirmedAt?: string | null;
  supersededBy?: string | null;
  affectsArtifactIds?: string[];
  createdAt?: string;
  updatedAt: string;
}

export interface SharedDecision {
  id: string;
  projectId?: ProjectId;
  title: string;
  value: unknown;
  status?: SharedFactStatus;
  reason?: string;
  sourceExpertId?: string | null;
  proposedBy?: ExpertType | string | null;
  affectedArtifactIds?: string[];
  createdAt?: string;
  updatedAt?: string;
  confirmedAt?: string | null;
  confirmedBy?: "user" | "system_rule" | string | null;
}

export interface ProjectDecision extends SharedDecision {
  projectId: ProjectId;
  status: SharedFactStatus;
  reason: string;
  confirmedBy?: "user" | "system_rule" | string | null;
}

export interface PendingItem {
  id: string;
  projectId: ProjectId;
  title: string;
  description: string;
  priority: PendingItemPriority;
  reason: string;
  affectedExperts: ExpertType[];
  options?: string[];
  status: PendingItemStatus;
  kind: PendingItemKind;
  actionType?: PendingItemActionType | null;
  authorizationId?: string | null;
  isHighlighted: boolean;
  criticalPath?: boolean;
  createdAt: string;
  updatedAt?: string;
}

export interface ProjectTask {
  id: string;
  projectId: ProjectId;
  title: string;
  description: string;
  ownerExpert: ExpertType;
  status: DomainTaskStatus;
  dependencyTaskIds: string[];
  artifactIds: string[];
  currentPendingItemId?: string | null;
  createdAt: string;
  updatedAt?: string;
}

export interface Handoff {
  id: string;
  projectId: ProjectId;
  fromExpert: ExpertType;
  toExpert: ExpertType;
  handoffType: "clarification" | "implementation" | "structure" | "review" | "change_request";
  status: HandoffStatus;
  summary?: string;
  confirmedRequirements: string[];
  sharedFactIds?: string[];
  relatedArtifacts: string[];
  requiredOutputs: string[];
  dependencies: string[];
  openQuestions: string[];
  currentPendingItemId?: string | null;
  createdAt: string;
  updatedAt?: string;
}

export interface ActiveArtifactVersion {
  artifactId: string;
  artifactVersionId: string | null;
  artifactType: string;
  version: number | null;
  ownerExpertId?: string | null;
  status: string;
}

export interface ProjectSharedContext {
  id: string;
  projectId: ProjectId;
  revision: number;
  goals: SharedFact[];
  constraints: SharedFact[];
  requirements: SharedFact[];
  decisions: ProjectDecision[];
  confirmedFacts?: SharedFact[];
  openQuestions?: SharedFact[];
  currentPendingItem?: PendingItem | null;
  activeArtifactVersions: ActiveArtifactVersion[];
  deliveryTrack?: "project" | "lesson";
  updatedAt: string;
}

export interface SharedContextChange {
  id: string;
  projectId: ProjectId;
  sourceExpertId: string;
  changeType: "proposed" | "confirmed" | "system";
  field: string;
  previousValue?: unknown;
  nextValue: unknown;
  reason: string;
  createdAt: string;
}

export interface CoordinatorItem {
  id: string;
  title: string;
  description: string;
  targetExpertId?: string | null;
  targetArtifactId?: string | null;
  actionLabel?: string | null;
  severity: CoordinatorSeverity;
}

export interface CoordinatorIssue {
  id: string;
  title: string;
  description: string;
  severity: CoordinatorSeverity;
  relatedExpertIds: string[];
  relatedArtifactIds: string[];
}

export interface ProjectCoordinatorState {
  id: string;
  projectId: ProjectId;
  currentItem: CoordinatorItem | null;
  currentPendingItem?: PendingItem | null;
  pendingItems?: PendingItem[];
  expertStatuses: ProjectExpert[];
  conflicts: CoordinatorIssue[];
  dependencies: CoordinatorIssue[];
  updatedAt: string;
}

export interface Project {
  id: ProjectId;
  name: string;
  stage: ProjectStage;
  profile: ProjectProfile;
  conversationId: ConversationId;
  activeExpertIds?: string[];
  activeExpertId?: string | null;
  sharedContextId?: string | null;
  coordinatorStateId?: string | null;
  selectedModel: LLMModelId;
  archivedAt: string | null;
  createdAt: string;
  updatedAt: string;
  lastOpenedAt: string | null;
  schemaVersion: ProjectPersistenceVersion;
}

export interface ProjectSummary {
  id: ProjectId;
  name: string;
  stage: ProjectStage;
  activeExpertIds?: string[];
  selectedModel: LLMModelId;
  messageCount: number;
  draftUpdatedAt: string | null;
  archivedAt: string | null;
  updatedAt: string;
  lastOpenedAt: string | null;
}

export interface Conversation {
  id: ConversationId;
  projectId: ProjectId;
  messages: ChatMessage[];
  updatedAt: string;
}

export interface Draft {
  projectId: ProjectId;
  content: string;
  updatedAt: string | null;
  projectExpertId?: string | null;
}

export interface ExpertConversation {
  id: ConversationId;
  projectId: ProjectId;
  projectExpertId: string;
  expertType: ExpertType;
  legacyExpertType?: ExpertType | string | null;
  archivedLegacyThread?: boolean;
  expertName: string;
  messages: ChatMessage[];
  draft: Draft;
  activeQuestionId?: string | null;
  activeTurnId?: string | null;
  updatedAt: string;
}

export type ProjectKickoffStatus =
  | "READY"
  | "PENDING"
  | "STREAMING"
  | "COMPLETED"
  | "FAILED"
  | "CANCELED";

export interface ProjectKickoff {
  turnId: string;
  responseTurnId: string;
  clientTurnId: string;
  userMessageId: MessageId;
  assistantMessageId: MessageId;
  projectExpertId: string;
  conversationId: ConversationId;
  expertType: ExpertType;
  content: string;
  status: ProjectKickoffStatus;
  retryable: boolean;
}

export interface ProjectWorkspace {
  project: Project;
  conversation: Conversation;
  draft: Draft;
  experts?: ProjectExpert[];
  expertDefinitions?: ExpertDefinition[];
  expertConversations?: ExpertConversation[];
  sharedContext?: ProjectSharedContext | null;
  coordinator?: ProjectCoordinatorState | null;
  kickoff?: ProjectKickoff | null;
}

export interface AppWorkspaceState {
  schemaVersion: ProjectPersistenceVersion;
  projects: ProjectSummary[];
  activeProjectId: ProjectId | null;
}

export interface CreateProjectRequest {
  name?: string;
  initialIdea: string;
  /** 用户已有或希望优先复用的组件；由 Sidecar 重新校验，不等同于完整 BOM。 */
  selectedHardwareIds?: string[];
  selectedModel?: LLMModelId;
  selectedExpertTypes?: ExpertType[];
  initialExpert?: ExpertType;
  routerResult?: RouterOutput;
  expertSelectionMode?: "auto" | "manual";
  idempotencyKey?: string;
}

export interface SuggestProjectRequest {
  initialIdea?: string;
  text?: string;
  /** 用户已有或希望优先复用的组件；空数组表示由掌问按需求推荐。 */
  selectedHardwareIds?: string[];
  userSelectedExpert?: ExpertType;
  useModelRouting?: boolean;
}

export interface RouterOutput {
  intent: string;
  projectName: string;
  initialExpert: ExpertType;
  recommendedExperts: ExpertType[];
  confidence: number;
  reason: string;
  requiresClarification: boolean;
}

export interface SuggestedProject {
  name: string;
  initialIdea: string;
  recommendedExpertTypes: ExpertType[];
  availableExperts: ExpertDefinition[];
  initialExpert: ExpertType;
  routerResult: RouterOutput;
  reason: string;
  confidence: number;
  requiresClarification: boolean;
  /** Sidecar Rule Engine 生成的中文提醒；空数组表示没有非阻塞警告。 */
  selectedHardwareWarnings?: string[];
}

export interface SuggestProjectResponse {
  suggestion: SuggestedProject;
}

export interface UpdateProjectRequest {
  name?: string;
  selectedModel?: LLMModelId;
}

export interface UpdateProjectHardwareRequest {
  selectedHardwareIds: string[];
}

export interface UpdateProjectHardwareResponse {
  workspace: ProjectWorkspace;
  selectedHardwareWarnings: string[];
}

export interface AuthAccount {
  id: string;
  username: string;
  displayName: string;
  createdAt: string;
}

export interface EmailAccount {
  id: string;
  email: string;
  displayName: string;
  emailVerified: boolean;
  createdAt: string;
}

export interface AccountProfile {
  persona?: UserPersona;
  technicalLevel?: TechnicalLevel;
  preferredBoards: string[];
  budgetPreference?: BudgetPreference;
  needsLesson: boolean;
  completed: boolean;
}

export interface RegisterEmailAccountRequest {
  email: string;
  displayName: string;
  password: string;
}

export interface EmailChallengeResponse {
  challengeId: string;
  expiresAt: string;
  message: string;
}

export interface VerifyEmailRequest {
  challengeId: string;
  code: string;
}

export interface ResendVerificationRequest {
  email: string;
}

export interface EmailLoginRequest {
  email: string;
  password: string;
}

export interface PasswordResetRequest {
  email: string;
}

export interface PasswordResetConfirmRequest {
  challengeId: string;
  code: string;
  newPassword: string;
}

export interface EmailAuthResultResponse {
  account: EmailAccount;
  profile: AccountProfile;
  sessionToken: string;
  expiresAt: string;
  offlineLeaseExpiresAt: string;
}

export interface AccountProfileResponse {
  account: EmailAccount;
  profile: AccountProfile;
}

export type UpdateAccountProfileRequest = AccountProfile;

export interface LegacyProjectClaimStatus {
  unclaimedProjectCount: number;
  decisionRecorded: boolean;
}

export interface ClaimLegacyProjectsRequest {
  claimAll: boolean;
}

export interface ClaimLegacyProjectsResponse {
  claimedProjectCount: number;
  decisionRecorded: boolean;
}

export interface ProjectCurrentAction {
  id: string;
  title: string;
  description: string;
  actionType?: PendingItemActionType;
  blocking: boolean;
}

export interface ProjectArtifactSummary {
  draftCount: number;
  formalCount: number;
  message: string;
}

export interface ProjectReadinessDimension {
  id: "HARDWARE" | "SPECIFICATION" | "CODE" | "TESTING" | "DEPLOYMENT";
  label: string;
  status: MvpReadinessStatus;
  message: string;
}

export interface ProjectProgressSnapshot {
  projectId: string;
  revision: number;
  stage: ProjectStage;
  stageLabel: string;
  status: ProjectProgressStatus;
  currentAction?: ProjectCurrentAction;
  readiness: MvpReadinessReport;
  readinessSummary: ProjectReadinessDimension[];
  artifacts: ProjectArtifactSummary;
  consistency: ProjectProgressConsistency;
  consistencyMessages: string[];
}

export interface ProjectProgressResponse {
  progress: ProjectProgressSnapshot;
}

export interface DuplicateProjectRequest {
  name?: string;
}

export interface DuplicateProjectResponse {
  workspace: ProjectWorkspace;
}

export interface PermanentDeleteProjectRequest {
  confirmationName: string;
}

export interface PermanentDeleteProjectResponse {
  deletedProjectId: string;
  backupId: string;
  backupCreatedAt: string;
  projects: ProjectSummary[];
  activeProjectId?: string;
}

export interface AuthStatusResponse {
  hasAccounts: boolean;
  hasLocalAccounts: boolean;
  cloudAuthConfigured: boolean;
}

export interface RegisterAccountRequest {
  username: string;
  displayName: string;
  password: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface AuthResultResponse {
  account: AuthAccount;
  sessionToken: string;
  expiresAt: string;
}

export interface AuthSessionResponse {
  account: AuthAccount;
  expiresAt: string;
}

export interface LogoutResponse {
  loggedOut: boolean;
}

export interface ArchiveProjectRequest {
  archived: boolean;
}

export interface AddProjectExpertRequest {
  expertType: ExpertType;
  activate?: boolean;
}

export interface RemoveProjectExpertRequest {
  confirmImpact?: boolean;
}

export interface SaveDraftRequest {
  content: string;
  projectExpertId?: string | null;
}

export interface ProjectListResponse {
  projects: ProjectSummary[];
  activeProjectId: ProjectId | null;
}

export interface ProjectWorkspaceResponse {
  workspace: ProjectWorkspace;
}

export interface PersistedChatRequest {
  content: string;
  model?: LLMModelId;
  abortPrevious?: boolean;
  projectExpertId?: string;
  threadId?: ConversationId;
  expertType?: ExpertType;
  clientTurnId?: string;
  kickoffTurnId?: string;
  retryKickoff?: boolean;
  turnContext?: ConversationTurnContext;
  structuredAnswer?: StructuredQuestionAnswer;
  conversationAction?: ConversationActionType;
  sourceMessageId?: MessageId;
  questionId?: string;
  selectedOptionIds?: string[];
  textInput?: string;
  automaticHandoff?: boolean;
  handoffLabel?: string;
  recoveryOfMessageId?: MessageId;
  recoveryLabel?: string;
}

export type ProjectStreamChunk = StreamChunk & {
  projectId: ProjectId;
  conversationId: ConversationId;
  requestTurnId?: string;
  responseTurnId?: string;
  userMessageId?: MessageId;
};

/* ── ZW-004 Clarification ── */

export interface ClarificationOption {
  id: string;
  label: string;
  value?: string;
  description?: string;
  recommended?: boolean;
}

export interface ClarificationAnswer {
  questionId: string;
  selectedOptionIds: string[];
  textInput?: string;
  usedRecommendation?: boolean;
}

export interface ClarificationBatchAnswer {
  type: "clarification_batch_answer";
  projectId: ProjectId;
  conversationId: ConversationId;
  sourceMessageId: MessageId;
  clientTurnId: string;
  answers: ClarificationAnswer[];
}

export interface SingleChoiceAnswer {
  type: "single_choice_answer";
  projectId: ProjectId;
  conversationId: ConversationId;
  questionId: string;
  optionId: string;
  optionValue: string;
  optionLabel: string;
  clientTurnId: string;
}

export interface MultipleChoiceAnswer {
  type: "multiple_choice_answer";
  projectId: ProjectId;
  conversationId: ConversationId;
  questionId: string;
  optionIds: string[];
  optionValues: string[];
  optionLabels: string[];
  clientTurnId: string;
}

export interface TextQuestionAnswer {
  type: "text_question_answer";
  projectId: ProjectId;
  conversationId: ConversationId;
  questionId: string;
  text: string;
  clientTurnId: string;
}

export type StructuredQuestionAnswer =
  | SingleChoiceAnswer
  | MultipleChoiceAnswer
  | TextQuestionAnswer
  | ClarificationBatchAnswer;

export interface ClarificationQuestionRecord {
  id: string;
  projectId: ProjectId;
  conversationId: ConversationId;
  sourceMessageId: MessageId;
  stage: ProjectStage | string;
  text: string;
  mode: ClarificationQuestionMode;
  options?: ClarificationOption[];
  required: boolean;
  status: "pending" | "answered" | "superseded" | "cancelled";
  answeredAt?: string | null;
}

export interface ClarificationAnswerRecord {
  id: string;
  projectId: ProjectId;
  conversationId: ConversationId;
  questionId: string;
  answerType: ConversationAnswerType;
  values: string[];
  labels: string[];
  userMessageId: MessageId;
  clientTurnId: string;
  createdAt: string;
}

export interface ClarificationQuestion {
  id: string;
  type: ClarificationQuestionType;
  question: string;
  options: ClarificationOption[];
  answered?: boolean;
  answer?: ClarificationAnswer;
}

export interface ClarificationRound {
  round: number;
  questions: ClarificationQuestion[];
  completeness: number;
  message: string;
}

export interface ClarifyRequest {
  userMessage: string;
}

export interface ClarifyResponse {
  round: ClarificationRound;
}

export interface AnswerQuestionsRequest {
  answers: ClarificationAnswer[];
}

export interface AnswerQuestionsResponse {
  round: ClarificationRound;
}

/* ── ZW-004 Solution ── */

export interface SolutionSection {
  id: string;
  title: string;
  content: string;
}

export interface SolutionVersion {
  id: string;
  projectId: ProjectId;
  version: number;
  basedOnVersion?: number | null;
  status: SolutionStatus;
  changeSummary?: string[];
  sections: SolutionSection[];
  artifactId?: string | null;
  artifactVersionId?: string | null;
  createdAt: string;
  confirmedAt: string | null;
}

export interface GenerateSolutionRequest {
  revisionMessage?: string;
  componentIds?: string[];
}

export interface ReviseSolutionRequest {
  baseSolutionId?: string;
  userInstruction: string;
}

export interface ReviseSolutionResponse {
  solution: SolutionVersion;
  revision: SolutionRevision;
}

export interface RestoreSolutionResponse {
  solution: SolutionVersion;
}

export interface SolutionResponse {
  solution: SolutionVersion;
}

export interface ConfirmSolutionRequest {
  solutionId: string;
}

export interface ConfirmSolutionResponse {
  solution: SolutionVersion;
}

export interface SolutionListResponse {
  solutions: SolutionVersion[];
}

/* ── ZW-006 Proposal ── */

export interface ProposalSection {
  id: string;
  title: string;
  content: string;
}

export interface ProposalVersion {
  id: string;
  projectId: ProjectId;
  solutionId: string;
  solutionVersion: number;
  version: number;
  status: ProposalStatus;
  sections: ProposalSection[];
  createdAt: string;
  updatedAt: string;
  confirmedAt: string | null;
  staleReason: string | null;
}

export interface ProposalListResponse {
  proposals: ProposalVersion[];
}

export interface ProposalResponse {
  proposal: ProposalVersion;
}

export interface GenerateProposalRequest {
  solutionId: string;
}

export interface ReviseProposalRequest {
  proposalId: string;
  revisionMessage: string;
}

export interface ConfirmProposalRequest {
  proposalId: string;
}

export interface ConfirmProposalResponse {
  proposal: ProposalVersion;
}

export interface RejectProposalRequest {
  proposalId: string;
  reason?: string;
}

export interface RejectProposalResponse {
  proposal: ProposalVersion;
}

export interface ExportProposalRequest {
  format: ProposalExportFormat;
}

/* ── ZW-007 Orchestrator and Agent Registry ── */

export interface AgentDefinition {
  id: string;
  name: string;
  description: string;
  capabilities: AgentCapability[];
  enabled: boolean;
  builtIn: boolean;
}

export interface AgentRegistryResponse {
  agents: AgentDefinition[];
}

export interface TaskLogEntry {
  id: string;
  level: "INFO" | "WARNING" | "ERROR";
  message: string;
  createdAt: string;
}

export interface TaskNode {
  id: string;
  planId: string;
  projectId: ProjectId;
  agentId: string;
  title: string;
  description: string;
  status: TaskStatus;
  dependencies: string[];
  attempts: number;
  maxAttempts: number;
  requiresApproval: boolean;
  logs: TaskLogEntry[];
  createdAt: string;
  updatedAt: string;
  startedAt: string | null;
  completedAt: string | null;
  error: string | null;
}

export interface ExecutionPlan {
  id: string;
  projectId: ProjectId;
  proposalId: string;
  status: TaskStatus;
  nodes: TaskNode[];
  createdAt: string;
  updatedAt: string;
  startedAt: string | null;
  completedAt: string | null;
}

export interface ExecutionPlanResponse {
  plan: ExecutionPlan;
}

export interface CreateExecutionPlanRequest {
  proposalId: string;
}

export interface PlanActionRequest {
  nodeId?: string;
}

export interface ApprovalRequest {
  nodeId: string;
  approved: boolean;
  comment?: string;
}

/* ── ZW-008 Skill Registry and Model Router ── */

export interface AgentPackageValidationIssue {
  path: string;
  message: string;
  severity: "warning" | "error";
}

export interface AgentPackageFile {
  path: string;
  title: string;
  kind: "entry" | "reference";
  content: string;
  editable: boolean;
  overridden: boolean;
}

export interface AgentPackageSummary {
  expertType: ExpertType;
  skillName: string;
  displayName: string;
  description: string;
  icon: string;
  entryFile: string;
  skillIds: string[];
  supportedArtifactTypes: string[];
  capabilityBoundaries: string[];
  fileCount: number;
  overridden: boolean;
  revision: string;
  validationIssues: AgentPackageValidationIssue[];
}

export interface AgentPackageDetail extends AgentPackageSummary {
  files: AgentPackageFile[];
}

export interface AgentPackageListResponse {
  packages: AgentPackageSummary[];
}

export interface AgentPackageResponse {
  package: AgentPackageDetail;
}

export interface UpdateAgentPackageFileRequest {
  path: string;
  content: string;
  expectedRevision: string;
}

export interface ResetAgentPackageFileRequest {
  path: string;
  expectedRevision: string;
}

export interface JsonSchemaObject {
  type: string;
  properties?: Record<string, JsonSchemaObject>;
  required?: string[];
  items?: JsonSchemaObject;
  enum?: string[];
  description?: string;
}

export interface SkillDefinition {
  id: string;
  name: string;
  description: string;
  origin: SkillOrigin;
  enabled: boolean;
  ownerExpert: ExpertType;
  inputSchema: JsonSchemaObject;
  outputSchema: JsonSchemaObject;
  requiredTools?: string[];
  riskLevel?: SkillRiskLevel;
  confirmationPolicy?: SkillConfirmationPolicy;
  timeoutPolicy: { timeoutMs: number };
  retryPolicy: { maxRetries: number; backoffMs: number };
  artifactTypes?: string[];
  permissions: SkillPermission[];
  createdAt: string;
  updatedAt: string;
}

export interface SkillRegistryResponse {
  skills: SkillDefinition[];
}

export interface CreateSkillRequest {
  name: string;
  description: string;
  inputSchema?: JsonSchemaObject;
  outputSchema?: JsonSchemaObject;
  permissions?: SkillPermission[];
  ownerExpert?: ExpertType;
}

export interface UpdateSkillRequest {
  name?: string;
  description?: string;
  enabled?: boolean;
  permissions?: SkillPermission[];
}

export interface SkillResponse {
  skill: SkillDefinition;
}

export type SkillRunStatus =
  | "queued"
  | "awaiting_confirmation"
  | "running"
  | "completed"
  | "failed";

export interface SkillRunRequest {
  projectId: string;
  input: Record<string, unknown>;
  expertRunId?: string;
  confirmed?: boolean;
  requestingExpert?: ExpertType;
}

export interface SkillRunResult {
  id: string;
  projectId: string;
  skillId: string;
  ownerExpert: ExpertType;
  status: SkillRunStatus;
  output?: Record<string, unknown> | null;
  error?: string | null;
  confirmationRequired: boolean;
  retryCount: number;
}

export interface SkillRunResponse {
  run: SkillRunResult;
}

export interface ModelRouteRequest {
  agentId: string;
  taskKind: string;
  strategy: ModelRouteStrategy;
}

export interface ModelRouteResult {
  provider: LLMProviderId;
  model: LLMModelId;
  strategy: ModelRouteStrategy;
  retryCount: number;
  fallbackModel: LLMModelId | null;
  costTier: "LOW" | "MEDIUM" | "HIGH";
  qualityTier: "STANDARD" | "HIGH";
  reasoning: string;
}

export interface ModelRouteResponse {
  route: ModelRouteResult;
}

/* ── ZW-009 Artifact and Floating Window System ── */

export interface ArtifactDependency {
  artifactId: string;
  versionId: string | null;
  version: number | null;
  kind: string;
  label: string;
  status: string;
  relation?:
    | "requires"
    | "derived_from"
    | "dimension_source"
    | "interface_contract"
    | "content_source";
  required?: boolean;
}

export interface ArtifactPreviewSection {
  id: string;
  title: string;
  content: string;
}

export interface ArtifactPreview {
  kind: ArtifactPreviewKind;
  summary: string;
  sections?: ArtifactPreviewSection[];
  code?: string;
  language?: string;
  imageUrl?: string;
  modelUrl?: string;
  modelFileId?: string | null;
  placeholder?: string;
}

export interface ArtifactVersion {
  id: string;
  artifactId: string;
  projectId: ProjectId;
  version: number;
  status: ArtifactStatus;
  domainStatus?: DomainArtifactStatus | null;
  mimeType: string;
  preview: ArtifactPreview;
  dependencies: ArtifactDependency[];
  producerTaskId: string | null;
  sourceEntityType: string | null;
  sourceEntityId: string | null;
  checksum: string;
  staleReason: string | null;
  sharedContextRevision?: number | null;
  createdAt: string;
  confirmedAt: string | null;
}

export interface ArtifactDefinition {
  id: string;
  projectId: ProjectId;
  title: string;
  kind: ArtifactKind;
  status: ArtifactStatus;
  domainStatus?: DomainArtifactStatus | null;
  sourceAgentId: string;
  ownerExpertId?: string | null;
  ownerExpertType?: ExpertType | null;
  legacyOwnerExpert?: ExpertType | string | null;
  creatorLegacyExpert?: ExpertType | string | null;
  sourceConversationId?: string | null;
  sharedContextRevision?: number | null;
  currentVersionId: string | null;
  versions: ArtifactVersion[];
  createdAt: string;
  updatedAt: string;
}

export interface ArtifactListResponse {
  artifacts: ArtifactDefinition[];
}

export interface ArtifactResponse {
  artifact: ArtifactDefinition;
}

export interface ArtifactFileBounds {
  min_x: number;
  min_y: number;
  min_z: number;
  max_x: number;
  max_y: number;
  max_z: number;
}

export interface ArtifactFile {
  id: string;
  artifactId: string;
  artifactVersionId: string;
  projectId: ProjectId;
  role: CadOutputRole;
  fileName: string;
  mimeType: string;
  byteSize: number;
  sha256: string;
  triangleCount: number | null;
  bounds: ArtifactFileBounds | null;
  createdAt: string;
}

export interface ArtifactFileResponse {
  file: ArtifactFile;
}

export interface ArtifactFileListResponse {
  files: ArtifactFile[];
}

export interface FloatingWindowBounds {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface FloatingWindowSpec {
  id: string;
  kind: FloatingWindowKind;
  title: string;
  artifactId?: string;
  versionId?: string;
  initialBounds?: FloatingWindowBounds;
  singletonKey?: string;
  zIndex?: number;
  minimized?: boolean;
  maximized?: boolean;
}

/* ── ZW-010 Spec Agent ── */

export interface SpecValidationCheck {
  dimension: string;
  severity: "PASS" | "WARNING" | "FAIL";
  message: string;
  details: string;
}

export interface SpecValidation {
  ok: boolean;
  checks: SpecValidationCheck[];
}

export interface SpecFile {
  id: string;
  specRunId: string;
  projectId: ProjectId;
  kind: SpecFileKind;
  path: string;
  mimeType: string;
  content: string;
  artifactId: string | null;
  artifactVersionId: string | null;
  createdAt: string;
}

export interface SpecRun {
  id: string;
  projectId: ProjectId;
  proposalId: string;
  version: number;
  status: SpecRunStatus;
  files: SpecFile[];
  validation: SpecValidation;
  staleReason: string | null;
  createdAt: string;
  updatedAt: string;
  confirmedAt: string | null;
}

export interface SpecRunResponse {
  spec: SpecRun;
}

export interface GenerateSpecRequest {
  proposalId: string;
}

export interface ConfirmSpecRequest {
  specRunId: string;
}

export interface RejectSpecRequest {
  specRunId: string;
  reason?: string;
}

/* ── ZW-011 Code Agent ── */

export interface CodeFile {
  id: string;
  codeRunId: string;
  projectId: ProjectId;
  kind: CodeFileKind;
  path: string;
  language: string;
  content: string;
  createdAt: string;
}

export interface CodePatch {
  id: string;
  codeRunId: string;
  projectId: ProjectId;
  baseSnapshotId: string | null;
  summary: string;
  diff: string;
  createdAt: string;
}

export interface CodeTestResult {
  ok: boolean;
  command: string;
  output: string;
  createdAt: string;
  checks: CodeValidationCheck[];
}

export interface CodeValidationCheck {
  kind: CodeValidationKind;
  status: CodeValidationStatus;
  command: string;
  exitCode: number | null;
  output: string;
}

export interface CodeRun {
  id: string;
  projectId: ProjectId;
  specRunId: string | null;
  version: number;
  status: CodeRunStatus;
  runtime: import("./enums.js").CodeRuntime;
  entrypoint: string;
  workspaceRoot: string;
  maxRetries: number;
  retries: number;
  files: CodeFile[];
  patch: CodePatch;
  testResult: CodeTestResult;
  artifactId: string | null;
  artifactVersionId: string | null;
  hardwareSolutionVersion: number | null;
  bomVersion: number | null;
  ioMapVersion: number | null;
  generatedByExpertId: string | null;
  staleReason: string | null;
  createdAt: string;
  updatedAt: string;
  acceptedAt: string | null;
  revisionSource: CodeRevisionSource;
  requiresValidation: boolean;
}

export interface CodeRunResponse {
  codeRun: CodeRun;
}

export interface GenerateCodeRequest {
  specRunId: string;
  runtime?: import("./enums.js").CodeRuntime;
}

export interface AcceptCodeRequest {
  codeRunId: string;
}

export interface RejectCodeRequest {
  codeRunId: string;
  reason?: string;
}

export interface RollbackCodeRequest {
  codeRunId: string;
}

export interface ValidateCodeRequest {
  codeRunId: string;
}

export interface ImportCodeMessageRequest {
  messageId: string;
}

export interface EditableCodeFile {
  path: string;
  content: string;
}

export interface ReviseCodeRequest {
  baseCodeRunId: string;
  files: EditableCodeFile[];
  summary: string;
}

/* ── ZW-013 CAD Agent ── */

export interface CadParameter {
  name: string;
  label: string;
  unit: "mm" | "count";
  value: number;
  min: number;
  max: number;
}

export interface CadValidationCheck {
  dimension: string;
  severity: "PASS" | "WARNING" | "FAIL";
  message: string;
  details: string;
}

export interface CadValidation {
  ok: boolean;
  checks: CadValidationCheck[];
}

export interface CadComponentDraft {
  instanceId: string;
  hardwareId?: string;
  profileId?: string;
  mountSurface?: CadMountSurface;
  rotationDeg?: number;
  offsetMm?: CadVector3;
}

/** Sidecar 依据已确认硬件映射固化后的组件；这些字段不能由云端模型提供。 */
export interface CadResolvedComponent extends CadComponentDraft {
  hardwareId: string;
  profileId: string;
  resolvedProfileId: string;
  resolvedProfileRevision: string;
  resolvedProfileSha256: string;
}

export interface CadVector3 {
  x: number;
  y: number;
  z: number;
}

export interface CadMechanicalSize3 {
  length_x: number;
  width_y: number;
  height_z: number;
}

export interface CadMechanicalCoordinateSystem {
  origin: "envelope_center" | "pcb_center";
  x_axis: "length";
  y_axis: "width";
  positive_z: "component_side" | "height";
}

export interface CadMechanicalHole {
  hole_id: string;
  center: { x: number; y: number };
  diameter: number;
  fastener: string;
}

export interface CadMounting {
  mode:
    | "envelope_only"
    | "external_independent_module"
    | "base_floor"
    | "lid_inner"
    | "lid_outer"
    | "front_inner"
    | "back_inner"
    | "left_inner"
    | "right_inner"
    | "inner_surface";
  preferred_surface: CadMountSurface;
  strategy: "none" | "hole_fastened" | "edge_retainer";
  clearance: number;
  mating_hardware_face?: string | null;
  allowed_enclosure_surfaces: CadMountSurface[];
  holes: CadMechanicalHole[];
}

export interface CadMechanicalOpening {
  opening_id: string;
  kind: "circle" | "rectangle";
  center: { x: number; y: number };
  center_z?: number;
  diameter?: number | null;
  size_u?: number | null;
  size_v?: number | null;
  corner_radius?: number;
  preferred_face: "top" | "bottom" | "left" | "right" | "front" | "back";
  clearance: number;
}

export interface CadMechanicalKeepout {
  keepout_id: string;
  center: CadVector3;
  size: CadMechanicalSize3;
}

export interface CadDeclarativePrimitive {
  primitive_id: string;
  operation: "add" | "cut";
  kind: "box" | "rounded_box" | "cylinder";
  center: CadVector3;
  size?: CadMechanicalSize3 | null;
  diameter?: number | null;
  height?: number | null;
  corner_radius: number;
  rotation_z_deg: 0 | 90 | 180 | 270;
  role: "body" | "pcb" | "connector" | "sensor" | "feature";
}

export interface CadDeclarativeGeometry {
  source_sha256?: string | null;
  primitives: CadDeclarativePrimitive[];
}

export interface CadMechanicalProfileSnapshot {
  schema_version: "1.0";
  profile_id: string;
  revision: string;
  display_name: string;
  category: string;
  roles: string[];
  dimensions: CadMechanicalSize3;
  coordinate_system: CadMechanicalCoordinateSystem;
  mounting: CadMounting;
  model_kind:
    | "envelope"
    | "unihiker_k10"
    | "unihiker_ultrasonic_distance_sensor";
  source: "declared" | "trusted";
  evidence_level: "TRUSTED" | "CONFIRMED";
  representation: "parametric_envelope" | "envelope_only";
  keepouts: CadMechanicalKeepout[];
  openings: CadMechanicalOpening[];
  preview_geometry?: CadDeclarativeGeometry | null;
  content_sha256: string;
}

export interface MechanicalProfileSummary {
  profileId: string;
  revision: string;
  displayName: string;
  category: string;
  dimensions: CadMechanicalSize3;
  mountingMode: string;
  mountingStrategy: "none" | "hole_fastened" | "edge_retainer";
  preferredSurface: CadMountSurface;
  allowedSurfaces: CadMountSurface[];
  clearance: number;
  evidenceLevel: "TRUSTED" | "CONFIRMED";
  representation: "parametric_envelope" | "envelope_only";
  coordinateSystem: CadMechanicalCoordinateSystem;
  modelKind: CadMechanicalProfileSnapshot["model_kind"];
  previewGeometry: CadDeclarativeGeometry | null;
  mountingHoles: CadMechanicalHole[];
  openings: CadMechanicalOpening[];
  keepouts: CadMechanicalKeepout[];
  contentSha256: string;
  confirmedHardwareIds: string[];
  lockedHardwareIds: string[];
}

export interface MechanicalProfileListResponse {
  profiles: MechanicalProfileSummary[];
}

export interface GenerateMechanicalProfilePreviewRequest {
  revision: string;
}

export interface MechanicalProfilePreviewGenerationResponse {
  profile: MechanicalProfileSummary;
  generationSource: "DESCRIPTION_CACHE" | "DESCRIPTION_GENERATED" | "ENVELOPE_FALLBACK";
}

export interface ConfirmMechanicalProfileLinkRequest {
  profileId: string;
  revision: string;
}

export interface MechanicalProfileLinkResponse {
  hardwareId: string;
  profileId: string;
  revision: string;
  confirmed: boolean;
}

export interface RemoveMechanicalProfileLinkResponse {
  hardwareId: string;
  removed: boolean;
}

export interface CadOutputFile {
  relativePath: string;
  fileName: string;
  role: CadOutputRole;
  mimeType: string;
  byteSize: number;
  sha256: string;
  triangleCount: number | null;
  bounds: ArtifactFileBounds | null;
}

export interface CadWorkerManifest {
  schemaVersion: "1.0";
  engineId: string;
  engineVersion: string;
  designId: string;
  specSha256: string;
  files: CadOutputFile[];
}

export interface CadWorkerResult {
  manifest: CadWorkerManifest;
  validation: Record<string, unknown>;
  geometrySummary: Record<string, unknown>;
}

export interface CadJobFile {
  id: string;
  role: CadOutputRole;
  fileName: string;
  mimeType: string;
  byteSize: number;
  sha256: string;
  triangleCount: number | null;
  bounds: ArtifactFileBounds | null;
}

export interface CadJobManifest {
  schemaVersion: "1.0";
  engineId: string;
  engineVersion: string;
  designId: string;
  specSha256: string;
}

export interface CadJobResult {
  manifest: CadJobManifest;
  files: CadJobFile[];
  validation: Record<string, unknown>;
  geometrySummary: Record<string, unknown>;
}

/** 结构工程师可交给本地 CAD Tool Runner 的声明式草稿。 */
export interface CadDraft {
  specRunId?: string | null;
  /** 本地服务固化的 confirmed CAD intake 轮次指纹，云端模型不得提供。 */
  intakeSnapshotSha256?: string | null;
  templateKind: CadTemplateKind;
  templateRevision?: string;
  parameters: Record<string, number>;
  components: CadComponentDraft[];
  geometry?: CadDeclarativeGeometry | null;
  constraints: Record<string, number | string | boolean>;
  summary: string;
  requestedOutputs?: CadOutputRole[];
}

/** 固化机械档案和模板 revision 后写入持久 Job 的构建规范。 */
export interface CadBuildSpec extends Omit<CadDraft, "components" | "templateRevision"> {
  jobId: string;
  projectId: ProjectId;
  templateRevision: string;
  components: CadResolvedComponent[];
  profileSnapshots: CadMechanicalProfileSnapshot[];
  sizingEvidence?: CadSizingEvidence | null;
}

export interface CadSizingEvidence {
  mode: "AUTO" | "MIXED" | "EXPLICIT";
  requiredParameters: {
    width: number;
    height: number;
    depth: number;
  };
  autoResolvedParameters: Array<"width" | "height" | "depth">;
}

export interface CadJobError {
  code: string;
  message: string;
  retryable?: boolean;
}

export interface CadJob {
  id: string;
  projectId: ProjectId;
  cadRunId: string;
  clientRequestId: string | null;
  status: CadJobStatus;
  phase: CadJobPhase;
  progress: number;
  sourceMessageId: string | null;
  projectExpertId: string | null;
  specRunId: string | null;
  requestHash: string;
  request: CadBuildSpec;
  result: CadJobResult | null;
  error: CadJobError | null;
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
}

export interface CadJobResponse {
  cadJob: CadJob;
}

export interface CreateCadJobRequest {
  cadRunId: string;
  clientRequestId?: string | null;
}

export interface RetryCadJobRequest {
  clientRequestId?: string | null;
}

export interface CadFile {
  id: string;
  cadRunId: string;
  projectId: ProjectId;
  kind: CadFileKind | null;
  role?: CadOutputRole;
  path: string;
  fileName?: string;
  artifactFileId?: string | null;
  storageKey?: string | null;
  mimeType: string;
  content: string | null;
  byteSize?: number;
  sha256?: string | null;
  bounds?: ArtifactFileBounds | null;
  triangleCount?: number | null;
  artifactId: string | null;
  artifactVersionId: string | null;
  createdAt: string;
}

export interface CadRun {
  id: string;
  projectId: ProjectId;
  specRunId: string | null;
  templateKind: CadTemplateKind;
  version: number;
  status: CadRunStatus;
  commandLabel: string;
  parameters: CadParameter[];
  validation: CadValidation;
  files: CadFile[];
  artifactId: string | null;
  artifactVersionId: string | null;
  sourceMessageId: string | null;
  generatedByExpertId: string | null;
  engineId: string;
  engineVersion: string | null;
  designState: Record<string, unknown> | null;
  latestJob: CadJob | null;
  staleReason: string | null;
  createdAt: string;
  updatedAt: string;
  confirmedAt: string | null;
}

export interface CadRunResponse {
  cadRun: CadRun;
}

export interface GenerateCadRequest {
  specRunId: string;
  templateKind?: CadTemplateKind;
  parameters?: Record<string, number>;
}

export interface ConfirmCadRequest {
  cadRunId: string;
}

export interface RejectCadRequest {
  cadRunId: string;
  reason?: string;
}

/* ── ZW-014 Lesson Agent ── */

export interface LessonFile {
  id: string;
  lessonRunId: string;
  projectId: ProjectId;
  kind: LessonDocumentKind;
  title: string;
  path: string;
  mimeType: string;
  content: string;
  artifactId: string | null;
  artifactVersionId: string | null;
  createdAt: string;
}

export interface LessonRun {
  id: string;
  projectId: ProjectId;
  specRunId: string;
  proposalId: string;
  version: number;
  status: LessonRunStatus;
  gradeBand: string;
  lessonHours: number;
  files: LessonFile[];
  staleReason: string | null;
  createdAt: string;
  updatedAt: string;
  confirmedAt: string | null;
}

export interface LessonRunResponse {
  lessonRun: LessonRun;
}

export interface GenerateLessonRequest {
  specRunId: string;
  gradeBand?: string;
  lessonHours?: number;
}

export interface ConfirmLessonRequest {
  lessonRunId: string;
}

export interface RejectLessonRequest {
  lessonRunId: string;
  reason?: string;
}

/* ── ZW-015 Sharing and Project Package ── */

export interface ProjectPackageArtifactSelection {
  includeDocuments: boolean;
  includeCode: boolean;
  includeCad: boolean;
  includeLessons: boolean;
  includeDeviceLogs: boolean;
}

export interface ProjectPackagePrivacyCheck {
  dimension: string;
  severity: "PASS" | "WARNING" | "FAIL";
  message: string;
  path: string | null;
}

export interface ProjectPackagePrivacyReport {
  ok: boolean;
  checks: ProjectPackagePrivacyCheck[];
}

export interface ProjectPackageManifestFile {
  artifactFileId: string;
  role: string;
  fileName: string;
  path: string;
  mimeType: string;
  byteSize: number;
  sha256: string;
  triangleCount: number | null;
  bounds: ArtifactFileBounds | null;
}

export interface ProjectPackageManifestArtifact {
  artifactId: string;
  versionId: string;
  title: string;
  kind: ArtifactKind;
  sourceAgentId: string;
  sourceEntityType: string | null;
  sourceEntityId: string | null;
  version: number;
  status: ArtifactStatus;
  path: string;
  checksum: string;
  files: ProjectPackageManifestFile[];
}

export interface ProjectPackageManifest {
  schemaVersion: number;
  packageId: string;
  packageVersion: number;
  status: ProjectPackageStatus;
  projectId: ProjectId;
  projectName: string;
  projectStage: ProjectStage;
  exportedAt: string;
  itemKinds: ProjectPackageItemKind[];
  artifactSelection: ProjectPackageArtifactSelection;
  artifacts: ProjectPackageManifestArtifact[];
  privacyReport: ProjectPackagePrivacyReport;
}

export interface ProjectPackageRecord {
  id: string;
  projectId: ProjectId;
  status: ProjectPackageStatus;
  title: string;
  fileName: string;
  manifest: ProjectPackageManifest;
  privacyReport: ProjectPackagePrivacyReport;
  artifactId: string | null;
  artifactVersionId: string | null;
  zipBase64: string | null;
  createdAt: string;
  importedAt: string | null;
}

export interface ExportProjectPackageRequest {
  title?: string;
  artifactSelection?: Partial<ProjectPackageArtifactSelection>;
}

export interface ExportProjectPackageResponse {
  package: ProjectPackageRecord;
}

export interface ImportProjectPackageRequest {
  zipBase64: string;
  conflictStrategy?: ProjectPackageConflictStrategy;
}

export interface ImportProjectPackageResponse {
  package: ProjectPackageRecord;
  workspace: ProjectWorkspace;
}

/* ── ZW-016 MVP Readiness ── */

export interface MvpReadinessItem {
  id: MvpReadinessItemId;
  label: string;
  status: MvpReadinessStatus;
  required: boolean;
  message: string;
  evidence: string[];
}

export interface MvpReadinessReport {
  projectId: ProjectId;
  overallStatus: MvpReadinessStatus;
  readyCount: number;
  totalCount: number;
  generatedAt: string;
  items: MvpReadinessItem[];
  externalValidationRequired: string[];
  manualAcceptance: string[];
}

export interface MvpReadinessResponse {
  readiness: MvpReadinessReport;
}

/* ── ZW-012 Device and MicroPython Deployment ── */

export interface DevicePort {
  id: string;
  label: string;
  transport: "mock-usb-serial" | "system-serial" | "usb-serial" | string;
  portName: string;
  portType: SerialPortType;
  description?: string | null;
  manufacturer?: string | null;
  product?: string | null;
  vid?: number | null;
  pid?: number | null;
  likelyBoard?: string | null;
  status: SerialPortStatus;
  chip: string;
  serialNumber: string | null;
  available: boolean;
}

export interface DeviceLogEntry {
  id: string;
  level: "INFO" | "WARNING" | "ERROR";
  message: string;
  createdAt: string;
}

export interface DeviceSession {
  id: string;
  projectId: ProjectId;
  portId: string;
  /** Canonical for new sessions; legacy projects may expose an unsupported historical value read-only. */
  board: string;
  status: DeviceSessionStatus;
  connectedAt: string | null;
  lastSeenAt: string;
  logs: DeviceLogEntry[];
}

export interface DeviceOperation {
  id: string;
  projectId: ProjectId;
  sessionId: string;
  kind: DeviceOperationKind;
  status: DeviceOperationStatus;
  dryRun: boolean;
  commandLabel: string;
  log: string;
  artifactId: string | null;
  artifactVersionId: string | null;
  createdAt: string;
  completedAt: string | null;
  phase?: DeviceOperationPhase;
  progress?: number;
  errorCode?: string | null;
  steps?: DeviceOperationStep[];
  backup?: DeviceBackupSummary | null;
  verification?: DeviceVerification | null;
  cancelable?: boolean;
  metadata?: Record<string, unknown>;
}

export interface DeviceOperationStep {
  phase: DeviceOperationPhase;
  status: DeviceOperationStatus;
  exitCode: number | null;
  summary: string;
  startedAt: string | null;
  completedAt: string | null;
}

export interface DeviceBackupSummary {
  backupId: string;
  fileCount: number;
  paths: string[];
  createdAt: string;
  restorable: boolean;
}

export interface DeviceVerification {
  fileHashes: Record<string, string>;
  reconnectExitCode: number | null;
  runtimeExitCode: number | null;
  ok: boolean;
  summary: string;
  deploymentOk: boolean | null;
  restartOk: boolean | null;
  runtimeInterruptedOk?: boolean | null;
  runtimeStartedOk?: boolean | null;
  managementChannelOk: boolean | null;
  warnings: string[];
}

export type FirmwareApplicationRuntime = "micropython" | "esp-claw" | "esp-idf";
export type DeviceLabTarget = "SIMULATOR" | "DEVICE";
export type DeviceLabEngine = "FUNCTIONAL_MODEL" | "QEMU_ESP32S3";
export type DeviceLabChannelKind =
  | "sensor-input"
  | "telemetry"
  | "actuator"
  | "parameter";
export type DeviceLabValueType = "number" | "boolean" | "string";
export type DeviceLabControlKind = "slider" | "number" | "switch" | "waveform" | "media";

export interface DeviceBoardPinConflict {
  resources: string[];
  message: string;
}

export interface DeviceBoardCapability {
  id: import("./enums.js").SupportedDeviceBoardId;
  displayName: string;
  manufacturer: string;
  chip: "esp32s3";
  flashSizeBytes: number;
  psramSizeBytes: number;
  legacyAliases: string[];
  peripherals: string[];
  pinConflicts: DeviceBoardPinConflict[];
}

export interface DeviceLabChannel {
  id: string;
  label: string;
  kind: DeviceLabChannelKind;
  valueType: DeviceLabValueType;
  control: DeviceLabControlKind;
  unit?: string | null;
  minimum?: number | null;
  maximum?: number | null;
  step?: number | null;
  defaultValue: number | boolean | string;
  writable: boolean;
  requiresArm: boolean;
  safeValue?: number | boolean | string | null;
  componentId?: string | null;
  source: "board-profile" | "project-scene";
}

export interface DeviceLabProfileV1 {
  schemaVersion: "zhangwen.device-lab-profile/v1";
  boardId: import("./enums.js").SupportedDeviceBoardId;
  revision: string;
  channels: DeviceLabChannel[];
}

export interface DeviceLabSceneSource {
  proposalId: string;
  proposalVersion: number;
  proposalConfirmedAt: string;
  hardwareFactId: string | null;
  hardwareFactUpdatedAt: string | null;
  specRunId: string | null;
  specVersion: number | null;
  specConfirmedAt: string | null;
}

export interface DeviceLabSceneComponent {
  id: string;
  name: string;
  category: "MCU" | "SENSOR" | "ACTUATOR" | "DISPLAY" | "POWER" | "STRUCTURE" | "ONBOARD" | "SERVICE";
  role: "controller" | "onboard" | "external" | "service";
  source: "project-hardware" | "approved-spec" | "approved-proposal" | "board-profile";
  simulation: "FUNCTIONAL" | "VISUAL_ONLY";
  builtIn: boolean;
  protocol: string | null;
}

export interface DeviceLabSceneConnection {
  id: string;
  fromComponentId: string;
  toComponentId: string;
  protocol: string;
  signal: string;
  pin: string | null;
  confidence: "CONFIRMED" | "PROPOSAL_DERIVED";
  note: string;
}

export interface DigitalPrototypeBindingV1 {
  schemaVersion: "zhangwen.digital-prototype-binding/v1";
  solutionRevisionId: string | null;
  codeRunId: string | null;
  parameterSetId: string | null;
  componentPackVersion: string;
  simulationCapability: "FUNCTIONAL" | "FIRMWARE" | "UART_BOOT_CHECK";
  layoutVersion: "auto-v1";
}

export interface DeviceLabProjectTestCase {
  id: string;
  title: string;
  inputChannelIds: string[];
  expectedBehavior: string;
  source: "acceptance-scenario" | "scene-default";
}

export interface DeviceLabSceneV1 {
  schemaVersion: "zhangwen.device-lab-scene/v1";
  projectId: ProjectId;
  revision: string;
  boardId: import("./enums.js").SupportedDeviceBoardId;
  status: "READY" | "NEEDS_IO_CONFIRMATION";
  source: DeviceLabSceneSource;
  binding?: DigitalPrototypeBindingV1 | null;
  components: DeviceLabSceneComponent[];
  connections: DeviceLabSceneConnection[];
  testCases?: DeviceLabProjectTestCase[];
  warnings: string[];
  generatedAt: string;
}

export interface DeviceLabSceneResponse {
  scene: DeviceLabSceneV1;
  profile: DeviceLabProfileV1;
}

export interface DeviceBoardListResponse {
  boards: DeviceBoardCapability[];
  profiles: DeviceLabProfileV1[];
  qemu: { available: boolean; version: string | null; reason: string | null };
}

export interface FirmwareImageSegment {
  path: string;
  address: number;
  sizeBytes: number;
  sha256: string;
  kind: "bootloader" | "partition-table" | "application";
}

export interface FirmwareSimulationImage {
  path: string;
  sizeBytes: number;
  sha256: string;
}

export interface FirmwareApplicationManifestV1 {
  schemaVersion: "zhangwen.firmware-application/v1";
  applicationId: string;
  displayName: string;
  version: string;
  runtime: FirmwareApplicationRuntime;
  boardId: import("./enums.js").SupportedDeviceBoardId;
  chip: "esp32s3";
  flashSizeBytes: number;
  psramSizeBytes: number;
  sourceUrl?: string | null;
  sourceRevision?: string | null;
  debugProtocolVersion?: "zwdbg/1" | null;
  deviceImages: FirmwareImageSegment[];
  elfImage?: FirmwareSimulationImage | null;
  simulationImage?: FirmwareSimulationImage | null;
}

export interface FirmwareApplicationRecord {
  id: string;
  projectId: ProjectId;
  manifest: FirmwareApplicationManifestV1;
  archiveSha256: string;
  simulationCapability: "FULL" | "UART_ONLY" | "NONE";
  importedAt: string;
}

export interface FirmwareApplicationListResponse {
  applications: FirmwareApplicationRecord[];
  curated: Array<{
    applicationId: string;
    displayName: string;
    boardId: import("./enums.js").SupportedDeviceBoardId;
    sourceUrl: string;
    bundled: boolean;
  }>;
}

export interface ImportFirmwareApplicationRequest {
  zipBase64: string;
}

export interface FirmwareApplicationResponse {
  application: FirmwareApplicationRecord;
}

export interface FirmwareApplicationInstallPrepareRequest {
  sessionId: string;
  applicationId: string;
  boardId: import("./enums.js").SupportedDeviceBoardId;
  confirmBoardIdentity: boolean;
}

export interface FirmwareApplicationInstallPlan {
  applicationId: string;
  sessionId: string;
  boardId: import("./enums.js").SupportedDeviceBoardId;
  segmentCount: number;
  totalBytes: number;
  confirmationToken: string;
  expiresAt: string;
  summary: string;
}

export interface FirmwareApplicationInstallPlanResponse {
  plan: FirmwareApplicationInstallPlan;
}

export interface FirmwareApplicationInstallRequest {
  sessionId: string;
  applicationId: string;
  confirmationToken: string;
  operationId?: string;
  confirmInstall: boolean;
  confirmationPhrase?: string;
}

export interface DeviceLabRun {
  id: string;
  projectId: ProjectId;
  boardId: import("./enums.js").SupportedDeviceBoardId;
  target: DeviceLabTarget;
  engine: DeviceLabEngine;
  status: "STARTING" | "RUNNING" | "STOPPED" | "ERROR";
  applicationId: string | null;
  parameterSetId: string | null;
  actuatorArmed: boolean;
  channelValues: Record<string, number | boolean | string>;
  revision: number;
  startedAt: string;
  updatedAt: string;
  errorMessage: string | null;
  scene: DeviceLabSceneV1 | null;
}

export interface CreateDeviceLabRunRequest {
  target: DeviceLabTarget;
  applicationId?: string | null;
  parameterSetId?: string | null;
  expectedSceneRevision?: string | null;
  expectedSolutionRevisionId?: string | null;
  codeRunId?: string | null;
  idempotencyKey: string;
}

export interface DeviceLabRunResponse {
  run: DeviceLabRun;
  profile: DeviceLabProfileV1;
}

export interface UpdateDeviceLabChannelRequest {
  value: number | boolean | string;
  expectedRevision: number;
  actuatorArmed?: boolean;
  commandId: string;
}

export interface ApplyParameterSetRequest {
  parameterSetId: string;
  expectedRevision: number;
}

export interface SyncParameterSetRequest {
  sessionId: string;
  operationId?: string;
  confirmSync: boolean;
}

export interface DeviceLabEvent {
  revision: number;
  type: "state" | "telemetry" | "log" | "ack" | "error";
  channelId?: string | null;
  value?: number | boolean | string | null;
  message: string;
  createdAt: string;
}

export interface ParameterSetRevision {
  id: string;
  projectId: ProjectId;
  boardId: import("./enums.js").SupportedDeviceBoardId;
  profileRevision: string;
  revision: number;
  label: string;
  values: Record<string, number | boolean | string>;
  createdAt: string;
}

export interface SaveParameterSetRequest {
  boardId: import("./enums.js").SupportedDeviceBoardId;
  profileRevision: string;
  label: string;
  values: Record<string, number | boolean | string>;
  idempotencyKey: string;
}

export interface ParameterSetListResponse {
  parameterSets: ParameterSetRevision[];
}

export interface ParameterSetResponse {
  parameterSet: ParameterSetRevision;
}

export interface ListDevicePortsResponse {
  ports: DevicePort[];
  scannedAt: string;
  count: number;
}

export interface ConnectDeviceRequest {
  portId: string;
  boardId: import("./enums.js").SupportedDeviceBoardId;
  confirmBoardIdentity: boolean;
  operationId?: string;
}

export interface DisconnectDeviceRequest {
  sessionId: string;
  operationId?: string;
}

export interface TakeoverDeviceRequest {
  sessionId: string;
  confirmHardwareReset?: boolean;
  confirmationPhrase?: string;
}

export interface DeviceSessionResponse {
  session: DeviceSession;
}

export interface EspClawEndpoint {
  id: string;
  projectId: ProjectId;
  /** Trusted-LAN Web Console origin, for example http://device.local. */
  webEndpoint: string;
  /** Trusted-LAN MCP endpoint URL, including its port and optional path. */
  mcpEndpoint: string;
  boardId: import("./enums.js").SupportedDeviceBoardId;
  status: "READY" | "ERROR";
  storageBasePath: "/fatfs";
  capabilities: string[];
  pairedAt: string;
  lastSeenAt: string;
}

export interface PairEspClawEndpointRequest {
  pairingMode: "TRUSTED_LAN_MANUAL";
  webEndpoint: string;
  mcpEndpoint: string;
  boardId: import("./enums.js").SupportedDeviceBoardId;
  confirmTrustedLan: boolean;
  confirmAdminMode: boolean;
  confirmBoardIdentity: boolean;
}

export interface EspClawEndpointResponse {
  endpoint: EspClawEndpoint;
}

export interface EspClawEndpointListResponse {
  endpoints: EspClawEndpoint[];
}

export interface DeviceTerminalRequest {
  sessionId: string;
}

export interface DeviceTerminalSnapshot {
  sessionId: string;
  status: DeviceTerminalStatus;
  output: string;
  revision: number;
  startedAt: string | null;
  updatedAt: string | null;
  errorMessage: string | null;
}

export interface DeviceTerminalResponse {
  terminal: DeviceTerminalSnapshot;
}

export interface DeviceTerminalUnlockRequest {
  sessionId: string;
  confirmProfessionalMode: boolean;
  confirmationPhrase: string;
}

export interface DeviceTerminalUnlock {
  sessionId: string;
  unlockToken: string;
  expiresAt: string;
  maxBytesPerWrite: number;
}

export interface DeviceTerminalUnlockResponse {
  unlock: DeviceTerminalUnlock;
}

export interface DeviceTerminalWriteRequest {
  sessionId: string;
  unlockToken: string;
  input: string;
}

export interface WateringSmokeRequest {
  sessionId: string;
  operationId?: string;
}

export interface WateringSmokeEvidence {
  sessionId: string;
  operationId: string;
  checkedAt: string;
  sampleCount: number;
  continuousMoistureOk: boolean;
  wetPumpOffOk: boolean;
  dryLimitedRunOk: boolean;
  noUnhandledException: boolean;
  ok: boolean;
  summary: string;
  observations: string[];
}

export interface WateringSmokeResponse {
  evidence: WateringSmokeEvidence;
  operation: DeviceOperation;
}

export interface UploadCodeRequest {
  codeRunId: string;
  sessionId: string;
  dryRun: boolean;
  operationId?: string;
  confirmWrite?: boolean;
}

export interface UsbSerialCodeDeploymentRequest {
  channel: typeof import("./enums.js").DeviceDeploymentChannel.USB_SERIAL;
  codeRunId: string;
  sessionId: string;
  dryRun?: boolean;
  operationId?: string;
  confirmWrite?: boolean;
}

export interface EspClawCodeDeploymentRequest {
  channel: typeof import("./enums.js").DeviceDeploymentChannel.ESP_CLAW;
  codeRunId: string;
  endpointId: string;
  operationId?: string;
  confirmWrite: boolean;
}

export type DeployCodeRequest =
  | UsbSerialCodeDeploymentRequest
  | EspClawCodeDeploymentRequest;

export interface FirmwareFlashRequest {
  sessionId: string;
  dryRun: boolean;
  confirmFlash: boolean;
  candidateId?: string;
  confirmationToken?: string;
  operationId?: string;
  address?: number;
  confirmationPhrase?: string;
}

export interface FirmwareInspectRequest {
  fileName: string;
  contentBase64: string;
}

export interface FirmwareCandidate {
  id: string;
  fileName: string;
  sizeBytes: number;
  sha256: string;
  targetChip: string | null;
  imageFormat: string | null;
  defaultAddress: number | null;
  compatible: boolean;
  warnings: string[];
  expiresAt: string;
}

export interface FirmwareCandidateResponse {
  candidate: FirmwareCandidate;
}

export interface FirmwarePrepareRequest {
  sessionId: string;
  candidateId: string;
  address?: number;
}

export interface FirmwareFlashPlan {
  candidate: FirmwareCandidate;
  sessionId: string;
  address: number;
  confirmationToken: string;
  expiresAt: string;
  summary: string;
}

export interface FirmwareFlashPlanResponse {
  plan: FirmwareFlashPlan;
}

export interface DeviceOperationResponse {
  operation: DeviceOperation;
  session: DeviceSession;
}

export type DeviceOperationCancelResponse = DeviceOperationResponse;

/* ── ZW-005 Hardware ── */

export interface HardwareElectricalProps {
  /** Recommended or nominal operating point. */
  voltage: number;
  /** Accepted component supply range; omitted legacy values collapse to `voltage`. */
  voltageMin?: number | null;
  voltageMax?: number | null;
  /** Discrete peripheral power rails exposed by an MCU or power source. */
  supplyVoltages?: number[];
  logicLevel: number;
  peakCurrent: number;
  communicationProtocol: string;
  i2cAddress: string | null;
  supportedMCUs: string[];
  driverName: string | null;
  firmwareRequirement: string | null;
}

export interface HardwareMediaAsset {
  path: string;
  role: "cover" | "gallery";
  alt: string;
  contentType: "image/jpeg" | "image/png" | "image/webp";
  sha256: string;
  sourceUrl: string;
  attribution: string;
  license: string;
  /** Authenticated Sidecar path. Fetch as a Blob; do not use as an anonymous hotlink. */
  url: string;
}

export interface HardwareComponent {
  id: string;
  name: string;
  category: HardwareCategory;
  status: HardwareComponentStatus;
  electrical: HardwareElectricalProps;
  stock: number;
  price: number;
  ageRecommendation: number | null;
  safetyTags: string[];
  notes: string;
  createdAt: string;
  updatedAt: string;
  /** Present on Sidecar v26+ projections; optional for imported legacy responses. */
  skillName?: string;
  skillRevision?: string;
  verificationStatus?: string;
  media?: HardwareMediaAsset[];
}

export interface HardwareSkillDiagnostic {
  path: string;
  code: string;
  message: string;
  severity: "warning" | "error";
}

export interface HardwareSkillFile {
  path: string;
  title: string;
  kind: "entry" | "reference" | "model" | "example" | "test";
  content: string;
  editable: boolean;
}

export interface HardwareSkillSpecification {
  schema: "zhangwen.hardware-skill/v1";
  componentId: string;
  name: string;
  category: HardwareCategory;
  electrical: HardwareElectricalProps;
  stock: number;
  price: number;
  ageRecommendation: number | null;
  safetyTags: string[];
  notes: string;
  verificationStatus: string;
  sourceIds: string[];
}

export interface HardwareSkillRule {
  id: string;
  operator: HardwareRuleOperator;
  severity: ValidationSeverity;
  message: string;
  params: Record<string, unknown>;
}

export interface HardwareSkillSummary {
  skillName: string;
  componentId: string;
  displayName: string;
  description: string;
  category: HardwareCategory;
  status: HardwareSkillStatus;
  sourceKind: HardwareSkillSourceKind;
  revision: string;
  verificationStatus: string;
  updatedAt: string;
  diagnostics: HardwareSkillDiagnostic[];
  media: HardwareMediaAsset[];
}

export interface HardwareSkillDetail extends HardwareSkillSummary {
  files: HardwareSkillFile[];
  specification: HardwareSkillSpecification;
  rules: HardwareSkillRule[];
  /** Derived from references/mechanical.md; its revision is owned by the Skill. */
  mechanicalProfile?: Record<string, unknown> | null;
}

export interface HardwareSkillListResponse {
  skills: HardwareSkillSummary[];
}

export interface HardwareCatalogRefreshResponse {
  skills: HardwareSkillSummary[];
  refreshedAt: string;
}

export interface HardwareSkillResponse {
  skill: HardwareSkillDetail;
}

export interface UpdateHardwareSkillFileRequest {
  path: string;
  content: string;
  expectedRevision: string;
}

export interface HardwareSkillFileUpdate {
  path: string;
  content: string;
}

export interface UpdateHardwareSkillFilesRequest {
  updates: HardwareSkillFileUpdate[];
  expectedRevision: string;
}

export interface HardwareSkillDraftSource {
  name: string;
  mediaType: string;
  content: string;
}

export interface HardwareSkillDraft {
  id: string;
  status: "DRAFT";
  revision: string;
  sources: Array<{ name: string; mediaType: string }>;
  files: HardwareSkillFile[];
  specification: HardwareSkillSpecification | null;
  rules: HardwareSkillRule[];
  missingQuestions: string[];
  diagnostics: HardwareSkillDiagnostic[];
  canConfirm: boolean;
}

export interface HardwareSkillDraftResponse {
  draft: HardwareSkillDraft;
}

export interface CreateHardwareSkillDraftRequest {
  name?: string;
  description?: string;
  sources: HardwareSkillDraftSource[];
}

export interface ContinueHardwareSkillDraftRequest {
  message: string;
  expectedRevision: string;
}

export interface ConfirmHardwareSkillDraftRequest {
  expectedRevision: string;
}

export interface HardwareComponentPackageFile {
  path: string;
  title: string;
  kind: "entry" | "reference";
  content: string;
  overridden: boolean;
}

export interface HardwareComponentPackageDetail {
  componentId: string;
  componentName: string;
  revision: string;
  files: HardwareComponentPackageFile[];
}

export interface HardwareComponentPackageResponse {
  package: HardwareComponentPackageDetail;
}

export interface UpdateHardwareComponentPackageFileRequest {
  path: string;
  content: string;
  expectedRevision: string;
}

export interface BoardSkillSummary {
  id: string;
  name: string;
  version: string;
  profileId: string;
  target: string;
  runtime: "MicroPython";
  referenceCount: number;
  templateCount: number;
  exampleCount: number;
  syntaxValidated: boolean;
  hardwareValidated: boolean;
  revision: string;
}

export interface BoardProfileSummary {
  id: string;
  displayName: string;
  aliases: string[];
  platform: string;
  language: "micropython";
  overridden: boolean;
  revision: string;
  skillPackage: BoardSkillSummary | null;
}

export interface BoardProfile extends BoardProfileSummary {
  content: string;
}

export interface BoardProfileListResponse {
  profiles: BoardProfileSummary[];
}

export interface BoardProfileResponse {
  profile: BoardProfile;
}

export interface UpdateBoardProfileRequest {
  content: string;
  expectedRevision: string;
}

export interface ResetBoardProfileRequest {
  expectedRevision: string;
}

export interface CreateComponentRequest {
  name: string;
  category: HardwareCategory;
  electrical: HardwareElectricalProps;
  stock?: number;
  price?: number;
  ageRecommendation?: number | null;
  safetyTags?: string[];
  notes?: string;
}

export interface UpdateComponentRequest {
  name?: string;
  category?: HardwareCategory;
  electrical?: HardwareElectricalProps;
  stock?: number;
  price?: number;
  ageRecommendation?: number | null;
  safetyTags?: string[];
  notes?: string;
}

export interface ComponentListResponse {
  components: HardwareComponent[];
}

export interface ComponentResponse {
  component: HardwareComponent;
}

export interface ValidationCheck {
  dimension: string;
  severity: ValidationSeverity;
  message: string;
  details: string;
}

export interface ValidationResult {
  checks: ValidationCheck[];
  overall: ValidationSeverity;
  message: string;
}

export interface ValidateCombinationRequest {
  componentIds: string[];
}

export interface ValidateCombinationResponse {
  result: ValidationResult;
}
