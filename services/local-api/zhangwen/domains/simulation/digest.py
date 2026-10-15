"""Canonical JSON and SHA-256 helpers for immutable simulation revisions."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from pydantic import BaseModel


def canonical_json(value: BaseModel | object) -> str:
    payload = (
        value.model_dump(by_alias=True, mode="json")
        if isinstance(value, BaseModel)
        else value
    )
    normalized = _normalize(payload)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_digest(value: BaseModel | object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        items = [_normalize(item) for item in value]
        if all(isinstance(item, str) for item in items):
            return sorted(items)
        if all(isinstance(item, dict) and "id" in item for item in items):
            return sorted(items, key=lambda item: str(item["id"]))
        if all(
            isinstance(item, dict) and {"instanceId", "pinId"}.issubset(item)
            for item in items
        ):
            return sorted(
                items,
                key=lambda item: (str(item["instanceId"]), str(item["pinId"])),
            )
        if all(isinstance(item, dict) and "path" in item for item in items):
            return sorted(items, key=lambda item: str(item["path"]))
        return items
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("simulation revisions cannot contain non-finite numbers")
        if value == 0:
            return 0
        if value.is_integer():
            return int(value)
    return value
