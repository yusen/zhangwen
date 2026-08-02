"""LLM settings routes."""

from fastapi import APIRouter, HTTPException, Request

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
from zhangwen.settings.repository import LLMSettingsRepository
from zhangwen.settings.service import LLMSettingsService
from zhangwen.host import has_desktop_host_access, is_web_host, require_desktop_host


def create_settings_service() -> LLMSettingsService:
    return LLMSettingsService(
        repository=LLMSettingsRepository(settings.data_dir),
        credentials=BackendCredentialStore(),
        provider=create_provider(),
    )


router = APIRouter(prefix="/api", tags=["settings"])


@router.get("/settings/llm", response_model=LLMConfigResponse)
async def get_llm_settings() -> LLMConfigResponse:
    return LLMConfigResponse(config=create_settings_service().get_config())


@router.put("/settings/llm", response_model=LLMConfigResponse)
async def save_llm_settings(
    request: SaveLLMConfigRequest,
    http_request: Request,
) -> LLMConfigResponse:
    _reject_web_secret(http_request, request.apiKey)
    return LLMConfigResponse(config=create_settings_service().save_config(request))


@router.delete("/settings/llm/api-key", response_model=LLMConfigResponse)
async def clear_llm_api_key(request: Request) -> LLMConfigResponse:
    _require_secret_access(request)
    return LLMConfigResponse(config=create_settings_service().clear_api_key())


@router.post("/settings/llm/test", response_model=ConnectionTestResult)
async def test_llm_connection(
    request: ConnectionTestRequest,
    http_request: Request,
) -> ConnectionTestResult:
    _reject_web_secret(
        http_request,
        request.apiKey or (request.config.apiKey if request.config else None),
    )
    return await create_settings_service().test_connection(request)


@router.get("/llm/models", response_model=ModelsResponse)
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
