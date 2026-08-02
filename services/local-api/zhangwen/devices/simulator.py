"""Mock-only device discovery for ZW-012 automated workflows."""

from __future__ import annotations

from zhangwen.devices.models import DevicePort

MOCK_DEVICE_PORT_ID = "mock_port_esp32_s3"


def list_mock_ports() -> list[DevicePort]:
    return [
        DevicePort(
            id=MOCK_DEVICE_PORT_ID,
            label="Mock ESP32-S3 USB Serial",
            transport="mock-usb-serial",
            portName=MOCK_DEVICE_PORT_ID,
            portType="usb",
            chip="ESP32-S3",
            serialNumber=None,
            likelyBoard="ESP32-S3",
            status="available",
            available=True,
        )
    ]


def get_mock_port(port_id: str) -> DevicePort:
    for port in list_mock_ports():
        if port.id == port_id:
            return port
    raise ValueError("未找到可用的 Mock 设备端口。")
