"""Skill Registry and Model Router HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from zhangwen.config import settings
from zhangwen.projects.repository import ProjectRepository
from zhangwen.skills.model_router import ModelRouter
from zhangwen.skills.models import (
    CreateSkillRequest,
    ModelRouteRequest,
    ModelRouteResponse,
    SkillRegistryResponse,
    SkillResponse,
    SkillRunRequest,
    SkillRunResponse,
    UpdateSkillRequest,
)
from zhangwen.skills.repository import SkillRepository
from zhangwen.skills.runtime import SkillRuntime

router = APIRouter(prefix="/api", tags=["skills"])


@router.get("/skills", response_model=SkillRegistryResponse)
async def list_skills() -> SkillRegistryResponse:
    repo = _skill_repo()
    return SkillRegistryResponse(skills=repo.list_skills())


@router.post("/skills", response_model=SkillResponse)
async def create_skill(request: CreateSkillRequest) -> SkillResponse:
    skill = _skill_repo().create_user_skill(
        name=request.name,
        description=request.description,
        input_schema=request.inputSchema,
        output_schema=request.outputSchema,
        permissions=request.permissions,
        owner_expert=request.ownerExpert,
    )
    return SkillResponse(skill=skill)


@router.post("/skills/{skill_id}/run", response_model=SkillRunResponse)
async def run_skill(skill_id: str, request: SkillRunRequest) -> SkillRunResponse:
    try:
        run = await SkillRuntime(_project_repo().db_path).run(
            project_id=request.projectId,
            skill_id=skill_id,
            payload=request.input,
            expert_run_id=request.expertRunId,
            confirmed=request.confirmed,
            requesting_expert=request.requestingExpert,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "SKILL_RUN_INVALID",
                "message": str(exc),
                "retryable": False,
            },
        ) from exc
    return SkillRunResponse(run=run)


@router.patch("/skills/{skill_id}", response_model=SkillResponse)
async def update_skill(skill_id: str, request: UpdateSkillRequest) -> SkillResponse:
    try:
        skill = _skill_repo().update_skill(
            skill_id,
            name=request.name,
            description=request.description,
            enabled=request.enabled,
            permissions=request.permissions,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "SKILL_NOT_FOUND",
                "message": str(exc),
                "retryable": False,
            },
        ) from exc
    return SkillResponse(skill=skill)


@router.post("/model-router/route", response_model=ModelRouteResponse)
async def route_model(request: ModelRouteRequest) -> ModelRouteResponse:
    route = ModelRouter(_project_repo().db_path).route(
        agent_id=request.agentId,
        task_kind=request.taskKind,
        strategy=request.strategy,
    )
    return ModelRouteResponse(route=route)


def _project_repo() -> ProjectRepository:
    return ProjectRepository(settings.data_dir)


def _skill_repo() -> SkillRepository:
    return SkillRepository(_project_repo().db_path)
