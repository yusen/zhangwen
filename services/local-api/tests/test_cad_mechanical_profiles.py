from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import pytest
from pydantic import ValidationError

from zhangwen.cad_agent.profile_repository import (
    MechanicalProfileRepository,
    MechanicalProfileSnapshot,
    canonical_profile_id,
)


def create_profile_tables(database: Path) -> None:
    with sqlite3.connect(database) as conn:
        conn.executescript(
            """
            CREATE TABLE hardware_components (id TEXT PRIMARY KEY);
            CREATE TABLE mechanical_profile_versions (
              id TEXT PRIMARY KEY,
              profile_id TEXT NOT NULL,
              revision TEXT NOT NULL,
              schema_version TEXT NOT NULL,
              display_name TEXT NOT NULL,
              source TEXT NOT NULL,
              evidence_level TEXT NOT NULL,
              representation TEXT NOT NULL,
              profile_json TEXT NOT NULL,
              content_sha256 TEXT NOT NULL,
              created_at TEXT NOT NULL,
              UNIQUE(profile_id, revision)
            );
            CREATE TABLE hardware_mechanical_links (
              id TEXT PRIMARY KEY,
              hardware_component_id TEXT NOT NULL REFERENCES hardware_components(id),
              mechanical_profile_id TEXT NOT NULL,
              mechanical_profile_revision TEXT NOT NULL,
              evidence_level TEXT NOT NULL,
              confirmed_at TEXT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE(hardware_component_id, mechanical_profile_id),
              FOREIGN KEY(mechanical_profile_id, mechanical_profile_revision)
                REFERENCES mechanical_profile_versions(profile_id, revision)
            );
            """
        )


def test_builtin_profiles_are_strict_hashed_and_idempotent(tmp_path: Path) -> None:
    database = tmp_path / "profiles.sqlite3"
    create_profile_tables(database)
    repository = MechanicalProfileRepository(database)

    repository.seed_builtin_profiles(now="2026-07-13T00:00:00+00:00")
    repository.seed_builtin_profiles(now="2026-07-14T00:00:00+00:00")

    k10 = repository.get("unihiker_k10")
    ultrasonic = repository.get("unihiker_ultrasonic_distance_sensor")
    xiao = repository.get("xiao_esp32s3")
    oled = repository.get("grove_oled_096")
    button = repository.get("grove_button")
    assert k10.dimensions.model_dump() == {
        "length_x": 83.2,
        "width_y": 51.3,
        "height_z": 10.6,
    }
    assert ultrasonic.dimensions.model_dump() == {
        "length_x": 22.0,
        "width_y": 47.0,
        "height_z": 20.3,
    }
    assert [opening.diameter for opening in ultrasonic.openings] == [17.4, 17.4]
    assert [opening.center.y for opening in ultrasonic.openings] == [-10.75, 10.75]
    assert len(ultrasonic.mounting.holes) == 4
    assert {hole.fastener for hole in ultrasonic.mounting.holes} == {"M3"}
    assert len(ultrasonic.content_sha256) == 64
    assert xiao.mounting.strategy.value == "edge_retainer"
    assert xiao.openings[0].center_z == 2.4
    assert xiao.openings[0].size_u == 10.0
    assert len(oled.mounting.holes) == 3
    assert (oled.openings[0].size_u, oled.openings[0].size_v) == (26.0, 14.5)
    assert len(button.mounting.holes) == 2
    assert button.openings[0].diameter == 9.0

    with sqlite3.connect(database) as conn:
        assert conn.execute("SELECT COUNT(*) FROM mechanical_profile_versions").fetchone()[0] == 5


def test_idempotent_seed_revalidates_the_stored_snapshot(tmp_path: Path) -> None:
    database = tmp_path / "profiles.sqlite3"
    create_profile_tables(database)
    repository = MechanicalProfileRepository(database)
    repository.seed_builtin_profiles(now="2026-07-13T00:00:00+00:00")
    with sqlite3.connect(database) as conn:
        raw = json.loads(
            conn.execute(
                "SELECT profile_json FROM mechanical_profile_versions WHERE profile_id = 'unihiker_k10'"
            ).fetchone()[0]
        )
        raw["display_name"] = "tampered"
        conn.execute(
            "UPDATE mechanical_profile_versions SET profile_json = ? WHERE profile_id = 'unihiker_k10'",
            (json.dumps(raw),),
        )

    with pytest.raises(ValidationError, match="content hash"):
        repository.seed_builtin_profiles(now="2026-07-14T00:00:00+00:00")


