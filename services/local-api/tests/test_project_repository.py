import json
import sqlite3

import pytest

from zhangwen.artifacts.models import ArtifactKind, ArtifactStatus
from zhangwen.artifacts.repository import ArtifactRepository
from zhangwen.llm.contracts import ChatMessageStatus, LLMErrorCode, LLMModelId
from zhangwen.llm.errors import make_llm_error
from zhangwen.projects.errors import (
    ConversationContextError,
    ProjectArchivedError,
    ProjectValidationError,
    UnsupportedProjectSchemaError,
)
from zhangwen.projects.models import (
    ExpertType,
    ExpertWorkspaceStatus,
    ProjectExpertStatus,
    ProjectPersistenceVersion,
    ProjectStage,
    RouterOutput,
)
from zhangwen.projects.repository import ProjectRepository


def test_repository_initializes_v31_schema(tmp_path) -> None:
    repository = ProjectRepository(tmp_path)

    with sqlite3.connect(repository.db_path) as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert version == 31
    assert {
        "projects",
        "conversations",
        "messages",
        "drafts",
        "meta",
        "solutions",
        "clarification_rounds",
        "hardware_components",
        "proposals",
        "execution_plans",
        "task_nodes",
        "user_skills",
        "model_route_audit",
        "artifacts",
        "artifact_versions",
        "floating_window_states",
        "spec_runs",
        "spec_files",
        "device_sessions",
        "device_operations",
        "cad_runs",
        "cad_files",
        "cad_jobs",
        "artifact_files",
        "hardware_mechanical_links",
        "lesson_runs",
        "lesson_files",
        "package_exports",
        "conversation_turns",
        "clarification_questions",
        "clarification_answers",
        "expert_definitions",
        "project_experts",
        "expert_private_memories",
        "expert_drafts",
        "project_shared_contexts",
        "shared_context_changes",
        "project_coordinator_states",
        "project_shared_facts",
        "project_decisions",
        "project_pending_items",
        "project_handoffs",
        "project_tasks",
        "artifact_dependencies",
        "expert_runs",
        "skill_runs",
        "tool_runs",
        "skill_run_authorizations",
        "project_state_snapshots",
        "project_events",
        "project_change_sets",
        "project_versions",
        "project_releases",
        "capabilities",
        "capability_relations",
        "project_capability_bindings",
        "tool_jobs",
        "local_bridge_sessions",
        "cad_intent_revisions",
        "creator_projection_receipts",
    }.issubset(tables)

    with sqlite3.connect(repository.db_path) as conn:
        message_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(messages)").fetchall()
        }
        conversation_indexes = conn.execute("PRAGMA index_list(conversations)").fetchall()
        unique_project_indexes = []
        for index in conversation_indexes:
            if not index[2]:
                continue
            columns = [
                column[2]
                for column in conn.execute(f"PRAGMA index_info({index[1]})").fetchall()
            ]
            if columns == ["project_id"]:
                unique_project_indexes.append(index[1])
        expert_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(project_experts)").fetchall()
        }
        artifact_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(artifacts)").fetchall()
        }
        shared_fact_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(project_shared_facts)").fetchall()
        }
        pending_item_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(project_pending_items)").fetchall()
        }
        task_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(project_tasks)").fetchall()
        }
        expert_indexes = conn.execute("PRAGMA index_list(project_experts)").fetchall()
        clarification_answer_indexes = conn.execute(
            "PRAGMA index_list(clarification_answers)"
        ).fetchall()
        unique_project_expert_indexes = []
        for index in expert_indexes:
            if not index[2]:
                continue
            columns = [
                column[2]
                for column in conn.execute(f"PRAGMA index_info({index[1]})").fetchall()
            ]
            if columns == ["project_id", "expert_type"]:
                unique_project_expert_indexes.append(index[1])
        unique_answer_turn_indexes = []
        unique_answer_question_indexes = []
        for index in clarification_answer_indexes:
            if not index[2]:
                continue
            columns = [
                column[2]
                for column in conn.execute(f"PRAGMA index_info({index[1]})").fetchall()
            ]
            if columns == ["project_id", "conversation_id", "client_turn_id"]:
                unique_answer_turn_indexes.append(index[1])
            if columns == ["question_record_id"]:
                unique_answer_question_indexes.append(index[1])
    assert "metadata_json" in message_columns
    assert {"legacy_expert_type", "archived_legacy_thread", "workspace_status"}.issubset(
        expert_columns
    )
    assert {"legacy_owner_expert", "creator_legacy_expert", "domain_status"}.issubset(
        artifact_columns
    )
    assert "key" in shared_fact_columns
    assert "critical_path" in pending_item_columns
    assert {"owner_expert_type", "dependency_task_ids_json", "artifact_ids_json"}.issubset(
        task_columns
    )
    assert unique_project_indexes == []
    assert unique_project_expert_indexes == []
    assert unique_answer_turn_indexes == []
    assert len(unique_answer_question_indexes) == 1


