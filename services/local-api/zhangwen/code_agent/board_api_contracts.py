"""Deterministic board API contracts used by generation and static validation."""

from __future__ import annotations

import ast
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from zhangwen.specs.models import SpecRun


MPYTHON_ESP32S3_V3_CONTRACT_ID = "mpython-esp32s3-v3"
UNIHIKER_K10_CONTRACT_ID = "unihiker-k10-micropython"


class BoardContractCodeFile(Protocol):
    path: str
    language: str
    content: str


@dataclass(frozen=True)
class ApiCallable:
    minimum_positional: int
    maximum_positional: int
    keywords: tuple[str, ...] = ()

    def prompt_payload(self) -> dict[str, object]:
        return {
            "minimumPositional": self.minimum_positional,
            "maximumPositional": self.maximum_positional,
            "keywords": list(self.keywords),
        }


@dataclass(frozen=True)
class ApiObject:
    callables: dict[str, ApiCallable]
    attributes: tuple[str, ...] = ()
    members_complete: bool = True

    @property
    def members(self) -> frozenset[str]:
        return frozenset((*self.callables, *self.attributes))

    def prompt_payload(self) -> dict[str, object]:
        return {
            "callables": {
                name: contract.prompt_payload()
                for name, contract in sorted(self.callables.items())
            },
            "attributes": sorted(self.attributes),
            "membersComplete": self.members_complete,
        }


@dataclass(frozen=True)
class BoardApiContract:
    id: str
    display_name: str
    component_ids: tuple[str, ...]
    firmware_family: str
    module: str
    source_url: str
    verification: str
    objects: dict[str, ApiObject]
    additional_exports: tuple[str, ...]
    forbidden_roots: dict[str, str]
    module_exports: dict[str, tuple[str, ...]] = field(default_factory=dict)
    constructors: dict[str, ApiCallable] = field(default_factory=dict)
    forbidden_modules: dict[str, str] = field(default_factory=dict)
    member_replacements: dict[tuple[str, str], str] = field(default_factory=dict)
    export_guidance: dict[str, str] = field(default_factory=dict)
    rules: tuple[str, ...] = ()

    @property
    def exports(self) -> frozenset[str]:
        return frozenset((*self.objects, *self.additional_exports))

    @property
    def modules(self) -> frozenset[str]:
        if self.module_exports:
            return frozenset(self.module_exports)
        return frozenset((self.module,))

    def exports_for_module(self, module: str) -> frozenset[str]:
        if self.module_exports:
            return frozenset(self.module_exports.get(module, ()))
        return self.exports if module == self.module else frozenset()

    def prompt_payload(self) -> dict[str, object]:
        return {
            "contractId": self.id,
            "board": self.display_name,
            "firmwareFamily": self.firmware_family,
            "requiredImportModule": self.module,
            "modules": {
                module: sorted(self.exports_for_module(module))
                for module in sorted(self.modules)
            },
            "source": self.source_url,
            "verification": self.verification,
            "objects": {
                name: contract.prompt_payload()
                for name, contract in sorted(self.objects.items())
            },
            "additionalExports": sorted(self.additional_exports),
            "constructors": {
                name: contract.prompt_payload()
                for name, contract in sorted(self.constructors.items())
            },
            "rules": list(self.rules),
        }


def _call(
    minimum: int,
    maximum: int | None = None,
    *keywords: str,
) -> ApiCallable:
    return ApiCallable(minimum, minimum if maximum is None else maximum, keywords)


_DISPLAY_CALLABLES = {
    "DispChar": _call(3, 5, "str", "x", "y", "color", "auto_wrap"),
    "DispChar_font": _call(
        4,
        6,
        "font",
        "str",
        "x",
        "y",
        "color",
        "auto_wrap",
    ),
    "RoundRect": _call(6),
    "background_color": _call(0, 1, "color"),
    "blit": _call(3, 5, "fb", "x", "y", "key", "palette"),
    "circle": _call(4),
    "clear": _call(0, 1, "color"),
    "decode_png_internal": _call(1),
    "ellipse": _call(6),
    "fill": _call(1),
    "fill_circle": _call(4),
    "fill_rect": _call(5),
    "fill_triangle": _call(7),
    "hline": _call(4),
    "line": _call(5),
    "pixel": _call(2, 3, "color"),
    "quarter_circle": _call(5),
    "rect": _call(5),
    "round_rect": _call(6),
    "show": _call(0),
    "text": _call(4),
    "triangle": _call(7),
    "vline": _call(4),
}

