"""Unified Work read API introduced before the UI compatibility switch."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TypeVar

from fastapi import APIRouter, HTTPException, Query, Request, status

from zhangwen.auth.context import current_owner_subject
from zhangwen.config import settings
from zhangwen.creator.models import (
    CreatePhysicalRunRequest,
    CreatorCommand,
    CreatorCommandRequest,
)
from zhangwen.creator.repository import CreatorError, CreatorRepository
from zhangwen.creator.router import ensure_creator_job_runner
from zhangwen.domains.works.canvas import (
    CanvasError,
    WorkCanvasService,
    derived_canvas_idempotency_key,
)
from zhangwen.domains.works.delivery import WorkDeliveryService, WorkRecoveryService
from zhangwen.domains.works.models import (
    AcceptWorkRequest,
    ObserveWorkRequest,
    RecordWorkDeploymentRequest,
    RecordWorkDeviceConnectionRequest,
    CanvasGenerationCommandRequest,
    CanvasGenerationResponse,
    CanvasGenerationSeed,
    CanvasLayoutResponse,
    ConfirmCanvasProposalRequest,
    ConfirmCanvasProposalResponse,
    CompleteWorkReproductionRequest,
    CreateWorkDeliveryRequest,
    CreateWorkRequest,
    ImportWorkDeliveryRequest,
    ImportWorkDeliveryResponse,
    SaveCanvasLayoutRequest,
    StartCanvasGenerationRequest,
    WorkBuildJourneyResponse,
    WorkDeliveryOverviewResponse,
    WorkDeliveryResponse,
    WorkListResponse,
    WorkMigrationReportResponse,
    WorkRecoveryOverviewResponse,
    WorkReproductionResponse,
    WorkSnapshotResponse,
    WorkSummary,
)
from zhangwen.domains.works.repository import WorkRepository
from zhangwen.host import require_desktop_host
from zhangwen.projects.errors import ProjectError


router = APIRouter(prefix="/api/works", tags=["works"])
T = TypeVar("T")


@router.post(
    "",
    response_model=WorkSnapshotResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_work(request: CreateWorkRequest) -> WorkSnapshotResponse:
    try:
        created = CreatorRepository(settings.data_dir).create_work(
            name=request.name,
            initial_idea=request.initial_idea,
            idempotency_key=request.idempotency_key,
            selected_hardware_ids=[],
        )
        seed = request.canvas_seed or CanvasGenerationSeed()
        _canvas_call(
            lambda service: service.start_generation(
                created.work_id,
                StartCanvasGenerationRequest(
                    **seed.model_dump(by_alias=True, mode="json"),
                    idempotencyKey=derived_canvas_idempotency_key(
                        request.idempotency_key
                    ),
                ),
            )
        )
        return WorkSnapshotResponse(
            snapshot=WorkRepository(settings.data_dir).snapshot(created.work_id)
        )
    except CreatorError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message, "retryable": False},
        ) from exc


@router.get("", response_model=WorkListResponse)
async def list_works(
    include_archived: bool = Query(False, alias="includeArchived"),
) -> WorkListResponse:
    return _call(
        lambda repository: repository.response(
            include_archived=include_archived
        )
    )


@router.get("/system-recovery", response_model=WorkRecoveryOverviewResponse)
async def get_system_recovery() -> WorkRecoveryOverviewResponse:
    return WorkRecoveryOverviewResponse(
        recovery=WorkRecoveryService(settings.data_dir).overview()
    )


@router.post(
    "/deliveries/import",
    response_model=ImportWorkDeliveryResponse,
)
async def import_work_delivery(
    payload: ImportWorkDeliveryRequest,
    request: Request,
) -> ImportWorkDeliveryResponse:
    require_desktop_host(request, "local_tool")
    subject = _require_subject()
    imported = _delivery_call(
        lambda service: service.import_delivery(
            payload,
            importer_subject=subject,
        )
    )
    snapshot = _call(
        lambda repository: repository.snapshot(imported.workspace.work_id)
    )
    assert snapshot.current_delivery is not None
    return ImportWorkDeliveryResponse(
        importId=imported.import_id,
        sourceDeliveryId=imported.source_delivery_id,
        packageSha256=imported.package_sha256,
        snapshot=snapshot,
        overview=snapshot.current_delivery,
    )


@router.get("/{work_id}", response_model=WorkSummary)
async def get_work(work_id: str) -> WorkSummary:
    return _call(lambda repository: repository.get(work_id))


@router.get("/{work_id}/snapshot", response_model=WorkSnapshotResponse)
async def get_work_snapshot(work_id: str) -> WorkSnapshotResponse:
    return WorkSnapshotResponse(
        snapshot=_call(lambda repository: repository.snapshot(work_id))
    )


@router.post(
    "/{work_id}/canvas/generations",
    response_model=CanvasGenerationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_canvas_generation(
    work_id: str,
    payload: StartCanvasGenerationRequest,
) -> CanvasGenerationResponse:
    generation = _canvas_call(
        lambda service: service.start_generation(work_id, payload)
    )
    return CanvasGenerationResponse(
        generation=generation,
        snapshot=_call(lambda repository: repository.snapshot(work_id)),
    )


@router.post(
    "/{work_id}/canvas/generations/{generation_id}/run",
    response_model=CanvasGenerationResponse,
)
async def run_canvas_generation(
    work_id: str,
    generation_id: str,
) -> CanvasGenerationResponse:
    generation = await asyncio.to_thread(
        _canvas_call,
        lambda service: service.run_generation(work_id, generation_id),
    )
    return CanvasGenerationResponse(
        generation=generation,
        snapshot=_call(lambda repository: repository.snapshot(work_id)),
    )


@router.post(
    "/{work_id}/canvas/generations/{generation_id}/cancel",
    response_model=CanvasGenerationResponse,
)
async def cancel_canvas_generation(
    work_id: str,
    generation_id: str,
    payload: CanvasGenerationCommandRequest,
) -> CanvasGenerationResponse:
    generation = _canvas_call(
        lambda service: service.cancel_generation(
            work_id,
            generation_id,
            payload,
        )
    )
    return CanvasGenerationResponse(
        generation=generation,
        snapshot=_call(lambda repository: repository.snapshot(work_id)),
    )


@router.post(
    "/{work_id}/canvas/generations/{generation_id}/retry",
    response_model=CanvasGenerationResponse,
)
async def retry_canvas_generation(
    work_id: str,
    generation_id: str,
    payload: CanvasGenerationCommandRequest,
) -> CanvasGenerationResponse:
    generation = _canvas_call(
        lambda service: service.retry_generation(
            work_id,
            generation_id,
            payload,
        )
    )
    return CanvasGenerationResponse(
        generation=generation,
        snapshot=_call(lambda repository: repository.snapshot(work_id)),
    )


@router.put(
    "/{work_id}/canvas/layout",
    response_model=CanvasLayoutResponse,
)
async def save_canvas_layout(
    work_id: str,
    payload: SaveCanvasLayoutRequest,
) -> CanvasLayoutResponse:
    layout = _canvas_call(
        lambda service: service.save_layout(work_id, payload)
    )
    return CanvasLayoutResponse(
        layout=layout,
        snapshot=_call(lambda repository: repository.snapshot(work_id)),
    )


@router.post(
    "/{work_id}/canvas/confirm",
    response_model=ConfirmCanvasProposalResponse,
)
async def confirm_canvas_proposal(
    work_id: str,
    payload: ConfirmCanvasProposalRequest,
) -> ConfirmCanvasProposalResponse:
    _canvas_call(lambda service: service.confirm_proposal(work_id, payload))
    runner = await ensure_creator_job_runner()
    runner.submit()
    return ConfirmCanvasProposalResponse(
        snapshot=_call(lambda repository: repository.snapshot(work_id))
    )


@router.get(
    "/{work_id}/build-journey",
    response_model=WorkBuildJourneyResponse,
)
async def get_work_build_journey(work_id: str) -> WorkBuildJourneyResponse:
    snapshot = _call(lambda repository: repository.snapshot(work_id))
    return WorkBuildJourneyResponse(journey=snapshot.current_build_journey)


@router.post(
    "/{work_id}/acceptance",
    response_model=WorkSnapshotResponse,
)
async def accept_work(
    work_id: str,
    payload: AcceptWorkRequest,
) -> WorkSnapshotResponse:
    """Record an explicit human conclusion without introducing another store."""

    subject = _require_subject()
    creator = CreatorRepository(settings.data_dir)
    try:
        workspace = creator.workspace(work_id)
        creator.execute(
            work_id,
            CreatorCommand.ACCEPT_WORK,
            CreatorCommandRequest(
                baseProjectVersion=workspace.project_version,
                idempotencyKey=payload.idempotency_key,
                payload={
                    "accepted": True,
                    "actor": payload.actor,
                    "summary": payload.summary,
                },
            ),
            authenticated_subject=subject,
        )
        return WorkSnapshotResponse(
            snapshot=WorkRepository(settings.data_dir).snapshot(work_id)
        )
    except CreatorError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message, "retryable": False},
        ) from exc


def _record_creator_fact(
    work_id: str,
    *,
    command: CreatorCommand,
    idempotency_key: str,
    payload: dict[str, object],
) -> WorkSnapshotResponse:
    creator = CreatorRepository(settings.data_dir)
    try:
        repeated = creator.replay_command(
            work_id,
            command,
            CreatorCommandRequest(
                baseProjectVersion=creator.workspace(work_id).project_version,
                idempotencyKey=idempotency_key,
                payload=payload,
            ),
        )
        if repeated is None:
            workspace = creator.workspace(work_id)
            request = CreatorCommandRequest(
                baseProjectVersion=workspace.project_version,
                idempotencyKey=idempotency_key,
                payload=payload,
            )
            creator.validate_command_source(work_id, command, payload)
            creator.execute(work_id, command, request)
        return WorkSnapshotResponse(
            snapshot=WorkRepository(settings.data_dir).snapshot(work_id)
        )
    except CreatorError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message, "retryable": False},
        ) from exc


@router.post(
    "/{work_id}/build/device-connection",
    response_model=WorkSnapshotResponse,
)
async def record_work_device_connection(
    work_id: str,
    payload: RecordWorkDeviceConnectionRequest,
    request: Request,
) -> WorkSnapshotResponse:
    require_desktop_host(request, "device_upload")
    return _record_creator_fact(
        work_id,
        command=CreatorCommand.RECORD_DEVICE_CONNECTION,
        idempotency_key=payload.idempotency_key,
        payload={
            "passed": True,
            "summary": "设备身份与当前作品已经在本机确认。",
            "sourceId": payload.source_id,
            "bindings": {"channel": payload.channel},
        },
    )


@router.post(
    "/{work_id}/build/deployment",
    response_model=WorkSnapshotResponse,
)
async def record_work_deployment(
    work_id: str,
    payload: RecordWorkDeploymentRequest,
    request: Request,
) -> WorkSnapshotResponse:
    require_desktop_host(request, "device_upload")
    return _record_creator_fact(
        work_id,
        command=CreatorCommand.RECORD_DEPLOYMENT,
        idempotency_key=payload.idempotency_key,
        payload={
            "passed": True,
            "summary": "当前版本已经写入并完成回读验证。",
            "sourceId": payload.operation_id,
            "bindings": (
                {"codeRunId": payload.code_run_id}
                if payload.code_run_id is not None
                else {}
            ),
        },
    )


@router.post(
    "/{work_id}/build/observation",
    response_model=WorkSnapshotResponse,
)
async def observe_work(
    work_id: str,
    payload: ObserveWorkRequest,
    request: Request,
) -> WorkSnapshotResponse:
    require_desktop_host(request, "device_upload")
    subject = _require_subject()
    creator = CreatorRepository(settings.data_dir)
    try:
        report = creator.create_physical_run(
            work_id,
            CreatePhysicalRunRequest(
                idempotencyKey=payload.idempotency_key,
                deploymentOperationId=payload.deployment_operation_id,
                targetId=payload.target_id,
                operator=payload.operator,
                emergencyStopVerified=payload.emergency_stop_verified,
                scenarioResults=[
                    item.model_dump(by_alias=True, mode="json")
                    for item in payload.scenario_results
                ],
            ),
            operator_subject=subject,
        )
        if not report.passed:
            raise CreatorError(
                "CREATOR_PHYSICAL_OBSERVATION_NOT_PASSED",
                "至少一项真实场景或紧急停止检查未通过；已保存观察结果，但不会进入最终验收。",
                status_code=409,
            )
        return _record_creator_fact(
            work_id,
            command=CreatorCommand.RECORD_PHYSICAL_BEHAVIOR,
            idempotency_key=f"{payload.idempotency_key}:evidence",
            payload={
                "passed": True,
                "summary": "实际观察者已逐项确认真实作品行为。",
                "sourceId": report.id,
                "bindings": {},
            },
        )
    except CreatorError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message, "retryable": False},
        ) from exc


@router.get(
    "/{work_id}/delivery",
    response_model=WorkDeliveryOverviewResponse,
)
async def get_work_delivery(work_id: str) -> WorkDeliveryOverviewResponse:
    return WorkDeliveryOverviewResponse(
        delivery=_delivery_call(lambda service: service.overview(work_id))
    )


@router.get(
    "/{work_id}/migration-report",
    response_model=WorkMigrationReportResponse,
)
async def get_work_migration_report(work_id: str) -> WorkMigrationReportResponse:
    return WorkMigrationReportResponse(
        report=_delivery_call(lambda service: service.migration_report(work_id))
    )


@router.post(
    "/{work_id}/deliveries",
    response_model=WorkDeliveryResponse,
)
async def create_work_delivery(
    work_id: str,
    payload: CreateWorkDeliveryRequest,
    request: Request,
) -> WorkDeliveryResponse:
    require_desktop_host(request, "local_tool")
    delivery, zip_base64, overview = _delivery_call(
        lambda service: service.create(
            work_id,
            payload,
            actor_subject=_require_subject(),
        )
    )
    return WorkDeliveryResponse(
        delivery=delivery,
        zipBase64=zip_base64,
        overview=overview,
    )


@router.post(
    "/{work_id}/reproduction-receipt",
    response_model=WorkReproductionResponse,
)
async def complete_work_reproduction(
    work_id: str,
    payload: CompleteWorkReproductionRequest,
    request: Request,
) -> WorkReproductionResponse:
    require_desktop_host(request, "local_tool")
    report, _source = _delivery_call(
        lambda service: service.complete_reproduction(
            work_id,
            payload,
            operator_subject=_require_subject(),
        )
    )
    source_snapshot = _call(
        lambda repository: repository.snapshot(report.source_work_id)
    )
    imported_snapshot = _call(lambda repository: repository.snapshot(work_id))
    return WorkReproductionResponse(
        report=report,
        sourceSnapshot=source_snapshot,
        importedSnapshot=imported_snapshot,
    )


def _call(operation: Callable[[WorkRepository], T]) -> T:
    try:
        return operation(WorkRepository(settings.data_dir))
    except CreatorError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message, "retryable": False},
        ) from exc
    except ProjectError as exc:
        raise HTTPException(
            status_code=getattr(exc, "status_code", 404),
            detail={
                "code": exc.__class__.__name__.upper(),
                "message": str(exc),
                "retryable": False,
            },
        ) from exc


def _delivery_call(operation: Callable[[WorkDeliveryService], T]) -> T:
    try:
        return operation(WorkDeliveryService(settings.data_dir))
    except CreatorError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message, "retryable": False},
        ) from exc
    except ProjectError as exc:
        raise HTTPException(
            status_code=getattr(exc, "status_code", 404),
            detail={
                "code": exc.__class__.__name__.upper(),
                "message": str(exc),
                "retryable": False,
            },
        ) from exc


def _canvas_call(operation: Callable[[WorkCanvasService], T]) -> T:
    try:
        return operation(WorkCanvasService(settings.data_dir))
    except CanvasError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "code": exc.code,
                "message": exc.message,
                "retryable": exc.retryable,
            },
        ) from exc
    except CreatorError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message, "retryable": False},
        ) from exc
    except ProjectError as exc:
        raise HTTPException(
            status_code=getattr(exc, "status_code", 404),
            detail={
                "code": exc.__class__.__name__.upper(),
                "message": str(exc),
                "retryable": False,
            },
        ) from exc


def _require_subject() -> str:
    subject = current_owner_subject()
    if not subject:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "WORK_AUTHENTICATED_SUBJECT_REQUIRED",
                "message": "该操作必须由已认证的本地账户签署。",
                "retryable": False,
            },
        )
    return subject
