"""Versioned model-provider settings and legacy compatibility routes."""

import asyncio
import uuid

from fastapi import APIRouter, HTTPException, Request, Response, status

from zhangwen.config import settings
from zhangwen.llm.contracts import (
    ConnectionTestRequest,
    ConnectionTestResult,
    LLMConfigResponse,
    ModelsResponse,
    SaveLLMConfigRequest,
    SUPPORTED_MODELS,
)
from zhangwen.llm.development_fake import create_provider
from zhangwen.security.credentials import BackendCredentialStore
from zhangwen.security.credentials import CredentialStoreError
from zhangwen.settings.models import (
    CreateProviderConfigurationRequest,
    ModelRoutingResponse,
    PrivacySettingsResponse,
    ProviderConfigurationResponse,
    ProviderConnectionTestRequest,
    ProviderConnectionTestResult,
    ProviderModelsResponse,
    ProviderSettingsResponse,
    SaveModelRoutingRequest,
    SavePrivacySettingsRequest,
    SaveProviderCredentialRequest,
    UpdateProviderConfigurationRequest,
)
from zhangwen.settings.provider_repository import (
    ProviderSettingsError,
    ProviderSettingsRepository,
)
from zhangwen.settings.provider_service import ProviderSettingsService
from zhangwen.settings.repository import LLMSettingsRepository
from zhangwen.settings.service import LLMSettingsService
from zhangwen.settings.url_security import ProviderUrlError
from zhangwen.host import has_desktop_host_access, is_web_host, require_desktop_host


def create_settings_service() -> LLMSettingsService:
    return LLMSettingsService(
        repository=LLMSettingsRepository(settings.data_dir),
        credentials=BackendCredentialStore(),
        provider=create_provider(),
    )


def create_provider_settings_service() -> ProviderSettingsService:
    return ProviderSettingsService(
        repository=ProviderSettingsRepository(settings.data_dir),
        credentials=BackendCredentialStore(),
        provider=create_provider(),
    )


router = APIRouter(prefix="/api", tags=["settings"])
retired_router = APIRouter(
    prefix="/api",
    tags=["retired-single-provider-settings"],
    include_in_schema=False,
)
_connection_test_tasks: dict[str, asyncio.Task[ProviderConnectionTestResult]] = {}


@router.get(
    "/settings/model-providers",
    response_model=ProviderSettingsResponse,
)
async def list_model_providers() -> ProviderSettingsResponse:
    return _provider_call(lambda service: service.list_settings())


