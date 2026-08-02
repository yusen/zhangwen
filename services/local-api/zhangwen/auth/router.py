from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from zhangwen.auth.cloud_client import CloudAuthClient
from zhangwen.auth.cloud_facade import CloudAuthFacade
from zhangwen.auth.middleware import bearer_token
from zhangwen.auth.models import (
    AcceptedResponse,
    AccountProfileResponse,
    AuthResultResponse,
    AuthSession,
    AuthSessionResponse,
    AuthStatusResponse,
    EmailAuthResultResponse,
    EmailLoginRequest,
    EmailRequest,
    LoginRequest,
    LogoutResponse,
    PasswordResetConfirmRequest,
    RegisterAccountRequest,
    RegisterEmailAccountRequest,
    UpdateAccountProfileRequest,
    VerificationChallengeResponse,
    VerifyEmailRequest,
)
from zhangwen.auth.repository import AuthError, AuthRepository
from zhangwen.config import settings
from zhangwen.security.credentials import BackendCredentialStore


router = APIRouter(prefix="/api/auth", tags=["auth"])
cloud_client_factory = CloudAuthClient
credential_store_factory = BackendCredentialStore


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status() -> AuthStatusResponse:
    repository = _repo()
    return AuthStatusResponse(
        hasAccounts=repository.has_accounts(),
        hasLocalAccounts=repository.has_local_accounts(),
        cloudAuthConfigured=bool(settings.cloud_auth_base_url),
    )


@router.post(
    "/register",
    response_model=AuthResultResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_account(request: RegisterAccountRequest) -> AuthResultResponse:
    try:
        account, token, expires_at = _repo().register(
            username=request.username,
            display_name=request.displayName,
            password=request.password,
        )
        return AuthResultResponse(
            account=account,
            sessionToken=token,
            expiresAt=expires_at,
        )
    except AuthError as exc:
        raise _http_error(exc) from exc


@router.post(
    "/register-email",
    response_model=VerificationChallengeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_email_account(
    request: RegisterEmailAccountRequest,
) -> VerificationChallengeResponse:
    try:
        return _cloud().register(
            email=request.email,
            display_name=request.displayName,
            password=request.password,
        )
    except AuthError as exc:
        raise _http_error(exc) from exc


@router.post("/verify-email", response_model=EmailAuthResultResponse)
async def verify_email(request: VerifyEmailRequest) -> EmailAuthResultResponse:
    try:
        return _cloud().verify_email(
            challenge_id=request.challengeId,
            code=request.code,
        )
    except AuthError as exc:
        raise _http_error(exc) from exc


@router.post("/resend", response_model=VerificationChallengeResponse)
async def resend_verification(request: EmailRequest) -> VerificationChallengeResponse:
    try:
        return _cloud().resend(email=request.email)
    except AuthError as exc:
        raise _http_error(exc) from exc


@router.post("/login", response_model=AuthResultResponse)
async def login(request: LoginRequest) -> AuthResultResponse:
    try:
        account, token, expires_at = _repo().login(
            username=request.username,
            password=request.password,
        )
        return AuthResultResponse(
            account=account,
            sessionToken=token,
            expiresAt=expires_at,
        )
    except AuthError as exc:
        raise _http_error(exc) from exc


@router.post("/login-email", response_model=EmailAuthResultResponse)
async def login_email(request: EmailLoginRequest) -> EmailAuthResultResponse:
    try:
        return _cloud().login(email=request.email, password=request.password)
    except AuthError as exc:
        raise _http_error(exc) from exc


@router.post("/password-reset/request", response_model=VerificationChallengeResponse)
async def request_password_reset(request: EmailRequest) -> VerificationChallengeResponse:
    try:
        return _cloud().request_password_reset(email=request.email)
    except AuthError as exc:
        raise _http_error(exc) from exc


@router.post("/password-reset/confirm", response_model=AcceptedResponse)
async def confirm_password_reset(request: PasswordResetConfirmRequest) -> AcceptedResponse:
    try:
        return _cloud().confirm_password_reset(
            challenge_id=request.challengeId,
            code=request.code,
            new_password=request.newPassword,
        )
    except AuthError as exc:
        raise _http_error(exc) from exc


@router.get("/profile", response_model=AccountProfileResponse)
async def get_profile(request: Request) -> AccountProfileResponse:
    session = _request_session(request)
    try:
        return _cloud().cached_profile(local_account_id=session.account.id)
    except AuthError as exc:
        raise _http_error(exc) from exc


@router.patch("/profile", response_model=AccountProfileResponse)
async def update_profile(
    request: Request,
    profile: UpdateAccountProfileRequest,
) -> AccountProfileResponse:
    session = _request_session(request)
    try:
        return _cloud().update_profile(
            local_account_id=session.account.id,
            payload=profile.model_dump(mode="json"),
        )
    except AuthError as exc:
        raise _http_error(exc) from exc


@router.get("/session", response_model=AuthSessionResponse)
async def current_session(request: Request) -> AuthSessionResponse:
    session = _request_session(request)
    return AuthSessionResponse(account=session.account, expiresAt=session.expiresAt)


@router.post("/logout", response_model=LogoutResponse)
async def logout(request: Request) -> LogoutResponse:
    token = bearer_token(request)
    if token is None:
        raise _http_error(
            AuthError("AUTH_REQUIRED", "请先登录后再使用掌问。", 401)
        )
    repository = _repo()
    try:
        session = repository.validate_session(token)
        if repository.cloud_identity(session.account.id) is not None:
            _cloud(repository).logout(local_account_id=session.account.id)
    finally:
        repository.logout(token)
    return LogoutResponse()


def _request_session(request: Request) -> AuthSession:
    session = getattr(request.state, "auth_session", None)
    if isinstance(session, AuthSession):
        return session
    token = bearer_token(request)
    if token is None:
        raise _http_error(
            AuthError("AUTH_REQUIRED", "请先登录后再使用掌问。", 401)
        )
    try:
        return _repo().validate_session(token)
    except AuthError as exc:
        raise _http_error(exc) from exc


def _repo() -> AuthRepository:
    return AuthRepository(settings.data_dir)


def _cloud(repository: AuthRepository | None = None) -> CloudAuthFacade:
    if not settings.cloud_auth_base_url:
        raise AuthError(
            "CLOUD_AUTH_NOT_CONFIGURED",
            "邮箱账号服务尚未配置，请联系管理员。",
            503,
        )
    return CloudAuthFacade(
        repository=repository or _repo(),
        client=cloud_client_factory(settings.cloud_auth_base_url),
        credential_store=credential_store_factory(),
        credential_service=settings.cloud_auth_credential_service,
    )


def _http_error(error: AuthError) -> HTTPException:
    return HTTPException(
        status_code=error.status_code,
        detail={"code": error.code, "message": error.message},
    )
