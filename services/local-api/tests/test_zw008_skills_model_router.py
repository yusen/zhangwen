"""Tests for ZW-008 Skill Registry and Model Router."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from zhangwen.config import settings
from zhangwen.experts.config import list_expert_configs
from zhangwen.main import app
from zhangwen.projects.migrations import CURRENT_SCHEMA_VERSION, migrate
from zhangwen.projects.repository import ProjectRepository


def test_v8_migration_keeps_skill_and_route_tables(tmp_path: Path) -> None:
    db_file = tmp_path / "test.sqlite3"
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    migrate(conn)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    conn.close()

    assert CURRENT_SCHEMA_VERSION == 31
    assert version == CURRENT_SCHEMA_VERSION
    assert {"user_skills", "model_route_audit"}.issubset(tables)


def test_builtin_and_user_skills_are_listed_with_safe_default_permissions(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)

    listed = client.get("/api/skills")
    assert listed.status_code == 200
    built_in_ids = {skill["id"] for skill in listed.json()["skills"]}
    assert "skill_project_reader" in built_in_ids
    assert "skill_model_draft" in built_in_ids

    created = client.post(
        "/api/skills",
        json={
            "name": "用户分析 Skill",
            "description": "只读项目并生成摘要",
        },
    )
    assert created.status_code == 200
    skill = created.json()["skill"]
    assert skill["origin"] == "USER"
    assert skill["enabled"] is True
    assert skill["permissions"] == []
    assert "RUN_SHELL" not in skill["permissions"]

    updated = client.patch(
        f"/api/skills/{skill['id']}",
        json={"enabled": False, "permissions": ["READ_PROJECT"]},
    )
    assert updated.status_code == 200
    assert updated.json()["skill"]["enabled"] is False
    assert updated.json()["skill"]["permissions"] == ["READ_PROJECT"]


def test_builtin_skill_description_can_be_edited_and_reloaded(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    ProjectRepository(tmp_path)
    client = TestClient(app)

    updated = client.patch(
        "/api/skills/hardware-selection",
        json={"description": "从公共硬件知识库中选择兼容组件，并说明取舍。"},
    )

    assert updated.status_code == 200
    assert updated.json()["skill"]["description"] == "从公共硬件知识库中选择兼容组件，并说明取舍。"
    reloaded = client.get("/api/skills")
    hardware_skill = next(
        skill for skill in reloaded.json()["skills"] if skill["id"] == "hardware-selection"
    )
    assert hardware_skill["description"] == "从公共硬件知识库中选择兼容组件，并说明取舍。"


def test_every_three_teacher_skill_is_registered_and_editable(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    ProjectRepository(tmp_path)
    client = TestClient(app)

    listed = client.get("/api/skills")
    assert listed.status_code == 200
    skills = {skill["id"]: skill for skill in listed.json()["skills"]}
    configured_skill_ids = {
        skill_id
        for expert in list_expert_configs()
        for skill_id in expert.skillIds
    }

    assert configured_skill_ids <= skills.keys()
    assert {skills[skill_id]["ownerExpert"] for skill_id in configured_skill_ids} == {
        "problem_guide",
        "smart_engineer",
        "structure_engineer",
    }

    for skill_id in configured_skill_ids:
        original = skills[skill_id]["description"]
        response = client.patch(
            f"/api/skills/{skill_id}",
            json={"description": f"{original}（可编辑验证）"},
        )
        assert response.status_code == 200
        assert response.json()["skill"]["description"].endswith("（可编辑验证）")


def test_model_router_uses_mock_route_and_records_audit(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    ProjectRepository(tmp_path)
    client = TestClient(app)

    fast = client.post(
        "/api/model-router/route",
        json={
            "agentId": "code-agent",
            "taskKind": "code",
            "strategy": "FAST_FIRST",
        },
    )
    assert fast.status_code == 200
    assert fast.json()["route"]["model"] == "deepseek-v4-flash"
    assert fast.json()["route"]["provider"] == "deepseek"

    quality = client.post(
        "/api/model-router/route",
        json={
            "agentId": "code-agent",
            "taskKind": "code",
            "strategy": "QUALITY_FIRST",
        },
    )
    assert quality.status_code == 200
    assert quality.json()["route"]["model"] == "deepseek-v4-pro"
    assert quality.json()["route"]["fallbackModel"] == "deepseek-v4-flash"

    with sqlite3.connect(ProjectRepository(tmp_path).db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM model_route_audit").fetchone()[0]
    assert count == 2
