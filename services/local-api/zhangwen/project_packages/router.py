"""Project package HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from zhangwen.config import settings
from zhangwen.project_packages.errors import ProjectPackageError
from zhangwen.project_packages.models import (
    ExportProjectPackageRequest,
    ExportProjectPackageResponse,
    ImportProjectPackageRequest,
    ImportProjectPackageResponse,
)
from zhangwen.project_packages.repository import ProjectPackageRepository
from zhangwen.projects.errors import ProjectError

router = APIRouter(prefix="/api/projects", tags=["project-packages"])


@router.post("/{project_id}/package/export", response_model=ExportProjectPackageResponse)
async def export_project_package(
    project_id: str,
    request: ExportProjectPackageRequest,
) -> ExportProjectPackageResponse:
    try:
        package = ProjectPackageRepository(settings.data_dir).export_project(
            project_id,
            request,
        )
        return ExportProjectPackageResponse(package=package)
    except (ProjectError, ProjectPackageError) as exc:
        raise _http_error(exc) from exc


@router.post("/package/import", response_model=ImportProjectPackageResponse)
async def import_project_package(
    request: ImportProjectPackageRequest,
) -> ImportProjectPackageResponse:
    try:
        package, workspace = ProjectPackageRepository(settings.data_dir).import_project(
            request,
        )
        return ImportProjectPackageResponse(package=package, workspace=workspace)
    except (ProjectError, ProjectPackageError) as exc:
        raise _http_error(exc) from exc


def _http_error(exc: ProjectError | ProjectPackageError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={
            "code": exc.code,
            "message": exc.message,
            "userActions": [{"id": "retry", "label": "重试"}],
            "retryable": exc.status_code >= 500,
        },
    )
