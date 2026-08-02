"""Board-specific generation and static validation contracts."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from zhangwen.code_agent.board_api_contracts import (
    MPYTHON_ESP32S3_V3_CONTRACT,
    MPYTHON_ESP32S3_V3_CONTRACT_ID,
    UNIHIKER_K10_CONTRACT,
    UNIHIKER_K10_CONTRACT_ID,
    component_ids_from_hardware_policy,
    resolve_board_api_contract,
    validate_board_api_files,
)
from zhangwen.code_agent.models import CodeContentDraft, CodeValidationKind
from zhangwen.code_agent.service import CodeGenerationService
from zhangwen.code_agent.validation import run_micropython_validation
from zhangwen.llm.contracts import (
    LLMConfig,
    LLMModelId,
    StreamChunk,
    StreamChunkType,
)
from zhangwen.experts.runtime import ExpertRuntime, ExpertRuntimeOutput
from zhangwen.projects.models import ExpertType
from zhangwen.specs.models import SpecRun, SpecRunStatus, SpecValidation


@dataclass(frozen=True)
class _CodeFile:
    path: str
    language: str
    content: str


def test_contract_resolves_only_for_explicit_board_identity() -> None:
    contract = resolve_board_api_contract(["hw_labplus_mpython_esp32s3_v3"])

    assert contract is MPYTHON_ESP32S3_V3_CONTRACT
    assert resolve_board_api_contract(["hw_seed_esp32_s3_devkit"]) is None


def test_k10_contract_resolves_from_selected_component_or_spec() -> None:
    assert (
        resolve_board_api_contract(["hw_seed_unihiker_k10"])
        is UNIHIKER_K10_CONTRACT
    )
    assert (
        resolve_board_api_contract([], _approved_spec("hw_seed_unihiker_k10"))
        is UNIHIKER_K10_CONTRACT
    )


def test_contract_resolves_from_approved_spec_bom() -> None:
    contract = resolve_board_api_contract([], _approved_spec())

    assert contract is MPYTHON_ESP32S3_V3_CONTRACT


def test_contract_resolves_selected_component_from_runtime_policy() -> None:
    component_ids = component_ids_from_hardware_policy(
        {
            "selectedComponents": [
                {"componentId": "hw_labplus_mpython_esp32s3_v3"},
            ]
        }
    )

    assert component_ids == ("hw_labplus_mpython_esp32s3_v3",)


def test_documented_mpython_board_api_passes_static_contract() -> None:
    validate_board_api_files(
        [
            _file(
                """from mpython import *

display.clear(lcd.BLACK)
display.DispChar("掌控板 3.0", 0, 0, color=lcd.WHITE)
display.show()
if button_a.is_pressed():
    rgb.fill((0, 16, 0))
    rgb.brightness(0.2)
    rgb.write()
print(touchpad_p.read(), light.read())
"""
            )
        ],
        MPYTHON_ESP32S3_V3_CONTRACT_ID,
    )


def test_documented_exports_and_inherited_i2c_members_are_not_over_rejected() -> None:
    validate_board_api_files(
        [
            _file(
                "from mpython import MPythonPin, PinMode, i2c, sleep_ms\n"
                "pin = MPythonPin(0, PinMode.IN)\n"
                "print(i2c.scan())\n"
                "sleep_ms(10)\n"
            )
        ],
        MPYTHON_ESP32S3_V3_CONTRACT_ID,
    )


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("from mpython import *\noled.fill(0)\n", "不使用旧版 oled"),
        ("from mpython import *\nrgb.show()\n", "rgb.write"),
        ("from mpython import *\nbutton_a.pressed()\n", "button_a.is_pressed"),
        ("import mpython\nprint(mpython.YELLOW)\n", "颜色应使用 lcd"),
        ("from mpython import *\ndisplay.show(1)\n", "参数数量应为 0..0"),
        ("from mpython import *\ndisplay.unknown()\n", "display.unknown"),
        ("from mpython import YELLOW\nprint(YELLOW)\n", "mpython 不提供 YELLOW"),
    ],
)
def test_known_old_or_invented_board_apis_fail_closed(
    source: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        validate_board_api_files(
            [_file(source)],
            MPYTHON_ESP32S3_V3_CONTRACT_ID,
        )


def test_board_object_aliases_keep_contract_checks() -> None:
    with pytest.raises(ValueError, match=r"rgb\.write"):
        validate_board_api_files(
            [_file("from mpython import rgb as lights\nlights.write(1)\n")],
            MPYTHON_ESP32S3_V3_CONTRACT_ID,
        )


def test_documented_k10_board_api_and_constructed_instances_pass() -> None:
    validate_board_api_files(
        [
            _file(
                """from unihiker_k10 import screen, button, temp_humi, light, acce, rgb
