"""Safe local-LAN adapter for ESP-Claw code deployment.

The normal deployment path writes Lua files through the ESP-Claw Web Console
and starts the accepted entrypoint through the MCP Lua tools.  It deliberately
contains no serial, esptool, firmware or Flash primitives.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import re
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import quote, urlsplit, urlunsplit

import httpx


REQUIRED_ESP_CLAW_TOOLS = frozenset(
    {"lua_run_script_async", "lua_get_async_job", "lua_stop_async_job"}
)
ESP_CLAW_STORAGE_BASE_PATH = "/fatfs"


class EspClawAdapterError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class EspClawAdapterCanceled(EspClawAdapterError):
    def __init__(self) -> None:
        super().__init__("DEVICE_OPERATION_CANCELED", "ESP-Claw deployment canceled.")


@dataclass(frozen=True)
class EspClawHandshake:
    storage_base_path: str
    capabilities: tuple[str, ...]
    file_readback_capable: bool
    reported_board_id: str | None = None


@dataclass(frozen=True)
class EspClawAsyncJob:
    job_id: str
    status: str
    ok: bool | None


class EspClawDeploymentAdapter(Protocol):
    async def handshake(
        self,
        web_endpoint: str,
        mcp_endpoint: str,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> EspClawHandshake: ...

    async def make_directory(
        self,
        endpoint: str,
        path: str,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> None: ...

    async def read_file(
        self,
        endpoint: str,
        path: str,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> bytes | None: ...

    async def upload_file(
        self,
        endpoint: str,
        path: str,
        content: bytes,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> None: ...

    async def delete_file(
        self,
        endpoint: str,
        path: str,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> None: ...

    async def run_lua_script(
        self,
        endpoint: str,
        path: str,
        job_name: str,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> str: ...

    async def get_async_job(
        self,
        endpoint: str,
        job_id: str,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> EspClawAsyncJob: ...

    async def get_async_job_by_name(
        self,
        endpoint: str,
        job_name: str,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> EspClawAsyncJob: ...

    async def stop_async_job(
        self,
        endpoint: str,
        job_name: str,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> None: ...


class HttpxEspClawDeploymentAdapter:
    """ESP-Claw Web Console/MCP adapter with a fixed request vocabulary."""

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    async def handshake(
        self,
        web_endpoint: str,
        mcp_endpoint: str,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> EspClawHandshake:
        status_response = await self._request(
            "GET",
            web_endpoint,
            "/api/status",
            cancel=cancel,
            timeout_seconds=timeout_seconds,
        )
        status = _json_object(status_response, "ESP_CLAW_STATUS_INVALID")
        storage = _storage_base_path(status)
        if storage != ESP_CLAW_STORAGE_BASE_PATH:
            raise EspClawAdapterError(
                "ESP_CLAW_STORAGE_PATH_MISMATCH",
                "ESP-Claw status did not report the required /fatfs storage base.",
            )
        tools_response = await self._mcp_request(
            mcp_endpoint,
            method="tools/list",
            params={},
            cancel=cancel,
            timeout_seconds=timeout_seconds,
        )
        result = _mcp_result(tools_response)
        tools = result.get("tools")
        if not isinstance(tools, list):
            raise EspClawAdapterError(
                "ESP_CLAW_TOOLS_INVALID",
                "ESP-Claw MCP tools/list returned an invalid tool catalog.",
            )
        names = sorted(
            {
                str(item.get("name"))
                for item in tools
                if isinstance(item, dict) and isinstance(item.get("name"), str)
            }
        )
        if not REQUIRED_ESP_CLAW_TOOLS.issubset(names):
            raise EspClawAdapterError(
                "ESP_CLAW_LUA_TOOLS_MISSING",
                "ESP-Claw does not expose the required asynchronous Lua tools.",
            )
        file_index_response = await self._request(
            "GET",
            web_endpoint,
            "/api/files",
            params={"path": "/"},
            cancel=cancel,
            timeout_seconds=timeout_seconds,
            accepted_statuses={200},
        )
        try:
            file_index = file_index_response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise EspClawAdapterError(
                "ESP_CLAW_FILE_READBACK_UNAVAILABLE",
                "ESP-Claw Web File API did not return a readable directory index.",
            ) from exc
        if not isinstance(file_index, (dict, list)):
            raise EspClawAdapterError(
                "ESP_CLAW_FILE_READBACK_UNAVAILABLE",
                "ESP-Claw Web File API directory index is invalid.",
            )
        names.append("web_file_readback")
        return EspClawHandshake(
            storage_base_path=storage,
            capabilities=tuple(names),
            file_readback_capable=True,
            reported_board_id=_reported_board_id(status),
        )

    async def make_directory(
        self,
        endpoint: str,
        path: str,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> None:
        response = await self._request(
            "POST",
            endpoint,
            "/api/files/mkdir",
            json_body={"path": _web_storage_path(path), "recursive": True},
            cancel=cancel,
            timeout_seconds=timeout_seconds,
            accepted_statuses={200, 201, 204, 409},
        )
        del response

    async def read_file(
        self,
        endpoint: str,
        path: str,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> bytes | None:
        response = await self._request(
            "GET",
            endpoint,
            f"/files/{quote(_web_storage_path(path).lstrip('/'), safe='/')}",
            cancel=cancel,
            timeout_seconds=timeout_seconds,
            accepted_statuses={200, 404},
        )
        return None if response.status_code == 404 else response.content

    async def upload_file(
        self,
        endpoint: str,
        path: str,
        content: bytes,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> None:
        response = await self._request(
            "POST",
            endpoint,
            "/api/files/upload",
            params={"path": _web_storage_path(path)},
            raw_content=content,
            cancel=cancel,
            timeout_seconds=timeout_seconds,
            accepted_statuses={200, 201, 204},
        )
        del response

    async def delete_file(
        self,
        endpoint: str,
        path: str,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> None:
        response = await self._request(
            "DELETE",
            endpoint,
            "/api/files",
            params={"path": _web_storage_path(path)},
            cancel=cancel,
            timeout_seconds=timeout_seconds,
            accepted_statuses={200, 204, 404},
        )
        del response

    async def run_lua_script(
        self,
        endpoint: str,
        path: str,
        job_name: str,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> str:
        response = await self._mcp_request(
            endpoint,
            method="tools/call",
            params={
                "name": "lua_run_script_async",
                "arguments": {
                    "path": path,
                    "name": job_name,
                    "exclusive": job_name,
                    "replace": True,
                    "timeout_ms": 0,
                },
            },
            cancel=cancel,
            timeout_seconds=timeout_seconds,
        )
        payload = _tool_payload(_mcp_result(response))
        job_id = payload.get("job_id") or payload.get("jobId") or payload.get("id")
        if not isinstance(job_id, (str, int)) or not str(job_id):
            text = payload.get("text")
            match = (
                re.search(
                    r"(?i)\bjob(?:[_ -]?id)?\s*(?:[:=#]|is)?\s*([A-Za-z0-9][A-Za-z0-9._-]{2,127})",
                    text,
                )
                if isinstance(text, str)
                else None
            )
            job_id = match.group(1) if match else None
        if not isinstance(job_id, (str, int)) or not str(job_id):
            raise EspClawAdapterError(
                "ESP_CLAW_JOB_ID_MISSING",
                "ESP-Claw did not return an asynchronous Lua job id.",
            )
        return str(job_id)

    async def get_async_job(
        self,
        endpoint: str,
        job_id: str,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> EspClawAsyncJob:
        return await self._get_async_job(
            endpoint,
            {"job_id": job_id},
            fallback_job_id=job_id,
            cancel=cancel,
            timeout_seconds=timeout_seconds,
        )

    async def get_async_job_by_name(
        self,
        endpoint: str,
        job_name: str,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> EspClawAsyncJob:
        return await self._get_async_job(
            endpoint,
            {"name": job_name},
            fallback_job_id=job_name,
            cancel=cancel,
            timeout_seconds=timeout_seconds,
        )

    async def stop_async_job(
        self,
        endpoint: str,
        job_name: str,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> None:
        response = await self._mcp_request(
            endpoint,
            method="tools/call",
            params={
                "name": "lua_stop_async_job",
                "arguments": {"name": job_name},
            },
            cancel=cancel,
            timeout_seconds=timeout_seconds,
        )
        _tool_payload(_mcp_result(response))

    async def _get_async_job(
        self,
        endpoint: str,
        arguments: dict[str, str],
        *,
        fallback_job_id: str,
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> EspClawAsyncJob:
        response = await self._mcp_request(
            endpoint,
            method="tools/call",
            params={
                "name": "lua_get_async_job",
                "arguments": arguments,
            },
            cancel=cancel,
            timeout_seconds=timeout_seconds,
        )
        payload = _tool_payload(_mcp_result(response))
        status = str(payload.get("status", "")).strip().casefold()
        if not status and isinstance(payload.get("text"), str):
            text = str(payload["text"]).casefold()
            status = next(
                (
                    candidate
                    for candidate in (
                        "completed",
                        "success",
                        "succeeded",
                        "done",
                        "failed",
                        "error",
                        "canceled",
                        "cancelled",
                        "timeout",
                        "queued",
                        "running",
                        "stopped",
                    )
                    if re.search(rf"\b{candidate}\b", text)
                ),
                "",
            )
        if not status:
            raise EspClawAdapterError(
                "ESP_CLAW_JOB_STATUS_MISSING",
                "ESP-Claw did not return an asynchronous Lua job status.",
            )
        if status in {"completed", "complete", "success", "succeeded", "done"}:
            ok: bool | None = True
        elif status in {"failed", "error", "canceled", "cancelled", "timeout", "stopped"}:
            ok = False
        else:
            ok = None
        returned_job_id = payload.get("job_id") or payload.get("jobId") or payload.get("id")
        return EspClawAsyncJob(
            job_id=str(returned_job_id or fallback_job_id),
            status=status,
            ok=ok,
        )

    async def _mcp_request(
        self,
        endpoint: str,
        *,
        method: str,
        params: dict[str, Any],
        cancel: asyncio.Event,
        timeout_seconds: float,
    ) -> httpx.Response:
        return await self._request(
            "POST",
            endpoint,
            "",
            json_body={"jsonrpc": "2.0", "id": "zhangwen", "method": method, "params": params},
            cancel=cancel,
            timeout_seconds=timeout_seconds,
            accepted_statuses={200},
        )

    async def _request(
        self,
        method: str,
        endpoint: str,
        path: str,
        *,
        cancel: asyncio.Event,
        timeout_seconds: float,
        params: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
        raw_content: bytes | None = None,
        accepted_statuses: set[int] | None = None,
    ) -> httpx.Response:
        if cancel.is_set():
            raise EspClawAdapterCanceled()
        accepted = accepted_statuses or {200}
        try:
            async with httpx.AsyncClient(
                transport=self._transport,
                follow_redirects=False,
                timeout=httpx.Timeout(timeout_seconds),
            ) as client:
                response = await client.request(
                    method,
                    f"{endpoint}{path}",
                    params=params,
                    json=json_body,
                    content=raw_content,
                    headers={
                        "Accept": "application/json",
                        **(
                            {"Content-Type": "application/octet-stream"}
                            if raw_content is not None
                            else {}
                        ),
                    },
                )
        except httpx.TimeoutException as exc:
            raise EspClawAdapterError(
                "ESP_CLAW_REQUEST_TIMEOUT",
                "ESP-Claw request timed out.",
                retryable=True,
            ) from exc
        except httpx.HTTPError as exc:
            raise EspClawAdapterError(
                "ESP_CLAW_UNREACHABLE",
                "ESP-Claw endpoint could not be reached on the trusted LAN.",
                retryable=True,
            ) from exc
        if cancel.is_set():
            raise EspClawAdapterCanceled()
        if response.status_code not in accepted:
            raise EspClawAdapterError(
                "ESP_CLAW_HTTP_ERROR",
                f"ESP-Claw request failed with HTTP {response.status_code}.",
                retryable=response.status_code >= 500,
            )
        return response


def normalize_espclaw_endpoint(raw: str) -> str:
    """Backward-compatible name for Web Console origin validation."""

    return normalize_espclaw_web_endpoint(raw)


def normalize_espclaw_web_endpoint(raw: str) -> str:
    """Allow only explicit Web Console HTTP origins on the trusted LAN."""

    candidate = raw.strip()
    try:
        parsed = urlsplit(candidate)
        port = parsed.port
    except ValueError as exc:
        raise EspClawAdapterError("ESP_CLAW_ENDPOINT_INVALID", "ESP-Claw endpoint is invalid.") from exc
    if parsed.scheme.casefold() != "http" or not parsed.hostname:
        raise EspClawAdapterError(
            "ESP_CLAW_ENDPOINT_INVALID",
            "ESP-Claw pairing accepts only an http:// trusted-LAN endpoint.",
        )
    if parsed.username is not None or parsed.password is not None:
        raise EspClawAdapterError(
            "ESP_CLAW_ENDPOINT_CREDENTIALS_FORBIDDEN",
            "Credentials must not be embedded in an ESP-Claw endpoint URL.",
        )
    if parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
        raise EspClawAdapterError(
            "ESP_CLAW_ENDPOINT_ORIGIN_REQUIRED",
            "ESP-Claw endpoint must be an origin without a path, query, or fragment.",
        )
    hostname = parsed.hostname.casefold().rstrip(".")
    allowed = hostname.endswith(".local") and hostname != ".local"
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address is not None:
        allowed = (
            (address.is_private or address.is_link_local or address.is_loopback)
            and not address.is_multicast
            and not address.is_unspecified
        )
    if not allowed:
        raise EspClawAdapterError(
            "ESP_CLAW_ENDPOINT_NOT_PRIVATE",
            "ESP-Claw endpoint must use a private IP address or a .local hostname.",
        )
    if ":" in hostname:
        host_text = f"[{hostname}]"
    else:
        host_text = hostname
    netloc = host_text if port is None else f"{host_text}:{port}"
    return urlunsplit(("http", netloc, "", "", ""))


def normalize_espclaw_mcp_endpoint(raw: str) -> str:
    """Validate the independently advertised private MCP HTTP endpoint URL."""

    candidate = raw.strip()
    try:
        parsed = urlsplit(candidate)
        port = parsed.port
    except ValueError as exc:
        raise EspClawAdapterError("ESP_CLAW_MCP_ENDPOINT_INVALID", "ESP-Claw MCP endpoint is invalid.") from exc
    if parsed.scheme.casefold() != "http" or not parsed.hostname:
        raise EspClawAdapterError(
            "ESP_CLAW_MCP_ENDPOINT_INVALID",
            "ESP-Claw MCP endpoint must use http:// on the trusted LAN.",
        )
    if parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment:
        raise EspClawAdapterError(
            "ESP_CLAW_MCP_ENDPOINT_INVALID",
            "ESP-Claw MCP endpoint cannot contain credentials, query parameters, or a fragment.",
        )
    hostname = parsed.hostname.casefold().rstrip(".")
    if not _private_or_local_hostname(hostname):
        raise EspClawAdapterError(
            "ESP_CLAW_ENDPOINT_NOT_PRIVATE",
            "ESP-Claw MCP endpoint must use a private IP address or a .local hostname.",
        )
    raw_path = parsed.path or "/"
    if "//" in raw_path:
        raise EspClawAdapterError(
            "ESP_CLAW_MCP_ENDPOINT_INVALID",
            "ESP-Claw MCP endpoint path is not safe.",
        )
    path = raw_path if raw_path == "/" else raw_path.rstrip("/")
    if (
        not path.startswith("/")
        or any(
            not segment
            or segment in {".", ".."}
            or re.fullmatch(r"[A-Za-z0-9._~-]{1,64}", segment) is None
            for segment in path.split("/")[1:]
            if path != "/"
        )
    ):
        raise EspClawAdapterError(
            "ESP_CLAW_MCP_ENDPOINT_INVALID",
            "ESP-Claw MCP endpoint path is not safe.",
        )
    if ":" in hostname:
        host_text = f"[{hostname}]"
    else:
        host_text = hostname
    netloc = host_text if port is None else f"{host_text}:{port}"
    normalized_path = path if path == "/" else path.rstrip("/")
    return urlunsplit(("http", netloc, normalized_path, "", ""))


def _private_or_local_hostname(hostname: str) -> bool:
    allowed = hostname.endswith(".local") and hostname != ".local"
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address is not None:
        allowed = (
            (address.is_private or address.is_link_local or address.is_loopback)
            and not address.is_multicast
            and not address.is_unspecified
        )
    return allowed


def _web_storage_path(absolute_path: str) -> str:
    prefix = f"{ESP_CLAW_STORAGE_BASE_PATH}/"
    if not absolute_path.startswith(prefix):
        raise EspClawAdapterError(
            "ESP_CLAW_FILE_PATH_INVALID",
            "ESP-Claw file path must remain under /fatfs.",
        )
    relative = absolute_path.removeprefix(ESP_CLAW_STORAGE_BASE_PATH)
    if ".." in relative.split("/"):
        raise EspClawAdapterError(
            "ESP_CLAW_FILE_PATH_INVALID",
            "ESP-Claw file path traversal is forbidden.",
        )
    return relative


def _json_object(response: httpx.Response, code: str) -> dict[str, Any]:
    try:
        payload = response.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise EspClawAdapterError(code, "ESP-Claw returned invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise EspClawAdapterError(code, "ESP-Claw returned an invalid JSON object.")
    return payload


def _mcp_result(response: httpx.Response) -> dict[str, Any]:
    payload = _json_object(response, "ESP_CLAW_MCP_RESPONSE_INVALID")
    if payload.get("error") is not None:
        raise EspClawAdapterError(
            "ESP_CLAW_MCP_ERROR",
            "ESP-Claw MCP returned an error response.",
        )
    result = payload.get("result")
    if not isinstance(result, dict):
        raise EspClawAdapterError(
            "ESP_CLAW_MCP_RESPONSE_INVALID",
            "ESP-Claw MCP response did not contain a result object.",
        )
    return result


def _tool_payload(result: dict[str, Any]) -> dict[str, Any]:
    structured = result.get("structuredContent") or result.get("structured_content")
    if isinstance(structured, dict):
        return structured
    content = result.get("content")
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict) or not isinstance(item.get("text"), str):
                continue
            try:
                parsed = json.loads(item["text"])
            except json.JSONDecodeError:
                return {"text": item["text"]}
            if isinstance(parsed, dict):
                return parsed
    if isinstance(result.get("data"), dict):
        return result["data"]
    return result


def _storage_base_path(status: dict[str, Any]) -> str | None:
    direct = status.get("storage_base_path") or status.get("storageBasePath")
    if isinstance(direct, str):
        return direct
    storage = status.get("storage")
    if isinstance(storage, dict):
        nested = storage.get("base_path") or storage.get("basePath")
        return nested if isinstance(nested, str) else None
    return None


def _reported_board_id(status: dict[str, Any]) -> str | None:
    for key in ("board_id", "boardId", "board"):
        value = status.get(key)
        if isinstance(value, str) and value:
            return value
    system = status.get("system")
    if isinstance(system, dict):
        for key in ("board_id", "boardId", "board"):
            value = system.get(key)
            if isinstance(value, str) and value:
                return value
    return None
