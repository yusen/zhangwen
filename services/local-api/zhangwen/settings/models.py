"""Strict contracts for the versioned model-provider settings platform."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from zhangwen.llm.contracts import (
    LLMError,
    LLMModelSelection,
    LLMProviderId,
    ModelConfig,
    ThinkingMode,
    model_belongs_to_provider,
)


class ProviderSettingsModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ProviderPresetId(StrEnum):
    DEEPSEEK = "deepseek"
    QWEN_OPENAI_COMPATIBLE = "qwen-openai-compatible"
    GLM = "glm"
    KIMI = "kimi"
    CUSTOM_OPENAI_COMPATIBLE = "custom-openai-compatible"


class ProviderConnectionStatus(StrEnum):
    NOT_TESTED = "NOT_TESTED"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


class ModelWorkload(StrEnum):
    CREATION = "CREATION"
    ENGINEERING = "ENGINEERING"
    VISION = "VISION"
    LONG_DOCUMENT = "LONG_DOCUMENT"


class CloudContextScope(StrEnum):
    MINIMUM_NEEDED = "MINIMUM_NEEDED"
    CURRENT_WORK = "CURRENT_WORK"
    EXPLICIT_ONLY = "EXPLICIT_ONLY"


class ProviderPreset(ProviderSettingsModel):
    id: ProviderPresetId
    display_name: str = Field(alias="displayName", min_length=1, max_length=80)
    provider: LLMProviderId
    catalog_revision: int = Field(alias="catalogRevision", ge=1)
    default_base_url: str | None = Field(alias="defaultBaseUrl")
    default_models: list[ModelConfig] = Field(alias="defaultModels")
    custom_base_url: bool = Field(alias="customBaseUrl")


class ProviderCredentialSummary(ProviderSettingsModel):
    configured: bool
    last_four: str | None = Field(alias="lastFour", min_length=4, max_length=4)


class ProviderConnectionTestSummary(ProviderSettingsModel):
    id: str
    status: ProviderConnectionStatus
    tested_revision_id: str = Field(alias="testedRevisionId")
    tested_at: str | None = Field(alias="testedAt")
    latency_ms: int | None = Field(alias="latencyMs", ge=0)
    message: str = Field(max_length=500)
    error_code: str | None = Field(alias="errorCode", max_length=80)


class ProviderConfiguration(ProviderSettingsModel):
    id: str
    revision_id: str = Field(alias="revisionId")
    revision: int = Field(ge=1)
    preset_id: ProviderPresetId = Field(alias="presetId")
    name: str = Field(min_length=1, max_length=80)
    provider: LLMProviderId
    base_url: str = Field(alias="baseUrl", min_length=1, max_length=2048)
    default_model: LLMModelSelection = Field(alias="defaultModel")
    custom_models: list[ModelConfig] = Field(
        default_factory=list,
        alias="customModels",
        max_length=32,
    )
    thinking_mode: ThinkingMode = Field(alias="thinkingMode")
    reasoning_effort: Literal["high", "max"] | None = Field(
        alias="reasoningEffort"
    )
    timeout_seconds: int = Field(alias="timeoutSeconds", ge=5, le=300)
    allow_private_network: bool = Field(alias="allowPrivateNetwork")
    enabled: bool
    credential: ProviderCredentialSummary
    connection_test: ProviderConnectionTestSummary | None = Field(
        alias="connectionTest"
    )
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class CreateProviderConfigurationRequest(ProviderSettingsModel):
    preset_id: ProviderPresetId = Field(alias="presetId")
    name: str = Field(min_length=1, max_length=80)
    base_url: str | None = Field(default=None, alias="baseUrl", max_length=2048)
    default_model: LLMModelSelection | None = Field(default=None, alias="defaultModel")
    custom_models: list[ModelConfig] = Field(
        default_factory=list,
        alias="customModels",
        max_length=32,
    )
    thinking_mode: ThinkingMode = Field(default=ThinkingMode.AUTO, alias="thinkingMode")
    reasoning_effort: Literal["high", "max"] | None = Field(
        default=None,
        alias="reasoningEffort",
    )
    timeout_seconds: int = Field(default=60, alias="timeoutSeconds", ge=5, le=300)
    allow_private_network: bool = Field(default=False, alias="allowPrivateNetwork")
    private_network_confirmed: bool = Field(
        default=False,
        alias="privateNetworkConfirmed",
    )


class UpdateProviderConfigurationRequest(ProviderSettingsModel):
    expected_revision: int = Field(alias="expectedRevision", ge=1)
    name: str = Field(min_length=1, max_length=80)
    base_url: str = Field(alias="baseUrl", min_length=1, max_length=2048)
    default_model: LLMModelSelection = Field(alias="defaultModel")
    custom_models: list[ModelConfig] = Field(
        default_factory=list,
        alias="customModels",
        max_length=32,
    )
    thinking_mode: ThinkingMode = Field(alias="thinkingMode")
    reasoning_effort: Literal["high", "max"] | None = Field(alias="reasoningEffort")
    timeout_seconds: int = Field(alias="timeoutSeconds", ge=5, le=300)
    allow_private_network: bool = Field(alias="allowPrivateNetwork")
    private_network_confirmed: bool = Field(
        default=False,
        alias="privateNetworkConfirmed",
    )
    enabled: bool = True


class SaveProviderCredentialRequest(ProviderSettingsModel):
    api_key: str = Field(alias="apiKey", min_length=1, max_length=4096)


class ProviderConfigurationResponse(ProviderSettingsModel):
    configuration: ProviderConfiguration


class ProviderSettingsResponse(ProviderSettingsModel):
    presets: list[ProviderPreset]
    configurations: list[ProviderConfiguration]


class ProviderConnectionTestRequest(ProviderSettingsModel):
    test_id: str | None = Field(
        default=None,
        alias="testId",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,159}$",
    )
    timeout_seconds: int | None = Field(
        default=None,
        alias="timeoutSeconds",
        ge=5,
        le=300,
    )


class ProviderConnectionTestResult(ProviderSettingsModel):
    test: ProviderConnectionTestSummary
    provider: LLMProviderId
    model: LLMModelSelection
    error: LLMError | None = None


class ProviderModelsResponse(ProviderSettingsModel):
    configuration_id: str = Field(alias="configurationId")
    revision_id: str = Field(alias="revisionId")
    models: list[ModelConfig]


class ModelRoutingTarget(ProviderSettingsModel):
    configuration_id: str = Field(alias="configurationId")
    model: LLMModelSelection


class ModelRoutingProfile(ProviderSettingsModel):
    id: str
    revision_id: str = Field(alias="revisionId")
    revision: int = Field(ge=1)
    default_target: ModelRoutingTarget = Field(alias="defaultTarget")
    fallback_target: ModelRoutingTarget | None = Field(alias="fallbackTarget")
    workload_routes: dict[ModelWorkload, ModelRoutingTarget] = Field(
        default_factory=dict,
        alias="workloadRoutes",
    )
    updated_at: str = Field(alias="updatedAt")


class SaveModelRoutingRequest(ProviderSettingsModel):
    expected_revision: int = Field(alias="expectedRevision", ge=1)
    default_target: ModelRoutingTarget = Field(alias="defaultTarget")
    fallback_target: ModelRoutingTarget | None = Field(alias="fallbackTarget")
    workload_routes: dict[ModelWorkload, ModelRoutingTarget] = Field(
        default_factory=dict,
        alias="workloadRoutes",
    )


class ModelRoutingResponse(ProviderSettingsModel):
    profile: ModelRoutingProfile


class PrivacySettings(ProviderSettingsModel):
    id: str
    revision_id: str = Field(alias="revisionId")
    revision: int = Field(ge=1)
    context_scope: CloudContextScope = Field(alias="contextScope")
    cloud_trace_enabled: bool = Field(alias="cloudTraceEnabled")
    allow_automatic_fallback: bool = Field(alias="allowAutomaticFallback")
    updated_at: str = Field(alias="updatedAt")


class SavePrivacySettingsRequest(ProviderSettingsModel):
    expected_revision: int = Field(alias="expectedRevision", ge=1)
    context_scope: CloudContextScope = Field(alias="contextScope")
    cloud_trace_enabled: bool = Field(alias="cloudTraceEnabled")
    allow_automatic_fallback: bool = Field(alias="allowAutomaticFallback")


class PrivacySettingsResponse(ProviderSettingsModel):
    settings: PrivacySettings


class RuntimeModelSelection(ProviderSettingsModel):
    provider_configuration_id: str = Field(alias="providerConfigurationId")
    provider_configuration_revision_id: str = Field(
        alias="providerConfigurationRevisionId"
    )
    routing_profile_revision_id: str = Field(alias="routingProfileRevisionId")
    provider: LLMProviderId
    model: LLMModelSelection
    workload: ModelWorkload
    fallback: bool = False


def validate_configuration_model(
    *,
    provider: LLMProviderId,
    default_model: str,
    custom_models: list[ModelConfig],
) -> None:
    if not model_belongs_to_provider(default_model, provider, custom_models):
        raise ValueError("defaultModel does not belong to provider configuration")

    if provider == LLMProviderId.OPENAI_COMPATIBLE:
        matching = [item for item in custom_models if str(item.id) == str(default_model)]
        if not matching:
            raise ValueError("custom OpenAI-compatible configurations require a custom model")


def validate_routing_targets_are_distinct(profile: SaveModelRoutingRequest) -> None:
    fallback = profile.fallback_target
    if fallback is None:
        return
    if (
        fallback.configuration_id == profile.default_target.configuration_id
        and str(fallback.model) == str(profile.default_target.model)
    ):
        raise ValueError("fallbackTarget must differ from defaultTarget")
