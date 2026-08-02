from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from zhangwen.auth.repository import AuthError, AuthRepository
from zhangwen.config import settings
from zhangwen.main import app


def test_registration_login_session_logout_and_business_gate(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("ZHANGWEN_AUTH_DISABLED", raising=False)
    monkeypatch.setattr(settings, "data_dir", tmp_path)

    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        preflight = client.options(
            "/api/projects",
            headers={
                "Origin": "http://localhost:1420",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization",
            },
        )
        assert preflight.status_code == 200
        assert "authorization" in preflight.headers[
            "access-control-allow-headers"
        ].lower()
        blocked = client.get("/api/projects")
        assert blocked.status_code == 401
        assert blocked.json()["detail"]["code"] == "AUTH_REQUIRED"

        status = client.get("/api/auth/status")
        assert status.status_code == 200
        assert status.json() == {
            "hasAccounts": False,
            "hasLocalAccounts": False,
            "cloudAuthConfigured": False,
        }

        weak = client.post(
            "/api/auth/register",
            json={
                "username": "maker_01",
                "displayName": "小掌",
                "password": "password",
            },
        )
        assert weak.status_code == 422

        registration = client.post(
            "/api/auth/register",
            json={
                "username": "maker_01",
                "displayName": "小掌",
                "password": "MakerPass123",
            },
        )
        assert registration.status_code == 201
        registration_body = registration.json()
        assert registration_body["account"]["username"] == "maker_01"
        assert registration_body["account"]["displayName"] == "小掌"
        assert "password" not in registration_body["account"]
        token = registration_body["sessionToken"]
        assert len(token) >= 32

        assert client.get("/api/auth/status").json() == {
            "hasAccounts": True,
            "hasLocalAccounts": True,
            "cloudAuthConfigured": False,
        }

        headers = {"Authorization": f"Bearer {token}"}
        session = client.get("/api/auth/session", headers=headers)
        assert session.status_code == 200
        assert session.json()["account"]["username"] == "maker_01"
        assert client.get("/api/projects", headers=headers).status_code == 200

        duplicate = client.post(
            "/api/auth/register",
            json={
                "username": "MAKER_01",
                "displayName": "另一个掌问用户",
                "password": "OtherPass123",
            },
        )
        assert duplicate.status_code == 409
        assert duplicate.json()["detail"]["code"] == "ACCOUNT_ALREADY_EXISTS"

        wrong_password = client.post(
            "/api/auth/login",
            json={"username": "maker_01", "password": "WrongPass123"},
        )
        unknown_account = client.post(
            "/api/auth/login",
            json={"username": "missing_01", "password": "WrongPass123"},
        )
        assert wrong_password.status_code == unknown_account.status_code == 401
        assert wrong_password.json()["detail"] == unknown_account.json()["detail"]

        login = client.post(
            "/api/auth/login",
            json={"username": "MAKER_01", "password": "MakerPass123"},
        )
        assert login.status_code == 200
        login_token = login.json()["sessionToken"]
        assert login_token != token

        logout = client.post(
            "/api/auth/logout",
            json={},
            headers={"Authorization": f"Bearer {login_token}"},
        )
        assert logout.status_code == 200
        assert logout.json() == {"loggedOut": True}
        assert (
            client.get(
                "/api/auth/session",
                headers={"Authorization": f"Bearer {login_token}"},
            ).status_code
            == 401
        )

    auth_db = tmp_path / "auth" / "zhangwen-auth.sqlite3"
    assert auth_db.is_file()
    with sqlite3.connect(auth_db) as conn:
        account_row = conn.execute(
            "SELECT password_hash, password_salt, password_iterations FROM local_accounts"
        ).fetchone()
        session_rows = conn.execute(
            "SELECT token_hash FROM auth_sessions"
        ).fetchall()
        version = conn.execute("PRAGMA user_version").fetchone()[0]
    assert account_row is not None
    assert account_row[0] != "MakerPass123"
    assert account_row[1] != "MakerPass123"
    assert account_row[2] >= 300_000
    assert all(row[0] not in {token, login_token} for row in session_rows)
    assert version == 2


def test_local_password_recovery_revokes_old_sessions_and_preserves_account(
    tmp_path: Path,
) -> None:
    repository = AuthRepository(tmp_path)
    account, old_token, _ = repository.register(
        username="local-maker",
        display_name="Test Maker",
        password="OriginalPass123",
    )
    repository.register(
        username="other_user",
        display_name="其他账号",
        password="OtherPass123",
    )

    recovered = repository.reset_local_password(
        username="LOCAL-MAKER",
        new_password="RecoveredPass123",
    )

    assert recovered == account
    assert repository.has_local_accounts() is True
    assert [item.username for item in repository.local_accounts()] == [
        "local-maker",
        "other_user",
    ]
    with pytest.raises(AuthError) as old_password:
        repository.login(username="local-maker", password="OriginalPass123")
    assert old_password.value.code == "AUTH_CREDENTIALS_INVALID"
    with pytest.raises(AuthError) as old_session:
        repository.validate_session(old_token)
    assert old_session.value.code == "AUTH_SESSION_INVALID"
    assert repository.login(
        username="local-maker",
        password="RecoveredPass123",
    )[0] == account
    assert repository.login(
        username="other_user",
        password="OtherPass123",
    )[0].displayName == "其他账号"

    with pytest.raises(AuthError) as invalid_password:
        repository.reset_local_password(username="local-maker", new_password="onlyletters")
    assert invalid_password.value.code == "AUTH_PASSWORD_INVALID"


def test_expired_session_is_rejected(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("ZHANGWEN_AUTH_DISABLED", raising=False)
    monkeypatch.setattr(settings, "data_dir", tmp_path)

    with TestClient(app) as client:
        registration = client.post(
            "/api/auth/register",
            json={
                "username": "expiry_user",
                "displayName": "过期测试",
                "password": "ExpiryPass123",
            },
        )
        token = registration.json()["sessionToken"]
        with sqlite3.connect(tmp_path / "auth" / "zhangwen-auth.sqlite3") as conn:
            conn.execute(
                "UPDATE auth_sessions SET expires_at = '2000-01-01T00:00:00+00:00'"
            )
        response = client.get(
            "/api/auth/session",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "AUTH_SESSION_INVALID"
