"""Application service for versioned model providers and secure credentials."""

from __future__ import annotations

import asyncio
import uuid

from zhangwen.config import settings
from zhangwen.llm.contracts import (
    ConnectionTestResult,
    LLMConfig,
    LLMErrorCode,
    ModelConfig,
)
from zhangwen.llm.errors import make_llm_error
from zhangwen.llm.gateway import LLMProvider
from zhangwen.security.credentials import (
    CredentialStore,
    credential_service_for_configuration,
)
from zhangwen.security.redaction import redact_text
from zhangwen.settings.models import (
    CreateProviderConfigurationRequest,
    ModelRoutingProfile,
    ModelWorkload,
    PrivacySettings,
    ProviderConfiguration,
    ProviderConnectionStatus,
    ProviderConnectionTestRequest,
    ProviderConnectionTestResult,
    ProviderCredentialSummary,
    ProviderModelsResponse,
    ProviderSettingsResponse,
    RuntimeModelSelection,
    SaveModelRoutingRequest,
    SavePrivacySettingsRequest,
    UpdateProviderConfigurationRequest,
)
from zhangwen.settings.provider_repository import (
    ProviderSettingsConflictError,
    ProviderSettingsRepository,
    provider_preset,
    provider_presets,
)
from zhangwen.settings.url_security import (
    AddressResolver,
    ProviderUrlError,
    validate_provider_base_url,
)


