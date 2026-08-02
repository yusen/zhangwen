"""Tests for ZW-005 deterministic hardware validation."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from zhangwen.config import settings
from zhangwen.hardware.models import (
    ElectricalProps,
    HardwareCategory,
    HardwareComponent,
    HardwareComponentStatus,
    HardwareRuleOperator,
    HardwareSkillRule,
    ValidationSeverity,
)
from zhangwen.hardware.rule_engine import validate_components
from zhangwen.main import app


def _component(
    component_id: str,
    name: str,
    category: HardwareCategory,
    electrical: ElectricalProps,
) -> HardwareComponent:
    now = datetime.now(UTC).isoformat()
    return HardwareComponent(
        id=component_id,
        name=name,
        category=category,
        status=HardwareComponentStatus.ACTIVE,
        electrical=electrical,
        stock=1,
        price=1.0,
        createdAt=now,
        updatedAt=now,
    )


def _electrical(
    voltage: float = 3.3,
    logic: float = 3.3,
    current: float = 0.05,
    protocol: str = "GPIO",
    i2c: str | None = None,
    supported: list[str] | None = None,
    driver: str | None = None,
    firmware: str | None = None,
    voltage_min: float | None = None,
    voltage_max: float | None = None,
    supply_voltages: list[float] | None = None,
) -> ElectricalProps:
    return ElectricalProps(
        voltage=voltage,
        voltageMin=voltage_min,
        voltageMax=voltage_max,
        supplyVoltages=supply_voltages or [],
        logicLevel=logic,
        peakCurrent=current,
        communicationProtocol=protocol,
        i2cAddress=i2c,
        supportedMCUs=supported or ["esp32-s3"],
        driverName=driver,
        firmwareRequirement=firmware,
    )


def test_rule_engine_selects_k10_3v3_rail_for_dfr0026_range() -> None:
    k10 = _component(
        "hw_seed_unihiker_k10",
        "行空板 K10",
        HardwareCategory.MCU,
        _electrical(
            voltage=5.0,
            logic=3.3,
            current=0,
            supply_voltages=[3.3, 5.0],
            supported=["unihiker-k10", "esp32-s3"],
        ),
    )
    sensor = _component(
        "hw_dfrobot_dfr0026",
        "DFRobot DFR0026 模拟环境光线传感器",
        HardwareCategory.SENSOR,
        _electrical(
            voltage=3.3,
            voltage_min=3.0,
            voltage_max=5.0,
            logic=3.3,
            current=0,
            protocol="ANALOG",
            supported=["unihiker-k10"],
        ),
    )
    voltage_rule = HardwareSkillRule(
        id="voltage-hw_dfrobot_dfr0026",
        operator=HardwareRuleOperator.RANGE_OVERLAP,
        severity=ValidationSeverity.FAIL,
        message="DFR0026 的允许供电范围与主控外设电源轨不匹配。",
        params={
            "field": "electrical.voltage",
            "leftCategories": ["SENSOR"],
            "rightCategories": ["MCU"],
            "tolerance": 0.5,
            "componentId": sensor.id,
        },
    )

    result = validate_components([k10, sensor], rules=[voltage_rule])

    assert result.overall == ValidationSeverity.PASS
    voltage = next(check for check in result.checks if check.dimension == "voltage")
    assert voltage.severity == ValidationSeverity.PASS
    assert "3.3V 外设电源轨" in voltage.message
    assert "选择 行空板 K10:3.3V" in voltage.details


def test_voltage_range_warns_for_non_recommended_rail_and_rejects_missing_rail() -> None:
    sensor = _component(
        "sensor",
        "范围传感器",
        HardwareCategory.SENSOR,
        _electrical(
            voltage=3.3,
            voltage_min=3.0,
            voltage_max=5.0,
            logic=3.3,
            current=0,
        ),
    )
    five_volt_only = _component(
        "mcu_5v",
        "仅 5V 主控",
        HardwareCategory.MCU,
        _electrical(voltage=5.0, logic=3.3, current=0, supply_voltages=[5.0]),
    )
    one_volt_eight_only = _component(
        "mcu_1v8",
        "仅 1.8V 主控",
        HardwareCategory.MCU,
        _electrical(voltage=1.8, logic=1.8, current=0, supply_voltages=[1.8]),
    )

    warning = validate_components([five_volt_only, sensor])
    rejected = validate_components([one_volt_eight_only, sensor])

    assert warning.overall == ValidationSeverity.WARNING
    assert any(
        check.dimension == "voltage"
        and check.severity == ValidationSeverity.WARNING
        and "偏离推荐 3.3V" in check.message
        for check in warning.checks
    )
    assert rejected.overall == ValidationSeverity.FAIL
    assert any(
        check.dimension == "voltage" and check.severity == ValidationSeverity.FAIL
        for check in rejected.checks
    )


def test_compatible_supply_rail_does_not_bypass_signal_level_failure() -> None:
    result = validate_components([
        _component(
            "mcu",
            "3.3V ADC 主控",
            HardwareCategory.MCU,
            _electrical(
                voltage=5.0,
                logic=3.3,
                current=0,
                supply_voltages=[3.3, 5.0],
            ),
        ),
        _component(
            "sensor",
            "5V 模拟输出传感器",
            HardwareCategory.SENSOR,
            _electrical(
                voltage=5.0,
                voltage_min=3.0,
                voltage_max=5.0,
                logic=5.0,
                current=0,
            ),
        ),
    ])

    assert result.overall == ValidationSeverity.FAIL
    assert any(
        check.dimension == "voltage" and check.severity == ValidationSeverity.PASS
        for check in result.checks
    )
    assert any(
        check.dimension == "logic_level" and check.severity == ValidationSeverity.FAIL
        for check in result.checks
    )


def test_rule_engine_passes_compatible_esp32_combination() -> None:
    result = validate_components([
        _component(
            "mcu",
            "ESP32-S3",
            HardwareCategory.MCU,
            _electrical(current=0.5, supported=["esp32-s3"]),
        ),
        _component(
            "sensor",
            "BME280",
            HardwareCategory.SENSOR,
            _electrical(protocol="I2C", i2c="0x76", driver="bme280"),
        ),
        _component(
            "display",
            "OLED",
            HardwareCategory.DISPLAY,
            _electrical(protocol="I2C", i2c="0x3c", driver="ssd1306"),
        ),
        _component(
            "power",
            "USB Power",
            HardwareCategory.POWER,
            _electrical(voltage=5.0, logic=5.0, current=2.0, protocol="POWER"),
        ),
    ])

    assert result.overall == ValidationSeverity.PASS
    assert {check.dimension for check in result.checks} >= {
        "voltage",
        "logic_level",
        "current",
        "i2c_address",
    }


def test_rule_engine_fails_voltage_logic_i2c_and_current() -> None:
    result = validate_components([
        _component("mcu", "ESP32-S3", HardwareCategory.MCU, _electrical(current=0.5)),
        _component(
            "relay",
            "5V Relay",
            HardwareCategory.ACTUATOR,
            _electrical(voltage=5.0, logic=5.0, current=0.08),
        ),
        _component(
            "sensor_a",
            "I2C Sensor A",
            HardwareCategory.SENSOR,
            _electrical(protocol="I2C", i2c="0x76", current=0.6),
        ),
        _component(
            "sensor_b",
            "I2C Sensor B",
            HardwareCategory.SENSOR,
            _electrical(protocol="I2C", i2c="0x76", current=0.6),
        ),
        _component(
            "power",
            "Small Power",
            HardwareCategory.POWER,
            _electrical(voltage=5.0, logic=5.0, current=0.5, protocol="POWER"),
        ),
    ])

    failed_dimensions = {
        check.dimension
        for check in result.checks
        if check.severity == ValidationSeverity.FAIL
    }
    assert result.overall == ValidationSeverity.FAIL
    assert {"voltage", "logic_level", "i2c_address", "current"}.issubset(
        failed_dimensions
    )


def test_hardware_validate_endpoint_seeds_default_components(tmp_path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)

    listed = client.get("/api/hardware")
    assert listed.status_code == 200
    components = listed.json()["components"]
    assert len(components) >= 10
    assert any(component["id"] == "hw_seed_unihiker_k10" for component in components)
    assert any(component["id"] == "hw_seeed_xiao_esp32s3_sense" for component in components)
    assert not any(component["id"] == "hw_seed_esp32_s3_devkit" for component in components)

    validation = client.post(
        "/api/hardware/validate",
        json={
            "componentIds": [
                "hw_seed_unihiker_k10",
                "hw_seed_bme280",
                "hw_seed_oled_096",
                "hw_missing",
            ]
        },
    )
    assert validation.status_code == 200
    body = validation.json()["result"]
    assert body["overall"] == "FAIL"
    assert any(
        check["dimension"] == "component_exists"
        and check["severity"] == "FAIL"
        for check in body["checks"]
    )


def test_solution_generation_blocks_invalid_hardware_before_llm_config(tmp_path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    created = client.post(
        "/api/projects",
        json={"name": "test", "initialIdea": "test"},
    )
    project_id = created.json()["workspace"]["project"]["id"]

    response = client.post(
        f"/api/projects/{project_id}/solution/generate",
        json={
            "componentIds": [
                "hw_seed_unihiker_k10",
                "hw_seed_relay_5v",
            ]
        },
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "HARDWARE_VALIDATION_FAILED"
    assert any(check["severity"] == "FAIL" for check in detail["checks"])
