"""Application service for the unified device package and inventory platform."""

from __future__ import annotations

from pathlib import Path

from zhangwen.devices.models import DeviceDeploymentChannel
from zhangwen.domains.inventory.models import (
    CreateInventoryItemRequest,
    CreateWorkDeviceBindingRequest,
    DeviceOperationRevisionPin,
    InventoryItem,
    InventoryOverviewResponse,
    UpdateInventoryItemRequest,
    UpdateWorkDeviceBindingRequest,
    WorkDeviceBinding,
    WorkDeviceListResponse,
)
from zhangwen.domains.inventory.repository import DevicePlatformRepository
from zhangwen.projects.repository import ProjectRepository


class DevicePlatformService:
    def __init__(self, data_dir: Path) -> None:
        self._projects = ProjectRepository(data_dir)
        self._repository = DevicePlatformRepository(data_dir)

    def overview(self) -> InventoryOverviewResponse:
        return InventoryOverviewResponse(
            items=self._repository.list_inventory(),
            deviceFacts=self._repository.list_device_facts(),
        )

    def create_inventory_item(
        self,
        request: CreateInventoryItemRequest,
    ) -> InventoryItem:
        return self._repository.create_inventory_item(
            device_package_id=request.device_package_id,
            display_name=request.display_name,
            quantity=request.quantity,
            price=request.price,
            location=request.location,
            notes=request.notes,
            idempotency_key=request.idempotency_key,
        )

    def update_inventory_item(
        self,
        item_id: str,
        request: UpdateInventoryItemRequest,
    ) -> InventoryItem:
        changes = {
            field: getattr(request, field)
            for field in request.model_fields_set
            if field != "expected_revision" and getattr(request, field) is not None
        }
        return self._repository.update_inventory_item(
            item_id,
            expected_revision=request.expected_revision,
            changes=changes,
        )

    def list_work_devices(self, work_id: str) -> WorkDeviceListResponse:
        self._assert_work(work_id)
        return WorkDeviceListResponse(
            bindings=self._repository.list_work_bindings(work_id),
            deviceFacts=self._repository.list_device_facts(),
        )

    def create_work_binding(
        self,
        work_id: str,
        request: CreateWorkDeviceBindingRequest,
    ) -> WorkDeviceBinding:
        self._assert_work(work_id)
        return self._repository.create_work_binding(
            work_id=work_id,
            inventory_item_id=request.inventory_item_id,
            device_package_id=request.device_package_id,
            deployment_channel=request.deployment_channel,
            idempotency_key=request.idempotency_key,
        )

    def update_work_binding(
        self,
        work_id: str,
        binding_id: str,
        request: UpdateWorkDeviceBindingRequest,
    ) -> WorkDeviceBinding:
        self._assert_work(work_id)
        changes = {
            field: getattr(request, field)
            for field in request.model_fields_set
            if field != "expected_revision"
        }
        return self._repository.update_work_binding(
            work_id,
            binding_id,
            expected_revision=request.expected_revision,
            changes=changes,
        )

    def resolve_operation_pin(
        self,
        *,
        work_id: str,
        session_id: str,
        channel: DeviceDeploymentChannel,
    ) -> DeviceOperationRevisionPin:
        self._assert_work(work_id)
        return self._repository.resolve_operation_pin(
            work_id=work_id,
            session_id=session_id,
            channel=channel,
        )

    def _assert_work(self, work_id: str) -> None:
        self._projects.get_workspace(work_id)
