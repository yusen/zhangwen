"""Contract and migration tests for the real CAD v24 foundation."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError

from zhangwen.cad_agent.models import CadBuildSpec, CadDraft
from zhangwen.cad_agent.profile_seeds import profile_seed
from zhangwen.projects.migrations import (
    CURRENT_SCHEMA_VERSION,
    _migrate_v24,
    migrate,
)
from zhangwen.projects.models import ProjectPersistenceVersion


def test_fresh_schema_contains_cad_v24_foundation(tmp_path: Path) -> None:
    conn = sqlite3.connect(tmp_path / "cad-v24.sqlite3")
    migrate(conn)

    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    run_columns = {
        row[1]: row for row in conn.execute("PRAGMA table_info(cad_runs)").fetchall()
    }
    file_columns = {
        row[1]: row for row in conn.execute("PRAGMA table_info(cad_files)").fetchall()
    }
    job_columns = {
        row[1]: row for row in conn.execute("PRAGMA table_info(cad_jobs)").fetchall()
    }
    artifact_file_columns = {
        row[1]: row
        for row in conn.execute("PRAGMA table_info(artifact_files)").fetchall()
    }

    assert ProjectPersistenceVersion.V26 == 26
    assert CURRENT_SCHEMA_VERSION == 31
    assert conn.execute("PRAGMA user_version").fetchone()[0] == CURRENT_SCHEMA_VERSION
    assert {
        "cad_jobs",
        "artifact_files",
        "mechanical_profile_versions",
        "hardware_mechanical_links",
        "cad_runs",
        "cad_files",
    }.issubset(tables)
    assert run_columns["spec_run_id"][3] == 0
    assert {
        "source_message_id",
        "generated_by_expert_id",
        "engine_id",
        "engine_version",
        "design_state_json",
        "latest_job_id",
    }.issubset(run_columns)
    assert {
        "role",
        "file_name",
        "storage_key",
        "byte_size",
        "sha256",
        "bounds_json",
        "triangle_count",
        "artifact_file_id",
    }.issubset(file_columns)
    assert {"cad_run_id", "request_hash", "request_json"}.issubset(job_columns)
    assert {"triangle_count", "bounds_json"}.issubset(artifact_file_columns)
    profile_columns = {
        row[1]
        for row in conn.execute(
            "PRAGMA table_info(mechanical_profile_versions)"
        ).fetchall()
    }
    assert {
        "profile_id",
        "revision",
        "profile_json",
        "content_sha256",
        "evidence_level",
        "representation",
    }.issubset(profile_columns)
    conn.close()


def test_v24_migration_preserves_legacy_cad_rows() -> None:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE projects (id TEXT PRIMARY KEY);
        CREATE TABLE spec_runs (id TEXT PRIMARY KEY);
        CREATE TABLE messages (id TEXT PRIMARY KEY);
        CREATE TABLE project_experts (id TEXT PRIMARY KEY);
        CREATE TABLE artifacts (id TEXT PRIMARY KEY);
        CREATE TABLE artifact_versions (id TEXT PRIMARY KEY);
        CREATE TABLE hardware_components (id TEXT PRIMARY KEY);

        CREATE TABLE cad_runs (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL,
          spec_run_id TEXT NOT NULL,
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
          cad_run_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          kind TEXT NOT NULL,
          path TEXT NOT NULL,
          mime_type TEXT NOT NULL,
          content TEXT NOT NULL,
          artifact_id TEXT NULL,
          artifact_version_id TEXT NULL,
          created_at TEXT NOT NULL
        );

        INSERT INTO projects (id) VALUES ('project-1');
        INSERT INTO spec_runs (id) VALUES ('spec-1');
        INSERT INTO cad_runs (
          id, project_id, spec_run_id, template_kind, version, status,
          command_label, parameters_json, validation_json, artifact_id,
          artifact_version_id, stale_reason, created_at, updated_at, confirmed_at
        ) VALUES (
          'cad-1', 'project-1', 'spec-1', 'BOX_WITH_LID', 1,
          'READY_FOR_REVIEW', 'cadquery-template-dry-run', '[]',
          '{"ok":true,"checks":[]}', NULL, NULL, NULL,
          '2026-07-13T00:00:00Z', '2026-07-13T00:00:00Z', NULL
        );
        INSERT INTO cad_files (
          id, cad_run_id, project_id, kind, path, mime_type, content,
          artifact_id, artifact_version_id, created_at
        ) VALUES (
          'cad-file-1', 'cad-1', 'project-1', 'STL', 'preview/model.stl',
          'model/stl', 'solid legacy\nendsolid legacy\n', NULL, NULL,
          '2026-07-13T00:00:00Z'
        );
        PRAGMA user_version=23;
        """
    )

    _migrate_v24(conn)

    run = conn.execute(
        """
        SELECT spec_run_id, engine_id, engine_version, design_state_json
        FROM cad_runs WHERE id='cad-1'
        """
    ).fetchone()
    file = conn.execute(
        """
        SELECT kind, role, path, file_name, content, byte_size, sha256,
               storage_key, artifact_file_id
        FROM cad_files WHERE id='cad-file-1'
        """
    ).fetchone()
    expected_content = "solid legacy\nendsolid legacy\n"

    assert conn.execute("PRAGMA user_version").fetchone()[0] == 24
    assert run == ("spec-1", "template-dry-run", "1", "{}")
    assert file[:5] == (
        "STL",
        "STL_PRINTABLE_PARTS",
        "preview/model.stl",
        "model.stl",
        expected_content,
    )
    assert file[5] == len(expected_content.encode("utf-8"))
    assert file[6] == hashlib.sha256(expected_content.encode("utf-8")).hexdigest()
    assert file[7:] == (None, None)
    conn.close()


def test_cad_draft_forbids_unknown_and_executable_fields() -> None:
    valid = {
        "specRunId": None,
        "templateKind": "BOX_WITH_LID",
        "parameters": {"width": 100, "depth": 80, "height": 40},
        "components": [],
        "constraints": {"process": "FDM", "minWallThicknessMm": 1.6},
        "summary": "为主控板生成带盖外壳",
    }

    draft = CadDraft.model_validate(valid)
    assert draft.specRunId is None
    assert draft.templateKind.value == "BOX_WITH_LID"

    with pytest.raises(ValidationError):
        CadDraft.model_validate({**valid, "python": "import cadquery"})
    with pytest.raises(ValidationError):
        CadDraft.model_validate(
            {**valid, "constraints": {"outputPath": "C:/outside/model.step"}}
        )
    with pytest.raises(ValidationError):
        CadDraft.model_validate({**valid, "unexpected": True})
    with pytest.raises(ValidationError):
        CadDraft.model_validate({**valid, "intakeSnapshotSha256": "not-a-sha256"})


def test_materialized_build_spec_forbids_profile_code() -> None:
    profile_snapshot = profile_seed("unihiker_k10")
    payload = {
        "jobId": "cadjob-1",
        "projectId": "project-1",
        "templateKind": "BOX_WITH_LID",
        "templateRevision": "sha256:template",
        "parameters": {"width": 100},
        "components": [],
        "constraints": {},
        "summary": "盒体",
        "profileSnapshots": [profile_snapshot],
    }
    assert CadBuildSpec.model_validate(payload).jobId == "cadjob-1"

    malicious = json.loads(json.dumps(payload))
    malicious["profileSnapshots"][0]["cadquery_code"] = "import cadquery"
    with pytest.raises(ValidationError):
        CadBuildSpec.model_validate(malicious)
