"""Agent Skill package loading, editing, and runtime prompt tests."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from zhangwen.config import settings
from zhangwen.experts.config import load_expert_prompt
from zhangwen.experts.runtime import ExpertRuntime, ExpertRuntimeRequest
from zhangwen.experts.packages import (
    BUNDLED_AGENT_PACKAGE_DIR,
    AgentPackageRepository,
)
from zhangwen.main import app
from zhangwen.llm.contracts import LLMConfig, LLMModelId, StreamChunk, StreamChunkType
from zhangwen.projects.migrations import CURRENT_SCHEMA_VERSION
from zhangwen.projects.models import ExpertType
from zhangwen.projects.repository import ProjectRepository


def test_bundled_agent_packages_have_skill_entry_and_declared_references(
    tmp_path: Path,
) -> None:
    packages = AgentPackageRepository(tmp_path).list_packages()

    assert [package.expertType for package in packages] == [
        ExpertType.PROBLEM_GUIDE,
        ExpertType.SMART_ENGINEER,
        ExpertType.STRUCTURE_ENGINEER,
    ]
    assert all(package.entryFile == "SKILL.md" for package in packages)
    assert all(package.validationIssues == [] for package in packages)

    smart = AgentPackageRepository(tmp_path).get_package(ExpertType.SMART_ENGINEER)
    assert smart.displayName == "智能工程师"
    assert smart.description
    assert smart.revision
    assert [file.path for file in smart.files][0] == "SKILL.md"
    assert any(file.path.startswith("references/") for file in smart.files)
    assert all(not Path(file.path).is_absolute() for file in smart.files)
    assert "hardware-selection" in smart.skillIds


def test_agent_package_file_update_is_atomic_persistent_and_resettable(
    tmp_path: Path,
) -> None:
    repository = AgentPackageRepository(tmp_path)
    original = repository.get_package(ExpertType.SMART_ENGINEER)
    entry = next(file for file in original.files if file.path == "SKILL.md")
    marker = "下一次回复必须先列出工程假设。"
    content = f"{entry.content.rstrip()}\n\n- {marker}\n"

    updated = repository.update_file(
        ExpertType.SMART_ENGINEER,
        path="SKILL.md",
        content=content,
        expected_revision=original.revision,
    )

    assert updated.revision != original.revision
    assert marker in next(file for file in updated.files if file.path == "SKILL.md").content
    assert marker in next(
        file
        for file in AgentPackageRepository(tmp_path)
        .get_package(ExpertType.SMART_ENGINEER)
        .files
        if file.path == "SKILL.md"
    ).content
    assert marker not in (
        BUNDLED_AGENT_PACKAGE_DIR / "smart-engineer" / "SKILL.md"
    ).read_text(encoding="utf-8")

    reset = repository.reset_file(
        ExpertType.SMART_ENGINEER,
        path="SKILL.md",
        expected_revision=updated.revision,
    )
    assert reset.revision == original.revision
    assert marker not in next(file for file in reset.files if file.path == "SKILL.md").content


def test_agent_package_api_rejects_conflicts_invalid_frontmatter_and_paths(
    tmp_path: Path,
) -> None:
    settings.data_dir = tmp_path
    ProjectRepository(tmp_path)
    client = TestClient(app)
    detail = client.get("/api/agent-packages/smart_engineer")
    assert detail.status_code == 200
    package = detail.json()["package"]
    entry = next(file for file in package["files"] if file["path"] == "SKILL.md")

    valid_content = entry["content"] + "\n\n- 输出前复核约束。\n"
    saved = client.put(
        "/api/agent-packages/smart_engineer/files",
        json={
            "path": "SKILL.md",
            "content": valid_content,
            "expectedRevision": package["revision"],
        },
    )
    assert saved.status_code == 200

    conflict = client.put(
        "/api/agent-packages/smart_engineer/files",
        json={
            "path": "SKILL.md",
            "content": valid_content + "\n- 冲突写入。\n",
            "expectedRevision": package["revision"],
        },
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "AGENT_PACKAGE_REVISION_CONFLICT"

    bad_name = valid_content.replace("name: smart-engineer", "name: other-agent", 1)
    invalid = client.put(
        "/api/agent-packages/smart_engineer/files",
        json={
            "path": "SKILL.md",
            "content": bad_name,
            "expectedRevision": saved.json()["package"]["revision"],
        },
    )
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["code"] == "AGENT_PACKAGE_INVALID"

    traversal = client.put(
        "/api/agent-packages/smart_engineer/files",
        json={
            "path": "../SKILL.md",
            "content": valid_content,
            "expectedRevision": saved.json()["package"]["revision"],
        },
    )
    assert traversal.status_code == 422
    assert traversal.json()["detail"]["code"] == "AGENT_PACKAGE_INVALID"


def test_effective_agent_package_changes_only_target_runtime_prompt(
    tmp_path: Path,
) -> None:
    settings.data_dir = tmp_path
    ProjectRepository(tmp_path)
    repository = AgentPackageRepository(tmp_path)
    smart = repository.get_package(ExpertType.SMART_ENGINEER)
    entry = next(file for file in smart.files if file.path == "SKILL.md")
    reference = next(
        file for file in smart.files if file.path == "references/ENGINEERING_RULES.md"
    )
    entry_marker = "SMART_ENTRY_PACKAGE_MARKER"
    reference_marker = "SMART_REFERENCE_PACKAGE_MARKER"
    smart = repository.update_file(
        ExpertType.SMART_ENGINEER,
        path=entry.path,
        content=f"{entry.content.rstrip()}\n\n{entry_marker}\n",
        expected_revision=smart.revision,
    )
    repository.update_file(
        ExpertType.SMART_ENGINEER,
        path=reference.path,
        content=f"{reference.content.rstrip()}\n\n{reference_marker}\n",
        expected_revision=smart.revision,
    )

    smart_prompt = load_expert_prompt(
        ExpertType.SMART_ENGINEER,
        user_message="请检查 ESP32 接线和供电",
        data_dir=tmp_path,
    )
    guide_prompt = load_expert_prompt(
        ExpertType.PROBLEM_GUIDE,
        user_message="请检查 ESP32 接线和供电",
        data_dir=tmp_path,
    )

    assert entry_marker in smart_prompt
    assert reference_marker in smart_prompt
    assert "hardware-selection" in smart_prompt
    assert entry_marker not in guide_prompt
    assert reference_marker not in guide_prompt


def test_agent_package_overlay_does_not_change_schema_version(tmp_path: Path) -> None:
    project_repository = ProjectRepository(tmp_path)
    package_repository = AgentPackageRepository(tmp_path)
    package = package_repository.get_package(ExpertType.PROBLEM_GUIDE)
    entry = next(file for file in package.files if file.path == "SKILL.md")
    package_repository.update_file(
        ExpertType.PROBLEM_GUIDE,
        path=entry.path,
        content=f"{entry.content.rstrip()}\n\n- 保持项目事实可追溯。\n",
        expected_revision=package.revision,
    )

    with sqlite3.connect(project_repository.db_path) as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
    assert version == CURRENT_SCHEMA_VERSION == 31


def test_workspace_expert_definitions_use_complete_package_manifest(tmp_path: Path) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="做一个带外壳的 ESP32 传感器",
        project_name="Agent package definitions",
        initial_expert=ExpertType.PROBLEM_GUIDE,
        participating_experts=[
            ExpertType.PROBLEM_GUIDE,
            ExpertType.SMART_ENGINEER,
            ExpertType.STRUCTURE_ENGINEER,
        ],
    )
    definitions = {definition.type: definition for definition in workspace.expertDefinitions}

    assert len(definitions[ExpertType.PROBLEM_GUIDE].skillIds) == 7
    assert len(definitions[ExpertType.SMART_ENGINEER].skillIds) == 16
    assert len(definitions[ExpertType.STRUCTURE_ENGINEER].skillIds) == 11
    assert "print-profile" in definitions[ExpertType.STRUCTURE_ENGINEER].skillIds


class _RecordingAgentProvider:
    def __init__(self) -> None:
        self.requests: list[object] = []

    async def stream_chat(
        self,
        request,
        config,
        api_key,
        cancel_token,
        request_id,
        message_id,
    ):
        self.requests.append(request)
        yield StreamChunk(
            requestId=request_id,
            messageId=message_id,
            type=StreamChunkType.COMPLETED,
            accumulatedContent=json.dumps({"content": "已检查工程约束。"}, ensure_ascii=False),
            model=LLMModelId.DEEPSEEK_V4_FLASH,
        )


@pytest.mark.asyncio
async def test_expert_runtime_uses_effective_agent_skill_package(tmp_path: Path) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="ESP32 接线测试",
        project_name="Agent package runtime",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
    )
    expert = next(
        expert
        for expert in workspace.experts
        if expert.expertType == ExpertType.SMART_ENGINEER
    )
    packages = AgentPackageRepository(tmp_path)
    package = packages.get_package(ExpertType.SMART_ENGINEER)
    entry = next(file for file in package.files if file.path == "SKILL.md")
    marker = "RUNTIME_AGENT_PACKAGE_MARKER"
    packages.update_file(
        ExpertType.SMART_ENGINEER,
        path=entry.path,
        content=f"{entry.content.rstrip()}\n\n{marker}\n",
        expected_revision=package.revision,
    )
    provider = _RecordingAgentProvider()

    await ExpertRuntime(repository.db_path).run(
        request=ExpertRuntimeRequest(
            projectId=workspace.project.id,
            projectExpertId=expert.id,
            conversationId=expert.conversationId,
            expertType=ExpertType.SMART_ENGINEER,
            userMessage="请检查 ESP32 接线",
            model=LLMModelId.DEEPSEEK_V4_FLASH,
        ),
        provider=provider,
        config=LLMConfig(),
        api_key="fake-test-key",
    )

    assert marker in provider.requests[0].messages[0].content
    assert "工程实现规则" in provider.requests[0].messages[0].content


@pytest.mark.asyncio
async def test_expert_runtime_sends_validated_k10_board_skill_to_provider(
    tmp_path: Path,
) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="用行空板 K10 在屏幕显示环境数据",
        project_name="K10 board skill runtime",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
    )
    expert = next(
        expert
        for expert in workspace.experts
        if expert.expertType == ExpertType.SMART_ENGINEER
    )
    provider = _RecordingAgentProvider()

    await ExpertRuntime(repository.db_path).run(
        request=ExpertRuntimeRequest(
            projectId=workspace.project.id,
            projectExpertId=expert.id,
            conversationId=expert.conversationId,
            expertType=ExpertType.SMART_ENGINEER,
            userMessage="现在生成屏幕代码。",
            model=LLMModelId.DEEPSEEK_V4_FLASH,
        ),
        provider=provider,
        config=LLMConfig(),
        api_key="fake-test-key",
    )

    request_payload = "\n".join(
        message.content for message in provider.requests[0].messages
    )
    assert '"boardSkill"' in request_payload
    assert "unihiker-k10-micropython-engineer" in request_payload
    assert "references/03-screen-api.md" in request_payload
    assert "templates/01_screen_shapes.py" in request_payload
    assert '"profileId": "unihiker-k10"' in request_payload


def test_micropython_board_skill_template_loads_facts_from_board_profile() -> None:
    template_root = (
        Path(__file__).parents[1]
        / "zhangwen"
        / "experts"
        / "skill-templates"
        / "micropython-board-project"
    )
    skill = (template_root / "SKILL.md").read_text(encoding="utf-8")
    board_reference = (template_root / "references" / "BOARD_PROFILE.md").read_text(
        encoding="utf-8"
    )
    validation_reference = (
        template_root / "references" / "VALIDATION.md"
    ).read_text(encoding="utf-8")

    assert skill.startswith("---\nname: micropython-board-project\n")
    assert "references/BOARD_PROFILE.md" in skill
    assert "references/VALIDATION.md" in skill
    assert "BoardProfile" in board_reference
    assert "exit code `0`" in validation_reference
    combined = "\n".join((skill, board_reference, validation_reference)).lower()
    assert "unihiker-k10" not in combined
    assert "esp32-s3 n16r8" not in combined
