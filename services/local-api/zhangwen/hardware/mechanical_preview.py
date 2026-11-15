"""Compile Hardware Skill mechanical prose into bounded preview geometry."""

from __future__ import annotations

import hashlib
import json
import re

from zhangwen.cad_engine.models import (
    DeclarativeGeometry,
    PreviewDeclarativeGeometry,
)
from zhangwen.llm.contracts import LLMConfig, LLMModelId
from zhangwen.llm.gateway import LLMProvider
from zhangwen.llm.structured import complete_structured


MECHANICAL_PREVIEW_SYSTEM_PROMPT = """你是掌问的器件机械预览几何编译器。
唯一尺寸来源是用户提供的 mechanical.md“自然语言描述”。把其中明确给出的可见刚性实体转换为
受控声明式几何；不得引用机器 JSON、图片、参考 Python、外部知识或猜测缺失尺寸。

约束：
- 只允许 box、rounded_box、cylinder；单位统一为 mm。
- operation 只允许 add 或 cut，第一项必须 add，总数不超过 32。
- 每个实体使用描述中的中心坐标、尺寸、圆角和 0/90/180/270 度 Z 轴旋转。
- PCB、连接器、传感体等可见实体分别建模；描述明确的通孔或槽可使用 cut。
- 不把线缆空间、光学视场或其他 keepout 当成实体。
- 不输出代码、路径、URL、网格、自由曲面、说明文字或未经描述确认的数据。
"""

_NATURAL_DESCRIPTION_PATTERN = re.compile(
    r"(?ms)^##[ \t]+自然语言描述[ \t]*\n(?P<body>.*?)(?=^##[ \t]+|\Z)"
)
_MECHANICAL_FENCE_PATTERN = re.compile(
    r"(?ms)```zhangwen:hardware-mechanical:v1[ \t]*\n"
    r"(?P<body>.*?)\n```"
)


class MechanicalPreviewSourceError(ValueError):
    """The Hardware Skill cannot provide a safe natural-description source."""


def extract_mechanical_natural_description(markdown: str) -> str:
    """Return the normalized H2 natural-description body and nothing else."""

    normalized = markdown.replace("\r\n", "\n").replace("\r", "\n")
    matches = list(_NATURAL_DESCRIPTION_PATTERN.finditer(normalized))
    if len(matches) != 1:
        raise MechanicalPreviewSourceError(
            "mechanical.md 必须且只能包含一个“## 自然语言描述”章节。"
        )
    description = matches[0].group("body").strip()
    if not description:
        raise MechanicalPreviewSourceError("mechanical.md 的自然语言描述不能为空。")
    if len(description) > 20_000:
        raise MechanicalPreviewSourceError("mechanical.md 的自然语言描述超出 20000 字符限制。")
    return description


def mechanical_description_sha256(description: str) -> str:
    """Hash the exact normalized description used as the model prompt."""

    normalized = description.replace("\r\n", "\n").replace("\r", "\n").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def write_preview_geometry(
    markdown: str,
    geometry: PreviewDeclarativeGeometry,
) -> str:
    """Replace only profile.preview_geometry inside the one mechanical JSON fence."""

    normalized = markdown.replace("\r\n", "\n").replace("\r", "\n")
    matches = list(_MECHANICAL_FENCE_PATTERN.finditer(normalized))
    if len(matches) != 1:
        raise MechanicalPreviewSourceError(
            "mechanical.md 的机器机械档案结构块必须且只能出现一次。"
        )
    match = matches[0]
    try:
        payload = json.loads(match.group("body"))
    except json.JSONDecodeError as exc:
        raise MechanicalPreviewSourceError("mechanical.md 的机器机械档案不是有效 JSON。") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("profile"), dict):
        raise MechanicalPreviewSourceError("mechanical.md 缺少有效 profile 对象。")
    payload["profile"]["preview_geometry"] = geometry.model_dump(
        mode="json",
        exclude_none=True,
    )
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    replacement = f"```zhangwen:hardware-mechanical:v1\n{rendered}\n```"
    return normalized[: match.start()] + replacement + normalized[match.end() :]


class MechanicalDescriptionPreviewService:
    """Provider-backed compiler with Pydantic validation and one repair attempt."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def generate(
        self,
        *,
        description: str,
        config: LLMConfig,
        api_key: str,
        model: LLMModelId,
    ) -> PreviewDeclarativeGeometry:
        normalized = extract_mechanical_natural_description(
            f"## 自然语言描述\n\n{description}\n"
        )
        source_sha256 = mechanical_description_sha256(normalized)
        geometry = await complete_structured(
            provider=self._provider,
            config=config,
            api_key=api_key,
            model=model,
            system_prompt=MECHANICAL_PREVIEW_SYSTEM_PROMPT,
            user_prompt=normalized,
            output_model=DeclarativeGeometry,
            request_id_prefix="mechanical_preview_generate",
        )
        return PreviewDeclarativeGeometry(
            source_sha256=source_sha256,
            primitives=geometry.primitives,
        )


__all__ = [
    "MechanicalDescriptionPreviewService",
    "MechanicalPreviewSourceError",
    "extract_mechanical_natural_description",
    "mechanical_description_sha256",
    "write_preview_geometry",
]
