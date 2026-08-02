"""Provider-neutral LLM settings service."""

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
    credential_service_for_provider,
)
from zhangwen.security.redaction import mask_api_key
from zhangwen.settings.repository import LLMSettingsRepository


class LLMSettingsService:
    def __init__(
        self,
        repository: LLMSettingsRepository,
        credentials: CredentialStore,
        provider: LLMProvider,
    ) -> None:
        self._repository = repository
        self._credentials = credentials
        self._provider = provider

    def get_config(self) -> LLMConfig:
        persisted = self._repository.load(
            key_saved=False,
            masked_api_key=None,
        )
        api_key = self._get_api_key(persisted.provider)
        return self._repository.load(
            key_saved=api_key is not None,
            masked_api_key=mask_api_key(api_key),
        )

    def save_config(self, request: SaveLLMConfigRequest) -> LLMConfig:
        service = self._credential_service(request.provider)
        if request.apiKey:
            self._credentials.set_password(
                service,
                settings.credential_account,
                request.apiKey,
            )

        api_key = self._credentials.get_password(
            service,
            settings.credential_account,
        )
        return self._repository.save(
            request,
            key_saved=api_key is not None,
            masked_api_key=mask_api_key(api_key),
        )

    def clear_api_key(self) -> LLMConfig:
        persisted = self._repository.load(
            key_saved=False,
            masked_api_key=None,
        )
        self._credentials.delete_password(
            self._credential_service(persisted.provider),
            settings.credential_account,
        )
        return self._repository.load(key_saved=False, masked_api_key=None)

    async def test_connection(
        self,
        request: ConnectionTestRequest,
    ) -> ConnectionTestResult:
        config = self.get_config()
        api_key = request.apiKey
        if request.config:
            config = LLMConfig(
                provider=request.config.provider,
                baseUrl=request.config.baseUrl.rstrip("/"),
                defaultModel=request.config.defaultModel,
                customModels=request.config.customModels,
                thinkingMode=request.config.thinkingMode,
                reasoningEffort=request.config.reasoningEffort,
                timeoutSeconds=request.config.timeoutSeconds,
            )
            api_key = api_key or request.config.apiKey

        api_key = api_key or self._get_api_key(config.provider)
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

    def _get_api_key(self, provider: LLMProviderId) -> str | None:
        return self._credentials.get_password(
            self._credential_service(provider),
            settings.credential_account,
        )

    @staticmethod
    def _credential_service(provider: LLMProviderId) -> str:
        if provider == LLMProviderId.DEEPSEEK:
            return settings.credential_service
        return credential_service_for_provider(provider.value)
