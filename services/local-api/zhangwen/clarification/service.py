"""Provider-backed clarification and solution structured outputs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from zhangwen.clarification.prompts import (
    CLARIFY_SYSTEM_PROMPT,
    REVISE_SOLUTION_SYSTEM_PROMPT,
    SOLUTION_SYSTEM_PROMPT,
)
from zhangwen.creator.models import ConversationProjectDraftV1
from zhangwen.experts.config import load_expert_prompt
from zhangwen.llm.contracts import ChatMessage, ChatProgressEmitter, LLMConfig
from zhangwen.llm.deepseek import DeepSeekProvider
from zhangwen.llm.gateway import LLMProvider
from zhangwen.llm.structured import complete_structured
from zhangwen.projects.models import ExpertType
from zhangwen.config import settings


class ClarificationOptionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=1000)
    recommended: bool | None = None


class ClarificationQuestionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=120)
    type: str = Field(pattern=r"^(SINGLE_SELECT|MULTI_SELECT|TEXT)$")
    question: str = Field(min_length=1, max_length=1000)
    options: list[ClarificationOptionModel] = Field(default_factory=list, max_length=6)

    @model_validator(mode="after")
    def _validate_options(self) -> "ClarificationQuestionModel":
        if self.type == "TEXT" and self.options:
            raise ValueError("TEXT questions cannot include options")
        if self.type != "TEXT" and not 2 <= len(self.options) <= 6:
            raise ValueError("selection questions require 2-6 options")
        return self


class ClarificationRoundModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questions: list[ClarificationQuestionModel] = Field(max_length=6)
    completeness: int = Field(ge=0, le=100)
    message: str = Field(min_length=1, max_length=4000)
    project_draft: ConversationProjectDraftV1 | None = Field(
        default=None, alias="projectDraft"
    )

    @model_validator(mode="after")
    def _keep_only_highest_impact_question(self) -> "ClarificationRoundModel":
        # Providers are instructed to order by impact. This local boundary
        # prevents a drifting model from turning the conversation into a form.
        self.questions = self.questions[:1]
        if not self.questions and self.completeness < 80:
            # Reject the incomplete output so ``complete_structured`` asks the
            # provider for one schema repair. A fabricated generic question is
            # not project evidence and must never be persisted as if it were.
            raise ValueError(
                "low-completeness clarification requires one project-specific question"
            )
        if self.questions and (
            self.questions[0].id == "creator_primary_outcome"
            or self.questions[0].question.strip()
            == "这个作品最重要、必须让人看到的结果是什么？"
        ):
            raise ValueError("generic clarification fallback is not allowed")
        if self.questions:
            normalized_question = "".join(self.questions[0].question.split())
            meta_question_markers = (
                "是否继续",
                "怎么继续",
                "如何继续",
                "还要继续",
                "继续补充需求",
                "需要继续补充",
                "是否需要补充",
                "是否还有补充",
                "要不要补充",
                "还有什么需要补充",
                "接下来你希望怎么",
            )
            if any(
                marker in normalized_question for marker in meta_question_markers
            ):
                raise ValueError(
                    "clarification must ask the next concrete product decision, "
                    "not whether to continue"
                )
        return self


class SolutionSectionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=12000)


class SolutionDraftModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sections: list[SolutionSectionModel] = Field(min_length=1, max_length=12)


class SolutionSectionChangeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sectionId: str
    sectionTitle: str
    changeType: str = Field(pattern=r"^(updated|added|removed)$")
    before: Any | None = None
    after: Any | None = None
    reason: str


class SolutionRevisionDraftModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revisedSolution: SolutionDraftModel
    changedSections: list[SolutionSectionChangeModel]
    preservedSections: list[str]
    impactSummary: list[str]
    requiresProposalUpdate: bool = True


class ClarificationService:
    def __init__(
        self,
        provider: LLMProvider | None = None,
        data_dir: Path | None = None,
    ) -> None:
        self._provider = provider or DeepSeekProvider()
        self._data_dir = data_dir or settings.data_dir

    async def clarify(
        self,
        user_message: str,
        context_messages: list[ChatMessage],
        config: LLMConfig,
        api_key: str,
        progress_emitter: ChatProgressEmitter | None = None,
    ) -> ClarificationRoundModel:
        return await complete_structured(
            provider=self._provider,
            config=config,
            api_key=api_key,
            model=config.defaultModel,
            system_prompt=self._problem_guide_prompt(CLARIFY_SYSTEM_PROMPT, user_message),
            context_messages=context_messages[-6:],
            user_prompt=user_message,
            output_model=ClarificationRoundModel,
            request_id_prefix="clarification",
            progress_emitter=progress_emitter,
        )

    async def generate_solution(
        self,
        context_messages: list[ChatMessage],
        revision_message: str | None,
        config: LLMConfig,
        api_key: str,
        progress_emitter: ChatProgressEmitter | None = None,
    ) -> SolutionDraftModel:
        instruction = (
            f"请根据以下修改意见生成完整唯一推荐方案：{revision_message}"
            if revision_message
            else "请根据以上已确认上下文生成一套完整的唯一推荐实现方案。"
        )
        return await complete_structured(
            provider=self._provider,
            config=config,
            api_key=api_key,
            model=config.defaultModel,
            system_prompt=self._problem_guide_prompt(SOLUTION_SYSTEM_PROMPT, instruction),
            context_messages=context_messages,
            user_prompt=instruction,
            output_model=SolutionDraftModel,
            request_id_prefix="solution_generate",
            progress_emitter=progress_emitter,
        )

    async def revise_solution(
        self,
        context_messages: list[ChatMessage],
        config: LLMConfig,
        api_key: str,
        progress_emitter: ChatProgressEmitter | None = None,
    ) -> SolutionRevisionDraftModel:
        revision_prompt = (
            context_messages[-1].content
            if context_messages
            else "请按当前用户要求修订并返回完整方案。"
        )
        return await complete_structured(
            provider=self._provider,
            config=config,
            api_key=api_key,
            model=config.defaultModel,
            system_prompt=self._problem_guide_prompt(
                REVISE_SOLUTION_SYSTEM_PROMPT,
                revision_prompt,
            ),
            context_messages=context_messages[:-1],
            user_prompt=revision_prompt,
            output_model=SolutionRevisionDraftModel,
            request_id_prefix="solution_revise",
            progress_emitter=progress_emitter,
        )

    def _problem_guide_prompt(self, flow_prompt: str, user_message: str) -> str:
        return (
            load_expert_prompt(
                ExpertType.PROBLEM_GUIDE,
                user_message=user_message,
                data_dir=self._data_dir,
            )
            + f"\n\n{flow_prompt}"
        )
