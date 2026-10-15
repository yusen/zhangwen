import type { ChatEvent, ChatInput, ChatMessage } from '../../../packages/contracts/src/mu';

let token = '';
export async function bootstrap(): Promise<{ aiConfigured: boolean; aiModel: string }> {
  const response = await fetch('/api/session');
  if (!response.ok) throw new Error('无法连接本机服务，请检查启动窗口。');
  const result = await response.json() as { token: string; aiConfigured: boolean; aiModel: string };
  token = result.token;
  return result;
}
export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch('/api' + path, {
    method, headers: { 'Content-Type': 'application/json', 'X-Mu-Session': token },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const result: unknown = await response.json();
  if (!response.ok) {
    const detail = (result as { detail?: unknown }).detail;
    throw new Error(typeof detail === 'string' ? detail : `请求失败（${response.status}），请核对输入和服务端状态。`);
  }
  return result as T;
}

export async function chat(projectId: string, input: ChatInput, signal: AbortSignal,
  onEvent: (event: ChatEvent) => void): Promise<{ messages: ChatMessage[] }> {
  const response = await fetch(`/api/projects/${projectId}/chat`, {
    method: 'POST', signal,
    headers: { 'Content-Type': 'application/json', 'X-Mu-Session': token, Accept: 'application/x-ndjson' },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    const result = await response.json() as { detail?: string };
    throw new Error(result.detail ?? `AI 请求失败（${response.status}）。`);
  }
  // Compatibility with a service still running the earlier JSON endpoint.
  if (response.headers.get('content-type')?.includes('application/json')) return response.json() as Promise<{ messages: ChatMessage[] }>;
  if (!response.body) throw new Error('无法读取 AI 回答。输入已保留，请刷新页面后重试。');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let pending = '';
  try {
    while (true) {
      const { value, done } = await reader.read();
      pending += decoder.decode(value, { stream: !done });
      let newline: number;
      while ((newline = pending.indexOf('\n')) >= 0) {
        const line = pending.slice(0, newline); pending = pending.slice(newline + 1);
        if (!line.trim()) continue;
        const event = JSON.parse(line) as ChatEvent;
        if (event.type === 'error') throw new Error(event.detail);
        onEvent(event);
        if (event.type === 'done') return { messages: event.messages };
      }
      if (done) throw new Error('AI 连接中断，回答尚未完整返回。输入已保留，代码未修改。');
    }
  } finally { await reader.cancel().catch(() => {}); reader.releaseLock(); }
}
