from __future__ import annotations

import json

from zhangwen.llm.contracts import (
    LLMErrorCode,
    LLMModelId,
    StreamChunk,
    StreamChunkType,
)
from zhangwen.llm.errors import make_llm_error
from zhangwen.proposals.models import ProposalContentDraft, ProposalSection
from zhangwen.proposals.service import proposal_sections


class FakeCredentialStore:
    def get_password(self, service: str, account: str) -> str:
        return "fake-test-key"


class EmptyCredentialStore:
    def get_password(self, service: str, account: str) -> None:
        return None


class SequenceProvider:
    def __init__(self, outputs: list[str | LLMErrorCode]) -> None:
        self.outputs = outputs
        self.calls = 0
        self.requests: list[object] = []

    async def stream_chat(
        self,
        request,
        config,
        api_key,
        cancel_token,
        request_id,
        message_id,
    ):
        self.requests.append(request)
        output = self.outputs[min(self.calls, len(self.outputs) - 1)]
        self.calls += 1
        if isinstance(output, LLMErrorCode):
            yield StreamChunk(
                requestId=request_id,
                messageId=message_id,
                type=StreamChunkType.ERROR,
                error=make_llm_error(output),
            )
            return
        yield StreamChunk(
            requestId=request_id,
            messageId=message_id,
            type=StreamChunkType.COMPLETED,
            accumulatedContent=output,
            model=LLMModelId.DEEPSEEK_V4_FLASH,
        )


