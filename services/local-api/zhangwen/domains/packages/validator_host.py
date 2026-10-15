"""Supervisor for isolated validation of editable package drafts."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

from zhangwen.domains.packages.models import (
    CapabilityPackage,
    PackagePluginHostError,
    PackageValidationSummary,
)
from zhangwen.domains.packages.plugin_host import (
    _minimal_environment,
    _terminate_process_tree,
)


_WORKER_PATH = Path(__file__).with_name("validator_worker.py")
_VALIDATION_SLOTS = threading.BoundedSemaphore(2)
MAX_REQUEST_BYTES = 768 * 1024
MAX_OUTPUT_BYTES = 128 * 1024


class PackageValidationHost:
    def __init__(self, data_dir: Path, *, timeout_seconds: float = 5.0) -> None:
        self._root = (Path(data_dir) / "package-validator").resolve(strict=False)
        self._timeout_seconds = max(1.0, min(timeout_seconds, 10.0))

    def validate(
        self,
        package: CapabilityPackage,
        files: dict[str, str],
    ) -> PackageValidationSummary:
        if not _VALIDATION_SLOTS.acquire(timeout=self._timeout_seconds):
            raise PackagePluginHostError("能力包校验队列已满，请稍后重试。")
        try:
            return self._validate(package, files)
        finally:
            _VALIDATION_SLOTS.release()

    def _validate(
        self,
        package: CapabilityPackage,
        files: dict[str, str],
    ) -> PackageValidationSummary:
        self._root.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(
            {
                "package": package.model_dump(mode="json", by_alias=True),
                "files": files,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        if len(encoded.encode("utf-8")) > MAX_REQUEST_BYTES:
            raise PackagePluginHostError("能力包草稿超过隔离校验输入上限。")
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
            raise PackagePluginHostError("隔离校验 Worker 无法启动。") from exc
        try:
            stdout, _stderr = process.communicate(encoded, timeout=self._timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            _terminate_process_tree(process)
            process.communicate()
            raise PackagePluginHostError("隔离校验 Worker 响应超时。") from exc
        if process.returncode != 0 or len(stdout.encode("utf-8")) > MAX_OUTPUT_BYTES:
            raise PackagePluginHostError("隔离校验 Worker 返回失败或超出输出上限。")
        try:
            return PackageValidationSummary.model_validate_json(stdout)
        except ValueError as exc:
            raise PackagePluginHostError("隔离校验结果未通过结构校验。") from exc
