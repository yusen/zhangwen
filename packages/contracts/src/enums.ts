/**
 * 掌问共享契约 — 状态枚举
 * 所有状态字符串必须从此文件获取，前后端不得各自复制。
 */

/** 项目阶段 */
export const ProjectStage = {
  IDEA: "IDEA",
  CLARIFYING: "CLARIFYING",
  SOLUTION_DRAFT: "SOLUTION_DRAFT",
  SOLUTION_CONFIRMED: "SOLUTION_CONFIRMED",
  PROPOSAL_DRAFT: "PROPOSAL_DRAFT",
  PROPOSAL_CONFIRMED: "PROPOSAL_CONFIRMED",
  EXECUTION_PLANNED: "EXECUTION_PLANNED",
  IMPLEMENTING: "IMPLEMENTING",
  VALIDATING: "VALIDATING",
  READY_TO_UPLOAD: "READY_TO_UPLOAD",
  DEVICE_VERIFIED: "DEVICE_VERIFIED",
  READY_TO_PUBLISH: "READY_TO_PUBLISH",
  PUBLISHED: "PUBLISHED",
} as const;
export type ProjectStage = (typeof ProjectStage)[keyof typeof ProjectStage];

/** 项目持久化 schema 版本 */
export const ProjectPersistenceVersion = {
  V1: 1,
  V2: 2,
  V3: 3,
  V4: 4,
  V5: 5,
  V6: 6,
  V7: 7,
  V8: 8,
  V9: 9,
  V10: 10,
  V11: 11,
  V12: 12,
  V13: 13,
  V14: 14,
  V15: 15,
  V16: 16,
  V17: 17,
  V18: 18,
  V19: 19,
  V20: 20,
  V21: 21,
  V22: 22,
  V23: 23,
  V24: 24,
  V25: 25,
  V26: 26,
  V27: 27,
  V28: 28,
  V29: 29,
  V30: 30,
  V31: 31,
} as const;
export type ProjectPersistenceVersion =
  (typeof ProjectPersistenceVersion)[keyof typeof ProjectPersistenceVersion];

/** 桌面认证门禁状态 */
export const AuthenticationStatus = {
  CHECKING: "checking",
  UNAUTHENTICATED: "unauthenticated",
  AUTHENTICATING: "authenticating",
  VERIFYING_EMAIL: "verifying_email",
  PROFILE_REQUIRED: "profile_required",
  LEGACY_CLAIM_REQUIRED: "legacy_claim_required",
  AUTHENTICATED: "authenticated",
  OFFLINE_TRUSTED: "offline_trusted",
  REAUTH_REQUIRED: "reauth_required",
} as const;
export type AuthenticationStatus =
  (typeof AuthenticationStatus)[keyof typeof AuthenticationStatus];

/** 云端账号人物画像。 */
export const UserPersona = {
  TEACHER: "TEACHER",
  STUDENT: "STUDENT",
  ENGINEER: "ENGINEER",
  MAKER: "MAKER",
  OTHER: "OTHER",
} as const;
export type UserPersona = (typeof UserPersona)[keyof typeof UserPersona];

/** 用户自报技术水平，只影响推荐上下文。 */
export const TechnicalLevel = {
  BEGINNER: "BEGINNER",
  INTERMEDIATE: "INTERMEDIATE",
  ADVANCED: "ADVANCED",
} as const;
export type TechnicalLevel = (typeof TechnicalLevel)[keyof typeof TechnicalLevel];

/** 用户默认预算倾向。 */
export const BudgetPreference = {
  ECONOMY: "ECONOMY",
  BALANCED: "BALANCED",
  PERFORMANCE: "PERFORMANCE",
} as const;
export type BudgetPreference =
  (typeof BudgetPreference)[keyof typeof BudgetPreference];

/** 统一项目进度对用户呈现的总状态。 */
export const ProjectProgressStatus = {
  READY: "READY",
  ACTION_REQUIRED: "ACTION_REQUIRED",
  BLOCKED: "BLOCKED",
  COMPLETE: "COMPLETE",
} as const;
export type ProjectProgressStatus =
  (typeof ProjectProgressStatus)[keyof typeof ProjectProgressStatus];

/** 进度投影与底层项目事实的一致性。 */
export const ProjectProgressConsistency = {
  CONSISTENT: "CONSISTENT",
  REPAIRED: "REPAIRED",
  NEEDS_ATTENTION: "NEEDS_ATTENTION",
} as const;
export type ProjectProgressConsistency =
  (typeof ProjectProgressConsistency)[keyof typeof ProjectProgressConsistency];

/** UX-003 三师类型；旧四专家和 v18 过渡值保留为历史数据兼容别名。 */
export const ExpertType = {
  PROBLEM_GUIDE: "problem_guide",
  SMART_ENGINEER: "smart_engineer",
  STRUCTURE_ENGINEER: "structure_engineer",
  /** @deprecated Use PROBLEM_GUIDE. */
  QUESTION_GUIDE: "question_guide",
  /** @deprecated Use SMART_ENGINEER. */
  INTELLIGENT_ENGINEER: "intelligent_engineer",
  /** @deprecated Use PROBLEM_GUIDE. */
  IDEATOR: "ideator",
  /** @deprecated Use SMART_ENGINEER. */
  OPEN_HARDWARE_DESIGNER: "open_hardware_designer",
  /** @deprecated Use STRUCTURE_ENGINEER. */
  STRUCTURE_DESIGNER: "structure_designer",
  /** @deprecated Use STRUCTURE_ENGINEER. */
  THREE_D_STRUCTURE_DESIGNER: "three_d_structure_designer",
  /** @deprecated Use PROBLEM_GUIDE. */
  EDUCATOR: "educator",
} as const;
export type ExpertType = (typeof ExpertType)[keyof typeof ExpertType];

