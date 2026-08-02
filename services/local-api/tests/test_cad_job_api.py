from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from zhangwen.cad_agent import router as cad_router
from zhangwen.cad_agent.job_repository import CadJobRepository
from zhangwen.cad_agent.models import CadDraft
from zhangwen.cad_agent.repository import CadRepository
from zhangwen.config import settings
from zhangwen.main import app
from zhangwen.projects.models import ExpertType
from zhangwen.projects.repository import ProjectRepository


_TOKEN = "cad-job-test-token"
_HEADERS = {
    "X-Zhangwen-Host": "tauri",
    "X-Zhangwen-Capability-Token": _TOKEN,
}


def test_confirmed_job_api_runs_cad_skill_and_is_idempotent(tmp_path, monkeypatch) -> None:
    settings.data_dir = tmp_path
    monkeypatch.setenv("ZHANGWEN_DESKTOP_CAPABILITY_TOKEN", _TOKEN)
    projects = ProjectRepository(tmp_path)
    workspace = projects.create_project_from_idea(
        idea="生成参数化盒体",
        project_name="CAD Job",
        initial_expert=ExpertType.STRUCTURE_ENGINEER,
        participating_experts=[ExpertType.STRUCTURE_ENGINEER],
    )
    cad_run = CadRepository(projects.db_path).create_draft(
        project_id=workspace.project.id,
        draft=CadDraft(
            templateKind="BOX_WITH_LID",
            parameters={"width": 80, "depth": 60, "height": 30},
            components=[],
            constraints={"process": "FDM", "minWallThicknessMm": 1.6},
            summary="参数化盒体",
        ),
        source_message_id=workspace.conversation.messages[0].id,
        generated_by_expert_id=workspace.experts[0].id,
    )

    class FakeCoordinator:
        def submit(self, job):
            return job

    coordinator = FakeCoordinator()

    async def fake_coordinator():
        return coordinator

    monkeypatch.setattr(cad_router, "ensure_cad_coordinator", fake_coordinator)
    client = TestClient(app)
    body = {"cadRunId": cad_run.id, "clientRequestId": "job-api-1"}

    denied = client.post(
        f"/api/projects/{workspace.project.id}/cad/jobs",
        json=body,
    )
    assert denied.status_code == 409

    web_confirm = client.post(
        f"/api/projects/{workspace.project.id}/cad/confirm",
        json={"cadRunId": cad_run.id},
    )
    web_reject = client.post(
        f"/api/projects/{workspace.project.id}/cad/reject",
        json={"cadRunId": cad_run.id, "reason": "浏览器门禁回归"},
    )
    assert web_confirm.status_code == 409
    assert web_reject.status_code == 409

    created = client.post(
        f"/api/projects/{workspace.project.id}/cad/jobs",
        json=body,
        headers=_HEADERS,
    )
    duplicate = client.post(
        f"/api/projects/{workspace.project.id}/cad/jobs",
        json=body,
        headers=_HEADERS,
    )

    assert created.status_code == 200
    assert duplicate.status_code == 200
    first_job = created.json()["cadJob"]
    assert first_job["status"] == "QUEUED"
    assert first_job["request"]["sizingEvidence"]["mode"] == "EXPLICIT"
    assert duplicate.json()["cadJob"]["id"] == first_job["id"]
    fetched = client.get(
        f"/api/projects/{workspace.project.id}/cad/jobs/{first_job['id']}"
    )
    assert fetched.status_code == 200
    assert fetched.json()["cadJob"]["cadRunId"] == cad_run.id
    assert CadJobRepository(projects.db_path).get(
        workspace.project.id,
        first_job["id"],
    ).request.jobId == first_job["id"]
    with projects._connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM skill_runs WHERE skill_id = 'parametric-modeling'"
        ).fetchone()[0] == 2
        assert conn.execute(
            "SELECT COUNT(*) FROM tool_runs WHERE tool_id = 'cad.build' AND status = 'completed'"
        ).fetchone()[0] == 2


def test_cad_job_materializes_missing_enclosure_dimensions(tmp_path) -> None:
    projects = ProjectRepository(tmp_path)
    workspace = projects.create_project_from_idea(
        idea="自动计算空盒尺寸",
        project_name="CAD Auto Size",
        initial_expert=ExpertType.STRUCTURE_ENGINEER,
        participating_experts=[ExpertType.STRUCTURE_ENGINEER],
    )
    repository = CadRepository(projects.db_path)
    cad_run = repository.create_draft(
        project_id=workspace.project.id,
        draft=CadDraft(
            templateKind="BOX_WITH_LID",
            parameters={},
            components=[],
            constraints={"process": "FDM"},
            summary="由本地内核计算尺寸",
        ),
        source_message_id=workspace.conversation.messages[0].id,
        generated_by_expert_id=workspace.experts[0].id,
    )

    job = repository.create_job(
        project_id=workspace.project.id,
        cad_run_id=cad_run.id,
        client_request_id="auto-size",
    )

    assert job.request.parameters["width"] == 80
    assert job.request.parameters["height"] == 28
    assert job.request.parameters["depth"] == 50
    assert job.request.sizingEvidence is not None
    assert job.request.sizingEvidence.mode == "AUTO"
    current = repository.get_cad(workspace.project.id, cad_run.id)
    values = {item.name: item.value for item in current.parameters}
    assert values["width"] == 80
    assert values["height"] == 28
    assert values["depth"] == 50


def test_cad_job_rejects_non_structure_source(tmp_path) -> None:
    projects = ProjectRepository(tmp_path)
    workspace = projects.create_project_from_idea(
        idea="问题引导师不应直接建模",
        project_name="CAD 来源边界",
        initial_expert=ExpertType.PROBLEM_GUIDE,
        participating_experts=[ExpertType.PROBLEM_GUIDE],
    )
    repository = CadRepository(projects.db_path)
    cad_run = repository.create_draft(
        project_id=workspace.project.id,
        draft=CadDraft(
            templateKind="BOX_WITH_LID",
            parameters={"width": 80, "depth": 60, "height": 30},
            components=[],
            constraints={},
            summary="错误来源草稿",
        ),
        source_message_id=workspace.conversation.messages[0].id,
        generated_by_expert_id=workspace.experts[0].id,
    )

    with pytest.raises(ValueError, match="CAD_SOURCE_EXPERT_INVALID"):
        repository.create_job(
            project_id=workspace.project.id,
            cad_run_id=cad_run.id,
            client_request_id="invalid-source",
        )


def test_revised_intake_error_is_a_stable_non_retryable_conflict() -> None:
    detail = cad_router._cad_http_exception(ValueError("CAD_INTAKE_REVISED"))

    assert detail.status_code == 409
    assert detail.detail == {
        "code": "CAD_INTAKE_REVISED",
        "message": "CAD 结构输入已更新，请使用最新 CAD 草稿。",
        "retryable": False,
    }
