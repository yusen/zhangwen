from __future__ import annotations

import json
import sqlite3

from fastapi.testclient import TestClient

from tests.fakes import FakeCredentialStore, SequenceProvider
from zhangwen.cad_agent.profile_repository import MechanicalProfileRepository
from zhangwen.config import settings
from zhangwen.hardware import router as hardware_router
from zhangwen.hardware.hardware_skills import HardwareSkillRepository
from zhangwen.hardware.seeds import seed_default_components
from zhangwen.main import app
from zhangwen.projects.repository import ProjectRepository


def test_mechanical_profile_api_lists_and_confirms_one_exact_link(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    projects = ProjectRepository(tmp_path)
    seed_default_components(projects.db_path)
    client = TestClient(app)

    listing = client.get("/api/hardware/mechanical-profiles")

    assert listing.status_code == 200
    profiles = listing.json()["profiles"]
    assert {item["profileId"] for item in profiles} == {
        "unihiker_k10",
        "unihiker_ultrasonic_distance_sensor",
        "xiao_esp32s3",
        "grove_oled_096",
        "grove_button",
    }
    k10 = next(item for item in profiles if item["profileId"] == "unihiker_k10")
    assert k10["confirmedHardwareIds"] == ["hw_seed_unihiker_k10"]
    assert k10["lockedHardwareIds"] == ["hw_seed_unihiker_k10"]
    assert k10["modelKind"] == "unihiker_k10"
    assert k10["coordinateSystem"]["origin"] == "pcb_center"
    assert k10["mountingHoles"] == []
    ultrasonic = next(
        item
        for item in profiles
        if item["profileId"] == "unihiker_ultrasonic_distance_sensor"
    )
    assert len(ultrasonic["mountingHoles"]) == 4
    assert len(ultrasonic["openings"]) == 2
    assert len(ultrasonic["keepouts"]) == 2
    assert "previewGeometry" in ultrasonic

    first = client.put(
        "/api/hardware/hw_seed_button_module/mechanical-profile-link",
        json={"profileId": "grove_button", "revision": "confirmed-v1"},
    )
    second = client.put(
        "/api/hardware/hw_seed_button_module/mechanical-profile-link",
        json={"profileId": "xiao_esp32s3", "revision": "confirmed-v1"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    repository = MechanicalProfileRepository(projects.db_path)
    assert repository.resolve_for_hardware("hw_seed_button_module").profile_id == "xiao_esp32s3"
    with sqlite3.connect(projects.db_path) as conn:
        confirmed = conn.execute(
            """
            SELECT mechanical_profile_id FROM hardware_mechanical_links
            WHERE hardware_component_id = ? AND confirmed_at IS NOT NULL
            """,
            ("hw_seed_button_module",),
        ).fetchall()
    assert confirmed == [("xiao_esp32s3",)]

    removed = client.delete(
        "/api/hardware/hw_seed_button_module/mechanical-profile-link"
    )
    assert removed.status_code == 200
    assert removed.json()["removed"] is True


def test_mechanical_profile_link_rejects_unknown_or_tampered_state(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    projects = ProjectRepository(tmp_path)
    seed_default_components(projects.db_path)
    profiles = MechanicalProfileRepository(projects.db_path)
    profiles.seed_builtin_profiles()
    client = TestClient(app)

    missing_component = client.put(
        "/api/hardware/hw_missing/mechanical-profile-link",
        json={"profileId": "xiao_esp32s3", "revision": "confirmed-v1"},
    )
    missing_profile = client.put(
        "/api/hardware/hw_seed_button_module/mechanical-profile-link",
        json={"profileId": "missing_profile", "revision": "v1"},
    )
    locked = client.delete(
        "/api/hardware/hw_seed_unihiker_k10/mechanical-profile-link"
    )

    assert missing_component.status_code == 404
    assert missing_component.json()["detail"]["code"] == "COMPONENT_NOT_FOUND"
    assert missing_profile.status_code == 404
    assert missing_profile.json()["detail"]["code"] == "MECHANICAL_PROFILE_NOT_FOUND"
    assert locked.status_code == 409

    with sqlite3.connect(projects.db_path) as conn:
        raw = json.loads(
            conn.execute(
                "SELECT profile_json FROM mechanical_profile_versions WHERE profile_id = ?",
                ("xiao_esp32s3",),
            ).fetchone()[0]
        )
        raw["display_name"] = "tampered"
        conn.execute(
            "UPDATE mechanical_profile_versions SET profile_json = ? WHERE profile_id = ?",
            (json.dumps(raw), "xiao_esp32s3"),
        )

    tampered = client.put(
        "/api/hardware/hw_seed_button_module/mechanical-profile-link",
        json={"profileId": "xiao_esp32s3", "revision": "confirmed-v1"},
    )
    assert tampered.status_code == 422
    assert tampered.json()["detail"]["code"] == "MECHANICAL_PROFILE_INVALID"


def test_preview_is_generated_from_current_skill_natural_description_and_cached(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    projects = ProjectRepository(tmp_path)
    seed_default_components(projects.db_path)
    provider = SequenceProvider(
        [
            json.dumps(
                {
                    "primitives": [
                        {
                            "primitive_id": "pcb",
                            "operation": "add",
                            "kind": "rounded_box",
                            "center": {"x": 0.0, "y": 0.0, "z": 0.8},
                            "size": {
                                "length_x": 83.2,
                                "width_y": 51.3,
                                "height_z": 1.6,
                            },
                            "corner_radius": 1.0,
                            "rotation_z_deg": 0,
                            "role": "pcb",
                        }
                    ]
                }
            )
        ]
    )
    monkeypatch.setattr(hardware_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(hardware_router, "provider_factory", lambda: provider)
    client = TestClient(app)
    listing = client.get("/api/hardware/mechanical-profiles")
    k10 = next(
        item
        for item in listing.json()["profiles"]
        if item["profileId"] == "unihiker_k10"
    )

    generated = client.post(
        "/api/hardware/mechanical-profiles/unihiker_k10/preview",
        json={"revision": k10["revision"]},
    )

    assert generated.status_code == 200
    payload = generated.json()
    assert payload["generationSource"] == "DESCRIPTION_GENERATED"
    assert payload["profile"]["revision"] != k10["revision"]
    geometry = payload["profile"]["previewGeometry"]
    assert geometry["source_sha256"]
    assert geometry["primitives"][0]["primitive_id"] == "pcb"
    assert provider.calls == 1

    repository = HardwareSkillRepository(tmp_path, projects.db_path)
    detail = repository.get_active_by_component_id("hw_seed_unihiker_k10")
    mechanical = next(
        file.content
        for file in detail.files
        if file.path == "references/mechanical.md"
    )
    assert geometry["source_sha256"] in mechanical

    cached = client.post(
        "/api/hardware/mechanical-profiles/unihiker_k10/preview",
        json={"revision": payload["profile"]["revision"]},
    )
    assert cached.status_code == 200
    assert cached.json()["generationSource"] == "DESCRIPTION_CACHE"
    assert provider.calls == 1

    changed_description = mechanical.replace("厚 1.6 mm", "厚 1.7 mm", 1)
    assert changed_description != mechanical
    changed_skill = repository.update_file(
        detail.skillName,
        path="references/mechanical.md",
        content=changed_description,
        expected_revision=detail.revision,
    )
    changed_listing = client.get("/api/hardware/mechanical-profiles")
    changed_k10 = next(
        item
        for item in changed_listing.json()["profiles"]
        if item["profileId"] == "unihiker_k10"
    )
    assert changed_k10["revision"].endswith(changed_skill.revision)

    regenerated = client.post(
        "/api/hardware/mechanical-profiles/unihiker_k10/preview",
        json={"revision": changed_k10["revision"]},
    )

    assert regenerated.status_code == 200
    assert regenerated.json()["generationSource"] == "DESCRIPTION_GENERATED"
    assert (
        regenerated.json()["profile"]["previewGeometry"]["source_sha256"]
        != geometry["source_sha256"]
    )
    assert provider.calls == 2
