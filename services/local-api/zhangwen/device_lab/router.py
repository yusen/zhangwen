"""HTTP routes for the two-board device laboratory."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from zhangwen.config import settings
from zhangwen.device_lab.boards import scene_profile
from zhangwen.device_lab.models import (
    ApplyParameterSetRequest,
    CreateDeviceLabRunRequest,
    DeviceBoardListResponse,
    DeviceLabSceneResponse,
    DeviceLabRunResponse,
    FirmwareApplicationListResponse,
    FirmwareApplicationResponse,
    ImportFirmwareApplicationRequest,
    ParameterSetListResponse,
    ParameterSetResponse,
    SaveParameterSetRequest,
    UpdateDeviceLabChannelRequest,
)
from zhangwen.device_lab.service import DeviceLabError, DeviceLabService
from zhangwen.host import require_desktop_host
from zhangwen.projects.repository import ProjectRepository


router = APIRouter(tags=["device-lab"])
_services: dict[Path, DeviceLabService] = {}


@router.get("/api/device-lab/boards", response_model=DeviceBoardListResponse)
async def list_device_lab_boards() -> DeviceBoardListResponse:
    return _service().board_list()


@router.get(
    "/api/projects/{project_id}/device-lab/scene",
    response_model=DeviceLabSceneResponse,
)
async def get_device_lab_scene(project_id: str) -> DeviceLabSceneResponse:
    _project(project_id)
    try:
        scene = _service().get_scene(project_id)
    except DeviceLabError as exc:
        raise _http_error(exc) from exc
    return DeviceLabSceneResponse(scene=scene, profile=scene_profile(scene))


@router.get(
    "/api/projects/{project_id}/device-lab/applications",
    response_model=FirmwareApplicationListResponse,
)
async def list_applications(project_id: str) -> FirmwareApplicationListResponse:
    _project(project_id)
    return _service().list_applications(project_id)


@router.post(
    "/api/projects/{project_id}/device-lab/applications/import",
    response_model=FirmwareApplicationResponse,
)
async def import_application(
    project_id: str,
    body: ImportFirmwareApplicationRequest,
    request: Request,
) -> FirmwareApplicationResponse:
    require_desktop_host(request, "local_tool")
    _project(project_id)
    try:
        application = _service().import_application(project_id, body)
    except DeviceLabError as exc:
        raise _http_error(exc) from exc
    return FirmwareApplicationResponse(application=application)


@router.post(
    "/api/projects/{project_id}/device-lab/runs",
    response_model=DeviceLabRunResponse,
)
async def create_run(
    project_id: str,
    body: CreateDeviceLabRunRequest,
    request: Request,
) -> DeviceLabRunResponse:
    require_desktop_host(request, "local_tool")
    _project(project_id)
    try:
        return await _service().create_run(project_id, body)
    except DeviceLabError as exc:
        raise _http_error(exc) from exc


@router.get(
    "/api/projects/{project_id}/device-lab/runs/{run_id}",
    response_model=DeviceLabRunResponse,
)
async def get_run(project_id: str, run_id: str) -> DeviceLabRunResponse:
    _project(project_id)
    try:
        return _service().get_run(project_id, run_id)
    except DeviceLabError as exc:
        raise _http_error(exc) from exc


@router.put(
    "/api/projects/{project_id}/device-lab/runs/{run_id}/channels/{channel_id}",
    response_model=DeviceLabRunResponse,
)
async def update_channel(
    project_id: str,
    run_id: str,
    channel_id: str,
    body: UpdateDeviceLabChannelRequest,
    request: Request,
) -> DeviceLabRunResponse:
    require_desktop_host(request, "local_tool")
    _project(project_id)
    try:
        return await _service().update_channel(project_id, run_id, channel_id, body)
    except DeviceLabError as exc:
        raise _http_error(exc) from exc


@router.post(
    "/api/projects/{project_id}/device-lab/runs/{run_id}/stop",
    response_model=DeviceLabRunResponse,
)
async def stop_run(project_id: str, run_id: str, request: Request) -> DeviceLabRunResponse:
    require_desktop_host(request, "local_tool")
    _project(project_id)
    try:
        return await _service().stop_run(project_id, run_id)
    except DeviceLabError as exc:
        raise _http_error(exc) from exc


@router.get("/api/projects/{project_id}/device-lab/runs/{run_id}/events")
async def stream_events(
    project_id: str,
    run_id: str,
    after_revision: int = Query(default=0, alias="afterRevision", ge=0),
) -> StreamingResponse:
    _project(project_id)
    try:
        events = _service().list_events(project_id, run_id, after_revision)
    except DeviceLabError as exc:
        raise _http_error(exc) from exc

    async def generate():
        for event in events:
            yield f"id: {event.revision}\nevent: {event.type}\ndata: {event.model_dump_json()}\n\n"
        yield "event: heartbeat\ndata: {}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.get(
    "/api/projects/{project_id}/device-lab/parameter-sets",
    response_model=ParameterSetListResponse,
)
async def list_parameter_sets(project_id: str) -> ParameterSetListResponse:
    _project(project_id)
    return ParameterSetListResponse(parameterSets=_service().list_parameter_sets(project_id))


@router.post(
    "/api/projects/{project_id}/device-lab/parameter-sets",
    response_model=ParameterSetResponse,
)
async def save_parameter_set(
    project_id: str,
    body: SaveParameterSetRequest,
    request: Request,
) -> ParameterSetResponse:
    require_desktop_host(request, "local_tool")
    _project(project_id)
    try:
        item = _service().save_parameter_set(project_id, body)
    except DeviceLabError as exc:
        raise _http_error(exc) from exc
    return ParameterSetResponse(parameterSet=item)


@router.post(
    "/api/projects/{project_id}/device-lab/runs/{run_id}/apply-parameters",
    response_model=DeviceLabRunResponse,
)
async def apply_parameter_set(
    project_id: str,
    run_id: str,
    body: ApplyParameterSetRequest,
    request: Request,
) -> DeviceLabRunResponse:
    require_desktop_host(request, "local_tool")
    _project(project_id)
    try:
        return await _service().apply_parameter_set(project_id, run_id, body)
    except DeviceLabError as exc:
        raise _http_error(exc) from exc


async def shutdown_device_lab_services() -> None:
    services = list(_services.values())
    _services.clear()
    for service in services:
        await service.shutdown()


def recover_device_lab_runs() -> int:
    """Recover durable run state before the local API accepts requests."""

    return _service().recover_interrupted_runs()


def _project(project_id: str) -> ProjectRepository:
    repository = ProjectRepository(settings.data_dir)
    repository.get_workspace(project_id)
    return repository


def _service() -> DeviceLabService:
    return device_lab_service()


def device_lab_service() -> DeviceLabService:
    """Return the one process-local Device Lab executor shared by adapters."""
    repository = ProjectRepository(settings.data_dir)
    key = repository.db_path.resolve()
    service = _services.get(key)
    if service is None:
        service = DeviceLabService(repository.db_path, settings.data_dir)
        _services[key] = service
    return service


def _http_error(exc: DeviceLabError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.message, "retryable": False},
    )
