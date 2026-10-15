"""Explicit local fake Provider for free Web interaction validation.

This module is never selected as a production fallback. It is enabled only when
``ZHANGWEN_LLM_TEST_MODE=fake`` is set by the dedicated development launcher.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator

from zhangwen.llm.contracts import (
    ChatRequest,
    ConnectionTestResult,
    LLMConfig,
    StreamChunk,
    StreamChunkType,
)
from zhangwen.config import LLMTestMode, current_llm_test_mode
from zhangwen.llm.deepseek import DeepSeekProvider
from zhangwen.llm.gateway import CancelToken, LLMProvider


def create_provider() -> LLMProvider:
    if current_llm_test_mode() == LLMTestMode.FAKE:
        return DevelopmentFakeProvider()
    return DeepSeekProvider()


class DevelopmentFakeProvider:
    """Deterministic structured replies for local, non-production UI checks."""

    async def test_connection(
        self,
        config: LLMConfig,
        api_key: str,
    ) -> ConnectionTestResult:
        _ = api_key
        return ConnectionTestResult(
            ok=True,
            message="本地 Fake Provider 已连接；不会产生模型费用。",
            provider=config.provider,
            model=config.defaultModel,
            latencyMs=0,
        )

    async def stream_chat(
        self,
        request: ChatRequest,
        config: LLMConfig,
        api_key: str,
        cancel_token: CancelToken,
        request_id: str,
        message_id: str,
    ) -> AsyncIterator[StreamChunk]:
        _ = api_key
        model = request.model or config.defaultModel
        if cancel_token.canceled:
            return
        content = json.dumps(
            _structured_reply(request),
            ensure_ascii=False,
        )
        yield StreamChunk(
            requestId=request_id,
            messageId=message_id,
            type=StreamChunkType.COMPLETED,
            accumulatedContent=content,
            model=model,
        )


def _structured_reply(request: ChatRequest) -> dict[str, object]:
    system_prompt = request.messages[0].content if request.messages else ""
    user_prompt = request.messages[-1].content if request.messages else ""

    if "掌问作品画布规划器" in system_prompt:
        return _canvas_plan_reply(user_prompt)

    if "入口主路由" in system_prompt:
        idea = _entry_idea(user_prompt)
        smart = _contains_any(
            idea,
            ("esp32", "传感器", "温湿度", "硬件", "代码", "mqtt", "联网"),
        )
        structure = _contains_any(
            idea,
            ("3d", "外壳", "结构", "打印", "stl", "装配"),
        )
        recommended = ["problem_guide"]
        if smart:
            recommended.append("smart_engineer")
        if structure:
            recommended.append("structure_engineer")
        return {
            "intent": "clarify_project_idea",
            "projectName": _project_name(idea),
            "initialExpert": "problem_guide",
            "recommendedExperts": recommended,
            "confidence": 0.98,
            "reason": "本地 Fake Provider 根据需求领域推荐参与智能体，仅用于 Web 交互验证。",
            "requiresClarification": True,
        }

    if "需求澄清助手" in system_prompt:
        return {
            "questions": [
                {
                    "id": "fake_primary_scene",
                    "type": "SINGLE_SELECT",
                    "question": "这个作品首先用于哪个场景？",
                    "options": [
                        {"id": "home", "label": "家庭或个人创作"},
                        {"id": "classroom", "label": "课堂或社团"},
                    ],
                }
            ],
            "completeness": 55,
            "message": "这是本地 Fake Provider 的澄清回复，不会调用付费模型。",
        }

    if "方案生成助手" in system_prompt:
        return {"sections": _solution_sections()}

    if "方案修订助手" in system_prompt:
        return {
            "revisedSolution": {"sections": _solution_sections()},
            "changedSections": [
                {
                    "sectionId": "structure",
                    "sectionTitle": "结构方案",
                    "changeType": "updated",
                    "before": "当前结构方案",
                    "after": "桌面外壳包含屏幕开孔、传感器通风孔和可拆后盖。",
                    "reason": "用于本地 Web 修订交互验证。",
                }
            ],
            "preservedSections": ["项目目标", "实现逻辑", "硬件方案"],
            "impactSummary": ["本地 Fake Provider 更新了结构方案。"],
            "requiresProposalUpdate": True,
        }

    if "你是“掌问”的智能工程师" in system_prompt:
        return {
            "content": "智能工程师：我会基于共享项目上下文，先核对 ESP32-S3、传感器、OLED 和供电兼容性，再给出 IO 与接线建议。",
        }

    if "你是“掌问”的结构工程师" in system_prompt:
        return {
            "content": "结构工程师：我已读取同一项目的硬件与尺寸知识，将围绕屏幕开孔、通风、装配间隙和可打印性设计桌面外壳。",
        }

    if "你是“掌问”的问题引导师" in system_prompt:
        return {
            "content": "问题引导师：我会继续整理目标、场景和验收标准，并把已确认内容写入共享项目上下文。",
        }

    return {"content": "本地 Fake Provider 已完成这次 Web 交互验证回复。"}


def _canvas_plan_reply(user_prompt: str) -> dict[str, object]:
    try:
        payload = json.loads(user_prompt)
    except json.JSONDecodeError:
        payload = {}
    context = str(payload.get("currentWorkContext", ""))
    name = str(payload.get("workName", "本地预览作品"))
    lowered = context.casefold()
    watering = _contains_any(lowered, ("浇花", "浇水", "水泵", "pump", "土壤"))
    reminder = _contains_any(lowered, ("提醒", "喝水", "定时", "timer"))
    if watering:
        scene_kind, subject_kind = "PLANT", "PLANTER"
        subject_label, environment_label = "智能花盆", "花盆旁"
        input_label, behavior = "土壤湿度", "判断土壤是否干燥，并限制连续浇水"
        output_label, action_label = "显示土壤状态", "驱动水泵"
        physical_actions = [action_label]
        constraints = ["默认离线优先，不自动开放网络", "水泵必须有独立供电、保护和异常停止策略"]
    elif reminder:
        scene_kind, subject_kind = "DESK", "REMINDER"
        subject_label, environment_label = "桌面提醒器", "书桌上"
        input_label, behavior = "时间条件", "到达设定时间后给出温和提醒"
        output_label, action_label = "给出可见提醒", behavior
        physical_actions = []
        constraints = ["默认离线优先，不自动开放网络"]
    else:
        scene_kind, subject_kind = "GENERIC", "GENERIC"
        subject_label, environment_label = name, "预期使用场景"
        input_label, behavior = "用户给出的内容或操作", "根据输入形成当前作品结果"
        output_label, action_label = "产生用户可以观察的结果", behavior
        physical_actions = []
        constraints = ["默认离线优先，不自动开放网络"]
    summary = context[:600] or f"{subject_label}会根据输入形成可以观察的结果。"
    parts: list[dict[str, str]] = [
        {"role": "SUBJECT", "label": subject_label, "description": summary},
        {"role": "INPUT", "label": input_label, "description": "作品读取这一触发信息。"},
        {"role": "DECISION", "label": behavior, "description": "作品依据输入判断下一步。"},
        {"role": "RESULT", "label": output_label, "description": "使用者能够观察这一结果。"},
    ]
    if physical_actions:
        parts.extend(
            [
                {"role": "ACTION", "label": action_label, "description": "真实执行前保留确认。"},
                {"role": "POWER", "label": "独立安全供电", "description": "受保护供电和停止策略。"},
            ]
        )
    return {
        "projectSummary": summary,
        "users": ["作品使用者"],
        "environments": [environment_label],
        "inputs": [input_label],
        "behaviors": [behavior],
        "outputs": [output_label],
        "physicalActions": physical_actions,
        "serviceNeeds": [],
        "structureNeeds": [],
        "constraints": constraints,
        "unknowns": ["具体实现载体仍需与本机能力包匹配"],
        "criticalQuestion": "你希望优先使用手边的哪件设备？",
        "confidence": 0.86,
        "scene": {
            "kind": scene_kind,
            "title": name,
            "description": summary,
            "environment": {
                "kind": "HOME" if watering else "DESKTOP" if reminder else "GENERIC",
                "label": environment_label,
                "description": f"作品放在{environment_label}使用。",
            },
            "subject": {"kind": subject_kind, "label": subject_label, "description": summary},
            "actors": [{"kind": "PERSON", "label": "作品使用者", "role": "触发作品并观察结果"}],
            "visualParts": parts,
            "stateNarratives": {
                "idle": f"{subject_label}正在等待触发。",
                "triggered": f"作品观察到{input_label}。",
                "deciding": behavior,
                "acting": f"作品正在{action_label}。",
                "result": f"使用者可以观察到{output_label}。",
                "fault": "发生异常时停止动作并等待使用者检查。",
            },
            "flow": {
                "trigger": f"读取{input_label}",
                "decide": "形成当前判断",
                "act": f"执行{action_label}",
                "result": f"呈现{output_label}",
                "fault": "异常时安全停止",
            },
            "composition": "WIDE_CONTEXT" if watering else "CENTERED",
            "accessibilityNarrative": f"画面位于{environment_label}，中心是{subject_label}。当{input_label}出现时，作品会{behavior}，最终{output_label}。",
        },
    }


def _entry_idea(prompt: str) -> str:
    match = re.search(r"用户项目想法：\s*(.+?)(?:\n用户已经明确选择|$)", prompt, re.S)
    return match.group(1).strip() if match else prompt.strip()


def _solution_sections() -> list[dict[str, str]]:
    return [
        {"id": "goal", "title": "项目目标", "content": "制作可验证的温湿度显示装置。"},
        {"id": "functional_logic", "title": "实现逻辑", "content": "采集温湿度后刷新显示，并保留异常提示。"},
        {"id": "hardware", "title": "硬件方案", "content": "ESP32-S3、DHT22、0.96 OLED 与 USB 5V 供电。"},
        {"id": "software", "title": "软件模块", "content": "MicroPython 采集、校验、显示和错误处理。"},
        {"id": "structure", "title": "结构方案", "content": "桌面外壳包含屏幕开孔、传感器通风孔和可拆后盖。"},
        {"id": "steps", "title": "实施步骤", "content": "先完成 Mock，再接线联调，最后确认结构尺寸。"},
        {"id": "cost", "title": "成本与工期", "content": "按教学级元件估算，先完成低风险原型。"},
        {"id": "risk", "title": "风险", "content": "复核供电、电平、通风和打印公差。"},
    ]


def _project_name(idea: str) -> str:
    if _contains_any(idea, ("温湿度", "dht22")):
        return "温湿度显示器与桌面外壳"
    compact = " ".join(idea.split()).strip()
    return (compact[:18] or "Web 交互验证") + "项目"


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)
