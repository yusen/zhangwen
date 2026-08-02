"""Provider-neutral LLM Gateway interfaces and helpers."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Protocol

from zhangwen.llm.contracts import (
    ChatRequest,
    ConnectionTestResult,
    LLMConfig,
    StreamChunk,
)


class CancelToken:
    def __init__(self) -> None:
        self._event = asyncio.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def canceled(self) -> bool:
        return self._event.is_set()


class LLMProvider(Protocol):
    async def test_connection(
        self, config: LLMConfig, api_key: str
    ) -> ConnectionTestResult:
        """Validate provider connectivity."""

    async def stream_chat(
        self,
        request: ChatRequest,
        config: LLMConfig,
        api_key: str,
        cancel_token: CancelToken,
        request_id: str,
        message_id: str,
    ) -> AsyncIterator[StreamChunk]:
        """Stream provider response as generic chunks."""
