"""Tests for ZW-006 project proposal workflow."""

from __future__ import annotations

import io
import sqlite3
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from zhangwen.config import settings
from zhangwen.main import app
from zhangwen.projects.migrations import CURRENT_SCHEMA_VERSION, migrate
from zhangwen.projects.repository import ProjectRepository
from zhangwen.proposals.models import ProposalStatus
from zhangwen.proposals.repository import ProposalRepository
from zhangwen.solutions.models import SolutionSection
from zhangwen.solutions.repository import SolutionRepository
from tests.fakes import fake_proposal_sections


def test_v4_migration_creates_proposals_table(tmp_path: Path) -> None:
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
    assert "proposals" in tables


def test_generate_requires_confirmed_solution(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id = _create_project(client)
    solution = _create_solution(tmp_path, project_id)

    response = client.post(
        f"/api/projects/{project_id}/proposal/generate",
        json={"solutionId": solution.id},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "PROPOSAL_REQUIRES_CONFIRMED_SOLUTION"


def test_generate_list_confirm_reject_and_export_proposal(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id = _create_project(client)
    solution = _create_solution(tmp_path, project_id)
    confirmed_solution = SolutionRepository(
        ProjectRepository(tmp_path).db_path
    ).confirm_solution(project_id, solution.id)

    generated = client.post(
        f"/api/projects/{project_id}/proposal/generate",
        json={"solutionId": confirmed_solution.id},
    )
    assert generated.status_code == 200
    proposal = generated.json()["proposal"]
    assert proposal["version"] == 1
    assert proposal["status"] == ProposalStatus.DRAFT.value
    assert len(proposal["sections"]) >= 6

    listed = client.get(f"/api/projects/{project_id}/proposal")
    assert listed.status_code == 200
    assert listed.json()["proposals"][0]["id"] == proposal["id"]

    revised = client.post(
        f"/api/projects/{project_id}/proposal/revise",
        json={"proposalId": proposal["id"], "revisionMessage": "增加课堂安全提醒"},
    )
    assert revised.status_code == 200
    revised_proposal = revised.json()["proposal"]
    assert revised_proposal["version"] == 2
    assert revised_proposal["sections"][-1]["id"] == "risks_acceptance"
    assert "课堂安全提醒" in revised_proposal["sections"][-1]["content"]

    confirmed = client.post(
        f"/api/projects/{project_id}/proposal/confirm",
        json={"proposalId": revised_proposal["id"]},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["proposal"]["status"] == ProposalStatus.APPROVED.value
    workspace = client.get(f"/api/projects/{project_id}").json()["workspace"]
    assert workspace["project"]["stage"] == "PROPOSAL_CONFIRMED"

    markdown = client.get(
        f"/api/projects/{project_id}/proposal/{revised_proposal['id']}/export",
        params={"format": "MARKDOWN"},
    )
    assert markdown.status_code == 200
    assert markdown.headers["content-type"].startswith("text/markdown")
    markdown_text = markdown.content.decode("utf-8")
    assert "| 立项项 | 执行内容 |" in markdown_text
    assert "| 项目名称与目标 |" in markdown_text
    assert "增加课堂安全提醒" in markdown_text

    docx = client.get(
        f"/api/projects/{project_id}/proposal/{revised_proposal['id']}/export",
        params={"format": "DOCX"},
    )
    assert docx.status_code == 200
    assert docx.content.startswith(b"PK")
    with zipfile.ZipFile(io.BytesIO(docx.content)) as archive:
        document_xml = archive.read("word/document.xml")
    assert b"<w:tbl>" in document_xml

    pdf = client.get(
        f"/api/projects/{project_id}/proposal/{revised_proposal['id']}/export",
        params={"format": "PDF"},
    )
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")

    rejected = client.post(
        f"/api/projects/{project_id}/proposal/reject",
        json={"proposalId": revised_proposal["id"], "reason": "需要重做"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["proposal"]["status"] == ProposalStatus.REJECTED.value


def test_new_solution_marks_existing_proposal_stale(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    project_id = _create_project(TestClient(app))
    db_path = ProjectRepository(tmp_path).db_path
    solution_repo = SolutionRepository(db_path)
    first_solution = solution_repo.confirm_solution(
        project_id,
        _create_solution(tmp_path, project_id).id,
    )
    proposal_repo = ProposalRepository(db_path)
    proposal = proposal_repo.create_from_solution(
        project_id,
        first_solution,
        fake_proposal_sections(),
    )

    proposal_repo.mark_project_proposals_stale(project_id, "推荐实现方案已生成新版本。")

    stale = proposal_repo.get_proposal(project_id, proposal.id)
    assert stale.status == ProposalStatus.STALE
    assert stale.staleReason == "推荐实现方案已生成新版本。"


def test_confirming_proposal_materializes_project_physical_scene(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    response = client.post(
        "/api/projects",
        json={
            "name": "K10 实物仿真项目",
            "initialIdea": "使用 K10 连接项目传感器",
            "selectedHardwareIds": ["hw_seed_unihiker_k10"],
        },
    )
    assert response.status_code == 200, response.json()
    project_id = str(response.json()["workspace"]["project"]["id"])
    db_path = ProjectRepository(tmp_path).db_path
    solution_repo = SolutionRepository(db_path)
    solution = solution_repo.confirm_solution(
        project_id,
        _create_solution(tmp_path, project_id).id,
    )
    proposal_sections = fake_proposal_sections()
    proposal_sections[0] = proposal_sections[0].model_copy(
        update={"content": f"{proposal_sections[0].content}\n主控采用 DFRobot K10。"}
    )
    proposal = ProposalRepository(db_path).create_from_solution(
        project_id,
        solution,
        proposal_sections,
    )

    confirmed = client.post(
        f"/api/projects/{project_id}/proposal/confirm",
        json={"proposalId": proposal.id},
    )

    assert confirmed.status_code == 200, confirmed.json()
    with sqlite3.connect(db_path) as conn:
        stored = conn.execute(
            "SELECT board_id, proposal_id FROM device_lab_scenes WHERE project_id = ?",
            (project_id,),
        ).fetchone()
    assert stored == ("dfrobot/dfrobot_k10", proposal.id)
    scene = client.get(f"/api/projects/{project_id}/device-lab/scene")
    assert scene.status_code == 200
    assert scene.json()["scene"]["source"]["proposalId"] == proposal.id


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
