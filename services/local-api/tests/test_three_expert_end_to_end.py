from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from zhangwen.config import settings
from zhangwen.experts.runtime import ExpertRuntime, ExpertRuntimeRequest
from zhangwen.experts.entry_router import EntryRouter
from zhangwen.llm.contracts import LLMConfig, LLMModelId, StreamChunk, StreamChunkType
from zhangwen.main import app
from zhangwen.projects import router as projects_router
from zhangwen.projects.migrations import CURRENT_SCHEMA_VERSION
from zhangwen.projects.models import ExpertType, ProjectExpertStatus, SharedFactStatus
from zhangwen.projects.repository import ProjectRepository
from zhangwen.proposals.repository import ProposalRepository
from zhangwen.skills.models import SkillRunStatus
from zhangwen.skills.runtime import SkillRuntime, ToolRunner
from zhangwen.solutions.models import SolutionSection
from zhangwen.solutions.repository import SolutionRepository
from tests.fakes import FakeCredentialStore, fake_proposal_sections


class RetryThenStructuredProvider:
    def __init__(self, project_id: str) -> None:
        self.calls = 0
        self.messages: list[list[str]] = []
        self.project_id = project_id

    async def stream_chat(self, request, config, api_key, cancel_token, request_id, message_id):
        self.calls += 1
        self.messages.append([message.content for message in request.messages])
        if self.calls == 1:
            content = "not valid json"
        else:
            content = json.dumps(
                {
                    "content": (
                        "已先评估本地 ACTIVE 硬件库中的 USB 5V 2A 供电模块、"
                        "ESP32-S3 DevKitC 和行空板 K10，"
                        "并形成电气检查候选项；执行前需要你的确认。"
                    ),
                    "proposedFacts": [
                        {
                            "field": "supply_voltage",
                            "key": "supply_voltage",
                            "value": "5V",
                            "reason": "来自当前技术讨论",
                        }
                    ],
                    "skillRequests": [
                        {
                            "skillId": "electrical-check",
                            "input": {"projectId": self.project_id},
                        }
                    ],
                },
                ensure_ascii=False,
            )
        yield StreamChunk(
            requestId=request_id,
            messageId=message_id,
            type=StreamChunkType.COMPLETED,
            accumulatedContent=content,
            model=LLMModelId.DEEPSEEK_V4_FLASH,
        )


class StructuredRouterProvider:
    async def stream_chat(self, request, config, api_key, cancel_token, request_id, message_id):
        content = json.dumps(
            {
                "intent": "technical_implementation",
                "projectName": "ESP32 MQTT 温湿度站",
                "initialExpert": "smart_engineer",
                "recommendedExperts": ["smart_engineer"],
                "confidence": 0.96,
                "reason": "任务包含明确硬件、固件和 MQTT 目标。",
                "requiresClarification": False,
            },
            ensure_ascii=False,
        )
        yield StreamChunk(
            requestId=request_id,
            messageId=message_id,
            type=StreamChunkType.COMPLETED,
            accumulatedContent=content,
            model=LLMModelId.DEEPSEEK_V4_FLASH,
        )


class ExpertHistoryProvider:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.requests: list[object] = []

    async def stream_chat(self, request, config, api_key, cancel_token, request_id, message_id):
        self.requests.append(request)
        content = json.dumps({"content": self.reply}, ensure_ascii=False)
        yield StreamChunk(
            requestId=request_id,
            messageId=message_id,
            type=StreamChunkType.COMPLETED,
            accumulatedContent=content,
            model=LLMModelId.DEEPSEEK_V4_FLASH,
        )


class CodeDraftProvider:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def stream_chat(self, request, config, api_key, cancel_token, request_id, message_id):
        self.messages = [message.content for message in request.messages]
        content = json.dumps(
            {
                "content": (
                    "已根据确认立项书和本地 ACTIVE 0.96 OLED 显示屏 Hardware Skill "
                    "生成首版实现。"
                ),
                "codeDraft": {
                    "files": [
                        {
                            "path": "src/main.py",
                            "language": "python",
                            "content": "print('proposal implementation')\n",
                        }
                    ],
                    "summary": "基于确认立项书和 0.96 OLED 显示屏 Hardware Skill 的首版实现",
                },
            },
            ensure_ascii=False,
        )
        yield StreamChunk(
            requestId=request_id,
            messageId=message_id,
            type=StreamChunkType.COMPLETED,
            accumulatedContent=content,
            model=LLMModelId.DEEPSEEK_V4_FLASH,
        )