_BUTTON_CALLABLES = {
    "get_presses": _call(0),
    "irq": _call(0, 5, "handler", "trigger", "priority", "wake"),
    "is_pressed": _call(0),
    "value": _call(0),
    "was_pressed": _call(0),
}

_TOUCH_CALLABLES = {
    "config": _call(1, 1, "threshold"),
    "get_presses": _call(0),
    "is_pressed": _call(0),
    "read": _call(0),
    "was_pressed": _call(0),
}

_LCD_COLORS = (
    "BLACK",
    "BLUE",
    "CYAN",
    "GREEN",
    "MAGENTA",
    "ORANGE",
    "RED",
    "WHITE",
    "YELLOW",
)

MPYTHON_ESP32S3_V3_CONTRACT = BoardApiContract(
    id=MPYTHON_ESP32S3_V3_CONTRACT_ID,
    display_name="掌控板 3.0（ESP32-S3）",
    component_ids=("hw_labplus_mpython_esp32s3_v3",),
    firmware_family="掌控板 3.0 官方 MicroPython 固件",
    module="mpython",
    source_url=(
        "https://mpython-esp32s3-doc.readthedocs.io/zh-cn/latest/"
        "5_api/library/mPython/mpython.html"
    ),
    verification="OFFICIAL_DOCUMENTATION_REVIEWED; DEVICE_SMOKE_PENDING",
    objects={
        "accelerometer": ApiObject(
            {
                "get_x": _call(0),
                "get_y": _call(0),
                "get_z": _call(0),
                "roll_pitch_angle": _call(0),
                "set_offset": _call(0, 3, "x", "y", "z"),
                "set_range": _call(1),
                "set_resolution": _call(1),
            }
        ),
        "button_a": ApiObject(
            _BUTTON_CALLABLES,
            ("event_pressed", "event_released"),
        ),
        "button_b": ApiObject(
            _BUTTON_CALLABLES,
            ("event_pressed", "event_released"),
        ),
        "display": ApiObject(_DISPLAY_CALLABLES),
        "gyroscope": ApiObject(
            {
                "get_x": _call(0),
                "get_y": _call(0),
                "get_z": _call(0),
                "set_offset": _call(0, 3, "x", "y", "z"),
                "set_range": _call(1),
            }
        ),
        "i2c": ApiObject({}, members_complete=False),
        "lcd": ApiObject({}, _LCD_COLORS, members_complete=False),
        "light": ApiObject({"read": _call(0)}),
        "magnetic": ApiObject(
            {
                "calibrate": _call(0),
                "clear_peeling": _call(0),
                "get_field_strength": _call(0),
                "get_heading": _call(0),
                "get_x": _call(0),
                "get_y": _call(0),
                "get_z": _call(0),
                "peeling": _call(0),
            }
        ),
        "rgb": ApiObject(
            {
                "brightness": _call(1, 1, "brightness"),
                "fill": _call(1, 1, "rgb_buf"),
                "write": _call(0),
            }
        ),
        "sound": ApiObject({"read": _call(0)}),
        **{
            name: ApiObject(
                _TOUCH_CALLABLES,
                ("event_pressed", "event_released"),
            )
            for name in (
                "touchpad_h",
                "touchpad_n",
                "touchpad_o",
                "touchpad_p",
                "touchpad_t",
                "touchpad_y",
            )
        },
    },
    additional_exports=(
        "MPythonPin",
        "Pin",
        "PinMode",
        "numberMap",
        "sleep",
        "sleep_ms",
    ),
    forbidden_roots={
        "oled": "掌控板 3.0 使用彩色 display 对象，不使用旧版 oled 对象。",
    },
    member_replacements={
        ("button_a", "pressed"): "；请改用 button_a.is_pressed()。",
        ("button_b", "pressed"): "；请改用 button_b.is_pressed()。",
        ("rgb", "show"): "；请改用 rgb.write()。",
    },
    export_guidance={
        color: "颜色应使用 lcd.<COLOR>。"
        for color in _LCD_COLORS
    },
    rules=(
        "板载 API 不在此契约中时视为不存在，不得使用旧版或其他开发板写法。",
        "显示颜色使用 lcd.<COLOR>；RGB 修改后使用 rgb.write()，不存在 rgb.show()。",
        "按键状态使用 button_a/button_b.is_pressed()，不存在 pressed()。",
    ),
)

