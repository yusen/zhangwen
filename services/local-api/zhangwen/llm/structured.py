"""Validated structured completions over the provider-neutral LLM gateway."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import TypeVar
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from zhangwen.llm.contracts import (
    ChatMessage,
    ChatMessageStatus,
    ChatProgressAction,
    ChatProgressEmitter,
    ChatProgressStatus,
    ChatRequest,
    ChatRole,
    LLMConfig,
    LLMError,
    LLMErrorCode,
    LLMModelId,
    StreamChunkType,
)
from zhangwen.llm.errors import make_llm_error
from zhangwen.llm.gateway import CancelToken, LLMProvider


StructuredModel = TypeVar("StructuredModel", bound=BaseModel)


class StructuredLLMError(RuntimeError):
    """A provider or structured-output error safe to expose at the API boundary."""

    def __init__(self, error: LLMError, *, diagnostic: str | None = None) -> None:
        super().__init__(error.message)
        self.error = error
        self.diagnostic = diagnostic


async def complete_structured(
    *,
    provider: LLMProvider,
    config: LLMConfig,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    output_model: type[StructuredModel],
    request_id_prefix: str,
    context_messages: list[ChatMessage] | None = None,
    validate_result: Callable[[StructuredModel], None] | None = None,
    cancel_token: CancelToken | None = None,
    on_validated_attempt: Callable[[int], None] | None = None,
    progress_emitter: ChatProgressEmitter | None = None,
    llm_progress_id: str | None = None,
    validation_progress_id: str | None = None,
) -> StructuredModel:
    """Call a real provider and validate one repair attempt against a Pydantic model."""

    schema_json = json.dumps(
        output_model.model_json_schema(),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    constrained_system_prompt = (
        f"{system_prompt.strip()}\n\n"
        "只返回一个 JSON 对象，不要输出 Markdown、解释或思维过程。"
        f"输出必须满足以下 JSON Schema：\n{schema_json}"
    )
    previous_output = ""
    validation_message = ""
    validation_source = "provider_structure"
    llm_id = None
    validation_id = None
    if progress_emitter is not None:
        llm_id = llm_progress_id or progress_emitter.next_id("llm.request")
        validation_id = validation_progress_id or progress_emitter.next_id(
            "output.validate"
        )
        progress_emitter.emit(
            progress_id=llm_id,
            action=ChatProgressAction.CLOUD_LLM_REQUEST,
            status=ChatProgressStatus.RUNNING,
        )

    try:
        for attempt in range(2):
            attempt_prompt = user_prompt
            if attempt == 1:
                attempt_prompt = _repair_prompt(
                    original_prompt=user_prompt,
                    previous_output=previous_output,
                    validation_message=validation_message,
                )
            raw = await _complete_text(
                provider=provider,
                config=config,
                api_key=api_key,
                model=model,
                system_prompt=constrained_system_prompt,
                user_prompt=attempt_prompt,
                context_messages=context_messages or [],
                cancel_token=cancel_token or CancelToken(),
                request_id=f"{request_id_prefix}_{uuid4().hex}",
            )
            previous_output = raw
            if progress_emitter is not None and validation_id is not None:
                progress_emitter.emit(
                    progress_id=validation_id,
                    action=ChatProgressAction.OUTPUT_VALIDATE,
                    status=ChatProgressStatus.RUNNING,
                )
            data = extract_json_object(raw)
            if data is None:
                validation_message = "输出中没有可解析的 JSON 对象。"
                validation_source = "provider_structure"
                if progress_emitter is not None and validation_id is not None:
                    progress_emitter.emit(
                        progress_id=validation_id,
                        action=ChatProgressAction.OUTPUT_VALIDATE,
                        status=ChatProgressStatus.FAILED,
                    )
                continue
            try:
                result = output_model.model_validate(data)
            except ValidationError as exc:
                validation_message = _safe_validation_feedback(exc)
                validation_source = "provider_structure"
                if progress_emitter is not None and validation_id is not None:
                    progress_emitter.emit(
                        progress_id=validation_id,
                        action=ChatProgressAction.OUTPUT_VALIDATE,
                        status=ChatProgressStatus.FAILED,
                    )
                continue
            try:
                if validate_result is not None:
                    validate_result(result)
                if on_validated_attempt is not None:
                    on_validated_attempt(attempt)
            except (ValidationError, ValueError, RuntimeError) as exc:
                validation_message = _safe_validation_feedback(exc)
                validation_source = "local_boundary"
                if progress_emitter is not None and validation_id is not None:
                    progress_emitter.emit(
                        progress_id=validation_id,
                        action=ChatProgressAction.OUTPUT_VALIDATE,
                        status=ChatProgressStatus.FAILED,
                    )
                continue
            if progress_emitter is not None and validation_id is not None:
                progress_emitter.emit(
                    progress_id=validation_id,
                    action=ChatProgressAction.OUTPUT_VALIDATE,
                    status=ChatProgressStatus.COMPLETED,
                )
            if progress_emitter is not None and llm_id is not None:
                progress_emitter.emit(
                    progress_id=llm_id,
                    action=ChatProgressAction.CLOUD_LLM_REQUEST,
                    status=ChatProgressStatus.COMPLETED,
                )
            return result
    except asyncio.CancelledError:
        if progress_emitter is not None and llm_id is not None:
            progress_emitter.emit(
                progress_id=llm_id,
                action=ChatProgressAction.CLOUD_LLM_REQUEST,
                status=ChatProgressStatus.FAILED,
            )
        raise
    except Exception:
        if progress_emitter is not None and llm_id is not None:
            progress_emitter.emit(
                progress_id=llm_id,
                action=ChatProgressAction.CLOUD_LLM_REQUEST,
                status=ChatProgressStatus.FAILED,
            )
        raise

    if progress_emitter is not None and llm_id is not None:
        progress_emitter.emit(
            progress_id=llm_id,
            action=ChatProgressAction.CLOUD_LLM_REQUEST,
            status=ChatProgressStatus.FAILED,
        )
    if validation_source == "local_boundary":
        error_code = LLMErrorCode.LOCAL_OUTPUT_REJECTED
        diagnostic_prefix = "local_output_rejected"
    else:
        error_code = LLMErrorCode.LLM_OUTPUT_INVALID
        diagnostic_prefix = "structured_validation_failed"
    raise StructuredLLMError(
        make_llm_error(error_code),
        diagnostic=(
            f"{diagnostic_prefix} after 2 attempts: "
            + (validation_message or "unknown_validation_error")
        ),
    )


def extract_json_object(text: str) -> dict[str, object] | None:
    """Extract the first decodable JSON object without using a greedy regex."""

    stripped = text.strip()
    if not stripped:
        return None
    decoder = json.JSONDecoder()
    for index, character in enumerate(stripped):
        if character != "{":
            continue
        try:
            value, _end = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


async def _complete_text(
    *,
    provider: LLMProvider,
    config: LLMConfig,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    context_messages: list[ChatMessage],
    cancel_token: CancelToken,
    request_id: str,
) -> str:
    request = ChatRequest(
        messages=[
            _message(f"{request_id}_system", ChatRole.SYSTEM, system_prompt),
            *context_messages,
            _message(f"{request_id}_user", ChatRole.USER, user_prompt),
        ],
        model=model,
        responseFormat="json_object",
    )
    content = ""
    try:
        async for chunk in provider.stream_chat(
            request,
            config,
            api_key,
            cancel_token,
            request_id,
            f"{request_id}_assistant",
        ):
            if chunk.type == StreamChunkType.PROGRESS:
                raise StructuredLLMError(
                    make_llm_error(LLMErrorCode.LLM_OUTPUT_INVALID)
                )
            if chunk.type == StreamChunkType.ERROR:
                raise StructuredLLMError(
                    chunk.error or make_llm_error(LLMErrorCode.UNKNOWN)
                )
            if chunk.type == StreamChunkType.CANCELED:
                raise StructuredLLMError(
                    chunk.error or make_llm_error(LLMErrorCode.CANCELED)
                )
            if chunk.accumulatedContent is not None:
                content = chunk.accumulatedContent
            elif chunk.delta:
                content += chunk.delta
    except StructuredLLMError:
        raise
    except Exception as exc:
        raise StructuredLLMError(make_llm_error(LLMErrorCode.UNKNOWN)) from exc
    return content


def _message(message_id: str, role: ChatRole, content: str) -> ChatMessage:
    return ChatMessage(
        id=message_id,
        role=role,
        content=content,
        status=ChatMessageStatus.READY,
        createdAt="",
        updatedAt="",
    )


def _repair_prompt(
    *,
    original_prompt: str,
    previous_output: str,
    validation_message: str,
) -> str:
    return (
        "上一次输出未通过校验。请修复后只返回完整 JSON 对象。\n"
        f"原始任务：\n{original_prompt}\n\n"
        f"校验错误：\n{validation_message}\n\n"
        f"上一次输出：\n{previous_output}"
    )


def _safe_validation_feedback(
    exc: ValidationError | ValueError | RuntimeError,
) -> str:
    """Return useful validation detail without retaining the model's raw output."""

    if isinstance(exc, ValidationError):
        details: list[str] = []
        for issue in exc.errors(
            include_url=False,
            include_context=False,
            include_input=False,
        ):
            location = ".".join(str(part) for part in issue.get("loc", ())) or "root"
            details.append(
                f"{location}:{issue.get('type', 'validation_error')}:{issue.get('msg', 'invalid')}"
            )
        feedback = "; ".join(details) or "pydantic_validation_failed"
    else:
        # Runtime validators in this boundary return controlled policy messages. Keep
        # only a compact single line; never include the previous provider output.
        feedback = f"{type(exc).__name__}: {' '.join(str(exc).split())}"
    return feedback[:2000]
