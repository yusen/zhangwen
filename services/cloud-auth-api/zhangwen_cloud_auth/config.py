from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class CloudAuthSettings:
    database_url: str
    secret: str
    smtp_host: str
    smtp_port: int
    smtp_from: str
    smtp_starttls: bool
    smtp_username: str | None
    smtp_password: str | None

    @classmethod
    def from_environment(cls) -> "CloudAuthSettings":
        secret = os.environ.get("ZHANGWEN_CLOUD_AUTH_SECRET", "").strip()
        if len(secret) < 32:
            raise RuntimeError("ZHANGWEN_CLOUD_AUTH_SECRET 至少需要 32 个字符。")
        return cls(
            database_url=os.environ.get(
                "ZHANGWEN_CLOUD_AUTH_DATABASE_URL",
                "postgresql://zhangwen:change-me@127.0.0.1:5432/zhangwen_auth",
            ),
            secret=secret,
            smtp_host=os.environ.get("ZHANGWEN_CLOUD_AUTH_SMTP_HOST", "127.0.0.1"),
            smtp_port=int(os.environ.get("ZHANGWEN_CLOUD_AUTH_SMTP_PORT", "1025")),
            smtp_from=os.environ.get(
                "ZHANGWEN_CLOUD_AUTH_SMTP_FROM",
                "掌问 <no-reply@example.invalid>",
            ),
            smtp_starttls=_boolean("ZHANGWEN_CLOUD_AUTH_SMTP_STARTTLS"),
            smtp_username=os.environ.get("ZHANGWEN_CLOUD_AUTH_SMTP_USERNAME") or None,
            smtp_password=os.environ.get("ZHANGWEN_CLOUD_AUTH_SMTP_PASSWORD") or None,
        )


def _boolean(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}
