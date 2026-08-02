import json
import sqlite3

from fastapi.testclient import TestClient

from zhangwen.chat import router as chat_router
from zhangwen.config import settings
from zhangwen.experts.context_assembler import ContextAssembler, ContextAssemblyInput
from zhangwen.llm.contracts import (
    ChatMessageStatus,
    LLMError,
    LLMErrorCode,
    StreamChunk,
    StreamChunkType,
)
from zhangwen.main import app
from zhangwen.projects.models import ExpertType, ProjectStage
from zhangwen.projects.repository import ProjectRepository
from zhangwen.proposals.repository import ProposalRepository
from zhangwen.solutions.models import SolutionSection
from zhangwen.solutions.repository import SolutionRepository
from tests.fakes import EmptyCredentialStore, FakeCredentialStore, fake_proposal_sections


class FakeClarificationProvider:
    calls: list[str] = []
    request_messages: list[list[str]] = []

    async def stream_chat(
        self,
        request,
        config,
        api_key,
        cancel_token,
        request_id,
        message_id,
    ):
        latest_user = request.messages[-1].content
        FakeClarificationProvider.calls.append(latest_user)
        FakeClarificationProvider.request_messages.append(
            [message.content for message in request.messages]
        )
        system_prompt = request.messages[0].content if request.messages else ""
        if "方案修订助手" in system_prompt:
            payload = _fake_solution_revision_payload()
        elif "方案生成助手" in system_prompt:
            payload = _fake_solution_payload()
        elif "工程规格内容设计器" in system_prompt:
            payload = _fake_spec_payload()
        else:
            payload = _fake_clarification_payload(latest_user)
        content = json.dumps(payload, ensure_ascii=False)
        yield StreamChunk(
            requestId=request_id,
            messageId=message_id,
            type=StreamChunkType.START,
            model=request.model or config.defaultModel,
        )
        yield StreamChunk(
            requestId=request_id,
            messageId=message_id,
            type=StreamChunkType.CONTENT_DELTA,
            delta=content,
            accumulatedContent=content,
            model=request.model or config.defaultModel,
        )
        yield StreamChunk(
            requestId=request_id,
            messageId=message_id,
            type=StreamChunkType.COMPLETED,
            accumulatedContent=content,
            model=request.model or config.defaultModel,
        )


def _fake_clarification_payload(latest_user: str) -> dict:
    if "修改方案" in latest_user:
        return {
            "questions": [
                {
                    "id": "solution_revision_scope",
                    "type": "MULTI_SELECT",
                    "question": "你想优先修改方案的哪些部分？",
                    "options": [
                        {"id": "hardware", "label": "硬件组成"},
                        {"id": "logic", "label": "工作逻辑"},
                        {"id": "cost", "label": "成本与工期"},
                        {"id": "custom", "label": "其他，我来补充"},
                    ],
                }
            ],
            "completeness": 65,
            "message": "我会先确认你想改动的范围，再基于当前方案修订。",
        }
    if "用户正在回答当前澄清问题" in latest_user:
        return {
            "questions": [],
            "completeness": 85,
            "message": "收到，已有信息可以进入方案生成。",
        }
    if "入门提醒器" in latest_user:
        return {
            "questions": [
                {
                    "id": "target_context",
                    "type": "SINGLE_SELECT",
                    "question": "你希望这个入门提醒器主要提醒什么？",
                    "options": [
                        {"id": "study", "label": "学习或任务提醒"},
                        {"id": "daily", "label": "日常习惯提醒"},
                        {"id": "recommended", "label": "由掌问推荐", "recommended": True},
                        {"id": "custom", "label": "其他，我来补充"},
                    ],
                },
                {
                    "id": "product_form",
                    "type": "SINGLE_SELECT",
                    "question": "你希望它采用哪种形态？",
                    "options": [
                        {"id": "desktop_device", "label": "桌面实体设备"},
                        {"id": "portable_device", "label": "随身提醒设备"},
                        {"id": "recommended", "label": "由掌问推荐", "recommended": True},
                        {"id": "custom", "label": "其他，我来补充"},
                    ],
                },
                {
                    "id": "reminder_method",
                    "type": "SINGLE_SELECT",
                    "question": "提醒方式希望以哪一种为主？",
                    "options": [
                        {"id": "light", "label": "灯光提醒"},
                        {"id": "sound", "label": "声音提醒"},
                        {"id": "recommended", "label": "由掌问推荐", "recommended": True},
                        {"id": "custom", "label": "其他，我来补充"},
                    ],
                },
            ],
            "completeness": 35,
            "message": "我先理解为一个面向新手使用的入门提醒器。为了确定更适合的实现方式，我一次确认几个关键需求。",
        }
    return {
        "questions": [
            {
                "id": "product_form",
                "type": "SINGLE_SELECT",
                "question": "你希望它采用哪种形态？",
                "options": [
                    {"id": "desktop_device", "label": "桌面实体设备"},
                    {"id": "portable_device", "label": "随身提醒设备"},
                    {"id": "recommended", "label": "由掌问推荐", "recommended": True},
                    {"id": "custom", "label": "其他，我来补充"},
                ],
            },
            {
                "id": "reminder_method",
                "type": "SINGLE_SELECT",
                "question": "提醒方式希望以哪一种为主？",
                "options": [
                    {"id": "light", "label": "灯光提醒"},
                    {"id": "sound", "label": "声音提醒"},
                    {"id": "recommended", "label": "由掌问推荐", "recommended": True},
                    {"id": "custom", "label": "其他，我来补充"},
                ],
            },
            {
                "id": "data_tracking",
                "type": "MULTI_SELECT",
                "question": "需要记录哪些数据或状态？",
                "options": [
                    {"id": "event_log", "label": "触发次数"},
                    {"id": "status", "label": "当前状态"},
                    {"id": "recommended", "label": "由掌问推荐", "recommended": True},
                    {"id": "custom", "label": "其他，我来补充"},
                ],
            },
        ],
        "completeness": 35,
        "message": "我先理解为你想做一个提醒类项目。为了确定更适合的实现方式，我一次确认几个关键需求。",
    }


