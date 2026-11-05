import type { Project } from '../../../packages/contracts/src/platform';

export interface ProjectContent { name: string; boardId: string; code: string; componentIds: string[] }
export interface ProjectDraft {
  name: string; board: string; code: string; components: string[]; baseRevision: number;
  base?: ProjectContent;
}
export const projectContent = (value: ProjectContent): ProjectContent => ({
  name: value.name, boardId: value.boardId, code: value.code, componentIds: [...value.componentIds],
});
export const sameProjectContent = (a: ProjectContent, b: ProjectContent) => a.name === b.name && a.boardId === b.boardId
  && a.code === b.code && JSON.stringify(a.componentIds) === JSON.stringify(b.componentIds);

function isContent(value: unknown): value is ProjectContent {
  if (!value || typeof value !== 'object') return false;
  const v = value as Partial<ProjectContent>;
  return typeof v.name === 'string' && typeof v.boardId === 'string' && typeof v.code === 'string'
    && Array.isArray(v.componentIds) && v.componentIds.every(id => typeof id === 'string');
}
export function readProjectDraft(raw: string | null, saved: Project): ProjectDraft | null {
  try {
    const v = JSON.parse(raw ?? 'null') as Partial<ProjectDraft> | null;
    if (!v || typeof v.code !== 'string' || typeof v.name !== 'string' || typeof v.board !== 'string'
        || !Array.isArray(v.components) || !v.components.every(id => typeof id === 'string')
        || !Number.isInteger(v.baseRevision) || v.baseRevision! < 1) return null;
    // An identical browser checkpoint is not an unsaved edit. In particular its
    // old revision must not become the base for the next hardware selection.
    if (sameProjectContent(saved, { name: v.name, boardId: v.board, code: v.code, componentIds: v.components })) return null;
    return { name: v.name, board: v.board, code: v.code, components: v.components, baseRevision: v.baseRevision!,
      ...(isContent(v.base) ? { base: projectContent(v.base) } : {}) };
  } catch { return null; }
}

export function canSaveProject(latest: Project, requested: ProjectContent, expectedRevision: number, base: ProjectContent | null) {
  // Only reconcile a stale revision when the current content is exactly the
  // intended result or its known base. Never rebase an unknown legacy draft.
  return latest.revision === expectedRevision || sameProjectContent(latest, requested)
    || (base !== null && sameProjectContent(latest, base));
}
