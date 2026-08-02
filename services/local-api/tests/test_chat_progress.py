from __future__ import annotations

import asyncio
import json
import sqlite3
import threading

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.requests import Request

from tests.fakes import FakeCredentialStore
from zhangwen.chat import router as chat_router
from zhangwen.config import settings
from zhangwen.coordinator import ProjectCoordinatorService
from zhangwen.experts.context_assembler import ContextAssembler
from zhangwen.experts.runtime import ExpertRuntime, ExpertRuntimeRequest
from zhangwen.llm.contracts import (
    ChatProgress,
    ChatProgressAction,
    ChatProgressEmitter,
    ChatProgressStatus,
    LLMConfig,
    LLMErrorCode,
    LLMModelId,
    StreamChunk,
    StreamChunkType,
)
from zhangwen.main import app
from zhangwen.llm.errors import make_llm_error
from zhangwen.projects.models import (
    ExpertType,
    PendingItemPriority,
    PersistedChatRequest,
    ProjectWorkspace,
)
from zhangwen.projects.repository import ProjectRepository
from zhangwen.skills.models import SkillRunStatus
from zhangwen.skills.runtime import (
    LOCAL_EXECUTION_PENDING_DESCRIPTION,
    LOCAL_EXECUTION_PENDING_REASON,
    LOCAL_EXECUTION_PENDING_TITLE,
    SkillAuthorizationError,
    SkillRuntime,
    ToolRunner,
)


class _ExpertReplyProvider:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    async def stream_chat(
        self,
        request,
        config,
        api_key,
        cancel_token,
        request_id,
        message_id,
    ):
        content = json.dumps(self._payload, ensure_ascii=False)
        yield StreamChunk(
            requestId=request_id,
            messageId=message_id,
            type=StreamChunkType.COMPLETED,
            accumulatedContent=content,
            model=LLMModelId.DEEPSEEK_V4_FLASH,
        )


class _ForgedProgressProvider:
    async def stream_chat(
        self,
        request,
        config,
        api_key,
        cancel_token,
        request_id,
        message_id,
    ):
        yield StreamChunk(
            requestId=request_id,
            messageId=message_id,
            type=StreamChunkType.PROGRESS,
            progress=ChatProgress.create(
                progress_id="tool.execute.1",
                action=ChatProgressAction.LOCAL_TOOL_EXECUTION,
                status=ChatProgressStatus.COMPLETED,
                sequence=1,
            ),
        )


class _CanceledExpertProvider:
    async def stream_chat(
        self,
        request,
        config,
        api_key,
        cancel_token,
        request_id,
        message_id,
    ):
        yield StreamChunk(
            requestId=request_id,
            messageId=message_id,
            type=StreamChunkType.CANCELED,
            error=make_llm_error(LLMErrorCode.CANCELED),
        )


class _BlockingExpertProvider:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def stream_chat(
        self,
        request,
        config,
        api_key,
        cancel_token,
        request_id,
        message_id,
    ):
        self.started.set()
        await self.release.wait()
        yield StreamChunk(
            requestId=request_id,
            messageId=message_id,
            type=StreamChunkType.COMPLETED,
            accumulatedContent=json.dumps({"content": "不应到达"}),
        )


class _BlockingProjectConversationProvider:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def stream_chat(
        self,
        request,
        config,
        api_key,
        cancel_token,
        request_id,
        message_id,
    ):
        self.started.set()
        await self.release.wait()
        yield StreamChunk(
            requestId=request_id,
            messageId=message_id,
            type=StreamChunkType.COMPLETED,
            accumulatedContent=json.dumps(self._payload, ensure_ascii=False),
            model=LLMModelId.DEEPSEEK_V4_FLASH,
        )


def test_chat_progress_labels_are_server_owned_and_status_specific() -> None:
    running = ChatProgress.create(
        progress_id="context.read",
        action=ChatProgressAction.CONTEXT_READ,
        status=ChatProgressStatus.RUNNING,
        sequence=1,
    )
    completed = ChatProgress.create(
        progress_id="context.read",
        action=ChatProgressAction.CONTEXT_READ,
        status=ChatProgressStatus.COMPLETED,
        sequence=1,
    )

    assert running.label == "正在读取项目上下文"
    assert completed.label == "已读取项目上下文"
    assert running.id == completed.id
    assert running.sequence == completed.sequence

    with pytest.raises(ValidationError, match="server-owned"):
        ChatProgress(
            id="context.read",
            action=ChatProgressAction.CONTEXT_READ,
            label=r"正在读取 C:\\private\\project.json",
            status=ChatProgressStatus.RUNNING,
            sequence=1,
        )
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ChatProgress.model_validate(
            {
                **running.model_dump(mode="json"),
                "toolId": "private-tool-id",
            }
        )


def test_stream_chunk_requires_progress_only_for_progress_type() -> None:
    progress = ChatProgress.create(
        progress_id="context.read",
        action=ChatProgressAction.CONTEXT_READ,
        status=ChatProgressStatus.RUNNING,
        sequence=1,
    )
    valid = StreamChunk(
        requestId="request",
        messageId="message",
        type=StreamChunkType.PROGRESS,
        progress=progress,
    )
    assert valid.progress == progress

    with pytest.raises(ValidationError, match="requires progress"):
        StreamChunk(
            requestId="request",
            messageId="message",
            type=StreamChunkType.PROGRESS,
        )
    with pytest.raises(ValidationError, match="only allowed"):
        StreamChunk(
            requestId="request",
            messageId="message",
            type=StreamChunkType.COMPLETED,
            progress=progress,
        )


