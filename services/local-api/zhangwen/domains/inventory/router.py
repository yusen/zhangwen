"""Local-only API for technical device facts, inventory, and work bindings."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from zhangwen.config import settings
from zhangwen.domains.inventory.models import (
    CreateInventoryItemRequest,
    CreateWorkDeviceBindingRequest,
    DevicePlatformConflictError,
    DevicePlatformError,
    DevicePlatformNotFoundError,
    DevicePlatformValidationError,
    InventoryItemResponse,
    InventoryOverviewResponse,
    UpdateInventoryItemRequest,
    UpdateWorkDeviceBindingRequest,
    WorkDeviceBindingResponse,
    WorkDeviceListResponse,
)
from zhangwen.domains.inventory.service import DevicePlatformService
from zhangwen.projects.errors import ProjectError


router = APIRouter(prefix="/api", tags=["device-platform"])


@router.get("/inventory", response_model=InventoryOverviewResponse)
def inventory_overview() -> InventoryOverviewResponse:
    try:
        return _service().overview()
    except DevicePlatformError as exc:
        raise _http_error(exc) from exc


@router.post("/inventory", response_model=InventoryItemResponse, status_code=201)
def create_inventory_item(
    request: CreateInventoryItemRequest,
) -> InventoryItemResponse:
    try:
        return InventoryItemResponse(item=_service().create_inventory_item(request))
    except DevicePlatformError as exc:
        raise _http_error(exc) from exc


@router.put("/inventory/{item_id}", response_model=InventoryItemResponse)
def update_inventory_item(
    item_id: str,
    request: UpdateInventoryItemRequest,
) -> InventoryItemResponse:
    try:
        return InventoryItemResponse(
            item=_service().update_inventory_item(item_id, request)
        )
    except DevicePlatformError as exc:
        raise _http_error(exc) from exc


@router.get("/works/{work_id}/devices", response_model=WorkDeviceListResponse)
def list_work_devices(work_id: str) -> WorkDeviceListResponse:
    try:
        return _service().list_work_devices(work_id)
    except ProjectError as exc:
        raise HTTPException(status_code=404, detail="作品不存在。") from exc
    except DevicePlatformError as exc:
        raise _http_error(exc) from exc


@router.post(
    "/works/{work_id}/devices/bindings",
    response_model=WorkDeviceBindingResponse,
    status_code=201,
)
def create_work_device_binding(
    work_id: str,
    request: CreateWorkDeviceBindingRequest,
) -> WorkDeviceBindingResponse:
    try:
        return WorkDeviceBindingResponse(
            binding=_service().create_work_binding(work_id, request)
        )
    except ProjectError as exc:
        raise HTTPException(status_code=404, detail="作品不存在。") from exc
    except DevicePlatformError as exc:
        raise _http_error(exc) from exc


@router.put(
    "/works/{work_id}/devices/bindings/{binding_id}",
    response_model=WorkDeviceBindingResponse,
)
def update_work_device_binding(
    work_id: str,
    binding_id: str,
    request: UpdateWorkDeviceBindingRequest,
) -> WorkDeviceBindingResponse:
    try:
        return WorkDeviceBindingResponse(
            binding=_service().update_work_binding(work_id, binding_id, request)
        )
    except ProjectError as exc:
        raise HTTPException(status_code=404, detail="作品不存在。") from exc
    except DevicePlatformError as exc:
        raise _http_error(exc) from exc


def _service() -> DevicePlatformService:
    return DevicePlatformService(settings.data_dir)


def _http_error(exc: DevicePlatformError) -> HTTPException:
    status = 422
    if isinstance(exc, DevicePlatformNotFoundError):
        status = 404
    elif isinstance(exc, DevicePlatformConflictError):
        status = 409
    elif isinstance(exc, DevicePlatformValidationError):
        status = 422
    return HTTPException(
        status_code=status,
        detail={"code": exc.code, "message": str(exc), "retryable": status == 409},
    )
