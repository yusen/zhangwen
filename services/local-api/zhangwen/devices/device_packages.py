"""Versioned device-package declarations shared by Creator and device services.

This catalog is intentionally data-only.  HTTP routes project these declarations
instead of inventing board capabilities, while the existing device operation
service remains the sole executor for every declared deployment channel.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Mapping

from zhangwen.device_lab.boards import BOARDS
from zhangwen.device_lab.models import SupportedDeviceBoardId
from zhangwen.devices.models import DeviceDeploymentChannel


@dataclass(frozen=True)
class DeploymentChannelDeclaration:
    id: DeviceDeploymentChannel
    runtime: Literal["MICROPYTHON", "ESP_CLAW_LUA"]
    connection_contract: Literal[
        "MICROPYTHON_IDENTITY_V1",
        "ESP_CLAW_STATUS_MCP_V1",
    ]
    requires_pairing: bool
    requires_file_readback: bool = True
    interactive_console: bool = False


@dataclass(frozen=True)
class DevicePackageDeclaration:
    id: SupportedDeviceBoardId
    version: str
    display_name: str
    board_profile_id: SupportedDeviceBoardId
    capabilities: tuple[str, ...]
    deployment_channels: tuple[DeploymentChannelDeclaration, ...]
    simulation_modes: tuple[str, ...]
    source: str


_USB_SERIAL = DeploymentChannelDeclaration(
    id=DeviceDeploymentChannel.USB_SERIAL,
    runtime="MICROPYTHON",
    connection_contract="MICROPYTHON_IDENTITY_V1",
    requires_pairing=False,
    interactive_console=True,
)
_ESP_CLAW = DeploymentChannelDeclaration(
    id=DeviceDeploymentChannel.ESP_CLAW,
    runtime="ESP_CLAW_LUA",
    connection_contract="ESP_CLAW_STATUS_MCP_V1",
    requires_pairing=True,
)


def _proxy_package(board_id: SupportedDeviceBoardId) -> DevicePackageDeclaration:
    board = BOARDS[board_id]
    return DevicePackageDeclaration(
        id=board_id,
        version="proxy-v1",
        display_name=board.displayName,
        board_profile_id=board_id,
        capabilities=("code", "simulation", "parameters", "telemetry"),
        # Both are peer code-deployment choices. Their distinct runtime and
        # connection contracts are declared here, not inferred in Creator.
        deployment_channels=(_USB_SERIAL, _ESP_CLAW),
        simulation_modes=("FUNCTIONAL_MODEL", "QEMU_ESP32S3"),
        source="bundled-proxy",
    )


DEVICE_PACKAGE_REGISTRY: Mapping[
    SupportedDeviceBoardId,
    DevicePackageDeclaration,
] = MappingProxyType(
    {
        board_id: _proxy_package(board_id)
        for board_id in BOARDS
    }
)


def list_device_packages() -> tuple[DevicePackageDeclaration, ...]:
    """Return a stable catalog ordered by package id."""

    return tuple(
        DEVICE_PACKAGE_REGISTRY[board_id]
        for board_id in sorted(DEVICE_PACKAGE_REGISTRY, key=lambda item: item.value)
    )