def test_automatic_recovery_claim_is_atomic_per_failed_message(tmp_path) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project("恢复并发", "制作一个提醒器")
    workspace = repository.add_project_expert(
        workspace.project.id,
        ExpertType.SMART_ENGINEER,
        activate=True,
    )
    expert = next(
        item for item in workspace.experts if item.expertType == ExpertType.SMART_ENGINEER
    )
    _, _, failed = repository.append_user_and_assistant(
        workspace.project.id,
        "保持原需求",
        LLMModelId.DEEPSEEK_V4_FLASH,
        project_expert_id=expert.id,
        client_turn_id="original-turn",
    )
    repository.update_message(
        workspace.project.id,
        failed.id,
        status=ChatMessageStatus.FAILED,
        error=make_llm_error(LLMErrorCode.LOCAL_OUTPUT_REJECTED),
    )

    repository.append_user_and_assistant(
        workspace.project.id,
        "保持原需求",
        LLMModelId.DEEPSEEK_V4_FLASH,
        project_expert_id=expert.id,
        client_turn_id="automatic-recovery-a",
        user_metadata={
            "recoveryOfMessageId": failed.id,
            "recoveryLabel": "已按原需求自动重试",
        },
        automatic_recovery_source_message_id=failed.id,
    )

    with pytest.raises(ConversationContextError) as exc_info:
        repository.append_user_and_assistant(
            workspace.project.id,
            "保持原需求",
            LLMModelId.DEEPSEEK_V4_FLASH,
            project_expert_id=expert.id,
            client_turn_id="automatic-recovery-b",
            user_metadata={
                "recoveryOfMessageId": failed.id,
                "recoveryLabel": "已按原需求自动重试",
            },
            automatic_recovery_source_message_id=failed.id,
        )

    assert exc_info.value.code == "DUPLICATE_TURN"


def test_automatic_recovery_claim_enforces_three_attempt_chain(tmp_path) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project("恢复上限", "制作一个提醒器")
    workspace = repository.add_project_expert(
        workspace.project.id,
        ExpertType.SMART_ENGINEER,
        activate=True,
    )
    expert = next(
        item for item in workspace.experts if item.expertType == ExpertType.SMART_ENGINEER
    )
    _, _, current_failure = repository.append_user_and_assistant(
        workspace.project.id,
        "保持原需求",
        LLMModelId.DEEPSEEK_V4_FLASH,
        project_expert_id=expert.id,
        client_turn_id="chain-original",
    )
    repository.update_message(
        workspace.project.id,
        current_failure.id,
        status=ChatMessageStatus.FAILED,
        error=make_llm_error(LLMErrorCode.LOCAL_OUTPUT_REJECTED),
    )

    for attempt in range(1, 4):
        _, _, next_failure = repository.append_user_and_assistant(
            workspace.project.id,
            "保持原需求",
            LLMModelId.DEEPSEEK_V4_FLASH,
            project_expert_id=expert.id,
            client_turn_id=f"chain-recovery-{attempt}",
            user_metadata={
                "recoveryOfMessageId": current_failure.id,
                "recoveryLabel": "已按原需求自动重试",
            },
            automatic_recovery_source_message_id=current_failure.id,
        )
        repository.update_message(
            workspace.project.id,
            next_failure.id,
            status=ChatMessageStatus.FAILED,
            error=make_llm_error(LLMErrorCode.LOCAL_OUTPUT_REJECTED),
        )
        current_failure = next_failure

    with pytest.raises(ConversationContextError) as exc_info:
        repository.append_user_and_assistant(
            workspace.project.id,
            "保持原需求",
            LLMModelId.DEEPSEEK_V4_FLASH,
            project_expert_id=expert.id,
            client_turn_id="chain-recovery-4",
            user_metadata={
                "recoveryOfMessageId": current_failure.id,
                "recoveryLabel": "已按原需求自动重试",
            },
            automatic_recovery_source_message_id=current_failure.id,
        )

    assert exc_info.value.code == "RATE_LIMITED"


def test_repository_refuses_future_schema_version(tmp_path) -> None:
    db_dir = tmp_path / "projects"
    db_dir.mkdir(parents=True)
    db_path = db_dir / "zhangwen.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA user_version=99")

    with pytest.raises(UnsupportedProjectSchemaError):
        ProjectRepository(tmp_path)