UNIHIKER_K10_CONTRACT = BoardApiContract(
    id=UNIHIKER_K10_CONTRACT_ID,
    display_name="行空板 K10（UNIHIKER K10）",
    component_ids=("hw_seed_unihiker_k10",),
    firmware_family="行空板 K10 官方 MicroPython 固件",
    module="unihiker_k10",
    source_url="https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10",
    verification="OFFICIAL_DOCUMENTATION_REVIEWED; DEVICE_SMOKE_PENDING",
    objects={
        "screen": ApiObject(
            {
                "init": _call(0, 1, "dir"),
                "show_camera": _call(1, 1, "camera"),
                "show_bg": _call(1, 1, "color"),
                "set_width": _call(1, 1, "width"),
                "draw_line": _call(5, 5, "x0", "y0", "x1", "y1", "color"),
                "draw_point": _call(3, 3, "x", "y", "color"),
                "draw_rect": _call(4, 6, "x", "y", "w", "h", "bcolor", "fcolor"),
                "draw_circle": _call(4, 5, "x", "y", "r", "bcolor", "fcolor"),
                "draw_text": _call(1, 6, "text", "x", "y", "line", "font_size", "color"),
                "show_draw": _call(0),
                "show_camera_img": _call(1, 1, "image_data"),
                "clear": _call(0),
            }
        ),
        "button": ApiObject(
            {"status": _call(0)},
            ("a", "b", "event_pressed", "event_released"),
        ),
        "temp_humi": ApiObject(
            {
                "read_temp": _call(0),
                "read_temp_f": _call(0),
                "read_humi": _call(0),
            }
        ),
        "light": ApiObject({"read": _call(0)}),
        "acce": ApiObject(
            {"read_x": _call(0), "read_y": _call(0), "read_z": _call(0)}
        ),
        "rgb": ApiObject(
            {
                "write": _call(1, 4, "num", "color", "R", "G", "B"),
                "brightness": _call(1),
                "clear": _call(0),
            }
        ),
        "mic": ApiObject(
            {
                "recode_sys": _call(2, 2, "name", "time"),
                "recode_tf": _call(2, 2, "name", "time"),
            }
        ),
        "speaker": ApiObject(
            {
                "play_sys_music": _call(1),
                "play_tf_music": _call(1),
            }
        ),
        "hid": ApiObject(
            {"isconnected": _call(0), "keyboard_send": _call(1)},
        ),
        "Camera": ApiObject(
            {"init": _call(0)},
            members_complete=False,
        ),
        "TF_card": ApiObject({}, members_complete=False),
        "WiFi": ApiObject(
            {
                "connect": _call(2, 3, "ssid", "psd", "timeout"),
                "status": _call(0),
                "info": _call(0),
            }
        ),
        "MqttClient": ApiObject(
            {
                "connect": _call(1, 5, "server", "port", "client_id", "user", "psd"),
                "connected": _call(0),
                "message": _call(1, 1, "topic"),
                "received": _call(2, 2, "topic", "callback"),
                "publish": _call(2, 2, "topic", "content"),
            },
            members_complete=False,
        ),
    },
    additional_exports=(
        "keycode",
        "servo",
        "neopixel",
        "dht",
        "ds18b20",
        "ultrasonic",
        "force",
        "pin",
    ),
    forbidden_roots={
        "oled": "行空板 K10 使用 screen 对象，不使用 oled 对象。",
        "display": "行空板 K10 使用 screen 对象，不使用掌控板 display 对象。",
    },
    module_exports={
        "unihiker_k10": (
            "screen",
            "button",
            "temp_humi",
            "light",
            "acce",
            "rgb",
            "mic",
            "speaker",
            "hid",
            "keycode",
            "servo",
            "neopixel",
            "dht",
            "ds18b20",
            "ultrasonic",
            "force",
            "pin",
        ),
        "k10_base": ("Camera", "TF_card", "WiFi", "MqttClient"),
    },
    constructors={
        "button": _call(1),
        "hid": _call(0, 1, "name"),
        "Camera": _call(0),
        "TF_card": _call(0),
        "WiFi": _call(0),
        "MqttClient": _call(0),
    },
    forbidden_modules={
        "mpython": "行空板 K10 不使用掌控板 mpython 模块；请使用 unihiker_k10。",
        "pinpong": "行空板 K10 的设备端 MicroPython 代码不使用主机侧 pinpong；请使用 unihiker_k10。",
    },
    member_replacements={
        ("screen", "show"): "；绘制完成后请改用 screen.show_draw()。",
        ("screen", "text"): "；请改用 screen.draw_text()。",
        ("rgb", "show"): "；K10 RGB 请直接使用 rgb.write()。",
        ("button", "is_pressed"): "；K10 按键实例请改用 status()。",
    },
    export_guidance={
        "camera": "摄像头对象来自 k10_base.Camera，或 AI 流程使用独立 ai 模块。",
    },
    rules=(
        "只使用 unihiker_k10 与 k10_base 中列出的 K10 API，不套用掌控板、M10、通用 ESP32 或 PinPong 写法。",
        "屏幕绘制使用 screen.draw_*，绘制后调用 screen.show_draw()；初始化只执行一次。",
        "按键使用 button(button.a/button.b) 创建实例并调用 status()；RGB 使用 rgb.write()，不存在 rgb.show()。",
        "AI/ASR 使用官方独立 ai/asr 模块；初始化、摄像头启动和模式选择不得放进主循环。",
        "不得在回调或中断中刷新屏幕、联网或执行高内存操作。",
    ),
)

