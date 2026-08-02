"""MVP readiness HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from zhangwen.config import settings
from zhangwen.mvp.models import MvpReadinessResponse
from zhangwen.mvp.repository import MvpReadinessRepository
from zhangwen.projects.errors import ProjectError
from zhangwen.projects.progress import ProjectProgressRepository, ProjectProgressResponse

router = APIRouter(prefix="/api", tags=["mvp"])


@router.get(
    "/projects/{project_id}/mvp/readiness",
    response_model=MvpReadinessResponse,
)
async def get_mvp_readiness(project_id: str) -> MvpReadinessResponse:
    try:
        readiness = MvpReadinessRepository(settings.data_dir).build_report(project_id)
        return MvpReadinessResponse(readiness=readiness)
    except ProjectError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "code": exc.code,
                "message": exc.message,
                "userActions": [{"id": "retry", "label": "重试"}],
                "retryable": exc.status_code >= 500,
            },
        ) from exc


@router.get(
    "/projects/{project_id}/progress",
    response_model=ProjectProgressResponse,
)
async def get_project_progress(project_id: str) -> ProjectProgressResponse:
    try:
        return ProjectProgressResponse(
            progress=ProjectProgressRepository(settings.data_dir).build_snapshot(project_id)
        )
    except ProjectError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "code": exc.code,
                "message": exc.message,
                "userActions": [{"id": "retry", "label": "重试"}],
                "retryable": exc.status_code >= 500,
            },
        ) from exc
