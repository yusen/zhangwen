/** Mu Web boundary. Validated on the server by zhangwen.mu_web.models. */
export type WorkspaceMode = 'engineer' | 'structure' | 'learning';
export interface UpdateJob {
  state: 'installing' | 'ready' | 'failed'; revision: string; message: string;
  startedAt: string; finishedAt?: string;
}
export interface PlatformUpdate {
  deployment: 'managed' | 'development'; currentRevision: string | null;
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
  skillName: string; componentId: string; displayName: string; description: string;
  category: 'MCU' | 'SENSOR' | 'ACTUATOR' | 'DISPLAY' | 'POWER' | 'STRUCTURE';
  status: string; revision: string; verificationStatus: string; media: HardwareMedia[];
  catalog?: HardwareCatalog;
}
export interface HardwareDetail extends HardwareSummary {
  files: { path: string; content: string; title: string }[];
  specification: { electrical: { voltage: number; logicLevel: number; communicationProtocol: string }; notes: string };
}
export interface ProjectSummary { id: string; name: string; boardId: string; componentIds: string[]; revision: number; updatedAt: string }
export interface CreateProject { name: string; boardId: string; code?: string; componentIds?: string[] }
/** Current API identifiers, verified against the official DeepSeek pricing page. */
export const DEFAULT_AI_MODEL = 'deepseek-flash';
export const DEEPSEEK_MODELS = [DEFAULT_AI_MODEL, 'deepseek-v4-pro'] as const;
export interface AiSettings { aiConfigured: boolean; aiModel: string; aiBaseUrl?: string }
/** null/omitted key preserves the saved key; empty string explicitly clears it. */
export interface SaveAiSettings { apiKey?: string | null; model: string; baseUrl?: string }
export interface FirmwareProfile { boardId: string; chip: 'ESP32' | 'ESP32-S3' | 'ESP32-C3'; offset: number; documentation: string }
export type AiCheckId = 'network' | 'key' | 'model' | 'balance' | 'generation';
export interface AiDiagnosticCheck {
  id: AiCheckId; label: string; status: 'running' | 'passed' | 'failed' | 'warning' | 'skipped';
  detail: string; elapsedMs?: number; firstTokenMs?: number; keepAlives?: number;
}
export interface AiDiagnosticReport { model: string; checkedAt: string; healthy: boolean; checks: AiDiagnosticCheck[]; suggestion: string }
/** Testing uses the form's values without saving them or submitting a project. */
export type AiDiagnosticEvent = { type: 'check'; check: AiDiagnosticCheck }
  | { type: 'done'; report: AiDiagnosticReport } | { type: 'error'; detail: string };
export interface Project extends ProjectSummary { code: string; checksum: string; messages: ChatMessage[] }
export interface ChatMessage { id: string; role: 'user' | 'assistant'; content: string; status: string; boardId?: string; createdAt?: string }
export interface ChatInput { message: string; code: string; boardId: string; componentIds: string[] }
/** Text-only model output; complete code remains a candidate, never a device action. */
export interface AssistantReply {
  summary: string; points: string[];
  question: { text: string; options: string[] } | null;
  details: string; code: string | null;
}
/** POST chat with Accept: application/x-ndjson. Only done contains a saved, complete answer. */
export type ChatEvent =
  | { type: 'status'; phase: 'waiting' }
  | { type: 'heartbeat' }
  | { type: 'delta'; content: string }
  | { type: 'done'; messages: ChatMessage[] }
  | { type: 'error'; detail: string };
export interface Version { revision: number; code: string; checksum: string; createdAt: string; source?: 'saved' | 'ai'; boardId?: string; messageId?: string }
/** Portable checkpoint of the original SQLite project, never includes API settings. */
export interface ProjectSnapshot {
  format: 'zhangwen-project'; schemaVersion: 1; portableId: string;
  project: { name: string; boardId: string; componentIds: string[]; revision: number };
  versions: Version[]; messages: ChatMessage[];
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
  diagnostics: { severity: 'PASS' | 'WARNING' | 'FAIL'; message: string; line?: number | null }[];
}
export interface UploadManifest {
  projectId: string; revision: number; boardId: string; hardwareRevisions: Record<string, string>;
  files: { path: 'main.py'; content: string; sha256: string; size: number }[];
}
export type DeviceState = 'disconnected' | 'connecting' | 'connected' | 'busy' | 'running' | 'attention';
export interface DeviceIdentity { implementation: string; machine: string; platform: string; uniqueId: string }
/** Read-only root listing; device writes remain limited to upload-manifest main.py. */
export interface DeviceFile { path: string; size: number; directory: boolean }
export interface DeviceFileContent { path: string; bytes: Uint8Array; sha256: string }
export interface UploadReceipt {
  projectId: string; revision: number; sha256: string; identity: DeviceIdentity;
  backupPath: string | null; verifiedAt: string;
}
