from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from argon2.low_level import Type


ACCESS_LIFETIME = timedelta(minutes=15)
REFRESH_LIFETIME = timedelta(days=30)
OFFLINE_LEASE_LIFETIME = timedelta(days=30)
CHALLENGE_LIFETIME = timedelta(minutes=10)


class PasswordSecurity:
    def __init__(self) -> None:
        self._hasher = PasswordHasher(
            time_cost=3,
            memory_cost=65536,
            parallelism=2,
            hash_len=32,
            salt_len=16,
            type=Type.ID,
        )
        self._dummy_hash = self._hasher.hash("zhangwen-dummy-password-2026")

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password_hash: str | None, password: str) -> bool:
        candidate = password_hash or self._dummy_hash
        try:
            verified = self._hasher.verify(candidate, password)
        except VerifyMismatchError:
            return False
        return bool(password_hash) and verified


def random_token() -> str:
    return secrets.token_urlsafe(32)


def verification_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def secure_hash(secret: str, purpose: str, value: str) -> str:
    payload = f"{purpose}:{value}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def now() -> datetime:
    return datetime.now(UTC)


def iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()
