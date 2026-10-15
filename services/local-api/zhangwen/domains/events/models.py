"""Strict realtime API and in-process hub contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


class RealtimeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class EventScope(StrEnum):
    WORK = "WORK"
    PACKAGE = "PACKAGE"
    DEVICE = "DEVICE"
    SERVICE = "SERVICE"
    SYSTEM = "SYSTEM"


MODEL_SETTINGS_SCOPE_ID = "model-settings"


class EventEnvelope(RealtimeModel):
    id: str = Field(min_length=1, max_length=160)
    seq: int = Field(ge=1)
    scope: EventScope
    scope_id: str = Field(alias="scopeId", min_length=1, max_length=160)
    type: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,127}$")
    revision: int = Field(ge=1)
    occurred_at: str = Field(alias="occurredAt")
    durable: bool
    payload: dict[str, JsonValue]


class TelemetrySubscription(RealtimeModel):
    work_id: str = Field(alias="workId", min_length=1, max_length=160)
    device_id: str | None = Field(default=None, alias="deviceId", max_length=160)
    service_instance_id: str | None = Field(
        default=None,
        alias="serviceInstanceId",
        max_length=160,
    )
    topic_contract_id: str | None = Field(
        default=None,
        alias="topicContractId",
        max_length=160,
    )
    max_rate_hz: float = Field(default=10.0, alias="maxRateHz", ge=0.1, le=10.0)

    @model_validator(mode="after")
    def normalize_optional_ids(self) -> "TelemetrySubscription":
        for field_name in (
            "device_id",
            "service_instance_id",
            "topic_contract_id",
        ):
            value = getattr(self, field_name)
            if value is not None and not value.strip():
                raise ValueError(f"{field_name} cannot be blank")
        return self


class TelemetrySubscribeCommand(RealtimeModel):
    action: Literal["subscribe"]
    subscription_id: str = Field(
        alias="subscriptionId",
        min_length=1,
        max_length=120,
    )
    subscription: TelemetrySubscription


class TelemetrySample(RealtimeModel):
    subscription_id: str = Field(alias="subscriptionId")
    sampled_at: str = Field(alias="sampledAt")
    dropped_samples: int = Field(alias="droppedSamples", ge=0)
    payload: dict[str, JsonValue]


class TelemetryPublication(RealtimeModel):
    work_id: str = Field(alias="workId", min_length=1, max_length=160)
    payload: dict[str, JsonValue]
    device_id: str | None = Field(default=None, alias="deviceId", max_length=160)
    service_instance_id: str | None = Field(
        default=None,
        alias="serviceInstanceId",
        max_length=160,
    )
    topic_contract_id: str | None = Field(
        default=None,
        alias="topicContractId",
        max_length=160,
    )
