"""健康检查路由"""

from fastapi import APIRouter, Request

from zhangwen.config import LLMTestMode, current_llm_test_mode, settings
from zhangwen.host import require_desktop_host
from zhangwen.runtime import get_uptime_seconds

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str | float | bool]:
    """返回服务健康状态"""
    mode = current_llm_test_mode()
    return {
        "status": "ok",
        "version": settings.version,
        "uptimeSeconds": round(get_uptime_seconds(), 2),
        "llmTestMode": mode,
        "usesPaidLlm": mode != LLMTestMode.FAKE,
    }


@router.get("/health/desktop-capability")
async def desktop_capability_check(request: Request) -> dict[str, str | bool]:
    """Verify that the caller and Sidecar share the current desktop token."""

    require_desktop_host(request, "desktop_capability")
    return {"status": "ok", "desktopCapability": True}
