"""SQLite repository for mock device sessions and deployment dry runs."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from zhangwen.artifacts.models import ArtifactKind, ArtifactStatus
from zhangwen.artifacts.repository import ArtifactRepository
from zhangwen.code_agent.models import CodeRun, CodeRuntime
from zhangwen.creator.metrics import append_device_operation_metrics
from zhangwen.devices.models import (
    DeviceDeploymentChannel,
    DeviceLogEntry,
    DevicePort,
    DeviceOperation,
    DeviceOperationKind,
    DeviceOperationPhase,
    DeviceOperationStatus,
    DeviceSession,
    DeviceSessionStatus,
    EspClawEndpoint,
    EspClawEndpointStatus,
)
from zhangwen.devices.espclaw import EspClawHandshake
from zhangwen.devices.simulator import get_mock_port
from zhangwen.device_lab.models import SupportedDeviceBoardId
from zhangwen.device_lab.scene import (
    DeviceLabSceneProjectionError,
    DeviceLabSceneProjector,
)


class DeviceOperationIdempotencyConflict(ValueError):
    """An operation id already belongs to a different request fingerprint."""


class DeviceSessionNotReady(ValueError):
    """A session could not be atomically reserved for a device operation."""

    def __init__(self, status: DeviceSessionStatus) -> None:
        super().__init__(f"设备会话未就绪：{status.value}")
        self.status = status


class DevicePortLeaseBusy(ValueError):
    """Another queued/running operation owns the same physical port."""


class DeviceProjectLeaseBusy(ValueError):
    """An ESP-Claw deployment conflicts with another active device operation."""


class DeviceDeploymentSessionMismatch(ValueError):
    """A deployment channel was paired with the wrong session transport."""


class DeviceRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._ensure_espclaw_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _ensure_espclaw_schema(self) -> None:
        """Create the V29 ESP-Claw tables for pre-migration development DBs.

        The canonical migration is also registered by the project migration
        owner.  Keeping this idempotent guard here makes isolated device tests
        and upgraded local databases fail closed instead of relying on import
        order.
        """

        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS espclaw_endpoints (
                  id TEXT PRIMARY KEY,
                  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                  session_id TEXT NOT NULL UNIQUE REFERENCES device_sessions(id) ON DELETE CASCADE,
                  web_endpoint TEXT NOT NULL,
                  mcp_endpoint TEXT NOT NULL,
                  board_id TEXT NOT NULL CHECK (
                    board_id IN ('dfrobot/dfrobot_k10', 'seeedstudio/xiao_esp32s3_sense')
                  ),
                  status TEXT NOT NULL CHECK (status IN ('READY', 'ERROR')),
                  storage_base_path TEXT NOT NULL CHECK (storage_base_path = '/fatfs'),
                  capabilities_json TEXT NOT NULL,
                  paired_at TEXT NOT NULL,
                  last_seen_at TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  UNIQUE(project_id, web_endpoint)
                );

                CREATE INDEX IF NOT EXISTS idx_espclaw_endpoints_project
                  ON espclaw_endpoints(project_id, last_seen_at DESC);

                CREATE TABLE IF NOT EXISTS espclaw_deployments (
                  operation_id TEXT PRIMARY KEY REFERENCES device_operations(id) ON DELETE CASCADE,
                  endpoint_id TEXT NOT NULL REFERENCES espclaw_endpoints(id) ON DELETE CASCADE,
                  code_run_id TEXT NOT NULL,
                  version_path TEXT NOT NULL,
                  entrypoint_path TEXT NOT NULL,
                  fingerprint TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_espclaw_deployments_endpoint
                  ON espclaw_deployments(endpoint_id, created_at DESC);
                """
            )
            columns = {
                str(row[1])
                for row in conn.execute("PRAGMA table_info(espclaw_endpoints)").fetchall()
            }
            legacy_single_endpoint = "endpoint_url" in columns and "web_endpoint" not in columns
            if "web_endpoint" not in columns:
                conn.execute("ALTER TABLE espclaw_endpoints ADD COLUMN web_endpoint TEXT NULL")
            if "mcp_endpoint" not in columns:
                conn.execute("ALTER TABLE espclaw_endpoints ADD COLUMN mcp_endpoint TEXT NULL")
            if legacy_single_endpoint:
                # The early, unreleased V29 shape incorrectly assumed MCP and
                # Web Console shared one origin. Preserve the Web value, but
                # mark the record ERROR and require a new two-endpoint
                # handshake; the MCP endpoint is never guessed as READY.
                conn.execute(
                    """
                    UPDATE espclaw_endpoints
                    SET web_endpoint = endpoint_url,
                        mcp_endpoint = endpoint_url,
                        status = 'ERROR'
                    WHERE web_endpoint IS NULL OR mcp_endpoint IS NULL
                    """
                )

    def pair_espclaw_endpoint(
        self,
        *,
        project_id: str,
        web_endpoint: str,
        mcp_endpoint: str,
        board_id: SupportedDeviceBoardId,
        handshake: EspClawHandshake,
    ) -> EspClawEndpoint:
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                """
                SELECT * FROM espclaw_endpoints
                WHERE project_id = ? AND web_endpoint = ?
                """,
                (project_id, web_endpoint),
            ).fetchone()
            if existing is None:
                endpoint_id = _id("espclaw_endpoint")
                session_id = _id("espclaw_session")
                paired_at = now
                logs = [
                    DeviceLogEntry(
                        id=_id("device_log"),
                        level="INFO",
                        message="ESP-Claw trusted-LAN endpoint paired; no firmware operation was performed.",
                        createdAt=now,
                    )
                ]
                conn.execute(
                    """
                    INSERT INTO device_sessions (
                      id, project_id, port_id, board, status, logs_json,
                      connected_at, last_seen_at, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        project_id,
                        f"esp-claw:{endpoint_id}",
                        board_id.value,
                        DeviceSessionStatus.READY.value,
                        _dump_logs(logs),
                        now,
                        now,
                        now,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO espclaw_endpoints (
                      id, project_id, session_id, web_endpoint, mcp_endpoint,
                      board_id, status,
                      storage_base_path, capabilities_json, paired_at, last_seen_at,
                      created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        endpoint_id,
                        project_id,
                        session_id,
                        web_endpoint,
                        mcp_endpoint,
                        board_id.value,
                        EspClawEndpointStatus.READY.value,
                        handshake.storage_base_path,
                        json.dumps(list(handshake.capabilities), ensure_ascii=False),
                        paired_at,
                        now,
                        now,
                        now,
                    ),
                )
            else:
                endpoint_id = str(existing["id"])
                session_id = str(existing["session_id"])
                paired_at = str(existing["paired_at"])
                conn.execute(
                    """
                    UPDATE device_sessions
                    SET board = ?, status = ?, last_seen_at = ?
                    WHERE id = ? AND project_id = ?
                    """,
                    (
                        board_id.value,
                        DeviceSessionStatus.READY.value,
                        now,
                        session_id,
                        project_id,
                    ),
                )
                conn.execute(
                    """
                    UPDATE espclaw_endpoints
                    SET mcp_endpoint = ?, board_id = ?, status = ?, storage_base_path = ?,
                        capabilities_json = ?, last_seen_at = ?, updated_at = ?
                    WHERE id = ? AND project_id = ?
                    """,
                    (
                        mcp_endpoint,
                        board_id.value,
                        EspClawEndpointStatus.READY.value,
                        handshake.storage_base_path,
                        json.dumps(list(handshake.capabilities), ensure_ascii=False),
                        now,
                        now,
                        endpoint_id,
                        project_id,
                    ),
                )
            row = conn.execute(
                "SELECT * FROM espclaw_endpoints WHERE id = ?",
                (endpoint_id,),
            ).fetchone()
        return _to_espclaw_endpoint(row)

    def get_espclaw_endpoint(self, project_id: str, endpoint_id: str) -> EspClawEndpoint:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM espclaw_endpoints WHERE id = ? AND project_id = ?",
                (endpoint_id, project_id),
            ).fetchone()
        if row is None:
            raise ValueError("ESP-Claw endpoint does not exist in this project.")
        return _to_espclaw_endpoint(row)

    def get_espclaw_session_id(self, project_id: str, endpoint_id: str) -> str:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT session_id FROM espclaw_endpoints WHERE id = ? AND project_id = ?",
                (endpoint_id, project_id),
            ).fetchone()
        if row is None:
            raise ValueError("ESP-Claw endpoint does not exist in this project.")
        return str(row["session_id"])

    def list_espclaw_endpoints(self, project_id: str) -> list[EspClawEndpoint]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM espclaw_endpoints
                WHERE project_id = ?
                ORDER BY last_seen_at DESC, id ASC
                """,
                (project_id,),
            ).fetchall()
        return [_to_espclaw_endpoint(row) for row in rows]

    def touch_espclaw_endpoint(self, project_id: str, endpoint_id: str) -> None:
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE espclaw_endpoints
                SET status = ?, last_seen_at = ?, updated_at = ?
                WHERE id = ? AND project_id = ?
                """,
                (EspClawEndpointStatus.READY.value, now, now, endpoint_id, project_id),
            )

    def record_espclaw_deployment(
        self,
        *,
        operation_id: str,
        endpoint_id: str,
        code_run_id: str,
        version_path: str,
        entrypoint_path: str,
        fingerprint: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO espclaw_deployments (
                  operation_id, endpoint_id, code_run_id, version_path,
                  entrypoint_path, fingerprint, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    operation_id,
                    endpoint_id,
                    code_run_id,
                    version_path,
                    entrypoint_path,
                    fingerprint,
                    _now(),
                ),
            )

    def has_active_espclaw_operation(self, project_id: str) -> bool:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT log FROM device_operations
                WHERE project_id = ? AND status IN ('QUEUED', 'RUNNING')
                """,
                (project_id,),
            ).fetchall()
        return any(
            _operation_channel_from_log(str(row["log"]))
            == DeviceDeploymentChannel.ESP_CLAW.value
            for row in rows
        )

    def get_current_session(self, project_id: str) -> DeviceSession | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM device_sessions
                WHERE project_id = ? AND port_id NOT LIKE 'esp-claw:%'
                ORDER BY last_seen_at DESC
                LIMIT 1
                """,
                (project_id,),
            ).fetchone()
            return _to_session(row) if row else None

    def get_session(self, project_id: str, session_id: str) -> DeviceSession:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM device_sessions WHERE id = ? AND project_id = ?",
                (session_id, project_id),
            ).fetchone()
            if row is None:
                raise ValueError("设备会话不存在。")
            return _to_session(row)

    def get_serial_session(
        self,
        project_id: str,
        session_id: str,
        *,
        require_current_scene: bool = False,
    ) -> DeviceSession:
        """Return a physical serial session and fail closed for ESP-Claw rows.

        ESP-Claw endpoints intentionally have a synthetic ``device_sessions``
        row so their operations can share the existing audit model.  That row
        is never a serial port and must not reach mpremote, esptool or terminal
        code, even when a legacy route calls the repository directly.
        """

        session = self.get_session(project_id, session_id)
        with self._connect() as conn:
            endpoint = conn.execute(
                """
                SELECT 1 FROM espclaw_endpoints
                WHERE project_id = ? AND session_id = ?
                LIMIT 1
                """,
                (project_id, session_id),
            ).fetchone()
        if session.portId.startswith("esp-claw:") or endpoint is not None:
            raise DeviceDeploymentSessionMismatch(
                "ESP-Claw endpoint sessions cannot be used by USB serial operations."
            )
        if require_current_scene:
            try:
                scene = DeviceLabSceneProjector(
                    self._db_path,
                    self._db_path.parents[1],
                ).project(project_id)
            except DeviceLabSceneProjectionError as exc:
                raise DeviceDeploymentSessionMismatch(
                    "USB serial operations require a current confirmed DeviceLabScene."
                ) from exc
            if session.board != scene.boardId.value:
                raise DeviceDeploymentSessionMismatch(
                    "USB serial session board does not match the current confirmed DeviceLabScene."
                )
        return session

    def connect_port(
        self,
        project_id: str,
        port: DevicePort,
        *,
        board_id: SupportedDeviceBoardId = SupportedDeviceBoardId.DFROBOT_K10,
        status: DeviceSessionStatus = DeviceSessionStatus.READY,
        messages: list[tuple[str, str]] | None = None,
    ) -> DeviceSession:
        now = _now()
        session_id = _id("device_session")
        log_messages = messages or [
            ("INFO", f"发现串口设备：{port.label}。"),
            ("INFO", "已建立受控 MicroPython 会话。"),
        ]
        logs = [
            DeviceLogEntry(
                id=_id("device_log"),
                level=level,
                message=message,
                createdAt=now,
            )
            for level, message in log_messages
        ]
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO device_sessions (
                  id, project_id, port_id, board, status, logs_json,
                  connected_at, last_seen_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    project_id,
                    port.id,
                    board_id.value,
                    status.value,
                    _dump_logs(logs),
                    now,
                    now,
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM device_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            return _to_session(row)

    def connect_mock_port(
        self,
        project_id: str,
        port_id: str,
        board_id: SupportedDeviceBoardId = SupportedDeviceBoardId.DFROBOT_K10,
    ) -> DeviceSession:
        """Backward-compatible Mock entry point used by the ZW-012 tests."""

        port = get_mock_port(port_id)
        return self.connect_port(
            project_id,
            port,
            board_id=board_id,
            messages=[
                ("INFO", f"发现 Mock USB 串口：{port.label}。"),
                ("INFO", "已建立 Mock MicroPython 会话，未访问真实串口。"),
            ],
        )

    def disconnect_session(self, project_id: str, session_id: str) -> DeviceSession:
        session = self.get_session(project_id, session_id)
        now = _now()
        self._append_session_log(
            project_id,
            session_id,
            DeviceLogEntry(
                id=_id("device_log"),
                level="INFO",
                message="设备会话已断开。",
                createdAt=now,
            ),
        )
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE device_sessions
                SET status = ?, last_seen_at = ?
                WHERE id = ? AND project_id = ?
                """,
                (DeviceSessionStatus.DISCONNECTED.value, now, session_id, project_id),
            )
        return self.get_session(project_id, session_id)

    def upload_code_dry_run(
        self,
        *,
        project_id: str,
        session_id: str,
        code_run: CodeRun,
    ) -> tuple[DeviceOperation, DeviceSession]:
        if code_run.runtime != CodeRuntime.MICROPYTHON:
            raise ValueError("USB serial deployment requires a MICROPYTHON CodeRun.")
        session = self.get_serial_session(
            project_id,
            session_id,
            require_current_scene=True,
        )
        now = _now()
        operation_id = _id("device_operation")
        file_lines = "\n".join(
            f"- {file.path} ({len(file.content.encode('utf-8'))} bytes)"
            for file in code_run.files
        )
        log = "\n".join(
            [
                "MicroPython 上传 Dry Run",
                f"会话：{session.id}",
                f"端口：{session.portId}",
                "命令标签：mpremote",
                "真实命令：未执行",
                "计划上传文件：",
                file_lines,
                "结果：Dry Run 完成，未写入真实设备。",
            ]
        )
        operation = self._create_operation(
            project_id=project_id,
            session_id=session_id,
            kind=DeviceOperationKind.UPLOAD_CODE,
            command_label="mpremote",
            log=log,
            now=now,
        )
        self._append_session_log(
            project_id,
            session_id,
            DeviceLogEntry(
                id=_id("device_log"),
                level="INFO",
                message=f"MicroPython 上传 Dry Run 完成：{len(code_run.files)} 个文件。",
                createdAt=now,
            ),
        )
        version = ArtifactRepository(self._db_path).upsert_text_artifact(
            artifact_id=f"artifact_device_log_{project_id}",
            project_id=project_id,
            title="设备操作日志",
            kind=ArtifactKind.DEVICE_LOG,
            status=ArtifactStatus.APPROVED,
            source_agent_id="deploy-agent",
            source_entity_type="device-operation",
            source_entity_id=operation.id,
            source_version=self._operation_version(project_id),
            content=log,
            summary="MicroPython 上传 Dry Run 日志",
            mime_type="text/plain",
            language="text",
        )
        self._link_operation_artifact(operation.id, version.artifactId, version.id)
        return self.get_operation(project_id, operation.id), self.get_session(project_id, session_id)

    def firmware_flash_dry_run(
        self,
        *,
        project_id: str,
        session_id: str,
    ) -> tuple[DeviceOperation, DeviceSession]:
        session = self.get_serial_session(
            project_id,
            session_id,
            require_current_scene=True,
        )
        now = _now()
        log = "\n".join(
            [
                "固件烧录 Dry Run",
                f"会话：{session.id}",
                f"端口：{session.portId}",
                "命令标签：esptool",
                "真实命令：未执行",
                "确认点：confirmFlash=true 已收到",
                "结果：Dry Run 完成，未擦除 Flash，未烧录固件。",
            ]
        )
        operation = self._create_operation(
            project_id=project_id,
            session_id=session_id,
            kind=DeviceOperationKind.FLASH_FIRMWARE,
            command_label="esptool",
            log=log,
            now=now,
        )
        self._append_session_log(
            project_id,
            session_id,
            DeviceLogEntry(
                id=_id("device_log"),
                level="WARNING",
                message="固件烧录仅完成 Dry Run；真实 Flash 操作需要外部人工确认。",
                createdAt=now,
            ),
        )
        version = ArtifactRepository(self._db_path).upsert_text_artifact(
            artifact_id=f"artifact_device_log_{project_id}",
            project_id=project_id,
            title="设备操作日志",
            kind=ArtifactKind.DEVICE_LOG,
            status=ArtifactStatus.APPROVED,
            source_agent_id="deploy-agent",
            source_entity_type="device-operation",
            source_entity_id=operation.id,
            source_version=self._operation_version(project_id),
            content=log,
            summary="固件烧录 Dry Run 日志",
            mime_type="text/plain",
            language="text",
        )
        self._link_operation_artifact(operation.id, version.artifactId, version.id)
        return self.get_operation(project_id, operation.id), self.get_session(project_id, session_id)

    def get_operation(self, project_id: str, operation_id: str) -> DeviceOperation:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM device_operations WHERE id = ? AND project_id = ?",
                (operation_id, project_id),
            ).fetchone()
            if row is None:
                raise ValueError("设备操作不存在。")
            return _to_operation(row)

    def get_operation_by_id(self, operation_id: str) -> DeviceOperation:
        """Resolve an in-memory task during bounded service shutdown."""

        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM device_operations WHERE id = ?",
                (operation_id,),
            ).fetchone()
        if row is None:
            raise ValueError("设备操作不存在。")
        return _to_operation(row)

    def get_stored_operation_status(
        self,
        project_id: str,
        operation_id: str,
    ) -> DeviceOperationStatus:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT status FROM device_operations WHERE id = ? AND project_id = ?",
                (operation_id, project_id),
            ).fetchone()
            if row is None:
                raise ValueError("设备操作不存在。")
            return DeviceOperationStatus(row["status"])

    def list_operations(self, project_id: str, *, limit: int = 20) -> list[DeviceOperation]:
        bounded_limit = max(1, min(limit, 100))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM device_operations
                WHERE project_id = ?
                ORDER BY created_at DESC, rowid DESC
                LIMIT ?
                """,
                (project_id, bounded_limit),
            ).fetchall()
            return [_to_operation(row) for row in rows]

    def get_latest_operation(self, project_id: str) -> DeviceOperation | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM device_operations
                WHERE project_id = ?
                ORDER BY created_at DESC, rowid DESC
                LIMIT 1
                """,
                (project_id,),
            ).fetchone()
            return _to_operation(row) if row else None

    def update_operation(
        self,
        project_id: str,
        operation_id: str,
        *,
        status: DeviceOperationStatus,
        log: str | None = None,
        completed_at: str | None = None,
    ) -> DeviceOperation:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM device_operations WHERE id = ? AND project_id = ?",
                (operation_id, project_id),
            ).fetchone()
            if row is None:
                raise ValueError("设备操作不存在。")
            conn.execute(
                """
                UPDATE device_operations
                SET status = ?, log = COALESCE(?, log), completed_at = ?
                WHERE id = ? AND project_id = ?
                """,
                (
                    status.value,
                    log,
                    completed_at if completed_at is not None else row["completed_at"],
                    operation_id,
                    project_id,
                ),
            )
            if status in {
                DeviceOperationStatus.COMPLETED,
                DeviceOperationStatus.FAILED,
                DeviceOperationStatus.CANCELED,
                DeviceOperationStatus.TIMED_OUT,
            }:
                updated = conn.execute(
                    "SELECT * FROM device_operations WHERE id = ? AND project_id = ?",
                    (operation_id, project_id),
                ).fetchone()
                assert updated is not None
                operation = _to_operation(updated)
                append_device_operation_metrics(
                    conn,
                    project_id=project_id,
                    operation_id=operation.id,
                    kind=operation.kind.value,
                    status=operation.status.value,
                    metadata=operation.metadata,
                    steps=[
                        step.model_dump(mode="json") for step in operation.steps
                    ],
                )
        return self.get_operation(project_id, operation_id)

    def create_operation(
        self,
        *,
        project_id: str,
        session_id: str,
        operation_id: str,
        kind: DeviceOperationKind,
        command_label: str,
        log: str,
        dry_run: bool = False,
        status: DeviceOperationStatus = DeviceOperationStatus.QUEUED,
    ) -> DeviceOperation:
        return self._create_operation(
            project_id=project_id,
            session_id=session_id,
            operation_id=operation_id,
            kind=kind,
            command_label=command_label,
            log=log,
            now=_now(),
            dry_run=dry_run,
            status=status,
        )

    def reserve_operation(
        self,
        *,
        project_id: str,
        session_id: str,
        operation_id: str,
        kind: DeviceOperationKind,
        command_label: str,
        log: str,
        fingerprint: str,
        claimed_status: DeviceSessionStatus,
    ) -> tuple[DeviceOperation, bool]:
        """Atomically claim an attachable session and insert an idempotent operation.

        The existing operation is checked inside the same write transaction as
        the session claim. This closes the check-then-insert race across local
        API workers while still allowing a lost HTTP response to be retried
        with the same operation id and fingerprint.
        """

        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT * FROM device_operations WHERE id = ?",
                (operation_id,),
            ).fetchone()
            if existing is not None:
                if existing["project_id"] != project_id:
                    raise DeviceOperationIdempotencyConflict(
                        "该 operationId 已用于不同设备操作。"
                    )
                operation = _to_operation(existing)
                if operation.metadata.get("fingerprint") != fingerprint:
                    raise DeviceOperationIdempotencyConflict(
                        "该 operationId 已用于不同设备操作。"
                    )
                return operation, False

            candidate_channel = _operation_channel_from_log(log)
            active_rows = conn.execute(
                """
                SELECT * FROM device_operations
                WHERE project_id = ? AND status IN ('QUEUED', 'RUNNING')
                """,
                (project_id,),
            ).fetchall()
            active_claw = any(
                _operation_channel_from_log(str(row["log"]))
                == DeviceDeploymentChannel.ESP_CLAW.value
                for row in active_rows
            )
            if (
                candidate_channel == DeviceDeploymentChannel.ESP_CLAW.value
                and active_rows
            ) or active_claw:
                raise DeviceProjectLeaseBusy(
                    "ESP-Claw deployment and serial device operations are mutually exclusive."
                )

            session = conn.execute(
                "SELECT status, port_id FROM device_sessions WHERE id = ? AND project_id = ?",
                (session_id, project_id),
            ).fetchone()
            if session is None:
                raise ValueError("设备会话不存在。")
            espclaw_session = (
                str(session["port_id"]).startswith("esp-claw:")
                or conn.execute(
                    """
                    SELECT 1 FROM espclaw_endpoints
                    WHERE project_id = ? AND session_id = ?
                    LIMIT 1
                    """,
                    (project_id, session_id),
                ).fetchone()
                is not None
            )
            if (
                candidate_channel == DeviceDeploymentChannel.ESP_CLAW.value
                and not espclaw_session
            ) or (
                candidate_channel != DeviceDeploymentChannel.ESP_CLAW.value
                and espclaw_session
            ):
                raise DeviceDeploymentSessionMismatch(
                    "The deployment channel does not match the selected device session."
                )
            port_owner = conn.execute(
                """
                SELECT o.id FROM device_operations AS o
                JOIN device_sessions AS s ON s.id = o.session_id
                WHERE s.port_id = ? AND o.status IN ('QUEUED', 'RUNNING')
                LIMIT 1
                """,
                (session["port_id"],),
            ).fetchone()
            if port_owner is not None:
                raise DevicePortLeaseBusy("设备端口已由另一个本地 Runner 租用。")
            session_status = DeviceSessionStatus(session["status"])
            reservable = {
                DeviceSessionStatus.READY,
                DeviceSessionStatus.ATTACHED_UNVERIFIED,
                DeviceSessionStatus.RUNTIME_BUSY,
                DeviceSessionStatus.MANAGED,
            }
            if session_status not in reservable:
                raise DeviceSessionNotReady(session_status)

            conn.execute(
                """
                INSERT INTO device_operations (
                  id, project_id, session_id, kind, status, dry_run,
                  command_label, log, artifact_id, artifact_version_id,
                  created_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, 0, ?, ?, NULL, NULL, ?, NULL)
                """,
                (
                    operation_id,
                    project_id,
                    session_id,
                    kind.value,
                    DeviceOperationStatus.QUEUED.value,
                    command_label,
                    log,
                    now,
                ),
            )
            updated = conn.execute(
                """
                UPDATE device_sessions
                SET status = ?, last_seen_at = ?
                WHERE id = ? AND project_id = ? AND status = ?
                """,
                (
                    claimed_status.value,
                    now,
                    session_id,
                    project_id,
                    session_status.value,
                ),
            )
            if updated.rowcount != 1:
                current = conn.execute(
                    "SELECT status FROM device_sessions WHERE id = ? AND project_id = ?",
                    (session_id, project_id),
                ).fetchone()
                status = (
                    DeviceSessionStatus(current["status"])
                    if current is not None
                    else DeviceSessionStatus.DISCONNECTED
                )
                raise DeviceSessionNotReady(status)
            row = conn.execute(
                "SELECT * FROM device_operations WHERE id = ?",
                (operation_id,),
            ).fetchone()
            return _to_operation(row), True

    def set_session_status(
        self,
        project_id: str,
        session_id: str,
        status: DeviceSessionStatus,
    ) -> DeviceSession:
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE device_sessions
                SET status = ?, last_seen_at = ?
                WHERE id = ? AND project_id = ?
                """,
                (status.value, now, session_id, project_id),
            )
        return self.get_session(project_id, session_id)

    def sync_operation_artifact(
        self,
        project_id: str,
        operation_id: str,
    ) -> DeviceOperation:
        operation = self.get_operation(project_id, operation_id)
        evidence = [
            operation.log,
            f"状态：{operation.status.value}",
            f"阶段：{operation.phase.value}",
        ]
        evidence.extend(
            f"- {step.phase.value}: exitCode={step.exitCode}; {step.summary}"
            for step in operation.steps
        )
        runtime_evidence = operation.metadata.get("runtimeEvidence")
        if isinstance(runtime_evidence, dict):
            evidence.extend(
                [
                    "运行冒烟证据：",
                    f"- 结果：{'通过' if runtime_evidence.get('ok') is True else '待补充'}",
                    f"- 湿度采样：{runtime_evidence.get('sampleCount', 0)} 条",
                    f"- 湿润停泵：{runtime_evidence.get('wetPumpOffOk') is True}",
                    f"- 干燥限时运行：{runtime_evidence.get('dryLimitedRunOk') is True}",
                    f"- 无未处理异常：{runtime_evidence.get('noUnhandledException') is True}",
                    f"- 核验时间：{runtime_evidence.get('checkedAt', '')}",
                ]
            )
        content = "\n".join(evidence)
        artifact_status = (
            ArtifactStatus.APPROVED
            if operation.status
            in {DeviceOperationStatus.COMPLETED, DeviceOperationStatus.DRY_RUN_COMPLETE}
            else ArtifactStatus.FAILED
        )
        version = None
        for _attempt in range(3):
            try:
                version = ArtifactRepository(self._db_path).upsert_text_artifact(
                    artifact_id=f"artifact_device_log_{project_id}",
                    project_id=project_id,
                    title="设备操作日志",
                    kind=ArtifactKind.DEVICE_LOG,
                    status=artifact_status,
                    source_agent_id="deploy-agent",
                    source_entity_type="device-operation",
                    source_entity_id=operation.id,
                    source_version=self._next_artifact_version(project_id),
                    content=content,
                    summary=operation.log,
                    mime_type="text/plain",
                    language="text",
                )
                break
            except sqlite3.IntegrityError as exc:
                if "artifact_versions.artifact_id, artifact_versions.version" not in str(exc):
                    raise
        if version is None:
            raise RuntimeError("设备日志 Artifact 版本分配冲突。")
        self._link_operation_artifact(operation.id, version.artifactId, version.id)
        return self.get_operation(project_id, operation.id)

    def _create_operation(
        self,
        *,
        project_id: str,
        session_id: str,
        kind: DeviceOperationKind,
        command_label: str,
        log: str,
        now: str,
        operation_id: str | None = None,
        dry_run: bool = True,
        status: DeviceOperationStatus = DeviceOperationStatus.DRY_RUN_COMPLETE,
    ) -> DeviceOperation:
        operation_id = operation_id or _id("device_operation")
        terminal = status in {
            DeviceOperationStatus.DRY_RUN_COMPLETE,
            DeviceOperationStatus.COMPLETED,
            DeviceOperationStatus.BLOCKED,
            DeviceOperationStatus.FAILED,
            DeviceOperationStatus.CANCELED,
            DeviceOperationStatus.TIMED_OUT,
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO device_operations (
                  id, project_id, session_id, kind, status, dry_run,
                  command_label, log, artifact_id, artifact_version_id,
                  created_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)
                """,
                (
                    operation_id,
                    project_id,
                    session_id,
                    kind.value,
                    status.value,
                    1 if dry_run else 0,
                    command_label,
                    log,
                    now,
                    now if terminal else None,
                ),
            )
            if terminal:
                conn.execute(
                    """
                    UPDATE device_sessions
                    SET status = ?, last_seen_at = ?
                    WHERE id = ? AND project_id = ?
                    """,
                    (DeviceSessionStatus.READY.value, now, session_id, project_id),
                )
            row = conn.execute(
                "SELECT * FROM device_operations WHERE id = ?",
                (operation_id,),
            ).fetchone()
            return _to_operation(row)

    def _append_session_log(
        self,
        project_id: str,
        session_id: str,
        entry: DeviceLogEntry,
    ) -> None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT logs_json FROM device_sessions WHERE id = ? AND project_id = ?",
                (session_id, project_id),
            ).fetchone()
            if row is None:
                raise ValueError("设备会话不存在。")
            logs = [DeviceLogEntry(**item) for item in json.loads(row["logs_json"])]
            logs.append(entry)
            conn.execute(
                """
                UPDATE device_sessions
                SET logs_json = ?, last_seen_at = ?
                WHERE id = ? AND project_id = ?
                """,
                (_dump_logs(logs), entry.createdAt, session_id, project_id),
            )

    def _link_operation_artifact(
        self,
        operation_id: str,
        artifact_id: str,
        artifact_version_id: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE device_operations
                SET artifact_id = ?, artifact_version_id = ?
                WHERE id = ?
                """,
                (artifact_id, artifact_version_id, operation_id),
            )

    def _operation_version(self, project_id: str) -> int:
        with self._connect() as conn:
            value = conn.execute(
                "SELECT COUNT(*) FROM device_operations WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0]
            return int(value)

    def _next_artifact_version(self, project_id: str) -> int:
        artifact_id = f"artifact_device_log_{project_id}"
        with self._connect() as conn:
            value = conn.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 FROM artifact_versions WHERE artifact_id = ?",
                (artifact_id,),
            ).fetchone()[0]
            return int(value)


def _to_session(row: sqlite3.Row) -> DeviceSession:
    return DeviceSession(
        id=row["id"],
        projectId=row["project_id"],
        portId=row["port_id"],
        board=row["board"],
        status=DeviceSessionStatus(row["status"]),
        connectedAt=row["connected_at"],
        lastSeenAt=row["last_seen_at"],
        logs=[DeviceLogEntry(**item) for item in json.loads(row["logs_json"])],
    )


def _to_espclaw_endpoint(row: sqlite3.Row) -> EspClawEndpoint:
    return EspClawEndpoint(
        id=row["id"],
        projectId=row["project_id"],
        webEndpoint=row["web_endpoint"],
        mcpEndpoint=row["mcp_endpoint"],
        boardId=row["board_id"],
        status=EspClawEndpointStatus(row["status"]),
        storageBasePath=row["storage_base_path"],
        capabilities=[str(item) for item in json.loads(row["capabilities_json"])],
        pairedAt=row["paired_at"],
        lastSeenAt=row["last_seen_at"],
    )


def _operation_channel_from_log(raw_log: str) -> str | None:
    try:
        payload = json.loads(raw_log)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        return None
    channel = metadata.get("channel")
    return str(channel) if isinstance(channel, str) else None


def _to_operation(row: sqlite3.Row) -> DeviceOperation:
    raw_log = str(row["log"])
    state: dict[str, object] = {}
    try:
        candidate = json.loads(raw_log)
        if isinstance(candidate, dict) and candidate.get("schema") == "device-operation/v1":
            state = candidate
    except (json.JSONDecodeError, TypeError):
        pass
    kind = DeviceOperationKind(row["kind"])
    status = DeviceOperationStatus(row["status"])
    if kind == DeviceOperationKind.UPLOAD_CODE and state:
        state, status = _normalized_upload_outcome(state, status)
    return DeviceOperation(
        id=row["id"],
        projectId=row["project_id"],
        sessionId=row["session_id"],
        kind=kind,
        status=status,
        dryRun=bool(row["dry_run"]),
        commandLabel=row["command_label"],
        log=str(state.get("log", raw_log)),
        artifactId=row["artifact_id"],
        artifactVersionId=row["artifact_version_id"],
        createdAt=row["created_at"],
        completedAt=row["completed_at"],
        phase=state.get("phase", DeviceOperationPhase.QUEUED.value),
        progress=int(state.get("progress", 0)),
        errorCode=state.get("errorCode"),
        steps=state.get("steps", []),
        backup=state.get("backup"),
        verification=state.get("verification"),
        cancelable=bool(state.get("cancelable", False)),
        metadata=state.get("metadata", {}),
    )


def _normalized_upload_outcome(
    state: dict[str, object],
    stored_status: DeviceOperationStatus,
) -> tuple[dict[str, object], DeviceOperationStatus]:
    """Build a compatible upload read model without rewriting historical rows.

    Older uploads treated a failed post-reset REPL reconnect as a failed file
    deployment and reused that reconnect code as ``runtimeExitCode``.  The
    immutable step evidence lets us correct the user-facing meaning only when
    transfer, readback and restart all truly exited with zero and no restore
    attempt of any outcome was recorded.
    """

    normalized = dict(state)
    steps = normalized.get("steps")
    if not isinstance(steps, list):
        return normalized, stored_status

    preflight_ok = _phase_outcome(steps, DeviceOperationPhase.PREFLIGHT)
    runtime_interrupted_ok = _phase_outcome(
        steps,
        DeviceOperationPhase.INTERRUPT_RUNTIME,
    )
    backup_ok = _phase_outcome(steps, DeviceOperationPhase.BACKUP)
    transfer_ok = _phase_outcome(steps, DeviceOperationPhase.TRANSFER)
    readback_ok = _phase_outcome(steps, DeviceOperationPhase.VERIFY_FILES)
    restart_ok = _phase_outcome(steps, DeviceOperationPhase.RESTART)
    runtime_started_ok = _phase_outcome(steps, DeviceOperationPhase.START_RUNTIME)
    reconnect_codes = _phase_exit_codes(steps, DeviceOperationPhase.RECONNECT)
    existing_verification = normalized.get("verification")
    verification = (
        dict(existing_verification)
        if isinstance(existing_verification, dict)
        else {}
    )
    explicit_management_ok = verification.get("managementChannelOk")
    if reconnect_codes:
        management_ok: bool | None = reconnect_codes[-1] == 0
    elif isinstance(explicit_management_ok, bool):
        management_ok = explicit_management_ok
    else:
        management_ok = None
    metadata = normalized.get("metadata")
    failure_evidence = (
        metadata.get("failureEvidence") if isinstance(metadata, dict) else None
    )
    interrupted_phase = (
        failure_evidence.get("interruptedPhase")
        if isinstance(failure_evidence, dict)
        else None
    )
    restore_codes = _phase_exit_codes(steps, DeviceOperationPhase.RESTORE)
    restore_attempted = bool(restore_codes)
    restore_succeeded = any(code == 0 for code in restore_codes)
    legacy_timeout_after_restart = (
        not reconnect_codes
        and not restore_attempted
        and normalized.get("errorCode") == "DEVICE_OPERATION_TIMEOUT"
        and preflight_ok is True
        and backup_ok is True
        and transfer_ok is True
        and readback_ok is True
        and restart_ok is True
        and _last_evidence_step_is_successful_restart(steps)
    )
    reached_reconnect = (
        bool(reconnect_codes)
        or interrupted_phase == DeviceOperationPhase.RECONNECT.value
        or legacy_timeout_after_restart
    )
    if transfer_ok is False or readback_ok is False or restore_succeeded:
        deployment_ok: bool | None = False
    elif restore_attempted:
        # A failed or indeterminate restore means neither the new deployment
        # nor the previous files can be asserted as the current device state.
        deployment_ok = None
    elif transfer_ok is True and readback_ok is True:
        deployment_ok = True
    else:
        deployment_ok = None

    qualifies_as_legacy_warning = (
        stored_status in {DeviceOperationStatus.FAILED, DeviceOperationStatus.TIMED_OUT}
        and deployment_ok is True
        and restart_ok is True
        and reached_reconnect
        and management_ok is not True
        and not restore_attempted
    )
    resolved_status = stored_status
    if qualifies_as_legacy_warning:
        resolved_status = DeviceOperationStatus.COMPLETED
        normalized.update(
            {
                "status": DeviceOperationStatus.COMPLETED.value,
                "phase": DeviceOperationPhase.COMPLETE.value,
                "progress": 100,
                "cancelable": False,
                "errorCode": None,
                "log": (
                    "MicroPython 文件部署、回读和设备重启完成；管理通道尚未恢复，"
                    "请重新扫描并连接，或按设备 RST 后重试。"
                ),
            }
        )
    resolved_management_ok = False if qualifies_as_legacy_warning else management_ok

    if steps or verification:
        warnings = verification.get("warnings")
        normalized_warnings = (
            [str(item) for item in warnings]
            if isinstance(warnings, list)
            else []
        )
        if (
            deployment_ok is True
            and restart_ok is True
            and resolved_management_ok is False
        ):
            _append_once(
                normalized_warnings,
                "文件部署已完成，但管理通道尚未恢复；请重新扫描并连接，或按设备 RST 后重试。",
            )
        if resolved_management_ok is not None:
            _append_once(normalized_warnings, "管理通道连通不代表用户程序业务效果已经验证。")
        reconnect_exit_code = reconnect_codes[-1] if reconnect_codes else None
        verification.update(
            {
                "reconnectExitCode": reconnect_exit_code,
                # Upload does not run the user's program under an observable
                # business-effect checker, so reconnect must never fill this.
                "runtimeExitCode": None,
                "deploymentOk": deployment_ok,
                "restartOk": restart_ok,
                "runtimeInterruptedOk": runtime_interrupted_ok,
                "runtimeStartedOk": runtime_started_ok,
                "managementChannelOk": resolved_management_ok,
                "warnings": normalized_warnings,
            }
        )
        if restore_attempted:
            verification.update(
                {
                    "ok": False,
                    "summary": (
                        "原设备文件已恢复；本次部署未保留。"
                        if restore_succeeded
                        else "设备文件恢复结果不确定；本次部署不能视为成功。"
                    ),
                }
            )
        if qualifies_as_legacy_warning:
            verification.update(
                {
                    "ok": True,
                    "summary": "文件部署、回读校验和设备重启已完成；管理通道待恢复。",
                }
            )
        normalized["verification"] = verification

    return normalized, resolved_status


def _phase_exit_codes(
    steps: list[object],
    phase: DeviceOperationPhase,
) -> list[int | None]:
    codes: list[int | None] = []
    for step in steps:
        if not isinstance(step, dict) or step.get("phase") != phase.value:
            continue
        value = step.get("exitCode")
        codes.append(value if isinstance(value, int) else None)
    return codes


def _phase_outcome(
    steps: list[object],
    phase: DeviceOperationPhase,
) -> bool | None:
    codes = _phase_exit_codes(steps, phase)
    return all(code == 0 for code in codes) if codes else None


def _last_evidence_step_is_successful_restart(steps: list[object]) -> bool:
    known_phases = {phase.value for phase in DeviceOperationPhase}
    for step in reversed(steps):
        if not isinstance(step, dict) or step.get("phase") not in known_phases:
            continue
        exit_code = step.get("exitCode")
        return (
            step.get("phase") == DeviceOperationPhase.RESTART.value
            and isinstance(exit_code, int)
            and exit_code == 0
        )
    return False


def _append_once(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _dump_logs(logs: list[DeviceLogEntry]) -> str:
    return json.dumps([log.model_dump(mode="json") for log in logs], ensure_ascii=False)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"
