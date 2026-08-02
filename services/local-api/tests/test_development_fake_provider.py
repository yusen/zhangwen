"""Explicit fake Provider used only by the dedicated Web validation launcher."""

from __future__ import annotations

import json

import pytest

from zhangwen.llm.contracts import (
    ChatMessage,
    ChatRequest,
    ChatRole,
    LLMConfig,
    StreamChunkType,
)
from zhangwen.llm.deepseek import DeepSeekProvider
from zhangwen.llm.development_fake import DevelopmentFakeProvider, create_provider
from zhangwen.llm.gateway import CancelToken
from zhangwen.experts.config import load_expert_prompt
from zhangwen.projects.models import ExpertType


def test_development_fake_provider_requires_explicit_test_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ZHANGWEN_LLM_TEST_MODE", raising=False)
    assert isinstance(create_provider(), DeepSeekProvider)

    monkeypatch.setenv("ZHANGWEN_LLM_TEST_MODE", "fake")
    assert isinstance(create_provider(), DevelopmentFakeProvider)

    monkeypatch.setenv("ZHANGWEN_LLM_TEST_MODE", "paid")
    assert isinstance(create_provider(), DeepSeekProvider)

    monkeypatch.setenv("ZHANGWEN_LLM_TEST_MODE", "unknown")
    assert isinstance(create_provider(), DeepSeekProvider)


@pytest.mark.asyncio
async def test_development_fake_provider_routes_and_labels_three_experts() -> None:
    provider = DevelopmentFakeProvider()
    route = await _complete(
        provider,
        system="你是掌问平台不可见的入口主路由。",
        user="用户项目想法：做一个 ESP32 温湿度显示器和 3D 打印外壳",
    )
    assert route["recommendedExperts"] == [
        "problem_guide",
        "smart_engineer",
        "structure_engineer",
    ]

    smart = await _complete(
        provider,
        system=load_expert_prompt(ExpertType.SMART_ENGINEER),
        user="检查硬件",
    )
    structure = await _complete(
        provider,
        system=load_expert_prompt(ExpertType.STRUCTURE_ENGINEER),
        user="设计外壳",
    )
    assert str(smart["content"]).startswith("智能工程师：")
    assert str(structure["content"]).startswith("结构工程师：")


async def _complete(
    provider: DevelopmentFakeProvider,
    *,
    system: str,
    user: str,
) -> dict[str, object]:
    request = ChatRequest(
        messages=[
            _message("system", ChatRole.SYSTEM, system),
            _message("user", ChatRole.USER, user),
        ]
    )
    chunks = [
        chunk
        async for chunk in provider.stream_chat(
            request,
            LLMConfig(),
            "fake",
            CancelToken(),
            "request",
            "assistant",
        )
    ]
    assert chunks[-1].type == StreamChunkType.COMPLETED
    return json.loads(chunks[-1].accumulatedContent or "{}")


def _message(message_id: str, role: ChatRole, content: str) -> ChatMessage:
    return ChatMessage(
        id=message_id,
        role=role,
        content=content,
        createdAt="2026-07-11T00:00:00Z",
        updatedAt="2026-07-11T00:00:00Z",
    )
