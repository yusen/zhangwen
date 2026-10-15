"""Local-only API for supervised MQTT service instances."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request, status

from zhangwen.config import settings
from zhangwen.domains.mqtt_service.models import (
    CreateMqttServiceInstanceRequest,
    MqttConfirmationRequiredError,
    MqttLifecycleRequest,
    MqttServiceError,
    MqttServiceInstanceResponse,
    MqttServiceSamplesResponse,
    MqttServiceStatusResponse,
    SetMqttCredentialsRequest,
    UpdateMqttTopicContractRequest,
)
from zhangwen.domains.mqtt_service.service import MqttService
from zhangwen.host import require_desktop_host


router = APIRouter(prefix="/api/services/mqtt", tags=["mqtt-service"])
_mqtt_service: MqttService | None = None


@router.get("/status", response_model=MqttServiceStatusResponse)
def mqtt_status() -> MqttServiceStatusResponse:
    return _service().status()


@router.post(
    "/instances",
    response_model=MqttServiceInstanceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_mqtt_instance(
    payload: CreateMqttServiceInstanceRequest,
) -> MqttServiceInstanceResponse:
    return _run(lambda: MqttServiceInstanceResponse(instance=_service().create(payload)))


@router.get("/instances/{instance_id}", response_model=MqttServiceInstanceResponse)
def get_mqtt_instance(instance_id: str) -> MqttServiceInstanceResponse:
    return _run(lambda: MqttServiceInstanceResponse(instance=_service().get(instance_id)))


@router.post("/instances/{instance_id}/start", response_model=MqttServiceInstanceResponse)
def start_mqtt_instance(
    instance_id: str,
    payload: MqttLifecycleRequest,
    request: Request,
) -> MqttServiceInstanceResponse:
    require_desktop_host(request, "local_service")
    return _run(lambda: MqttServiceInstanceResponse(instance=_service().start(instance_id, payload)))


@router.post("/instances/{instance_id}/stop", response_model=MqttServiceInstanceResponse)
def stop_mqtt_instance(
    instance_id: str,
    payload: MqttLifecycleRequest,
    request: Request,
) -> MqttServiceInstanceResponse:
    require_desktop_host(request, "local_service")
    return _run(lambda: MqttServiceInstanceResponse(instance=_service().stop(instance_id, payload)))


@router.put(
    "/instances/{instance_id}/topic-contract",
    response_model=MqttServiceInstanceResponse,
)
def update_mqtt_topic_contract(
    instance_id: str,
    payload: UpdateMqttTopicContractRequest,
) -> MqttServiceInstanceResponse:
    return _run(lambda: MqttServiceInstanceResponse(instance=_service().update_contract(instance_id, payload)))


@router.post(
    "/instances/{instance_id}/credentials",
    response_model=MqttServiceInstanceResponse,
)
def set_mqtt_credentials(
    instance_id: str,
    payload: SetMqttCredentialsRequest,
    request: Request,
) -> MqttServiceInstanceResponse:
    require_desktop_host(request, "service_credentials")
    return _run(lambda: MqttServiceInstanceResponse(instance=_service().set_credentials(instance_id, payload)))


@router.get(
    "/instances/{instance_id}/samples",
    response_model=MqttServiceSamplesResponse,
)
def mqtt_samples(
    instance_id: str,
    limit: int = Query(default=100, ge=1, le=200),
) -> MqttServiceSamplesResponse:
    return _run(lambda: _service().samples(instance_id, limit=limit))


def shutdown_mqtt_service() -> None:
    global _mqtt_service
    service = _mqtt_service
    _mqtt_service = None
    if service is not None:
        service.shutdown()


def recover_mqtt_service() -> None:
    _service().recover_incomplete()


def _service() -> MqttService:
    global _mqtt_service
    data_dir = Path(settings.data_dir).resolve()
    if _mqtt_service is not None and _mqtt_service.data_dir != data_dir:
        _mqtt_service.shutdown()
        _mqtt_service = None
    if _mqtt_service is None:
        _mqtt_service = MqttService(data_dir)
    return _mqtt_service


def _run(operation):
    try:
        return operation()
    except MqttServiceError as exc:
        detail: dict[str, object] = {
            "code": exc.code,
            "message": str(exc),
            "retryable": exc.retryable,
        }
        if isinstance(exc, MqttConfirmationRequiredError):
            detail["confirmationToken"] = exc.confirmation_token
        raise HTTPException(status_code=exc.status_code, detail=detail) from exc
