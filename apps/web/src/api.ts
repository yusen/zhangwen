import type { AiDiagnosticEvent, AiDiagnosticReport, ChatEvent, ChatInput, ChatMessage, SaveAiSettings } from '../../../packages/contracts/src/mu';

let token = '';
export async function bootstrap(signal?: AbortSignal): Promise<{ aiConfigured: boolean; aiModel: string; aiBaseUrl?: string }> {
  const response = await fetch('/api/session', { signal });
  if (!response.ok) throw new Error('无法连接本机服务，请检查启动窗口。');
  const result = await response.json() as { token: string; aiConfigured: boolean; aiModel: string; aiBaseUrl?: string };
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
  const event = await readEvents<ChatEvent>(response, onEvent, 'AI 连接中断，回答尚未完整返回。输入已保留，代码未修改。');
  if (event.type !== 'done') throw new Error('AI 回答未完成。');
  return { messages: event.messages };
}

export async function testAiSettings(input: SaveAiSettings, signal: AbortSignal,
  onEvent: (event: AiDiagnosticEvent) => void): Promise<AiDiagnosticReport> {
  const response = await fetch('/api/settings/ai/test', {
    method: 'POST', signal,
    headers: { 'Content-Type': 'application/json', 'X-Mu-Session': token, Accept: 'application/x-ndjson' },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    const result = await response.json() as { detail?: string };
    throw new Error(result.detail ?? `检测失败（${response.status}）。`);
  }
  const event = await readEvents<AiDiagnosticEvent>(response, onEvent, '检测连接中断，请重新测试。');
  if (event.type !== 'done') throw new Error('检测尚未完成。');
  return event.report;
}

async function readEvents<T extends { type: string; detail?: string }>(response: Response, onEvent: (event: T) => void, incomplete: string): Promise<T> {
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
        const event = JSON.parse(line) as T;
        if (event.type === 'error') throw new Error(event.detail);
        onEvent(event);
        if (event.type === 'done') return event;
      }
      if (done) throw new Error(incomplete);
    }
  } finally { await reader.cancel().catch(() => {}); reader.releaseLock(); }
}
