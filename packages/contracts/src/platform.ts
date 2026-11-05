/** 掌问本地 Web boundary. Validated on the server by zhangwen.web.models. */
export type WorkspaceMode = 'engineer' | 'structure' | 'learning';
export type ProgrammingMode = 'micropython' | 'chat-coding';
export interface ChatCodingRecord {
  protocol?: 'session-v1' | 'legacy-websocket';
  id: string; kind: 'submission' | 'device-history' | 'observation';
  createdAt: string; text: string;
  state?: 'pending' | 'submitted' | 'outcome-unknown' | 'rejected';
  session?: string; bootId?: string; runId?: number;
  role?: 'user' | 'assistant' | 'system' | 'tool';
  taskRevision?: number; taskChecksum?: string;
  files?: string[]; links?: {url:string;label:string}[];
}
export interface ChatCodingCheckpoint { schemaVersion: 1; records: ChatCodingRecord[] }
export interface ChatCodingState extends ChatCodingCheckpoint {
  protocol?: 'session-v1' | 'legacy-websocket';
  connectionError?: string;
  revision: number; connected: boolean; endpoint?: string; bootId?: string;
  session?: string; runState?: 'idle' | 'queued' | 'running' | 'unavailable';
  bound?: boolean;
}
export interface UpdateJob {
  state: 'installing' | 'ready' | 'failed'; revision: string; message: string;
  startedAt: string; finishedAt?: string;
}
export interface PlatformUpdate {
  /** Plain-text release items from the same version document as each label. */
  currentReleaseNotes: string[]; latestReleaseNotes: string[];
  deployment: 'managed' | 'development'; currentRevision: string | null;
  currentVersion: string | null; latestVersion: string | null;
  latestRevision: string | null; checkedAt: string | null;
  state: 'unchecked' | 'available' | 'current' | 'development' | 'error';
  message: string; canInstall: boolean; checkToken: string | null; job: UpdateJob | null;
}
export interface InstallUpdate { revision: string; checkToken: string; confirmed: true }
export interface HardwareMedia { path: string; alt: string; url: string; attribution: string; license: string; sourceUrl: string }
/** Catalog labels come from the installed Hardware Skill; selection is not compatibility approval. */
export interface HardwareCatalog {
  brand: string; moduleType: string; sourceUrl: string;
  programmingSupport: 'reference' | 'existing'; electricalVerified: boolean;
}
export interface HardwareSummary {
  programmingMode?: ProgrammingMode;
  skillName: string; componentId: string; displayName: string; description: string;
  category: 'MCU' | 'SENSOR' | 'ACTUATOR' | 'DISPLAY' | 'POWER' | 'STRUCTURE';
  status: string; revision: string; verificationStatus: string; media: HardwareMedia[];
  catalog?: HardwareCatalog;
  /** User-marked module/controller checks. Never inferred from code or catalog status. */
  verifiedBoardIds?: string[];
  personal?: boolean;
  verificationRecords?: HardwareVerificationRecord[];
}
export interface HardwareDetail extends HardwareSummary {
  /** Canonical Hardware Skill mechanical profile; dimensions and coordinates are mm. */
  mechanicalProfile?: Record<string, unknown> | null;
  files: { path: string; content: string; title: string }[];
  specification: { electrical: { voltage: number; logicLevel: number; communicationProtocol: string }; notes: string };
  localExamples?: HardwareExample[];
  moduleGuides?: HardwareModuleGuide[];
  /** User-declared module scope, not physical verification. Empty means unmarked. */
  supportedBoardIds?: string[];
  i2c?: HardwareI2CInfo;
}
export interface SaveHardwareMechanical { expectedRevision: string; profile: Record<string, unknown>; notes: string }
/** 7-bit device addresses from the canonical skill, not a scan or verification. */
export interface HardwareI2CInfo { defaultAddress: string | null; addresses: string[]; notes: string; sources: string[] }
/** Stored inside the canonical Hardware Skill examples/usage.md, scoped by board. */
export interface HardwareExample { boardId: string; notes: string; code: string; setup?: Record<string, string>; i2cAddress?: string }
export interface SaveHardwareExample extends HardwareExample { expectedRevision: string; supportedBoardIds?: string[] }
export type HardwareVerificationState = 'unverified' | 'documented' | 'pending' | 'passed' | 'failed';
export interface HardwareVerificationRecord {
  boardId: string; dimension: 'identity' | 'electrical' | 'wiring' | 'driver' | 'function' | 'mechanical';
  state: HardwareVerificationState; notes: string; firmware: string; wiring: string; codeHash: string;
  evidence: string; updatedAt: string; stale?: boolean;
}
export interface SaveHardwareVerification { expectedRevision: string; verifiedBoardIds?: string[]; record?: Omit<HardwareVerificationRecord, 'updatedAt' | 'stale' | 'codeHash'> }
export interface CreatePersonalModule {
  name: string; category: 'SENSOR' | 'ACTUATOR' | 'DISPLAY' | 'POWER' | 'STRUCTURE';
  description: string; voltage: number; logicLevel: number; protocol: string;
  boardId: string; code: string; notes: string;
}
export interface ProjectReference {
  id: string; version: number; name: string; text: string; original: string;
  encoding: 'text' | 'base64'; mode: 'auto' | 'pin' | 'off'; checksum: string;
}
export interface ReferenceCitation { id: string; version: number; name: string; startLine: number; endLine: number; text: string }
/** Source-reviewed recipe supplements, installed into the same Hardware Skill document.
 * Functional/diagnostic describes the example's scope, never physical verification.
 */
