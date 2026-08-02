import httpx
import pytest

from zhangwen.llm.contracts import (
    ChatMessage,
    ChatMessageStatus,
    ChatRequest,
    ChatRole,
    LLMConfig,
    LLMErrorCode,
    LLMModelId,
    LLMProviderId,
    StreamChunkType,
    ThinkingMode,
    SUPPORTED_MODELS,
)
from zhangwen.llm.deepseek import DeepSeekProvider, parse_sse_line
from zhangwen.llm.gateway import CancelToken


def _message(content: str) -> ChatMessage:
    return ChatMessage(
        id="msg_user",
        role=ChatRole.USER,
        content=content,
        status=ChatMessageStatus.READY,
        createdAt="2026-07-08T00:00:00Z",
        updatedAt="2026-07-08T00:00:00Z",
    )


def test_build_payload_keeps_deepseek_thinking_provider_specific() -> None:
    provider = DeepSeekProvider()
    config = LLMConfig(
        defaultModel=LLMModelId.DEEPSEEK_V4_PRO,
        thinkingMode=ThinkingMode.ENABLED,
        reasoningEffort="max",
    )

    payload = provider.build_payload(
        ChatRequest(messages=[_message("你好")]),
        config,
        stream=True,
    )

    assert payload["model"] == "deepseek-v4-pro"
    assert payload["stream"] is True
    assert payload["stream_options"] == {"include_usage": True}
    assert payload["thinking"] == {"type": "enabled", "reasoning_effort": "max"}
    assert payload["messages"] == [{"role": "user", "content": "你好"}]


def test_build_payload_enables_json_object_for_structured_requests() -> None:
    payload = DeepSeekProvider().build_payload(
        ChatRequest(messages=[_message("json")], responseFormat="json_object"),
        LLMConfig(),
        stream=True,
    )

    assert payload["response_format"] == {"type": "json_object"}


def test_build_payload_uses_qwen_options_and_rejects_cross_provider_model() -> None:
    payload = DeepSeekProvider().build_payload(
        ChatRequest(
            messages=[_message("hello")],
            model=LLMModelId.DEEPSEEK_V4_PRO,
        ),
        LLMConfig(
            provider=LLMProviderId.QWEN,
            baseUrl="https://dashscope.aliyuncs.com/compatible-mode/v1",
            defaultModel=LLMModelId.QWEN_3_7_MAX,
            thinkingMode=ThinkingMode.ENABLED,
        ),
        stream=False,
    )

    assert payload["model"] == "qwen3.7-max"
    assert payload["enable_thinking"] is True
    assert "thinking" not in payload


def test_build_payload_keeps_glm_reasoning_effort_at_top_level() -> None:
    payload = DeepSeekProvider().build_payload(
        ChatRequest(messages=[_message("分析方案")]),
        LLMConfig(
            provider=LLMProviderId.GLM,
            baseUrl="https://open.bigmodel.cn/api/paas/v4",
            defaultModel=LLMModelId.GLM_5_2,
            thinkingMode=ThinkingMode.ENABLED,
            reasoningEffort="high",
        ),
        stream=True,
    )

    assert payload["thinking"] == {"type": "enabled"}
    assert payload["reasoning_effort"] == "high"
    assert "reasoning_effort" not in payload["thinking"]


def test_parse_sse_line() -> None:
    assert parse_sse_line("") is None
    assert parse_sse_line("event: chat.delta") is None
    assert parse_sse_line("data: [DONE]") == "[DONE]"
    assert parse_sse_line('data: {"choices": []}') == {"choices": []}


@pytest.mark.asyncio
async def test_stream_chat_maps_401_to_auth_failed() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "bad key"}})

    provider = DeepSeekProvider(transport=httpx.MockTransport(handler))
    chunks = [
        chunk
        async for chunk in provider.stream_chat(
            ChatRequest(messages=[_message("hi")]),
            LLMConfig(),
            "sk-test",
            CancelToken(),
            "req_1",
            "msg_1",
        )
    ]

    assert chunks[0].type == StreamChunkType.START
    assert chunks[1].type == StreamChunkType.ERROR
    assert chunks[1].error is not None
    assert chunks[1].error.code == LLMErrorCode.AUTH_FAILED
    assert "API Key" in chunks[1].error.message


@pytest.mark.parametrize(
    ("provider_id", "model_id", "base_url"),
    [
        (LLMProviderId.KIMI, LLMModelId.KIMI_K3, "https://api.moonshot.cn/v1"),
        (LLMProviderId.GLM, LLMModelId.GLM_5_2, "https://open.bigmodel.cn/api/paas/v4"),
    ],
)
@pytest.mark.asyncio
async def test_stream_chat_tolerates_usage_only_chunks_for_kimi_and_glm(
    provider_id: LLMProviderId,
    model_id: LLMModelId,
    base_url: str,
) -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text=(
                'data: {"choices":[],"usage":{"prompt_tokens":2,'
                '"completion_tokens":1,"total_tokens":3}}\n\n'
                'data: {"choices":[{"delta":{"content":"{\\"ok\\":true}"}}]}\n\n'
                "data: [DONE]\n\n"
            ),
        )

    chunks = [
        chunk
        async for chunk in DeepSeekProvider(
            transport=httpx.MockTransport(handler)
        ).stream_chat(
            ChatRequest(
                messages=[_message("json")],
                model=model_id,
                responseFormat="json_object",
            ),
            LLMConfig(
                provider=provider_id,
                baseUrl=base_url,
                defaultModel=model_id,
            ),
            "sk-test",
            CancelToken(),
            "req_usage",
            "msg_usage",
        )
    ]

    assert [chunk.type for chunk in chunks] == [
        StreamChunkType.START,
        StreamChunkType.CONTENT_DELTA,
        StreamChunkType.COMPLETED,
    ]
    assert chunks[-1].accumulatedContent == '{"ok":true}'
    assert chunks[-1].usage is not None
    assert chunks[-1].usage.totalTokens == 3


def test_kimi_catalog_contains_all_official_project_models() -> None:
    kimi_ids = {model.id for model in SUPPORTED_MODELS if model.provider == LLMProviderId.KIMI}

    assert kimi_ids == {
        LLMModelId.KIMI_K3,
        "kimi-k2.7-code",
        LLMModelId.KIMI_K2_7_CODE_HIGHSPEED,
    }
