"""Privacy and size boundaries for frontend realtime channels."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


_SENSITIVE_KEY_PARTS = (
    "credential",
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "serial_number",
    "serialnumber",
    "port_id",
    "portid",
    "backup_path",
    "backuppath",
)
_MAX_PAYLOAD_BYTES = 16 * 1024
_MAX_STRING_CHARS = 512
_MAX_LIST_ITEMS = 64
_MAX_DEPTH = 5

_CREATOR_EVENT_TYPES = {
    "WORK_CREATED": "work.created",
    "COMMAND": "work.command.changed",
    "JOB": "work.task.changed",
    "PROJECTION": "work.projection.changed",
    "EVIDENCE": "work.evidence.changed",
    "DEVICE": "work.device.changed",
    "PROJECT_BOOK_GENERATED": "work.plan-document.generated",
}

_CREATOR_ALLOWED_KEYS = {
    "WORK_CREATED": {"origin"},
    "COMMAND": {"commandId", "command", "projectVersion"},
    "JOB": {
        "jobId",
        "kind",
        "status",
        "progress",
        "solutionRevisionId",
        "reason",
        "command",
        "error",
        "waiting",
    },
    "PROJECTION": {
        "source",
        "sourceMessageId",
        "sourceTurnId",
        "projectionReceiptId",
        "goalRevisionId",
        "sourcePlanId",
        "sourcePlanVersion",
    },
    "EVIDENCE": {"evidenceId", "kind", "passed"},
    "DEVICE": {"physicalRunId", "deploymentOperationId", "status"},
    "PROJECT_BOOK_GENERATED": {
        "bookId",
        "revision",
        "goalRevisionId",
        "solutionRevisionId",
        "generatedAt",
    },
}

_EVENT_ALLOWED_KEYS: dict[str, set[str]] = {
    "work.canvas.generation.changed": {
        "generationId",
        "status",
        "step",
        "progress",
        "errorCode",
        "retryable",
        "reason",
    },
    "work.canvas.generation.progress": {
        "generationId",
        "status",
        "completedStep",
        "nextStep",
        "progress",
    },
    "work.canvas.generated": {
        "generationId",
        "status",
        "canvasSpecId",
        "canvasRevision",
        "layoutRevision",
        "sceneSchemaVersion",
        "sceneKind",
        "reused",
        "imported",
        "progress",
    },
    "work.canvas.layout.changed": {
        "canvasSpecId",
        "layoutRevision",
        "changeKind",
    },
    "system.model-provider.configuration.changed": {
        "configurationId",
        "provider",
        "revisionId",
        "revision",
        "enabled",
        "changeKind",
    },
    "system.model-provider.credential.changed": {
        "configurationId",
        "providerConfigurationRevisionId",
        "configured",
    },
    "system.model-routing.changed": {
        "revisionId",
        "revision",
        "defaultProvider",
        "defaultModel",
        "fallbackConfigured",
        "workloadCount",
    },
    "system.model-privacy.changed": {
        "revisionId",
        "revision",
        "contextScope",
        "cloudTraceEnabled",
        "automaticFallbackEnabled",
    },
    "system.model-provider.test.changed": {
        "configurationId",
        "testId",
        "testedRevisionId",
        "status",
        "latencyMs",
        "errorCode",
    },
}


def creator_event_projection(
    event_type: str,
    payload: Mapping[str, Any],
) -> tuple[str, dict[str, Any]] | None:
    projected_type = _CREATOR_EVENT_TYPES.get(event_type)
    if projected_type is None:
        return None
    allowed = _CREATOR_ALLOWED_KEYS[event_type]
    projected = {
        key: value
        for key, value in payload.items()
        if key in allowed
    }
    projected["changeKind"] = event_type
    return projected_type, sanitize_payload(projected)


def sanitize_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    sanitized = _sanitize_mapping(payload, depth=0, reject_sensitive=False)
    encoded = json.dumps(
        sanitized,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(encoded) > _MAX_PAYLOAD_BYTES:
        raise ValueError("Realtime payload exceeds the bounded event size")
    return sanitized


def sanitize_event_payload(
    event_type: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply a positive field allowlist to security-sensitive event families."""

    allowed = _EVENT_ALLOWED_KEYS.get(event_type)
    projected = (
        {key: value for key, value in payload.items() if key in allowed}
        if allowed is not None
        else payload
    )
    return sanitize_payload(projected)


def validate_telemetry_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    sanitized = _sanitize_mapping(payload, depth=0, reject_sensitive=True)
    encoded = json.dumps(
        sanitized,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(encoded) > _MAX_PAYLOAD_BYTES:
        raise ValueError("Telemetry payload exceeds the bounded sample size")
    return sanitized


def _sanitize_mapping(
    payload: Mapping[str, Any],
    *,
    depth: int,
    reject_sensitive: bool,
) -> dict[str, Any]:
    if depth > _MAX_DEPTH:
        raise ValueError("Realtime payload nesting is too deep")
    result: dict[str, Any] = {}
    for raw_key, value in payload.items():
        key = str(raw_key)
        normalized = key.lower().replace("-", "_")
        if any(part in normalized for part in _SENSITIVE_KEY_PARTS):
            if reject_sensitive:
                raise ValueError("Telemetry payload contains a sensitive field")
            continue
        result[key[:128]] = _sanitize_value(
            value,
            depth=depth + 1,
            reject_sensitive=reject_sensitive,
        )
    return result


def _sanitize_value(value: Any, *, depth: int, reject_sensitive: bool) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:_MAX_STRING_CHARS]
    if isinstance(value, Mapping):
        return _sanitize_mapping(
            value,
            depth=depth,
            reject_sensitive=reject_sensitive,
        )
    if isinstance(value, (list, tuple)):
        if depth > _MAX_DEPTH:
            raise ValueError("Realtime payload nesting is too deep")
        return [
            _sanitize_value(
                item,
                depth=depth + 1,
                reject_sensitive=reject_sensitive,
            )
            for item in value[:_MAX_LIST_ITEMS]
        ]
    return str(value)[:_MAX_STRING_CHARS]
