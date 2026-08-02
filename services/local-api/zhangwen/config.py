"""掌问本地服务 — 配置"""

import os
from pathlib import Path

from pydantic import BaseModel


_LOCAL_UI_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://localhost:1420",
    "http://tauri.localhost",
    "tauri://localhost",
]


def _configured_bridge_origins() -> list[str]:
    return [
        item.strip().rstrip("/")
        for item in os.environ.get("ZHANGWEN_BRIDGE_ALLOWED_ORIGINS", "").split(",")
        if item.strip()
    ]


class LLMTestMode:
    STANDARD = "standard"
    FAKE = "fake"
    PAID = "paid"


def current_llm_test_mode() -> str:
    mode = os.environ.get("ZHANGWEN_LLM_TEST_MODE", "").strip().lower()
    if mode in {LLMTestMode.FAKE, LLMTestMode.PAID}:
        return mode
    return LLMTestMode.STANDARD


class Settings(BaseModel):
    """应用配置"""

    app_name: str = "掌问本地服务"
    version: str = "0.1.0"
    host: str = "127.0.0.1"
    port: int = 8100
    cors_origins: list[str] = list(dict.fromkeys([*_LOCAL_UI_ORIGINS, *_configured_bridge_origins()]))
    bridge_allowed_origins: list[str] = list(
        dict.fromkeys(
            ["http://127.0.0.1:5173", "http://localhost:5173", *_configured_bridge_origins()]
        )
    )
    data_dir: Path = Path(
        os.environ.get(
            "ZHANGWEN_DATA_DIR",
            Path(__file__).resolve().parents[1] / ".data",
        )
    )
    credential_service: str = "zhangwen.deepseek"
    credential_account: str = "default"
    cloud_auth_base_url: str = os.environ.get("ZHANGWEN_CLOUD_AUTH_BASE_URL", "").strip()
    cloud_auth_credential_service: str = "zhangwen.cloud-auth.refresh"


settings = Settings()
