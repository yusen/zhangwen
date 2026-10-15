"""Resolve and pin model-provider settings without exposing credentials."""

from __future__ import annotations

from pathlib import Path

from zhangwen.llm.contracts import LLMConfig
from zhangwen.llm.deepseek import DeepSeekProvider
from zhangwen.security.credentials import CredentialStore
from zhangwen.settings.models import ModelWorkload, RuntimeModelSelection
from zhangwen.settings.provider_repository import ProviderSettingsRepository
from zhangwen.settings.provider_service import ProviderSettingsService


def require_llm_config(
    *,
    data_dir: Path,
    credential_store: CredentialStore,
    credential_service: str,
    credential_account: str,
    workload: ModelWorkload | str = ModelWorkload.CREATION,
    owner_kind: str | None = None,
    owner_id: str | None = None,
    fallback: bool = False,
) -> tuple[LLMConfig, str]:
    """Resolve one immutable Provider/route revision and require its Key.

    ``credential_service`` and ``credential_account`` remain in the signature so
    legacy routers need no broad migration. The repository keeps a compatibility
    read pointer to the old target until a configuration-specific credential is
    saved or explicitly cleared.
    """

    _ = credential_service, credential_account
    selected_workload = (
        workload if isinstance(workload, ModelWorkload) else ModelWorkload(workload)
    )
    config, api_key, _selection = ProviderSettingsService(
        ProviderSettingsRepository(data_dir),
        credential_store,
        DeepSeekProvider(),
    ).resolve_runtime(
        selected_workload,
        fallback=fallback,
        owner_kind=owner_kind,
        owner_id=owner_id,
    )
    return config, api_key


def resolve_llm_runtime(
    *,
    data_dir: Path,
    credential_store: CredentialStore,
    workload: ModelWorkload | str,
    owner_kind: str | None = None,
    owner_id: str | None = None,
    fallback: bool = False,
) -> tuple[LLMConfig, str, RuntimeModelSelection]:
    """Developer/runtime entry point that also returns the immutable pin."""

    selected_workload = (
        workload if isinstance(workload, ModelWorkload) else ModelWorkload(workload)
    )
    return ProviderSettingsService(
        ProviderSettingsRepository(data_dir),
        credential_store,
        DeepSeekProvider(),
    ).resolve_runtime(
        selected_workload,
        fallback=fallback,
        owner_kind=owner_kind,
        owner_id=owner_id,
    )
