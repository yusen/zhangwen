from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

import pytest

from zhangwen.cad_agent.intake import (
    CAD_COMPONENT_MOUNT_OPTION_ID,
    CAD_COMPONENT_MOUNT_PROFILE_QUESTION_ID,
    CAD_COMPONENT_MODE_QUESTION_ID,
    CAD_DIMENSIONS_QUESTION_ID,
    CAD_FIXED_INSTALL_OPTION_ID,
    CAD_FREEFORM_DESCRIPTION_QUESTION_ID,
    CAD_FREEFORM_STRUCTURE_OPTION_ID,
    CAD_LOOSE_STORAGE_OPTION_ID,
    CAD_PROFILE_QUESTION_ID,
    CAD_TARGET_QUESTION_ID,
    CAD_VIRTUAL_HARDWARE_PREFIX,
    CadProfileIntake,
    classify_cad_target,
    is_cad_intent,
    is_cad_revision_request,
    parse_cad_dimensions,
)
from zhangwen.cad_agent.chat_projection import sync_cad_message_projection
from zhangwen.cad_agent.job_repository import CadJobRepository
from zhangwen.cad_agent.models import CadDraft, CadJobStatus, CadRun, CadRunStatus
from zhangwen.cad_agent.profile_repository import (
    MechanicalProfileRepository,
    MechanicalProfileSnapshot,
)
from zhangwen.cad_agent.repository import CadRepository
from zhangwen.experts.context_assembler import ContextAssembler, ContextAssemblyInput
from zhangwen.experts.runtime import ExpertRuntimeOutput
from zhangwen.llm.contracts import LLMModelId
from zhangwen.projects.models import ExpertType
from zhangwen.projects.repository import ClarificationAnswerValue, ProjectRepository


NOW = "2026-07-13T12:00:00+00:00"


