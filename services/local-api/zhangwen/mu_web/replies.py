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
无需用户确认时question为null。不要重复整份代码到summary/points/details。
缺少接口、引脚、固件等必要条件时只澄清一个关键问题，code为null，不先猜测多个程序。
联调一次只处理一个模块和一个步骤，先确认连接，再生成最小程序，再询问用户实际现象。不能宣称已经运行或测试通过。
选项只是用户可选回复，不是命令或自动操作。'''


def structured_reply(content: str) -> AssistantReply | None:
    value = content.strip()
    fence = re.fullmatch(r'```(?:json|zhangwen)\s*\n([\s\S]*?)\s*```', value)
    if fence:
        value = fence[1]
    try:
        return AssistantReply.model_validate(json.loads(value))
    except (ValueError, TypeError, ValidationError):
        return None


def reply_code(content: str) -> str | None:
    reply = structured_reply(content)
    if reply:
        return reply.code
    # Legacy or nonconforming provider replies keep their complete text.
    match = re.search(r'```(?:python|micropython|py)\s*\n([\s\S]*?)```', content)
    return match[1].rstrip() + '\n' if match else None
