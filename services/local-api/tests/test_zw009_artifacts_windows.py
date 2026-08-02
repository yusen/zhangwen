"""Tests for ZW-009 artifact and window system."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from zhangwen.artifacts.models import (
    ArtifactKind,
    ArtifactStatus,
    DomainArtifactStatus,
)
from zhangwen.artifacts.repository import ArtifactRepository
from zhangwen.config import settings
from zhangwen.main import app
from zhangwen.projects.migrations import CURRENT_SCHEMA_VERSION, migrate
from zhangwen.projects.repository import ProjectRepository
from zhangwen.proposals.models import ProposalStatus
from zhangwen.proposals.repository import ProposalRepository
from zhangwen.solutions.models import SolutionSection
from zhangwen.solutions.repository import SolutionRepository
from tests.fakes import fake_proposal_sections


def test_v7_migration_creates_artifact_and_window_tables(tmp_path: Path) -> None:
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
    assert {
        "artifacts",
        "artifact_versions",
        "floating_window_states",
    }.issubset(tables)


def test_proposal_lifecycle_syncs_artifact_versions(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id = _create_project(client)
    db_path = ProjectRepository(tmp_path).db_path
    solution = SolutionRepository(db_path).confirm_solution(
        project_id,
        _create_solution(tmp_path, project_id).id,
    )

    proposal_repo = ProposalRepository(db_path)
    first = proposal_repo.create_from_solution(
        project_id,
        solution,
        fake_proposal_sections(),
    )
    second = proposal_repo.revise_proposal(
        project_id,
        first.id,
        fake_proposal_sections("补充课堂安全提醒"),
    )
    approved = proposal_repo.confirm_proposal(project_id, second.id)

    artifact = ArtifactRepository(db_path).get_artifact(
        project_id,
        f"artifact_proposal_{project_id}",
    )
    assert artifact.title == "项目立项书"
    assert artifact.status == "APPROVED"
    assert artifact.currentVersionId == f"artifact_version_proposal_{approved.id}"
    assert [version.version for version in artifact.versions] == [2, 1]
    assert artifact.versions[0].status == "APPROVED"
    assert artifact.versions[0].dependencies[0].label == "推荐实现方案 v1"

    proposal_repo.mark_project_proposals_stale(project_id, "方案已生成新版本。")
    stale = ArtifactRepository(db_path).get_artifact(project_id, artifact.id)
    assert stale.status == "STALE"
    assert stale.versions[0].staleReason == "方案已生成新版本。"


def test_artifact_api_lists_project_artifacts(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id = _create_project(client)
    db_path = ProjectRepository(tmp_path).db_path
    solution = SolutionRepository(db_path).confirm_solution(
        project_id,
        _create_solution(tmp_path, project_id).id,
    )
    proposal = ProposalRepository(db_path).create_from_solution(
        project_id,
        solution,
        fake_proposal_sections(),
    )

    listed = client.get(f"/api/projects/{project_id}/artifacts")
    assert listed.status_code == 200
    artifact = listed.json()["artifacts"][0]
    assert artifact["title"] == "项目立项书"
    assert artifact["kind"] == "DOCUMENT"
    assert artifact["versions"][0]["sourceEntityId"] == proposal.id
    assert artifact["versions"][0]["preview"]["sections"][0]["title"] == "项目名称与目标"

    loaded = client.get(f"/api/projects/{project_id}/artifacts/{artifact['id']}")
    assert loaded.status_code == 200
    assert loaded.json()["artifact"]["id"] == artifact["id"]


def test_same_artifact_version_syncs_domain_status_through_code_review(
    tmp_path: Path,
) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id = _create_project(client)
    repository = ArtifactRepository(ProjectRepository(tmp_path).db_path)
    artifact_id = f"artifact_code_{project_id}"

    def upsert(
        source_entity_id: str,
        source_version: int,
        status: ArtifactStatus,
    ):
        return repository.upsert_text_artifact(
            artifact_id=artifact_id,
            project_id=project_id,
            title="MicroPython 工程代码",
            kind=ArtifactKind.CODE,
            status=status,
            source_agent_id="code-agent",
            source_entity_type="code",
            source_entity_id=source_entity_id,
            source_version=source_version,
            content=f"# code v{source_version}\n",
            summary=f"MicroPython 工程代码 v{source_version}",
            mime_type="text/x-python",
            language="python",
        )

    first = upsert("code_v1", 1, ArtifactStatus.APPROVED)
    draft = upsert("code_v2", 2, ArtifactStatus.DRAFT)
    first_snapshot = repository.get_artifact(project_id, artifact_id).versions[1]
    assert draft.domainStatus == DomainArtifactStatus.DRAFT

    review = upsert("code_v2", 2, ArtifactStatus.NEEDS_REVIEW)
    assert review.id == draft.id
    assert review.domainStatus == DomainArtifactStatus.PENDING_CONFIRMATION

    approved = upsert("code_v2", 2, ArtifactStatus.APPROVED)
    artifact = repository.get_artifact(project_id, artifact_id)
    current = artifact.versions[0]
    preserved = artifact.versions[1]
    assert approved.id == draft.id
    assert len(artifact.versions) == 2
    assert artifact.status == ArtifactStatus.APPROVED
    assert artifact.domainStatus == DomainArtifactStatus.CONFIRMED
    assert current.status == ArtifactStatus.APPROVED
    assert current.domainStatus == DomainArtifactStatus.CONFIRMED
    assert (preserved.id, preserved.status, preserved.domainStatus, preserved.checksum) == (
        first.id,
        first_snapshot.status,
        first_snapshot.domainStatus,
        first_snapshot.checksum,
    )


def test_model_artifact_upsert_persists_domain_status_transitions(
    tmp_path: Path,
) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id = _create_project(client)
    db_path = ProjectRepository(tmp_path).db_path
    repository = ArtifactRepository(db_path)
    artifact_id = f"artifact_cad_{project_id}"

    def upsert(status: ArtifactStatus):
        return repository.upsert_model_artifact(
            artifact_id=artifact_id,
            project_id=project_id,
            title="结构模型",
            status=status,
            source_agent_id="cad-agent",
            source_entity_type="cad",
            source_entity_id="cad_v1",
            source_version=1,
            content="solid model",
            summary="结构模型 v1",
            model_url="workspace://cad/v1/model.step",
        )

    draft = upsert(ArtifactStatus.DRAFT)
    review = upsert(ArtifactStatus.NEEDS_REVIEW)
    approved = upsert(ArtifactStatus.APPROVED)
    assert draft.id == review.id == approved.id
    assert review.domainStatus == DomainArtifactStatus.PENDING_CONFIRMATION
    assert approved.domainStatus == DomainArtifactStatus.CONFIRMED

    with sqlite3.connect(db_path) as conn:
        artifact_domain_status = conn.execute(
            "SELECT domain_status FROM artifacts WHERE id = ?",
            (artifact_id,),
        ).fetchone()[0]
        version_domain_status = conn.execute(
            "SELECT domain_status FROM artifact_versions WHERE id = ?",
            (approved.id,),
        ).fetchone()[0]
    assert artifact_domain_status == DomainArtifactStatus.CONFIRMED.value
    assert version_domain_status == DomainArtifactStatus.CONFIRMED.value

    loaded = repository.get_artifact(project_id, artifact_id)
    assert loaded.domainStatus == DomainArtifactStatus.CONFIRMED
    assert loaded.versions[0].domainStatus == DomainArtifactStatus.CONFIRMED

    for explicit_status in (
        DomainArtifactStatus.CONFIRMED,
        DomainArtifactStatus.OUTDATED,
        DomainArtifactStatus.ARCHIVED,
    ):
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "UPDATE artifacts SET domain_status = ? WHERE id = ?",
                (explicit_status.value, artifact_id),
            )
            conn.execute(
                "UPDATE artifact_versions SET domain_status = ? WHERE id = ?",
                (explicit_status.value, approved.id),
            )
        preserved = upsert(ArtifactStatus.APPROVED)
        preserved_artifact = repository.get_artifact(project_id, artifact_id)
        assert preserved.domainStatus == explicit_status
        assert preserved_artifact.domainStatus == explicit_status
        assert preserved_artifact.versions[0].domainStatus == explicit_status


def test_legacy_approved_draft_domain_status_reads_as_confirmed(
    tmp_path: Path,
) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id = _create_project(client)
    db_path = ProjectRepository(tmp_path).db_path
    repository = ArtifactRepository(db_path)
    artifact_id = f"artifact_code_{project_id}"
    version = repository.upsert_text_artifact(
        artifact_id=artifact_id,
        project_id=project_id,
        title="MicroPython 工程代码",
        kind=ArtifactKind.CODE,
        status=ArtifactStatus.APPROVED,
        source_agent_id="code-agent",
        source_entity_type="code",
        source_entity_id="code_v2",
        source_version=2,
        content="print('legacy')\n",
        summary="MicroPython 工程代码 v2",
        mime_type="text/x-python",
        language="python",
    )
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE artifacts SET domain_status = 'draft' WHERE id = ?",
            (artifact_id,),
        )
        conn.execute(
            "UPDATE artifact_versions SET domain_status = 'draft' WHERE id = ?",
            (version.id,),
        )
        migrate(conn)
        stored_artifact_status = conn.execute(
            "SELECT domain_status FROM artifacts WHERE id = ?",
            (artifact_id,),
        ).fetchone()[0]
        stored_version_status = conn.execute(
            "SELECT domain_status FROM artifact_versions WHERE id = ?",
            (version.id,),
        ).fetchone()[0]

    assert stored_artifact_status == DomainArtifactStatus.CONFIRMED.value
    assert stored_version_status == DomainArtifactStatus.CONFIRMED.value

    artifact = repository.get_artifact(project_id, artifact_id)
    assert artifact.status == ArtifactStatus.APPROVED
    assert artifact.domainStatus == DomainArtifactStatus.CONFIRMED
    assert artifact.versions[0].status == ArtifactStatus.APPROVED
    assert artifact.versions[0].domainStatus == DomainArtifactStatus.CONFIRMED


def _create_project(client: TestClient) -> str:
    response = client.post(
        "/api/projects",
        json={"name": "测试项目", "initialIdea": "测试创意"},
    )
    assert response.status_code == 200
    return str(response.json()["workspace"]["project"]["id"])


def _create_solution(tmp_path: Path, project_id: str):
    repo = SolutionRepository(ProjectRepository(tmp_path).db_path)
    return repo.create_solution(
        project_id,
        [
            SolutionSection(id="goal", title="项目目标", content="做一个自动浇花装置"),
            SolutionSection(id="hardware", title="硬件方案", content="ESP32-S3 + 土壤湿度传感器"),
            SolutionSection(id="software", title="软件方案", content="MicroPython 定时采样并控制水泵"),
        ],
    )
