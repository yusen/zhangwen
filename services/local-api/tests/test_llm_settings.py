from pathlib import Path

import httpx
import pytest

from zhangwen.llm.contracts import (
    ChatRequest,
    ConnectionTestRequest,
    LLMModelId,
    LLMProviderId,
    SaveLLMConfigRequest,
    ThinkingMode,
)
from zhangwen.llm.deepseek import DeepSeekProvider
from zhangwen.security.credentials import MemoryCredentialStore
from zhangwen.settings.repository import LLMSettingsRepository
from zhangwen.settings.service import LLMSettingsService


def make_service(
    tmp_path: Path,
    credentials: MemoryCredentialStore | None = None,
    provider: DeepSeekProvider | None = None,
) -> LLMSettingsService:
    return LLMSettingsService(
        LLMSettingsRepository(tmp_path),
        credentials or MemoryCredentialStore(),
        provider or DeepSeekProvider(),
    )


def test_save_config_does_not_write_api_key_to_json(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    config = service.save_config(
        SaveLLMConfigRequest(
            apiKey="sk-test-secret-value",
            defaultModel=LLMModelId.DEEPSEEK_V4_PRO,
            thinkingMode=ThinkingMode.ENABLED,
            reasoningEffort="high",
        )
    )

    assert config.keySaved is True
    assert config.maskedApiKey == "sk-****alue"
    stored = (tmp_path / "config" / "llm.json").read_text(encoding="utf-8")
    assert "sk-test-secret-value" not in stored
    assert "apiKey" not in stored


@pytest.mark.asyncio
async def test_connection_without_api_key_returns_config_error(
    tmp_path: Path,
) -> None:
    result = await make_service(tmp_path).test_connection(ConnectionTestRequest())

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "CONFIG_MISSING"
    assert result.message == "请先在设置中配置所选模型服务的 API Key。"


@pytest.mark.asyncio
async def test_connection_uses_mock_transport(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/chat/completions"
        assert request.headers["authorization"] == "Bearer sk-test-secret-value"
        return httpx.Response(200, json={"choices": []})

    credentials = MemoryCredentialStore()
    credentials.set_password("zhangwen.deepseek", "default", "sk-test-secret-value")
    service = make_service(
        tmp_path,
        credentials,
        DeepSeekProvider(transport=httpx.MockTransport(handler)),
    )

    result = await service.test_connection(ConnectionTestRequest())

    assert result.ok is True
    assert result.model == LLMModelId.DEEPSEEK_V4_FLASH


def test_provider_credentials_are_isolated(tmp_path: Path) -> None:
    credentials = MemoryCredentialStore()
    service = make_service(tmp_path, credentials)

    qwen = service.save_config(
        SaveLLMConfigRequest(
            provider=LLMProviderId.QWEN,
            baseUrl="https://dashscope.aliyuncs.com/compatible-mode/v1",
            defaultModel=LLMModelId.QWEN_3_7_MAX,
            apiKey="sk-qwen-secret",
        )
    )
    assert qwen.keySaved is True
    assert credentials.get_password("zhangwen.qwen", "default") == "sk-qwen-secret"
    assert credentials.get_password("zhangwen.deepseek", "default") is None

    deepseek = service.save_config(SaveLLMConfigRequest())
    assert deepseek.keySaved is False
    assert credentials.get_password("zhangwen.qwen", "default") == "sk-qwen-secret"


def test_custom_provider_model_persists_and_is_used_by_transport(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    config = service.save_config(
        SaveLLMConfigRequest(
            provider=LLMProviderId.KIMI,
            baseUrl="https://api.moonshot.cn/v1",
            defaultModel="kimi-preview-custom",
            customModels=[
                {
                    "id": "kimi-preview-custom",
                    "label": "kimi-preview-custom",
                    "provider": LLMProviderId.KIMI,
                    "supportsThinking": True,
                    "supportsStreaming": True,
                    "isCustom": True,
                }
            ],
        )
    )

    assert config.defaultModel == "kimi-preview-custom"
    assert [model.id for model in config.customModels] == ["kimi-preview-custom"]
    reloaded = service.get_config()
    assert reloaded.defaultModel == "kimi-preview-custom"
    assert [model.id for model in reloaded.customModels] == ["kimi-preview-custom"]
    payload = DeepSeekProvider().build_payload(
        ChatRequest(messages=[]),
        reloaded,
        stream=False,
    )
    assert payload["model"] == "kimi-preview-custom"


@pytest.mark.parametrize(
    "model_id",
    ["", " model", "model?token=secret", "model\\name", "x" * 129],
)
def test_custom_model_id_rejects_unsafe_values(model_id: str) -> None:
    with pytest.raises(ValueError):
        SaveLLMConfigRequest(
            provider=LLMProviderId.KIMI,
            baseUrl="https://api.moonshot.cn/v1",
            defaultModel=model_id,
            customModels=[
                {
                    "id": model_id,
                    "label": model_id or "empty",
                    "provider": LLMProviderId.KIMI,
                    "supportsThinking": True,
                    "supportsStreaming": True,
                    "isCustom": True,
                }
            ],
        )


@pytest.mark.asyncio
async def test_missing_key_result_uses_selected_provider(tmp_path: Path) -> None:
    result = await make_service(tmp_path).test_connection(
        ConnectionTestRequest(
            config=SaveLLMConfigRequest(
                provider=LLMProviderId.KIMI,
                baseUrl="https://api.moonshot.cn/v1",
                defaultModel=LLMModelId.KIMI_K3,
            )
        )
    )

    assert result.ok is False
    assert result.provider == LLMProviderId.KIMI
    assert result.model == LLMModelId.KIMI_K3
