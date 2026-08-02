"""ZW-016 MVP end-to-end integration and readiness tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from zhangwen.cad_agent import router as cad_router
from zhangwen.cad_agent.coordinator import CadJobCoordinator
from zhangwen.cad_agent.models import CadDraft
from zhangwen.cad_agent.repository import CadRepository
from zhangwen.config import settings
from zhangwen.main import app
from zhangwen.projects.repository import ProjectRepository
from zhangwen.projects.models import ExpertType
from zhangwen.solutions.models import SolutionSection
from zhangwen.solutions.repository import SolutionRepository


def test_mvp_full_software_flow_reaches_ready_readiness(tmp_path: Path, monkeypatch) -> None:
    settings.data_dir = tmp_path
    desktop_token = "test-desktop-capability-token"
    monkeypatch.setenv("ZHANGWEN_DESKTOP_CAPABILITY_TOKEN", desktop_token)
    desktop_headers = {
        "X-Zhangwen-Host": "tauri",
        "X-Zhangwen-Capability-Token": desktop_token,
    }
    client = TestClient(app)
    project_id = _create_project(client)
    solution_id = _confirmed_solution(tmp_path, project_id)

    proposal = client.post(
        f"/api/projects/{project_id}/proposal/generate",
        json={"solutionId": solution_id},
    ).json()["proposal"]
    confirmed_proposal = client.post(
        f"/api/projects/{project_id}/proposal/confirm",
        json={"proposalId": proposal["id"]},
    ).json()["proposal"]
    assert confirmed_proposal["status"] == "APPROVED"

    plan = client.post(
        f"/api/projects/{project_id}/execution-plan",
        json={"proposalId": confirmed_proposal["id"]},
    ).json()["plan"]
    plan = client.post(
        f"/api/projects/{project_id}/execution-plan/{plan['id']}/start"
    ).json()["plan"]
    plan = _approve_awaiting_node(client, project_id, plan)
    plan = _approve_awaiting_node(client, project_id, plan)
    assert plan["status"] == "COMPLETED"

    spec = client.post(
        f"/api/projects/{project_id}/spec/generate",
        json={"proposalId": confirmed_proposal["id"]},
    ).json()["spec"]
    spec = client.post(
        f"/api/projects/{project_id}/spec/confirm",
        json={"specRunId": spec["id"]},
    ).json()["spec"]
    assert spec["status"] == "APPROVED"

    code_run = client.post(
        f"/api/projects/{project_id}/code/generate",
        json={"specRunId": spec["id"]},
    ).json()["codeRun"]
    code_run = client.post(
        f"/api/projects/{project_id}/code/accept",
        json={"codeRunId": code_run["id"]},
    ).json()["codeRun"]
    assert code_run["status"] == "ACCEPTED"

    session = client.post(
        f"/api/projects/{project_id}/devices/connect",
        json={"portId": "mock_port_esp32_s3", "boardId": "dfrobot/dfrobot_k10", "confirmBoardIdentity": True},
        headers=desktop_headers,
    ).json()["session"]
    upload = client.post(
        f"/api/projects/{project_id}/devices/upload",
        json={
            "codeRunId": code_run["id"],
            "sessionId": session["id"],
            "dryRun": True,
        },
        headers=desktop_headers,
    ).json()["operation"]
    assert upload["status"] == "DRY_RUN_COMPLETE"
    assert upload["dryRun"] is True
    assert upload["commandLabel"] == "mpremote"

    cad_run = _build_and_confirm_real_cad(
        client=client,
        data_dir=tmp_path,
        project_id=project_id,
        spec_run_id=spec["id"],
        desktop_headers=desktop_headers,
        monkeypatch=monkeypatch,
    )
    assert cad_run["status"] == "APPROVED"

    lesson_run = client.post(
        f"/api/projects/{project_id}/lesson/generate",
        json={"specRunId": spec["id"], "gradeBand": "初中", "lessonHours": 2},
    ).json()["lessonRun"]
    lesson_run = client.post(
        f"/api/projects/{project_id}/lesson/confirm",
        json={"lessonRunId": lesson_run["id"]},
    ).json()["lessonRun"]
    assert lesson_run["status"] == "APPROVED"

    package = client.post(
        f"/api/projects/{project_id}/package/export",
        json={"title": "MVP 验收包"},
    ).json()["package"]
    assert package["status"] == "EXPORTED"
    assert package["privacyReport"]["ok"] is True
    assert package["zipBase64"]

    readiness = client.get(
        f"/api/projects/{project_id}/mvp/readiness"
    ).json()["readiness"]

    assert readiness["overallStatus"] == "READY"
    # CAD 与教案已按当前产品基线变为可选项，不计入十项必选就绪度。
    assert readiness["readyCount"] == readiness["totalCount"] == 10
    statuses = {item["id"]: item["status"] for item in readiness["items"]}
    assert statuses == {
        "PROJECT_BASELINE": "READY",
        "SOLUTION": "READY",
        "PROPOSAL": "READY",
        "EXECUTION_PLAN": "READY",
        "SPEC": "READY",
        "CODE": "READY",
        "DEVICE_DRY_RUN": "READY",
        "CAD": "READY",
        "LESSON": "READY",
        "PACKAGE": "READY",
        "ARTIFACTS": "READY",
        "SECURITY": "READY",
    }
    assert any("真实 ESP32" in item for item in readiness["externalValidationRequired"])
    assert any("中央主对话" in item for item in readiness["manualAcceptance"])


def test_mvp_readiness_reports_needs_action_for_new_project(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id = _create_project(client)

    response = client.get(f"/api/projects/{project_id}/mvp/readiness")

    assert response.status_code == 200
    readiness = response.json()["readiness"]
    assert readiness["overallStatus"] == "NEEDS_ACTION"
    assert readiness["readyCount"] < readiness["totalCount"]
    pending = [
        item for item in readiness["items"]
        if item["status"] == "NEEDS_ACTION"
    ]
    assert any(item["id"] == "SOLUTION" for item in pending)
    assert any(item["id"] == "PACKAGE" for item in pending)


def _create_project(client: TestClient) -> str:
    response = client.post(
        "/api/projects",
        json={
            "name": "MVP 测试项目",
            "initialIdea": "做一个自动浇花装置",
            "selectedExpertTypes": ["structure_engineer"],
        },
    )
    assert response.status_code == 200
    return str(response.json()["workspace"]["project"]["id"])


def _confirmed_solution(tmp_path: Path, project_id: str) -> str:
    repo = SolutionRepository(ProjectRepository(tmp_path).db_path)
    solution = repo.create_solution(
        project_id,
        [
            SolutionSection(id="goal", title="项目目标", content="做一个自动浇花装置"),
            SolutionSection(
                id="hardware",
                title="硬件方案",
                content="ESP32-S3、土壤湿度传感器、水泵驱动和状态指示灯",
            ),
            SolutionSection(
                id="software",
                title="软件方案",
                content="MicroPython 定时采样，按阈值控制水泵并记录状态",
            ),
            SolutionSection(
                id="structure",
                title="结构方案",
                content="传感器支架和主控板固定底座",
            ),
        ],
    )
    confirmed = repo.confirm_solution(project_id, solution.id)
    return confirmed.id


def _build_and_confirm_real_cad(
    *,
    client: TestClient,
    data_dir: Path,
    project_id: str,
    spec_run_id: str,
    desktop_headers: dict[str, str],
    monkeypatch,
) -> dict:
    projects = ProjectRepository(data_dir)
    workspace = projects.get_workspace(project_id)
    cad_repository = CadRepository(projects.db_path)
    cad_run = cad_repository.create_draft(
        project_id=project_id,
        draft=CadDraft(
            specRunId=spec_run_id,
            templateKind="BOX_WITH_LID",
            parameters={
                "width": 80,
                "depth": 60,
                "height": 30,
                "wall_thickness": 2.4,
                "screw_posts": 4,
            },
            components=[],
            constraints={"process": "FDM", "minWallThicknessMm": 1.6},
            summary="MVP 参数化盒体与盖板",
            requestedOutputs=[
                "STEP_ASSEMBLY",
                "STL_PRINTABLE_PARTS",
                "GLB_PREVIEW",
            ],
        ),
        source_message_id=workspace.conversation.messages[0].id,
        generated_by_expert_id=next(
            expert.id
            for expert in workspace.experts
            if expert.expertType == ExpertType.STRUCTURE_ENGINEER
        ),
    )

    class DeferredCoordinator:
        def submit(self, job):
            return job

    async def deferred_coordinator():
        return DeferredCoordinator()

    monkeypatch.setattr(cad_router, "ensure_cad_coordinator", deferred_coordinator)
    queued = client.post(
        f"/api/projects/{project_id}/cad/jobs",
        json={"cadRunId": cad_run.id, "clientRequestId": "mvp-real-cad"},
        headers=desktop_headers,
    )
    assert queued.status_code == 200
    job_id = queued.json()["cadJob"]["id"]

    coordinator = CadJobCoordinator(projects.db_path, data_dir)
    asyncio.run(coordinator._execute(job_id))
    completed = client.get(f"/api/projects/{project_id}/cad/jobs/{job_id}")
    assert completed.status_code == 200
    job = completed.json()["cadJob"]
    assert job["status"] == "SUCCEEDED", job.get("error")

    ready = client.get(f"/api/projects/{project_id}/cad/runs/{cad_run.id}")
    assert ready.status_code == 200
    ready_run = ready.json()["cadRun"]
    assert ready_run["status"] == "READY_FOR_REVIEW"
    assert ready_run["validation"]["ok"] is True
    assert {item["role"] for item in ready_run["files"]} >= {
        "STEP_ASSEMBLY",
        "STL_PRINTABLE_PARTS",
        "GLB_PREVIEW",
    }

    confirmed = client.post(
        f"/api/projects/{project_id}/cad/confirm",
        json={"cadRunId": cad_run.id},
        headers=desktop_headers,
    )
    assert confirmed.status_code == 200
    return confirmed.json()["cadRun"]


def _approve_awaiting_node(
    client: TestClient,
    project_id: str,
    plan: dict,
) -> dict:
    node = next(
        item for item in plan["nodes"]
        if item["status"] == "AWAITING_APPROVAL"
    )
    response = client.post(
        f"/api/projects/{project_id}/execution-plan/{plan['id']}/approve",
        json={"nodeId": node["id"], "approved": True, "comment": "通过"},
    )
    assert response.status_code == 200
    return response.json()["plan"]