class StructuredFakeProvider:
    async def stream_chat(
        self,
        request,
        config,
        api_key,
        cancel_token,
        request_id,
        message_id,
    ):
        system_prompt = request.messages[0].content if request.messages else ""
        user_prompt = request.messages[-1].content if request.messages else ""
        if "方案修订助手" in system_prompt:
            content = json.dumps(
                {
                    "revisedSolution": {
                        "sections": [
                            {"id": "goal", "title": "项目目标", "content": "自动浇花"},
                            {"id": "hardware", "title": "硬件方案", "content": "ESP32 与传感器"},
                        ]
                    },
                    "changedSections": [
                        {
                            "sectionId": "hardware",
                            "sectionTitle": "硬件方案",
                            "changeType": "updated",
                            "before": "旧硬件",
                            "after": "ESP32 与传感器",
                            "reason": "按用户要求更新。",
                        }
                    ],
                    "preservedSections": ["项目目标"],
                    "impactSummary": ["硬件方案已更新"],
                    "requiresProposalUpdate": True,
                },
                ensure_ascii=False,
            )
        elif "方案生成助手" in system_prompt:
            content = json.dumps(
                {
                    "sections": [
                        {"id": "sec_goal", "title": "项目目标", "content": "制作自动浇花装置。"},
                        {"id": "sec_logic", "title": "工作逻辑", "content": "低湿度时控制水泵。"},
                        {"id": "sec_hardware", "title": "硬件组成", "content": "ESP32 x1、传感器 x1、水泵驱动 x1。"},
                        {"id": "sec_software", "title": "软件模块", "content": "MicroPython 采集与控制。"},
                        {"id": "sec_structure", "title": "结构实现", "content": "防水盒和传感器支架。"},
                        {"id": "sec_steps", "title": "实施步骤", "content": "先采集，再控制，最后联调。"},
                        {"id": "sec_cost", "title": "成本与工期", "content": "预算 200 元，工期两天。"},
                        {"id": "sec_risk", "title": "风险与限制", "content": "复核供电、防水和水泵空转。"},
                    ]
                },
                ensure_ascii=False,
            )
        elif "需求澄清助手" in system_prompt:
            if "AUTO_COMPLETE_CREATOR_GUIDE" in user_prompt:
                content = json.dumps(
                    {
                        "questions": [],
                        "completeness": 95,
                        "message": "关键信息已经齐全。",
                        "projectDraft": {
                            "schemaVersion": 1,
                            "useScenario": "家庭阳台盆栽自动浇水",
                            "observableBehavior": "干燥时启动水泵，湿润后停止",
                            "constraints": ["水泵默认关闭", "断线归零"],
                            "successCriteria": ["干燥时启动", "湿润后停止"],
                            "missingFields": [],
                        },
                    },
                    ensure_ascii=False,
                )
            else:
                content = json.dumps(
                    {
                        "questions": [
                            {
                                "id": "target_context",
                                "type": "SINGLE_SELECT",
                                "question": "主要使用场景是什么？",
                                "options": [
                                    {"id": "home", "label": "家庭"},
                                    {"id": "school", "label": "学校"},
                                ],
                            }
                        ],
                        "completeness": 40,
                        "message": "请先确认主要使用场景。",
                    },
                    ensure_ascii=False,
                )
        elif "项目立项书生成器" in system_prompt:
            revision = "增加课堂安全提醒" if "revisionInstruction" in user_prompt else ""
            content = json.dumps(
                {
                    "projectOverview": "形成可执行、可验证的创客项目。",
                    "requirements": "实现已经确认方案中的功能逻辑。",
                    "hardwareSoftwareStructure": "按确认方案落实硬件、软件和结构。",
                    "implementationPlan": "依次完成 Spec、代码、结构和验证。",
                    "costDifficultySchedule": "按低风险 MVP 安排成本和工期。",
                    "risksAcceptance": f"保留设备安全确认并完成验收。{revision}",
                },
                ensure_ascii=False,
            )
        elif "工程规格内容设计器" in system_prompt:
            content = json.dumps(
                {
                    "projectName": "自动浇花装置",
                    "goal": "根据土壤湿度安全控制水泵并反馈状态。",
                    "modules": [
                        {
                            "id": "sense",
                            "name": "湿度采集",
                            "responsibility": "读取土壤湿度传感器。",
                        },
                        {
                            "id": "control",
                            "name": "水泵控制",
                            "responsibility": "按阈值控制水泵驱动。",
                        },
                    ],
                    "acceptance": [
                        "湿度低于阈值时启动水泵。",
                        "设备操作前保留人工确认。",
                    ],
                    "risks": ["必须复核供电、电流和防水。"],
                    "componentIds": [
                        "hw_seed_unihiker_k10",
                        "hw_seed_dht22",
                        "hw_seed_mosfet_driver",
                        "hw_seed_oled_096",
                        "hw_seed_usb_5v_power",
                        "hw_seed_breadboard",
                    ],
                    "ioSuggestions": [
                        {
                            "signal": "sensor_data",
                            "pin": "GPIO4",
                            "protocol": "GPIO",
                            "componentId": "hw_seed_dht22",
                        },
                        {
                            "signal": "actuator_pwm",
                            "pin": "GPIO5",
                            "protocol": "PWM",
                            "componentId": "hw_seed_mosfet_driver",
                        },
                        {
                            "signal": "status_i2c",
                            "pin": "GPIO8/GPIO9",
                            "protocol": "I2C",
                            "componentId": "hw_seed_oled_096",
                        },
                    ],
                },
                ensure_ascii=False,
            )
        elif "ESP-Claw Lua 代码草稿生成器" in system_prompt:
            content = json.dumps(
                {
                    "files": [
                        {
                            "path": "scripts/main.lua",
                            "language": "lua",
                            "content": (
                                "local pump = { state = 'OFF' }\n"
                                "local function stop_pump()\n"
                                "  pump.state = 'OFF'\n"
                                "  print('ZW_WATER event=pump_stop pump=OFF elapsed_ms=0')\n"
                                "end\n"
                                "local function sample()\n"
                                "  stop_pump()\n"
                                "  print('ZW_WATER event=sample moisture=700 state=WET pump=OFF')\n"
                                "end\n"
                                "sample()\n"
                            ),
                        },
                        {
                            "path": "README.md",
                            "language": "markdown",
                            "content": "# ESP-Claw 自动浇花\n\n默认关闭水泵，断线与异常保持安全值。\n",
                        },
                    ],
                    "summary": "自动浇花 ESP-Claw Lua 安全草稿",
                },
                ensure_ascii=False,
            )
        elif "MicroPython 代码草稿生成器" in system_prompt:
            content = json.dumps(
                {
                    "files": [
                        {
                            "path": "src/boot.py",
                            "language": "python",
                            "content": (
                                "# 上电阶段不启动水泵；main.py 初始化后仍先写入停止脉宽。\n"
                                "BOOT_PUMP_DEFAULT = 'OFF'\n"
                            ),
                        },
                        {
                            "path": "src/main.py",
                            "language": "python",
                            "content": (
                                "import time\n"
                                "from config import LOOP_DELAY_MS, PUMP_COOLDOWN_MS\n"
                                "from drivers.soil_moisture import SoilMoistureSensor\n"
                                "from drivers.pump import PumpController\n\n"
                                "def main():\n"
                                "    sensor = SoilMoistureSensor()\n"
                                "    pump = PumpController()\n"
                                "    try:\n"
                                "        while True:\n"
                                "            value, state = sensor.sample()\n"
                                "            if state == 'DRY' and pump.cooldown_elapsed():\n"
                                "                pump.run_limited()\n"
                                "            else:\n"
                                "                pump.stop()\n"
                                "            print('ZW_WATER event=sample moisture={} state={} pump={}'.format(value, state, pump.state))\n"
                                "            time.sleep_ms(LOOP_DELAY_MS)\n"
                                "    except Exception:\n"
                                "        pump.stop()\n"
                                "        raise\n"
                                "    finally:\n"
                                "        pump.stop()\n\n"
                                "if __name__ == '__main__':\n"
                                "    main()\n"
                            ),
                        },
                        {
                            "path": "src/config.py",
                            "language": "python",
                            "content": (
                                "SENSOR_PIN = 4\nPUMP_PWM_PIN = 5\n"
                                "DRY_CALIBRATION = 3000\nWET_CALIBRATION = 1200\n"
                                "LOOP_DELAY_MS = 1000\nPUMP_MAX_RUN_MS = 3000\n"
                                "PUMP_COOLDOWN_MS = 60000\n"
                            ),
                        },
                        {
                            "path": "src/drivers/soil_moisture.py",
                            "language": "python",
                            "content": (
                                "from machine import ADC, Pin\n"
                                "from config import SENSOR_PIN, DRY_CALIBRATION, WET_CALIBRATION\n\n"
                                "class SoilMoistureSensor:\n"
                                "    def __init__(self):\n"
                                "        if DRY_CALIBRATION <= WET_CALIBRATION:\n"
                                "            raise ValueError('invalid calibration')\n"
                                "        self.adc = ADC(Pin(SENSOR_PIN))\n\n"
                                "    def sample(self):\n"
                                "        value = self.adc.read()\n"
                                "        if value < 0 or value > 4095:\n"
                                "            raise ValueError('sensor out of range')\n"
                                "        return value, ('DRY' if value >= DRY_CALIBRATION else 'WET')\n"
                            ),
                        },
                        {
                            "path": "src/drivers/pump.py",
                            "language": "python",
                            "content": (
                                "import time\nfrom machine import Pin, PWM\n"
                                "from config import PUMP_PWM_PIN, PUMP_MAX_RUN_MS, PUMP_COOLDOWN_MS\n\n"
                                "class PumpController:\n"
                                "    def __init__(self):\n"
                                "        self.pwm = PWM(Pin(PUMP_PWM_PIN), freq=500)\n"
                                "        self.state = 'OFF'\n        self.last_stop_ms = -PUMP_COOLDOWN_MS\n"
                                "        self.daily_runtime_ms = 0\n        self.stop()\n\n"
                                "    def stop(self):\n"
                                "        self.pwm.duty_u16(32768)\n        self.state = 'OFF'\n\n"
                                "    def cooldown_elapsed(self):\n"
                                "        return time.ticks_diff(time.ticks_ms(), self.last_stop_ms) >= PUMP_COOLDOWN_MS\n\n"
                                "    def run_limited(self):\n"
                                "        started = time.ticks_ms()\n        self.pwm.duty_u16(50000)\n        self.state = 'ON'\n"
                                "        try:\n            time.sleep_ms(PUMP_MAX_RUN_MS)\n"
                                "        finally:\n"
                                "            elapsed = min(time.ticks_diff(time.ticks_ms(), started), PUMP_MAX_RUN_MS)\n"
                                "            self.stop()\n            self.last_stop_ms = time.ticks_ms()\n"
                                "            self.daily_runtime_ms += max(0, elapsed)\n"
                                "            print('ZW_WATER event=pump_stop pump=OFF elapsed_ms={}'.format(elapsed))\n"
                                "            print('ZW_WATER event=daily_runtime elapsed_ms={}'.format(self.daily_runtime_ms))\n"
                            ),
                        },
                        {
                            "path": "README.md",
                            "language": "markdown",
                            "content": (
                                "# 自动浇花\n\nSEN0193 以 3.3V 供电并接 K10 ADC；DFR0523 控制信号接 PWM。"
                                "水泵使用独立 5V/3A 稳压电源并与 K10 共地，禁止由 GPIO 或 K10 供电。\n\n"
                                "首次运行前分别记录干燥/湿润读数并更新 `src/config.py`。先在 Mock 环境验证，"
                                "再确认上传；观察湿润关泵、干燥有限启动、三秒内停止和无未处理异常。\n"
                            ),
                        },
                    ],
                    "summary": "自动浇花 MicroPython 结构化安全工程草稿",
                },
                ensure_ascii=False,
            )
        elif "受限 CAD 设计输入生成器" in system_prompt:
            content = json.dumps(
                {
                    "templateKind": "SENSOR_BRACKET",
                    "parameters": {
                        "width": 48,
                        "height": 36,
                        "thickness": 3,
                        "mount_holes": 4,
                        "hole_diameter": 3,
                    },
                    "rationale": "为传感器提供保守尺寸的可打印支架。",
                },
                ensure_ascii=False,
            )
        elif "创客工程教案生成器" in system_prompt:
            content = json.dumps(
                {
                    "teacherGuide": (
                        "# 教师教案\n\n## 学习目标\n理解湿度采集和水泵控制。\n\n"
                        "## 教学流程\n分析 Spec、完成 Mock 验证并复盘。\n"
                    ),
                    "studentWorksheet": (
                        "# 学生任务单\n\n## 今日任务\n标出输入、输出和控制逻辑。\n"
                    ),
                    "rubric": (
                        "# 评价量表\n\n## 评价维度\n功能逻辑、工程记录、测试证据和安全操作。\n"
                    ),
                    "safetyNotes": (
                        "# 安全说明\n\n## 供电与接线\n不带电改线，先复核额定参数。\n\n"
                        "## 设备操作\n串口、上传和固件操作必须经过人工确认。\n"
                    ),
                },
                ensure_ascii=False,
            )
        else:
            content = json.dumps(
                {
                    "intent": "clarify_project_idea",
                    "projectName": "测试创客项目",
                    "initialExpert": "problem_guide",
                    "recommendedExperts": ["problem_guide"],
                    "confidence": 0.9,
                    "reason": "测试 Provider 返回的项目路由。",
                    "requiresClarification": True,
                },
                ensure_ascii=False,
            )
        yield StreamChunk(
            requestId=request_id,
            messageId=message_id,
            type=StreamChunkType.COMPLETED,
            accumulatedContent=content,
            model=request.model or LLMModelId.DEEPSEEK_V4_FLASH,
        )


def fake_proposal_sections(note: str = "") -> list[ProposalSection]:
    suffix = f" {note}" if note else ""
    return proposal_sections(
        ProposalContentDraft(
            projectOverview=f"形成可执行、可验证的测试项目。{suffix}",
            requirements="实现确认方案中的功能逻辑。",
            hardwareSoftwareStructure="按确认方案落实硬件、软件和结构。",
            implementationPlan="依次完成 Spec、代码、结构和验证。",
            costDifficultySchedule="按低风险 MVP 安排成本和工期。",
            risksAcceptance=f"保留设备安全确认并完成验收。{suffix}",
        )
    )
