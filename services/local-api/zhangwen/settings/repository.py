"""Compatibility projection for the historical single-provider settings API.

The versioned ProviderSettingsRepository is the source of truth. ``llm.json``
is retained only as a non-sensitive rollback projection until M11 removes the
legacy endpoint and file shape.
"""

from __future__ import annotations

import json
from pathlib import Path

from zhangwen.llm.contracts import LLMConfig, SaveLLMConfigRequest
from zhangwen.settings.provider_repository import ProviderSettingsRepository


class LLMSettingsRepository:
    def __init__(self, data_dir: Path) -> None:
        self._data_dir = Path(data_dir)
        self._config_dir = self._data_dir / "config"
        self._config_path = self._config_dir / "llm.json"

    @property
    def data_dir(self) -> Path:
        return self._data_dir

    def load(self, *, key_saved: bool, masked_api_key: str | None) -> LLMConfig:
        repository = ProviderSettingsRepository(self._data_dir)
        resolved = repository.resolve_runtime(
            workload=_creation_workload(),
        )
        return resolved.config.model_copy(
            update={
                "keySaved": key_saved,
                "maskedApiKey": masked_api_key,
            }
        )

    def save(
        self,
        request: SaveLLMConfigRequest,
        *,
        key_saved: bool,
        masked_api_key: str | None,
    ) -> LLMConfig:
        """Write only the temporary non-sensitive compatibility projection."""

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
        )
        self.save_projection(config)
        return config

    def save_projection(self, config: LLMConfig) -> None:
        self._config_dir.mkdir(parents=True, exist_ok=True)
        payload = config.model_dump(mode="json")
        for field in (
            "keySaved",
            "maskedApiKey",
            "providerConfigurationId",
            "providerConfigurationRevisionId",
            "routingProfileRevisionId",
        ):
            payload.pop(field, None)
        self._config_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _creation_workload():
    from zhangwen.settings.models import ModelWorkload

    return ModelWorkload.CREATION
