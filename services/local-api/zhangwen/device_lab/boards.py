"""Single source of truth for the only two supported controller boards."""

from __future__ import annotations

import hashlib

from zhangwen.device_lab.models import (
    DeviceBoardCapability,
    DeviceBoardPinConflict,
    DeviceLabChannel,
    DeviceLabProfileV1,
    DeviceLabSceneV1,
    SupportedDeviceBoardId,
)


_K10 = SupportedDeviceBoardId.DFROBOT_K10
_XIAO = SupportedDeviceBoardId.XIAO_ESP32S3_SENSE

BOARDS: dict[SupportedDeviceBoardId, DeviceBoardCapability] = {
    _K10: DeviceBoardCapability(
        id=_K10,
        displayName="DFRobot UNIHIKER K10",
        manufacturer="DFRobot",
        flashSizeBytes=16 * 1024 * 1024,
        psramSizeBytes=8 * 1024 * 1024,
        legacyAliases=["unihiker-k10", "unihiker_k10", "hw_seed_unihiker_k10", "dfrobot_k10"],
        peripherals=[
            "ILI9341 LCD", "GC2145 camera", "AHT20 temperature/humidity",
            "LTR303ALS ambient light", "SC7A20H accelerometer", "microphone",
            "speaker", "3x WS2812 RGB", "A/B/RST/BOOT buttons", "TF card",
        ],
    ),
    _XIAO: DeviceBoardCapability(
        id=_XIAO,
        displayName="Seeed Studio XIAO ESP32S3 Sense",
        manufacturer="Seeed Studio",
        flashSizeBytes=8 * 1024 * 1024,
        psramSizeBytes=8 * 1024 * 1024,
        legacyAliases=["xiao_esp32s3_sense", "xiao-esp32s3-sense"],
        peripherals=["OV2640 camera", "PDM microphone", "SPI microSD", "USB Serial/JTAG"],
        pinConflicts=[
            DeviceBoardPinConflict(
                resources=["microSD CS", "user LED", "GPIO21"],
                message="启用 microSD 时 GPIO21 被片选占用，用户 LED 必须保持关闭。",
            )
        ],
    ),
}


def _channel(**kwargs: object) -> DeviceLabChannel:
    return DeviceLabChannel(**kwargs)


PROFILES: dict[SupportedDeviceBoardId, DeviceLabProfileV1] = {
    _K10: DeviceLabProfileV1(
        boardId=_K10,
        revision="dfrobot-k10-functional-v1",
        channels=[
            _channel(id="temperature", label="温度", kind="sensor-input", valueType="number", control="slider", unit="°C", minimum=-40, maximum=85, step=0.1, defaultValue=25, writable=True),
            _channel(id="humidity", label="湿度", kind="sensor-input", valueType="number", control="slider", unit="%", minimum=0, maximum=100, step=0.5, defaultValue=50, writable=True),
            _channel(id="ambient-light", label="环境光", kind="sensor-input", valueType="number", control="slider", unit="lux", minimum=0, maximum=64000, step=10, defaultValue=300, writable=True),
            _channel(id="accel-x", label="加速度 X", kind="sensor-input", valueType="number", control="slider", unit="g", minimum=-16, maximum=16, step=0.1, defaultValue=0, writable=True),
            _channel(id="accel-y", label="加速度 Y", kind="sensor-input", valueType="number", control="slider", unit="g", minimum=-16, maximum=16, step=0.1, defaultValue=0, writable=True),
            _channel(id="accel-z", label="加速度 Z", kind="sensor-input", valueType="number", control="slider", unit="g", minimum=-16, maximum=16, step=0.1, defaultValue=1, writable=True),
            _channel(id="button-a", label="按键 A", kind="sensor-input", valueType="boolean", control="switch", defaultValue=False, writable=True),
            _channel(id="button-b", label="按键 B", kind="sensor-input", valueType="boolean", control="switch", defaultValue=False, writable=True),
            _channel(id="fault-mode", label="故障注入", kind="sensor-input", valueType="string", control="media", defaultValue="none", writable=True),
            _channel(id="rgb-brightness", label="RGB 亮度", kind="actuator", valueType="number", control="slider", minimum=0, maximum=9, step=1, defaultValue=0, writable=True, requiresArm=True, safeValue=0),
            _channel(id="speaker-volume", label="扬声器音量", kind="actuator", valueType="number", control="slider", unit="%", minimum=0, maximum=100, step=1, defaultValue=0, writable=True, requiresArm=True, safeValue=0),
            _channel(id="sample-interval-ms", label="采样周期", kind="parameter", valueType="number", control="number", unit="ms", minimum=100, maximum=10000, step=100, defaultValue=1000, writable=True),
            _channel(id="temperature-offset", label="温度校准", kind="parameter", valueType="number", control="number", unit="°C", minimum=-10, maximum=10, step=0.1, defaultValue=0, writable=True),
            _channel(id="rgb-max-brightness", label="RGB 最大亮度", kind="parameter", valueType="number", control="number", minimum=0, maximum=9, step=1, defaultValue=3, writable=True),
        ],
    ),
    _XIAO: DeviceLabProfileV1(
        boardId=_XIAO,
        revision="xiao-esp32s3-sense-functional-v1",
        channels=[
            _channel(id="camera-fixture", label="摄像头画面", kind="sensor-input", valueType="string", control="media", defaultValue="color-bars", writable=True),
            _channel(id="microphone-level", label="麦克风电平", kind="sensor-input", valueType="number", control="waveform", unit="%", minimum=0, maximum=100, step=1, defaultValue=0, writable=True),
            _channel(id="sd-mounted", label="虚拟 SD 卡", kind="sensor-input", valueType="boolean", control="switch", defaultValue=True, writable=True),
            _channel(id="fault-mode", label="故障注入", kind="sensor-input", valueType="string", control="media", defaultValue="none", writable=True),
            _channel(id="user-led", label="用户 LED", kind="actuator", valueType="boolean", control="switch", defaultValue=False, writable=True, requiresArm=True, safeValue=False),
            _channel(id="gpio-output", label="扩展 GPIO 输出", kind="actuator", valueType="boolean", control="switch", defaultValue=False, writable=True, requiresArm=True, safeValue=False),
            _channel(id="sample-interval-ms", label="采样周期", kind="parameter", valueType="number", control="number", unit="ms", minimum=100, maximum=10000, step=100, defaultValue=1000, writable=True),
            _channel(id="microphone-gain", label="麦克风增益", kind="parameter", valueType="number", control="number", unit="dB", minimum=0, maximum=30, step=1, defaultValue=0, writable=True),
        ],
    ),
}

