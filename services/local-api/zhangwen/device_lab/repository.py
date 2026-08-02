"""SQLite persistence for application imports, lab runs and parameter revisions."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from zhangwen.device_lab.models import (
    DeviceLabEvent,
    DeviceLabRun,
    DeviceLabSceneV1,
    FirmwareApplicationManifestV1,
    FirmwareApplicationRecord,
    ParameterSetRevision,
    SupportedDeviceBoardId,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


class DeviceLabRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def save_application(
        self,
        *,
        project_id: str,
        manifest: FirmwareApplicationManifestV1,
        archive_path: Path,
        archive_sha256: str,
        simulation_capability: str,
    ) -> FirmwareApplicationRecord:
        application_id = f"fwapp-{uuid.uuid4().hex}"
        imported_at = _now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO firmware_applications (
                  id, project_id, application_id, board_id, manifest_json, archive_path,
                  archive_sha256, simulation_capability, imported_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    application_id,
                    project_id,
                    manifest.applicationId,
                    manifest.boardId.value,
                    manifest.model_dump_json(),
                    str(archive_path),
                    archive_sha256,
                    simulation_capability,
                    imported_at,
                ),
            )
        return FirmwareApplicationRecord(
            id=application_id,
            projectId=project_id,
            manifest=manifest,
            archiveSha256=archive_sha256,
            simulationCapability=simulation_capability,  # type: ignore[arg-type]
            importedAt=imported_at,
        )

    def save_scene(self, scene: DeviceLabSceneV1) -> DeviceLabSceneV1:
        """Persist the immutable projection; identical source revisions are idempotent."""

        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO device_lab_scenes (
                  project_id, revision, proposal_id, proposal_version, board_id,
                  scene_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scene.projectId,
                    scene.revision,
                    scene.source.proposalId,
                    scene.source.proposalVersion,
                    scene.boardId.value,
                    scene.model_dump_json(),
                    scene.generatedAt,
                ),
            )
        return scene

    def get_current_scene(self, project_id: str) -> DeviceLabSceneV1 | None:
        with self._connect() as conn:
            try:
                row = conn.execute(
                    """
                    SELECT scene_json FROM device_lab_scenes
                    WHERE project_id = ?
                    ORDER BY rowid DESC LIMIT 1
                    """,
                    (project_id,),
                ).fetchone()
            except sqlite3.OperationalError:
                return None
        return (
            DeviceLabSceneV1.model_validate_json(str(row["scene_json"]))
            if row is not None
            else None
        )

    def list_applications(self, project_id: str) -> list[FirmwareApplicationRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM firmware_applications WHERE project_id = ? ORDER BY imported_at DESC",
                (project_id,),
            ).fetchall()
        return [_application_from_row(row) for row in rows]

    def get_application(self, project_id: str, application_id: str) -> tuple[FirmwareApplicationRecord, Path]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM firmware_applications WHERE project_id = ? AND id = ?",
                (project_id, application_id),
            ).fetchone()
        if row is None:
            raise KeyError("application not found")
        return _application_from_row(row), Path(str(row["archive_path"]))

    def find_run_by_idempotency(
        self, project_id: str, key: str, request_hash: str
    ) -> DeviceLabRun | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT state_json, request_hash FROM device_lab_runs "
                "WHERE project_id = ? AND idempotency_key = ?",
                (project_id, key),
            ).fetchone()
        if row is None:
            return None
        if str(row["request_hash"]) != request_hash:
            raise ValueError("DEVICE_LAB_IDEMPOTENCY_KEY_REUSED")
        return DeviceLabRun.model_validate_json(str(row["state_json"]))

    def insert_run(
        self, run: DeviceLabRun, event: DeviceLabEvent, *,
        idempotency_key: str, request_hash: str,
    ) -> DeviceLabRun:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT state_json, request_hash FROM device_lab_runs "
                "WHERE project_id = ? AND idempotency_key = ?",
                (run.projectId, idempotency_key),
            ).fetchone()
            if existing is not None:
                if str(existing["request_hash"]) != request_hash:
                    raise ValueError("DEVICE_LAB_IDEMPOTENCY_KEY_REUSED")
                return DeviceLabRun.model_validate_json(str(existing["state_json"]))
            conn.execute(
                """
                INSERT INTO device_lab_runs (
                  id, project_id, board_id, target, engine, status, application_id,
                  parameter_set_id, state_json, started_at, updated_at, stopped_at,
                  idempotency_key, request_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
                """,
                (
                    run.id, run.projectId, run.boardId.value, run.target.value,
                    run.engine.value, run.status.value, run.applicationId, run.parameterSetId,
                    run.model_dump_json(), run.startedAt, run.updatedAt,
                    idempotency_key, request_hash,
                ),
            )
            conn.execute(
                "INSERT INTO device_lab_events (run_id, revision, event_json, created_at) VALUES (?, ?, ?, ?)",
                (run.id, event.revision, event.model_dump_json(), event.createdAt),
            )
        return run

    def get_run(self, project_id: str, run_id: str) -> DeviceLabRun:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT state_json FROM device_lab_runs WHERE project_id = ? AND id = ?",
                (project_id, run_id),
            ).fetchone()
        if row is None:
            raise KeyError("run not found")
        return DeviceLabRun.model_validate_json(str(row["state_json"]))

    def update_run(self, run: DeviceLabRun, event: DeviceLabEvent) -> None:
        stopped_at = run.updatedAt if run.status.value in {"STOPPED", "ERROR"} else None
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE device_lab_runs
                SET status = ?, state_json = ?, updated_at = ?, stopped_at = ?
                WHERE id = ? AND project_id = ?
                """,
                (run.status.value, run.model_dump_json(), run.updatedAt, stopped_at, run.id, run.projectId),
            )
            conn.execute(
                "INSERT INTO device_lab_events (run_id, revision, event_json, created_at) VALUES (?, ?, ?, ?)",
                (run.id, event.revision, event.model_dump_json(), event.createdAt),
            )
            conn.execute(
                """
                DELETE FROM device_lab_events
                WHERE run_id = ? AND revision <= (
                  SELECT COALESCE(MAX(revision), 0) - 512 FROM device_lab_events WHERE run_id = ?
                )
                """,
                (run.id, run.id),
            )

    def list_events(self, project_id: str, run_id: str, after_revision: int) -> list[DeviceLabEvent]:
        self.get_run(project_id, run_id)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT event_json FROM device_lab_events
                WHERE run_id = ? AND revision > ? ORDER BY revision ASC LIMIT 512
                """,
                (run_id, after_revision),
            ).fetchall()
        return [DeviceLabEvent.model_validate_json(str(row["event_json"])) for row in rows]

    def command_seen(self, run_id: str, command_id: str) -> bool:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT event_json FROM device_lab_events WHERE run_id = ? ORDER BY revision DESC LIMIT 512",
                (run_id,),
            ).fetchall()
        return any(
            json.loads(str(row["event_json"])).get("commandId") == command_id
            for row in rows
        )

    def save_parameter_set(
        self,
        *,
        project_id: str,
        board_id: SupportedDeviceBoardId,
        profile_revision: str,
        label: str,
        values: dict[str, float | bool | str],
        idempotency_key: str,
        request_hash: str,
    ) -> ParameterSetRevision:
        item_id = f"params-{uuid.uuid4().hex}"
        created_at = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT * FROM device_parameter_sets "
                "WHERE project_id = ? AND idempotency_key = ?",
                (project_id, idempotency_key),
            ).fetchone()
            if existing is not None:
                if str(existing["request_hash"]) != request_hash:
                    raise ValueError("DEVICE_LAB_IDEMPOTENCY_KEY_REUSED")
                return _parameter_set_from_row(existing)
            row = conn.execute(
                "SELECT COALESCE(MAX(revision), 0) + 1 AS revision FROM device_parameter_sets WHERE project_id = ? AND board_id = ?",
                (project_id, board_id.value),
            ).fetchone()
            revision = int(row["revision"])
            conn.execute(
                """
                INSERT INTO device_parameter_sets (
                  id, project_id, board_id, profile_revision, revision, label, values_json,
                  created_at, idempotency_key, request_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (item_id, project_id, board_id.value, profile_revision, revision, label,
                 json.dumps(values, ensure_ascii=False, sort_keys=True), created_at,
                 idempotency_key, request_hash),
            )
        return ParameterSetRevision(
            id=item_id, projectId=project_id, boardId=board_id,
            profileRevision=profile_revision, revision=revision, label=label,
            values=values, createdAt=created_at,
        )

    def find_parameter_set_by_idempotency(
        self, project_id: str, key: str, request_hash: str
    ) -> ParameterSetRevision | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM device_parameter_sets "
                "WHERE project_id = ? AND idempotency_key = ?",
                (project_id, key),
            ).fetchone()
        if row is None:
            return None
        if str(row["request_hash"]) != request_hash:
            raise ValueError("DEVICE_LAB_IDEMPOTENCY_KEY_REUSED")
        return _parameter_set_from_row(row)

    def list_parameter_sets(self, project_id: str) -> list[ParameterSetRevision]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM device_parameter_sets WHERE project_id = ? ORDER BY created_at DESC",
                (project_id,),
            ).fetchall()
        return [_parameter_set_from_row(row) for row in rows]

    def get_parameter_set(self, project_id: str, item_id: str) -> ParameterSetRevision:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM device_parameter_sets WHERE project_id = ? AND id = ?",
                (project_id, item_id),
            ).fetchone()
        if row is None:
            raise KeyError("parameter set not found")
        return _parameter_set_from_row(row)


def _application_from_row(row: sqlite3.Row) -> FirmwareApplicationRecord:
    return FirmwareApplicationRecord(
        id=str(row["id"]),
        projectId=str(row["project_id"]),
        manifest=FirmwareApplicationManifestV1.model_validate_json(str(row["manifest_json"])),
        archiveSha256=str(row["archive_sha256"]),
        simulationCapability=str(row["simulation_capability"]),  # type: ignore[arg-type]
        importedAt=str(row["imported_at"]),
    )


def _parameter_set_from_row(row: sqlite3.Row) -> ParameterSetRevision:
    return ParameterSetRevision(
        id=str(row["id"]), projectId=str(row["project_id"]),
        boardId=SupportedDeviceBoardId(str(row["board_id"])),
        profileRevision=str(row["profile_revision"]), revision=int(row["revision"]),
        label=str(row["label"]), values=json.loads(str(row["values_json"])),
        createdAt=str(row["created_at"]),
    )
