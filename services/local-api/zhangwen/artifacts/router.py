"""Artifact HTTP routes."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from zhangwen.artifacts.models import (
    ArtifactFileListResponse,
    ArtifactListResponse,
    ArtifactResponse,
)
from zhangwen.artifacts.repository import ArtifactRepository
from zhangwen.config import settings
from zhangwen.host import require_desktop_host
from zhangwen.projects.repository import ProjectRepository

router = APIRouter(prefix="/api/projects", tags=["artifacts"])


@router.get("/{project_id}/artifacts", response_model=ArtifactListResponse)
async def list_artifacts(project_id: str) -> ArtifactListResponse:
    repo = _project_repo()
    repo.get_workspace(project_id)
    artifacts = ArtifactRepository(repo.db_path).list_artifacts(project_id)
    return ArtifactListResponse(artifacts=artifacts)


@router.get("/{project_id}/artifacts/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact(project_id: str, artifact_id: str) -> ArtifactResponse:
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        artifact = ArtifactRepository(repo.db_path).get_artifact(project_id, artifact_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "ARTIFACT_NOT_FOUND",
                "message": str(exc),
                "retryable": False,
            },
        ) from exc
    return ArtifactResponse(artifact=artifact)


@router.get(
    "/{project_id}/artifacts/{artifact_id}/versions/{version_id}/files",
    response_model=ArtifactFileListResponse,
)
async def list_artifact_files(
    project_id: str,
    artifact_id: str,
    version_id: str,
    request: Request,
) -> ArtifactFileListResponse:
    require_desktop_host(request, "local_cad")
    repo = _project_repo()
    repo.get_workspace(project_id)
    files = ArtifactRepository(repo.db_path).list_artifact_files(
        project_id,
        artifact_id,
        version_id,
    )
    return ArtifactFileListResponse(files=files)


@router.get(
    "/{project_id}/artifacts/{artifact_id}/versions/{version_id}/files/{file_id}"
)
async def download_artifact_file(
    project_id: str,
    artifact_id: str,
    version_id: str,
    file_id: str,
    request: Request,
) -> FileResponse:
    require_desktop_host(request, "local_cad")
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        metadata, storage_key = ArtifactRepository(repo.db_path).get_artifact_file(
            project_id,
            artifact_id,
            version_id,
            file_id,
        )
        file_path = _artifact_file_path(storage_key)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "ARTIFACT_FILE_NOT_FOUND",
                "message": str(exc),
                "retryable": False,
            },
        ) from exc
    return FileResponse(
        file_path,
        media_type=metadata.mimeType,
        filename=metadata.fileName,
        headers={
            "ETag": f'"{metadata.sha256}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


def _project_repo() -> ProjectRepository:
    return ProjectRepository(settings.data_dir)


def _artifact_file_path(storage_key: str) -> Path:
    key = PurePosixPath(storage_key)
    if key.is_absolute() or not key.parts or any(part in {"", ".", ".."} for part in key.parts):
        raise ValueError("产物文件存储键无效。")
    root = (settings.data_dir / "artifact-files").resolve()
    candidate = root.joinpath(*key.parts)
    resolved = candidate.resolve(strict=True)
    if resolved != root and root not in resolved.parents:
        raise ValueError("产物文件路径越界。")
    for current in (resolved, *resolved.parents):
        if current == root.parent:
            break
        if current.is_symlink() or getattr(current, "is_junction", lambda: False)():
            raise ValueError("产物文件路径包含不受支持的链接。")
        if current == root:
            break
    if not resolved.is_file():
        raise ValueError("产物文件不存在。")
    return resolved
