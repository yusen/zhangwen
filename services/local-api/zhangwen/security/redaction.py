"""日志和错误脱敏工具。"""

import re
from collections.abc import Mapping
from typing import Any

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE),
]

SECRET_KEYS = {
    "authorization",
    "api_key",
    "apikey",
    "token",
    "secret",
    "password",
    "credential",
}


def redact_text(value: str) -> str:
    """Mask likely API credentials in a string."""

    redacted = value
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def redact_mapping(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy with sensitive keys and string values redacted."""

    redacted: dict[str, Any] = {}
    for key, value in data.items():
        if key.lower() in SECRET_KEYS:
            redacted[key] = "[REDACTED]"
        elif isinstance(value, str):
            redacted[key] = redact_text(value)
        elif isinstance(value, Mapping):
            redacted[key] = redact_mapping(value)
        else:
            redacted[key] = value
    return redacted


def mask_api_key(api_key: str | None) -> str | None:
    """Return a display-safe API key mask."""

    if not api_key:
        return None
    if len(api_key) <= 8:
        return "****"
    return f"{api_key[:3]}****{api_key[-4:]}"
