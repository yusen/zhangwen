from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from zhangwen.config import settings
from zhangwen.creator.models import (
    CreatorCommand,
    CreatorCommandRequest,
    CreatorJob,
    CreateCreatorWorkRequest,
    ParameterRevision,
)
from zhangwen.creator.repository import CreatorError, CreatorRepository
from zhangwen.main import app
from zhangwen.projects.models import ExpertType
from zhangwen.projects.repository import ProjectRepository


def _goal_payload(name: str = "自动浇花") -> dict[str, object]:
    return {
        "statement": f"制作{name}作品",
        "observableBehavior": "土壤干燥时启动水泵，湿润后停止",
        "constraints": ["水泵默认关闭", "离线可运行"],
        "successCriteria": ["低于阈值时启动", "达到阈值时停止"],
    }


def _solution_payload(name: str = "自动浇花") -> dict[str, object]:
    return {
        "summary": f"{name}当前实施方案",
        "logic": "读取湿度，经过滞回判断后控制水泵",
        "hardware": "主控、土壤湿度传感器、MOSFET 驱动和独立水泵电源",
        "software": "受控 MicroPython 主循环与看门狗",
        "structure": "防溅控制盒",
        "simulation": "注入湿度值和传感器断线，检查水泵状态",
        "safety": "水泵限时运行，断线和重启时关闭",
        "bom": [
            {"componentId": "sensor", "name": "湿度传感器", "quantity": 1},
            {"componentId": "pump-driver", "name": "MOSFET 驱动", "quantity": 1},
        ],
        "ioMap": [{"signal": "pump", "pin": "D1", "purpose": "控制水泵"}],
        "acceptanceScenarios": [
            {
                "title": "干燥启动并在湿润后停止",
                "required": True,
                "simulationExpected": "输出从关闭切换为启动再回到关闭",
                "physicalExpected": "水泵按阈值启动并在安全时间内停止",
            }
        ],
    }


def _request(version: int, key: str, payload: dict[str, object]) -> CreatorCommandRequest:
    return CreatorCommandRequest.model_validate(
        {
            "baseProjectVersion": version,
            "idempotencyKey": key,
            "payload": payload,
        }
    )


def _created_work(tmp_path) -> tuple[CreatorRepository, str]:
    repository = CreatorRepository(tmp_path)
    workspace = repository.create_work(
        name="Creator M1 测试",
        initial_idea="制作一个自动浇花装置",
        idempotency_key="creator-create-0001",
        selected_hardware_ids=[],
    )
    return repository, workspace.work_id


def test_creator_boundaries_forbid_extra_fields() -> None:
    with pytest.raises(ValidationError):
        CreateCreatorWorkRequest.model_validate(
            {
                "initialIdea": "做一个作品",
                "idempotencyKey": "creator-test-0001",
                "unknown": True,
            }
        )

    with pytest.raises(ValidationError):
        CreatorCommandRequest.model_validate(
            {
                "baseProjectVersion": 0,
                "idempotencyKey": "creator-test-0002",
                "payload": {},
                "unknown": True,
            }
        )

    with pytest.raises(ValidationError):
        CreatorJob.model_validate(
            {
                "id": "job-1",
                "workId": "work-1",
                "solutionRevisionId": "solution-1",
                "kind": "DIGITAL_PROTOTYPE",
                "status": "QUEUED",
                "progress": 0,
                "message": None,
                "result": None,
                "createdAt": "2026-07-31T00:00:00+00:00",
                "updatedAt": "2026-07-31T00:00:00+00:00",
                "startedAt": None,
                "completedAt": None,
                "unknown": True,
            }
        )

    with pytest.raises(ValidationError):
        ParameterRevision.model_validate(
            {
                "id": "params-1",
                "workId": "work-1",
                "boardId": "board-1",
                "profileRevision": "profile-1",
                "revision": 1,
                "label": "默认参数",
                "values": {"threshold": 30},
                "createdAt": "2026-07-31T00:00:00+00:00",
                "unknown": True,
            }
        )


