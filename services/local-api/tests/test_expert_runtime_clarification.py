from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError

from tests.fakes import SequenceProvider
from zhangwen.experts import context_assembler as context_assembler_module
from zhangwen.experts.runtime import (
    CandidateFact,
    CandidatePendingItem,
    ExpertRuntime,
    ExpertRuntimeOutput,
    ExpertRuntimeRequest,
    ExpertRuntimeResult,
)
from zhangwen.hardware.seeds import (
    seed_default_components as production_seed_default_components,
)
from zhangwen.llm.contracts import LLMConfig, LLMErrorCode, LLMModelId
from zhangwen.llm.structured import StructuredLLMError
from zhangwen.projects.models import ExpertType, PendingItemPriority
from zhangwen.projects.repository import ProjectRepository


def _runtime_request(
    tmp_path: Path,
    expert_type: ExpertType = ExpertType.SMART_ENGINEER,
) -> tuple[ProjectRepository, ExpertRuntimeRequest]:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="Build a small sensor project",
        project_name="Runtime clarification contract",
        initial_expert=expert_type,
        participating_experts=[expert_type],
    )
    expert = workspace.experts[0]
    return repository, ExpertRuntimeRequest(
        projectId=workspace.project.id,
        projectExpertId=expert.id,
        conversationId=expert.conversationId,
        expertType=expert_type,
        userMessage="Help me decide the remaining implementation details",
        model=LLMModelId.DEEPSEEK_V4_FLASH,
    )


def _question(
    question_id: str,
    mode: str,
    *,
    required: bool = True,
) -> dict[str, object]:
    options: list[dict[str, object]] = []
    allow_custom_input = mode == "text"
    if mode in {"single", "multiple"}:
        options = [
            {"id": f"{question_id}_a", "label": "Option A", "value": "a"},
            {"id": f"{question_id}_b", "label": "Option B", "value": "b"},
        ]
    return {
        "id": question_id,
        "text": f"Choose {question_id}",
        "mode": mode,
        "options": options,
        "allowCustomInput": allow_custom_input,
        "required": required,
    }


def _clarification_output() -> dict[str, object]:
    questions = [
        _question("install_mode", "single"),
        _question("features", "multiple"),
        _question("notes", "text", required=False),
    ]
    return {
        "content": "Please confirm these implementation details.",
        "uiPayload": {
            "type": "clarification",
            "summary": "Confirm the remaining implementation details.",
            "question": copy.deepcopy(questions[0]),
            "questions": questions,
            "completeness": 45,
        },
    }


def _external_hardware_output() -> dict[str, object]:
    return {
        "content": (
            "建议采用 ESP32-WROOM-32、外接 SPI 屏幕、SD 卡模块和独立升压电源，"
            "并据此继续生成硬件方案。"
        )
    }


def _local_hardware_grounded_output() -> dict[str, object]:
    return {
        "content": (
            "已先评估本地 ACTIVE 硬件库中的行空板 K10：优先复用其板载屏幕、"
            "TF 卡槽和按键；只有当前 Skill 未覆盖的能力才进入硬件补充选择。"
        )
    }


def _hardware_code_output(*, content: str, summary: str) -> dict[str, object]:
    return {
        "content": content,
        "codeDraft": {
            "summary": summary,
            "files": [
                {
                    "path": "src/main.py",
                    "language": "python",
                    "content": "print('hardware skill code')\n",
                }
            ],
        },
    }


def _provider_pending_output(priority: str, title: str) -> dict[str, object]:
    return {
        "content": "A project item needs attention.",
        "pendingItems": [
            {
                "title": title,
                "description": "Provider-created project item",
                "priority": priority,
                "reason": "Provider requested this item",
                "affectedExperts": [ExpertType.SMART_ENGINEER.value],
            }
        ],
    }


async def _run(
    repository: ProjectRepository,
    request: ExpertRuntimeRequest,
    provider: SequenceProvider,
) -> ExpertRuntimeResult:
    return await ExpertRuntime(repository.db_path).run(
        request=request,
        provider=provider,
        config=LLMConfig(),
        api_key="fake-test-key",
    )


