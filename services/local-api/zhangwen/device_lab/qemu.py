"""Verified optional Espressif QEMU runtime boundary."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

from zhangwen.device_lab.models import QemuRuntimeStatus


class QemuRuntimeManager:
    def __init__(self, data_dir: Path) -> None:
        self._root = Path(data_dir) / "runtimes" / "qemu-esp32s3"
        self._executable = self._root / "qemu-system-xtensa.exe"
        self._manifest = self._root / "runtime-manifest.json"

    def status(self) -> QemuRuntimeStatus:
        if not self._executable.is_file() or not self._manifest.is_file():
            return QemuRuntimeStatus(
                available=False,
                reason="ESP32-S3 QEMU 可选运行时尚未安装。",
            )
        try:
            value = json.loads(self._manifest.read_text(encoding="utf-8"))
            version = str(value["version"])
            expected = str(value["sha256"]).lower()
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return QemuRuntimeStatus(available=False, reason="QEMU 运行时清单无效。")
        actual = hashlib.sha256(self._executable.read_bytes()).hexdigest()
        if actual != expected:
            return QemuRuntimeStatus(available=False, reason="QEMU 运行时完整性校验失败。")
        return QemuRuntimeStatus(available=True, version=version)

    def build_argv(self, flash_image: Path) -> list[str]:
        if not self.status().available:
            raise RuntimeError("QEMU runtime unavailable")
        resolved = flash_image.resolve()
        if not resolved.is_file():
            raise RuntimeError("simulation image missing")
        return [
            str(self._executable.resolve()),
            "-M", "esp32s3",
            "-nographic",
            "-nic", "none",
            "-drive", f"file={resolved},if=mtd,format=raw",
        ]

    async def start(self, flash_image: Path) -> asyncio.subprocess.Process:
        argv = self.build_argv(flash_image)
        return await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(flash_image.parent),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
