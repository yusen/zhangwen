from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from zhangwen.auth import router as auth_router
from zhangwen.config import settings
from zhangwen.main import app
from zhangwen.security.credentials import MemoryCredentialStore


def _future(days: int) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).isoformat()


class FakeCloudAuthClient:
    refresh_seen: list[str] = []

    def __init__(self, _base_url: str) -> None:
        pass

    def register(self, payload):
        assert "deviceId" not in payload
        return {"challengeId": "challenge_123456789", "expiresAt": _future(1), "message": "sent"}

    def verify_email(self, payload):
        assert payload["deviceId"].startswith("device_")
        return self._tokens("refresh-initial")

    def resend(self, payload):
        return {"challengeId": "challenge_987654321", "expiresAt": _future(1), "message": "sent"}

    def login(self, payload):
        assert payload["deviceId"].startswith("device_")
        return self._tokens("refresh-login")

    def refresh(self, payload):
        self.refresh_seen.append(payload["refreshToken"])
        return self._tokens(f"refresh-rotated-{len(self.refresh_seen)}")

    def logout(self, access_token, payload):
        assert access_token == "access-token"
        assert payload["refreshToken"].startswith("refresh-rotated-")
        return {"accepted": True, "message": "logged out"}

    def request_password_reset(self, payload):
        return {"challengeId": "challenge_reset_123", "expiresAt": _future(1), "message": "accepted"}

    def confirm_password_reset(self, payload):
        return {"accepted": True, "message": "reset"}

    def get_profile(self, access_token):
        assert access_token == "access-token"
        return {"account": self._account(), "profile": self._profile(False)}

    def update_profile(self, access_token, payload):
        assert access_token == "access-token"
        assert payload["persona"] == "TEACHER"
        return {"account": self._account(), "profile": self._profile(True)}

    @classmethod
    def _tokens(cls, refresh_token: str):
        return {
            "account": cls._account(),
            "accessToken": "access-token",
            "accessExpiresAt": _future(1),
            "refreshToken": refresh_token,
            "refreshExpiresAt": _future(30),
            "offlineLeaseExpiresAt": _future(30),
        }

    @staticmethod
    def _account():
        return {
            "id": "subject-001",
            "email": "teacher@example.com",
            "displayName": "王老师",
            "emailVerified": True,
            "createdAt": datetime.now(UTC).isoformat(),
        }

    @staticmethod
    def _profile(completed: bool):
        return {
            "persona": "TEACHER" if completed else None,
            "technicalLevel": "BEGINNER" if completed else None,
            "preferredBoards": ["K10"] if completed else [],
            "budgetPreference": "BALANCED" if completed else None,
            "needsLesson": completed,
            "completed": completed,
        }


def test_sidecar_keeps_refresh_token_out_of_http_and_sqlite(
    tmp_path: Path,
    monkeypatch,
) -> None:
    credential_store = MemoryCredentialStore()
    FakeCloudAuthClient.refresh_seen = []
    monkeypatch.delenv("ZHANGWEN_AUTH_DISABLED", raising=False)
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "cloud_auth_base_url", "https://auth.test")
    monkeypatch.setattr(auth_router, "cloud_client_factory", FakeCloudAuthClient)
    monkeypatch.setattr(auth_router, "credential_store_factory", lambda: credential_store)

    with TestClient(app) as client:
        challenge = client.post(
            "/api/auth/register-email",
            json={
                "email": "teacher@example.com",
                "displayName": "王老师",
                "password": "TeacherPass123",
            },
        )
        assert challenge.status_code == 201

        verified = client.post(
            "/api/auth/verify-email",
            json={"challengeId": "challenge_123456789", "code": "123456"},
        )
        assert verified.status_code == 200
        body = verified.json()
        assert "refreshToken" not in body
        assert "accessToken" not in body
        assert body["profile"]["completed"] is False
        local_token = body["sessionToken"]
        headers = {"Authorization": f"Bearer {local_token}"}
        assert client.get("/api/projects", headers=headers).status_code == 200

        profile = client.patch(
            "/api/auth/profile",
            headers=headers,
            json={
                "persona": "TEACHER",
                "technicalLevel": "BEGINNER",
                "preferredBoards": ["K10"],
                "budgetPreference": "BALANCED",
                "needsLesson": True,
                "completed": True,
            },
        )
        assert profile.status_code == 200
        assert profile.json()["profile"]["needsLesson"] is True
        assert FakeCloudAuthClient.refresh_seen == ["refresh-initial"]

        logout = client.post("/api/auth/logout", headers=headers, json={})
        assert logout.status_code == 200
        assert credential_store.get_password(
            settings.cloud_auth_credential_service,
            "subject-001",
        ) is None

    database_bytes = (tmp_path / "auth" / "zhangwen-auth.sqlite3").read_bytes()
    assert b"refresh-initial" not in database_bytes
    assert b"refresh-rotated" not in database_bytes
    with sqlite3.connect(tmp_path / "auth" / "zhangwen-auth.sqlite3") as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
        row = conn.execute(
            "SELECT auth_kind, cloud_subject, email FROM local_accounts"
        ).fetchone()
    assert row == ("cloud", "subject-001", "teacher@example.com")


def test_expired_cloud_offline_lease_blocks_local_session(
    tmp_path: Path,
    monkeypatch,
) -> None:
    credential_store = MemoryCredentialStore()
    monkeypatch.delenv("ZHANGWEN_AUTH_DISABLED", raising=False)
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "cloud_auth_base_url", "https://auth.test")
    monkeypatch.setattr(auth_router, "cloud_client_factory", FakeCloudAuthClient)
    monkeypatch.setattr(auth_router, "credential_store_factory", lambda: credential_store)

    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login-email",
            json={"email": "teacher@example.com", "password": "TeacherPass123"},
        )
        token = login.json()["sessionToken"]
        with sqlite3.connect(tmp_path / "auth" / "zhangwen-auth.sqlite3") as conn:
            conn.execute(
                "UPDATE local_accounts SET offline_lease_expires_at = '2000-01-01T00:00:00+00:00'"
            )
        response = client.get(
            "/api/projects",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "OFFLINE_LEASE_EXPIRED"