/** 三师工作区领域状态。 */
export const ExpertWorkspaceStatus = {
  NOT_STARTED: "not_started",
  WAITING_DEPENDENCY: "waiting_dependency",
  IN_PROGRESS: "in_progress",
  AWAITING_USER: "awaiting_user",
  COMPLETED: "completed",
  OUTDATED: "outdated",
} as const;
export type ExpertWorkspaceStatus =
  (typeof ExpertWorkspaceStatus)[keyof typeof ExpertWorkspaceStatus];

/** 项目专家工作状态 */
export const ProjectExpertStatus = {
  IDLE: "idle",
  WAITING_USER: "waiting_user",
  WORKING: "working",
  BLOCKED: "blocked",
  COMPLETED: "completed",
} as const;
export type ProjectExpertStatus =
  (typeof ProjectExpertStatus)[keyof typeof ProjectExpertStatus];

/** 项目协调器事项严重级别 */
export const CoordinatorSeverity = {
  INFO: "info",
  WARNING: "warning",
  BLOCKING: "blocking",
} as const;
export type CoordinatorSeverity =
  (typeof CoordinatorSeverity)[keyof typeof CoordinatorSeverity];

/** Agent 任务状态 */
export const TaskStatus = {
  DISABLED: "DISABLED",
  QUEUED: "QUEUED",
  PLANNING: "PLANNING",
  RUNNING: "RUNNING",
  AWAITING_APPROVAL: "AWAITING_APPROVAL",
  PAUSED: "PAUSED",
  BLOCKED: "BLOCKED",
  COMPLETED: "COMPLETED",
  FAILED: "FAILED",
  CANCELED: "CANCELED",
} as const;
export type TaskStatus = (typeof TaskStatus)[keyof typeof TaskStatus];

/** 三师领域任务状态；保留 Agent TaskStatus 不变。 */
export const DomainTaskStatus = {
  QUEUED: "queued",
  READY: "ready",
  RUNNING: "running",
  BLOCKED: "blocked",
  AWAITING_USER: "awaiting_user",
  COMPLETED: "completed",
  FAILED: "failed",
  CANCELLED: "cancelled",
} as const;
export type DomainTaskStatus =
  (typeof DomainTaskStatus)[keyof typeof DomainTaskStatus];

/** Agent 能力声明 */
export const AgentCapability = {
  ORCHESTRATE: "ORCHESTRATE",
  SPEC: "SPEC",
  CODE: "CODE",
  CAD: "CAD",
  DEPLOY: "DEPLOY",
  PUBLISH: "PUBLISH",
  LESSON: "LESSON",
  REVIEW: "REVIEW",
} as const;
export type AgentCapability =
  (typeof AgentCapability)[keyof typeof AgentCapability];

/** Skill 来源 */
export const SkillOrigin = {
  BUILT_IN: "BUILT_IN",
  USER: "USER",
} as const;
export type SkillOrigin = (typeof SkillOrigin)[keyof typeof SkillOrigin];

/** Skill 权限声明 */
export const SkillPermission = {
  READ_PROJECT: "READ_PROJECT",
  WRITE_ARTIFACT: "WRITE_ARTIFACT",
  RUN_MODEL: "RUN_MODEL",
  USE_DEVICE: "USE_DEVICE",
  RUN_CAD: "RUN_CAD",
  RUN_SHELL: "RUN_SHELL",
} as const;
export type SkillPermission =
  (typeof SkillPermission)[keyof typeof SkillPermission];

/** Skill 风险等级 */
export const SkillRiskLevel = {
  LOW: "low",
  MEDIUM: "medium",
  HIGH: "high",
} as const;
export type SkillRiskLevel =
  (typeof SkillRiskLevel)[keyof typeof SkillRiskLevel];

/** Skill 确认策略 */
export const SkillConfirmationPolicy = {
  NEVER: "never",
  BEFORE_EXTERNAL_EFFECT: "before_external_effect",
  ALWAYS: "always",
} as const;
export type SkillConfirmationPolicy =
  (typeof SkillConfirmationPolicy)[keyof typeof SkillConfirmationPolicy];

/** 模型路由策略 */
export const ModelRouteStrategy = {
  BALANCED: "BALANCED",
  COST_FIRST: "COST_FIRST",
  QUALITY_FIRST: "QUALITY_FIRST",
  FAST_FIRST: "FAST_FIRST",
} as const;
export type ModelRouteStrategy =
  (typeof ModelRouteStrategy)[keyof typeof ModelRouteStrategy];

/** 产物类型 */
export const ArtifactKind = {
  DOCUMENT: "DOCUMENT",
  CODE: "CODE",
  IMAGE: "IMAGE",
  MODEL_3D: "MODEL_3D",
  DEVICE_LOG: "DEVICE_LOG",
  PACKAGE: "PACKAGE",
  REPORT: "REPORT",
} as const;
export type ArtifactKind = (typeof ArtifactKind)[keyof typeof ArtifactKind];

/** 产物状态 */
export const ArtifactStatus = {
  DRAFT: "DRAFT",
  GENERATING: "GENERATING",
  NEEDS_REVIEW: "NEEDS_REVIEW",
  APPROVED: "APPROVED",
  REJECTED: "REJECTED",
  STALE: "STALE",
  FAILED: "FAILED",
  ARCHIVED: "ARCHIVED",
} as const;
export type ArtifactStatus = (typeof ArtifactStatus)[keyof typeof ArtifactStatus];

