"""Deterministic hardware compatibility checks for ZW-005."""

from __future__ import annotations

from collections import defaultdict

from zhangwen.hardware.models import (
    HardwareCategory,
    HardwareComponent,
    HardwareComponentStatus,
    HardwareRuleOperator,
    HardwareSkillRule,
    ValidationCheck,
    ValidationResult,
    ValidationSeverity,
)

VALID_PROTOCOLS = {"GPIO", "I2C", "SPI", "UART", "PWM", "ADC", "POWER", "NONE"}
VOLTAGE_TOLERANCE = 0.5
LOGIC_LEVEL_TOLERANCE = 0.3


def validate_components(
    components: list[HardwareComponent],
    *,
    rules: list[HardwareSkillRule] | None = None,
) -> ValidationResult:
    if rules is not None:
        return _validate_declared_rules(components, rules)

    checks: list[ValidationCheck] = []
    active_components = [
        component
        for component in components
        if component.status == HardwareComponentStatus.ACTIVE
    ]

    if not components:
        return ValidationResult(
            checks=[
                _check(
                    "component_selection",
                    ValidationSeverity.FAIL,
                    "没有可校验的硬件组件。",
                    "请求中未包含有效组件。",
                )
            ],
            overall=ValidationSeverity.FAIL,
            message="硬件组合校验未通过。",
        )

    archived = [
        component for component in components
        if component.status == HardwareComponentStatus.ARCHIVED
    ]
    for component in archived:
        checks.append(
            _check(
                "component_status",
                ValidationSeverity.FAIL,
                f"{component.name} 已归档，不能用于新方案。",
                component.id,
            )
        )

    mcus = [c for c in active_components if c.category == HardwareCategory.MCU]
    if not mcus:
        checks.append(
            _check(
                "mcu",
                ValidationSeverity.WARNING,
                "未选择主控板，无法完整判断电压、总线和固件兼容性。",
                "建议至少选择一个 ESP32 主控。",
            )
        )

    for component in active_components:
        checks.append(
            _check(
                "component_exists",
                ValidationSeverity.PASS,
                f"{component.name} 可用于校验。",
                component.id,
            )
        )

    checks.extend(_validate_voltage(active_components, mcus))
    checks.extend(_validate_logic_level(active_components, mcus))
    checks.extend(_validate_current(active_components))
    checks.extend(_validate_i2c(active_components))
    checks.extend(_validate_bus_and_firmware(active_components, mcus))

    overall = _overall(checks)
    return ValidationResult(
        checks=checks,
        overall=overall,
        message=_summary(overall),
    )


def _validate_declared_rules(
    components: list[HardwareComponent],
    rules: list[HardwareSkillRule],
) -> ValidationResult:
    """Execute only the fixed declarative operator allowlist.

    Field lookup is explicit below. Rule content is never evaluated as Python,
    an expression, a function name, or a path.
    """
    if not components:
        return ValidationResult(
            checks=[
                _check(
                    "component_selection",
                    ValidationSeverity.FAIL,
                    "没有可校验的硬件组件。",
                    "请求中未包含有效组件。",
                )
            ],
            overall=ValidationSeverity.FAIL,
            message="硬件组合校验未通过。",
        )

    checks: list[ValidationCheck] = []
    active = [
        component
        for component in components
        if component.status == HardwareComponentStatus.ACTIVE
    ]
    for component in components:
        if component.status == HardwareComponentStatus.ARCHIVED:
            checks.append(
                _check(
                    "component_status",
                    ValidationSeverity.FAIL,
                    f"{component.name} 已归档，不能用于新方案。",
                    component.id,
                )
            )
        else:
            checks.append(
                _check(
                    "component_exists",
                    ValidationSeverity.PASS,
                    f"{component.name} 可用于校验。",
                    component.id,
                )
            )

    mcus = [item for item in active if item.category == HardwareCategory.MCU]
    if not mcus:
        checks.append(
            _check(
                "mcu",
                ValidationSeverity.WARNING,
                "未选择主控板，无法完整判断电压、总线和固件兼容性。",
                "建议至少选择一个主控 Hardware Skill。",
            )
        )

    loads = [
        item
        for item in active
        if item.category not in {HardwareCategory.POWER, HardwareCategory.STRUCTURE}
        and item.electrical.peakCurrent > 0
    ]
    if loads and not any(item.category == HardwareCategory.POWER for item in active):
        checks.append(
            _check(
                "current",
                ValidationSeverity.WARNING,
                "未选择供电模块，无法确认峰值电流余量。",
                f"估算负载峰值 {sum(item.electrical.peakCurrent for item in loads):.2f}A。",
            )
        )

    seen_rules: set[tuple[str, str]] = set()
    for rule in rules:
        signature = (rule.id, rule.model_dump_json(exclude={"id"}))
        if signature in seen_rules:
            continue
        seen_rules.add(signature)
        if rule.operator == HardwareRuleOperator.RANGE_OVERLAP:
            checks.extend(_execute_range_overlap(active, rule))
        elif rule.operator == HardwareRuleOperator.SUM_LTE:
            checks.extend(_execute_sum_lte(active, rule))
        elif rule.operator == HardwareRuleOperator.UNIQUE:
            checks.extend(_execute_unique(active, rule))
        elif rule.operator == HardwareRuleOperator.CONTAINS_ANY:
            checks.extend(_execute_contains_any(active, rule))
        elif rule.operator == HardwareRuleOperator.REQUIRED_IF:
            checks.extend(_execute_required_if(active, rule))

    checks.extend(_validate_watering_topology(active))

    overall = _overall(checks)
    return ValidationResult(checks=checks, overall=overall, message=_summary(overall))


