"""Strict MVP API contracts; MicroPython file transport lives in the browser."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_CODE_BYTES = 65_536
DEFAULT_AI_MODEL = "deepseek-flash"


def current_ai_model(value: str) -> str:
    # Local upgrade policy for old defaults; not a provider equivalence claim.
    # The v4-flash aliases are also retired aliases in the official docs.
    legacy = {"deepseek-chat", "deepseek-reasoner", "deepseek-v4-flash", "deepseek-v4-flash-vision-exp"}
    value = value.strip()
    return DEFAULT_AI_MODEL if not value or value in legacy else value


DEFAULT_CODE = '# 掌问 · MicroPython\n# 上传后，点击「运行」查看串口输出。\nimport sys\nimport time\n\nprint("你好，掌问！")\nprint("当前平台:", sys.platform)\n\nfor count in range(5):\n    print("计数:", count + 1)\n    time.sleep(1)\n'


class Boundary(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CodeInput(Boundary):
    code: str = Field(max_length=MAX_CODE_BYTES)
    boardId: str = Field(min_length=1, max_length=150)
    componentIds: list[str] = Field(default_factory=list, max_length=32)

    @field_validator("code")
    @classmethod
    def code_size(cls, value: str) -> str:
        if len(value.encode("utf-8")) > MAX_CODE_BYTES or "\x00" in value:
            raise ValueError("代码须为 UTF-8 文本、无 NUL，且不超过 64 KiB。")
        return value


class CreateInput(Boundary):
    name: str = Field(min_length=1, max_length=80)
    boardId: str = Field(max_length=150)  # Empty for a project awaiting controller selection.
    code: str = Field(default=DEFAULT_CODE, max_length=MAX_CODE_BYTES)
    componentIds: list[str] = Field(default_factory=list, max_length=32)

    @field_validator("code")
    @classmethod
    def code_size(cls, value: str) -> str:
        return CodeInput.code_size(value)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("项目名称不能为空。")
        return value.strip()


class SaveInput(CodeInput):
    boardId: str = Field(max_length=150)
    expectedRevision: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        return CreateInput.name_not_blank(value)


class ChatInput(CodeInput):
    message: str = Field(min_length=1, max_length=4000)
    intent: Literal['integration'] | None = None


class HardwareExampleInput(Boundary):
    expectedRevision: str = Field(pattern=r'^[a-f0-9]{24}$')
    boardId: str = Field(min_length=1, max_length=150)
    notes: str = Field(max_length=2000)
    code: str = Field(max_length=16000)
    setup: dict[str, str] | None = None
    supportedBoardIds: list[str] | None = Field(default=None, max_length=5)

    @field_validator('supportedBoardIds')
    @classmethod
    def supported_boards_boundary(cls, value):
        if value is not None and (len(set(value)) != len(value) or any(
                not board_id or len(board_id) > 150 or not board_id.isascii()
                or not board_id.replace('_', '').isalnum() for board_id in value)):
            raise ValueError('支持的主控选项无效或重复。')
        return value

    @field_validator('setup')
    @classmethod
    def setup_boundary(cls, value):
        if value is not None and (len(value) > 16 or any(
                not key.isascii() or not key.replace('_', '').isalnum() or len(key) > 32
                or len(text) > 160 or '\x00' in text for key, text in value.items())):
            raise ValueError('接线选项格式无效。')
        return value

    @field_validator('notes', 'code')
    @classmethod
    def text_boundary(cls, value: str) -> str:
        if '\x00' in value:
            raise ValueError('案例不能包含NUL。')
        return value


class HardwareVerificationInput(Boundary):
    expectedRevision: str = Field(pattern=r'^[a-f0-9]{24}$')
    verifiedBoardIds: list[str] = Field(max_length=5)


class ManifestInput(Boundary):
    expectedRevision: int = Field(ge=1)


class AiSettingsInput(Boundary):
    """Local-only persisted settings; the API key is never returned by the service."""
    apiKey: str | None = Field(default=None, max_length=500, repr=False)
    model: str = Field(default=DEFAULT_AI_MODEL, min_length=1, max_length=100)
    baseUrl: str | None = Field(default=None, max_length=500)
    mode: Literal['engineer', 'structure', 'learning'] = 'engineer'

    @field_validator("baseUrl")
    @classmethod
    def endpoint_text(cls, value: str | None) -> str | None:
        from .endpoints import base_url
        return base_url(value) if value is not None else None

    @field_validator("apiKey")
    @classmethod
    def key_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if any(ord(character) < 33 or ord(character) > 126 for character in value):
            raise ValueError("API Key 不应包含空格或控制字符。")
        return value

    @field_validator("model")
    @classmethod
    def model_text(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ord(c) < 33 or ord(c) > 126 for c in value):
            raise ValueError("模型名称不能为空。")
        return value
