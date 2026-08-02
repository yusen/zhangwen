from __future__ import annotations

from typing import Any, Protocol

import httpx


class CloudAuthClientError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable


class CloudAuthClientProtocol(Protocol):
    def register(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def verify_email(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def resend(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def login(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def refresh(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def logout(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]: ...
    def request_password_reset(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def confirm_password_reset(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def get_profile(self, access_token: str) -> dict[str, Any]: ...
    def update_profile(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]: ...


class CloudAuthClient:
    """Narrow HTTP adapter; cloud refresh tokens never cross this Sidecar boundary."""

    def __init__(self, base_url: str, *, timeout_seconds: float = 8.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 3.0))

    def register(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/v1/auth/register", json=payload)

    def verify_email(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/v1/auth/verify-email", json=payload)

    def resend(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/v1/auth/resend", json=payload)

    def login(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/v1/auth/login", json=payload)

    def refresh(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/v1/auth/refresh", json=payload)

    def logout(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/v1/auth/logout", access_token=access_token, json=payload)

    def request_password_reset(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/v1/auth/password-reset/request", json=payload)

    def confirm_password_reset(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/v1/auth/password-reset/confirm", json=payload)

    def get_profile(self, access_token: str) -> dict[str, Any]:
        return self._request("GET", "/v1/me/profile", access_token=access_token)

    def update_profile(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("PATCH", "/v1/me/profile", access_token=access_token, json=payload)

    def _request(
        self,
        method: str,
        path: str,
        *,
        access_token: str | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {access_token}"} if access_token else None
        try:
            response = httpx.request(
                method,
                f"{self._base_url}{path}",
                headers=headers,
                json=json,
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise CloudAuthClientError(
                "CLOUD_AUTH_UNAVAILABLE",
                "暂时无法连接账号服务，请检查网络后重试。",
                503,
                retryable=True,
            ) from exc
        if response.is_success:
            body = response.json()
            if not isinstance(body, dict):
                raise CloudAuthClientError(
                    "CLOUD_AUTH_INVALID_RESPONSE",
                    "账号服务返回了无效响应。",
                    502,
                )
            return body
        try:
            detail = response.json().get("detail", {})
        except ValueError:
            detail = {}
        raise CloudAuthClientError(
            str(detail.get("code") or "CLOUD_AUTH_REQUEST_FAILED"),
            str(detail.get("message") or "账号服务请求失败。"),
            response.status_code,
            retryable=bool(detail.get("retryable", response.status_code >= 500)),
        )
