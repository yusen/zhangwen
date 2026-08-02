import type {
  CancelChatResponse,
  ChatRequest,
  ConnectionTestRequest,
  ConnectionTestResult,
  LLMConfigResponse,
  ModelsResponse,
  SaveLLMConfigRequest,
  StreamChunk,
  PersistedChatRequest,
  ProjectStreamChunk,
} from "@zhangwen/contracts";
import { ApiError, apiDelete, apiFetch, apiGet, apiPost, apiPut } from "./api";

export function getLlmConfig(): Promise<LLMConfigResponse> {
  return apiGet<LLMConfigResponse>("/api/settings/llm");
}

export function saveLlmConfig(
  request: SaveLLMConfigRequest
): Promise<LLMConfigResponse> {
  return apiPut<SaveLLMConfigRequest, LLMConfigResponse>(
    "/api/settings/llm",
    request
  );
}

export function clearLlmApiKey(): Promise<LLMConfigResponse> {
  return apiDelete<LLMConfigResponse>("/api/settings/llm/api-key");
}

export function testLlmConnection(
  request: ConnectionTestRequest
): Promise<ConnectionTestResult> {
  return apiPost<ConnectionTestRequest, ConnectionTestResult>(
    "/api/settings/llm/test",
    request
  );
}

export function getLlmModels(): Promise<ModelsResponse> {
  return apiGet<ModelsResponse>("/api/llm/models");
}

export function cancelChat(requestId: string): Promise<CancelChatResponse> {
  return apiPost<Record<string, never>, CancelChatResponse>(
    `/api/chat/cancel/${requestId}`,
    {}
  );
}

export function cancelProjectChat(
  projectId: string,
  requestId: string
): Promise<CancelChatResponse> {
  return apiPost<Record<string, never>, CancelChatResponse>(
    `/api/projects/${projectId}/chat/cancel/${requestId}`,
    {}
  );
}

interface StreamChatOptions {
  request: ChatRequest;
  signal: AbortSignal;
  onChunk: (chunk: StreamChunk) => void;
}

export async function streamChat({
  request,
  signal,
  onChunk,
}: StreamChatOptions): Promise<void> {
  const response = await apiFetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new ApiError("本地后端未返回可读取的对话流。", response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const cancelReader = () => void reader.cancel().catch(() => undefined);
  signal.addEventListener("abort", cancelReader, { once: true });

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const events = buffer.split("\n\n");
      buffer = events.pop() ?? "";
      for (const event of events) {
        const dataLine = event
          .split("\n")
          .find((line) => line.startsWith("data:"));
        if (!dataLine) continue;
        onChunk(JSON.parse(dataLine.slice(5).trim()) as StreamChunk);
      }
    }
  } finally {
    signal.removeEventListener("abort", cancelReader);
  }
}

interface StreamProjectChatOptions {
  projectId: string;
  request: PersistedChatRequest;
  signal: AbortSignal;
  onChunk: (chunk: ProjectStreamChunk) => void;
}

export async function streamProjectChat({
  projectId,
  request,
  signal,
  onChunk,
}: StreamProjectChatOptions): Promise<void> {
  const response = await apiFetch(`/api/projects/${projectId}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new ApiError("本地后端未返回可读取的项目对话流。", response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const cancelReader = () => void reader.cancel().catch(() => undefined);
  signal.addEventListener("abort", cancelReader, { once: true });

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const events = buffer.split("\n\n");
      buffer = events.pop() ?? "";
      for (const event of events) {
        const dataLine = event
          .split("\n")
          .find((line) => line.startsWith("data:"));
        if (!dataLine) continue;
        onChunk(JSON.parse(dataLine.slice(5).trim()) as ProjectStreamChunk);
      }
    }
  } finally {
    signal.removeEventListener("abort", cancelReader);
  }
}

interface StreamPendingItemResolutionOptions {
  projectId: string;
  pendingItemId: string;
  signal: AbortSignal;
  onChunk: (chunk: ProjectStreamChunk) => void;
}

export async function streamPendingItemResolution({
  projectId,
  pendingItemId,
  signal,
  onChunk,
}: StreamPendingItemResolutionOptions): Promise<void> {
  const response = await apiFetch(
    `/api/projects/${projectId}/pending-items/${pendingItemId}/resolve/stream`,
    {
      method: "POST",
      signal,
    }
  );

  if (!response.ok) {
    throw await streamResponseError(
      response,
      "本地服务拒绝了这次执行授权，请重新发起操作。",
    );
  }
  if (!response.body) {
    throw new ApiError("本地服务未返回可读取的执行进度流。", response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const cancelReader = () => void reader.cancel().catch(() => undefined);
  signal.addEventListener("abort", cancelReader, { once: true });

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const events = buffer.split("\n\n");
      buffer = events.pop() ?? "";
      for (const event of events) {
        const dataLine = event
          .split("\n")
          .find((line) => line.startsWith("data:"));
        if (!dataLine) continue;
        onChunk(JSON.parse(dataLine.slice(5).trim()) as ProjectStreamChunk);
      }
    }
  } finally {
    signal.removeEventListener("abort", cancelReader);
  }
}

async function streamResponseError(
  response: Response,
  fallbackMessage: string,
): Promise<ApiError> {
  let message = fallbackMessage;
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
    // Keep the fixed user-safe fallback when the response is not structured JSON.
  }
  return new ApiError(message, response.status, code);
}