/** 三师领域产物状态；保留现有 ArtifactStatus 供旧链路兼容。 */
export const DomainArtifactStatus = {
  DRAFT: "draft",
  PENDING_CONFIRMATION: "pending_confirmation",
  CONFIRMED: "confirmed",
  OUTDATED: "outdated",
  ARCHIVED: "archived",
} as const;
export type DomainArtifactStatus =
  (typeof DomainArtifactStatus)[keyof typeof DomainArtifactStatus];

export const SharedFactStatus = {
  PROPOSED: "proposed",
  CONFIRMED: "confirmed",
  SUPERSEDED: "superseded",
  REJECTED: "rejected",
} as const;
export type SharedFactStatus =
  (typeof SharedFactStatus)[keyof typeof SharedFactStatus];

export const HandoffStatus = {
  PROPOSED: "proposed",
  ACCEPTED: "accepted",
  IN_PROGRESS: "in_progress",
  COMPLETED: "completed",
  REJECTED: "rejected",
  CANCELLED: "cancelled",
} as const;
export type HandoffStatus = (typeof HandoffStatus)[keyof typeof HandoffStatus];

export const PendingItemPriority = {
  SAFETY: "safety",
  BLOCKING: "blocking",
  CONFLICT: "conflict",
  CONFIRMATION: "confirmation",
  MISSING_INPUT: "missing_input",
  NORMAL: "normal",
} as const;
export type PendingItemPriority =
  (typeof PendingItemPriority)[keyof typeof PendingItemPriority];

export const PendingItemStatus = {
  OPEN: "open",
  RESOLVED: "resolved",
  DISMISSED: "dismissed",
} as const;
export type PendingItemStatus =
  (typeof PendingItemStatus)[keyof typeof PendingItemStatus];

export const PendingItemKind = {
  GENERAL: "general",
  LOCAL_EXECUTION_AUTHORIZATION: "local_execution_authorization",
} as const;
export type PendingItemKind =
  (typeof PendingItemKind)[keyof typeof PendingItemKind];

export const PendingItemActionType = {
  RESUME_SKILL_RUN: "resume_skill_run",
} as const;
export type PendingItemActionType =
  (typeof PendingItemActionType)[keyof typeof PendingItemActionType];

/** 产物预览类型 */
export const ArtifactPreviewKind = {
  DOCUMENT: "DOCUMENT",
  CODE: "CODE",
  IMAGE: "IMAGE",
  MODEL_3D: "MODEL_3D",
  TEXT: "TEXT",
} as const;
export type ArtifactPreviewKind =
  (typeof ArtifactPreviewKind)[keyof typeof ArtifactPreviewKind];

/** 项目包状态 */
export const ProjectPackageStatus = {
  READY: "READY",
  EXPORTED: "EXPORTED",
  IMPORTED: "IMPORTED",
  BLOCKED: "BLOCKED",
  FAILED: "FAILED",
} as const;
export type ProjectPackageStatus =
  (typeof ProjectPackageStatus)[keyof typeof ProjectPackageStatus];

/** 项目包条目类型 */
export const ProjectPackageItemKind = {
  PROJECT: "PROJECT",
  ARTIFACT: "ARTIFACT",
  ARTIFACT_FILE: "ARTIFACT_FILE",
  MANIFEST: "MANIFEST",
  PRIVACY_REPORT: "PRIVACY_REPORT",
} as const;
export type ProjectPackageItemKind =
  (typeof ProjectPackageItemKind)[keyof typeof ProjectPackageItemKind];

/** 项目包导入冲突策略 */
export const ProjectPackageConflictStrategy = {
  CREATE_COPY: "CREATE_COPY",
  FAIL_IF_EXISTS: "FAIL_IF_EXISTS",
} as const;
export type ProjectPackageConflictStrategy =
  (typeof ProjectPackageConflictStrategy)[keyof typeof ProjectPackageConflictStrategy];

/** MVP 就绪度状态 */
export const MvpReadinessStatus = {
  READY: "READY",
  NEEDS_ACTION: "NEEDS_ACTION",
  BLOCKED: "BLOCKED",
} as const;
export type MvpReadinessStatus =
  (typeof MvpReadinessStatus)[keyof typeof MvpReadinessStatus];

/** MVP 就绪度检查项 */
export const MvpReadinessItemId = {
  PROJECT_BASELINE: "PROJECT_BASELINE",
  SOLUTION: "SOLUTION",
  PROPOSAL: "PROPOSAL",
  EXECUTION_PLAN: "EXECUTION_PLAN",
  SPEC: "SPEC",
  CODE: "CODE",
  DEVICE_DRY_RUN: "DEVICE_DRY_RUN",
  CAD: "CAD",
  LESSON: "LESSON",
  PACKAGE: "PACKAGE",
  ARTIFACTS: "ARTIFACTS",
  SECURITY: "SECURITY",
} as const;
export type MvpReadinessItemId =
  (typeof MvpReadinessItemId)[keyof typeof MvpReadinessItemId];

/** 浮窗类型 */
export const FloatingWindowKind = {
  DOCUMENT: "document",
  CODE: "code",
  MODEL_3D: "model3d",
  IMAGE: "image",
  TERMINAL: "terminal",
  WEB_PREVIEW: "web-preview",
  HARDWARE_COMPONENT: "hardware-component",
  HARDWARE_SKILL: "hardware-skill",
  MECHANICAL_PROFILE: "mechanical-profile",
  AGENT_PACKAGE: "agent-package",
} as const;
export type FloatingWindowKind =
  (typeof FloatingWindowKind)[keyof typeof FloatingWindowKind];

