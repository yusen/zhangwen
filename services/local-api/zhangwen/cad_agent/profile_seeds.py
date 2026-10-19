"""Built-in, reviewed mechanical profile seeds for the deterministic CAD engine."""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

from zhangwen.cad_engine.models import HardwareProfile
from zhangwen.cad_engine.profiles import trusted_profiles


PROFILE_SCHEMA_VERSION = "1.0"
PROFILE_EVIDENCE_LEVEL = "TRUSTED"
PROFILE_REPRESENTATION = "parametric_envelope"


def builtin_profiles() -> tuple[HardwareProfile, ...]:
    """Return fresh immutable instances of every reviewed built-in profile."""

    return trusted_profiles()


def canonical_profile_payload(profile: HardwareProfile) -> dict[str, Any]:
    """Build the hash input; no executable/path/network fields are included."""

    payload = {
        "schema_version": PROFILE_SCHEMA_VERSION,
        **profile.model_dump(mode="json"),
        "evidence_level": PROFILE_EVIDENCE_LEVEL,
        "representation": PROFILE_REPRESENTATION,
    }
    return normalize_profile_snapshot_payload(payload)


def normalize_profile_snapshot_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Keep schema 1.0 hashes stable when newly modeled fields use legacy defaults."""

    normalized = json.loads(json.dumps(payload, ensure_ascii=False))
    preview_geometry = normalized.get("preview_geometry")
    if preview_geometry is None:
        normalized.pop("preview_geometry", None)
    elif isinstance(preview_geometry, dict) and preview_geometry.get("source_sha256") is None:
        preview_geometry.pop("source_sha256", None)
    mounting = normalized.get("mounting")
    if isinstance(mounting, dict) and mounting.get("strategy") == "none":
        mounting.pop("strategy", None)
    openings = normalized.get("openings")
    if isinstance(openings, list):
        for opening in openings:
            if isinstance(opening, dict) and float(opening.get("center_z", 0.0)) == 0.0:
                opening.pop("center_z", None)
    return normalized


def canonical_profile_bytes(profile: HardwareProfile) -> bytes:
    return json.dumps(
        canonical_profile_payload(profile),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def profile_content_sha256(profile: HardwareProfile) -> str:
    return sha256(canonical_profile_bytes(profile)).hexdigest()


def profile_snapshot(profile: HardwareProfile) -> dict[str, Any]:
    """Return the server-owned snapshot sent to a worker and persisted in a Job."""

    payload = canonical_profile_payload(profile)
    payload["content_sha256"] = profile_content_sha256(profile)
    return payload


def profile_seed(profile_id: str) -> dict[str, Any]:
    for profile in builtin_profiles():
        if profile.profile_id == profile_id:
            return profile_snapshot(profile)
    raise KeyError(f"unknown built-in mechanical profile: {profile_id}")
