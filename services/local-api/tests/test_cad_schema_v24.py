"""Schema and boundary regression tests for the real CAD runtime."""

from __future__ import annotations

import sqlite3

import pytest
from pydantic import ValidationError

from zhangwen.cad_agent.models import CadDraft
from zhangwen.projects.migrations import _migrate_v24


def test_v24_migration_preserves_legacy_cad_text_rows() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(
        """
        CREATE TABLE projects (id TEXT PRIMARY KEY);
        CREATE TABLE spec_runs (id TEXT PRIMARY KEY);
        CREATE TABLE messages (id TEXT PRIMARY KEY);
        CREATE TABLE project_experts (id TEXT PRIMARY KEY);
        CREATE TABLE artifacts (id TEXT PRIMARY KEY);
        CREATE TABLE artifact_versions (
          id TEXT PRIMARY KEY,
          artifact_id TEXT NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE
        );
        CREATE TABLE hardware_components (id TEXT PRIMARY KEY);
        CREATE TABLE schema_migration_audit (
          id TEXT PRIMARY KEY,
          from_version INTEGER NOT NULL,
          to_version INTEGER NOT NULL,
          status TEXT NOT NULL,
          backup_path TEXT NULL,
          applied_at TEXT NOT NULL
        );
        CREATE TABLE cad_runs (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id),
          spec_run_id TEXT NOT NULL REFERENCES spec_runs(id),
          template_kind TEXT NOT NULL,
          version INTEGER NOT NULL,
          status TEXT NOT NULL,
          command_label TEXT NOT NULL,
          parameters_json TEXT NOT NULL,
          validation_json TEXT NOT NULL,
          artifact_id TEXT NULL,
          artifact_version_id TEXT NULL,
          stale_reason TEXT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          confirmed_at TEXT NULL
        );
        CREATE TABLE cad_files (
          id TEXT PRIMARY KEY,
          cad_run_id TEXT NOT NULL REFERENCES cad_runs(id) ON DELETE CASCADE,
          project_id TEXT NOT NULL REFERENCES projects(id),
          kind TEXT NOT NULL,
          path TEXT NOT NULL,
          mime_type TEXT NOT NULL,
          content TEXT NOT NULL,
          artifact_id TEXT NULL,
          artifact_version_id TEXT NULL,
          created_at TEXT NOT NULL
        );
        INSERT INTO projects VALUES ('project_1');
        INSERT INTO spec_runs VALUES ('spec_1');
        INSERT INTO cad_runs VALUES (
          'cad_1', 'project_1', 'spec_1', 'BOX_WITH_LID', 1,
          'READY_FOR_REVIEW', 'cadquery-template-dry-run', '[]',
          '{"ok":true,"checks":[]}', NULL, NULL, NULL,
          '2026-07-13T00:00:00+00:00', '2026-07-13T00:00:00+00:00', NULL
        );
        INSERT INTO cad_files VALUES (
          'cad_file_1', 'cad_1', 'project_1', 'STL', 'model.stl',
          'model/stl', 'solid legacy\nendsolid legacy\n', NULL, NULL,
          '2026-07-13T00:00:00+00:00'
        );
        PRAGMA user_version=23;
        """
    )

    _migrate_v24(conn)

    run = conn.execute(
        "SELECT spec_run_id, engine_id, engine_version FROM cad_runs WHERE id='cad_1'"
    ).fetchone()
    file_row = conn.execute(
        "SELECT role, content, storage_key FROM cad_files WHERE id='cad_file_1'"
    ).fetchone()
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 24
    assert run == ("spec_1", "template-dry-run", "1")
    assert file_row == (
        "STL_PRINTABLE_PARTS",
        "solid legacy\nendsolid legacy\n",
        None,
    )
    assert conn.execute("SELECT COUNT(*) FROM cad_jobs").fetchone()[0] == 0


def test_v24_migration_rolls_back_on_foreign_key_violation() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(
        """
        CREATE TABLE projects (id TEXT PRIMARY KEY);
        CREATE TABLE spec_runs (id TEXT PRIMARY KEY);
        CREATE TABLE messages (id TEXT PRIMARY KEY);
        CREATE TABLE project_experts (id TEXT PRIMARY KEY);
        CREATE TABLE artifacts (id TEXT PRIMARY KEY);
        CREATE TABLE artifact_versions (id TEXT PRIMARY KEY);
        CREATE TABLE hardware_components (id TEXT PRIMARY KEY);
        CREATE TABLE schema_migration_audit (
          id TEXT PRIMARY KEY,
          from_version INTEGER NOT NULL,
          to_version INTEGER NOT NULL,
          status TEXT NOT NULL,
          backup_path TEXT NULL,
          applied_at TEXT NOT NULL
        );
        CREATE TABLE cad_runs (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id),
          spec_run_id TEXT NOT NULL REFERENCES spec_runs(id),
          template_kind TEXT NOT NULL,
          version INTEGER NOT NULL,
          status TEXT NOT NULL,
          command_label TEXT NOT NULL,
          parameters_json TEXT NOT NULL,
          validation_json TEXT NOT NULL,
          artifact_id TEXT NULL,
          artifact_version_id TEXT NULL,
          stale_reason TEXT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          confirmed_at TEXT NULL
        );
        CREATE TABLE cad_files (
          id TEXT PRIMARY KEY,
          cad_run_id TEXT NOT NULL REFERENCES cad_runs(id),
          project_id TEXT NOT NULL REFERENCES projects(id),
          kind TEXT NOT NULL,
          path TEXT NOT NULL,
          mime_type TEXT NOT NULL,
          content TEXT NOT NULL,
          artifact_id TEXT NULL,
          artifact_version_id TEXT NULL,
          created_at TEXT NOT NULL
        );
        """
    )
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute(
        """
        INSERT INTO cad_runs (
          id, project_id, spec_run_id, template_kind, version, status,
          command_label, parameters_json, validation_json, artifact_id,
          artifact_version_id, stale_reason, created_at, updated_at, confirmed_at
        ) VALUES ('bad-run', 'missing-project', 'missing-spec', 'BOX_WITH_LID', 1,
                  'DRAFT', 'legacy', '{}', '{}', NULL, NULL, NULL, 'now', 'now', NULL)
        """
    )
    conn.execute("PRAGMA user_version=23")
    conn.commit()
    conn.execute("PRAGMA foreign_keys=ON")

    with pytest.raises(sqlite3.IntegrityError, match="foreign-key check"):
        _migrate_v24(conn)

    assert conn.execute("PRAGMA user_version").fetchone()[0] == 23
    assert conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='cad_jobs'"
    ).fetchone() is None
    assert "engine_id" not in {
        row[1] for row in conn.execute("PRAGMA table_info(cad_runs)").fetchall()
    }


def test_cad_draft_rejects_executable_and_path_fields() -> None:
    with pytest.raises(ValidationError, match="不允许由调用方提供"):
        CadDraft.model_validate(
            {
                "templateKind": "BOX_WITH_LID",
                "parameters": {"width": 80, "height": 50, "depth": 30},
                "components": [],
                "constraints": {"python": "runpy"},
                "summary": "外壳",
            }
        )
