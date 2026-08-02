from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

from zhangwen_cloud_auth.config import CloudAuthSettings


class Mailer(Protocol):
    def send_code(self, *, email: str, code: str, purpose: str) -> None: ...


class SmtpMailer:
    def __init__(self, settings: CloudAuthSettings) -> None:
        self._settings = settings

    def send_code(self, *, email: str, code: str, purpose: str) -> None:
        subject = "验证掌问邮箱" if purpose == "VERIFY_EMAIL" else "重置掌问密码"
        message = EmailMessage()
        message["From"] = self._settings.smtp_from
        message["To"] = email
        message["Subject"] = subject
        message.set_content(
            f"你的掌问验证码是：{code}\n\n验证码 10 分钟内有效，且只能使用一次。"
            "如果不是你本人操作，请忽略此邮件。"
        )
        with smtplib.SMTP(self._settings.smtp_host, self._settings.smtp_port, timeout=10) as smtp:
            if self._settings.smtp_starttls:
                smtp.starttls()
            if self._settings.smtp_username:
                smtp.login(
                    self._settings.smtp_username,
                    self._settings.smtp_password or "",
                )
            smtp.send_message(message)


@dataclass
class SentCode:
    email: str
    code: str
    purpose: str


class MemoryMailer:
    def __init__(self) -> None:
        self.sent: list[SentCode] = []

    def send_code(self, *, email: str, code: str, purpose: str) -> None:
        self.sent.append(SentCode(email=email, code=code, purpose=purpose))
