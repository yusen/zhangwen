from __future__ import annotations

import asyncio
import sqlite3

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from zhangwen.clarification.service import ClarificationRoundModel
from zhangwen.config import settings
from zhangwen.creator.jobs import CreatorJobExecutionError, CreatorJobRunner
from zhangwen.creator.models import (
    ConversationProjectDraftV1,
    CreatorCommand,
    CreatorCommandRequest,
)
from zhangwen.creator.repository import CreatorRepository
from zhangwen.device_lab.repository import DeviceLabRepository
from zhangwen.main import app
from zhangwen.llm.contracts import LLMConfig, LLMModelId
from zhangwen.proposals.repository import ProposalRepository
from zhangwen.projects.repository import ProjectRepository
from zhangwen.solutions.models import SolutionSection
from zhangwen.solutions.repository import SolutionRepository
from tests.fakes import StructuredFakeProvider, fake_proposal_sections


def _request(version: int, key: str, payload: dict[str, object]) -> CreatorCommandRequest:
    return CreatorCommandRequest.model_validate(
        {
            "baseProjectVersion": version,
            "idempotencyKey": key,
            "payload": payload,
        }
    )


def _goal_payload() -> dict[str, object]:
    return {
        "statement": "制作会在土壤干燥时自动浇水的作品",
        "observableBehavior": "干燥时启动水泵，湿润或超时后停止",
        "constraints": ["离线工作", "水泵默认关闭"],
        "successCriteria": ["低于阈值启动", "达到阈值停止"],
    }


def _solution_payload() -> dict[str, object]:
    return {
        "summary": "湿度闭环浇水方案",
        "logic": "采样、滞回判断、限时驱动和故障回退",
        "hardware": "主控、湿度传感器、MOSFET、水泵与独立供电",
        "software": "受控主循环、参数存储和看门狗",
        "structure": "防溅控制盒与水管固定",
        "simulation": "注入湿度和断线故障，观察输出状态",
        "safety": "复位、断线和超时均关闭水泵",
        "bom": [{"componentId": "pump", "name": "直流水泵", "quantity": 1}],
        "ioMap": [{"signal": "pump", "pin": "D1", "purpose": "水泵使能"}],
        "acceptanceScenarios": [
            {
                "title": "干燥启动、湿润停止",
                "required": True,
                "simulationExpected": "输出按阈值切换并在断线时关闭",
                "physicalExpected": "真实水泵按阈值运行且超时停止",
            }
        ],
    }


def test_low_completeness_without_project_specific_question_is_rejected() -> None:
    with pytest.raises(ValidationError, match="project-specific question"):
        ClarificationRoundModel.model_validate(
            {"questions": [], "completeness": 45, "message": "还需要补充信息。"}
        )

    with pytest.raises(ValidationError, match="generic clarification fallback"):
        ClarificationRoundModel.model_validate(
            {
                "questions": [
                    {
                        "id": "creator_primary_outcome",
                        "type": "TEXT",
                        "question": "这个作品最重要、必须让人看到的结果是什么？",
                        "options": [],
                    }
                ],
                "completeness": 45,
                "message": "还需要补充信息。",
            }
        )

    with pytest.raises(ValidationError, match="next concrete product decision"):
        ClarificationRoundModel.model_validate(
            {
                "questions": [
                    {
                        "id": "continue_or_not",
                        "type": "SINGLE_SELECT",
                        "question": "目前信息不少了，接下来你希望怎么继续？",
                        "options": [
                            {"id": "continue", "label": "继续补充需求"},
                            {"id": "generate", "label": "生成方案"},
                        ],
                    }
                ],
                "completeness": 70,
                "message": "请选择下一步。",
            }
        )

    ready = ClarificationRoundModel.model_validate(
        {"questions": [], "completeness": 80, "message": "可以形成方案。"}
    )
    assert ready.questions == []