def test_cloud_provider_cannot_forge_progress_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(chat_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(chat_router, "provider_factory", _ForgedProgressProvider)

    response = TestClient(app).post(
        "/api/chat/stream",
        json={
            "messages": [
                {
                    "id": "user-message",
                    "role": "user",
                    "content": "检查工具状态",
                    "status": "READY",
                    "createdAt": "",
                    "updatedAt": "",
                }
            ],
            "model": "deepseek-v4-flash",
        },
    )

    events = _events(response.text)
    assert [event for event, _ in events] == ["chat.error"]
    assert events[0][1]["type"] == "ERROR"
    assert events[0][1]["error"]["code"] == "LLM_OUTPUT_INVALID"
    assert "chat.progress" not in response.text
    assert "已完成本地工具执行" not in response.text


@pytest.mark.asyncio
async def test_expert_runtime_reports_only_real_sanitized_stages(tmp_path) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="ESP32 温度提醒器",
        project_name="温度提醒器",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
    )
    expert = workspace.experts[0]
    progress: list[ChatProgress] = []

    await ExpertRuntime(repository.db_path).run(
        request=ExpertRuntimeRequest(
            projectId=workspace.project.id,
            projectExpertId=expert.id,
            conversationId=expert.conversationId,
            expertType=ExpertType.SMART_ENGINEER,
            userMessage="检查当前方案",
            model=LLMModelId.DEEPSEEK_V4_FLASH,
        ),
        provider=_ExpertReplyProvider({"content": "方案检查完成。"}),
        config=LLMConfig(),
        api_key="fake-test-key",
        on_progress=progress.append,
    )

    pairs = [(item.action, item.status) for item in progress]
    assert pairs == [
        (ChatProgressAction.CONTEXT_READ, ChatProgressStatus.RUNNING),
        (ChatProgressAction.CONTEXT_READ, ChatProgressStatus.COMPLETED),
        (ChatProgressAction.CLOUD_LLM_REQUEST, ChatProgressStatus.RUNNING),
        (ChatProgressAction.OUTPUT_VALIDATE, ChatProgressStatus.RUNNING),
        (ChatProgressAction.OUTPUT_VALIDATE, ChatProgressStatus.COMPLETED),
        (ChatProgressAction.CLOUD_LLM_REQUEST, ChatProgressStatus.COMPLETED),
        (ChatProgressAction.PROJECT_UPDATE, ChatProgressStatus.RUNNING),
        (ChatProgressAction.PROJECT_UPDATE, ChatProgressStatus.COMPLETED),
    ]
    by_id: dict[str, list[ChatProgress]] = {}
    for item in progress:
        by_id.setdefault(item.id, []).append(item)
    assert all(
        len({item.sequence for item in items}) == 1
        for items in by_id.values()
    )
    assert [items[0].sequence for items in by_id.values()] == [1, 2, 3, 4]
    serialized = json.dumps(
        [item.model_dump(mode="json") for item in progress], ensure_ascii=False
    )
    assert "fake-test-key" not in serialized
    assert "skill" not in serialized.lower()
    assert "tool_id" not in serialized.lower()


@pytest.mark.asyncio
async def test_context_read_runs_off_event_loop(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="ESP32 上下文调度",
        project_name="上下文调度",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
    )
    expert = workspace.experts[0]
    loop = asyncio.get_running_loop()
    event_loop_thread_id = threading.get_ident()
    worker_thread_id: int | None = None
    context_started = asyncio.Event()
    release_context = threading.Event()
    original_assemble = ContextAssembler.assemble

    def checked_assemble(self, request):
        nonlocal worker_thread_id
        worker_thread_id = threading.get_ident()
        loop.call_soon_threadsafe(context_started.set)
        release_context.wait(timeout=2)
        return original_assemble(self, request)

    monkeypatch.setattr(ContextAssembler, "assemble", checked_assemble)
    failsafe = threading.Timer(1, release_context.set)
    failsafe.start()
    started_at = loop.time()
    runtime_task = asyncio.create_task(
        ExpertRuntime(repository.db_path).run(
            request=ExpertRuntimeRequest(
                projectId=workspace.project.id,
                projectExpertId=expert.id,
                conversationId=expert.conversationId,
                expertType=ExpertType.SMART_ENGINEER,
                userMessage="检查上下文",
                model=LLMModelId.DEEPSEEK_V4_FLASH,
            ),
            provider=_ExpertReplyProvider({"content": "上下文检查完成。"}),
            config=LLMConfig(),
            api_key="fake-test-key",
        )
    )
    try:
        await asyncio.wait_for(context_started.wait(), timeout=1.5)
        assert loop.time() - started_at < 0.5
        assert worker_thread_id != event_loop_thread_id
        await asyncio.wait_for(asyncio.sleep(0), timeout=0.1)
        assert runtime_task.done() is False
    finally:
        release_context.set()
        failsafe.cancel()
        await runtime_task


@pytest.mark.asyncio
async def test_waiting_authorization_never_reports_or_invokes_tool(tmp_path) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="ESP32 沙箱测试",
        project_name="沙箱测试",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
    )
    calls = 0

    async def handler(payload: dict[str, object]) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"validated": True, "projectId": payload["projectId"]}

    progress: list[ChatProgress] = []
    result = await SkillRuntime(
        repository.db_path,
        ToolRunner(repository.db_path, {"sandbox": handler}),
    ).run(
        project_id=workspace.project.id,
        skill_id="mock-test",
        payload={"projectId": workspace.project.id},
        confirmed=False,
        requesting_expert=ExpertType.SMART_ENGINEER,
        progress_emitter=ChatProgressEmitter(progress.append),
    )

    assert result.status == SkillRunStatus.AWAITING_CONFIRMATION
    assert calls == 0
    assert [(item.action, item.status) for item in progress] == [
        (
            ChatProgressAction.LOCAL_EXECUTION_AUTHORIZATION,
            ChatProgressStatus.WAITING,
        )
    ]
    with sqlite3.connect(repository.db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM tool_runs").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_tool_progress_follows_persisted_attempt_state_and_redacts_errors(
    tmp_path,
) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="ESP32 沙箱重试",
        project_name="沙箱重试",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
    )
    calls = 0
    snapshots: list[tuple[ChatProgress, list[str]]] = []

    async def handler(payload: dict[str, object]) -> dict[str, object]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError(r"SECRET C:\\private\\command.ps1 --token=abc")
        return {"validated": True, "projectId": payload["projectId"]}

    def capture(item: ChatProgress) -> None:
        with sqlite3.connect(repository.db_path) as conn:
            statuses = [
                row[0]
                for row in conn.execute(
                    "SELECT status FROM tool_runs ORDER BY created_at, rowid"
                ).fetchall()
            ]
        snapshots.append((item, statuses))

    result = await SkillRuntime(
        repository.db_path,
        ToolRunner(repository.db_path, {"sandbox": handler}),
    ).run(
        project_id=workspace.project.id,
        skill_id="mock-test",
        payload={"projectId": workspace.project.id},
        confirmed=True,
        requesting_expert=ExpertType.SMART_ENGINEER,
        progress_emitter=ChatProgressEmitter(capture),
    )

    assert result.status == SkillRunStatus.COMPLETED
    tool_snapshots = [
        (item, statuses)
        for item, statuses in snapshots
        if item.action == ChatProgressAction.LOCAL_TOOL_EXECUTION
    ]
    assert [item.status for item, _ in tool_snapshots] == [
        ChatProgressStatus.RUNNING,
        ChatProgressStatus.FAILED,
        ChatProgressStatus.RUNNING,
        ChatProgressStatus.COMPLETED,
    ]
    assert [item.id for item, _ in tool_snapshots] == [
        "tool.execute.1",
        "tool.execute.1",
        "tool.execute.2",
        "tool.execute.2",
    ]
    assert tool_snapshots[0][1] == ["running"]
    assert tool_snapshots[1][1] == ["failed"]
    assert tool_snapshots[2][1] == ["failed", "running"]
    assert tool_snapshots[3][1] == ["failed", "completed"]
    public_progress = json.dumps(
        [item.model_dump(mode="json") for item, _ in tool_snapshots],
        ensure_ascii=False,
    )
    assert "SECRET" not in public_progress
    assert "private" not in public_progress
    assert "sandbox" not in public_progress


