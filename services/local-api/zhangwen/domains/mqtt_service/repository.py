"""Same-database repository for MQTT service instances and their immutable config."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from zhangwen.auth.context import current_owner_subject
from zhangwen.domains.events.privacy import validate_telemetry_payload
from zhangwen.domains.events.store import RealtimeEventStore
from zhangwen.domains.mqtt_service.contracts import (
    namespace_for_work,
    render_private_config,
    validate_and_compile,
)
from zhangwen.domains.mqtt_service.models import (
    CreateMqttServiceInstanceRequest,
    MqttMode,
    MqttSampleDirection,
    MqttServiceConflictError,
    MqttServiceInstance,
    MqttServiceNotFoundError,
    MqttServiceSample,
    MqttServiceSamplesResponse,
    MqttServiceStatus,
    MqttTopicContractRevision,
    MqttTopicRule,
)
from zhangwen.domains.packages.repository import PackagePlatformRepository
from zhangwen.projects.repository import ProjectRepository


_LOCAL_OWNER = "__local__"
_SERVICE_PACKAGE_ID = "service-package:mqtt-local"
_MAX_SAMPLES = 200


class MqttServiceRepository:
    def __init__(
        self,
        data_dir: Path,
        *,
        owner_subject: str | None = None,
    ) -> None:
        self._data_dir = Path(data_dir)
        self._projects = ProjectRepository(self._data_dir)
        self._db_path = self._projects.db_path
        # The supervised MQTT service is intentionally process-scoped, while the
        # authenticated owner is request-scoped.  Keep only an explicit test or
        # migration override here; otherwise resolve the owner from the current
        # request on every repository operation so a long-lived service cannot
        # capture the first account that touched it.
        self._owner_subject_override = owner_subject
        self._events = RealtimeEventStore(self._db_path)

    @property
    def db_path(self) -> Path:
        return self._db_path

    @property
    def _owner_subject(self) -> str | None:
        if self._owner_subject_override is not None:
            return self._owner_subject_override
        return current_owner_subject()

    @property
    def _owner_key(self) -> str:
        return self._owner_subject or _LOCAL_OWNER

    def list_instances(self) -> list[MqttServiceInstance]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM mqtt_service_instances
                WHERE owner_key = ? ORDER BY updated_at DESC, id
                """,
                (self._owner_key,),
            ).fetchall()
            return [self._instance_from_row(conn, row) for row in rows]

    def get_instance(self, instance_id: str) -> MqttServiceInstance:
        with self._connect() as conn:
            row = self._instance_row(conn, instance_id)
            return self._instance_from_row(conn, row)

    def replayed_command(
        self,
        instance_id: str,
        *,
        operation: str,
        idempotency_key: str,
        request_digest: str,
    ) -> MqttServiceInstance | None:
        with self._connect() as conn:
            self._instance_row(conn, instance_id)
            replay = self._command_replay(
                conn,
                instance_id,
                operation,
                idempotency_key,
                request_digest,
            )
            if replay is None:
                return None
            return self._instance_from_row(conn, self._instance_row(conn, instance_id))

    def create_instance(
        self,
        request: CreateMqttServiceInstanceRequest,
        rules: list[MqttTopicRule],
    ) -> MqttServiceInstance:
        self._projects.assert_project_access(request.work_id)
        packages = PackagePlatformRepository(
            self._data_dir,
            owner_subject=self._owner_subject,
        )
        packages.ensure_legacy_packages()
        package_revision = packages.stable_revision(_SERVICE_PACKAGE_ID)
        normalized_rules, acl, acl_digest = validate_and_compile(request.work_id, rules)
        now = _now()
        instance_id = _id("mqtt_service")
        contract_id = _id("mqtt_contract")
        listen_host, listen_port = _resolved_listener(request)
        config = render_private_config(
            instance_id=instance_id,
            work_id=request.work_id,
            mode=request.mode,
            listen_host=listen_host,
            listen_port=listen_port,
            external_endpoint=request.external_endpoint,
            external_tls=request.external_tls,
            service_package_revision_id=package_revision.id,
            topic_contract_revision_id=contract_id,
            acl=acl,
        )
        config_digest = hashlib.sha256(config.encode("utf-8")).hexdigest()
        artifact_id = f"artifact_mqtt_config_{instance_id}"
        artifact_version_id = f"artifact_version_{artifact_id}_{contract_id}"
        request_digest = _digest(
            {
                **request.model_dump(mode="json", by_alias=True),
                "rules": [item.model_dump(mode="json", by_alias=True) for item in normalized_rules],
            }
        )
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                """
                SELECT * FROM mqtt_service_instances
                WHERE work_id = ? AND owner_key = ? AND idempotency_key = ?
                """,
                (request.work_id, self._owner_key, request.idempotency_key),
            ).fetchone()
            if existing is not None:
                instance = self._instance_from_row(conn, existing)
                stored = conn.execute(
                    """
                    SELECT request_digest FROM mqtt_service_commands
                    WHERE instance_id = ? AND operation = 'CREATE'
                      AND owner_key = ? AND idempotency_key = ?
                    """,
                    (instance.id, self._owner_key, request.idempotency_key),
                ).fetchone()
                if stored is None or str(stored["request_digest"]) != request_digest:
                    raise MqttServiceConflictError("同一幂等键不能创建不同的本机服务。")
                return instance
            conn.execute(
                """
                INSERT INTO mqtt_topic_contract_revisions (
                  id, work_id, owner_key, revision, namespace, rules_json,
                  compiled_acl_json, acl_digest, created_at
                ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?)
                """,
                (
                    contract_id,
                    request.work_id,
                    self._owner_key,
                    namespace_for_work(request.work_id),
                    _dump([item.model_dump(mode="json", by_alias=True) for item in normalized_rules]),
                    _dump(acl),
                    acl_digest,
                    now,
                ),
            )
            self._insert_config_artifact(
                conn,
                artifact_id=artifact_id,
                artifact_version_id=artifact_version_id,
                work_id=request.work_id,
                version=1,
                contract_id=contract_id,
                config=config,
                checksum=config_digest,
                now=now,
            )
            natural_status = "设备通信已准备，尚未启动。"
            conn.execute(
                """
                INSERT INTO mqtt_service_instances (
                  id, work_id, owner_subject, owner_key, mode, status,
                  service_package_id, service_package_revision_id,
                  topic_contract_revision_id, config_artifact_id,
                  config_artifact_version_id, config_digest,
                  credential_ref, credential_digest, listen_host, listen_port,
                  external_endpoint, external_tls, auto_recover,
                  natural_status, idempotency_key, revision,
                  created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'STOPPED', ?, ?, ?, ?, ?, ?,
                          NULL, NULL, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    instance_id,
                    request.work_id,
                    self._owner_subject,
                    self._owner_key,
                    request.mode.value,
                    _SERVICE_PACKAGE_ID,
                    package_revision.id,
                    contract_id,
                    artifact_id,
                    artifact_version_id,
                    config_digest,
                    listen_host,
                    listen_port,
                    request.external_endpoint,
                    int(request.external_tls),
                    int(request.auto_recover),
                    natural_status,
                    request.idempotency_key,
                    now,
                    now,
                ),
            )
            self._record_command(
                conn,
                instance_id=instance_id,
                operation="CREATE",
                idempotency_key=request.idempotency_key,
                request_digest=request_digest,
                result_revision=1,
                now=now,
            )
            self._events.append_service_event(
                conn,
                service_instance_id=instance_id,
                service_revision=1,
                event_type="service.mqtt.created",
                source_event_id=f"mqtt:{instance_id}:created:1",
                payload={"workId": request.work_id, "mode": request.mode.value, "naturalStatus": natural_status},
            )
        return self.get_instance(instance_id)

    def update_topic_contract(
        self,
        instance_id: str,
        *,
        expected_revision: int,
        idempotency_key: str,
        rules: list[MqttTopicRule],
    ) -> MqttServiceInstance:
        now = _now()
        request_digest = _digest(
            {"expectedRevision": expected_revision, "rules": [item.model_dump(mode="json", by_alias=True) for item in rules]}
        )
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._instance_row(conn, instance_id)
            replay = self._command_replay(
                conn, instance_id, "UPDATE_CONTRACT", idempotency_key, request_digest
            )
            if replay is not None:
                return self._instance_from_row(conn, self._instance_row(conn, instance_id))
            if int(row["revision"]) != expected_revision:
                raise MqttServiceConflictError("服务状态已经变化，请刷新后重试。")
            if str(row["status"]) != MqttServiceStatus.STOPPED.value:
                raise MqttServiceConflictError("正在执行的服务固定当前规则；请先停止后再创建新版本。")
            normalized, acl, acl_digest = validate_and_compile(str(row["work_id"]), rules)
            contract_revision = self._next_contract_revision(conn, str(row["work_id"]))
            contract_id = _id("mqtt_contract")
            conn.execute(
                """
                INSERT INTO mqtt_topic_contract_revisions (
                  id, work_id, owner_key, revision, namespace, rules_json,
                  compiled_acl_json, acl_digest, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    contract_id,
                    row["work_id"],
                    self._owner_key,
                    contract_revision,
                    namespace_for_work(str(row["work_id"])),
                    _dump([item.model_dump(mode="json", by_alias=True) for item in normalized]),
                    _dump(acl),
                    acl_digest,
                    now,
                ),
            )
            config = render_private_config(
                instance_id=instance_id,
                work_id=str(row["work_id"]),
                mode=MqttMode(str(row["mode"])),
                listen_host=_optional(row["listen_host"]),
                listen_port=int(row["listen_port"]) if row["listen_port"] is not None else None,
                external_endpoint=_optional(row["external_endpoint"]),
                external_tls=bool(row["external_tls"]),
                service_package_revision_id=str(row["service_package_revision_id"]),
                topic_contract_revision_id=contract_id,
                acl=acl,
            )
            digest = hashlib.sha256(config.encode("utf-8")).hexdigest()
            artifact_id = str(row["config_artifact_id"])
            version_id = f"artifact_version_{artifact_id}_{contract_id}"
            self._insert_config_artifact(
                conn,
                artifact_id=artifact_id,
                artifact_version_id=version_id,
                work_id=str(row["work_id"]),
                version=contract_revision,
                contract_id=contract_id,
                config=config,
                checksum=digest,
                now=now,
            )
            next_revision = expected_revision + 1
            natural_status = "设备通信规则已更新，下一次启动会使用新版本。"
            conn.execute(
                """
                UPDATE mqtt_service_instances
                SET topic_contract_revision_id = ?, config_artifact_version_id = ?,
                    config_digest = ?, natural_status = ?, revision = ?, updated_at = ?
                WHERE id = ? AND owner_key = ? AND revision = ?
                """,
                (contract_id, version_id, digest, natural_status, next_revision, now, instance_id, self._owner_key, expected_revision),
            )
            self._record_command(
                conn,
                instance_id=instance_id,
                operation="UPDATE_CONTRACT",
                idempotency_key=idempotency_key,
                request_digest=request_digest,
                result_revision=next_revision,
                now=now,
            )
            self._events.append_service_event(
                conn,
                service_instance_id=instance_id,
                service_revision=next_revision,
                event_type="service.mqtt.contract.updated",
                source_event_id=f"mqtt:{instance_id}:contract:{next_revision}",
                payload={"workId": row["work_id"], "naturalStatus": natural_status},
            )
        return self.get_instance(instance_id)

    def set_credentials_reference(
        self,
        instance_id: str,
        *,
        expected_revision: int,
        idempotency_key: str,
        credential_ref: str,
        credential_digest: str,
        request_digest: str,
    ) -> MqttServiceInstance:
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._instance_row(conn, instance_id)
            replay = self._command_replay(
                conn, instance_id, "SET_CREDENTIALS", idempotency_key, request_digest
            )
            if replay is not None:
                return self._instance_from_row(conn, self._instance_row(conn, instance_id))
            if int(row["revision"]) != expected_revision:
                raise MqttServiceConflictError("服务状态已经变化，请刷新后重试。")
            if str(row["status"]) != MqttServiceStatus.STOPPED.value:
                raise MqttServiceConflictError("正在执行的服务固定当前凭据引用；请先停止后再更换。")
            next_revision = expected_revision + 1
            natural_status = "设备通信身份已安全保存，可以启动服务。"
            conn.execute(
                """
                UPDATE mqtt_service_instances
                SET credential_ref = ?, credential_digest = ?, natural_status = ?,
                    revision = ?, updated_at = ?
                WHERE id = ? AND owner_key = ? AND revision = ?
                """,
                (credential_ref, credential_digest, natural_status, next_revision, now, instance_id, self._owner_key, expected_revision),
            )
            self._record_command(
                conn,
                instance_id=instance_id,
                operation="SET_CREDENTIALS",
                idempotency_key=idempotency_key,
                request_digest=request_digest,
                result_revision=next_revision,
                now=now,
            )
            self._events.append_service_event(
                conn,
                service_instance_id=instance_id,
                service_revision=next_revision,
                event_type="service.mqtt.credentials.changed",
                source_event_id=f"mqtt:{instance_id}:credentials:{next_revision}",
                payload={"workId": row["work_id"], "configured": True, "naturalStatus": natural_status},
            )
        return self.get_instance(instance_id)

    def transition(
        self,
        instance_id: str,
        *,
        expected_revision: int,
        idempotency_key: str,
        operation: str,
        status: MqttServiceStatus,
        natural_status: str,
        process_pid: int | None = None,
        last_exit_code: int | None = None,
        last_error: str | None = None,
        restart_count: int | None = None,
        next_restart_at: str | None = None,
    ) -> MqttServiceInstance:
        request_digest = _digest({"expectedRevision": expected_revision, "status": status.value})
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._instance_row(conn, instance_id)
            replay = self._command_replay(conn, instance_id, operation, idempotency_key, request_digest)
            if replay is not None:
                return self._instance_from_row(conn, self._instance_row(conn, instance_id))
            if int(row["revision"]) != expected_revision:
                raise MqttServiceConflictError("服务状态已经变化，请刷新后重试。")
            next_revision = expected_revision + 1
            conn.execute(
                """
                UPDATE mqtt_service_instances
                SET status = ?, natural_status = ?, process_pid = ?,
                    last_exit_code = ?, last_error = ?,
                    restart_count = COALESCE(?, restart_count),
                    next_restart_at = ?, revision = ?, updated_at = ?,
                    started_at = CASE WHEN ? = 'RUNNING' THEN COALESCE(started_at, ?) ELSE started_at END,
                    stopped_at = CASE WHEN ? IN ('STOPPED', 'FAILED_NEEDS_ATTENTION') THEN ? ELSE stopped_at END
                WHERE id = ? AND owner_key = ? AND revision = ?
                """,
                (
                    status.value,
                    natural_status,
                    process_pid,
                    last_exit_code,
                    _bounded_error(last_error),
                    restart_count,
                    next_restart_at,
                    next_revision,
                    now,
                    status.value,
                    now,
                    status.value,
                    now,
                    instance_id,
                    self._owner_key,
                    expected_revision,
                ),
            )
            self._record_command(
                conn,
                instance_id=instance_id,
                operation=operation,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
                result_revision=next_revision,
                now=now,
            )
            self._events.append_service_event(
                conn,
                service_instance_id=instance_id,
                service_revision=next_revision,
                event_type=f"service.mqtt.{operation.lower()}",
                source_event_id=f"mqtt:{instance_id}:{operation.lower()}:{idempotency_key}",
                payload={"workId": row["work_id"], "status": status.value, "naturalStatus": natural_status},
            )
        return self.get_instance(instance_id)

    def record_sample(
        self,
        instance_id: str,
        *,
        topic: str,
        direction: MqttSampleDirection,
        payload: dict[str, object],
        max_rate_hz: float,
        drop_on_limit: bool,
    ) -> MqttServiceSample | None:
        safe = validate_telemetry_payload(payload)
        encoded = _dump(safe).encode("utf-8")
        now = _now()
        sample_id = _id("mqtt_sample")
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._instance_row(conn, instance_id)
            window_start = (datetime.fromisoformat(now) - timedelta(seconds=1)).isoformat()
            recent = conn.execute(
                """
                SELECT COUNT(*) FROM mqtt_service_samples
                WHERE instance_id = ? AND topic = ? AND sampled_at >= ?
                """,
                (instance_id, topic, window_start),
            ).fetchone()
            if int(recent[0] if recent is not None else 0) >= max(1, int(max_rate_hz)):
                if not drop_on_limit:
                    raise MqttServiceConflictError(
                        "控制消息超过当前通信规则允许的速率，未发送且未按样本丢弃。"
                    )
                conn.execute(
                    """
                    UPDATE mqtt_service_instances
                    SET sample_drop_count = sample_drop_count + 1, updated_at = ?
                    WHERE id = ? AND owner_key = ?
                    """,
                    (now, instance_id, self._owner_key),
                )
                return None
            conn.execute(
                """
                INSERT INTO mqtt_service_samples (
                  id, instance_id, work_id, owner_key, topic, direction,
                  payload_json, payload_bytes, sampled_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (sample_id, instance_id, row["work_id"], self._owner_key, topic, direction.value, encoded.decode("utf-8"), len(encoded), now),
            )
            conn.execute(
                """
                DELETE FROM mqtt_service_samples WHERE id IN (
                  SELECT id FROM mqtt_service_samples
                  WHERE instance_id = ? ORDER BY sampled_at DESC, id DESC
                  LIMIT -1 OFFSET ?
                )
                """,
                (instance_id, _MAX_SAMPLES),
            )
        return MqttServiceSample(
            id=sample_id,
            instanceId=instance_id,
            topic=topic,
            direction=direction,
            payload=safe,
            payloadBytes=len(encoded),
            sampledAt=now,
        )

    def list_samples(self, instance_id: str, *, limit: int = 100) -> MqttServiceSamplesResponse:
        with self._connect() as conn:
            row = self._instance_row(conn, instance_id)
            sample_rows = conn.execute(
                """
                SELECT * FROM mqtt_service_samples
                WHERE instance_id = ? AND owner_key = ?
                ORDER BY sampled_at DESC, id DESC LIMIT ?
                """,
                (instance_id, self._owner_key, max(1, min(limit, _MAX_SAMPLES))),
            ).fetchall()
        return MqttServiceSamplesResponse(
            samples=[
                MqttServiceSample(
                    id=str(item["id"]),
                    instanceId=instance_id,
                    topic=str(item["topic"]),
                    direction=MqttSampleDirection(str(item["direction"])),
                    payload=json.loads(str(item["payload_json"])),
                    payloadBytes=int(item["payload_bytes"]),
                    sampledAt=str(item["sampled_at"]),
                )
                for item in sample_rows
            ],
            droppedSamples=int(row["sample_drop_count"]),
        )

    def private_config(self, instance_id: str) -> str:
        with self._connect() as conn:
            row = self._instance_row(conn, instance_id)
            version = conn.execute(
                "SELECT preview_json FROM artifact_versions WHERE id = ?",
                (row["config_artifact_version_id"],),
            ).fetchone()
        if version is None:
            raise MqttServiceNotFoundError("设备通信配置版本不存在。")
        preview = json.loads(str(version["preview_json"]))
        return str(preview.get("code") or "")

    def _instance_from_row(self, conn: sqlite3.Connection, row: sqlite3.Row) -> MqttServiceInstance:
        contract = self._contract_from_row(
            conn.execute(
                "SELECT * FROM mqtt_topic_contract_revisions WHERE id = ?",
                (row["topic_contract_revision_id"],),
            ).fetchone()
        )
        return MqttServiceInstance(
            id=str(row["id"]),
            workId=str(row["work_id"]),
            mode=MqttMode(str(row["mode"])),
            status=MqttServiceStatus(str(row["status"])),
            servicePackageRevisionId=str(row["service_package_revision_id"]),
            topicContractRevisionId=str(row["topic_contract_revision_id"]),
            topicContract=contract,
            configArtifactId=str(row["config_artifact_id"]),
            configArtifactVersionId=str(row["config_artifact_version_id"]),
            configDigest=str(row["config_digest"]),
            credentialRef=_optional(row["credential_ref"]),
            credentialConfigured=row["credential_ref"] is not None,
            listenHost=_optional(row["listen_host"]),
            listenPort=int(row["listen_port"]) if row["listen_port"] is not None else None,
            externalEndpoint=_optional(row["external_endpoint"]),
            autoRecover=bool(row["auto_recover"]),
            restartCount=int(row["restart_count"]),
            sampleDropCount=int(row["sample_drop_count"]),
            lastError=_optional(row["last_error"]),
            naturalStatus=str(row["natural_status"]),
            revision=int(row["revision"]),
            createdAt=str(row["created_at"]),
            updatedAt=str(row["updated_at"]),
        )

    def _contract_from_row(self, row: sqlite3.Row | None) -> MqttTopicContractRevision:
        if row is None:
            raise MqttServiceNotFoundError("设备通信规则版本不存在。")
        return MqttTopicContractRevision(
            id=str(row["id"]),
            revision=int(row["revision"]),
            workId=str(row["work_id"]),
            namespace=str(row["namespace"]),
            rules=[MqttTopicRule.model_validate(item) for item in json.loads(str(row["rules_json"]))],
            aclDigest=str(row["acl_digest"]),
            createdAt=str(row["created_at"]),
        )

    def _instance_row(self, conn: sqlite3.Connection, instance_id: str) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM mqtt_service_instances WHERE id = ? AND owner_key = ?",
            (instance_id, self._owner_key),
        ).fetchone()
        if row is None:
            raise MqttServiceNotFoundError("设备通信服务不存在。")
        return row

    def _command_replay(
        self,
        conn: sqlite3.Connection,
        instance_id: str,
        operation: str,
        idempotency_key: str,
        request_digest: str,
    ) -> int | None:
        row = conn.execute(
            """
            SELECT request_digest, result_revision FROM mqtt_service_commands
            WHERE instance_id = ? AND owner_key = ? AND operation = ? AND idempotency_key = ?
            """,
            (instance_id, self._owner_key, operation, idempotency_key),
        ).fetchone()
        if row is None:
            return None
        if str(row["request_digest"]) != request_digest:
            raise MqttServiceConflictError("同一幂等键不能用于不同的服务操作。")
        return int(row["result_revision"])

    def _record_command(
        self,
        conn: sqlite3.Connection,
        *,
        instance_id: str,
        operation: str,
        idempotency_key: str,
        request_digest: str,
        result_revision: int,
        now: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO mqtt_service_commands (
              id, instance_id, owner_key, operation, idempotency_key,
              request_digest, result_revision, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (_id("mqtt_command"), instance_id, self._owner_key, operation, idempotency_key, request_digest, result_revision, now),
        )

    def _insert_config_artifact(
        self,
        conn: sqlite3.Connection,
        *,
        artifact_id: str,
        artifact_version_id: str,
        work_id: str,
        version: int,
        contract_id: str,
        config: str,
        checksum: str,
        now: str,
    ) -> None:
        preview = _dump(
            {
                "kind": "CODE",
                "summary": "本机服务使用的不可变设备通信配置。",
                "code": config,
                "language": "json",
            }
        )
        existing = conn.execute("SELECT id FROM artifacts WHERE id = ?", (artifact_id,)).fetchone()
        if existing is None:
            conn.execute(
                """
                INSERT INTO artifacts (
                  id, project_id, title, kind, status, source_agent_id,
                  current_version_id, created_at, updated_at, domain_status
                ) VALUES (?, ?, '设备通信配置', 'PACKAGE', 'APPROVED',
                          'service-supervisor', ?, ?, ?, 'confirmed')
                """,
                (artifact_id, work_id, artifact_version_id, now, now),
            )
        conn.execute(
            """
            INSERT INTO artifact_versions (
              id, artifact_id, project_id, version, status, mime_type,
              preview_json, dependencies_json, producer_task_id,
              source_entity_type, source_entity_id, checksum, stale_reason,
              created_at, confirmed_at, domain_status
            ) VALUES (?, ?, ?, ?, 'APPROVED', 'application/json', ?, '[]',
                      NULL, 'MQTT_TOPIC_CONTRACT', ?, ?, NULL, ?, ?, 'confirmed')
            """,
            (artifact_version_id, artifact_id, work_id, version, preview, contract_id, checksum, now, now),
        )
        conn.execute(
            """
            UPDATE artifacts SET current_version_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (artifact_version_id, now, artifact_id),
        )

    def _next_contract_revision(self, conn: sqlite3.Connection, work_id: str) -> int:
        row = conn.execute(
            """
            SELECT COALESCE(MAX(revision), 0) FROM mqtt_topic_contract_revisions
            WHERE work_id = ? AND owner_key = ?
            """,
            (work_id, self._owner_key),
        ).fetchone()
        return int(row[0] if row is not None else 0) + 1

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


def _resolved_listener(request: CreateMqttServiceInstanceRequest) -> tuple[str | None, int | None]:
    if request.mode is MqttMode.LOOPBACK:
        return request.listen_host or "127.0.0.1", request.listen_port or 1883
    if request.mode is MqttMode.LAN:
        return request.listen_host, request.listen_port or 1883
    return None, None


def _bounded_error(value: str | None) -> str | None:
    if value is None:
        return None
    return value.replace("\r", " ").replace("\n", " ")[:512]


def _optional(value: object) -> str | None:
    return str(value) if value is not None else None


def _digest(value: object) -> str:
    return hashlib.sha256(_dump(value).encode("utf-8")).hexdigest()


def _dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _now() -> str:
    return datetime.now(UTC).isoformat()
