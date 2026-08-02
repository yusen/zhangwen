import type {
  AccountProfileResponse,
  AuthResultResponse,
  AuthSessionResponse,
  AuthStatusResponse,
  EmailAuthResultResponse,
  EmailChallengeResponse,
  EmailLoginRequest,
  LoginRequest,
  LogoutResponse,
  PasswordResetConfirmRequest,
  PasswordResetRequest,
  RegisterAccountRequest,
  RegisterEmailAccountRequest,
  ResendVerificationRequest,
  UpdateAccountProfileRequest,
  VerifyEmailRequest,
} from "@zhangwen/contracts";
import { apiGet, apiPatch, apiPost } from "./api";


export function getAuthStatus(): Promise<AuthStatusResponse> {
  return apiGet<AuthStatusResponse>("/api/auth/status");
}

export function registerAccount(
  request: RegisterAccountRequest,
): Promise<AuthResultResponse> {
  return apiPost<RegisterAccountRequest, AuthResultResponse>(
    "/api/auth/register",
    request,
  );
}

export function loginAccount(request: LoginRequest): Promise<AuthResultResponse> {
  return apiPost<LoginRequest, AuthResultResponse>("/api/auth/login", request);
}

export function getAuthSession(): Promise<AuthSessionResponse> {
  return apiGet<AuthSessionResponse>("/api/auth/session");
}

export function logoutAccount(): Promise<LogoutResponse> {
  return apiPost<Record<string, never>, LogoutResponse>("/api/auth/logout", {});
}

export function registerEmailAccount(
  request: RegisterEmailAccountRequest,
): Promise<EmailChallengeResponse> {
  return apiPost<RegisterEmailAccountRequest, EmailChallengeResponse>(
    "/api/auth/register-email",
    request,
  );
}

export function verifyEmail(
  request: VerifyEmailRequest,
): Promise<EmailAuthResultResponse> {
  return apiPost<VerifyEmailRequest, EmailAuthResultResponse>(
    "/api/auth/verify-email",
    request,
  );
}

export function resendVerification(
  request: ResendVerificationRequest,
): Promise<EmailChallengeResponse> {
  return apiPost<ResendVerificationRequest, EmailChallengeResponse>(
    "/api/auth/resend",
    request,
  );
}

export function loginEmailAccount(
  request: EmailLoginRequest,
): Promise<EmailAuthResultResponse> {
  return apiPost<EmailLoginRequest, EmailAuthResultResponse>(
    "/api/auth/login-email",
    request,
  );
}

export function requestPasswordReset(
  request: PasswordResetRequest,
): Promise<EmailChallengeResponse> {
  return apiPost<PasswordResetRequest, EmailChallengeResponse>(
    "/api/auth/password-reset/request",
    request,
  );
}

export function confirmPasswordReset(
  request: PasswordResetConfirmRequest,
): Promise<{ accepted: boolean; message: string }> {
  return apiPost<PasswordResetConfirmRequest, { accepted: boolean; message: string }>(
    "/api/auth/password-reset/confirm",
    request,
  );
}

export function getAccountProfile(): Promise<AccountProfileResponse> {
  return apiGet<AccountProfileResponse>("/api/auth/profile");
}

export function updateAccountProfile(
  request: UpdateAccountProfileRequest,
): Promise<AccountProfileResponse> {
  return apiPatch<UpdateAccountProfileRequest, AccountProfileResponse>(
    "/api/auth/profile",
    request,
  );
}
