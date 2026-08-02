from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from zhangwen.cad_agent.intake import (
    CAD_COMPONENT_MODE_QUESTION_ID,
    CAD_DIMENSIONS_QUESTION_ID,
    CAD_LOOSE_STORAGE_OPTION_ID,
    CadProfileIntake,
)
from zhangwen.cad_agent.models import CadRunStatus
from zhangwen.cad_engine.profiles import unihiker_k10_profile
from zhangwen.experts.context_assembler import (
    AssembledContext,
    ContextAssembler,
    ContextAssemblyInput,
)
from zhangwen.experts.runtime import (
    ExpertRuntime,
    ExpertRuntimeOutput,
    ExpertRuntimeRequest,
    _validate_hardware_grounding,
)
from zhangwen.hardware.seeds import seed_default_components
from zhangwen.llm.contracts import LLMConfig, LLMModelId
from zhangwen.llm.structured import StructuredLLMError
from zhangwen.projects.models import ExpertType
from zhangwen.projects.repository import ClarificationAnswerValue, ProjectRepository
from tests.fakes import SequenceProvider


NOW = "2026-07-13T08:00:00+00:00"


def test_mechanical_profiles_require_confirmed_bom_and_mapping(tmp_path: Path) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="用行空板 K10 做一个带外壳的装置",
        project_name="机械档案上下文",
        initial_expert=ExpertType.STRUCTURE_ENGINEER,
        participating_experts=[ExpertType.STRUCTURE_ENGINEER],
    )
    seed_default_components(repository.db_path)
    request = ContextAssemblyInput(
        projectId=workspace.project.id,
        expert=ExpertType.STRUCTURE_ENGINEER,
        userMessage="请为 K10 生成外壳",
    )

    assert ContextAssembler(repository.db_path).assemble(request).mechanicalProfiles == []

    profile = unihiker_k10_profile().model_dump(mode="json")
    with sqlite3.connect(repository.db_path) as conn:
        conn.execute(
            """
            INSERT INTO spec_runs (
              id, project_id, proposal_id, version, status, validation_json,
              stale_reason, created_at, updated_at, confirmed_at
            ) VALUES (?, ?, ?, 1, 'APPROVED', ?, NULL, ?, ?, ?)
            """,
            (
                "spec_confirmed_bom",
                workspace.project.id,
                "proposal_test_only",
                json.dumps({"ok": True, "checks": []}),
                NOW,
                NOW,
                NOW,
            ),
        )
        conn.execute(
            """
            INSERT INTO spec_files (
              id, spec_run_id, project_id, kind, path, mime_type, content,
              artifact_id, artifact_version_id, created_at
            ) VALUES (?, ?, ?, 'BOM', 'spec/bom.yaml', 'application/yaml', ?, NULL, NULL, ?)
            """,
            (
                "spec_file_confirmed_bom",
                "spec_confirmed_bom",
                workspace.project.id,
                "components:\n  - id: hw_seed_unihiker_k10\n    quantity: 1\n",
                NOW,
            ),
        )
        conn.execute(
            """
            INSERT INTO mechanical_profile_versions (
              id, profile_id, revision, schema_version, display_name, source,
              evidence_level, representation, profile_json, content_sha256,
              created_at
            ) VALUES (?, ?, ?, '1.0', ?, 'trusted', 'TRUSTED', 'parametric', ?, ?, ?)
            """,
            (
                "mechanical_profile_k10_v1",
                profile["profile_id"],
                profile["revision"],
                profile["display_name"],
                json.dumps(profile, ensure_ascii=False),
                "a" * 64,
                NOW,
            ),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO hardware_mechanical_links (
              id, hardware_component_id, mechanical_profile_id,
              mechanical_profile_revision, evidence_level, confirmed_at,
              created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'TRUSTED', ?, ?, ?)
            """,
            (
                "hardware_mechanical_link_k10",
                "hw_seed_unihiker_k10",
                profile["profile_id"],
                profile["revision"],
                NOW,
                NOW,
                NOW,
            ),
        )

    context = ContextAssembler(repository.db_path).assemble(request)

    assert len(context.mechanicalProfiles) == 1
    mapped = context.mechanicalProfiles[0]
    assert mapped["hardwareId"] == "hw_seed_unihiker_k10"
    assert mapped["profileId"] == "unihiker_k10"
    assert mapped["mappingConfirmed"] is True
    assert mapped["profile"]["dimensions"] == {
        "length_x": 83.2,
        "width_y": 51.3,
        "height_z": 10.6,
    }
    smart_context = ContextAssembler(repository.db_path).assemble(
        request.model_copy(update={"expert": ExpertType.SMART_ENGINEER})
    )
    assert smart_context.mechanicalProfiles == []


def test_cad_draft_rejects_unmapped_component_profile(tmp_path: Path) -> None:
    output = ExpertRuntimeOutput.model_validate(
        {
            "content": "结构草稿",
            "cadDraft": {
                "templateKind": "BOX_WITH_LID",
                "parameters": {"width": 100},
                "components": [
                    {
                        "instanceId": "controller_1",
                        "hardwareId": "hw_provider_invented",
                        "profileId": "profile_provider_invented",
                    }
                ],
                "constraints": {},
                "summary": "包含未知器件的草稿",
            },
        }
    )

    with pytest.raises(ValueError, match="confirmed project mechanical profile"):
        ExpertRuntime(tmp_path / "unused.sqlite3")._validate_boundaries(
            ExpertType.STRUCTURE_ENGINEER,
            output,
            mechanical_profiles=[],
        )


def test_cad_grounding_uses_confirmed_profile_ids_without_text_aliases() -> None:
    context = AssembledContext(
        projectSummary="结构化 grounding",
        hardwareKnowledgePolicy={
            "selectedComponents": [
                {
                    "componentId": "hw_selected_light_sensor",
                    "name": "项目已选光线传感器",
                }
            ],
            "activeLibraryComponents": [
                {
                    "componentId": "hw_seed_unihiker_k10",
                    "name": "行空板 K10",
                }
            ],
        },
        mechanicalProfiles=[
            {
                "hardwareId": "hw_seed_unihiker_k10",
                "profileId": "unihiker_k10",
                "mappingConfirmed": True,
            }
        ],
    )
    output = ExpertRuntimeOutput.model_validate(
        {
            "content": "已按确认的机械档案形成固定安装草稿。",
            "cadDraft": {
                "templateKind": "BOX_WITH_LID",
                "parameters": {"width": 100},
                "components": [
                    {
                        "instanceId": "controller_1",
                        "hardwareId": "hw_seed_unihiker_k10",
                        "profileId": "unihiker_k10",
                    }
                ],
                "constraints": {},
                "summary": "固定安装草稿",
            },
        }
    )

    _validate_hardware_grounding(context, output)


@pytest.mark.asyncio
async def test_structure_cad_draft_is_materialized_without_model_tool_authority(
    tmp_path: Path,
) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="设计一个参数化盒体",
        project_name="结构草稿",
        initial_expert=ExpertType.STRUCTURE_ENGINEER,
        participating_experts=[ExpertType.STRUCTURE_ENGINEER],
    )
    expert = workspace.experts[0]
    intake = CadProfileIntake(repository.db_path)
    intake_payload = intake.initial_question_payload()
    intake_message_id = "msg_structure_cad_intake"
    _insert_assistant_message(
        repository.db_path,
        workspace.project.id,
        expert.conversationId,
        message_id=intake_message_id,
        structured_payload=intake_payload,
    )
    intake.record_confirmed_answers(
        project_id=workspace.project.id,
        source_message_id=intake_message_id,
        user_message_id="msg_structure_cad_intake_answer",
        answers=(
            ClarificationAnswerValue(
                question_id=CAD_COMPONENT_MODE_QUESTION_ID,
                selected_option_ids=(CAD_LOOSE_STORAGE_OPTION_ID,),
            ),
            ClarificationAnswerValue(
                question_id=CAD_DIMENSIONS_QUESTION_ID,
                text_input="100 x 45 x 70 mm",
            ),
        ),
    )
    response_message_id = _insert_assistant_message(
        repository.db_path,
        workspace.project.id,
        expert.conversationId,
    )
    output = {
        "content": "结构参数已整理为待确认草稿。",
        "cadDraft": {
            "templateKind": "BOX_WITH_LID",
            "parameters": {
                "width": 100,
                "height": 70,
                "depth": 45,
                "wall_thickness": 2.4,
                "screw_posts": 4,
            },
            "components": [],
            "constraints": {"process": "FDM"},
            "summary": "参数化盒体与盖板",
            "requestedOutputs": ["STEP_ASSEMBLY", "STL_PRINTABLE_PARTS", "GLB_PREVIEW"],
        },
        "skillRequests": [
            {
                "skillId": "parametric-modeling",
                "input": {"projectId": "provider-cannot-authorize"},
            }
        ],
    }

    result = await ExpertRuntime(repository.db_path).run(
        request=ExpertRuntimeRequest(
            projectId=workspace.project.id,
            projectExpertId=expert.id,
            conversationId=expert.conversationId,
            expertType=ExpertType.STRUCTURE_ENGINEER,
            userMessage="已确认，生成外壳",
            responseMessageId=response_message_id,
            model=LLMModelId.DEEPSEEK_V4_FLASH,
        ),
        provider=SequenceProvider([json.dumps(output, ensure_ascii=False)]),
        config=LLMConfig(),
        api_key="fake-test-key",
    )

    assert result.cadRun is not None
    assert result.cadRun.status == CadRunStatus.DRAFT
    assert result.cadRun.sourceMessageId == response_message_id
    with sqlite3.connect(repository.db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM skill_runs").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM tool_runs").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_structure_cad_intent_returns_server_owned_clarification_then_loose_draft(
    tmp_path: Path,
) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="做一个 ESP32 储物盒",
        project_name="直接结构 intake",
        initial_expert=ExpertType.STRUCTURE_ENGINEER,
        participating_experts=[ExpertType.STRUCTURE_ENGINEER],
    )
    expert = workspace.experts[0]
    first_response_id = _insert_assistant_message(
        repository.db_path,
        workspace.project.id,
        expert.conversationId,
    )
    first = await ExpertRuntime(repository.db_path).run(
        request=ExpertRuntimeRequest(
            projectId=workspace.project.id,
            projectExpertId=expert.id,
            conversationId=expert.conversationId,
            expertType=ExpertType.STRUCTURE_ENGINEER,
            userMessage="做一个装 ESP32 的储物盒并生成 3D 模型",
            responseMessageId=first_response_id,
            model=LLMModelId.DEEPSEEK_V4_FLASH,
        ),
        provider=SequenceProvider(
            [
                json.dumps(
                    {
                        "content": "还需要尺寸。",
                    },
                    ensure_ascii=False,
                )
            ]
        ),
        config=LLMConfig(),
        api_key="fake-test-key",
    )
    assert first.cadRun is None
    assert first.output.uiPayload["type"] == "clarification"
    assert {item["id"] for item in first.output.uiPayload["questions"]} == {
        CAD_COMPONENT_MODE_QUESTION_ID,
    }
    assert first.output.pendingItems == []

    intake = CadProfileIntake(repository.db_path)
    with sqlite3.connect(repository.db_path) as conn:
        conn.execute(
            "UPDATE messages SET structured_payload_json = ? WHERE id = ?",
            (json.dumps(first.output.uiPayload, ensure_ascii=False), first_response_id),
        )
    intake.record_confirmed_answers(
        project_id=workspace.project.id,
        source_message_id=first_response_id,
        user_message_id="msg_loose_answer",
        answers=(
            ClarificationAnswerValue(
                question_id=CAD_COMPONENT_MODE_QUESTION_ID,
                selected_option_ids=(CAD_LOOSE_STORAGE_OPTION_ID,),
            ),
            ClarificationAnswerValue(
                question_id=CAD_DIMENSIONS_QUESTION_ID,
                text_input="100 x 100 x 50 mm",
            ),
        ),
    )
    second_response_id = "msg_structure_cad_response_second"
    _insert_assistant_message(
        repository.db_path,
        workspace.project.id,
        expert.conversationId,
        message_id=second_response_id,
    )
    second = await ExpertRuntime(repository.db_path).run(
        request=ExpertRuntimeRequest(
            projectId=workspace.project.id,
            projectExpertId=expert.id,
            conversationId=expert.conversationId,
            expertType=ExpertType.STRUCTURE_ENGINEER,
            userMessage="已确认，可以生成 3D 模型",
            responseMessageId=second_response_id,
            model=LLMModelId.DEEPSEEK_V4_FLASH,
        ),
        provider=SequenceProvider([json.dumps({"content": "继续说明。"}, ensure_ascii=False)]),
        config=LLMConfig(),
        api_key="fake-test-key",
    )
    assert second.cadRun is not None
    assert second.output.cadDraft.parameters == {
        "width": 100.0,
        "depth": 100.0,
        "height": 50.0,
    }
    assert second.output.cadDraft.components == []


@pytest.mark.asyncio
async def test_freeform_structure_uses_focused_geometry_schema_and_materializes_draft(
    tmp_path: Path,
) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="创建一块无器件安装板",
        project_name="自由结构恢复",
        initial_expert=ExpertType.STRUCTURE_ENGINEER,
        participating_experts=[ExpertType.STRUCTURE_ENGINEER],
    )
    expert = workspace.experts[0]
    response_message_id = _insert_assistant_message(
        repository.db_path,
        workspace.project.id,
        expert.conversationId,
        message_id="msg_freeform_geometry_response",
    )
    provider = SequenceProvider(
        [
            json.dumps(
                {
                    "primitives": [
                        {
                            "primitive_id": "plate",
                            "operation": "add",
                            "kind": "rounded_box",
                            "center": {"x": 0.0, "y": 0.0, "z": 2.0},
                            "size": {
                                "length_x": 80.0,
                                "width_y": 30.0,
                                "height_z": 4.0,
                            },
                            "corner_radius": 4.0,
                            "rotation_z_deg": 0,
                            "role": "body",
                        },
                        {
                            "primitive_id": "hole_left",
                            "operation": "cut",
                            "kind": "cylinder",
                            "center": {"x": -30.0, "y": 0.0, "z": 2.0},
                            "diameter": 3.0,
                            "height": 4.0,
                            "corner_radius": 0.0,
                            "rotation_z_deg": 0,
                            "role": "feature",
                        },
                    ]
                },
                ensure_ascii=False,
            )
        ]
    )

    result = await ExpertRuntime(repository.db_path).run(
        request=ExpertRuntimeRequest(
            projectId=workspace.project.id,
            projectExpertId=expert.id,
            conversationId=expert.conversationId,
            expertType=ExpertType.STRUCTURE_ENGINEER,
            userMessage=(
                "不使用任何传感器，创建一块 80×30×4 mm、四角 R4 的安装板，"
                "在 X=-30 mm 处打一个直径 3 mm 通孔"
            ),
            responseMessageId=response_message_id,
            model=LLMModelId.DEEPSEEK_V4_FLASH,
        ),
        provider=provider,
        config=LLMConfig(),
        api_key="fake-test-key",
    )

    assert provider.calls == 1
    assert result.cadRun is not None
    assert result.output.cadDraft is not None
    assert result.output.cadDraft.templateKind.value == "FREEFORM_STRUCTURE"
    assert [
        item.primitive_id for item in result.output.cadDraft.geometry.primitives
    ] == ["plate", "hole_left"]
    system_prompt = provider.requests[0].messages[0].content
    assert '"primitives"' in system_prompt
    assert '"cadDraft"' not in system_prompt


@pytest.mark.asyncio
async def test_non_structure_expert_cannot_materialize_cad_draft(tmp_path: Path) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="智能工程师不应生成 CAD",
        project_name="专家边界",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
    )
    expert = workspace.experts[0]
    output = {
        "content": "尝试生成 CAD。",
        "cadDraft": {
            "templateKind": "BOX_WITH_LID",
            "parameters": {"width": 100},
            "components": [],
            "constraints": {},
            "summary": "不允许的草稿",
        },
    }

    with pytest.raises(StructuredLLMError):
        await ExpertRuntime(repository.db_path).run(
            request=ExpertRuntimeRequest(
                projectId=workspace.project.id,
                projectExpertId=expert.id,
                conversationId=expert.conversationId,
                expertType=ExpertType.SMART_ENGINEER,
                userMessage="生成 CAD",
                model=LLMModelId.DEEPSEEK_V4_FLASH,
            ),
            provider=SequenceProvider([json.dumps(output, ensure_ascii=False)]),
            config=LLMConfig(),
            api_key="fake-test-key",
        )
    with sqlite3.connect(repository.db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM cad_runs").fetchone()[0] == 0


def _insert_assistant_message(
    db_path: Path,
    project_id: str,
    conversation_id: str,
    message_id: str = "msg_structure_cad_response",
    structured_payload: dict[str, object] | None = None,
) -> str:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO messages (
              id, conversation_id, project_id, role, content, reasoning_content,
              status, model, error_json, usage_json, structured_payload_json,
              metadata_json, created_at, updated_at
            ) VALUES (?, ?, ?, 'assistant', '', NULL, 'STREAMING', NULL, NULL,
                      NULL, ?, NULL, ?, ?)
            """,
            (
                message_id,
                conversation_id,
                project_id,
                json.dumps(structured_payload, ensure_ascii=False)
                if structured_payload is not None
                else None,
                NOW,
                NOW,
            ),
        )
    return message_id
