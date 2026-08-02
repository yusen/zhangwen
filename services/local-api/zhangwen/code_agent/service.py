"""Provider-backed draft generation for supported device runtimes."""

from __future__ import annotations

import json

from zhangwen.code_agent.board_api_contracts import BoardApiContract
from zhangwen.code_agent.generator import validate_and_package_code
from zhangwen.code_agent.models import CodeContentDraft, CodeRuntime
from zhangwen.llm.contracts import LLMConfig, LLMModelId
from zhangwen.llm.gateway import LLMProvider
from zhangwen.llm.structured import complete_structured
from zhangwen.specs.models import SpecRun


CODE_SYSTEM_PROMPT = """你是掌问的 MicroPython 代码草稿生成器。
根据已确认 Spec 生成可审查、可上传的结构化项目。至少生成 src/boot.py、src/main.py、src/config.py 和 README.md；器件驱动放入 src/drivers/*.py。
自动浇花项目固定包含 src/drivers/soil_moisture.py 与 src/drivers/pump.py。main.py 必须导入所有项目依赖，README 必须写清接线、干湿标定、模拟测试和上传步骤。
代码必须适合 Spec 指定开发板的 MicroPython，并使用 Spec 中已确认的板型和 IO 事实。
泵类必须上电默认关闭、异常 finally 停泵、单次最长 3 秒、两次运行至少间隔 60 秒，并记录每日累计运行时间；标定无效或传感器异常时保持关闭。
自动浇花运行时必须输出可机读且不含隐私的证据行：每次采样输出 `ZW_WATER event=sample moisture=<整数> state=WET|DRY pump=ON|OFF`；停泵输出 `ZW_WATER event=pump_stop pump=OFF elapsed_ms=<整数>`。不得伪造未发生的湿润、干燥或停泵事件。
不得包含 API Key、令牌、Wi-Fi 密码、真实设备标识、Shell 命令执行、固件烧录或 Flash 擦除逻辑。
只生成可审查文本，不声称已经执行测试或上传设备。
"""

ESP_CLAW_LUA_SYSTEM_PROMPT = """你是掌问的 ESP-Claw Lua 代码草稿生成器。
根据已确认 Spec 生成可审查、可部署到既有 ESP-Claw 运行时的结构化 Lua 项目。
必须生成 scripts/main.lua 作为入口；辅助模块只能放在 scripts/ 下的 .lua 文件中，可选生成 README.md。
只使用 Lua 语法；绝不能输出 Python、把 Python 文件改扩展名，或声称已经执行、上传、烧录固件。
代码必须使用 Spec 中已确认的板型和 IO 事实，并保留执行器上电安全值、异常停止和有界刷新率。
不得包含 API Key、令牌、Wi-Fi 密码、真实设备标识、Shell 命令、动态代码加载、固件烧录或 Flash 擦除逻辑。
ESP-Claw 固件安装/升级不属于本次代码生成；这里只生成运行时可部署的 Lua 行为代码。
"""

BOARD_API_SYSTEM_RULES = """
如果请求包含 targetBoardApiContract，它是目标开发板板载软件 API 的确定性门禁：
- 只使用契约列出的板载对象、成员和调用参数；契约中没有的板载 API 一律视为不存在。
- 不得混用旧版掌控板、OLED、micro:bit 或其他 ESP32 开发板的便利 API。
- 普通 MicroPython 标准库和项目自身平级模块不属于板载对象白名单，但仍须满足现有安全与文件约束。
"""


class CodeGenerationService:
    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def generate(
        self,
        *,
        spec: SpecRun,
        config: LLMConfig,
        api_key: str,
        model: LLMModelId,
        board_contract: BoardApiContract | None = None,
        runtime: CodeRuntime = CodeRuntime.MICROPYTHON,
    ) -> CodeContentDraft:
        payload: dict[str, object]
        if runtime == CodeRuntime.MICROPYTHON:
            payload = {
                "operation": "generate_micropython_draft",
                "runtime": runtime.value,
                "approvedSpec": spec.model_dump(mode="json"),
                "requiredEntry": "src/main.py",
                "allowedPaths": ["src/boot.py", "src/main.py", "src/config.py", "src/drivers/*.py", "README.md"],
                "filePolicy": "structured project; include every imported module; no host-only capabilities",
            }
            system_prompt = CODE_SYSTEM_PROMPT
        else:
            payload = {
                "operation": "generate_esp_claw_lua_draft",
                "runtime": runtime.value,
                "approvedSpec": spec.model_dump(mode="json"),
                "requiredEntry": "scripts/main.lua",
                "allowedPaths": ["scripts/**/*.lua", "README.md"],
                "filePolicy": "Lua only; bounded ESP-Claw runtime files; no firmware image or host capability",
            }
            system_prompt = ESP_CLAW_LUA_SYSTEM_PROMPT
        if runtime == CodeRuntime.MICROPYTHON and board_contract is not None:
            payload["targetBoardApiContract"] = board_contract.prompt_payload()
            system_prompt += BOARD_API_SYSTEM_RULES
        return await complete_structured(
            provider=self._provider,
            config=config,
            api_key=api_key,
            model=model,
            system_prompt=system_prompt,
            user_prompt=json.dumps(payload, ensure_ascii=False, indent=2),
            output_model=CodeContentDraft,
            request_id_prefix="code_generate",
            validate_result=lambda draft: validate_and_package_code(
                spec,
                draft,
                now="validation",
                board_contract_id=(
                    board_contract.id
                    if runtime == CodeRuntime.MICROPYTHON
                    and board_contract is not None
                    else None
                ),
                runtime=runtime,
            ),
        )
