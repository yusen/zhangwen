"""Unified electrical, mechanical, and reference-model Hardware Skill tests."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from zhangwen.cad_agent.profile_repository import MechanicalProfileRepository
from zhangwen.config import settings
from zhangwen.hardware.hardware_skills import (
    HARDWARE_SKILL_PATHS,
    HardwareSkillRepository,
    HardwareSkillValidationError,
)
from zhangwen.hardware.models import HardwareSkillSourceKind
from zhangwen.hardware.seeds import seed_default_components
from zhangwen.projects.repository import ProjectRepository


@pytest.fixture
def unified_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    projects = ProjectRepository(tmp_path)
    seed_default_components(projects.db_path)
    skills = HardwareSkillRepository(tmp_path, projects.db_path)
    return tmp_path, projects.db_path, skills


def test_bundled_k10_is_one_electrical_and_mechanical_source(
    unified_environment,
) -> None:
    data_dir, db_path, skills = unified_environment

    detail = skills.get_active_by_component_id("hw_seed_unihiker_k10")

    assert detail.sourceKind.value == "BUNDLED"
    assert detail.specification.name == "行空板 K10"
    assert detail.specification.electrical.communicationProtocol == (
        "GPIO/I2C/UART/Wi-Fi/Bluetooth LE"
    )
    assert detail.mechanicalProfile is not None
    assert detail.mechanicalProfile["profile_id"] == "unihiker_k10"
    assert detail.mechanicalProfile["dimensions"] == {
        "length_x": 83.2,
        "width_y": 51.3,
        "height_z": 10.6,
    }
    paths = [file.path for file in detail.files]
    assert "references/mechanical.md" in paths
    assert "models/cadquery.py" in paths
    assert (data_dir / "hardware-skills" / detail.skillName / "assets" / "cover.webp").is_file()

    snapshot = MechanicalProfileRepository(db_path).resolve_for_hardware(
        "hw_seed_unihiker_k10"
    )
    assert snapshot.revision == f"skill-{detail.revision}"
    assert snapshot.dimensions.length_x == 83.2
    assert snapshot.model_kind.value == "unihiker_k10"

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT electrical_json FROM hardware_components WHERE id = ?",
            ("hw_seed_unihiker_k10",),
        ).fetchone()
        link = conn.execute(
            """
            SELECT mechanical_profile_revision
            FROM hardware_mechanical_links
            WHERE hardware_component_id = ? AND confirmed_at IS NOT NULL
            """,
            ("hw_seed_unihiker_k10",),
        ).fetchone()
    assert row is not None and "Bluetooth LE" in str(row[0])
    assert link == (f"skill-{detail.revision}",)

    context = skills.render_context("hw_seed_unihiker_k10")
    assert "references/mechanical.md" in context
    assert "models/cadquery.py" in context
    assert "display_frame_length = 71.0" in context


def test_existing_eight_file_k10_is_upgraded_without_becoming_invalid(
    unified_environment,
) -> None:
    _, _, skills = unified_environment
    bundled_root = (
        Path(__file__).parents[1]
        / "zhangwen"
        / "hardware"
        / "bundled-hardware-skills"
        / "k10"
    )
    specification = skills._load_package(bundled_root)[2]
    legacy = skills.create_skill(
        specification,
        skill_name="k10",
        description="保留的旧八文件 K10 说明。",
        source_kind=HardwareSkillSourceKind.MIGRATED,
    )
    assert [file.path for file in legacy.files] == list(HARDWARE_SKILL_PATHS)

    upgraded = skills.get_active_by_component_id("hw_seed_unihiker_k10")

    assert upgraded.skillName == "k10"
    assert upgraded.description == "保留的旧八文件 K10 说明。"
    assert "references/mechanical.md" in {file.path for file in upgraded.files}
    assert "models/cadquery.py" in {file.path for file in upgraded.files}
    assert upgraded.mechanicalProfile is not None


def test_model_and_mechanical_metadata_update_atomically(
    unified_environment,
) -> None:
    _, db_path, skills = unified_environment
    detail = skills.get_active_by_component_id("hw_seed_unihiker_k10")
    files = {file.path: file.content for file in detail.files}
    old_snapshot = MechanicalProfileRepository(db_path).resolve_for_hardware(
        "hw_seed_unihiker_k10"
    )

    changed_model = files["models/cadquery.py"].replace(
        'hardware_name = "行空板K10"',
        'hardware_name = "行空板K10统一模型"',
    )
    digest = hashlib.sha256(changed_model.encode("utf-8")).hexdigest()
    changed_mechanical = files["references/mechanical.md"].replace(
        hashlib.sha256(files["models/cadquery.py"].encode("utf-8")).hexdigest(),
        digest,
    )
    updated = skills.update_files(
        detail.skillName,
        updates=[
            ("references/mechanical.md", changed_mechanical),
            ("models/cadquery.py", changed_model),
        ],
        expected_revision=detail.revision,
    )

    assert updated.revision != detail.revision
    new_snapshot = MechanicalProfileRepository(db_path).resolve_for_hardware(
        "hw_seed_unihiker_k10"
    )
    assert new_snapshot.revision == f"skill-{updated.revision}"
    assert new_snapshot.revision != old_snapshot.revision
    assert "行空板K10统一模型" in skills.render_context(
        "hw_seed_unihiker_k10"
    )


def test_reference_model_hash_mismatch_rolls_back_package_and_projection(
    unified_environment,
) -> None:
    _, db_path, skills = unified_environment
    detail = skills.get_active_by_component_id("hw_seed_unihiker_k10")
    model = next(
        file.content for file in detail.files if file.path == "models/cadquery.py"
    )
    before = MechanicalProfileRepository(db_path).resolve_for_hardware(
        "hw_seed_unihiker_k10"
    )

    with pytest.raises(HardwareSkillValidationError, match="SHA-256"):
        skills.update_file(
            detail.skillName,
            path="models/cadquery.py",
            content=model + "\n# 未同步模型哈希\n",
            expected_revision=detail.revision,
        )

    current = skills.get_skill(detail.skillName)
    after = MechanicalProfileRepository(db_path).resolve_for_hardware(
        "hw_seed_unihiker_k10"
    )
    assert current.revision == detail.revision
    assert after.revision == before.revision