def test_project_lifecycle_persists_after_reload(tmp_path) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project(
        " 自动浇花 ",
        "想做一个自动浇花装置",
        LLMModelId.DEEPSEEK_V4_PRO,
    )

    assert workspace.project.name == "自动浇花"
    assert workspace.project.profile.initialIdea == "想做一个自动浇花装置"
    assert workspace.project.selectedModel == LLMModelId.DEEPSEEK_V4_PRO
    assert workspace.project.schemaVersion == ProjectPersistenceVersion.V31
    assert workspace.sharedContext is not None
    assert workspace.coordinator is not None
    assert workspace.conversation.messages[0].content == "想做一个自动浇花装置"
    assert [expert.expertType for expert in workspace.experts] == [
        ExpertType.PROBLEM_GUIDE,
        ExpertType.SMART_ENGINEER,
    ]
    assert workspace.expertConversations[0].id == workspace.conversation.id

    guide = workspace.experts[0]
    engineer = workspace.experts[1]
    repository.save_draft(workspace.project.id, "项目共享草稿")
    repository.update_project(
        workspace.project.id,
        name="自动浇花 v2",
        selected_model=LLMModelId.DEEPSEEK_V4_FLASH,
    )

    reloaded = ProjectRepository(tmp_path).open_project(workspace.project.id)
    assert reloaded.project.name == "自动浇花 v2"
    assert reloaded.project.selectedModel == LLMModelId.DEEPSEEK_V4_FLASH
    assert reloaded.draft.content == "项目共享草稿"
    engineer_workspace = ProjectRepository(tmp_path).set_active_expert(
        workspace.project.id,
        engineer.id,
    )
    assert engineer_workspace.conversation.id == engineer.conversationId
    assert engineer_workspace.draft.content == "项目共享草稿"

    projects, active_id = repository.list_projects()
    assert active_id == workspace.project.id
    assert projects[0].messageCount == 2
    assert len(projects[0].activeExpertIds) == 2


def test_delivery_track_defaults_to_project_and_persists_lesson_choice(tmp_path) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project("教案路线", "制作课堂环境监测项目")

    assert repository.get_delivery_track(workspace.project.id) == "project"

    updated = repository.set_delivery_track(workspace.project.id, "lesson")

    assert repository.get_delivery_track(workspace.project.id) == "lesson"
    assert updated.sharedContext is not None
    assert updated.sharedContext.deliveryTrack == "lesson"
    with pytest.raises(ProjectValidationError, match="未知产物路线"):
        repository.set_delivery_track(workspace.project.id, "invalid")


def test_project_suggestion_recommends_experts_without_llm(tmp_path) -> None:
    repository = ProjectRepository(tmp_path)

    suggestion = repository.suggest_project("做一个带外壳的 ESP32 课堂提醒器")

    assert suggestion.name.endswith(("项目", "装置", "课程", "器"))
    assert ExpertType.PROBLEM_GUIDE in suggestion.recommendedExpertTypes
    assert ExpertType.SMART_ENGINEER in suggestion.recommendedExpertTypes
    assert ExpertType.STRUCTURE_ENGINEER in suggestion.recommendedExpertTypes
    assert {expert.type for expert in suggestion.availableExperts} == {
        ExpertType.PROBLEM_GUIDE,
        ExpertType.SMART_ENGINEER,
        ExpertType.STRUCTURE_ENGINEER,
    }


