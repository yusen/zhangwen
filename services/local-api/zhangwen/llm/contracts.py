"""LLM Gateway boundary models."""

from collections.abc import Callable, Sequence
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LLMProviderId(StrEnum):
    DEEPSEEK = "deepseek"
    QWEN = "qwen"
    GLM = "glm"
    KIMI = "kimi"
    OPENAI_COMPATIBLE = "openai-compatible"


class LLMModelId(StrEnum):
    DEEPSEEK_V4_FLASH = "deepseek-v4-flash"
    DEEPSEEK_V4_PRO = "deepseek-v4-pro"
    QWEN_3_7_MAX = "qwen3.7-max"
    QWEN_PLUS = "qwen-plus"
    GLM_5_2 = "glm-5.2"
    GLM_5_1 = "glm-5.1"
    KIMI_K3 = "kimi-k3"
    KIMI_K2_7_CODE = "kimi-k2.7-code"
    KIMI_K2_7_CODE_HIGHSPEED = "kimi-k2.7-code-highspeed"


LLMModelName = Annotated[
    str,
    Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$",
    ),
]
LLMModelSelection = Annotated[
    LLMModelId | LLMModelName,
    Field(union_mode="left_to_right"),
]


class ThinkingMode(StrEnum):
    AUTO = "AUTO"
    DISABLED = "DISABLED"
    ENABLED = "ENABLED"


class ChatRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessageStatus(StrEnum):
    READY = "READY"
    SENDING = "SENDING"
    STREAMING = "STREAMING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


class StreamChunkType(StrEnum):
    START = "START"
    PROGRESS = "PROGRESS"
    CONTENT_DELTA = "CONTENT_DELTA"
    REASONING_DELTA = "REASONING_DELTA"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"
    CANCELED = "CANCELED"


class ChatProgressAction(StrEnum):
    CONTEXT_READ = "CONTEXT_READ"
    CLOUD_LLM_REQUEST = "CLOUD_LLM_REQUEST"
    OUTPUT_VALIDATE = "OUTPUT_VALIDATE"
    PROJECT_UPDATE = "PROJECT_UPDATE"
    CODE_DRAFT_SAVE = "CODE_DRAFT_SAVE"
    CAD_DRAFT_SAVE = "CAD_DRAFT_SAVE"
    LOCAL_EXECUTION_AUTHORIZATION = "LOCAL_EXECUTION_AUTHORIZATION"
    LOCAL_TOOL_EXECUTION = "LOCAL_TOOL_EXECUTION"


