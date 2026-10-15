"""Redaction for versioned Package Studio replay inputs."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


_SENSITIVE_KEYS = (
    "credential",
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "serial_number",
    "port_id",
    "backup_path",
)
_TEXT_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"(?i)(password|api[_-]?key|secret|token)\s*[:=]\s*\S+"),
    re.compile(r"(?i)\bCOM\d{1,4}\b"),
)


def redact_replay_input(value: Any) -> tuple[Any, bool]:
    redacted = False

    def visit(item: Any, depth: int = 0) -> Any:
        nonlocal redacted
        if depth > 8:
            redacted = True
            return "[TRUNCATED]"
        if isinstance(item, Mapping):
            result: dict[str, Any] = {}
            for raw_key, child in item.items():
                key = str(raw_key)[:160]
                normalized = key.lower().replace("-", "_")
                if any(part in normalized for part in _SENSITIVE_KEYS):
                    result[key] = "[REDACTED]"
                    redacted = True
                else:
                    result[key] = visit(child, depth + 1)
            return result
        if isinstance(item, (list, tuple)):
            if len(item) > 256:
                redacted = True
            return [visit(child, depth + 1) for child in item[:256]]
        if isinstance(item, str):
            text = item[:8_000]
            if len(item) > len(text):
                redacted = True
            for pattern in _TEXT_PATTERNS:
                next_text = pattern.sub("[REDACTED]", text)
                if next_text != text:
                    redacted = True
                    text = next_text
            return text
        if item is None or isinstance(item, (bool, int, float)):
            return item
        redacted = True
        return str(item)[:1000]

    return visit(value), redacted
