"""Tests for ZW-014 Lesson Agent."""

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
from zhangwen.lesson_agent.models import LessonRunStatus
from zhangwen.main import app
from zhangwen.projects.migrations import CURRENT_SCHEMA_VERSION, migrate
from zhangwen.projects.repository import ProjectRepository
from zhangwen.proposals.repository import ProposalRepository
from zhangwen.solutions.models import SolutionSection
from zhangwen.solutions.repository import SolutionRepository
from tests.fakes import fake_proposal_sections
from zhangwen.specs.models import SpecRunStatus


def test_v13_migration_creates_lesson_and_package_tables(tmp_path: Path) -> None:
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
    assert {"lesson_runs", "lesson_files", "package_exports"}.issubset(tables)


def test_lesson_requires_approved_spec(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id, spec_id = _project_with_spec(tmp_path, approved_spec=False)

    response = client.post(
        f"/api/projects/{project_id}/lesson/generate",
        json={"specRunId": spec_id},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "LESSON_REQUIRES_APPROVED_SPEC"


def test_generate_confirm_reject_lesson_and_sync_artifacts(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id, spec_id = _project_with_spec(tmp_path, approved_spec=True)

    generated = client.post(
        f"/api/projects/{project_id}/lesson/generate",
        json={"specRunId": spec_id, "gradeBand": "初中", "lessonHours": 2},
    )

    assert generated.status_code == 200
    lesson = generated.json()["lessonRun"]
    assert lesson["status"] == LessonRunStatus.READY_FOR_REVIEW.value
    assert lesson["gradeBand"] == "初中"
    assert lesson["lessonHours"] == 2
    assert {file["kind"] for file in lesson["files"]} == {
        "TEACHER_GUIDE",
        "STUDENT_WORKSHEET",
        "RUBRIC",
        "SAFETY_NOTES",
    }
    assert all("sk-" not in file["content"] for file in lesson["files"])
    assert all("apiKey" not in file["content"] for file in lesson["files"])
    teacher_guide = next(
        file for file in lesson["files"] if file["kind"] == "TEACHER_GUIDE"
    )
    safety_notes = next(
        file for file in lesson["files"] if file["kind"] == "SAFETY_NOTES"
    )
    assert "学习目标" in teacher_guide["content"]
    assert "安全说明" in safety_notes["content"]
    assert "未访问真实串口" not in teacher_guide["content"]

    artifacts = ArtifactRepository(ProjectRepository(tmp_path).db_path).list_artifacts(project_id)
    lesson_artifacts = [
        artifact for artifact in artifacts if artifact.sourceAgentId == "lesson-agent"
    ]
    assert len(lesson_artifacts) == 4
    assert all(artifact.kind == ArtifactKind.DOCUMENT for artifact in lesson_artifacts)
    assert all(artifact.status == ArtifactStatus.NEEDS_REVIEW for artifact in lesson_artifacts)
    assert all(
        artifact.versions[0].preview.kind == ArtifactPreviewKind.DOCUMENT
        for artifact in lesson_artifacts
    )
    assert all(artifact.versions[0].dependencies for artifact in lesson_artifacts)

    confirmed = client.post(
        f"/api/projects/{project_id}/lesson/confirm",
        json={"lessonRunId": lesson["id"]},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["lessonRun"]["status"] == LessonRunStatus.APPROVED.value

    current = client.get(f"/api/projects/{project_id}/lesson/current")
    assert current.status_code == 200
    assert current.json()["lessonRun"]["id"] == lesson["id"]

    rejected = client.post(
        f"/api/projects/{project_id}/lesson/reject",
        json={"lessonRunId": lesson["id"], "reason": "需要补充课堂时间安排"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["lessonRun"]["status"] == LessonRunStatus.REJECTED.value
    assert rejected.json()["lessonRun"]["staleReason"] == "需要补充课堂时间安排"


def test_new_lesson_marks_previous_run_stale(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id, spec_id = _project_with_spec(tmp_path, approved_spec=True)

    first = client.post(
        f"/api/projects/{project_id}/lesson/generate",
        json={"specRunId": spec_id, "gradeBand": "初中", "lessonHours": 2},
    ).json()["lessonRun"]
    second = client.post(
        f"/api/projects/{project_id}/lesson/generate",
        json={"specRunId": spec_id, "gradeBand": "小学高年级", "lessonHours": 3},
    ).json()["lessonRun"]

    assert first["id"] != second["id"]
    current = client.get(f"/api/projects/{project_id}/lesson/current").json()["lessonRun"]
    assert current["id"] == second["id"]
    stale = ArtifactRepository(ProjectRepository(tmp_path).db_path).get_artifact(
        project_id,
        f"artifact_lesson_{project_id}_teacher_guide",
    )
    assert stale.versions[-1].staleReason == "教案已生成新版本。"


def _project_with_spec(tmp_path: Path, *, approved_spec: bool) -> tuple[str, str]:
    client = TestClient(app)
    project_id = _create_project(client)
    db_path = ProjectRepository(tmp_path).db_path
    solution = SolutionRepository(db_path).confirm_solution(
        project_id,
        SolutionRepository(db_path).create_solution(
            project_id,
            [
                SolutionSection(id="goal", title="项目目标", content="做一个自动浇花装置"),
                SolutionSection(id="hardware", title="硬件方案", content="ESP32-S3 + 土壤湿度传感器"),
                SolutionSection(id="software", title="软件方案", content="MicroPython 控制水泵"),
            ],
        ).id,
    )
    proposal_repo = ProposalRepository(db_path)
    proposal = proposal_repo.confirm_proposal(
        project_id,
        proposal_repo.create_from_solution(
            project_id,
            solution,
            fake_proposal_sections(),
        ).id,
    )
    spec = client.post(
        f"/api/projects/{project_id}/spec/generate",
        json={"proposalId": proposal.id},
    ).json()["spec"]
    if approved_spec:
        spec = client.post(
            f"/api/projects/{project_id}/spec/confirm",
            json={"specRunId": spec["id"]},
        ).json()["spec"]
        assert spec["status"] == SpecRunStatus.APPROVED.value
    return project_id, spec["id"]


def _create_project(client: TestClient) -> str:
    response = client.post(
        "/api/projects",
        json={"name": "测试项目", "initialIdea": "测试创意"},
    )
    assert response.status_code == 200
    return str(response.json()["workspace"]["project"]["id"])
