import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  AuthenticationStatus,
  BudgetPreference,
  TechnicalLevel,
  UserPersona,
  type AccountProfile,
  type AuthAccount,
  type AuthResultResponse,
  type EmailAuthResultResponse,
} from "@zhangwen/contracts";
import {
  AUTH_SESSION_EXPIRED_EVENT,
  clearAuthSessionToken,
  getAuthSessionToken,
  setAuthSessionToken,
} from "../../services/api";
import {
  confirmPasswordReset,
  getAuthSession,
  getAuthStatus,
  loginAccount,
  loginEmailAccount,
  logoutAccount,
  registerEmailAccount,
  requestPasswordReset,
  resendVerification,
  updateAccountProfile,
  verifyEmail,
} from "../../services/authApi";
import {
  decideLegacyProjectClaim,
  getLegacyProjectClaimStatus,
} from "../../services/projectsApi";
import { ProfileFields } from "./ProfileFields";

type AuthMode =
  | "login"
  | "local-login"
  | "register"
  | "verify"
  | "reset-request"
  | "reset-confirm"
  | "profile"
  | "legacy-claim";

interface AuthGateSession {
  account: AuthAccount;
  logout: () => Promise<void>;
}

interface AuthGateProps {
  children: (session: AuthGateSession) => ReactNode;
}

interface AuthViewState {
  status: (typeof AuthenticationStatus)[keyof typeof AuthenticationStatus];
  account: AuthAccount | null;
  mode: AuthMode;
  email: string;
  challengeId: string | null;
  unclaimedProjectCount: number;
  cloudAuthConfigured: boolean;
  localLoginAvailable: boolean;
  error: string | null;
}

const INITIAL_STATE: AuthViewState = {
  status: AuthenticationStatus.CHECKING,
  account: null,
  mode: "login",
  email: "",
  challengeId: null,
  unclaimedProjectCount: 0,
  cloudAuthConfigured: false,
  localLoginAvailable: false,
  error: null,
};

