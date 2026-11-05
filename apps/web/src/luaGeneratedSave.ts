import type { LuaCodingCheckpoint } from '../../../packages/contracts/src/platform';

type Request = <T>(path: string, method?: string, body?: unknown) => Promise<T>;

/** The user's generate action also saves locally. This never contacts a device. */
export async function saveGeneratedLua(request: Request, projectId: string, baseline: LuaCodingCheckpoint,
  latest: LuaCodingCheckpoint, code: string): Promise<LuaCodingCheckpoint> {
  if (latest.accepted !== baseline.accepted) throw new Error('其他页面已保存新的Lua。生成代码已保留为生成稿，未覆盖当前版本。');
  const accepted = latest.versions.find(v => v.revision === latest.accepted);
  if (accepted?.code === code) return latest;
  // One attempt with the original concurrency guard. A lost response or 409
  // remains visible; generation and saving are never retried automatically.
  return request<LuaCodingCheckpoint>(`/projects/${projectId}/lua-coding/save`, 'POST', { expectedRevision: latest.revision, code });
}
