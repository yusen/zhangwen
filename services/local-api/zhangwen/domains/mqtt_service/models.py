"""Strict public and internal contracts for supervised MQTT services."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    SecretStr,
    field_validator,
    model_validator,
)


class MqttModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )


class MqttMode(StrEnum):
    SIMULATED = "SIMULATED"
    LOOPBACK = "LOOPBACK"
    LAN = "LAN"
    EXTERNAL = "EXTERNAL"


class MqttServiceStatus(StrEnum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    FAILED_NEEDS_ATTENTION = "FAILED_NEEDS_ATTENTION"


class MqttTopicDirection(StrEnum):
    PUBLISH = "PUBLISH"
    SUBSCRIBE = "SUBSCRIBE"
    BOTH = "BOTH"


class MqttSampleDirection(StrEnum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class MqttTopicRule(MqttModel):
    id: str = Field(min_length=1, max_length=120, pattern=r"^[a-zA-Z0-9_.-]+$")
    topic_pattern: str = Field(alias="topicPattern", min_length=1, max_length=512)
    direction: MqttTopicDirection
    payload_schema: dict[str, JsonValue] = Field(alias="payloadSchema")
    max_payload_bytes: int = Field(alias="maxPayloadBytes", ge=1, le=16_384)
    max_rate_hz: float = Field(alias="maxRateHz", ge=0.1, le=100.0)
    qos: Literal[0, 1, 2]
    retain: bool
    principal: str = Field(min_length=1, max_length=120, pattern=r"^[a-zA-Z0-9_.-]+$")


class MqttTopicContractRevision(MqttModel):
    id: str
    revision: int = Field(ge=1)
    work_id: str = Field(alias="workId")
    namespace: str
    rules: list[MqttTopicRule] = Field(min_length=1, max_length=64)
    acl_digest: str = Field(alias="aclDigest", min_length=64, max_length=64)
    created_at: str = Field(alias="createdAt")


class MqttServiceInstance(MqttModel):
    id: str
    work_id: str = Field(alias="workId")
    mode: MqttMode
    status: MqttServiceStatus
    service_package_revision_id: str = Field(alias="servicePackageRevisionId")
    topic_contract_revision_id: str = Field(alias="topicContractRevisionId")
    topic_contract: MqttTopicContractRevision = Field(alias="topicContract")
    config_artifact_id: str = Field(alias="configArtifactId")
    config_artifact_version_id: str = Field(alias="configArtifactVersionId")
    config_digest: str = Field(alias="configDigest")
    credential_ref: str | None = Field(alias="credentialRef")
    credential_configured: bool = Field(alias="credentialConfigured")
    listen_host: str | None = Field(alias="listenHost")
    listen_port: int | None = Field(alias="listenPort")
    external_endpoint: str | None = Field(alias="externalEndpoint")
    auto_recover: bool = Field(alias="autoRecover")
    restart_count: int = Field(alias="restartCount", ge=0)
    sample_drop_count: int = Field(alias="sampleDropCount", ge=0)
    last_error: str | None = Field(alias="lastError")
    natural_status: str = Field(alias="naturalStatus")
    revision: int = Field(ge=1)
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class CreateMqttServiceInstanceRequest(MqttModel):
    work_id: str = Field(alias="workId", min_length=1, max_length=160)
    mode: MqttMode
    idempotency_key: str = Field(alias="idempotencyKey", min_length=8, max_length=128)
    rules: list[MqttTopicRule] | None = Field(default=None, max_length=64)
    listen_host: str | None = Field(default=None, alias="listenHost", max_length=255)
    listen_port: int | None = Field(default=None, alias="listenPort", ge=1, le=65535)
    external_endpoint: str | None = Field(
        default=None,
        alias="externalEndpoint",
        max_length=512,
    )
    external_tls: bool = Field(default=True, alias="externalTls")
    auto_recover: bool = Field(default=False, alias="autoRecover")

    @model_validator(mode="after")
    def validate_mode_configuration(self) -> "CreateMqttServiceInstanceRequest":
        if self.mode is MqttMode.SIMULATED:
            if self.listen_host or self.listen_port or self.external_endpoint:
                raise ValueError("进程内仿真不能声明监听或外部地址。")
        elif self.mode is MqttMode.LOOPBACK:
            if self.listen_host not in {None, "127.0.0.1", "::1"}:
                raise ValueError("仅本机模式只能绑定回环地址。")
            if self.external_endpoint is not None:
                raise ValueError("仅本机模式不能声明外部地址。")
        elif self.mode is MqttMode.LAN:
            if self.listen_host in {None, "", "0.0.0.0", "::", "127.0.0.1", "::1"}:
                raise ValueError("家庭网络模式必须选择一个具体的私有网络地址。")
            if self.external_endpoint is not None:
                raise ValueError("家庭网络模式不能声明外部地址。")
        elif self.mode is MqttMode.EXTERNAL:
            if not self.external_endpoint:
                raise ValueError("已有通信服务模式必须声明外部地址。")
            if not self.external_tls:
                raise ValueError("已有通信服务必须启用 TLS，禁止明文回退。")
            if self.listen_host or self.listen_port:
                raise ValueError("已有通信服务模式不能创建本地监听。")
        if self.auto_recover and self.mode is not MqttMode.LOOPBACK:
            raise ValueError("自动恢复只适用于仅本机模式。")
        return self


class MqttLifecycleRequest(MqttModel):
    idempotency_key: str = Field(alias="idempotencyKey", min_length=8, max_length=128)
    expected_revision: int = Field(alias="expectedRevision", ge=1)
    confirmation_token: str | None = Field(
        default=None,
        alias="confirmationToken",
        max_length=512,
    )


class UpdateMqttTopicContractRequest(MqttModel):
    idempotency_key: str = Field(alias="idempotencyKey", min_length=8, max_length=128)
    expected_revision: int = Field(alias="expectedRevision", ge=1)
    rules: list[MqttTopicRule] = Field(min_length=1, max_length=64)
    confirmation_token: str | None = Field(
        default=None,
        alias="confirmationToken",
        max_length=512,
    )


class SetMqttCredentialsRequest(MqttModel):
    idempotency_key: str = Field(alias="idempotencyKey", min_length=8, max_length=128)
    expected_revision: int = Field(alias="expectedRevision", ge=1)
    username: str = Field(min_length=1, max_length=256)
    password: SecretStr
    confirmation_token: str | None = Field(
        default=None,
        alias="confirmationToken",
        max_length=512,
    )

    @field_validator("username")
    @classmethod
    def strip_username(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("用户名不能为空。")
        return stripped

    @field_validator("password")
    @classmethod
    def validate_password_length(cls, value: SecretStr) -> SecretStr:
        if not 8 <= len(value.get_secret_value()) <= 4096:
            raise ValueError("密码长度必须在 8 到 4096 个字符之间。")
        return value


class MqttServiceInstanceResponse(MqttModel):
    instance: MqttServiceInstance


class MqttServiceStatusResponse(MqttModel):
    instances: list[MqttServiceInstance]
    local_process_running: bool = Field(alias="localProcessRunning")
    natural_status: str = Field(alias="naturalStatus")


class MqttServiceSample(MqttModel):
    id: str
    instance_id: str = Field(alias="instanceId")
    topic: str
    direction: MqttSampleDirection
    payload: dict[str, JsonValue]
    payload_bytes: int = Field(alias="payloadBytes", ge=0)
    sampled_at: str = Field(alias="sampledAt")


class MqttServiceSamplesResponse(MqttModel):
    samples: list[MqttServiceSample]
    dropped_samples: int = Field(alias="droppedSamples", ge=0)


class MqttServiceError(RuntimeError):
    code = "MQTT_SERVICE_ERROR"
    status_code = 422
    retryable = False


class MqttServiceNotFoundError(MqttServiceError):
    code = "MQTT_SERVICE_NOT_FOUND"
    status_code = 404


class MqttServiceConflictError(MqttServiceError):
    code = "MQTT_SERVICE_REVISION_CONFLICT"
    status_code = 409
    retryable = True


class MqttServiceValidationError(MqttServiceError):
    code = "MQTT_SERVICE_INVALID"


class MqttServiceUnavailableError(MqttServiceError):
    code = "MQTT_SERVICE_UNAVAILABLE"
    status_code = 503
    retryable = True


class MqttConfirmationRequiredError(MqttServiceError):
    code = "MQTT_SERVICE_CONFIRMATION_REQUIRED"
    status_code = 409
    retryable = True

    def __init__(self, message: str, confirmation_token: str) -> None:
        super().__init__(message)
        self.confirmation_token = confirmation_token