export function AuthGate({ children }: AuthGateProps) {
  const [state, setState] = useState<AuthViewState>(INITIAL_STATE);

  const completeAccountEntry = useCallback(async (account: AuthAccount, email: string) => {
    const claim = await getLegacyProjectClaimStatus();
    if (!claim.decisionRecorded && claim.unclaimedProjectCount > 0) {
      setState((current) => ({
        ...current,
        status: AuthenticationStatus.LEGACY_CLAIM_REQUIRED,
        account,
        mode: "legacy-claim",
        email,
        challengeId: null,
        unclaimedProjectCount: claim.unclaimedProjectCount,
        error: null,
      }));
      return;
    }
    setState((current) => ({
      ...current,
      status: AuthenticationStatus.AUTHENTICATED,
      account,
      mode: "login",
      email,
      challengeId: null,
      unclaimedProjectCount: 0,
      error: null,
    }));
  }, []);

  const enterWorkspace = useCallback(async (result: EmailAuthResultResponse) => {
    setAuthSessionToken(result.sessionToken);
    if (!result.profile.completed) {
      setState((current) => ({
        ...current,
        status: AuthenticationStatus.PROFILE_REQUIRED,
        account: {
          id: result.account.id,
          username: result.account.email,
          displayName: result.account.displayName,
          createdAt: result.account.createdAt,
        },
        mode: "profile",
        email: result.account.email,
        unclaimedProjectCount: 0,
        error: null,
      }));
      return;
    }
    const session = await getAuthSession();
    await completeAccountEntry(session.account, result.account.email);
  }, [completeAccountEntry]);

  const enterLocalWorkspace = useCallback(async (result: AuthResultResponse) => {
    setAuthSessionToken(result.sessionToken);
    await completeAccountEntry(result.account, "");
  }, [completeAccountEntry]);

  const bootstrap = useCallback(async () => {
    setState((current) => ({ ...current, status: AuthenticationStatus.CHECKING, error: null }));
    let cloudAuthConfigured = false;
    let localLoginAvailable = false;
    try {
      const authStatus = await getAuthStatus();
      localLoginAvailable = authStatus.hasLocalAccounts;
      cloudAuthConfigured = authStatus.cloudAuthConfigured;
      if (!getAuthSessionToken()) {
        setState({
          ...INITIAL_STATE,
          status: AuthenticationStatus.UNAUTHENTICATED,
          mode: !cloudAuthConfigured && localLoginAvailable ? "local-login" : "login",
          cloudAuthConfigured,
          localLoginAvailable,
        });
        return;
      }
      setState((current) => ({
        ...current,
        cloudAuthConfigured,
        localLoginAvailable,
      }));
      const session = await getAuthSession();
      await completeAccountEntry(
        session.account,
        session.account.username.includes("@") ? session.account.username : "",
      );
    } catch (error) {
      clearAuthSessionToken();
      setState({
        ...INITIAL_STATE,
        status: AuthenticationStatus.UNAUTHENTICATED,
        mode: !cloudAuthConfigured && localLoginAvailable ? "local-login" : "login",
        cloudAuthConfigured,
        localLoginAvailable,
        error: error instanceof Error ? error.message : "账号服务暂时不可用。",
      });
    }
  }, [completeAccountEntry]);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  useEffect(() => {
    const handleExpired = () => {
      clearAuthSessionToken();
      setState((current) => ({
        ...INITIAL_STATE,
        status: AuthenticationStatus.REAUTH_REQUIRED,
        mode: !current.cloudAuthConfigured && current.localLoginAvailable
          ? "local-login"
          : "login",
        email: current.email,
        cloudAuthConfigured: current.cloudAuthConfigured,
        localLoginAvailable: current.localLoginAvailable,
        error: "登录或离线使用期限已到，请重新登录。",
      }));
    };
    globalThis.addEventListener?.(AUTH_SESSION_EXPIRED_EVENT, handleExpired);
    return () => globalThis.removeEventListener?.(AUTH_SESSION_EXPIRED_EVENT, handleExpired);
  }, []);

  const logout = useCallback(async () => {
    try {
      await logoutAccount();
    } catch {
      // Leaving the local workspace must remain possible while offline.
    } finally {
      clearAuthSessionToken();
      setState((current) => ({
        ...INITIAL_STATE,
        status: AuthenticationStatus.UNAUTHENTICATED,
        mode: !current.cloudAuthConfigured && current.localLoginAvailable
          ? "local-login"
          : "login",
        cloudAuthConfigured: current.cloudAuthConfigured,
        localLoginAvailable: current.localLoginAvailable,
      }));
    }
  }, []);

  if (state.status === AuthenticationStatus.AUTHENTICATED && state.account) {
    return <>{children({ account: state.account, logout })}</>;
  }

  return (
    <AuthScreen
      state={state}
      onStateChange={setState}
      onEnterWorkspace={enterWorkspace}
      onEnterLocalWorkspace={enterLocalWorkspace}
      onCompleteAccountEntry={completeAccountEntry}
      onRetry={() => void bootstrap()}
    />
  );
}

