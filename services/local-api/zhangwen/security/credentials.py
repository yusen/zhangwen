"""API Key credential storage.

The production adapter uses Windows Credential Manager and never writes
API keys into project or settings JSON files.
"""

from __future__ import annotations

import ctypes
import os
import re
from ctypes import wintypes
from typing import Protocol


class CredentialStore(Protocol):
    def get_password(self, service: str, account: str) -> str | None:
        """Read a secret from secure storage."""

    def set_password(self, service: str, account: str, password: str) -> None:
        """Write a secret to secure storage."""

    def delete_password(self, service: str, account: str) -> None:
        """Delete a secret from secure storage."""


class CredentialStoreError(RuntimeError):
    """Raised when secure credential storage is unavailable or fails."""


class MemoryCredentialStore:
    """Test-only credential store."""

    def __init__(self) -> None:
        self._values: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, account: str) -> str | None:
        return self._values.get((service, account))

    def set_password(self, service: str, account: str, password: str) -> None:
        self._values[(service, account)] = password

    def delete_password(self, service: str, account: str) -> None:
        self._values.pop((service, account), None)


def credential_service_for_provider(provider: str) -> str:
    """Return an isolated credential target while preserving DeepSeek compatibility."""

    return "zhangwen.deepseek" if provider == "deepseek" else f"zhangwen.{provider}"


def credential_service_for_configuration(configuration_id: str) -> str:
    """Return the isolated Credential Manager target for a Provider config."""

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,159}", configuration_id):
        raise CredentialStoreError("模型服务配置标识无效。")
    return f"zhangwen.provider.{configuration_id}"


class BackendCredentialStore:
    """Backend-only environment override with Windows Credential Manager fallback."""

    def __init__(self, environment_variable: str | None = None) -> None:
        self._environment_variable = environment_variable
        self._windows = WindowsCredentialStore()

    def get_password(self, service: str, account: str) -> str | None:
        environment_variable = self._environment_variable or {
            "zhangwen.deepseek": "ZHANGWEN_DEEPSEEK_API_KEY",
            "zhangwen.qwen": "ZHANGWEN_QWEN_API_KEY",
            "zhangwen.glm": "ZHANGWEN_GLM_API_KEY",
            "zhangwen.kimi": "ZHANGWEN_KIMI_API_KEY",
        }.get(service)
        environment_value = (
            os.environ.get(environment_variable, "").strip()
            if environment_variable
            else ""
        )
        if environment_value:
            return environment_value
        return self._windows.get_password(service, account)

    def set_password(self, service: str, account: str, password: str) -> None:
        self._windows.set_password(service, account, password)

    def delete_password(self, service: str, account: str) -> None:
        self._windows.delete_password(service, account)


if os.name == "nt":
    advapi32 = ctypes.WinDLL("Advapi32.dll")

    CRED_TYPE_GENERIC = 1
    CRED_PERSIST_LOCAL_MACHINE = 2

    class CREDENTIAL(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD),
            ("Type", wintypes.DWORD),
            ("TargetName", wintypes.LPWSTR),
            ("Comment", wintypes.LPWSTR),
            ("LastWritten", wintypes.FILETIME),
            ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
            ("Persist", wintypes.DWORD),
            ("AttributeCount", wintypes.DWORD),
            ("Attributes", wintypes.LPVOID),
            ("TargetAlias", wintypes.LPWSTR),
            ("UserName", wintypes.LPWSTR),
        ]

    PCREDENTIAL = ctypes.POINTER(CREDENTIAL)

    advapi32.CredReadW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(PCREDENTIAL),
    ]
    advapi32.CredReadW.restype = wintypes.BOOL
    advapi32.CredWriteW.argtypes = [ctypes.POINTER(CREDENTIAL), wintypes.DWORD]
    advapi32.CredWriteW.restype = wintypes.BOOL
    advapi32.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
    advapi32.CredDeleteW.restype = wintypes.BOOL
    advapi32.CredFree.argtypes = [wintypes.LPVOID]
    advapi32.CredFree.restype = None


class WindowsCredentialStore:
    """Windows Credential Manager adapter."""

    def _target(self, service: str, account: str) -> str:
        return f"{service}:{account}"

    def get_password(self, service: str, account: str) -> str | None:
        if os.name != "nt":
            raise CredentialStoreError("当前系统不支持 Windows Credential Manager。")

        target = self._target(service, account)
        credential = PCREDENTIAL()
        ok = advapi32.CredReadW(target, CRED_TYPE_GENERIC, 0, ctypes.byref(credential))
        if not ok:
            return None

        try:
            blob_size = credential.contents.CredentialBlobSize
            blob = credential.contents.CredentialBlob
            raw = ctypes.string_at(blob, blob_size)
            return raw.decode("utf-16-le")
        finally:
            advapi32.CredFree(credential)

    def set_password(self, service: str, account: str, password: str) -> None:
        if os.name != "nt":
            raise CredentialStoreError("当前系统不支持 Windows Credential Manager。")

        encoded = password.encode("utf-16-le")
        blob = (ctypes.c_ubyte * len(encoded)).from_buffer_copy(encoded)
        credential = CREDENTIAL()
        credential.Type = CRED_TYPE_GENERIC
        credential.TargetName = self._target(service, account)
        credential.CredentialBlobSize = len(encoded)
        credential.CredentialBlob = blob
        credential.Persist = CRED_PERSIST_LOCAL_MACHINE
        credential.UserName = account

        ok = advapi32.CredWriteW(ctypes.byref(credential), 0)
        if not ok:
            raise CredentialStoreError("API Key 写入 Windows Credential Manager 失败。")

    def delete_password(self, service: str, account: str) -> None:
        if os.name != "nt":
            raise CredentialStoreError("当前系统不支持 Windows Credential Manager。")

        advapi32.CredDeleteW(self._target(service, account), CRED_TYPE_GENERIC, 0)
