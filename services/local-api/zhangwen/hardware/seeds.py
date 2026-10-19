"""Built-in hardware seed data for the local hardware library."""

from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from zhangwen.hardware.models import (
    HardwareComponentStatus,
    HardwareSkillSpecification,
)


RETIRED_DEFAULT_COMPONENT_IDS: tuple[str, ...] = (
    "hw_seed_esp32_s3_devkit",
    "hw_seed_dht22",
    "hw_seed_bme280",
    "hw_seed_oled_096",
    "hw_seed_sg90_servo",
    "hw_seed_led_module",
    "hw_seed_button_module",
    "hw_seed_buzzer",
    "hw_seed_relay_5v",
    "hw_seed_mosfet_driver",
    "hw_seed_usb_5v_power",
    "hw_seed_breadboard",
)


def seed_default_components(db_path) -> None:
    now = datetime.now(UTC).isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        if os.getenv("ZHANGWEN_TEST_PRESERVE_RETIRED_HARDWARE") != "1":
            placeholders = ",".join("?" for _ in RETIRED_DEFAULT_COMPONENT_IDS)
            conn.execute(
                f"DELETE FROM hardware_components WHERE id IN ({placeholders})",
                RETIRED_DEFAULT_COMPONENT_IDS,
            )
        for item in _default_components(now):
            conn.execute(
                """
                INSERT OR IGNORE INTO hardware_components (
                    id, name, category, status, electrical_json,
                    stock, price, age_recommendation, safety_tags_json,
                    notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["id"],
                    item["name"],
                    item["category"],
                    HardwareComponentStatus.ACTIVE.value,
                    json.dumps(item["electrical"], ensure_ascii=False),
                    item["stock"],
                    item["price"],
                    item["age_recommendation"],
                    json.dumps(item["safety_tags"], ensure_ascii=False),
                    item["notes"],
                    now,
                    now,
                ),
            )


def _default_components(now: str) -> list[dict]:
    specifications = (_bundled_k10_specification(), _bundled_xiao_specification())
    return [
        {
            "id": specification.componentId,
            "name": specification.name,
            "category": specification.category.value,
            "electrical": specification.electrical.model_dump(mode="json"),
            "stock": specification.stock,
            "price": specification.price,
            "age_recommendation": specification.ageRecommendation,
            "safety_tags": list(specification.safetyTags),
            "notes": specification.notes,
            "created_at": now,
        }
        for specification in specifications
    ]


@lru_cache(maxsize=1)
def _bundled_k10_specification() -> HardwareSkillSpecification:
    path = (
        Path(__file__).with_name("bundled-hardware-skills")
        / "k10"
        / "references"
        / "specifications.md"
    )
    content = path.read_text(encoding="utf-8")
    match = re.search(
        r"```zhangwen:hardware-spec:v1[ \t]*\r?\n(.*?)\r?\n```",
        content,
        re.DOTALL,
    )
    if match is None:
        raise RuntimeError("内置 K10 Hardware Skill 缺少结构化电气参数。")
    return HardwareSkillSpecification(**json.loads(match.group(1)))


@lru_cache(maxsize=1)
def _bundled_xiao_specification() -> HardwareSkillSpecification:
    return HardwareSkillSpecification.model_validate(
        {
            "schema": "zhangwen.hardware-skill/v1",
            "componentId": "hw_seeed_xiao_esp32s3_sense",
            "name": "Seeed Studio XIAO ESP32S3 Sense",
            "category": "MCU",
            "electrical": {
                "voltage": 5.0,
                "voltageMin": 5.0,
                "voltageMax": 5.0,
                "supplyVoltages": [3.3, 5.0],
                "logicLevel": 3.3,
                "peakCurrent": 0.0,
                "communicationProtocol": "GPIO/I2C/SPI/PDM/USB/Wi-Fi/Bluetooth LE",
                "i2cAddress": None,
                "supportedMCUs": [
                    "seeedstudio/xiao_esp32s3_sense",
                    "xiao-esp32s3-sense",
                ],
                "driverName": "xiao_esp32s3_sense",
                "firmwareRequirement": "XIAO ESP32S3 Sense exact-board MicroPython or verified application package",
            },
            "stock": 0,
            "price": 0.0,
            "ageRecommendation": 8,
            "safetyTags": [
                "USB 5V供电",
                "3.3V逻辑",
                "GPIO21与microSD片选冲突",
                "执行器需独立供电",
            ],
            "notes": (
                "规范板型 seeedstudio/xiao_esp32s3_sense；8 MB Flash、8 MB OPI PSRAM，"
                "Sense 扩展含 OV2640、PDM 麦克风和 SPI microSD。peakCurrent=0 表示未固化"
                "整板峰值，并非实际电流为零。"
            ),
            "verificationStatus": "OFFICIAL_DOC_VERIFIED",
            "sourceIds": [
                "https://github.com/espressif/esp-claw/tree/master/application/edge_agent/boards/seeedstudio/xiao_esp32s3_sense",
                "https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/",
            ],
        }
    )