@pytest.mark.parametrize(
    "failure",
    [OSError("private os failure"), KeyError("private-key")],
    ids=["os-error", "key-error"],
)
@pytest.mark.asyncio
async def test_unexpected_tool_failure_closes_tool_and_skill_before_final_progress(
    tmp_path,
    failure: Exception,
) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="ESP32 工具异常",
        project_name="工具异常",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
    )
    snapshots: list[tuple[ChatProgress, list[str], list[str]]] = []

    async def handler(payload: dict[str, object]) -> dict[str, object]:
        _ = payload
        raise failure

    def capture(item: ChatProgress) -> None:
        with sqlite3.connect(repository.db_path) as conn:
            tool_statuses = [
                row[0]
                for row in conn.execute(
                    "SELECT status FROM tool_runs ORDER BY created_at, rowid"
                ).fetchall()
            ]
            skill_statuses = [
                row[0]
                for row in conn.execute(
                    "SELECT status FROM skill_runs ORDER BY created_at, rowid"
                ).fetchall()
            ]
        snapshots.append((item, tool_statuses, skill_statuses))

    result = await SkillRuntime(
        repository.db_path,
        ToolRunner(repository.db_path, {"sandbox": handler}),
    ).run(
        project_id=workspace.project.id,
        skill_id="mock-test",
        payload={"projectId": workspace.project.id},
        confirmed=True,
        requesting_expert=ExpertType.SMART_ENGINEER,
        progress_emitter=ChatProgressEmitter(capture),
    )

    assert result.status == SkillRunStatus.FAILED
    tool_events = [
        snapshot
        for snapshot in snapshots
        if snapshot[0].action == ChatProgressAction.LOCAL_TOOL_EXECUTION
    ]
    assert tool_events[-1][0].status == ChatProgressStatus.FAILED
    assert tool_events[-1][1] == ["failed", "failed"]
    assert tool_events[-1][2] == ["failed"]


def test_tool_runner_rejects_synchronous_handlers(tmp_path) -> None:
    def handler(payload: dict[str, object]) -> dict[str, object]:
        return payload

    with pytest.raises(ValueError, match="async"):
        ToolRunner(tmp_path / "sync.sqlite3", {"sandbox": handler})
    runner = ToolRunner(tmp_path / "register.sqlite3")
    with pytest.raises(ValueError, match="async"):
        runner.register("sandbox", handler)


@pytest.mark.asyncio
async def test_cancelled_tool_closes_tool_and_skill_before_failed_progress(
    tmp_path,
) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="ESP32 工具取消",
        project_name="工具取消",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
    )
    started = asyncio.Event()
    release = asyncio.Event()
    progress: list[tuple[ChatProgress, list[str], list[str]]] = []

    async def handler(payload: dict[str, object]) -> dict[str, object]:
        _ = payload
        started.set()
        await release.wait()
        return {"validated": True}

    def capture(item: ChatProgress) -> None:
        with sqlite3.connect(repository.db_path) as conn:
            tool_statuses = [
                row[0] for row in conn.execute("SELECT status FROM tool_runs").fetchall()
            ]
            skill_statuses = [
                row[0] for row in conn.execute("SELECT status FROM skill_runs").fetchall()
            ]
        progress.append((item, tool_statuses, skill_statuses))

    task = asyncio.create_task(
        SkillRuntime(
            repository.db_path,
            ToolRunner(repository.db_path, {"sandbox": handler}),
        ).run(
            project_id=workspace.project.id,
            skill_id="mock-test",
            payload={"projectId": workspace.project.id},
            confirmed=True,
            requesting_expert=ExpertType.SMART_ENGINEER,
            progress_emitter=ChatProgressEmitter(capture),
        )
    )
    await asyncio.wait_for(started.wait(), timeout=2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    tool_events = [
        snapshot
        for snapshot in progress
        if snapshot[0].action == ChatProgressAction.LOCAL_TOOL_EXECUTION
    ]
    assert tool_events[-1][0].status == ChatProgressStatus.FAILED
    assert tool_events[-1][1] == ["failed"]
    assert tool_events[-1][2] == ["failed"]


@pytest.mark.asyncio
async def test_missing_tool_handler_emits_no_tool_execution_progress(tmp_path) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="ESP32 未注册工具",
        project_name="未注册工具",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
    )
    progress: list[ChatProgress] = []

    result = await SkillRuntime(repository.db_path).run(
        project_id=workspace.project.id,
        skill_id="mock-test",
        payload={"projectId": workspace.project.id},
        confirmed=True,
        requesting_expert=ExpertType.SMART_ENGINEER,
        progress_emitter=ChatProgressEmitter(progress.append),
    )

    assert result.status == SkillRunStatus.FAILED
    assert all(
        item.action != ChatProgressAction.LOCAL_TOOL_EXECUTION
        for item in progress
    )


