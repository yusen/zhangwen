import type { ChatMessage } from '../../../packages/contracts/src/platform';

export const integrationScope = (projectId: string | undefined, boardId: string, componentIds: string[]) => JSON.stringify([projectId ?? 'scratch', boardId, [...componentIds].sort()]);

/** Resume only the most recent user intent in this exact hardware selection. */
export function integrationSession(messages: ChatMessage[], boardId: string, componentIds: string[]) {
  if (!componentIds.length) return null;
  const ids = new Set(componentIds);
  const latest = [...messages].reverse().find(m => m.role === 'user' && m.boardId === boardId && m.componentIds?.length === ids.size && m.componentIds.every(id => ids.has(id)));
  if (latest?.intent !== 'integration') return null;
  const targetId = latest.integrationModuleId && ids.has(latest.integrationModuleId) ? latest.integrationModuleId : componentIds[0];
  const index = componentIds.indexOf(targetId);
  return { targetId, index, total: componentIds.length, nextId: componentIds[index + 1] ?? null };
}