def _execute_range_overlap(
    components: list[HardwareComponent],
    rule: HardwareSkillRule,
) -> list[ValidationCheck]:
    field = rule.params.get("field")
    if field not in {"electrical.voltage", "electrical.logicLevel"}:
        return [_invalid_rule_check(rule, "range-overlap 字段不在白名单。")]
    subjects = _select_components(
        components,
        rule.params.get("leftCategories"),
        rule.params.get("componentId"),
    )
    targets = _select_components(components, rule.params.get("rightCategories"), None)
    if not subjects or not targets:
        return []
    tolerance = rule.params.get("tolerance", 0.0)
    if not isinstance(tolerance, (int, float)) or isinstance(tolerance, bool) or tolerance < 0:
        return [_invalid_rule_check(rule, "range-overlap tolerance 无效。")]
    dimension = "voltage" if field.endswith("voltage") else "logic_level"
    results: list[ValidationCheck] = []
    for subject in subjects:
        if field == "electrical.voltage":
            selection = _select_supply_rail(subject, targets, float(tolerance))
            if selection is None:
                results.append(
                    _check(
                        dimension,
                        rule.severity,
                        f"{subject.name}：{rule.message}",
                        _voltage_compatibility_details(subject, targets),
                    )
                )
                continue
            target, rail = selection
            recommended = abs(rail - subject.electrical.voltage) <= float(tolerance)
            results.append(
                _check(
                    dimension,
                    ValidationSeverity.PASS if recommended else ValidationSeverity.WARNING,
                    (
                        f"{subject.name} 可使用 {target.name} 的 {rail:g}V 外设电源轨。"
                        if recommended
                        else (
                            f"{subject.name} 可由 {target.name} 的 {rail:g}V 电源轨供电，"
                            f"但偏离推荐 {subject.electrical.voltage:g}V；需复核信号上限与保护。"
                        )
                    ),
                    _voltage_compatibility_details(
                        subject,
                        targets,
                        selected=(target, rail),
                    ),
                )
            )
            continue
        value = _field_value(subject, field)
        target_values = [_field_value(target, field) for target in targets]
        compatible = any(abs(float(value) - float(other)) <= float(tolerance) for other in target_values)
        results.append(
            _check(
                dimension,
                ValidationSeverity.PASS if compatible else rule.severity,
                (
                    f"{subject.name} 的{_field_label(field)}与当前主控组合可兼容。"
                    if compatible
                    else f"{subject.name}：{rule.message}"
                ),
                f"组件 {float(value):g}V，主控 {', '.join(f'{float(other):g}V' for other in target_values)}。",
            )
        )
    return results


