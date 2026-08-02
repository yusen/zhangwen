"""Orchestrator and Agent Registry HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from zhangwen.config import settings
from zhangwen.orchestrator.models import (
    AgentRegistryResponse,
    ApprovalRequest,
    CreateExecutionPlanRequest,
    ExecutionPlan,
    ExecutionPlanResponse,
    PlanActionRequest,
)
from zhangwen.orchestrator.registry import AgentRegistry
from zhangwen.orchestrator.repository import OrchestratorRepository
from zhangwen.orchestrator.service import OrchestratorService
from zhangwen.projects.models import ProjectStage
from zhangwen.projects.repository import ProjectRepository
from zhangwen.proposals.repository import ProposalRepository

router = APIRouter(prefix="/api", tags=["orchestrator"])


@router.get("/agents", response_model=AgentRegistryResponse)
async def list_agents() -> AgentRegistryResponse:
    return AgentRegistryResponse(agents=AgentRegistry().list_agents())


@router.get(
    "/projects/{project_id}/execution-plan/current",
    response_model=ExecutionPlanResponse,
)
async def get_current_plan(project_id: str) -> ExecutionPlanResponse:
    repo = _project_repo()
    repo.get_workspace(project_id)
    plan = OrchestratorRepository(repo.db_path).get_current_plan(project_id)
    if plan is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "EXECUTION_PLAN_NOT_FOUND",
                "message": "当前项目还没有执行计划。",
                "retryable": False,
            },
        )
    return ExecutionPlanResponse(plan=plan)


@router.post(
    "/projects/{project_id}/execution-plan",
    response_model=ExecutionPlanResponse,
)
async def create_execution_plan(
    project_id: str,
    request: CreateExecutionPlanRequest,
) -> ExecutionPlanResponse:
    repo = _project_repo()
    repo.get_workspace(project_id)
    proposal = ProposalRepository(repo.db_path).get_proposal(project_id, request.proposalId)
    try:
        plan = OrchestratorService(
            OrchestratorRepository(repo.db_path)
        ).create_plan(project_id, proposal)
    except ValueError as exc:
        raise _unprocessable("EXECUTION_PLAN_CREATE_FAILED", str(exc)) from exc
    _update_stage(repo, project_id, ProjectStage.EXECUTION_PLANNED)
    return ExecutionPlanResponse(plan=plan)


@router.post(
    "/projects/{project_id}/execution-plan/{plan_id}/start",
    response_model=ExecutionPlanResponse,
)
async def start_execution_plan(
    project_id: str,
    plan_id: str,
) -> ExecutionPlanResponse:
    return _mutate_plan(project_id, plan_id, lambda service, plan: service.start_plan(plan))


@router.post(
    "/projects/{project_id}/execution-plan/{plan_id}/pause",
    response_model=ExecutionPlanResponse,
)
async def pause_execution_plan(
    project_id: str,
    plan_id: str,
) -> ExecutionPlanResponse:
    return _mutate_plan(project_id, plan_id, lambda service, plan: service.pause_plan(plan))


@router.post(
    "/projects/{project_id}/execution-plan/{plan_id}/resume",
    response_model=ExecutionPlanResponse,
)
async def resume_execution_plan(
    project_id: str,
    plan_id: str,
) -> ExecutionPlanResponse:
    return _mutate_plan(project_id, plan_id, lambda service, plan: service.resume_plan(plan))


@router.post(
    "/projects/{project_id}/execution-plan/{plan_id}/retry",
    response_model=ExecutionPlanResponse,
)
async def retry_execution_plan(
    project_id: str,
    plan_id: str,
    request: PlanActionRequest | None = None,
) -> ExecutionPlanResponse:
    return _mutate_plan(
        project_id,
        plan_id,
        lambda service, plan: service.retry_node(plan, request.nodeId if request else None),
    )


@router.post(
    "/projects/{project_id}/execution-plan/{plan_id}/approve",
    response_model=ExecutionPlanResponse,
)
async def approve_execution_node(
    project_id: str,
    plan_id: str,
    request: ApprovalRequest,
) -> ExecutionPlanResponse:
    return _mutate_plan(
        project_id,
        plan_id,
        lambda service, plan: service.approve_node(
            plan,
            request.nodeId,
            request.approved,
            request.comment,
        ),
    )


def _mutate_plan(project_id: str, plan_id: str, mutator) -> ExecutionPlanResponse:
    repo = _project_repo()
    repo.get_workspace(project_id)
    orch_repo = OrchestratorRepository(repo.db_path)
    try:
        plan = orch_repo.get_plan(project_id, plan_id)
        updated = mutator(OrchestratorService(orch_repo), plan)
    except ValueError as exc:
        raise _unprocessable("EXECUTION_PLAN_ACTION_FAILED", str(exc)) from exc
    return ExecutionPlanResponse(plan=updated)


def _project_repo() -> ProjectRepository:
    return ProjectRepository(settings.data_dir)


def _unprocessable(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={
            "code": code,
            "message": message,
            "retryable": False,
        },
    )


def _update_stage(repo: ProjectRepository, project_id: str, stage: ProjectStage) -> None:
    from datetime import UTC, datetime

    now = datetime.now(UTC).isoformat()
    with repo._connect() as conn:
        conn.execute(
            "UPDATE projects SET stage = ?, updated_at = ? WHERE id = ?",
            (stage.value, now, project_id),
        )
