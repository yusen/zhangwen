import type { DeviceIdentity, UploadManifest, LuaCodingCheckpoint, ChatCodingState } from './platform';

/** Historical data only. Live device connections are never restored from a snapshot. */
export interface ChannelMosaicoState {
  lua: LuaCodingCheckpoint;
  claw: Pick<ChatCodingState, 'schemaVersion' | 'records'>;
  clawRevision: number;
  source: 'local' | 'device';
  backups: { id: string; path: string; exists: boolean; content: string; sha256: string | null; operation: string; createdAt: string }[];
}

export interface ControllerCheck {
  id: string; label: string; status: 'passed' | 'failed' | 'unavailable'; detail: string;
}
export interface ControllerSelfTest {
  connectionId?: string;
  boardId: string; identity: DeviceIdentity; checkedAt: string; checks: ControllerCheck[];
  observed: 'unconfirmed' | 'passed' | 'failed'; note: string;
}
export interface ChannelVersion {
  revision: number; code: string; checksum: string; createdAt: string;
  boardId?: string; componentIds?: string[];
  programmingMode?: 'chat-coding';
}
export interface ChannelMessage { role: 'user' | 'assistant'; content: string; status: 'COMPLETED'; createdAt: string; boardId?: string; componentIds?: string[]; intent?: 'integration' | 'lua-coding'; integrationModuleId?: string }
export interface DevelopmentChannel {
  id: string; name: string; boardId: string; componentIds: string[];
  hardwareRevisions: Record<string, string>; revision: number;
  versions: ChannelVersion[]; messages: ChannelMessage[];
  mosaico?: ChannelMosaicoState | null;
}
/** Original main channel remains in Project; these are additional controller channels. */
export interface ChannelsCheckpoint { schemaVersion: 1; revision: number; mainName?: string; channels: DevelopmentChannel[] }
export interface ChannelSave { expectedRevision: number; name: string; boardId: string; componentIds: string[]; code: string }
export interface ChannelManifest extends UploadManifest { channelId: string }
