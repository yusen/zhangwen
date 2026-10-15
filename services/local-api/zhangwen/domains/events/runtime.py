"""In-process wake-up hub and bounded telemetry fan-out."""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic

from zhangwen.domains.events.models import (
    TelemetryPublication,
    TelemetrySample,
    TelemetrySubscription,
)
from zhangwen.domains.events.privacy import validate_telemetry_payload
from zhangwen.domains.events.store import RealtimeEventStore
from zhangwen.projects.repository import ProjectRepository


class RealtimeEventHub:
    def __init__(
        self,
        data_dir: Path,
        *,
        poll_interval_seconds: float = 0.1,
    ) -> None:
        db_path = ProjectRepository(data_dir).db_path
        self._store = RealtimeEventStore(db_path)
        self._poll_interval = max(0.01, poll_interval_seconds)
        self._condition = asyncio.Condition()
        self._generation = 0
        self._task: asyncio.Task[None] | None = None
        self._stopping = False

    @property
    def generation(self) -> int:
        return self._generation

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stopping = False
        self._task = asyncio.create_task(
            self._run(),
            name="realtime-event-outbox",
        )

    async def stop(self) -> None:
        self._stopping = True
        task = self._task
        self._task = None
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    def dispatch_pending_once(self) -> int:
        return self._store.publish_pending()

    async def wait_after(self, generation: int, *, timeout: float) -> bool:
        if self._generation != generation:
            return True
        try:
            async with asyncio.timeout(timeout):
                async with self._condition:
                    await self._condition.wait_for(
                        lambda: self._generation != generation
                    )
            return True
        except TimeoutError:
            return False

    async def _run(self) -> None:
        while not self._stopping:
            published = self._store.publish_pending()
            if published:
                async with self._condition:
                    self._generation += 1
                    self._condition.notify_all()
                continue
            await asyncio.sleep(self._poll_interval)


@dataclass
class _TelemetrySubscriber:
    internal_id: str
    subscription_id: str
    subscription: TelemetrySubscription
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue[TelemetrySample]
    dropped_total: int = 0
    last_enqueued_at: float = 0.0


class TelemetryHub:
    def __init__(self, *, queue_size: int = 32) -> None:
        self._queue_size = max(1, min(queue_size, 256))
        self._lock = threading.RLock()
        self._subscribers: dict[str, _TelemetrySubscriber] = {}

    def subscribe(
        self,
        subscription_id: str,
        subscription: TelemetrySubscription,
        *,
        internal_id: str | None = None,
    ) -> asyncio.Queue[TelemetrySample]:
        subscriber_key = internal_id or subscription_id
        subscriber = _TelemetrySubscriber(
            internal_id=subscriber_key,
            subscription_id=subscription_id,
            subscription=subscription,
            loop=asyncio.get_running_loop(),
            queue=asyncio.Queue(maxsize=self._queue_size),
        )
        with self._lock:
            self._subscribers[subscriber_key] = subscriber
        return subscriber.queue

    def unsubscribe(self, internal_id: str) -> None:
        with self._lock:
            self._subscribers.pop(internal_id, None)

    def publish(
        self,
        *,
        work_id: str,
        payload: dict[str, object],
        device_id: str | None = None,
        service_instance_id: str | None = None,
        topic_contract_id: str | None = None,
    ) -> None:
        publication = TelemetryPublication(
            workId=work_id,
            payload=validate_telemetry_payload(payload),
            deviceId=device_id,
            serviceInstanceId=service_instance_id,
            topicContractId=topic_contract_id,
        )
        with self._lock:
            subscribers = tuple(self._subscribers.values())
        for subscriber in subscribers:
            if not _matches(subscriber.subscription, publication):
                continue
            try:
                subscriber.loop.call_soon_threadsafe(
                    self._enqueue,
                    subscriber,
                    publication,
                )
            except RuntimeError:
                # A disconnect may close its loop after the subscriber snapshot.
                continue

    @staticmethod
    def _enqueue(
        subscriber: _TelemetrySubscriber,
        publication: TelemetryPublication,
    ) -> None:
        now = monotonic()
        minimum_interval = 1.0 / subscriber.subscription.max_rate_hz
        if now - subscriber.last_enqueued_at < minimum_interval:
            subscriber.dropped_total += 1
            return
        if subscriber.queue.full():
            try:
                subscriber.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            subscriber.dropped_total += 1
        subscriber.last_enqueued_at = now
        subscriber.queue.put_nowait(
            TelemetrySample(
                subscriptionId=subscriber.subscription_id,
                sampledAt=datetime.now(UTC).isoformat(),
                droppedSamples=subscriber.dropped_total,
                payload=publication.payload,
            )
        )


def _matches(
    subscription: TelemetrySubscription,
    publication: TelemetryPublication,
) -> bool:
    return (
        subscription.work_id == publication.work_id
        and _optional_match(subscription.device_id, publication.device_id)
        and _optional_match(
            subscription.service_instance_id,
            publication.service_instance_id,
        )
        and _optional_match(
            subscription.topic_contract_id,
            publication.topic_contract_id,
        )
    )


def _optional_match(expected: str | None, actual: str | None) -> bool:
    return expected is None or expected == actual


_EVENT_HUBS: dict[Path, RealtimeEventHub] = {}
_TELEMETRY_HUB: TelemetryHub | None = None


def realtime_event_hub(
    data_dir: Path,
    *,
    poll_interval_seconds: float = 0.1,
) -> RealtimeEventHub:
    resolved = Path(data_dir).resolve()
    hub = _EVENT_HUBS.get(resolved)
    if hub is None:
        hub = RealtimeEventHub(
            resolved,
            poll_interval_seconds=poll_interval_seconds,
        )
        _EVENT_HUBS[resolved] = hub
    return hub


async def stop_realtime_event_hubs() -> None:
    hubs = tuple(_EVENT_HUBS.values())
    _EVENT_HUBS.clear()
    for hub in hubs:
        await hub.stop()


def telemetry_hub(*, queue_size: int = 32) -> TelemetryHub:
    global _TELEMETRY_HUB
    if _TELEMETRY_HUB is None:
        _TELEMETRY_HUB = TelemetryHub(queue_size=queue_size)
    return _TELEMETRY_HUB
