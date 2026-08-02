"""Non-sensitive LLM settings repository."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from zhangwen.llm.contracts import LLMConfig, SaveLLMConfigRequest


class LLMSettingsRepository:
    def __init__(self, data_dir: Path) -> None:
        self._config_dir = data_dir / "config"
        self._config_path = self._config_dir / "llm.json"

    def load(self, *, key_saved: bool, masked_api_key: str | None) -> LLMConfig:
        if not self._config_path.exists():
            return LLMConfig(keySaved=key_saved, maskedApiKey=masked_api_key)

        data = json.loads(self._config_path.read_text(encoding="utf-8"))
        return LLMConfig(
            **data,
            keySaved=key_saved,
            maskedApiKey=masked_api_key,
        )

    def save(
        self,
        request: SaveLLMConfigRequest,
        *,
        key_saved: bool,
        masked_api_key: str | None,
    ) -> LLMConfig:
        self._config_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now(UTC).isoformat()
        config = LLMConfig(
            provider=request.provider,
            baseUrl=request.baseUrl.rstrip("/"),
            defaultModel=request.defaultModel,
            customModels=request.customModels,
            thinkingMode=request.thinkingMode,
            reasoningEffort=request.reasoningEffort,
            timeoutSeconds=request.timeoutSeconds,
            keySaved=key_saved,
            maskedApiKey=masked_api_key,
            updatedAt=now,
        )

        payload = config.model_dump(mode="json")
        payload.pop("keySaved", None)
        payload.pop("maskedApiKey", None)
        self._config_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return config
