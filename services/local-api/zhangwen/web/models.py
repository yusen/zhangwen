"""Strict MVP API contracts; MicroPython file transport lives in the browser."""
from __future__ import annotations
import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
MAX_CODE_BYTES = 65536
DEFAULT_AI_MODEL = 'deepseek-flash'

def current_ai_model(value: str) -> str:
    legacy = {'deepseek-chat', 'deepseek-reasoner', 'deepseek-v4-flash', 'deepseek-v4-flash-vision-exp'}
    value = value.strip()
    return DEFAULT_AI_MODEL if not value or value in legacy else value
DEFAULT_CODE = '# 掌问 · MicroPython\n# 上传后，点击「运行」查看串口输出。\nimport sys\nimport time\n\nprint("你好，掌问！")\nprint("当前平台:", sys.platform)\n\nfor count in range(5):\n    print("计数:", count + 1)\n    time.sleep(1)\n'

class Boundary(BaseModel):
    model_config = ConfigDict(extra='forbid')

class CodeInput(Boundary):
    code: str = Field(max_length=MAX_CODE_BYTES)
    boardId: str = Field(min_length=1, max_length=150)
    componentIds: list[str] = Field(default_factory=list, max_length=32)

    @field_validator('code')
    @classmethod
    def code_size(cls, value: str) -> str:
        if len(value.encode('utf-8')) > MAX_CODE_BYTES or '\x00' in value:
            raise ValueError('代码须为 UTF-8 文本、无 NUL，且不超过 64 KiB。')
        return value

class CreateInput(Boundary):
    name: str = Field(min_length=1, max_length=80)
    boardId: str = Field(max_length=150)
    code: str = Field(default=DEFAULT_CODE, max_length=MAX_CODE_BYTES)
    componentIds: list[str] = Field(default_factory=list, max_length=32)

    @field_validator('code')
    @classmethod
    def code_size(cls, value: str) -> str:
        return CodeInput.code_size(value)

    @field_validator('name')
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('项目名称不能为空。')
        return value.strip()

class SaveInput(CodeInput):
    boardId: str = Field(max_length=150)
    expectedRevision: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=80)

    @field_validator('name')
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        return CreateInput.name_not_blank(value)

class ChatInput(CodeInput):
    code: str = Field(max_length=131072)
    message: str = Field(min_length=1, max_length=4000)
    intent: Literal['integration', 'lua-coding'] | None = None
    integrationModuleId: str | None = Field(default=None, min_length=1, max_length=150)

    @model_validator(mode='after')
    def integration_target(self):
        if self.integrationModuleId is not None and (self.intent != 'integration' or self.integrationModuleId not in self.componentIds):
            raise ValueError('联调对象必须是当前已加入的模块，且只能用于模块联调。')
        return self

    @field_validator('code')
    @classmethod
    def code_size(cls, value):
        if len(value.encode('utf-8')) > 131072 or '\x00' in value:
            raise ValueError('工程对话内容须为无NUL的UTF-8文本，最多128KiB。')
        return value

    @model_validator(mode='after')
    def source_limit(self):
        if self.intent != 'idea-coding':
            CodeInput.code_size(self.code)
        return self

class HardwareExampleInput(Boundary):
    expectedRevision: str = Field(pattern='^[a-f0-9]{24}$')
    boardId: str = Field(min_length=1, max_length=150)
    notes: str = Field(max_length=2000)
    code: str = Field(max_length=16000)
    setup: dict[str, str] | None = None
    i2cAddress: str | None = Field(default=None, max_length=4)
    supportedBoardIds: list[str] | None = Field(default=None, max_length=5)

    @field_validator('i2cAddress')
    @classmethod
    def i2c_address_valid(cls, value):
        if value is None or value == '':
            return value
        if not re.fullmatch('0[xX][0-9a-fA-F]{1,2}', value) or not 1 <= int(value, 16) <= 127:
            raise ValueError('请填写7位I²C设备地址（0x01～0x7F），不要填写8位读写地址。')
        return f'0x{int(value, 16):02x}'

    @field_validator('supportedBoardIds')
    @classmethod
    def supported_boards_boundary(cls, value):
        if value is not None and (len(set(value)) != len(value) or any((not board_id or len(board_id) > 150 or (not board_id.isascii()) or (not board_id.replace('_', '').isalnum()) for board_id in value))):
            raise ValueError('支持的主控选项无效或重复。')
        return value

    @field_validator('setup')
    @classmethod
    def setup_boundary(cls, value):
        if value is not None and (len(value) > 16 or any((not key.isascii() or not key.replace('_', '').isalnum() or len(key) > 32 or (len(text) > 160) or ('\x00' in text) for key, text in value.items()))):
            raise ValueError('接线选项格式无效。')
        return value

    @field_validator('notes', 'code')
    @classmethod
    def text_boundary(cls, value: str) -> str:
        if '\x00' in value:
            raise ValueError('案例不能包含NUL。')
        return value

class VerificationRecordInput(Boundary):
    boardId: str = Field(min_length=1, max_length=150)
    dimension: Literal['identity', 'electrical', 'wiring', 'driver', 'function', 'mechanical']
    state: Literal['unverified', 'documented', 'pending', 'passed', 'failed']
    notes: str = Field(max_length=1500)
    firmware: str = Field(max_length=150)
    wiring: str = Field(max_length=1500)
    evidence: str = Field(max_length=1500)

    @field_validator('evidence')
    @classmethod
    def printable(cls, value):
        if '\x00' in value:
            raise ValueError('核实记录包含无效文字。')
        return value

class HardwareVerificationInput(Boundary):
    expectedRevision: str = Field(pattern='^[a-f0-9]{24}$')
    verifiedBoardIds: list[str] | None = Field(default=None, max_length=5)
    record: VerificationRecordInput | None = None

class PersonalModuleInput(Boundary):
    name: str = Field(min_length=1, max_length=80)
    category: Literal['SENSOR', 'ACTUATOR', 'DISPLAY', 'POWER', 'STRUCTURE']
    description: str = Field(max_length=2000)
    voltage: float = Field(ge=0, le=1000, allow_inf_nan=False)
    logicLevel: float = Field(ge=0, le=1000, allow_inf_nan=False)
    protocol: str = Field(min_length=1, max_length=80)
    boardId: str = Field(max_length=150)
    code: str = Field(max_length=16000)
    notes: str = Field(max_length=20000)

class ManifestInput(Boundary):
    expectedRevision: int = Field(ge=1)

class AiSettingsInput(Boundary):
    """Local-only persisted settings; the API key is never returned by the service."""
    apiKey: str | None = Field(default=None, max_length=500, repr=False)
    model: str = Field(default=DEFAULT_AI_MODEL, min_length=1, max_length=100)
    baseUrl: str | None = Field(default=None, max_length=500)
    mode: Literal['engineer', 'structure', 'learning'] = 'engineer'

    @field_validator('baseUrl')
    @classmethod
    def endpoint_text(cls, value: str | None) -> str | None:
        from .endpoints import base_url
        return base_url(value) if value is not None else None

    @field_validator('apiKey')
    @classmethod
    def key_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if any((ord(character) < 33 or ord(character) > 126 for character in value)):
            raise ValueError('API Key 不应包含空格或控制字符。')
        return value

    @field_validator('model')
    @classmethod
    def model_text(cls, value: str) -> str:
        value = value.strip()
        if not value or any((ord(c) < 33 or ord(c) > 126 for c in value)):
            raise ValueError('模型名称不能为空。')
        return value
