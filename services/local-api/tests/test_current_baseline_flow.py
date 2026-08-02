"""Acceptance test for the frozen ZW-STABILIZE-001 minimum product flow."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from zhangwen.artifacts.repository import ArtifactRepository
from zhangwen.chat import router as chat_router
from zhangwen.config import settings
from zhangwen.main import app
from zhangwen.projects.models import ExpertType, ProjectStage
from zhangwen.projects.repository import ProjectRepository
from tests.fakes import FakeCredentialStore, StructuredFakeProvider


def test_problem_guide_automatically_generates_solution_when_information_is_complete(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(chat_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(chat_router, "provider_factory", StructuredFakeProvider)
    client = TestClient(app)
    created = client.post(
        "/api/projects",
        json={
            "name": "自动收口方案",
            "initialIdea": "做一个自动浇花装置",
            "initialExpert": ExpertType.PROBLEM_GUIDE.value,
            "selectedExpertTypes": [ExpertType.PROBLEM_GUIDE.value],
            "routerResult": {
                "intent": "clarify_project_idea",
                "projectName": "自动收口方案",
                "initialExpert": ExpertType.PROBLEM_GUIDE.value,
                "recommendedExperts": [ExpertType.PROBLEM_GUIDE.value],
                "confidence": 1,
                "reason": "测试固定路由。",
                "requiresClarification": True,
            },
        },
    ).json()["workspace"]
    project_id = created["project"]["id"]
    guide = created["experts"][0]

    response = client.post(
        f"/api/projects/{project_id}/chat/stream",
        json={
            "content": "AUTO_COMPLETE_CREATOR_GUIDE",
            "projectExpertId": guide["id"],
            "expertType": ExpertType.PROBLEM_GUIDE.value,
            "clientTurnId": "automatic-solution-after-clarification",
        },
    )

    assert response.status_code == 200
    chunk = _completed_chunks(response.text)[-1]
    card = chunk["structuredPayload"]
    assert card["type"] == "solution_card"
    assert "创意与方案" in chunk["accumulatedContent"]
    assert {
        action["action"] for action in card["actions"]
    }.isdisjoint(
        {
            "generate_solution",
            "continue_clarification",
            "confirm_solution",
            "accept_solution_revision",
            "generate_project_proposal",
            "generate_lesson_version",
        }
    )
    creator = client.get(f"/api/creator/works/{project_id}").json()["workspace"]
    assert creator["draftGoal"]["observableBehavior"] == "干燥时启动水泵，湿润后停止"
    assert creator["draftSolution"] is not None


def test_minimum_three_teacher_flow_survives_repository_restart(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(chat_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(chat_router, "provider_factory", StructuredFakeProvider)
    client = TestClient(app)

    create_response = client.post(
        "/api/projects",
        json={
            "name": "自动浇花基线项目",
            "initialIdea": "做一个自动浇花装置",
            "initialExpert": ExpertType.PROBLEM_GUIDE.value,
            "selectedExpertTypes": [
                ExpertType.PROBLEM_GUIDE.value,
                ExpertType.SMART_ENGINEER.value,
            ],
            "routerResult": {
                "intent": "clarify_project_idea",
                "projectName": "自动浇花基线项目",
                "initialExpert": ExpertType.PROBLEM_GUIDE.value,
                "recommendedExperts": [
                    ExpertType.PROBLEM_GUIDE.value,
                    ExpertType.SMART_ENGINEER.value,
                ],
                "confidence": 1,
                "reason": "稳定化验收使用已验证路由结果，不调用真实 Provider。",
                "requiresClarification": True,
            },
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()["workspace"]
    project_id = created["project"]["id"]
    experts = {expert["expertType"]: expert for expert in created["experts"]}
    guide = experts[ExpertType.PROBLEM_GUIDE.value]
    engineer = experts[ExpertType.SMART_ENGINEER.value]
    assert created["project"]["activeExpertId"] == guide["id"]
    assert guide["conversationId"] != engineer["conversationId"]

    clarification = client.post(
        f"/api/projects/{project_id}/chat/stream",
        json={
            "content": "请先帮我梳理自动浇花装置的关键需求",
            "projectExpertId": guide["id"],
            "expertType": ExpertType.PROBLEM_GUIDE.value,
            "clientTurnId": "baseline_clarification",
        },
    )
    assert clarification.status_code == 200
    clarification_chunks = _completed_chunks(clarification.text)
    assert clarification_chunks[-1]["structuredPayload"]["type"] == "clarification"

    generated = client.post(
        f"/api/projects/{project_id}/chat/stream",
        json={
            "content": "生成推荐实现方案",
            "projectExpertId": guide["id"],
            "expertType": ExpertType.PROBLEM_GUIDE.value,
            "clientTurnId": "baseline_generate_solution",
            "conversationAction": "generate_solution",
        },
    )
    assert generated.status_code == 200
    solution_card = _completed_chunks(generated.text)[-1]["structuredPayload"]
    assert solution_card["type"] == "solution_card"
    assert solution_card["version"] == 1
    assert solution_card["artifactId"]
    assert solution_card["artifactVersionId"]
    assert {
        action["action"] for action in solution_card["actions"]
    }.isdisjoint(
        {
            "confirm_solution",
            "generate_project_proposal",
            "generate_lesson_version",
        }
    )

    confirmed = client.post(
        f"/api/projects/{project_id}/chat/stream",
        json={
            "content": "确认方案",
            "projectExpertId": guide["id"],
            "expertType": ExpertType.PROBLEM_GUIDE.value,
            "clientTurnId": "baseline_confirm_solution",
            "conversationAction": "confirm_solution",
        },
    )
    assert confirmed.status_code == 200
    confirmed_card = _completed_chunks(confirmed.text)[-1]["structuredPayload"]
    assert confirmed_card["type"] == "solution_card"
    assert {
        action["action"] for action in confirmed_card["actions"]
    }.isdisjoint({"generate_project_proposal", "generate_lesson_version"})

    generated_proposal = client.post(
        f"/api/projects/{project_id}/chat/stream",
        json={
            "content": "生成立项书",
            "projectExpertId": guide["id"],
            "expertType": ExpertType.PROBLEM_GUIDE.value,
            "clientTurnId": "baseline_generate_project_book",
            "conversationAction": "generate_project_proposal",
        },
    )
    assert generated_proposal.status_code == 200
    proposal_card = _completed_chunks(generated_proposal.text)[-1]["structuredPayload"]
    assert proposal_card["type"] == "proposal_action"
    assert proposal_card["proposalId"]
    assert proposal_card["proposalVersion"] == 1
    assert any(action["action"] == "confirm_project_proposal" for action in proposal_card["actions"])

    current_solution = client.get(
        f"/api/projects/{project_id}/solution/current"
    ).json()["solution"]
    assert current_solution["status"] == "CONFIRMED"
    assert current_solution["artifactId"] == solution_card["artifactId"]
    assert current_solution["artifactVersionId"] == solution_card["artifactVersionId"]

    artifact_response = client.get(
        f"/api/projects/{project_id}/artifacts/{current_solution['artifactId']}"
    )
    assert artifact_response.status_code == 200
    artifact = artifact_response.json()["artifact"]
    assert artifact["currentVersionId"] == current_solution["artifactVersionId"]
    artifact_version = next(
        version
        for version in artifact["versions"]
        if version["id"] == artifact["currentVersionId"]
    )
    assert artifact_version["version"] == current_solution["version"]
    assert artifact_version["sourceEntityId"] == current_solution["id"]

    project_draft = "项目共享输入草稿"
    assert client.put(
        f"/api/projects/{project_id}/draft",
        json={"content": project_draft},
    ).status_code == 200
    activated = client.post(
        f"/api/projects/{project_id}/experts/{engineer['id']}/activate"
    )
    assert activated.status_code == 200
    assert activated.json()["workspace"]["conversation"]["id"] == engineer["conversationId"]
    assert activated.json()["workspace"]["draft"]["content"] == project_draft

    restarted_repository = ProjectRepository(tmp_path)
    restored = restarted_repository.get_workspace(project_id)
    restored_conversations = {
        conversation.expertType: conversation
        for conversation in restored.expertConversations
        if not conversation.archivedLegacyThread
    }
    assert restored.project.stage == ProjectStage.PROPOSAL_DRAFT
    assert restored.project.activeExpertId == engineer["id"]
    assert restored.conversation.id == engineer["conversationId"]
    assert restored.draft.content == project_draft
    assert any(
        message.content == "请先帮我梳理自动浇花装置的关键需求"
        for message in restored_conversations[ExpertType.PROBLEM_GUIDE].messages
    )
    assert all(
        message.content != "请先帮我梳理自动浇花装置的关键需求"
        for message in restored_conversations[ExpertType.SMART_ENGINEER].messages
    )

    restored_artifact = ArtifactRepository(restarted_repository.db_path).get_artifact(
        project_id,
        current_solution["artifactId"],
    )
    assert restored_artifact.currentVersionId == current_solution["artifactVersionId"]


def test_problem_guide_lesson_choice_persists_track_and_generates_baseline(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(chat_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(chat_router, "provider_factory", StructuredFakeProvider)
    client = TestClient(app)

    created = client.post(
        "/api/projects",
        json={
            "name": "课堂环境监测",
            "initialIdea": "用行空板 K10 做课堂环境监测教案",
            "initialExpert": ExpertType.PROBLEM_GUIDE.value,
            "selectedExpertTypes": [ExpertType.PROBLEM_GUIDE.value],
            "routerResult": {
                "intent": "clarify_project_idea",
                "projectName": "课堂环境监测",
                "initialExpert": ExpertType.PROBLEM_GUIDE.value,
                "recommendedExperts": [ExpertType.PROBLEM_GUIDE.value],
                "confidence": 1,
                "reason": "测试固定路由，不调用真实 Provider。",
                "requiresClarification": False,
            },
        },
    ).json()["workspace"]
    project_id = created["project"]["id"]
    guide = created["experts"][0]

    generated = client.post(
        f"/api/projects/{project_id}/chat/stream",
        json={
            "content": "生成推荐实现方案",
            "projectExpertId": guide["id"],
            "expertType": ExpertType.PROBLEM_GUIDE.value,
            "clientTurnId": "lesson_track_solution",
            "conversationAction": "generate_solution",
        },
    )
    assert generated.status_code == 200
    solution_card = _completed_chunks(generated.text)[-1]["structuredPayload"]
    assert {
        action["action"] for action in solution_card["actions"]
    }.isdisjoint(
        {
            "confirm_solution",
            "generate_project_proposal",
            "generate_lesson_version",
        }
    )

    confirmed_solution = client.post(
        f"/api/projects/{project_id}/chat/stream",
        json={
            "content": "确认方案",
            "projectExpertId": guide["id"],
            "expertType": ExpertType.PROBLEM_GUIDE.value,
            "clientTurnId": "lesson_track_confirm_solution",
            "conversationAction": "confirm_solution",
        },
    )
    confirmed_card = _completed_chunks(confirmed_solution.text)[-1]["structuredPayload"]
    assert {
        action["action"] for action in confirmed_card["actions"]
    }.isdisjoint({"generate_project_proposal", "generate_lesson_version"})

    lesson_choice = client.post(
        f"/api/projects/{project_id}/chat/stream",
        json={
            "content": "生成教案版本",
            "projectExpertId": guide["id"],
            "expertType": ExpertType.PROBLEM_GUIDE.value,
            "clientTurnId": "lesson_track_choose",
            "conversationAction": "generate_lesson_version",
        },
    )
    assert lesson_choice.status_code == 200
    completed = _completed_chunks(lesson_choice.text)[-1]
    assert "已选择教案版本" in completed["accumulatedContent"]
    assert completed["structuredPayload"]["proposalId"]
    assert any(
        action["label"] == "确认教学实施基线"
        for action in completed["structuredPayload"]["actions"]
    )

    confirmed_baseline = client.post(
        f"/api/projects/{project_id}/chat/stream",
        json={
            "content": "确认教学实施基线",
            "projectExpertId": guide["id"],
            "expertType": ExpertType.PROBLEM_GUIDE.value,
            "clientTurnId": "lesson_track_confirm_baseline",
            "conversationAction": "confirm_project_proposal",
        },
    )
    assert confirmed_baseline.status_code == 200
    confirmed_chunk = _completed_chunks(confirmed_baseline.text)[-1]
    confirmed_content = confirmed_chunk["accumulatedContent"]
    assert "正在交接给智能工程师" in confirmed_content
    assert confirmed_chunk["structuredPayload"]["handoff"] == {
        "automatic": True,
        "targetExpert": ExpertType.SMART_ENGINEER.value,
        "label": "已交接给智能工程师",
        "prompt": "立项书已确认，请基于当前已确认立项书直接开始项目实现。",
    }
    current_spec = client.get(f"/api/projects/{project_id}/spec/current")
    assert current_spec.status_code == 404

    repository = ProjectRepository(tmp_path)
    assert repository.get_delivery_track(project_id) == "lesson"
    restored = repository.get_workspace(project_id)
    assert restored.sharedContext.deliveryTrack == "lesson"


def _completed_chunks(stream_text: str) -> list[dict[str, object]]:
    chunks: list[dict[str, object]] = []
    for line in stream_text.splitlines():
        if not line.startswith("data: "):
            continue
        chunk = json.loads(line.removeprefix("data: "))
        if chunk.get("type") == "COMPLETED":
            chunks.append(chunk)
    assert chunks
    return chunks