def _fake_solution_payload() -> dict:
    return {
        "sections": [
            {"id": "sec_goal", "title": "项目目标", "content": "制作一个自动浇水系统，预算约300元，支持 Wi-Fi 查看状态。"},
            {"id": "sec_logic", "title": "工作逻辑", "content": "土壤湿度低于阈值时启动水泵，达到目标湿度后停止，并记录浇水事件。"},
            {"id": "sec_hardware", "title": "硬件组成", "content": "ESP32 x1、土壤湿度传感器 x1、继电器或 MOS 管驱动 x1、微型水泵 x1、水管与电源模块。"},
            {"id": "sec_software", "title": "软件模块", "content": "MicroPython 负责传感器采集、阈值判断、水泵控制、Wi-Fi 状态上报和本地安全保护。"},
            {"id": "sec_structure", "title": "结构实现", "content": "传感器插入花盆土壤，水泵与水箱固定在侧边，ESP32 与驱动板放入防水小盒。"},
            {"id": "sec_steps", "title": "实施步骤", "content": "先验证湿度读取，再测试水泵驱动，随后接入 Wi-Fi 状态页并完成整机固定。"},
            {"id": "sec_cost", "title": "成本与工期", "content": "预计成本 120-180 元，低于 300 元预算，制作时间约 1-2 天。"},
            {"id": "sec_risk", "title": "风险与限制", "content": "重点风险是水泵干烧、供电不足、传感器腐蚀和水电隔离，需要加入最大运行时长保护。"},
        ]
    }


def _fake_solution_revision_payload() -> dict:
    return {
        "revisedSolution": {
            "sections": [
                {"id": "goal", "title": "项目目标", "content": "制作一个自动浇水系统，预算约300元，支持 Wi-Fi 查看状态。"},
                {"id": "functional_logic", "title": "工作逻辑", "content": "土壤湿度低于阈值时启动蠕动泵，达到目标湿度或超过安全时长后停止，并记录浇水事件。"},
                {"id": "hardware", "title": "硬件组成", "content": "ESP32 x1、土壤湿度传感器 x1、蠕动泵 x1、MOS 管驱动 x1、水管与电源模块。"},
                {"id": "software", "title": "软件模块", "content": "MicroPython 负责传感器采集、阈值判断、蠕动泵控制、Wi-Fi 状态上报和本地安全保护。"},
                {"id": "structure", "title": "结构实现", "content": "传感器插入花盆土壤，蠕动泵与水箱固定在侧边，ESP32 与驱动板放入防水小盒。"},
                {"id": "implementation_steps", "title": "实施步骤", "content": "先验证湿度读取，再测试蠕动泵驱动，随后接入 Wi-Fi 状态页并完成整机固定。"},
                {"id": "cost_difficulty_time", "title": "成本与工期", "content": "预计成本 150-220 元，仍低于 300 元预算，制作时间约 1-2 天。"},
                {"id": "risks", "title": "风险与限制", "content": "重点风险是蠕动泵流量校准、供电不足、传感器腐蚀和水电隔离，需要最大运行时长保护。"},
            ]
        },
        "changedSections": [
            {
                "sectionId": "hardware",
                "sectionTitle": "硬件组成",
                "changeType": "updated",
                "before": "微型水泵",
                "after": "蠕动泵",
                "reason": "用户要求将水泵改为蠕动泵。",
            }
        ],
        "preservedSections": ["项目目标", "结构实现"],
        "impactSummary": ["执行器：微型水泵 → 蠕动泵", "成本略升但仍低于 300 元预算"],
        "requiresProposalUpdate": True,
    }


def _fake_spec_payload() -> dict:
    return {
        "projectName": "自动浇花装置",
        "goal": "根据土壤湿度安全控制水泵并反馈状态。",
        "modules": [
            {
                "id": "sense",
                "name": "湿度采集",
                "responsibility": "读取土壤湿度传感器。",
            },
            {
                "id": "control",
                "name": "水泵控制",
                "responsibility": "按阈值控制水泵驱动。",
            },
        ],
        "acceptance": [
            "湿度低于阈值时启动水泵。",
            "设备操作前保留人工确认。",
        ],
        "risks": ["必须复核供电、电流和防水。"],
        "componentIds": [
            "hw_seed_unihiker_k10",
            "hw_seed_dht22",
            "hw_seed_mosfet_driver",
            "hw_seed_oled_096",
            "hw_seed_usb_5v_power",
            "hw_seed_breadboard",
        ],
        "ioSuggestions": [
            {
                "signal": "sensor_data",
                "pin": "GPIO4",
                "protocol": "GPIO",
                "componentId": "hw_seed_dht22",
            },
            {
                "signal": "actuator_pwm",
                "pin": "GPIO5",
                "protocol": "PWM",
                "componentId": "hw_seed_mosfet_driver",
            },
            {
                "signal": "status_i2c",
                "pin": "GPIO8/GPIO9",
                "protocol": "I2C",
                "componentId": "hw_seed_oled_096",
            },
        ],
    }


