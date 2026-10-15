"""Bounded JSON-RPC/stdio PluginHost supervisor for editable package previews."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from zhangwen.domains.packages.models import PackagePluginHostError, PackageRevision


_WORKER_PATH = Path(__file__).with_name("plugin_worker.py")
MAX_REQUEST_BYTES = 256 * 1024
MAX_OUTPUT_BYTES = 64 * 1024
_PLUGIN_SLOTS = threading.BoundedSemaphore(4)


class PackagePluginHost:
    def __init__(self, data_dir: Path, *, timeout_seconds: float = 4.0) -> None:
        self._root = (Path(data_dir) / "plugin-host").resolve(strict=False)
        self._timeout_seconds = max(0.5, min(timeout_seconds, 10.0))

    def evaluate(
        self,
        *,
        revision: PackageRevision,
        manifest: dict[str, object],
        input_snapshot: dict[str, object],
    ) -> tuple[dict[str, object], list[dict[str, object]], list[str], int, int]:
        if not _PLUGIN_SLOTS.acquire(timeout=self._timeout_seconds):
            raise PackagePluginHostError("PluginHost 并发队列已满，请稍后重试。")
        try:
            return self._evaluate(
                revision=revision,
                manifest=manifest,
                input_snapshot=input_snapshot,
            )
        finally:
            _PLUGIN_SLOTS.release()

    def _evaluate(
        self,
        *,
        revision: PackageRevision,
        manifest: dict[str, object],
        input_snapshot: dict[str, object],
    ) -> tuple[dict[str, object], list[dict[str, object]], list[str], int, int]:
        self._root.mkdir(parents=True, exist_ok=True)
        request_id = f"plugin_{uuid.uuid4().hex}"
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "shadow.evaluate",
            "params": {
                "packageId": revision.package_id,
                "packageRevisionId": revision.id,
                "contentDigest": revision.content_digest,
                "displayName": str(manifest.get("displayName", "能力包"))[:120],
                "capabilities": _bounded_strings(manifest.get("capabilities")),
                "input": input_snapshot,
            },
        }
        encoded = json.dumps(request, ensure_ascii=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > MAX_REQUEST_BYTES:
            raise PackagePluginHostError("影子运行输入超过 PluginHost 上限。")
        command = (
            sys.executable,
            "-I",
            "-X",
            "utf8",
            str(_WORKER_PATH),
        )
        startupinfo = None
        creationflags = 0
        start_new_session = os.name != "nt"
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        started = time.perf_counter()
        try:
            process = subprocess.Popen(
                command,
                cwd=self._root,
                env=_minimal_environment(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,
                startupinfo=startupinfo,
                creationflags=creationflags,
                start_new_session=start_new_session,
            )
        except OSError as exc:
            raise PackagePluginHostError("隔离 PluginHost 无法启动。") from exc
        try:
            stdout, _stderr = process.communicate(encoded, timeout=self._timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            _terminate_process_tree(process)
            process.communicate()
            raise PackagePluginHostError("隔离 PluginHost 响应超时。") from exc
        duration_ms = max(0, round((time.perf_counter() - started) * 1000))
        output_bytes = len(stdout.encode("utf-8"))
        if process.returncode != 0 or output_bytes > MAX_OUTPUT_BYTES:
            raise PackagePluginHostError("隔离 PluginHost 返回失败或超出输出上限。")
        try:
            response = json.loads(stdout)
            if (
                not isinstance(response, dict)
                or response.get("jsonrpc") != "2.0"
                or response.get("id") != request_id
                or not isinstance(response.get("result"), dict)
            ):
                raise ValueError
            result = response["result"]
            output = result["output"]
            tool_plan = result["toolPlan"]
            messages = result["messages"]
            if not isinstance(output, dict) or not isinstance(tool_plan, list) or not isinstance(messages, list):
                raise ValueError
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
            raise PackagePluginHostError("隔离 PluginHost 输出未通过结构校验。") from exc
        return (
            {str(key): value for key, value in output.items()},
            [item for item in tool_plan if isinstance(item, dict)],
            [str(item)[:300] for item in messages[:32]],
            duration_ms,
            output_bytes,
        )


def _minimal_environment() -> dict[str, str]:
    environment = {
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP"):
        value = os.environ.get(key)
        if value:
            environment[key] = value
    return environment


def _bounded_strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item)[:160] for item in value[:64]]


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
            timeout=3,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