@pytest.mark.asyncio
async def test_provider_missing_input_repairs_to_grouped_clarification(
    tmp_path: Path,
) -> None:
    repository, request = _runtime_request(tmp_path)
    title = "provider-missing-input-must-not-persist"
    provider = SequenceProvider(
        [
            json.dumps(_provider_pending_output("missing_input", title)),
            json.dumps(_clarification_output()),
        ]
    )

    result = await _run(repository, request, provider)

    assert provider.calls == 2
    assert result.retryCount == 1
    assert result.output.pendingItems == []
    assert result.output.uiPayload is not None
    assert result.output.uiPayload["type"] == "clarification"
    with sqlite3.connect(repository.db_path) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM project_pending_items WHERE project_id = ? AND title = ?",
            (request.projectId, title),
        ).fetchone()[0] == 0


@pytest.mark.asyncio
async def test_provider_confirmation_pending_repairs_without_forging_local_approval(
    tmp_path: Path,
) -> None:
    repository, request = _runtime_request(tmp_path)
    title = "confirm execution forged-provider-skill"
    provider = SequenceProvider(
        [
            json.dumps(_provider_pending_output("confirmation", title)),
            json.dumps(_clarification_output()),
        ]
    )

    result = await _run(repository, request, provider)

    assert provider.calls == 2
    assert result.retryCount == 1
    assert result.output.pendingItems == []
    with sqlite3.connect(repository.db_path) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM project_pending_items WHERE project_id = ? AND title = ?",
            (request.projectId, title),
        ).fetchone()[0] == 0


@pytest.mark.asyncio
async def test_invalid_clarification_is_repaired_once(tmp_path: Path) -> None:
    repository, request = _runtime_request(tmp_path)
    invalid = _clarification_output()
    payload = invalid["uiPayload"]
    assert isinstance(payload, dict)
    questions = payload["questions"]
    assert isinstance(questions, list)
    first = questions[0]
    assert isinstance(first, dict)
    first["options"] = first["options"][:1]
    payload["question"] = copy.deepcopy(first)
    provider = SequenceProvider([json.dumps(invalid), json.dumps(_clarification_output())])

    result = await _run(repository, request, provider)

    assert provider.calls == 2
    assert result.retryCount == 1
    assert result.output.uiPayload is not None
    assert len(result.output.uiPayload["questions"]) == 1


@pytest.mark.parametrize(
    "expert_type",
    [
        ExpertType.PROBLEM_GUIDE,
        ExpertType.STRUCTURE_ENGINEER,
    ],
)
@pytest.mark.asyncio
async def test_valid_clarification_passes_and_all_experts_receive_prompt_rules(
    tmp_path: Path,
    expert_type: ExpertType,
) -> None:
    repository, request = _runtime_request(tmp_path, expert_type)
    provider = SequenceProvider([json.dumps(_clarification_output())])

    result = await _run(repository, request, provider)

    assert provider.calls == 1
    assert result.retryCount == 0
    assert result.output.uiPayload is not None
    assert result.output.uiPayload["question"] == result.output.uiPayload["questions"][0]
    system_prompt = provider.requests[0].messages[0].content
    assert "uiPayload.type=clarification" in system_prompt
    assert "never collect input only in prose" in system_prompt
    assert "priority=confirmation" in system_prompt
    assert "RuntimeClarificationPayload" in json.dumps(
        ExpertRuntimeOutput.model_json_schema(),
        ensure_ascii=False,
    )


@pytest.mark.parametrize("question_case", ["missing", "mismatched"])
def test_compatibility_question_is_canonicalized_from_first_question(
    question_case: str,
) -> None:
    output = _clarification_output()
    payload = output["uiPayload"]
    assert isinstance(payload, dict)
    questions = payload["questions"]
    assert isinstance(questions, list)
    if question_case == "missing":
        payload.pop("question")
    else:
        payload["question"] = _question("stale_compatibility_copy", "single")

    validated = ExpertRuntimeOutput.model_validate(output)

    assert validated.uiPayload is not None
    assert validated.uiPayload["question"] == validated.uiPayload["questions"][0]


def test_hardware_gap_payload_uses_capabilities_without_component_ids() -> None:
    validated = ExpertRuntimeOutput.model_validate(
        {
            "content": "The current project hardware does not cover every planned function.",
            "uiPayload": {
                "type": "hardware_selection",
                "summary": "Add hardware for the remaining capabilities.",
                "missingCapabilities": ["ambient light sensing", "audible reminder"],
            },
        }
    )

    assert validated.uiPayload == {
        "type": "hardware_selection",
        "summary": "Add hardware for the remaining capabilities.",
        "missingCapabilities": ["ambient light sensing", "audible reminder"],
    }
    schema = json.dumps(ExpertRuntimeOutput.model_json_schema(), ensure_ascii=False)
    assert "RuntimeHardwareSelectionPayload" in schema
    assert "missingCapabilities" in schema