def _execute_sum_lte(
    components: list[HardwareComponent],
    rule: HardwareSkillRule,
) -> list[ValidationCheck]:
    if rule.params.get("field") != "electrical.peakCurrent":
        return [_invalid_rule_check(rule, "sum-lte 字段不在白名单。")]
    loads = _select_components(components, rule.params.get("sumCategories"), None)
    limits = _select_components(
        components,
        rule.params.get("limitCategories"),
        rule.params.get("componentId"),
    )
    if not limits:
        return [
            _check(
                "current",
                rule.severity,
                rule.message,
                "未选择满足规则的独立电源；不得改由主控板或 GPIO 供电。",
            )
        ]
    total = sum(max(0.0, item.electrical.peakCurrent) for item in loads)
    capacity = max(max(0.0, item.electrical.peakCurrent) for item in limits)
    passed = capacity >= total
    return [
        _check(
            "current",
            ValidationSeverity.PASS if passed else rule.severity,
            "供电电流余量满足当前硬件组合。" if passed else rule.message,
            f"供电能力 {capacity:.2f}A，估算负载 {total:.2f}A。",
        )
    ]


def _execute_unique(
    components: list[HardwareComponent],
    rule: HardwareSkillRule,
) -> list[ValidationCheck]:
    if rule.params.get("field") != "electrical.i2cAddress":
        return [_invalid_rule_check(rule, "unique 字段不在白名单。")]
    owner_id = rule.params.get("componentId")
    subjects = _select_components(components, None, owner_id)
    if not subjects:
        return []
    when_field = rule.params.get("whenField")
    when_equals = str(rule.params.get("whenEquals", ""))
    results: list[ValidationCheck] = []
    for subject in subjects:
        if when_field:
            if when_field != "electrical.communicationProtocol":
                return [_invalid_rule_check(rule, "unique 条件字段不在白名单。")]
            if str(_field_value(subject, when_field)).casefold() != when_equals.casefold():
                continue
        address = subject.electrical.i2cAddress
        if not address:
            continue
        matches = [
            item
            for item in components
            if item.electrical.communicationProtocol.upper() == "I2C"
            and (item.electrical.i2cAddress or "").casefold() == address.casefold()
        ]
        passed = len(matches) <= 1
        results.append(
            _check(
                "i2c_address",
                ValidationSeverity.PASS if passed else rule.severity,
                "I2C 地址未发现冲突。" if passed else f"I2C 地址 {address.casefold()}：{rule.message}",
                ", ".join(item.name for item in matches),
            )
        )
    return results


def _execute_contains_any(
    components: list[HardwareComponent],
    rule: HardwareSkillRule,
) -> list[ValidationCheck]:
    if (
        rule.params.get("field") != "electrical.supportedMCUs"
        or rule.params.get("candidateField") != "identifiers"
    ):
        return [_invalid_rule_check(rule, "contains-any 字段不在白名单。")]
    subjects = _select_components(
        components,
        rule.params.get("subjectCategories"),
        rule.params.get("componentId"),
    )
    candidates = _select_components(components, rule.params.get("candidateCategories"), None)
    if not subjects or not candidates:
        return []
    candidate_values = {
        value.casefold()
        for candidate in candidates
        for value in (candidate.id, candidate.name, *candidate.electrical.supportedMCUs)
    }
    results: list[ValidationCheck] = []
    for subject in subjects:
        supported = {value.casefold() for value in subject.electrical.supportedMCUs}
        if not supported:
            continue
        passed = bool(supported & candidate_values)
        results.append(
            _check(
                "mcu_support",
                ValidationSeverity.PASS if passed else rule.severity,
                f"{subject.name} 已声明支持当前主控。" if passed else f"{subject.name}：{rule.message}",
                f"支持列表: {', '.join(subject.electrical.supportedMCUs)}",
            )
        )
    return results


def _execute_required_if(
    components: list[HardwareComponent],
    rule: HardwareSkillRule,
) -> list[ValidationCheck]:
    if (
        rule.params.get("requiredField") != "electrical.driverName"
        or rule.params.get("ifField") != "electrical.firmwareRequirement"
    ):
        return [_invalid_rule_check(rule, "required-if 字段不在白名单。")]
    subjects = _select_components(components, None, rule.params.get("componentId"))
    results: list[ValidationCheck] = []
    for subject in subjects:
        condition_value = subject.electrical.firmwareRequirement
        condition = bool(condition_value) if rule.params.get("ifPresent", False) else (
            condition_value == rule.params.get("ifEquals")
        )
        if not condition:
            continue
        passed = bool(subject.electrical.driverName)
        results.append(
            _check(
                "firmware",
                ValidationSeverity.PASS if passed else rule.severity,
                f"{subject.name} 已登记驱动名称。" if passed else f"{subject.name}：{rule.message}",
                str(condition_value or ""),
            )
        )
    return results