function AuthScreen({
  state,
  onStateChange,
  onEnterWorkspace,
  onEnterLocalWorkspace,
  onCompleteAccountEntry,
  onRetry,
}: {
  state: AuthViewState;
  onStateChange: React.Dispatch<React.SetStateAction<AuthViewState>>;
  onEnterWorkspace: (result: EmailAuthResultResponse) => Promise<void>;
  onEnterLocalWorkspace: (result: AuthResultResponse) => Promise<void>;
  onCompleteAccountEntry: (account: AuthAccount, email: string) => Promise<void>;
  onRetry: () => void;
}) {
  const [email, setEmail] = useState(state.email);
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [code, setCode] = useState("");
  const [profile, setProfile] = useState<AccountProfile>({
    persona: UserPersona.MAKER,
    technicalLevel: TechnicalLevel.BEGINNER,
    preferredBoards: ["K10"],
    budgetPreference: BudgetPreference.BALANCED,
    needsLesson: false,
    completed: true,
  });
  const [formError, setFormError] = useState<string | null>(null);
  const busy = state.status === AuthenticationStatus.AUTHENTICATING
    || state.status === AuthenticationStatus.VERIFYING_EMAIL;
  const checking = state.status === AuthenticationStatus.CHECKING;
  const emailValid = useMemo(
    () => email.length === 0 || /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim()),
    [email],
  );

  const changeMode = (mode: AuthMode) => {
    setFormError(null);
    onStateChange((current) => ({ ...current, mode, error: null }));
  };

  const fail = (error: unknown) => {
    onStateChange((current) => ({
      ...current,
      status: current.mode === "profile"
        ? AuthenticationStatus.PROFILE_REQUIRED
        : current.mode === "legacy-claim"
          ? AuthenticationStatus.LEGACY_CLAIM_REQUIRED
          : AuthenticationStatus.UNAUTHENTICATED,
      error: error instanceof Error ? error.message : "操作失败，请重试。",
    }));
  };

  const submit = async () => {
    setFormError(null);
    try {
      if (state.mode === "register") {
        if (!emailValid || !email.trim()) return setFormError("请输入有效的邮箱地址。");
        if (!displayName.trim()) return setFormError("请输入显示名称。");
        if (password.length < 10 || !/[A-Za-z]/.test(password) || !/[0-9]/.test(password)) {
          return setFormError("密码至少 10 位，并同时包含字母和数字。");
        }
        if (password !== confirmPassword) return setFormError("两次输入的密码不一致。");
        onStateChange((current) => ({ ...current, status: AuthenticationStatus.AUTHENTICATING, error: null }));
        const challenge = await registerEmailAccount({
          email: email.trim(),
          displayName: displayName.trim(),
          password,
        });
        onStateChange((current) => ({
          ...current,
          status: AuthenticationStatus.UNAUTHENTICATED,
          mode: "verify",
          email: email.trim(),
          challengeId: challenge.challengeId,
          error: null,
        }));
        return;
      }
      if (state.mode === "verify") {
        if (!/^\d{6}$/.test(code)) return setFormError("请输入邮件中的六位验证码。");
        if (!state.challengeId) return setFormError("验证请求已失效，请重新注册或重发验证码。");
        onStateChange((current) => ({ ...current, status: AuthenticationStatus.VERIFYING_EMAIL, error: null }));
        await onEnterWorkspace(await verifyEmail({ challengeId: state.challengeId, code }));
        return;
      }
      if (state.mode === "login") {
        if (!emailValid || !email.trim() || !password) return setFormError("请输入邮箱和密码。");
        onStateChange((current) => ({ ...current, status: AuthenticationStatus.AUTHENTICATING, error: null }));
        await onEnterWorkspace(await loginEmailAccount({ email: email.trim(), password }));
        return;
      }
      if (state.mode === "local-login") {
        if (!username.trim() || !password) return setFormError("请输入本机账号和密码。");
        onStateChange((current) => ({ ...current, status: AuthenticationStatus.AUTHENTICATING, error: null }));
        await onEnterLocalWorkspace(await loginAccount({
          username: username.trim(),
          password,
        }));
        return;
      }
      if (state.mode === "reset-request") {
        if (!emailValid || !email.trim()) return setFormError("请输入有效的邮箱地址。");
        onStateChange((current) => ({ ...current, status: AuthenticationStatus.AUTHENTICATING, error: null }));
        const challenge = await requestPasswordReset({ email: email.trim() });
        onStateChange((current) => ({
          ...current,
          status: AuthenticationStatus.UNAUTHENTICATED,
          mode: "reset-confirm",
          email: email.trim(),
          challengeId: challenge.challengeId,
          error: null,
        }));
        return;
      }
      if (state.mode === "reset-confirm") {
        if (!/^\d{6}$/.test(code)) return setFormError("请输入邮件中的六位验证码。");
        if (!state.challengeId) return setFormError("重置请求已失效，请重新申请。");
        if (password.length < 10 || !/[A-Za-z]/.test(password) || !/[0-9]/.test(password)) {
          return setFormError("新密码至少 10 位，并同时包含字母和数字。");
        }
        if (password !== confirmPassword) return setFormError("两次输入的密码不一致。");
        onStateChange((current) => ({ ...current, status: AuthenticationStatus.AUTHENTICATING, error: null }));
        await confirmPasswordReset({ challengeId: state.challengeId, code, newPassword: password });
        setPassword("");
        setConfirmPassword("");
        setCode("");
        onStateChange((current) => ({
          ...current,
          status: AuthenticationStatus.UNAUTHENTICATED,
          mode: "login",
          challengeId: null,
          error: "密码已重置，请使用新密码登录。",
        }));
        return;
      }
      if (state.mode === "profile") {
        onStateChange((current) => ({ ...current, status: AuthenticationStatus.AUTHENTICATING, error: null }));
        await updateAccountProfile({ ...profile, completed: true });
        const session = await getAuthSession();
        await onCompleteAccountEntry(session.account, state.email);
      }
    } catch (error) {
      fail(error);
    }
  };

  const completeLegacyClaim = async (claimAll: boolean) => {
    if (!state.account) {
      fail(new Error("登录会话已失效，请重新登录。"));
      return;
    }
    onStateChange((current) => ({
      ...current,
      status: AuthenticationStatus.AUTHENTICATING,
      error: null,
    }));
    try {
      await decideLegacyProjectClaim({ claimAll });
      onStateChange({
        ...state,
        status: AuthenticationStatus.AUTHENTICATED,
        account: state.account,
        mode: "login",
        email: state.email,
        challengeId: null,
        unclaimedProjectCount: 0,
        error: null,
      });
    } catch (error) {
      fail(error);
    }
  };

  return (
    <main className="auth-page">
      <section className="auth-brand-panel" aria-label="掌问产品介绍">
        <img className="auth-brand-mark" src="/app-logo.png" alt="掌问 Logo" />
        <div>
          <span>掌问</span>
          <h1>AI 创客工程工作台</h1>
          <p>从创意、硬件与代码，到可验证的工程作品。</p>
        </div>
        <ul>
          <li>用清晰步骤完成方案、实现和设备验证</li>
          <li>项目保存在本机，并按邮箱账号严格隔离</li>
          <li>已验证设备可离线使用本地项目 30 天</li>
        </ul>
      </section>

      <section className="auth-card" aria-live="polite">
        {checking ? (
          <div className="auth-checking" role="status">
            <span aria-hidden="true" />
            <h2>正在检查登录状态</h2>
            <p>正在连接本地安全服务...</p>
          </div>
        ) : (
          <>
            <span className="auth-card-eyebrow">{eyebrow(state.mode)}</span>
            <h2>{heading(state.mode)}</h2>
            <p className="auth-card-description">{description(state.mode, state.email)}</p>

            {state.mode === "legacy-claim" ? (
              <div className="auth-form auth-legacy-claim">
                <p>
                  这台设备上有 {state.unclaimedProjectCount} 个升级前创建的项目。
                  数据库迁移前备份已经保留。
                </p>
                {(formError || state.error) && (
                  <div className="auth-error" role="alert">{formError || state.error}</div>
                )}
                <button
                  type="button"
                  className="auth-primary"
                  disabled={busy}
                  onClick={() => void completeLegacyClaim(true)}
                >
                  认领全部旧项目
                </button>
                <button
                  type="button"
                  className="auth-retry"
                  disabled={busy}
                  onClick={() => void completeLegacyClaim(false)}
                >
                  暂不处理
                </button>
                <p className="auth-card-description">
                  认领前，这些项目不会显示给任何邮箱账号。
                </p>
              </div>
            ) : <form
              className="auth-form"
              onSubmit={(event) => {
                event.preventDefault();
                void submit();
              }}
            >
              {state.mode === "local-login" && (
                <label>
                  <span>本机账号</span>
                  <input
                    aria-label="本机账号"
                    autoComplete="username"
                    value={username}
                    disabled={busy}
                    onChange={(event) => setUsername(event.target.value)}
                    placeholder="例如 maker"
                  />
                </label>
              )}
              {(["login", "register", "reset-request"] as AuthMode[]).includes(state.mode) && (
                <label>
                  <span>邮箱</span>
                  <input
                    aria-label="邮箱"
                    type="email"
                    autoComplete="email"
                    value={email}
                    disabled={busy}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="name@example.com"
                    data-invalid={!emailValid || undefined}
                  />
                </label>
              )}
              {state.mode === "register" && (
                <label>
                  <span>显示名称</span>
                  <input aria-label="显示名称" autoComplete="name" value={displayName} disabled={busy} onChange={(event) => setDisplayName(event.target.value)} />
                </label>
              )}
              {(["login", "local-login", "register", "reset-confirm"] as AuthMode[]).includes(state.mode) && (
                <label>
                  <span>{state.mode === "reset-confirm" ? "新密码" : "密码"}</span>
                  <input
                    aria-label={state.mode === "reset-confirm" ? "新密码" : "密码"}
                    type="password"
                    autoComplete={state.mode === "login" || state.mode === "local-login"
                      ? "current-password"
                      : "new-password"}
                    value={password}
                    disabled={busy}
                    onChange={(event) => setPassword(event.target.value)}
                  />
                </label>
              )}
              {(["register", "reset-confirm"] as AuthMode[]).includes(state.mode) && (
                <label>
                  <span>确认密码</span>
                  <input aria-label="确认密码" type="password" autoComplete="new-password" value={confirmPassword} disabled={busy} onChange={(event) => setConfirmPassword(event.target.value)} />
                </label>
              )}
              {(["verify", "reset-confirm"] as AuthMode[]).includes(state.mode) && (
                <label>
                  <span>六位验证码</span>
                  <input aria-label="六位验证码" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} disabled={busy} onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))} />
                </label>
              )}
              {state.mode === "profile" && (
                <ProfileFields profile={profile} onChange={setProfile} busy={busy} />
              )}

              {(formError || state.error) && <div className="auth-error" role="alert">{formError || state.error}</div>}
              <button type="submit" className="auth-primary" disabled={busy}>{submitLabel(state.mode, busy)}</button>
            </form>}

            {state.mode === "verify" && (
              <button
                type="button"
                className="auth-retry"
                disabled={busy}
                onClick={() => void resendVerification({ email: state.email }).then((challenge) => {
                  onStateChange((current) => ({ ...current, challengeId: challenge.challengeId, error: "验证码已重新发送。" }));
                }).catch(fail)}
              >
                重新发送验证码
              </button>
            )}
            {state.mode === "login" && (
              <div className="auth-switch">
                <button type="button" disabled={busy} onClick={() => changeMode("reset-request")}>忘记密码</button>
                <button type="button" disabled={busy} onClick={() => changeMode("register")}>创建邮箱账号</button>
                {state.localLoginAvailable && (
                  <button type="button" disabled={busy} onClick={() => changeMode("local-login")}>
                    使用本机账号
                  </button>
                )}
              </div>
            )}
            {state.mode === "local-login" && (
              <>
                <p className="auth-card-description">
                  忘记密码时，请运行掌问目录中的“重置本机密码”工具；工具会先备份认证库。
                </p>
                {state.cloudAuthConfigured && (
                  <div className="auth-switch">
                    <button type="button" disabled={busy} onClick={() => changeMode("login")}>
                      使用邮箱账号
                    </button>
                  </div>
                )}
              </>
            )}
            {state.mode !== "login"
              && state.mode !== "local-login"
              && state.mode !== "profile"
              && state.mode !== "legacy-claim" && (
              <div className="auth-switch">
                <button type="button" disabled={busy} onClick={() => changeMode("login")}>返回登录</button>
              </div>
            )}
            {state.error?.includes("服务") && <button type="button" className="auth-retry" onClick={onRetry}>重新连接</button>}
          </>
        )}
      </section>
    </main>
  );
}