def test_loose_storage_answers_create_project_intake_without_profile(tmp_path: Path) -> None:
    repository, project_id, conversation_id = _structure_project(tmp_path)
    intake = CadProfileIntake(repository.db_path)
    source_message_id = _insert_clarification(
        repository.db_path,
        project_id,
        conversation_id,
        intake.initial_question_payload(),
    )

    assert intake.record_confirmed_answers(
        project_id=project_id,
        source_message_id=source_message_id,
        user_message_id="msg_user_answer",
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

    state = intake.state(project_id)
    assert state.mode == "loose_storage"
    assert state.dimensions == {"width": 100.0, "depth": 100.0, "height": 50.0}
    assert state.profiles == ()


def test_fixed_install_exposes_only_server_owned_profile_options(tmp_path: Path) -> None:
    repository, project_id, conversation_id = _structure_project(tmp_path)
    intake = CadProfileIntake(repository.db_path)
    initial_message_id = _insert_clarification(
        repository.db_path,
        project_id,
        conversation_id,
        intake.initial_question_payload(),
    )
    intake.record_confirmed_answers(
        project_id=project_id,
        source_message_id=initial_message_id,
        user_message_id="msg_fixed_mode",
        answers=(
            ClarificationAnswerValue(
                question_id=CAD_COMPONENT_MODE_QUESTION_ID,
                selected_option_ids=(CAD_FIXED_INSTALL_OPTION_ID,),
            ),
            ClarificationAnswerValue(
                question_id=CAD_DIMENSIONS_QUESTION_ID,
                text_input="80 × 50 × 28 mm",
            ),
        ),
    )

    payload = intake.profile_question_payload()
    question = payload["questions"][0]
    assert question["id"] == CAD_PROFILE_QUESTION_ID
    assert question["mode"] == "multiple"
    assert all(
        option["id"].startswith("cad_profile_option_")
        and option["value"] == option["id"]
        for option in question["options"]
    )
    xiao_option = next(
        option for option in question["options"] if "XIAO ESP32S3" in option["label"]
    )
    profile_message_id = _insert_clarification(
        repository.db_path,
        project_id,
        conversation_id,
        payload,
    )
    intake.record_confirmed_answers(
        project_id=project_id,
        source_message_id=profile_message_id,
        user_message_id="msg_profile_answer",
        answers=(
            ClarificationAnswerValue(
                question_id=CAD_PROFILE_QUESTION_ID,
                selected_option_ids=(xiao_option["id"],),
            ),
        ),
    )

    selection = intake.selected_profiles(project_id)[0]
    assert selection.hardware_id.startswith(CAD_VIRTUAL_HARDWARE_PREFIX)
    assert selection.profile_id == "xiao_esp32s3"
    assert selection.revision == "confirmed-v1"
    context = ContextAssembler(repository.db_path).assemble(
        ContextAssemblyInput(
            projectId=project_id,
            expert=ExpertType.STRUCTURE_ENGINEER,
            userMessage="开始生成外壳",
        )
    )
    assert context.mechanicalProfiles[0]["hardwareId"] == selection.hardware_id
    assert context.mechanicalProfiles[0]["profileId"] == "xiao_esp32s3"


def test_component_mount_intake_selects_one_profile_without_box_dimensions(
    tmp_path: Path,
) -> None:
    repository, project_id, conversation_id = _structure_project(tmp_path)
    intake = CadProfileIntake(repository.db_path)
    target_payload = intake.target_question_payload()
    target_message_id = _insert_clarification(
        repository.db_path,
        project_id,
        conversation_id,
        target_payload,
    )

    assert intake.record_confirmed_answers(
        project_id=project_id,
        source_message_id=target_message_id,
        user_message_id="msg_component_mount_target",
        answers=(
            ClarificationAnswerValue(
                question_id=CAD_TARGET_QUESTION_ID,
                selected_option_ids=(CAD_COMPONENT_MOUNT_OPTION_ID,),
            ),
        ),
    )
    assert intake.state(project_id).target == "component_mount"
    assert intake.state(project_id).dimensions is None

    profile_payload = intake.component_mount_profile_question_payload()
    question = profile_payload["questions"][0]
    assert question["id"] == CAD_COMPONENT_MOUNT_PROFILE_QUESTION_ID
    assert question["mode"] == "single"
    selected = next(
        option for option in question["options"] if "XIAO ESP32S3" in option["label"]
    )
    profile_message_id = _insert_clarification(
        repository.db_path,
        project_id,
        conversation_id,
        profile_payload,
    )
    assert intake.record_confirmed_answers(
        project_id=project_id,
        source_message_id=profile_message_id,
        user_message_id="msg_component_mount_profile",
        answers=(
            ClarificationAnswerValue(
                question_id=CAD_COMPONENT_MOUNT_PROFILE_QUESTION_ID,
                selected_option_ids=(selected["id"],),
            ),
        ),
    )

    output = ExpertRuntimeOutput(content="已按器件机械档案生成安装结构。")
    intake.canonicalize_output(project_id, output)

    assert output.cadDraft is not None
    assert output.cadDraft.templateKind.value == "COMPONENT_MOUNT"
    assert output.cadDraft.parameters == {}
    assert len(output.cadDraft.components) == 1
    assert output.cadDraft.components[0].profileId == "xiao_esp32s3"
    assert output.uiPayload is None

    source_message = _insert_assistant_message(
        repository.db_path,
        project_id,
        conversation_id,
        "msg_component_mount_draft",
    )
    run = CadRepository(repository.db_path).create_draft(
        project_id=project_id,
        source_message_id=source_message,
        generated_by_expert_id=repository.get_workspace(project_id).experts[0].id,
        draft=output.cadDraft,
    )
    job = CadRepository(repository.db_path).create_job(
        project_id=project_id,
        cad_run_id=run.id,
        client_request_id="component-mount-build",
    )

    assert job.request.templateKind.value == "COMPONENT_MOUNT"
    assert len(job.request.profileSnapshots) == 1
    assert job.request.sizingEvidence is None


def test_freeform_intake_uses_natural_description_without_hardware_profile(
    tmp_path: Path,
) -> None:
    repository, project_id, conversation_id = _structure_project(tmp_path)
    intake = CadProfileIntake(repository.db_path)
    target_message_id = _insert_clarification(
        repository.db_path,
        project_id,
        conversation_id,
        intake.target_question_payload(),
    )
    assert intake.record_confirmed_answers(
        project_id=project_id,
        source_message_id=target_message_id,
        user_message_id="msg_freeform_target",
        answers=(
            ClarificationAnswerValue(
                question_id=CAD_TARGET_QUESTION_ID,
                selected_option_ids=(CAD_FREEFORM_STRUCTURE_OPTION_ID,),
            ),
        ),
    )

    prompt_output = ExpertRuntimeOutput(content="请描述结构。")
    intake.canonicalize_output(project_id, prompt_output)
    assert prompt_output.cadDraft is None
    assert prompt_output.uiPayload is not None
    assert prompt_output.uiPayload["questions"][0]["id"] == CAD_FREEFORM_DESCRIPTION_QUESTION_ID

    description_message_id = _insert_clarification(
        repository.db_path,
        project_id,
        conversation_id,
        prompt_output.uiPayload,
    )
    description = "做一块 80×30×4 mm、四角 R4 的安装板，在 x=±30 mm 处各切一个直径 3 mm 通孔。"
    assert intake.record_confirmed_answers(
        project_id=project_id,
        source_message_id=description_message_id,
        user_message_id="msg_freeform_description",
        answers=(
            ClarificationAnswerValue(
                question_id=CAD_FREEFORM_DESCRIPTION_QUESTION_ID,
                text_input=description,
            ),
        ),
    )
    assert intake.state(project_id).freeform_description == description
    assert intake.state(project_id).profiles == ()

    output = ExpertRuntimeOutput(
        content="已生成声明式结构。",
        cadDraft=CadDraft(
            templateKind="FREEFORM_STRUCTURE",
            parameters={},
            components=[],
            geometry={
                "primitives": [
                    {
                        "primitive_id": "plate",
                        "operation": "add",
                        "kind": "rounded_box",
                        "center": {"x": 0, "y": 0, "z": 2},
                        "size": {"length_x": 80, "width_y": 30, "height_z": 4},
                        "corner_radius": 4,
                        "role": "body",
                    },
                    {
                        "primitive_id": "hole_left",
                        "operation": "cut",
                        "kind": "cylinder",
                        "center": {"x": -30, "y": 0, "z": 2},
                        "diameter": 3,
                        "height": 6,
                        "role": "feature",
                    },
                    {
                        "primitive_id": "hole_right",
                        "operation": "cut",
                        "kind": "cylinder",
                        "center": {"x": 30, "y": 0, "z": 2},
                        "diameter": 3,
                        "height": 6,
                        "role": "feature",
                    },
                ]
            },
            constraints={"process": "FDM"},
            summary="圆角双孔安装板",
        ),
    )
    intake.canonicalize_output(project_id, output)
    assert output.cadDraft is not None
    assert output.cadDraft.templateKind.value == "FREEFORM_STRUCTURE"
    assert output.cadDraft.components == []

    source_message = _insert_assistant_message(
        repository.db_path,
        project_id,
        conversation_id,
        "msg_freeform_draft",
    )
    run = CadRepository(repository.db_path).create_draft(
        project_id=project_id,
        source_message_id=source_message,
        generated_by_expert_id=repository.get_workspace(project_id).experts[0].id,
        draft=output.cadDraft,
    )
    job = CadRepository(repository.db_path).create_job(
        project_id=project_id,
        cad_run_id=run.id,
        client_request_id="freeform-build",
    )
    assert job.request.templateKind.value == "FREEFORM_STRUCTURE"
    assert job.request.profileSnapshots == []
    assert job.request.sizingEvidence is None


def test_job_rejects_superseded_project_profile_selection(tmp_path: Path) -> None:
    repository, project_id, conversation_id = _structure_project(tmp_path)
    expert_id = repository.get_workspace(project_id).experts[0].id
    intake = CadProfileIntake(repository.db_path)
    initial_message_id = _insert_clarification(
        repository.db_path,
        project_id,
        conversation_id,
        intake.initial_question_payload(),
    )
    intake.record_confirmed_answers(
        project_id=project_id,
        source_message_id=initial_message_id,
        user_message_id="msg_fixed_mode",
        answers=(
            ClarificationAnswerValue(
                question_id=CAD_COMPONENT_MODE_QUESTION_ID,
                selected_option_ids=(CAD_FIXED_INSTALL_OPTION_ID,),
            ),
            ClarificationAnswerValue(
                question_id=CAD_DIMENSIONS_QUESTION_ID,
                text_input="80 x 50 x 28 mm",
            ),
        ),
    )
    profile_payload = intake.profile_question_payload()
    xiao_option = next(
        option
        for option in profile_payload["questions"][0]["options"]
        if "XIAO ESP32S3" in option["label"]
    )
    profile_message_id = _insert_clarification(
        repository.db_path,
        project_id,
        conversation_id,
        profile_payload,
    )
    intake.record_confirmed_answers(
        project_id=project_id,
        source_message_id=profile_message_id,
        user_message_id="msg_profile_answer",
        answers=(
            ClarificationAnswerValue(
                question_id=CAD_PROFILE_QUESTION_ID,
                selected_option_ids=(xiao_option["id"],),
            ),
        ),
    )
    selection = intake.selected_profiles(project_id)[0]
    source_message = _insert_assistant_message(
        repository.db_path,
        project_id,
        conversation_id,
        "msg_cad_draft",
    )
    cad = CadRepository(repository.db_path)
    run = cad.create_draft(
        project_id=project_id,
        source_message_id=source_message,
        generated_by_expert_id=expert_id,
        draft=CadDraft.model_validate(
            {
                "templateKind": "BOX_WITH_LID",
                "parameters": {"width": 80, "depth": 50, "height": 28},
                "components": [
                    {
                        "instanceId": "component_1",
                        "hardwareId": selection.hardware_id,
                        "profileId": selection.profile_id,
                    }
                ],
                "constraints": {"process": "FDM"},
                "summary": "XIAO 固定安装外壳",
            }
        ),
    )
    loose_message_id = _insert_clarification(
        repository.db_path,
        project_id,
        conversation_id,
        _fresh_intake_payload(intake),
    )
    intake.record_confirmed_answers(
        project_id=project_id,
        source_message_id=loose_message_id,
        user_message_id="msg_switch_loose",
        answers=(
            ClarificationAnswerValue(
                question_id=CAD_COMPONENT_MODE_QUESTION_ID,
                selected_option_ids=(CAD_LOOSE_STORAGE_OPTION_ID,),
            ),
            ClarificationAnswerValue(
                question_id=CAD_DIMENSIONS_QUESTION_ID,
                text_input="80 x 50 x 28 mm",
            ),
        ),
    )

    with pytest.raises(
        ValueError,
        match="CAD_(?:INTAKE_REVISED|PROJECT_PROFILE_SELECTION_STALE)",
    ):
        cad.create_job(
            project_id=project_id,
            cad_run_id=run.id,
            client_request_id="stale-selection",
        )


def test_complete_loose_intake_guarantees_draft_when_provider_omits_it(
    tmp_path: Path,
) -> None:
    repository, project_id, conversation_id = _structure_project(tmp_path)
    intake = CadProfileIntake(repository.db_path)
    source_message_id = _insert_clarification(
        repository.db_path,
        project_id,
        conversation_id,
        intake.initial_question_payload(),
    )
    intake.record_confirmed_answers(
        project_id=project_id,
        source_message_id=source_message_id,
        user_message_id="msg_complete_loose",
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
    output = ExpertRuntimeOutput(content="参数已经确认，可以继续。")

    intake.canonicalize_output(project_id, output)
    intake.ensure_runtime_output(project_id, output)

    assert output.cadDraft is not None
    assert output.cadDraft.parameters == {
        "width": 100.0,
        "depth": 100.0,
        "height": 50.0,
    }
    assert output.cadDraft.components == []


def test_invalid_dimensions_roll_back_chat_answers_and_cad_facts_then_allow_retry(
    tmp_path: Path,
) -> None:
    repository, project_id, conversation_id = _structure_project(tmp_path)
    expert = repository.get_workspace(project_id).experts[0]
    intake = CadProfileIntake(repository.db_path)
    payload = _legacy_combined_intake_payload(intake)
    source_message_id = _insert_clarification(
        repository.db_path,
        project_id,
        conversation_id,
        payload,
    )
    repository.register_clarification_question(
        project_id=project_id,
        conversation_id=conversation_id,
        source_message_id=source_message_id,
        stage=repository.get_workspace(project_id).project.stage,
        payload=payload,
    )
    invalid_answers = [
        ClarificationAnswerValue(
            question_id=CAD_COMPONENT_MODE_QUESTION_ID,
            selected_option_ids=(CAD_LOOSE_STORAGE_OPTION_ID,),
        ),
        ClarificationAnswerValue(
            question_id=CAD_DIMENSIONS_QUESTION_ID,
            text_input="长 100、宽 80、高 40",
        ),
    ]

    def record_invalid_answers(conn: sqlite3.Connection, user_message_id: str) -> None:
        intake.record_confirmed_answers(
            project_id=project_id,
            source_message_id=source_message_id,
            user_message_id=user_message_id,
            answers=invalid_answers,
            connection=conn,
        )

    with sqlite3.connect(repository.db_path) as conn:
        before = {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "messages",
                "conversation_turns",
                "clarification_answers",
                "project_shared_facts",
            )
        }

    with pytest.raises(ValueError, match="CAD_DIMENSIONS_INVALID"):
        repository.append_user_and_assistant(
            project_id,
            "已选择松散存放，但尺寸格式无效",
            LLMModelId.DEEPSEEK_V4_FLASH,
            project_expert_id=expert.id,
            turn_id="turn_invalid_cad_dimensions",
            response_turn_id="turn_invalid_cad_dimensions_response",
            client_turn_id="client_cad_dimensions_retry",
            clarification_source_message_id=source_message_id,
            clarification_answers=invalid_answers,
            require_complete_clarification=True,
            clarification_transaction=record_invalid_answers,
        )

    with sqlite3.connect(repository.db_path) as conn:
        after_invalid = {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in before
        }
        question_rows = conn.execute(
            """
            SELECT question_id, status, answered_at
            FROM clarification_questions
            WHERE project_id = ? AND source_message_id = ?
            ORDER BY question_id
            """,
            (project_id, source_message_id),
        ).fetchall()
    assert after_invalid == before
    assert question_rows == [
        (CAD_COMPONENT_MODE_QUESTION_ID, "pending", None),
        (CAD_DIMENSIONS_QUESTION_ID, "pending", None),
    ]
    assert intake.state(project_id).mode is None
    assert intake.state(project_id).dimensions is None

    valid_answers = [
        invalid_answers[0],
        ClarificationAnswerValue(
            question_id=CAD_DIMENSIONS_QUESTION_ID,
            text_input="100 x 80 x 40 mm",
        ),
    ]

    def record_valid_answers(conn: sqlite3.Connection, user_message_id: str) -> None:
        intake.record_confirmed_answers(
            project_id=project_id,
            source_message_id=source_message_id,
            user_message_id=user_message_id,
            answers=valid_answers,
            connection=conn,
        )

    repository.append_user_and_assistant(
        project_id,
        "已确认松散存放，内腔 100 x 80 x 40 mm",
        LLMModelId.DEEPSEEK_V4_FLASH,
        project_expert_id=expert.id,
        turn_id="turn_valid_cad_dimensions",
        response_turn_id="turn_valid_cad_dimensions_response",
        client_turn_id="client_cad_dimensions_retry",
        clarification_source_message_id=source_message_id,
        clarification_answers=valid_answers,
        require_complete_clarification=True,
        clarification_transaction=record_valid_answers,
    )

    state = intake.state(project_id)
    assert state.mode == "loose_storage"
    assert state.dimensions == {"width": 100.0, "depth": 80.0, "height": 40.0}
    with sqlite3.connect(repository.db_path) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM clarification_answers WHERE client_turn_id = ?",
            ("client_cad_dimensions_retry",),
        ).fetchone()[0] == 2
        assert conn.execute(
            """
            SELECT COUNT(*) FROM clarification_questions
            WHERE project_id = ? AND source_message_id = ? AND status = 'answered'
            """,
            (project_id, source_message_id),
        ).fetchone()[0] == 2


