"""V2 Project Kernel HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from zhangwen.config import settings
from zhangwen.host import require_desktop_host
from zhangwen.projects.errors import ProjectError
from zhangwen.v2.kernel import ProjectKernel, ProjectKernelError
from zhangwen.v2.cad_intent import (
    CadIntentError,
    CadIntentPromptRequest,
    CadIntentService,
    CadIntentUndoRequest,
)
from zhangwen.v2.models import (
    CapabilityCoverageResponse,
    CapabilityListResponse,
    ChangeSetListResponse,
    ChangeSetResponse,
    CreateChangeSetRequest,
    CreateReleaseRequest,
    ProjectReleaseListResponse,
    ProjectStateResponse,
    ProjectVersionListResponse,
)

router = APIRouter(prefix="/api/v2/projects", tags=["v2-project-kernel"])


@router.get("/{project_id}/state", response_model=ProjectStateResponse)
async def project_state(project_id: str) -> ProjectStateResponse:
    return ProjectStateResponse(state=_call(lambda kernel: kernel.project_state(project_id)))


@router.get("/{project_id}/changesets", response_model=ChangeSetListResponse)
async def list_change_sets(project_id: str) -> ChangeSetListResponse:
    return ChangeSetListResponse(
        changeSets=_call(lambda kernel: kernel.list_change_sets(project_id))
    )


@router.post("/{project_id}/changesets", response_model=ChangeSetResponse)
async def create_change_set(
    project_id: str, request: CreateChangeSetRequest
) -> ChangeSetResponse:
    return ChangeSetResponse(
        changeSet=_call(lambda kernel: kernel.create_change_set(project_id, request))
    )


@router.post(
    "/{project_id}/changesets/{change_set_id}/confirm",
    response_model=ChangeSetResponse,
)
async def confirm_change_set(project_id: str, change_set_id: str) -> ChangeSetResponse:
    return ChangeSetResponse(
        changeSet=_call(
            lambda kernel: kernel.confirm_change_set(project_id, change_set_id)
        )
    )


@router.post(
    "/{project_id}/changesets/{change_set_id}/commit",
)
async def commit_change_set(project_id: str, change_set_id: str) -> dict[str, object]:
    return {
        "version": _call(
            lambda kernel: kernel.commit_change_set(project_id, change_set_id)
        )
    }


@router.get("/{project_id}/versions", response_model=ProjectVersionListResponse)
async def list_versions(project_id: str) -> ProjectVersionListResponse:
    return ProjectVersionListResponse(
        versions=_call(lambda kernel: kernel.list_versions(project_id))
    )


@router.get("/{project_id}/releases", response_model=ProjectReleaseListResponse)
async def list_releases(project_id: str) -> ProjectReleaseListResponse:
    return ProjectReleaseListResponse(
        releases=_call(lambda kernel: kernel.list_releases(project_id))
    )


@router.post("/{project_id}/releases")
async def create_release(
    project_id: str, request: CreateReleaseRequest
) -> dict[str, object]:
    return {
        "release": _call(lambda kernel: kernel.create_release(project_id, request))
    }


@router.get("/{project_id}/capabilities", response_model=CapabilityListResponse)
async def list_capabilities(project_id: str) -> CapabilityListResponse:
    return CapabilityListResponse(
        capabilities=_call(lambda kernel: kernel.list_capabilities(project_id))
    )


@router.get(
    "/{project_id}/capability-coverage", response_model=CapabilityCoverageResponse
)
async def capability_coverage(project_id: str) -> CapabilityCoverageResponse:
    return CapabilityCoverageResponse(
        coverage=_call(lambda kernel: kernel.capability_coverage(project_id))
    )


@router.get("/{project_id}/cad/workspace")
async def cad_workspace(project_id: str) -> dict[str, object]:
    return {"workspace": _cad_call(lambda service: service.workspace(project_id))}


@router.post("/{project_id}/cad/intent")
async def cad_intent(
    project_id: str,
    payload: CadIntentPromptRequest,
    request: Request,
) -> dict[str, object]:
    require_desktop_host(request, "local_cad")
    return _cad_call(lambda service: service.submit(project_id, payload))


@router.post("/{project_id}/cad/revisions/{revision_id}/confirm")
async def confirm_cad_revision(
    project_id: str,
    revision_id: str,
    request: Request,
) -> dict[str, object]:
    require_desktop_host(request, "local_cad")
    return {
        "revision": _cad_call(
            lambda service: service.confirm_revision(project_id, revision_id)
        )
    }


@router.post("/{project_id}/cad/revisions/{revision_id}/build")
async def build_cad_revision(
    project_id: str,
    revision_id: str,
    request: Request,
) -> dict[str, object]:
    require_desktop_host(request, "local_cad")
    return {
        "result": _cad_call(
            lambda service: service.build_revision(project_id, revision_id)
        )
    }


@router.post("/{project_id}/cad/revisions/{revision_id}/undo")
async def undo_cad_revision(
    project_id: str,
    revision_id: str,
    payload: CadIntentUndoRequest,
    request: Request,
) -> dict[str, object]:
    require_desktop_host(request, "local_cad")
    return {
        "revision": _cad_call(
            lambda service: service.plan_undo(
                project_id, revision_id, payload.baseProjectVersion
            )
        )
    }


def _call(action):
    try:
        return action(ProjectKernel(settings.data_dir))
    except (ProjectKernelError, ProjectError) as exc:
        raise HTTPException(
            status_code=getattr(exc, "status_code", 400),
            detail={
                "code": getattr(exc, "code", "PROJECT_KERNEL_ERROR"),
                "message": getattr(exc, "message", str(exc)),
                "retryable": getattr(exc, "status_code", 400) >= 500,
                "userActions": [{"id": "retry", "label": "重试"}],
            },
        ) from exc


def _cad_call(action):
    try:
        return action(CadIntentService(settings.data_dir))
    except (CadIntentError, ProjectKernelError, ProjectError) as exc:
        raise HTTPException(
            status_code=getattr(exc, "status_code", 400),
            detail={
                "code": getattr(exc, "code", "CAD_INTENT_ERROR"),
                "message": getattr(exc, "message", str(exc)),
                "retryable": getattr(exc, "status_code", 400) >= 500,
                "userActions": [{"id": "retry", "label": "重试"}],
            },
        ) from exc