/** Spec 文件类型 */
export const SpecFileKind = {
  PROJECT_SPEC: "PROJECT_SPEC",
  BOM: "BOM",
  IO_MAP: "IO_MAP",
} as const;
export type SpecFileKind = (typeof SpecFileKind)[keyof typeof SpecFileKind];

/** Spec 运行状态 */
export const SpecRunStatus = {
  DRAFT: "DRAFT",
  VALIDATED: "VALIDATED",
  APPROVED: "APPROVED",
  REJECTED: "REJECTED",
  STALE: "STALE",
  FAILED: "FAILED",
} as const;
export type SpecRunStatus =
  (typeof SpecRunStatus)[keyof typeof SpecRunStatus];

/** Code Agent 文件类型 */
export const CodeFileKind = {
  MAIN: "MAIN",
  DRIVER: "DRIVER",
  CONFIG: "CONFIG",
  README: "README",
  TEST: "TEST",
} as const;
export type CodeFileKind = (typeof CodeFileKind)[keyof typeof CodeFileKind];

/** Code Agent 运行状态 */
export const CodeRunStatus = {
  DRAFT: "DRAFT",
  TESTING: "TESTING",
  READY_FOR_REVIEW: "READY_FOR_REVIEW",
  ACCEPTED: "ACCEPTED",
  STALE: "STALE",
  REJECTED: "REJECTED",
  ROLLED_BACK: "ROLLED_BACK",
  FAILED: "FAILED",
} as const;
export type CodeRunStatus =
  (typeof CodeRunStatus)[keyof typeof CodeRunStatus];

/** 代码产物面向的受控设备运行时。 */
export const CodeRuntime = {
  MICROPYTHON: "MICROPYTHON",
  ESP_CLAW_LUA: "ESP_CLAW_LUA",
} as const;
export type CodeRuntime = (typeof CodeRuntime)[keyof typeof CodeRuntime];

/** 代码版本来源 */
export const CodeRevisionSource = {
  MODEL: "MODEL",
  USER: "USER",
} as const;
export type CodeRevisionSource =
  (typeof CodeRevisionSource)[keyof typeof CodeRevisionSource];

/** MicroPython 本地验证维度 */
export const CodeValidationKind = {
  STATIC: "STATIC",
  SYNTAX: "SYNTAX",
  SIMULATION: "SIMULATION",
} as const;
export type CodeValidationKind =
  (typeof CodeValidationKind)[keyof typeof CodeValidationKind];

/** MicroPython 本地验证状态；已执行项只由子进程退出码决定。 */
export const CodeValidationStatus = {
  PASSED: "PASSED",
  FAILED: "FAILED",
  NOT_RUN: "NOT_RUN",
} as const;
export type CodeValidationStatus =
  (typeof CodeValidationStatus)[keyof typeof CodeValidationStatus];

/** CAD Agent 模板类型 */
export const CadTemplateKind = {
  COMPONENT_MOUNT: "COMPONENT_MOUNT",
  FREEFORM_STRUCTURE: "FREEFORM_STRUCTURE",
  UNIHIKER_K10_PHOTO_ALBUM: "UNIHIKER_K10_PHOTO_ALBUM",
  SENSOR_BRACKET: "SENSOR_BRACKET",
  MCU_MOUNT: "MCU_MOUNT",
  MOTOR_MOUNT: "MOTOR_MOUNT",
  SERVO_MOUNT: "SERVO_MOUNT",
  SIMPLE_ENCLOSURE: "SIMPLE_ENCLOSURE",
  PANEL_CUTOUT: "PANEL_CUTOUT",
  BOX_WITH_LID: "BOX_WITH_LID",
} as const;
export type CadTemplateKind =
  (typeof CadTemplateKind)[keyof typeof CadTemplateKind];

/** CAD Agent 文件类型 */
export const CadFileKind = {
  STEP: "STEP",
  STL: "STL",
  PARAMETERS: "PARAMETERS",
} as const;
export type CadFileKind = (typeof CadFileKind)[keyof typeof CadFileKind];

/** CAD 持久化 Job 状态；状态由本地 Tool Runner/Worker 产生。 */
export const CadJobStatus = {
  QUEUED: "QUEUED",
  RUNNING: "RUNNING",
  CANCEL_REQUESTED: "CANCEL_REQUESTED",
  CANCELED: "CANCELED",
  SUCCEEDED: "SUCCEEDED",
  FAILED: "FAILED",
  TIMED_OUT: "TIMED_OUT",
  INTERRUPTED: "INTERRUPTED",
} as const;
export type CadJobStatus = (typeof CadJobStatus)[keyof typeof CadJobStatus];

/** CAD Job 的确定性执行阶段。 */
export const CadJobPhase = {
  QUEUED: "QUEUED",
  VALIDATING: "VALIDATING",
  RESOLVING_PROFILES: "RESOLVING_PROFILES",
  LAYOUT: "LAYOUT",
  BUILDING: "BUILDING",
  EXPORTING: "EXPORTING",
  VALIDATING_OUTPUTS: "VALIDATING_OUTPUTS",
  STORING_ARTIFACTS: "STORING_ARTIFACTS",
  COMPLETED: "COMPLETED",
  CANCELED: "CANCELED",
  FAILED: "FAILED",
} as const;
export type CadJobPhase = (typeof CadJobPhase)[keyof typeof CadJobPhase];

