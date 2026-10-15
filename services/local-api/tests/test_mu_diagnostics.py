"""Diagnostic protocol tests, without live network, credentials or hardware."""
import asyncio
import json

import httpx
import pytest

from zhangwen.mu_web import diagnostics as diag


class Stream(httpx.AsyncByteStream):
    def __init__(self, chunks, keep_alive=False):
        self.chunks, self.keep_alive, self.closed = chunks, keep_alive, False

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk
        while self.keep_alive:
            await asyncio.sleep(0.002)
            yield b": keep-alive\n\n"

    async def aclose(self):
        self.closed = True


def answer(content="OK", finish="stop", done=True):
    return Stream([("data: " + json.dumps({"choices": [{"delta": {"content": content}, "finish_reason": finish}]}) + "\n\n").encode(),
                   b"data: [DONE]\n\n" if done else b""])


def install(monkeypatch, *, model_status=200, models=None, balance_status=200, available=True,
            balance_error=None, generation_status=200, stream=None, generation_error=None, network_error=None):
    real_client = httpx.AsyncClient
    sent = []

    def respond(request):
        sent.append(request)
        assert request.headers["authorization"] == "Bearer test-secret"
        assert request.url.host == "api.deepseek.com"
        if request.url.path == "/models":
            if network_error:
                raise network_error
            return httpx.Response(model_status, json={"data": [{"id": "deepseek-flash"}]} if models is None else models)
        if request.url.path == "/user/balance":
            if balance_error:
                raise balance_error
            return httpx.Response(balance_status, json={"is_available": available})
        assert request.url.path == "/chat/completions"
        if generation_error:
            raise generation_error
        return httpx.Response(generation_status, stream=stream if stream is not None else answer())

    monkeypatch.setattr(diag.httpx, "AsyncClient", lambda **kw: real_client(**kw, transport=httpx.MockTransport(respond)))
    return sent


def run():
    async def collect():
        return [event async for event in diag.diagnose_ai(api_key="test-secret", model="deepseek-flash")]
    events = asyncio.run(collect())
    assert events[-1]["type"] == "done"
    assert "test-secret" not in json.dumps(events)
    report = events[-1]["report"]
    return events, report, {item["id"]: item for item in report["checks"]}


def test_success_checks_generation_separately_with_only_a_tiny_prompt(monkeypatch):
    sent = install(monkeypatch)
    events, report, checks = run()
    assert report["healthy"]
    assert all(item["status"] == "passed" for item in checks.values())
    body = json.loads(sent[-1].content)
    assert body == {"model": "deepseek-flash", "messages": [{"role": "user", "content": "只回复OK"}],
                    "thinking": {"type": "disabled"}, "max_tokens": 16, "stream": True}
    assert checks["generation"]["firstTokenMs"] >= 0
    assert any(e["type"] == "check" and e["check"]["status"] == "running" for e in events)


@pytest.mark.parametrize("status", [401, 403, 429, 503])
def test_model_endpoint_failures_do_not_attempt_generation(monkeypatch, status):
    sent = install(monkeypatch, model_status=status)
    _, report, checks = run()
    assert not report["healthy"]
    assert checks["network"]["status"] == "passed"
    assert checks["key"]["status"] == ("failed" if status in {401, 403} else "warning")
    assert checks["generation"]["status"] == "skipped"
    assert len(sent) == 1


def test_missing_model_is_reported_without_changing_or_trying_other_models(monkeypatch):
    sent = install(monkeypatch, models={"data": [{"id": "other"}]})
    _, report, checks = run()
    assert not report["healthy"] and checks["model"]["status"] == "failed"
    assert len(sent) == 1


@pytest.mark.parametrize("error", [httpx.ConnectError("test-secret"), httpx.ConnectTimeout("test-secret")])
def test_network_failures_do_not_claim_key_or_model_is_bad(monkeypatch, error):
    install(monkeypatch, network_error=error)
    _, report, checks = run()
    assert not report["healthy"]
    assert checks["network"]["status"] == "failed"
    assert checks["key"]["status"] == checks["model"]["status"] == "skipped"


@pytest.mark.parametrize("available, status", [(False, 200), (True, 402)])
def test_unavailable_account_skips_paid_generation(monkeypatch, available, status):
    sent = install(monkeypatch, available=available, balance_status=status)
    _, report, checks = run()
    assert not report["healthy"] and checks["balance"]["status"] == "failed"
    assert checks["generation"]["status"] == "skipped"
    assert len(sent) == 2


def test_unavailable_balance_endpoint_still_allows_a_real_generation_check(monkeypatch):
    install(monkeypatch, balance_status=404)
    _, report, checks = run()
    assert report["healthy"] and checks["balance"]["status"] == "warning"


@pytest.mark.parametrize("status", [401, 402, 404, 429, 503])
def test_generation_access_or_provider_failure_is_not_a_success(monkeypatch, status):
    install(monkeypatch, generation_status=status)
    _, report, checks = run()
    assert not report["healthy"] and checks["generation"]["status"] == "failed"
    assert checks["network"]["status"] == "passed"


@pytest.mark.parametrize("content, finish, done", [("", "stop", True), ("partial", "length", True), ("partial", "stop", False)])
def test_incomplete_answers_fail_generation_even_when_connection_is_healthy(monkeypatch, content, finish, done):
    install(monkeypatch, stream=answer(content, finish, done))
    _, report, checks = run()
    assert not report["healthy"] and checks["generation"]["status"] == "failed"


def test_keepalives_never_count_as_generated_text_and_total_time_is_bounded(monkeypatch):
    stream = Stream([b": keep-alive\n\n"], keep_alive=True)
    install(monkeypatch, stream=stream)
    monkeypatch.setattr(diag, "GENERATION_TIMEOUT", 0.03)
    _, report, checks = run()
    assert not report["healthy"]
    assert "没有返回正文" in checks["generation"]["detail"]
    assert checks["generation"]["keepAlives"] > 0
    assert "firstTokenMs" not in checks["generation"]
    assert stream.closed


def test_closing_the_diagnostic_closes_upstream(monkeypatch):
    stream = Stream([], keep_alive=True)
    install(monkeypatch, stream=stream)

    async def close():
        iterator = diag.diagnose_ai(api_key="test-secret", model="deepseek-flash")
        async for event in iterator:
            if event["type"] == "check" and "请求已被受理" in event["check"]["detail"]:
                break
        await iterator.aclose()

    asyncio.run(close())
    assert stream.closed