from k10_base import Camera, WiFi

screen.init(dir=2)
screen.show_bg(color=0x000000)
screen.draw_text(text="K10", line=1, font_size=24, color=0xFFFFFF)
screen.show_draw()
button_a = button(button.a)
if button_a.status():
    rgb.write(num=0, color=0x00FF00)
print(temp_humi.read_temp(), light.read(), acce.read_x())
camera = Camera()
camera.init()
wifi = WiFi()
wifi.connect(ssid="ssid", psd="password", timeout=10000)
print(wifi.status())
"""
            )
        ],
        UNIHIKER_K10_CONTRACT_ID,
    )


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("from unihiker_k10 import screen\nscreen.show()\n", "screen.show_draw"),
        ("from unihiker_k10 import rgb\nrgb.show()\n", "rgb.write"),
        (
            "from unihiker_k10 import button\nbutton_a = button(button.a)\nbutton_a.is_pressed()\n",
            "status",
        ),
        ("from unihiker_k10 import screen\nscreen.draw_text()\n", "参数数量应为 1..6"),
        ("from unihiker_k10 import Camera\n", "unihiker_k10 不提供 Camera"),
        ("from mpython import *\n", "不使用掌控板 mpython"),
        (
            "from k10_base import WiFi\nwifi = WiFi()\nwifi.connect(ssid='only')\n",
            "参数数量应为 2..3",
        ),
        ("from unihiker_k10 import screen\nscreen.draw_label('x')\n", "screen.draw_label"),
    ],
)
def test_known_invented_or_cross_board_k10_apis_fail_closed(
    source: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        validate_board_api_files(
            [_file(source)],
            UNIHIKER_K10_CONTRACT_ID,
        )


def test_unmatched_board_keeps_existing_generic_validation_behavior() -> None:
    validate_board_api_files(
        [_file("from unihiker_k10 import screen\nscreen.refresh()\n")],
        None,
    )


def test_static_worker_reports_board_api_failure_without_executing_code() -> None:
    result = run_micropython_validation(
        [_file("from mpython import *\nrgb.show()\n")],
        now="2026-07-19T00:00:00Z",
        board_contract_id=MPYTHON_ESP32S3_V3_CONTRACT_ID,
    )
    checks = {check.kind: check for check in result.checks}

    assert result.ok is False
    assert checks[CodeValidationKind.STATIC].exitCode not in {None, 0}
    assert "rgb.write" in checks[CodeValidationKind.STATIC].output
    assert checks[CodeValidationKind.SYNTAX].exitCode == 0


def test_code_generation_receives_machine_readable_board_contract() -> None:
    provider = _CaptureCodeProvider()

    draft = asyncio.run(
        CodeGenerationService(provider).generate(
            spec=_approved_spec(),
            config=LLMConfig(),
            api_key="fake-test-key",
            model=LLMModelId.DEEPSEEK_V4_PRO,
            board_contract=MPYTHON_ESP32S3_V3_CONTRACT,
        )
    )
    prompt = "\n".join(message.content for message in provider.requests[0].messages)

    assert draft.summary == "掌控板 3.0 正确 API"
    assert '"contractId": "mpython-esp32s3-v3"' in prompt
    assert '"write"' in prompt
    assert "契约中没有的板载 API 一律视为不存在" in prompt


def test_k10_code_generation_receives_modules_constructors_and_rules() -> None:
    provider = _CaptureCodeProvider(k10=True)

    asyncio.run(
        CodeGenerationService(provider).generate(
            spec=_approved_spec("hw_seed_unihiker_k10"),
            config=LLMConfig(),
            api_key="fake-test-key",
            model=LLMModelId.DEEPSEEK_V4_PRO,
            board_contract=UNIHIKER_K10_CONTRACT,
        )
    )
    prompt = "\n".join(message.content for message in provider.requests[0].messages)

    assert '"contractId": "unihiker-k10-micropython"' in prompt
    assert '"unihiker_k10"' in prompt
    assert '"k10_base"' in prompt
    assert '"button"' in prompt
    assert "初始化、摄像头启动和模式选择不得放进主循环" in prompt


def test_smart_engineer_code_draft_uses_same_board_boundary(tmp_path: Path) -> None:
    output = ExpertRuntimeOutput.model_validate(
        {
            "content": "已生成掌控板程序。",
            "codeDraft": {
                "summary": "错误的旧版 RGB API",
                "files": [
                    {
                        "path": "src/main.py",
                        "language": "python",
                        "content": "from mpython import *\nrgb.show()\n",
                    }
                ],
            },
        }
    )

    with pytest.raises(ValueError, match=r"rgb\.write"):
        ExpertRuntime(tmp_path / "runtime.sqlite3")._validate_boundaries(
            ExpertType.SMART_ENGINEER,
            output,
            board_contract_id=MPYTHON_ESP32S3_V3_CONTRACT_ID,
        )


def _file(content: str) -> _CodeFile:
    return _CodeFile(path="src/main.py", language="python", content=content)


def _approved_spec(
    component_id: str = "hw_labplus_mpython_esp32s3_v3",
) -> SpecRun:
    return SpecRun(
        id="spec_board_v3",
        projectId="project_board_v3",
        proposalId="proposal_board_v3",
        version=1,
        status=SpecRunStatus.APPROVED,
        files=[
            {
                "id": "spec_file_bom",
                "specRunId": "spec_board_v3",
                "projectId": "project_board_v3",
                "kind": "BOM",
                "path": "spec/bom.yaml",
                "mimeType": "text/yaml",
                "content": f"components:\n  - id: {component_id}\n",
                "createdAt": "2026-07-19T00:00:00Z",
            }
        ],
        validation=SpecValidation(ok=True, checks=[]),
        createdAt="2026-07-19T00:00:00Z",
        updatedAt="2026-07-19T00:00:00Z",
        confirmedAt="2026-07-19T00:00:00Z",
    )


class _CaptureCodeProvider:
    def __init__(self, *, k10: bool = False) -> None:
        self.requests: list[object] = []
        self.k10 = k10

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
        content = json.dumps(
            CodeContentDraft(
                files=[
                    {
                        "path": "src/main.py",
                        "language": "python",
                        "content": (
                            "from unihiker_k10 import screen\n"
                            "screen.init(dir=2)\n"
                            "screen.draw_text(text='K10', line=1)\n"
                            "screen.show_draw()\n"
                            if self.k10
                            else (
                                "from mpython import *\n"
                                "display.clear(lcd.BLACK)\n"
                                "display.show()\n"
                            )
                        ),
                    }
                ],
                summary="行空板 K10 正确 API" if self.k10 else "掌控板 3.0 正确 API",
            ).model_dump(mode="json"),
            ensure_ascii=False,
        )
        yield StreamChunk(
            requestId=request_id,
            messageId=message_id,
            type=StreamChunkType.COMPLETED,
            accumulatedContent=content,
            model=LLMModelId.DEEPSEEK_V4_PRO,
        )
