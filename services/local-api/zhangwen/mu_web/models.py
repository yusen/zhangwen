"""Strict MVP API contracts; MicroPython file transport lives in the browser."""
from __future__ import annotations

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
    boardId: str = Field(min_length=1, max_length=150)
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
    expectedRevision: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        return CreateInput.name_not_blank(value)


class ChatInput(CodeInput):
    message: str = Field(min_length=1, max_length=4000)


class ManifestInput(Boundary):
    expectedRevision: int = Field(ge=1)


class AiSettingsInput(Boundary):
    """Local-only persisted settings; the API key is never returned by the service."""
    apiKey: str | None = Field(default=None, max_length=500, repr=False)
    model: str = Field(default=DEFAULT_AI_MODEL, min_length=1, max_length=100)

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
        if not value:
            raise ValueError("模型名称不能为空。")
        return current_ai_model(value)
