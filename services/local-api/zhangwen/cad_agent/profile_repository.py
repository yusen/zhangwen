"""Versioned mechanical profile storage and exact hardware linking."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Literal

from pydantic import Field, model_validator

from zhangwen.cad_agent.profile_seeds import (
    PROFILE_EVIDENCE_LEVEL,
    PROFILE_REPRESENTATION,
    PROFILE_SCHEMA_VERSION,
    builtin_profiles,
    profile_snapshot,
    normalize_profile_snapshot_payload,
)
from zhangwen.cad_engine.models import HardwareProfile


K10_PROFILE_ALIASES = {
    "hw_seed_unihiker_k10": "unihiker_k10",
    "hw_seeed_xiao_esp32s3_sense": "xiao_esp32s3",
}


class MechanicalProfileSnapshot(HardwareProfile):
    """Strict, self-verifying snapshot persisted in a CadBuildSpec."""

    schema_version: Literal["1.0"] = PROFILE_SCHEMA_VERSION
    evidence_level: Literal["TRUSTED", "CONFIRMED"]
    representation: Literal["parametric_envelope", "envelope_only"]
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_content_hash(self) -> "MechanicalProfileSnapshot":
        payload = self.model_dump(mode="json")
        payload.pop("content_sha256", None)
        payload = normalize_profile_snapshot_payload(payload)
        digest = hashlib.sha256(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        if digest != self.content_sha256:
            raise ValueError("mechanical profile content hash does not match snapshot")
        return self

    @classmethod
    def from_profile(cls, profile: HardwareProfile) -> "MechanicalProfileSnapshot":
        return cls.model_validate(profile_snapshot(profile))

    def to_profile(self) -> HardwareProfile:
        payload = self.model_dump(mode="python")
        for key in ("schema_version", "evidence_level", "representation", "content_sha256"):
            payload.pop(key, None)
        return HardwareProfile.model_validate(payload)


class MechanicalProfileRepository:
    """Read/write boundary for immutable mechanical profile versions."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)

    def seed_builtin_profiles(self, *, now: str | None = None) -> None:
        timestamp = now or datetime.now(UTC).isoformat()
        with self._connect() as conn:
            for profile in builtin_profiles():
                snapshot = MechanicalProfileSnapshot.from_profile(profile)
                existing = conn.execute(
                    """
                    SELECT profile_json, content_sha256
                    FROM mechanical_profile_versions
                    WHERE profile_id = ? AND revision = ?
                    """,
                    (profile.profile_id, profile.revision),
                ).fetchone()
                if existing is not None:
                    stored_snapshot = MechanicalProfileSnapshot.model_validate_json(
                        existing["profile_json"]
                    )
                    stored_hash = str(existing["content_sha256"])
                    if stored_snapshot.content_sha256 != stored_hash:
                        raise ValueError(
                            "stored mechanical profile hash does not match database metadata"
                        )
                    if stored_hash != snapshot.content_sha256:
                        raise ValueError(
                            f"mechanical profile is immutable but changed: {profile.profile_id}:{profile.revision}"
                        )
                    continue
                row_id = f"mechanical_profile_{profile.profile_id}_{profile.revision}"
                conn.execute(
                    """
                    INSERT INTO mechanical_profile_versions (
                      id, profile_id, revision, schema_version, display_name,
                      source, evidence_level, representation, profile_json,
                      content_sha256, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row_id,
                        profile.profile_id,
                        profile.revision,
                        PROFILE_SCHEMA_VERSION,
                        profile.display_name,
                        profile.source.value,
                        PROFILE_EVIDENCE_LEVEL,
                        PROFILE_REPRESENTATION,
                        json.dumps(
                            snapshot.model_dump(mode="json"),
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                        snapshot.content_sha256,
                        timestamp,
                    ),
                )

    def get(
        self,
        profile_id: str,
        *,
        revision: str | None = None,
    ) -> MechanicalProfileSnapshot:
        canonical_id = canonical_profile_id(profile_id)
        with self._connect() as conn:
            if revision is None:
                row = conn.execute(
                    """
                    SELECT * FROM mechanical_profile_versions
                    WHERE profile_id = ?
                    ORDER BY created_at DESC, revision DESC
                    LIMIT 1
                    """,
                    (canonical_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT * FROM mechanical_profile_versions
                    WHERE profile_id = ? AND revision = ?
                    """,
                    (canonical_id, revision),
                ).fetchone()
        if row is None:
            raise KeyError(f"unknown mechanical profile: {canonical_id}:{revision or '*'}")
        snapshot = MechanicalProfileSnapshot.model_validate_json(row["profile_json"])
        if snapshot.content_sha256 != str(row["content_sha256"]):
            raise ValueError("stored mechanical profile hash does not match database metadata")
        return snapshot

    def resolve_for_hardware(self, hardware_component_id: str) -> MechanicalProfileSnapshot:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT mechanical_profile_id, mechanical_profile_revision
                FROM hardware_mechanical_links
                WHERE hardware_component_id = ? AND confirmed_at IS NOT NULL
                ORDER BY updated_at DESC
                """,
                (hardware_component_id,),
            ).fetchall()
        if not rows and hardware_component_id in K10_PROFILE_ALIASES:
            return self.get(K10_PROFILE_ALIASES[hardware_component_id])
        if not rows:
            raise KeyError(f"no confirmed mechanical profile link: {hardware_component_id}")
        if len(rows) > 1:
            raise ValueError(f"ambiguous confirmed mechanical profile link: {hardware_component_id}")
        return self.get(
            str(rows[0]["mechanical_profile_id"]),
            revision=str(rows[0]["mechanical_profile_revision"]),
        )

    def list_with_confirmed_hardware(
        self,
    ) -> list[tuple[MechanicalProfileSnapshot, tuple[str, ...], tuple[str, ...]]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT profile_id, revision, profile_json, content_sha256,
                       created_at
                FROM mechanical_profile_versions
                ORDER BY profile_id, created_at DESC, revision DESC
                """
            ).fetchall()
            link_rows = conn.execute(
                """
                SELECT hardware_component_id, mechanical_profile_id,
                       mechanical_profile_revision
                FROM hardware_mechanical_links
                WHERE confirmed_at IS NOT NULL
                ORDER BY hardware_component_id
                """
            ).fetchall()
        linked: dict[tuple[str, str], list[str]] = {}
        for row in link_rows:
            linked.setdefault(
                (str(row["mechanical_profile_id"]), str(row["mechanical_profile_revision"])),
                [],
            ).append(str(row["hardware_component_id"]))
        linked_profile_ids = {profile_id for profile_id, _revision in linked}
        selected_keys = set(linked)
        for row in rows:
            profile_id = str(row["profile_id"])
            if profile_id in linked_profile_ids:
                continue
            selected_keys.add((profile_id, str(row["revision"])))
            linked_profile_ids.add(profile_id)
        implicit_k10_key: tuple[str, str] | None = None
        if not any(
            "hw_seed_unihiker_k10" in hardware_ids
            for hardware_ids in linked.values()
        ):
            try:
                fallback_k10 = self.get("unihiker_k10")
                implicit_k10_key = (
                    fallback_k10.profile_id,
                    fallback_k10.revision,
                )
            except KeyError:
                implicit_k10_key = None
        result = []
        for row in rows:
            snapshot = MechanicalProfileSnapshot.model_validate_json(row["profile_json"])
            if snapshot.content_sha256 != str(row["content_sha256"]):
                raise ValueError("stored mechanical profile hash does not match database metadata")
            key = (snapshot.profile_id, snapshot.revision)
            if key not in selected_keys:
                continue
            hardware_ids = list(linked.get(key, ()))
            locked: list[str] = []
            if key == implicit_k10_key:
                hardware_ids.append("hw_seed_unihiker_k10")
            if "hw_seed_unihiker_k10" in hardware_ids:
                locked.append("hw_seed_unihiker_k10")
            result.append((snapshot, tuple(hardware_ids), tuple(locked)))
        return sorted(
            result,
            key=lambda item: (item[0].display_name.casefold(), item[0].profile_id),
        )

    def confirm_hardware_link(
        self,
        hardware_component_id: str,
        *,
        profile_id: str,
        revision: str,
        now: str | None = None,
    ) -> MechanicalProfileSnapshot:
        snapshot = self.get(profile_id, revision=revision)
        timestamp = now or datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            component = conn.execute(
                "SELECT id FROM hardware_components WHERE id = ? AND status != 'ARCHIVED'",
                (hardware_component_id,),
            ).fetchone()
            if component is None:
                raise KeyError(f"unknown active hardware component: {hardware_component_id}")
            conn.execute(
                """
                UPDATE hardware_mechanical_links
                SET confirmed_at = NULL, updated_at = ?
                WHERE hardware_component_id = ? AND confirmed_at IS NOT NULL
                """,
                (timestamp, hardware_component_id),
            )
            link_id = f"mechanical_link_{hardware_component_id}_{snapshot.profile_id}"
            conn.execute(
                """
                INSERT INTO hardware_mechanical_links (
                  id, hardware_component_id, mechanical_profile_id,
                  mechanical_profile_revision, evidence_level, confirmed_at,
                  created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(hardware_component_id, mechanical_profile_id) DO UPDATE SET
                  mechanical_profile_revision = excluded.mechanical_profile_revision,
                  evidence_level = excluded.evidence_level,
                  confirmed_at = excluded.confirmed_at,
                  updated_at = excluded.updated_at
                """,
                (
                    link_id,
                    hardware_component_id,
                    snapshot.profile_id,
                    snapshot.revision,
                    snapshot.evidence_level,
                    timestamp,
                    timestamp,
                    timestamp,
                ),
            )
        return snapshot

    def remove_hardware_link(
        self,
        hardware_component_id: str,
        *,
        now: str | None = None,
    ) -> bool:
        if hardware_component_id in K10_PROFILE_ALIASES:
            raise ValueError("the built-in controller mechanical profile link is locked")
        timestamp = now or datetime.now(UTC).isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE hardware_mechanical_links
                SET confirmed_at = NULL, updated_at = ?
                WHERE hardware_component_id = ? AND confirmed_at IS NOT NULL
                """,
                (timestamp, hardware_component_id),
            )
        return cursor.rowcount > 0

    def snapshot_for_exact_id(self, profile_id: str, revision: str | None = None) -> MechanicalProfileSnapshot:
        """Resolve only an explicit profile ID; names and roles are never searched."""

        return self.get(profile_id, revision=revision)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


def canonical_profile_id(profile_id: str) -> str:
    if profile_id in K10_PROFILE_ALIASES:
        return K10_PROFILE_ALIASES[profile_id]
    if not profile_id or not profile_id[0].islower() or any(
        character not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for character in profile_id
    ):
        raise ValueError(f"invalid mechanical profile identifier: {profile_id}")
    return profile_id


def seed_builtin_mechanical_profiles(db_path: Path, *, now: str | None = None) -> None:
    MechanicalProfileRepository(db_path).seed_builtin_profiles(now=now)


__all__ = [
    "K10_PROFILE_ALIASES",
    "MechanicalProfileRepository",
    "MechanicalProfileSnapshot",
    "canonical_profile_id",
    "seed_builtin_mechanical_profiles",
]
