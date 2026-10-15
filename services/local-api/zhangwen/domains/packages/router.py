"""Local-only HTTP API for the unified capability package platform."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from zhangwen.config import settings
from zhangwen.domains.packages.models import (
    CreatePackageWorkspaceRequest,
    PackageDetailResponse,
    PackageInputListResponse,
    PackageKind,
    PackageListResponse,
    PackagePlatformError,
    PackagePublishResponse,
    PackageReplayRequest,
    PackageReplayResult,
    PackageShadowRequest,
    PackageShadowResult,
    PackageWorkspaceResponse,
    PublishPackageWorkspaceRequest,
    RollbackPackageRequest,
    SavePackageWorkspaceRequest,
)
from zhangwen.domains.packages.service import PackagePlatformService


router = APIRouter(prefix="/api", tags=["capability-packages"])


@router.get("/packages", response_model=PackageListResponse)
def list_packages(
    kind: PackageKind | None = Query(default=None),
) -> PackageListResponse:
    try:
        return _service().list_packages(kind)
    except PackagePlatformError as exc:
        raise _http_error(exc) from exc


@router.get("/packages/{package_id}", response_model=PackageDetailResponse)
def package_detail(package_id: str) -> PackageDetailResponse:
    try:
        return _service().detail(package_id)
    except PackagePlatformError as exc:
        raise _http_error(exc) from exc


@router.get(
    "/packages/{package_id}/inputs",
    response_model=PackageInputListResponse,
)
def package_inputs(package_id: str) -> PackageInputListResponse:
    try:
        return PackageInputListResponse(inputs=_service().inputs(package_id))
    except PackagePlatformError as exc:
        raise _http_error(exc) from exc


@router.post(
    "/package-workspaces",
    response_model=PackageWorkspaceResponse,
    status_code=201,
)
def create_package_workspace(
    request: CreatePackageWorkspaceRequest,
) -> PackageWorkspaceResponse:
    try:
        workspace = _service().create_workspace(
            package_id=request.package_id,
            kind=request.kind,
            slug=request.slug,
            display_name=request.display_name,
        )
        return PackageWorkspaceResponse(workspace=workspace)
    except PackagePlatformError as exc:
        raise _http_error(exc) from exc


@router.get(
    "/package-workspaces/{workspace_id}",
    response_model=PackageWorkspaceResponse,
)
def package_workspace(workspace_id: str) -> PackageWorkspaceResponse:
    try:
        return PackageWorkspaceResponse(workspace=_service().workspace(workspace_id))
    except PackagePlatformError as exc:
        raise _http_error(exc) from exc


@router.put(
    "/package-workspaces/{workspace_id}/files/batch",
    response_model=PackageWorkspaceResponse,
)
def save_package_workspace(
    workspace_id: str,
    request: SavePackageWorkspaceRequest,
) -> PackageWorkspaceResponse:
    try:
        workspace = _service().save(
            workspace_id,
            expected_revision=request.expected_revision,
            files=request.files,
        )
        return PackageWorkspaceResponse(workspace=workspace)
    except PackagePlatformError as exc:
        raise _http_error(exc) from exc


@router.post(
    "/package-workspaces/{workspace_id}/validate",
    response_model=PackageWorkspaceResponse,
)
def validate_package_workspace(workspace_id: str) -> PackageWorkspaceResponse:
    try:
        return PackageWorkspaceResponse(workspace=_service().validate(workspace_id))
    except PackagePlatformError as exc:
        raise _http_error(exc) from exc


@router.post(
    "/package-workspaces/{workspace_id}/replay",
    response_model=PackageReplayResult,
)
def replay_package_workspace(
    workspace_id: str,
    request: PackageReplayRequest,
) -> PackageReplayResult:
    try:
        return _service().replay(workspace_id, request.turn_id)
    except PackagePlatformError as exc:
        raise _http_error(exc) from exc


@router.post(
    "/package-workspaces/{workspace_id}/shadow-run",
    response_model=PackageShadowResult,
)
def shadow_package_workspace(
    workspace_id: str,
    request: PackageShadowRequest,
) -> PackageShadowResult:
    try:
        return _service().shadow(workspace_id, request.turn_id)
    except PackagePlatformError as exc:
        raise _http_error(exc) from exc


@router.post(
    "/package-workspaces/{workspace_id}/publish",
    response_model=PackagePublishResponse,
)
def publish_package_workspace(
    workspace_id: str,
    request: PublishPackageWorkspaceRequest,
) -> PackagePublishResponse:
    try:
        return _service().publish(
            workspace_id,
            expected_revision=request.expected_revision,
            confirmed=request.confirmed,
        )
    except PackagePlatformError as exc:
        raise _http_error(exc) from exc


@router.post(
    "/packages/{package_id}/rollback",
    response_model=PackagePublishResponse,
)
def rollback_package(
    package_id: str,
    request: RollbackPackageRequest,
) -> PackagePublishResponse:
    try:
        return _service().rollback(
            package_id,
            target_revision_id=request.target_revision_id,
            expected_revision=request.expected_revision,
            confirmed=request.confirmed,
        )
    except PackagePlatformError as exc:
        raise _http_error(exc) from exc


def _service() -> PackagePlatformService:
    return PackagePlatformService(settings.data_dir)


def _http_error(exc: PackagePlatformError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={
            "code": exc.code,
            "message": str(exc),
            "retryable": exc.retryable,
        },
    )
