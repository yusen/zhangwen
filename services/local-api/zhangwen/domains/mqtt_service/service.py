"""Application service for MQTT lifecycle, confirmation, credentials, and telemetry."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from zhangwen.config import settings
from zhangwen.domains.events.runtime import telemetry_hub
from zhangwen.domains.mqtt_service.contracts import (
    default_topic_rules,
    topic_matches,
    validate_and_compile,
    validate_lan_host,
    validate_payload_against_schema,
)
from zhangwen.domains.mqtt_service.models import (
    CreateMqttServiceInstanceRequest,
    MqttConfirmationRequiredError,
    MqttLifecycleRequest,
    MqttMode,
    MqttSampleDirection,
    MqttServiceConflictError,
    MqttServiceInstance,
    MqttServiceSamplesResponse,
    MqttServiceStatus,
    MqttServiceStatusResponse,
    SetMqttCredentialsRequest,
    UpdateMqttTopicContractRequest,
)
from zhangwen.domains.mqtt_service.repository import MqttServiceRepository
from zhangwen.domains.mqtt_service.supervisor import MqttBrokerSupervisor
from zhangwen.security.credentials import BackendCredentialStore, CredentialStore


_CONFIRMATION_TTL_SECONDS = 180
_MAX_RESTARTS = 3


class MqttService:
    def __init__(
        self,
        data_dir: Path,
        *,
        supervisor: MqttBrokerSupervisor | None = None,
        credential_store: CredentialStore | None = None,
        confirmation_secret: bytes | None = None,
        restart_backoff_seconds: float = 0.25,
    ) -> None:
        self.data_dir = Path(data_dir).resolve()
        self._repository = MqttServiceRepository(self.data_dir)
        self._supervisor = supervisor or MqttBrokerSupervisor(self.data_dir)
        self._credentials = credential_store or BackendCredentialStore()
        self._confirmation_secret = confirmation_secret or secrets.token_bytes(32)
        self._restart_backoff = max(0.0, restart_backoff_seconds)
        self._recoveries: dict[str, float] = {}

    def status(self) -> MqttServiceStatusResponse:
        self._poll_and_recover()
        instances = self._repository.list_instances()
        running = [item for item in instances if item.status is MqttServiceStatus.RUNNING]
        if running:
            natural = f"{len(running)} 个设备通信服务正在运行。"
        elif any(item.status is MqttServiceStatus.FAILED_NEEDS_ATTENTION for item in instances):
            natural = "设备通信需要处理后才能继续。"
        else:
            natural = "当前没有运行中的设备通信服务。"
        return MqttServiceStatusResponse(
            instances=instances,
            localProcessRunning=self._supervisor.local_process_running,
            naturalStatus=natural,
        )

    def create(self, request: CreateMqttServiceInstanceRequest) -> MqttServiceInstance:
        if request.mode is MqttMode.LAN:
            assert request.listen_host is not None
            validate_lan_host(request.listen_host)
        rules = request.rules or default_topic_rules(request.work_id)
        return self._repository.create_instance(request, rules)

    def get(self, instance_id: str) -> MqttServiceInstance:
        self._poll_and_recover(instance_id)
        return self._repository.get_instance(instance_id)

    def start(self, instance_id: str, request: MqttLifecycleRequest) -> MqttServiceInstance:
        instance = self._repository.get_instance(instance_id)
        replay = self._repository.replayed_command(
            instance.id,
            operation="START",
            idempotency_key=request.idempotency_key,
            request_digest=_digest(
                {
                    "expectedRevision": request.expected_revision,
                    "status": MqttServiceStatus.RUNNING.value,
                }
            ),
        )
        if replay is not None:
            return replay
        if instance.status is MqttServiceStatus.RUNNING:
            raise MqttServiceConflictError("设备通信已经启动；请刷新后使用当前状态。")
        if instance.revision != request.expected_revision:
            raise MqttServiceConflictError("服务状态已经变化，请刷新后重试。")
        if instance.status not in {
            MqttServiceStatus.STOPPED,
            MqttServiceStatus.FAILED_NEEDS_ATTENTION,
        }:
            raise MqttServiceConflictError("服务正在切换状态，请稍后重试。")
        if instance.mode in {MqttMode.LAN, MqttMode.EXTERNAL}:
            self._require_confirmation(
                instance,
                "START_NETWORK_SERVICE",
                request.confirmation_token,
                "启用家庭网络或已有通信服务前需要再次确认。",
            )
        if instance.mode is not MqttMode.SIMULATED:
            self._require_credentials(instance)
        config = self._repository.private_config(instance.id)
        config_digest: str | None = None
        if instance.mode in {MqttMode.LOOPBACK, MqttMode.LAN}:
            config, config_digest = self._local_broker_config()
        try:
            pid = self._supervisor.start(
                instance,
                config,
                config_digest=config_digest,
            )
            started = self._repository.transition(
                instance.id,
                expected_revision=instance.revision,
                idempotency_key=request.idempotency_key,
                operation="START",
                status=MqttServiceStatus.RUNNING,
                natural_status=_running_status(instance.mode),
                process_pid=pid,
                last_error=None,
            )
        except Exception as exc:
            self._supervisor.stop(instance.id)
            if isinstance(exc, (MqttServiceConflictError, MqttConfirmationRequiredError)):
                raise
            try:
                self._repository.transition(
                    instance.id,
                    expected_revision=instance.revision,
                    idempotency_key=f"{request.idempotency_key}:failed",
                    operation="START_FAILED",
                    status=MqttServiceStatus.FAILED_NEEDS_ATTENTION,
                    natural_status="设备通信没有启动，检查本机运行组件或连接设置后重试。",
                    last_error=str(exc),
                )
            except MqttServiceConflictError:
                pass
            raise
        self._publish_state(started, "RUNNING")
        return started

    def stop(self, instance_id: str, request: MqttLifecycleRequest) -> MqttServiceInstance:
        instance = self._repository.get_instance(instance_id)
        replay = self._repository.replayed_command(
            instance.id,
            operation="STOP",
            idempotency_key=request.idempotency_key,
            request_digest=_digest(
                {
                    "expectedRevision": request.expected_revision,
                    "status": MqttServiceStatus.STOPPED.value,
                }
            ),
        )
        if replay is not None:
            return replay
        if instance.status is MqttServiceStatus.STOPPED:
            raise MqttServiceConflictError("设备通信已经停止；请刷新后使用当前状态。")
        if instance.revision != request.expected_revision:
            raise MqttServiceConflictError("服务状态已经变化，请刷新后重试。")
        self._supervisor.stop(instance.id)
        self._recoveries.pop(instance.id, None)
        stopped = self._repository.transition(
            instance.id,
            expected_revision=instance.revision,
            idempotency_key=request.idempotency_key,
            operation="STOP",
            status=MqttServiceStatus.STOPPED,
            natural_status="设备通信已安全停止。",
            process_pid=None,
            last_error=None,
        )
        self._publish_state(stopped, "STOPPED")
        return stopped

    def update_contract(
        self,
        instance_id: str,
        request: UpdateMqttTopicContractRequest,
    ) -> MqttServiceInstance:
        instance = self._repository.get_instance(instance_id)
        request_digest = _digest(
            {
                "expectedRevision": request.expected_revision,
                "rules": [
                    item.model_dump(mode="json", by_alias=True)
                    for item in request.rules
                ],
            }
        )
        replay = self._repository.replayed_command(
            instance.id,
            operation="UPDATE_CONTRACT",
            idempotency_key=request.idempotency_key,
            request_digest=request_digest,
        )
        if replay is not None:
            return replay
        if instance.revision != request.expected_revision:
            raise MqttServiceConflictError("服务状态已经变化，请刷新后重试。")
        _, compiled, _ = validate_and_compile(instance.work_id, request.rules)
        current = {
            (rule.principal, access, rule.topic_pattern)
            for rule in instance.topic_contract.rules
            for access in _access(rule.direction.value)
        }
        candidate = {
            (str(item["principal"]), str(item["access"]), str(item["topic"]))
            for item in compiled
        }
        if candidate - current:
            self._require_confirmation(
                instance,
                "EXPAND_TOPIC_ACCESS",
                request.confirmation_token,
                "扩大设备通信范围前需要再次确认。",
            )
        return self._repository.update_topic_contract(
            instance.id,
            expected_revision=request.expected_revision,
            idempotency_key=request.idempotency_key,
            rules=request.rules,
        )

    def set_credentials(
        self,
        instance_id: str,
        request: SetMqttCredentialsRequest,
    ) -> MqttServiceInstance:
        instance = self._repository.get_instance(instance_id)
        password = request.password.get_secret_value()
        request_digest = hashlib.sha256(
            f"{request.username}\0{password}".encode("utf-8")
        ).hexdigest()
        replay = self._repository.replayed_command(
            instance.id,
            operation="SET_CREDENTIALS",
            idempotency_key=request.idempotency_key,
            request_digest=request_digest,
        )
        if replay is not None:
            return replay
        if instance.revision != request.expected_revision:
            raise MqttServiceConflictError("服务状态已经变化，请刷新后重试。")
        self._require_confirmation(
            instance,
            "REPLACE_CREDENTIALS",
            request.confirmation_token,
            "保存或更换设备通信身份前需要再次确认。",
        )
        account = instance.id
        service = settings.mqtt_credential_service
        previous = self._credentials.get_password(service, account)
        encoded = json.dumps(
            {"username": request.username, "password": password},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        credential_digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        credential_ref = f"credential://{service}/{account}"
        self._credentials.set_password(service, account, encoded)
        try:
            return self._repository.set_credentials_reference(
                instance.id,
                expected_revision=request.expected_revision,
                idempotency_key=request.idempotency_key,
                credential_ref=credential_ref,
                credential_digest=credential_digest,
                request_digest=request_digest,
            )
        except Exception:
            if previous is None:
                self._credentials.delete_password(service, account)
            else:
                self._credentials.set_password(service, account, previous)
            raise

    def samples(self, instance_id: str, *, limit: int = 100) -> MqttServiceSamplesResponse:
        return self._repository.list_samples(instance_id, limit=limit)

    def sample(
        self,
        instance_id: str,
        *,
        topic: str,
        direction: MqttSampleDirection,
        payload: dict[str, object],
    ) -> None:
        instance = self._repository.get_instance(instance_id)
        if instance.status is not MqttServiceStatus.RUNNING:
            raise MqttServiceConflictError("设备通信未运行，不能记录实时样本。")
        if not topic.startswith(f"{instance.topic_contract.namespace}/"):
            raise MqttServiceConflictError("消息超出当前作品范围。")
        if "+" in topic or "#" in topic or topic.startswith("$"):
            raise MqttServiceConflictError("实际消息主题不能包含通配符或系统主题。")
        accepted_directions = (
            {"SUBSCRIBE", "BOTH"}
            if direction is MqttSampleDirection.INBOUND
            else {"PUBLISH", "BOTH"}
        )
        rule = next(
            (
                item
                for item in instance.topic_contract.rules
                if item.direction.value in accepted_directions
                and topic_matches(item.topic_pattern, topic)
            ),
            None,
        )
        if rule is None:
            raise MqttServiceConflictError("消息没有在当前作品的通信规则中声明。")
        payload_bytes = len(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        if payload_bytes > rule.max_payload_bytes:
            raise MqttServiceConflictError("消息大小超过当前通信规则允许的上限。")
        validate_payload_against_schema(payload, rule.payload_schema)
        sample = self._repository.record_sample(
            instance.id,
            topic=topic,
            direction=direction,
            payload=payload,
            max_rate_hz=rule.max_rate_hz,
            drop_on_limit=(
                "command" not in rule.topic_pattern.lower().split("/")
                and "commands" not in rule.topic_pattern.lower().split("/")
            ),
        )
        if sample is None:
            return
        telemetry_hub().publish(
            work_id=instance.work_id,
            service_instance_id=instance.id,
            topic_contract_id=instance.topic_contract.id,
            payload={
                "kind": "service_message",
                "instanceId": instance.id,
                "direction": direction.value,
                "topic": topic,
                "payload": sample.payload,
                "payloadBytes": sample.payload_bytes,
            },
        )

    def recover_incomplete(self) -> None:
        for instance in self._repository.list_instances():
            if instance.status not in {MqttServiceStatus.RUNNING, MqttServiceStatus.STARTING}:
                continue
            target = (
                MqttServiceStatus.STARTING
                if instance.mode is MqttMode.LOOPBACK and instance.auto_recover
                else MqttServiceStatus.STOPPED
                if instance.mode is MqttMode.SIMULATED
                else MqttServiceStatus.FAILED_NEEDS_ATTENTION
            )
            recovered = self._repository.transition(
                instance.id,
                expected_revision=instance.revision,
                idempotency_key=f"sidecar-recovery-{instance.revision}",
                operation="SIDECAR_RECOVERY",
                status=target,
                natural_status=(
                    "本机服务将在受控退避后恢复。"
                    if target is MqttServiceStatus.STARTING
                    else "上次本机进程已经回收，请确认后重新启动。"
                    if target is MqttServiceStatus.FAILED_NEEDS_ATTENTION
                    else "进程内仿真已随本机服务安全停止。"
                ),
            )
            if target is MqttServiceStatus.STARTING:
                self._recoveries[recovered.id] = time.monotonic() + self._restart_backoff

    def shutdown(self) -> None:
        self._supervisor.shutdown()
        self._recoveries.clear()

    def _local_broker_config(self) -> tuple[str, str]:
        instances = [
            item
            for item in self._repository.list_instances()
            if item.mode in {MqttMode.LOOPBACK, MqttMode.LAN}
        ]
        entries = [
            json.loads(self._repository.private_config(item.id))
            for item in sorted(instances, key=lambda candidate: candidate.id)
        ]
        content = json.dumps(
            {
                "schema": "zhangwen.mqtt-broker-config/v1",
                "instances": entries,
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        ) + "\n"
        return content, hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _poll_and_recover(self, only_instance_id: str | None = None) -> None:
        instances = self._repository.list_instances()
        for instance in instances:
            if only_instance_id is not None and instance.id != only_instance_id:
                continue
            if instance.status is MqttServiceStatus.RUNNING:
                crash = self._supervisor.poll_crash(instance.id)
                if crash is not None:
                    self._handle_crash(instance, crash.exit_code, crash.error_summary)
            current = self._repository.get_instance(instance.id)
            due = self._recoveries.get(instance.id)
            if current.status is MqttServiceStatus.STARTING and due is not None and time.monotonic() >= due:
                self._attempt_recovery(current)

    def _handle_crash(self, instance: MqttServiceInstance, exit_code: int, error: str | None) -> None:
        restart_count = instance.restart_count + 1
        retry = instance.mode is MqttMode.LOOPBACK and instance.auto_recover and restart_count <= _MAX_RESTARTS
        status = MqttServiceStatus.STARTING if retry else MqttServiceStatus.FAILED_NEEDS_ATTENTION
        delay = self._restart_backoff * (2 ** max(0, restart_count - 1))
        next_at = datetime.now(UTC) + timedelta(seconds=delay)
        changed = self._repository.transition(
            instance.id,
            expected_revision=instance.revision,
            idempotency_key=f"broker-crash-{instance.revision}-{restart_count}",
            operation="CRASH",
            status=status,
            natural_status=(
                f"本机通信意外停止，将进行第 {restart_count} 次受控恢复。"
                if retry
                else "本机通信多次意外停止，需要检查后再继续。"
            ),
            last_exit_code=exit_code,
            last_error=error,
            restart_count=restart_count,
            next_restart_at=next_at.isoformat() if retry else None,
        )
        if retry:
            self._recoveries[changed.id] = time.monotonic() + delay
        self._publish_state(changed, status.value)

    def _attempt_recovery(self, instance: MqttServiceInstance) -> None:
        self._recoveries.pop(instance.id, None)
        try:
            self._require_credentials(instance)
            config, config_digest = self._local_broker_config()
            pid = self._supervisor.start(
                instance,
                config,
                config_digest=config_digest,
            )
            recovered = self._repository.transition(
                instance.id,
                expected_revision=instance.revision,
                idempotency_key=f"auto-recover-{instance.restart_count}-{instance.revision}",
                operation="AUTO_RECOVER",
                status=MqttServiceStatus.RUNNING,
                natural_status="本机通信已自动恢复，并继续使用启动时固定的版本。",
                process_pid=pid,
            )
            self._publish_state(recovered, "RUNNING")
        except Exception as exc:
            self._handle_crash(instance, -1, str(exc))

    def _require_credentials(self, instance: MqttServiceInstance) -> None:
        if not instance.credential_ref:
            raise MqttServiceConflictError("启动前需要先在桌面应用中保存设备通信身份。")
        if self._credentials.get_password(settings.mqtt_credential_service, instance.id) is None:
            raise MqttServiceConflictError("设备通信身份引用已经失效，请重新保存后再启动。")

    def _require_confirmation(
        self,
        instance: MqttServiceInstance,
        action: str,
        supplied: str | None,
        message: str,
    ) -> None:
        if supplied and self._verify_confirmation(supplied, instance, action):
            return
        raise MqttConfirmationRequiredError(
            message,
            self._issue_confirmation(instance, action),
        )

    def _issue_confirmation(self, instance: MqttServiceInstance, action: str) -> str:
        payload = {
            "instance": instance.id,
            "revision": instance.revision,
            "action": action,
            "expires": int(time.time()) + _CONFIRMATION_TTL_SECONDS,
            "nonce": secrets.token_hex(8),
        }
        encoded = base64.urlsafe_b64encode(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).decode("ascii").rstrip("=")
        signature = hmac.new(
            self._confirmation_secret,
            encoded.encode("ascii"),
            hashlib.sha256,
        ).hexdigest()
        return f"{encoded}.{signature}"

    def _verify_confirmation(
        self,
        token: str,
        instance: MqttServiceInstance,
        action: str,
    ) -> bool:
        try:
            encoded, signature = token.split(".", 1)
            expected = hmac.new(
                self._confirmation_secret,
                encoded.encode("ascii"),
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(signature, expected):
                return False
            padded = encoded + "=" * (-len(encoded) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
            return bool(
                payload.get("instance") == instance.id
                and payload.get("revision") == instance.revision
                and payload.get("action") == action
                and int(payload.get("expires", 0)) >= int(time.time())
            )
        except (ValueError, TypeError, json.JSONDecodeError):
            return False

    @staticmethod
    def _publish_state(instance: MqttServiceInstance, status: str) -> None:
        telemetry_hub().publish(
            work_id=instance.work_id,
            service_instance_id=instance.id,
            topic_contract_id=instance.topic_contract.id,
            payload={
                "kind": "service_state",
                "instanceId": instance.id,
                "status": status,
                "message": instance.natural_status,
            },
        )


def _running_status(mode: MqttMode) -> str:
    return {
        MqttMode.SIMULATED: "设备通信正在本机仿真中，没有打开网络监听。",
        MqttMode.LOOPBACK: "设备通信只在这台电脑上运行。",
        MqttMode.LAN: "设备通信已在选定的家庭网络地址上运行。",
        MqttMode.EXTERNAL: "设备通信已通过 TLS 连接到已有服务。",
    }[mode]


def _access(direction: str) -> tuple[str, ...]:
    if direction == "PUBLISH":
        return ("write",)
    if direction == "SUBSCRIBE":
        return ("read",)
    return ("read", "write")


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
