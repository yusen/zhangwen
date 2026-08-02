const DEFAULT_API_BASE_URL = "http://127.0.0.1:8100";
const DEFAULT_TIMEOUT_MS = 30_000;
import { detectHost } from "../platform/capabilities";
import { getActiveBridgeLease } from "../platform/bridgeLease";

let desktopCapabilityTokenPromise: Promise<string | null> | null = null;
const AUTH_SESSION_STORAGE_KEY = "zhangwen.auth.session-token.v1";
export const AUTH_SESSION_EXPIRED_EVENT = "zhangwen:auth-session-expired";

export class ApiError extends Error {
  readonly status: number | null;
  readonly code: string | null;

  constructor(message: string, status: number | null = null, code: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export function getApiBaseUrl(): string {
  const configured = import.meta.env.VITE_ZHANGWEN_API_BASE_URL?.trim();
  return (configured || DEFAULT_API_BASE_URL).replace(/\/+$/, "");
}

export async function apiGet<T>(
  path: string,
  signal?: AbortSignal,
  timeoutMs = DEFAULT_TIMEOUT_MS
): Promise<T> {
  return apiRequest<T>(path, { method: "GET", signal }, timeoutMs);
}

export async function apiPut<TRequest, TResponse>(
  path: string,
  body: TRequest,
  signal?: AbortSignal
): Promise<TResponse> {
  return apiRequest<TResponse>(path, jsonRequest("PUT", body, signal));
}

export async function apiPost<TRequest, TResponse>(
  path: string,
  body: TRequest,
  signal?: AbortSignal
): Promise<TResponse> {
  return apiRequest<TResponse>(path, jsonRequest("POST", body, signal));
}

export async function apiPatch<TRequest, TResponse>(
  path: string,
  body: TRequest,
  signal?: AbortSignal
): Promise<TResponse> {
  return apiRequest<TResponse>(path, jsonRequest("PATCH", body, signal));
}

export async function apiDelete<TResponse>(
  path: string,
  signal?: AbortSignal
): Promise<TResponse> {
  return apiRequest<TResponse>(path, { method: "DELETE", signal });
}

export async function apiFetch(
  path: string,
  init: RequestInit = {},
  timeoutMs = DEFAULT_TIMEOUT_MS
): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = globalThis.setTimeout(() => controller.abort("timeout"), timeoutMs);
  const combinedSignal = combineAbortSignals(init.signal, controller.signal);
  const headers = new Headers(init.headers);
  const authToken = getAuthSessionToken();
  if (authToken) headers.set("Authorization", `Bearer ${authToken}`);
  const host = detectHost();
  headers.set("X-Zhangwen-Host", host);
  if (host === "tauri") {
    const token = await desktopCapabilityToken();
    if (token) headers.set("X-Zhangwen-Capability-Token", token);
  } else {
    const lease = getActiveBridgeLease();
    if (lease) {
      headers.set("X-Zhangwen-Bridge-Lease", lease.token);
      if (["POST", "PUT", "PATCH", "DELETE"].includes((init.method ?? "GET").toUpperCase())) {
        headers.set("X-Zhangwen-Bridge-Request-Id", bridgeRequestId());
      }
    }
  }
  try {
    const response = await fetch(apiUrl(path), {
      ...init,
      headers,
      signal: combinedSignal.signal,
    });
    if (response.status === 401) expireAuthSession(path);
    return response;
  } catch (error) {
    if (controller.signal.aborted && init.signal?.aborted !== true) {
      throw new ApiError("掌问本地服务请求超时，请重启应用后重试。", null, "TIMEOUT");
    }
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(
      "掌问本地服务未连接，请关闭应用后重新启动。",
      null,
      "SIDECAR_UNAVAILABLE"
    );
  } finally {
    globalThis.clearTimeout(timeoutId);
    combinedSignal.cleanup();
  }
}

function bridgeRequestId(): string {
  const generated = globalThis.crypto?.randomUUID?.();
  if (generated) return `bridge-request-${generated}`;
  return `bridge-request-${Date.now()}-${Math.random().toString(36).slice(2, 14)}`;
}

async function desktopCapabilityToken(): Promise<string | null> {
  desktopCapabilityTokenPromise ??= import("@tauri-apps/api/core")
    .then(({ invoke }) => invoke<string>("get_desktop_capability_token"))
    .then((token) => token.trim() || null)
    .catch(() => null);
  return desktopCapabilityTokenPromise;
}

export function apiUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${getApiBaseUrl()}${normalizedPath}`;
}

async function apiRequest<T>(
  path: string,
  init: RequestInit,
  timeoutMs = DEFAULT_TIMEOUT_MS
): Promise<T> {
  const response = await apiFetch(path, init, timeoutMs);
  if (!response.ok) throw await apiResponseError(path, response);
  return response.json() as Promise<T>;
}

export function getAuthSessionToken(): string | null {
  try {
    return globalThis.localStorage?.getItem(AUTH_SESSION_STORAGE_KEY)?.trim() || null;
  } catch {
    return null;
  }
}

export function setAuthSessionToken(token: string): void {
  const normalized = token.trim();
  if (!normalized) {
    clearAuthSessionToken();
    return;
  }
  try {
    globalThis.localStorage?.setItem(AUTH_SESSION_STORAGE_KEY, normalized);
  } catch {
    // The login still succeeds for the current render; a restart will require login again.
  }
}

export function clearAuthSessionToken(): void {
  try {
    globalThis.localStorage?.removeItem(AUTH_SESSION_STORAGE_KEY);
  } catch {
    // Storage may be unavailable in restricted browser contexts.
  }
}

function jsonRequest(method: string, body: unknown, signal?: AbortSignal): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  };
}

export async function apiResponseError(
  path: string,
  response: Response,
): Promise<ApiError> {
  let message = `API 请求失败: ${path} (HTTP ${response.status})`;
  let code: string | null = null;
  try {
    const body = (await response.json()) as {
      detail?: { code?: string; message?: string } | string;
    };
    if (typeof body.detail === "string") message = body.detail;
    if (body.detail && typeof body.detail === "object") {
      code = body.detail.code ?? null;
      message = body.detail.message ?? message;
    }
  } catch {
    // Keep the generic status-only error without exposing response internals.
  }
  return new ApiError(code ? `${code}: ${message}` : message, response.status, code);
}

function combineAbortSignals(
  external: AbortSignal | null | undefined,
  timeout: AbortSignal
): { signal: AbortSignal; cleanup: () => void } {
  const noCleanup = () => undefined;
  if (!external) return { signal: timeout, cleanup: noCleanup };
  if (typeof AbortSignal.any === "function") {
    return { signal: AbortSignal.any([external, timeout]), cleanup: noCleanup };
  }
  if (external.aborted) return { signal: external, cleanup: noCleanup };
  if (timeout.aborted) return { signal: timeout, cleanup: noCleanup };

  const controller = new AbortController();
  let listening = true;
  const cleanup = () => {
    if (!listening) return;
    listening = false;
    external.removeEventListener("abort", abortExternal);
    timeout.removeEventListener("abort", abortTimeout);
  };
  const abortFrom = (source: AbortSignal) => {
    cleanup();
    controller.abort(source.reason);
  };
  const abortExternal = () => abortFrom(external);
  const abortTimeout = () => abortFrom(timeout);
  external.addEventListener("abort", abortExternal, { once: true });
  timeout.addEventListener("abort", abortTimeout, { once: true });
  return { signal: controller.signal, cleanup };
}

function isCredentialSubmission(path: string): boolean {
  return path.endsWith("/api/auth/login") || path.endsWith("/api/auth/register");
}

function expireAuthSession(path: string): void {
  if (isCredentialSubmission(path)) return;
  clearAuthSessionToken();
  globalThis.dispatchEvent?.(new Event(AUTH_SESSION_EXPIRED_EVENT));
}
