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