def test_create_project_from_idea_builds_selected_three_teacher_workspace(tmp_path) -> None:
    repository = ProjectRepository(tmp_path)
    route = RouterOutput(
        intent="technical_and_structure_implementation",
        projectName="智能花盆",
        initialExpert=ExpertType.STRUCTURE_ENGINEER,
        recommendedExperts=[
            ExpertType.SMART_ENGINEER,
            ExpertType.STRUCTURE_ENGINEER,
            ExpertType.SMART_ENGINEER,
        ],
        confidence=0.82,
        reason="需要硬件和结构协同。",
        requiresClarification=False,
    )

    workspace = repository.create_project_from_idea(
        idea="做自动浇水、联网并带外壳的花盆",
        project_name="智能花盆",
        initial_expert=ExpertType.STRUCTURE_ENGINEER,
        participating_experts=[
            ExpertType.SMART_ENGINEER,
            ExpertType.STRUCTURE_ENGINEER,
            ExpertType.SMART_ENGINEER,
        ],
        router_result=route,
        expert_selection_mode="manual",
        idempotency_key="create-flowerpot-1",
    )

    assert workspace.project.name == "智能花盆"
    assert {expert.expertType for expert in workspace.experts} == {
        ExpertType.SMART_ENGINEER,
        ExpertType.STRUCTURE_ENGINEER,
    }
    assert ExpertType.PROBLEM_GUIDE not in {expert.expertType for expert in workspace.experts}
    assert len({expert.conversationId for expert in workspace.experts}) == 2
    experts_by_type = {expert.expertType: expert for expert in workspace.experts}
    structure_expert = experts_by_type[ExpertType.STRUCTURE_ENGINEER]
    smart_expert = experts_by_type[ExpertType.SMART_ENGINEER]
    assert workspace.project.activeExpertId == structure_expert.id
    assert workspace.conversation.id == structure_expert.conversationId
    assert structure_expert.status == ProjectExpertStatus.WORKING
    assert structure_expert.workspaceStatus == ExpertWorkspaceStatus.IN_PROGRESS
    assert smart_expert.status == ProjectExpertStatus.IDLE
    assert smart_expert.workspaceStatus == ExpertWorkspaceStatus.NOT_STARTED
    assert workspace.conversation.messages[0].content == "做自动浇水、联网并带外壳的花盆"
    assert workspace.conversation.messages[0].metadata["source"] == "project_creation"
    assert workspace.conversation.messages[0].metadata["initialExpert"] == "structure_engineer"
    assert workspace.conversation.messages[1].role == "assistant"
    assert workspace.conversation.messages[1].status == ChatMessageStatus.READY
    assert workspace.conversation.messages[1].metadata["source"] == "project_creation_runtime"
    assert workspace.conversation.messages[1].metadata["initialExpert"] == "structure_engineer"
    assert workspace.conversation.messages[1].content == ""
    assert workspace.kickoff is not None
    assert workspace.kickoff.status == "READY"
    assert workspace.kickoff.content == "做自动浇水、联网并带外壳的花盆"
    assert workspace.kickoff.userMessageId == workspace.conversation.messages[0].id
    assert workspace.kickoff.assistantMessageId == workspace.conversation.messages[1].id
    assert workspace.kickoff.projectExpertId == structure_expert.id
    assert workspace.coordinator is not None
    assert workspace.coordinator.currentPendingItem is not None
    assert workspace.coordinator.currentPendingItem.isHighlighted is True
    assert workspace.coordinator.currentPendingItem.affectedExperts == [
        ExpertType.STRUCTURE_ENGINEER
    ]

    with sqlite3.connect(repository.db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT field, key, value_json, status
            FROM project_shared_facts
            WHERE project_id = ?
            ORDER BY field
            """,
            (workspace.project.id,),
        ).fetchall()
        task = conn.execute(
            "SELECT owner_expert_type, status, current_pending_item_id FROM project_tasks WHERE project_id = ?",
            (workspace.project.id,),
        ).fetchone()
        pending_count = conn.execute(
            "SELECT COUNT(*) FROM project_pending_items WHERE project_id = ? AND is_highlighted = 1",
            (workspace.project.id,),
        ).fetchone()[0]

    facts = {row["field"]: row for row in rows}
    assert json.loads(facts["initial_idea"]["value_json"]) == "做自动浇水、联网并带外壳的花盆"
    router_metadata = json.loads(facts["entry_router_result"]["value_json"])
    assert router_metadata["expertSelectionMode"] == "manual"
    assert router_metadata["initialExpert"] == "structure_engineer"
    assert router_metadata["routerResult"] == {
        "intent": "technical_and_structure_implementation",
        "projectName": "智能花盆",
        "initialExpert": "structure_engineer",
        "recommendedExperts": ["smart_engineer", "structure_engineer"],
        "confidence": 0.82,
        "reason": "需要硬件和结构协同。",
        "requiresClarification": False,
    }
    assert facts["creation_idempotency_key"]["key"] == (
        "creation_idempotency_key:create-flowerpot-1"
    )
    assert task["owner_expert_type"] == "structure_engineer"
    assert task["status"] == "running"
    assert task["current_pending_item_id"] is not None
    assert pending_count == 1


def test_create_project_from_idea_rejects_initial_expert_outside_selection(tmp_path) -> None:
    repository = ProjectRepository(tmp_path)

    with pytest.raises(ProjectValidationError):
        repository.create_project_from_idea(
            idea="ESP32 读取温湿度并上传 MQTT",
            project_name="温湿度 MQTT",
            initial_expert=ExpertType.STRUCTURE_ENGINEER,
            participating_experts=[ExpertType.SMART_ENGINEER],
        )

    with sqlite3.connect(repository.db_path) as conn:
        project_count = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    assert project_count == 0


def test_create_project_from_idea_rolls_back_when_seed_records_fail(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = ProjectRepository(tmp_path)

    def fail_insert(*_args, **_kwargs) -> None:
        raise RuntimeError("seed failed")

    monkeypatch.setattr(repository, "_insert_creation_records", fail_insert)

    with pytest.raises(RuntimeError):
        repository.create_project_from_idea(
            idea="ESP32 读取温湿度并上传 MQTT",
            project_name="温湿度 MQTT",
            initial_expert=ExpertType.SMART_ENGINEER,
            participating_experts=[ExpertType.SMART_ENGINEER, ExpertType.PROBLEM_GUIDE],
            idempotency_key="rollback-key",
        )

    with sqlite3.connect(repository.db_path) as conn:
        for table in (
            "projects",
            "conversations",
            "messages",
            "project_experts",
            "project_shared_contexts",
            "project_coordinator_states",
            "project_shared_facts",
            "project_pending_items",
            "project_tasks",
        ):
            assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_create_project_from_idea_uses_idempotency_key(tmp_path) -> None:
    repository = ProjectRepository(tmp_path)
    first = repository.create_project_from_idea(
        idea="ESP32 读取温湿度并上传 MQTT",
        project_name="温湿度 MQTT",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
        idempotency_key="same-create-key",
    )

    second = repository.create_project_from_idea(
        idea="ESP32 读取温湿度并上传 MQTT",
        project_name="不应创建的新名字",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
        idempotency_key="same-create-key",
    )

    assert second.project.id == first.project.id
    assert second.project.name == "温湿度 MQTT"
    with sqlite3.connect(repository.db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 2
        assert (
            conn.execute(
                """
                SELECT COUNT(*) FROM project_shared_facts
                WHERE field = 'creation_idempotency_key'
                """
            ).fetchone()[0]
            == 1
        )


def test_add_and_remove_project_expert_preserves_independent_thread(tmp_path) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="先梳理一个自动浇水项目",
        project_name="自动浇水",
        initial_expert=ExpertType.PROBLEM_GUIDE,
        participating_experts=[ExpertType.PROBLEM_GUIDE],
    )
    guide = workspace.experts[0]

    added = repository.add_project_expert(
        workspace.project.id,
        ExpertType.SMART_ENGINEER,
        activate=True,
    )
    experts_by_type = {expert.expertType: expert for expert in added.experts}
    smart = experts_by_type[ExpertType.SMART_ENGINEER]

    assert added.project.activeExpertId == smart.id
    assert added.conversation.id == smart.conversationId
    assert smart.conversationId != guide.conversationId
    smart_thread = next(
        thread
        for thread in added.expertConversations
        if thread.projectExpertId == smart.id
    )
    guide_thread = next(
        thread
        for thread in added.expertConversations
        if thread.projectExpertId == guide.id
    )
    assert smart_thread.messages == []
    assert [message.role for message in guide_thread.messages] == ["user", "assistant"]

    removed = repository.remove_project_expert(
        workspace.project.id,
        smart.id,
        confirm_impact=True,
    )

    assert {expert.expertType for expert in removed.experts} == {ExpertType.PROBLEM_GUIDE}
    assert removed.project.activeExpertId == guide.id
    assert removed.conversation.id == guide.conversationId

    with sqlite3.connect(repository.db_path) as conn:
        conn.row_factory = sqlite3.Row
        removed_row = conn.execute(
            "SELECT removed_at, conversation_id FROM project_experts WHERE id = ?",
            (smart.id,),
        ).fetchone()
        conversation_count = conn.execute(
            "SELECT COUNT(*) FROM conversations WHERE project_id = ?",
            (workspace.project.id,),
        ).fetchone()[0]
        smart_message_count = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE conversation_id = ?",
            (smart.conversationId,),
        ).fetchone()[0]

    assert removed_row is not None
    assert removed_row["removed_at"] is not None
    assert removed_row["conversation_id"] == smart.conversationId
    assert conversation_count == 2
    assert smart_message_count == 0


def test_remove_project_expert_requires_one_remaining_expert(tmp_path) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="只从一个专家开始",
        project_name="单专家项目",
        initial_expert=ExpertType.PROBLEM_GUIDE,
        participating_experts=[ExpertType.PROBLEM_GUIDE],
    )

    with pytest.raises(ProjectValidationError):
        repository.remove_project_expert(
            workspace.project.id,
            workspace.experts[0].id,
            confirm_impact=True,
        )

    with sqlite3.connect(repository.db_path) as conn:
        removed_at = conn.execute(
            "SELECT removed_at FROM project_experts WHERE id = ?",
            (workspace.experts[0].id,),
        ).fetchone()[0]

    assert removed_at is None


def test_v19_preserves_legacy_threads_without_merging_chat_content(tmp_path) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project("旧项目", "做一个课堂提醒器")
    now = "2026-07-09T00:00:00+00:00"

    with sqlite3.connect(repository.db_path) as conn:
        conn.execute(
            """
            INSERT INTO expert_definitions (
              id, expert_type, name, description, icon, built_in,
              skill_ids_json, supported_artifact_types_json
            ) VALUES
              ('expert_def_ideator', 'ideator', '创想家', '', 'spark', 1, '[]', '[]'),
              ('expert_def_educator', 'educator', '教育家', '', 'book', 1, '[]', '[]')
            ON CONFLICT(expert_type) DO NOTHING
            """
        )
        conn.execute(
            """
            INSERT INTO conversations (id, project_id, created_at, updated_at)
            VALUES ('conv_legacy_ideator', ?, ?, ?),
                   ('conv_legacy_educator', ?, ?, ?)
            """,
            (workspace.project.id, now, now, workspace.project.id, now, now),
        )
        conn.execute(
            """
            INSERT INTO project_experts (
              id, project_id, expert_definition_id, expert_type, legacy_expert_type,
              archived_legacy_thread, conversation_id, private_memory_id, status,
              workspace_status, current_task, added_at, removed_at
            ) VALUES
              ('pexp_legacy_ideator', ?, 'expert_def_ideator', 'ideator',
               NULL, 0, 'conv_legacy_ideator', 'pmem_legacy_ideator', 'waiting_user',
               NULL, '旧创想家任务', ?, NULL),
              ('pexp_legacy_educator', ?, 'expert_def_educator', 'educator',
               NULL, 0, 'conv_legacy_educator', 'pmem_legacy_educator', 'idle',
               NULL, '旧教育家任务', ?, NULL)
            """,
            (workspace.project.id, now, workspace.project.id, now),
        )
        conn.execute(
            """
            INSERT INTO messages (
              id, conversation_id, project_id, role, content, reasoning_content,
              status, model, error_json, usage_json, structured_payload_json,
              metadata_json, created_at, updated_at
            ) VALUES
              ('msg_legacy_ideator', 'conv_legacy_ideator', ?, 'user',
               '创想家历史内容', NULL, 'COMPLETED', NULL, NULL, NULL, NULL, NULL, ?, ?),
              ('msg_legacy_educator', 'conv_legacy_educator', ?, 'user',
               '教育家历史内容', NULL, 'COMPLETED', NULL, NULL, NULL, NULL, NULL, ?, ?)
            """,
            (workspace.project.id, now, now, workspace.project.id, now, now),
        )
        conn.execute(
            """
            INSERT INTO expert_private_memories (
              id, project_id, project_expert_id, notes_json, updated_at
            ) VALUES
              ('pmem_legacy_ideator', ?, 'pexp_legacy_ideator', '[]', ?),
              ('pmem_legacy_educator', ?, 'pexp_legacy_educator', '[]', ?)
            """,
            (workspace.project.id, now, workspace.project.id, now),
        )
        conn.execute(
            """
            INSERT INTO expert_drafts (project_expert_id, project_id, content, updated_at)
            VALUES ('pexp_legacy_ideator', ?, '旧创想家草稿', ?),
                   ('pexp_legacy_educator', ?, '旧教育家草稿', ?)
            """,
            (workspace.project.id, now, workspace.project.id, now),
        )
        conn.execute(
            "UPDATE projects SET active_expert_id = 'pexp_legacy_ideator' WHERE id = ?",
            (workspace.project.id,),
        )
        conn.execute("PRAGMA user_version=18")

    migrated = ProjectRepository(tmp_path).get_workspace(workspace.project.id)
    ProjectRepository(tmp_path).get_workspace(workspace.project.id)

    assert migrated.project.schemaVersion == ProjectPersistenceVersion.V31
    assert migrated.project.activeExpertId == migrated.experts[0].id
    assert [expert.expertType for expert in migrated.experts] == [
        ExpertType.PROBLEM_GUIDE,
        ExpertType.SMART_ENGINEER,
    ]
    legacy_threads = {
        conversation.legacyExpertType: conversation
        for conversation in migrated.expertConversations
        if conversation.archivedLegacyThread
    }
    assert set(legacy_threads) == {"ideator", "educator"}
    assert legacy_threads["ideator"].id == "conv_legacy_ideator"
    assert legacy_threads["educator"].id == "conv_legacy_educator"
    assert legacy_threads["ideator"].messages[0].content == "创想家历史内容"
    assert legacy_threads["educator"].messages[0].content == "教育家历史内容"

    with sqlite3.connect(repository.db_path) as conn:
        legacy_rows = conn.execute(
            """
            SELECT expert_type, legacy_expert_type, archived_legacy_thread, removed_at
            FROM project_experts
            WHERE id IN ('pexp_legacy_ideator', 'pexp_legacy_educator')
            ORDER BY legacy_expert_type
            """
        ).fetchall()
        counts = conn.execute(
            """
            SELECT expert_type, archived_legacy_thread, COUNT(*)
            FROM project_experts
            WHERE project_id = ?
            GROUP BY expert_type, archived_legacy_thread
            """,
            (workspace.project.id,),
        ).fetchall()
    assert [row[0] for row in legacy_rows] == ["problem_guide", "problem_guide"]
    assert [row[1] for row in legacy_rows] == ["educator", "ideator"]
    assert all(row[2] == 1 and row[3] is not None for row in legacy_rows)
    assert {
        (row[0], row[1], row[2])
        for row in counts
        if row[0] == "problem_guide"
    } == {("problem_guide", 0, 1), ("problem_guide", 1, 2)}


def test_archive_hides_project_and_blocks_edit(tmp_path) -> None:
    repository = ProjectRepository(tmp_path)
    fallback = repository.create_project("保留项目", "保留项目创意")
    workspace = repository.create_project("待归档项目", "普通创意")
    repository.save_draft(workspace.project.id, "归档前草稿")
    ArtifactRepository(repository.db_path).upsert_text_artifact(
        artifact_id="artifact_archive_test",
        project_id=workspace.project.id,
        title="归档保留代码",
        kind=ArtifactKind.CODE,
        status=ArtifactStatus.DRAFT,
        source_agent_id=workspace.experts[0].id,
        source_entity_type="code",
        source_entity_id="code_archive_test",
        source_version=1,
        content="print('archive-safe')\n",
        summary="归档恢复验证",
        mime_type="text/x-python",
        language="python",
    )

    projects, active_id = repository.archive_project(workspace.project.id, True)
    assert [project.id for project in projects] == [fallback.project.id]
    assert active_id == fallback.project.id
    all_projects, _ = repository.list_projects(include_archived=True)
    archived = next(project for project in all_projects if project.id == workspace.project.id)
    assert archived.archivedAt is not None

    with pytest.raises(ProjectArchivedError):
        repository.save_draft(workspace.project.id, "不能写入")

    restored_projects, restored_active_id = repository.restore_project(
        workspace.project.id
    )
    assert {project.id for project in restored_projects} == {
        fallback.project.id,
        workspace.project.id,
    }
    assert restored_active_id == fallback.project.id

    restored = repository.open_project(workspace.project.id)
    assert restored.draft.content == "归档前草稿"
    assert restored.conversation.messages[0].content == "普通创意"
    artifacts = ArtifactRepository(repository.db_path).list_artifacts(workspace.project.id)
    assert [artifact.id for artifact in artifacts] == ["artifact_archive_test"]


def test_messages_and_stale_streaming_are_persisted(tmp_path) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project("项目", "普通创意")

    _, user, assistant = repository.append_user_and_assistant(
        workspace.project.id,
        "你好",
        LLMModelId.DEEPSEEK_V4_FLASH,
    )
    repository.update_message(
        workspace.project.id,
        assistant.id,
        content="你好，我是掌问。",
        status=ChatMessageStatus.COMPLETED,
        structured_payload={
            "type": "clarification",
            "completeness": 20,
            "question": {
                "id": "product_form",
                "text": "你希望它采用哪种形态？",
                "mode": "single",
                "allowCustomInput": True,
                "required": True,
                "options": [{"id": "recommended", "label": "由掌问推荐"}],
            },
        },
    )

    reloaded = ProjectRepository(tmp_path).get_workspace(workspace.project.id)
    assert reloaded.conversation.messages[0].content == "普通创意"
    assert [message.id for message in reloaded.conversation.messages[-2:]] == [
        user.id,
        assistant.id,
    ]
    assert reloaded.conversation.messages[-1].content == "你好，我是掌问。"
    assert reloaded.conversation.messages[-1].status == ChatMessageStatus.COMPLETED
    assert reloaded.conversation.messages[-1].structuredPayload is not None
    assert reloaded.conversation.messages[-1].structuredPayload["type"] == "clarification"

    _, _, streaming = repository.append_user_and_assistant(
        workspace.project.id,
        "再来一次",
        LLMModelId.DEEPSEEK_V4_FLASH,
    )
    assert streaming.status == ChatMessageStatus.STREAMING
    assert ProjectRepository(tmp_path).normalize_stale_streaming() == 1

    normalized = repository.get_workspace(workspace.project.id)
    assert normalized.conversation.messages[-1].status == ChatMessageStatus.FAILED
    assert normalized.conversation.messages[-1].error is not None
    assert normalized.conversation.messages[-1].error.code == "GENERATION_INTERRUPTED"
    assert [
        action.label for action in normalized.conversation.messages[-1].error.userActions
    ] == ["继续生成", "修改原需求"]


def test_v16_turn_metadata_and_structured_answers_are_persisted(tmp_path) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project("project", "ordinary idea")

    _, user, assistant = repository.append_user_and_assistant(
        workspace.project.id,
        "idea",
        LLMModelId.DEEPSEEK_V4_FLASH,
        turn_id="turn_idea",
        response_turn_id="turn_idea_response",
        client_turn_id="client_idea",
        request_json={"clientTurnId": "client_idea"},
        user_metadata={"currentIntent": "describe_idea"},
    )
    payload = _clarification_payload()
    repository.update_message(
        workspace.project.id,
        assistant.id,
        content="Pick one.",
        status=ChatMessageStatus.COMPLETED,
        structured_payload=payload,
        metadata={"requestTurnId": "turn_idea", "responseTurnId": "turn_idea_response"},
    )
    repository.register_clarification_question(
        project_id=workspace.project.id,
        conversation_id=workspace.conversation.id,
        source_message_id=assistant.id,
        stage=ProjectStage.CLARIFYING,
        payload=payload,
    )

    with pytest.raises(ConversationContextError) as invalid_option:
        repository.validate_structured_answer(
            project_id=workspace.project.id,
            conversation_id=workspace.conversation.id,
            source_message_id=assistant.id,
            question_id="product_form",
            selected_option_ids=["missing"],
            text_input="missing",
        )
    assert invalid_option.value.code == "OPTION_NOT_ALLOWED"

    _, answer_user, _ = repository.append_user_and_assistant(
        workspace.project.id,
        "desktop device",
        LLMModelId.DEEPSEEK_V4_FLASH,
        turn_id="turn_answer",
        response_turn_id="turn_answer_response",
        client_turn_id="client_answer",
        parent_turn_id="turn_idea",
        request_json={"clientTurnId": "client_answer", "questionId": "product_form"},
        user_metadata={
            "replyToMessageId": assistant.id,
            "replyToQuestionId": "product_form",
            "answerType": "single",
            "answerOptionIds": ["desktop_device"],
        },
    )
    repository.record_structured_answer(
        project_id=workspace.project.id,
        conversation_id=workspace.conversation.id,
        user_message_id=answer_user.id,
        client_turn_id="client_answer",
        source_message_id=assistant.id,
        question_id="product_form",
        selected_option_ids=["desktop_device"],
        text_input="desktop device",
    )

    reloaded = ProjectRepository(tmp_path).get_workspace(workspace.project.id)
    reloaded_messages = {message.id: message for message in reloaded.conversation.messages}
    assert reloaded_messages[user.id].metadata["clientTurnId"] == "client_idea"
    assert reloaded_messages[assistant.id].metadata["responseTurnId"] == "turn_idea_response"
    source_payload = reloaded_messages[assistant.id].structuredPayload
    assert source_payload["question"]["answered"] is True
    assert source_payload["question"]["answer"]["selectedOptionIds"] == ["desktop_device"]

    with sqlite3.connect(repository.db_path) as conn:
        conn.row_factory = sqlite3.Row
        turn = conn.execute(
            "SELECT * FROM conversation_turns WHERE client_turn_id = ?",
            ("client_answer",),
        ).fetchone()
        question = conn.execute(
            "SELECT * FROM clarification_questions WHERE question_id = ?",
            ("product_form",),
        ).fetchone()
        answer = conn.execute(
            "SELECT * FROM clarification_answers WHERE client_turn_id = ?",
            ("client_answer",),
        ).fetchone()

    assert turn["parent_turn_id"] == "turn_idea"
    assert question["status"] == "answered"
    assert answer["answer_type"] == "single"
    assert answer["values_json"] == '["desktop_device"]'
    assert answer["labels_json"] == '["Desktop device"]'

    with pytest.raises(ConversationContextError) as duplicate:
        repository.validate_structured_answer(
            project_id=workspace.project.id,
            conversation_id=workspace.conversation.id,
            source_message_id=assistant.id,
            question_id="product_form",
            selected_option_ids=["desktop_device"],
            text_input="desktop device",
        )
    assert duplicate.value.code == "QUESTION_ALREADY_ANSWERED"


def test_custom_text_answer_is_allowed_for_customizable_choice_question(tmp_path) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project("project", "ordinary idea")
    _, _, assistant = repository.append_user_and_assistant(
        workspace.project.id,
        "idea",
        LLMModelId.DEEPSEEK_V4_FLASH,
    )
    payload = _clarification_payload()
    repository.update_message(
        workspace.project.id,
        assistant.id,
        content="Pick one.",
        status=ChatMessageStatus.COMPLETED,
        structured_payload=payload,
    )
    repository.register_clarification_question(
        project_id=workspace.project.id,
        conversation_id=workspace.conversation.id,
        source_message_id=assistant.id,
        stage=ProjectStage.CLARIFYING,
        payload=payload,
    )
    _, answer_user, _ = repository.append_user_and_assistant(
        workspace.project.id,
        "hang it on the wall",
        LLMModelId.DEEPSEEK_V4_FLASH,
        turn_id="turn_custom_answer",
        client_turn_id="client_custom_answer",
    )

    repository.record_structured_answer(
        project_id=workspace.project.id,
        conversation_id=workspace.conversation.id,
        user_message_id=answer_user.id,
        client_turn_id="client_custom_answer",
        source_message_id=assistant.id,
        question_id="product_form",
        selected_option_ids=[],
        text_input="hang it on the wall",
    )

    with sqlite3.connect(repository.db_path) as conn:
        conn.row_factory = sqlite3.Row
        answer = conn.execute(
            "SELECT * FROM clarification_answers WHERE client_turn_id = ?",
            ("client_custom_answer",),
        ).fetchone()

    assert answer["answer_type"] == "text"
    assert answer["values_json"] == '["hang it on the wall"]'


def test_project_database_does_not_store_api_key(tmp_path) -> None:
    secret = "sk-test-secret-value"
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project("项目", "普通创意")
    repository.save_draft(workspace.project.id, "普通草稿")

    raw = repository.db_path.read_bytes()
    assert b"sk-test-secret-value" not in raw
    assert b"Authorization" not in raw


def _clarification_payload() -> dict:
    return {
        "type": "clarification",
        "completeness": 20,
        "question": {
            "id": "product_form",
            "text": "What form should it take?",
            "mode": "single",
            "allowCustomInput": True,
            "required": True,
            "options": [
                {
                    "id": "desktop_device",
                    "label": "Desktop device",
                    "value": "desktop_device",
                },
                {
                    "id": "recommended",
                    "label": "Use recommendation",
                    "value": "recommended",
                    "recommended": True,
                },
                {
                    "id": "custom",
                    "label": "Other",
                    "value": "custom",
                },
            ],
        },
    }
