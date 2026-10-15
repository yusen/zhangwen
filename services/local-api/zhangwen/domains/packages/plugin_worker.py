"""Trusted manifest interpreter used by the isolated M5 PluginHost sample."""

from __future__ import annotations

import hashlib
import json
import sys


MAX_INPUT_BYTES = 256 * 1024
MAX_OUTPUT_BYTES = 64 * 1024


def main() -> int:
    _apply_resource_limits()
    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        return _write_error(None, -32600, "request too large")
    try:
        request = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _write_error(None, -32700, "invalid json")
    request_id = request.get("id") if isinstance(request, dict) else None
    if (
        not isinstance(request, dict)
        or request.get("jsonrpc") != "2.0"
        or request.get("method") != "shadow.evaluate"
        or not isinstance(request.get("params"), dict)
    ):
        return _write_error(request_id, -32600, "invalid request")
    params = request["params"]
    allowed = {
        "packageId",
        "packageRevisionId",
        "contentDigest",
        "displayName",
        "capabilities",
        "input",
    }
    if set(params) - allowed:
        return _write_error(request_id, -32602, "unexpected params")
    encoded_input = json.dumps(
        params.get("input", {}),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    result = {
        "output": {
            "summary": f"{str(params.get('displayName', '能力包'))} 已完成无副作用回放。",
            "inputDigest": hashlib.sha256(encoded_input).hexdigest()[:24],
            "revisionDigest": str(params.get("contentDigest", ""))[:24],
            "capabilities": params.get("capabilities", []),
        },
        "toolPlan": [],
        "messages": ["可编辑包未被导入主进程；外部副作用能力已禁用。"],
    }
    response = {"jsonrpc": "2.0", "id": request_id, "result": result}
    encoded = json.dumps(response, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_OUTPUT_BYTES:
        return _write_error(request_id, -32000, "response too large")
    sys.stdout.buffer.write(encoded)
    return 0


def _write_error(request_id: object, code: int, message: str) -> int:
    response = {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }
    sys.stdout.write(json.dumps(response, separators=(",", ":")))
    return 2


def _apply_resource_limits() -> None:
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
        resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    except (ImportError, OSError, ValueError):
        return


if __name__ == "__main__":
    raise SystemExit(main())