def test_expert_project_stream_starts_before_sanitized_progress(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="ESP32 项目",
        project_name="进度事件测试",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
    )
    expert = workspace.experts[0]
    provider = _ExpertReplyProvider(
        {
            "content": "执行前需要确认。",
            "skillRequests": [
                {
                    "skillId": "mock-test",
                    "input": {"projectId": workspace.project.id},
                }
            ],
        }
    )
    monkeypatch.setattr(chat_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(chat_router, "provider_factory", lambda: provider)

    response = TestClient(app).post(
        f"/api/projects/{workspace.project.id}/chat/stream",
        json={
            "content": "检查方案",
            "model": "deepseek-v4-flash",
            "projectExpertId": expert.id,
            "threadId": expert.conversationId,
            "expertType": "smart_engineer",
        },
    )

    assert response.status_code == 200
    events = _events(response.text)
    assert events[0][0] == "chat.started"
    assert events[0][1]["type"] == "START"
    assert events[-1][0] == "chat.completed"
    assert events[-1][1]["type"] == "COMPLETED"
    progress = [payload["progress"] for event, payload in events if event == "chat.progress"]
    assert progress
    assert all(
        payload["type"] == "PROGRESS"
        for event, payload in events
        if event == "chat.progress"
    )
    assert any(
        item["action"] == "LOCAL_EXECUTION_AUTHORIZATION"
        and item["status"] == "WAITING"
        for item in progress
    )
    assert "mock-test" not in response.text
    assert "skillrun" not in response.text
    assert "toolrun" not in response.text
    with sqlite3.connect(repository.db_path) as conn:
        pending = conn.execute(
            """
            SELECT title, description, reason
            FROM project_pending_items
            WHERE project_id = ? AND priority = 'confirmation'
            """,
            (workspace.project.id,),
        ).fetchone()
    assert pending == (
        "确认本地执行",
        "该操作可能产生本地或外部影响，确认后才能执行。",
        "本地执行需要用户明确授权。",
    )


@pytest.mark.asyncio
async def test_failed_skill_pending_item_is_sanitized(tmp_path) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="ESP32 数据分析",
        project_name="数据分析",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
    )
    expert = workspace.experts[0]
    await ExpertRuntime(repository.db_path).run(
        request=ExpertRuntimeRequest(
            projectId=workspace.project.id,
            projectExpertId=expert.id,
            conversationId=expert.conversationId,
            expertType=ExpertType.SMART_ENGINEER,
            userMessage="分析数据",
            model=LLMModelId.DEEPSEEK_V4_FLASH,
        ),
        provider=_ExpertReplyProvider(
            {
                "content": "本地分析未完成。",
                "skillRequests": [
                    {
                        "skillId": "data-analysis",
                        "input": {"projectId": workspace.project.id},
                    }
                ],
            }
        ),
        config=LLMConfig(),
        api_key="fake-test-key",
    )

    with sqlite3.connect(repository.db_path) as conn:
        pending = conn.execute(
            """
            SELECT title, description, reason
            FROM project_pending_items
            WHERE project_id = ? AND priority = 'blocking'
            """,
            (workspace.project.id,),
        ).fetchone()
    assert pending == (
        "本地执行受阻",
        "本地执行未完成，请检查配置或稍后重试。",
        "本地执行未产生有效结果。",
    )
    assert "data-analysis" not in json.dumps(pending, ensure_ascii=False)
    assert "registered" not in json.dumps(pending, ensure_ascii=False)


@pytest.mark.asyncio
async def test_confirmation_skill_without_persisted_messages_cannot_leave_dead_item(
    tmp_path,
) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="ESP32 无消息关联授权",
        project_name="无消息关联授权",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
    )
    expert = workspace.experts[0]

    await ExpertRuntime(repository.db_path).run(
        request=ExpertRuntimeRequest(
            projectId=workspace.project.id,
            projectExpertId=expert.id,
            conversationId=expert.conversationId,
            expertType=ExpertType.SMART_ENGINEER,
            userMessage="运行沙箱检查",
            model=LLMModelId.DEEPSEEK_V4_FLASH,
        ),
        provider=_ExpertReplyProvider(
            {
                "content": "需要执行本地检查。",
                "skillRequests": [
                    {
                        "skillId": "mock-test",
                        "input": {"projectId": workspace.project.id},
                    }
                ],
            }
        ),
        config=LLMConfig(),
        api_key="fake-test-key",
    )

    with sqlite3.connect(repository.db_path) as conn:
        skill_status = conn.execute(
            "SELECT status FROM skill_runs ORDER BY created_at DESC LIMIT 1"
        ).fetchone()[0]
        confirmation_count = conn.execute(
            """
            SELECT COUNT(*) FROM project_pending_items
            WHERE project_id = ? AND status = 'open' AND priority = 'confirmation'
              AND title = ? AND reason = ?
            """,
            (
                workspace.project.id,
                LOCAL_EXECUTION_PENDING_TITLE,
                LOCAL_EXECUTION_PENDING_REASON,
            ),
        ).fetchone()[0]
        authorization_count = conn.execute(
            "SELECT COUNT(*) FROM skill_run_authorizations WHERE project_id = ?",
            (workspace.project.id,),
        ).fetchone()[0]
        blocker = conn.execute(
            """
            SELECT title, description, reason FROM project_pending_items
            WHERE project_id = ? AND status = 'open' AND priority = 'blocking'
            """,
            (workspace.project.id,),
        ).fetchone()

    assert skill_status == SkillRunStatus.FAILED.value
    assert confirmation_count == 0
    assert authorization_count == 0
    assert blocker == (
        "本地执行受阻",
        "本地执行未完成，请检查配置或稍后重试。",
        "本地执行缺少可恢复的对话关联。",
    )


