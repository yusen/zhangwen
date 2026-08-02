from __future__ import annotations

import os
import re
import time
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from zhangwen_cloud_auth.config import CloudAuthSettings
from zhangwen_cloud_auth.database import Database
from zhangwen_cloud_auth.mailer import SmtpMailer
from zhangwen_cloud_auth.main import create_app
from zhangwen_cloud_auth.service import CloudAuthService


DATABASE_URL = os.environ.get("ZHANGWEN_CLOUD_AUTH_INTEGRATION_DATABASE_URL", "")
MAILPIT_URL = os.environ.get("ZHANGWEN_CLOUD_AUTH_INTEGRATION_MAILPIT_URL", "")
INTEGRATION_ENABLED = DATABASE_URL.startswith("postgresql://") and bool(MAILPIT_URL)


@pytest.mark.skipif(
    not INTEGRATION_ENABLED,
    reason="需要显式配置隔离的 PostgreSQL 与 Mailpit 集成环境。",
)
def test_postgres_registration_delivers_mailpit_code_and_verifies_email() -> None:
    settings = CloudAuthSettings(
        database_url=DATABASE_URL,
        secret="integration-secret-that-is-longer-than-thirty-two-characters",
        smtp_host=os.environ.get("ZHANGWEN_CLOUD_AUTH_SMTP_HOST", "127.0.0.1"),
        smtp_port=int(os.environ.get("ZHANGWEN_CLOUD_AUTH_SMTP_PORT", "1025")),
        smtp_from="掌问集成测试 <no-reply@example.invalid>",
        smtp_starttls=False,
        smtp_username=None,
        smtp_password=None,
    )
    service = CloudAuthService(
        database=Database(settings.database_url),
        mailer=SmtpMailer(settings),
        secret=settings.secret,
    )
    client = TestClient(create_app(service))
    email = f"integration-{uuid.uuid4().hex}@example.invalid"

    registered = client.post(
        "/v1/auth/register",
        json={
            "email": email,
            "displayName": "集成测试",
            "password": "IntegrationPass123",
        },
    )
    assert registered.status_code == 201

    code = _mailpit_code(email)
    verified = client.post(
        "/v1/auth/verify-email",
        json={
            "challengeId": registered.json()["challengeId"],
            "code": code,
            "deviceId": "integration-desktop-device",
        },
    )
    assert verified.status_code == 200
    assert verified.json()["account"]["email"] == email


def _mailpit_code(email: str) -> str:
    deadline = time.monotonic() + 10
    with httpx.Client(base_url=MAILPIT_URL, timeout=3) as client:
        while time.monotonic() < deadline:
            search = client.get("/api/v1/search", params={"query": f"to:{email}"})
            search.raise_for_status()
            messages = search.json().get("messages", [])
            if messages:
                message_id = messages[0].get("ID") or messages[0].get("Id")
                detail = client.get(f"/api/v1/message/{message_id}")
                detail.raise_for_status()
                body = detail.json()
                text = str(body.get("Text") or body.get("text") or "")
                match = re.search(r"(?<!\d)(\d{6})(?!\d)", text)
                if match:
                    return match.group(1)
            time.sleep(0.2)
    raise AssertionError(f"Mailpit 未在 10 秒内收到 {email} 的六位验证码。")
