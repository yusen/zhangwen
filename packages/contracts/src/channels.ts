import type { DeviceIdentity, UploadManifest } from './platform';

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
}
export interface ChannelMessage { role: 'user' | 'assistant'; content: string; status: 'COMPLETED'; createdAt: string; boardId?: string; componentIds?: string[]; intent?: 'integration'; integrationModuleId?: string }
export interface DevelopmentChannel {
  id: string; name: string; boardId: string; componentIds: string[];
  hardwareRevisions: Record<string, string>; revision: number;
  versions: ChannelVersion[]; messages: ChannelMessage[];
}
/** Original main channel remains in Project; these are additional controller channels. */
export interface ChannelsCheckpoint { schemaVersion: 1; revision: number; channels: DevelopmentChannel[] }
export interface ChannelSave { expectedRevision: number; name: string; boardId: string; componentIds: string[]; code: string }
export interface ChannelManifest extends UploadManifest { channelId: string }
