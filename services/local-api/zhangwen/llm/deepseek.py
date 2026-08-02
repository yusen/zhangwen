"""OpenAI-compatible provider implementation for supported cloud LLM APIs."""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from zhangwen.llm.contracts import (
    ChatMessageStatus,
    ChatRequest,
    ChatRole,
    ConnectionTestResult,
    LLMConfig,
    LLMErrorCode,
    LLMModelId,
    LLMProviderId,
    StreamChunk,
    StreamChunkType,
    ThinkingMode,
    TokenUsage,
    model_belongs_to_provider,
)
from zhangwen.llm.errors import make_llm_error, map_http_status
from zhangwen.llm.gateway import CancelToken


class DeepSeekProvider:
    """Provider-neutral OpenAI-compatible transport.

    The historical class name is retained to avoid a broad router migration.
    Provider identity, model selection and endpoint now come from ``LLMConfig``.
    """

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    def build_payload(
        self,
        request: ChatRequest,
        config: LLMConfig,
        stream: bool,
    ) -> dict[str, Any]:
        model = _selected_model(request, config)
        messages = [
            {"role": message.role.value, "content": message.content}
            for message in request.messages
            if message.role in {ChatRole.SYSTEM, ChatRole.USER, ChatRole.ASSISTANT}
        ]
        payload: dict[str, Any] = {
            "model": str(model),
            "messages": messages,
            "stream": stream,
        }
        if request.responseFormat == "json_object":
            payload["response_format"] = {"type": "json_object"}
        if stream:
            payload["stream_options"] = {"include_usage": True}
        _apply_thinking_options(payload, config)
        return payload

    async def test_connection(
        self,
        config: LLMConfig,
        api_key: str,
    ) -> ConnectionTestResult:
        started = time.perf_counter()
        request = ChatRequest(
            messages=[
                _message("test_user", ChatRole.USER, "ping", config.defaultModel),
            ],
            model=config.defaultModel,
        )
        payload = self.build_payload(request, config, stream=False)
        payload["max_tokens"] = 1

        try:
            async with self._client(config, api_key) as client:
                response = await client.post("/chat/completions", json=payload)
        except httpx.TimeoutException:
            return _connection_result(
                False,
                config,
                error=make_llm_error(code=LLMErrorCode.TIMEOUT),
            )
        except httpx.HTTPError:
            return _connection_result(
                False,
                config,
                error=make_llm_error(code=LLMErrorCode.NETWORK_UNAVAILABLE),
            )

        if response.status_code >= 400:
            return _connection_result(
                False,
                config,
                error=map_http_status(response.status_code),
            )

        return ConnectionTestResult(
            ok=True,
            message=f"{_provider_label(config.provider)} API 连接测试成功。",
            provider=config.provider,
            model=config.defaultModel,
            latencyMs=int((time.perf_counter() - started) * 1000),
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
        selected_model = _selected_model(request, config)
        yield StreamChunk(
            requestId=request_id,
            messageId=message_id,
            type=StreamChunkType.START,
            model=selected_model,
        )
        payload = self.build_payload(request, config, stream=True)
        content = ""
        reasoning = ""
        final_usage: TokenUsage | None = None

        try:
            async with self._client(config, api_key) as client:
                async with client.stream(
                    "POST",
                    "/chat/completions",
                    json=payload,
                ) as response:
                    if response.status_code >= 400:
                        yield StreamChunk(
                            requestId=request_id,
                            messageId=message_id,
                            type=StreamChunkType.ERROR,
                            error=map_http_status(response.status_code),
                        )
                        return

                    async for line in response.aiter_lines():
                        if cancel_token.canceled:
                            yield StreamChunk(
                                requestId=request_id,
                                messageId=message_id,
                                type=StreamChunkType.CANCELED,
                                error=make_llm_error(LLMErrorCode.CANCELED),
                            )
                            return

                        chunk = parse_sse_line(line)
                        if chunk is None:
                            continue
                        if chunk == "[DONE]":
                            break

                        usage = _usage(chunk.get("usage"))
                        if usage is not None:
                            final_usage = usage
                        choices = chunk.get("choices")
                        if not isinstance(choices, list) or not choices:
                            continue
                        first_choice = choices[0]
                        if not isinstance(first_choice, dict):
                            continue
                        delta = first_choice.get("delta", {})
                        if not isinstance(delta, dict):
                            continue
                        if delta.get("reasoning_content"):
                            reasoning_delta = str(delta["reasoning_content"])
                            reasoning += reasoning_delta
                            yield StreamChunk(
                                requestId=request_id,
                                messageId=message_id,
                                type=StreamChunkType.REASONING_DELTA,
                                delta=reasoning_delta,
                                accumulatedReasoning=reasoning,
                                model=selected_model,
                                usage=usage,
                            )
                        if delta.get("content"):
                            content_delta = str(delta["content"])
                            content += content_delta
                            yield StreamChunk(
                                requestId=request_id,
                                messageId=message_id,
                                type=StreamChunkType.CONTENT_DELTA,
                                delta=content_delta,
                                accumulatedContent=content,
                                accumulatedReasoning=reasoning or None,
                                model=selected_model,
                                usage=usage,
                            )

        except httpx.TimeoutException:
            yield StreamChunk(
                requestId=request_id,
                messageId=message_id,
                type=StreamChunkType.ERROR,
                error=make_llm_error(LLMErrorCode.TIMEOUT),
            )
            return
        except httpx.HTTPError:
            yield StreamChunk(
                requestId=request_id,
                messageId=message_id,
                type=StreamChunkType.ERROR,
                error=make_llm_error(LLMErrorCode.NETWORK_UNAVAILABLE),
            )
            return

        yield StreamChunk(
            requestId=request_id,
            messageId=message_id,
            type=StreamChunkType.COMPLETED,
            accumulatedContent=content,
            accumulatedReasoning=reasoning or None,
            model=selected_model,
            usage=final_usage,
        )

    def _client(self, config: LLMConfig, api_key: str) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=config.baseUrl.rstrip("/"),
            timeout=config.timeoutSeconds,
            headers={"Authorization": f"Bearer {api_key}"},
            transport=self._transport,
        )


