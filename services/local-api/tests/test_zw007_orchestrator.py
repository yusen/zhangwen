"""Tests for ZW-007 Orchestrator and Agent Registry."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from zhangwen.config import settings
from zhangwen.main import app
from zhangwen.projects.migrations import CURRENT_SCHEMA_VERSION, migrate
from zhangwen.projects.repository import ProjectRepository
from zhangwen.proposals.repository import ProposalRepository
from zhangwen.solutions.models import SolutionSection
from zhangwen.solutions.repository import SolutionRepository
from tests.fakes import fake_proposal_sections


def test_v5_migration_creates_orchestrator_tables(tmp_path: Path) -> None:
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
    assert {"execution_plans", "task_nodes"}.issubset(tables)


def test_agent_registry_endpoint_lists_builtin_agents(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)

    response = client.get("/api/agents")

    assert response.status_code == 200
    ids = {agent["id"] for agent in response.json()["agents"]}
    assert {
        "orchestrator",
        "spec-agent",
        "code-agent",
        "cad-agent",
        "deploy-agent",
        "publish-agent",
        "lesson-agent",
    }.issubset(ids)


def test_create_plan_requires_approved_proposal(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id = _create_project(client)
    proposal_id = _proposal(tmp_path, project_id, approved=False)

    response = client.post(
        f"/api/projects/{project_id}/execution-plan",
        json={"proposalId": proposal_id},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "EXECUTION_PLAN_CREATE_FAILED"


def test_execution_plan_lifecycle_pause_approve_reject_and_retry(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id = _create_project(client)
    proposal_id = _proposal(tmp_path, project_id, approved=True)

    created = client.post(
        f"/api/projects/{project_id}/execution-plan",
        json={"proposalId": proposal_id},
    )
    assert created.status_code == 200
    plan = created.json()["plan"]
    assert plan["status"] == "QUEUED"
    assert len(plan["nodes"]) == 7

    started = client.post(
        f"/api/projects/{project_id}/execution-plan/{plan['id']}/start"
    )
    assert started.status_code == 200
    plan = started.json()["plan"]
    assert plan["status"] == "AWAITING_APPROVAL"
    spec_review = _node_by_title(plan, "确认工程规格")
    assert spec_review["status"] == "AWAITING_APPROVAL"

    paused = client.post(
        f"/api/projects/{project_id}/execution-plan/{plan['id']}/pause"
    )
    assert paused.status_code == 200
    assert paused.json()["plan"]["status"] == "PAUSED"

    resumed = client.post(
        f"/api/projects/{project_id}/execution-plan/{plan['id']}/resume"
    )
    assert resumed.status_code == 200
    assert resumed.json()["plan"]["status"] == "AWAITING_APPROVAL"

    approved = client.post(
        f"/api/projects/{project_id}/execution-plan/{plan['id']}/approve",
        json={"nodeId": spec_review["id"], "approved": True, "comment": "通过"},
    )
    assert approved.status_code == 200
    plan = approved.json()["plan"]
    assert plan["status"] == "AWAITING_APPROVAL"
    publish_review = _node_by_title(plan, "确认发布准备")
    assert publish_review["status"] == "AWAITING_APPROVAL"

    rejected = client.post(
        f"/api/projects/{project_id}/execution-plan/{plan['id']}/approve",
        json={
            "nodeId": publish_review["id"],
            "approved": False,
            "comment": "补充材料",
        },
    )
    assert rejected.status_code == 200
    plan = rejected.json()["plan"]
    assert plan["status"] == "FAILED"

    retried = client.post(
        f"/api/projects/{project_id}/execution-plan/{plan['id']}/retry",
        json={"nodeId": publish_review["id"]},
    )
    assert retried.status_code == 200
    plan = retried.json()["plan"]
    publish_review = _node_by_title(plan, "确认发布准备")
    assert publish_review["status"] == "AWAITING_APPROVAL"

    completed = client.post(
        f"/api/projects/{project_id}/execution-plan/{plan['id']}/approve",
        json={"nodeId": publish_review["id"], "approved": True},
    )
    assert completed.status_code == 200
    assert completed.json()["plan"]["status"] == "COMPLETED"


def _create_project(client: TestClient) -> str:
    response = client.post(
        "/api/projects",
        json={"name": "编排测试", "initialIdea": "测试"},
    )
    assert response.status_code == 200
    return str(response.json()["workspace"]["project"]["id"])


def _proposal(tmp_path: Path, project_id: str, *, approved: bool) -> str:
    db_path = ProjectRepository(tmp_path).db_path
    solution_repo = SolutionRepository(db_path)
    solution = solution_repo.create_solution(
        project_id,
        [
            SolutionSection(id="goal", title="项目目标", content="做一个装置"),
            SolutionSection(id="hardware", title="硬件方案", content="ESP32"),
        ],
    )
    confirmed = solution_repo.confirm_solution(project_id, solution.id)
    proposal_repo = ProposalRepository(db_path)
    proposal = proposal_repo.create_from_solution(
        project_id,
        confirmed,
        fake_proposal_sections(),
    )
    if approved:
        proposal = proposal_repo.confirm_proposal(project_id, proposal.id)
    return proposal.id


def _node_by_title(plan: dict, title: str) -> dict:
    for node in plan["nodes"]:
        if node["title"] == title:
            return node
    raise AssertionError(f"node not found: {title}")
