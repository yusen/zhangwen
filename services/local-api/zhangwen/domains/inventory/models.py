"""Strict boundary models for the unified M6 device platform."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from zhangwen.devices.models import DeviceDeploymentChannel
from zhangwen.domains.orchestration.models import ExecutionRevisionSet


class InventoryModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )


class InventoryItemStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    IN_USE = "IN_USE"
    NEEDS_ATTENTION = "NEEDS_ATTENTION"
    RETIRED = "RETIRED"


class DeviceTechnicalFactClass(StrEnum):
    BOARD = "BOARD"
    COMPONENT = "COMPONENT"


class DeviceIdentityStatus(StrEnum):
    NOT_CONNECTED = "NOT_CONNECTED"
    MATCHED = "MATCHED"
    NEEDS_ATTENTION = "NEEDS_ATTENTION"


class DeviceRecoveryStatus(StrEnum):
    READY = "READY"
    RECOVERY_AVAILABLE = "RECOVERY_AVAILABLE"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


class DeviceTechnicalFact(InventoryModel):
    device_package_id: str = Field(alias="devicePackageId")
    device_package_revision_id: str = Field(alias="devicePackageRevisionId")
    display_name: str = Field(alias="displayName")
    device_class: DeviceTechnicalFactClass = Field(alias="deviceClass")
    capabilities: list[str]
    deployment_channels: list[DeviceDeploymentChannel] = Field(
        alias="deploymentChannels"
    )
    runtime: str | None
    verification_status: str = Field(alias="verificationStatus")
    natural_summary: str = Field(alias="naturalSummary")
    image_url: str | None = Field(default=None, alias="imageUrl")


class InventoryItem(InventoryModel):
    id: str
    device_package_id: str = Field(alias="devicePackageId")
    display_name: str = Field(alias="displayName")
    quantity: int = Field(ge=0)
    status: InventoryItemStatus
    price: float = Field(ge=0)
    location: str
    notes: str
    last_connection_status: str | None = Field(alias="lastConnectionStatus")
    last_connected_at: str | None = Field(alias="lastConnectedAt")
    revision: int = Field(ge=1)
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class WorkDeviceBinding(InventoryModel):
    id: str
    work_id: str = Field(alias="workId")
    inventory_item_id: str | None = Field(alias="inventoryItemId")
    device_package_id: str = Field(alias="devicePackageId")
    device_package_revision_id: str = Field(alias="devicePackageRevisionId")
    identity_status: DeviceIdentityStatus = Field(alias="identityStatus")
    deployment_channel: DeviceDeploymentChannel | None = Field(
        alias="deploymentChannel"
    )
    runtime_package_revision_id: str | None = Field(
        alias="runtimePackageRevisionId"
    )
    code_variant_id: str | None = Field(alias="codeVariantId")
    io_config: dict[str, str | int | float | bool] = Field(alias="ioConfig")
    recovery_status: DeviceRecoveryStatus = Field(alias="recoveryStatus")
    natural_status: str = Field(alias="naturalStatus")
    revision: int = Field(ge=1)
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class InventoryOverviewResponse(InventoryModel):
    items: list[InventoryItem]
    device_facts: list[DeviceTechnicalFact] = Field(alias="deviceFacts")


class InventoryItemResponse(InventoryModel):
    item: InventoryItem


class CreateInventoryItemRequest(InventoryModel):
    device_package_id: str = Field(alias="devicePackageId", min_length=1, max_length=200)
    display_name: str | None = Field(default=None, alias="displayName", max_length=100)
    quantity: int = Field(default=1, ge=0, le=999)
    price: float = Field(default=0, ge=0, le=10_000_000)
    location: str = Field(default="", max_length=200)
    notes: str = Field(default="", max_length=2_000)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=8, max_length=128)


class UpdateInventoryItemRequest(InventoryModel):
    expected_revision: int = Field(alias="expectedRevision", ge=1)
    display_name: str | None = Field(default=None, alias="displayName", max_length=100)
    quantity: int | None = Field(default=None, ge=0, le=999)
    status: InventoryItemStatus | None = None
    price: float | None = Field(default=None, ge=0, le=10_000_000)
    location: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2_000)


class WorkDeviceListResponse(InventoryModel):
    bindings: list[WorkDeviceBinding]
    device_facts: list[DeviceTechnicalFact] = Field(alias="deviceFacts")


class WorkDeviceBindingResponse(InventoryModel):
    binding: WorkDeviceBinding


class CreateWorkDeviceBindingRequest(InventoryModel):
    inventory_item_id: str | None = Field(
        default=None, alias="inventoryItemId", max_length=200
    )
    device_package_id: str | None = Field(
        default=None, alias="devicePackageId", max_length=200
    )
    deployment_channel: DeviceDeploymentChannel | None = Field(
        default=None, alias="deploymentChannel"
    )
    idempotency_key: str = Field(alias="idempotencyKey", min_length=8, max_length=128)

    @model_validator(mode="after")
    def exactly_one_device_source(self) -> "CreateWorkDeviceBindingRequest":
        if (self.inventory_item_id is None) == (self.device_package_id is None):
            raise ValueError("inventoryItemId 与 devicePackageId 必须且只能提供一个。")
        return self


class UpdateWorkDeviceBindingRequest(InventoryModel):
    expected_revision: int = Field(alias="expectedRevision", ge=1)
    device_package_revision_id: str | None = Field(
        default=None, alias="devicePackageRevisionId", max_length=200
    )
    deployment_channel: DeviceDeploymentChannel | None = Field(
        default=None, alias="deploymentChannel"
    )
    runtime_package_revision_id: str | None = Field(
        default=None, alias="runtimePackageRevisionId", max_length=200
    )
    code_variant_id: str | None = Field(default=None, alias="codeVariantId", max_length=200)
    io_config: dict[str, str | int | float | bool] | None = Field(
        default=None, alias="ioConfig"
    )


class DeviceOperationRevisionPin(InventoryModel):
    device_binding_id: str = Field(alias="deviceBindingId")
    execution_revision_set: ExecutionRevisionSet = Field(alias="executionRevisionSet")


class DevicePlatformError(RuntimeError):
    code = "DEVICE_PLATFORM_ERROR"


class DevicePlatformNotFoundError(DevicePlatformError):
    code = "DEVICE_PLATFORM_NOT_FOUND"


class DevicePlatformConflictError(DevicePlatformError):
    code = "DEVICE_PLATFORM_CONFLICT"


class DevicePlatformValidationError(DevicePlatformError):
    code = "DEVICE_PLATFORM_INVALID"