_ALIASES = {
    alias.casefold(): board_id
    for board_id, board in BOARDS.items()
    for alias in [board_id.value, *board.legacyAliases]
}


def normalize_board_id(value: str) -> SupportedDeviceBoardId:
    board_id = _ALIASES.get(value.strip().casefold())
    if board_id is None:
        raise ValueError("掌问只支持 DFRobot K10 与 XIAO ESP32S3 Sense。")
    return board_id


def board_capability(board_id: SupportedDeviceBoardId) -> DeviceBoardCapability:
    return BOARDS[board_id]


def board_profile(board_id: SupportedDeviceBoardId) -> DeviceLabProfileV1:
    return PROFILES[board_id]


def scene_profile(scene: DeviceLabSceneV1) -> DeviceLabProfileV1:
    """Bind safe functional controls to the proposal-derived physical scene.

    Board channels remain exact board-profile facts. External proposal devices
    receive deliberately generic fixtures, clearly labelled as simulation
    inputs/outputs; no electrical range or physical unit is invented.
    """

    base = board_profile(scene.boardId)
    channels = list(base.channels)
    for component in sorted(scene.components, key=lambda item: item.id):
        if component.role != "external" or component.simulation != "FUNCTIONAL":
            continue
        prefix = f"project.{hashlib.sha256(component.id.encode('utf-8')).hexdigest()[:12]}"
        if component.category == "SENSOR":
            channels.extend(
                [
                    _channel(
                        id=f"{prefix}.input",
                        label=f"{component.name}（仿真输入）",
                        kind="sensor-input",
                        valueType="number",
                        control="slider",
                        minimum=0,
                        maximum=100,
                        step=1,
                        defaultValue=50,
                        writable=True,
                        componentId=component.id,
                        source="project-scene",
                    ),
                    _channel(
                        id=f"{prefix}.offset",
                        label=f"{component.name}（仿真偏移）",
                        kind="parameter",
                        valueType="number",
                        control="number",
                        minimum=-100,
                        maximum=100,
                        step=1,
                        defaultValue=0,
                        writable=True,
                        componentId=component.id,
                        source="project-scene",
                    ),
                ]
            )
        elif component.category in {"ACTUATOR", "DISPLAY"}:
            channels.extend(
                [
                    _channel(
                        id=f"{prefix}.output",
                        label=f"{component.name}（仿真输出）",
                        kind="actuator",
                        valueType="number",
                        control="slider",
                        unit="%",
                        minimum=0,
                        maximum=100,
                        step=1,
                        defaultValue=0,
                        writable=True,
                        requiresArm=True,
                        safeValue=0,
                        componentId=component.id,
                        source="project-scene",
                    ),
                    _channel(
                        id=f"{prefix}.max-output",
                        label=f"{component.name}（仿真输出上限）",
                        kind="parameter",
                        valueType="number",
                        control="number",
                        unit="%",
                        minimum=0,
                        maximum=100,
                        step=1,
                        defaultValue=100,
                        writable=True,
                        componentId=component.id,
                        source="project-scene",
                    ),
                ]
            )
    return DeviceLabProfileV1(
        boardId=scene.boardId,
        revision=f"{base.revision}+scene-{scene.revision[:16]}",
        channels=channels,
    )
