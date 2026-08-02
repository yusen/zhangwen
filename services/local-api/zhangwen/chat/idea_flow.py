"""Project IDEA-stage conversation orchestration."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

from zhangwen.clarification.service import (
    ClarificationRoundModel,
    ClarificationService,
    SolutionDraftModel,
    SolutionRevisionDraftModel,
)
from zhangwen.chat.workspace_context import v2_workspace_prompt_context
from zhangwen.device_lab.scene import materialize_device_lab_scene
from zhangwen.experts.config import canonical_expert_type, load_expert_prompt
from zhangwen.experts.context_assembler import ContextAssembler, ContextAssemblyInput
from zhangwen.llm.contracts import (
    ChatMessage,
    ChatMessageStatus,
    ChatProgressAction,
    ChatProgressCallback,
    ChatProgressEmitter,
    ChatProgressStatus,
    ChatRole,
    LLMConfig,
    LLMErrorCode,
    LLMModelId,
    LLMModelSelection,
)
from zhangwen.llm.errors import make_llm_error
from zhangwen.llm.structured import StructuredLLMError
from zhangwen.projects.models import ExpertType, PersistedChatRequest, ProjectStage
from zhangwen.projects.repository import ProjectRepository
from zhangwen.proposals.repository import ProposalRepository
from zhangwen.proposals.service import ProposalGenerationService
from zhangwen.skills.model_router import ModelRouter
from zhangwen.skills.models import ModelRouteStrategy
from zhangwen.solutions.models import (
    SolutionSection,
    SolutionSectionChange,
    SolutionStatus,
    SolutionVersion,
)
from zhangwen.solutions.repository import SolutionRepository


CLARIFICATION = "clarification"
SOLUTION = "solution"
SOLUTION_CARD = "solution_card"
PROPOSAL_ACTION = "proposal_action"
SYSTEM_NOTICE = "system_notice"
PROJECT_DELIVERY_TRACK = "project"
LESSON_DELIVERY_TRACK = "lesson"
_T = TypeVar("_T")


@dataclass(frozen=True)
class ConversationResult:
    content: str
    payload: dict[str, Any]


def should_handle_project_conversation(stage: ProjectStage, request: PersistedChatRequest) -> bool:
    if request.conversationAction:
        return True
    return stage in {
        ProjectStage.IDEA,
        ProjectStage.CLARIFYING,
        ProjectStage.SOLUTION_DRAFT,
        ProjectStage.SOLUTION_CONFIRMED,
        ProjectStage.PROPOSAL_DRAFT,
    }


async def handle_project_conversation(
    *,
    repo: ProjectRepository,
    project_id: str,
    request: PersistedChatRequest,
    user_message: ChatMessage,
    config: LLMConfig | None = None,
    api_key: str | None = None,
    provider: Any | None = None,
    model: LLMModelSelection | None = None,
    on_progress: ChatProgressCallback | None = None,
) -> ConversationResult:
    progress_emitter = ChatProgressEmitter(on_progress)
    if request.sourceMessageId and request.questionId:
        _run_project_update(
            progress_emitter,
            lambda: _mark_source_answered(repo, project_id, request),
        )
    context_progress_id = progress_emitter.next_id("context.read")
    progress_emitter.emit(
        progress_id=context_progress_id,
        action=ChatProgressAction.CONTEXT_READ,
        status=ChatProgressStatus.RUNNING,
    )
    await asyncio.sleep(0)
    try:
        workspace = repo.get_workspace(project_id)
        action = request.conversationAction
        expert_type = canonical_expert_type(
            request.expertType
            or next(
                (
                    expert.expertType
                    for expert in workspace.experts
                    if expert.id
                    == (request.projectExpertId or workspace.project.activeExpertId)
                ),
                ExpertType.PROBLEM_GUIDE,
            )
        )
        assembled = ContextAssembler(repo.db_path).assemble(
            ContextAssemblyInput(
                projectId=project_id,
                expert=expert_type,
                userMessage=user_message.content,
            )
        )
        v2_workspace_context = v2_workspace_prompt_context(request.turnContext)
        runtime_context_message = ChatMessage(
            id=f"runtime_context_{user_message.id}",
            role=ChatRole.SYSTEM,
            content=(
                load_expert_prompt(
                    expert_type,
                    user_message=user_message.content,
                    data_dir=repo.db_path.parents[1],
                )
                + "\n\n最小项目上下文：\n"
                + json.dumps(assembled.model_dump(mode="json"), ensure_ascii=False)
                + (f"\n\n{v2_workspace_context}" if v2_workspace_context else "")
            ),
            status=ChatMessageStatus.READY,
            createdAt=user_message.createdAt,
            updatedAt=user_message.updatedAt,
        )
        runtime_messages = [runtime_context_message, *workspace.conversation.messages]
    except Exception:
        progress_emitter.emit(
            progress_id=context_progress_id,
            action=ChatProgressAction.CONTEXT_READ,
            status=ChatProgressStatus.FAILED,
        )
        raise
    progress_emitter.emit(
        progress_id=context_progress_id,
        action=ChatProgressAction.CONTEXT_READ,
        status=ChatProgressStatus.COMPLETED,
    )

    if action in {"generate_solution", "use_recommended_defaults"}:
        return await _generate_solution(
            repo,
            project_id,
            config=config,
            api_key=api_key,
            provider=provider,
            use_defaults=action == "use_recommended_defaults",
            progress_emitter=progress_emitter,
        )
    if action == "continue_clarification":
        _run_project_update(
            progress_emitter,
            lambda: _update_stage(repo, project_id, ProjectStage.CLARIFYING),
        )
        return await _clarify_with_llm(
            repo=repo,
            project_id=project_id,
            workspace_messages=runtime_messages,
            request=request,
            user_message=user_message,
            data_dir=repo.db_path.parents[1],
            config=config,
            api_key=api_key,
            provider=provider,
            progress_emitter=progress_emitter,
            auto_generate_solution=True,
        )
    if action == "modify_solution":
        return await _ask_solution_revision_scope(
            repo,
            project_id,
            request=request,
            user_message=user_message,
            config=config,
            api_key=api_key,
            provider=provider,
            progress_emitter=progress_emitter,
        )
    if action == "accept_solution_revision":
        return _accept_solution_revision(repo, project_id)
    if action == "restore_previous_solution":
        return _restore_previous_solution(repo, project_id, progress_emitter)
    if action == "confirm_solution":
        return _confirm_solution(repo, project_id, progress_emitter)
    if action == "generate_project_proposal":
        return await _generate_proposal(
            repo,
            project_id,
            confirm_first=False,
            config=config,
            api_key=api_key,
            provider=provider,
            model=model,
            progress_emitter=progress_emitter,
            delivery_track=PROJECT_DELIVERY_TRACK,
        )
    if action == "confirm_solution_and_generate_project_proposal":
        return await _generate_proposal(
            repo,
            project_id,
            confirm_first=True,
            config=config,
            api_key=api_key,
            provider=provider,
            model=model,
            progress_emitter=progress_emitter,
            delivery_track=PROJECT_DELIVERY_TRACK,
        )
    if action in {
        "generate_lesson_version",
        "confirm_solution_and_generate_lesson_version",
    }:
        return await _generate_proposal(
            repo,
            project_id,
            confirm_first=action == "confirm_solution_and_generate_lesson_version",
            config=config,
            api_key=api_key,
            provider=provider,
            model=model,
            progress_emitter=progress_emitter,
            delivery_track=LESSON_DELIVERY_TRACK,
        )
    if action == "view_solution":
        return _current_solution_card(repo, project_id)
    if action == "open_solution_floating":
        return _system_notice("已为当前方案准备浮窗预览入口，中央对话会继续保留。")
    if action == "view_project_proposal":
        return _system_notice(
            "当前客户端未能打开立项书浮窗，请更新桌面应用后重试。",
            severity="warning",
        )
    if action == "modify_project_proposal":
        return _system_notice(
            "请告诉我你想修改立项书的哪一部分，例如目标、计划、成本、风险或验收标准。",
            severity="info",
        )
    if action == "confirm_project_proposal":
        return await _confirm_proposal(
            repo,
            project_id,
            progress_emitter=progress_emitter,
        )
    if action == "continue_chat":
        return _system_notice("好的，我们先保持当前进度。你可以继续输入想补充的内容。")
    if action == "continue_project_implementation":
        return _system_notice(
            "立项书确认后将由项目中已有的智能工程师继续执行。"
        )

    if workspace.project.stage in {
        ProjectStage.SOLUTION_DRAFT,
        ProjectStage.SOLUTION_CONFIRMED,
    }:
        return await _revise_solution(
            repo,
            project_id,
            user_message.content,
            config=config,
            api_key=api_key,
            provider=provider,
            progress_emitter=progress_emitter,
        )
    if workspace.project.stage == ProjectStage.PROPOSAL_DRAFT:
        if _looks_like_solution_revision(user_message.content):
            return await _revise_solution(
                repo,
                project_id,
                user_message.content,
                config=config,
                api_key=api_key,
                provider=provider,
                progress_emitter=progress_emitter,
            )
        return await _revise_proposal(
            repo,
            project_id,
            user_message.content,
            config=config,
            api_key=api_key,
            provider=provider,
            model=model,
            progress_emitter=progress_emitter,
        )

    _run_project_update(
        progress_emitter,
        lambda: _update_stage(repo, project_id, ProjectStage.CLARIFYING),
    )
    return await _clarify_with_llm(
        repo=repo,
        project_id=project_id,
        workspace_messages=runtime_messages,
        request=request,
        user_message=user_message,
        data_dir=repo.db_path.parents[1],
        config=config,
        api_key=api_key,
        provider=provider,
        progress_emitter=progress_emitter,
        auto_generate_solution=True,
    )


async def _clarify_with_llm(
    *,
    repo: ProjectRepository | None = None,
    project_id: str | None = None,
    workspace_messages: list[ChatMessage],
    request: PersistedChatRequest,
    user_message: ChatMessage,
    data_dir: Path,
    config: LLMConfig | None,
    api_key: str | None,
    provider: Any | None,
    progress_emitter: ChatProgressEmitter,
    auto_generate_solution: bool = False,
) -> ConversationResult:
    if config is not None and api_key and provider is not None:
        try:
            result = await ClarificationService(
                provider,
                data_dir=data_dir,
            ).clarify(
                user_message=_clarification_user_message(
                    request,
                    user_message,
                    workspace_messages,
                ),
                context_messages=_clarification_context(workspace_messages, user_message.id),
                config=config,
                api_key=api_key,
                progress_emitter=progress_emitter,
            )
        except ValueError as exc:
            return _system_notice(str(exc), severity="warning")
        if (
            auto_generate_solution
            and not result.questions
            and result.completeness >= 80
        ):
            if repo is None or project_id is None:
                return _system_notice(
                    "项目上下文不完整，暂时无法自动生成推荐方案，请重试。",
                    severity="warning",
                )
            return await _generate_solution(
                repo,
                project_id,
                config=config,
                api_key=api_key,
                provider=provider,
                project_draft=result.project_draft,
                progress_emitter=progress_emitter,
            )
        mapped = _clarification_result_to_payload(result)
        if mapped is not None:
            return mapped
    return _system_notice(
        "云端模型没有返回可用的结构化引导，请重试或补充更明确的需求。",
        severity="warning",
    )


def _clarification_user_message(
    request: PersistedChatRequest,
    user_message: ChatMessage,
    workspace_messages: list[ChatMessage],
) -> str:
    structured_answer = request.structuredAnswer
    if getattr(structured_answer, "type", None) == "clarification_batch_answer":
        source_message_id = getattr(structured_answer, "sourceMessageId", None)
        source = next(
            (message for message in workspace_messages if message.id == source_message_id),
            None,
        )
        answered_questions = []
        if source is not None and source.structuredPayload:
            answered_questions = [
                {
                    "questionId": question.get("id"),
                    "question": question.get("text"),
                    "answer": question.get("answer"),
                }
                for question in _payload_questions(source.structuredPayload)
                if question.get("answered")
            ]
        return (
            "用户已完成本轮全部澄清问题。\n"
            f"回答摘要: {user_message.content}\n"
            "结构化问题与答案:\n"
            + json.dumps(answered_questions, ensure_ascii=False)
            + "\n请一次处理完整答案集合，更新已确认需求；如果仍有方向性缺口，"
            "请像产品经理一样直接返回下一个最高影响的具体问题，不要询问是否继续。"
        )
    if request.questionId:
        return (
            "用户正在回答当前澄清问题。\n"
            f"questionId: {request.questionId}\n"
            f"用户回答: {user_message.content}\n"
            "请只处理这个回答，更新已确认需求；如果仍有方向性缺口，请直接提出下一个最高影响的"
            "具体问题，不要询问是否继续或是否需要补充。"
        )
    return user_message.content


def _clarification_context(
    messages: list[ChatMessage],
    current_user_message_id: str,
) -> list[ChatMessage]:
    context: list[ChatMessage] = []
    for message in messages:
        if message.id == current_user_message_id:
            continue
        if message.role == ChatRole.ASSISTANT and not message.content.strip():
            continue
        context.append(message)
    return context[-8:]


def _clarification_result_to_payload(
    result: ClarificationRoundModel,
) -> ConversationResult | None:
    if result.questions:
        mapped_questions = [_map_clarification_question(question) for question in result.questions]
        payload = {
            "type": CLARIFICATION,
            "summary": result.message,
            "completeness": result.completeness,
            "question": mapped_questions[0],
            "questions": mapped_questions,
        }
        if result.project_draft is not None:
            payload["projectDraft"] = result.project_draft.model_dump(
                by_alias=True,
                mode="json",
            )
        return ConversationResult(content=result.message, payload=payload)
    return None


def _map_clarification_question(question) -> dict[str, Any]:
    mode = {
        "SINGLE_SELECT": "single",
        "MULTI_SELECT": "multiple",
        "TEXT": "text",
    }[question.type]
    options = [
        _option(
            option.id,
            option.label,
            option.id,
            recommended=bool(option.recommended),
        )
        | ({"description": option.description} if option.description else {})
        for option in question.options
    ]
    return {
        "id": question.id,
        "text": question.question,
        "mode": mode,
        "allowCustomInput": mode == "text" or any(
            option["id"] == "custom" for option in options
        ),
        "required": True,
        "options": options,
    }


SECTION_ID_ALIASES = {
    "sec_goal": "goal",
    "project_goal": "goal",
    "goal": "goal",
    "sec_logic": "functional_logic",
    "logic": "functional_logic",
    "working_logic": "functional_logic",
    "functional_logic": "functional_logic",
    "sec_hardware": "hardware",
    "hardware_solution": "hardware",
    "hardware": "hardware",
    "sec_software": "software",
    "software_modules": "software",
    "software": "software",
    "sec_structure": "structure",
    "structure": "structure",
    "sec_steps": "implementation_steps",
    "steps": "implementation_steps",
    "implementation_steps": "implementation_steps",
    "sec_cost": "cost_difficulty_time",
    "cost": "cost_difficulty_time",
    "cost_difficulty_time": "cost_difficulty_time",
    "sec_risk": "risks",
    "risk": "risks",
    "risks": "risks",
}


def _solution_generation_context(
    repo: ProjectRepository,
    project_id: str,
    *,
    use_defaults: bool = False,
    base_solution: SolutionVersion | None = None,
) -> list[ChatMessage]:
    workspace = repo.get_workspace(project_id)
    shared_context = workspace.sharedContext
    assembled = ContextAssembler(repo.db_path).assemble(
        ContextAssemblyInput(
            projectId=project_id,
            expert=ExpertType.SMART_ENGINEER,
            userMessage="生成推荐实现方案",
        )
    )
    legacy_confirmed_facts = [
        fact.model_dump(mode="json")
        for fact in (shared_context.confirmedFacts if shared_context else [])
    ]
    modern_confirmed_facts = [
        fact
        for fact in assembled.relevantFacts
        if fact.get("status") == "confirmed"
    ]
    confirmed_facts = _dedupe_context_facts(
        [*legacy_confirmed_facts, *modern_confirmed_facts]
    )
    preferred_hardware = [
        item
        for item in assembled.publicKnowledge
        if item.get("source") == "preferred_project_hardware"
    ]
    local_hardware_library = [
        item
        for item in assembled.publicKnowledge
        if item.get("source") == "local_hardware_library"
    ]
    context_payload: dict[str, Any] = {
        "project": {
            "id": workspace.project.id,
            "name": workspace.project.name,
            "stage": workspace.project.stage.value,
            "initialIdea": workspace.project.profile.initialIdea,
        },
        "instruction": (
            "用户选择由掌问补全未明确内容并生成唯一推荐方案。"
            if use_defaults
            else "用户明确要求生成唯一推荐方案。"
        ),
        "confirmedFacts": confirmed_facts,
        "preferredHardware": preferred_hardware,
        "localHardwareLibrary": local_hardware_library,
        "hardwareKnowledgePolicy": assembled.hardwareKnowledgePolicy,
        "preferredHardwareRule": (
            "preferredHardware 是用户已有器件；硬件章节必须复用并标注“用户已有”，"
            "只补充功能缺口，不得把其中的 componentId 再列为新增建议；"
            "当 preferredHardware 为空时，必须先评估 localHardwareLibrary 中匹配的本地 "
            "ACTIVE Hardware Skill，再按已确认需求声明仍缺少的能力。"
        ),
        "clarificationAnswers": _clarification_answer_context(
            workspace.conversation.messages
        ),
        "recentConversation": _recent_conversation_context(
            workspace.conversation.messages
        ),
    }
    if base_solution is not None:
        context_payload["baseSolution"] = _solution_context_payload(base_solution)
    return [
        _context_message(
            "solution_context",
            "以下是生成/修改推荐实现方案必须使用的项目上下文 JSON：\n"
            f"{json.dumps(context_payload, ensure_ascii=False, indent=2)}",
        )
    ]


def _dedupe_context_facts(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for fact in facts:
        fact_id = str(fact.get("id") or "")
        if fact_id and fact_id in seen:
            continue
        if fact_id:
            seen.add(fact_id)
        result.append(fact)
    return result


def _solution_revision_context(
    repo: ProjectRepository,
    project_id: str,
    *,
    base: SolutionVersion,
    user_request: str,
) -> list[ChatMessage]:
    payload = {
        "baseSolution": _solution_context_payload(base),
        "userInstruction": user_request.strip(),
        "rule": "请基于 baseSolution 修订，保留未受影响章节，并返回完整 revisedSolution。",
    }
    return [
        *_solution_generation_context(repo, project_id, base_solution=base),
        _context_message(
            "solution_revision_request",
            "以下是本次方案修订请求 JSON：\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}",
        ),
    ]


def _solution_sections_from_draft(draft: SolutionDraftModel) -> list[SolutionSection]:
    sections = [
        SolutionSection(
            id=_normalize_solution_section_id(section.id),
            title=section.title,
            content=section.content,
        )
        for section in draft.sections
        if section.content.strip()
    ]
    if not sections:
        raise ValueError("云端模型没有返回可保存的方案章节，请重试。")
    return sections


def _merge_revised_solution_sections(
    base: SolutionVersion,
    draft: SolutionRevisionDraftModel,
) -> list[SolutionSection]:
    revised_by_id = {
        _normalize_solution_section_id(section.id): SolutionSection(
            id=_normalize_solution_section_id(section.id),
            title=section.title,
            content=section.content,
        )
        for section in draft.revisedSolution.sections
        if section.content.strip()
    }
    merged: list[SolutionSection] = []
    seen: set[str] = set()
    for base_section in base.sections:
        normalized_id = _normalize_solution_section_id(base_section.id)
        merged.append(revised_by_id.get(normalized_id, base_section))
        seen.add(normalized_id)
    for section_id, section in revised_by_id.items():
        if section_id not in seen:
            merged.append(section)
    if not merged:
        raise ValueError("云端模型没有返回可保存的修订方案，请重试。")
    return merged


def _normalize_solution_section_id(section_id: str) -> str:
    key = section_id.strip().lower().replace("-", "_")
    return SECTION_ID_ALIASES.get(key, key)


def _solution_context_payload(solution: SolutionVersion) -> dict[str, Any]:
    return {
        "id": solution.id,
        "version": solution.version,
        "status": solution.status.value,
        "sections": [section.model_dump(mode="json") for section in solution.sections],
        "changeSummary": solution.changeSummary,
    }


def _clarification_answer_context(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    answers: list[dict[str, Any]] = []
    for message in messages:
        payload = message.structuredPayload or {}
        if payload.get("type") != CLARIFICATION:
            continue
        for question in _payload_questions(payload):
            answer = question.get("answer") if isinstance(question, dict) else None
            if not isinstance(answer, dict):
                continue
            options = question.get("options") or []
            labels = [
                str(option.get("label") or option.get("id"))
                for option in options
                if isinstance(option, dict)
                and option.get("id") in set(answer.get("selectedOptionIds") or [])
            ]
            answers.append(
                {
                    "questionId": question.get("id"),
                    "question": question.get("text"),
                    "selectedOptionIds": answer.get("selectedOptionIds") or [],
                    "selectedLabels": labels,
                    "textInput": answer.get("textInput"),
                    "usedRecommendation": answer.get("usedRecommendation"),
                }
            )
    return answers


def _payload_questions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    questions = payload.get("questions")
    if isinstance(questions, list):
        return [question for question in questions if isinstance(question, dict)]
    question = payload.get("question")
    return [question] if isinstance(question, dict) else []


def _recent_conversation_context(messages: list[ChatMessage]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for message in messages[-16:]:
        content = " ".join(message.content.split())
        if not content:
            continue
        items.append({"role": message.role.value, "content": content[:1200]})
    return items


def _context_message(message_id: str, content: str) -> ChatMessage:
    return ChatMessage(
        id=message_id,
        role=ChatRole.USER,
        content=content,
        status=ChatMessageStatus.READY,
        createdAt="",
        updatedAt="",
    )


async def _generate_solution(
    repo: ProjectRepository,
    project_id: str,
    *,
    config: LLMConfig | None,
    api_key: str | None,
    provider: Any | None,
    use_defaults: bool = False,
    project_draft=None,
    progress_emitter: ChatProgressEmitter,
) -> ConversationResult:
    if config is None or not api_key or provider is None:
        return _system_notice(
            "生成推荐方案需要云端模型配置，请先配置 DeepSeek API Key。",
            severity="warning",
        )
    revision_message = "用户选择由掌问补全未明确内容，请基于已澄清信息做推荐默认决策。" if use_defaults else None
    try:
        draft = await ClarificationService(
            provider,
            data_dir=repo.db_path.parents[1],
        ).generate_solution(
            context_messages=_solution_generation_context(
                repo,
                project_id,
                use_defaults=use_defaults,
            ),
            revision_message=revision_message,
            config=config,
            api_key=api_key,
            progress_emitter=progress_emitter,
        )
    except ValueError as exc:
        return _system_notice(str(exc), severity="warning")

    sections = _solution_sections_from_draft(draft)

    def persist_solution() -> SolutionVersion:
        solution = SolutionRepository(repo.db_path).create_solution(project_id, sections)
        ProposalRepository(repo.db_path).mark_project_proposals_stale(
            project_id,
            "推荐实现方案已生成新版本。",
        )
        _update_stage(repo, project_id, ProjectStage.SOLUTION_DRAFT)
        return solution

    solution = _run_project_update(progress_emitter, persist_solution)
    content = (
        "关键信息已经齐全，推荐方案已自动生成并同步到右侧“创意与方案”。"
        "你可以在那里查看、要求修改或确认方案。"
    )
    payload = _solution_card_payload(
        solution,
        message=content,
        mode="draft",
    )
    if project_draft is not None:
        payload["projectDraft"] = project_draft.model_dump(
            by_alias=True,
            mode="json",
        )
    return ConversationResult(
        content=content,
        payload=payload,
    )


async def _ask_solution_revision_scope(
    repo: ProjectRepository,
    project_id: str,
    *,
    request: PersistedChatRequest,
    user_message: ChatMessage,
    config: LLMConfig | None,
    api_key: str | None,
    provider: Any | None,
    progress_emitter: ChatProgressEmitter,
) -> ConversationResult:
    if config is None or not api_key or provider is None:
        return _system_notice(
            "修改方案需要云端模型配置，请先配置 DeepSeek API Key。",
            severity="warning",
        )
    current = SolutionRepository(repo.db_path).get_current_solution(project_id)
    if current is None:
        return _system_notice("当前还没有可修改的推荐实现方案。", severity="warning")
    prompt_message = ChatMessage(
        id="solution_revision_scope_request",
        role=ChatRole.USER,
        content=(
            "用户点击了“修改方案”，请根据当前方案判断需要让用户补充哪些修改意图。"
            "只返回 1-2 个澄清问题，不要直接修订方案。"
        ),
        status=ChatMessageStatus.READY,
        createdAt="",
        updatedAt="",
    )
    result = await _clarify_with_llm(
        workspace_messages=[
            *_solution_generation_context(repo, project_id, base_solution=current),
            prompt_message,
        ],
        request=request,
        user_message=user_message,
        data_dir=repo.db_path.parents[1],
        config=config,
        api_key=api_key,
        provider=provider,
        progress_emitter=progress_emitter,
    )
    return result


async def _revise_solution(
    repo: ProjectRepository,
    project_id: str,
    user_request: str,
    *,
    config: LLMConfig | None,
    api_key: str | None,
    provider: Any | None,
    progress_emitter: ChatProgressEmitter,
) -> ConversationResult:
    solution_repo = SolutionRepository(repo.db_path)
    base = solution_repo.get_current_solution(project_id)
    if base is None:
        return _system_notice("当前还没有可修改的推荐实现方案。", severity="warning")
    if config is None or not api_key or provider is None:
        return _system_notice(
            "修改方案需要云端模型配置，请先配置 DeepSeek API Key。",
            severity="warning",
        )

    try:
        draft = await ClarificationService(
            provider,
            data_dir=repo.db_path.parents[1],
        ).revise_solution(
            context_messages=_solution_revision_context(
                repo,
                project_id,
                base=base,
                user_request=user_request,
            ),
            config=config,
            api_key=api_key,
            progress_emitter=progress_emitter,
        )
        revised_sections = _merge_revised_solution_sections(base, draft)
        changed_sections = [
            SolutionSectionChange(**change.model_dump(mode="json"))
            for change in draft.changedSections
        ]
        def persist_revision():
            solution, revision = solution_repo.create_revision_from_llm(
                project_id,
                base=base,
                revised_sections=revised_sections,
                user_request=user_request,
                changed_sections=changed_sections,
                preserved_sections=draft.preservedSections,
                impact_summary=draft.impactSummary,
            )
            ProposalRepository(repo.db_path).mark_project_proposals_stale(
                project_id,
                "推荐实现方案已修订，立项书需在确认新方案后更新。",
            )
            _update_stage(repo, project_id, ProjectStage.SOLUTION_DRAFT)
            return solution, revision

        solution, revision = _run_project_update(progress_emitter, persist_revision)
    except ValueError as exc:
        return _system_notice(str(exc), severity="warning")
    changed = "；".join(revision.impactSummary[:3])
    content = (
        f"方案已更新为 v{solution.version}。\n\n"
        f"本次修改：{changed}\n\n"
        f"保持不变：{'、'.join(revision.preservedSections[:6]) or '未标记'}"
    )
    return ConversationResult(
        content=content,
        payload=_solution_card_payload(
            solution,
            message=content,
            mode="revision",
            revision=revision.model_dump(mode="json"),
        ),
    )


def _confirm_solution(
    repo: ProjectRepository,
    project_id: str,
    progress_emitter: ChatProgressEmitter,
) -> ConversationResult:
    solution_repo = SolutionRepository(repo.db_path)
    solution = solution_repo.get_current_solution(project_id)
    if solution is None:
        return _system_notice("当前还没有可确认的推荐实现方案。", severity="warning")
    def persist_confirmation():
        confirmed = solution_repo.confirm_solution(project_id, solution.id)
        _update_stage(repo, project_id, ProjectStage.SOLUTION_CONFIRMED)
        proposal = ProposalRepository(repo.db_path).get_current_proposal(project_id)
        return confirmed, proposal

    confirmed, proposal = _run_project_update(progress_emitter, persist_confirmation)
    if proposal is not None and proposal.staleReason:
        content = (
            f"当前方案 v{confirmed.version} 已确认。\n\n"
            "已有立项书基于旧方案，需要更新。"
        )
    else:
        content = f"已确认当前推荐实现方案 v{confirmed.version}。后续正式工程产物会引用这个确认版本。"
    return ConversationResult(
        content=content,
        payload=_solution_card_payload(
            confirmed,
            message=content,
            mode="confirmed",
            proposal_outdated=proposal is not None and proposal.staleReason is not None,
        ),
    )


def _accept_solution_revision(repo: ProjectRepository, project_id: str) -> ConversationResult:
    solution = SolutionRepository(repo.db_path).get_current_solution(project_id)
    if solution is None:
        return _system_notice("当前还没有可接受的方案修订。", severity="warning")
    content = (
        f"已接受本次修改，方案 v{solution.version} 现在作为当前草稿。\n\n"
        "如果要进入后续正式工程产物，请继续确认当前方案。"
    )
    return ConversationResult(
        content=content,
        payload=_solution_card_payload(solution, message=content, mode="draft"),
    )


def _restore_previous_solution(
    repo: ProjectRepository,
    project_id: str,
    progress_emitter: ChatProgressEmitter,
) -> ConversationResult:
    try:
        def persist_restore() -> SolutionVersion:
            solution = SolutionRepository(repo.db_path).restore_previous_solution(project_id)
            _update_stage(repo, project_id, ProjectStage.SOLUTION_DRAFT)
            return solution

        solution = _run_project_update(progress_emitter, persist_restore)
    except ValueError as exc:
        return _system_notice(str(exc), severity="warning")
    content = f"已恢复到推荐实现方案 v{solution.version}。被恢复前的新版本保留为历史版本。"
    return ConversationResult(
        content=content,
        payload=_solution_card_payload(solution, message=content, mode="draft"),
    )


def _current_solution_card(repo: ProjectRepository, project_id: str) -> ConversationResult:
    solution = SolutionRepository(repo.db_path).get_current_solution(project_id)
    if solution is None:
        return _system_notice("当前还没有可查看的推荐实现方案。", severity="warning")
    content = f"这是当前推荐实现方案 v{solution.version}。"
    return ConversationResult(
        content=content,
        payload=_solution_card_payload(solution, message=content, mode="draft"),
    )


async def _generate_proposal(
    repo: ProjectRepository,
    project_id: str,
    *,
    confirm_first: bool,
    config: LLMConfig | None,
    api_key: str | None,
    provider: Any | None,
    model: LLMModelSelection | None,
    progress_emitter: ChatProgressEmitter,
    delivery_track: str,
) -> ConversationResult:
    solution_repo = SolutionRepository(repo.db_path)
    solution = solution_repo.get_current_solution(project_id)
    if solution is None:
        return _system_notice("生成立项书前需要先生成并确认当前方案。", severity="warning")
    if solution.status != SolutionStatus.CONFIRMED:
        if not confirm_first:
            content = "生成立项书前需要先确认当前方案。"
            payload = {
                "type": PROPOSAL_ACTION,
                "message": content,
                "actions": [
                    _action(
                        "confirm_solution_and_generate_project_proposal",
                        "确认方案并生成立项书",
                        "confirm_solution_and_generate_project_proposal",
                    ),
                    _action(
                        "confirm_solution_and_generate_lesson_version",
                        "确认方案并生成教案版本",
                        "confirm_solution_and_generate_lesson_version",
                    ),
                    _action("modify_solution", "继续修改方案", "modify_solution"),
                    _action("continue_chat", "暂不生成", "continue_chat"),
                ],
            }
            return ConversationResult(content=content, payload=payload)
        def persist_solution_confirmation() -> SolutionVersion:
            confirmed = solution_repo.confirm_solution(project_id, solution.id)
            _update_stage(repo, project_id, ProjectStage.SOLUTION_CONFIRMED)
            return confirmed

        solution = _run_project_update(
            progress_emitter,
            persist_solution_confirmation,
        )

    _run_project_update(
        progress_emitter,
        lambda: repo.set_delivery_track(project_id, delivery_track),
    )

    llm_config, llm_api_key, llm_provider = _require_proposal_llm(
        config,
        api_key,
        provider,
    )
    route = ModelRouter(repo.db_path).route(
        agent_id="proposal_generator",
        task_kind="proposal_generation",
        strategy=ModelRouteStrategy.QUALITY_FIRST,
    )
    sections = await ProposalGenerationService(llm_provider).generate(
        solution=solution,
        config=llm_config,
        api_key=llm_api_key,
        model=model or route.model,
        progress_emitter=progress_emitter,
    )
    def persist_proposal():
        proposal = ProposalRepository(repo.db_path).create_from_solution(
            project_id,
            solution,
            sections,
        )
        _update_stage(repo, project_id, ProjectStage.PROPOSAL_DRAFT)
        return proposal

    proposal = _run_project_update(progress_emitter, persist_proposal)
    lesson_track = delivery_track == LESSON_DELIVERY_TRACK
    content = (
        "已选择教案版本，并生成教学实施基线。请先确认这份表格式立项书；"
        "确认后如项目已有智能工程师，将直接交接执行。"
        if lesson_track
        else "立项书已经生成，包含项目目标、功能方案、硬件清单、实施计划、成本、风险和验收标准。"
    )
    payload = {
        "type": PROPOSAL_ACTION,
        "message": content,
        "proposalId": proposal.id,
        "proposalVersion": proposal.version,
        "actions": [
            _action("view_project_proposal", "查看立项书", "view_project_proposal"),
            _action("modify_project_proposal", "修改立项书", "modify_project_proposal"),
            _action(
                "confirm_project_proposal",
                "确认教学实施基线" if lesson_track else "确认立项书",
                "confirm_project_proposal",
            ),
            _action(
                "continue_project_implementation",
                "继续项目实施",
                "continue_project_implementation",
            ),
        ],
    }
    return ConversationResult(content=content, payload=payload)


async def _revise_proposal(
    repo: ProjectRepository,
    project_id: str,
    revision: str,
    *,
    config: LLMConfig | None,
    api_key: str | None,
    provider: Any | None,
    model: LLMModelSelection | None,
    progress_emitter: ChatProgressEmitter,
) -> ConversationResult:
    proposal_repo = ProposalRepository(repo.db_path)
    current = proposal_repo.get_current_proposal(project_id)
    if current is None:
        return _system_notice("当前还没有可修改的立项书。", severity="warning")
    llm_config, llm_api_key, llm_provider = _require_proposal_llm(
        config,
        api_key,
        provider,
    )
    route = ModelRouter(repo.db_path).route(
        agent_id="proposal_generator",
        task_kind="proposal_revision",
        strategy=ModelRouteStrategy.QUALITY_FIRST,
    )
    sections = await ProposalGenerationService(llm_provider).revise(
        proposal=current,
        revision_message=revision,
        config=llm_config,
        api_key=llm_api_key,
        model=model or route.model,
        progress_emitter=progress_emitter,
    )
    def persist_proposal_revision():
        proposal = proposal_repo.revise_proposal(
            project_id,
            current.id,
            sections,
        )
        _update_stage(repo, project_id, ProjectStage.PROPOSAL_DRAFT)
        return proposal

    proposal = _run_project_update(progress_emitter, persist_proposal_revision)
    content = f"立项书已按你的补充生成新版本 v{proposal.version}。"
    payload = {
        "type": PROPOSAL_ACTION,
        "message": content,
        "proposalId": proposal.id,
        "proposalVersion": proposal.version,
        "actions": [
            _action("view_project_proposal", "查看立项书", "view_project_proposal"),
            _action("modify_project_proposal", "继续修改立项书", "modify_project_proposal"),
            _action("confirm_project_proposal", "确认立项书", "confirm_project_proposal"),
        ],
    }
    return ConversationResult(content=content, payload=payload)


def _require_proposal_llm(
    config: LLMConfig | None,
    api_key: str | None,
    provider: Any | None,
) -> tuple[LLMConfig, str, Any]:
    if config is None or not api_key or provider is None:
        raise StructuredLLMError(make_llm_error(LLMErrorCode.CONFIG_MISSING))
    return config, api_key, provider


async def _confirm_proposal(
    repo: ProjectRepository,
    project_id: str,
    *,
    progress_emitter: ChatProgressEmitter,
) -> ConversationResult:
    proposal_repo = ProposalRepository(repo.db_path)
    current = proposal_repo.get_current_proposal(project_id)
    if current is None:
        return _system_notice("当前还没有可确认的立项书。", severity="warning")

    workspace = repo.get_workspace(project_id)
    smart_engineer = next(
        (
            expert
            for expert in workspace.experts
            if expert.expertType == ExpertType.SMART_ENGINEER
            and expert.removedAt is None
            and not expert.archivedLegacyThread
        ),
        None,
    )

    def persist_confirmation():
        proposal = proposal_repo.confirm_proposal(project_id, current.id)
        _update_stage(
            repo,
            project_id,
            ProjectStage.IMPLEMENTING
            if smart_engineer is not None
            else ProjectStage.PROPOSAL_CONFIRMED,
        )
        return proposal

    proposal = _run_project_update(progress_emitter, persist_confirmation)
    scene = materialize_device_lab_scene(repo.db_path, repo.data_dir, project_id)
    content = (
        f"已确认立项书 v{proposal.version}，正在交接给智能工程师执行。"
        if smart_engineer is not None
        else f"已确认立项书 v{proposal.version}。当前项目没有智能工程师，已保留确认结果。"
    )
    payload: dict[str, Any] = {
        "type": PROPOSAL_ACTION,
        "message": content,
        "proposalId": proposal.id,
        "proposalVersion": proposal.version,
        "actions": [
            _action("view_project_proposal", "查看立项书", "view_project_proposal"),
        ],
    }
    if scene is not None:
        payload["simulation"] = {
            "automatic": True,
            "sceneRevision": scene.revision,
            "boardId": scene.boardId.value,
            "componentCount": len(scene.components),
            "status": scene.status,
            "label": "已根据立项内容创建实物仿真",
        }
    if smart_engineer is not None:
        payload["handoff"] = {
            "automatic": True,
            "targetExpert": ExpertType.SMART_ENGINEER.value,
            "label": "已交接给智能工程师",
            "prompt": "立项书已确认，请基于当前已确认立项书直接开始项目实现。",
        }
    return ConversationResult(
        content=content,
        payload=payload,
    )


def _system_notice(
    message: str,
    *,
    severity: str = "info",
) -> ConversationResult:
    return ConversationResult(
        content=message,
        payload={
            "type": SYSTEM_NOTICE,
            "severity": severity,
            "message": message,
        },
    )


def _solution_card_payload(
    solution,
    *,
    message: str,
    mode: str,
    revision: dict[str, Any] | None = None,
    proposal_outdated: bool = False,
) -> dict[str, Any]:
    if mode == "revision":
        actions = [
            _action("modify_solution", "继续修改", "modify_solution"),
            _action("view_solution", "查看完整方案", "view_solution"),
            _action("restore_previous_solution", "恢复上一版本", "restore_previous_solution"),
        ]
    elif solution.status == SolutionStatus.CONFIRMED:
        actions = [
            _action("modify_solution", "创建新修订", "modify_solution"),
            _action("open_solution_floating", "打开浮窗", "open_solution_floating"),
        ]
        if proposal_outdated:
            actions = [
                _action("modify_solution", "继续修改", "modify_solution"),
                _action("open_solution_floating", "打开浮窗", "open_solution_floating"),
            ]
    else:
        actions = [
            _action("modify_solution", "修改方案", "modify_solution"),
            _action("open_solution_floating", "打开浮窗", "open_solution_floating"),
        ]
    return {
        "type": SOLUTION_CARD,
        "solutionId": solution.id,
        "artifactId": solution.artifactId,
        "artifactVersionId": solution.artifactVersionId,
        "version": solution.version,
        "basedOnVersion": solution.basedOnVersion,
        "status": solution.status.value,
        "title": _solution_title(solution),
        "summary": _solution_summary(solution, message),
        "sections": [
            {
                "id": section.id,
                "title": section.title,
                "content": section.content,
                "summary": _section_summary(section.content),
            }
            for section in solution.sections
        ],
        "changeSummary": solution.changeSummary,
        "revision": revision,
        "actions": actions,
    }


def _solution_title(solution) -> str:
    goal = next((section for section in solution.sections if section.id == "goal"), None)
    if goal is None:
        return "推荐实现方案"
    content = goal.content.replace("制作一个围绕“", "").split("”")[0].strip()
    return content or "推荐实现方案"


def _solution_summary(solution, fallback: str) -> str:
    hardware = next((s.content for s in solution.sections if s.id == "hardware"), "")
    logic = next((s.content for s in solution.sections if s.id == "functional_logic"), "")
    summary = "；".join(item for item in [logic, hardware] if item)
    if not summary:
        summary = fallback
    return _section_summary(summary, limit=120)


def _section_summary(content: str, *, limit: int = 72) -> str:
    compact = " ".join(content.split())
    return compact if len(compact) <= limit else f"{compact[:limit]}..."


def _looks_like_solution_revision(text: str) -> bool:
    return any(keyword in text for keyword in ("推荐实现方案", "实现方案", "修改方案", "方案版本"))


def _mark_source_answered(
    repo: ProjectRepository,
    project_id: str,
    request: PersistedChatRequest,
) -> None:
    if not request.sourceMessageId or not request.questionId:
        return
    workspace = repo.get_workspace(project_id)
    source = next(
        (
            message
            for message in workspace.conversation.messages
            if message.id == request.sourceMessageId
        ),
        None,
    )
    if source is None or not source.structuredPayload:
        return
    payload = dict(source.structuredPayload)
    answer = {
        "questionId": request.questionId,
        "selectedOptionIds": request.selectedOptionIds or [],
        "textInput": request.textInput,
        "usedRecommendation": "recommended" in set(request.selectedOptionIds or []),
    }
    matched = False
    questions = [dict(question) for question in _payload_questions(payload)]
    for question in questions:
        if question.get("id") != request.questionId:
            continue
        if question.get("answered"):
            return
        question["answered"] = True
        question["answer"] = answer
        matched = True
    if not matched:
        return
    payload["questions"] = questions
    if isinstance(payload.get("question"), dict) and payload["question"].get("id") == request.questionId:
        payload["question"] = next(
            question for question in questions if question.get("id") == request.questionId
        )
    repo.update_message(project_id, source.id, structured_payload=payload)


def _update_stage(repo: ProjectRepository, project_id: str, stage: ProjectStage) -> None:
    now = datetime.now(UTC).isoformat()
    with repo._connect() as conn:
        conn.execute(
            "UPDATE projects SET stage = ?, updated_at = ? WHERE id = ?",
            (stage.value, now, project_id),
        )


def _run_project_update(
    progress_emitter: ChatProgressEmitter,
    operation: Callable[[], _T],
) -> _T:
    progress_id = progress_emitter.next_id("project.update")
    progress_emitter.emit(
        progress_id=progress_id,
        action=ChatProgressAction.PROJECT_UPDATE,
        status=ChatProgressStatus.RUNNING,
    )
    try:
        result = operation()
    except Exception:
        progress_emitter.emit(
            progress_id=progress_id,
            action=ChatProgressAction.PROJECT_UPDATE,
            status=ChatProgressStatus.FAILED,
        )
        raise
    progress_emitter.emit(
        progress_id=progress_id,
        action=ChatProgressAction.PROJECT_UPDATE,
        status=ChatProgressStatus.COMPLETED,
    )
    return result


def _option(
    option_id: str,
    label: str,
    value: str,
    *,
    recommended: bool = False,
) -> dict[str, Any]:
    return {
        "id": option_id,
        "label": label,
        "value": value,
        "recommended": recommended,
    }


def _action(
    action_id: str,
    label: str,
    action: str,
    *,
    recommended: bool = False,
) -> dict[str, Any]:
    return {
        "id": action_id,
        "label": label,
        "action": action,
        "recommended": recommended,
    }