_CONTRACTS = {
    MPYTHON_ESP32S3_V3_CONTRACT.id: MPYTHON_ESP32S3_V3_CONTRACT,
    UNIHIKER_K10_CONTRACT.id: UNIHIKER_K10_CONTRACT,
}


def board_api_contract(contract_id: str | None) -> BoardApiContract | None:
    if contract_id is None:
        return None
    try:
        return _CONTRACTS[contract_id]
    except KeyError as exc:
        raise ValueError(f"未知开发板 API 契约：{contract_id}") from exc


def resolve_board_api_contract(
    component_ids: Iterable[str],
    spec: SpecRun | None = None,
) -> BoardApiContract | None:
    normalized_ids = {str(item).strip() for item in component_ids if str(item).strip()}
    spec_text = "\n".join(file.content for file in spec.files) if spec is not None else ""
    for contract in _CONTRACTS.values():
        if normalized_ids.intersection(contract.component_ids):
            return contract
        if any(component_id in spec_text for component_id in contract.component_ids):
            return contract
    return None


def component_ids_from_hardware_policy(policy: dict[str, object]) -> tuple[str, ...]:
    selected = policy.get("selectedComponents")
    if not isinstance(selected, list):
        return ()
    return tuple(
        str(item["componentId"])
        for item in selected
        if isinstance(item, dict) and item.get("componentId")
    )


def validate_board_api_files(
    files: Sequence[BoardContractCodeFile],
    contract_id: str | None,
) -> None:
    contract = board_api_contract(contract_id)
    if contract is None:
        return
    issues: list[str] = []
    for file in files:
        if file.language != "python":
            continue
        try:
            tree = ast.parse(file.content, filename=file.path)
        except SyntaxError:
            continue
        issues.extend(_board_api_issues(file.path, tree, contract))
    if issues:
        raise ValueError(" ".join(issues))


