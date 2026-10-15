"""Trusted bounded worker for package manifest and static-safety validation."""

from __future__ import annotations

import json
import sys
from pathlib import Path


MAX_REQUEST_BYTES = 768 * 1024
MAX_OUTPUT_BYTES = 128 * 1024


def main() -> int:
    _apply_resource_limits()
    raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
    if len(raw) > MAX_REQUEST_BYTES:
        return _write_error("request too large")
    try:
        request = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _write_error("invalid json")
    if not isinstance(request, dict) or set(request) != {"package", "files"}:
        return _write_error("invalid request")

    # -I removes ambient import paths. Only this checked-in service root is
    # restored so the worker can load trusted contracts and static validators.
    service_root = str(Path(__file__).resolve().parents[3])
    sys.path.insert(0, service_root)
    try:
        from zhangwen.domains.packages.models import CapabilityPackage
        from zhangwen.domains.packages.validation import validate_package_files

        package = CapabilityPackage.model_validate(request["package"])
        raw_files = request["files"]
        if not isinstance(raw_files, dict):
            raise ValueError("files must be an object")
        files = {str(path): str(content) for path, content in raw_files.items()}
        _, summary = validate_package_files(package, files)
        response = summary.model_dump(mode="json", by_alias=True)
    except (ImportError, TypeError, ValueError) as exc:
        return _write_error(str(exc)[:300])
    encoded = json.dumps(
        response,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(encoded) > MAX_OUTPUT_BYTES:
        return _write_error("response too large")
    sys.stdout.buffer.write(encoded)
    return 0


def _write_error(message: str) -> int:
    sys.stdout.write(json.dumps({"error": message}, separators=(",", ":")))
    return 2


def _apply_resource_limits() -> None:
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (384 * 1024 * 1024, 384 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CPU, (4, 4))
        resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    except (ImportError, OSError, ValueError):
        return


if __name__ == "__main__":
    raise SystemExit(main())
