from __future__ import annotations

from typing import Any

from zhangwen.auth.cloud_client import CloudAuthClientError, CloudAuthClientProtocol
from zhangwen.auth.models import (
    AccountProfileResponse,
    AcceptedResponse,
    EmailAuthResultResponse,
    VerificationChallengeResponse,
)
from zhangwen.auth.repository import AuthError, AuthRepository
from zhangwen.security.credentials import CredentialStore, CredentialStoreError


class CloudAuthFacade:
    def __init__(
        self,
        *,
        repository: AuthRepository,
        client: CloudAuthClientProtocol,
        credential_store: CredentialStore,
        credential_service: str,
    ) -> None:
        self._repository = repository
        self._client = client
        self._credential_store = credential_store
        self._credential_service = credential_service

    def register(self, *, email: str, display_name: str, password: str) -> VerificationChallengeResponse:
        return VerificationChallengeResponse.model_validate(
            self._call(
                self._client.register,
                {"email": email, "displayName": display_name, "password": password},
            )
        )

    def verify_email(self, *, challenge_id: str, code: str) -> EmailAuthResultResponse:
        tokens = self._call(
            self._client.verify_email,
            {
                "challengeId": challenge_id,
                "code": code,
                "deviceId": self._repository.device_id(),
            },
        )
        return self._establish_session(tokens)

    def resend(self, *, email: str) -> VerificationChallengeResponse:
        return VerificationChallengeResponse.model_validate(
            self._call(self._client.resend, {"email": email})
        )

    def login(self, *, email: str, password: str) -> EmailAuthResultResponse:
        tokens = self._call(
            self._client.login,
            {
                "email": email,
                "password": password,
                "deviceId": self._repository.device_id(),
            },
        )
        return self._establish_session(tokens)

    def request_password_reset(self, *, email: str) -> VerificationChallengeResponse:
        return VerificationChallengeResponse.model_validate(
            self._call(self._client.request_password_reset, {"email": email})
        )

    def confirm_password_reset(
        self,
        *,
        challenge_id: str,
        code: str,
        new_password: str,
    ) -> AcceptedResponse:
        return AcceptedResponse.model_validate(
            self._call(
                self._client.confirm_password_reset,
                {
                    "challengeId": challenge_id,
                    "code": code,
                    "newPassword": new_password,
                },
            )
        )

    def cached_profile(self, *, local_account_id: str) -> AccountProfileResponse:
        identity = self._repository.cloud_identity(local_account_id)
        if identity is None:
            raise AuthError("CLOUD_ACCOUNT_REQUIRED", "当前会话不是邮箱账号。", 409)
        return AccountProfileResponse.model_validate(
            {"account": identity["account"], "profile": identity["profile"]}
        )

    def update_profile(
        self,
        *,
        local_account_id: str,
        payload: dict[str, Any],
    ) -> AccountProfileResponse:
        identity = self._repository.cloud_identity(local_account_id)
        if identity is None:
            raise AuthError("CLOUD_ACCOUNT_REQUIRED", "当前会话不是邮箱账号。", 409)
        tokens = self._refresh(identity)
        cloud_response = self._call(
            self._client.update_profile,
            str(tokens["accessToken"]),
            payload,
        )
        account, profile = self._repository.update_cloud_profile(
            cloud_subject=str(identity["subject"]),
            account_data=_dict(cloud_response, "account"),
            profile_data=_dict(cloud_response, "profile"),
            offline_lease_expires_at=str(tokens["offlineLeaseExpiresAt"]),
        )
        return AccountProfileResponse(account=account, profile=profile)

    def logout(self, *, local_account_id: str) -> None:
        identity = self._repository.cloud_identity(local_account_id)
        if identity is None:
            return
        subject = str(identity["subject"])
        refresh_token = self._read_refresh_token(subject)
        if refresh_token:
            try:
                tokens = self._call(
                    self._client.refresh,
                    {"refreshToken": refresh_token, "deviceId": self._repository.device_id()},
                )
                rotated = str(tokens["refreshToken"])
                self._write_refresh_token(subject, rotated)
                self._call(
                    self._client.logout,
                    str(tokens["accessToken"]),
                    {"refreshToken": rotated},
                )
            except AuthError:
                # Local logout must still work without a network. A reused or revoked
                # token cannot be useful after the credential is removed locally.
                pass
        self._delete_refresh_token(subject)

    def _establish_session(self, tokens: dict[str, Any]) -> EmailAuthResultResponse:
        account_data = _dict(tokens, "account")
        subject = str(account_data.get("id") or "")
        refresh_token = str(tokens.get("refreshToken") or "")
        access_token = str(tokens.get("accessToken") or "")
        offline_lease = str(tokens.get("offlineLeaseExpiresAt") or "")
        if not subject or not refresh_token or not access_token or not offline_lease:
            raise AuthError("CLOUD_AUTH_INVALID_RESPONSE", "账号服务返回了无效响应。", 502)
        profile_response = self._call(self._client.get_profile, access_token)
        profile_data = _dict(profile_response, "profile")
        self._write_refresh_token(subject, refresh_token)
        try:
            account, profile, session_token, expires_at = self._repository.create_cloud_session(
                account_data=account_data,
                profile_data=profile_data,
                offline_lease_expires_at=offline_lease,
            )
        except Exception:
            self._delete_refresh_token(subject)
            raise
        return EmailAuthResultResponse(
            account=account,
            profile=profile,
            sessionToken=session_token,
            expiresAt=expires_at,
            offlineLeaseExpiresAt=offline_lease,
        )

    def _refresh(self, identity: dict[str, object]) -> dict[str, Any]:
        subject = str(identity["subject"])
        refresh_token = self._read_refresh_token(subject)
        if not refresh_token:
            raise AuthError("CLOUD_REAUTH_REQUIRED", "请重新登录以继续修改账号资料。", 401)
        tokens = self._call(
            self._client.refresh,
            {"refreshToken": refresh_token, "deviceId": self._repository.device_id()},
        )
        self._write_refresh_token(subject, str(tokens["refreshToken"]))
        return tokens

    def _read_refresh_token(self, subject: str) -> str | None:
        try:
            return self._credential_store.get_password(self._credential_service, subject)
        except CredentialStoreError as exc:
            raise AuthError("CREDENTIAL_STORE_UNAVAILABLE", "系统凭据库不可用，无法安全登录。", 503) from exc

    def _write_refresh_token(self, subject: str, token: str) -> None:
        try:
            self._credential_store.set_password(self._credential_service, subject, token)
        except CredentialStoreError as exc:
            raise AuthError("CREDENTIAL_STORE_UNAVAILABLE", "系统凭据库不可用，无法安全登录。", 503) from exc

    def _delete_refresh_token(self, subject: str) -> None:
        try:
            self._credential_store.delete_password(self._credential_service, subject)
        except CredentialStoreError as exc:
            raise AuthError("CREDENTIAL_STORE_UNAVAILABLE", "系统凭据库不可用，无法安全退出。", 503) from exc

    @staticmethod
    def _call(method, *args):
        try:
            return method(*args)
        except CloudAuthClientError as exc:
            raise AuthError(exc.code, exc.message, exc.status_code) from exc


def _dict(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise AuthError("CLOUD_AUTH_INVALID_RESPONSE", "账号服务返回了无效响应。", 502)
    return value
