from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status

from zhangwen_cloud_auth.config import CloudAuthSettings
from zhangwen_cloud_auth.database import Database
from zhangwen_cloud_auth.mailer import SmtpMailer
from zhangwen_cloud_auth.models import (
    AcceptedResponse,
    ChallengeResponse,
    LoginRequest,
    LogoutRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    ProfileResponse,
    RefreshRequest,
    RegisterRequest,
    ResendVerificationRequest,
    TokenResponse,
    UpdateProfileRequest,
    VerifyEmailRequest,
)
from zhangwen_cloud_auth.service import CloudAuthError, CloudAuthService


def create_app(service: CloudAuthService | None = None) -> FastAPI:
    application = FastAPI(title="掌问云端身份服务", version="1.0.0")
    service_instance = service

    def current_service() -> CloudAuthService:
        nonlocal service_instance
        if service_instance is None:
            settings = CloudAuthSettings.from_environment()
            service_instance = CloudAuthService(
                database=Database(settings.database_url),
                mailer=SmtpMailer(settings),
                secret=settings.secret,
            )
        return service_instance

    def current_account(
        authorization: str | None = Header(default=None),
        auth_service: CloudAuthService = Depends(current_service),
    ):
        if not authorization:
            raise _http_error(CloudAuthError("AUTH_REQUIRED", "请先登录。", 401))
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise _http_error(CloudAuthError("AUTH_REQUIRED", "请先登录。", 401))
        try:
            return auth_service.validate_access(token.strip())
        except CloudAuthError as exc:
            raise _http_error(exc) from exc

    @application.exception_handler(CloudAuthError)
    async def cloud_auth_error_handler(_request: Request, exc: CloudAuthError):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": {"code": exc.code, "message": exc.message, "retryable": False}},
        )

    @application.get("/health")
    async def health() -> dict[str, str]:
        current_service()
        return {"status": "ok"}

    @application.post("/v1/auth/register", response_model=ChallengeResponse, status_code=status.HTTP_201_CREATED)
    async def register(request: RegisterRequest, raw: Request):
        return current_service().register(
            email=request.email,
            display_name=request.displayName,
            password=request.password,
            rate_key=_client_ip(raw),
        )

    @application.post("/v1/auth/verify-email", response_model=TokenResponse)
    async def verify_email(request: VerifyEmailRequest):
        return current_service().verify_email(
            challenge_id=request.challengeId,
            code=request.code,
            device_id=request.deviceId,
        )

    @application.post("/v1/auth/resend", response_model=ChallengeResponse)
    async def resend(request: ResendVerificationRequest, raw: Request):
        return current_service().resend_verification(
            email=request.email,
            rate_key=_client_ip(raw),
        )

    @application.post("/v1/auth/login", response_model=TokenResponse)
    async def login(request: LoginRequest, raw: Request):
        return current_service().login(
            email=request.email,
            password=request.password,
            device_id=request.deviceId,
            rate_key=f"{_client_ip(raw)}:{request.email}",
        )

    @application.post("/v1/auth/refresh", response_model=TokenResponse)
    async def refresh(request: RefreshRequest):
        return current_service().refresh(
            refresh_token=request.refreshToken,
            device_id=request.deviceId,
        )

    @application.post("/v1/auth/logout", response_model=AcceptedResponse)
    async def logout(request: LogoutRequest, account=Depends(current_account)):
        current_service().logout(account_id=account.id, refresh_token=request.refreshToken)
        return AcceptedResponse(message="已退出登录。")

    @application.post("/v1/auth/password-reset/request", response_model=ChallengeResponse)
    async def password_reset(request: PasswordResetRequest, raw: Request):
        return current_service().request_password_reset(
            email=request.email,
            rate_key=_client_ip(raw),
        )

    @application.post("/v1/auth/password-reset/confirm", response_model=AcceptedResponse)
    async def confirm_password_reset(request: PasswordResetConfirmRequest):
        current_service().confirm_password_reset(
            challenge_id=request.challengeId,
            code=request.code,
            new_password=request.newPassword,
        )
        return AcceptedResponse(message="密码已重置，请重新登录。")

    @application.get("/v1/me/profile", response_model=ProfileResponse)
    async def profile(account=Depends(current_account)):
        return current_service().get_profile(account.id)

    @application.patch("/v1/me/profile", response_model=ProfileResponse)
    async def update_profile(request: UpdateProfileRequest, account=Depends(current_account)):
        return current_service().update_profile(account.id, request)

    return application


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _http_error(exc: CloudAuthError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.message, "retryable": False},
    )


app = create_app()