def _validate_watering_topology(
    components: list[HardwareComponent],
) -> list[ValidationCheck]:
    by_id = {component.id: component for component in components}
    sensor = by_id.get("hw_dfrobot_sen0193")
    pump = by_id.get("hw_dfrobot_dfr0523")
    k10 = by_id.get("hw_seed_unihiker_k10")
    checks: list[ValidationCheck] = []
    if sensor is not None:
        checks.append(
            _check(
                "watering_sensor_adc",
                ValidationSeverity.PASS if k10 is not None else ValidationSeverity.FAIL,
                (
                    "SEN0193 使用 K10 的 3.3V 外设电源并连接 ADC；模拟输出上限 3.0V。"
                    if k10 is not None
                    else "SEN0193 方案缺少 K10，无法确认 3.3V 供电与 ADC 接线。"
                ),
                "SEN0193: VCC=3.3V, signal=K10 ADC, output<=3.0V",
            )
        )
    if pump is not None:
        power = next(
            (
                component
                for component in components
                if component.category == HardwareCategory.POWER
                and 5.0 >= (component.electrical.voltageMin or component.electrical.voltage)
                and 5.0 <= (component.electrical.voltageMax or component.electrical.voltage)
                and component.electrical.peakCurrent >= 2.5
            ),
            None,
        )
        checks.append(
            _check(
                "watering_pump_control",
                ValidationSeverity.PASS
                if k10 is not None and power is not None
                else ValidationSeverity.FAIL,
                (
                    "DFR0523 控制信号连接 K10 支持的 PWM 引脚；水泵由独立 5V/3A 电源供电并与 K10 共地。"
                    if k10 is not None and power is not None
                    else "DFR0523 必须连接 K10 PWM，并使用独立稳压 5V/3A 电源与 K10 共地；不得由 GPIO 或板载电源供电。"
                ),
                "pump signal=PWM; load power=external 5V/3A; common ground required",
            )
        )
    return checks


def _select_components(
    components: list[HardwareComponent],
    categories: object,
    component_id: object,
) -> list[HardwareComponent]:
    category_values = (
        {str(value) for value in categories}
        if isinstance(categories, list)
        else None
    )
    return [
        component
        for component in components
        if (category_values is None or component.category.value in category_values)
        and (component_id is None or component.id == component_id)
    ]


def _field_value(component: HardwareComponent, field: str) -> object:
    fields: dict[str, object] = {
        "electrical.voltage": component.electrical.voltage,
        "electrical.logicLevel": component.electrical.logicLevel,
        "electrical.peakCurrent": component.electrical.peakCurrent,
        "electrical.communicationProtocol": component.electrical.communicationProtocol,
        "electrical.i2cAddress": component.electrical.i2cAddress,
        "electrical.supportedMCUs": component.electrical.supportedMCUs,
        "electrical.driverName": component.electrical.driverName,
        "electrical.firmwareRequirement": component.electrical.firmwareRequirement,
    }
    return fields[field]


def _field_label(field: str) -> str:
    return "工作电压" if field.endswith("voltage") else "逻辑电平"


def _invalid_rule_check(rule: HardwareSkillRule, details: str) -> ValidationCheck:
    return _check(
        "rule",
        ValidationSeverity.FAIL,
        f"声明式规则 {rule.id} 无效。",
        details,
    )


