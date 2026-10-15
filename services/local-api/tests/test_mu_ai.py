"""Provider protocol tests: no credentials, network, hardware or project fixtures."""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

from zhangwen.mu_web import app as mu
from zhangwen.mu_web.models import ChatInput


class Stream(httpx.AsyncByteStream):
    def __init__(self, chunks, error=None, keep_alive=False):
        self.chunks, self.error, self.keep_alive = chunks, error, keep_alive
        self.closed = False

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk
        if self.error:
            raise self.error
        while self.keep_alive:
            await asyncio.sleep(0.005)
            yield b": keep-alive\n\n"

    async def aclose(self):
        self.closed = True


def event(delta, finish=None):
    return ("data: " + json.dumps({"choices": [{"delta": delta, "finish_reason": finish}]}, ensure_ascii=False) + "\n\n").encode()


def install(monkeypatch, stream=None, error=None):
    real_client = httpx.AsyncClient

    def respond(request):
        if error:
            raise error
        assert json.loads(request.content)["stream"] is True
        return httpx.Response(200, stream=stream, headers={"content-type": "text/event-stream"})

    monkeypatch.setattr(mu.httpx, "AsyncClient", lambda **kw: real_client(**kw, transport=httpx.MockTransport(respond)))


async def generate(**kwargs):
    repo = SimpleNamespace(skills=SimpleNamespace(render_context=lambda *_args, **_kw: "板型资料"))
    return await mu.generate_reply(ChatInput(message="生成程序", code="", boardId="board"), repo, [],
                                   api_key="test-secret", model="deepseek-flash", **kwargs)


def test_stream_handles_fragmented_utf8_keepalives_and_never_exposes_reasoning(monkeypatch):
    content = event({"role": "assistant", "reasoning_content": "不要回显"}) + event({"content": "中文"})
    content += event({"content": "```python\nprint(1)\n```"}) + event({}, "stop")
    content += b'data: {"choices":[],"usage":{}}\n\ndata: [DONE]\n\n'
    stream = Stream([b": keep-alive\n\n", *[content[i:i + 1] for i in range(len(content))]])
    install(monkeypatch, stream)
    chunks = []

    async def delta(text):
        chunks.append(text)

    result = asyncio.run(generate(on_delta=delta))
    assert result == "中文```python\nprint(1)\n```"
    assert "".join(chunks) == result
    assert stream.closed


@pytest.mark.parametrize("chunks, phrase", [
    ([event({"content": "partial"})], "不完整"),
    ([event({"content": "partial"}, "length"), b"data: [DONE]\n\n"], "长度上限"),
    ([event({"reasoning_content": "hidden"}, "stop"), b"data: [DONE]\n\n"], "不完整"),
    ([b'data: {"error":"test-secret"}\n\n'], "不完整"),
    ([b"data: malformed\n\n"], "不完整"),
])
def test_incomplete_or_invalid_answers_are_not_success(monkeypatch, chunks, phrase):
    stream = Stream(chunks)
    install(monkeypatch, stream)
    with pytest.raises(HTTPException) as caught:
        asyncio.run(generate())
    assert caught.value.status_code == 502
    assert phrase in caught.value.detail
    assert "test-secret" not in caught.value.detail
    assert stream.closed


@pytest.mark.parametrize("phase, phrase", [("connect", "连接 DeepSeek 超时"), ("waiting", "长时间未返回"), ("answer", "回答中断")])
def test_timeout_distinguishes_connect_wait_and_generation(monkeypatch, phase, phrase):
    if phase == "connect":
        install(monkeypatch, error=httpx.ConnectTimeout("test-secret"))
    else:
        install(monkeypatch, Stream([event({"content": "partial"})] if phase == "answer" else [], error=httpx.ReadTimeout("test-secret")))
    with pytest.raises(HTTPException) as caught:
        asyncio.run(generate())
    assert caught.value.status_code == 504
    assert phrase in caught.value.detail
    assert "test-secret" not in caught.value.detail


def test_total_deadline_stops_an_endless_keepalive_connection(monkeypatch):
    stream = Stream([], keep_alive=True)
    install(monkeypatch, stream)
    monkeypatch.setattr(mu, "AI_TOTAL_TIMEOUT", 0.03)
    with pytest.raises(HTTPException) as caught:
        asyncio.run(generate())
    assert caught.value.status_code == 504
    assert "长时间未返回" in caught.value.detail
    assert stream.closed


def test_cancelling_closes_the_provider_connection(monkeypatch):
    stream = Stream([event({"content": "partial"})], keep_alive=True)
    install(monkeypatch, stream)

    async def run():
        ready = asyncio.Event()

        async def delta(_):
            ready.set()

        task = asyncio.create_task(generate(on_delta=delta))
        await asyncio.wait_for(ready.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    assert stream.closed