export interface HardwareGuideField {
  key: string; label: string; default: string; options: { value: string; label: string }[];
}
export interface HardwareModuleGuide {
  boardId: string; kind: 'functional' | 'diagnostic' | 'reference';
  title: string; summary: string; fields: HardwareGuideField[];
  connections: { signal: string; target: string }[];
  notes: string[]; sources: string[]; codeTemplate: string;
}
/** boardId is empty until a controller is explicitly selected in the workspace. */
export interface ProjectSummary { id: string; name: string; boardId: string; componentIds: string[]; revision: number; updatedAt: string; programmingMode?: ProgrammingMode }
export interface CreateProject { name: string; boardId: string; code?: string; componentIds?: string[] }
/** Current API identifiers, verified against the official DeepSeek pricing page. */
export const DEFAULT_AI_MODEL = 'deepseek-flash';
export const DEEPSEEK_MODELS = [DEFAULT_AI_MODEL, 'deepseek-v4-pro'] as const;
export interface AiSettings { aiConfigured: boolean; aiModel: string; aiBaseUrl?: string; mode?: WorkspaceMode; inherited?: boolean }
/** null/omitted key preserves the saved key; empty string explicitly clears it. */
export interface SaveAiSettings { apiKey?: string | null; model: string; baseUrl?: string; mode?: WorkspaceMode }
export interface FirmwareProfile { boardId: string; chip: 'ESP32' | 'ESP32-S3' | 'ESP32-C3'; offset: number; documentation: string;
  image?: { name: string; version: string; url: string; sha256: string; size: number; sourceUrl: string; notes: string }; unavailable?: string }
export type AiCheckId = 'network' | 'key' | 'model' | 'balance' | 'generation';
export interface AiDiagnosticCheck {
  id: AiCheckId; label: string; status: 'running' | 'passed' | 'failed' | 'warning' | 'skipped';
  detail: string; elapsedMs?: number; firstTokenMs?: number; keepAlives?: number;
}
export interface AiDiagnosticReport { model: string; checkedAt: string; healthy: boolean; checks: AiDiagnosticCheck[]; suggestion: string }
/** Testing uses the form's values without saving them or submitting a project. */
export type AiDiagnosticEvent = { type: 'check'; check: AiDiagnosticCheck }
  | { type: 'done'; report: AiDiagnosticReport } | { type: 'error'; detail: string };
