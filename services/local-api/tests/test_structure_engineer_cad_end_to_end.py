from __future__ import annotations

import asyncio
from hashlib import sha256
import json
import sqlite3

from fastapi.testclient import TestClient

from zhangwen.cad_agent import router as cad_router
from zhangwen.cad_agent.coordinator import CadJobCoordinator
from zhangwen.cad_agent.intake import (
    CAD_COMPONENT_MODE_QUESTION_ID,
    CAD_LOOSE_STORAGE_OPTION_ID,
)
from zhangwen.cad_agent.repository import CadRepository
from zhangwen.chat import router as chat_router
from zhangwen.config import settings
from zhangwen.main import app
from zhangwen.projects.models import ExpertType
from zhangwen.projects.repository import ProjectRepository
from tests.fakes import FakeCredentialStore, SequenceProvider


TOKEN = "structure-cad-e2e-token"
DESKTOP_HEADERS = {
    "X-Zhangwen-Host": "tauri",
    "X-Zhangwen-Capability-Token": TOKEN,
}


def test_structure_chat_builds_real_reviewable_cad_artifact(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setenv("ZHANGWEN_DESKTOP_CAPABILITY_TOKEN", TOKEN)
    projects = ProjectRepository(tmp_path)
    workspace = projects.create_project_from_idea(
        idea="生成一个可打印的带盖控制盒",
        project_name="结构工程师真实 CAD",
        initial_expert=ExpertType.STRUCTURE_ENGINEER,
        participating_experts=[ExpertType.STRUCTURE_ENGINEER],
    )
    provider = SequenceProvider(
        [
            json.dumps(
                {
                    "content": "已整理确定性盒体草稿，尺寸交由本地结构内核求解。",
                    "cadDraft": {
                        "templateKind": "BOX_WITH_LID",
                        "parameters": {},
                        "components": [],
                        "constraints": {
                            "process": "FDM",
                            "minWallThicknessMm": 1.6,
                        },
                        "summary": "自动尺寸带盖控制盒",
                        "requestedOutputs": [
                            "STEP_ASSEMBLY",
                            "STEP_PRINTABLE_PARTS",
                            "STL_PRINTABLE_PARTS",
                            "GLB_PREVIEW",
                        ],
                    },
                },
                ensure_ascii=False,
            )
        ]
    )
    monkeypatch.setattr(chat_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(chat_router, "provider_factory", lambda: provider)
    client = TestClient(app)

    clarification = client.post(
        f"/api/projects/{workspace.project.id}/chat/stream",
        json={"content": "请生成结构外壳", "model": "deepseek-v4-flash"},
    )

    assert clarification.status_code == 200
    assert provider.calls == 1
    with projects._connect() as conn:
        source = conn.execute(
            """
            SELECT id, conversation_id, structured_payload_json
            FROM messages
            WHERE project_id = ? AND role = 'assistant' AND status = 'COMPLETED'
            ORDER BY created_at DESC LIMIT 1
            """,
            (workspace.project.id,),
        ).fetchone()
    payload = json.loads(source["structured_payload_json"])
    assert payload["type"] == "clarification"
    answers = {
        "type": "clarification_batch_answer",
        "projectId": workspace.project.id,
        "conversationId": source["conversation_id"],
        "sourceMessageId": source["id"],
        "clientTurnId": "structure-cad-intake",
        "answers": [
            {
                "questionId": CAD_COMPONENT_MODE_QUESTION_ID,
                "selectedOptionIds": [CAD_LOOSE_STORAGE_OPTION_ID],
            },
        ],
    }
    response = client.post(
        f"/api/projects/{workspace.project.id}/chat/stream",
        json={
            "content": "已确认松散存放，内腔 80 x 50 x 28 mm，请生成。",
            "model": "deepseek-v4-flash",
            "projectExpertId": workspace.experts[0].id,
            "threadId": source["conversation_id"],
            "sourceMessageId": source["id"],
            "clientTurnId": "structure-cad-intake",
            "structuredAnswer": answers,
            "turnContext": {
                "projectId": workspace.project.id,
                "conversationId": source["conversation_id"],
                "threadId": source["conversation_id"],
                "expertType": "structure_engineer",
                "turnId": "structure-cad-intake",
                "currentStage": "IDEA",
                "currentIntent": "answer_question",
            },
        },
    )
    assert response.status_code == 200
    assert provider.calls == 2
    repository = CadRepository(projects.db_path)
    draft = repository.get_current_cad(workspace.project.id)
    assert draft is not None
    assert draft.status.value == "DRAFT"
    assert draft.sourceMessageId is not None

    class DeferredCoordinator:
        def submit(self, job):
            return job

    async def deferred_coordinator():
        return DeferredCoordinator()

    monkeypatch.setattr(cad_router, "ensure_cad_coordinator", deferred_coordinator)
    queued = client.post(
        f"/api/projects/{workspace.project.id}/cad/jobs",
        json={"cadRunId": draft.id, "clientRequestId": "structure-cad-e2e"},
        headers=DESKTOP_HEADERS,
    )
    assert queued.status_code == 200, queued.text
    job = queued.json()["cadJob"]
    assert job["request"]["sizingEvidence"] == {
        "mode": "EXPLICIT",
        "requiredParameters": {"width": 80.0, "height": 28.0, "depth": 50.0},
        "autoResolvedParameters": [],
    }

    asyncio.run(CadJobCoordinator(projects.db_path, tmp_path)._execute(job["id"]))
    completed = client.get(
        f"/api/projects/{workspace.project.id}/cad/jobs/{job['id']}"
    ).json()["cadJob"]
    assert completed["status"] == "SUCCEEDED", completed.get("error")

    ready = client.get(
        f"/api/projects/{workspace.project.id}/cad/runs/{draft.id}"
    ).json()["cadRun"]
    assert ready["status"] == "READY_FOR_REVIEW"
    assert ready["validation"]["ok"] is True
    assert {item["fileName"] for item in ready["files"]} == {
        "assembly.step",
        "base.step",
        "base.stl",
        "geometry-summary.json",
        "lid.step",
        "lid.stl",
        "manifest.json",
        "parameters.json",
        "preview.glb",
        "profiles.json",
        "validation.json",
    }
    glb = next(item for item in ready["files"] if item["role"] == "GLB_PREVIEW")
    downloaded = client.get(
        f"/api/projects/{workspace.project.id}/artifacts/{ready['artifactId']}/versions/"
        f"{ready['artifactVersionId']}/files/{glb['artifactFileId']}",
        headers=DESKTOP_HEADERS,
    )
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.content[:4] == b"glTF"
    assert sha256(downloaded.content).hexdigest() == glb["sha256"]

    confirmed = client.post(
        f"/api/projects/{workspace.project.id}/cad/confirm",
        json={"cadRunId": draft.id},
        headers=DESKTOP_HEADERS,
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["cadRun"]["status"] == "APPROVED"

    with projects._connect() as conn:
        message_payload = conn.execute(
            "SELECT structured_payload_json FROM messages WHERE id = ?",
            (draft.sourceMessageId,),
        ).fetchone()[0]
    assert json.loads(message_payload)["status"] == "APPROVED"


def test_solution_draft_cad_routes_to_expert_runtime_and_applies_dimension_revision(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    projects = ProjectRepository(tmp_path)
    workspace = projects.create_project_from_idea(
        idea="为控制器生成保护壳",
        project_name="方案阶段 CAD 路由",
        initial_expert=ExpertType.STRUCTURE_ENGINEER,
        participating_experts=[ExpertType.STRUCTURE_ENGINEER],
    )
    expert = workspace.experts[0]
    with sqlite3.connect(projects.db_path) as conn:
        conn.execute(
            "UPDATE projects SET stage = 'SOLUTION_DRAFT' WHERE id = ?",
            (workspace.project.id,),
        )

    async def unexpected_idea_flow(**_kwargs):
        raise AssertionError("structure CAD must not enter project idea_flow")

    provider = SequenceProvider(
        [json.dumps({"content": "服务端应规范化此回复。"}, ensure_ascii=False)]
    )
    monkeypatch.setattr(chat_router, "handle_project_conversation", unexpected_idea_flow)
    monkeypatch.setattr(chat_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(chat_router, "provider_factory", lambda: provider)
    client = TestClient(app)

    def latest_completed_assistant() -> tuple[str, str, dict[str, object]]:
        with sqlite3.connect(projects.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT id, conversation_id, structured_payload_json
                FROM messages
                WHERE project_id = ? AND role = 'assistant' AND status = 'COMPLETED'
                ORDER BY created_at DESC, rowid DESC
                LIMIT 1
                """,
                (workspace.project.id,),
            ).fetchone()
        assert row is not None
        assert row["structured_payload_json"] is not None
        return (
            str(row["id"]),
            str(row["conversation_id"]),
            json.loads(str(row["structured_payload_json"])),
        )

    def submit_intake(
        *,
        source_message_id: str,
        conversation_id: str,
        dimensions: str,
        client_turn_id: str,
    ):
        structured_answer = {
            "type": "clarification_batch_answer",
            "projectId": workspace.project.id,
            "conversationId": conversation_id,
            "sourceMessageId": source_message_id,
            "clientTurnId": client_turn_id,
            "answers": [
                {
                    "questionId": CAD_COMPONENT_MODE_QUESTION_ID,
                    "selectedOptionIds": [CAD_LOOSE_STORAGE_OPTION_ID],
                },
            ],
        }
        return client.post(
            f"/api/projects/{workspace.project.id}/chat/stream",
            json={
                "content": f"已确认松散存放，内腔 {dimensions}，请生成。",
                "model": "deepseek-v4-flash",
                "projectExpertId": expert.id,
                "threadId": conversation_id,
                "sourceMessageId": source_message_id,
                "clientTurnId": client_turn_id,
                "structuredAnswer": structured_answer,
                "turnContext": {
                    "projectId": workspace.project.id,
                    "conversationId": conversation_id,
                    "threadId": conversation_id,
                    "expertType": "structure_engineer",
                    "turnId": client_turn_id,
                    "currentStage": "SOLUTION_DRAFT",
                    "currentIntent": "answer_question",
                },
            },
        )

    first = client.post(
        f"/api/projects/{workspace.project.id}/chat/stream",
        json={
            "content": "请为控制器生成保护壳 3D 模型",
            "model": "deepseek-v4-flash",
            "projectExpertId": expert.id,
            "threadId": expert.conversationId,
        },
    )

    assert first.status_code == 200
    first_source_id, conversation_id, first_payload = latest_completed_assistant()
    assert first_payload["type"] == "clarification"
    assert {question["id"] for question in first_payload["questions"]} == {
        CAD_COMPONENT_MODE_QUESTION_ID,
    }
    with sqlite3.connect(projects.db_path) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM expert_runs WHERE project_id = ?",
            (workspace.project.id,),
        ).fetchone()[0] == 1

    initial_answer = submit_intake(
        source_message_id=first_source_id,
        conversation_id=conversation_id,
        dimensions="80 x 50 x 28 mm",
        client_turn_id="solution_stage_cad_initial",
    )
    assert initial_answer.status_code == 200
    initial_draft = CadRepository(projects.db_path).get_current_cad(workspace.project.id)
    assert initial_draft is not None
    assert initial_draft.designState["parameters"] == {
        "width": 80.0,
        "depth": 50.0,
        "height": 28.0,
    }

    revision = client.post(
        f"/api/projects/{workspace.project.id}/chat/stream",
        json={
            "content": "把保护壳内腔尺寸改成 120 x 80 x 40 mm",
            "model": "deepseek-v4-flash",
            "projectExpertId": expert.id,
            "threadId": conversation_id,
        },
    )
    assert revision.status_code == 200
    _, _, revision_payload = latest_completed_assistant()
    assert revision_payload["type"] == "cad_artifact"
    revised_draft = CadRepository(projects.db_path).get_current_cad(workspace.project.id)
    assert revised_draft is not None
    assert revised_draft.id != initial_draft.id
    assert revised_draft.designState["parameters"] == {
        "width": 120.0,
        "depth": 80.0,
        "height": 40.0,
    }
    assert provider.calls == 3
    with sqlite3.connect(projects.db_path) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM expert_runs WHERE project_id = ?",
            (workspace.project.id,),
        ).fetchone()[0] == 3
        assert conn.execute(
            "SELECT COUNT(*) FROM cad_runs WHERE project_id = ?",
            (workspace.project.id,),
        ).fetchone()[0] == 2
