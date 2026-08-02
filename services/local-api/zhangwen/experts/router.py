"""Agent Skill package configuration routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from zhangwen.config import settings
from zhangwen.experts.packages import (
    AgentPackageConflictError,
    AgentPackageListResponse,
    AgentPackageNotFoundError,
    AgentPackageRepository,
    AgentPackageResponse,
    AgentPackageValidationError,
    ResetAgentPackageFileRequest,
    UpdateAgentPackageFileRequest,
)
from zhangwen.projects.models import ExpertType


router = APIRouter(prefix="/api/agent-packages", tags=["agent-packages"])


@router.get("", response_model=AgentPackageListResponse)
async def list_agent_packages() -> AgentPackageListResponse:
    return AgentPackageListResponse(packages=_repository().list_packages())


@router.get("/{expert_type}", response_model=AgentPackageResponse)
async def get_agent_package(expert_type: ExpertType) -> AgentPackageResponse:
    return AgentPackageResponse(package=_repository().get_package(expert_type))


@router.put("/{expert_type}/files", response_model=AgentPackageResponse)
async def update_agent_package_file(
    expert_type: ExpertType,
    request: UpdateAgentPackageFileRequest,
) -> AgentPackageResponse:
    try:
        package = _repository().update_file(
            expert_type,
            path=request.path,
            content=request.content,
            expected_revision=request.expectedRevision,
        )
    except AgentPackageConflictError as exc:
        raise _http_error(409, "AGENT_PACKAGE_REVISION_CONFLICT", str(exc)) from exc
    except AgentPackageValidationError as exc:
        raise _http_error(422, "AGENT_PACKAGE_INVALID", str(exc)) from exc
    except AgentPackageNotFoundError as exc:
        raise _http_error(404, "AGENT_PACKAGE_NOT_FOUND", str(exc)) from exc
    return AgentPackageResponse(package=package)


@router.post("/{expert_type}/files/reset", response_model=AgentPackageResponse)
async def reset_agent_package_file(
    expert_type: ExpertType,
    request: ResetAgentPackageFileRequest,
) -> AgentPackageResponse:
    try:
        package = _repository().reset_file(
            expert_type,
            path=request.path,
            expected_revision=request.expectedRevision,
        )
    except AgentPackageConflictError as exc:
        raise _http_error(409, "AGENT_PACKAGE_REVISION_CONFLICT", str(exc)) from exc
    except AgentPackageValidationError as exc:
        raise _http_error(422, "AGENT_PACKAGE_INVALID", str(exc)) from exc
    except AgentPackageNotFoundError as exc:
        raise _http_error(404, "AGENT_PACKAGE_NOT_FOUND", str(exc)) from exc
    return AgentPackageResponse(package=package)


def _repository() -> AgentPackageRepository:
    return AgentPackageRepository(settings.data_dir)


def _http_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={"code": code, "message": message, "retryable": status == 409},
    )
