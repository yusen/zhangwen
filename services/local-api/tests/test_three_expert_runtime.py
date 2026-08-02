"""Tests for three-teacher runtime, routing, and context isolation."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from zhangwen.experts.config import (
    PROBLEM_GUIDE_SKILLS,
    SMART_ENGINEER_SKILLS,
    STRUCTURE_ENGINEER_SKILLS,
    get_expert_config,
    list_expert_configs,
    load_expert_prompt,
)
from zhangwen.experts.context_assembler import ContextAssembler, ContextAssemblyInput
from zhangwen.experts.runtime import ExpertRuntime, ExpertRuntimeOutput
from zhangwen.hardware.board_profiles import BoardProfileRepository
from zhangwen.hardware.repository import HardwareRepository
from zhangwen.hardware.seeds import seed_default_components
from zhangwen.orchestrator.registry import AgentRegistry
from zhangwen.projects.models import ExpertType
from zhangwen.projects.repository import ProjectRepository
from zhangwen.skills.models import SkillConfirmationPolicy, SkillRiskLevel
from zhangwen.skills.registry import built_in_skills


def test_formal_project_code_draft_no_longer_requires_spec_binding(
    tmp_path: Path,
) -> None:
    runtime = ExpertRuntime(tmp_path / "formal-spec-gate.sqlite3")
    output = ExpertRuntimeOutput.model_validate(
        {
            "content": "代码草稿已生成。",
            "codeDraft": {
                "files": [
                    {
                        "path": "src/main.py",
                        "language": "python",
                        "content": "print('formal project')\n",
                    }
                ],
                "summary": "正式工程代码草稿",
            },
        }
    )

    runtime._validate_boundaries(
        ExpertType.SMART_ENGINEER,
        output,
    )


def test_three_expert_configs_have_independent_prompts_and_boundaries() -> None:
    configs = list_expert_configs()

    assert [config.id for config in configs] == [
        ExpertType.PROBLEM_GUIDE,
        ExpertType.SMART_ENGINEER,
        ExpertType.STRUCTURE_ENGINEER,
    ]
    for config in configs:
        prompt = load_expert_prompt(config.id)
        assert prompt.strip()
        assert config.artifactTypes
        assert config.skillIds
        assert config.capabilityBoundaries

    smart_config = get_expert_config(ExpertType.SMART_ENGINEER)
    assert set(SMART_ENGINEER_SKILLS).issubset(set(smart_config.skillIds))


def test_three_teacher_skills_are_registered_as_skills_not_agents() -> None:
    skills = {skill.id: skill for skill in built_in_skills()}

    configured_skills = {
        ExpertType.PROBLEM_GUIDE: PROBLEM_GUIDE_SKILLS,
        ExpertType.SMART_ENGINEER: SMART_ENGINEER_SKILLS,
        ExpertType.STRUCTURE_ENGINEER: STRUCTURE_ENGINEER_SKILLS,
    }
    for owner, skill_ids in configured_skills.items():
        for skill_id in skill_ids:
            assert skills[skill_id].ownerExpert == owner

    for skill_id in {
        skill_id for skill_ids in configured_skills.values() for skill_id in skill_ids
    }:
        skill = skills[skill_id]
        assert skill.inputSchema.type == "object"
        assert skill.outputSchema.type == "object"
        assert skill.riskLevel in {
            SkillRiskLevel.LOW,
            SkillRiskLevel.MEDIUM,
            SkillRiskLevel.HIGH,
        }
        assert skill.confirmationPolicy in {
            SkillConfirmationPolicy.NEVER,
            SkillConfirmationPolicy.BEFORE_EXTERNAL_EFFECT,
            SkillConfirmationPolicy.ALWAYS,
        }
        assert skill.artifactTypes

    agent_ids = {agent.id for agent in AgentRegistry().list_agents()}
    assert "smart_engineer" not in agent_ids
    assert all(set(skill_ids).isdisjoint(agent_ids) for skill_ids in configured_skills.values())


def test_context_assembler_uses_shared_state_without_chat_or_private_drafts(
    tmp_path: Path,
) -> None:
    repo = ProjectRepository(tmp_path)
    workspace = repo.create_project(
        name="Context isolation",
        initial_idea="Build an ESP32 reminder with an enclosure.",
        selected_expert_types=[
            ExpertType.PROBLEM_GUIDE,
            ExpertType.SMART_ENGINEER,
            ExpertType.STRUCTURE_ENGINEER,
        ],
    )
    project_id = workspace.project.id
    now = "2026-07-10T00:00:00+00:00"

    with sqlite3.connect(repo.db_path) as conn:
        conn.execute(
            """
            INSERT INTO project_shared_facts (
              id, project_id, field, value_json, status, source_type, source_id,
              source_expert_id, proposed_by_expert_type, confirmed_by, confirmed_at,
              superseded_by, affects_artifact_ids_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, NULL, ?, ?, ?)
            """,
            (
                "fact_confirmed_hardware",
                project_id,
                "hardware",
                json.dumps({"mcu": "ESP32"}, ensure_ascii=False),
                "confirmed",
                "user",
                "smart_engineer",
                "user",
                now,
                "[]",
                now,
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO project_shared_facts (
              id, project_id, field, value_json, status, source_type, source_id,
              source_expert_id, proposed_by_expert_type, confirmed_by, confirmed_at,
              superseded_by, affects_artifact_ids_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?, NULL, NULL, NULL, ?, ?, ?)
            """,
            (
                "fact_model_summary",
                project_id,
                "summary",
                json.dumps("model summary should be lower priority", ensure_ascii=False),
                "proposed",
                "model_summary",
                "problem_guide",
                "[]",
                now,
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO project_decisions (
              id, project_id, title, value_json, status, reason,
              proposed_by_expert_type, confirmed_by, confirmed_at,
              affected_artifact_ids_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "decision_power",
                project_id,
                "Power source",
                json.dumps({"power": "USB"}, ensure_ascii=False),
                "confirmed",
                "User selected a safe starter power source.",
                "smart_engineer",
                "user",
                now,
                "[]",
                now,
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO artifacts (
              id, project_id, title, kind, status, source_agent_id, current_version_id,
              owner_expert_id, owner_expert_type, source_conversation_id,
              shared_context_revision, legacy_owner_expert, creator_legacy_expert,
              domain_status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?, NULL, 1, NULL, NULL, ?, ?, ?)
            """,
            (
                "artifact_hardware",
                project_id,
                "Hardware plan",
                "DOCUMENT",
                "APPROVED",
                "spec-agent",
                "smart_engineer",
                "confirmed",
                now,
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO artifact_versions (
              id, artifact_id, project_id, version, status, mime_type, preview_json,
              dependencies_json, producer_task_id, source_entity_type, source_entity_id,
              checksum, stale_reason, shared_context_revision, domain_status,
              created_at, confirmed_at
            ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, NULL, NULL, NULL, ?, NULL, 1, ?, ?, ?)
            """,
            (
                "artifact_hardware_v1",
                "artifact_hardware",
                project_id,
                "APPROVED",
                "application/json",
                json.dumps(
                    {"kind": "TEXT", "summary": "Confirmed ESP32 hardware plan"},
                    ensure_ascii=False,
                ),
                "[]",
                "checksum",
                "confirmed",
                now,
                now,
            ),
        )
        conn.execute(
            "UPDATE artifacts SET current_version_id = ? WHERE id = ?",
            ("artifact_hardware_v1", "artifact_hardware"),
        )
        conn.execute(
            """
            INSERT INTO device_sessions (
              id, project_id, port_id, board, status, logs_json,
              connected_at, last_seen_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?)
            """,
            (
                "session_esp32",
                project_id,
                "mock-port",
                "ESP32",
                "DISCOVERED",
                json.dumps(["secret device log"], ensure_ascii=False),
                now,
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO messages (
              id, conversation_id, project_id, role, content, reasoning_content,
              status, model, error_json, usage_json, structured_payload_json,
              metadata_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, NULL, ?, NULL, NULL, NULL, NULL, NULL, ?, ?)
            """,
            (
                "msg_secret",
                workspace.conversation.id,
                project_id,
                "user",
                "secret chat should not be injected",
                "COMPLETED",
                now,
                now,
            ),
        )
        conn.execute(
            """
            UPDATE expert_drafts
            SET content = ?, updated_at = ?
            WHERE project_id = ?
            """,
            ("secret draft should not be injected", now, project_id),
        )

    assembled = ContextAssembler(repo.db_path).assemble(
        ContextAssemblyInput(
            projectId=project_id,
            expert=ExpertType.SMART_ENGINEER,
            userMessage="write firmware",
        )
    )
    payload = json.dumps(assembled.model_dump(mode="json"), ensure_ascii=False)

    assert assembled.relevantFacts[0]["id"] == "fact_confirmed_hardware"
    assert "fact_model_summary" in {fact["id"] for fact in assembled.relevantFacts}
    assert assembled.relevantDecisions[0]["id"] == "decision_power"
    assert assembled.upstreamArtifacts[0]["artifactId"] == "artifact_hardware"
    assert assembled.relevantDevices == [
        {
            "board": "ESP32",
            "status": "available",
            "ready": False,
            "connectedAt": None,
            "lastSeenAt": now,
        }
    ]
    assert "session_esp32" not in payload
    assert "mock-port" not in payload
    assert "sessionId" not in payload
    assert "portId" not in payload
    assert "secret chat should not be injected" not in payload
    assert "secret draft should not be injected" not in payload
    assert "secret device log" not in payload


def test_context_assembler_adds_bounded_public_hardware_knowledge(
    tmp_path: Path,
) -> None:
    repo = ProjectRepository(tmp_path)
    workspace = repo.create_project(
        name="Knowledge retrieval",
        initial_idea="Build an ESP32 temperature display.",
        selected_expert_types=[ExpertType.SMART_ENGINEER],
    )

    assembled = ContextAssembler(repo.db_path).assemble(
        ContextAssemblyInput(
            projectId=workspace.project.id,
            expert=ExpertType.SMART_ENGINEER,
            userMessage="用 ESP32-S3 读取 DHT22 温湿度，并在 OLED 上显示。",
        )
    )

    names = {item["name"] for item in assembled.publicKnowledge}
    payload = json.dumps(assembled.publicKnowledge, ensure_ascii=False)

    assert len(assembled.publicKnowledge) <= 5
    assert {
        "Seeed Studio XIAO ESP32S3 Sense",
        "DHT22 温湿度传感器",
        "0.96 OLED 显示屏",
    }.issubset(names)
    assert all(
        item["source"] in {"local_hardware_library", "markdown_board_profile"}
        for item in assembled.publicKnowledge
    )
    assert all("stock" not in item and "price" not in item for item in assembled.publicKnowledge)
    assert "zhangwen:hardware-spec:v1" in payload
    assert "createdAt" not in payload


def test_context_assembler_loads_matching_k10_markdown_board_profile(
    tmp_path: Path,
) -> None:
    repo = ProjectRepository(tmp_path)
    workspace = repo.create_project(
        name="K10 MicroPython",
        initial_idea="用行空板 K10 做环境监测。",
        selected_expert_types=[ExpertType.SMART_ENGINEER],
    )

    k10_context = ContextAssembler(repo.db_path).assemble(
        ContextAssemblyInput(
            projectId=workspace.project.id,
            expert=ExpertType.SMART_ENGINEER,
            userMessage="请用行空板 K10 的 MicroPython API 生成代码。",
        )
    )
    other_context = ContextAssembler(repo.db_path).assemble(
        ContextAssemblyInput(
            projectId=workspace.project.id,
            expert=ExpertType.SMART_ENGINEER,
            userMessage="请用 ESP32-C3 生成代码。",
        )
    )

    board_profile = next(
        item
        for item in k10_context.publicKnowledge
        if item["source"] == "markdown_board_profile"
    )
    assert board_profile["profileId"] == "unihiker-k10"
    assert "from unihiker_k10 import screen" in board_profile["markdown"]
    assert k10_context.boardSkill is not None
    assert k10_context.boardSkill["package"]["id"] == (
        "unihiker-k10-micropython-engineer"
    )
    assert k10_context.boardSkill["boardProfile"]["revision"] == board_profile["revision"]
    assert k10_context.boardSkill["templates"][0]["path"] == (
        "templates/00_profile_probe.py"
    )
    assert other_context.boardSkill is None
    assert all(
        item["source"] != "markdown_board_profile"
        for item in other_context.publicKnowledge
    )


def test_context_assembler_keeps_k10_skill_for_followup_generation_only_for_engineer(
    tmp_path: Path,
) -> None:
    repo = ProjectRepository(tmp_path)
    workspace = repo.create_project(
        name="K10 followup",
        initial_idea="用行空板 K10 做温湿度屏幕仪表盘。",
        selected_expert_types=[
            ExpertType.SMART_ENGINEER,
            ExpertType.PROBLEM_GUIDE,
        ],
    )

    engineer = ContextAssembler(repo.db_path).assemble(
        ContextAssemblyInput(
            projectId=workspace.project.id,
            expert=ExpertType.SMART_ENGINEER,
            userMessage="现在生成代码。",
        )
    )
    guide = ContextAssembler(repo.db_path).assemble(
        ContextAssemblyInput(
            projectId=workspace.project.id,
            expert=ExpertType.PROBLEM_GUIDE,
            userMessage="现在生成代码。",
        )
    )

    assert engineer.boardSkill is not None
    assert engineer.boardSkill["templates"][0]["path"] == (
        "templates/02_onboard_dashboard.py"
    )
    assert engineer.boardSkill["boardProfile"]["profileId"] == "unihiker-k10"
    assert guide.boardSkill is None


def test_context_assembler_uses_effective_board_profile_overlay(tmp_path: Path) -> None:
    repo = ProjectRepository(tmp_path)
    workspace = repo.create_project(
        name="K10 overlay",
        initial_idea="用行空板 K10 做温湿度显示。",
        selected_expert_types=[ExpertType.SMART_ENGINEER],
    )
    board_profiles = BoardProfileRepository(tmp_path)
    bundled = board_profiles.get_profile("unihiker-k10")
    marker = "OVERLAY_BOARD_PROFILE_CONTEXT_MARKER"
    updated = board_profiles.update_profile(
        "unihiker-k10",
        content=f"{bundled.content.rstrip()}\n\n## 项目覆盖\n\n{marker}\n",
        expected_revision=bundled.revision,
    )

    context = ContextAssembler(repo.db_path).assemble(
        ContextAssemblyInput(
            projectId=workspace.project.id,
            expert=ExpertType.SMART_ENGINEER,
            userMessage="请根据行空板 K10 档案审查 MicroPython 代码。",
        )
    )

    profile = next(
        item
        for item in context.publicKnowledge
        if item["source"] == "markdown_board_profile"
    )
    assert profile["revision"] == updated.revision
    assert marker in profile["markdown"]


def test_public_hardware_knowledge_is_shared_by_every_expert(tmp_path) -> None:
    repo = ProjectRepository(tmp_path)
    workspace = repo.create_project_from_idea(
        idea="做一个带传感器和外壳的装置",
        project_name="公共硬件知识测试",
        initial_expert=ExpertType.PROBLEM_GUIDE,
        participating_experts=[
            ExpertType.PROBLEM_GUIDE,
            ExpertType.SMART_ENGINEER,
            ExpertType.STRUCTURE_ENGINEER,
        ],
    )

    assembled = {
        expert: ContextAssembler(repo.db_path).assemble(
            ContextAssemblyInput(
                projectId=workspace.project.id,
                expert=expert,
                userMessage="ESP32 传感器外壳",
            )
        )
        for expert in (
            ExpertType.PROBLEM_GUIDE,
            ExpertType.SMART_ENGINEER,
            ExpertType.STRUCTURE_ENGINEER,
        )
    }

    assert all(context.publicKnowledge for context in assembled.values())
    assert all(
        item["source"] in {"local_hardware_library", "markdown_board_profile"}
        for context in assembled.values()
        for item in context.publicKnowledge
    )


def test_edited_public_hardware_knowledge_is_identical_for_every_expert(
    tmp_path: Path,
) -> None:
    repo = ProjectRepository(tmp_path)
    workspace = repo.create_project_from_idea(
        idea="做一个 ESP32 温湿度装置和外壳",
        project_name="可编辑公共知识测试",
        initial_expert=ExpertType.PROBLEM_GUIDE,
        participating_experts=[
            ExpertType.PROBLEM_GUIDE,
            ExpertType.SMART_ENGINEER,
            ExpertType.STRUCTURE_ENGINEER,
        ],
    )
    hardware = HardwareRepository(repo.db_path)
    seed_default_components(repo.db_path)
    dht22 = next(
        component
        for component in hardware.list_components()
        if component.name == "DHT22 温湿度传感器"
    )
    edited_note = "公共编辑说明：外壳必须给传感器保留通风开孔。"
    hardware.update_component(dht22.id, notes=edited_note)

    assembled = [
        ContextAssembler(repo.db_path).assemble(
            ContextAssemblyInput(
                projectId=workspace.project.id,
                expert=expert,
                userMessage="DHT22 温湿度传感器 外壳",
            )
        )
        for expert in (
            ExpertType.PROBLEM_GUIDE,
            ExpertType.SMART_ENGINEER,
            ExpertType.STRUCTURE_ENGINEER,
        )
    ]
    shared_entries = [
        next(
            item
            for item in context.publicKnowledge
            if item.get("componentId") == dht22.id
        )
        for context in assembled
    ]

    assert all(item["notes"] == edited_note for item in shared_entries)
    assert shared_entries[0] == shared_entries[1] == shared_entries[2]


def test_project_facts_decisions_and_artifacts_are_shared_by_every_expert(
    tmp_path: Path,
) -> None:
    repo = ProjectRepository(tmp_path)
    workspace = repo.create_project_from_idea(
        idea="做一个带传感器和外壳的装置",
        project_name="三师共享上下文测试",
        initial_expert=ExpertType.PROBLEM_GUIDE,
        participating_experts=[
            ExpertType.PROBLEM_GUIDE,
            ExpertType.SMART_ENGINEER,
            ExpertType.STRUCTURE_ENGINEER,
        ],
    )
    project_id = workspace.project.id
    now = "2026-07-11T00:00:00+00:00"
    with sqlite3.connect(repo.db_path) as conn:
        conn.execute(
            """
            INSERT INTO project_shared_facts (
              id, project_id, field, value_json, status, source_type, source_id,
              source_expert_id, proposed_by_expert_type, confirmed_by, confirmed_at,
              superseded_by, affects_artifact_ids_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'confirmed', 'user', NULL, NULL, ?, 'user', ?, NULL, '[]', ?, ?)
            """,
            (
                "fact_shared_sensor",
                project_id,
                "selected_sensor",
                json.dumps("DHT22", ensure_ascii=False),
                ExpertType.PROBLEM_GUIDE.value,
                now,
                now,
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO project_decisions (
              id, project_id, title, value_json, status, reason,
              proposed_by_expert_type, confirmed_by, confirmed_at,
              affected_artifact_ids_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'confirmed', ?, ?, 'user', ?, '[]', ?, ?)
            """,
            (
                "decision_shared_power",
                project_id,
                "统一使用 USB 5V 供电",
                json.dumps("USB 5V", ensure_ascii=False),
                "用户已确认供电方案。",
                ExpertType.SMART_ENGINEER.value,
                now,
                now,
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO artifacts (
              id, project_id, title, kind, status, source_agent_id, current_version_id,
              owner_expert_id, owner_expert_type, source_conversation_id,
              shared_context_revision, legacy_owner_expert, creator_legacy_expert,
              domain_status, created_at, updated_at
            ) VALUES (?, ?, ?, 'DOCUMENT', 'APPROVED', 'problem-guide', NULL,
                      NULL, 'problem_guide', NULL, 1, NULL, NULL, 'confirmed', ?, ?)
            """,
            ("artifact_shared_solution", project_id, "当前推荐实现方案", now, now),
        )
        conn.execute(
            """
            INSERT INTO artifact_versions (
              id, artifact_id, project_id, version, status, mime_type, preview_json,
              dependencies_json, producer_task_id, source_entity_type, source_entity_id,
              checksum, stale_reason, shared_context_revision, domain_status,
              created_at, confirmed_at
            ) VALUES (?, ?, ?, 1, 'APPROVED', 'application/json', ?, '[]', NULL,
                      NULL, NULL, 'shared-checksum', NULL, 1, 'confirmed', ?, ?)
            """,
            (
                "artifact_shared_solution_v1",
                "artifact_shared_solution",
                project_id,
                json.dumps({"summary": "同一版本方案"}, ensure_ascii=False),
                now,
                now,
            ),
        )
        conn.execute(
            "UPDATE artifacts SET current_version_id = ? WHERE id = ?",
            ("artifact_shared_solution_v1", "artifact_shared_solution"),
        )

    assembled = [
        ContextAssembler(repo.db_path).assemble(
            ContextAssemblyInput(
                projectId=project_id,
                expert=expert,
                userMessage="请继续这个项目",
            )
        )
        for expert in (
            ExpertType.PROBLEM_GUIDE,
            ExpertType.SMART_ENGINEER,
            ExpertType.STRUCTURE_ENGINEER,
        )
    ]

    assert all(
        "fact_shared_sensor" in {item["id"] for item in context.relevantFacts}
        for context in assembled
    )
    assert all(
        "decision_shared_power" in {item["id"] for item in context.relevantDecisions}
        for context in assembled
    )
    assert all(
        "artifact_shared_solution"
        in {item["artifactId"] for item in context.upstreamArtifacts}
        for context in assembled
    )