def test_schema_v1_hash_remains_compatible_with_new_default_profile_fields() -> None:
    from hashlib import sha256

    from zhangwen.cad_agent.profile_seeds import profile_snapshot
    from zhangwen.cad_engine.profiles import unihiker_k10_profile

    payload = profile_snapshot(unihiker_k10_profile())
    stored_hash = payload.pop("content_sha256")
    payload["mounting"].pop("strategy", None)
    for opening in payload["openings"]:
        opening.pop("center_z", None)
    assert sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest() == stored_hash
    payload["content_sha256"] = stored_hash

    assert MechanicalProfileSnapshot.model_validate(payload).profile_id == "unihiker_k10"

    legacy_preview = profile_snapshot(unihiker_k10_profile())
    legacy_preview.pop("content_sha256")
    legacy_preview["preview_geometry"] = {
        "primitives": [
            {
                "primitive_id": "pcb",
                "operation": "add",
                "kind": "box",
                "center": {"x": 0.0, "y": 0.0, "z": 0.8},
                "size": {
                    "length_x": 83.2,
                    "width_y": 51.3,
                    "height_z": 1.6,
                },
                "diameter": None,
                "height": None,
                "corner_radius": 0.0,
                "rotation_z_deg": 0,
                "role": "pcb",
            }
        ]
    }
    legacy_preview_hash = sha256(
        json.dumps(
            legacy_preview,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    legacy_preview["content_sha256"] = legacy_preview_hash

    restored = MechanicalProfileSnapshot.model_validate(legacy_preview)
    assert restored.preview_geometry is not None
    assert restored.preview_geometry.source_sha256 is None


def test_only_k10_has_an_automatic_hardware_alias(tmp_path: Path) -> None:
    database = tmp_path / "profiles.sqlite3"
    create_profile_tables(database)
    repository = MechanicalProfileRepository(database)
    repository.seed_builtin_profiles()

    assert repository.resolve_for_hardware("hw_seed_unihiker_k10").profile_id == "unihiker_k10"
    with pytest.raises(KeyError, match="no confirmed mechanical profile link"):
        repository.resolve_for_hardware("hw_seed_ultrasonic")
    with pytest.raises(ValueError, match="invalid mechanical profile identifier"):
        canonical_profile_id("超声波")


def test_confirmed_hardware_link_resolves_exact_ultrasonic_profile(tmp_path: Path) -> None:
    database = tmp_path / "profiles.sqlite3"
    create_profile_tables(database)
    repository = MechanicalProfileRepository(database)
    repository.seed_builtin_profiles(now="2026-07-13T00:00:00+00:00")
    with sqlite3.connect(database) as conn:
        conn.execute("INSERT INTO hardware_components (id) VALUES ('hw_ultrasonic_exact')")
        conn.execute(
            """
            INSERT INTO hardware_mechanical_links (
              id, hardware_component_id, mechanical_profile_id,
              mechanical_profile_revision, evidence_level, confirmed_at,
              created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "link_ultrasonic",
                "hw_ultrasonic_exact",
                "unihiker_ultrasonic_distance_sensor",
                "measured-v1",
                "TRUSTED",
                "2026-07-13T00:00:00+00:00",
                "2026-07-13T00:00:00+00:00",
                "2026-07-13T00:00:00+00:00",
            ),
        )

    resolved = repository.resolve_for_hardware("hw_ultrasonic_exact")

    assert resolved.profile_id == "unihiker_ultrasonic_distance_sensor"


def test_snapshot_rejects_code_path_and_hash_tampering(tmp_path: Path) -> None:
    database = tmp_path / "profiles.sqlite3"
    create_profile_tables(database)
    repository = MechanicalProfileRepository(database)
    repository.seed_builtin_profiles()
    payload = repository.get("unihiker_k10").model_dump(mode="json")
    payload["path"] = "untrusted.py"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        MechanicalProfileSnapshot.model_validate(payload)

    payload = repository.get("unihiker_k10").model_dump(mode="json")
    payload["mounting"]["code"] = "import cadquery"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        MechanicalProfileSnapshot.model_validate(payload)

    with sqlite3.connect(database) as conn:
        raw = json.loads(
            conn.execute(
                "SELECT profile_json FROM mechanical_profile_versions WHERE profile_id = 'unihiker_k10'"
            ).fetchone()[0]
        )
        raw["display_name"] = "tampered"
        conn.execute(
            "UPDATE mechanical_profile_versions SET profile_json = ? WHERE profile_id = 'unihiker_k10'",
            (json.dumps(raw),),
        )
    with pytest.raises(ValidationError, match="content hash"):
        repository.get("unihiker_k10")
