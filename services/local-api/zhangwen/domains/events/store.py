"""SQLite event store and outbox port used inside existing domain transactions."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from zhangwen.domains.events.models import EventEnvelope, EventScope
from zhangwen.domains.events.privacy import (
    creator_event_projection,
    sanitize_event_payload,
)


class RealtimeEventStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)

    def append_work_event(
        self,
        conn: sqlite3.Connection,
        *,
        work_id: str,
        event_type: str,
        source_event_id: str,
        payload: dict[str, Any],
    ) -> EventEnvelope:
        seq = _next_work_seq(conn, work_id)
        return self._append_scope_event(
            conn,
            scope=EventScope.WORK,
            scope_id=work_id,
            seq=seq,
            revision=seq,
            event_type=event_type,
            source_event_id=source_event_id,
            payload=payload,
        )

    def append_package_event(
        self,
        conn: sqlite3.Connection,
        *,
        package_id: str,
        package_revision: int,
        event_type: str,
        source_event_id: str,
        payload: dict[str, Any],
    ) -> EventEnvelope:
        seq = _next_scope_seq(conn, EventScope.PACKAGE, package_id)
        return self._append_scope_event(
            conn,
            scope=EventScope.PACKAGE,
            scope_id=package_id,
            seq=seq,
            revision=max(package_revision, 1),
            event_type=event_type,
            source_event_id=source_event_id,
            payload=payload,
        )

    def append_device_event(
        self,
        conn: sqlite3.Connection,
        *,
        device_id: str,
        device_revision: int,
        event_type: str,
        source_event_id: str,
        payload: dict[str, Any],
    ) -> EventEnvelope:
        seq = _next_scope_seq(conn, EventScope.DEVICE, device_id)
        return self._append_scope_event(
            conn,
            scope=EventScope.DEVICE,
            scope_id=device_id,
            seq=seq,
            revision=max(device_revision, 1),
            event_type=event_type,
            source_event_id=source_event_id,
            payload=payload,
        )

    def append_service_event(
        self,
        conn: sqlite3.Connection,
        *,
        service_instance_id: str,
        service_revision: int,
        event_type: str,
        source_event_id: str,
        payload: dict[str, Any],
    ) -> EventEnvelope:
        seq = _next_scope_seq(conn, EventScope.SERVICE, service_instance_id)
        return self._append_scope_event(
            conn,
            scope=EventScope.SERVICE,
            scope_id=service_instance_id,
            seq=seq,
            revision=max(service_revision, 1),
            event_type=event_type,
            source_event_id=source_event_id,
            payload=payload,
        )

    def append_system_event(
        self,
        conn: sqlite3.Connection,
        *,
        system_id: str,
        system_revision: int,
        event_type: str,
        source_event_id: str,
        payload: dict[str, Any],
    ) -> EventEnvelope:
        seq = _next_scope_seq(conn, EventScope.SYSTEM, system_id)
        return self._append_scope_event(
            conn,
            scope=EventScope.SYSTEM,
            scope_id=system_id,
            seq=seq,
            revision=max(system_revision, 1),
            event_type=event_type,
            source_event_id=source_event_id,
            payload=payload,
        )

    def _append_scope_event(
        self,
        conn: sqlite3.Connection,
        *,
        scope: EventScope,
        scope_id: str,
        seq: int,
        revision: int,
        event_type: str,
        source_event_id: str,
        payload: dict[str, Any],
    ) -> EventEnvelope:
        existing = conn.execute(
            "SELECT * FROM realtime_events WHERE source_event_id = ?",
            (source_event_id,),
        ).fetchone()
        if existing is not None:
            return _event_from_row(existing)
        event_id = f"event_{uuid.uuid4().hex}"
        occurred_at = _now()
        safe_payload = sanitize_event_payload(event_type, payload)
        conn.execute(
            """
            INSERT INTO realtime_events (
              id, scope, scope_id, seq, type, revision, occurred_at,
              durable, payload_json, source_event_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                event_id,
                scope.value,
                scope_id,
                seq,
                event_type,
                revision,
                occurred_at,
                _dump(safe_payload),
                source_event_id,
            ),
        )
        conn.execute(
            """
            INSERT INTO realtime_outbox (
              event_id, attempts, available_at, published_at, last_error
            ) VALUES (?, 0, ?, NULL, NULL)
            """,
            (event_id, occurred_at),
        )
        row = conn.execute(
            "SELECT * FROM realtime_events WHERE id = ?",
            (event_id,),
        ).fetchone()
        assert row is not None
        return _event_from_row(row)

    def append_creator_event(
        self,
        conn: sqlite3.Connection,
        *,
        work_id: str,
        source_event_id: str,
        creator_event_type: str,
        payload: dict[str, Any],
    ) -> EventEnvelope | None:
        projected = creator_event_projection(creator_event_type, payload)
        if projected is None:
            return None
        event_type, safe_payload = projected
        safe_payload["sourceEventId"] = source_event_id
        return self.append_work_event(
            conn,
            work_id=work_id,
            event_type=event_type,
            source_event_id=source_event_id,
            payload=safe_payload,
        )

    def list_work_events(
        self,
        work_id: str,
        *,
        after_position: int = 0,
        limit: int = 500,
    ) -> list[EventEnvelope]:
        return self.list_scope_events(
            EventScope.WORK,
            work_id,
            after_position=after_position,
            limit=limit,
        )

    def list_scope_events(
        self,
        scope: EventScope,
        scope_id: str,
        *,
        after_position: int = 0,
        limit: int = 500,
    ) -> list[EventEnvelope]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM realtime_events
                WHERE scope = ? AND scope_id = ? AND position > ?
                ORDER BY position ASC LIMIT ?
                """,
                (scope.value, scope_id, after_position, limit),
            ).fetchall()
        return [_event_from_row(row) for row in rows]

    def event_position(
        self,
        event_id: str,
        *,
        work_id: str | None = None,
    ) -> int | None:
        with self._connect() as conn:
            if work_id is None:
                row = conn.execute(
                    "SELECT position FROM realtime_events WHERE id = ?",
                    (event_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT position FROM realtime_events
                    WHERE id = ? AND scope = 'WORK' AND scope_id = ?
                    """,
                    (event_id, work_id),
                ).fetchone()
        return int(row["position"]) if row is not None else None

    def scope_event_position(
        self,
        event_id: str,
        *,
        scope: EventScope,
        scope_id: str,
    ) -> int | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT position FROM realtime_events
                WHERE id = ? AND scope = ? AND scope_id = ?
                """,
                (event_id, scope.value, scope_id),
            ).fetchone()
        return int(row["position"]) if row is not None else None

    def latest_work_position(self, work_id: str) -> int:
        return self.latest_scope_position(EventScope.WORK, work_id)

    def latest_scope_position(self, scope: EventScope, scope_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(MAX(position), 0) AS position
                FROM realtime_events WHERE scope = ? AND scope_id = ?
                """,
                (scope.value, scope_id),
            ).fetchone()
        return int(row["position"] if row is not None else 0)

    def latest_work_seq(self, work_id: str) -> int:
        return self.latest_scope_seq(EventScope.WORK, work_id)

    def latest_scope_seq(self, scope: EventScope, scope_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(MAX(seq), 0) AS seq
                FROM realtime_events WHERE scope = ? AND scope_id = ?
                """,
                (scope.value, scope_id),
            ).fetchone()
        return int(row["seq"] if row is not None else 0)

    def publish_pending(self, *, limit: int = 500) -> int:
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                """
                SELECT event_id FROM realtime_outbox
                WHERE published_at IS NULL AND available_at <= ?
                ORDER BY available_at ASC, event_id ASC LIMIT ?
                """,
                (now, limit),
            ).fetchall()
            if not rows:
                return 0
            event_ids = [str(row["event_id"]) for row in rows]
            conn.executemany(
                """
                UPDATE realtime_outbox
                SET attempts = attempts + 1, published_at = ?, last_error = NULL
                WHERE event_id = ? AND published_at IS NULL
                """,
                [(now, event_id) for event_id in event_ids],
            )
            return len(event_ids)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


def _next_work_seq(conn: sqlite3.Connection, work_id: str) -> int:
    event_row = conn.execute(
        """
        SELECT COALESCE(MAX(seq), 0) AS seq FROM realtime_events
        WHERE scope = 'WORK' AND scope_id = ?
        """,
        (work_id,),
    ).fetchone()
    event_seq = int(event_row[0] if event_row is not None else 0)
    project_row = conn.execute(
        """
        SELECT COALESCE(MAX(version), 0) AS version
        FROM project_versions WHERE project_id = ?
        """,
        (work_id,),
    ).fetchone()
    project_version = int(project_row[0] if project_row is not None else 0)
    creator_row = conn.execute(
        """
        SELECT creator_version FROM creator_work_state WHERE project_id = ?
        """,
        (work_id,),
    ).fetchone()
    creator_version = int(creator_row[0] if creator_row is not None else 0)
    return max(event_seq + 1, project_version, creator_version, 1)


def _next_scope_seq(
    conn: sqlite3.Connection,
    scope: EventScope,
    scope_id: str,
) -> int:
    row = conn.execute(
        """
        SELECT COALESCE(MAX(seq), 0) AS seq FROM realtime_events
        WHERE scope = ? AND scope_id = ?
        """,
        (scope.value, scope_id),
    ).fetchone()
    return int(row[0] if row is not None else 0) + 1


def _event_from_row(row: sqlite3.Row) -> EventEnvelope:
    return EventEnvelope(
        id=str(row["id"]),
        seq=int(row["seq"]),
        scope=EventScope(str(row["scope"])),
        scopeId=str(row["scope_id"]),
        type=str(row["type"]),
        revision=int(row["revision"]),
        occurredAt=str(row["occurred_at"]),
        durable=bool(row["durable"]),
        payload=json.loads(str(row["payload_json"])),
    )


def _dump(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _now() -> str:
    return datetime.now(UTC).isoformat()
