"""Tests for ZW-005 hardware component CRUD and migration."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from zhangwen.hardware.models import (
    ElectricalProps,
    HardwareCategory,
    HardwareComponentStatus,
)
from zhangwen.hardware.repository import HardwareRepository
from zhangwen.projects.migrations import CURRENT_SCHEMA_VERSION, migrate


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test.sqlite3"
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    migrate(conn)
    conn.close()
    return path


@pytest.fixture
def repo(db_path):
    return HardwareRepository(db_path)


def _sample_electrical(**overrides):
    defaults = {
        "voltage": 3.3,
        "logicLevel": 3.3,
        "peakCurrent": 0.5,
        "communicationProtocol": "GPIO",
        "i2cAddress": None,
        "supportedMCUs": ["esp32-s3"],
        "driverName": None,
        "firmwareRequirement": None,
    }
    defaults.update(overrides)
    return ElectricalProps(**defaults)


# ── Migration tests ──


class TestMigrationV3:
    def test_migration_creates_hardware_table(self, db_path):
        conn = sqlite3.connect(db_path)
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == CURRENT_SCHEMA_VERSION
        assert CURRENT_SCHEMA_VERSION == 31

        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        assert "hardware_components" in tables
        conn.close()

    def test_migration_idempotent(self, db_path):
        # Running migrate again should not fail
        conn = sqlite3.connect(db_path)
        migrate(conn)
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == CURRENT_SCHEMA_VERSION
        conn.close()


# ── CRUD tests ──


class TestHardwareCRUD:
    def test_create_component(self, repo):
        comp = repo.create_component(
            name="ESP32-S3",
            category=HardwareCategory.MCU.value,
            electrical=_sample_electrical(),
            stock=5,
            price=25.0,
            notes="主控制器",
        )
        assert comp.id.startswith("hw_")
        assert comp.name == "ESP32-S3"
        assert comp.category == HardwareCategory.MCU
        assert comp.status == HardwareComponentStatus.ACTIVE
        assert comp.stock == 5
        assert comp.price == 25.0
        assert comp.electrical.voltage == 3.3

    def test_list_components_empty(self, repo):
        assert repo.list_components() == []

    def test_list_components_after_create(self, repo):
        repo.create_component(
            name="状态灯",
            category=HardwareCategory.ACTUATOR.value,
            electrical=_sample_electrical(),
        )
        repo.create_component(
            name="DHT11",
            category=HardwareCategory.SENSOR.value,
            electrical=_sample_electrical(voltage=5.0),
        )
        comps = repo.list_components()
        assert len(comps) == 2

    def test_list_components_filter_by_category(self, repo):
        repo.create_component(
            name="状态灯",
            category=HardwareCategory.ACTUATOR.value,
            electrical=_sample_electrical(),
        )
        repo.create_component(
            name="DHT11",
            category=HardwareCategory.SENSOR.value,
            electrical=_sample_electrical(voltage=5.0),
        )
        actuators = repo.list_components(category=HardwareCategory.ACTUATOR.value)
        assert len(actuators) == 1
        assert actuators[0].name == "状态灯"

    def test_list_components_search(self, repo):
        repo.create_component(
            name="AlphaUnique 传感器",
            category=HardwareCategory.SENSOR.value,
            electrical=_sample_electrical(),
        )
        repo.create_component(
            name="Beta 传感器",
            category=HardwareCategory.SENSOR.value,
            electrical=_sample_electrical(),
        )
        results = repo.list_components(search="AlphaUnique")
        assert len(results) == 1
        assert results[0].name == "AlphaUnique 传感器"

    def test_list_components_searches_shared_knowledge_details(self, repo):
        repo.create_component(
            name="环境传感模块",
            category=HardwareCategory.SENSOR.value,
            electrical=_sample_electrical(
                communicationProtocol="I2C",
                i2cAddress="0x76",
                driverName="bme280",
            ),
            safety_tags=["防反接"],
            notes="外壳需要保留通风孔",
        )

        assert [item.name for item in repo.list_components(search="通风孔")] == [
            "环境传感模块"
        ]
        assert [item.name for item in repo.list_components(search="0x76")] == [
            "环境传感模块"
        ]
        assert [item.name for item in repo.list_components(search="防反接")] == [
            "环境传感模块"
        ]

    def test_get_component(self, repo):
        created = repo.create_component(
            name="DHT11",
            category=HardwareCategory.SENSOR.value,
            electrical=_sample_electrical(),
        )
        fetched = repo.get_component(created.id)
        assert fetched.id == created.id
        assert fetched.name == "DHT11"

    def test_get_component_not_found(self, repo):
        with pytest.raises(ValueError, match="硬件组件不存在"):
            repo.get_component("hw_nonexistent")

    def test_update_component(self, repo):
        comp = repo.create_component(
            name="DHT11",
            category=HardwareCategory.SENSOR.value,
            electrical=_sample_electrical(),
            stock=5,
        )
        updated = repo.update_component(
            comp.id,
            name="DHT11 校准版",
            stock=10,
        )
        assert updated.name == "DHT11 校准版"
        assert updated.stock == 10
        assert updated.category == HardwareCategory.SENSOR

    def test_archive_component(self, repo):
        comp = repo.create_component(
            name="DHT11",
            category=HardwareCategory.SENSOR.value,
            electrical=_sample_electrical(),
        )
        archived = repo.archive_component(comp.id)
        assert archived.status == HardwareComponentStatus.ARCHIVED

        # Default list excludes archived
        active = repo.list_components()
        assert len(active) == 0

        # Include archived
        all_comps = repo.list_components(include_archived=True)
        assert len(all_comps) == 1

    def test_create_component_with_safety_tags(self, repo):
        comp = repo.create_component(
            name="SG90 舵机",
            category=HardwareCategory.ACTUATOR.value,
            electrical=_sample_electrical(voltage=5.0, peakCurrent=1.0),
            safety_tags=["需要外部供电", "堵转保护"],
        )
        assert comp.safetyTags == ["需要外部供电", "堵转保护"]

    def test_update_component_no_changes(self, repo):
        comp = repo.create_component(
            name="ESP32-S3",
            category=HardwareCategory.MCU.value,
            electrical=_sample_electrical(),
        )
        updated = repo.update_component(comp.id)
        assert updated.name == comp.name
        assert updated.category == comp.category
