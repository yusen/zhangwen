"""Provider-backed selection of bounded CAD templates and parameters."""

from __future__ import annotations

import json

from zhangwen.cad_agent.generator import template_specs
from zhangwen.cad_agent.models import CadDesignDraft, CadTemplateKind
from zhangwen.cad_agent.template_catalog import production_parameter_spec
from zhangwen.llm.contracts import LLMConfig, LLMModelId
from zhangwen.llm.gateway import LLMProvider
from zhangwen.llm.structured import complete_structured
from zhangwen.specs.models import SpecRun


CAD_SYSTEM_PROMPT = """你是掌问的受限 CAD 设计输入生成器。
只能从给定模板中选择，并只返回该模板允许的数值参数；不得生成或请求执行 Python、CadQuery、Shell 或文件操作。
根据已确认 Spec 给出适合 3D 打印和装配的保守尺寸。最终范围、几何和预览由本地校验器决定。
用户明确指定的模板或参数是必须遵守的约束，但仍需返回完整设计建议。
"""


class CadDesignService:
    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def design(
        self,
        *,
        spec: SpecRun,
        requested_template: CadTemplateKind | None,
        requested_parameters: dict[str, float] | None,
        config: LLMConfig,
        api_key: str,
        model: LLMModelId,
    ) -> CadDesignDraft:
        allowed = {
            kind.value: [
                {
                    "name": name,
                    "unit": unit,
                    "default": default,
                    "min": minimum,
                    "max": maximum,
                }
                for name, _label, unit, default, minimum, maximum in specs
            ]
            for kind, specs in template_specs().items()
        }
        payload = {
            "operation": "design_bounded_cad_input",
            "approvedSpec": spec.model_dump(mode="json"),
            "allowedTemplates": allowed,
            "userConstraints": {
                "templateKind": requested_template.value if requested_template else None,
                "parameters": requested_parameters or {},
            },
        }
        specs_by_template = template_specs()

        def validate_design(design: CadDesignDraft) -> None:
            allowed_parameters = {
                name: (minimum, maximum)
                for name, _label, _unit, _default, minimum, maximum in specs_by_template[
                    design.templateKind
                ]
            }
            unknown = sorted(set(design.parameters) - set(allowed_parameters))
            if unknown:
                raise ValueError(f"parameters are not allowed for template: {unknown}")
            out_of_range = sorted(
                name
                for name, value in design.parameters.items()
                if not allowed_parameters[name][0]
                <= value
                <= allowed_parameters[name][1]
            )
            if out_of_range:
                raise ValueError(f"parameters are outside allowed ranges: {out_of_range}")
            if design.templateKind is CadTemplateKind.BOX_WITH_LID:
                unsupported_values = sorted(
                    name
                    for name, value in design.parameters.items()
                    if not production_parameter_spec(design.templateKind, name).accepts(value)
                )
                if unsupported_values:
                    raise ValueError(
                        "parameters use unsupported discrete values: "
                        f"{unsupported_values}"
                    )

        return await complete_structured(
            provider=self._provider,
            config=config,
            api_key=api_key,
            model=model,
            system_prompt=CAD_SYSTEM_PROMPT,
            user_prompt=json.dumps(payload, ensure_ascii=False, indent=2),
            output_model=CadDesignDraft,
            request_id_prefix="cad_design",
            validate_result=validate_design,
        )
