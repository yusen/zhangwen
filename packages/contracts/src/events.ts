/**
 * 掌问共享契约 — 事件类型定义
 * WebSocket 推送的统一事件结构。
 */

/** 事件类型枚举 */
export const EventType = {
  CHAT_STARTED: "chat.started",
  CHAT_DELTA: "chat.delta",
  CHAT_COMPLETED: "chat.completed",
  CHAT_ERROR: "chat.error",
  CHAT_CANCELED: "chat.canceled",
  PROJECT_CREATED: "project.created",
  PROJECT_UPDATED: "project.updated",
  PROJECT_ARCHIVED: "project.archived",
  PROJECT_OPENED: "project.opened",
  CONVERSATION_MESSAGE_CREATED: "conversation.message.created",
  CONVERSATION_MESSAGE_UPDATED: "conversation.message.updated",
  DRAFT_UPDATED: "draft.updated",
  PROJECT_STAGE_CHANGED: "project.stage.changed",
  AGENT_STATUS_CHANGED: "agent.status.changed",
  TASK_PROGRESS: "task.progress",
  TASK_APPROVAL_REQUIRED: "task.approval.required",
  ARTIFACT_CREATED: "artifact.created",
  ARTIFACT_UPDATED: "artifact.updated",
  DEVICE_DISCOVERED: "device.discovered",
  DEVICE_LOG: "device.log",
  DEVICE_UPLOAD_PROGRESS: "device.upload.progress",
  DEVICE_ERROR: "device.error",
  SECURITY_WARNING: "security.warning",
} as const;
export type EventType = (typeof EventType)[keyof typeof EventType];

/** 统一事件结构 */
export interface ZwEvent {
  eventId: string;
  projectId: string;
  type: EventType;
  timestamp: string;
  payload: Record<string, unknown>;
}