def test_conversation_project_draft_is_idempotently_projected_and_preserves_manual_draft(
    tmp_path,
) -> None:
    creator = CreatorRepository(tmp_path)
    work = creator.create_work(
        name="自动浇花",
        initial_idea="制作自动浇花装置",
        idempotency_key="creator-projection-create",
        selected_hardware_ids=[],
    )
    candidate = ConversationProjectDraftV1(
        useScenario="在家中根据土壤湿度自动浇水",
        observableBehavior="干燥时启动水泵，湿润或超时后停止",
        constraints=["断线时水泵归零"],
        successCriteria=["低于阈值启动", "达到阈值停止"],
        missingFields=[],
    )

    first = creator.project_conversation_draft(
        work.work_id,
        source_message_id="msg_projection_1",
        source_turn_id="turn_projection_1",
        draft=candidate,
    )
    repeated = creator.project_conversation_draft(
        work.work_id,
        source_message_id="msg_projection_1",
        source_turn_id="turn_projection_1",
        draft=candidate,
    )
    projected = creator.workspace(work.work_id)

    assert repeated.id == first.id
    assert projected.draft_goal is not None
    assert projected.draft_goal.source_type == "CONVERSATION"
    assert projected.draft_goal.source_message_id == "msg_projection_1"
    assert projected.conversation_projection_status.status == "CURRENT"
    with sqlite3.connect(creator._db_path) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM creator_goal_revisions WHERE project_id = ?",
            (work.work_id,),
        ).fetchone()[0] == 1

    manual_payload = {
        "statement": "人工目标草稿",
        "observableBehavior": "由三师专业模式编辑",
        "constraints": ["保留人工修改"],
        "successCriteria": ["人工确认后生效"],
    }
    manual = creator.execute(
        work.work_id,
        CreatorCommand.SAVE_GOAL,
        _request(
            projected.project_version,
            "creator-projection-manual",
            manual_payload,
        ),
    ).workspace
    conflict = creator.project_conversation_draft(
        work.work_id,
        source_message_id="msg_projection_2",
        source_turn_id="turn_projection_2",
        draft=candidate.model_copy(
            update={"observable_behavior": "新的对话候选不覆盖人工草稿"}
        ),
    )
    after_conflict = creator.workspace(work.work_id)

    assert manual.draft_goal is not None
    assert conflict.status == "CONFLICT"
    assert after_conflict.draft_goal is not None
    assert after_conflict.draft_goal.statement == "人工目标草稿"
    assert after_conflict.conversation_projection_status.status == "CONFLICT"


def test_legacy_chat_solution_draft_is_projected_into_creator(tmp_path) -> None:
    creator = CreatorRepository(tmp_path)
    work = creator.create_work(
        name="对话方案适配",
        initial_idea="做一个浇水作品",
        idempotency_key="creator-m3-adapter-create",
        selected_hardware_ids=[],
    )
    db_path = ProjectRepository(tmp_path).db_path
    draft = SolutionRepository(db_path).create_solution(
        work.work_id,
        [
            SolutionSection(id="logic", title="工作逻辑", content="读取湿度后控制水泵"),
            SolutionSection(id="hardware", title="硬件", content="湿度传感器与水泵驱动"),
        ],
    )

    projected = creator.workspace(work.work_id)
    assert projected.current_solution is not None
    assert projected.current_solution.id == f"legacy-solution:{draft.id}"
    assert projected.current_solution.status == "DRAFT"
    assert projected.current_solution.logic == "读取湿度后控制水泵"


