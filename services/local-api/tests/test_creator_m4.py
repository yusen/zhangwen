from __future__ import annotations

import sqlite3
import json
import pytest
from fastapi.testclient import TestClient

from zhangwen.config import settings
from zhangwen.creator.models import CreatorCommand, CreatorCommandRequest
from zhangwen.creator.repository import CreatorRepository
from zhangwen.device_lab.models import SupportedDeviceBoardId
from zhangwen.device_lab.repository import DeviceLabRepository
from zhangwen.main import app
from zhangwen.projects.repository import ProjectRepository
from zhangwen.proposals.models import ProposalSection
from zhangwen.proposals.repository import ProposalRepository
from zhangwen.solutions.models import SolutionSection
from zhangwen.solutions.repository import SolutionRepository


HEADERS = {
    "X-Zhangwen-Host": "tauri",
    "X-Zhangwen-Capability-Token": "creator-m4-token",
}


@pytest.fixture(autouse=True)
def _runtime(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings.data_dir = tmp_path
    monkeypatch.setenv("ZHANGWEN_DESKTOP_CAPABILITY_TOKEN", "creator-m4-token")


def _request(version: int, key: str, payload: dict[str, object]) -> CreatorCommandRequest:
    return CreatorCommandRequest.model_validate(
        {"baseProjectVersion": version, "idempotencyKey": key, "payload": payload}
    )


def _prepare_creator_work(tmp_path) -> tuple[CreatorRepository, str]:
    repository = CreatorRepository(tmp_path)
    workspace = repository.create_work(
        name="Creator 数字原型",
        initial_idea="用 K10 制作温湿度提醒器",
        idempotency_key="creator-m4-create-work",
        selected_hardware_ids=["hw_seed_unihiker_k10"],
    )
    workspace = repository.execute(
        workspace.work_id,
        CreatorCommand.CONFIRM_GOAL,
        _request(
            workspace.project_version,
            "creator-m4-confirm-goal",
            {
                "statement": "制作温湿度提醒器",
                "observableBehavior": "环境过热时灯光提醒，恢复后关闭",
                "constraints": ["离线运行"],
                "successCriteria": ["超过阈值点亮", "恢复后关闭"],
            },
        ),
    ).workspace
    repository.execute(
        workspace.work_id,
        CreatorCommand.CONFIRM_SOLUTION,
        _request(
            workspace.project_version,
            "creator-m4-confirm-solution",
            {
                "summary": "K10 温湿度灯光提醒",
                "logic": "采样温湿度并按滞回阈值控制 RGB",
                "hardware": "DFRobot K10 板载 AHT20 与 RGB",
                "software": "MicroPython 采样循环与参数存储",
                "structure": "不需要结构",
                "simulation": "改变温度输入并观察 RGB 输出",
                "safety": "停止和复位时 RGB 归零",
                "bom": [{"componentId": "hw_seed_unihiker_k10", "name": "DFRobot K10", "quantity": 1}],
                "ioMap": [],
                "acceptanceScenarios": [
                    {
                        "title": "过热提醒并恢复",
                        "required": True,
                        "simulationExpected": "高温时 RGB 点亮，恢复时关闭",
                        "physicalExpected": "真机在相同阈值下完成提醒与恢复",
                    }
                ],
            },
        ),
    )
    return repository, workspace.work_id


def test_creator_solution_materializes_scene_and_only_stopped_run_can_pass(tmp_path) -> None:
    repository, work_id = _prepare_creator_work(tmp_path)
    project_repository = ProjectRepository(tmp_path)
    legacy_solution_repository = SolutionRepository(project_repository.db_path)
    legacy_solution = legacy_solution_repository.create_solution(
        work_id,
        [
            SolutionSection(
                id="legacy",
                title="旧实施建议",
                content="历史立项使用 K10，但不能覆盖 Creator 当前方案。",
            )
        ],
    )
    legacy_solution = legacy_solution_repository.confirm_solution(
        work_id, legacy_solution.id
    )
    legacy_proposal_repository = ProposalRepository(project_repository.db_path)
    legacy_proposal = legacy_proposal_repository.create_proposal(
        project_id=work_id,
        solution=legacy_solution,
        sections=[
            ProposalSection(
                id="project_overview",
                title="历史立项",
                content="历史 K10 方案。",
            ),
            ProposalSection(id="requirements", title="需求", content="温度提醒。"),
            ProposalSection(
                id="hardware_software_structure",
                title="软硬件结构",
                content="使用 DFRobot K10。",
            ),
            ProposalSection(id="implementation_plan", title="实施", content="历史计划。"),
            ProposalSection(
                id="cost_difficulty_schedule",
                title="成本",
                content="历史估算。",
            ),
            ProposalSection(
                id="risks_acceptance",
                title="风险",
                content="历史验收。",
            ),
        ],
        supersede_drafts=True,
    )
    legacy_proposal_repository.confirm_proposal(work_id, legacy_proposal.id)
    client = TestClient(app)

    scene_response = client.get(f"/api/projects/{work_id}/device-lab/scene")
    assert scene_response.status_code == 200, scene_response.json()
    scene = scene_response.json()["scene"]
    assert scene["source"]["proposalId"].startswith("csolution_")
    assert (
        scene["binding"]["solutionRevisionId"]
        == repository.workspace(work_id).confirmed_solution.id
    )
    assert scene["boardId"] == "dfrobot/dfrobot_k10"
    assert any(item["id"] == "fault-mode" for item in scene_response.json()["profile"]["channels"])

    workspace = repository.workspace(work_id)
    static_base_version = workspace.project_version
    static = client.post(
        f"/api/creator/works/{work_id}/commands/RECORD_STATIC_VALIDATION",
        headers=HEADERS,
        json={
            "baseProjectVersion": static_base_version,
            "idempotencyKey": "creator-m4-static-pass",
            "payload": {
                "passed": True,
                "summary": "当前 Creator 方案场景静态检查通过",
                "sourceId": scene["revision"],
                "bindings": {"sceneRevision": scene["revision"]},
            },
        },
    )
    assert static.status_code == 200, static.json()
    assert static.json()["workspace"]["verificationLevel"] == 2

    started = client.post(
        f"/api/projects/{work_id}/device-lab/runs",
        headers=HEADERS,
        json={
            "idempotencyKey": "creator-m4-simulation-run",
            "target": "SIMULATOR",
            "expectedSceneRevision": scene["revision"],
        },
    )
    assert started.status_code == 200, started.json()
    run = started.json()["run"]
    repeated = client.post(
        f"/api/projects/{work_id}/device-lab/runs",
        headers=HEADERS,
        json={
            "idempotencyKey": "creator-m4-simulation-run",
            "target": "SIMULATOR",
            "expectedSceneRevision": scene["revision"],
        },
    )
    assert repeated.status_code == 200
    assert repeated.json() == started.json()
    reused = client.post(
        f"/api/projects/{work_id}/device-lab/runs",
        headers=HEADERS,
        json={
            "idempotencyKey": "creator-m4-simulation-run",
            "target": "SIMULATOR",
            "expectedSceneRevision": "0" * 64,
        },
    )
    assert reused.status_code == 409
    assert reused.json()["detail"]["code"] == "DEVICE_LAB_IDEMPOTENCY_KEY_REUSED"

    running_result = client.post(
        f"/api/creator/works/{work_id}/commands/RECORD_SIMULATION",
        headers=HEADERS,
        json={
            "baseProjectVersion": static.json()["workspace"]["projectVersion"],
            "idempotencyKey": "creator-m4-running-rejected",
            "payload": {"passed": True, "summary": "不应通过", "sourceId": run["id"]},
        },
    )
    assert running_result.status_code == 409
    assert running_result.json()["detail"]["code"] == "CREATOR_SIMULATION_NOT_STOPPED"

    stopped = client.post(
        f"/api/projects/{work_id}/device-lab/runs/{run['id']}/stop",
        headers=HEADERS,
        json={},
    )
    assert stopped.status_code == 200
    workspace = repository.workspace(work_id)
    scenario_ids = ",".join(sorted(item.id for item in workspace.acceptance_scenarios))
    passed = client.post(
        f"/api/creator/works/{work_id}/commands/RECORD_SIMULATION",
        headers=HEADERS,
        json={
            "baseProjectVersion": workspace.project_version,
            "idempotencyKey": "creator-m4-simulation-pass",
            "payload": {
                "passed": True,
                "summary": "所有必需场景通过且会话已安全停止",
                "sourceId": run["id"],
                "bindings": {"scenarioIds": scenario_ids, "sceneRevision": scene["revision"]},
            },
        },
    )
    assert passed.status_code == 200, passed.json()
    assert passed.json()["workspace"]["verificationLevel"] == 3
    assert passed.json()["workspace"]["phase"] == "SIMULATION_PASSED"
    with sqlite3.connect(ProjectRepository(tmp_path).db_path) as conn:
        conn.execute(
            "DELETE FROM device_lab_scenes WHERE project_id = ?", (work_id,)
        )
    historical_retry = client.post(
        f"/api/creator/works/{work_id}/commands/RECORD_STATIC_VALIDATION",
        headers=HEADERS,
        json=json.loads(static.request.content.decode("utf-8")),
    )
    assert historical_retry.status_code == 200, historical_retry.json()
    assert historical_retry.json()["repeated"] is True
    assert historical_retry.json()["commandId"] == static.json()["commandId"]


def test_creator_static_evidence_rejects_caller_authored_source(tmp_path) -> None:
    repository, work_id = _prepare_creator_work(tmp_path)
    workspace = repository.workspace(work_id)
    response = TestClient(app).post(
        f"/api/creator/works/{work_id}/commands/RECORD_STATIC_VALIDATION",
        headers=HEADERS,
        json={
            "baseProjectVersion": workspace.project_version,
            "idempotencyKey": "creator-m4-forged-static",
            "payload": {"passed": True, "summary": "伪造成功", "sourceId": "0" * 64},
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "CREATOR_SCENE_EVIDENCE_NOT_FOUND"


def test_creator_workspace_projects_immutable_parameter_revisions(tmp_path) -> None:
    repository, work_id = _prepare_creator_work(tmp_path)
    parameter_repository = DeviceLabRepository(ProjectRepository(tmp_path).db_path)
    first = parameter_repository.save_parameter_set(
        project_id=work_id,
        board_id=SupportedDeviceBoardId.DFROBOT_K10,
        profile_revision="k10-functional-v1",
        label="保守阈值",
        values={"temperature-threshold": 30.0, "hysteresis": 2.0},
        idempotency_key="creator-m4-params-first",
        request_hash="creator-m4-params-first-hash",
    )
    second = parameter_repository.save_parameter_set(
        project_id=work_id,
        board_id=SupportedDeviceBoardId.DFROBOT_K10,
        profile_revision="k10-functional-v1",
        label="高温环境",
        values={"temperature-threshold": 34.0, "hysteresis": 3.0},
        idempotency_key="creator-m4-params-second",
        request_hash="creator-m4-params-second-hash",
    )
    repeated = parameter_repository.save_parameter_set(
        project_id=work_id,
        board_id=SupportedDeviceBoardId.DFROBOT_K10,
        profile_revision="k10-functional-v1",
        label="conservative threshold",
        values={"temperature-threshold": 30.0, "hysteresis": 2.0},
        idempotency_key="creator-m4-params-first",
        request_hash="creator-m4-params-first-hash",
    )
    assert repeated.id == first.id
    with pytest.raises(ValueError, match="IDEMPOTENCY_KEY_REUSED"):
        parameter_repository.save_parameter_set(
            project_id=work_id,
            board_id=SupportedDeviceBoardId.DFROBOT_K10,
            profile_revision="k10-functional-v1",
            label="changed",
            values={"temperature-threshold": 31.0},
            idempotency_key="creator-m4-params-first",
            request_hash="changed-hash",
        )

    workspace = repository.workspace(work_id)
    assert [item.id for item in workspace.parameter_revisions] == [second.id, first.id]
    assert [item.revision for item in workspace.parameter_revisions] == [2, 1]
    assert workspace.parameter_revisions[0].board_id == "dfrobot/dfrobot_k10"
    assert workspace.parameter_revisions[0].values == {
        "temperature-threshold": 34.0,
        "hysteresis": 3.0,
    }