def _validate_voltage(
    components: list[HardwareComponent],
    mcus: list[HardwareComponent],
) -> list[ValidationCheck]:
    checks: list[ValidationCheck] = []
    if not mcus:
        return checks

    for component in components:
        if component.category in {HardwareCategory.MCU, HardwareCategory.STRUCTURE}:
            continue
        selection = _select_supply_rail(component, mcus, VOLTAGE_TOLERANCE)
        if component.category == HardwareCategory.POWER:
            checks.append(
                _check(
                    "voltage",
                    ValidationSeverity.PASS,
                    f"{component.name} 作为独立供电模块保留额定电压校验。",
                    f"{component.electrical.voltage:g}V",
                )
            )
        elif selection is not None:
            mcu, rail = selection
            recommended = (
                abs(rail - component.electrical.voltage) <= VOLTAGE_TOLERANCE
            )
            checks.append(
                _check(
                    "voltage",
                    ValidationSeverity.PASS if recommended else ValidationSeverity.WARNING,
                    (
                        f"{component.name} 可使用 {mcu.name} 的 {rail:g}V 外设电源轨。"
                        if recommended
                        else (
                            f"{component.name} 可由 {mcu.name} 的 {rail:g}V 电源轨供电，"
                            f"但偏离推荐 {component.electrical.voltage:g}V；"
                            "需复核信号上限与保护。"
                        )
                    ),
                    _voltage_compatibility_details(
                        component,
                        mcus,
                        selected=(mcu, rail),
                    ),
                )
            )
        else:
            checks.append(
                _check(
                    "voltage",
                    ValidationSeverity.FAIL,
                    f"{component.name} 的允许工作电压范围与主控外设电源轨不匹配。",
                    _voltage_compatibility_details(component, mcus),
                )
            )
    return checks


def _select_supply_rail(
    component: HardwareComponent,
    sources: list[HardwareComponent],
    tolerance: float,
) -> tuple[HardwareComponent, float] | None:
    minimum, maximum, explicit_range = _voltage_range(component)
    candidates: list[tuple[HardwareComponent, float]] = []
    for source in sources:
        for rail in _supply_rails(source):
            compatible = (
                minimum <= rail <= maximum
                if explicit_range
                else abs(rail - component.electrical.voltage) <= tolerance
            )
            if compatible:
                candidates.append((source, rail))
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda item: (
            abs(item[1] - component.electrical.voltage),
            item[0].name,
            item[1],
        ),
    )


def _voltage_range(component: HardwareComponent) -> tuple[float, float, bool]:
    electrical = component.electrical
    explicit = electrical.voltageMin is not None or electrical.voltageMax is not None
    minimum = electrical.voltage if electrical.voltageMin is None else electrical.voltageMin
    maximum = electrical.voltage if electrical.voltageMax is None else electrical.voltageMax
    return minimum, maximum, explicit


def _supply_rails(component: HardwareComponent) -> list[float]:
    return component.electrical.supplyVoltages or [component.electrical.voltage]


def _voltage_compatibility_details(
    component: HardwareComponent,
    sources: list[HardwareComponent],
    *,
    selected: tuple[HardwareComponent, float] | None = None,
) -> str:
    minimum, maximum, _explicit = _voltage_range(component)
    allowed = (
        f"{minimum:g}–{maximum:g}V"
        if minimum != maximum
        else f"{component.electrical.voltage:g}V"
    )
    rails = "；".join(
        f"{source.name}:{'/'.join(f'{rail:g}V' for rail in _supply_rails(source))}"
        for source in sources
    )
    selected_text = (
        f"；选择 {selected[0].name}:{selected[1]:g}V"
        if selected is not None
        else ""
    )
    return (
        f"器件允许 {allowed}，推荐 {component.electrical.voltage:g}V；"
        f"可用外设电源轨 {rails or '无'}{selected_text}。"
    )


def _validate_logic_level(
    components: list[HardwareComponent],
    mcus: list[HardwareComponent],
) -> list[ValidationCheck]:
    checks: list[ValidationCheck] = []
    if not mcus:
        return checks

    for component in components:
        if component.category in {
            HardwareCategory.MCU,
            HardwareCategory.POWER,
            HardwareCategory.STRUCTURE,
        }:
            continue
        compatible = [
            mcu for mcu in mcus
            if abs(component.electrical.logicLevel - mcu.electrical.logicLevel)
            <= LOGIC_LEVEL_TOLERANCE
        ]
        if compatible:
            checks.append(
                _check(
                    "logic_level",
                    ValidationSeverity.PASS,
                    f"{component.name} 的逻辑电平匹配主控。",
                    f"{component.electrical.logicLevel:g}V",
                )
            )
        else:
            checks.append(
                _check(
                    "logic_level",
                    ValidationSeverity.FAIL,
                    f"{component.name} 的逻辑电平与主控不兼容。",
                    (
                        f"组件 {component.electrical.logicLevel:g}V，"
                        f"主控 {', '.join(f'{m.name}:{m.electrical.logicLevel:g}V' for m in mcus)}。"
                    ),
                )
            )
    return checks