@pytest.mark.asyncio
async def test_entry_router_uses_provider_when_explicitly_enabled() -> None:
    result = await EntryRouter().route_with_provider(
        text="ESP32 读取 DHT22 并上传 MQTT",
        provider=StructuredRouterProvider(),
        config=LLMConfig(),
        api_key="fake-test-key",
        model=LLMModelId.DEEPSEEK_V4_FLASH,
    )
    assert result.initialExpert == ExpertType.SMART_ENGINEER
    assert result.projectName == "ESP32 MQTT 温湿度站"
    assert result.requiresClarification is False


def test_project_suggest_http_uses_fake_provider_when_enabled(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(projects_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(projects_router, "provider_factory", StructuredRouterProvider)

    response = TestClient(app).post(
        "/api/projects/suggest",
        json={
            "text": "ESP32 读取 DHT22 并上传 MQTT",
            "useModelRouting": True,
        },
    )

    assert response.status_code == 200
    suggestion = response.json()["suggestion"]
    assert suggestion["name"] == "ESP32 MQTT 温湿度站"
    assert suggestion["initialExpert"] == ExpertType.SMART_ENGINEER.value
    assert suggestion["requiresClarification"] is False

    with sqlite3.connect(ProjectRepository(tmp_path).db_path) as conn:
        audit = conn.execute(
            "SELECT agent_id, task_kind, model FROM model_route_audit"
        ).fetchone()
    assert audit == ("entry_router", "project_routing", LLMModelId.DEEPSEEK_V4_FLASH.value)


@pytest.mark.asyncio
async def test_expert_runtime_uses_minimal_context_and_triggers_coordinator(tmp_path) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="ESP32 传感器项目",
        project_name="传感器项目",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
    )
    active = workspace.experts[0]
    repository.save_draft(workspace.project.id, "PRIVATE-DRAFT-MUST-NOT-LEAK", active.id)
    provider = RetryThenStructuredProvider(workspace.project.id)
    _, user_message, assistant_message = repository.append_user_and_assistant(
        workspace.project.id,
        "检查 5V 供电是否安全",
        LLMModelId.DEEPSEEK_V4_FLASH,
        project_expert_id=active.id,
    )

    result = await ExpertRuntime(repository.db_path).run(
        request=ExpertRuntimeRequest(
            projectId=workspace.project.id,
            projectExpertId=active.id,
            conversationId=active.conversationId,
            expertType=ExpertType.SMART_ENGINEER,
            userMessage="检查 5V 供电是否安全",
            requestMessageId=user_message.id,
            responseMessageId=assistant_message.id,
            model=LLMModelId.DEEPSEEK_V4_FLASH,
        ),
        provider=provider,
        config=LLMConfig(),
        api_key="fake-test-key",
    )

    assert result.retryCount == 1
    assert provider.calls == 2
    assert "智能工程师" in provider.messages[-1][0]
    assert "PRIVATE-DRAFT-MUST-NOT-LEAK" not in "\n".join(provider.messages[-1])

    refreshed = repository.get_workspace(workspace.project.id)
    assert refreshed.experts[0].status == ProjectExpertStatus.WAITING_USER
    assert refreshed.coordinator is not None
    assert refreshed.coordinator.currentPendingItem is not None
    assert sum(item.isHighlighted for item in refreshed.coordinator.pendingItems) == 1
    approval = next(
        item
        for item in refreshed.coordinator.pendingItems
        if item.title == "确认本地执行"
    )
    assert approval.description == "该操作可能产生本地或外部影响，确认后才能执行。"
    assert approval.reason == "本地执行需要用户明确授权。"
    assert approval.kind == "local_execution_authorization"
    assert approval.actionType == "resume_skill_run"
    assert approval.authorizationId == approval.id
    assert "electrical-check" not in json.dumps(
        approval.model_dump(mode="json"), ensure_ascii=False
    )

    with sqlite3.connect(repository.db_path) as conn:
        conn.row_factory = sqlite3.Row
        fact = conn.execute(
            "SELECT status FROM project_shared_facts WHERE project_id = ? AND key = 'supply_voltage'",
            (workspace.project.id,),
        ).fetchone()
        expert_run = conn.execute(
            "SELECT status, retry_count FROM expert_runs WHERE project_id = ?",
            (workspace.project.id,),
        ).fetchone()
        skill_run = conn.execute(
            "SELECT status, confirmation_required FROM skill_runs WHERE project_id = ?",
            (workspace.project.id,),
        ).fetchone()
        authorization_count = conn.execute(
            "SELECT COUNT(*) FROM skill_run_authorizations WHERE project_id = ?",
            (workspace.project.id,),
        ).fetchone()[0]
    assert fact["status"] == SharedFactStatus.PROPOSED.value
    assert expert_run["status"] == "completed"
    assert expert_run["retry_count"] == 1
    assert skill_run["status"] == SkillRunStatus.AWAITING_CONFIRMATION.value
    assert skill_run["confirmation_required"] == 1
    assert authorization_count == 1


@pytest.mark.asyncio
async def test_smart_engineer_executes_approved_proposal_without_spec(tmp_path) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="实现一个简单状态提示器",
        project_name="状态提示器",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
    )
    expert = workspace.experts[0]
    solution_repository = SolutionRepository(repository.db_path)
    solution = solution_repository.create_solution(
        workspace.project.id,
        [SolutionSection(id="goal", title="项目目标", content="显示当前状态")],
    )
    solution = solution_repository.confirm_solution(workspace.project.id, solution.id)
    proposal_repository = ProposalRepository(repository.db_path)
    proposal = proposal_repository.create_from_solution(
        workspace.project.id,
        solution,
        fake_proposal_sections("直接进入实现"),
    )
    proposal_repository.confirm_proposal(workspace.project.id, proposal.id)
    _, user_message, assistant_message = repository.append_user_and_assistant(
        workspace.project.id,
        "立项书已确认，请直接开始实现。",
        LLMModelId.DEEPSEEK_V4_FLASH,
        project_expert_id=expert.id,
    )
    provider = CodeDraftProvider()

    result = await ExpertRuntime(repository.db_path).run(
        request=ExpertRuntimeRequest(
            projectId=workspace.project.id,
            projectExpertId=expert.id,
            conversationId=expert.conversationId,
            expertType=ExpertType.SMART_ENGINEER,
            userMessage="立项书已确认，请直接开始实现。",
            requestMessageId=user_message.id,
            responseMessageId=assistant_message.id,
            model=LLMModelId.DEEPSEEK_V4_FLASH,
        ),
        provider=provider,
        config=LLMConfig(),
        api_key="fake-test-key",
    )

    assert result.codeRun is not None
    assert result.codeRun.specRunId is None
    prompt = "\n".join(provider.messages)
    assert "正式工程代码门禁" not in prompt
    assert "codeDraftAllowed" not in prompt
    assert "当前 Spec 未确认时不得生成" not in prompt