function heading(mode: AuthMode): string {
  return {
    login: "登录掌问",
    "local-login": "本机账号登录",
    register: "创建邮箱账号",
    verify: "验证邮箱",
    "reset-request": "重置密码",
    "reset-confirm": "输入验证码和新密码",
    profile: "完善使用偏好",
    "legacy-claim": "认领这台设备上的旧项目",
  }[mode];
}

function eyebrow(mode: AuthMode): string {
  return mode === "login" || mode === "local-login"
    ? "欢迎回来"
    : mode === "profile"
      ? "只需设置一次"
      : mode === "legacy-claim"
        ? "一次性迁移"
        : "安全账号";
}

function description(mode: AuthMode, email: string): string {
  if (mode === "verify") return `验证码已发送至 ${email}，10 分钟内有效且只能使用一次。`;
  if (mode === "profile") return "这些偏好只用于改善推荐，不会改变权限或设备安全规则。";
  if (mode === "legacy-claim") return "请选择是否将升级前的本地项目归入当前邮箱账号。";
  if (mode === "reset-request") return "无论邮箱是否存在，系统都会返回相同提示。";
  if (mode === "reset-confirm") return `请输入发送至 ${email} 的验证码。`;
  if (mode === "register") return "项目仍保存在本机；邮箱账号用于隔离本机上的项目和设置。";
  if (mode === "local-login") {
    return "邮箱服务尚未配置，使用这台设备上已有的本机账号访问原项目。";
  }
  return "登录后访问这台设备上属于你的项目、产物和设备记录。";
}

function submitLabel(mode: AuthMode, busy: boolean): string {
  if (busy) return "正在处理...";
  return {
    login: "登录",
    "local-login": "登录本机账号",
    register: "发送验证码",
    verify: "验证并继续",
    "reset-request": "发送重置验证码",
    "reset-confirm": "确认重置密码",
    profile: "保存并进入掌问",
    "legacy-claim": "继续",
  }[mode];
}
