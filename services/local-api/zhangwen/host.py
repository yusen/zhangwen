"""Browser/Tauri host boundary for capabilities with local side effects."""

from __future__ import annotations

import hmac
import os

from fastapi import HTTPException, Request


def is_web_host(request: Request) -> bool:
    declared_host = request.headers.get("x-zhangwen-host", "").lower()
    origin = request.headers.get("origin", "").lower().rstrip("/")
    return declared_host == "web" or origin in {
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    }


def has_desktop_host_access(request: Request) -> bool:
    expected_token = os.environ.get("ZHANGWEN_DESKTOP_CAPABILITY_TOKEN", "")
    supplied_token = request.headers.get("x-zhangwen-capability-token", "")
    declared_host = request.headers.get("x-zhangwen-host", "").lower()
    return bool(
        expected_token
        and declared_host == "tauri"
        and supplied_token
        and hmac.compare_digest(expected_token, supplied_token)
    )


def require_desktop_host(request: Request, capability: str) -> None:
    """Reject side-effectful local-host capabilities requested by the Web UI."""

    if has_desktop_host_access(request):
        return
    if request.headers.get("x-zhangwen-bridge-lease", "").strip():
        from zhangwen.local_bridge.service import (
            LocalBridgeError,
            LocalBridgeService,
        )

        try:
            if LocalBridgeService().verify_request(request, capability):
                return
        except LocalBridgeError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail={
                    **exc.detail(),
                    "capability": capability,
                },
            ) from exc
    declared_host = request.headers.get("x-zhangwen-host", "").lower()
    if declared_host == "tauri":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "DESKTOP_CAPABILITY_MISMATCH",
                "message": (
                    "桌面窗口与 FastAPI Sidecar 的本地会话不一致。"
                    "请关闭其他掌问窗口后重新启动应用。"
                ),
                "capability": capability,
                "retryable": True,
            },
        )
    messages = {
        "serial_scan": "当前浏览器模式不支持本地串口扫描，请在桌面模式中完成此操作。",
        "serial_connection": "当前浏览器模式不支持本地串口连接，请在桌面模式中完成此操作。",
        "device_upload": "当前浏览器模式不支持设备上传，请在桌面模式中完成此操作。",
        "device_flash": "当前浏览器模式不支持固件烧录，请在桌面模式中完成此操作。",
        "local_cad": "当前浏览器模式不支持本地 CAD 执行，请在桌面模式中完成此操作。",
        "local_tool": "当前浏览器模式不支持本地工具执行，请在桌面模式中完成此操作。",
        "shell": "当前浏览器模式不支持本地 Shell，请在桌面模式中完成此操作。",
        "provider_credentials": "浏览器不能提交或修改模型服务密钥，请在掌问桌面应用中完成。",
        "desktop_capability": "当前浏览器模式不支持桌面能力校验。",
    }
    raise HTTPException(
        status_code=409,
        detail={
            "code": "HOST_CAPABILITY_UNAVAILABLE",
            "message": messages.get(capability, "当前浏览器模式不支持此本地能力。"),
            "capability": capability,
            "retryable": False,
        },
    )
