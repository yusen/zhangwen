"""Provider-backed project proposal generation and revision."""

from __future__ import annotations

import json

from zhangwen.llm.contracts import ChatProgressEmitter, LLMConfig, LLMModelId
from zhangwen.llm.gateway import LLMProvider
from zhangwen.llm.structured import complete_structured
from zhangwen.proposals.models import (
    ProposalContentDraft,
    ProposalSection,
    ProposalVersion,
)
from zhangwen.solutions.models import SolutionVersion


PROPOSAL_SYSTEM_PROMPT = """你是掌问的项目立项书生成器。
根据已经确认的唯一推荐实现方案生成完整、具体、可执行的立项书内容。
推荐方案是“方向选择与取舍”，立项书是“执行承诺与验收基线”，两者不得写成重复的两份方案说明。
不要复述或改写推荐方案的章节正文；只引用已经确认的方向，并把它转换为六行立项表所需的执行信息：
1. projectOverview：项目名称、目标、使用场景和可观察成功结果；
2. requirements：明确交付范围、必须完成和明确不包含的内容，不重复论证选型；
3. hardwareSoftwareStructure：列出硬件、软件、结构各自的交付物、接口和边界；
4. implementationPlan：按 Spec、代码、验证和最终交付分阶段写明输入、动作、产出和完成条件；
5. costDifficultySchedule：给出成本区间、难点、阶段工期和影响工期的条件；
6. risksAcceptance：逐项对应风险、控制措施、验收方法和验收证据。
每一项使用紧凑、可核对的短句，避免宣传性描述和大段背景说明。
不得虚构已经完成的测试、设备操作或采购结果；真实设备和固件操作必须保留人工确认。
"""


class ProposalGenerationService:
    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def generate(
        self,
        *,
        solution: SolutionVersion,
        config: LLMConfig,
        api_key: str,
        model: LLMModelId,
        progress_emitter: ChatProgressEmitter | None = None,
    ) -> list[ProposalSection]:
        payload = {
            "operation": "generate_project_proposal",
            "confirmedSolution": solution.model_dump(mode="json"),
        }
        draft = await self._complete(
            payload=payload,
            config=config,
            api_key=api_key,
            model=model,
            request_id_prefix="proposal_generate",
            progress_emitter=progress_emitter,
        )
        return proposal_sections(draft)

    async def revise(
        self,
        *,
        proposal: ProposalVersion,
        revision_message: str,
        config: LLMConfig,
        api_key: str,
        model: LLMModelId,
        progress_emitter: ChatProgressEmitter | None = None,
    ) -> list[ProposalSection]:
        payload = {
            "operation": "revise_project_proposal",
            "currentProposal": proposal.model_dump(mode="json"),
            "revisionInstruction": revision_message.strip(),
            "rule": "返回修订后的完整六章节内容，未要求修改的章节必须保留。",
        }
        draft = await self._complete(
            payload=payload,
            config=config,
            api_key=api_key,
            model=model,
            request_id_prefix="proposal_revise",
            progress_emitter=progress_emitter,
        )
        return proposal_sections(draft)

    async def _complete(
        self,
        *,
        payload: dict[str, object],
        config: LLMConfig,
        api_key: str,
        model: LLMModelId,
        request_id_prefix: str,
        progress_emitter: ChatProgressEmitter | None,
    ) -> ProposalContentDraft:
        return await complete_structured(
            provider=self._provider,
            config=config,
            api_key=api_key,
            model=model,
            system_prompt=PROPOSAL_SYSTEM_PROMPT,
            user_prompt=json.dumps(payload, ensure_ascii=False, indent=2),
            output_model=ProposalContentDraft,
            request_id_prefix=request_id_prefix,
            progress_emitter=progress_emitter,
        )


def proposal_sections(draft: ProposalContentDraft) -> list[ProposalSection]:
    return [
        ProposalSection(
            id="project_overview",
            title="项目名称与目标",
            content=draft.projectOverview,
        ),
        ProposalSection(
            id="requirements",
            title="需求与功能逻辑",
            content=draft.requirements,
        ),
        ProposalSection(
            id="hardware_software_structure",
            title="硬件、软件与结构方案",
            content=draft.hardwareSoftwareStructure,
        ),
        ProposalSection(
            id="implementation_plan",
            title="实施步骤",
            content=draft.implementationPlan,
        ),
        ProposalSection(
            id="cost_difficulty_schedule",
            title="成本、难度与时间",
            content=draft.costDifficultySchedule,
        ),
        ProposalSection(
            id="risks_acceptance",
            title="风险与验收标准",
            content=draft.risksAcceptance,
        ),
    ]
