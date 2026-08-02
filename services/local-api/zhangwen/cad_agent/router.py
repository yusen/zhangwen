"""CAD Agent HTTP routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from zhangwen.cad_agent.coordinator import CadJobCoordinator
from zhangwen.cad_agent.job_repository import CadJobRepository
from zhangwen.cad_agent.models import (
    CadJob,
    CadRunResponse,
    ConfirmCadRequest,
    RejectCadRequest,
)
from zhangwen.cad_agent.repository import CadRepository
from zhangwen.config import settings
from zhangwen.projects.models import ExpertType
from zhangwen.projects.repository import ProjectRepository
from zhangwen.skills.runtime import CadBuildEnqueueRequest, SkillRuntime
from zhangwen.host import require_desktop_host

router = APIRouter(prefix="/api/projects", tags=["cad-agent"])
_coordinator: CadJobCoordinator | None = None


class CadJobResponse(BaseModel):
    cadJob: CadJob


class CreateCadJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cadRunId: str = Field(min_length=1, max_length=120)
    clientRequestId: str | None = Field(default=None, min_length=1, max_length=160)


class RetryCadJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clientRequestId: str | None = Field(default=None, min_length=1, max_length=160)


@router.get("/{project_id}/cad/current", response_model=CadRunResponse)
async def get_current_cad(project_id: str) -> CadRunResponse:
    repo = _project_repo()
    repo.get_workspace(project_id)
    cad_run = CadRepository(repo.db_path).get_current_cad(project_id)
    if cad_run is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "CAD_NOT_FOUND",
                "message": "当前项目还没有 CAD 运行。",
                "retryable": False,
            },
        )
    return CadRunResponse(cadRun=cad_run)


@router.get("/{project_id}/cad/runs/{cad_run_id}", response_model=CadRunResponse)
async def get_cad_run(project_id: str, cad_run_id: str) -> CadRunResponse:
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        cad_run = CadRepository(repo.db_path).get_cad(project_id, cad_run_id)
    except ValueError as exc:
        raise _cad_http_exception(exc) from exc
    return CadRunResponse(cadRun=cad_run)


@router.post("/{project_id}/cad/jobs", response_model=CadJobResponse)
async def create_cad_job(
    project_id: str,
    request: CreateCadJobRequest,
    http_request: Request,
) -> CadJobResponse:
    require_desktop_host(http_request, "local_cad")
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        async def enqueue(value: CadBuildEnqueueRequest) -> dict[str, object]:
            created = CadRepository(repo.db_path).create_job(
                project_id=value.projectId,
                cad_run_id=value.cadRunId,
                client_request_id=value.clientRequestId,
            )
            (await ensure_cad_coordinator()).submit(created)
            return {
                "cadJobId": created.id,
                "cadRunId": created.cadRunId,
                "status": created.status.value,
            }

        skill_result = await SkillRuntime.with_cad_build(repo.db_path, enqueue).run(
            project_id=project_id,
            skill_id="parametric-modeling",
            payload={
                "projectId": project_id,
                "cadRunId": request.cadRunId,
                "clientRequestId": request.clientRequestId,
            },
            confirmed=True,
            requesting_expert=ExpertType.STRUCTURE_ENGINEER,
        )
        output = skill_result.output or {}
        job_id = output.get("cadJobId")
        if not isinstance(job_id, str):
            raise ValueError("CAD_SKILL_OUTPUT_INVALID")
        job = CadJobRepository(repo.db_path).get(project_id, job_id)
    except (ValueError, RuntimeError) as exc:
        raise _cad_http_exception(exc) from exc
    return CadJobResponse(cadJob=job)


@router.get("/{project_id}/cad/jobs/{job_id}", response_model=CadJobResponse)
async def get_cad_job(project_id: str, job_id: str) -> CadJobResponse:
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        job = CadJobRepository(repo.db_path).get(project_id, job_id)
    except ValueError as exc:
        raise _cad_http_exception(exc) from exc
    return CadJobResponse(cadJob=job)


@router.post("/{project_id}/cad/jobs/{job_id}/cancel", response_model=CadJobResponse)
async def cancel_cad_job(
    project_id: str,
    job_id: str,
    http_request: Request,
) -> CadJobResponse:
    require_desktop_host(http_request, "local_cad")
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        job = await (await ensure_cad_coordinator()).cancel(project_id, job_id)
    except ValueError as exc:
        raise _cad_http_exception(exc) from exc
    return CadJobResponse(cadJob=job)


@router.post("/{project_id}/cad/jobs/{job_id}/retry", response_model=CadJobResponse)
async def retry_cad_job(
    project_id: str,
    job_id: str,
    request: RetryCadJobRequest,
    http_request: Request,
) -> CadJobResponse:
    require_desktop_host(http_request, "local_cad")
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        job = (await ensure_cad_coordinator()).retry(
            project_id=project_id,
            job_id=job_id,
            client_request_id=request.clientRequestId,
        )
    except ValueError as exc:
        raise _cad_http_exception(exc) from exc
    return CadJobResponse(cadJob=job)


@router.post("/{project_id}/cad/generate")
async def generate_cad(
    project_id: str,
    http_request: Request,
) -> None:
    """Keep the former endpoint as an explicit, non-executing migration boundary."""

    require_desktop_host(http_request, "local_cad")
    repo = _project_repo()
    repo.get_workspace(project_id)
    raise HTTPException(
        status_code=410,
        detail={
            "code": "CAD_LEGACY_ROUTE_DISABLED",
            "message": "旧 CAD 生成入口已停用，请由结构工程师草稿卡确认后开始建模。",
            "retryable": False,
        },
    )


@router.post("/{project_id}/cad/confirm", response_model=CadRunResponse)
async def confirm_cad(
    project_id: str,
    request: ConfirmCadRequest,
    http_request: Request,
) -> CadRunResponse:
    require_desktop_host(http_request, "local_cad")
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        cad_run = CadRepository(repo.db_path).confirm_cad(
            project_id,
            request.cadRunId,
        )
    except ValueError as exc:
        if str(exc) == "CAD_INTAKE_REVISED":
            raise _cad_http_exception(exc) from exc
        raise _unprocessable("CAD_CONFIRM_FAILED", str(exc)) from exc
    return CadRunResponse(cadRun=cad_run)


@router.post("/{project_id}/cad/reject", response_model=CadRunResponse)
async def reject_cad(
    project_id: str,
    request: RejectCadRequest,
    http_request: Request,
) -> CadRunResponse:
    require_desktop_host(http_request, "local_cad")
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        cad_run = CadRepository(repo.db_path).reject_cad(
            project_id,
            request.cadRunId,
            request.reason,
        )
    except ValueError as exc:
        raise _unprocessable("CAD_REJECT_FAILED", str(exc)) from exc
    return CadRunResponse(cadRun=cad_run)


def _project_repo() -> ProjectRepository:
    return ProjectRepository(settings.data_dir)


async def ensure_cad_coordinator() -> CadJobCoordinator:
    global _coordinator
    data_dir = Path(settings.data_dir).resolve()
    if _coordinator is not None and _coordinator.data_dir != data_dir:
        await _coordinator.stop()
        _coordinator = None
    if _coordinator is None:
        repo = ProjectRepository(data_dir)
        _coordinator = CadJobCoordinator(repo.db_path, data_dir)
        await _coordinator.start()
    return _coordinator


async def stop_cad_coordinator() -> None:
    global _coordinator
    coordinator = _coordinator
    _coordinator = None
    if coordinator is not None:
        await coordinator.stop()


def _unprocessable(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={
            "code": code,
            "message": message,
            "retryable": False,
        },
    )


def _cad_http_exception(exc: ValueError) -> HTTPException:
    message = str(exc)
    if "不存在" in message:
        status_code = 404
        code = "CAD_NOT_FOUND"
    elif message in {"CAD_CLIENT_REQUEST_CONFLICT", "CAD_PROJECT_JOB_ACTIVE"}:
        status_code = 409
        code = message
    elif message == "CAD_JOB_QUEUE_FULL":
        status_code = 429
        code = message
    elif message in {
        "CAD_INTAKE_REVISED",
        "CAD_JOB_NOT_RETRYABLE",
        "CAD_RUN_NOT_BUILDABLE",
    }:
        status_code = 409
        code = message
    else:
        status_code = 422
        code = message if message.startswith("CAD_") else "CAD_REQUEST_INVALID"
    display_message = (
        "CAD 结构输入已更新，请使用最新 CAD 草稿。"
        if code == "CAD_INTAKE_REVISED"
        else message
    )
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": display_message, "retryable": False},
    )
