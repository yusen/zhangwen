"""Creator V3 aggregate HTTP API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from zhangwen.config import settings
from zhangwen.auth.context import current_owner_subject
from zhangwen.creator.models import (
    CompleteReproductionRequest,
    CompleteImportedReproductionRequest,
    CreateCreatorDeliveryRequest,
    CreateCreatorWorkRequest,
    CreatePhysicalRunRequest,
    CreatorCommand,
    CreatorCommandRequest,
    CreatorCommandResponse,
    CreatorJobCommand,
    CreatorJobCommandRequest,
    CreatorJobCommandResponse,
    CreatorJobResponse,
    CreatorWorkListResponse,
    CreatorWorkspaceResponse,
    CreatorDeliveryResponse,
    CreatorImportContextResponse,
    DevicePackageListResponse,
    DevicePackageRevision,
    ImportCreatorDeliveryRequest,
    ImportCreatorDeliveryResponse,
    PhysicalRunResponse,
    ReproductionResponse,
)
from zhangwen.creator.delivery import CreatorDeliveryService
from zhangwen.creator.jobs import (
    CreatorJobExecutionError,
    CreatorJobRunner,
)
from zhangwen.creator.repository import CreatorError, CreatorRepository
from zhangwen.devices.device_packages import list_device_packages
from zhangwen.host import require_desktop_host
from zhangwen.llm.deepseek import DeepSeekProvider
from zhangwen.llm.runtime import require_llm_config
from zhangwen.settings.models import ModelWorkload
from zhangwen.projects.errors import ProjectError
from zhangwen.projects.repository import ProjectRepository
from zhangwen.security.credentials import BackendCredentialStore
from zhangwen.skills.model_router import ModelRouter
from zhangwen.skills.models import ModelRouteStrategy


router = APIRouter(prefix="/api/creator", tags=["creator-v3"])
_job_runner: CreatorJobRunner | None = None
credential_store_factory = BackendCredentialStore
provider_factory = DeepSeekProvider

_LOCAL_COMMAND_CAPABILITY = {
    CreatorCommand.RECORD_STATIC_VALIDATION: "local_tool",
    CreatorCommand.RECORD_SIMULATION: "local_tool",
    CreatorCommand.RECORD_STRUCTURE_CHECK: "local_cad",
    CreatorCommand.RECORD_DEVICE_CONNECTION: "device_upload",
    CreatorCommand.RECORD_DEPLOYMENT: "device_upload",
    CreatorCommand.RECORD_PHYSICAL_BEHAVIOR: "device_upload",
}


@router.get("/works", response_model=CreatorWorkListResponse)
async def list_works(
    include_archived: bool = Query(False, alias="includeArchived"),
) -> CreatorWorkListResponse:
    works, active = _call(
        lambda repository: repository.list_works(include_archived=include_archived)
    )
    return CreatorWorkListResponse(works=works, activeWorkId=active)


@router.post("/works", response_model=CreatorWorkspaceResponse)
async def create_work(request: CreateCreatorWorkRequest) -> CreatorWorkspaceResponse:
    workspace = _call(
        lambda repository: repository.create_work(
            name=request.name,
            initial_idea=request.initial_idea,
            idempotency_key=request.idempotency_key,
            selected_hardware_ids=request.selected_hardware_ids,
        )
    )
    return CreatorWorkspaceResponse(workspace=workspace)


@router.get("/works/{work_id}", response_model=CreatorWorkspaceResponse)
@router.get("/works/{work_id}/workspace", response_model=CreatorWorkspaceResponse)
async def get_workspace(work_id: str) -> CreatorWorkspaceResponse:
    return CreatorWorkspaceResponse(
        workspace=_call(lambda repository: repository.workspace(work_id))
    )


@router.post(
    "/works/{work_id}/commands/{command}",
    response_model=CreatorCommandResponse,
)
async def execute_command(
    work_id: str,
    command: CreatorCommand,
    payload: CreatorCommandRequest,
    request: Request,
) -> CreatorCommandResponse:
    capability = _LOCAL_COMMAND_CAPABILITY.get(command)
    if capability is not None:
        require_desktop_host(request, capability)
    def run(repository: CreatorRepository) -> CreatorCommandResponse:
        subject = _require_subject() if command is CreatorCommand.ACCEPT_WORK else None
        repeated = repository.replay_command(
            work_id, command, payload, authenticated_subject=subject
        )
        if repeated is not None:
            return repeated
        repository.validate_command_source(work_id, command, payload.payload)
        return repository.execute(
            work_id, command, payload, authenticated_subject=subject
        )

    response = _call(run)
    if command is CreatorCommand.CONFIRM_SOLUTION and not response.repeated:
        runner = await ensure_creator_job_runner()
        runner.submit()
    return response


@router.get("/works/{work_id}/events")
async def work_events(
    work_id: str,
    after: str | None = Query(default=None),
) -> StreamingResponse:
    events = _call(lambda repository: repository.events(work_id, after=after))

    async def stream() -> AsyncIterator[str]:
        for event in events:
            yield f"id: {event['id']}\nevent: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
        yield ": creator-snapshot-complete\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.get(
    "/works/{work_id}/jobs/{job_id}",
    response_model=CreatorJobResponse,
)
async def get_creator_job(work_id: str, job_id: str) -> CreatorJobResponse:
    runner = await ensure_creator_job_runner()
    return CreatorJobResponse(
        job=_job_call(lambda: runner.get(work_id, job_id))
    )


@router.post(
    "/works/{work_id}/jobs/{job_id}/commands/{command}",
    response_model=CreatorJobCommandResponse,
)
async def execute_creator_job_command(
    work_id: str,
    job_id: str,
    command: CreatorJobCommand,
    payload: CreatorJobCommandRequest,
    request: Request,
) -> CreatorJobCommandResponse:
    require_desktop_host(request, "local_tool")
    runner = await ensure_creator_job_runner()
    if command is CreatorJobCommand.CANCEL:
        job, repeated = _job_call(
            lambda: runner.cancel(
                work_id,
                job_id,
                idempotency_key=payload.idempotency_key,
            )
        )
    elif command is CreatorJobCommand.RETRY:
        job, repeated = _job_call(
            lambda: runner.retry(
                work_id,
                job_id,
                idempotency_key=payload.idempotency_key,
            )
        )
    else:
        raise HTTPException(status_code=404, detail="Creator Job 命令不存在。")
    workspace = _call(lambda repository: repository.workspace(work_id))
    return CreatorJobCommandResponse(
        command=command,
        repeated=repeated,
        job=job,
        workspace=workspace,
    )


@router.post(
    "/works/{work_id}/physical-runs",
    response_model=PhysicalRunResponse,
)
async def create_physical_run(
    work_id: str,
    payload: CreatePhysicalRunRequest,
    request: Request,
) -> PhysicalRunResponse:
    require_desktop_host(request, "device_upload")
    return PhysicalRunResponse(
        run=_call(
            lambda repository: repository.create_physical_run(
                work_id, payload, operator_subject=_require_subject()
            )
        )
    )


@router.post(
    "/works/{work_id}/deliveries",
    response_model=CreatorDeliveryResponse,
)
async def create_delivery(
    work_id: str,
    payload: CreateCreatorDeliveryRequest,
    request: Request,
) -> CreatorDeliveryResponse:
    require_desktop_host(request, "local_tool")
    return CreatorDeliveryResponse(
        delivery=_delivery_call(
            lambda service: service.create(
                work_id, payload, actor_subject=_require_subject()
            )
        )
    )


@router.post(
    "/deliveries/import",
    response_model=ImportCreatorDeliveryResponse,
)
async def import_delivery(
    payload: ImportCreatorDeliveryRequest,
    request: Request,
) -> ImportCreatorDeliveryResponse:
    require_desktop_host(request, "local_tool")
    return _delivery_call(
        lambda service: service.import_delivery(
            payload, importer_subject=_require_subject()
        )
    )


@router.post(
    "/works/{work_id}/reproductions",
    response_model=ReproductionResponse,
)
async def complete_reproduction(
    work_id: str,
    payload: CompleteReproductionRequest,
    request: Request,
) -> ReproductionResponse:
    require_desktop_host(request, "local_tool")
    report, workspace = _delivery_call(
        lambda service: service.complete_reproduction(
            work_id, payload, operator_subject=_require_subject()
        )
    )
    return ReproductionResponse(report=report, workspace=workspace)


def _require_subject() -> str:
    subject = current_owner_subject()
    if not subject:
        raise CreatorError(
            "CREATOR_AUTHENTICATED_SUBJECT_REQUIRED",
            "该操作必须由已认证的本地账户签署。",
            status_code=401,
        )
    return subject


@router.get(
    "/works/{work_id}/import-context",
    response_model=CreatorImportContextResponse,
)
async def import_context(work_id: str) -> CreatorImportContextResponse:
    return CreatorImportContextResponse(
        context=_delivery_call(lambda service: service.import_context(work_id))
    )


@router.post(
    "/works/{work_id}/reproduction-receipt",
    response_model=ReproductionResponse,
)
async def complete_imported_reproduction(
    work_id: str,
    payload: CompleteImportedReproductionRequest,
    request: Request,
) -> ReproductionResponse:
    require_desktop_host(request, "local_tool")
    report, workspace = _delivery_call(
        lambda service: service.complete_from_imported(
            work_id, payload, operator_subject=_require_subject()
        )
    )
    return ReproductionResponse(report=report, workspace=workspace)


@router.get("/device-packages", response_model=DevicePackageListResponse)
async def device_packages() -> DevicePackageListResponse:
    return DevicePackageListResponse(
        packages=[
            DevicePackageRevision(
                id=package.id.value,
                version=package.version,
                displayName=package.display_name,
                boardProfileId=package.board_profile_id.value,
                capabilities=list(package.capabilities),
                deploymentChannels=[
                    channel.id.value for channel in package.deployment_channels
                ],
                interactiveConsoleChannels=[
                    channel.id.value
                    for channel in package.deployment_channels
                    if channel.interactive_console
                ],
                simulationModes=list(package.simulation_modes),
                source=package.source,
            )
            for package in list_device_packages()
        ]
    )


def _call(action):
    try:
        return action(CreatorRepository(settings.data_dir))
    except (CreatorError, ProjectError) as exc:
        raise HTTPException(
            status_code=getattr(exc, "status_code", 400),
            detail={
                "code": getattr(exc, "code", "CREATOR_ERROR"),
                "message": getattr(exc, "message", str(exc)),
                "retryable": getattr(exc, "status_code", 400) >= 500,
                "userActions": [{"id": "retry", "label": "重试"}],
            },
        ) from exc


def _delivery_call(action):
    try:
        return action(CreatorDeliveryService(settings.data_dir))
    except (CreatorError, ProjectError) as exc:
        raise HTTPException(
            status_code=getattr(exc, "status_code", 400),
            detail={
                "code": getattr(exc, "code", "CREATOR_DELIVERY_ERROR"),
                "message": getattr(exc, "message", str(exc)),
                "retryable": getattr(exc, "status_code", 400) >= 500,
                "userActions": [{"id": "retry", "label": "重试"}],
            },
        ) from exc


def _job_call(action):
    try:
        return action()
    except CreatorJobExecutionError as exc:
        status_code = (
            404
            if exc.code == "CREATOR_JOB_NOT_FOUND"
            else 409
        )
        raise HTTPException(
            status_code=status_code,
            detail={
                "code": exc.code,
                "message": exc.message,
                "retryable": exc.retryable,
                "userActions": [{"id": "refresh", "label": "刷新作品"}],
            },
        ) from exc


async def ensure_creator_job_runner() -> CreatorJobRunner:
    global _job_runner
    data_dir = Path(settings.data_dir).resolve()
    if _job_runner is not None and _job_runner.data_dir != data_dir:
        await _job_runner.stop()
        _job_runner = None
    if _job_runner is None:
        projects = ProjectRepository(data_dir)

        def code_generation_factory():
            config, api_key = require_llm_config(
                data_dir=data_dir,
                credential_store=credential_store_factory(),
                credential_service=settings.credential_service,
                credential_account=settings.credential_account,
                workload=ModelWorkload.ENGINEERING,
            )
            route = ModelRouter(projects.db_path).route(
                agent_id="code_generator",
                task_kind="code",
                strategy=ModelRouteStrategy.QUALITY_FIRST,
            )
            return provider_factory(), config, api_key, route.model

        _job_runner = CreatorJobRunner(
            projects.db_path,
            data_dir,
            code_generation_factory=code_generation_factory,
        )
        await _job_runner.start()
    return _job_runner


async def stop_creator_job_runner() -> None:
    global _job_runner
    runner = _job_runner
    _job_runner = None
    if runner is not None:
        await runner.stop()