class ChatProgressStatus(StrEnum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    WAITING = "WAITING"
    FAILED = "FAILED"


_CHAT_PROGRESS_LABELS: dict[
    tuple[ChatProgressAction, ChatProgressStatus], str
] = {
    (ChatProgressAction.CONTEXT_READ, ChatProgressStatus.RUNNING): "正在读取项目上下文",
    (ChatProgressAction.CONTEXT_READ, ChatProgressStatus.COMPLETED): "已读取项目上下文",
    (ChatProgressAction.CONTEXT_READ, ChatProgressStatus.WAITING): "等待读取项目上下文",
    (ChatProgressAction.CONTEXT_READ, ChatProgressStatus.FAILED): "项目上下文读取受阻",
    (
        ChatProgressAction.CLOUD_LLM_REQUEST,
        ChatProgressStatus.RUNNING,
    ): "正在请求云端 LLM",
    (
        ChatProgressAction.CLOUD_LLM_REQUEST,
        ChatProgressStatus.COMPLETED,
    ): "已收到云端 LLM 回复",
    (
        ChatProgressAction.CLOUD_LLM_REQUEST,
        ChatProgressStatus.WAITING,
    ): "等待请求云端 LLM",
    (
        ChatProgressAction.CLOUD_LLM_REQUEST,
        ChatProgressStatus.FAILED,
    ): "云端 LLM 请求受阻",
    (ChatProgressAction.OUTPUT_VALIDATE, ChatProgressStatus.RUNNING): "正在校验模型输出",
    (
        ChatProgressAction.OUTPUT_VALIDATE,
        ChatProgressStatus.COMPLETED,
    ): "已校验模型输出",
    (ChatProgressAction.OUTPUT_VALIDATE, ChatProgressStatus.WAITING): "等待校验模型输出",
    (ChatProgressAction.OUTPUT_VALIDATE, ChatProgressStatus.FAILED): "模型输出校验受阻",
    (ChatProgressAction.PROJECT_UPDATE, ChatProgressStatus.RUNNING): "正在更新项目状态",
    (ChatProgressAction.PROJECT_UPDATE, ChatProgressStatus.COMPLETED): "已更新项目状态",
    (ChatProgressAction.PROJECT_UPDATE, ChatProgressStatus.WAITING): "等待更新项目状态",
    (ChatProgressAction.PROJECT_UPDATE, ChatProgressStatus.FAILED): "项目状态更新受阻",
    (ChatProgressAction.CODE_DRAFT_SAVE, ChatProgressStatus.RUNNING): "正在保存代码草稿",
    (ChatProgressAction.CODE_DRAFT_SAVE, ChatProgressStatus.COMPLETED): "已保存代码草稿",
    (ChatProgressAction.CODE_DRAFT_SAVE, ChatProgressStatus.WAITING): "等待保存代码草稿",
    (ChatProgressAction.CODE_DRAFT_SAVE, ChatProgressStatus.FAILED): "代码草稿保存受阻",
    (ChatProgressAction.CAD_DRAFT_SAVE, ChatProgressStatus.RUNNING): "正在保存结构草稿",
    (ChatProgressAction.CAD_DRAFT_SAVE, ChatProgressStatus.COMPLETED): "已保存结构草稿",
    (ChatProgressAction.CAD_DRAFT_SAVE, ChatProgressStatus.WAITING): "等待保存结构草稿",
    (ChatProgressAction.CAD_DRAFT_SAVE, ChatProgressStatus.FAILED): "结构草稿保存受阻",
    (
        ChatProgressAction.LOCAL_EXECUTION_AUTHORIZATION,
        ChatProgressStatus.RUNNING,
    ): "正在检查本地执行授权",
    (
        ChatProgressAction.LOCAL_EXECUTION_AUTHORIZATION,
        ChatProgressStatus.COMPLETED,
    ): "已确认本地执行授权",
    (
        ChatProgressAction.LOCAL_EXECUTION_AUTHORIZATION,
        ChatProgressStatus.WAITING,
    ): "等待本地执行授权",
    (
        ChatProgressAction.LOCAL_EXECUTION_AUTHORIZATION,
        ChatProgressStatus.FAILED,
    ): "本地执行授权受阻",
    (
        ChatProgressAction.LOCAL_TOOL_EXECUTION,
        ChatProgressStatus.RUNNING,
    ): "正在执行本地工具",
    (
        ChatProgressAction.LOCAL_TOOL_EXECUTION,
        ChatProgressStatus.COMPLETED,
    ): "已完成本地工具执行",
    (
        ChatProgressAction.LOCAL_TOOL_EXECUTION,
        ChatProgressStatus.WAITING,
    ): "等待本地工具执行",
    (
        ChatProgressAction.LOCAL_TOOL_EXECUTION,
        ChatProgressStatus.FAILED,
    ): "本地工具执行受阻",
}


class ChatProgress(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9]*(?:\.[a-z0-9]+)*$", max_length=80)
    action: ChatProgressAction
    label: str
    status: ChatProgressStatus
    sequence: int = Field(ge=1)

    @classmethod
    def create(
        cls,
        *,
        progress_id: str,
        action: ChatProgressAction,
        status: ChatProgressStatus,
        sequence: int,
    ) -> "ChatProgress":
        return cls(
            id=progress_id,
            action=action,
            label=_CHAT_PROGRESS_LABELS[(action, status)],
            status=status,
            sequence=sequence,
        )

    @model_validator(mode="after")
    def _validate_server_owned_label(self) -> "ChatProgress":
        if self.label != _CHAT_PROGRESS_LABELS[(self.action, self.status)]:
            raise ValueError("Chat progress label is server-owned")
        return self


ChatProgressCallback = Callable[[ChatProgress], None]


class ChatProgressEmitter:
    """Assign stable sequence numbers while keeping public progress identifiers safe."""

    def __init__(self, callback: ChatProgressCallback | None = None) -> None:
        self._callback = callback
        self._sequences: dict[str, int] = {}
        self._id_counts: dict[str, int] = {}

    def next_id(self, prefix: str) -> str:
        count = self._id_counts.get(prefix, 0) + 1
        self._id_counts[prefix] = count
        return f"{prefix}.{count}"

    def emit(
        self,
        *,
        progress_id: str,
        action: ChatProgressAction,
        status: ChatProgressStatus,
    ) -> ChatProgress:
        sequence = self._sequences.setdefault(progress_id, len(self._sequences) + 1)
        progress = ChatProgress.create(
            progress_id=progress_id,
            action=action,
            status=status,
            sequence=sequence,
        )
        if self._callback is not None:
            self._callback(progress)
        return progress


class LLMErrorCode(StrEnum):
    CONFIG_MISSING = "CONFIG_MISSING"
    LLM_OUTPUT_INVALID = "LLM_OUTPUT_INVALID"
    LOCAL_OUTPUT_REJECTED = "LOCAL_OUTPUT_REJECTED"
    GENERATION_INTERRUPTED = "GENERATION_INTERRUPTED"
    INVALID_REQUEST = "INVALID_REQUEST"
    AUTH_FAILED = "AUTH_FAILED"
    INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"
    INVALID_PARAMETERS = "INVALID_PARAMETERS"
    RATE_LIMITED = "RATE_LIMITED"
    SERVER_ERROR = "SERVER_ERROR"
    SERVICE_BUSY = "SERVICE_BUSY"
    NETWORK_UNAVAILABLE = "NETWORK_UNAVAILABLE"
    DNS_UNAVAILABLE = "DNS_UNAVAILABLE"
    TLS_FAILED = "TLS_FAILED"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    TIMEOUT = "TIMEOUT"
    CANCELED = "CANCELED"
    SIDECAR_UNAVAILABLE = "SIDECAR_UNAVAILABLE"
    QUESTION_NOT_FOUND = "QUESTION_NOT_FOUND"
    QUESTION_ALREADY_ANSWERED = "QUESTION_ALREADY_ANSWERED"
    OPTION_NOT_ALLOWED = "OPTION_NOT_ALLOWED"
    CLARIFICATION_INCOMPLETE = "CLARIFICATION_INCOMPLETE"
    DUPLICATE_QUESTION_ANSWER = "DUPLICATE_QUESTION_ANSWER"
    STALE_CONVERSATION_TURN = "STALE_CONVERSATION_TURN"
    PROJECT_CONTEXT_MISMATCH = "PROJECT_CONTEXT_MISMATCH"
    DUPLICATE_TURN = "DUPLICATE_TURN"
    UNKNOWN = "UNKNOWN"


class UserAction(BaseModel):
    id: str
    label: str


class LLMError(BaseModel):
    code: LLMErrorCode
    message: str
    retryable: bool
    userActions: list[UserAction]
    providerStatus: int | None = None


class TokenUsage(BaseModel):
    promptTokens: int | None = None
    completionTokens: int | None = None
    totalTokens: int | None = None


class ModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: LLMModelSelection
    label: str = Field(min_length=1, max_length=80)
    provider: LLMProviderId
    supportsThinking: bool
    supportsStreaming: bool
    isCustom: bool = False


SUPPORTED_MODELS = [
    ModelConfig(
        id=LLMModelId.DEEPSEEK_V4_FLASH,
        label="DeepSeek V4 Flash",
        provider=LLMProviderId.DEEPSEEK,
        supportsThinking=True,
        supportsStreaming=True,
    ),
    ModelConfig(
        id=LLMModelId.DEEPSEEK_V4_PRO,
        label="DeepSeek V4 Pro",
        provider=LLMProviderId.DEEPSEEK,
        supportsThinking=True,
        supportsStreaming=True,
    ),
    ModelConfig(
        id=LLMModelId.QWEN_3_7_MAX,
        label="Qwen 3.7 Max",
        provider=LLMProviderId.QWEN,
        supportsThinking=True,
        supportsStreaming=True,
    ),
    ModelConfig(
        id=LLMModelId.QWEN_PLUS,
        label="Qwen Plus",
        provider=LLMProviderId.QWEN,
        supportsThinking=True,
        supportsStreaming=True,
    ),
    ModelConfig(
        id=LLMModelId.GLM_5_2,
        label="GLM-5.2",
        provider=LLMProviderId.GLM,
        supportsThinking=True,
        supportsStreaming=True,
    ),
    ModelConfig(
        id=LLMModelId.GLM_5_1,
        label="GLM-5.1",
        provider=LLMProviderId.GLM,
        supportsThinking=True,
        supportsStreaming=True,
    ),
    ModelConfig(
        id=LLMModelId.KIMI_K3,
        label="Kimi K3",
        provider=LLMProviderId.KIMI,
        supportsThinking=True,
        supportsStreaming=True,
    ),
    ModelConfig(
        id=LLMModelId.KIMI_K2_7_CODE,
        label="Kimi K2.7 Code",
        provider=LLMProviderId.KIMI,
        supportsThinking=True,
        supportsStreaming=True,
    ),
    ModelConfig(
        id=LLMModelId.KIMI_K2_7_CODE_HIGHSPEED,
        label="Kimi K2.7 Code Highspeed",
        provider=LLMProviderId.KIMI,
        supportsThinking=True,
        supportsStreaming=True,
    ),
]

MODEL_PROVIDER = {str(model.id): model.provider for model in SUPPORTED_MODELS}


def model_belongs_to_provider(
    model: str,
    provider: LLMProviderId,
    custom_models: Sequence[ModelConfig] = (),
) -> bool:
    model_id = str(model)
    if MODEL_PROVIDER.get(model_id) == provider:
        return True
    return any(
        item.isCustom and item.provider == provider and item.id == model_id
        for item in custom_models
    )


def _validate_model_catalog(
    provider: LLMProviderId,
    default_model: str,
    custom_models: Sequence[ModelConfig],
) -> None:
    seen: set[tuple[LLMProviderId, str]] = set()
    for item in custom_models:
        if not item.isCustom:
            raise ValueError("customModels entries must be marked as custom")
        if item.id in MODEL_PROVIDER:
            raise ValueError("custom model duplicates a built-in model")
        key = (item.provider, item.id)
        if key in seen:
            raise ValueError("custom model ids must be unique per provider")
        seen.add(key)
    if not model_belongs_to_provider(default_model, provider, custom_models):
        raise ValueError("defaultModel does not belong to provider")


class LLMConfig(BaseModel):
    provider: LLMProviderId = LLMProviderId.DEEPSEEK
    baseUrl: str = "https://api.deepseek.com"
    defaultModel: LLMModelSelection = LLMModelId.DEEPSEEK_V4_FLASH
    customModels: list[ModelConfig] = Field(default_factory=list, max_length=32)
    thinkingMode: ThinkingMode = ThinkingMode.AUTO
    reasoningEffort: Literal["high", "max"] | None = None
    timeoutSeconds: int = Field(default=60, ge=5, le=300)
    keySaved: bool = False
    maskedApiKey: str | None = None
    updatedAt: str | None = None
    providerConfigurationId: str | None = None
    providerConfigurationRevisionId: str | None = None
    routingProfileRevisionId: str | None = None

    @model_validator(mode="after")
    def _validate_model_provider(self) -> "LLMConfig":
        _validate_model_catalog(self.provider, self.defaultModel, self.customModels)
        return self


class SaveLLMConfigRequest(BaseModel):
    provider: LLMProviderId = LLMProviderId.DEEPSEEK
    baseUrl: str = "https://api.deepseek.com"
    defaultModel: LLMModelSelection = LLMModelId.DEEPSEEK_V4_FLASH
    customModels: list[ModelConfig] = Field(default_factory=list, max_length=32)
    thinkingMode: ThinkingMode = ThinkingMode.AUTO
    reasoningEffort: Literal["high", "max"] | None = None
    timeoutSeconds: int = Field(default=60, ge=5, le=300)
    apiKey: str | None = None

    @model_validator(mode="after")
    def _validate_model_provider(self) -> "SaveLLMConfigRequest":
        _validate_model_catalog(self.provider, self.defaultModel, self.customModels)
        return self


class LLMConfigResponse(BaseModel):
    config: LLMConfig


class ModelsResponse(BaseModel):
    models: list[ModelConfig]


class ConnectionTestRequest(BaseModel):
    config: SaveLLMConfigRequest | None = None
    apiKey: str | None = None


class ConnectionTestResult(BaseModel):
    ok: bool
    message: str
    provider: LLMProviderId
    model: LLMModelSelection
    latencyMs: int | None = None
    error: LLMError | None = None


class ChatMessage(BaseModel):
    id: str
    role: ChatRole
    content: str
    structuredPayload: dict | None = None
    metadata: dict | None = None
    reasoningContent: str | None = None
    status: ChatMessageStatus = ChatMessageStatus.READY
    createdAt: str
    updatedAt: str
    model: LLMModelSelection | None = None
    error: LLMError | None = None
    usage: TokenUsage | None = None


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: LLMModelSelection | None = None
    abortPrevious: bool = False
    responseFormat: Literal["json_object"] | None = None


class StreamChunk(BaseModel):
    requestId: str
    messageId: str
    requestTurnId: str | None = None
    responseTurnId: str | None = None
    type: StreamChunkType
    delta: str | None = None
    accumulatedContent: str | None = None
    accumulatedReasoning: str | None = None
    model: LLMModelSelection | None = None
    error: LLMError | None = None
    usage: TokenUsage | None = None
    progress: ChatProgress | None = None
    structuredPayload: dict | None = None
    envelope: dict | None = None

    @model_validator(mode="after")
    def _validate_progress_payload(self) -> "StreamChunk":
        if self.type == StreamChunkType.PROGRESS and self.progress is None:
            raise ValueError("PROGRESS stream chunk requires progress")
        if self.type != StreamChunkType.PROGRESS and self.progress is not None:
            raise ValueError("progress is only allowed on PROGRESS stream chunks")
        return self


class CancelChatResponse(BaseModel):
    requestId: str
    canceled: bool
