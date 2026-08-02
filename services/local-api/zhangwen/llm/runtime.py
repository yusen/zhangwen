"""Shared loading of non-sensitive model settings and secure API credentials."""

from __future__ import annotations

from pathlib import Path

from zhangwen.llm.contracts import LLMConfig, LLMErrorCode
from zhangwen.llm.errors import make_llm_error
from zhangwen.llm.structured import StructuredLLMError
from zhangwen.security.credentials import CredentialStore
from zhangwen.security.credentials import credential_service_for_provider
from zhangwen.settings.repository import LLMSettingsRepository


def require_llm_config(
    *,
    data_dir: Path,
    credential_store: CredentialStore,
    credential_service: str,
    credential_account: str,
) -> tuple[LLMConfig, str]:
    """Load settings and require a Key without exposing the secret."""

    try:
        config = LLMSettingsRepository(data_dir).load(
            key_saved=False,
            masked_api_key=None,
        )
        service = credential_service_for_provider(config.provider.value)
        if config.provider.value == "deepseek":
            service = credential_service
        api_key = credential_store.get_password(service, credential_account)
        if not api_key:
            raise StructuredLLMError(
                make_llm_error(LLMErrorCode.CONFIG_MISSING)
            )
        config = config.model_copy(update={"keySaved": True})
    except StructuredLLMError:
        raise
    except Exception as exc:
        raise StructuredLLMError(
            make_llm_error(LLMErrorCode.UNKNOWN)
        ) from exc
    return config, api_key
