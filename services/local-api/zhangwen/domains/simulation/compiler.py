"""L0 static circuit compiler; it never executes student code."""

from __future__ import annotations

from collections import defaultdict

from zhangwen.domains.simulation.catalog import SimulationCatalog
from zhangwen.domains.simulation.digest import canonical_digest
from zhangwen.domains.simulation.models import (
    CircuitDraftV1,
    SimulationDiagnosticSeverity,
    SimulationStaticCompilation,
    SimulationStaticDiagnostic,
)


def compile_circuit(
    circuit: CircuitDraftV1, catalog: SimulationCatalog
) -> SimulationStaticCompilation:
    diagnostics: list[SimulationStaticDiagnostic] = []
    board = catalog.board(circuit.board_instance.board_package_revision_id)
    board_pins = {item.id: item for item in board.pins} if board else {}
    if board is None:
        _add(
            diagnostics,
            "ERROR",
            "SIM_BOARD_UNKNOWN",
            "当前板型 revision 不在已审核的仿真目录中。",
            circuit.board_instance.id,
        )

    part_profiles = {
        part.id: catalog.component(part.component_package_revision_id)
        for part in circuit.parts
    }
    for part in circuit.parts:
        if part_profiles[part.id] is None:
            _add(
                diagnostics,
                "ERROR",
                "SIM_COMPONENT_UNKNOWN",
                f"器件 {part.id} 没有受信任的组件模型，只能作为只读占位。",
                part.id,
            )

    instances = {circuit.board_instance.id, *(item.id for item in circuit.parts)}
    endpoint_nets: dict[tuple[str, str], list[str]] = defaultdict(list)
    net_endpoints: dict[str, set[tuple[str, str]]] = {}
    for net in circuit.nets:
        endpoints = {(item.instance_id, item.pin_id) for item in net.endpoints}
        net_endpoints[net.id] = endpoints
        if len(endpoints) != len(net.endpoints):
            _add(
                diagnostics,
                "ERROR",
                "SIM_ENDPOINT_DUPLICATE",
                f"连线组 {net.id} 重复引用了同一端点。",
                net.id,
            )
        power_caps: set[str] = set()
        signal_outputs = 0
        for instance_id, pin_id in endpoints:
            endpoint_nets[(instance_id, pin_id)].append(net.id)
            if instance_id not in instances:
                _add(
                    diagnostics,
                    "ERROR",
                    "SIM_ENDPOINT_INSTANCE_MISSING",
                    f"连线组 {net.id} 引用了不存在的实例 {instance_id}。",
                    net.id,
                )
                continue
            if instance_id == circuit.board_instance.id:
                pin = board_pins.get(pin_id)
                if pin is None:
                    _add(
                        diagnostics,
                        "ERROR",
                        "SIM_BOARD_PIN_UNKNOWN",
                        f"参考板没有引脚 {pin_id}。",
                        net.id,
                    )
                    continue
                power_caps.update(
                    item
                    for item in pin.capabilities
                    if item in {"POWER_3V3", "POWER_5V", "GROUND"}
                )
                if pin.reserved:
                    _add(
                        diagnostics,
                        "WARNING",
                        "SIM_BOARD_PIN_RESERVED",
                        f"{pin.label} 默认保留；需核对具体板型包和部署通道。",
                        net.id,
                    )
                continue
            part = next(item for item in circuit.parts if item.id == instance_id)
            profile = part_profiles[instance_id]
            if profile is None:
                continue
            component_pin = next((item for item in profile.pins if item.id == pin_id), None)
            if component_pin is None:
                _add(
                    diagnostics,
                    "ERROR",
                    "SIM_COMPONENT_PIN_UNKNOWN",
                    f"器件 {instance_id} 没有引脚 {pin_id}。",
                    net.id,
                )
            elif component_pin.role in {"SIGNAL_OUT", "ANALOG_OUT"}:
                signal_outputs += 1
        if "GROUND" in power_caps and power_caps & {"POWER_3V3", "POWER_5V"}:
            _add(
                diagnostics,
                "ERROR",
                "SIM_POWER_GROUND_SHORT",
                f"连线组 {net.id} 把电源与地直接短接。",
                net.id,
            )
        if {"POWER_3V3", "POWER_5V"}.issubset(power_caps):
            _add(
                diagnostics,
                "ERROR",
                "SIM_POWER_DOMAIN_SHORT",
                f"连线组 {net.id} 混接了 3.3V 与 5V。",
                net.id,
            )
        if signal_outputs > 1:
            _add(
                diagnostics,
                "ERROR",
                "SIM_OUTPUT_CONFLICT",
                f"连线组 {net.id} 包含多个主动输出。",
                net.id,
            )

    for endpoint, net_ids in endpoint_nets.items():
        if len(net_ids) > 1:
            _add(
                diagnostics,
                "ERROR",
                "SIM_ENDPOINT_MULTIPLE_NETS",
                f"端点 {endpoint[0]}:{endpoint[1]} 同时属于多个连线组。",
                endpoint[0],
            )

    i2c_addresses: dict[str, list[str]] = defaultdict(list)
    for part in circuit.parts:
        profile = part_profiles[part.id]
        if profile is None:
            continue
        for pin in profile.pins:
            if not pin.required:
                continue
            net_ids = endpoint_nets.get((part.id, pin.id), [])
            if not net_ids:
                severity = (
                    "ERROR"
                    if pin.role
                    in {
                        "POWER_3V3",
                        "POWER_5V",
                        "GROUND",
                        "I2C_SDA",
                        "I2C_SCL",
                        "PWM_IN",
                        "ANALOG_OUT",
                    }
                    else "WARNING"
                )
                _add(
                    diagnostics,
                    severity,
                    "SIM_REQUIRED_PIN_UNCONNECTED",
                    f"器件 {part.id} 的必需引脚 {pin.id} 尚未连接。",
                    part.id,
                )
                continue
            board_caps = _connected_board_capabilities(
                net_endpoints[net_ids[0]], circuit.board_instance.id, board_pins
            )
            required_capability = {
                "POWER_3V3": "POWER_3V3",
                "POWER_5V": "POWER_5V",
                "GROUND": "GROUND",
                "ANALOG_OUT": "ADC",
                "PWM_IN": "PWM",
                "I2C_SDA": "I2C_SDA",
                "I2C_SCL": "I2C_SCL",
                "SIGNAL_IN": "DIGITAL_OUT",
                "SIGNAL_OUT": "DIGITAL_IN",
                "DIGITAL_BIDIRECTIONAL": "DIGITAL_IN",
            }.get(pin.role)
            if required_capability and required_capability not in board_caps:
                _add(
                    diagnostics,
                    "ERROR",
                    "SIM_PIN_CAPABILITY_MISMATCH",
                    f"器件 {part.id}:{pin.id} 没有连接到支持 {required_capability} 的板端。",
                    part.id,
                )
        if profile.protocol == "I2C":
            address = str(
                part.properties.get(
                    "i2cAddress", profile.default_properties.get("i2cAddress", "")
                )
            ).casefold()
            if address:
                i2c_addresses[address].append(part.id)

    for address, part_ids in i2c_addresses.items():
        if len(part_ids) > 1:
            _add(
                diagnostics,
                "ERROR",
                "SIM_I2C_ADDRESS_CONFLICT",
                f"I²C 地址 {address} 被多个器件占用：{'、'.join(sorted(part_ids))}。",
                part_ids[0],
            )

    if not circuit.parts:
        _add(
            diagnostics,
            "WARNING",
            "SIM_CIRCUIT_EMPTY",
            "电路尚未加入器件；可以保存草稿，但还没有可验证功能。",
            circuit.board_instance.id,
        )
    diagnostics.sort(
        key=lambda item: (
            {"ERROR": 0, "WARNING": 1, "INFO": 2}[item.severity.value],
            item.code,
            item.target_id or "",
            item.message,
        )
    )
    return SimulationStaticCompilation(
        runnable=not any(
            item.severity is SimulationDiagnosticSeverity.ERROR
            for item in diagnostics
        ),
        circuitDigest=canonical_digest(circuit),
        diagnostics=diagnostics,
    )


def _connected_board_capabilities(
    endpoints: set[tuple[str, str]],
    board_instance_id: str,
    board_pins: dict[str, object],
) -> set[str]:
    capabilities: set[str] = set()
    for instance_id, pin_id in endpoints:
        if instance_id != board_instance_id:
            continue
        pin = board_pins.get(pin_id)
        if pin is not None:
            capabilities.update(getattr(pin, "capabilities"))
    return capabilities


def _add(
    diagnostics: list[SimulationStaticDiagnostic],
    severity: str,
    code: str,
    message: str,
    target_id: str | None,
) -> None:
    diagnostics.append(
        SimulationStaticDiagnostic(
            severity=severity,
            code=code,
            message=message,
            targetId=target_id,
        )
    )
