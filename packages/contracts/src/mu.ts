/** Mu Web boundary. Validated on the server by zhangwen.mu_web.models. */
export interface HardwareMedia { path: string; alt: string; url: string; attribution: string; license: string; sourceUrl: string }
export interface HardwareSummary {
  skillName: string; componentId: string; displayName: string; description: string;
  category: 'MCU' | 'SENSOR' | 'ACTUATOR' | 'DISPLAY' | 'POWER' | 'STRUCTURE';
  status: string; revision: string; verificationStatus: string; media: HardwareMedia[];
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
export interface AiSettings { aiConfigured: boolean; aiModel: string }
/** null/omitted key preserves the saved key; empty string explicitly clears it. */
export interface SaveAiSettings { apiKey?: string | null; model: string }
export interface Project extends ProjectSummary { code: string; checksum: string; messages: ChatMessage[] }
export interface ChatMessage { id: string; role: 'user' | 'assistant'; content: string; status: string }
export interface Version { revision: number; code: string; checksum: string; createdAt: string }
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
