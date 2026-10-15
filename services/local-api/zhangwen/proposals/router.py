"""Proposal HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response

from zhangwen.config import settings
from zhangwen.device_lab.scene import materialize_device_lab_scene
from zhangwen.llm.deepseek import DeepSeekProvider
from zhangwen.llm.http import llm_http_exception
from zhangwen.llm.runtime import require_llm_config
from zhangwen.settings.models import ModelWorkload
from zhangwen.llm.structured import StructuredLLMError
from zhangwen.projects.models import ProjectStage
from zhangwen.projects.repository import ProjectRepository
from zhangwen.proposals.exporter import render_docx, render_markdown, render_pdf
from zhangwen.proposals.models import (
    ConfirmProposalRequest,
    ConfirmProposalResponse,
    GenerateProposalRequest,
    ProposalExportFormat,
    ProposalListResponse,
    ProposalResponse,
    RejectProposalRequest,
    RejectProposalResponse,
    ReviseProposalRequest,
)
from zhangwen.proposals.repository import ProposalRepository
from zhangwen.proposals.service import ProposalGenerationService
from zhangwen.security.credentials import BackendCredentialStore
from zhangwen.skills.model_router import ModelRouter
from zhangwen.skills.models import ModelRouteStrategy
from zhangwen.solutions.models import SolutionStatus
from zhangwen.solutions.repository import SolutionRepository

router = APIRouter(prefix="/api/projects", tags=["proposals"])
credential_store_factory = BackendCredentialStore
provider_factory = DeepSeekProvider


@router.get("/{project_id}/proposal", response_model=ProposalListResponse)
async def list_proposals(project_id: str) -> ProposalListResponse:
    repo = _project_repo()
    repo.get_workspace(project_id)
    proposals = ProposalRepository(repo.db_path).list_proposals(project_id)
    return ProposalListResponse(proposals=proposals)


@router.get("/{project_id}/proposal/current", response_model=ProposalResponse)
async def get_current_proposal(project_id: str) -> ProposalResponse:
    repo = _project_repo()
    repo.get_workspace(project_id)
    proposal = ProposalRepository(repo.db_path).get_current_proposal(project_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail={
            "code": "PROPOSAL_NOT_FOUND",
            "message": "当前项目还没有立项书。",
            "retryable": False,
        })
    return ProposalResponse(proposal=proposal)


@router.post("/{project_id}/proposal/generate", response_model=ProposalResponse)
async def generate_proposal(
    project_id: str,
    request: GenerateProposalRequest,
) -> ProposalResponse:
    repo = _project_repo()
    repo.get_workspace(project_id)
    solution = _confirmed_solution(repo.db_path, project_id, request.solutionId)
    try:
        config, api_key = _llm_config()
        route = ModelRouter(repo.db_path).route(
            agent_id="proposal_generator",
            task_kind="proposal_generation",
            strategy=ModelRouteStrategy.QUALITY_FIRST,
        )
        sections = await ProposalGenerationService(provider_factory()).generate(
            solution=solution,
            config=config,
            api_key=api_key,
            model=route.model,
        )
        proposal = ProposalRepository(repo.db_path).create_from_solution(
            project_id,
            solution,
            sections,
        )
    except StructuredLLMError as exc:
        raise llm_http_exception(exc) from exc
    _update_stage(repo, project_id, ProjectStage.PROPOSAL_DRAFT)
    return ProposalResponse(proposal=proposal)


@router.post("/{project_id}/proposal/revise", response_model=ProposalResponse)
async def revise_proposal(
    project_id: str,
    request: ReviseProposalRequest,
) -> ProposalResponse:
    repo = _project_repo()
    repo.get_workspace(project_id)
    proposal_repo = ProposalRepository(repo.db_path)
    current = proposal_repo.get_proposal(project_id, request.proposalId)
    try:
        config, api_key = _llm_config()
        route = ModelRouter(repo.db_path).route(
            agent_id="proposal_generator",
            task_kind="proposal_revision",
            strategy=ModelRouteStrategy.QUALITY_FIRST,
        )
        sections = await ProposalGenerationService(provider_factory()).revise(
            proposal=current,
            revision_message=request.revisionMessage,
            config=config,
            api_key=api_key,
            model=route.model,
        )
        proposal = proposal_repo.revise_proposal(
            project_id,
            request.proposalId,
            sections,
        )
    except StructuredLLMError as exc:
        raise llm_http_exception(exc) from exc
    _update_stage(repo, project_id, ProjectStage.PROPOSAL_DRAFT)
    return ProposalResponse(proposal=proposal)


@router.post("/{project_id}/proposal/confirm", response_model=ConfirmProposalResponse)
async def confirm_proposal(
    project_id: str,
    request: ConfirmProposalRequest,
) -> ConfirmProposalResponse:
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        proposal = ProposalRepository(repo.db_path).confirm_proposal(
            project_id,
            request.proposalId,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={
            "code": "PROPOSAL_CONFIRM_FAILED",
            "message": str(exc),
            "retryable": False,
        }) from exc
    materialize_device_lab_scene(repo.db_path, settings.data_dir, project_id)
    _update_stage(repo, project_id, ProjectStage.PROPOSAL_CONFIRMED)
    return ConfirmProposalResponse(proposal=proposal)


@router.post("/{project_id}/proposal/reject", response_model=RejectProposalResponse)
async def reject_proposal(
    project_id: str,
    request: RejectProposalRequest,
) -> RejectProposalResponse:
    repo = _project_repo()
    repo.get_workspace(project_id)
    proposal = ProposalRepository(repo.db_path).reject_proposal(
        project_id,
        request.proposalId,
        request.reason,
    )
    _update_stage(repo, project_id, ProjectStage.SOLUTION_CONFIRMED)
    return RejectProposalResponse(proposal=proposal)


@router.get("/{project_id}/proposal/{proposal_id}/export")
async def export_proposal(
    project_id: str,
    proposal_id: str,
    format: ProposalExportFormat = Query(ProposalExportFormat.MARKDOWN),
) -> Response:
    repo = _project_repo()
    repo.get_workspace(project_id)
    proposal = ProposalRepository(repo.db_path).get_proposal(project_id, proposal_id)
    if format == ProposalExportFormat.DOCX:
        return Response(
            content=render_docx(proposal),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{proposal.id}.docx"'},
        )
    if format == ProposalExportFormat.PDF:
        return Response(
            content=render_pdf(proposal),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{proposal.id}.pdf"'},
        )
    return Response(
        content=render_markdown(proposal),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{proposal.id}.md"'},
    )


def _project_repo() -> ProjectRepository:
    return ProjectRepository(settings.data_dir)


def _llm_config():
    return require_llm_config(
        data_dir=settings.data_dir,
        credential_store=credential_store_factory(),
        credential_service=settings.credential_service,
        credential_account=settings.credential_account,
        workload=ModelWorkload.ENGINEERING,
    )


def _confirmed_solution(db_path, project_id: str, solution_id: str):
    try:
        solution = SolutionRepository(db_path).get_solution(project_id, solution_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={
            "code": "SOLUTION_NOT_FOUND",
            "message": str(exc),
            "retryable": False,
        }) from exc
    if solution.status != SolutionStatus.CONFIRMED:
        raise HTTPException(status_code=422, detail={
            "code": "PROPOSAL_REQUIRES_CONFIRMED_SOLUTION",
            "message": "只有已确认方案可以生成立项书。",
            "retryable": False,
        })
    return solution


def _update_stage(repo: ProjectRepository, project_id: str, stage: ProjectStage) -> None:
    from datetime import UTC, datetime

    now = datetime.now(UTC).isoformat()
    with repo._connect() as conn:
        conn.execute(
            "UPDATE projects SET stage = ?, updated_at = ? WHERE id = ?",
            (stage.value, now, project_id),
        )