def test_canceled_expert_stream_has_terminal_event_and_no_running_audit(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="ESP32 取消测试",
        project_name="取消测试",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
    )
    expert = workspace.experts[0]
    monkeypatch.setattr(chat_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(chat_router, "provider_factory", _CanceledExpertProvider)
    client = TestClient(app)

    response = client.post(
        f"/api/projects/{workspace.project.id}/chat/stream",
        json={
            "content": "取消这次生成",
            "model": "deepseek-v4-flash",
            "projectExpertId": expert.id,
            "threadId": expert.conversationId,
            "expertType": "smart_engineer",
        },
    )

    events = _events(response.text)
    assert events[0][0] == "chat.started"
    assert events[-1][0] == "chat.canceled"
    assert events[-1][1]["type"] == "CANCELED"
    request_id = str(events[-1][1]["requestId"])
    assert client.post(f"/api/chat/cancel/{request_id}").json()["canceled"] is False
    with sqlite3.connect(repository.db_path) as conn:
        expert_statuses = [
            row[0] for row in conn.execute("SELECT status FROM expert_runs").fetchall()
        ]
        message_status = conn.execute(
            "SELECT status FROM messages WHERE id = ?",
            (events[-1][1]["messageId"],),
        ).fetchone()[0]
    assert expert_statuses == ["failed"]
    assert message_status == "CANCELED"


@pytest.mark.asyncio
async def test_client_stream_cancellation_closes_message_turn_and_runtime(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="ESP32 断连测试",
        project_name="断连测试",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
    )
    expert = workspace.experts[0]
    provider = _BlockingExpertProvider()
    monkeypatch.setattr(chat_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(chat_router, "provider_factory", lambda: provider)
    response = await chat_router.stream_project_chat(
        workspace.project.id,
        PersistedChatRequest(
            content="开始后断开连接",
            model=LLMModelId.DEEPSEEK_V4_FLASH,
            projectExpertId=expert.id,
            threadId=expert.conversationId,
            expertType=ExpertType.SMART_ENGINEER,
        ),
    )
    iterator = response.body_iterator
    chunk = await anext(iterator)
    assert "event: chat.started" in chunk
    while "CLOUD_LLM_REQUEST" not in chunk:
        chunk = await anext(iterator)

    pending_next = asyncio.create_task(anext(iterator))
    await asyncio.wait_for(provider.started.wait(), timeout=2)
    await asyncio.sleep(0)
    assert pending_next.done() is False
    pending_next.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending_next

    with sqlite3.connect(repository.db_path) as conn:
        message_status = conn.execute(
            """
            SELECT status FROM messages
            WHERE role = 'assistant' ORDER BY created_at DESC, rowid DESC LIMIT 1
            """
        ).fetchone()[0]
        turn_status = conn.execute(
            "SELECT status FROM conversation_turns ORDER BY created_at DESC LIMIT 1"
        ).fetchone()[0]
        expert_status = conn.execute(
            "SELECT status FROM expert_runs ORDER BY created_at DESC LIMIT 1"
        ).fetchone()[0]
    assert message_status == "CANCELED"
    assert turn_status == "CANCELED"
    assert expert_status == "failed"


def test_authorized_skill_resume_stream_executes_once_with_sanitized_progress(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, workspace, pending_id, assistant_message_id = _chat_authorization(
        tmp_path,
        monkeypatch,
    )
    token = "local-skill-test-token"
    monkeypatch.setenv("ZHANGWEN_DESKTOP_CAPABILITY_TOKEN", token)
    calls = 0
    observed_tool_statuses: list[list[str]] = []

    async def handler(payload: dict[str, object]) -> dict[str, object]:
        nonlocal calls
        calls += 1
        with sqlite3.connect(repository.db_path) as conn:
            observed_tool_statuses.append(
                [row[0] for row in conn.execute("SELECT status FROM tool_runs").fetchall()]
            )
        return {"validated": True, "projectId": payload["projectId"]}

    monkeypatch.setattr(
        chat_router,
        "local_skill_runtime_factory",
        lambda db_path: SkillRuntime(
            db_path,
            ToolRunner(db_path, {"sandbox": handler}),
        ),
    )
    client = TestClient(app)
    legacy_resolve = client.post(
        f"/api/projects/{workspace.project.id}/pending-items/{pending_id}/resolve"
    )
    assert legacy_resolve.status_code == 409
    assert legacy_resolve.json()["detail"]["code"] == "SKILL_AUTHORIZATION_STREAM_REQUIRED"

    headers = {
        "X-Zhangwen-Host": "tauri",
        "X-Zhangwen-Capability-Token": token,
    }
    response = client.post(
        f"/api/projects/{workspace.project.id}/pending-items/{pending_id}/resolve/stream",
        headers=headers,
    )
    assert response.status_code == 200
    events = _events(response.text)
    assert [event for event, _ in events][0] == "chat.started"
    assert [event for event, _ in events][-1] == "chat.completed"
    assert calls == 1
    assert observed_tool_statuses == [["running"]]

    event_identity = {
        (
            payload["projectId"],
            payload["conversationId"],
            payload["messageId"],
            payload["requestTurnId"],
            payload["responseTurnId"],
        )
        for _, payload in events
    }
    assert len(event_identity) == 1
    identity = next(iter(event_identity))
    assert identity[0] == workspace.project.id
    assert identity[2] == assistant_message_id
    assert identity[3] != identity[4]
    progress = [payload["progress"] for event, payload in events if event == "chat.progress"]
    assert [(item["action"], item["status"]) for item in progress] == [
        ("LOCAL_EXECUTION_AUTHORIZATION", "COMPLETED"),
        ("LOCAL_TOOL_EXECUTION", "RUNNING"),
        ("LOCAL_TOOL_EXECUTION", "COMPLETED"),
    ]
    serialized = json.dumps(progress, ensure_ascii=False)
    assert "sandbox" not in serialized
    assert "skillrun" not in serialized
    assert workspace.project.id not in serialized

    with sqlite3.connect(repository.db_path) as conn:
        pending_status = conn.execute(
            "SELECT status FROM project_pending_items WHERE id = ?",
            (pending_id,),
        ).fetchone()[0]
        skill_status = conn.execute(
            "SELECT status FROM skill_runs ORDER BY created_at DESC LIMIT 1"
        ).fetchone()[0]
        authorization = conn.execute(
            """
            SELECT claimed_at, completed_at FROM skill_run_authorizations
            WHERE pending_item_id = ?
            """,
            (pending_id,),
        ).fetchone()
    assert pending_status == "resolved"
    assert skill_status == "completed"
    assert authorization[0] is not None and authorization[1] is not None

    repeated = client.post(
        f"/api/projects/{workspace.project.id}/pending-items/{pending_id}/resolve/stream",
        headers=headers,
    )
    assert repeated.status_code == 200
    assert [event for event, _ in _events(repeated.text)] == [
        "chat.started",
        "chat.completed",
    ]
    assert calls == 1


def test_skill_resume_requires_desktop_capability_and_old_pending_stays_non_executable(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, workspace, pending_id, _assistant_message_id = _chat_authorization(
        tmp_path,
        monkeypatch,
    )
    calls = 0

    async def handler(payload: dict[str, object]) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return payload

    monkeypatch.setattr(
        chat_router,
        "local_skill_runtime_factory",
        lambda db_path: SkillRuntime(
            db_path,
            ToolRunner(db_path, {"sandbox": handler}),
        ),
    )
    response = TestClient(app).post(
        f"/api/projects/{workspace.project.id}/pending-items/{pending_id}/resolve/stream",
        headers={"X-Zhangwen-Host": "web"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "HOST_CAPABILITY_UNAVAILABLE"
    assert calls == 0
    with sqlite3.connect(repository.db_path) as conn:
        assert conn.execute(
            "SELECT status FROM skill_runs ORDER BY created_at DESC LIMIT 1"
        ).fetchone()[0] == "awaiting_confirmation"
        assert conn.execute(
            "SELECT claimed_at FROM skill_run_authorizations WHERE pending_item_id = ?",
            (pending_id,),
        ).fetchone()[0] is None

    old_pending = ProjectCoordinatorService(repository.db_path).create_pending_item(
        project_id=workspace.project.id,
        title=LOCAL_EXECUTION_PENDING_TITLE,
        description=LOCAL_EXECUTION_PENDING_DESCRIPTION,
        priority=PendingItemPriority.CONFIRMATION,
        reason=LOCAL_EXECUTION_PENDING_REASON,
    )
    old_response = TestClient(app).post(
        f"/api/projects/{workspace.project.id}/pending-items/{old_pending.id}/resolve"
    )
    assert old_response.status_code == 200
    assert calls == 0
    with sqlite3.connect(repository.db_path) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM skill_run_authorizations WHERE pending_item_id = ?",
            (old_pending.id,),
        ).fetchone()[0] == 0


@pytest.mark.parametrize(
    ("mutation", "column", "value"),
    [
        ("missing-skill", "skill_id", "private-missing-skill"),
        ("invalid-input", "input_json", "{private-invalid-json"),
        ("owner-changed", "owner_expert_type", "structure_engineer"),
    ],
)
def test_authorization_revalidation_failure_never_leaves_running_state(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    column: str,
    value: str,
) -> None:
    repository, workspace, pending_id, assistant_message_id = _chat_authorization(
        tmp_path,
        monkeypatch,
    )
    token = f"revalidate-{mutation}-token"
    monkeypatch.setenv("ZHANGWEN_DESKTOP_CAPABILITY_TOKEN", token)
    with sqlite3.connect(repository.db_path) as conn:
        conn.execute(f"UPDATE skill_runs SET {column} = ?", (value,))

    response = TestClient(app).post(
        f"/api/projects/{workspace.project.id}/pending-items/{pending_id}/resolve/stream",
        headers={
            "X-Zhangwen-Host": "tauri",
            "X-Zhangwen-Capability-Token": token,
        },
    )

    assert response.status_code == 200
    events = _events(response.text)
    assert [event for event, _ in events] == ["chat.started", "chat.error"]
    assert value not in response.text
    assert "LOCAL_TOOL_EXECUTION" not in response.text
    with sqlite3.connect(repository.db_path) as conn:
        skill_status = conn.execute(
            "SELECT status FROM skill_runs ORDER BY created_at DESC LIMIT 1"
        ).fetchone()[0]
        authorization_completed = conn.execute(
            "SELECT completed_at FROM skill_run_authorizations WHERE pending_item_id = ?",
            (pending_id,),
        ).fetchone()[0]
        pending_status = conn.execute(
            "SELECT status FROM project_pending_items WHERE id = ?",
            (pending_id,),
        ).fetchone()[0]
        message_status = conn.execute(
            "SELECT status FROM messages WHERE id = ?",
            (assistant_message_id,),
        ).fetchone()[0]
        tool_count = conn.execute("SELECT COUNT(*) FROM tool_runs").fetchone()[0]
    assert skill_status == "failed"
    assert authorization_completed is not None
    assert pending_status == "resolved"
    assert message_status == "COMPLETED"
    assert tool_count == 0


def test_authorization_resume_revalidates_persisted_message_binding(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, workspace, pending_id, _assistant_message_id = _chat_authorization(
        tmp_path,
        monkeypatch,
    )
    token = "message-binding-token"
    monkeypatch.setenv("ZHANGWEN_DESKTOP_CAPABILITY_TOKEN", token)
    with sqlite3.connect(repository.db_path) as conn:
        request_message_id = conn.execute(
            "SELECT request_message_id FROM expert_runs ORDER BY created_at DESC LIMIT 1"
        ).fetchone()[0]
        conn.execute(
            "UPDATE expert_runs SET response_message_id = ?",
            (request_message_id,),
        )

    response = TestClient(app).post(
        f"/api/projects/{workspace.project.id}/pending-items/{pending_id}/resolve/stream",
        headers={
            "X-Zhangwen-Host": "tauri",
            "X-Zhangwen-Capability-Token": token,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "SKILL_AUTHORIZATION_NOT_FOUND"
    with sqlite3.connect(repository.db_path) as conn:
        assert conn.execute(
            "SELECT status FROM skill_runs ORDER BY created_at DESC LIMIT 1"
        ).fetchone()[0] == "awaiting_confirmation"
        assert conn.execute(
            "SELECT claimed_at FROM skill_run_authorizations WHERE pending_item_id = ?",
            (pending_id,),
        ).fetchone()[0] is None
        assert conn.execute("SELECT COUNT(*) FROM tool_runs").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_v24_migration_does_not_infer_legacy_skill_authorization(
    tmp_path,
) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="ESP32 历史授权",
        project_name="历史授权",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
    )
    legacy_run = await SkillRuntime(repository.db_path).run(
        project_id=workspace.project.id,
        skill_id="mock-test",
        payload={"projectId": workspace.project.id},
        confirmed=False,
        requesting_expert=ExpertType.SMART_ENGINEER,
    )
    legacy_pending = ProjectCoordinatorService(
        repository.db_path
    ).create_pending_item(
        project_id=workspace.project.id,
        title=LOCAL_EXECUTION_PENDING_TITLE,
        description=LOCAL_EXECUTION_PENDING_DESCRIPTION,
        priority=PendingItemPriority.CONFIRMATION,
        reason=LOCAL_EXECUTION_PENDING_REASON,
    )
    with sqlite3.connect(repository.db_path) as conn:
        conn.execute("DROP TABLE skill_run_authorizations")
        conn.execute(
            "DELETE FROM schema_migration_audit WHERE id = 'migration_v24_v25'"
        )
        conn.execute("PRAGMA user_version=24")

    migrated = ProjectRepository(tmp_path)
    migrated_runtime = SkillRuntime(migrated.db_path)
    with sqlite3.connect(migrated.db_path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 31
        assert conn.execute(
            "SELECT COUNT(*) FROM skill_run_authorizations"
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT status FROM skill_runs WHERE id = ?",
            (legacy_run.id,),
        ).fetchone()[0] == "awaiting_confirmation"
    assert migrated_runtime.has_authorization(
        project_id=workspace.project.id,
        pending_item_id=legacy_pending.id,
    ) is False
    with pytest.raises(SkillAuthorizationError) as missing:
        await migrated_runtime.resume_authorized(
            project_id=workspace.project.id,
            pending_item_id=legacy_pending.id,
        )
    assert missing.value.code == "SKILL_AUTHORIZATION_NOT_FOUND"


@pytest.mark.asyncio
async def test_authorization_stream_cancel_closes_tool_and_skill_without_rewriting_message(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, workspace, pending_id, assistant_message_id = _chat_authorization(
        tmp_path,
        monkeypatch,
    )
    token = "cancel-local-skill-token"
    monkeypatch.setenv("ZHANGWEN_DESKTOP_CAPABILITY_TOKEN", token)
    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def handler(payload: dict[str, object]) -> dict[str, object]:
        nonlocal calls
        _ = payload
        calls += 1
        started.set()
        await release.wait()
        return {"validated": True}

    runtime = SkillRuntime(
        repository.db_path,
        ToolRunner(repository.db_path, {"sandbox": handler}),
    )
    monkeypatch.setattr(chat_router, "local_skill_runtime_factory", lambda _db: runtime)
    http_request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [
                (b"x-zhangwen-host", b"tauri"),
                (b"x-zhangwen-capability-token", token.encode()),
            ],
        }
    )
    response = await chat_router.stream_skill_authorization_resolution(
        workspace.project.id,
        pending_id,
        http_request,
    )
    iterator = response.body_iterator
    chunks = [await anext(iterator)]
    start_event = _events(chunks[0])[0][1]
    while True:
        chunk = await anext(iterator)
        chunks.append(chunk)
        parsed = _events(chunk)
        if any(
            event == "chat.progress"
            and payload["progress"]["action"] == "LOCAL_TOOL_EXECUTION"
            and payload["progress"]["status"] == "RUNNING"
            for event, payload in parsed
        ):
            break
    await asyncio.wait_for(started.wait(), timeout=2)
    with pytest.raises(SkillAuthorizationError) as duplicate:
        await runtime.resume_authorized(
            project_id=workspace.project.id,
            pending_item_id=pending_id,
        )
    assert duplicate.value.code == "SKILL_AUTHORIZATION_IN_PROGRESS"
    assert calls == 1

    assert chat_router.sessions.cancel(str(start_event["requestId"])) is True
    while True:
        try:
            chunks.append(await anext(iterator))
        except StopAsyncIteration:
            break
    events = _events("".join(chunks))
    assert events[-1][0] == "chat.canceled"
    assert events[-1][1]["type"] == "CANCELED"
    with sqlite3.connect(repository.db_path) as conn:
        tool_status = conn.execute(
            "SELECT status FROM tool_runs ORDER BY created_at DESC LIMIT 1"
        ).fetchone()[0]
        skill_status = conn.execute(
            "SELECT status FROM skill_runs ORDER BY created_at DESC LIMIT 1"
        ).fetchone()[0]
        authorization_completed = conn.execute(
            "SELECT completed_at FROM skill_run_authorizations WHERE pending_item_id = ?",
            (pending_id,),
        ).fetchone()[0]
        message_status = conn.execute(
            "SELECT status FROM messages WHERE id = ?",
            (assistant_message_id,),
        ).fetchone()[0]
    assert tool_status == "failed"
    assert skill_status == "failed"
    assert authorization_completed is not None
    assert message_status == "COMPLETED"


@pytest.mark.asyncio
async def test_authorization_stream_disconnect_closes_tool_and_skill_without_rewriting_message(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, workspace, pending_id, assistant_message_id = _chat_authorization(
        tmp_path,
        monkeypatch,
    )
    token = "disconnect-local-skill-token"
    monkeypatch.setenv("ZHANGWEN_DESKTOP_CAPABILITY_TOKEN", token)
    started = asyncio.Event()
    release = asyncio.Event()

    async def handler(payload: dict[str, object]) -> dict[str, object]:
        _ = payload
        started.set()
        await release.wait()
        return {"validated": True}

    monkeypatch.setattr(
        chat_router,
        "local_skill_runtime_factory",
        lambda db_path: SkillRuntime(
            db_path,
            ToolRunner(db_path, {"sandbox": handler}),
        ),
    )
    http_request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [
                (b"x-zhangwen-host", b"tauri"),
                (b"x-zhangwen-capability-token", token.encode()),
            ],
        }
    )
    response = await chat_router.stream_skill_authorization_resolution(
        workspace.project.id,
        pending_id,
        http_request,
    )
    iterator = response.body_iterator
    start_chunk = await anext(iterator)
    request_id = str(_events(start_chunk)[0][1]["requestId"])
    while True:
        chunk = await anext(iterator)
        if any(
            event == "chat.progress"
            and payload["progress"]["action"] == "LOCAL_TOOL_EXECUTION"
            and payload["progress"]["status"] == "RUNNING"
            for event, payload in _events(chunk)
        ):
            break
    await asyncio.wait_for(started.wait(), timeout=2)
    await iterator.aclose()

    with sqlite3.connect(repository.db_path) as conn:
        tool_status = conn.execute(
            "SELECT status FROM tool_runs ORDER BY created_at DESC LIMIT 1"
        ).fetchone()[0]
        skill_status = conn.execute(
            "SELECT status FROM skill_runs ORDER BY created_at DESC LIMIT 1"
        ).fetchone()[0]
        authorization_completed = conn.execute(
            "SELECT completed_at FROM skill_run_authorizations WHERE pending_item_id = ?",
            (pending_id,),
        ).fetchone()[0]
        message_status = conn.execute(
            "SELECT status FROM messages WHERE id = ?",
            (assistant_message_id,),
        ).fetchone()[0]
    assert tool_status == "failed"
    assert skill_status == "failed"
    assert authorization_completed is not None
    assert message_status == "COMPLETED"
    assert chat_router.sessions.cancel(request_id) is False


@pytest.mark.asyncio
async def test_problem_guide_stream_starts_before_real_project_progress(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="ESP32 需求澄清",
        project_name="需求澄清",
        initial_expert=ExpertType.PROBLEM_GUIDE,
        participating_experts=[ExpertType.PROBLEM_GUIDE],
    )
    expert = workspace.experts[0]
    provider = _BlockingProjectConversationProvider(
        {
            "questions": [
                {
                    "id": "product_form",
                    "type": "SINGLE_SELECT",
                    "question": "作品形态是什么？",
                    "options": [
                        {"id": "desktop", "label": "桌面设备"},
                        {"id": "portable", "label": "便携设备"},
                    ],
                }
            ],
            "completeness": 35,
            "message": "先确认作品形态。",
        }
    )
    monkeypatch.setattr(chat_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(chat_router, "provider_factory", lambda: provider)
    response = await chat_router.stream_project_chat(
        workspace.project.id,
        PersistedChatRequest(
            content="请帮我梳理需求",
            model=LLMModelId.DEEPSEEK_V4_FLASH,
            projectExpertId=expert.id,
            threadId=expert.conversationId,
            expertType=ExpertType.PROBLEM_GUIDE,
        ),
    )
    iterator = response.body_iterator
    chunks = [await anext(iterator)]
    assert _events(chunks[0])[0][0] == "chat.started"
    assert provider.started.is_set() is False
    for _ in range(12):
        chunks.append(await anext(iterator))
        if provider.started.is_set():
            break
    assert provider.started.is_set() is True
    provider.release.set()
    async for chunk in iterator:
        chunks.append(chunk)

    events = _events("".join(chunks))
    assert events[0][0] == "chat.started"
    assert events[-1][0] == "chat.completed"
    progress = [payload["progress"] for event, payload in events if event == "chat.progress"]
    pairs = [(item["action"], item["status"]) for item in progress]
    assert ("CONTEXT_READ", "RUNNING") in pairs
    assert ("CONTEXT_READ", "COMPLETED") in pairs
    assert ("CLOUD_LLM_REQUEST", "RUNNING") in pairs
    assert ("OUTPUT_VALIDATE", "RUNNING") in pairs
    assert ("OUTPUT_VALIDATE", "COMPLETED") in pairs
    assert ("CLOUD_LLM_REQUEST", "COMPLETED") in pairs
    assert ("PROJECT_UPDATE", "RUNNING") in pairs
    assert ("PROJECT_UPDATE", "COMPLETED") in pairs
    identities = {
        (
            payload["requestId"],
            payload["messageId"],
            payload["requestTurnId"],
            payload["responseTurnId"],
            payload["projectId"],
            payload["conversationId"],
        )
        for _, payload in events
    }
    assert len(identities) == 1


def _chat_authorization(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[ProjectRepository, ProjectWorkspace, str, str]:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="ESP32 受控沙箱",
        project_name="受控沙箱",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
    )
    expert = workspace.experts[0]
    monkeypatch.setattr(chat_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(
        chat_router,
        "provider_factory",
        lambda: _ExpertReplyProvider(
            {
                "content": "执行前需要确认。",
                "skillRequests": [
                    {
                        "skillId": "mock-test",
                        "input": {"projectId": workspace.project.id},
                    }
                ],
            }
        ),
    )
    response = TestClient(app).post(
        f"/api/projects/{workspace.project.id}/chat/stream",
        json={
            "content": "运行受控沙箱检查",
            "model": "deepseek-v4-flash",
            "projectExpertId": expert.id,
            "threadId": expert.conversationId,
            "expertType": "smart_engineer",
        },
    )
    assert response.status_code == 200
    events = _events(response.text)
    assert events[-1][0] == "chat.completed"
    assistant_message_id = str(events[-1][1]["messageId"])
    with sqlite3.connect(repository.db_path) as conn:
        pending_id = conn.execute(
            """
            SELECT pending_item_id FROM skill_run_authorizations
            WHERE project_id = ?
            """,
            (workspace.project.id,),
        ).fetchone()[0]
    return repository, workspace, str(pending_id), assistant_message_id


def _events(text: str) -> list[tuple[str, dict[str, object]]]:
    events: list[tuple[str, dict[str, object]]] = []
    for block in text.strip().split("\n\n"):
        event_name = ""
        payload: dict[str, object] | None = None
        for line in block.splitlines():
            if line.startswith("event:"):
                event_name = line[6:].strip()
            elif line.startswith("data:"):
                payload = json.loads(line[5:].strip())
        if event_name and payload is not None:
            events.append((event_name, payload))
    return events
