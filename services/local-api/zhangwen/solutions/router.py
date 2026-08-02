"""Solution HTTP routes."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from zhangwen.clarification.service import ClarificationService
from zhangwen.config import settings
from zhangwen.llm.contracts import ChatMessage, ChatMessageStatus, ChatRole
from zhangwen.llm.deepseek import DeepSeekProvider
from zhangwen.llm.http import llm_http_exception
from zhangwen.llm.runtime import require_llm_config
from zhangwen.llm.structured import StructuredLLMError
from zhangwen.hardware.models import ValidationSeverity
from zhangwen.hardware.router import validate_component_ids
from zhangwen.projects.models import ProjectStage
from zhangwen.projects.repository import ProjectRepository
from zhangwen.proposals.repository import ProposalRepository
from zhangwen.security.credentials import BackendCredentialStore
from zhangwen.solutions.models import (
    ConfirmSolutionRequest,
    ConfirmSolutionResponse,
    GenerateSolutionRequest,
    RestoreSolutionResponse,
    ReviseSolutionRequest,
    ReviseSolutionResponse,
    SolutionSection,
    SolutionSectionChange,
    SolutionVersion,
    SolutionListResponse,
    SolutionResponse,
)
from zhangwen.solutions.repository import SolutionRepository

router = APIRouter(prefix="/api/projects", tags=["solutions"])
credential_store_factory = BackendCredentialStore
provider_factory = DeepSeekProvider


@router.get("/{project_id}/solution", response_model=SolutionListResponse)
async def list_solutions(project_id: str) -> SolutionListResponse:
    repo = _repo()
    repo.get_workspace(project_id)  # verify project exists
    solutions = SolutionRepository(repo.db_path).list_solutions(project_id)
    return SolutionListResponse(solutions=solutions)


@router.get("/{project_id}/solution/current", response_model=SolutionResponse)
async def get_current_solution(project_id: str) -> SolutionResponse:
    repo = _repo()
    repo.get_workspace(project_id)
    solution = SolutionRepository(repo.db_path).get_current_solution(project_id)
    if solution is None:
        raise HTTPException(status_code=404, detail={
            "code": "SOLUTION_NOT_FOUND",
            "message": "当前项目还没有方案，请先在中央对话中选择生成推荐实现方案。",
            "retryable": False,
        })
    return SolutionResponse(solution=solution)


@router.post("/{project_id}/solution/revise", response_model=ReviseSolutionResponse)
async def revise_solution(
    project_id: str,
    request: ReviseSolutionRequest,
) -> ReviseSolutionResponse:
    repo = _repo()
    repo.get_workspace(project_id)
    sol_repo = SolutionRepository(repo.db_path)
    base = (
        sol_repo.get_solution(project_id, request.baseSolutionId)
        if request.baseSolutionId
        else sol_repo.get_current_solution(project_id)
    )
    if base is None:
        raise HTTPException(status_code=422, detail={
            "code": "SOLUTION_REVISE_FAILED",
            "message": "当前还没有可修改的推荐实现方案。",
            "retryable": True,
        })
    try:
        config, api_key = _get_llm_config()
        service = ClarificationService(provider_factory())
        draft = await service.revise_solution(
            context_messages=_revision_context(base, request.userInstruction),
            config=config,
            api_key=api_key,
        )
        solution, revision = sol_repo.create_revision_from_llm(
            project_id,
            base=base,
            revised_sections=_merge_revised_sections(base, draft.revisedSolution.sections),
            user_request=request.userInstruction,
            changed_sections=[
                SolutionSectionChange(**change.model_dump(mode="json"))
                for change in draft.changedSections
            ],
            preserved_sections=draft.preservedSections,
            impact_summary=draft.impactSummary,
        )
    except StructuredLLMError as exc:
        raise llm_http_exception(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={
            "code": "SOLUTION_REVISE_FAILED",
            "message": str(exc),
            "retryable": True,
        }) from exc

    ProposalRepository(repo.db_path).mark_project_proposals_stale(
        project_id,
        "推荐实现方案已修订，立项书需在确认新方案后更新。",
    )

    from datetime import UTC, datetime
    now = datetime.now(UTC).isoformat()
    with repo._connect() as conn:
        conn.execute(
            "UPDATE projects SET stage = ?, updated_at = ? WHERE id = ?",
            (ProjectStage.SOLUTION_DRAFT.value, now, project_id),
        )

    return ReviseSolutionResponse(solution=solution, revision=revision)


@router.post("/{project_id}/solution/restore-previous", response_model=RestoreSolutionResponse)
async def restore_previous_solution(project_id: str) -> RestoreSolutionResponse:
    repo = _repo()
    repo.get_workspace(project_id)
    try:
        solution = SolutionRepository(repo.db_path).restore_previous_solution(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={
            "code": "SOLUTION_RESTORE_FAILED",
            "message": str(exc),
            "retryable": False,
        }) from exc

    from datetime import UTC, datetime
    now = datetime.now(UTC).isoformat()
    with repo._connect() as conn:
        conn.execute(
            "UPDATE projects SET stage = ?, updated_at = ? WHERE id = ?",
            (ProjectStage.SOLUTION_DRAFT.value, now, project_id),
        )
    return RestoreSolutionResponse(solution=solution)


@router.post("/{project_id}/solution/generate", response_model=SolutionResponse)
async def generate_solution(
    project_id: str, request: GenerateSolutionRequest | None = None,
) -> SolutionResponse:
    repo = _repo()
    workspace = repo.get_workspace(project_id)
    component_ids = request.componentIds if request else []
    if component_ids:
        validation = validate_component_ids(component_ids)
        if validation.overall == ValidationSeverity.FAIL:
            raise HTTPException(status_code=422, detail={
                "code": "HARDWARE_VALIDATION_FAILED",
                "message": validation.message,
                "checks": [
                    check.model_dump(mode="json")
                    for check in validation.checks
                    if check.severity == ValidationSeverity.FAIL
                ],
                "retryable": False,
            })

    revision_msg = request.revisionMessage if request else None
    try:
        config, api_key = _get_llm_config()
        service = ClarificationService(provider_factory())
        draft = await service.generate_solution(
            context_messages=workspace.conversation.messages,
            revision_message=revision_msg,
            config=config,
            api_key=api_key,
        )
    except StructuredLLMError as exc:
        raise llm_http_exception(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={
            "code": "SOLUTION_GENERATE_FAILED",
            "message": str(exc),
            "retryable": True,
        }) from exc

    sections = _solution_sections(draft.sections)

    sol_repo = SolutionRepository(repo.db_path)
    solution = sol_repo.create_solution(project_id, sections)
    ProposalRepository(repo.db_path).mark_project_proposals_stale(
        project_id,
        "推荐实现方案已生成新版本。",
    )

    # Update stage to SOLUTION_DRAFT
    from datetime import UTC, datetime
    now = datetime.now(UTC).isoformat()
    with repo._connect() as conn:
        conn.execute(
            "UPDATE projects SET stage = ?, updated_at = ? WHERE id = ?",
            (ProjectStage.SOLUTION_DRAFT.value, now, project_id),
        )

    return SolutionResponse(solution=solution)


@router.post("/{project_id}/solution/confirm", response_model=ConfirmSolutionResponse)
async def confirm_solution(
    project_id: str, request: ConfirmSolutionRequest,
) -> ConfirmSolutionResponse:
    repo = _repo()
    repo.get_workspace(project_id)
    sol_repo = SolutionRepository(repo.db_path)

    try:
        solution = sol_repo.confirm_solution(project_id, request.solutionId)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={
            "code": "SOLUTION_NOT_FOUND",
            "message": str(exc),
            "retryable": False,
        }) from exc

    # Update stage to SOLUTION_CONFIRMED
    from datetime import UTC, datetime
    now = datetime.now(UTC).isoformat()
    with repo._connect() as conn:
        conn.execute(
            "UPDATE projects SET stage = ?, updated_at = ? WHERE id = ?",
            (ProjectStage.SOLUTION_CONFIRMED.value, now, project_id),
        )

    return ConfirmSolutionResponse(solution=solution)


def _repo() -> ProjectRepository:
    return ProjectRepository(settings.data_dir)


def _get_llm_config():
    return require_llm_config(
        data_dir=settings.data_dir,
        credential_store=credential_store_factory(),
        credential_service=settings.credential_service,
        credential_account=settings.credential_account,
    )


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


def _solution_sections(sections) -> list[SolutionSection]:
    normalized = [
        SolutionSection(
            id=_normalize_section_id(section.id),
            title=section.title,
            content=section.content,
        )
        for section in sections
        if section.content.strip()
    ]
    if not normalized:
        raise ValueError("云端模型没有返回可保存的方案章节，请重试。")
    return normalized


def _merge_revised_sections(base: SolutionVersion, revised_sections) -> list[SolutionSection]:
    revised_by_id = {
        _normalize_section_id(section.id): SolutionSection(
            id=_normalize_section_id(section.id),
            title=section.title,
            content=section.content,
        )
        for section in revised_sections
        if section.content.strip()
    }
    merged: list[SolutionSection] = []
    seen: set[str] = set()
    for base_section in base.sections:
        normalized_id = _normalize_section_id(base_section.id)
        merged.append(revised_by_id.get(normalized_id, base_section))
        seen.add(normalized_id)
    for section_id, section in revised_by_id.items():
        if section_id not in seen:
            merged.append(section)
    if not merged:
        raise ValueError("云端模型没有返回可保存的修订方案，请重试。")
    return merged


def _revision_context(base: SolutionVersion, user_instruction: str) -> list[ChatMessage]:
    payload = {
        "baseSolution": {
            "id": base.id,
            "version": base.version,
            "status": base.status.value,
            "sections": [section.model_dump(mode="json") for section in base.sections],
        },
        "userInstruction": user_instruction,
        "rule": "请基于 baseSolution 修订，保留未受影响章节，并返回完整 revisedSolution。",
    }
    return [
        ChatMessage(
            id="solution_revision_request",
            role=ChatRole.USER,
            content="以下是本次方案修订请求 JSON：\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}",
            status=ChatMessageStatus.READY,
            createdAt="",
            updatedAt="",
        )
    ]


def _normalize_section_id(section_id: str) -> str:
    key = section_id.strip().lower().replace("-", "_")
    return SECTION_ID_ALIASES.get(key, key)