def test_project_chat_stream_persists_structured_idea_response(tmp_path, monkeypatch) -> None:
    settings.data_dir = tmp_path
    FakeClarificationProvider.calls = []
    FakeClarificationProvider.request_messages = []
    monkeypatch.setattr(chat_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(chat_router, "provider_factory", FakeClarificationProvider)
    client = TestClient(app)
    project = client.post(
        "/api/projects",
        json={"name": "项目", "initialIdea": "项目初始创意"},
    ).json()["workspace"]["project"]

    response = client.post(
        f"/api/projects/{project['id']}/chat/stream",
        json={"content": "我想做一个入门提醒器", "model": "deepseek-v4-flash"},
    )

    assert response.status_code == 200
    chunks = _chunks(response.text)
    assert chunks[0]["type"] == "START"
    assert chunks[0]["projectId"] == project["id"]
    assert chunks[-1]["type"] == "COMPLETED"
    assert chunks[-1]["structuredPayload"]["type"] == "clarification"

    workspace = ProjectRepository(tmp_path).get_workspace(project["id"])
    assert [message.role for message in workspace.conversation.messages[-2:]] == ["user", "assistant"]
    assert workspace.conversation.messages[0].content == "项目初始创意"
    assert workspace.conversation.messages[-2].content == "我想做一个入门提醒器"
    assistant = workspace.conversation.messages[-1]
    assert assistant.status == "COMPLETED"
    assert assistant.structuredPayload is not None
    assert assistant.structuredPayload["type"] == "clarification"
    assert assistant.structuredPayload["question"]["id"] == "target_context"
    assert assistant.structuredPayload["question"]["text"] == "你希望这个入门提醒器主要提醒什么？"
    assert [question["id"] for question in assistant.structuredPayload["questions"]] == [
        "target_context",
    ]
    assert "入门提醒器" in assistant.content
    assert "喝水" not in assistant.content
    assert "饮水" not in assistant.content
    assert FakeClarificationProvider.calls == ["我想做一个入门提醒器"]
    assert "由掌问推荐" in [
        option["label"] for option in assistant.structuredPayload["question"]["options"]
    ]
    assert "```" not in assistant.content
    assert "HTML" not in assistant.content.upper()


def test_project_chat_receives_validated_v2_workspace_context(tmp_path, monkeypatch) -> None:
    settings.data_dir = tmp_path
    FakeClarificationProvider.calls = []
    FakeClarificationProvider.request_messages = []
    monkeypatch.setattr(chat_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(chat_router, "provider_factory", FakeClarificationProvider)
    client = TestClient(app)
    workspace = client.post(
        "/api/projects",
        json={"name": "项目", "initialIdea": "项目初始创意"},
    ).json()["workspace"]
    project = workspace["project"]
    expert_conversation = workspace["expertConversations"][0]

    response = client.post(
        f"/api/projects/{project['id']}/chat/stream",
        json={
            "content": "检查当前代码还缺什么",
            "model": "deepseek-v4-flash",
            "projectExpertId": expert_conversation["projectExpertId"],
            "threadId": expert_conversation["id"],
            "expertType": expert_conversation["expertType"],
            "turnContext": {
                "projectId": project["id"],
                "conversationId": expert_conversation["id"],
                "threadId": expert_conversation["id"],
                "expertType": expert_conversation["expertType"],
                "turnId": "turn_v2_context",
                "currentStage": project["stage"],
                "currentIntent": "DESCRIBE_IDEA",
                "workspaceKind": "engineering",
                "workspaceView": "code",
                "projectVersion": 3,
            },
        },
    )

    assert response.status_code == 200
    provider_context = "\n".join(FakeClarificationProvider.request_messages[-1])
    assert "当前 V2 页面上下文：工程实现 / 代码工程，项目版本 V3" in provider_context
    assert "页面上下文只是导航提示" in provider_context


def test_project_chat_without_key_persists_failed_assistant(tmp_path, monkeypatch) -> None:
    settings.data_dir = tmp_path
    monkeypatch.setattr(chat_router, "credential_store_factory", EmptyCredentialStore)
    client = TestClient(app)
    project = client.post(
        "/api/projects",
        json={"name": "项目", "initialIdea": "项目初始创意"},
    ).json()["workspace"]["project"]

    response = client.post(
        f"/api/projects/{project['id']}/chat/stream",
        json={"content": "你好"},
    )

    assert response.status_code == 200
    chunks = _chunks(response.text)
    assert chunks[0]["type"] == "ERROR"
    assert chunks[0]["error"]["code"] == "CONFIG_MISSING"

    workspace = ProjectRepository(tmp_path).get_workspace(project["id"])
    assert workspace.conversation.messages[-1].status == "FAILED"
    assert workspace.conversation.messages[-1].error is not None


def test_project_chat_generates_solution_card_then_incremental_revision(tmp_path, monkeypatch) -> None:
    settings.data_dir = tmp_path
    FakeClarificationProvider.calls = []
    FakeClarificationProvider.request_messages = []
    monkeypatch.setattr(chat_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(chat_router, "provider_factory", FakeClarificationProvider)
    client = TestClient(app)
    project = client.post(
        "/api/projects",
        json={"name": "自动浇水系统", "initialIdea": "自动浇水系统，预算300元，需要 Wi-Fi 和土壤湿度传感器"},
    ).json()["workspace"]["project"]

    generate_response = client.post(
        f"/api/projects/{project['id']}/chat/stream",
        json={
            "content": "生成推荐实现方案",
            "model": "deepseek-v4-flash",
            "conversationAction": "generate_solution",
        },
    )
    assert generate_response.status_code == 200
    generate_chunks = _chunks(generate_response.text)
    assert generate_chunks[0]["type"] == "START"
    assert generate_chunks[-1]["type"] == "COMPLETED"
    generate_progress = [
        (chunk["progress"]["action"], chunk["progress"]["status"])
        for chunk in generate_chunks
        if chunk["type"] == "PROGRESS"
    ]
    assert ("CONTEXT_READ", "RUNNING") in generate_progress
    assert ("CONTEXT_READ", "COMPLETED") in generate_progress
    assert ("CLOUD_LLM_REQUEST", "RUNNING") in generate_progress
    assert ("OUTPUT_VALIDATE", "COMPLETED") in generate_progress
    assert ("PROJECT_UPDATE", "RUNNING") in generate_progress
    assert ("PROJECT_UPDATE", "COMPLETED") in generate_progress
    solution_payload = generate_chunks[-1]["structuredPayload"]
    assert solution_payload["type"] == "solution_card"
    assert solution_payload["artifactId"].startswith("artifact_solution_")
    assert solution_payload["version"] == 1
    assert "土壤湿度传感器" in solution_payload["summary"]
    assert "喝水" not in json.dumps(solution_payload, ensure_ascii=False)
    assert any(
        "预算300元" in "\n".join(messages)
        for messages in FakeClarificationProvider.request_messages
    )

    modify_response = client.post(
        f"/api/projects/{project['id']}/chat/stream",
        json={
            "content": "修改方案",
            "model": "deepseek-v4-flash",
            "conversationAction": "modify_solution",
        },
    )
    assert modify_response.status_code == 200
    modify_chunks = _chunks(modify_response.text)
    modify_payload = modify_chunks[-1]["structuredPayload"]
    assert modify_payload["type"] == "clarification"
    assert modify_payload["question"]["id"] == "solution_revision_scope"

    revise_response = client.post(
        f"/api/projects/{project['id']}/chat/stream",
        json={
            "content": "把水泵改成蠕动泵",
            "model": "deepseek-v4-flash",
        },
    )
    assert revise_response.status_code == 200
    revise_chunks = _chunks(revise_response.text)
    revision_payload = revise_chunks[-1]["structuredPayload"]
    assert revision_payload["type"] == "solution_card"
    assert revision_payload["version"] == 2
    assert revision_payload["basedOnVersion"] == 1
    assert revision_payload["revision"]["changedSections"]
    assert any("蠕动泵" in item for item in revision_payload["changeSummary"])
    assert "立项书已经生成" not in revise_chunks[-1]["accumulatedContent"]
    assert any("把水泵改成蠕动泵" in call for call in FakeClarificationProvider.calls)


def test_confirmed_proposal_skips_spec_and_hands_off_to_existing_smart_engineer(
    tmp_path,
    monkeypatch,
) -> None:
    settings.data_dir = tmp_path
    monkeypatch.setattr(chat_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(chat_router, "provider_factory", FakeClarificationProvider)
    client = TestClient(app)
    workspace = client.post(
        "/api/projects",
        json={
            "name": "自动浇水系统",
            "initialIdea": "使用 K10 做自动浇水系统",
            "selectedExpertTypes": ["problem_guide", "smart_engineer"],
            "initialExpert": "problem_guide",
        },
    ).json()["workspace"]
    project_id = workspace["project"]["id"]
    repository = ProjectRepository(tmp_path)
    solution_repository = SolutionRepository(repository.db_path)
    solution = solution_repository.create_solution(
        project_id,
        [
            SolutionSection(id="goal", title="项目目标", content="保持土壤湿度"),
            SolutionSection(id="hardware", title="硬件方案", content="K10 与土壤传感器"),
        ],
    )
    solution = solution_repository.confirm_solution(project_id, solution.id)
    proposal = ProposalRepository(repository.db_path).create_from_solution(
        project_id,
        solution,
        fake_proposal_sections("智能工程师必须直接读取这份基线"),
    )
    guide = next(
        expert for expert in workspace["experts"] if expert["expertType"] == "problem_guide"
    )

    response = client.post(
        f"/api/projects/{project_id}/chat/stream",
        json={
            "content": "确认立项书",
            "model": "deepseek-v4-flash",
            "projectExpertId": guide["id"],
            "threadId": guide["conversationId"],
            "expertType": "problem_guide",
            "conversationAction": "confirm_project_proposal",
        },
    )

    assert response.status_code == 200
    payload = _chunks(response.text)[-1]["structuredPayload"]
    assert payload["type"] == "proposal_action"
    assert payload["proposalId"] == proposal.id
    assert payload["handoff"] == {
        "automatic": True,
        "targetExpert": "smart_engineer",
        "label": "已交接给智能工程师",
        "prompt": "立项书已确认，请基于当前已确认立项书直接开始项目实现。",
    }
    assert "智能工程师" in payload["message"]
    assert "Spec" not in payload["message"]

    with sqlite3.connect(repository.db_path) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM spec_runs WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0] == 0

    context = ContextAssembler(repository.db_path).assemble(
        ContextAssemblyInput(
            projectId=project_id,
            expert=ExpertType.SMART_ENGINEER,
            userMessage="请基于已确认立项书直接开始项目实现。",
        )
    )
    assert context.activeProposal is not None
    assert context.activeProposal["id"] == proposal.id
    assert context.activeProposal["status"] == "APPROVED"
    assert "智能工程师必须直接读取这份基线" in json.dumps(
        context.activeProposal,
        ensure_ascii=False,
    )
    client.close()


def test_confirmed_proposal_without_smart_engineer_stays_confirmed_without_handoff(
    tmp_path,
    monkeypatch,
) -> None:
    settings.data_dir = tmp_path
    monkeypatch.setattr(chat_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(chat_router, "provider_factory", FakeClarificationProvider)
    client = TestClient(app)
    workspace = client.post(
        "/api/projects",
        json={
            "name": "创意说明项目",
            "initialIdea": "整理一个无需工程实现的创意说明",
            "selectedExpertTypes": ["problem_guide"],
            "initialExpert": "problem_guide",
        },
    ).json()["workspace"]
    project_id = workspace["project"]["id"]
    repository = ProjectRepository(tmp_path)
    solution_repository = SolutionRepository(repository.db_path)
    solution = solution_repository.create_solution(
        project_id,
        [SolutionSection(id="goal", title="项目目标", content="整理创意说明")],
    )
    solution = solution_repository.confirm_solution(project_id, solution.id)
    proposal = ProposalRepository(repository.db_path).create_from_solution(
        project_id,
        solution,
        fake_proposal_sections("只确认实施基线"),
    )
    guide = workspace["experts"][0]

    response = client.post(
        f"/api/projects/{project_id}/chat/stream",
        json={
            "content": "确认立项书",
            "model": "deepseek-v4-flash",
            "projectExpertId": guide["id"],
            "threadId": guide["conversationId"],
            "expertType": "problem_guide",
            "conversationAction": "confirm_project_proposal",
        },
    )

    assert response.status_code == 200
    payload = _chunks(response.text)[-1]["structuredPayload"]
    assert payload["proposalId"] == proposal.id
    assert "handoff" not in payload
    assert "没有智能工程师" in payload["message"]
    assert repository.get_workspace(project_id).project.stage == ProjectStage.PROPOSAL_CONFIRMED
    client.close()


def test_project_chat_recovery_turn_preserves_source_metadata(tmp_path, monkeypatch) -> None:
    settings.data_dir = tmp_path
    FakeClarificationProvider.calls = []
    FakeClarificationProvider.request_messages = []
    monkeypatch.setattr(chat_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(chat_router, "provider_factory", FakeClarificationProvider)
    client = TestClient(app)
    project = client.post(
        "/api/projects",
        json={"name": "恢复项目", "initialIdea": "制作一个提醒器"},
    ).json()["workspace"]["project"]

    response = client.post(
        f"/api/projects/{project['id']}/chat/stream",
        json={
            "content": "按原需求重新生成",
            "model": "deepseek-v4-flash",
            "clientTurnId": "client_recovery",
            "recoveryOfMessageId": "assistant_failed_1",
            "recoveryLabel": "已按原需求重新生成",
        },
    )

    assert response.status_code == 200
    assert _chunks(response.text)[-1]["type"] == "COMPLETED"
    workspace = ProjectRepository(tmp_path).get_workspace(project["id"])
    recovery_user = next(
        message
        for message in workspace.conversation.messages
        if message.metadata and message.metadata.get("clientTurnId") == "client_recovery"
    )
    assert recovery_user.metadata["recoveryOfMessageId"] == "assistant_failed_1"
    assert recovery_user.metadata["recoveryLabel"] == "已按原需求重新生成"
    client.close()


def test_project_chat_structured_answer_binds_question_and_is_idempotent(
    tmp_path,
    monkeypatch,
) -> None:
    settings.data_dir = tmp_path
    FakeClarificationProvider.calls = []
    FakeClarificationProvider.request_messages = []
    monkeypatch.setattr(chat_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(chat_router, "provider_factory", FakeClarificationProvider)
    client = TestClient(app)
    project = client.post(
        "/api/projects",
        json={"name": "project", "initialIdea": "project seed"},
    ).json()["workspace"]["project"]

    idea_response = client.post(
        f"/api/projects/{project['id']}/chat/stream",
        json={
            "content": "water reminder",
            "model": "deepseek-v4-flash",
            "clientTurnId": "client_idea",
            "turnContext": {
                "projectId": project["id"],
                "conversationId": project["conversationId"],
                "turnId": "client_idea",
                "currentStage": "IDEA",
                "currentIntent": "describe_idea",
            },
        },
    )
    assert idea_response.status_code == 200
    first_chunks = _chunks(idea_response.text)
    question = first_chunks[-1]["structuredPayload"]["question"]
    source_message_id = first_chunks[-1]["messageId"]

    answer_body = {
        "content": "Desktop device",
        "model": "deepseek-v4-flash",
        "clientTurnId": "client_answer",
        "sourceMessageId": source_message_id,
        "questionId": question["id"],
        "selectedOptionIds": ["desktop_device"],
        "textInput": "Desktop device",
        "turnContext": {
            "projectId": project["id"],
            "conversationId": project["conversationId"],
            "turnId": "client_answer",
            "replyToMessageId": source_message_id,
            "replyToQuestionId": question["id"],
            "currentStage": "CLARIFYING",
            "currentIntent": "answer_question",
            "activeQuestionId": question["id"],
        },
        "structuredAnswer": {
            "type": "single_choice_answer",
            "projectId": project["id"],
            "conversationId": project["conversationId"],
            "questionId": question["id"],
            "optionId": "desktop_device",
            "optionValue": "desktop_device",
            "optionLabel": "Desktop device",
            "clientTurnId": "client_answer",
        },
    }
    answer_response = client.post(
        f"/api/projects/{project['id']}/chat/stream",
        json=answer_body,
    )
    assert answer_response.status_code == 200
    answer_chunks = _chunks(answer_response.text)
    assert answer_chunks[-1]["type"] == "COMPLETED"
    assert answer_chunks[-1]["requestTurnId"] == "client_answer"
    assert answer_chunks[-1]["structuredPayload"]["type"] == "next_action"
    assert any("用户正在回答当前澄清问题" in call for call in FakeClarificationProvider.calls)

    workspace = ProjectRepository(tmp_path).get_workspace(project["id"])
    assert len(workspace.conversation.messages) == 6
    messages_by_id = {message.id: message for message in workspace.conversation.messages}
    assert messages_by_id[source_message_id].structuredPayload["question"]["answered"] is True
    assert messages_by_id[source_message_id].structuredPayload["questions"][0]["answered"] is True
    answer_user = next(
        message
        for message in workspace.conversation.messages
        if message.metadata and message.metadata.get("clientTurnId") == "client_answer"
    )
    assert answer_user.metadata["replyToQuestionId"] == "product_form"
    assert answer_user.metadata["answerOptionIds"] == ["desktop_device"]

    with sqlite3.connect(ProjectRepository(tmp_path).db_path) as conn:
        conn.row_factory = sqlite3.Row
        answer = conn.execute(
            "SELECT * FROM clarification_answers WHERE client_turn_id = ?",
            ("client_answer",),
        ).fetchone()
    assert answer["question_id"] == "product_form"
    assert answer["answer_type"] == "single"

    duplicate_response = client.post(
        f"/api/projects/{project['id']}/chat/stream",
        json=answer_body,
    )
    assert duplicate_response.status_code == 200
    duplicate_chunks = _chunks(duplicate_response.text)
    assert duplicate_chunks[-1]["type"] == "COMPLETED"
    assert duplicate_chunks[-1]["messageId"] == answer_chunks[-1]["messageId"]
    assert len(ProjectRepository(tmp_path).get_workspace(project["id"]).conversation.messages) == 6


def test_project_chat_batch_answer_requires_all_questions_and_calls_provider_once(
    tmp_path,
    monkeypatch,
) -> None:
    settings.data_dir = tmp_path
    FakeClarificationProvider.calls = []
    FakeClarificationProvider.request_messages = []
    monkeypatch.setattr(chat_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(chat_router, "provider_factory", FakeClarificationProvider)
    client = TestClient(app)
    project = client.post(
        "/api/projects",
        json={"name": "project", "initialIdea": "project seed"},
    ).json()["workspace"]["project"]

    idea_response = client.post(
        f"/api/projects/{project['id']}/chat/stream",
        json={
            "content": "water reminder",
            "model": "deepseek-v4-flash",
            "clientTurnId": "client_batch_idea",
        },
    )
    first_chunks = _chunks(idea_response.text)
    source_message_id = first_chunks[-1]["messageId"]
    assert len(first_chunks[-1]["structuredPayload"]["questions"]) == 1

    # Simulate a clarification message created before M7. New responses expose only
    # one blocker, while historical multi-question payloads must remain answerable.
    legacy_payload = first_chunks[-1]["structuredPayload"]
    legacy_payload["questions"] = [
        legacy_payload["questions"][0],
        {
            "id": "reminder_method",
            "text": "提醒方式希望以哪一种为主？",
            "mode": "single",
            "options": [
                {"id": "light", "label": "灯光提醒", "value": "light"},
                {"id": "sound", "label": "声音提醒", "value": "sound"},
            ],
            "required": True,
            "answered": False,
        },
        {
            "id": "data_tracking",
            "text": "需要记录哪些数据或状态？",
            "mode": "multiple",
            "options": [
                {"id": "event_log", "label": "触发次数", "value": "event_log"},
                {"id": "status", "label": "当前状态", "value": "status"},
            ],
            "required": True,
            "answered": False,
        },
    ]
    legacy_payload["question"] = legacy_payload["questions"][0]
    repository = ProjectRepository(tmp_path)
    with sqlite3.connect(repository.db_path) as conn:
        conn.execute(
            "UPDATE messages SET structured_payload_json = ? WHERE id = ?",
            (json.dumps(legacy_payload, ensure_ascii=False), source_message_id),
        )
    repository.register_clarification_question(
        project_id=project["id"],
        conversation_id=project["conversationId"],
        source_message_id=source_message_id,
        stage="CLARIFYING",
        payload=legacy_payload,
    )

    incomplete_response = client.post(
        f"/api/projects/{project['id']}/chat/stream",
        json={
            "content": "形态：桌面实体设备",
            "model": "deepseek-v4-flash",
            "clientTurnId": "client_batch_incomplete",
            "sourceMessageId": source_message_id,
            "structuredAnswer": {
                "type": "clarification_batch_answer",
                "projectId": project["id"],
                "conversationId": project["conversationId"],
                "sourceMessageId": source_message_id,
                "clientTurnId": "client_batch_incomplete",
                "answers": [
                    {
                        "questionId": "product_form",
                        "selectedOptionIds": ["desktop_device"],
                    }
                ],
            },
        },
    )
    incomplete_chunks = _chunks(incomplete_response.text)
    assert incomplete_chunks[0]["type"] == "ERROR"
    assert incomplete_chunks[0]["error"]["code"] == "CLARIFICATION_INCOMPLETE"
    assert len(ProjectRepository(tmp_path).get_workspace(project["id"]).conversation.messages) == 4

    duplicate_question_response = client.post(
        f"/api/projects/{project['id']}/chat/stream",
        json={
            "content": "重复回答",
            "model": "deepseek-v4-flash",
            "clientTurnId": "client_batch_duplicate_question",
            "sourceMessageId": source_message_id,
            "structuredAnswer": {
                "type": "clarification_batch_answer",
                "projectId": project["id"],
                "conversationId": project["conversationId"],
                "sourceMessageId": source_message_id,
                "clientTurnId": "client_batch_duplicate_question",
                "answers": [
                    {
                        "questionId": "product_form",
                        "selectedOptionIds": ["desktop_device"],
                    },
                    {
                        "questionId": "product_form",
                        "selectedOptionIds": ["portable_device"],
                    },
                ],
            },
        },
    )
    duplicate_question_chunks = _chunks(duplicate_question_response.text)
    assert duplicate_question_chunks[0]["type"] == "ERROR"
    assert (
        duplicate_question_chunks[0]["error"]["code"]
        == "DUPLICATE_QUESTION_ANSWER"
    )
    assert len(ProjectRepository(tmp_path).get_workspace(project["id"]).conversation.messages) == 4

    answer_body = {
        "content": "形态：桌面实体设备\n提醒方式：灯光提醒\n记录：触发次数、当前状态",
        "model": "deepseek-v4-flash",
        "clientTurnId": "client_batch_answer",
        "sourceMessageId": source_message_id,
        "turnContext": {
            "projectId": project["id"],
            "conversationId": project["conversationId"],
            "turnId": "client_batch_answer",
            "replyToMessageId": source_message_id,
            "currentStage": "CLARIFYING",
            "currentIntent": "answer_question",
        },
        "structuredAnswer": {
            "type": "clarification_batch_answer",
            "projectId": project["id"],
            "conversationId": project["conversationId"],
            "sourceMessageId": source_message_id,
            "clientTurnId": "client_batch_answer",
            "answers": [
                {
                    "questionId": "product_form",
                    "selectedOptionIds": ["desktop_device"],
                },
                {
                    "questionId": "reminder_method",
                    "selectedOptionIds": ["light"],
                },
                {
                    "questionId": "data_tracking",
                    "selectedOptionIds": ["event_log", "status"],
                },
            ],
        },
    }
    provider_calls_before = len(FakeClarificationProvider.calls)
    answer_response = client.post(
        f"/api/projects/{project['id']}/chat/stream",
        json=answer_body,
    )
    answer_chunks = _chunks(answer_response.text)
    assert answer_chunks[-1]["type"] == "COMPLETED"
    assert len(FakeClarificationProvider.calls) == provider_calls_before + 1
    assert "用户已完成本轮全部澄清问题" in FakeClarificationProvider.calls[-1]
    assert "product_form" in FakeClarificationProvider.calls[-1]
    assert "data_tracking" in FakeClarificationProvider.calls[-1]

    workspace = ProjectRepository(tmp_path).get_workspace(project["id"])
    source_message = next(
        message for message in workspace.conversation.messages if message.id == source_message_id
    )
    assert all(question["answered"] for question in source_message.structuredPayload["questions"])
    answer_user = next(
        message
        for message in workspace.conversation.messages
        if message.metadata and message.metadata.get("clientTurnId") == "client_batch_answer"
    )
    assert answer_user.metadata["replyToQuestionIds"] == [
        "product_form",
        "reminder_method",
        "data_tracking",
    ]
    with sqlite3.connect(ProjectRepository(tmp_path).db_path) as conn:
        conn.row_factory = sqlite3.Row
        answers = conn.execute(
            "SELECT * FROM clarification_answers WHERE client_turn_id = ? ORDER BY question_id",
            ("client_batch_answer",),
        ).fetchall()
        confirmed_answer_facts = conn.execute(
            """
            SELECT key, status FROM project_shared_facts
            WHERE project_id = ? AND field = 'clarification_answer'
            """,
            (project["id"],),
        ).fetchall()
    assert [answer["question_id"] for answer in answers] == [
        "data_tracking",
        "product_form",
        "reminder_method",
    ]
    assert {fact["key"] for fact in confirmed_answer_facts} == {
        "product_form",
        "reminder_method",
        "data_tracking",
    }
    assert {fact["status"] for fact in confirmed_answer_facts} == {"confirmed"}

    duplicate_response = client.post(
        f"/api/projects/{project['id']}/chat/stream",
        json=answer_body,
    )
    duplicate_chunks = _chunks(duplicate_response.text)
    assert duplicate_chunks[-1]["messageId"] == answer_chunks[-1]["messageId"]
    assert len(FakeClarificationProvider.calls) == provider_calls_before + 1


def test_project_chat_rejects_invalid_structured_answer_without_new_messages(
    tmp_path,
    monkeypatch,
) -> None:
    settings.data_dir = tmp_path
    monkeypatch.setattr(chat_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(chat_router, "provider_factory", FakeClarificationProvider)
    client = TestClient(app)
    project = client.post(
        "/api/projects",
        json={"name": "project", "initialIdea": "project seed"},
    ).json()["workspace"]["project"]
    idea_response = client.post(
        f"/api/projects/{project['id']}/chat/stream",
        json={"content": "water reminder", "model": "deepseek-v4-flash"},
    )
    source_message_id = _chunks(idea_response.text)[-1]["messageId"]

    invalid_response = client.post(
        f"/api/projects/{project['id']}/chat/stream",
        json={
            "content": "not allowed",
            "model": "deepseek-v4-flash",
            "clientTurnId": "client_invalid",
            "sourceMessageId": source_message_id,
            "questionId": "product_form",
            "selectedOptionIds": ["not_allowed"],
            "textInput": "not allowed",
            "turnContext": {
                "projectId": project["id"],
                "conversationId": project["conversationId"],
                "turnId": "client_invalid",
                "currentStage": "CLARIFYING",
                "currentIntent": "answer_question",
            },
            "structuredAnswer": {
                "type": "single_choice_answer",
                "projectId": project["id"],
                "conversationId": project["conversationId"],
                "questionId": "product_form",
                "optionId": "not_allowed",
                "optionValue": "not_allowed",
                "optionLabel": "not allowed",
                "clientTurnId": "client_invalid",
            },
        },
    )

    assert invalid_response.status_code == 200
    chunks = _chunks(invalid_response.text)
    assert chunks[0]["type"] == "ERROR"
    assert chunks[0]["projectId"] == project["id"]
    assert chunks[0]["conversationId"] == project["conversationId"]
    assert chunks[0]["error"]["code"] == "OPTION_NOT_ALLOWED"
    assert len(ProjectRepository(tmp_path).get_workspace(project["id"]).conversation.messages) == 4


def test_project_chat_rejects_context_mismatch_without_new_messages(
    tmp_path,
    monkeypatch,
) -> None:
    settings.data_dir = tmp_path
    monkeypatch.setattr(chat_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(chat_router, "provider_factory", FakeClarificationProvider)
    client = TestClient(app)
    project = client.post(
        "/api/projects",
        json={"name": "project", "initialIdea": "project seed"},
    ).json()["workspace"]["project"]

    response = client.post(
        f"/api/projects/{project['id']}/chat/stream",
        json={
            "content": "Desktop device",
            "model": "deepseek-v4-flash",
            "clientTurnId": "client_mismatch",
            "turnContext": {
                "projectId": "other_project",
                "conversationId": project["conversationId"],
                "turnId": "client_mismatch",
                "currentStage": "CLARIFYING",
                "currentIntent": "answer_question",
            },
        },
    )

    assert response.status_code == 200
    chunks = _chunks(response.text)
    assert chunks[0]["type"] == "ERROR"
    assert chunks[0]["error"]["code"] == "PROJECT_CONTEXT_MISMATCH"
    workspace = ProjectRepository(tmp_path).get_workspace(project["id"])
    assert len(workspace.conversation.messages) == 2
    assert workspace.conversation.messages[0].content == "project seed"
    assert workspace.conversation.messages[1].metadata["source"] == "project_creation_runtime"


def test_project_kickoff_reuses_creation_messages_and_replays_completion(
    tmp_path,
    monkeypatch,
) -> None:
    settings.data_dir = tmp_path
    FakeClarificationProvider.calls = []
    FakeClarificationProvider.request_messages = []
    monkeypatch.setattr(chat_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(chat_router, "provider_factory", FakeClarificationProvider)
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project("入门提醒器", "我想做一个入门提醒器")
    request = _kickoff_request(workspace)
    client = TestClient(app)

    response = client.post(
        f"/api/projects/{workspace.project.id}/chat/stream",
        json=request,
    )

    assert response.status_code == 200
    chunks = _chunks(response.text)
    assert chunks[0]["type"] == "START"
    assert chunks[-1]["type"] == "COMPLETED"
    assert any(chunk["type"] == "PROGRESS" for chunk in chunks)
    assert len(FakeClarificationProvider.calls) == 1
    reloaded = repository.get_workspace(workspace.project.id)
    assert reloaded.kickoff is not None
    assert reloaded.kickoff.status == "COMPLETED"
    assert len(reloaded.conversation.messages) == 2
    assert [message.role.value for message in reloaded.conversation.messages].count("user") == 1
    assert reloaded.conversation.messages[0].content == "我想做一个入门提醒器"
    assert reloaded.conversation.messages[1].status == ChatMessageStatus.COMPLETED

    duplicate = client.post(
        f"/api/projects/{workspace.project.id}/chat/stream",
        json=request,
    )

    assert [chunk["type"] for chunk in _chunks(duplicate.text)] == [
        "START",
        "COMPLETED",
    ]
    assert len(FakeClarificationProvider.calls) == 1
    assert len(repository.get_workspace(workspace.project.id).conversation.messages) == 2


def test_project_kickoff_running_request_is_deduplicated_without_false_completion(
    tmp_path,
    monkeypatch,
) -> None:
    settings.data_dir = tmp_path
    FakeClarificationProvider.calls = []
    monkeypatch.setattr(chat_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(chat_router, "provider_factory", FakeClarificationProvider)
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project("入门提醒器", "我想做一个入门提醒器")
    kickoff = workspace.kickoff
    assert kickoff is not None
    state, _, _ = repository.claim_kickoff_turn(
        project_id=workspace.project.id,
        turn_id=kickoff.turnId,
        content=kickoff.content,
        conversation_id=kickoff.conversationId,
        project_expert_id=kickoff.projectExpertId,
        client_turn_id=kickoff.clientTurnId,
        retry=False,
    )
    assert state == "CLAIMED"

    response = TestClient(app).post(
        f"/api/projects/{workspace.project.id}/chat/stream",
        json=_kickoff_request(workspace),
    )

    assert [chunk["type"] for chunk in _chunks(response.text)] == ["START"]
    assert FakeClarificationProvider.calls == []
    reloaded = repository.get_workspace(workspace.project.id)
    assert reloaded.kickoff is not None
    assert reloaded.kickoff.status == "PENDING"
    assert len(reloaded.conversation.messages) == 2


def test_project_kickoff_failure_requires_explicit_retry_and_reuses_same_turn(
    tmp_path,
    monkeypatch,
) -> None:
    settings.data_dir = tmp_path
    FakeClarificationProvider.calls = []
    monkeypatch.setattr(chat_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(chat_router, "provider_factory", FakeClarificationProvider)
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project("入门提醒器", "我想做一个入门提醒器")
    kickoff = workspace.kickoff
    assert kickoff is not None
    repository.claim_kickoff_turn(
        project_id=workspace.project.id,
        turn_id=kickoff.turnId,
        content=kickoff.content,
        conversation_id=kickoff.conversationId,
        project_expert_id=kickoff.projectExpertId,
        client_turn_id=kickoff.clientTurnId,
        retry=False,
    )
    repository.update_message(
        workspace.project.id,
        kickoff.assistantMessageId,
        status=ChatMessageStatus.FAILED,
        error=LLMError(
            code=LLMErrorCode.NETWORK_UNAVAILABLE,
            message="network unavailable",
            retryable=True,
            userActions=[{"id": "retry", "label": "重试"}],
        ),
    )
    repository.update_turn_status(kickoff.turnId, "FAILED")
    client = TestClient(app)

    replay = client.post(
        f"/api/projects/{workspace.project.id}/chat/stream",
        json=_kickoff_request(workspace),
    )
    assert [chunk["type"] for chunk in _chunks(replay.text)] == ["START", "ERROR"]
    assert FakeClarificationProvider.calls == []

    retry_request = _kickoff_request(workspace)
    retry_request["retryKickoff"] = True
    retried = client.post(
        f"/api/projects/{workspace.project.id}/chat/stream",
        json=retry_request,
    )

    retry_chunks = _chunks(retried.text)
    assert retry_chunks[0]["type"] == "START"
    assert retry_chunks[-1]["type"] == "COMPLETED"
    assert any(chunk["type"] == "PROGRESS" for chunk in retry_chunks)
    assert len(FakeClarificationProvider.calls) == 1
    reloaded = repository.get_workspace(workspace.project.id)
    assert reloaded.kickoff is not None
    assert reloaded.kickoff.status == "COMPLETED"
    assert reloaded.kickoff.turnId == kickoff.turnId
    assert len(reloaded.conversation.messages) == 2


def _chunks(text: str) -> list[dict]:
    chunks = []
    for event in text.strip().split("\n\n"):
        for line in event.splitlines():
            if line.startswith("data:"):
                chunks.append(json.loads(line[5:].strip()))
    return chunks


def _kickoff_request(workspace) -> dict:
    kickoff = workspace.kickoff
    assert kickoff is not None
    return {
        "content": kickoff.content,
        "model": workspace.project.selectedModel.value,
        "projectExpertId": kickoff.projectExpertId,
        "threadId": kickoff.conversationId,
        "expertType": kickoff.expertType.value,
        "clientTurnId": kickoff.clientTurnId,
        "kickoffTurnId": kickoff.turnId,
        "turnContext": {
            "projectId": workspace.project.id,
            "conversationId": kickoff.conversationId,
            "turnId": kickoff.turnId,
            "currentStage": workspace.project.stage.value,
            "currentIntent": "describe_idea",
        },
    }
