"""Compatibility service over the single versioned Provider settings platform."""

from __future__ import annotations

from zhangwen.config import settings
from zhangwen.llm.contracts import (
    ConnectionTestRequest,
    ConnectionTestResult,
    LLMConfig,
    LLMErrorCode,
    LLMProviderId,
    SaveLLMConfigRequest,
)
from zhangwen.llm.errors import make_llm_error
from zhangwen.llm.gateway import LLMProvider
from zhangwen.security.credentials import (
    CredentialStore,
    credential_service_for_configuration,
)
from zhangwen.security.redaction import mask_api_key
from zhangwen.settings.models import (
    CreateProviderConfigurationRequest,
    ModelRoutingTarget,
    ProviderConnectionTestRequest,
    ProviderPresetId,
    SaveModelRoutingRequest,
    UpdateProviderConfigurationRequest,
)
from zhangwen.settings.provider_repository import ProviderSettingsRepository
from zhangwen.settings.provider_service import ProviderSettingsService
from zhangwen.settings.repository import LLMSettingsRepository
from zhangwen.settings.url_security import ProviderUrlError, validate_provider_base_url


class LLMSettingsService:
    """Keep `/settings/llm` working while all state lives in the new platform."""

    def __init__(
        self,
        repository: LLMSettingsRepository,
        credentials: CredentialStore,
        provider: LLMProvider,
    ) -> None:
        self._legacy_repository = repository
        self._credentials = credentials
        self._provider = provider
        self._repository = ProviderSettingsRepository(repository.data_dir)
        self._providers = ProviderSettingsService(
            self._repository,
            credentials,
            provider,
        )

    def get_config(self) -> LLMConfig:
        profile = self._repository.get_routing_profile()
        configuration = self._repository.get_configuration(
            profile.default_target.configuration_id
        )
        api_key = self._credential(configuration.id)
        return LLMConfig(
            provider=configuration.provider,
            baseUrl=configuration.base_url,
            defaultModel=profile.default_target.model,
            customModels=configuration.custom_models,
            thinkingMode=configuration.thinking_mode,
            reasoningEffort=configuration.reasoning_effort,
            timeoutSeconds=configuration.timeout_seconds,
            keySaved=api_key is not None,
            maskedApiKey=mask_api_key(api_key),
            updatedAt=configuration.updated_at,
            providerConfigurationId=configuration.id,
            providerConfigurationRevisionId=configuration.revision_id,
            routingProfileRevisionId=profile.revision_id,
        )

    def save_config(self, request: SaveLLMConfigRequest) -> LLMConfig:
        profile = self._repository.get_routing_profile()
        configurations = self._repository.list_configurations()
        current = self._repository.get_configuration(
            profile.default_target.configuration_id
        )
        selected = current
        if current.provider != request.provider:
            selected = next(
                (
                    item
                    for item in configurations
                    if item.provider == request.provider and item.enabled
                ),
                None,
            )
        if selected is None:
            selected = self._providers.create_configuration(
                CreateProviderConfigurationRequest(
                    presetId=_preset_id(request.provider),
                    name=_provider_label(request.provider),
                    baseUrl=request.baseUrl,
                    defaultModel=request.defaultModel,
                    customModels=request.customModels,
                    thinkingMode=request.thinkingMode,
                    reasoningEffort=request.reasoningEffort,
                    timeoutSeconds=request.timeoutSeconds,
                )
            )
        else:
            selected = self._providers.update_configuration(
                selected.id,
                UpdateProviderConfigurationRequest(
                    expectedRevision=selected.revision,
                    name=selected.name,
                    baseUrl=request.baseUrl,
                    defaultModel=request.defaultModel,
                    customModels=request.customModels,
                    thinkingMode=request.thinkingMode,
                    reasoningEffort=request.reasoningEffort,
                    timeoutSeconds=request.timeoutSeconds,
                    allowPrivateNetwork=selected.allow_private_network,
                    privateNetworkConfirmed=selected.allow_private_network,
                    enabled=True,
                ),
            )

        fallback = profile.fallback_target
        if (
            fallback is not None
            and fallback.configuration_id == selected.id
            and str(fallback.model) == str(request.defaultModel)
        ):
            fallback = None
        profile = self._repository.save_routing_profile(
            SaveModelRoutingRequest(
                expectedRevision=profile.revision,
                defaultTarget=ModelRoutingTarget(
                    configurationId=selected.id,
                    model=request.defaultModel,
                ),
                fallbackTarget=fallback,
                workloadRoutes=profile.workload_routes,
            )
        )
        if request.apiKey:
            self._providers.save_credential(selected.id, request.apiKey)
        config = self.get_config()
        self._legacy_repository.save_projection(config)
        return config

    def clear_api_key(self) -> LLMConfig:
        profile = self._repository.get_routing_profile()
        self._providers.clear_credential(profile.default_target.configuration_id)
        config = self.get_config()
        self._legacy_repository.save_projection(config)
        return config

    async def test_connection(
        self,
        request: ConnectionTestRequest,
    ) -> ConnectionTestResult:
        if request.config is None and request.apiKey is None:
            profile = self._repository.get_routing_profile()
            result = await self._providers.test_connection(
                profile.default_target.configuration_id,
                ProviderConnectionTestRequest(),
            )
            return ConnectionTestResult(
                ok=result.test.status == "PASSED",
                message=result.test.message,
                provider=result.provider,
                model=result.model,
                latencyMs=result.test.latency_ms,
                error=result.error,
            )

        source = request.config
        if source is None:
            config = self.get_config()
        else:
            try:
                base_url = validate_provider_base_url(
                    source.baseUrl,
                    allow_private_network=False,
                    private_network_confirmed=False,
                )
            except ProviderUrlError as exc:
                error = make_llm_error(LLMErrorCode.NETWORK_UNAVAILABLE)
                return ConnectionTestResult(
                    ok=False,
                    message=str(exc),
                    provider=source.provider,
                    model=source.defaultModel,
                    error=error,
                )
            config = LLMConfig(
                provider=source.provider,
                baseUrl=base_url,
                defaultModel=source.defaultModel,
                customModels=source.customModels,
                thinkingMode=source.thinkingMode,
                reasoningEffort=source.reasoningEffort,
                timeoutSeconds=source.timeoutSeconds,
            )
        api_key = request.apiKey or (source.apiKey if source else None)
        if not api_key:
            current = self.get_config()
            if current.provider == config.provider and current.providerConfigurationId:
                api_key = self._credential(current.providerConfigurationId)
        if not api_key:
            error = make_llm_error(LLMErrorCode.CONFIG_MISSING)
            return ConnectionTestResult(
                ok=False,
                message=error.message,
                provider=config.provider,
                model=config.defaultModel,
                error=error,
            )
        return await self._provider.test_connection(config, api_key)

    def _credential(self, configuration_id: str) -> str | None:
        locator = self._repository.credential_locator(configuration_id)
        target = credential_service_for_configuration(configuration_id)
        value = self._credentials.get_password(target, settings.credential_account)
        if value:
            return value
        if locator.state == "FALLBACK" and locator.legacy_service:
            return self._credentials.get_password(
                locator.legacy_service,
                settings.credential_account,
            )
        return None


def _preset_id(provider: LLMProviderId) -> ProviderPresetId:
    return {
        LLMProviderId.DEEPSEEK: ProviderPresetId.DEEPSEEK,
        LLMProviderId.QWEN: ProviderPresetId.QWEN_OPENAI_COMPATIBLE,
        LLMProviderId.GLM: ProviderPresetId.GLM,
        LLMProviderId.KIMI: ProviderPresetId.KIMI,
        LLMProviderId.OPENAI_COMPATIBLE: ProviderPresetId.CUSTOM_OPENAI_COMPATIBLE,
    }[provider]


def _provider_label(provider: LLMProviderId) -> str:
    return {
        LLMProviderId.DEEPSEEK: "DeepSeek",
        LLMProviderId.QWEN: "千问（Qwen）",
        LLMProviderId.GLM: "智谱 GLM",
        LLMProviderId.KIMI: "Kimi",
        LLMProviderId.OPENAI_COMPATIBLE: "自定义 OpenAI-compatible",
    }[provider]
