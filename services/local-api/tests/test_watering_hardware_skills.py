from __future__ import annotations

from pathlib import Path

import pytest

from zhangwen.hardware.hardware_skills import HardwareSkillRepository
from zhangwen.hardware.seeds import seed_default_components
from zhangwen.hardware.models import ValidationSeverity
from zhangwen.projects.repository import ProjectRepository


def _skills(tmp_path: Path) -> HardwareSkillRepository:
    projects = ProjectRepository(tmp_path)
    seed_default_components(projects.db_path)
    skills = HardwareSkillRepository(tmp_path, projects.db_path)
    result = skills.install_bundled_catalog()
    assert result.invalidExisting == 0
    skills.migrate_legacy_rows()
    return skills


def test_watering_catalog_installs_official_sensor_pump_and_power_packages(
    tmp_path: Path,
) -> None:
    skills = _skills(tmp_path)
    sensor = skills.get_skill("sen0193")
    pump = skills.get_skill("dfr0523")
    power = skills.get_skill("regulated-5v-3a-power")

    assert sensor.verificationStatus == "OFFICIAL_DOC_VERIFIED"
    assert sensor.specification.electrical.voltageMin == 3.3
    assert sensor.specification.electrical.voltageMax == 5.5
    assert sensor.specification.electrical.logicLevel == 3.0
    assert pump.verificationStatus == "OFFICIAL_DOC_VERIFIED"
    assert pump.specification.electrical.voltageMin == 5.0
    assert pump.specification.electrical.voltageMax == 6.0
    assert pump.specification.electrical.peakCurrent == 2.5
    assert power.specification.electrical.peakCurrent == 3.0

    sensor_sources = next(file.content for file in sensor.files if file.path == "references/sources.md")
    pump_sources = next(file.content for file in pump.files if file.path == "references/sources.md")
    assert "https://wiki.dfrobot.com/sen0193/" in sensor_sources
    assert "6fc3c4f7b67067b249326f4b19669ba65364090c1acb21430d6f941d57979f84" in sensor_sources
    assert "https://wiki.dfrobot.com/dfr0523/" in pump_sources
    assert "0f5ee34e455155d1ce8841af228cf07dec2ab04655c9df4d46c9ee03a9741db2" in pump_sources


def test_pump_without_independent_power_fails_and_full_watering_kit_passes(
    tmp_path: Path,
) -> None:
    skills = _skills(tmp_path)
    without_power = skills.validate_component_ids(
        ["hw_seed_unihiker_k10", "hw_dfrobot_sen0193", "hw_dfrobot_dfr0523"]
    )
    assert without_power.overall == ValidationSeverity.FAIL
    assert any(
        check.severity == ValidationSeverity.FAIL
        and "不得由 K10 或 GPIO 供电" in check.message
        for check in without_power.checks
    )

    full_kit = skills.validate_component_ids(
        [
            "hw_seed_unihiker_k10",
            "hw_dfrobot_sen0193",
            "hw_dfrobot_dfr0523",
            "hw_power_5v_3a_regulated",
        ]
    )
    assert full_kit.overall == ValidationSeverity.PASS
    assert any(check.dimension == "watering_sensor_adc" for check in full_kit.checks)
    assert any(check.dimension == "watering_pump_control" for check in full_kit.checks)


def test_minimum_official_catalog_replaces_retired_demo_oled_and_button_seeds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ZHANGWEN_TEST_PRESERVE_RETIRED_HARDWARE", raising=False)
    skills = _skills(tmp_path)
    ultrasonic = skills.get_skill("sen0388")
    oled = skills.get_skill("dfr0486")
    button = skills.get_skill("dfr0029-button")

    assert ultrasonic.verificationStatus == "OFFICIAL_DOC_VERIFIED"
    assert ultrasonic.specification.electrical.voltageMax == 5.5
    assert oled.verificationStatus == "OFFICIAL_DOC_VERIFIED"
    assert oled.specification.electrical.i2cAddress == "0x3C"
    assert button.verificationStatus == "OFFICIAL_DOC_VERIFIED"
    assert button.specification.electrical.communicationProtocol == "GPIO_DIGITAL"

    sources = {
        skill.skillName: next(
            file.content for file in skill.files if file.path == "references/sources.md"
        )
        for skill in (ultrasonic, oled, button)
    }
    assert "https://wiki.dfrobot.com/sen0388/" in sources["sen0388"]
    assert "https://wiki.dfrobot.com/dfr0486/" in sources["dfr0486"]
    assert "https://wiki.dfrobot.com/dfr0029-b/" in sources["dfr0029-button"]

    active_ids = {item.componentId for item in skills.list_skills()}
    assert "hw_seed_oled_096" not in active_ids
    assert "hw_seed_button_module" not in active_ids
    assert {
        "hw_dfrobot_sen0388",
        "hw_dfrobot_dfr0486",
        "hw_dfrobot_dfr0029_button",
    }.issubset(active_ids)

    for component_id in (
        "hw_dfrobot_sen0388",
        "hw_dfrobot_dfr0486",
        "hw_dfrobot_dfr0029_button",
    ):
        report = skills.validate_component_ids(
            ["hw_seed_unihiker_k10", component_id]
        )
        assert report.overall != ValidationSeverity.FAIL