@pytest.mark.asyncio
async def test_expert_runtime_redacts_local_device_details_from_provider_context(
    tmp_path,
) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="行空板 K10 MicroPython 项目",
        project_name="设备上下文脱敏测试",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
    )
    expert = workspace.experts[0]
    now = "2026-07-12T08:00:00+00:00"
    session_id = "device-session-private-sentinel"
    port_details = (
        r"COM97|PORT-NAME-SENTINEL|SERIAL-NUMBER-SENTINEL|"
        r"VID-10C4|PID-EA60|C:\Users\private\main.py"
    )
    operation_id = "device-operation-private-sentinel"
    backup_path = r"C:\Users\private\device-backups\main.py"
    session_log = "RAW-SESSION-LOG-SENTINEL"
    operation_log = "RAW-OPERATION-LOG-SENTINEL"
    with sqlite3.connect(repository.db_path) as conn:
        conn.execute(
            """
            INSERT INTO device_sessions (
              id, project_id, port_id, board, status, logs_json,
              connected_at, last_seen_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                workspace.project.id,
                port_details,
                "UNIHIKER K10",
                "READY",
                json.dumps(
                    [
                        {
                            "id": "private-log-id",
                            "level": "INFO",
                            "message": f"{session_log}: {backup_path}",
                            "createdAt": now,
                        }
                    ],
                    ensure_ascii=False,
                ),
                now,
                now,
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO device_operations (
              id, project_id, session_id, kind, status, dry_run,
              command_label, log, artifact_id, artifact_version_id,
              created_at, completed_at
            ) VALUES (?, ?, ?, 'UPLOAD_CODE', 'COMPLETED', 0,
                      'mpremote', ?, NULL, NULL, ?, ?)
            """,
            (
                operation_id,
                workspace.project.id,
                session_id,
                f"{operation_log}: backup={backup_path}",
                now,
                now,
            ),
        )

    provider = ExpertHistoryProvider("设备上下文已检查。")
    await ExpertRuntime(repository.db_path).run(
        request=ExpertRuntimeRequest(
            projectId=workspace.project.id,
            projectExpertId=expert.id,
            conversationId=expert.conversationId,
            expertType=ExpertType.SMART_ENGINEER,
            userMessage="检查设备是否已准备好继续本地验证。",
            model=LLMModelId.DEEPSEEK_V4_FLASH,
        ),
        provider=provider,
        config=LLMConfig(),
        api_key="fake-test-key",
    )

    provider_payload = "\n".join(
        message.content for message in provider.requests[0].messages
    )
    assert '"board": "UNIHIKER K10"' in provider_payload
    assert '"status": "ready"' in provider_payload
    assert '"ready": true' in provider_payload
    for private_value in (
        session_id,
        port_details,
        "COM97",
        "PORT-NAME-SENTINEL",
        "SERIAL-NUMBER-SENTINEL",
        "VID-10C4",
        "PID-EA60",
        operation_id,
        backup_path,
        "device-backups",
        session_log,
        operation_log,
    ):
        assert private_value not in provider_payload
    for private_key in (
        "sessionId",
        "portId",
        "portName",
        "serialNumber",
        "vid",
        "pid",
        "operationId",
        "backupPath",
        "logs",
    ):
        assert f'"{private_key}"' not in provider_payload

    with sqlite3.connect(repository.db_path) as conn:
        stored_session = conn.execute(
            "SELECT port_id, logs_json FROM device_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        stored_operation = conn.execute(
            "SELECT log FROM device_operations WHERE id = ?",
            (operation_id,),
        ).fetchone()
    assert stored_session == (
        port_details,
        json.dumps(
            [
                {
                    "id": "private-log-id",
                    "level": "INFO",
                    "message": f"{session_log}: {backup_path}",
                    "createdAt": now,
                }
            ],
            ensure_ascii=False,
        ),
    )
    assert stored_operation == (f"{operation_log}: backup={backup_path}",)


