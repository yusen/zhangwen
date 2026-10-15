"""Deterministic ESP32-S3/C3 API subset and first-party component bus.

This module contains no FastAPI or project persistence imports so the isolated worker can
load it under Python isolated mode. It is a behavioral reference, not a MicroPython core.
"""

from __future__ import annotations

import io
import random as _random
from types import ModuleType
from typing import Any, Callable


class SimulationRuntimeFault(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class UnsupportedSimulationFeature(SimulationRuntimeFault):
    def __init__(self, feature: str) -> None:
        super().__init__(
            "UNSUPPORTED_SIMULATION_FEATURE",
            f"当前 ZW-MPY-SIM 子集不支持 {feature}。",
        )


class ResourceLimitExceeded(SimulationRuntimeFault):
    pass


class RuntimeEventCollector:
    def __init__(self, *, max_events: int, max_output_bytes: int) -> None:
        self.max_events = max_events
        self.max_output_bytes = max_output_bytes
        self.events: list[dict[str, Any]] = []
        self.serial_chunks: list[str] = []
        self.output_bytes = 0
        self.clock: VirtualClock | None = None

    def emit(self, kind: str, source: str, **payload: Any) -> None:
        if len(self.events) >= self.max_events:
            raise ResourceLimitExceeded(
                "SIMULATION_EVENT_LIMIT_EXCEEDED",
                "仿真事件数量超过当前运行上限。",
            )
        self.events.append(
            {
                "sequence": len(self.events) + 1,
                "virtualTimeUs": self.clock.now_us if self.clock is not None else 0,
                "kind": kind,
                "source": source,
                "payload": payload,
            }
        )

    def serial_write(self, *values: Any, sep: str = " ", end: str = "\n") -> None:
        text = sep.join(str(item) for item in values) + end
        size = len(text.encode("utf-8"))
        if self.output_bytes + size > self.max_output_bytes:
            raise ResourceLimitExceeded(
                "SIMULATION_OUTPUT_LIMIT_EXCEEDED",
                "仿真串口输出超过当前运行上限。",
            )
        self.serial_chunks.append(text)
        self.output_bytes += size
        self.emit("SERIAL_WRITE", "console", text=text)

    @property
    def serial_output(self) -> str:
        return "".join(self.serial_chunks)


class VirtualClock:
    def __init__(
        self,
        collector: RuntimeEventCollector,
        *,
        max_virtual_time_us: int,
    ) -> None:
        self.collector = collector
        self.max_virtual_time_us = max_virtual_time_us
        self.now_us = 0
        self._timers: list[Timer] = []
        self._scheduled_actions: list[tuple[int, str, Callable[[], None]]] = []
        collector.clock = self

    def register(self, timer: Timer) -> None:
        if timer not in self._timers:
            self._timers.append(timer)

    def schedule_action(
        self, at_us: int, action_id: str, callback: Callable[[], None]
    ) -> None:
        self._scheduled_actions.append((at_us, action_id, callback))
        self._scheduled_actions.sort(key=lambda item: (item[0], item[1]))

    def advance(self, delta_us: int) -> None:
        if delta_us < 0:
            raise SimulationRuntimeFault(
                "SIMULATION_INVALID_TIME",
                "虚拟时间不能倒退。",
            )
        target = self.now_us + delta_us
        if target > self.max_virtual_time_us:
            raise ResourceLimitExceeded(
                "SIMULATION_VIRTUAL_TIME_LIMIT_EXCEEDED",
                "虚拟时间超过当前运行上限。",
            )
        while True:
            due = [
                timer
                for timer in self._timers
                if timer._active and timer._due_us is not None and timer._due_us <= target
            ]
            due_action = next(
                (item for item in self._scheduled_actions if item[0] <= target),
                None,
            )
            next_timer = (
                min(due, key=lambda item: (item._due_us or 0, item.id))
                if due
                else None
            )
            if due_action is None and next_timer is None:
                break
            if due_action is not None and (
                next_timer is None
                or due_action[0] <= int(next_timer._due_us or 0)
            ):
                self._scheduled_actions.remove(due_action)
                self.now_us = due_action[0]
                due_action[2]()
                continue
            assert next_timer is not None and next_timer._due_us is not None
            self.now_us = next_timer._due_us
            next_timer._fire()
        self.now_us = target
        self.collector.emit(
            "VIRTUAL_TIME_ADVANCED",
            "clock",
            deltaUs=delta_us,
            nowUs=self.now_us,
        )


class ComponentBus:
    def __init__(
        self,
        *,
        board_profile: dict[str, Any],
        component_profiles: list[dict[str, Any]],
        circuit: dict[str, Any],
        seed: int,
        uart_inputs: dict[str, str],
        scenario_actions: list[dict[str, Any]],
        max_events: int,
        max_output_bytes: int,
        max_virtual_time_us: int,
    ) -> None:
        self.collector = RuntimeEventCollector(
            max_events=max_events,
            max_output_bytes=max_output_bytes,
        )
        self.clock = VirtualClock(
            self.collector,
            max_virtual_time_us=max_virtual_time_us,
        )
        self.random = _random.Random(seed)
        self.board_profile = board_profile
        self.board_revision_id = str(board_profile["revisionId"])
        self.chip_family = str(board_profile["chipFamily"])
        self.pins = {
            str(item["id"]): item for item in board_profile.get("pins", [])
        }
        profiles = {
            str(item["revisionId"]): item for item in component_profiles
        }
        self.parts: dict[str, dict[str, Any]] = {}
        for item in circuit.get("parts", []):
            revision_id = str(item["componentPackageRevisionId"])
            profile = profiles.get(revision_id)
            if profile is None:
                raise SimulationRuntimeFault(
                    "SIM_COMPONENT_UNKNOWN",
                    f"运行时不认识组件包 {revision_id}。",
                )
            properties = dict(profile.get("defaultProperties", {}))
            properties.update(dict(item.get("properties", {})))
            self.parts[str(item["id"])] = {
                "id": str(item["id"]),
                "revisionId": revision_id,
                "slug": str(profile["slug"]),
                "protocol": str(profile["protocol"]),
                "properties": properties,
            }
        self.connections_by_board: dict[str, list[tuple[str, str]]] = {}
        self.board_by_part_pin: dict[tuple[str, str], str] = {}
        board_id = str(circuit["boardInstance"]["id"])
        for net in circuit.get("nets", []):
            endpoints = list(net.get("endpoints", []))
            board_pins = [
                str(endpoint["pinId"])
                for endpoint in endpoints
                if str(endpoint["instanceId"]) == board_id
            ]
            part_endpoints = [
                (str(endpoint["instanceId"]), str(endpoint["pinId"]))
                for endpoint in endpoints
                if str(endpoint["instanceId"]) != board_id
            ]
            for board_pin in board_pins:
                for part_endpoint in part_endpoints:
                    self.connections_by_board.setdefault(board_pin, []).append(
                        part_endpoint
                    )
                    self.board_by_part_pin[part_endpoint] = board_pin
        self.pin_values: dict[str, int] = {}
        self.uart_inputs = {
            str(key): value.encode("utf-8") for key, value in uart_inputs.items()
        }
        self._last_dht: dict[str, tuple[float, float]] = {}
        self._disconnected_parts: set[str] = set()
        for action in scenario_actions:
            action_id = str(action.get("id", ""))
            at_ms = int(action.get("atMs", 0))
            self.clock.schedule_action(
                at_ms * 1000,
                action_id,
                lambda item=dict(action): self._apply_scenario_action(item),
            )
        if any(int(item.get("atMs", 0)) == 0 for item in scenario_actions):
            self.clock.advance(0)

    def _apply_scenario_action(self, action: dict[str, Any]) -> None:
        target = str(action.get("target", ""))
        value = action.get("value")
        if target.startswith("component:"):
            reference = target.removeprefix("component:")
            part_id, separator, property_name = reference.rpartition(".")
            part = self.parts.get(part_id)
            if not separator or part is None or property_name not in part["properties"]:
                raise SimulationRuntimeFault(
                    "SIMULATION_ACTION_TARGET_INVALID",
                    f"场景输入目标 {target} 不存在。",
                )
            part["properties"][property_name] = value
        elif target.startswith("pin:"):
            pin_id = self.normalize_pin(target.removeprefix("pin:"))
            self.require_capability(pin_id, "DIGITAL_IN")
            self.pin_values[pin_id] = 1 if bool(value) else 0
        elif target.startswith("uart:"):
            uart_id = target.removeprefix("uart:")
            self.uart_inputs[uart_id] = self.uart_inputs.get(uart_id, b"") + str(
                value
            ).encode("utf-8")
        elif target.startswith("fault:"):
            reference = target.removeprefix("fault:")
            part_id, separator, fault_name = reference.rpartition(".")
            if (
                not separator
                or fault_name != "disconnected"
                or part_id not in self.parts
            ):
                raise SimulationRuntimeFault(
                    "SIMULATION_ACTION_TARGET_INVALID",
                    f"场景故障目标 {target} 不受支持。",
                )
            if bool(value):
                self._disconnected_parts.add(part_id)
            else:
                self._disconnected_parts.discard(part_id)
        else:
            raise SimulationRuntimeFault(
                "SIMULATION_ACTION_TARGET_INVALID",
                f"场景输入目标 {target} 不受支持。",
            )
        self.collector.emit(
            "SCENARIO_INPUT",
            target,
            actionId=str(action.get("id", "")),
            value=value,
        )

    def normalize_pin(self, value: Any) -> str:
        if isinstance(value, Pin):
            return value.id
        if isinstance(value, int):
            pin_id = f"GPIO{value}"
        else:
            raw = str(value)
            pin_id = f"GPIO{raw}" if raw.isdigit() else raw.upper()
        if pin_id not in self.pins:
            raise SimulationRuntimeFault(
                "SIM_PIN_UNAVAILABLE",
                f"{self.chip_family} 参考板没有引脚 {pin_id}。",
            )
        return pin_id

    def require_capability(self, pin_id: str, capability: str) -> None:
        pin = self.pins[pin_id]
        if capability not in pin.get("capabilities", []):
            raise SimulationRuntimeFault(
                "SIM_PIN_CAPABILITY_UNAVAILABLE",
                f"{pin_id} 不具备 {capability} 能力。",
            )
        if bool(pin.get("reserved")) and capability in {"DIGITAL_OUT", "PWM"}:
            raise SimulationRuntimeFault(
                "SIM_PIN_RESERVED",
                f"{pin_id} 在当前 {self.chip_family} profile 中被保留。",
            )

    def connected(self, pin_id: str, slug: str | None = None) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for part_id, _part_pin in self.connections_by_board.get(pin_id, []):
            if part_id in self._disconnected_parts:
                continue
            part = self.parts.get(part_id)
            if part is not None and (slug is None or part["slug"] == slug):
                result.append(part)
        return result

    def pin_read(self, pin_id: str, pull: int | None) -> int:
        for part in self.connected(pin_id, "button"):
            pressed = bool(part["properties"].get("pressed", False))
            value = 0 if pressed else 1
            self.collector.emit(
                "BUTTON_STATE",
                part["id"],
                pressed=pressed,
                value=value,
            )
            return value
        if pin_id in self.pin_values:
            return self.pin_values[pin_id]
        if pull == Pin.PULL_UP:
            return 1
        return 0

    def pin_write(self, pin_id: str, value: int) -> None:
        normalized = 1 if value else 0
        self.pin_values[pin_id] = normalized
        self.collector.emit("PIN_WRITE", pin_id, value=normalized)
        for part in self.connected(pin_id):
            if part["slug"] == "led":
                self.collector.emit(
                    "LED_STATE",
                    part["id"],
                    on=bool(normalized),
                    brightness=1.0 if normalized else 0.0,
                    color=str(part["properties"].get("color", "red")),
                )

    def adc_read_u16(self, pin_id: str) -> int:
        self.require_capability(pin_id, "ADC")
        value = 0.0
        parts = self.connected(pin_id, "potentiometer")
        if parts:
            value = float(parts[0]["properties"].get("value", 0.5))
        value = min(1.0, max(0.0, value))
        sample = round(value * 65535)
        self.collector.emit("ADC_READ", pin_id, value=sample, normalized=value)
        return sample

    def pwm_write(self, pin_id: str, *, frequency: int, duty_u16: int) -> None:
        self.require_capability(pin_id, "PWM")
        duty = min(65535, max(0, int(duty_u16)))
        self.collector.emit(
            "PWM_WRITE",
            pin_id,
            frequency=frequency,
            dutyU16=duty,
        )
        for part in self.connected(pin_id):
            if part["slug"] == "buzzer":
                self.collector.emit(
                    "BUZZER_STATE",
                    part["id"],
                    active=duty > 0,
                    frequency=frequency,
                    dutyU16=duty,
                )
            elif part["slug"] == "servo":
                period_us = 1_000_000 / max(1, frequency)
                pulse_us = period_us * duty / 65535
                angle = min(180.0, max(0.0, (pulse_us - 500) * 180 / 2000))
                self.collector.emit(
                    "SERVO_STATE",
                    part["id"],
                    angle=round(angle, 3),
                    frequency=frequency,
                    dutyU16=duty,
                )
            elif part["slug"] == "led":
                self.collector.emit(
                    "LED_STATE",
                    part["id"],
                    on=duty > 0,
                    brightness=round(duty / 65535, 6),
                    color=str(part["properties"].get("color", "red")),
                )

    def i2c_devices(self, sda: str, scl: str) -> list[tuple[int, dict[str, Any]]]:
        self.require_capability(sda, "I2C_SDA")
        self.require_capability(scl, "I2C_SCL")
        result: list[tuple[int, dict[str, Any]]] = []
        for part in self.parts.values():
            if part["protocol"] != "I2C":
                continue
            if (
                self.board_by_part_pin.get((part["id"], "SDA")) == sda
                and self.board_by_part_pin.get((part["id"], "SCL")) == scl
            ):
                raw = part["properties"].get("i2cAddress", "0x3c")
                address = int(str(raw), 0) if isinstance(raw, str) else int(raw)
                result.append((address, part))
        return sorted(result, key=lambda item: item[0])

    def dht_measure(self, pin_id: str) -> tuple[float, float, str]:
        parts = self.connected(pin_id, "dht22")
        if not parts:
            raise SimulationRuntimeFault(
                "SIM_COMPONENT_NOT_CONNECTED",
                f"{pin_id} 没有连接 DHT22 数据引脚。",
            )
        part = parts[0]
        temperature = float(part["properties"].get("temperature", 24.0))
        humidity = float(part["properties"].get("humidity", 45.0))
        temperature = round(temperature + self.random.uniform(-0.05, 0.05), 2)
        humidity = round(humidity + self.random.uniform(-0.05, 0.05), 2)
        self._last_dht[part["id"]] = (temperature, humidity)
        self.collector.emit(
            "DHT22_READ",
            part["id"],
            temperature=temperature,
            humidity=humidity,
        )
        return temperature, humidity, str(part["id"])

    def component_for_pin(self, pin_id: str, slug: str) -> dict[str, Any]:
        parts = self.connected(pin_id, slug)
        if not parts:
            raise SimulationRuntimeFault(
                "SIM_COMPONENT_NOT_CONNECTED",
                f"{pin_id} 没有连接 {slug} 组件。",
            )
        return parts[0]


class Pin:
    IN = 0
    OUT = 1
    OPEN_DRAIN = 2
    PULL_UP = 3
    PULL_DOWN = 4

    def __init__(
        self,
        bus: ComponentBus,
        pin_id: Any,
        mode: int | None = None,
        pull: int | None = None,
        *,
        value: int | None = None,
        **kwargs: Any,
    ) -> None:
        if kwargs:
            raise UnsupportedSimulationFeature(f"machine.Pin 参数 {next(iter(kwargs))}")
        self.bus = bus
        self.id = bus.normalize_pin(pin_id)
        self.mode = mode
        self.pull = pull
        self.init(mode=mode, pull=pull, value=value)

    def init(
        self,
        mode: int | None = None,
        pull: int | None = None,
        *,
        value: int | None = None,
        **kwargs: Any,
    ) -> None:
        if kwargs:
            raise UnsupportedSimulationFeature(f"machine.Pin.init 参数 {next(iter(kwargs))}")
        if mode is not None:
            if mode in {self.OUT, self.OPEN_DRAIN}:
                self.bus.require_capability(self.id, "DIGITAL_OUT")
            elif mode == self.IN:
                self.bus.require_capability(self.id, "DIGITAL_IN")
            else:
                raise UnsupportedSimulationFeature(f"machine.Pin mode={mode}")
            self.mode = mode
        if pull is not None:
            if pull not in {self.PULL_UP, self.PULL_DOWN}:
                raise UnsupportedSimulationFeature(f"machine.Pin pull={pull}")
            self.pull = pull
        if value is not None:
            self.value(value)

    def value(self, value: int | None = None) -> int:
        if value is None:
            result = self.bus.pin_read(self.id, self.pull)
            self.bus.collector.emit("PIN_READ", self.id, value=result)
            return result
        if self.mode not in {self.OUT, self.OPEN_DRAIN}:
            self.bus.require_capability(self.id, "DIGITAL_OUT")
        self.bus.pin_write(self.id, value)
        return 1 if value else 0

    __call__ = value

    def on(self) -> None:
        self.value(1)

    def off(self) -> None:
        self.value(0)

    def toggle(self) -> None:
        self.value(0 if self.bus.pin_values.get(self.id, 0) else 1)

    def irq(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs
        raise UnsupportedSimulationFeature("machine.Pin.irq")


class ADC:
    def __init__(self, bus: ComponentBus, pin: Pin | int | str, **kwargs: Any) -> None:
        if kwargs:
            raise UnsupportedSimulationFeature(f"machine.ADC 参数 {next(iter(kwargs))}")
        self.bus = bus
        self.pin_id = bus.normalize_pin(pin)
        bus.require_capability(self.pin_id, "ADC")

    def read_u16(self) -> int:
        return self.bus.adc_read_u16(self.pin_id)

    def read(self) -> int:
        return round(self.read_u16() * 4095 / 65535)

    def read_uv(self) -> int:
        return round(self.read_u16() * 3_300_000 / 65535)

    def atten(self, *args: Any) -> None:
        del args
        raise UnsupportedSimulationFeature("machine.ADC.atten")

    def width(self, *args: Any) -> None:
        del args
        raise UnsupportedSimulationFeature("machine.ADC.width")


class PWM:
    def __init__(
        self,
        bus: ComponentBus,
        pin: Pin | int | str,
        *,
        freq: int = 5000,
        duty_u16: int = 0,
        duty: int | None = None,
        duty_ns: int | None = None,
    ) -> None:
        self.bus = bus
        self.pin_id = bus.normalize_pin(pin)
        bus.require_capability(self.pin_id, "PWM")
        self._frequency = int(freq)
        self._duty_u16 = 0
        if duty is not None:
            duty_u16 = round(min(1023, max(0, duty)) * 65535 / 1023)
        elif duty_ns is not None:
            period_ns = 1_000_000_000 / max(1, self._frequency)
            duty_u16 = round(min(1.0, max(0.0, duty_ns / period_ns)) * 65535)
        self.duty_u16(duty_u16)

    def freq(self, value: int | None = None) -> int:
        if value is not None:
            if value <= 0 or value > 1_000_000:
                raise SimulationRuntimeFault(
                    "SIM_PWM_FREQUENCY_INVALID",
                    "PWM 频率必须在 1 到 1000000 Hz 之间。",
                )
            self._frequency = int(value)
            self.bus.pwm_write(
                self.pin_id,
                frequency=self._frequency,
                duty_u16=self._duty_u16,
            )
        return self._frequency

    def duty_u16(self, value: int | None = None) -> int:
        if value is not None:
            self._duty_u16 = min(65535, max(0, int(value)))
            self.bus.pwm_write(
                self.pin_id,
                frequency=self._frequency,
                duty_u16=self._duty_u16,
            )
        return self._duty_u16

    def duty(self, value: int | None = None) -> int:
        if value is not None:
            self.duty_u16(round(min(1023, max(0, value)) * 65535 / 1023))
        return round(self._duty_u16 * 1023 / 65535)

    def duty_ns(self, value: int | None = None) -> int:
        period_ns = 1_000_000_000 / max(1, self._frequency)
        if value is not None:
            self.duty_u16(round(min(1.0, max(0.0, value / period_ns)) * 65535))
        return round(period_ns * self._duty_u16 / 65535)

    def deinit(self) -> None:
        self._duty_u16 = 0
        self.bus.pwm_write(self.pin_id, frequency=self._frequency, duty_u16=0)


class I2C:
    def __init__(
        self,
        bus: ComponentBus,
        bus_id: int = -1,
        *,
        scl: Pin | int | str,
        sda: Pin | int | str,
        freq: int = 400_000,
        **kwargs: Any,
    ) -> None:
        if kwargs:
            raise UnsupportedSimulationFeature(f"machine.I2C 参数 {next(iter(kwargs))}")
        self.bus = bus
        self.id = int(bus_id)
        self.scl = bus.normalize_pin(scl)
        self.sda = bus.normalize_pin(sda)
        self.freq = int(freq)
        bus.require_capability(self.scl, "I2C_SCL")
        bus.require_capability(self.sda, "I2C_SDA")

    def scan(self) -> list[int]:
        addresses = [address for address, _ in self.bus.i2c_devices(self.sda, self.scl)]
        self.bus.collector.emit(
            "I2C_SCAN",
            f"i2c:{self.id}",
            addresses=addresses,
            sda=self.sda,
            scl=self.scl,
        )
        return addresses

    def _device(self, address: int) -> dict[str, Any]:
        return next(
            (
                part
                for candidate, part in self.bus.i2c_devices(self.sda, self.scl)
                if candidate == address
            ),
            None,
        ) or self._raise_no_device(address)

    @staticmethod
    def _raise_no_device(address: int) -> Any:
        raise SimulationRuntimeFault(
            "SIM_I2C_DEVICE_NOT_FOUND",
            f"I²C 地址 0x{address:02x} 没有已连接组件。",
        )

    def writeto(self, address: int, data: bytes | bytearray, stop: bool = True) -> int:
        part = self._device(address)
        payload = bytes(data)
        self.bus.collector.emit(
            "I2C_WRITE",
            part["id"],
            address=address,
            bytes=list(payload),
            stop=bool(stop),
        )
        return len(payload)

    def readfrom(self, address: int, count: int, stop: bool = True) -> bytes:
        part = self._device(address)
        result = bytes(max(0, int(count)))
        self.bus.collector.emit(
            "I2C_READ",
            part["id"],
            address=address,
            count=len(result),
            stop=bool(stop),
        )
        return result

    def writeto_mem(
        self,
        address: int,
        memory_address: int,
        data: bytes | bytearray,
        *,
        addrsize: int = 8,
    ) -> None:
        self.writeto(address, bytes([memory_address & 0xFF]) + bytes(data))
        if addrsize not in {8, 16}:
            raise UnsupportedSimulationFeature(f"machine.I2C addrsize={addrsize}")

    def readfrom_mem(
        self,
        address: int,
        memory_address: int,
        count: int,
        *,
        addrsize: int = 8,
    ) -> bytes:
        del memory_address
        if addrsize not in {8, 16}:
            raise UnsupportedSimulationFeature(f"machine.I2C addrsize={addrsize}")
        return self.readfrom(address, count)


class SoftI2C(I2C):
    def __init__(self, bus: ComponentBus, **kwargs: Any) -> None:
        super().__init__(bus, -1, **kwargs)


class UART:
    def __init__(
        self,
        bus: ComponentBus,
        uart_id: int,
        baudrate: int = 115200,
        *,
        tx: Pin | int | str | None = None,
        rx: Pin | int | str | None = None,
        **kwargs: Any,
    ) -> None:
        self.bus = bus
        self.id = int(uart_id)
        self._buffer = bytearray(bus.uart_inputs.get(str(self.id), b""))
        self.active = True
        self.init(baudrate=baudrate, tx=tx, rx=rx, **kwargs)

    def init(
        self,
        baudrate: int = 115200,
        *,
        tx: Pin | int | str | None = None,
        rx: Pin | int | str | None = None,
        bits: int = 8,
        parity: int | None = None,
        stop: int = 1,
        **kwargs: Any,
    ) -> None:
        if kwargs:
            raise UnsupportedSimulationFeature(f"machine.UART 参数 {next(iter(kwargs))}")
        if bits != 8 or parity not in {None, 0, 1} or stop not in {1, 2}:
            raise UnsupportedSimulationFeature("machine.UART framing")
        self.baudrate = int(baudrate)
        tx_pin = self.bus.normalize_pin(tx) if tx is not None else self._default_pin("UART_TX")
        rx_pin = self.bus.normalize_pin(rx) if rx is not None else self._default_pin("UART_RX")
        self.bus.require_capability(tx_pin, "UART_TX")
        self.bus.require_capability(rx_pin, "UART_RX")
        self.tx = tx_pin
        self.rx = rx_pin
        self.active = True

    def _default_pin(self, capability: str) -> str:
        result = next(
            (
                pin_id
                for pin_id, pin in self.bus.pins.items()
                if capability in pin.get("capabilities", [])
            ),
            None,
        )
        return result if result is not None else self._raise_default(capability)

    @staticmethod
    def _raise_default(capability: str) -> Any:
        raise SimulationRuntimeFault(
            "SIM_PIN_CAPABILITY_UNAVAILABLE",
            f"当前板型没有默认 {capability} 引脚。",
        )

    def any(self) -> int:
        return len(self._buffer)

    def read(self, count: int | None = None) -> bytes | None:
        if not self._buffer:
            return None
        length = len(self._buffer) if count is None else min(len(self._buffer), count)
        result = bytes(self._buffer[:length])
        del self._buffer[:length]
        self.bus.collector.emit("UART_READ", f"uart:{self.id}", bytes=list(result))
        return result

    def readline(self) -> bytes | None:
        if not self._buffer:
            return None
        try:
            end = self._buffer.index(10) + 1
        except ValueError:
            end = len(self._buffer)
        return self.read(end)

    def write(self, data: str | bytes | bytearray) -> int:
        payload = data.encode("utf-8") if isinstance(data, str) else bytes(data)
        self.bus.collector.emit(
            "UART_WRITE",
            f"uart:{self.id}",
            bytes=list(payload),
            text=payload.decode("utf-8", errors="replace"),
            baudrate=self.baudrate,
        )
        return len(payload)

    def deinit(self) -> None:
        self.active = False


class Timer:
    ONE_SHOT = 0
    PERIODIC = 1

    def __init__(self, clock: VirtualClock, timer_id: int = -1) -> None:
        self.clock = clock
        self.id = int(timer_id)
        self._active = False
        self._period_us = 0
        self._mode = self.PERIODIC
        self._callback: Callable[[Timer], Any] | None = None
        self._due_us: int | None = None
        clock.register(self)

    def init(
        self,
        *,
        period: int = -1,
        mode: int = PERIODIC,
        callback: Callable[[Timer], Any] | None = None,
        freq: float = -1,
    ) -> None:
        if period >= 0:
            period_us = int(period) * 1000
        elif freq > 0:
            period_us = round(1_000_000 / freq)
        else:
            raise SimulationRuntimeFault(
                "SIM_TIMER_PERIOD_INVALID",
                "Timer 需要正数 period 或 freq。",
            )
        if period_us <= 0 or mode not in {self.ONE_SHOT, self.PERIODIC}:
            raise UnsupportedSimulationFeature("machine.Timer mode/period")
        if callback is None or not callable(callback):
            raise SimulationRuntimeFault(
                "SIM_TIMER_CALLBACK_REQUIRED",
                "Timer 需要可调用的 callback。",
            )
        self._period_us = period_us
        self._mode = mode
        self._callback = callback
        self._due_us = self.clock.now_us + period_us
        self._active = True

    def _fire(self) -> None:
        if not self._active or self._callback is None:
            return
        if self._mode == self.ONE_SHOT:
            self._active = False
            self._due_us = None
        else:
            assert self._due_us is not None
            self._due_us += self._period_us
        self.clock.collector.emit("TIMER_FIRED", f"timer:{self.id}", timerId=self.id)
        self._callback(self)

    def deinit(self) -> None:
        self._active = False
        self._due_us = None


class DHT22:
    def __init__(self, bus: ComponentBus, pin: Pin | int | str) -> None:
        self.bus = bus
        self.pin_id = bus.normalize_pin(pin)
        self._temperature: float | None = None
        self._humidity: float | None = None

    def measure(self) -> None:
        temperature, humidity, _part_id = self.bus.dht_measure(self.pin_id)
        self._temperature = temperature
        self._humidity = humidity

    def temperature(self) -> float:
        if self._temperature is None:
            raise SimulationRuntimeFault(
                "SIM_DHT_MEASURE_REQUIRED",
                "读取温度前必须先调用 DHT22.measure()。",
            )
        return self._temperature

    def humidity(self) -> float:
        if self._humidity is None:
            raise SimulationRuntimeFault(
                "SIM_DHT_MEASURE_REQUIRED",
                "读取湿度前必须先调用 DHT22.measure()。",
            )
        return self._humidity


class SSD1306I2C:
    def __init__(
        self,
        bus: ComponentBus,
        width: int,
        height: int,
        i2c: I2C,
        addr: int = 0x3C,
        external_vcc: bool = False,
    ) -> None:
        del external_vcc
        self.bus = bus
        self.width = int(width)
        self.height = int(height)
        self.i2c = i2c
        self.addr = int(addr)
        self.part = i2c._device(self.addr)
        if self.part["slug"] != "ssd1306":
            raise SimulationRuntimeFault(
                "SIM_I2C_COMPONENT_MISMATCH",
                f"I²C 地址 0x{addr:02x} 不是 SSD1306。",
            )
        self.operations: list[dict[str, Any]] = []

    def fill(self, color: int) -> None:
        self.operations = [{"op": "fill", "color": 1 if color else 0}]

    def pixel(self, x: int, y: int, color: int | None = None) -> int:
        if color is None:
            return 0
        self.operations.append(
            {"op": "pixel", "x": int(x), "y": int(y), "color": 1 if color else 0}
        )
        return 1 if color else 0

    def text(self, value: str, x: int, y: int, color: int = 1) -> None:
        self.operations.append(
            {
                "op": "text",
                "text": str(value)[:200],
                "x": int(x),
                "y": int(y),
                "color": 1 if color else 0,
            }
        )

    def show(self) -> None:
        self.bus.collector.emit(
            "DISPLAY_FRAME",
            self.part["id"],
            width=self.width,
            height=self.height,
            operations=self.operations[:256],
        )


class NeoPixel:
    def __init__(
        self,
        bus: ComponentBus,
        pin: Pin | int | str,
        count: int,
        bpp: int = 3,
        timing: int = 1,
    ) -> None:
        if bpp not in {3, 4} or timing not in {0, 1}:
            raise UnsupportedSimulationFeature("neopixel bpp/timing")
        self.bus = bus
        self.pin_id = bus.normalize_pin(pin)
        self.part = bus.component_for_pin(self.pin_id, "neopixel")
        self.count = int(count)
        if self.count <= 0 or self.count > 1024:
            raise SimulationRuntimeFault(
                "SIM_NEOPIXEL_COUNT_INVALID",
                "NeoPixel 数量必须在 1 到 1024 之间。",
            )
        self.values: list[tuple[int, ...]] = [(0,) * bpp for _ in range(self.count)]

    def __setitem__(self, index: int, value: tuple[int, ...] | list[int]) -> None:
        normalized = tuple(min(255, max(0, int(item))) for item in value)
        if len(normalized) != len(self.values[0]):
            raise SimulationRuntimeFault(
                "SIM_NEOPIXEL_COLOR_INVALID",
                "NeoPixel 颜色通道数量不匹配。",
            )
        self.values[index] = normalized

    def __getitem__(self, index: int) -> tuple[int, ...]:
        return self.values[index]

    def fill(self, value: tuple[int, ...] | list[int]) -> None:
        for index in range(self.count):
            self[index] = value

    def write(self) -> None:
        self.bus.collector.emit(
            "NEOPIXEL_FRAME",
            self.part["id"],
            pixels=[list(item) for item in self.values],
        )


class ReadOnlyBundleFile:
    def __init__(self, content: str, *, binary: bool) -> None:
        self._stream: io.StringIO | io.BytesIO
        self._stream = (
            io.BytesIO(content.encode("utf-8")) if binary else io.StringIO(content)
        )

    def __enter__(self) -> ReadOnlyBundleFile:
        return self

    def __exit__(self, *args: Any) -> None:
        del args
        self.close()

    def read(self, *args: Any) -> Any:
        return self._stream.read(*args)

    def readline(self, *args: Any) -> Any:
        return self._stream.readline(*args)

    def readlines(self, *args: Any) -> Any:
        return self._stream.readlines(*args)

    def seek(self, *args: Any) -> Any:
        return self._stream.seek(*args)

    def tell(self) -> int:
        return self._stream.tell()

    def close(self) -> None:
        self._stream.close()

    def write(self, *args: Any) -> None:
        del args
        raise UnsupportedSimulationFeature("host filesystem writes")


def build_modules(bus: ComponentBus) -> dict[str, ModuleType]:
    machine = ModuleType("machine")

    class BoundPin(Pin):
        def __init__(self, pin_id: Any, *args: Any, **kwargs: Any) -> None:
            super().__init__(bus, pin_id, *args, **kwargs)

    class BoundADC(ADC):
        def __init__(self, pin: Any, **kwargs: Any) -> None:
            super().__init__(bus, pin, **kwargs)

    class BoundPWM(PWM):
        def __init__(self, pin: Any, **kwargs: Any) -> None:
            super().__init__(bus, pin, **kwargs)

    class BoundI2C(I2C):
        def __init__(self, bus_id: int = -1, **kwargs: Any) -> None:
            super().__init__(bus, bus_id, **kwargs)

    class BoundSoftI2C(SoftI2C):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(bus, **kwargs)

    class BoundUART(UART):
        def __init__(self, uart_id: int, *args: Any, **kwargs: Any) -> None:
            super().__init__(bus, uart_id, *args, **kwargs)

    class BoundTimer(Timer):
        def __init__(self, timer_id: int = -1) -> None:
            super().__init__(bus.clock, timer_id)

    for name, value in {
        "Pin": BoundPin,
        "ADC": BoundADC,
        "PWM": BoundPWM,
        "I2C": BoundI2C,
        "SoftI2C": BoundSoftI2C,
        "UART": BoundUART,
        "Timer": BoundTimer,
    }.items():
        setattr(machine, name, value)

    def _unsupported_machine_attribute(name: str) -> Any:
        raise UnsupportedSimulationFeature(f"machine.{name}")

    machine.__getattr__ = _unsupported_machine_attribute

    time_module = ModuleType("time")
    time_module.sleep = lambda seconds: bus.clock.advance(round(float(seconds) * 1_000_000))
    time_module.sleep_ms = lambda milliseconds: bus.clock.advance(int(milliseconds) * 1000)
    time_module.sleep_us = lambda microseconds: bus.clock.advance(int(microseconds))
    time_module.ticks_ms = lambda: bus.clock.now_us // 1000
    time_module.ticks_us = lambda: bus.clock.now_us
    time_module.ticks_add = lambda ticks, delta: int(ticks) + int(delta)
    time_module.ticks_diff = lambda ticks1, ticks2: int(ticks1) - int(ticks2)

    dht_module = ModuleType("dht")

    class BoundDHT22(DHT22):
        def __init__(self, pin: Any) -> None:
            super().__init__(bus, pin)

    dht_module.DHT22 = BoundDHT22

    ssd1306_module = ModuleType("ssd1306")

    class BoundSSD1306I2C(SSD1306I2C):
        def __init__(self, width: int, height: int, i2c: I2C, **kwargs: Any) -> None:
            super().__init__(bus, width, height, i2c, **kwargs)

    ssd1306_module.SSD1306_I2C = BoundSSD1306I2C

    neopixel_module = ModuleType("neopixel")

    class BoundNeoPixel(NeoPixel):
        def __init__(self, pin: Any, count: int, *args: Any, **kwargs: Any) -> None:
            super().__init__(bus, pin, count, *args, **kwargs)

    neopixel_module.NeoPixel = BoundNeoPixel

    random_module = ModuleType("random")
    random_module.random = bus.random.random
    random_module.randint = bus.random.randint
    random_module.uniform = bus.random.uniform

    def reject_random_seed(*_args: Any, **_kwargs: Any) -> None:
        raise UnsupportedSimulationFeature("random.seed override")

    random_module.seed = reject_random_seed

    return {
        "machine": machine,
        "time": time_module,
        "dht": dht_module,
        "ssd1306": ssd1306_module,
        "neopixel": neopixel_module,
        "random": random_module,
    }
