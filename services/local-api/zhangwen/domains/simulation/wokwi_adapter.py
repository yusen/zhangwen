"""One-way Wokwi diagram.json compatibility import into Zhangwen schemas."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from zhangwen.domains.simulation.models import (
    CircuitBoardInstance,
    CircuitDraftV1,
    CircuitEndpoint,
    CircuitNet,
    CircuitPartInstance,
    CircuitSourceCompatibility,
)


MAX_WOKWI_IMPORT_BYTES = 512 * 1024
WOKWI_ADAPTER_REVISION = "zhangwen-wokwi-import@1"

_BOARD_TYPES = {
    "board-xiao-esp32-s3": "board/esp32s3-reference@1",
    "board-esp32-s3-devkitc-1": "board/esp32s3-reference@1",
    "wokwi-esp32-s3-devkitc-1": "board/esp32s3-reference@1",
    "board-esp32-c3-devkitm-1": "board/esp32c3-reference@1",
    "wokwi-esp32-c3-devkitm-1": "board/esp32c3-reference@1",
}
_COMPONENT_TYPES = {
    "wokwi-led": "component/led@1",
    "wokwi-resistor": "component/resistor@1",
    "wokwi-pushbutton": "component/button@1",
    "wokwi-potentiometer": "component/potentiometer@1",
    "wokwi-dht22": "component/dht22@1",
    "board-ssd1306": "component/ssd1306@1",
    "wokwi-ssd1306": "component/ssd1306@1",
    "wokwi-neopixel": "component/neopixel@1",
    "wokwi-buzzer": "component/buzzer@1",
    "wokwi-servo": "component/servo@1",
}
_XIAO_PIN_MAP = {
    **{f"D{index}": f"GPIO{gpio}" for index, gpio in enumerate((1, 2, 3, 4, 5, 6, 43, 44, 7, 8, 9))},
    "3V3": "3V3",
    "5V": "5V",
    "GND": "GND",
}
_COMPONENT_PIN_MAP = {
    "wokwi-pushbutton": {"1.l": "1", "1.r": "1", "2.l": "2", "2.r": "2"},
    "wokwi-dht22": {"SDA": "DATA"},
    "wokwi-buzzer": {"1": "SIG", "2": "GND"},
    "wokwi-servo": {"V+": "VCC", "PWM": "SIG"},
}


class WokwiImportError(ValueError):
    pass


@dataclass(frozen=True)
class ImportedWokwiCircuit:
    board_package_revision_id: str
    circuit: CircuitDraftV1


def import_wokwi_diagram(diagram_json: str) -> ImportedWokwiCircuit:
    encoded = diagram_json.encode("utf-8")
    if len(encoded) > MAX_WOKWI_IMPORT_BYTES:
        raise WokwiImportError("diagram.json 超过 512 KiB 导入上限。")
    try:
        payload = json.loads(diagram_json, object_pairs_hook=_reject_duplicate_keys)
    except (json.JSONDecodeError, ValueError) as exc:
        raise WokwiImportError("diagram.json 不是无重复字段的有效 JSON。") from exc
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise WokwiImportError("只支持 Wokwi diagram.json version 1。")
    if payload.get("dependencies") not in (None, {}):
        raise WokwiImportError("自定义 Wokwi 芯片依赖不能进入掌问受信任仿真。")
    raw_parts = payload.get("parts")
    raw_connections = payload.get("connections", [])
    if not isinstance(raw_parts, list) or not isinstance(raw_connections, list):
        raise WokwiImportError("diagram.json 的 parts/connections 必须是数组。")

    parsed_parts = [_part(item) for item in raw_parts]
    boards = [item for item in parsed_parts if item["type"] in _BOARD_TYPES]
    if len(boards) != 1:
        raise WokwiImportError("兼容导入必须且只能识别一个 ESP32-S3/C3 板型。")
    board = boards[0]
    board_revision = _BOARD_TYPES[str(board["type"])]
    unknown_types: set[str] = set()
    parts: list[CircuitPartInstance] = []
    types_by_id = {str(item["id"]): str(item["type"]) for item in parsed_parts}
    for item in parsed_parts:
        part_type = str(item["type"])
        if item is board:
            continue
        component_revision = _COMPONENT_TYPES.get(part_type)
        read_only = component_revision is None
        if component_revision is None:
            unknown_types.add(part_type)
            slug = hashlib.sha256(part_type.encode("utf-8")).hexdigest()[:16]
            component_revision = f"compat/wokwi-unknown-{slug}@1"
        properties = dict(item["attrs"])
        if read_only:
            properties["wokwiType"] = part_type
        parts.append(
            CircuitPartInstance(
                id=str(item["id"]),
                componentPackageRevisionId=component_revision,
                position={"x": float(item["left"]), "y": float(item["top"])},
                rotation=_rotation(item["rotate"]),
                properties=properties,
                readOnly=read_only,
            )
        )

    pairs: list[tuple[tuple[str, str], tuple[str, str], str]] = []
    for raw in raw_connections:
        source, target, color = _connection(raw)
        pairs.append(
            (
                _map_endpoint(source, board, types_by_id),
                _map_endpoint(target, board, types_by_id),
                color,
            )
        )
    nets = _merge_pairs(pairs)
    source_digest = hashlib.sha256(encoded).hexdigest()
    circuit = CircuitDraftV1(
        boardInstance=CircuitBoardInstance(
            id="board",
            boardPackageRevisionId=board_revision,
            position={"x": float(board["left"]), "y": float(board["top"])},
            rotation=_rotation(board["rotate"]),
        ),
        parts=parts,
        nets=nets,
        sourceCompatibility=CircuitSourceCompatibility(
            sourceDigest=source_digest,
            adapterRevision=WOKWI_ADAPTER_REVISION,
            unknownPartTypes=sorted(unknown_types),
        ),
    )
    return ImportedWokwiCircuit(
        board_package_revision_id=board_revision, circuit=circuit
    )


def _part(raw: object) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise WokwiImportError("Wokwi 器件必须是对象。")
    if set(raw) - {"id", "type", "top", "left", "rotate", "attrs"}:
        raise WokwiImportError("Wokwi 器件包含未允许字段。")
    part_id = raw.get("id")
    part_type = raw.get("type")
    attrs = raw.get("attrs", {})
    if (
        not isinstance(part_id, str)
        or not isinstance(part_type, str)
        or not isinstance(attrs, dict)
        or any(not isinstance(key, str) or not isinstance(value, str) for key, value in attrs.items())
    ):
        raise WokwiImportError("Wokwi 器件字段类型无效。")
    try:
        top = float(raw.get("top", 0))
        left = float(raw.get("left", 0))
        rotate = int(raw.get("rotate", 0))
    except (TypeError, ValueError) as exc:
        raise WokwiImportError("Wokwi 器件位置或旋转无效。") from exc
    return {
        "id": part_id,
        "type": part_type,
        "top": top,
        "left": left,
        "rotate": rotate,
        "attrs": attrs,
    }


def _connection(raw: object) -> tuple[tuple[str, str], tuple[str, str], str]:
    if not isinstance(raw, list) or not 2 <= len(raw) <= 4:
        raise WokwiImportError("Wokwi 连线格式无效。")
    source = _split_endpoint(raw[0])
    target = _split_endpoint(raw[1])
    color = raw[2] if len(raw) >= 3 else "#0f766e"
    if not isinstance(color, str):
        raise WokwiImportError("Wokwi 连线颜色无效。")
    return source, target, _color(color)


def _split_endpoint(raw: object) -> tuple[str, str]:
    if not isinstance(raw, str) or ":" not in raw:
        raise WokwiImportError("Wokwi 连线端点无效。")
    return tuple(raw.split(":", 1))  # type: ignore[return-value]


def _map_endpoint(
    endpoint: tuple[str, str],
    board: dict[str, object],
    types_by_id: dict[str, str],
) -> tuple[str, str]:
    instance_id, pin_id = endpoint
    part_type = types_by_id.get(instance_id)
    if part_type is None:
        raise WokwiImportError(f"连线引用了不存在的器件 {instance_id}。")
    if instance_id == board["id"]:
        if board["type"] == "board-xiao-esp32-s3":
            return "board", _XIAO_PIN_MAP.get(pin_id, pin_id.removeprefix("GPIO"))
        return "board", _generic_board_pin(pin_id)
    return instance_id, _COMPONENT_PIN_MAP.get(part_type, {}).get(pin_id, pin_id)


def _generic_board_pin(pin_id: str) -> str:
    if pin_id in {"3V3", "5V", "GND"}:
        return pin_id
    clean = pin_id.removeprefix("GPIO").removeprefix("IO")
    return f"GPIO{clean}" if clean.isdigit() else pin_id


def _merge_pairs(
    pairs: list[tuple[tuple[str, str], tuple[str, str], str]]
) -> list[CircuitNet]:
    parent: dict[tuple[str, str], tuple[str, str]] = {}
    colors: dict[tuple[str, str], str] = {}

    def find(item: tuple[str, str]) -> tuple[str, str]:
        parent.setdefault(item, item)
        if parent[item] != item:
            parent[item] = find(parent[item])
        return parent[item]

    def union(left: tuple[str, str], right: tuple[str, str], color: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root
        colors.setdefault(left_root, color)

    for source, target, color in pairs:
        union(source, target, color)
    groups: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for endpoint in parent:
        groups.setdefault(find(endpoint), set()).add(endpoint)
    result: list[CircuitNet] = []
    for index, (root, endpoints) in enumerate(
        sorted(groups.items(), key=lambda item: sorted(item[1])), start=1
    ):
        result.append(
            CircuitNet(
                id=f"imported-net-{index}",
                endpoints=[
                    CircuitEndpoint(instanceId=instance_id, pinId=pin_id)
                    for instance_id, pin_id in sorted(endpoints)
                ],
                signalKind="UNSPECIFIED",
                label=f"导入连线 {index}",
                color=colors.get(root, "#0f766e"),
            )
        )
    return result


def _rotation(raw: object) -> int:
    value = int(raw) % 360
    return value if value in {0, 90, 180, 270} else 0


def _color(value: str) -> str:
    named = {
        "black": "#334155",
        "red": "#dc2626",
        "green": "#0f766e",
        "blue": "#2563eb",
        "orange": "#ea580c",
        "purple": "#7e22ce",
        "yellow": "#ca8a04",
    }
    if value.casefold() in named:
        return named[value.casefold()]
    if len(value) == 7 and value.startswith("#"):
        return value
    return "#0f766e"


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key: {key}")
        result[key] = value
    return result