/** CAD Worker 生成的不可变文件角色。 */
export const CadOutputRole = {
  STEP_ASSEMBLY: "STEP_ASSEMBLY",
  STEP_PRINTABLE_PARTS: "STEP_PRINTABLE_PARTS",
  STL_PRINTABLE_PARTS: "STL_PRINTABLE_PARTS",
  GLB_PREVIEW: "GLB_PREVIEW",
  PARAMETERS: "PARAMETERS",
  PROFILE_SNAPSHOTS: "PROFILE_SNAPSHOTS",
  VALIDATION_REPORT: "VALIDATION_REPORT",
  GEOMETRY_SUMMARY: "GEOMETRY_SUMMARY",
  MANIFEST: "MANIFEST",
} as const;
export type CadOutputRole = (typeof CadOutputRole)[keyof typeof CadOutputRole];

/** CAD 受信任机械档案允许的安装面。 */
export const CadMountSurface = {
  BASE_FLOOR: "base_floor",
  LID_INNER: "lid_inner",
  LID_OUTER: "lid_outer",
  FRONT_INNER: "front_inner",
  BACK_INNER: "back_inner",
  LEFT_INNER: "left_inner",
  RIGHT_INNER: "right_inner",
  EXTERNAL: "external",
} as const;
export type CadMountSurface =
  (typeof CadMountSurface)[keyof typeof CadMountSurface];

/** CAD Agent 运行状态 */
export const CadRunStatus = {
  DRAFT: "DRAFT",
  QUEUED: "QUEUED",
  RUNNING: "RUNNING",
  VALIDATED: "VALIDATED",
  READY_FOR_REVIEW: "READY_FOR_REVIEW",
  APPROVED: "APPROVED",
  REJECTED: "REJECTED",
  STALE: "STALE",
  CANCELED: "CANCELED",
  FAILED: "FAILED",
} as const;
export type CadRunStatus =
  (typeof CadRunStatus)[keyof typeof CadRunStatus];

/** Lesson Agent 文档类型 */
export const LessonDocumentKind = {
  TEACHER_GUIDE: "TEACHER_GUIDE",
  STUDENT_WORKSHEET: "STUDENT_WORKSHEET",
  RUBRIC: "RUBRIC",
  SAFETY_NOTES: "SAFETY_NOTES",
} as const;
export type LessonDocumentKind =
  (typeof LessonDocumentKind)[keyof typeof LessonDocumentKind];

/** Lesson Agent 运行状态 */
export const LessonRunStatus = {
  DRAFT: "DRAFT",
  READY_FOR_REVIEW: "READY_FOR_REVIEW",
  APPROVED: "APPROVED",
  REJECTED: "REJECTED",
  STALE: "STALE",
  FAILED: "FAILED",
} as const;
export type LessonRunStatus =
  (typeof LessonRunStatus)[keyof typeof LessonRunStatus];

/** 设备会话状态 */
export const DeviceSessionStatus = {
  DISCONNECTED: "DISCONNECTED",
  DISCOVERED: "DISCOVERED",
  CONNECTING: "CONNECTING",
  CONNECTED: "CONNECTED",
  ATTACHED_UNVERIFIED: "ATTACHED_UNVERIFIED",
  RUNTIME_BUSY: "RUNTIME_BUSY",
  MANAGED: "MANAGED",
  UPLOADING: "UPLOADING",
  RESTARTING: "RESTARTING",
  VERIFYING: "VERIFYING",
  READY: "READY",
  ERROR: "ERROR",
} as const;
export type DeviceSessionStatus =
  (typeof DeviceSessionStatus)[keyof typeof DeviceSessionStatus];

export const DeviceTerminalStatus = {
  IDLE: "IDLE",
  STARTING: "STARTING",
  RUNNING: "RUNNING",
  STOPPED: "STOPPED",
  ERROR: "ERROR",
} as const;

export type DeviceTerminalStatus =
  (typeof DeviceTerminalStatus)[keyof typeof DeviceTerminalStatus];

/** 掌问允许执行上传、仿真和调参的唯一主控板型。 */
export const SupportedDeviceBoardId = {
  XIAO_ESP32S3_SENSE: "seeedstudio/xiao_esp32s3_sense",
  DFROBOT_K10: "dfrobot/dfrobot_k10",
} as const;
export type SupportedDeviceBoardId =
  (typeof SupportedDeviceBoardId)[keyof typeof SupportedDeviceBoardId];

/** 已接受代码的同级部署通道。 */
export const DeviceDeploymentChannel = {
  USB_SERIAL: "USB_SERIAL",
  ESP_CLAW: "ESP_CLAW",
} as const;
export type DeviceDeploymentChannel =
  (typeof DeviceDeploymentChannel)[keyof typeof DeviceDeploymentChannel];

/** 设备操作类型 */
export const DeviceOperationKind = {
  UPLOAD_CODE: "UPLOAD_CODE",
  FLASH_FIRMWARE: "FLASH_FIRMWARE",
  INSTALL_APPLICATION: "INSTALL_APPLICATION",
  SYNC_PARAMETERS: "SYNC_PARAMETERS",
  BACKUP_FILES: "BACKUP_FILES",
  REPL_LOG: "REPL_LOG",
} as const;
export type DeviceOperationKind =
  (typeof DeviceOperationKind)[keyof typeof DeviceOperationKind];

