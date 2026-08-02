"""Tests for ZW-013 CAD Agent safe template workflow."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from zhangwen.config import settings
from zhangwen.main import app
from zhangwen.projects.migrations import CURRENT_SCHEMA_VERSION, migrate
from zhangwen.projects.repository import ProjectRepository

_DESKTOP_TOKEN = "test-desktop-capability-token"
_DESKTOP_HEADERS = {
    "X-Zhangwen-Host": "tauri",
    "X-Zhangwen-Capability-Token": _DESKTOP_TOKEN,
}


def test_v11_migration_creates_cad_tables(tmp_path: Path) -> None:
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
    assert {"cad_runs", "cad_files"}.issubset(tables)


def test_legacy_cad_route_is_disabled_without_side_effects(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings.data_dir = tmp_path
    monkeypatch.setenv("ZHANGWEN_DESKTOP_CAPABILITY_TOKEN", _DESKTOP_TOKEN)
    client = TestClient(app)
    project_id = _create_project(client)

    response = client.post(
        f"/api/projects/{project_id}/cad/generate",
        json={"specRunId": "legacy-spec"},
        headers=_DESKTOP_HEADERS,
    )

    assert response.status_code == 410
    assert response.json()["detail"]["code"] == "CAD_LEGACY_ROUTE_DISABLED"
    with ProjectRepository(tmp_path)._connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM cad_runs WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0] == 0


def _create_project(client: TestClient) -> str:
    response = client.post(
        "/api/projects",
        json={"name": "测试项目", "initialIdea": "测试创意"},
    )
    assert response.status_code == 200
    return str(response.json()["workspace"]["project"]["id"])