def test_confirmed_project_book_synchronizes_creator_goal_and_solution(tmp_path) -> None:
    creator = CreatorRepository(tmp_path)
    work = creator.create_work(
        name="智能垃圾桶",
        initial_idea="制作智能垃圾桶",
        idempotency_key="creator-m3-confirmed-plan-create",
        selected_hardware_ids=[],
    )
    db_path = ProjectRepository(tmp_path).db_path
    solution_repository = SolutionRepository(db_path)
    draft = solution_repository.create_solution(
        work.work_id,
        [
            SolutionSection(
                id="goal",
                title="项目目标",
                content="靠近时桶盖自动打开，离开后自动关闭。",
            ),
            SolutionSection(
                id="functional_logic",
                title="工作逻辑",
                content="测距、滞回判断并控制舵机。",
            ),
            SolutionSection(
                id="hardware",
                title="硬件组成",
                content="K10、超声波传感器和舵机。",
            ),
            SolutionSection(
                id="software",
                title="软件模块",
                content="距离采集、状态机、舵机控制和日志。",
            ),
            SolutionSection(
                id="structure",
                title="结构实现",
                content="桌面垃圾桶箱体、桶盖转轴和舵机支架。",
            ),
            SolutionSection(
                id="risks",
                title="风险与限制",
                content="舵机堵转时必须超时回关。",
            ),
        ],
    )
    confirmed_solution = solution_repository.confirm_solution(work.work_id, draft.id)
    proposal_repository = ProposalRepository(db_path)
    proposal = proposal_repository.create_from_solution(
        work.work_id,
        confirmed_solution,
        fake_proposal_sections("桶盖开合验收"),
    )
    approved_proposal = proposal_repository.confirm_proposal(work.work_id, proposal.id)

    projected = creator.workspace(work.work_id)

    assert projected.current_goal is not None
    assert projected.current_goal.status == "CONFIRMED"
    assert projected.current_solution is not None
    assert projected.current_solution.status == "CONFIRMED"
    assert projected.current_solution.logic == "测距、滞回判断并控制舵机。"
    assert projected.current_solution.hardware == "K10、超声波传感器和舵机。"
    assert projected.phase == "DIGITAL_BUILDING"
    assert projected.active_stage == "DIGITAL_PROTOTYPE"
    assert projected.next_action.id == "static-validation"
    assert len(projected.acceptance_scenarios) == 1

    with sqlite3.connect(db_path) as conn:
        source_proposal_id = conn.execute(
            """
            SELECT source_proposal_id FROM creator_solution_revisions
            WHERE project_id = ? AND status = 'CONFIRMED'
            """,
            (work.work_id,),
        ).fetchone()
        assert source_proposal_id == (approved_proposal.id,)
        assert conn.execute(
            """
            SELECT COUNT(*) FROM creator_evidence
            WHERE project_id = ? AND kind = 'GOAL_CONFIRMATION'
              AND status = 'CURRENT' AND passed = 1
            """,
            (work.work_id,),
        ).fetchone() == (1,)

    repeated = creator.workspace(work.work_id)
    assert repeated.current_goal is not None
    assert repeated.current_goal.id == projected.current_goal.id
    assert repeated.current_solution is not None
    assert repeated.current_solution.id == projected.current_solution.id


def test_confirm_solution_queues_real_creator_materialization_jobs(tmp_path) -> None:
    creator = CreatorRepository(tmp_path)
    workspace = creator.create_work(
        name="纵向闭环",
        initial_idea="制作自动浇水作品",
        idempotency_key="creator-m3-flow-create",
        selected_hardware_ids=[],
    )
    workspace = creator.execute(
        workspace.work_id,
        CreatorCommand.CONFIRM_GOAL,
        _request(workspace.project_version, "creator-m3-goal-confirm", _goal_payload()),
    ).workspace
    base_version = workspace.project_version
    confirmed = creator.execute(
        workspace.work_id,
        CreatorCommand.CONFIRM_SOLUTION,
        _request(base_version, "creator-m3-solution-confirm", _solution_payload()),
    )
    workspace = confirmed.workspace

    assert workspace.phase == "DIGITAL_BUILDING"
    assert workspace.active_stage == "DIGITAL_PROTOTYPE"
    assert workspace.current_solution is not None
    assert workspace.current_solution.status == "CONFIRMED"
    assert len(workspace.acceptance_scenarios) == 1
    assert {job.kind for job in workspace.jobs} == {
        "CODE_PREPARATION",
        "DIGITAL_PROTOTYPE",
        "STRUCTURE_DRAFT",
    }
    assert all(job.status == "QUEUED" for job in workspace.jobs)
    jobs = [event["payload"] for event in creator.events(workspace.work_id) if event["type"] == "JOB"]
    assert {job["kind"] for job in jobs} == {
        "CODE_PREPARATION",
        "DIGITAL_PROTOTYPE",
        "STRUCTURE_DRAFT",
    }
    assert all(job["status"] == "QUEUED" for job in jobs)
    assert {job["jobId"] for job in jobs} == {job.id for job in workspace.jobs}

    repeated = creator.execute(
        workspace.work_id,
        CreatorCommand.CONFIRM_SOLUTION,
        _request(base_version, "creator-m3-solution-confirm", _solution_payload()),
    )
    assert repeated.repeated is True
    assert {job.id for job in repeated.workspace.jobs} == {
        job.id for job in workspace.jobs
    }

    db_path = ProjectRepository(tmp_path).db_path
    with sqlite3.connect(db_path) as conn:
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM creator_jobs WHERE project_id = ?",
                (workspace.work_id,),
            ).fetchone()[0]
            == 3
        )

    async def consume_jobs() -> None:
        async def succeed(job, progress):
            progress(50, "Fake worker 正在处理正式 Job。")
            return {"materializedBy": "fake-worker", "kind": job.kind.value}

        runner = CreatorJobRunner(
            db_path,
            tmp_path,
            handlers={kind: succeed for kind in {job.kind for job in workspace.jobs}},
        )
        await runner.start()
        runner.submit()
        await runner.wait_until_idle()
        await runner.stop()

    asyncio.run(consume_jobs())

    after_job = creator.workspace(workspace.work_id)
    assert after_job.phase == "DIGITAL_BUILDING"
    assert after_job.verification_level == 1
    assert all(job.status == "SUCCEEDED" for job in after_job.jobs)
    assert all(job.progress == 100 for job in after_job.jobs)
    assert all(job.result and job.result["materializedBy"] == "fake-worker" for job in after_job.jobs)
    transitions = [
        event["payload"]
        for event in creator.events(workspace.work_id)
        if event["type"] == "JOB"
    ]
    assert {"QUEUED", "RUNNING", "SUCCEEDED"}.issubset(
        {str(event["status"]) for event in transitions}
    )


