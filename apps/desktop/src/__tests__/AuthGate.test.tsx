import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthGate } from "../components/auth/AuthGate";
import {
  apiGet,
  getAuthSessionToken,
  setAuthSessionToken,
} from "../services/api";

const account = {
  id: "account_1",
  username: "maker_01",
  displayName: "小掌",
  createdAt: "2026-07-15T00:00:00+00:00",
};

describe("AuthGate", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("邮箱注册验证成功后才挂载工作台并可退出", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/auth/status")) {
        return json({
          hasAccounts: false,
          hasLocalAccounts: false,
          cloudAuthConfigured: true,
        });
      }
      if (url.endsWith("/api/auth/register-email")) {
        return json({
          challengeId: "challenge_123456789",
          expiresAt: "2026-07-15T00:10:00+00:00",
          message: "验证码已发送。",
        }, 201);
      }
      if (url.endsWith("/api/auth/verify-email")) {
        return json({
          account: {
            id: "subject_1",
            email: "maker@example.com",
            displayName: "小掌",
            emailVerified: true,
            createdAt: "2026-07-15T00:00:00+00:00",
          },
          profile: {
            persona: "MAKER",
            technicalLevel: "BEGINNER",
            preferredBoards: ["K10"],
            budgetPreference: "BALANCED",
            needsLesson: false,
            completed: true,
          },
          sessionToken: "register-session-token-1234567890",
          expiresAt: "2026-08-14T00:00:00+00:00",
          offlineLeaseExpiresAt: "2026-08-14T00:00:00+00:00",
        });
      }
      if (url.endsWith("/api/auth/session")) {
        return json({ account, expiresAt: "2026-08-14T00:00:00+00:00" });
      }
      if (url.endsWith("/api/projects/legacy-claim/status")) {
        return json({ unclaimedProjectCount: 0, decisionRecorded: true });
      }
      if (url.endsWith("/api/auth/logout") && init?.method === "POST") {
        return json({ loggedOut: true });
      }
      return json({ detail: { code: "NOT_FOUND", message: url } }, 404);
    }));

    renderGate();

    expect(await screen.findByRole("heading", { name: "登录掌问" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "掌问 Logo" })).toHaveAttribute(
      "src",
      "/app-logo.png",
    );
    expect(screen.queryByTestId("protected-workspace")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "创建邮箱账号" }));
    expect(await screen.findByRole("heading", { name: "创建邮箱账号" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("邮箱"), { target: { value: "maker@example.com" } });
    fireEvent.change(screen.getByLabelText("显示名称"), { target: { value: "小掌" } });
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "MakerPass123" } });
    fireEvent.change(screen.getByLabelText("确认密码"), { target: { value: "MakerPass123" } });
    fireEvent.click(screen.getByRole("button", { name: "发送验证码" }));
    expect(await screen.findByRole("heading", { name: "验证邮箱" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("六位验证码"), { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: "验证并继续" }));

    expect(await screen.findByTestId("protected-workspace")).toHaveTextContent("小掌");
    expect(getAuthSessionToken()).toBe("register-session-token-1234567890");

    fireEvent.click(screen.getByRole("button", { name: "测试退出" }));
    expect(await screen.findByRole("heading", { name: "登录掌问" })).toBeInTheDocument();
    expect(getAuthSessionToken()).toBeNull();
  });

  it("已有账号登录失败显示统一错误，成功后恢复工作台", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/auth/status")) {
        return json({
          hasAccounts: true,
          hasLocalAccounts: false,
          cloudAuthConfigured: true,
        });
      }
      if (url.endsWith("/api/auth/login-email")) {
        const body = JSON.parse(String(init?.body)) as { password: string };
        if (body.password !== "MakerPass123") {
          return json({
            detail: { code: "AUTH_CREDENTIALS_INVALID", message: "邮箱或密码不正确。" },
          }, 401);
        }
        return json({
          account: {
            id: "subject_1",
            email: "maker@example.com",
            displayName: "小掌",
            emailVerified: true,
            createdAt: "2026-07-15T00:00:00+00:00",
          },
          profile: {
            persona: "MAKER",
            technicalLevel: "BEGINNER",
            preferredBoards: ["K10"],
            budgetPreference: "BALANCED",
            needsLesson: false,
            completed: true,
          },
          sessionToken: "login-session-token-1234567890",
          expiresAt: "2026-08-14T00:00:00+00:00",
          offlineLeaseExpiresAt: "2026-08-14T00:00:00+00:00",
        });
      }
      if (url.endsWith("/api/auth/session")) {
        return json({ account, expiresAt: "2026-08-14T00:00:00+00:00" });
      }
      if (url.endsWith("/api/projects/legacy-claim/status")) {
        return json({ unclaimedProjectCount: 0, decisionRecorded: true });
      }
      return json({ loggedOut: true });
    }));

    renderGate();
    expect(await screen.findByRole("heading", { name: "登录掌问" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("邮箱"), { target: { value: "maker@example.com" } });
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "WrongPass123" } });
    fireEvent.click(screen.getByRole("button", { name: "登录" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("邮箱或密码不正确");

    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "MakerPass123" } });
    fireEvent.click(screen.getByRole("button", { name: "登录" }));
    expect(await screen.findByTestId("protected-workspace")).toHaveTextContent("maker_01");
  });

  it("云认证未配置时自动恢复本机账号登录并保留原账号", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/auth/status")) {
        return json({
          hasAccounts: true,
          hasLocalAccounts: true,
          cloudAuthConfigured: false,
        });
      }
      if (url.endsWith("/api/auth/login") && init?.method === "POST") {
        expect(JSON.parse(String(init.body))).toEqual({
          username: "local-maker",
          password: "RecoveredPass123",
        });
        return json({
          account: {
            ...account,
            username: "local-maker",
            displayName: "Test Maker",
          },
          sessionToken: "local-session-token-1234567890",
          expiresAt: "2026-08-27T00:00:00+00:00",
        });
      }
      if (url.endsWith("/api/projects/legacy-claim/status")) {
        return json({ unclaimedProjectCount: 0, decisionRecorded: true });
      }
      return json({ detail: { code: "NOT_FOUND", message: url } }, 404);
    }));

    renderGate();
    expect(await screen.findByRole("heading", { name: "本机账号登录" })).toBeInTheDocument();
    expect(screen.queryByLabelText("邮箱")).not.toBeInTheDocument();
    expect(screen.getByText(/邮箱服务尚未配置/)).toBeInTheDocument();
    expect(screen.getByText(/重置本机密码/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("本机账号"), { target: { value: "local-maker" } });
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "RecoveredPass123" } });
    fireEvent.click(screen.getByRole("button", { name: "登录本机账号" }));

    expect(await screen.findByTestId("protected-workspace")).toHaveTextContent("Test Maker local-maker");
    expect(getAuthSessionToken()).toBe("local-session-token-1234567890");
  });

  it("旧会话失效时仍按服务能力回到本机账号登录", async () => {
    setAuthSessionToken("expired-local-session-token-1234567890");
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/auth/status")) {
        return json({
          hasAccounts: true,
          hasLocalAccounts: true,
          cloudAuthConfigured: false,
        });
      }
      if (url.endsWith("/api/auth/session")) {
        return json({
          detail: { code: "AUTH_SESSION_INVALID", message: "登录已失效。" },
        }, 401);
      }
      return json({ detail: { code: "NOT_FOUND", message: url } }, 404);
    }));

    renderGate();

    expect(await screen.findByRole("heading", { name: "本机账号登录" })).toBeInTheDocument();
    expect(screen.getByLabelText("本机账号")).toBeInTheDocument();
    expect(screen.queryByLabelText("邮箱")).not.toBeInTheDocument();
    expect(getAuthSessionToken()).toBeNull();
  });

  it("持久 token 可恢复会话，后续业务 401 会卸载工作台", async () => {
    setAuthSessionToken("persisted-session-token-1234567890");
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/auth/status")) {
        return json({
          hasAccounts: true,
          hasLocalAccounts: false,
          cloudAuthConfigured: true,
        });
      }
      if (url.endsWith("/api/auth/session")) {
        return json({ account, expiresAt: "2026-08-14T00:00:00+00:00" });
      }
      if (url.endsWith("/api/projects/legacy-claim/status")) {
        return json({ unclaimedProjectCount: 0, decisionRecorded: true });
      }
      if (url.endsWith("/api/projects")) {
        return json({ detail: { code: "AUTH_SESSION_INVALID", message: "登录已失效。" } }, 401);
      }
      return json({ loggedOut: true });
    }));

    renderGate();
    expect(await screen.findByTestId("protected-workspace")).toBeInTheDocument();

    await act(async () => {
      await expect(apiGet("/api/projects")).rejects.toThrow("登录已失效");
    });
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "登录掌问" })).toBeInTheDocument();
    });
    expect(screen.queryByTestId("protected-workspace")).not.toBeInTheDocument();
    expect(getAuthSessionToken()).toBeNull();
  });

  it("首次登录只向当前账号展示一次旧项目认领页", async () => {
    setAuthSessionToken("persisted-session-token-1234567890");
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/auth/status")) {
        return json({
          hasAccounts: true,
          hasLocalAccounts: false,
          cloudAuthConfigured: true,
        });
      }
      if (url.endsWith("/api/auth/session")) {
        return json({ account, expiresAt: "2026-08-14T00:00:00+00:00" });
      }
      if (url.endsWith("/api/projects/legacy-claim/status")) {
        return json({ unclaimedProjectCount: 2, decisionRecorded: false });
      }
      if (url.endsWith("/api/projects/legacy-claim") && init?.method === "POST") {
        expect(JSON.parse(String(init.body))).toEqual({ claimAll: true });
        return json({ claimedProjectCount: 2, decisionRecorded: true });
      }
      return json({ detail: { code: "NOT_FOUND", message: url } }, 404);
    }));

    renderGate();
    expect(await screen.findByRole("heading", { name: "认领这台设备上的旧项目" })).toBeInTheDocument();
    expect(screen.getByText(/2 个升级前创建的项目/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "认领全部旧项目" }));
    expect(await screen.findByTestId("protected-workspace")).toBeInTheDocument();
  });
});

function renderGate() {
  render(
    <AuthGate>
      {({ account: currentAccount, logout }) => (
        <div data-testid="protected-workspace">
          {currentAccount.displayName} {currentAccount.username}
          <button type="button" onClick={() => void logout()}>测试退出</button>
        </div>
      )}
    </AuthGate>,
  );
}

function json(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}