@pytest.mark.asyncio
async def test_provider_history_is_independent_for_each_expert_conversation(tmp_path) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="ESP32 传感器和外壳",
        project_name="独立云端对话测试",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[
            ExpertType.SMART_ENGINEER,
            ExpertType.STRUCTURE_ENGINEER,
        ],
    )
    experts = {expert.expertType: expert for expert in workspace.experts}
    smart = experts[ExpertType.SMART_ENGINEER]
    structure = experts[ExpertType.STRUCTURE_ENGINEER]
    repository.append_user_and_assistant(
        workspace.project.id,
        "SMART-HISTORY-ONLY",
        LLMModelId.DEEPSEEK_V4_FLASH,
        project_expert_id=smart.id,
    )
    repository.append_user_and_assistant(
        workspace.project.id,
        "STRUCTURE-HISTORY-ONLY",
        LLMModelId.DEEPSEEK_V4_FLASH,
        project_expert_id=structure.id,
    )

    smart_provider = ExpertHistoryProvider("智能工程师回复")
    await ExpertRuntime(repository.db_path).run(
        request=ExpertRuntimeRequest(
            projectId=workspace.project.id,
            projectExpertId=smart.id,
            conversationId=smart.conversationId,
            expertType=smart.expertType,
            userMessage="继续技术讨论",
            workspaceContext={
                "workspaceKind": "engineering",
                "workspaceView": "code",
                "projectVersion": 2,
            },
            model=LLMModelId.DEEPSEEK_V4_FLASH,
        ),
        provider=smart_provider,
        config=LLMConfig(),
        api_key="fake-test-key",
    )
    structure_provider = ExpertHistoryProvider("结构工程师回复")
    await ExpertRuntime(repository.db_path).run(
        request=ExpertRuntimeRequest(
            projectId=workspace.project.id,
            projectExpertId=structure.id,
            conversationId=structure.conversationId,
            expertType=structure.expertType,
            userMessage="继续结构讨论",
            model=LLMModelId.DEEPSEEK_V4_FLASH,
        ),
        provider=structure_provider,
        config=LLMConfig(),
        api_key="fake-test-key",
    )

    smart_payload = "\n".join(
        message.content for message in smart_provider.requests[0].messages
    )
    structure_payload = "\n".join(
        message.content for message in structure_provider.requests[0].messages
    )
    assert "SMART-HISTORY-ONLY" in smart_payload
    assert "STRUCTURE-HISTORY-ONLY" not in smart_payload
    assert "当前 V2 页面上下文：工程实现 / 代码工程，项目版本 V2" in smart_payload
    assert "页面上下文只是导航提示" in smart_payload
    assert "STRUCTURE-HISTORY-ONLY" in structure_payload
    assert "SMART-HISTORY-ONLY" not in structure_payload
    assert "当前 V2 页面上下文" not in structure_payload