def _board_api_issues(
    path: str,
    tree: ast.AST,
    contract: BoardApiContract,
) -> list[str]:
    issues: list[str] = []
    module_aliases: dict[str, str] = {}
    object_aliases: dict[str, str] = {}
    star_exports: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in contract.forbidden_modules:
                    issues.append(_issue(path, node, contract.forbidden_modules[alias.name]))
                if alias.name in contract.modules:
                    module_aliases[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module in contract.forbidden_modules:
            issues.append(_issue(path, node, contract.forbidden_modules[node.module]))
        elif isinstance(node, ast.ImportFrom) and node.module in contract.modules:
            allowed_exports = contract.exports_for_module(node.module)
            for alias in node.names:
                if alias.name == "*":
                    star_exports.update(allowed_exports)
                    continue
                if alias.name not in allowed_exports:
                    guidance = contract.export_guidance.get(
                        alias.name,
                        f"请使用 {contract.display_name} API 契约中的导出。",
                    )
                    issues.append(
                        _issue(
                            path,
                            node,
                            f"{node.module} 不提供 {alias.name}；{guidance}",
                        )
                    )
                    continue
                object_aliases[alias.asname or alias.name] = alias.name

    instance_aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if not isinstance(value, ast.Call):
            continue
        constructor_name = _constructor_name(
            value.func,
            module_aliases,
            object_aliases,
            star_exports,
            contract,
        )
        if constructor_name is None:
            continue
        constructor_issue = _call_issue(
            constructor_name,
            "构造",
            value,
            contract.constructors[constructor_name],
        )
        if constructor_issue is not None:
            issues.append(_issue(path, value, constructor_issue))
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                instance_aliases[target.id] = constructor_name

    checked_attributes: set[tuple[int, int]] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        attribute_key = (node.lineno, node.col_offset)
        if attribute_key in checked_attributes:
            continue
        parts = _attribute_parts(node)
        if len(parts) < 2:
            continue
        root = parts[0]
        if root in contract.forbidden_roots:
            issues.append(_issue(path, node, contract.forbidden_roots[root]))
            checked_attributes.add(attribute_key)
            continue

        object_name: str | None = None
        member_name: str | None = None
        if root in module_aliases and len(parts) >= 2:
            object_name = parts[1]
            module_name = module_aliases[root]
            if object_name not in contract.exports_for_module(module_name):
                guidance = contract.export_guidance.get(
                    object_name,
                    f"请使用 {contract.display_name} API 契约中的导出。",
                )
                issues.append(
                    _issue(
                        path,
                        node,
                        f"{module_name} 不提供 {object_name}；{guidance}",
                    )
                )
                checked_attributes.add(attribute_key)
                continue
            if len(parts) >= 3:
                member_name = parts[2]
        elif root in object_aliases:
            object_name = object_aliases[root]
            member_name = parts[1]
        elif root in instance_aliases:
            object_name = instance_aliases[root]
            member_name = parts[1]
        elif root in star_exports:
            object_name = root
            member_name = parts[1]

        if object_name is None or member_name is None:
            continue
        object_contract = contract.objects.get(object_name)
        if object_contract is None:
            continue
        if member_name not in object_contract.members:
            if not object_contract.members_complete:
                continue
            replacement = _known_replacement(contract, object_name, member_name)
            issues.append(
                _issue(
                    path,
                    node,
                    f"{contract.display_name} API 不存在 {object_name}.{member_name}{replacement}",
                )
            )
            checked_attributes.add(attribute_key)
            continue
        if isinstance(node.ctx, ast.Load) and isinstance(_parent_call(tree, node), ast.Call):
            call_node = _parent_call(tree, node)
            assert isinstance(call_node, ast.Call)
            callable_contract = object_contract.callables.get(member_name)
            if callable_contract is not None:
                call_issue = _call_issue(
                    object_name,
                    member_name,
                    call_node,
                    callable_contract,
                )
                if call_issue is not None:
                    issues.append(_issue(path, call_node, call_issue))
        checked_attributes.add(attribute_key)
    return issues


def _constructor_name(
    node: ast.expr,
    module_aliases: dict[str, str],
    object_aliases: dict[str, str],
    star_exports: set[str],
    contract: BoardApiContract,
) -> str | None:
    if isinstance(node, ast.Name):
        candidate = object_aliases.get(node.id, node.id if node.id in star_exports else None)
        return candidate if candidate in contract.constructors else None
    if not isinstance(node, ast.Attribute):
        return None
    parts = _attribute_parts(node)
    if len(parts) != 2 or parts[0] not in module_aliases:
        return None
    module_name = module_aliases[parts[0]]
    candidate = parts[1]
    if candidate not in contract.exports_for_module(module_name):
        return None
    return candidate if candidate in contract.constructors else None


def _parent_call(tree: ast.AST, target: ast.Attribute) -> ast.AST | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and node.func is target:
            return node
    return None


def _attribute_parts(node: ast.Attribute) -> tuple[str, ...]:
    parts = [node.attr]
    value: ast.expr = node.value
    while isinstance(value, ast.Attribute):
        parts.append(value.attr)
        value = value.value
    if not isinstance(value, ast.Name):
        return ()
    parts.append(value.id)
    return tuple(reversed(parts))


def _call_issue(
    object_name: str,
    member_name: str,
    node: ast.Call,
    contract: ApiCallable,
) -> str | None:
    if any(isinstance(arg, ast.Starred) for arg in node.args) or any(
        keyword.arg is None for keyword in node.keywords
    ):
        return None
    positional_count = len(node.args)
    if positional_count > contract.maximum_positional:
        return (
            f"{object_name}.{member_name}() 位置参数数量应为 "
            f"0..{contract.maximum_positional}，"
            f"实际为 {positional_count}。"
        )
    unknown_keywords = sorted(
        keyword.arg
        for keyword in node.keywords
        if keyword.arg is not None and keyword.arg not in contract.keywords
    )
    if unknown_keywords:
        return (
            f"{object_name}.{member_name}() 不支持关键字参数："
            + ", ".join(unknown_keywords)
            + "。"
        )
    total_arguments = positional_count + len(node.keywords)
    if not contract.minimum_positional <= total_arguments <= contract.maximum_positional:
        return (
            f"{object_name}.{member_name}() 参数数量应为 "
            f"{contract.minimum_positional}..{contract.maximum_positional}，"
            f"实际为 {total_arguments}。"
        )
    return None


def _known_replacement(
    contract: BoardApiContract,
    object_name: str,
    member_name: str,
) -> str:
    return contract.member_replacements.get((object_name, member_name), "。")


def _issue(path: str, node: ast.AST, message: str) -> str:
    return f"{path}:{getattr(node, 'lineno', 0)}: {message}"