class ProviderSettingsService:
    def __init__(
        self,
        repository: ProviderSettingsRepository,
        credentials: CredentialStore,
        provider: LLMProvider,
        *,
        address_resolver: AddressResolver | None = None,
    ) -> None:
        self._repository = repository
        self._credentials = credentials
        self._provider = provider
        self._address_resolver = address_resolver

    def list_settings(self) -> ProviderSettingsResponse:
        return ProviderSettingsResponse(
            presets=provider_presets(),
            configurations=[
                self._with_credential(item)
                for item in self._repository.list_configurations()
            ],
        )

    def get_configuration(self, configuration_id: str) -> ProviderConfiguration:
        return self._with_credential(
            self._repository.get_configuration(configuration_id)
        )

    def create_configuration(
        self,
        request: CreateProviderConfigurationRequest,
    ) -> ProviderConfiguration:
        preset = provider_preset(request.preset_id)
        base_url = request.base_url or preset.default_base_url
        if not base_url:
            raise ProviderSettingsConflictError(
                "自定义模型服务需要填写 Base URL。"
            )
        default_model = request.default_model
        if default_model is None and preset.default_models:
            default_model = preset.default_models[0].id
        if default_model is None:
            raise ProviderSettingsConflictError(
                "自定义模型服务需要至少填写一个模型 ID。"
            )
        custom_models = list(request.custom_models)
        self._validate_custom_models(preset.provider, custom_models)
        canonical_url = validate_provider_base_url(
            base_url,
            allow_private_network=request.allow_private_network,
            private_network_confirmed=request.private_network_confirmed,
        )
        created = self._repository.create_configuration(
            preset_id=preset.id,
            name=request.name,
            provider=preset.provider,
            base_url=canonical_url,
            default_model=default_model,
            custom_models=custom_models,
            thinking_mode=request.thinking_mode,
            reasoning_effort=request.reasoning_effort,
            timeout_seconds=request.timeout_seconds,
            allow_private_network=request.allow_private_network,
        )
        return self._with_credential(created)

    def update_configuration(
        self,
        configuration_id: str,
        request: UpdateProviderConfigurationRequest,
    ) -> ProviderConfiguration:
        current = self._repository.get_configuration(configuration_id)
        self._validate_custom_models(current.provider, list(request.custom_models))
        canonical_url = validate_provider_base_url(
            request.base_url,
            allow_private_network=request.allow_private_network,
            private_network_confirmed=request.private_network_confirmed,
        )
        updated = self._repository.update_configuration(
            configuration_id,
            expected_revision=request.expected_revision,
            name=request.name,
            base_url=canonical_url,
            default_model=request.default_model,
            custom_models=list(request.custom_models),
            thinking_mode=request.thinking_mode,
            reasoning_effort=request.reasoning_effort,
            timeout_seconds=request.timeout_seconds,
            allow_private_network=request.allow_private_network,
            enabled=request.enabled,
        )
        return self._with_credential(updated)

    def delete_configuration(self, configuration_id: str) -> None:
        if self._credential(configuration_id) is not None:
            raise ProviderSettingsConflictError(
                "请先清除这个模型服务的凭据，再删除配置。"
            )
        self._repository.delete_configuration(configuration_id)

    def save_credential(
        self,
        configuration_id: str,
        api_key: str,
    ) -> ProviderConfiguration:
        self._repository.get_configuration(configuration_id)
        target = credential_service_for_configuration(configuration_id)
        previous = self._credentials.get_password(target, settings.credential_account)
        self._credentials.set_password(
            target,
            settings.credential_account,
            api_key.strip(),
        )
        try:
            self._repository.mark_credential_configured(configuration_id)
        except Exception:
            self._restore_credential(target, previous)
            raise
        return self.get_configuration(configuration_id)

    def clear_credential(self, configuration_id: str) -> ProviderConfiguration:
        self._repository.get_configuration(configuration_id)
        target = credential_service_for_configuration(configuration_id)
        previous = self._credentials.get_password(target, settings.credential_account)
        self._credentials.delete_password(target, settings.credential_account)
        try:
            self._repository.mark_credential_cleared(configuration_id)
        except Exception:
            self._restore_credential(target, previous)
            raise
        return self.get_configuration(configuration_id)

    def models(self, configuration_id: str) -> ProviderModelsResponse:
        configuration = self._repository.get_configuration(configuration_id)
        preset = provider_preset(configuration.preset_id)
        catalog = [*preset.default_models, *configuration.custom_models]
        unique: dict[str, ModelConfig] = {}
        for item in catalog:
            unique[str(item.id)] = item
        return ProviderModelsResponse(
            configurationId=configuration.id,
            revisionId=configuration.revision_id,
            models=list(unique.values()),
        )

    def get_routing_profile(self) -> ModelRoutingProfile:
        return self._repository.get_routing_profile()

    def save_routing_profile(
        self,
        request: SaveModelRoutingRequest,
    ) -> ModelRoutingProfile:
        return self._repository.save_routing_profile(request)

    def get_privacy_settings(self) -> PrivacySettings:
        return self._repository.get_privacy_settings()

    def save_privacy_settings(
        self,
        request: SavePrivacySettingsRequest,
    ) -> PrivacySettings:
        return self._repository.save_privacy_settings(request)

    def resolve_runtime(
        self,
        workload: ModelWorkload,
        *,
        fallback: bool = False,
        owner_kind: str | None = None,
        owner_id: str | None = None,
    ) -> tuple[LLMConfig, str, RuntimeModelSelection]:
        resolved = self._repository.resolve_runtime(
            workload,
            fallback=fallback,
            owner_kind=owner_kind,
            owner_id=owner_id,
        )
        secret = self._credential(resolved.selection.provider_configuration_id)
        if not secret:
            from zhangwen.llm.structured import StructuredLLMError

            raise StructuredLLMError(make_llm_error(LLMErrorCode.CONFIG_MISSING))
        config = resolved.config.model_copy(update={"keySaved": True})
        return config, secret, resolved.selection

    async def test_connection(
        self,
        configuration_id: str,
        request: ProviderConnectionTestRequest,
    ) -> ProviderConnectionTestResult:
        configuration = self._repository.get_configuration(configuration_id)
        test_id = request.test_id or f"provider_test_{uuid.uuid4().hex}"
        started = self._repository.start_connection_test(configuration_id, test_id)
        if started.status != ProviderConnectionStatus.RUNNING:
            return ProviderConnectionTestResult(
                test=started,
                provider=configuration.provider,
                model=configuration.default_model,
                error=(
                    None
                    if started.status == ProviderConnectionStatus.PASSED
                    else make_llm_error(LLMErrorCode.UNKNOWN)
                ),
            )
        secret = self._credential(configuration_id)
        if not secret:
            error = make_llm_error(LLMErrorCode.CONFIG_MISSING)
            summary = self._repository.finish_connection_test(
                test_id,
                status=ProviderConnectionStatus.FAILED,
                message=error.message,
                latency_ms=None,
                error_code=error.code.value,
            )
            return ProviderConnectionTestResult(
                test=summary,
                provider=configuration.provider,
                model=configuration.default_model,
                error=error,
            )

        try:
            safe_url = validate_provider_base_url(
                configuration.base_url,
                allow_private_network=configuration.allow_private_network,
                private_network_confirmed=configuration.allow_private_network,
                resolve_dns=True,
                resolver=self._address_resolver,
            )
            config = _llm_config(configuration, safe_url)
            timeout = min(
                request.timeout_seconds or configuration.timeout_seconds,
                configuration.timeout_seconds,
            )
            result = await asyncio.wait_for(
                self._provider.test_connection(config, secret),
                timeout=timeout,
            )
        except ProviderUrlError as exc:
            error_code = (
                LLMErrorCode.DNS_UNAVAILABLE
                if exc.code.startswith("DNS_")
                else LLMErrorCode.NETWORK_UNAVAILABLE
            )
            error = make_llm_error(error_code)
            result = ConnectionTestResult(
                ok=False,
                message=str(exc),
                provider=configuration.provider,
                model=configuration.default_model,
                error=error,
            )
            summary_code = exc.code
        except TimeoutError:
            error = make_llm_error(LLMErrorCode.TIMEOUT)
            result = ConnectionTestResult(
                ok=False,
                message=error.message,
                provider=configuration.provider,
                model=configuration.default_model,
                error=error,
            )
            summary_code = error.code.value
        except asyncio.CancelledError:
            error = make_llm_error(LLMErrorCode.CANCELED)
            summary = self._repository.finish_connection_test(
                test_id,
                status=ProviderConnectionStatus.CANCELED,
                message=error.message,
                latency_ms=None,
                error_code=error.code.value,
            )
            return ProviderConnectionTestResult(
                test=summary,
                provider=configuration.provider,
                model=configuration.default_model,
                error=error,
            )
        else:
            summary_code = result.error.code.value if result.error is not None else None

        summary = self._repository.finish_connection_test(
            test_id,
            status=(
                ProviderConnectionStatus.PASSED
                if result.ok
                else ProviderConnectionStatus.FAILED
            ),
            message=redact_text(result.message),
            latency_ms=result.latencyMs,
            error_code=summary_code,
        )
        return ProviderConnectionTestResult(
            test=summary,
            provider=result.provider,
            model=result.model,
            error=result.error,
        )

    def cancel_connection_test(self, test_id: str):
        return self._repository.cancel_connection_test(test_id)

    def _with_credential(
        self,
        configuration: ProviderConfiguration,
    ) -> ProviderConfiguration:
        secret = self._credential(configuration.id)
        return configuration.model_copy(
            update={
                "credential": ProviderCredentialSummary(
                    configured=secret is not None,
                    lastFour=secret[-4:] if secret else None,
                )
            }
        )

    def _credential(self, configuration_id: str) -> str | None:
        locator = self._repository.credential_locator(configuration_id)
        target = credential_service_for_configuration(configuration_id)
        configured = self._credentials.get_password(
            target,
            settings.credential_account,
        )
        if configured:
            return configured
        if locator.state == "FALLBACK" and locator.legacy_service:
            return self._credentials.get_password(
                locator.legacy_service,
                settings.credential_account,
            )
        return None

    def _restore_credential(self, target: str, previous: str | None) -> None:
        if previous is None:
            self._credentials.delete_password(target, settings.credential_account)
        else:
            self._credentials.set_password(
                target,
                settings.credential_account,
                previous,
            )

    @staticmethod
    def _validate_custom_models(provider, models: list[ModelConfig]) -> None:
        if any(not item.isCustom or item.provider != provider for item in models):
            raise ProviderSettingsConflictError(
                "自定义模型必须属于当前模型服务，并标记为自定义。"
            )


def _llm_config(configuration: ProviderConfiguration, base_url: str) -> LLMConfig:
    return LLMConfig(
        provider=configuration.provider,
        baseUrl=base_url,
        defaultModel=configuration.default_model,
        customModels=configuration.custom_models,
        thinkingMode=configuration.thinking_mode,
        reasoningEffort=configuration.reasoning_effort,
        timeoutSeconds=configuration.timeout_seconds,
        keySaved=True,
        providerConfigurationId=configuration.id,
        providerConfigurationRevisionId=configuration.revision_id,
    )