def parse_sse_line(line: str) -> dict[str, Any] | str | None:
    if not line.startswith("data:"):
        return None
    data = line[5:].strip()
    if not data:
        return None
    if data == "[DONE]":
        return data
    return json.loads(data)


def _usage(raw: Any) -> TokenUsage | None:
    if not isinstance(raw, dict):
        return None
    return TokenUsage(
        promptTokens=raw.get("prompt_tokens"),
        completionTokens=raw.get("completion_tokens"),
        totalTokens=raw.get("total_tokens"),
    )


def _message(
    message_id: str,
    role: ChatRole,
    content: str,
    model: str,
):
    from datetime import UTC, datetime

    from zhangwen.llm.contracts import ChatMessage

    now = datetime.now(UTC).isoformat()
    return ChatMessage(
        id=message_id,
        role=role,
        content=content,
        status=ChatMessageStatus.READY,
        createdAt=now,
        updatedAt=now,
        model=model,
    )


def _connection_result(
    ok: bool,
    config: LLMConfig,
    error=None,
) -> ConnectionTestResult:
    return ConnectionTestResult(
        ok=ok,
        message=(
            error.message
            if error
            else f"{_provider_label(config.provider)} API 连接测试成功。"
        ),
        provider=config.provider,
        model=config.defaultModel,
        error=error,
    )


def _selected_model(request: ChatRequest, config: LLMConfig) -> str:
    if request.model and model_belongs_to_provider(
        request.model,
        config.provider,
        config.customModels,
    ):
        return request.model
    return config.defaultModel


def _provider_label(provider: LLMProviderId) -> str:
    return {
        LLMProviderId.DEEPSEEK: "DeepSeek",
        LLMProviderId.QWEN: "千问",
        LLMProviderId.GLM: "GLM",
        LLMProviderId.KIMI: "Kimi",
    }[provider]


def _apply_thinking_options(payload: dict[str, Any], config: LLMConfig) -> None:
    if config.thinkingMode == ThinkingMode.AUTO:
        return
    enabled = config.thinkingMode == ThinkingMode.ENABLED
    if config.provider == LLMProviderId.QWEN:
        payload["enable_thinking"] = enabled
        return
    if config.provider == LLMProviderId.KIMI:
        if enabled:
            payload["reasoning_effort"] = config.reasoningEffort or "high"
        return

    if config.provider == LLMProviderId.GLM:
        payload["thinking"] = {"type": "enabled" if enabled else "disabled"}
        if enabled and config.reasoningEffort:
            payload["reasoning_effort"] = config.reasoningEffort
        return

    thinking: dict[str, Any] = {"type": "enabled" if enabled else "disabled"}
    if enabled and config.reasoningEffort:
        thinking["reasoning_effort"] = config.reasoningEffort
    payload["thinking"] = thinking