/** 设备操作状态 */
export const DeviceOperationStatus = {
  QUEUED: "QUEUED",
  RUNNING: "RUNNING",
  DRY_RUN_COMPLETE: "DRY_RUN_COMPLETE",
  COMPLETED: "COMPLETED",
  BLOCKED: "BLOCKED",
  FAILED: "FAILED",
  CANCELED: "CANCELED",
  TIMED_OUT: "TIMED_OUT",
} as const;
export type DeviceOperationStatus =
  (typeof DeviceOperationStatus)[keyof typeof DeviceOperationStatus];

export const DeviceOperationPhase = {
  QUEUED: "QUEUED",
  PREFLIGHT: "PREFLIGHT",
  INTERRUPT_RUNTIME: "INTERRUPT_RUNTIME",
  BACKUP: "BACKUP",
  TRANSFER: "TRANSFER",
  VERIFY_FILES: "VERIFY_FILES",
  START_RUNTIME: "START_RUNTIME",
  RESTART: "RESTART",
  RECONNECT: "RECONNECT",
  VERIFY_RUNTIME: "VERIFY_RUNTIME",
  FIRMWARE_VALIDATE: "FIRMWARE_VALIDATE",
  MANIFEST_VALIDATE: "MANIFEST_VALIDATE",
  WRITE_SEGMENTS: "WRITE_SEGMENTS",
  VERIFY_SEGMENTS: "VERIFY_SEGMENTS",
  PROVISION: "PROVISION",
  RUNTIME_HANDSHAKE: "RUNTIME_HANDSHAKE",
  FLASH_WRITE: "FLASH_WRITE",
  RESTORE: "RESTORE",
  COMPLETE: "COMPLETE",
} as const;
export type DeviceOperationPhase =
  (typeof DeviceOperationPhase)[keyof typeof DeviceOperationPhase];

/** LLM 供应商 */
export const LLMProviderId = {
  DEEPSEEK: "deepseek",
  QWEN: "qwen",
  GLM: "glm",
  KIMI: "kimi",
} as const;
export type LLMProviderId = (typeof LLMProviderId)[keyof typeof LLMProviderId];

/** 当前正式支持的模型 */
export const LLMModelId = {
  DEEPSEEK_V4_FLASH: "deepseek-v4-flash",
  DEEPSEEK_V4_PRO: "deepseek-v4-pro",
  QWEN_3_7_MAX: "qwen3.7-max",
  QWEN_PLUS: "qwen-plus",
  GLM_5_2: "glm-5.2",
  GLM_5_1: "glm-5.1",
  KIMI_K3: "kimi-k3",
  KIMI_K2_7_CODE: "kimi-k2.7-code",
  KIMI_K2_7_CODE_HIGHSPEED: "kimi-k2.7-code-highspeed",
} as const;
export type LLMModelId =
  | (typeof LLMModelId)[keyof typeof LLMModelId]
  | (string & { readonly __customModelId?: never });

/** 思考模式 */
export const ThinkingMode = {
  AUTO: "AUTO",
  DISABLED: "DISABLED",
  ENABLED: "ENABLED",
} as const;
export type ThinkingMode = (typeof ThinkingMode)[keyof typeof ThinkingMode];

/** 对话角色 */
export const ChatRole = {
  SYSTEM: "system",
  USER: "user",
  ASSISTANT: "assistant",
} as const;
export type ChatRole = (typeof ChatRole)[keyof typeof ChatRole];

/** 对话消息状态 */
export const ChatMessageStatus = {
  READY: "READY",
  SENDING: "SENDING",
  STREAMING: "STREAMING",
  COMPLETED: "COMPLETED",
  FAILED: "FAILED",
  CANCELED: "CANCELED",
} as const;
export type ChatMessageStatus =
  (typeof ChatMessageStatus)[keyof typeof ChatMessageStatus];

/** 流式响应片段类型 */
export const StreamChunkType = {
  START: "START",
  PROGRESS: "PROGRESS",
  CONTENT_DELTA: "CONTENT_DELTA",
  REASONING_DELTA: "REASONING_DELTA",
  COMPLETED: "COMPLETED",
  ERROR: "ERROR",
  CANCELED: "CANCELED",
} as const;
export type StreamChunkType =
  (typeof StreamChunkType)[keyof typeof StreamChunkType];

/** 对话过程中的服务端受控动作 */
export const ChatProgressAction = {
  CONTEXT_READ: "CONTEXT_READ",
  CLOUD_LLM_REQUEST: "CLOUD_LLM_REQUEST",
  OUTPUT_VALIDATE: "OUTPUT_VALIDATE",
  PROJECT_UPDATE: "PROJECT_UPDATE",
  CODE_DRAFT_SAVE: "CODE_DRAFT_SAVE",
  CAD_DRAFT_SAVE: "CAD_DRAFT_SAVE",
  LOCAL_EXECUTION_AUTHORIZATION: "LOCAL_EXECUTION_AUTHORIZATION",
  LOCAL_TOOL_EXECUTION: "LOCAL_TOOL_EXECUTION",
} as const;
export type ChatProgressAction =
  (typeof ChatProgressAction)[keyof typeof ChatProgressAction];

/** 对话过程动作状态 */
export const ChatProgressStatus = {
  RUNNING: "RUNNING",
  COMPLETED: "COMPLETED",
  WAITING: "WAITING",
  FAILED: "FAILED",
} as const;
export type ChatProgressStatus =
  (typeof ChatProgressStatus)[keyof typeof ChatProgressStatus];

