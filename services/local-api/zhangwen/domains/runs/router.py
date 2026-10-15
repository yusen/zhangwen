"""Unified Work Run HTTP boundary."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar

from fastapi import APIRouter, HTTPException, Request

from zhangwen.config import settings
from zhangwen.creator.repository import CreatorError
from zhangwen.device_lab.router import device_lab_service
from zhangwen.device_lab.service import DeviceLabError
from zhangwen.domains.runs.service import WorkRunError, WorkRunService
from zhangwen.domains.works.models import (
    CompleteWorkRunRequest,
    StartWorkRunRequest,
    UpdateWorkRunControlRequest,
    WorkRunListResponse,
    WorkRunResponse,
)
from zhangwen.host import require_desktop_host
from zhangwen.projects.errors import ProjectError


router = APIRouter(prefix="/api/works/{work_id}/runs", tags=["work-runs"])
T = TypeVar("T")


@router.get("", response_model=WorkRunListResponse)
async def list_runs(work_id: str) -> WorkRunListResponse:
    return _call(lambda service: service.list_runs(work_id))


@router.post("", response_model=WorkRunResponse)
async def start_run(
    work_id: str,
    body: StartWorkRunRequest,
    request: Request,
) -> WorkRunResponse:
    require_desktop_host(request, "local_tool")
    return await _async_call(lambda service: service.start(work_id, body))


@router.put("/{run_id}/inputs/{control_id}", response_model=WorkRunResponse)
async def update_input(
    work_id: str,
    run_id: str,
    control_id: str,
    body: UpdateWorkRunControlRequest,
    request: Request,
) -> WorkRunResponse:
    require_desktop_host(request, "local_tool")
    return await _async_call(
        lambda service: service.update_control(
            work_id,
            run_id,
            control_id,
            body,
            advanced=False,
        )
    )


@router.put("/{run_id}/controls/{control_id}", response_model=WorkRunResponse)
async def update_advanced_control(
    work_id: str,
    run_id: str,
    control_id: str,
    body: UpdateWorkRunControlRequest,
    request: Request,
) -> WorkRunResponse:
    require_desktop_host(request, "local_tool")
    return await _async_call(
        lambda service: service.update_control(
            work_id,
            run_id,
            control_id,
            body,
            advanced=True,
        )
    )


@router.post("/{run_id}/complete", response_model=WorkRunResponse)
async def complete_run(
    work_id: str,
    run_id: str,
    body: CompleteWorkRunRequest,
    request: Request,
) -> WorkRunResponse:
    require_desktop_host(request, "local_tool")
    return await _async_call(lambda service: service.complete(work_id, run_id, body))


@router.post("/{run_id}/stop", response_model=WorkRunResponse)
async def stop_run(
    work_id: str,
    run_id: str,
    request: Request,
) -> WorkRunResponse:
    require_desktop_host(request, "local_tool")
    return await _async_call(lambda service: service.stop(work_id, run_id))


def _service() -> WorkRunService:
    return WorkRunService(settings.data_dir, device_lab_service())


def _call(operation: Callable[[WorkRunService], T]) -> T:
    try:
        return operation(_service())
    except (WorkRunError, DeviceLabError, CreatorError, ProjectError) as exc:
        raise _http_error(exc) from exc


async def _async_call(operation: Callable[[WorkRunService], Awaitable[T]]) -> T:
    try:
        return await operation(_service())
    except (WorkRunError, DeviceLabError, CreatorError, ProjectError) as exc:
        raise _http_error(exc) from exc


def _http_error(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=getattr(exc, "status_code", 404),
        detail={
            "code": getattr(exc, "code", exc.__class__.__name__.upper()),
            "message": getattr(exc, "message", str(exc)),
            "retryable": False,
        },
    )