@router.post(
    "/settings/model-providers",
    response_model=ProviderConfigurationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_model_provider(
    payload: CreateProviderConfigurationRequest,
) -> ProviderConfigurationResponse:
    configuration = _provider_call(
        lambda service: service.create_configuration(payload)
    )
    return ProviderConfigurationResponse(configuration=configuration)


@router.put(
    "/settings/model-providers/{configuration_id}",
    response_model=ProviderConfigurationResponse,
)
async def update_model_provider(
    configuration_id: str,
    payload: UpdateProviderConfigurationRequest,
) -> ProviderConfigurationResponse:
    configuration = _provider_call(
        lambda service: service.update_configuration(configuration_id, payload)
    )
    return ProviderConfigurationResponse(configuration=configuration)


@router.delete(
    "/settings/model-providers/{configuration_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_model_provider(configuration_id: str) -> Response:
    _provider_call(lambda service: service.delete_configuration(configuration_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/settings/model-providers/{configuration_id}/credential",
    response_model=ProviderConfigurationResponse,
)
async def save_model_provider_credential(
    configuration_id: str,
    payload: SaveProviderCredentialRequest,
    request: Request,
) -> ProviderConfigurationResponse:
    _require_secret_access(request)
    configuration = _provider_call(
        lambda service: service.save_credential(
            configuration_id,
            payload.api_key,
        )
    )
    return ProviderConfigurationResponse(configuration=configuration)


@router.delete(
    "/settings/model-providers/{configuration_id}/credential",
    response_model=ProviderConfigurationResponse,
)
async def clear_model_provider_credential(
    configuration_id: str,
    request: Request,
) -> ProviderConfigurationResponse:
    _require_secret_access(request)
    configuration = _provider_call(
        lambda service: service.clear_credential(configuration_id)
    )
    return ProviderConfigurationResponse(configuration=configuration)


@router.post(
    "/settings/model-providers/{configuration_id}/test",
    response_model=ProviderConnectionTestResult,
)
async def test_model_provider_connection(
    configuration_id: str,
    payload: ProviderConnectionTestRequest,
    request: Request,
) -> ProviderConnectionTestResult:
    _require_secret_access(request)
    test_id = payload.test_id or f"provider_test_{uuid.uuid4().hex}"
    if test_id in _connection_test_tasks:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "PROVIDER_TEST_ALREADY_RUNNING",
                "message": "这个连接测试正在运行。",
                "retryable": False,
            },
        )
    service = create_provider_settings_service()
    task = asyncio.create_task(
        service.test_connection(
            configuration_id,
            payload.model_copy(update={"test_id": test_id}),
        )
    )
    _connection_test_tasks[test_id] = task
    try:
        return await task
    except (ProviderSettingsError, ProviderUrlError, CredentialStoreError) as exc:
        raise _provider_error(exc) from exc
    finally:
        _connection_test_tasks.pop(test_id, None)


@router.delete(
    "/settings/model-providers/{configuration_id}/tests/{test_id}",
    response_model=ProviderConnectionTestResult,
)
async def cancel_model_provider_connection_test(
    configuration_id: str,
    test_id: str,
    request: Request,
) -> ProviderConnectionTestResult:
    _require_secret_access(request)
    task = _connection_test_tasks.get(test_id)
    if task is not None:
        task.cancel()
        try:
            return await task
        finally:
            _connection_test_tasks.pop(test_id, None)
    service = create_provider_settings_service()
    try:
        configuration = service.get_configuration(configuration_id)
        summary = service.cancel_connection_test(test_id)
        from zhangwen.llm.contracts import LLMErrorCode
        from zhangwen.llm.errors import make_llm_error

        return ProviderConnectionTestResult(
            test=summary,
            provider=configuration.provider,
            model=configuration.default_model,
            error=make_llm_error(LLMErrorCode.CANCELED),
        )
    except (ProviderSettingsError, ProviderUrlError, CredentialStoreError) as exc:
        raise _provider_error(exc) from exc


@router.get(
    "/settings/model-providers/{configuration_id}/models",
    response_model=ProviderModelsResponse,
)
async def list_model_provider_models(
    configuration_id: str,
) -> ProviderModelsResponse:
    return _provider_call(lambda service: service.models(configuration_id))


@router.get("/settings/model-routing", response_model=ModelRoutingResponse)
async def get_model_routing() -> ModelRoutingResponse:
    return ModelRoutingResponse(
        profile=_provider_call(lambda service: service.get_routing_profile())
    )


@router.put("/settings/model-routing", response_model=ModelRoutingResponse)
async def save_model_routing(
    payload: SaveModelRoutingRequest,
) -> ModelRoutingResponse:
    return ModelRoutingResponse(
        profile=_provider_call(
            lambda service: service.save_routing_profile(payload)
        )
    )


@router.get("/settings/privacy", response_model=PrivacySettingsResponse)
async def get_privacy_settings() -> PrivacySettingsResponse:
    return PrivacySettingsResponse(
        settings=_provider_call(lambda service: service.get_privacy_settings())
    )


@router.put("/settings/privacy", response_model=PrivacySettingsResponse)
async def save_privacy_settings(
    payload: SavePrivacySettingsRequest,
) -> PrivacySettingsResponse:
    return PrivacySettingsResponse(
        settings=_provider_call(
            lambda service: service.save_privacy_settings(payload)
        )
    )


@retired_router.get("/settings/llm", response_model=LLMConfigResponse)
async def get_llm_settings() -> LLMConfigResponse:
    return LLMConfigResponse(config=create_settings_service().get_config())


@retired_router.put("/settings/llm", response_model=LLMConfigResponse)
async def save_llm_settings(
    request: SaveLLMConfigRequest,
    http_request: Request,
) -> LLMConfigResponse:
    _reject_web_secret(http_request, request.apiKey)
    return LLMConfigResponse(config=create_settings_service().save_config(request))


@retired_router.delete("/settings/llm/api-key", response_model=LLMConfigResponse)
async def clear_llm_api_key(request: Request) -> LLMConfigResponse:
    _require_secret_access(request)
    return LLMConfigResponse(config=create_settings_service().clear_api_key())


@retired_router.post("/settings/llm/test", response_model=ConnectionTestResult)
async def test_llm_connection(
    request: ConnectionTestRequest,
    http_request: Request,
) -> ConnectionTestResult:
    _reject_web_secret(
        http_request,
        request.apiKey or (request.config.apiKey if request.config else None),
    )
    return await create_settings_service().test_connection(request)


@retired_router.get("/llm/models", response_model=ModelsResponse)
async def list_llm_models() -> ModelsResponse:
    custom_models = create_settings_service().get_config().customModels
    return ModelsResponse(models=[*SUPPORTED_MODELS, *custom_models])


def _reject_web_secret(request: Request, api_key: str | None) -> None:
    if api_key:
        _require_secret_access(request)


def _require_secret_access(request: Request) -> None:
    if has_desktop_host_access(request):
        return
    if request.headers.get("x-zhangwen-host", "").lower() == "tauri":
        require_desktop_host(request, "provider_credentials")
        return
    if is_web_host(request):
        raise _web_secret_error()
    require_desktop_host(request, "provider_credentials")


def _web_secret_error() -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "code": "WEB_PROVIDER_KEY_BLOCKED",
            "message": "浏览器不能提交或修改 Provider Key，请在本地后端配置。",
            "retryable": False,
        },
    )


def _provider_call(operation):
    try:
        return operation(create_provider_settings_service())
    except (ProviderSettingsError, ProviderUrlError, CredentialStoreError) as exc:
        raise _provider_error(exc) from exc


def _provider_error(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=getattr(exc, "status_code", 422),
        detail={
            "code": getattr(exc, "code", "PROVIDER_SETTINGS_ERROR"),
            "message": str(exc),
            "retryable": getattr(exc, "retryable", False),
        },
    )
