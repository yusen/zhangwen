"""Explicit legacy component fixtures for tests that exercise multi-part rules.

These records are intentionally outside the production default catalog.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


_COMPONENTS: dict[str, dict[str, object]] = {
    "hw_seed_esp32_s3_devkit": {
        "name": "ESP32-S3 DevKitC",
        "category": "MCU",
        "electrical": {
            "voltage": 3.3,
            "logicLevel": 3.3,
            "peakCurrent": 0.5,
            "communicationProtocol": "GPIO",
            "i2cAddress": None,
            "supportedMCUs": ["esp32", "esp32-s3", "ESP32-S3 DevKitC"],
            "driverName": None,
            "firmwareRequirement": None,
        },
        "stock": 6, "price": 42.0, "age": 10,
        "safety": ["USB供电"], "notes": "内置 ESP32-S3 主控开发板。",
    },
    "hw_seed_dht22": {
        "name": "DHT22 温湿度传感器",
        "category": "SENSOR",
        "electrical": {
            "voltage": 3.3,
            "logicLevel": 3.3,
            "peakCurrent": 0.0025,
            "communicationProtocol": "GPIO",
            "i2cAddress": None,
            "supportedMCUs": ["esp32", "esp32-s3", "ESP32-S3 DevKitC"],
            "driverName": "dht",
            "firmwareRequirement": None,
        },
        "stock": 10, "price": 18.0, "age": 9,
        "safety": [], "notes": "单总线温湿度传感器。",
    },
    "hw_seed_bme280": {
        "name": "BME280 环境传感器",
        "category": "SENSOR",
        "electrical": {
            "voltage": 3.3,
            "logicLevel": 3.3,
            "peakCurrent": 0.001,
            "communicationProtocol": "I2C",
            "i2cAddress": "0x76",
            "supportedMCUs": ["esp32", "esp32-s3", "ESP32-S3 DevKitC"],
            "driverName": "bme280",
            "firmwareRequirement": None,
        },
        "stock": 8, "price": 26.0, "age": 10,
        "safety": [], "notes": "I2C 温湿度气压传感器。",
    },
    "hw_seed_relay_5v": {
        "name": "5V 继电器模块",
        "category": "ACTUATOR",
        "electrical": {
            "voltage": 5.0,
            "logicLevel": 5.0,
            "peakCurrent": 0.08,
            "communicationProtocol": "GPIO",
            "i2cAddress": None,
            "supportedMCUs": ["esp32", "esp32-s3", "ESP32-S3 DevKitC"],
            "driverName": None,
            "firmwareRequirement": None,
        },
        "stock": 6, "price": 8.0, "age": 14,
        "safety": ["高压隔离", "教师监督"],
        "notes": "5V 逻辑继电器模块，ESP32 直连需电平转换或驱动。",
    },
    "hw_seed_oled_096": {
        "name": "0.96 OLED 显示屏", "category": "DISPLAY",
        "electrical": {
            "voltage": 3.3, "logicLevel": 3.3, "peakCurrent": 0.02,
            "communicationProtocol": "I2C", "i2cAddress": "0x3c",
            "supportedMCUs": ["esp32", "esp32-s3", "ESP32-S3 DevKitC"],
            "driverName": "ssd1306", "firmwareRequirement": None,
        },
        "stock": 12, "price": 16.0, "age": 9,
        "safety": [], "notes": "SSD1306 I2C 小尺寸显示屏。",
    },
    "hw_seed_button_module": {
        "name": "按钮模块", "category": "SENSOR",
        "electrical": {
            "voltage": 3.3, "logicLevel": 3.3, "peakCurrent": 0.001,
            "communicationProtocol": "GPIO", "i2cAddress": None,
            "supportedMCUs": ["esp32", "esp32-s3", "ESP32-S3 DevKitC"],
            "driverName": None, "firmwareRequirement": None,
        },
        "stock": 20, "price": 2.0, "age": 8,
        "safety": [], "notes": "基础数字输入模块。",
    },
    "hw_seed_mosfet_driver": {
        "name": "MOSFET 驱动模块", "category": "ACTUATOR",
        "electrical": {
            "voltage": 3.3, "logicLevel": 3.3, "peakCurrent": 0.02,
            "communicationProtocol": "PWM", "i2cAddress": None,
            "supportedMCUs": ["esp32", "esp32-s3", "ESP32-S3 DevKitC"],
            "driverName": None, "firmwareRequirement": None,
        },
        "stock": 8, "price": 9.0, "age": 12,
        "safety": ["外部负载供电"], "notes": "用于控制 LED 灯带或直流负载。",
    },
    "hw_seed_usb_5v_power": {
        "name": "USB 5V 2A 供电模块", "category": "POWER",
        "electrical": {
            "voltage": 5.0, "logicLevel": 5.0, "peakCurrent": 2.0,
            "communicationProtocol": "POWER", "i2cAddress": None,
            "supportedMCUs": [], "driverName": None, "firmwareRequirement": None,
        },
        "stock": 8, "price": 10.0, "age": 10,
        "safety": ["低压供电"], "notes": "为外设提供 5V 电源，总电流按 2A 估算。",
    },
    "hw_seed_breadboard": {
        "name": "面包板与杜邦线套件", "category": "STRUCTURE",
        "electrical": {
            "voltage": 0.0, "logicLevel": 0.0, "peakCurrent": 0.0,
            "communicationProtocol": "NONE", "i2cAddress": None,
            "supportedMCUs": [], "driverName": None, "firmwareRequirement": None,
        },
        "stock": 20, "price": 15.0, "age": 8,
        "safety": [], "notes": "原型搭建结构件。",
    },
}


def seed_legacy_test_components(
    db_path: Path,
    component_ids: tuple[str, ...] | None = None,
) -> None:
    now = datetime.now(UTC).isoformat()
    ids = component_ids or tuple(_COMPONENTS)
    with sqlite3.connect(db_path) as conn:
        for component_id in ids:
            item = _COMPONENTS[component_id]
            conn.execute(
                """
                INSERT OR IGNORE INTO hardware_components (
                  id, name, category, status, electrical_json, stock, price,
                  age_recommendation, safety_tags_json, notes, created_at, updated_at
                ) VALUES (?, ?, ?, 'ACTIVE', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    component_id, item["name"], item["category"],
                    json.dumps(item["electrical"], ensure_ascii=False),
                    item["stock"], item["price"], item["age"],
                    json.dumps(item["safety"], ensure_ascii=False),
                    item["notes"], now, now,
                ),
            )