def test_persisted_messages_keep_expert_and_conversation_metadata(tmp_path) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="ESP32 传感器和外壳",
        project_name="消息归属测试",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[
            ExpertType.SMART_ENGINEER,
            ExpertType.STRUCTURE_ENGINEER,
        ],
    )
    structure = next(
        expert
        for expert in workspace.experts
        if expert.expertType == ExpertType.STRUCTURE_ENGINEER
    )
    _workspace, user_message, assistant_message = repository.append_user_and_assistant(
        workspace.project.id,
        "请调整外壳安装孔",
        LLMModelId.DEEPSEEK_V4_FLASH,
        project_expert_id=structure.id,
    )

    expected = {
        "projectExpertId": structure.id,
        "expertType": ExpertType.STRUCTURE_ENGINEER.value,
        "conversationId": structure.conversationId,
    }
    assert {key: user_message.metadata[key] for key in expected} == expected
    assert {key: assistant_message.metadata[key] for key in expected} == expected

    reloaded = repository.get_workspace(workspace.project.id)
    persisted = next(
        conversation
        for conversation in reloaded.expertConversations
        if conversation.id == structure.conversationId
    ).messages
    assert all(
        {key: message.metadata[key] for key in expected} == expected
        for message in persisted
    )


@pytest.mark.asyncio
async def test_skill_runtime_retries_registered_mock_tool_and_audits_runs(tmp_path) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="ESP32 Mock 测试",
        project_name="Mock 测试",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
    )
    calls = 0

    async def mock_sandbox(payload: dict[str, object]) -> dict[str, object]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("transient mock failure")
        return {"validated": True, "projectId": payload["projectId"]}

    runner = ToolRunner(repository.db_path, {"sandbox": mock_sandbox})
    result = await SkillRuntime(repository.db_path, runner).run(
        project_id=workspace.project.id,
        skill_id="mock-test",
        payload={"projectId": workspace.project.id},
        confirmed=True,
        requesting_expert=ExpertType.SMART_ENGINEER,
    )

    assert result.status == SkillRunStatus.COMPLETED
    assert result.retryCount == 1
    assert calls == 2
    with sqlite3.connect(repository.db_path) as conn:
        statuses = [
            row[0]
            for row in conn.execute(
                "SELECT status FROM tool_runs WHERE skill_run_id = ? ORDER BY created_at",
                (result.id,),
            ).fetchall()
        ]
    assert statuses == ["failed", "completed"]


def test_current_migration_creates_backup_and_audit_record(tmp_path) -> None:
    repository = ProjectRepository(tmp_path)
    with sqlite3.connect(repository.db_path) as conn:
        conn.execute("DROP TABLE expert_runs")
        conn.execute("DROP TABLE skill_runs")
        conn.execute("DROP TABLE tool_runs")
        conn.execute("DROP TABLE schema_migration_audit")
        conn.execute("PRAGMA user_version=20")

    migrated = ProjectRepository(tmp_path)
    backups = list(
        (tmp_path / "projects" / "backups").glob(
            f"pre-migration-v20-to-v{CURRENT_SCHEMA_VERSION}-*.sqlite3"
        )
    )
    assert len(backups) == 1
    with sqlite3.connect(migrated.db_path) as conn:
        audit = conn.execute(
            """
            SELECT status, backup_path FROM schema_migration_audit
            WHERE from_version = 20 AND to_version = ? AND backup_path IS NOT NULL
            """,
            (CURRENT_SCHEMA_VERSION,),
        ).fetchone()
    assert audit[0] == "applied"
    assert audit[1] == str(backups[0])
