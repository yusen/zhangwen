"""A relationally complete V29 project-store fixture for V30 migration audits."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from zhangwen.projects import migrations


LEGACY_PROJECT_ID = "project_v29_migration_audit"
LEGACY_HISTORY_TABLES = (
    "projects",
    "conversations",
    "messages",
    "solutions",
    "proposals",
    "project_versions",
    "artifacts",
    "artifact_versions",
    "artifact_files",
    "code_runs",
    "code_files",
    "code_patches",
    "device_parameter_sets",
    "cad_runs",
    "cad_files",
    "device_lab_scenes",
    "device_lab_runs",
    "device_lab_events",
    "device_sessions",
    "device_operations",
)
_NOW = "2026-07-30T08:00:00+00:00"


@dataclass(frozen=True)
class TableDigest:
    columns: tuple[str, ...]
    row_count: int
    content_sha256: str


@dataclass(frozen=True)
class DatabaseFingerprint:
    user_version: int
    schema_sha256: str
    content_sha256: str


def create_v29_project_store(data_dir: Path) -> Path:
    """Build the real production V29 schema and seed representative history."""

    db_path = Path(data_dir) / "projects" / "zhangwen.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        migrations._create_v1(conn)
        for version in range(2, 30):
            getattr(migrations, f"_migrate_v{version}")(conn)
        assert int(conn.execute("PRAGMA user_version").fetchone()[0]) == 29
        conn.execute("PRAGMA foreign_keys=ON")
        _seed_v29_history(conn)
        foreign_key_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
        assert foreign_key_errors == []
        conn.commit()
    return db_path


def capture_table_digests(
    conn: sqlite3.Connection,
    *,
    tables: Iterable[str] = LEGACY_HISTORY_TABLES,
    columns_by_table: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, TableDigest]:
    digests: dict[str, TableDigest] = {}
    for table in sorted(tables):
        columns = (
            tuple(columns_by_table[table])
            if columns_by_table is not None
            else _table_columns(conn, table)
        )
        quoted_columns = ", ".join(_quote_identifier(column) for column in columns)
        rows = conn.execute(
            f"SELECT {quoted_columns} FROM {_quote_identifier(table)}"
        ).fetchall()
        normalized_rows = [
            [_normalize_value(value) for value in row]
            for row in rows
        ]
        normalized_rows.sort(key=_canonical_json)
        payload = _canonical_json(
            {
                "columns": columns,
                "rows": normalized_rows,
            }
        )
        digests[table] = TableDigest(
            columns=columns,
            row_count=len(rows),
            content_sha256=hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        )
    return digests


def fingerprint_database(conn: sqlite3.Connection) -> DatabaseFingerprint:
    schema_rows = conn.execute(
        """
        SELECT type, name, tbl_name, COALESCE(sql, '')
        FROM sqlite_master
        WHERE name NOT LIKE 'sqlite_%'
        ORDER BY type, name
        """
    ).fetchall()
    schema_payload = _canonical_json(
        [[_normalize_value(value) for value in row] for row in schema_rows]
    )
    tables = [
        str(row[0])
        for row in conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
    ]
    table_digests = capture_table_digests(conn, tables=tables)
    content_payload = _canonical_json(
        {
            table: {
                "columns": digest.columns,
                "rowCount": digest.row_count,
                "contentSha256": digest.content_sha256,
            }
            for table, digest in table_digests.items()
        }
    )
    return DatabaseFingerprint(
        user_version=int(conn.execute("PRAGMA user_version").fetchone()[0]),
        schema_sha256=hashlib.sha256(schema_payload.encode("utf-8")).hexdigest(),
        content_sha256=hashlib.sha256(content_payload.encode("utf-8")).hexdigest(),
    )


def _seed_v29_history(conn: sqlite3.Connection) -> None:
    _insert(
        conn,
        "projects",
        {
            "id": LEGACY_PROJECT_ID,
            "name": "V29 历史作品",
            "stage": "implementation",
            "initial_idea": "保留全部历史关系并迁移到 V30",
            "selected_model": "fixture-model",
            "archived_at": None,
            "created_at": _NOW,
            "updated_at": _NOW,
            "last_opened_at": _NOW,
            "active_expert_id": None,
            "owner_subject": None,
        },
    )
    _insert(
        conn,
        "conversations",
        {
            "id": "conversation_v29",
            "project_id": LEGACY_PROJECT_ID,
            "created_at": _NOW,
            "updated_at": _NOW,
            "owner_expert_type": "smart_engineer",
            "legacy_expert_type": None,
            "archived_legacy_thread": 0,
        },
    )
    _insert(
        conn,
        "messages",
        {
            "id": "message_v29",
            "conversation_id": "conversation_v29",
            "project_id": LEGACY_PROJECT_ID,
            "role": "user",
            "content": "V29 消息内容不可丢失。",
            "reasoning_content": None,
            "status": "completed",
            "model": None,
            "error_json": None,
            "usage_json": '{"completion":2, "prompt":1}',
            "created_at": _NOW,
            "updated_at": _NOW,
            "structured_payload_json": '{"z":2, "a":1}',
            "metadata_json": '{"source":"v29-fixture"}',
        },
    )
    _insert(
        conn,
        "solutions",
        {
            "id": "solution_v29",
            "project_id": LEGACY_PROJECT_ID,
            "version": 1,
            "status": "CONFIRMED",
            "sections_json": '[{"content":"保留方案","id":"overview","title":"方案"}]',
            "created_at": _NOW,
            "confirmed_at": _NOW,
            "based_on_version": None,
            "change_summary_json": "[]",
            "artifact_id": None,
            "artifact_version_id": None,
        },
    )
    _insert(
        conn,
        "proposals",
        {
            "id": "proposal_v29",
            "project_id": LEGACY_PROJECT_ID,
            "solution_id": "solution_v29",
            "solution_version": 1,
            "version": 1,
            "status": "CONFIRMED",
            "sections_json": '[{"content":"K10 功能原型","id":"project_overview"}]',
            "stale_reason": None,
            "created_at": _NOW,
            "updated_at": _NOW,
            "confirmed_at": _NOW,
        },
    )
    _insert(
        conn,
        "project_versions",
        {
            "id": "project_version_v29",
            "project_id": LEGACY_PROJECT_ID,
            "version": 1,
            "state_hash": "1" * 64,
            "change_set_id": None,
            "capability_snapshot_hash": "2" * 64,
            "artifact_version_ids_json": '["artifact_version_v29"]',
            "validation_summary_json": '{"ok":true}',
            "created_at": _NOW,
        },
    )
    _insert(
        conn,
        "artifacts",
        {
            "id": "artifact_v29",
            "project_id": LEGACY_PROJECT_ID,
            "title": "V29 CAD 产物",
            "kind": "CAD",
            "status": "APPROVED",
            "source_agent_id": "fixture-agent",
            "current_version_id": None,
            "created_at": _NOW,
            "updated_at": _NOW,
            "owner_expert_id": None,
            "owner_expert_type": "structure_engineer",
            "source_conversation_id": "conversation_v29",
            "shared_context_revision": 1,
            "legacy_owner_expert": None,
            "creator_legacy_expert": None,
            "domain_status": "confirmed",
        },
    )
    _insert(
        conn,
        "artifact_versions",
        {
            "id": "artifact_version_v29",
            "artifact_id": "artifact_v29",
            "project_id": LEGACY_PROJECT_ID,
            "version": 1,
            "status": "APPROVED",
            "mime_type": "model/stl",
            "preview_json": '{"kind":"mesh","summary":"legacy"}',
            "dependencies_json": "[]",
            "producer_task_id": None,
            "source_entity_type": "cad_run",
            "source_entity_id": "cad_run_v29",
            "checksum": "3" * 64,
            "stale_reason": None,
            "created_at": _NOW,
            "confirmed_at": _NOW,
            "shared_context_revision": 1,
            "domain_status": "confirmed",
        },
    )
    conn.execute(
        "UPDATE artifacts SET current_version_id = ? WHERE id = ?",
        ("artifact_version_v29", "artifact_v29"),
    )
    _insert(
        conn,
        "artifact_files",
        {
            "id": "artifact_file_v29",
            "artifact_id": "artifact_v29",
            "artifact_version_id": "artifact_version_v29",
            "project_id": LEGACY_PROJECT_ID,
            "role": "manufacturing",
            "file_name": "legacy.stl",
            "storage_key": "fixtures/v29/legacy.stl",
            "mime_type": "model/stl",
            "byte_size": 29,
            "sha256": "4" * 64,
            "triangle_count": 12,
            "bounds_json": '{"max":[1,1,1],"min":[0,0,0]}',
            "created_at": _NOW,
        },
    )
    _insert(
        conn,
        "code_runs",
        {
            "id": "code_run_v29",
            "project_id": LEGACY_PROJECT_ID,
            "spec_run_id": None,
            "version": 1,
            "status": "ACCEPTED",
            "workspace_root": "workspace://v29/code/1",
            "max_retries": 1,
            "retries": 0,
            "test_result_json": '{"checks":[],"ok":true}',
            "artifact_id": None,
            "artifact_version_id": None,
            "hardware_solution_version": 1,
            "bom_version": 1,
            "io_map_version": 1,
            "generated_by_expert_id": None,
            "stale_reason": None,
            "created_at": _NOW,
            "updated_at": _NOW,
            "accepted_at": _NOW,
        },
    )
    _insert(
        conn,
        "code_files",
        {
            "id": "code_file_v29",
            "code_run_id": "code_run_v29",
            "project_id": LEGACY_PROJECT_ID,
            "kind": "MAIN",
            "path": "src/main.py",
            "language": "python",
            "content": "print('v29-history')\n",
            "created_at": _NOW,
        },
    )
    _insert(
        conn,
        "code_patches",
        {
            "id": "code_patch_v29",
            "code_run_id": "code_run_v29",
            "project_id": LEGACY_PROJECT_ID,
            "base_snapshot_id": None,
            "summary": "V29 accepted patch",
            "diff": "+print('v29-history')",
            "created_at": _NOW,
        },
    )
    _insert(
        conn,
        "device_parameter_sets",
        {
            "id": "parameter_set_v29",
            "project_id": LEGACY_PROJECT_ID,
            "board_id": "dfrobot/dfrobot_k10",
            "profile_revision": "dfrobot-k10-functional-v1",
            "revision": 1,
            "label": "V29 参数",
            "values_json": '{"sample-interval-ms":1000,"temperature-offset":0.5}',
            "created_at": _NOW,
        },
    )
    _insert(
        conn,
        "cad_runs",
        {
            "id": "cad_run_v29",
            "project_id": LEGACY_PROJECT_ID,
            "spec_run_id": None,
            "template_kind": "BOX_WITH_LID",
            "version": 1,
            "status": "CONFIRMED",
            "command_label": "fixture-cad",
            "parameters_json": '{"height":30,"length":80,"width":50}',
            "validation_json": '{"ok":true}',
            "artifact_id": "artifact_v29",
            "artifact_version_id": "artifact_version_v29",
            "source_message_id": "message_v29",
            "generated_by_expert_id": None,
            "engine_id": "fixture-engine",
            "engine_version": "v29",
            "design_state_json": '{"objects":["body"]}',
            "latest_job_id": None,
            "stale_reason": None,
            "created_at": _NOW,
            "updated_at": _NOW,
            "confirmed_at": _NOW,
        },
    )
    _insert(
        conn,
        "cad_files",
        {
            "id": "cad_file_v29",
            "cad_run_id": "cad_run_v29",
            "project_id": LEGACY_PROJECT_ID,
            "kind": "STL",
            "role": "manufacturing",
            "path": "legacy.stl",
            "file_name": "legacy.stl",
            "storage_key": "fixtures/v29/legacy.stl",
            "mime_type": "model/stl",
            "content": "solid legacy\nendsolid legacy\n",
            "byte_size": 29,
            "sha256": "4" * 64,
            "bounds_json": '{"max":[1,1,1],"min":[0,0,0]}',
            "triangle_count": 12,
            "artifact_file_id": "artifact_file_v29",
            "artifact_id": "artifact_v29",
            "artifact_version_id": "artifact_version_v29",
            "created_at": _NOW,
        },
    )
    _insert(
        conn,
        "device_lab_scenes",
        {
            "project_id": LEGACY_PROJECT_ID,
            "revision": "scene-revision-v29",
            "proposal_id": "proposal_v29",
            "proposal_version": 1,
            "board_id": "dfrobot/dfrobot_k10",
            "scene_json": (
                '{"boardId":"dfrobot/dfrobot_k10","components":[],'
                '"proposalId":"proposal_v29","revision":"scene-revision-v29"}'
            ),
            "created_at": _NOW,
        },
    )
    _insert(
        conn,
        "device_lab_runs",
        {
            "id": "device_lab_run_v29",
            "project_id": LEGACY_PROJECT_ID,
            "board_id": "dfrobot/dfrobot_k10",
            "target": "SIMULATOR",
            "engine": "FUNCTIONAL_MODEL",
            "status": "STOPPED",
            "application_id": None,
            "parameter_set_id": "parameter_set_v29",
            "state_json": '{"safeStop":true,"scenarioResults":{"required":true}}',
            "started_at": _NOW,
            "updated_at": _NOW,
            "stopped_at": _NOW,
        },
    )
    _insert(
        conn,
        "device_lab_events",
        {
            "run_id": "device_lab_run_v29",
            "revision": 1,
            "event_json": '{"kind":"STOPPED","safe":true}',
            "created_at": _NOW,
        },
    )
    _insert(
        conn,
        "device_sessions",
        {
            "id": "device_session_v29",
            "project_id": LEGACY_PROJECT_ID,
            "port_id": "mock:v29-usb",
            "board": "dfrobot/dfrobot_k10",
            "status": "READY",
            "logs_json": '["fixture-only"]',
            "connected_at": _NOW,
            "last_seen_at": _NOW,
            "created_at": _NOW,
        },
    )
    _insert(
        conn,
        "device_operations",
        {
            "id": "device_operation_v29",
            "project_id": LEGACY_PROJECT_ID,
            "session_id": "device_session_v29",
            "kind": "UPLOAD_CODE",
            "status": "COMPLETED",
            "dry_run": 0,
            "command_label": "fixture-only",
            "log": '{"channel":"USB_SERIAL","verification":{"ok":true}}',
            "artifact_id": None,
            "artifact_version_id": None,
            "created_at": _NOW,
            "completed_at": _NOW,
        },
    )


def _insert(conn: sqlite3.Connection, table: str, values: Mapping[str, object]) -> None:
    columns = tuple(values)
    placeholders = ", ".join("?" for _ in columns)
    conn.execute(
        (
            f"INSERT INTO {_quote_identifier(table)} "
            f"({', '.join(_quote_identifier(column) for column in columns)}) "
            f"VALUES ({placeholders})"
        ),
        tuple(values[column] for column in columns),
    )


def _table_columns(conn: sqlite3.Connection, table: str) -> tuple[str, ...]:
    rows = conn.execute(
        f"PRAGMA table_info({_quote_identifier(table)})"
    ).fetchall()
    if not rows:
        raise AssertionError(f"missing table in migration fixture: {table}")
    return tuple(str(row[1]) for row in rows)


def _quote_identifier(value: str) -> str:
    if not value.replace("_", "").isalnum():
        raise ValueError(f"unsafe SQLite identifier: {value}")
    return f'"{value}"'


def _normalize_value(value: object) -> object:
    if isinstance(value, bytes):
        return {"type": "bytes", "hex": value.hex()}
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return {"type": "text", "value": value}
        return {"type": "json", "value": parsed}
    return {"type": type(value).__name__, "value": value}


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