export interface Project extends ProjectSummary { code: string; checksum: string; messages: ChatMessage[]; hardwareRevisions?: Record<string, string> }
export interface ChatMessage { id: string; role: 'user' | 'assistant'; content: string; status: string; boardId?: string; componentIds?: string[]; intent?: 'integration' | 'lua-coding' | 'idea-coding'; integrationModuleId?: string; createdAt?: string; references?: ReferenceCitation[]; referenceNotice?: string }
/** integrationModuleId selects one of componentIds, never records a physical test result. */
export interface ChatInput { message: string; code: string; boardId: string; componentIds: string[]; intent?: 'integration' | 'lua-coding' | 'idea-coding'; integrationModuleId?: string }
/** Text-only model output; complete code remains a candidate, never a device action. */
export interface AssistantReply {
  summary: string; points: string[];
  question: { text: string; options: string[] } | null;
  details: string; code: string | null;
}
/** POST chat with Accept: application/x-ndjson. Only done contains a saved, complete answer. */
export type ChatEvent =
  | { type: 'references'; references: ReferenceCitation[]; notice: string }
  | { type: 'status'; phase: 'waiting' }
  | { type: 'heartbeat' }
  | { type: 'delta'; content: string }
  | { type: 'done'; messages: ChatMessage[] }
  | { type: 'error'; detail: string };
export interface Version { revision: number; code: string; checksum: string; createdAt: string; source?: 'saved' | 'ai'; boardId?: string; messageId?: string; name?: string; programmingMode?: ProgrammingMode }
/** Portable checkpoint of the original SQLite project, never includes API settings.
 * Structure asset keys are internal identities, not user-facing directory names.
 * Folder mirrors may use readable categories without changing this import contract. */
export interface ProjectSnapshot {
  workflow?: import('./workflow').WorkflowCheckpoint;
  luaCoding?: LuaCodingCheckpoint;
  format: 'zhangwen-project'; schemaVersion: 1; portableId: string;
  project: { name: string; boardId: string; componentIds: string[]; revision: number; programmingMode?: ProgrammingMode };
  versions: Version[]; messages: ChatMessage[];
  chatCoding?: ChatCodingCheckpoint;
  references?: ProjectReference[];
  structure?: { versions: import('./structure').StructureVersion[]; messages: { id: string; role: string; content: string; createdAt: string }[]; assets: Record<string, { sha256: string; content: string }> };
}
/** Current resource copies for the saved selection; inert, outside device manifests. */
export interface HardwareResourceBundle {
  schemaVersion: 1;
  modules: { id: string; name: string; componentId: string | null; revision: string;
    files: { path: string[]; sha256: string; content: string }[] }[];
}
/** User-named program archive in a project folder; physical results are user observations. */
export interface ProjectProgramRecord {
  format: 'zhangwen-program'; schemaVersion: 1; name: string; createdAt: string;
  boardId: string; boardName: string; componentIds: string[]; checksum: string; sourceRevision: number | null;
  verification: { observed: 'unconfirmed' | 'passed' | 'failed'; note: string; uploadVerifiedAt: string | null; runSubmittedAt: string | null };
}
export interface ProgramRunSubmission {
  projectId: string; revision: number; boardId: string; sha256: string; submittedAt: string;
}
export interface CheckResult {
  valid: boolean; checksum: string;
  diagnostics: { severity: 'PASS' | 'WARNING' | 'FAIL'; message: string; line?: number | null; repair?: 'k10-screen' | 'mpython-pins' }[];
}
export interface CodeRepair { code: string; check: CheckResult; summary: string }
export interface UploadManifest {
  projectId: string; revision: number; boardId: string; hardwareRevisions: Record<string, string>;
  files: { path: 'main.py'; content: string; sha256: string; size: number }[];
}
export type DeviceState = 'disconnected' | 'connecting' | 'connected' | 'busy' | 'running' | 'attention';
export interface DeviceIdentity { implementation: string; machine: string; platform: string; uniqueId: string }
/** Read-only root listing; device writes remain limited to upload-manifest main.py. */
export interface DeviceFile { path: string; size: number; directory: boolean }
export interface DeviceFileContent { path: string; bytes: Uint8Array; sha256: string }