/** 澄清问题类型 */
export const ConversationResponseType = {
  CLARIFICATION: "clarification",
  NEXT_ACTION: "next_action",
  SOLUTION: "solution",
  SOLUTION_CARD: "solution_card",
  CODE_ARTIFACT: "code_artifact",
  CAD_ARTIFACT: "cad_artifact",
  HARDWARE_SELECTION: "hardware_selection",
  PROPOSAL_ACTION: "proposal_action",
  SYSTEM_NOTICE: "system_notice",
} as const;
export type ConversationResponseType =
  (typeof ConversationResponseType)[keyof typeof ConversationResponseType];

export const ConversationActionType = {
  GENERATE_SOLUTION: "generate_solution",
  CONTINUE_CLARIFICATION: "continue_clarification",
  USE_RECOMMENDED_DEFAULTS: "use_recommended_defaults",
  VIEW_SOLUTION: "view_solution",
  OPEN_SOLUTION_FLOATING: "open_solution_floating",
  MODIFY_SOLUTION: "modify_solution",
  CONFIRM_SOLUTION: "confirm_solution",
  ACCEPT_SOLUTION_REVISION: "accept_solution_revision",
  RESTORE_PREVIOUS_SOLUTION: "restore_previous_solution",
  GENERATE_PROJECT_PROPOSAL: "generate_project_proposal",
  CONFIRM_SOLUTION_AND_GENERATE_PROJECT_PROPOSAL:
    "confirm_solution_and_generate_project_proposal",
  GENERATE_LESSON_VERSION: "generate_lesson_version",
  CONFIRM_SOLUTION_AND_GENERATE_LESSON_VERSION:
    "confirm_solution_and_generate_lesson_version",
  VIEW_PROJECT_PROPOSAL: "view_project_proposal",
  MODIFY_PROJECT_PROPOSAL: "modify_project_proposal",
  CONFIRM_PROJECT_PROPOSAL: "confirm_project_proposal",
  CONTINUE_PROJECT_IMPLEMENTATION: "continue_project_implementation",
  CONTINUE_CHAT: "continue_chat",
} as const;
export type ConversationActionType =
  (typeof ConversationActionType)[keyof typeof ConversationActionType];

export const ConversationIntent = {
  DESCRIBE_IDEA: "describe_idea",
  ANSWER_QUESTION: "answer_question",
  REQUEST_RECOMMENDATION: "request_recommendation",
  GENERATE_SOLUTION: "generate_solution",
  REVISE_SOLUTION: "revise_solution",
  CONFIRM_SOLUTION: "confirm_solution",
  GENERATE_PROPOSAL: "generate_proposal",
  REVISE_PROPOSAL: "revise_proposal",
  CONFIRM_PROPOSAL: "confirm_proposal",
  CONTINUE_PROJECT: "continue_project",
  DEVICE_REQUEST: "device_request",
  GENERAL_CHAT: "general_chat",
} as const;
export type ConversationIntent =
  (typeof ConversationIntent)[keyof typeof ConversationIntent];

export const ProjectWorkflowState = {
  IDEA_EMPTY: "IDEA_EMPTY",
  IDEA_RECEIVED: "IDEA_RECEIVED",
  CLARIFICATION_PENDING: "CLARIFICATION_PENDING",
  CLARIFICATION_PROCESSING: "CLARIFICATION_PROCESSING",
  READY_FOR_SOLUTION: "READY_FOR_SOLUTION",
  SOLUTION_GENERATING: "SOLUTION_GENERATING",
  SOLUTION_DRAFT: "SOLUTION_DRAFT",
  SOLUTION_REVISING: "SOLUTION_REVISING",
  SOLUTION_CONFIRMED: "SOLUTION_CONFIRMED",
  PROPOSAL_GENERATING: "PROPOSAL_GENERATING",
  PROPOSAL_DRAFT: "PROPOSAL_DRAFT",
  PROPOSAL_CONFIRMED: "PROPOSAL_CONFIRMED",
  EXECUTION_PLANNING: "EXECUTION_PLANNING",
  EXECUTION_RUNNING: "EXECUTION_RUNNING",
  DEVICE_PENDING: "DEVICE_PENDING",
  COMPLETED: "COMPLETED",
} as const;
export type ProjectWorkflowState =
  (typeof ProjectWorkflowState)[keyof typeof ProjectWorkflowState];

export const ConversationAnswerType = {
  SINGLE: "single",
  MULTIPLE: "multiple",
  TEXT: "text",
  BATCH: "batch",
} as const;
export type ConversationAnswerType =
  (typeof ConversationAnswerType)[keyof typeof ConversationAnswerType];

export const ClarificationQuestionMode = {
  SINGLE: "single",
  MULTIPLE: "multiple",
  TEXT: "text",
} as const;
export type ClarificationQuestionMode =
  (typeof ClarificationQuestionMode)[keyof typeof ClarificationQuestionMode];

export const ClarificationQuestionType = {
  SINGLE_SELECT: "SINGLE_SELECT",
  MULTI_SELECT: "MULTI_SELECT",
  TEXT: "TEXT",
} as const;
export type ClarificationQuestionType =
  (typeof ClarificationQuestionType)[keyof typeof ClarificationQuestionType];

/** 方案状态 */
export const SolutionStatus = {
  DRAFT: "DRAFT",
  CONFIRMED: "CONFIRMED",
  SUPERSEDED: "SUPERSEDED",
  OUTDATED: "OUTDATED",
} as const;
export type SolutionStatus =
  (typeof SolutionStatus)[keyof typeof SolutionStatus];

