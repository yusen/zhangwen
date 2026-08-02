"""Provider-backed lesson document generation."""

from __future__ import annotations

import json

from zhangwen.lesson_agent.generator import validate_and_package_lesson
from zhangwen.lesson_agent.models import LessonContentDraft
from zhangwen.llm.contracts import LLMConfig, LLMModelId
from zhangwen.llm.gateway import LLMProvider
from zhangwen.llm.structured import complete_structured
from zhangwen.proposals.models import ProposalVersion
from zhangwen.specs.models import SpecRun


LESSON_SYSTEM_PROMPT = """你是掌问的创客工程教案生成器。
基于已确认立项书和 Spec 生成教师教案、学生任务单、评价量表和安全说明四份完整 Markdown 文档。
教师教案必须包含学习目标、材料、流程和评价；安全说明必须覆盖供电、接线、串口、上传和固件操作的确认边界。
不得声称已经执行真实设备操作，不得包含 API Key、Wi-Fi 密码、令牌、真实串口唯一标识或本机绝对路径。
"""


class LessonGenerationService:
    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def generate(
        self,
        *,
        spec: SpecRun,
        proposal: ProposalVersion,
        grade_band: str,
        lesson_hours: int,
        config: LLMConfig,
        api_key: str,
        model: LLMModelId,
    ) -> LessonContentDraft:
        payload = {
            "operation": "generate_lesson_documents",
            "gradeBand": grade_band,
            "lessonHours": lesson_hours,
            "approvedProposal": proposal.model_dump(mode="json"),
            "approvedSpec": spec.model_dump(mode="json"),
        }
        return await complete_structured(
            provider=self._provider,
            config=config,
            api_key=api_key,
            model=model,
            system_prompt=LESSON_SYSTEM_PROMPT,
            user_prompt=json.dumps(payload, ensure_ascii=False, indent=2),
            output_model=LessonContentDraft,
            request_id_prefix="lesson_generate",
            validate_result=lambda draft: validate_and_package_lesson(
                draft=draft,
                grade_band=grade_band,
                lesson_hours=lesson_hours,
            ),
        )
