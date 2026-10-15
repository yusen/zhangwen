"""Recoverable SSE events and bounded telemetry WebSocket endpoints."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from fastapi import APIRouter, Header, HTTPException, Query, WebSocket
from fastapi.responses import StreamingResponse
from fastapi.websockets import WebSocketDisconnect
from pydantic import ValidationError

from zhangwen.auth.context import bind_owner_subject, reset_owner_subject
from zhangwen.auth.middleware import auth_enforcement_enabled
from zhangwen.auth.repository import AuthError, AuthRepository
from zhangwen.config import settings
from zhangwen.creator.repository import CreatorError
from zhangwen.domains.events.models import (
    EventEnvelope,
    EventScope,
    MODEL_SETTINGS_SCOPE_ID,
    TelemetrySample,
    TelemetrySubscribeCommand,
)
from zhangwen.domains.events.runtime import realtime_event_hub, telemetry_hub
from zhangwen.domains.events.store import RealtimeEventStore
from zhangwen.domains.inventory.repository import DevicePlatformRepository
from zhangwen.domains.mqtt_service.models import MqttServiceError
from zhangwen.domains.mqtt_service.repository import MqttServiceRepository
from zhangwen.domains.packages.models import PackagePlatformError
from zhangwen.domains.packages.repository import PackagePlatformRepository
from zhangwen.domains.works.repository import WorkRepository
from zhangwen.projects.errors import ProjectError
from zhangwen.projects.repository import ProjectRepository


router = APIRouter(tags=["realtime"])
_SSE_HEARTBEAT_SECONDS = 15.0
_TELEMETRY_PROTOCOL = "zhangwen.telemetry.v1"


@router.get("/api/events")
async def stream_events(
    work_id: str | None = Query(default=None, alias="workId", min_length=1),
    package_id: str | None = Query(default=None, alias="packageId", min_length=1),
    device_id: str | None = Query(default=None, alias="deviceId", min_length=1),
    service_instance_id: str | None = Query(
        default=None,
        alias="serviceInstanceId",
        min_length=1,
    ),
    system_id: str | None = Query(default=None, alias="systemId", min_length=1),
    follow: bool = Query(default=True),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> StreamingResponse:
    provided_scopes = sum(
        value is not None
        for value in (
            work_id,
            package_id,
            device_id,
            service_instance_id,
            system_id,
        )
    )
    if provided_scopes != 1:
        raise HTTPException(
            status_code=422,
            detail=(
                "workId、packageId、deviceId、serviceInstanceId 与 systemId "
                "必须且只能提供一个。"
            ),
        )
    if work_id is not None:
        scope = EventScope.WORK
        scope_id = work_id
    elif package_id is not None:
        scope = EventScope.PACKAGE
        scope_id = package_id
    elif device_id is not None:
        scope = EventScope.DEVICE
        scope_id = device_id
    elif service_instance_id is not None:
        scope = EventScope.SERVICE
        scope_id = service_instance_id
    else:
        scope = EventScope.SYSTEM
        scope_id = system_id
    assert scope_id is not None
    if scope is EventScope.WORK:
        _assert_work_access(scope_id)
    elif scope is EventScope.PACKAGE:
        _assert_package_access(scope_id)
    elif scope is EventScope.DEVICE:
        _assert_device_access(scope_id)
    elif scope is EventScope.SERVICE:
        _assert_service_access(scope_id)
    else:
        _assert_system_access(scope_id)
    store = RealtimeEventStore(ProjectRepository(settings.data_dir).db_path)
    hub = realtime_event_hub(settings.data_dir)

    async def generate() -> AsyncIterator[str]:
        if last_event_id is None:
            cursor = 0
        else:
            retained_position = store.scope_event_position(
                last_event_id,
                scope=scope,
                scope_id=scope_id,
            )
            if retained_position is None:
                yield _sse_frame(_snapshot_required(scope, scope_id, store))
                cursor = store.latest_scope_position(scope, scope_id)
            else:
                cursor = retained_position

        while True:
            generation = hub.generation
            events = store.list_scope_events(
                scope,
                scope_id,
                after_position=cursor,
            )
            for event in events:
                position = store.event_position(event.id)
                if position is not None:
                    cursor = position
                yield _sse_frame(event)
            if not follow:
                return
            changed = await hub.wait_after(
                generation,
                timeout=_SSE_HEARTBEAT_SECONDS,
            )
            if not changed:
                yield ": heartbeat\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
            "X-Zhangwen-Event-Contract": "1",
        },
    )


@router.websocket("/api/telemetry")
async def telemetry_socket(websocket: WebSocket) -> None:
    owner_subject = await _websocket_owner_subject(websocket)
    if owner_subject is None:
        return
    owner_token = bind_owner_subject(owner_subject) if owner_subject else None
    connection_id = uuid.uuid4().hex
    subscriptions: dict[str, tuple[str, asyncio.Task[None]]] = {}
    send_lock = asyncio.Lock()
    hub = telemetry_hub()
    try:
        await websocket.accept(subprotocol=_TELEMETRY_PROTOCOL)
        while True:
            try:
                raw = await websocket.receive_json()
            except json.JSONDecodeError:
                await _send_json(
                    websocket,
                    send_lock,
                    {
                        "type": "error",
                        "code": "TELEMETRY_SUBSCRIPTION_INVALID",
                        "message": "订阅请求不是有效 JSON。",
                    },
                )
                continue
            try:
                command = TelemetrySubscribeCommand.model_validate(raw)
                _assert_work_access(command.subscription.work_id)
            except (HTTPException, ValidationError, ProjectError):
                await _send_json(
                    websocket,
                    send_lock,
                    {
                        "type": "error",
                        "code": "TELEMETRY_SUBSCRIPTION_INVALID",
                        "message": "订阅请求无效或无权访问该作品。",
                    },
                )
                continue
            old_subscription = subscriptions.pop(command.subscription_id, None)
            if old_subscription is not None:
                old_internal_id, old_task = old_subscription
                old_task.cancel()
                hub.unsubscribe(old_internal_id)
            internal_id = f"{connection_id}:{command.subscription_id}"
            queue = hub.subscribe(
                command.subscription_id,
                command.subscription,
                internal_id=internal_id,
            )
            await _send_json(
                websocket,
                send_lock,
                {
                    "type": "subscribed",
                    "subscriptionId": command.subscription_id,
                },
            )
            subscriptions[command.subscription_id] = (
                internal_id,
                asyncio.create_task(
                    _send_telemetry_samples(
                        websocket,
                        send_lock,
                        queue,
                    ),
                    name=f"telemetry-{connection_id}-{command.subscription_id}",
                ),
            )
    except WebSocketDisconnect:
        pass
    finally:
        for internal_id, task in subscriptions.values():
            hub.unsubscribe(internal_id)
            task.cancel()
        if subscriptions:
            await asyncio.gather(
                *(task for _, task in subscriptions.values()),
                return_exceptions=True,
            )
        if owner_token is not None:
            reset_owner_subject(owner_token)


async def _send_telemetry_samples(
    websocket: WebSocket,
    send_lock: asyncio.Lock,
    queue: asyncio.Queue[TelemetrySample],
) -> None:
    while True:
        sample = await queue.get()
        await _send_json(
            websocket,
            send_lock,
            {
                "type": "sample",
                "sample": sample.model_dump(mode="json", by_alias=True),
            },
        )


async def _send_json(
    websocket: WebSocket,
    lock: asyncio.Lock,
    payload: dict[str, object],
) -> None:
    async with lock:
        await websocket.send_json(payload)


def _snapshot_required(
    scope: EventScope,
    scope_id: str,
    store: RealtimeEventStore,
) -> EventEnvelope:
    latest = max(store.latest_scope_seq(scope, scope_id), 1)
    return EventEnvelope(
        id=f"snapshot_{uuid.uuid4().hex}",
        seq=latest,
        scope=scope,
        scopeId=scope_id,
        type="snapshot.required",
        revision=latest,
        occurredAt=datetime.now(UTC).isoformat(),
        durable=False,
        payload={"reason": "CURSOR_NOT_RETAINED"},
    )


def _sse_frame(event: EventEnvelope) -> str:
    encoded = json.dumps(
        event.model_dump(mode="json", by_alias=True),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return f"id: {event.id}\nevent: {event.type}\ndata: {encoded}\n\n"


def _assert_work_access(work_id: str) -> None:
    try:
        WorkRepository(settings.data_dir).snapshot(work_id)
    except (CreatorError, ProjectError) as exc:
        raise HTTPException(status_code=404, detail="作品不存在。") from exc


def _assert_package_access(package_id: str) -> None:
    try:
        PackagePlatformRepository(settings.data_dir).get_package(package_id)
    except PackagePlatformError as exc:
        raise HTTPException(status_code=404, detail="能力包不存在。") from exc


def _assert_device_access(device_id: str) -> None:
    if not DevicePlatformRepository(settings.data_dir).can_access_device_scope(
        device_id
    ):
        raise HTTPException(status_code=404, detail="设备记录不存在。")


def _assert_service_access(instance_id: str) -> None:
    try:
        MqttServiceRepository(settings.data_dir).get_instance(instance_id)
    except MqttServiceError as exc:
        raise HTTPException(status_code=404, detail="本机服务不存在。") from exc


def _assert_system_access(system_id: str) -> None:
    if system_id != MODEL_SETTINGS_SCOPE_ID:
        raise HTTPException(status_code=404, detail="系统实时范围不存在。")


async def _websocket_owner_subject(websocket: WebSocket) -> str | None:
    if not auth_enforcement_enabled():
        return ""
    origin = websocket.headers.get("origin", "").rstrip("/")
    if origin not in settings.cors_origins:
        await websocket.close(code=4403, reason="Origin not allowed")
        return None
    protocols = {
        item.strip()
        for item in websocket.headers.get("sec-websocket-protocol", "").split(",")
        if item.strip()
    }
    auth_protocol = next(
        (item for item in protocols if item.startswith("zhangwen.auth.")),
        None,
    )
    if _TELEMETRY_PROTOCOL not in protocols or auth_protocol is None:
        await websocket.close(code=4401, reason="Authentication required")
        return None
    token = auth_protocol.removeprefix("zhangwen.auth.")
    repository = AuthRepository(settings.data_dir)
    try:
        session = repository.validate_session(token)
    except AuthError:
        await websocket.close(code=4401, reason="Invalid session")
        return None
    cloud_identity = repository.cloud_identity(session.account.id)
    return (
        str(cloud_identity["subject"])
        if cloud_identity is not None
        else session.account.id
    )
