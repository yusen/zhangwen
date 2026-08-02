"""Focused structured compiler for no-hardware freeform CAD geometry."""

from __future__ import annotations

from collections.abc import Callable

from zhangwen.cad_engine.models import DeclarativeGeometry
from zhangwen.llm.contracts import (
    ChatProgressEmitter,
    LLMConfig,
    LLMModelId,
)
from zhangwen.llm.gateway import CancelToken, LLMProvider
from zhangwen.llm.structured import complete_structured


FREEFORM_GEOMETRY_SYSTEM_PROMPT = """你是掌问的自由结构受控几何编译器。
把用户已经确认的自然语言零件描述转换为一个可 3D 打印的声明式 CSG 配方。

约束：
- 只允许 box、rounded_box、cylinder，单位统一为 mm。
- operation 只允许 add 或 cut；第一项必须 add，总数不超过 32，primitive_id 必须唯一。
- 所有尺寸、中心、圆角和 0/90/180/270 度 Z 轴旋转必须来自描述，不得猜测缺失尺寸。
- 孔和槽使用 cut，并确保它们与已有实体相交；add 实体应相交或接触，最终目标是一个连通实体。
- 不引用任何电子器件、机械档案、图片、Python、路径、URL 或外部知识。
- 不输出说明、代码、网格或自由曲面，只返回 Schema 要求的几何对象。
"""


class FreeformGeometryCompiler:
    """Compile one confirmed description against the small geometry-only schema."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def generate(
        self,
        *,
        description: str,
        config: LLMConfig,
        api_key: str,
        model: LLMModelId,
        cancel_token: CancelToken,
        on_validated_attempt: Callable[[int], None] | None = None,
        progress_emitter: ChatProgressEmitter | None = None,
    ) -> DeclarativeGeometry:
        normalized = description.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized:
            raise ValueError("自由结构自然语言描述不能为空。")
        if len(normalized) > 20_000:
            raise ValueError("自由结构自然语言描述超出 20000 字符限制。")
        return await complete_structured(
            provider=self._provider,
            config=config,
            api_key=api_key,
            model=model,
            system_prompt=FREEFORM_GEOMETRY_SYSTEM_PROMPT,
            user_prompt=normalized,
            output_model=DeclarativeGeometry,
            request_id_prefix="freeform_geometry_generate",
            cancel_token=cancel_token,
            on_validated_attempt=on_validated_attempt,
            progress_emitter=progress_emitter,
            llm_progress_id="llm.request",
            validation_progress_id="output.validate",
        )


__all__ = ["FreeformGeometryCompiler"]
