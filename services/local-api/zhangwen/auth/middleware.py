from __future__ import annotations

import os

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from zhangwen.auth.repository import AuthError, AuthRepository
from zhangwen.auth.context import bind_owner_subject, reset_owner_subject
from zhangwen.config import settings


PUBLIC_API_PATHS = {
    "/api/health",
    "/api/health/desktop-capability",
    "/api/auth/status",
    "/api/auth/register",
    "/api/auth/register-email",
    "/api/auth/verify-email",
    "/api/auth/resend",
    "/api/auth/login",
    "/api/auth/login-email",
    "/api/auth/password-reset/request",
    "/api/auth/password-reset/confirm",
}


class AuthSessionMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not auth_enforcement_enabled():
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive=receive)
        path = request.url.path.rstrip("/") or "/"
        if (
            request.method == "OPTIONS"
            or not path.startswith("/api")
            or path in PUBLIC_API_PATHS
        ):
            await self.app(scope, receive, send)
            return
        token = bearer_token(request)
        if token is None:
            await _auth_error_response(
                AuthError("AUTH_REQUIRED", "请先登录后再使用掌问。", 401),
                scope,
                receive,
                send,
            )
            return
        repository = AuthRepository(settings.data_dir)
        try:
            session = repository.validate_session(token)
        except AuthError as exc:
            await _auth_error_response(exc, scope, receive, send)
            return
        request.state.auth_session = session
        cloud_identity = repository.cloud_identity(session.account.id)
        owner_subject = (
            str(cloud_identity["subject"])
            if cloud_identity is not None
            else session.account.id
        )
        owner_token = bind_owner_subject(owner_subject)
        try:
            if project_id := _scoped_project_id(path):
                from zhangwen.projects.errors import ProjectNotFoundError
                from zhangwen.projects.repository import ProjectRepository

                try:
                    ProjectRepository(settings.data_dir).assert_project_access(project_id)
                except ProjectNotFoundError:
                    response = JSONResponse(
                        status_code=404,
                        content={
                            "detail": {
                                "code": "PROJECT_NOT_FOUND",
                                "message": "项目不存在。",
                                "userActions": [],
                                "retryable": False,
                            }
                        },
                    )
                    await response(scope, receive, send)
                    return
            await self.app(scope, receive, send)
        finally:
            reset_owner_subject(owner_token)


def auth_enforcement_enabled() -> bool:
    return os.environ.get("ZHANGWEN_AUTH_DISABLED", "").strip().lower() not in {
        "1",
        "true",
        "yes",
    }


def bearer_token(request: Request) -> str | None:
    authorization = request.headers.get("Authorization", "").strip()
    scheme, separator, token = authorization.partition(" ")
    if separator and scheme.lower() == "bearer" and token.strip():
        return token.strip()
    return None


def _scoped_project_id(path: str) -> str | None:
    prefix = "/api/projects/"
    if not path.startswith(prefix):
        return None
    candidate = path[len(prefix) :].split("/", 1)[0]
    if not candidate or candidate in {"suggest", "package", "legacy-claim"}:
        return None
    return candidate


async def _auth_error_response(
    error: AuthError,
    scope: Scope,
    receive: Receive,
    send: Send,
) -> None:
    response = JSONResponse(
        status_code=error.status_code,
        content={"detail": {"code": error.code, "message": error.message}},
    )
    await response(scope, receive, send)