def test_creator_job_runner_recovers_interrupted_work_and_projects_failure_and_cancel(
    tmp_path,
) -> None:
    creator = CreatorRepository(tmp_path)
    workspace = creator.create_work(
        name="Job 恢复",
        initial_idea="制作需要结构的自动浇水作品",
        idempotency_key="creator-job-recovery-create",
        selected_hardware_ids=[],
    )
    workspace = creator.execute(
        workspace.work_id,
        CreatorCommand.CONFIRM_GOAL,
        _request(
            workspace.project_version,
            "creator-job-recovery-goal",
            _goal_payload(),
        ),
    ).workspace
    workspace = creator.execute(
        workspace.work_id,
        CreatorCommand.CONFIRM_SOLUTION,
        _request(
            workspace.project_version,
            "creator-job-recovery-solution",
            _solution_payload(),
        ),
    ).workspace
    db_path = ProjectRepository(tmp_path).db_path
    code_job = next(job for job in workspace.jobs if job.kind == "CODE_PREPARATION")
    structure_job = next(job for job in workspace.jobs if job.kind == "STRUCTURE_DRAFT")

    async def exercise_runner() -> None:
        interrupted = asyncio.Event()

        async def hang(_job, progress):
            progress(25, "等待模拟进程重启。")
            interrupted.set()
            await asyncio.Event().wait()
            return {}

        first = CreatorJobRunner(
            db_path,
            tmp_path,
            handlers={code_job.kind: hang},
        )
        await first.start()
        first.submit()
        await asyncio.wait_for(interrupted.wait(), timeout=2)
        await first.stop()

        structure_running = asyncio.Event()
        structure_release = asyncio.Event()

        async def recovered_success(job, progress):
            progress(60, "已从持久队列恢复。")
            return {"recovered": job.id == code_job.id}

        async def fail_digital(_job, _progress):
            raise CreatorJobExecutionError(
                "CREATOR_DIGITAL_FAKE_FAILED",
                "Fake 数字原型 worker 报告失败。",
            )

        async def wait_for_cancel(_job, progress):
            progress(40, "等待取消。")
            structure_running.set()
            await structure_release.wait()
            return {"shouldNotCommit": True}

        second = CreatorJobRunner(
            db_path,
            tmp_path,
            handlers={
                code_job.kind: recovered_success,
                next(job.kind for job in workspace.jobs if job.kind == "DIGITAL_PROTOTYPE"): fail_digital,
                structure_job.kind: wait_for_cancel,
            },
        )
        await second.start()
        second.submit()
        await asyncio.wait_for(structure_running.wait(), timeout=2)
        canceled, repeated = second.cancel(
            workspace.work_id,
            structure_job.id,
            idempotency_key="creator-job-cancel-001",
        )
        assert repeated is False
        assert canceled.status == "CANCELED"
        repeated_cancel, repeated = second.cancel(
            workspace.work_id,
            structure_job.id,
            idempotency_key="creator-job-cancel-001",
        )
        assert repeated is True
        assert repeated_cancel.status == "CANCELED"
        structure_release.set()
        await second.wait_until_idle()
        await second.stop()

    asyncio.run(exercise_runner())

    projected = creator.workspace(workspace.work_id)
    statuses = {job.kind.value: job.status.value for job in projected.jobs}
    assert statuses == {
        "CODE_PREPARATION": "SUCCEEDED",
        "DIGITAL_PROTOTYPE": "FAILED",
        "STRUCTURE_DRAFT": "CANCELED",
    }
    code = next(job for job in projected.jobs if job.id == code_job.id)
    assert code.result == {"recovered": True}
    events = [
        event["payload"]
        for event in creator.events(workspace.work_id)
        if event["type"] == "JOB"
    ]
    assert any(
        event["jobId"] == code_job.id
        and event["status"] == "QUEUED"
        and event.get("reason") == "PROCESS_RESTART_RECOVERY"
        for event in events
    )


