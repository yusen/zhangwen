from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from zhangwen.config import settings
from zhangwen.main import app
from zhangwen.projects.repository import ProjectRepository


def test_progress_snapshot_is_the_single_stage_action_and_readiness_projection(
    tmp_path: Path,
) -> None:
    settings.data_dir = tmp_path
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project("自动浇花", "做一个自动浇花装置")

    with TestClient(app) as client:
        response = client.get(f"/api/projects/{workspace.project.id}/progress")

    assert response.status_code == 200
    progress = response.json()["progress"]
    assert progress["projectId"] == workspace.project.id
    assert progress["stage"] == "IDEA"
    assert progress["stageLabel"] == "描述创意"
    assert progress["currentAction"]["title"] == "继续澄清并确认方案"
    assert [item["id"] for item in progress["readinessSummary"]] == [
        "HARDWARE",
        "SPECIFICATION",
        "CODE",
        "TESTING",
        "DEPLOYMENT",
    ]
    assert progress["artifacts"] == {
        "draftCount": 0,
        "formalCount": 0,
        "message": "尚无正式产物；对话中的草稿需确认后才会出现在产物栏。",
    }
    optional = {
        item["id"]: item["required"]
        for item in progress["readiness"]["items"]
        if item["id"] in {"CAD", "LESSON"}
    }
    assert optional == {"CAD": False, "LESSON": False}


def test_progress_snapshot_repairs_stale_stored_stage_from_project_facts(
    tmp_path: Path,
) -> None:
    settings.data_dir = tmp_path
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project("状态修复", "做一个课堂装置")
    with sqlite3.connect(repository.db_path) as conn:
        conn.execute(
            "UPDATE projects SET stage = 'PUBLISHED' WHERE id = ?",
            (workspace.project.id,),
        )

    with TestClient(app) as client:
        response = client.get(f"/api/projects/{workspace.project.id}/progress")

    progress = response.json()["progress"]
    assert progress["stage"] == "IDEA"
    assert progress["consistency"] == "REPAIRED"
    assert progress["consistencyMessages"]
    assert repository.get_workspace(workspace.project.id).project.stage.value == "IDEA"