def _validate_current(components: list[HardwareComponent]) -> list[ValidationCheck]:
    loads = [
        c for c in components
        if c.category not in {HardwareCategory.POWER, HardwareCategory.STRUCTURE}
    ]
    power_sources = [c for c in components if c.category == HardwareCategory.POWER]
    total_load = sum(max(0.0, c.electrical.peakCurrent) for c in loads)

    if total_load <= 0:
        return []
    if not power_sources:
        return [
            _check(
                "current",
                ValidationSeverity.WARNING,
                "未选择供电模块，无法确认峰值电流余量。",
                f"估算负载峰值 {total_load:.2f}A。",
            )
        ]

    capacity = max(source.electrical.peakCurrent for source in power_sources)
    if capacity >= total_load:
        return [
            _check(
                "current",
                ValidationSeverity.PASS,
                "供电电流余量满足当前硬件组合。",
                f"供电能力 {capacity:.2f}A，估算负载 {total_load:.2f}A。",
            )
        ]
    return [
        _check(
            "current",
            ValidationSeverity.FAIL,
            "供电电流不足，存在掉电或过热风险。",
            f"供电能力 {capacity:.2f}A，估算负载 {total_load:.2f}A。",
        )
    ]


def _validate_i2c(components: list[HardwareComponent]) -> list[ValidationCheck]:
    addresses: dict[str, list[HardwareComponent]] = defaultdict(list)
    for component in components:
        protocol = component.electrical.communicationProtocol.upper()
        if protocol == "I2C" and component.electrical.i2cAddress:
            addresses[component.electrical.i2cAddress.lower()].append(component)

    checks: list[ValidationCheck] = []
    for address, same_address in addresses.items():
        if len(same_address) > 1:
            checks.append(
                _check(
                    "i2c_address",
                    ValidationSeverity.FAIL,
                    f"I2C 地址 {address} 被多个组件占用。",
                    ", ".join(component.name for component in same_address),
                )
            )
    if not checks and addresses:
        checks.append(
            _check(
                "i2c_address",
                ValidationSeverity.PASS,
                "I2C 地址未发现冲突。",
                ", ".join(sorted(addresses.keys())),
            )
        )
    return checks


def _validate_bus_and_firmware(
    components: list[HardwareComponent],
    mcus: list[HardwareComponent],
) -> list[ValidationCheck]:
    checks: list[ValidationCheck] = []
    mcu_keys = {
        value.lower()
        for mcu in mcus
        for value in (mcu.id, mcu.name, *mcu.electrical.supportedMCUs)
    }

    for component in components:
        protocol = component.electrical.communicationProtocol.upper()
        if protocol not in VALID_PROTOCOLS:
            checks.append(
                _check(
                    "bus",
                    ValidationSeverity.WARNING,
                    f"{component.name} 使用未登记的通信协议 {protocol}。",
                    "请人工确认接线和驱动支持。",
                )
            )

        supported = {item.lower() for item in component.electrical.supportedMCUs}
        if mcus and supported and not (supported & mcu_keys):
            checks.append(
                _check(
                    "mcu_support",
                    ValidationSeverity.FAIL,
                    f"{component.name} 未声明支持当前主控。",
                    f"支持列表: {', '.join(component.electrical.supportedMCUs)}",
                )
            )

        if component.electrical.firmwareRequirement and not component.electrical.driverName:
            checks.append(
                _check(
                    "firmware",
                    ValidationSeverity.WARNING,
                    f"{component.name} 有固件要求，但未登记驱动名称。",
                    component.electrical.firmwareRequirement,
                )
            )
    return checks


def _check(
    dimension: str,
    severity: ValidationSeverity,
    message: str,
    details: str,
) -> ValidationCheck:
    return ValidationCheck(
        dimension=dimension,
        severity=severity,
        message=message,
        details=details,
    )


def _overall(checks: list[ValidationCheck]) -> ValidationSeverity:
    if any(check.severity == ValidationSeverity.FAIL for check in checks):
        return ValidationSeverity.FAIL
    if any(check.severity == ValidationSeverity.WARNING for check in checks):
        return ValidationSeverity.WARNING
    return ValidationSeverity.PASS


def _summary(overall: ValidationSeverity) -> str:
    if overall == ValidationSeverity.FAIL:
        return "硬件组合校验未通过，请先处理失败项。"
    if overall == ValidationSeverity.WARNING:
        return "硬件组合存在需要人工确认的风险。"
    return "硬件组合校验通过。"
