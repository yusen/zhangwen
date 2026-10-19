"""Versioned NDJSON protocol shared by the CAD worker and its parent."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


WORKER_PROTOCOL = "zhangwen.cad.worker"
WORKER_VERSION = 1
MAX_REQUEST_BYTES = 256 * 1024


class WorkerEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol: Literal["zhangwen.cad.worker"]
    version: Literal[1]
    jobId: str = Field(min_length=1, max_length=120)
    sequence: int = Field(ge=1)
    event: Literal["STARTED", "PROGRESS", "RESULT", "ERROR"]
    payload: dict[str, Any]


def canonical_json_bytes(value: BaseModel | dict[str, Any]) -> bytes:
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
