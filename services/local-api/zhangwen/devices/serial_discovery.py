"""Serial port discovery for the device tab."""

from __future__ import annotations

import platform
from typing import Any

from zhangwen.devices.models import DevicePort, SerialPortStatus, SerialPortType


class SerialDiscoveryError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 500) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def list_serial_ports() -> list[DevicePort]:
    try:
        return _list_pyserial_ports()
    except ImportError:
        if platform.system() == "Windows":
            return _list_windows_registry_ports()
        return []
    except PermissionError as exc:
        raise SerialDiscoveryError(
            "SERIAL_PERMISSION_DENIED",
            "串口扫描权限不足，请检查系统权限后重试。",
            403,
        ) from exc
    except OSError as exc:
        raise SerialDiscoveryError(
            "SERIAL_SYSTEM_API_FAILED",
            f"系统串口 API 调用失败：{exc}",
            500,
        ) from exc
    except Exception as exc:
        raise SerialDiscoveryError(
            "SERIAL_SCAN_UNKNOWN",
            f"未知串口扫描错误：{exc}",
            500,
        ) from exc


def _list_pyserial_ports() -> list[DevicePort]:
    from serial.tools import list_ports

    ports = []
    for raw in list_ports.comports():
        port_name = str(getattr(raw, "device", "") or getattr(raw, "name", "") or "")
        if not port_name:
            continue
        description = _optional_str(getattr(raw, "description", None))
        manufacturer = _optional_str(getattr(raw, "manufacturer", None))
        product = _optional_str(getattr(raw, "product", None))
        vid = _optional_int(getattr(raw, "vid", None))
        pid = _optional_int(getattr(raw, "pid", None))
        serial_number = _optional_str(getattr(raw, "serial_number", None))
        likely_board = _infer_board(
            description=description,
            manufacturer=manufacturer,
            product=product,
            vid=vid,
            pid=pid,
        )
        ports.append(
            DevicePort(
                id=port_name,
                label=description or port_name,
                transport="usb-serial" if vid is not None or pid is not None else "system-serial",
                portName=port_name,
                portType=_infer_port_type(description, manufacturer, product, vid, pid),
                description=description,
                manufacturer=manufacturer,
                product=product,
                vid=vid,
                pid=pid,
                serialNumber=serial_number,
                likelyBoard=likely_board,
                chip=likely_board or "Unknown",
                status=SerialPortStatus.AVAILABLE,
                available=True,
            )
        )
    return sorted(ports, key=lambda port: port.portName)


def _list_windows_registry_ports() -> list[DevicePort]:
    try:
        import winreg
    except ImportError as exc:
        raise SerialDiscoveryError(
            "SERIAL_SERVICE_UNAVAILABLE",
            "当前运行环境不支持串口枚举服务。",
            503,
        ) from exc

    ports: list[DevicePort] = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DEVICEMAP\SERIALCOMM") as key:
            index = 0
            while True:
                try:
                    _name, value, _type = winreg.EnumValue(key, index)
                except OSError:
                    break
                port_name = str(value)
                ports.append(
                    DevicePort(
                        id=port_name,
                        label=port_name,
                        transport="system-serial",
                        portName=port_name,
                        portType=SerialPortType.UNKNOWN,
                        description=None,
                        manufacturer=None,
                        product=None,
                        vid=None,
                        pid=None,
                        serialNumber=None,
                        likelyBoard=None,
                        chip="Unknown",
                        status=SerialPortStatus.AVAILABLE,
                        available=True,
                    )
                )
                index += 1
    except PermissionError as exc:
        raise SerialDiscoveryError(
            "SERIAL_PERMISSION_DENIED",
            "串口扫描权限不足，请检查系统权限后重试。",
            403,
        ) from exc
    except OSError as exc:
        raise SerialDiscoveryError(
            "SERIAL_SYSTEM_API_FAILED",
            f"Windows 串口注册表读取失败：{exc}",
            500,
        ) from exc

    return sorted(ports, key=lambda port: port.portName)


def _infer_port_type(
    description: str | None,
    manufacturer: str | None,
    product: str | None,
    vid: int | None,
    pid: int | None,
) -> SerialPortType:
    text = " ".join(
        item.lower()
        for item in [description, manufacturer, product]
        if item
    )
    if "bluetooth" in text:
        return SerialPortType.BLUETOOTH
    if vid is not None or pid is not None or "usb" in text:
        return SerialPortType.USB
    if "pci" in text:
        return SerialPortType.PCI
    return SerialPortType.UNKNOWN


def _infer_board(
    *,
    description: str | None,
    manufacturer: str | None,
    product: str | None,
    vid: int | None,
    pid: int | None,
) -> str | None:
    text = " ".join(
        item.lower()
        for item in [description, manufacturer, product]
        if item
    )
    if vid == 0x303A or "espressif" in text or "esp32" in text:
        return "ESP32"
    if "ch340" in text or vid == 0x1A86:
        return "CH340 USB Serial"
    if "cp210" in text or vid == 0x10C4:
        return "CP210x USB Serial"
    if "ftdi" in text or vid == 0x0403:
        return "FTDI USB Serial"
    if "arduino" in text:
        return "Arduino"
    return None


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