def test_profile_options_expose_only_current_revision_per_profile(tmp_path: Path) -> None:
    repository, _project_id, _conversation_id = _structure_project(tmp_path)
    profiles = MechanicalProfileRepository(repository.db_path)
    profiles.seed_builtin_profiles(now="2026-07-13T00:00:00+00:00")
    current = profiles.get("xiao_esp32s3")
    revised = MechanicalProfileSnapshot.from_profile(
        current.to_profile().model_copy(update={"revision": "confirmed-v2"})
    )
    with sqlite3.connect(repository.db_path) as conn:
        conn.execute(
            """
            INSERT INTO mechanical_profile_versions (
              id, profile_id, revision, schema_version, display_name, source,
              evidence_level, representation, profile_json, content_sha256,
              created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "mechanical_profile_xiao_esp32s3_confirmed_v2",
                revised.profile_id,
                revised.revision,
                revised.schema_version,
                revised.display_name,
                revised.source.value,
                revised.evidence_level,
                revised.representation,
                revised.model_dump_json(),
                revised.content_sha256,
                "2026-07-14T00:00:00+00:00",
            ),
        )

    xiao_options = [
        option
        for option in CadProfileIntake(repository.db_path).list_options()
        if option.profile_id == "xiao_esp32s3"
    ]
    assert [(option.revision, option.content_sha256) for option in xiao_options] == [
        (revised.revision, revised.content_sha256)
    ]


def test_project_profile_selection_precedes_confirmed_bom_at_context_limit(
    tmp_path: Path,
) -> None:
    repository, project_id, conversation_id = _structure_project(tmp_path)
    intake = CadProfileIntake(repository.db_path)
    initial_message_id = _insert_clarification(
        repository.db_path,
        project_id,
        conversation_id,
        intake.initial_question_payload(),
    )
    intake.record_confirmed_answers(
        project_id=project_id,
        source_message_id=initial_message_id,
        user_message_id="msg_fixed_mode_for_context_limit",
        answers=(
            ClarificationAnswerValue(
                question_id=CAD_COMPONENT_MODE_QUESTION_ID,
                selected_option_ids=(CAD_FIXED_INSTALL_OPTION_ID,),
            ),
            ClarificationAnswerValue(
                question_id=CAD_DIMENSIONS_QUESTION_ID,
                text_input="100 x 80 x 40 mm",
            ),
        ),
    )
    profile_payload = intake.profile_question_payload()
    selected_option = next(
        option
        for option in profile_payload["questions"][0]["options"]
        if "XIAO ESP32S3" in option["label"]
    )
    profile_message_id = _insert_clarification(
        repository.db_path,
        project_id,
        conversation_id,
        profile_payload,
    )
    intake.record_confirmed_answers(
        project_id=project_id,
        source_message_id=profile_message_id,
        user_message_id="msg_project_profile_for_context_limit",
        answers=(
            ClarificationAnswerValue(
                question_id=CAD_PROFILE_QUESTION_ID,
                selected_option_ids=(selected_option["id"],),
            ),
        ),
    )
    selection = intake.selected_profiles(project_id)[0]
    snapshot = intake.resolve_virtual_hardware(
        project_id=project_id,
        hardware_id=selection.hardware_id,
        declared_profile_id=selection.profile_id,
    )
    bom_ids = [f"hw_cad_context_limit_{index:02d}" for index in range(32)]
    bom_yaml = "components:\n" + "".join(
        f"  - id: {component_id}\n    quantity: 1\n" for component_id in bom_ids
    )
    with sqlite3.connect(repository.db_path) as conn:
        for index, component_id in enumerate(bom_ids):
            conn.execute(
                """
                INSERT INTO hardware_components (
                  id, name, category, status, electrical_json, stock, price,
                  age_recommendation, safety_tags_json, notes, created_at, updated_at
                ) VALUES (?, ?, 'MCU', 'ACTIVE', '{}', 1, 0, NULL, '[]', '', ?, ?)
                """,
                (component_id, f"CAD context component {index:02d}", NOW, NOW),
            )
            conn.execute(
                """
                INSERT INTO hardware_mechanical_links (
                  id, hardware_component_id, mechanical_profile_id,
                  mechanical_profile_revision, evidence_level, confirmed_at,
                  created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'CONFIRMED', ?, ?, ?)
                """,
                (
                    f"link_cad_context_limit_{index:02d}",
                    component_id,
                    snapshot.profile_id,
                    snapshot.revision,
                    NOW,
                    NOW,
                    NOW,
                ),
            )
        conn.execute(
            """
            INSERT INTO spec_runs (
              id, project_id, proposal_id, version, status, validation_json,
              stale_reason, created_at, updated_at, confirmed_at
            ) VALUES ('spec_cad_context_limit', ?, 'proposal_test_only', 1,
                      'APPROVED', '{"ok": true, "checks": []}', NULL, ?, ?, ?)
            """,
            (project_id, NOW, NOW, NOW),
        )
        conn.execute(
            """
            INSERT INTO spec_files (
              id, spec_run_id, project_id, kind, path, mime_type, content,
              artifact_id, artifact_version_id, created_at
            ) VALUES ('spec_file_cad_context_limit', 'spec_cad_context_limit', ?,
                      'BOM', 'spec/bom.yaml', 'application/yaml', ?, NULL, NULL, ?)
            """,
            (project_id, bom_yaml, NOW),
        )

    context = ContextAssembler(repository.db_path).assemble(
        ContextAssemblyInput(
            projectId=project_id,
            expert=ExpertType.STRUCTURE_ENGINEER,
            userMessage="生成固定安装外壳",
        )
    )

    assert len(context.mechanicalProfiles) == 32
    assert context.mechanicalProfiles[0]["source"] == "confirmed_project_cad_selection"
    assert context.mechanicalProfiles[0]["hardwareId"] == selection.hardware_id
    assert {item["hardwareId"] for item in context.mechanicalProfiles[1:]} == set(
        bom_ids[:31]
    )


@pytest.mark.parametrize(
    "status",
    [
        CadRunStatus.DRAFT,
        CadRunStatus.VALIDATED,
        CadRunStatus.READY_FOR_REVIEW,
        CadRunStatus.FAILED,
        CadRunStatus.CANCELED,
        CadRunStatus.REJECTED,
    ],
)
def test_revision_stales_every_non_active_candidate_and_chat_projection(
    tmp_path: Path,
    status: CadRunStatus,
) -> None:
    repository, project_id, conversation_id = _structure_project(tmp_path)
    intake, cad, run = _complete_loose_draft(
        repository,
        project_id,
        conversation_id,
    )
    with sqlite3.connect(repository.db_path) as conn:
        conn.execute(
            "UPDATE cad_runs SET status = ? WHERE id = ?",
            (status.value, run.id),
        )
    sync_cad_message_projection(repository.db_path, cad.get_cad(project_id, run.id))

    intake.restart_for_revision(project_id)

    with sqlite3.connect(repository.db_path) as conn:
        conn.row_factory = sqlite3.Row
        run_row = conn.execute(
            "SELECT status FROM cad_runs WHERE id = ?",
            (run.id,),
        ).fetchone()
        message_row = conn.execute(
            "SELECT structured_payload_json FROM messages WHERE id = ?",
            (run.sourceMessageId,),
        ).fetchone()
    assert run_row is not None and run_row["status"] == CadRunStatus.STALE.value
    assert message_row is not None
    assert json.loads(str(message_row["structured_payload_json"]))["status"] == "STALE"


@pytest.mark.parametrize(
    "status",
    [CadRunStatus.QUEUED, CadRunStatus.RUNNING, CadRunStatus.APPROVED],
)
def test_revision_does_not_cancel_active_jobs_or_replace_approved_baseline(
    tmp_path: Path,
    status: CadRunStatus,
) -> None:
    repository, project_id, conversation_id = _structure_project(tmp_path)
    intake, _cad, run = _complete_loose_draft(
        repository,
        project_id,
        conversation_id,
    )
    with sqlite3.connect(repository.db_path) as conn:
        conn.execute(
            "UPDATE cad_runs SET status = ? WHERE id = ?",
            (status.value, run.id),
        )

    intake.restart_for_revision(project_id)

    with sqlite3.connect(repository.db_path) as conn:
        persisted = conn.execute(
            "SELECT status FROM cad_runs WHERE id = ?",
            (run.id,),
        ).fetchone()
    assert persisted is not None and persisted[0] == status.value


def test_revised_intake_blocks_old_draft_job_creation(tmp_path: Path) -> None:
    repository, project_id, conversation_id = _structure_project(tmp_path)
    intake, cad, run = _complete_loose_draft(
        repository,
        project_id,
        conversation_id,
    )

    intake.restart_for_revision(project_id)

    with pytest.raises(ValueError, match="CAD_INTAKE_REVISED"):
        cad.create_job(
            project_id=project_id,
            cad_run_id=run.id,
            client_request_id="old-intake-create",
        )


def test_revised_intake_blocks_old_failed_job_retry(tmp_path: Path) -> None:
    repository, project_id, conversation_id = _structure_project(tmp_path)
    intake, cad, run = _complete_loose_draft(
        repository,
        project_id,
        conversation_id,
    )
    job = cad.create_job(
        project_id=project_id,
        cad_run_id=run.id,
        client_request_id="old-intake-first-job",
    )
    jobs = CadJobRepository(repository.db_path)
    jobs.mark_running(job.id, "2026-07-13T12:01:00+00:00")
    jobs.finish_error(
        job.id,
        status=CadJobStatus.FAILED,
        code="SYNTHETIC_RETRYABLE",
        message="synthetic retryable failure",
        retryable=True,
        completed_at="2026-07-13T12:02:00+00:00",
    )

    intake.restart_for_revision(project_id)

    with pytest.raises(ValueError, match="CAD_INTAKE_REVISED"):
        cad.retry_job(
            project_id=project_id,
            job_id=job.id,
            client_request_id="old-intake-retry",
        )


def test_revised_intake_blocks_old_ready_run_confirmation(tmp_path: Path) -> None:
    repository, project_id, conversation_id = _structure_project(tmp_path)
    intake, cad, run = _complete_loose_draft(
        repository,
        project_id,
        conversation_id,
    )
    with sqlite3.connect(repository.db_path) as conn:
        conn.execute(
            """
            UPDATE cad_runs
            SET status = 'READY_FOR_REVIEW', validation_json = '{"ok":true,"checks":[]}'
            WHERE id = ?
            """,
            (run.id,),
        )

    intake.restart_for_revision(project_id)

    with pytest.raises(ValueError, match="CAD_INTAKE_REVISED"):
        cad.confirm_cad(project_id, run.id)


def test_same_values_in_a_new_intake_round_do_not_revive_old_draft(tmp_path: Path) -> None:
    repository, project_id, conversation_id = _structure_project(tmp_path)
    intake, cad, old_run = _complete_loose_draft(
        repository,
        project_id,
        conversation_id,
    )
    old_revision = old_run.designState["intakeSnapshotSha256"]
    intake.restart_for_revision(project_id)
    _record_loose_intake(
        repository,
        project_id,
        conversation_id,
        intake,
        user_message_id="msg_same_values_new_round",
    )
    source_message_id = _insert_assistant_message(
        repository.db_path,
        project_id,
        conversation_id,
        f"msg_cad_same_values_{uuid.uuid4().hex}",
    )
    new_run = cad.create_draft(
        project_id=project_id,
        source_message_id=source_message_id,
        generated_by_expert_id=repository.get_workspace(project_id).experts[0].id,
        draft=_loose_draft(),
    )

    assert new_run.designState["intakeSnapshotSha256"] != old_revision
    with pytest.raises(ValueError, match="CAD_INTAKE_REVISED"):
        cad.create_job(
            project_id=project_id,
            cad_run_id=old_run.id,
            client_request_id="same-values-old-run",
        )


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("这个支架需要加强吗", False),
        ("结构件用铝合金还是 ABS", False),
        ("请生成一个安装座", True),
        ("请生成一个保护盒", True),
        ("请为控制器做保护壳建模", True),
        ("做一个 80×30×4 mm 的圆角板并打两个孔", True),
        ("生成一个可 3D 打印的零件", True),
        ("生成行空板 K10 电子相册结构", True),
    ],
)
def test_cad_intent_does_not_route_unsupported_structure_terms_to_box_template(
    message: str,
    expected: bool,
) -> None:
    assert is_cad_intent(message) is expected


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("给这个光线传感器做一个安装座", "component_mount"),
        ("基于 K10 创建固定底座", "component_mount"),
        ("给这个传感器做一个安装座零件", "component_mount"),
        ("做一个装传感器的保护壳", "box_with_lid"),
        ("不使用任何传感器，按描述生成一块带孔安装板", "freeform_structure"),
        ("创建一个 80×30×4 mm 的圆角零件", "freeform_structure"),
        ("做一个 80×30×4 mm 的圆角板并打两个孔", "freeform_structure"),
        ("生成一个可 3D 打印的零件", "freeform_structure"),
        ("使用行空板 K10 电子相册模板", "unihiker_k10_photo_album"),
        ("生成 K10 相册支架", "unihiker_k10_photo_album"),
        ("创建一个三维结构", None),
    ],
)
def test_cad_target_classification_does_not_default_to_box(
    message: str,
    expected: str | None,
) -> None:
    assert classify_cad_target(message) == expected


def test_bare_dimensions_are_a_revision_inside_existing_cad_context() -> None:
    assert is_cad_revision_request("120 × 80 × 40") is True


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("100 x 90 x 50 mm", {"width": 100.0, "depth": 90.0, "height": 50.0}),
        ("80×50×28毫米", {"width": 80.0, "depth": 50.0, "height": 28.0}),
    ],
)
def test_dimension_parser_accepts_explicit_inner_dimensions(
    text: str,
    expected: dict[str, float],
) -> None:
    assert parse_cad_dimensions(text) == expected


def _structure_project(tmp_path: Path) -> tuple[ProjectRepository, str, str]:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="生成一个结构外壳",
        project_name="CAD intake",
        initial_expert=ExpertType.STRUCTURE_ENGINEER,
        participating_experts=[ExpertType.STRUCTURE_ENGINEER],
    )
    return repository, workspace.project.id, workspace.experts[0].conversationId


def _loose_draft() -> CadDraft:
    return CadDraft(
        templateKind="BOX_WITH_LID",
        parameters={"width": 80, "depth": 50, "height": 28},
        components=[],
        constraints={"process": "FDM"},
        summary="松散存放保护盒",
    )


def _record_loose_intake(
    repository: ProjectRepository,
    project_id: str,
    conversation_id: str,
    intake: CadProfileIntake,
    *,
    user_message_id: str,
) -> None:
    source_message_id = _insert_clarification(
        repository.db_path,
        project_id,
        conversation_id,
        intake.initial_question_payload(),
    )
    intake.record_confirmed_answers(
        project_id=project_id,
        source_message_id=source_message_id,
        user_message_id=user_message_id,
        answers=(
            ClarificationAnswerValue(
                question_id=CAD_COMPONENT_MODE_QUESTION_ID,
                selected_option_ids=(CAD_LOOSE_STORAGE_OPTION_ID,),
            ),
            ClarificationAnswerValue(
                question_id=CAD_DIMENSIONS_QUESTION_ID,
                text_input="80 x 50 x 28 mm",
            ),
        ),
    )


def _complete_loose_draft(
    repository: ProjectRepository,
    project_id: str,
    conversation_id: str,
) -> tuple[CadProfileIntake, CadRepository, CadRun]:
    intake = CadProfileIntake(repository.db_path)
    _record_loose_intake(
        repository,
        project_id,
        conversation_id,
        intake,
        user_message_id=f"msg_loose_{uuid.uuid4().hex}",
    )
    source_message_id = _insert_assistant_message(
        repository.db_path,
        project_id,
        conversation_id,
        f"msg_cad_draft_{uuid.uuid4().hex}",
    )
    cad = CadRepository(repository.db_path)
    run = cad.create_draft(
        project_id=project_id,
        source_message_id=source_message_id,
        generated_by_expert_id=repository.get_workspace(project_id).experts[0].id,
        draft=_loose_draft(),
    )
    sync_cad_message_projection(repository.db_path, run)
    return intake, cad, run


def _insert_clarification(
    db_path: Path,
    project_id: str,
    conversation_id: str,
    payload: dict[str, object],
) -> str:
    message_id = f"msg_clarification_{uuid.uuid4().hex}"
    _insert_assistant_message(db_path, project_id, conversation_id, message_id, payload)
    return message_id


def _fresh_intake_payload(intake: CadProfileIntake) -> dict[str, object]:
    payload = intake.initial_question_payload()
    assert len(payload["questions"]) == 1
    return payload


def _legacy_combined_intake_payload(
    intake: CadProfileIntake,
) -> dict[str, object]:
    """Historical two-question payload retained for transaction rollback coverage."""
    payload = intake.initial_question_payload()
    questions = list(payload["questions"])
    questions.append(
        {
            "id": CAD_DIMENSIONS_QUESTION_ID,
            "text": "请确认盒体内腔长 × 宽 × 高，单位为毫米。",
            "mode": "text",
            "options": [],
            "allowCustomInput": True,
            "required": True,
        }
    )
    payload["questions"] = questions
    payload["question"] = questions[0]
    return payload


def _insert_assistant_message(
    db_path: Path,
    project_id: str,
    conversation_id: str,
    message_id: str,
    payload: dict[str, object] | None = None,
) -> str:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO messages (
              id, conversation_id, project_id, role, content, reasoning_content,
              status, model, error_json, usage_json, structured_payload_json,
              metadata_json, created_at, updated_at
            ) VALUES (?, ?, ?, 'assistant', '请确认', NULL, 'COMPLETED', NULL,
                      NULL, NULL, ?, NULL, ?, ?)
            """,
            (
                message_id,
                conversation_id,
                project_id,
                json.dumps(payload, ensure_ascii=False) if payload is not None else None,
                NOW,
                NOW,
            ),
        )
    return message_id
