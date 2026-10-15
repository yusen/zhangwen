"""Bounded, user-triggered DeepSeek checks. Never submits project data or saves keys."""
from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import httpx

BASE = "https://api.deepseek.com"
MODELS_TIMEOUT = 10
BALANCE_TIMEOUT = 8
GENERATION_TIMEOUT = 30
LABELS = {"network": "网络连接", "key": "Key 认证", "model": "所选模型", "balance": "账户可用性", "generation": "实际生成"}


def status_detail(status: int) -> str:
    if status in {401, 403}:
        return "Key 无效或没有访问权限，请核对 Key。"
    if status == 402:
        return "账户余额不足，请检查 DeepSeek 账户。"
    if status == 429:
        return "供应商限制了请求频率，请稍后再测。"
    if status == 404:
        return "所选模型或接口不可用，请核对当前模型。"
    if status >= 500:
        return "DeepSeek 服务暂时不可用，请稍后再测。"
    return f"供应商拒绝请求（HTTP {status}），请核对设置后重试。"


async def diagnose_ai(*, api_key: str, model: str) -> AsyncIterator[dict[str, Any]]:
    checks: dict[str, dict[str, Any]] = {}

    def check(id: str, status: str, detail: str, **metrics) -> dict[str, Any]:
        item = {"id": id, "label": LABELS[id], "status": status, "detail": detail, **metrics}
        checks[id] = item
        return {"type": "check", "check": item}

    def done(suggestion: str) -> dict[str, Any]:
        for id in LABELS:
            if id not in checks:
                check(id, "skipped", "前置检查未通过，未执行。")
        return {"type": "done", "report": {
            "model": model, "checkedAt": datetime.now(UTC).isoformat(),
            "healthy": checks["generation"]["status"] == "passed", "checks": list(checks.values()), "suggestion": suggestion,
        }}

    if not api_key.strip():
        yield check("key", "failed", "尚未填写 Key。")
        yield done("填写 Key 后再测试；检测不会保存设置。")
        return

    async with httpx.AsyncClient(timeout=httpx.Timeout(connect=8, read=15, write=8, pool=8), trust_env=False) as client:
        headers = {"Authorization": "Bearer " + api_key.strip()}
        yield check("network", "running", "正在连接 DeepSeek 并读取模型列表…")
        start = time.monotonic()
        try:
            async with asyncio.timeout(MODELS_TIMEOUT):
                response = await client.get(BASE + "/models", headers=headers)
            yield check("network", "passed", f"HTTPS 接口可达（HTTP {response.status_code}）。", elapsedMs=round((time.monotonic() - start) * 1000))
            if response.status_code in {401, 403}:
                yield check("key", "failed", status_detail(response.status_code))
                yield done("检查 Key 是否完整、有效且具有访问权限。")
                return
            if not response.is_success:
                yield check("key", "warning", "接口已连接，但当前无法验证认证和模型。")
                yield done(status_detail(response.status_code))
                return
            payload = response.json()
            ids = [item["id"] for item in payload["data"] if isinstance(item, dict) and isinstance(item.get("id"), str)]
            yield check("key", "passed", "模型列表接口接受了 Key；实际生成权限将在下一步验证。")
            if model not in ids:
                yield check("model", "failed", "所选模型不在当前 Key 可访问的模型列表中。")
                yield done("选择当前可用模型后重新测试。")
                return
            yield check("model", "passed", f"{model} 在当前可用模型列表中。")
        except (TimeoutError, httpx.TimeoutException):
            yield check("network", "failed", "连接或读取模型列表超时。")
            yield done("检查本机网络、防火墙或代理，再重新测试。")
            return
        except httpx.HTTPError:
            yield check("network", "failed", "无法完成 HTTPS 连接，可能存在 DNS、TLS 或连接中断问题。")
            yield done("检查本机网络或代理；此结果尚不能判断 Key 是否有效。")
            return
        except (ValueError, KeyError, TypeError, AttributeError):
            yield check("model", "failed", "供应商没有返回有效的模型列表。")
            yield done("连接已建立，但供应商响应格式异常，请稍后再测。")
            return

        yield check("balance", "running", "正在检查账户是否可用…")
        try:
            async with asyncio.timeout(BALANCE_TIMEOUT):
                balance = await client.get(BASE + "/user/balance", headers=headers)
            if balance.is_success and balance.json().get("is_available") is False:
                yield check("balance", "failed", "供应商报告账户当前不可用，可能余额不足。")
                yield done("请在 DeepSeek 控制台检查余额和账户状态。")
                return
            if balance.status_code in {401, 403, 402}:
                yield check("balance", "failed", status_detail(balance.status_code))
                yield done("请在 DeepSeek 控制台检查 Key 权限、账户和余额。")
                return
            if balance.is_success and balance.json().get("is_available") is True:
                yield check("balance", "passed", "供应商报告账户可用。")
            else:
                yield check("balance", "warning", "账户接口未能确认状态，继续用实际生成验证。")
        except (TimeoutError, httpx.HTTPError, ValueError, TypeError, AttributeError):
            yield check("balance", "warning", "账户状态暂时无法读取，继续用实际生成验证。")

        yield check("generation", "running", "发送一条简短测试消息，最多等待30秒…")
        start = time.monotonic()
        first = None
        keep_alives = 0
        received = False
        finished = False
        finish_reason = None
        answer_size = 0

        def metrics():
            result = {"elapsedMs": round((time.monotonic() - start) * 1000), "keepAlives": keep_alives}
            if first is not None:
                result["firstTokenMs"] = first
            return result

        try:
            async with asyncio.timeout(GENERATION_TIMEOUT):
                async with client.stream("POST", BASE + "/chat/completions", headers=headers, json={
                    "model": model, "messages": [{"role": "user", "content": "只回复OK"}],
                    "thinking": {"type": "disabled"}, "max_tokens": 16, "stream": True,
                }) as response:
                    response.raise_for_status()
                    received = True
                    yield check("generation", "running", "请求已被受理，正在等待回答正文…", **metrics())
                    async for line in response.aiter_lines():
                        if line.startswith(":"):
                            keep_alives += 1
                            if first is None:
                                yield check("generation", "running", "连接仍在保活，供应商尚未返回正文…", **metrics())
                            continue
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            finished = True
                            break
                        payload = json.loads(data)
                        if "error" in payload:
                            raise ValueError("stream error")
                        choices = payload.get("choices", [])
                        if not choices:
                            continue
                        choice = choices[0]
                        finish_reason = choice.get("finish_reason") or finish_reason
                        content = choice.get("delta", {}).get("content")
                        if content is not None and not isinstance(content, str):
                            raise ValueError("invalid content")
                        if content and content.strip() and first is None:
                            first = round((time.monotonic() - start) * 1000)
                            yield check("generation", "running", "已收到首段正文，正在确认回答完整结束…", **metrics())
                        answer_size += len(content or "")
                        if answer_size > 4096:
                            raise ValueError("oversized test answer")
            if first is not None and finished and finish_reason == "stop":
                yield check("generation", "passed", "测试回答已完整返回。", **metrics())
                yield done("当前模型可以生成回答。该检测不代表每次长对话都能在相同时间完成。")
            else:
                yield check("generation", "failed", "回答为空、被截断或没有完整结束。", **metrics())
                yield done("生成接口未通过完整回答检测，请稍后重试或选择其他可用模型。")
        except (TimeoutError, httpx.TimeoutException):
            if not received:
                detail = "生成请求连接或等待响应超时。"
                suggestion = "模型列表可达，但生成接口没有及时响应；请检查网络并稍后重试。"
            elif first is None:
                detail = "请求已被受理，但30秒内没有返回正文。"
                suggestion = "生成服务未及时输出，可能正在排队或暂时异常；可稍后重测或手动换模型。"
            else:
                detail = "已收到正文，但回答没有在30秒内完整结束。"
                suggestion = "供应商响应较慢，本次检测未通过；可以稍后重测。"
            yield check("generation", "failed", detail, **metrics())
            yield done(suggestion)
        except httpx.HTTPStatusError as exc:
            yield check("generation", "failed", status_detail(exc.response.status_code), **metrics())
            yield done("根据生成接口返回的原因处理后重测；未修改保存的设置。")
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError, AttributeError):
            yield check("generation", "failed", "生成连接中断或返回格式异常。", **metrics())
            yield done("请稍后重测；没有把不完整响应记为成功。")
