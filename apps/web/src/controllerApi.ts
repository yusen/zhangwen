import { api, chat } from './api';

export interface MosaicoScope {
  client: typeof api;
  generateChat: typeof chat;
  key: string;
}

/** Bind all Mosaico requests, including polling, to one real Project channel. */
export function mosaicoScope(projectId: string, channelId: string, revision: () => number): MosaicoScope {
  const prefix = `/projects/${projectId}/channels/${channelId}/runtime`;
  return {
    key: `${projectId}:${channelId}`,
    client: <T>(path: string, method?: string, body?: unknown, signal?: AbortSignal) => {
      if (!(path === `/projects/${projectId}` || path.startsWith(`/projects/${projectId}/`) || path === '/mosaico' || path.startsWith('/mosaico/'))) {
        return Promise.reject(new Error('请求不属于当前Mosaico主控。'));
      }
      return api<T>(prefix+path, method, body, signal);
    },
    generateChat: (id, input, signal, onEvent) => {
      if (id !== projectId) return Promise.reject(new Error('生成请求不属于当前主控。'));
      const request = {...input, expectedRevision:revision()};
      return chat(id, request, signal, onEvent, prefix+`/projects/${id}/chat`);
    },
  };
}
