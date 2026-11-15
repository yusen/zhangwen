import type { LuaCodingCheckpoint, LuaManifest } from '../../../packages/contracts/src/platform';

type Request = <T>(path: string, method?: string, body?: Record<string, unknown>) => Promise<T>;

// One explicit user action, using the existing fixed upload and run endpoints.
// Any failed/unknown step stops the chain; submission is never retried.
export async function uploadAndRunLua(request: Request, options: {
  projectId: string; revision: number; checksum: string; connectionId: string; timeoutMs: number;
  progress: (text: string) => void;
}): Promise<LuaCodingCheckpoint> {
  const { projectId, revision, checksum, connectionId, timeoutMs, progress } = options;
  progress('正在检查设备文件…');
  const manifest = await request<LuaManifest>(`/mosaico/lua-manifest?projectId=${projectId}&revision=${revision}`);
  if (manifest.connectionId !== connectionId || manifest.projectId !== projectId || manifest.revision !== revision || manifest.checksum !== checksum)
    throw new Error('设备或保存版本已改变，请重新操作。');
  if (manifest.expectedChecksum !== checksum) {
    progress('正在备份、上传并校验…');
    await request('/mosaico/lua-upload', 'POST', {
      projectId, revision, checksum, expectedChecksum: manifest.expectedChecksum, connectionId,
      requestId: crypto.randomUUID().replaceAll('-', ''),
    });
  }
  progress('正在提交运行…');
  return request<LuaCodingCheckpoint>(`/projects/${projectId}/lua-coding/wifi-run`, 'POST', {
    revision, timeoutMs, connectionId, requestId: crypto.randomUUID().replaceAll('-', ''),
  });
}
