import { afterEach, describe, expect, it, vi } from "vitest";
import {
  AUTH_SESSION_EXPIRED_EVENT,
  apiFetch,
  apiGet,
  apiPost,
  apiUrl,
  clearAuthSessionToken,
  getApiBaseUrl,
  getAuthSessionToken,
  setAuthSessionToken,
} from "../services/api";
import { clearActiveBridgeLease, setActiveBridgeLease } from "../platform";

vi.mock("@tauri-apps/api/core", () => ({
  invoke: vi.fn(async () => "desktop-capability-test-token"),
}));

afterEach(() => {
  clearActiveBridgeLease(false);
  clearAuthSessionToken();
  vi.unstubAllGlobals();
});

describe("Browser/Tauri 共用 API Client", () => {
  it("默认使用统一 FastAPI Base URL", () => {
    expect(getApiBaseUrl()).toBe("http://127.0.0.1:8100");
    expect(apiUrl("/api/health")).toBe("http://127.0.0.1:8100/api/health");
  });

  it("Tauri Host 的 REST 请求使用同一接口且不添加 Provider Key", async () => {
    const fetchMock = vi.fn(
      async (_input: RequestInfo | URL, _init?: RequestInit) => json({ ok: true })
    );
    vi.stubGlobal("fetch", fetchMock);

    await apiGet("/api/health");
    await apiPost("/api/projects", { initialIdea: "Web API Client" });

    for (const [, init] of fetchMock.mock.calls) {
      const headers = new Headers(init?.headers);
      expect(headers.get("X-Zhangwen-Host")).toBe("tauri");
      expect(headers.get("X-Zhangwen-Capability-Token")).toBe(
        "desktop-capability-test-token",
      );
      expect(headers.has("Authorization")).toBe(false);
      expect(JSON.stringify(init ?? {})).not.toContain("apiKey");
    }
  });

  it("Web Host 的 REST 请求仍使用同一接口并声明 web 宿主", async () => {
    Object.defineProperty(window, "__TAURI_INTERNALS__", {
      configurable: true,
      value: undefined,
    });
    const fetchMock = vi.fn(
      async (_input: RequestInfo | URL, _init?: RequestInit) => json({ ok: true })
    );
    vi.stubGlobal("fetch", fetchMock);

    await apiGet("/api/health");

    const [, init] = fetchMock.mock.calls[0]!;
    expect(new Headers(init?.headers).get("X-Zhangwen-Host")).toBe("web");
    expect(
      new Headers(init?.headers).has("X-Zhangwen-Capability-Token"),
    ).toBe(false);
    expect(String(fetchMock.mock.calls[0]![0])).toBe(
      "http://127.0.0.1:8100/api/health"
    );
    Object.defineProperty(window, "__TAURI_INTERNALS__", {
      configurable: true,
      value: { test: true },
    });
  });

  it("Web+Bridge 为本地写操作附加短期 lease 和一次性 request id", async () => {
    Object.defineProperty(window, "__TAURI_INTERNALS__", {
      configurable: true,
      value: undefined,
    });
    setActiveBridgeLease({
      token: "bridge-test-token",
      id: "bridge-test",
      projectId: "project-test",
      origin: "http://localhost:5173",
      capabilities: ["device.upload"],
      expiresAt: new Date(Date.now() + 60_000).toISOString(),
    });
    const fetchMock = vi.fn(
      async (_input: RequestInfo | URL, _init?: RequestInit) => json({ ok: true }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await apiPost("/api/projects/project-test/devices/upload", { operationId: "op" });

    const headers = new Headers(fetchMock.mock.calls[0]?.[1]?.headers);
    expect(headers.get("X-Zhangwen-Host")).toBe("web");
    expect(headers.get("X-Zhangwen-Bridge-Lease")).toBe("bridge-test-token");
    expect(headers.get("X-Zhangwen-Bridge-Request-Id")).toMatch(/^bridge-request-/);
    expect(headers.has("X-Zhangwen-Capability-Token")).toBe(false);
    Object.defineProperty(window, "__TAURI_INTERNALS__", {
      configurable: true,
      value: { test: true },
    });
  });

  it("底层流式或二进制请求遇到 401 时统一清除会话并通知登录门禁", async () => {
    setAuthSessionToken("expired-session-token");
    const expired = vi.fn();
    globalThis.addEventListener(AUTH_SESSION_EXPIRED_EVENT, expired, { once: true });
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({ detail: { code: "AUTH_REQUIRED", message: "登录已失效" } }),
          { status: 401, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    const response = await apiFetch("/api/projects/project-1/chat/stream");

    expect(response.status).toBe(401);
    expect(getAuthSessionToken()).toBeNull();
    expect(expired).toHaveBeenCalledTimes(1);
  });

  it("兼容 AbortSignal.any 缺失且调用前已经取消的请求", async () => {
    const anyDescriptor = Object.getOwnPropertyDescriptor(AbortSignal, "any");
    Object.defineProperty(AbortSignal, "any", {
      configurable: true,
      value: undefined,
    });
    const controller = new AbortController();
    controller.abort("project-switched");
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.signal?.aborted) throw new DOMException("Aborted", "AbortError");
      return json({ ok: true });
    });
    vi.stubGlobal("fetch", fetchMock);

    try {
      await expect(apiFetch("/api/projects/project-1", { signal: controller.signal }))
        .rejects.toMatchObject({ name: "AbortError" });
      expect(fetchMock.mock.calls[0]?.[1]?.signal?.aborted).toBe(true);
    } finally {
      if (anyDescriptor) {
        Object.defineProperty(AbortSignal, "any", anyDescriptor);
      } else {
        Reflect.deleteProperty(AbortSignal, "any");
      }
    }
  });
});

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
}
