from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from zhangwen_cloud_auth.database import Database
from zhangwen_cloud_auth.mailer import MemoryMailer
from zhangwen_cloud_auth.main import create_app
from zhangwen_cloud_auth.service import CloudAuthService


SECRET = "test-secret-that-is-longer-than-thirty-two-characters"


def _client(tmp_path: Path):
    mailer = MemoryMailer()
    service = CloudAuthService(
        database=Database(f"sqlite:///{tmp_path / 'cloud-auth.sqlite3'}"),
        mailer=mailer,
        secret=SECRET,
        code_generator=lambda: "123456",
    )
    return TestClient(create_app(service)), service, mailer


def _register_and_verify(client: TestClient, mailer: MemoryMailer):
    registration = client.post(
        "/v1/auth/register",
        json={
            "email": "teacher@example.com",
            "displayName": "林老师",
            "password": "TeacherPass123",
        },
    )
    assert registration.status_code == 201
    assert mailer.sent[-1].code == "123456"
    verified = client.post(
        "/v1/auth/verify-email",
        json={
            "challengeId": registration.json()["challengeId"],
            "code": "123456",
            "deviceId": "desktop-device-001",
        },
    )
    assert verified.status_code == 200
    return verified.json()


def test_register_verify_login_profile_refresh_and_logout(tmp_path: Path) -> None:
    client, _service, mailer = _client(tmp_path)
    tokens = _register_and_verify(client, mailer)
    assert tokens["account"]["email"] == "teacher@example.com"
    assert tokens["account"]["emailVerified"] is True
    assert tokens["refreshToken"] not in (tmp_path / "cloud-auth.sqlite3").read_bytes().decode("latin1")

    headers = {"Authorization": f"Bearer {tokens['accessToken']}"}
    empty_profile = client.get("/v1/me/profile", headers=headers)
    assert empty_profile.status_code == 200
    assert empty_profile.json()["profile"]["completed"] is False

    updated = client.patch(
        "/v1/me/profile",
        headers=headers,
        json={
            "persona": "TEACHER",
            "technicalLevel": "BEGINNER",
            "preferredBoards": ["unihiker_k10"],
            "budgetPreference": "BALANCED",
            "needsLesson": True,
            "completed": False,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["profile"]["completed"] is True

    refreshed = client.post(
        "/v1/auth/refresh",
        json={"refreshToken": tokens["refreshToken"], "deviceId": "desktop-device-001"},
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["refreshToken"] != tokens["refreshToken"]

    reused = client.post(
        "/v1/auth/refresh",
        json={"refreshToken": tokens["refreshToken"], "deviceId": "desktop-device-001"},
    )
    assert reused.status_code == 401
    assert reused.json()["detail"]["code"] == "REFRESH_TOKEN_REUSED"

    login = client.post(
        "/v1/auth/login",
        json={
            "email": "teacher@example.com",
            "password": "TeacherPass123",
            "deviceId": "desktop-device-001",
        },
    )
    assert login.status_code == 200
    logout_tokens = login.json()
    logout = client.post(
        "/v1/auth/logout",
        headers={"Authorization": f"Bearer {logout_tokens['accessToken']}"},
        json={"refreshToken": logout_tokens["refreshToken"]},
    )
    assert logout.status_code == 200


def test_verification_is_single_use_and_password_reset_is_enumeration_safe(tmp_path: Path) -> None:
    client, _service, mailer = _client(tmp_path)
    registration = client.post(
        "/v1/auth/register",
        json={
            "email": "maker@example.com",
            "displayName": "创客",
            "password": "MakerPass123",
        },
    )
    challenge_id = registration.json()["challengeId"]
    first = client.post(
        "/v1/auth/verify-email",
        json={"challengeId": challenge_id, "code": "123456", "deviceId": "desktop-device-002"},
    )
    second = client.post(
        "/v1/auth/verify-email",
        json={"challengeId": challenge_id, "code": "123456", "deviceId": "desktop-device-002"},
    )
    assert first.status_code == 200
    assert second.status_code == 422

    known = client.post("/v1/auth/password-reset/request", json={"email": "maker@example.com"})
    unknown = client.post("/v1/auth/password-reset/request", json={"email": "missing@example.com"})
    assert known.status_code == unknown.status_code == 200
    assert known.json()["message"] == unknown.json()["message"]
    reset_code = mailer.sent[-1]
    assert reset_code.purpose == "PASSWORD_RESET"

    reset = client.post(
        "/v1/auth/password-reset/confirm",
        json={
            "challengeId": known.json()["challengeId"],
            "code": reset_code.code,
            "newPassword": "UpdatedPass456",
        },
    )
    assert reset.status_code == 200
    assert client.post(
        "/v1/auth/login",
        json={
            "email": "maker@example.com",
            "password": "MakerPass123",
            "deviceId": "desktop-device-002",
        },
    ).status_code == 401
    assert client.post(
        "/v1/auth/login",
        json={
            "email": "maker@example.com",
            "password": "UpdatedPass456",
            "deviceId": "desktop-device-002",
        },
    ).status_code == 200


def test_expired_verification_and_rate_limit(tmp_path: Path) -> None:
    mailer = MemoryMailer()
    current = datetime(2026, 7, 25, tzinfo=UTC)
    service = CloudAuthService(
        database=Database(f"sqlite:///{tmp_path / 'cloud-auth.sqlite3'}"),
        mailer=mailer,
        secret=SECRET,
        code_generator=lambda: "123456",
        clock=lambda: current,
    )
    client = TestClient(create_app(service))
    registration = client.post(
        "/v1/auth/register",
        json={
            "email": "expiry@example.com",
            "displayName": "过期",
            "password": "ExpiryPass123",
        },
    )
    service.clock = lambda: current + timedelta(minutes=11)
    expired = client.post(
        "/v1/auth/verify-email",
        json={
            "challengeId": registration.json()["challengeId"],
            "code": "123456",
            "deviceId": "desktop-device-003",
        },
    )
    assert expired.status_code == 422

    for index in range(5):
        response = client.post(
            "/v1/auth/register",
            json={
                "email": f"rate-{index}@example.com",
                "displayName": "限流",
                "password": "RateLimit123",
            },
        )
        assert response.status_code == 201
    limited = client.post(
        "/v1/auth/register",
        json={
            "email": "rate-final@example.com",
            "displayName": "限流",
            "password": "RateLimit123",
        },
    )
    assert limited.status_code == 429
