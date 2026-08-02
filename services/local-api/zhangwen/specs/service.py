"""Provider-backed engineering Spec content design."""

from __future__ import annotations

import json

from zhangwen.hardware.models import HardwareComponent
from zhangwen.llm.contracts import ChatProgressEmitter, LLMConfig, LLMModelId
from zhangwen.llm.gateway import LLMProvider
from zhangwen.llm.structured import complete_structured
from zhangwen.proposals.models import ProposalVersion
from zhangwen.specs.models import SpecContentDraft


SPEC_SYSTEM_PROMPT = """你是掌问的工程规格内容设计器。
根据已确认立项书和给定的本地硬件目录，设计项目目标、功能模块、验收标准、风险、硬件候选和 IO 建议。
componentIds 只能使用目录中提供的 id；不得虚构库存、价格、已完成测试或设备状态。
IO 建议必须使用 GPIO 数字格式。最终电气兼容、BOM 和参数校验由本地规则引擎决定。
"""


class SpecGenerationService:
    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def generate(
        self,
        *,
        proposal: ProposalVersion,
        hardware_components: list[HardwareComponent],
        config: LLMConfig,
        api_key: str,
        model: LLMModelId,
        progress_emitter: ChatProgressEmitter | None = None,
    ) -> SpecContentDraft:
        catalog = [
            {
                "id": component.id,
                "name": component.name,
                "category": component.category.value,
                "skillName": component.skillName,
                "skillRevision": component.skillRevision,
                "driver": component.electrical.driverName,
                "logicVoltage": component.electrical.logicLevel,
                "supplyVoltage": component.electrical.voltage,
            }
            for component in hardware_components
        ]
        payload = {
            "operation": "generate_engineering_spec",
            "proposal": proposal.model_dump(mode="json"),
            "allowedHardwareCatalog": catalog,
        }
        allowed_ids = {component.id for component in hardware_components}

        def validate_draft(draft: SpecContentDraft) -> None:
            unknown_ids = sorted(set(draft.componentIds) - allowed_ids)
            if unknown_ids:
                raise ValueError(f"componentIds are not in the allowed catalog: {unknown_ids}")
            selected_ids = set(draft.componentIds)
            invalid_io = sorted(
                item.componentId
                for item in draft.ioSuggestions
                if item.componentId not in selected_ids
            )
            if invalid_io:
                raise ValueError(
                    f"IO suggestions must reference selected componentIds: {invalid_io}"
                )

        return await complete_structured(
            provider=self._provider,
            config=config,
            api_key=api_key,
            model=model,
            system_prompt=SPEC_SYSTEM_PROMPT,
            user_prompt=json.dumps(payload, ensure_ascii=False, indent=2),
            output_model=SpecContentDraft,
            request_id_prefix="spec_generate",
            validate_result=validate_draft,
            progress_emitter=progress_emitter,
        )