@pytest.mark.parametrize(
    "invalid_payload",
    [
        {
            "type": "hardware_selection",
            "summary": "Missing a sensor.",
            "missingCapabilities": [],
        },
        {
            "type": "hardware_selection",
            "summary": "Missing a sensor.",
            "missingCapabilities": ["sensing"],
            "componentIds": ["provider_forged_id"],
        },
    ],
)
def test_hardware_gap_payload_rejects_empty_capabilities_and_provider_component_ids(
    invalid_payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        ExpertRuntimeOutput.model_validate(
            {"content": "More hardware is required.", "uiPayload": invalid_payload}
        )


@pytest.mark.parametrize(
    "expert_type",
    [
        ExpertType.PROBLEM_GUIDE,
        ExpertType.SMART_ENGINEER,
        ExpertType.STRUCTURE_ENGINEER,
    ],
)
@pytest.mark.asyncio
async def test_all_experts_receive_local_hardware_selection_prompt_rule(
    tmp_path: Path,
    expert_type: ExpertType,
) -> None:
    repository, request = _runtime_request(tmp_path, expert_type)
    provider = SequenceProvider([json.dumps(_clarification_output())])

    await _run(repository, request, provider)

    system_prompt = provider.requests[0].messages[0].content
    assert "uiPayload.type=hardware_selection" in system_prompt
    assert "must not invent component ids" in system_prompt.lower()


@pytest.mark.asyncio
async def test_smart_engineer_accepts_ntp_alarm_code_with_safe_wifi_placeholders(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ZHANGWEN_TEST_PRESERVE_RETIRED_HARDWARE", raising=False)
    monkeypatch.setattr(
        context_assembler_module,
        "seed_default_components",
        production_seed_default_components,
    )
    repository, request = _runtime_request(tmp_path)
    _, user_message, assistant_message = repository.append_user_and_assistant(
        request.projectId,
        request.userMessage,
        request.model,
        project_expert_id=request.projectExpertId,
    )
    request.requestMessageId = user_message.id
    request.responseMessageId = assistant_message.id
    provider = SequenceProvider(
        [
            json.dumps(
                {
                    "content": "已基于行空板 K10 生成联网校时与固定闹钟代码草稿。",
                    "codeDraft": {
                        "summary": "生成 K10 NTP 固定闹钟",
                        "files": [
                            {
                                "path": "src/main.py",
                                "language": "python",
                                "content": (
                                    "import network\n"
                                    "import ntptime\n\n"
                                    "WIFI_SSID = 'YOUR_WIFI_SSID'\n"
                                    "WIFI_PASSWORD = 'YOUR_WIFI_PASSWORD'\n"
                                    "alarm_time = '07-30'.replace('-', ':')\n"
                                    "print(alarm_time)\n"
                                ),
                            }
                        ],
                    },
                },
                ensure_ascii=False,
            )
        ]
    )

    result = await _run(repository, request, provider)

    assert provider.calls == 1
    assert result.retryCount == 0
    assert result.codeRun is not None
    assert result.codeRun.status.value == "DRAFT"
    system_prompt = provider.requests[0].messages[0].content
    assert "YOUR_WIFI_PASSWORD" in system_prompt


@pytest.mark.parametrize(
    "expert_type",
    [
        ExpertType.PROBLEM_GUIDE,
        ExpertType.STRUCTURE_ENGINEER,
    ],
)
@pytest.mark.asyncio
async def test_problem_and_structure_experts_repair_hardware_reasoning_that_skips_active_library(
    tmp_path: Path,
    expert_type: ExpertType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ZHANGWEN_TEST_PRESERVE_RETIRED_HARDWARE", raising=False)
    monkeypatch.setattr(
        context_assembler_module,
        "seed_default_components",
        production_seed_default_components,
    )
    repository, request = _runtime_request(tmp_path, expert_type)
    request.userMessage = "请为电子相册推荐主控、屏幕、供电和结构适配方案。"
    provider = SequenceProvider(
        [
            json.dumps(_external_hardware_output(), ensure_ascii=False),
            json.dumps(_local_hardware_grounded_output(), ensure_ascii=False),
        ]
    )

    result = await _run(repository, request, provider)

    assert provider.calls == 2
    assert result.retryCount == 1
    assert "行空板 K10" in result.output.content
    system_prompt = provider.requests[0].messages[0].content
    assert "preferred_project_hardware" in system_prompt
    assert "local_hardware_library" in system_prompt
    context_prompt = provider.requests[0].messages[1].content
    assert '"hardwareKnowledgePolicy"' in context_prompt
    assert '"name": "行空板 K10"' in context_prompt
    repair_prompt = provider.requests[1].messages[-1].content
    assert "本地 ACTIVE 硬件库" in repair_prompt


@pytest.mark.asyncio
async def test_smart_engineer_hardware_grounding_is_advisory_while_facts_are_incomplete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ZHANGWEN_TEST_PRESERVE_RETIRED_HARDWARE", raising=False)
    monkeypatch.setattr(
        context_assembler_module,
        "seed_default_components",
        production_seed_default_components,
    )
    repository, request = _runtime_request(tmp_path, ExpertType.SMART_ENGINEER)
    request.userMessage = "请为电子相册给出当前可行的硬件实现方案。"
    provider = SequenceProvider(
        [json.dumps(_external_hardware_output(), ensure_ascii=False)]
    )

    result = await _run(repository, request, provider)

    assert provider.calls == 1
    assert result.retryCount == 0
    assert "ESP32-WROOM-32" in result.output.content
    context_prompt = provider.requests[0].messages[1].content
    assert '"hardwareKnowledgePolicy"' in context_prompt
    assert '"name": "行空板 K10"' in context_prompt


@pytest.mark.asyncio
async def test_smart_engineer_code_draft_repairs_when_it_skips_local_hardware_skill(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ZHANGWEN_TEST_PRESERVE_RETIRED_HARDWARE", raising=False)
    monkeypatch.setattr(
        context_assembler_module,
        "seed_default_components",
        production_seed_default_components,
    )
    repository, request = _runtime_request(tmp_path, ExpertType.SMART_ENGINEER)
    request.userMessage = "请为电子相册生成可上传的 MicroPython 代码。"
    _, user_message, assistant_message = repository.append_user_and_assistant(
        request.projectId,
        request.userMessage,
        request.model,
        project_expert_id=request.projectExpertId,
    )
    request.requestMessageId = user_message.id
    request.responseMessageId = assistant_message.id
    provider = SequenceProvider(
        [
            json.dumps(
                _hardware_code_output(
                    content="已直接按外部 ESP32-WROOM-32 示例生成代码。",
                    summary="外部示例代码",
                ),
                ensure_ascii=False,
            ),
            json.dumps(
                _hardware_code_output(
                    content=(
                        "已先读取本地 ACTIVE Hardware Skill 中的行空板 K10 当前 revision，"
                        "再生成对应的 MicroPython 代码草稿。"
                    ),
                    summary="基于行空板 K10 Hardware Skill 的代码",
                ),
                ensure_ascii=False,
            ),
        ]
    )

    result = await _run(repository, request, provider)

    assert provider.calls == 2
    assert result.retryCount == 1
    assert result.codeRun is not None
    context_prompt = provider.requests[0].messages[1].content
    assert '"hardwareSkillMarkdown"' in context_prompt
    assert '"skillRevision"' in context_prompt
    assert '"name": "行空板 K10"' in context_prompt
    repair_prompt = provider.requests[1].messages[-1].content
    assert "本地 ACTIVE 硬件库" in repair_prompt


@pytest.mark.asyncio
async def test_k10_code_draft_repairs_when_selected_reference_template_is_ignored(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ZHANGWEN_TEST_PRESERVE_RETIRED_HARDWARE", raising=False)
    monkeypatch.setattr(
        context_assembler_module,
        "seed_default_components",
        production_seed_default_components,
    )
    repository, request = _runtime_request(tmp_path, ExpertType.SMART_ENGINEER)
    request.userMessage = "请使用行空板 K10 摄像头进行实时预览并生成代码。"
    _, user_message, assistant_message = repository.append_user_and_assistant(
        request.projectId,
        request.userMessage,
        request.model,
        project_expert_id=request.projectExpertId,
    )
    request.requestMessageId = user_message.id
    request.responseMessageId = assistant_message.id
    misleading = _hardware_code_output(
        content="已使用行空板 K10 Hardware Skill 生成 AI 摄像头代码。",
        summary="行空板 K10 AI 摄像头预览",
    )
    misleading["codeDraft"]["files"][0]["content"] = (
        "import time\n"
        "import ai\n"
        "from unihiker_k10 import screen\n\n"
        "ai.init_ai()\n"
        "ai.camera_start()\n"
        "screen.init(dir=2)\n"
        "while True:\n"
        "    frame = ai.camera_capture()\n"
        "    screen.show_camera_img(frame)\n"
        "    time.sleep_ms(20)\n"
    )
    grounded = _hardware_code_output(
        content=(
            "已使用行空板 K10 Hardware Skill，并以 "
            "templates/14_camera_preview.py 为参考骨架生成预览代码。"
        ),
        summary="基于 K10 Camera 参考模板的实时预览",
    )
    grounded["codeDraft"]["files"][0]["content"] = (
        "import time\n"
        "from k10_base import Camera\n"
        "from unihiker_k10 import screen\n\n"
        "camera = Camera()\n"
        "screen.init(dir=2)\n"
        "camera.init()\n"
        "screen.show_camera(camera)\n"
        "while True:\n"
        "    time.sleep(1)\n"
    )
    provider = SequenceProvider(
        [
            json.dumps(misleading, ensure_ascii=False),
            json.dumps(grounded, ensure_ascii=False),
        ]
    )

    result = await _run(repository, request, provider)

    assert provider.calls == 2
    assert result.retryCount == 1
    assert result.codeRun is not None
    reference_message = next(
        message.content
        for message in provider.requests[0].messages
        if "K10 当前需求参考代码契约" in message.content
    )
    assert "templates/14_camera_preview.py" in reference_message
    assert "screen.show_camera(camera)" in reference_message
    repair_prompt = provider.requests[1].messages[-1].content
    assert "templates/14_camera_preview.py" in repair_prompt
    assert "k10_base:Camera" in repair_prompt
    assert "screen.show_camera" in repair_prompt


@pytest.mark.asyncio
async def test_k10_camera_photo_request_rejects_fake_capture_success_claim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ZHANGWEN_TEST_PRESERVE_RETIRED_HARDWARE", raising=False)
    monkeypatch.setattr(
        context_assembler_module,
        "seed_default_components",
        production_seed_default_components,
    )
    repository, request = _runtime_request(tmp_path, ExpertType.SMART_ENGINEER)
    request.userMessage = "使用行空板 K10 摄像头拍照。"
    _, user_message, assistant_message = repository.append_user_and_assistant(
        request.projectId,
        request.userMessage,
        request.model,
        project_expert_id=request.projectExpertId,
    )
    request.requestMessageId = user_message.id
    request.responseMessageId = assistant_message.id
    fake_capture = _hardware_code_output(
        content="已使用行空板 K10 Hardware Skill，按 A 键后照片已保存。",
        summary="K10 拍照完成并保存照片",
    )
    fake_capture["codeDraft"]["files"][0]["content"] = (
        "import ai\n"
        "from unihiker_k10 import screen\n"
        "ai.init_ai()\n"
        "ai.camera_start()\n"
        "frame = ai.camera_capture()\n"
        "screen.show_camera_img(frame)\n"
        "print('Photo captured')\n"
    )
    verified_preview = _hardware_code_output(
        content=(
            "已使用行空板 K10 Hardware Skill 和 templates/14_camera_preview.py。"
            "当前 Skill 未验证静态照片编码与保存，所以本草稿只交付已证实的实时预览，"
            "不声称拍照成功或照片已保存。"
        ),
        summary="K10 已验证摄像头预览；静态照片保存待受信参考",
    )
    verified_preview["codeDraft"]["files"][0]["content"] = (
        "import time\n"
        "from k10_base import Camera\n"
        "from unihiker_k10 import screen\n\n"
        "camera = Camera()\n"
        "screen.init(dir=2)\n"
        "camera.init()\n"
        "screen.show_camera(camera)\n"
        "while True:\n"
        "    time.sleep(1)\n"
    )
    provider = SequenceProvider(
        [
            json.dumps(fake_capture, ensure_ascii=False),
            json.dumps(verified_preview, ensure_ascii=False),
        ]
    )

    result = await _run(repository, request, provider)

    assert provider.calls == 2
    assert result.retryCount == 1
    assert result.codeRun is not None
    assert "只交付已证实的实时预览" in result.output.content
    repair_prompt = provider.requests[1].messages[-1].content
    assert "k10-camera-still-image-save" in repair_prompt
    assert "不得声称照片已拍摄或保存成功" in repair_prompt


@pytest.mark.asyncio
async def test_structure_terms_do_not_trigger_hardware_selection_grounding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ZHANGWEN_TEST_PRESERVE_RETIRED_HARDWARE", raising=False)
    monkeypatch.setattr(
        context_assembler_module,
        "seed_default_components",
        production_seed_default_components,
    )
    repository, request = _runtime_request(tmp_path, ExpertType.STRUCTURE_ENGINEER)
    provider = SequenceProvider(
        [
            json.dumps(
                {
                    "content": (
                        "传感器模块安装在壳体内侧，接口开孔应保留装配间隙，"
                        "建议采用加强筋改善传感器安装处的局部结构刚度。"
                    )
                },
                ensure_ascii=False,
            )
        ]
    )

    result = await _run(repository, request, provider)

    assert provider.calls == 1
    assert result.retryCount == 0
    assert "接口开孔" in result.output.content


@pytest.mark.asyncio
async def test_repeated_local_hardware_rejection_has_local_error_classification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ZHANGWEN_TEST_PRESERVE_RETIRED_HARDWARE", raising=False)
    monkeypatch.setattr(
        context_assembler_module,
        "seed_default_components",
        production_seed_default_components,
    )
    repository, request = _runtime_request(tmp_path, ExpertType.STRUCTURE_ENGINEER)
    request.userMessage = "请推荐主控、屏幕、供电和结构适配方案。"
    invalid = json.dumps(_external_hardware_output(), ensure_ascii=False)
    provider = SequenceProvider([invalid, invalid])

    with pytest.raises(StructuredLLMError) as exc_info:
        await _run(repository, request, provider)

    assert provider.calls == 2
    assert exc_info.value.error.code == LLMErrorCode.LOCAL_OUTPUT_REJECTED
    assert exc_info.value.error.message == (
        "生成结果未通过当前工程约束或安全边界，未写入工程产物。"
        "原需求本身不需要修改，可按原需求重新生成。"
    )
    with sqlite3.connect(repository.db_path) as conn:
        error = conn.execute(
            "SELECT error FROM expert_runs WHERE project_id = ? ORDER BY created_at DESC",
            (request.projectId,),
        ).fetchone()[0]
    assert "local_output_rejected after 2 attempts" in error
    assert "ESP32-WROOM-32" not in error


@pytest.mark.parametrize(
    "case",
    [
        "wrong_type",
        "empty_questions",
        "duplicate_question_id",
        "invalid_mode",
        "missing_required",
        "invalid_selection_options",
        "invalid_completeness",
    ],
)
def test_clarification_schema_rejects_contract_violations(case: str) -> None:
    output = _clarification_output()
    payload = output["uiPayload"]
    assert isinstance(payload, dict)
    questions = payload["questions"]
    assert isinstance(questions, list)

    if case == "wrong_type":
        payload["type"] = "clarify"
    elif case == "empty_questions":
        payload["questions"] = []
    elif case == "duplicate_question_id":
        second = questions[1]
        assert isinstance(second, dict)
        second["id"] = questions[0]["id"]
    elif case == "invalid_mode":
        questions[0]["mode"] = "choice"
        payload["question"] = copy.deepcopy(questions[0])
    elif case == "missing_required":
        questions[0].pop("required")
        payload["question"] = copy.deepcopy(questions[0])
    elif case == "invalid_selection_options":
        questions[0]["options"] = questions[0]["options"][:1]
        payload["question"] = copy.deepcopy(questions[0])
    elif case == "invalid_completeness":
        payload["completeness"] = 101

    with pytest.raises(ValidationError):
        ExpertRuntimeOutput.model_validate(output)


@pytest.mark.asyncio
async def test_failed_run_persists_sanitized_validation_diagnostic(
    tmp_path: Path,
) -> None:
    repository, request = _runtime_request(tmp_path)
    invalid = _clarification_output()
    payload = invalid["uiPayload"]
    assert isinstance(payload, dict)
    payload["questions"] = []
    invalid["content"] = "MODEL-OUTPUT-MUST-NOT-BE-PERSISTED"
    provider = SequenceProvider([json.dumps(invalid), json.dumps(invalid)])

    with pytest.raises(StructuredLLMError) as exc_info:
        await _run(repository, request, provider)

    assert exc_info.value.error.message == (
        "云端返回的结构化内容连续两次不完整。原需求已保留，可直接重新生成；"
        "若反复出现，请检查模型设置。"
    )
    with sqlite3.connect(repository.db_path) as conn:
        error = conn.execute(
            "SELECT error FROM expert_runs WHERE project_id = ? ORDER BY created_at DESC",
            (request.projectId,),
        ).fetchone()[0]
    assert "structured_validation_failed" in error
    assert "questions" in error
    assert "MODEL-OUTPUT-MUST-NOT-BE-PERSISTED" not in error


@pytest.mark.parametrize("priority", ["blocking", "conflict", "safety"])
@pytest.mark.asyncio
async def test_provider_work_summary_pending_priorities_remain_allowed(
    tmp_path: Path,
    priority: str,
) -> None:
    repository, request = _runtime_request(tmp_path)
    title = f"provider-{priority}-summary"
    provider = SequenceProvider(
        [json.dumps(_provider_pending_output(priority, title))]
    )

    result = await _run(repository, request, provider)

    assert provider.calls == 1
    assert result.output.pendingItems[0].priority.value == priority
    with sqlite3.connect(repository.db_path) as conn:
        stored = conn.execute(
            "SELECT priority FROM project_pending_items WHERE project_id = ? AND title = ?",
            (request.projectId, title),
        ).fetchone()
    assert stored == (priority,)


@pytest.mark.asyncio
async def test_local_missing_expert_pending_items_remain_available(tmp_path: Path) -> None:
    repository, request = _runtime_request(tmp_path)
    provider = SequenceProvider(
        [
            json.dumps(
                {
                    "content": "Prepared work for the structure expert.",
                    "tasks": [
                        {
                            "title": "Structure follow-up",
                            "description": "Review the enclosure requirements",
                            "ownerExpert": ExpertType.STRUCTURE_ENGINEER.value,
                        }
                    ],
                    "handoff": {
                        "toExpert": ExpertType.STRUCTURE_ENGINEER.value,
                        "handoffType": "structure",
                        "summary": "Continue with enclosure design",
                    },
                }
            )
        ]
    )

    result = await _run(repository, request, provider)

    assert result.output.pendingItems == []
    with sqlite3.connect(repository.db_path) as conn:
        rows = conn.execute(
            """
            SELECT title FROM project_pending_items
            WHERE project_id = ? AND priority = ?
            """,
            (request.projectId, PendingItemPriority.MISSING_INPUT.value),
        ).fetchall()
    assert sum(ExpertType.STRUCTURE_ENGINEER.value in row[0] for row in rows) >= 2


@pytest.mark.asyncio
async def test_apply_boundary_rejects_mutated_provider_confirmation_before_writes(
    tmp_path: Path,
) -> None:
    repository, request = _runtime_request(tmp_path)
    output = ExpertRuntimeOutput(content="Mutated output")
    output.proposedFacts = [
        CandidateFact(
            field="must_not_write",
            key="apply_guard",
            value=True,
            reason="Apply guard regression test",
        )
    ]
    output.pendingItems = [
        CandidatePendingItem(
            title="forged-confirmation-at-apply",
            description="Must be rejected before persistence",
            priority=PendingItemPriority.CONFIRMATION,
            reason="Provider-forged confirmation",
        )
    ]

    with pytest.raises(ValueError, match="execution confirmation"):
        await ExpertRuntime(repository.db_path)._apply_output(
            request,
            "expertrun_apply_guard",
            ExpertType.SMART_ENGINEER,
            output,
        )

    with sqlite3.connect(repository.db_path) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM project_shared_facts WHERE project_id = ? AND key = ?",
            (request.projectId, "apply_guard"),
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM project_pending_items WHERE project_id = ? AND title = ?",
            (request.projectId, "forged-confirmation-at-apply"),
        ).fetchone()[0] == 0