/** Fixed native Mosaico operations. Secrets remain transient, outside projects/models. */
export type MosaicoSection = 'records' | 'status' | 'basic' | 'llm' | 'asr' | 'im' | 'search' | 'memory' | 'logs' | 'capabilities' | 'skills' | 'files';
export interface MosaicoDeviceState { connected: boolean; endpoint?: string; connectionId?: string; status?: Record<string, string | boolean | number>; unknownWrite?: string }
export interface MosaicoConfig { section: string; revision: string; values: Record<string, string>; secrets: string[]; available: string[] }
export interface MosaicoConfigSave { connectionId: string; requestId: string; section: string; revision: string; patch: Record<string, string> }
export interface MosaicoFileEntry { name: string; path: string; is_dir: boolean; size: number }
export interface MosaicoFileData { path: string; content: string; sha256: string; size: number; encoding: 'base64'; missing?: boolean }
export interface MosaicoWriteResult { state: 'verified' | 'accepted'; message: string; backupId?: string; sha256?: string }
/** Inert Lua history in the original Artifact store. Imported receipts never grant execution. */
export interface LuaVersion { revision: number; code: string; checksum: string; source: 'ai' | 'saved'; createdAt: string }
export interface LuaUploadRecord { id: string; revision: number; checksum: string; path: string; createdAt: string; state: 'pending' | 'verified' | 'outcome-unknown'; backupId?: string }
export interface LuaRunRecord { id: string; revision: number; createdAt: string; state: 'submitted' | 'returned' | 'outcome-unknown'; timeoutMs: number; output: string; transport?: 'usb' | 'wifi'; bootId?: string; deviceEndpoint?: string; jobId?: string; deviceState?: string }
/** Explicitly archived after checking a different boot. The original outcome stays intact. */
export interface LuaRunRecovery { id: string; runId: string; previousBootId: string; bootId: string; deviceEndpoint: string; createdAt: string }
export interface RecoverLuaRun { connectionId: string; requestId: string; projectId: string; runId: string; bootId: string; confirmed: true }
export interface LuaWifiSetupRecord { id: string; createdAt: string; state: 'pending' | 'verified' | 'outcome-unknown'; planChecksum: string; files: {path: string; checksum: string; backupId?: string}[] }
export interface LuaCodingCheckpoint { schemaVersion: 1; revision: number; accepted: number | null; versions: LuaVersion[]; uploads: LuaUploadRecord[]; runs: LuaRunRecord[]; wifiSetups?: LuaWifiSetupRecord[]; runRecoveries?: LuaRunRecovery[] }
export interface LuaManifest { projectId: string; revision: number; checksum: string; path: string; content: string; size: number; expectedChecksum: string | null; connectionId: string }
export interface LuaWifiPlan { projectId: string; connectionId: string; bootId: string; planChecksum: string; preservedRules: number; files: {path: string; checksum: string; expectedChecksum: string | null; content: string; size: number}[] }
export interface LuaWifiStatus {
  ready: boolean; message: string; bootId?: string; connectionId?: string;
  serviceReady?: boolean; scriptVerified?: boolean;
  recoverableRunIds?: string[];
  phase?: 'needs-install' | 'needs-restart' | 'needs-code' | 'needs-upload' | 'ready';
  path?: string; checksum?: string; deviceChecksum?: string | null;
}
export interface MosaicoWechatState { active?: boolean; completed?: boolean; configured?: boolean; qr_data_url?: string; status?: string; message?: string; token?: string; account_id?: string; base_url?: string }
export interface UploadReceipt {
  projectId: string; revision: number; sha256: string; identity: DeviceIdentity;
  backupPath: string | null; verifiedAt: string;
}
