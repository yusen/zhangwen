"""Validate optional presentation data while preserving the original model text."""
from __future__ import annotations

import json
import re
from pydantic import Field, ValidationError, field_validator
from .models import Boundary, CodeInput


class ReplyQuestion(Boundary):
    text: str = Field(min_length=1, max_length=240)
    options: list[str] = Field(max_length=4)

    @field_validator('text')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('Question must not be blank')
        return value

    @field_validator('options')
    @classmethod
    def options_text(cls, value):
        if any(not item.strip() or len(item) > 60 for item in value):
            raise ValueError('Invalid answer choices')
        return value


class AssistantReply(Boundary):
    summary: str = Field(min_length=1, max_length=240)
    points: list[str] = Field(max_length=3)
    question: ReplyQuestion | None
    details: str = Field(max_length=12000)
    code: str | None

    @field_validator('summary')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('Summary must not be blank')
        return value

    @field_validator('points')
    @classmethod
    def points_text(cls, value):
        if any(not item.strip() or len(item) > 240 for item in value):
            raise ValueError('Invalid key points')
        return value

    @field_validator('code')
    @classmethod
    def code_text(cls, value):
        return CodeInput.code_size(value) if value is not None else None


REPLY_INSTRUCTION = '''回答使用一个JSON对象，不加Markdown围栏，所有字段必填：
{"summary":"一句中文结论，最多240字", "points":["本轮要点，最多3条、每条最多240字"],
"question":{"text":"本轮只问一个需要用户回答的问题，最多240字", "options":["可选的简短回复，最多4个，每个最多60字"]},
"details":"补充解释，界面默认折叠；必要的供电/电平/接线条件或警示必须出现在points，不能仅放这里；最多12000字",
"code":"需要生成代码时给完整main.py文本（JSON字符串，换行转义），否则null"}。
无需用户确认时question为null。不要重复整份代码到summary/points/details。points严格最多3条，补充说明放details。
JSON结束后不要追加文字；换行只做标准JSON转义，不要把代码重复转义。说“给出程序”时必须附code，不能只描述程序。
当前编辑器为空不代表用户已保存、上传或运行；这些状态只能依据用户明确反馈，不能从代码是否为空推断。
缺少接口、引脚、固件等必要条件时只澄清一个关键问题，code为null，不先猜测多个程序。
联调一次只处理一个模块和一个步骤，先确认连接，再生成最小程序，再询问用户实际现象。不能宣称已经运行或测试通过。
附测试程序并询问实际现象时，先明确让用户核对接线和右侧代码，点击顶部「上传」；平台回读校验通过后自动运行，运行中按键变为「停止」。用户操作并观察后再回答现象，不要直接要求给出尚未运行的结果。
必要条件应以当前步骤为准：已有适用的当前主控本机案例时，先沿用其中的库调用完成最小测试，不因地址未填或主控摘要没有列出模块库签名而退回扫描/原始读字节或索要寄存器协议。只有没有适用案例，或用户反馈该案例实际导入/调用报错等需要诊断时，才按当前主控已知API提供I2C扫描或屏幕显示等独立诊断程序，并附完整code；不反复询问已确认的接线。
用户再次要求同一功能时，若仍缺必要条件，应在summary明确说明缺哪一项，并在question给出能直接回答的选择；不能只说稍后给程序。不要依据历史助手的猜测认定模块驱动或寄存器协议已确认。
回复说明的测试范围必须与code一致。若说明是“独立屏幕自检”或“先排除传感器”，code只能包含屏幕初始化、静态文字或计数显示与必要串口报错，不保留传感器导入、ADC初始化、采样或阈值判断；要保留传感器联调时明确说明并非独立屏幕自检。不要声称旧版本已经替换；用户须核对本条回复的查看代码链接与右侧版本，明确采用后再上传。
选项只是用户可选回复，不是命令或自动操作。'''


def reply_data(content: str) -> dict | None:
    """Accept one complete JSON object, optionally followed by plain prose.

    Presentation mistakes must not discard the independent bounded code field.
    Never repair truncated JSON or combine competing JSON/code payloads.
    """
    value = content.strip()
    fence = re.fullmatch(r'```(?:json|zhangwen)\s*\n([\s\S]*?)\s*```', value)
    if fence:
        value = fence[1]
    try:
        data, end = json.JSONDecoder().raw_decode(value)
        if not isinstance(data, dict) or value[end:].lstrip().startswith(('{', '[', '```')):
            return None
        return data
    except (ValueError, TypeError):
        return None


def structured_reply(content: str) -> AssistantReply | None:
    try:
        data = reply_data(content)
        return AssistantReply.model_validate(data) if data is not None else None
    except (ValueError, TypeError, ValidationError):
        return None


def reply_code(content: str) -> str | None:
    data = reply_data(content)
    if data is not None:
        code = data.get('code')
        try:
            return CodeInput.code_size(code) if isinstance(code, str) and code.strip() else None
        except ValueError:
            return None
    if content.lstrip().startswith(('{', '```json', '```zhangwen')):
        return None
    # Legacy or nonconforming provider replies keep their complete text.
    match = re.search(r'```(?:python|micropython|py)\s*\n([\s\S]*?)```', content)
    if match:
        code = match[1].rstrip() + '\n'
        try:
            return CodeInput.code_size(code) if code.strip() else None
        except ValueError:
            pass
    return None