def test_creator_job_cancel_command_api_is_persistently_idempotent(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings.data_dir = tmp_path
    monkeypatch.setenv(
        "ZHANGWEN_DESKTOP_CAPABILITY_TOKEN",
        "creator-job-command-token",
    )
    creator = CreatorRepository(tmp_path)
    workspace = creator.create_work(
        name="取消 Job",
        initial_idea="建立可取消的 Creator 任务",
        idempotency_key="creator-job-api-create",
        selected_hardware_ids=[],
    )
    workspace = creator.execute(
        workspace.work_id,
        CreatorCommand.CONFIRM_GOAL,
        _request(workspace.project_version, "creator-job-api-goal", _goal_payload()),
    ).workspace
    workspace = creator.execute(
        workspace.work_id,
        CreatorCommand.CONFIRM_SOLUTION,
        _request(
            workspace.project_version,
            "creator-job-api-solution",
            _solution_payload(),
        ),
    ).workspace
    job = next(item for item in workspace.jobs if item.kind == "CODE_PREPARATION")
    runner = CreatorJobRunner(ProjectRepository(tmp_path).db_path, tmp_path)

    async def passive_runner() -> CreatorJobRunner:
        return runner

    monkeypatch.setattr(
        "zhangwen.creator.router.ensure_creator_job_runner",
        passive_runner,
    )
    headers = {
        "X-Zhangwen-Host": "tauri",
        "X-Zhangwen-Capability-Token": "creator-job-command-token",
    }
    url = (
        f"/api/creator/works/{workspace.work_id}/jobs/{job.id}"
        "/commands/CANCEL"
    )
    first = TestClient(app).post(
        url,
        headers=headers,
        json={"idempotencyKey": "creator-job-api-cancel-001"},
    )
    assert first.status_code == 200, first.json()
    assert first.json()["job"]["status"] == "CANCELED"
    assert first.json()["repeated"] is False

    repeated = TestClient(app).post(
        url,
        headers=headers,
        json={"idempotencyKey": "creator-job-api-cancel-001"},
    )
    assert repeated.status_code == 200, repeated.json()
    assert repeated.json()["job"]["status"] == "CANCELED"
    assert repeated.json()["repeated"] is True


def test_production_job_handlers_only_succeed_from_real_persisted_results(
    tmp_path,
) -> None:
    creator = CreatorRepository(tmp_path)
    workspace = creator.create_work(
        name="真实 Job 来源",
        initial_idea="用 K10 制作环境提醒器",
        idempotency_key="creator-job-real-source-create",
        selected_hardware_ids=["hw_seed_unihiker_k10"],
    )
    workspace = creator.execute(
        workspace.work_id,
        CreatorCommand.CONFIRM_GOAL,
        _request(
            workspace.project_version,
            "creator-job-real-source-goal",
            _goal_payload(),
        ),
    ).workspace
    payload = {
        **_solution_payload(),
        "structure": "不需要结构",
        "software": "受控 MicroPython 主循环与本地 MQTT Broker 消息总线",
    }
    workspace = creator.execute(
        workspace.work_id,
        CreatorCommand.CONFIRM_SOLUTION,
        _request(
            workspace.project_version,
            "creator-job-real-source-solution",
            payload,
        ),
    ).workspace
    db_path = ProjectRepository(tmp_path).db_path

    async def run_production_handlers() -> None:
        runner = CreatorJobRunner(db_path, tmp_path)
        await runner.start()
        runner.submit()
        await runner.wait_until_idle()
        await runner.stop()

    asyncio.run(run_production_handlers())

    projected = creator.workspace(workspace.work_id)
    code = next(job for job in projected.jobs if job.kind == "CODE_PREPARATION")
    digital = next(job for job in projected.jobs if job.kind == "DIGITAL_PROTOTYPE")
    assert code.status == "FAILED"
    assert code.result == {
        "error": {
            "code": "CREATOR_CODE_GENERATOR_UNAVAILABLE",
            "retryable": True,
        }
    }
    assert digital.status == "SUCCEEDED"
    assert digital.result is not None
    assert digital.result["materialization"] == "DEVICE_LAB_SCENE"
    scene = DeviceLabRepository(db_path).get_current_scene(workspace.work_id)
    assert scene is not None
    assert digital.result["sceneRevision"] == scene.revision
    external = {item.name: item.category for item in scene.components if item.role == "external"}
    assert any("湿度" in name and category == "SENSOR" for name, category in external.items())
    assert any("驱动" in name and category == "ACTUATOR" for name, category in external.items())
    assert any("水泵" in name and "驱动" not in name for name in external)
    assert any(category == "POWER" for category in external.values())
    assert any(
        item.category == "SERVICE" and item.protocol == "MQTT"
        for item in scene.components
    )
    topology = {
        (item.fromComponentId, item.toComponentId, item.protocol)
        for item in scene.connections
    }
    driver = next(
        item.id for item in scene.components if "驱动" in item.name
    )
    pump = next(
        item.id
        for item in scene.components
        if "水泵" in item.name and "驱动" not in item.name
    )
    power = next(item.id for item in scene.components if item.category == "POWER")
    mqtt = next(item.id for item in scene.components if item.category == "SERVICE")
    controller = next(
        item.id for item in scene.components if item.role == "controller"
    )
    assert (driver, pump, "POWER_LOAD") in topology
    assert (power, driver, "POWER") in topology
    assert (controller, mqtt, "MQTT") in topology
    assert scene.testCases
    assert any(
        channel_id.startswith("project.") and channel_id.endswith(".input")
        for test_case in scene.testCases
        for channel_id in test_case.inputChannelIds
    )
    assert all(
        "temperature" not in test_case.inputChannelIds
        for test_case in scene.testCases
    )
    assert scene.binding is not None
    assert scene.binding.solutionRevisionId == workspace.current_solution.id
    assert scene.binding.componentPackVersion == "wokwi-elements@1.9.2+zhangwen-v1"


def test_code_preparation_generates_independent_usb_and_espclaw_variants(
    tmp_path,
) -> None:
    creator = CreatorRepository(tmp_path)
    workspace = creator.create_work(
        name="双通道自动浇花",
        initial_idea="用 K10 制作自动浇花装置",
        idempotency_key="creator-dual-code-create",
        selected_hardware_ids=["hw_seed_unihiker_k10"],
    )
    workspace = creator.execute(
        workspace.work_id,
        CreatorCommand.CONFIRM_GOAL,
        _request(
            workspace.project_version,
            "creator-dual-code-goal",
            _goal_payload(),
        ),
    ).workspace
    workspace = creator.execute(
        workspace.work_id,
        CreatorCommand.CONFIRM_SOLUTION,
        _request(
            workspace.project_version,
            "creator-dual-code-solution",
            _solution_payload(),
        ),
    ).workspace
    provider = StructuredFakeProvider()
    runner = CreatorJobRunner(
        ProjectRepository(tmp_path).db_path,
        tmp_path,
        code_generation_factory=lambda: (
            provider,
            LLMConfig(),
            "fake-test-key",
            LLMModelId.DEEPSEEK_V4_PRO,
        ),
    )

    async def consume() -> None:
        await runner.start()
        runner.submit()
        await runner.wait_until_idle(timeout=10)
        await runner.stop()

    asyncio.run(consume())
    projected = creator.workspace(workspace.work_id)
    code_job = next(
        item for item in projected.jobs if item.kind == "CODE_PREPARATION"
    )
    assert code_job.status == "SUCCEEDED"
    assert {item.deployment_channel for item in projected.code_variants} == {
        "USB_SERIAL",
        "ESP_CLAW",
    }
    assert {item.runtime for item in projected.code_variants} == {
        "MICROPYTHON",
        "ESP_CLAW_LUA",
    }
    assert all(
        item.validation_status == "READY_FOR_REVIEW"
        and item.code_run_id is not None
        for item in projected.code_variants
    )