def test_v30_migration_adds_creator_tables_without_losing_legacy_project(tmp_path) -> None:
    projects = ProjectRepository(tmp_path)
    legacy = projects.create_project(
        "历史教学项目",
        "保留已有对话和产物",
        selected_expert_types=[ExpertType.PROBLEM_GUIDE],
    )
    with sqlite3.connect(projects.db_path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 31
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert {
            "creator_work_state",
            "creator_goal_revisions",
            "creator_solution_revisions",
            "creator_acceptance_scenarios",
            "creator_evidence",
            "creator_commands",
            "creator_events",
            "creator_jobs",
        }.issubset(tables)

    projected = CreatorRepository(tmp_path).workspace(legacy.project.id)
    assert projected.legacy is True
    assert projected.needs_organization is True
    assert projected.initial_idea == "保留已有对话和产物"
    assert projected.current_goal is not None
    assert projected.current_goal.status == "DRAFT"
    assert projects.get_workspace(legacy.project.id).conversation.id == legacy.conversation.id


def test_creator_goal_command_is_versioned_idempotent_and_strict(tmp_path) -> None:
    repository, work_id = _created_work(tmp_path)
    initial = repository.workspace(work_id)
    result = repository.execute(
        work_id,
        CreatorCommand.CONFIRM_GOAL,
        _request(initial.project_version, "goal-confirm-0001", _goal_payload()),
    )
    assert result.repeated is False
    assert result.workspace.project_version == initial.project_version + 1
    assert result.workspace.verification_level == 1
    assert result.workspace.current_goal is not None
    assert result.workspace.current_goal.status == "CONFIRMED"
    assert result.workspace.next_action.id == "confirm-solution"

    repeated = repository.execute(
        work_id,
        CreatorCommand.CONFIRM_GOAL,
        _request(initial.project_version, "goal-confirm-0001", _goal_payload()),
    )
    assert repeated.repeated is True
    assert repeated.command_id == result.command_id
    assert repeated.workspace.project_version == result.workspace.project_version

    with pytest.raises(CreatorError) as conflict:
        repository.execute(
            work_id,
            CreatorCommand.SAVE_GOAL,
            _request(initial.project_version, "goal-save-stale-0001", _goal_payload("旧版本")),
        )
    assert conflict.value.code == "CREATOR_VERSION_CONFLICT"
    assert conflict.value.status_code == 409

    with pytest.raises(CreatorError) as invalid:
        repository.execute(
            work_id,
            CreatorCommand.SAVE_GOAL,
            _request(
                result.workspace.project_version,
                "goal-invalid-0001",
                {**_goal_payload(), "unknown": True},
            ),
        )
    assert invalid.value.code == "CREATOR_COMMAND_PAYLOAD_INVALID"


def test_confirming_solution_also_confirms_the_current_conversation_goal(
    tmp_path,
) -> None:
    repository, work_id = _created_work(tmp_path)
    workspace = repository.workspace(work_id)
    workspace = repository.execute(
        work_id,
        CreatorCommand.SAVE_GOAL,
        _request(
            workspace.project_version,
            "single-confirm-goal-draft-0001",
            _goal_payload(),
        ),
    ).workspace

    confirmed = repository.execute(
        work_id,
        CreatorCommand.CONFIRM_SOLUTION,
        _request(
            workspace.project_version,
            "single-confirm-solution-0001",
            _solution_payload(),
        ),
    ).workspace

    assert confirmed.confirmed_goal is not None
    assert confirmed.confirmed_goal.status == "CONFIRMED"
    assert confirmed.confirmed_solution is not None
    assert confirmed.confirmed_solution.status == "CONFIRMED"
    assert confirmed.active_stage == "DIGITAL_PROTOTYPE"
    assert confirmed.next_action.id == "static-validation"


def test_project_book_is_optional_and_bound_to_confirmed_solution(tmp_path) -> None:
    repository, work_id = _created_work(tmp_path)
    workspace = repository.workspace(work_id)
    workspace = repository.execute(
        work_id,
        CreatorCommand.CONFIRM_GOAL,
        _request(workspace.project_version, "book-goal-0001", _goal_payload()),
    ).workspace
    workspace = repository.execute(
        work_id,
        CreatorCommand.CONFIRM_SOLUTION,
        _request(workspace.project_version, "book-solution-0001", _solution_payload()),
    ).workspace
    assert workspace.project_book_projection.status == "EMPTY"

    workspace = repository.execute(
        work_id,
        CreatorCommand.GENERATE_PROJECT_BOOK,
        _request(workspace.project_version, "book-generate-0001", {}),
    ).workspace
    book = workspace.project_book_projection
    assert book.status == "CURRENT"
    assert book.revision == 1
    assert book.solution_revision_id == workspace.confirmed_solution.id
    assert [section.title for section in book.sections] == [
        "项目目标",
        "约束与成功标准",
        "实施方案",
        "结构、仿真与安全",
        "验收场景",
    ]

    workspace = repository.execute(
        work_id,
        CreatorCommand.CONFIRM_SOLUTION,
        _request(
            workspace.project_version,
            "book-solution-0002",
            _solution_payload("修改后的自动浇花"),
        ),
    ).workspace
    assert workspace.project_book_projection.status == "STALE"


def test_evidence_ladder_keeps_deployment_separate_and_invalidates_downstream(tmp_path) -> None:
    repository, work_id = _created_work(tmp_path)
    workspace = repository.workspace(work_id)
    workspace = repository.execute(
        work_id,
        CreatorCommand.CONFIRM_GOAL,
        _request(workspace.project_version, "ladder-goal-0001", _goal_payload()),
    ).workspace
    workspace = repository.execute(
        work_id,
        CreatorCommand.CONFIRM_SOLUTION,
        _request(workspace.project_version, "ladder-solution-0001", _solution_payload()),
    ).workspace
    assert len(workspace.acceptance_scenarios) == 1
    assert workspace.verification_level == 1

    for command, key, source in (
        (CreatorCommand.RECORD_STATIC_VALIDATION, "static-pass-0001", "static-report"),
        (CreatorCommand.RECORD_SIMULATION, "simulation-pass-0001", "sim-run"),
        (CreatorCommand.RECORD_DEVICE_CONNECTION, "device-pass-0001", "device-session"),
        (CreatorCommand.RECORD_DEPLOYMENT, "deploy-pass-0001", "device-operation"),
    ):
        workspace = repository.execute(
            work_id,
            command,
            _request(
                workspace.project_version,
                key,
                {"passed": True, "summary": f"{command.value} 通过", "sourceId": source},
            ),
        ).workspace

    assert workspace.verification_level == 4
    assert workspace.phase == "DEPLOYED"
    assert workspace.next_action.id == "physical-validation"

    workspace = repository.execute(
        work_id,
        CreatorCommand.RECORD_PHYSICAL_BEHAVIOR,
        _request(
            workspace.project_version,
            "physical-pass-0001",
            {"passed": True, "summary": "真机阈值与安全停止行为通过", "sourceId": "run-1"},
        ),
    ).workspace
    assert workspace.verification_level == 5

    workspace = repository.execute(
        work_id,
        CreatorCommand.CONFIRM_SOLUTION,
        _request(
            workspace.project_version,
            "ladder-solution-0002",
            _solution_payload("修改阈值后的自动浇花"),
        ),
    ).workspace
    assert workspace.verification_level == 1
    stale_kinds = {item.kind for item in workspace.evidence if item.status == "STALE"}
    assert {
        "STATIC_VALIDATION",
        "SIMULATION",
        "DEVICE_CONNECTION",
        "DEPLOYMENT",
        "PHYSICAL_BEHAVIOR",
    }.issubset(stale_kinds)


def test_creator_api_returns_one_authoritative_next_action(tmp_path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    created = client.post(
        "/api/creator/works",
        json={
            "name": "API 作品",
            "initialIdea": "制作环境提醒灯",
            "idempotencyKey": "creator-api-create-0001",
        },
    )
    assert created.status_code == 200, created.text
    workspace = created.json()["workspace"]
    assert workspace["schemaVersion"] == 1
    assert workspace["nextAction"]["id"] == "confirm-solution"
    assert workspace["nextAction"]["enabled"] is False
    assert "自动形成推荐方案" in workspace["nextAction"]["blockedReason"]

    listed = client.get("/api/creator/works")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["works"]] == [workspace["workId"]]

    event_stream = client.get(
        f"/api/creator/works/{workspace['workId']}/events"
    )
    assert event_stream.status_code == 200
    metric_envelopes = [
        json.loads(line.removeprefix("data: "))
        for line in event_stream.text.splitlines()
        if line.startswith("data: ")
    ]
    assert metric_envelopes
    assert metric_envelopes[0]["type"] == "METRIC"
    assert "workId" not in metric_envelopes[0]

    extra = client.post(
        f"/api/creator/works/{workspace['workId']}/commands/CONFIRM_GOAL",
        json={
            "baseProjectVersion": workspace["projectVersion"],
            "idempotencyKey": "creator-api-goal-0001",
            "payload": {**_goal_payload(), "unknown": True},
        },
    )
    assert extra.status_code == 400
    assert extra.json()["detail"]["code"] == "CREATOR_COMMAND_PAYLOAD_INVALID"


def test_web_host_cannot_forge_physical_creator_evidence(tmp_path) -> None:
    settings.data_dir = tmp_path
    repository, work_id = _created_work(tmp_path)
    workspace = repository.workspace(work_id)
    client = TestClient(app)
    response = client.post(
        f"/api/creator/works/{work_id}/commands/RECORD_DEVICE_CONNECTION",
        headers={"x-zhangwen-host": "web"},
        json={
            "baseProjectVersion": workspace.project_version,
            "idempotencyKey": "forged-device-0001",
            "payload": {"passed": True, "summary": "伪造连接"},
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "HOST_CAPABILITY_UNAVAILABLE"
