"""Opt-in managed installation updates; fixed repository/installer, never model tools.

The running server stays alive. The existing installer verifies and prepares an
immutable version before selecting it for the next launch. User data is shared.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

REPOSITORY_REF = "https://api.github.com/repos/yusen/zhangwen/git/ref/heads/main"
GITEE_REF = "https://gitee.com/api/v5/repos/ys_Ethan/zhangwen/branches/main"
SHA = re.compile(r"[0-9a-f]{40}")


class InstallUpdateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    checkToken: str = Field(min_length=20, max_length=100)
    confirmed: Literal[True]

    @field_validator("confirmed", mode="before")
    @classmethod
    def exact_confirmation(cls, value):
        if value is not True:
            raise ValueError("explicit confirmation required")
        return value


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def latest_revision(source: str = "github") -> str:
    if source not in {"gitee", "github"}:
        raise ValueError("invalid distribution source")
    # No model URL, browser-supplied URL, credentials, redirect or proxy routing.
    started = time.monotonic()
    with httpx.Client(timeout=httpx.Timeout(10, connect=5), trust_env=False, follow_redirects=False) as client:
        with client.stream("GET", GITEE_REF if source == "gitee" else REPOSITORY_REF, headers={"User-Agent": "zhangwen-update-check", "Accept": "application/json"}) as response:
            response.raise_for_status()
            content = bytearray()
            for chunk in response.iter_bytes():
                content.extend(chunk)
                if len(content) > 16_384 or time.monotonic() - started > 15:
                    raise ValueError("oversized repository response")
    value = json.loads(content)["commit" if source == "gitee" else "object"]["sha"]
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise ValueError("invalid repository revision")
    return value


def verify_installer(root: Path) -> None:
    """Refuse edited installed sources; the installer verifies the next archive."""
    lines = (root / "DEPLOYMENT.sha256").read_text(encoding="utf-8").splitlines()
    seen: set[str] = set()
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_./@+ -]+)", line)
        if not match:
            raise ValueError("invalid deployment manifest")
        digest, relative = match.groups()
        file = root / relative
        if relative.startswith('/') or '..' in Path(relative).parts or relative in seen or not file.resolve().is_relative_to(root) or not file.is_file():
            raise ValueError("unsafe deployment manifest")
        seen.add(relative)
        if hashlib.sha256(file.read_bytes()).hexdigest() != digest:
            raise ValueError("modified installed sources")
    if not {"install.ps1", "install.sh", "scripts/bootstrap-windows.ps1", "scripts/bootstrap-unix.sh"} <= seen:
        raise ValueError("missing verified installer")


class UpdateManager:
    def __init__(self, root: Path, data_dir: Path):
        self.root = root.resolve()
        self.install_root: Path | None = None
        self.current: str | None = None
        self.source = "github"  # Existing installations keep their original channel.
        if SHA.fullmatch(self.root.name) and self.root.parent.name == "versions" and sys.platform in {"win32", "darwin"}:
            candidate = self.root.parent.parent
            try:
                selected = (candidate / "current.txt").read_text().strip()
                if (SHA.fullmatch(selected) and (candidate / "versions" / selected).is_dir()
                        and data_dir.resolve() == (candidate / "data").resolve()
                        and (self.root / "DEPLOYMENT.sha256").is_file()):
                    self.install_root, self.current = candidate, self.root.name
            except OSError:
                pass
        self.source_error = False
        if self.install_root:
            try:
                marker = self.root / ".runtime/distribution-source.txt"
                if marker.exists():
                    self.source = marker.read_text(encoding="utf-8").strip()
                self.source_error = self.source not in {"gitee", "github"}
            except (OSError, UnicodeError):
                self.source_error = True
        self.lock = threading.RLock()
        self.checking = False
        self.checked_clock = 0.0
        self.result: dict = {
            "deployment": "managed" if self.install_root else "development",
            "currentRevision": self.current, "latestRevision": None, "checkedAt": None,
            "state": "unchecked", "message": "尚未检查更新。", "canInstall": False,
            "checkToken": None, "job": None,
        }

    def status(self) -> dict:
        with self.lock:
            return json.loads(json.dumps(self.result))

    def check(self) -> dict:
        with self.lock:
            if self.checking or (self.checked_clock and time.monotonic() - self.checked_clock < 30):
                return self.status()
            self.checking = True
        try:
            if self.source_error:
                raise ValueError("invalid installed distribution source")
            revision = latest_revision(self.source)
            with self.lock:
                if self.result["job"] and self.result["job"]["state"] == "failed":
                    self.result["job"] = None
                self.result.update(latestRevision=revision, checkedAt=now(), checkToken=secrets.token_urlsafe(32))
                if not self.install_root:
                    self.result.update(state="development", canInstall=False, message="当前是开发工作区，可查看线上版本；请通过安装器部署后使用平台内更新。")
                elif revision == self.current:
                    self.result.update(state="current", canInstall=False, message="当前已是最新版本。")
                else:
                    selected = (self.install_root / "current.txt").read_text().strip()
                    ready = selected == revision
                    self.result.update(state="available", canInstall=not ready, message="新版本已安装，下次启动生效。" if ready else "发现新版本。是否更新？")
                    if ready and not self.result["job"]:
                        self.result["job"] = {"state": "ready", "revision": revision, "message": "新版本已安装，下次启动生效。", "startedAt": now()}
        except (httpx.HTTPError, OSError, ValueError, KeyError, TypeError):
            with self.lock:
                self.result.update(state="error", message="无法检查更新，请检查安装来源配置或网络后重试；代码托管服务也可能暂时限流。", canInstall=False, checkToken=None, checkedAt=now())
        finally:
            with self.lock:
                self.checked_clock = time.monotonic()
                self.checking = False
        return self.status()

    def install(self, request: InstallUpdateInput) -> dict:
        with self.lock:
            if not self.install_root:
                raise HTTPException(409, "开发工作区不能原地更新。请使用一键安装器部署。")
            if self.result["job"] and self.result["job"]["state"] in {"installing", "ready"}:
                raise HTTPException(409, "更新已在安装或等待重启，请勿重复安装。")
            if (self.checking or not self.result["canInstall"] or request.revision != self.result["latestRevision"]
                    or not secrets.compare_digest(request.checkToken, self.result["checkToken"] or "")
                    or time.monotonic() - self.checked_clock > 900):
                raise HTTPException(409, "更新信息已过期，请重新检查后确认。")
            # Never write into this development checkout or accept a command/URL.
            try:
                verify_installer(self.root)
            except (OSError, ValueError):
                raise HTTPException(409, "安装目录文件被修改或缺失，已保留原文件；请先修复安装目录。") from None
            self.result["job"] = {"state": "installing", "revision": request.revision, "startedAt": now(), "message": "正在下载、校验并准备新版本，可能需要几分钟。当前平台可以继续使用。"}
            self.result["canInstall"] = False
            threading.Thread(target=self._install, args=(request.revision,), daemon=True, name="zhangwen-update").start()
            return self.status()

    def _install(self, revision: str) -> None:
        assert self.install_root is not None
        message = "更新失败，当前服务仍可使用；请查看安装目录 updates 下的日志后重试。"
        state = "failed"
        try:
            log_dir = self.install_root / "updates"
            log_dir.mkdir(exist_ok=True)
            env = dict(os.environ)
            env.update(ZHANGWEN_INSTALL_DIR=str(self.install_root), ZHANGWEN_REVISION=revision, ZHANGWEN_NO_START="1", ZHANGWEN_SOURCE=self.source)
            if sys.platform == "win32":
                # -NoProfile does not discard paths inherited from PowerShell 7.
                # Let Windows PowerShell construct its own module search path.
                for key in tuple(env):
                    if key.casefold() == "psmodulepath":
                        del env[key]
                powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
                command = [str(powershell), "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(self.root / "install.ps1"), "-InstallDir", str(self.install_root), "-Revision", revision, "-Source", self.source, "-NoStart"]
                options = {"creationflags": subprocess.CREATE_NO_WINDOW}
            else:
                command = ["/bin/bash", str(self.root / "install.sh")]
                options = {"start_new_session": True}
            with (log_dir / f"{revision}.log").open("wb") as log:
                result = subprocess.run(command, cwd=self.root, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, shell=False, **options)
            selected = (self.install_root / "current.txt").read_text().strip()
            if selected == revision:
                state, message = "ready", "新版本已安装。请先保存项目，关闭原服务窗口，再用启动图标打开平台。"
            elif result.returncode:
                message = "下载、校验或环境准备失败，原启动版本保留。详情见安装目录 updates 下的日志。"
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
        with self.lock:
            self.result["job"].update(state=state, message=message, finishedAt=now())
            self.result["canInstall"] = state == "failed"