/** 立项书状态 */
export const ProposalStatus = {
  DRAFT: "DRAFT",
  APPROVED: "APPROVED",
  REJECTED: "REJECTED",
  STALE: "STALE",
  SUPERSEDED: "SUPERSEDED",
} as const;
export type ProposalStatus =
  (typeof ProposalStatus)[keyof typeof ProposalStatus];

/** 立项书导出格式 */
export const ProposalExportFormat = {
  MARKDOWN: "MARKDOWN",
  DOCX: "DOCX",
  PDF: "PDF",
} as const;
export type ProposalExportFormat =
  (typeof ProposalExportFormat)[keyof typeof ProposalExportFormat];

/** 硬件分类 */
export const SerialPortType = {
  USB: "usb",
  PCI: "pci",
  BLUETOOTH: "bluetooth",
  UNKNOWN: "unknown",
} as const;
export type SerialPortType = (typeof SerialPortType)[keyof typeof SerialPortType];

export const SerialPortStatus = {
  AVAILABLE: "available",
  BUSY: "busy",
  CONNECTED: "connected",
  UNKNOWN: "unknown",
} as const;
export type SerialPortStatus =
  (typeof SerialPortStatus)[keyof typeof SerialPortStatus];

export const HardwareCategory = {
  MCU: "MCU",
  SENSOR: "SENSOR",
  ACTUATOR: "ACTUATOR",
  DISPLAY: "DISPLAY",
  POWER: "POWER",
  STRUCTURE: "STRUCTURE",
} as const;
export type HardwareCategory =
  (typeof HardwareCategory)[keyof typeof HardwareCategory];

/** 硬件组件状态 */
export const HardwareComponentStatus = {
  ACTIVE: "ACTIVE",
  ARCHIVED: "ARCHIVED",
} as const;
export type HardwareComponentStatus =
  (typeof HardwareComponentStatus)[keyof typeof HardwareComponentStatus];

/** Hardware Skill 生命周期状态 */
export const HardwareSkillStatus = {
  DRAFT: "DRAFT",
  ACTIVE: "ACTIVE",
  ARCHIVED: "ARCHIVED",
  INVALID: "INVALID",
} as const;
export type HardwareSkillStatus =
  (typeof HardwareSkillStatus)[keyof typeof HardwareSkillStatus];

/** Hardware Skill 的资料来源 */
export const HardwareSkillSourceKind = {
  BUNDLED: "BUNDLED",
  MIGRATED: "MIGRATED",
  UPLOAD: "UPLOAD",
  DIALOGUE: "DIALOGUE",
  MANUAL: "MANUAL",
} as const;
export type HardwareSkillSourceKind =
  (typeof HardwareSkillSourceKind)[keyof typeof HardwareSkillSourceKind];

/** Sidecar 可执行的声明式硬件规则算子 */
export const HardwareRuleOperator = {
  RANGE_OVERLAP: "range-overlap",
  SUM_LTE: "sum-lte",
  UNIQUE: "unique",
  CONTAINS_ANY: "contains-any",
  REQUIRED_IF: "required-if",
} as const;
export type HardwareRuleOperator =
  (typeof HardwareRuleOperator)[keyof typeof HardwareRuleOperator];

/** 校验严重级别 */
export const ValidationSeverity = {
  PASS: "PASS",
  WARNING: "WARNING",
  FAIL: "FAIL",
} as const;
export type ValidationSeverity =
  (typeof ValidationSeverity)[keyof typeof ValidationSeverity];

/** LLM 错误码 */
export const LLMErrorCode = {
  CONFIG_MISSING: "CONFIG_MISSING",
  LLM_OUTPUT_INVALID: "LLM_OUTPUT_INVALID",
  LOCAL_OUTPUT_REJECTED: "LOCAL_OUTPUT_REJECTED",
  GENERATION_INTERRUPTED: "GENERATION_INTERRUPTED",
  INVALID_REQUEST: "INVALID_REQUEST",
  AUTH_FAILED: "AUTH_FAILED",
  INSUFFICIENT_BALANCE: "INSUFFICIENT_BALANCE",
  INVALID_PARAMETERS: "INVALID_PARAMETERS",
  RATE_LIMITED: "RATE_LIMITED",
  SERVER_ERROR: "SERVER_ERROR",
  SERVICE_BUSY: "SERVICE_BUSY",
  NETWORK_UNAVAILABLE: "NETWORK_UNAVAILABLE",
  TIMEOUT: "TIMEOUT",
  CANCELED: "CANCELED",
  SIDECAR_UNAVAILABLE: "SIDECAR_UNAVAILABLE",
  QUESTION_NOT_FOUND: "QUESTION_NOT_FOUND",
  QUESTION_ALREADY_ANSWERED: "QUESTION_ALREADY_ANSWERED",
  OPTION_NOT_ALLOWED: "OPTION_NOT_ALLOWED",
  CLARIFICATION_INCOMPLETE: "CLARIFICATION_INCOMPLETE",
  DUPLICATE_QUESTION_ANSWER: "DUPLICATE_QUESTION_ANSWER",
  STALE_CONVERSATION_TURN: "STALE_CONVERSATION_TURN",
  PROJECT_CONTEXT_MISMATCH: "PROJECT_CONTEXT_MISMATCH",
  DUPLICATE_TURN: "DUPLICATE_TURN",
  UNKNOWN: "UNKNOWN",
} as const;
export type LLMErrorCode = (typeof LLMErrorCode)[keyof typeof LLMErrorCode];
