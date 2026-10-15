"""Fail-closed source integrity and license inventory for project learning E10."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath


_ROOT = Path(__file__).resolve().parent
_MANIFEST_PATH = _ROOT / "release-integrity.json"
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_REQUIRED_IDS = {
    "MICROPYTHON_SOURCE_PIN",
    "BEHAVIORAL_REFERENCE_WORKER",
    "BEHAVIORAL_COMPONENT_BUS",
    "ESPRESSIF_QEMU_PIN",
    "COMPONENT_CATALOG",
    "ORIGINAL_BOARD_VISUAL",
    "ORIGINAL_COMPONENT_VISUAL",
    "ORIGINAL_ASSET_LICENSE_INDEX",
    "MICROPYTHON_LICENSE_NOTICE",
    "ESPRESSIF_QEMU_NOTICE",
}


class ReleaseIntegrityError(RuntimeError):
    """Raised when a pinned source/license input is missing or has drifted."""


def verify_release_integrity() -> dict[str, object]:
    """Verify source inputs without building, signing, installing, or publishing."""

    raw = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ReleaseIntegrityError("Release integrity manifest must be an object.")
    if raw.get("schema") != "zhangwen.project-learning-release-integrity/v1":
        raise ReleaseIntegrityError("Release integrity schema is unsupported.")
    if raw.get("packageBuilt") is not False:
        raise ReleaseIntegrityError("E10 source verification must not claim a package build.")
    if raw.get("packageBuildStatus") != "SKIPPED_BY_USER":
        raise ReleaseIntegrityError("The user-requested package skip is not recorded.")
    entries = raw.get("entries")
    if not isinstance(entries, list):
        raise ReleaseIntegrityError("Release integrity entries are missing.")

    verified: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    resolved_root = _ROOT.resolve()
    for value in entries:
        if not isinstance(value, dict):
            raise ReleaseIntegrityError("Release integrity entry must be an object.")
        entry_id = _required_text(value, "id")
        relative_text = _required_text(value, "path")
        expected_sha256 = _required_text(value, "sha256")
        _required_text(value, "spdx")
        _required_text(value, "source")
        _required_text(value, "version")
        _required_text(value, "distributionStatus")
        if entry_id in seen_ids or relative_text in seen_paths:
            raise ReleaseIntegrityError("Release integrity ids and paths must be unique.")
        seen_ids.add(entry_id)
        seen_paths.add(relative_text)
        relative = PurePosixPath(relative_text)
        if relative.is_absolute() or ".." in relative.parts or "\\" in relative_text:
            raise ReleaseIntegrityError(f"Unsafe release integrity path: {relative_text}")
        target = _ROOT.joinpath(*relative.parts).resolve()
        if not target.is_relative_to(resolved_root) or not target.is_file():
            raise ReleaseIntegrityError(f"Release integrity source is missing: {relative_text}")
        if _SHA256.fullmatch(expected_sha256) is None:
            raise ReleaseIntegrityError(f"Invalid SHA-256 for {entry_id}.")
        actual_sha256 = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual_sha256 != expected_sha256:
            raise ReleaseIntegrityError(f"Release integrity drift detected: {entry_id}")
        verified.append({**value, "integrity": "OK"})

    missing = sorted(_REQUIRED_IDS - seen_ids)
    if missing:
        raise ReleaseIntegrityError(f"Release integrity entries are missing: {', '.join(missing)}")
    _verify_nested_license_contracts()
    return {
        "schema": raw["schema"],
        "valid": True,
        "scope": raw.get("scope"),
        "packageBuilt": False,
        "packageBuildStatus": "SKIPPED_BY_USER",
        "entries": verified,
    }


def _verify_nested_license_contracts() -> None:
    runtime = json.loads(
        (_ROOT / "runtime" / "runtime-manifest.json").read_text(encoding="utf-8")
    )
    micropython = runtime.get("micropython", {})
    if (
        not isinstance(micropython, dict)
        or micropython.get("version") != "1.26.1"
        or micropython.get("licenseSpdx") != "MIT"
        or runtime.get("nativeDistributions") != []
        or runtime.get("behavioralReference", {}).get("evidenceEligible") is not False
    ):
        raise ReleaseIntegrityError("MicroPython/worker release boundary drifted.")
    qemu = json.loads((_ROOT / "qemu_manifest.json").read_text(encoding="utf-8"))
    if (
        qemu.get("upstreamRelease") != "esp-develop-9.2.2-20260417"
        or qemu.get("licenseSpdx") != "GPL-2.0-only"
    ):
        raise ReleaseIntegrityError("Espressif QEMU release boundary drifted.")
    asset_licenses = json.loads(
        (_ROOT / "catalog" / "licenses.json").read_text(encoding="utf-8")
    )
    licensed_paths = {
        str(item.get("path"))
        for item in asset_licenses.get("entries", [])
        if isinstance(item, dict)
    }
    if licensed_paths != {"reference-boards.svg", "component-symbols.svg"}:
        raise ReleaseIntegrityError("Original visual asset license index drifted.")


def _required_text(value: dict[str, object], key: str) -> str:
    candidate = value.get(key)
    if not isinstance(candidate, str) or not candidate.strip():
        raise ReleaseIntegrityError(f"Release integrity entry field is missing: {key}")
    return candidate

