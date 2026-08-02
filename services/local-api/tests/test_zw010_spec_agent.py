"""Tests for ZW-010 Spec Agent."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from zhangwen.artifacts.models import (
    ArtifactKind,
    ArtifactPreviewKind,
    ArtifactStatus,
)
from zhangwen.artifacts.repository import ArtifactRepository
from zhangwen.config import settings
from zhangwen.main import app
from zhangwen.projects.migrations import CURRENT_SCHEMA_VERSION, migrate
from zhangwen.projects.repository import ProjectRepository
from zhangwen.proposals.repository import ProposalRepository
from zhangwen.solutions.models import SolutionSection
from zhangwen.solutions.repository import SolutionRepository
from tests.fakes import fake_proposal_sections
from zhangwen.specs.models import SpecRunStatus


def test_v8_migration_creates_spec_tables(tmp_path: Path) -> None:
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
    assert {"spec_runs", "spec_files"}.issubset(tables)


def test_spec_requires_approved_proposal(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id, proposal_id = _project_with_proposal(tmp_path, approved=False)

    response = client.post(
        f"/api/projects/{project_id}/spec/generate",
        json={"proposalId": proposal_id},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "SPEC_REQUIRES_APPROVED_PROPOSAL"


def test_generate_confirm_reject_spec_and_sync_artifacts(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id, proposal_id = _project_with_proposal(tmp_path, approved=True)

    generated = client.post(
        f"/api/projects/{project_id}/spec/generate",
        json={"proposalId": proposal_id},
    )
    assert generated.status_code == 200
    spec = generated.json()["spec"]
    assert spec["status"] == SpecRunStatus.VALIDATED.value
    assert {file["kind"] for file in spec["files"]} == {
        "PROJECT_SPEC",
        "BOM",
        "IO_MAP",
    }
    assert spec["validation"]["ok"] is True
    assert "project:" in spec["files"][0]["content"]

    artifacts = ArtifactRepository(ProjectRepository(tmp_path).db_path).list_artifacts(project_id)
    spec_artifacts = [artifact for artifact in artifacts if artifact.sourceAgentId == "spec-agent"]
    assert len(spec_artifacts) == 3
    assert all(artifact.kind == ArtifactKind.DOCUMENT for artifact in spec_artifacts)
    assert all(artifact.versions[0].preview.kind == ArtifactPreviewKind.CODE for artifact in spec_artifacts)
    assert all(artifact.versions[0].status == ArtifactStatus.NEEDS_REVIEW for artifact in spec_artifacts)

    confirmed = client.post(
        f"/api/projects/{project_id}/spec/confirm",
        json={"specRunId": spec["id"]},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["spec"]["status"] == SpecRunStatus.APPROVED.value

    current = client.get(f"/api/projects/{project_id}/spec/current")
    assert current.status_code == 200
    assert current.json()["spec"]["id"] == spec["id"]

    rejected = client.post(
        f"/api/projects/{project_id}/spec/reject",
        json={"specRunId": spec["id"], "reason": "需要调整 IO"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["spec"]["status"] == SpecRunStatus.REJECTED.value


def test_confirm_spec_marks_downstream_artifacts_stale(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    project_id, proposal_id = _project_with_proposal(tmp_path, approved=True)
    db_path = ProjectRepository(tmp_path).db_path
    repo = ArtifactRepository(db_path)
    repo.upsert_text_artifact(
        artifact_id=f"artifact_code_{project_id}",
        project_id=project_id,
        title="代码草稿",
        kind=ArtifactKind.CODE,
        status=ArtifactStatus.APPROVED,
        source_agent_id="code-agent",
        source_entity_type="code",
        source_entity_id="code_v1",
        source_version=1,
        content="print('ok')",
        summary="代码草稿",
        mime_type="text/x-python",
        language="python",
    )
    client = TestClient(app)
    spec = client.post(
        f"/api/projects/{project_id}/spec/generate",
        json={"proposalId": proposal_id},
    ).json()["spec"]

    confirmed = client.post(
        f"/api/projects/{project_id}/spec/confirm",
        json={"specRunId": spec["id"]},
    )

    assert confirmed.status_code == 200
    code_artifact = repo.get_artifact(project_id, f"artifact_code_{project_id}")
    assert code_artifact.status == ArtifactStatus.STALE
    assert code_artifact.versions[0].staleReason == "硬件方案或 IO Map 已确认新版本，下游产物需要重新生成。"


def _project_with_proposal(tmp_path: Path, *, approved: bool) -> tuple[str, str]:
    client = TestClient(app)
    project_id = _create_project(client)
    db_path = ProjectRepository(tmp_path).db_path
    solution = SolutionRepository(db_path).confirm_solution(
        project_id,
        SolutionRepository(db_path).create_solution(
            project_id,
            [
                SolutionSection(id="goal", title="项目目标", content="做一个自动浇花装置"),
                SolutionSection(id="hardware", title="硬件方案", content="ESP32-S3 + 传感器"),
                SolutionSection(id="software", title="软件方案", content="MicroPython 控制水泵"),
            ],
        ).id,
    )
    proposal_repo = ProposalRepository(db_path)
    proposal = proposal_repo.create_from_solution(
        project_id,
        solution,
        fake_proposal_sections(),
    )
    if approved:
        proposal = proposal_repo.confirm_proposal(project_id, proposal.id)
    return project_id, proposal.id


def _create_project(client: TestClient) -> str:
    response = client.post(
        "/api/projects",
        json={"name": "测试项目", "initialIdea": "测试创意"},
    )
    assert response.status_code == 200
    return str(response.json()["workspace"]["project"]["id"])
