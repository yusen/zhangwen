from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from zhangwen.config import settings
from zhangwen.hardware.hardware_skills import HardwareSkillRepository
from zhangwen.hardware.models import ElectricalProps, HardwareCategory
from zhangwen.hardware.repository import HardwareRepository
from zhangwen.hardware.seeds import seed_default_components
from zhangwen.main import app
from zhangwen.projects.repository import ProjectRepository


def test_default_catalog_contains_minimum_official_suite_and_serves_verified_k10_cover(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)

    with TestClient(app) as client:
        response = client.get("/api/hardware")
        assert response.status_code == 200
        components = response.json()["components"]
        assert {component["id"] for component in components} == {
            "hw_seed_unihiker_k10",
            "hw_seeed_xiao_esp32s3_sense",
            "hw_dfrobot_sen0193",
            "hw_dfrobot_dfr0523",
            "hw_power_5v_3a_regulated",
            "hw_dfrobot_sen0388",
            "hw_dfrobot_dfr0486",
            "hw_dfrobot_dfr0029_button",
        }
        k10 = next(
            component for component in components
            if component["id"] == "hw_seed_unihiker_k10"
        )
        media = k10["media"]
        assert len(media) >= 1
        cover = next(asset for asset in media if asset["role"] == "cover")
        assert cover["alt"] == "行空板 K10 正面产品图"
        assert cover["sourceUrl"].startswith("https://www.dfrobot.com/")

        image = client.get(cover["url"])
        assert image.status_code == 200
        assert image.headers["content-type"] == cover["contentType"]
        assert hashlib.sha256(image.content).hexdigest() == cover["sha256"]
        assert image.headers["cache-control"] == "private, max-age=86400"


def test_legacy_seed_is_retired_but_user_skill_is_preserved(tmp_path: Path) -> None:
    projects = ProjectRepository(tmp_path)
    seed_default_components(projects.db_path)
    _insert_retired_seed(projects.db_path)
    components = HardwareRepository(projects.db_path, data_dir=tmp_path)
    skills = HardwareSkillRepository(tmp_path, projects.db_path)
    migrated = skills.ensure_component_migrated("hw_seed_dht22")
    assert (tmp_path / "hardware-skills" / migrated.skillName).is_dir()

    custom = components.create_component(
        name="用户自建光照传感器",
        category=HardwareCategory.SENSOR.value,
        electrical=ElectricalProps(
            voltage=3.3,
            logicLevel=3.3,
            peakCurrent=0.01,
            communicationProtocol="I2C",
            supportedMCUs=["unihiker-k10"],
        ),
        notes="用户自建，不属于旧 seed。",
    )

    seed_default_components(projects.db_path)
    listed = skills.list_skills()
    assert {item.componentId for item in listed} == {
        "hw_seed_unihiker_k10",
        "hw_seeed_xiao_esp32s3_sense",
        custom.id,
    }
    with sqlite3.connect(projects.db_path) as conn:
        assert conn.execute(
            "SELECT 1 FROM hardware_components WHERE id = 'hw_seed_dht22'"
        ).fetchone() is None
        assert conn.execute(
            "SELECT 1 FROM hardware_components WHERE id = ?",
            (custom.id,),
        ).fetchone() is not None
    retired = list(
        (tmp_path / "retired-hardware-seeds").rglob("manifest.json")
    )
    assert any(
        json.loads(path.read_text(encoding="utf-8"))["componentId"]
        == "hw_seed_dht22"
        for path in retired
    )


def test_copyable_hardware_skill_template_is_minimal_and_documents_media_contract() -> None:
    template = (
        Path(__file__).parents[1]
        / "zhangwen"
        / "hardware"
        / "hardware-skill-template"
    )
    expected = {
        "README.md",
        "manifest.template.json",
        "SKILL.md",
        "references/specifications.md",
        "references/compatibility-rules.md",
        "references/mechanical.md",
        "references/integration.md",
        "references/safety.md",
        "references/sources.md",
        "models/cadquery.py",
        "examples/usage.md",
        "tests/validation-cases.md",
    }
    actual = {
        path.relative_to(template).as_posix()
        for path in template.rglob("*")
        if path.is_file()
        and not ("__pycache__" in path.parts and path.suffix == ".pyc")
    }
    assert expected == actual
    manifest = json.loads(
        (template / "manifest.template.json").read_text(encoding="utf-8")
    )
    assert manifest["media"] == []
    readme = (template / "README.md").read_text(encoding="utf-8")
    assert '默认 `manifest.template.json` 使用 `"media": []`' in readme
    assert '"path": "assets/cover.webp"' in readme
    assert '"sourceUrl": "https://<图片来源页>"' in readme
    assert '"sha256": "<图片原始字节的64位小写SHA-256>"' in readme


def test_ai_authoring_guide_covers_strict_import_failure_modes() -> None:
    guide = (
        Path(__file__).parents[3]
        / "docs"
        / "HARDWARE_SKILL_AI_AUTHORING_GUIDE.md"
    ).read_text(encoding="utf-8")
    for required in (
        "实际文件集合必须严格等于",
        "manifest.json 本身不能放入 files",
        "禁止增加 checksums.sha256",
        "examples/*.py",
        "voltageMin",
        "profile + model",
        "禁止添加 `fixture`",
        "Package revision",
        "AI 交付报告格式",
    ):
        assert required in guide


def _insert_retired_seed(db_path: Path) -> None:
    now = "2026-07-15T00:00:00+00:00"
    electrical = {
        "voltage": 3.3,
        "logicLevel": 3.3,
        "peakCurrent": 0.0025,
        "communicationProtocol": "GPIO",
        "i2cAddress": None,
        "supportedMCUs": ["unihiker-k10"],
        "driverName": "dht",
        "firmwareRequirement": None,
    }
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO hardware_components (
              id, name, category, status, electrical_json, stock, price,
              age_recommendation, safety_tags_json, notes, created_at, updated_at
            ) VALUES (?, ?, ?, 'ACTIVE', ?, 1, 18, 9, '[]', ?, ?, ?)
            """,
            (
                "hw_seed_dht22",
                "DHT22 温湿度传感器",
                "SENSOR",
                json.dumps(electrical, ensure_ascii=False),
                "历史占位 seed。",
                now,
                now,
            ),
        )
