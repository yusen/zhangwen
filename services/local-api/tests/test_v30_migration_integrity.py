"""V29 -> current schema zero-loss, idempotency and backup recovery acceptance."""

from __future__ import annotations

import shutil
import sqlite3
import json
from pathlib import Path

import pytest

from tests.v29_migration_fixture import (
    LEGACY_HISTORY_TABLES,
    LEGACY_PROJECT_ID,
    capture_table_digests,
    create_v29_project_store,
    fingerprint_database,
)
from zhangwen.projects import migrations
from zhangwen.projects import repository as project_repository_module
from zhangwen.projects.repository import ProjectRepository


def test_new_database_is_not_counted_as_a_legacy_migration(
    tmp_path: Path,
) -> None:
    repository = ProjectRepository(tmp_path)

    with sqlite3.connect(repository.db_path) as conn:
        assert int(conn.execute("PRAGMA user_version").fetchone()[0]) == 31
        assert conn.execute(
            """
            SELECT COUNT(*) FROM creator_system_metrics
            WHERE event_type = 'METRIC'
              AND json_extract(payload_json, '$.metric') =
                  'LEGACY_MIGRATION_FINISHED'
            """
        ).fetchone()[0] == 0
        assert conn.execute(
            """
            SELECT COUNT(*) FROM schema_migration_audit
            WHERE id = 'migration_v29_v30'
            """
        ).fetchone()[0] == 0


def test_real_v29_store_migrates_without_history_loss_or_duplicate_reopen(
    tmp_path: Path,
) -> None:
    db_path = create_v29_project_store(tmp_path)
    with sqlite3.connect(db_path) as conn:
        before = capture_table_digests(conn)
        assert all(digest.row_count == 1 for digest in before.values())
        assert int(conn.execute("PRAGMA user_version").fetchone()[0]) == 29

    first = ProjectRepository(tmp_path)
    assert first.db_path == db_path
    with sqlite3.connect(db_path) as conn:
        after = capture_table_digests(
            conn,
            columns_by_table={
                table: before[table].columns for table in LEGACY_HISTORY_TABLES
            },
        )
        assert after == before
        assert int(conn.execute("PRAGMA user_version").fetchone()[0]) == 31
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        metric_rows = conn.execute(
            """
            SELECT payload_json FROM creator_events
            WHERE event_type = 'METRIC'
            ORDER BY created_at, id
            """
        ).fetchall()
        metric_payloads = [json.loads(str(row[0])) for row in metric_rows]
        assert {payload["metric"] for payload in metric_payloads} == {
            "WORK_CREATED",
        }
        system_rows = conn.execute(
            """
            SELECT payload_json FROM creator_system_metrics
            WHERE event_type = 'METRIC'
            """
        ).fetchall()
        assert len(system_rows) == 1
        migration_payload = json.loads(str(system_rows[0][0]))
        assert migration_payload["metric"] == "LEGACY_MIGRATION_FINISHED"
        assert migration_payload["fromSchemaVersion"] == 29
        assert migration_payload["migratedRowCount"] >= sum(
            digest.row_count for digest in before.values()
        )
        assert migration_payload["zeroDataLoss"] is True
        assert migration_payload["passed"] is True
        assert LEGACY_PROJECT_ID not in migration_payload["triggerId"]

    backups_after_first_open = sorted(
        (tmp_path / "projects" / "backups").glob("pre-migration-v29-to-v31-*.sqlite3")
    )
    assert len(backups_after_first_open) == 1
    with sqlite3.connect(db_path) as conn:
        audit_row = conn.execute(
            """
            SELECT from_version, to_version, status, backup_path
            FROM schema_migration_audit
            WHERE id LIKE 'migration_session_%'
            """
        ).fetchone()
        assert audit_row == (
            29,
            31,
            "applied",
            str(backups_after_first_open[0]),
        )

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        assert conn.execute(
            """
            SELECT COUNT(*)
            FROM creator_system_metrics
            WHERE event_type = 'METRIC'
              AND json_extract(payload_json, '$.metric') = 'LEGACY_MIGRATION_FINISHED'
            """
        ).fetchone()[0] == 1
        first_open_fingerprint = fingerprint_database(conn)

    second = ProjectRepository(tmp_path)
    assert second.db_path == db_path
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        assert fingerprint_database(conn) == first_open_fingerprint
        assert conn.execute(
            "SELECT COUNT(*) FROM projects WHERE id = ?",
            (LEGACY_PROJECT_ID,),
        ).fetchone()[0] == 1
        assert conn.execute(
            """
            SELECT COUNT(*)
            FROM creator_system_metrics
            WHERE event_type = 'METRIC'
              AND json_extract(payload_json, '$.metric') = 'LEGACY_MIGRATION_FINISHED'
            """
        ).fetchone()[0] == 1
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert sorted(
        (tmp_path / "projects" / "backups").glob("pre-migration-v29-to-v31-*.sqlite3")
    ) == backups_after_first_open


def test_interrupted_real_v30_migration_restores_exact_v29_backup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = create_v29_project_store(tmp_path)
    with sqlite3.connect(db_path) as conn:
        original_fingerprint = fingerprint_database(conn)
        original_history = capture_table_digests(conn)

    real_migrate = migrations.migrate
    created_v30_tables: list[str] = []

    def fail_during_v30(conn: sqlite3.Connection) -> None:
        def authorizer(
            action: int,
            arg1: str | None,
            _arg2: str | None,
            _database: str | None,
            _trigger: str | None,
        ) -> int:
            if (
                action == sqlite3.SQLITE_CREATE_TABLE
                and arg1 is not None
                and arg1.startswith("creator_")
            ):
                created_v30_tables.append(arg1)
                if len(created_v30_tables) == 4:
                    return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        conn.set_authorizer(authorizer)
        try:
            real_migrate(conn)
        finally:
            conn.set_authorizer(None)

    monkeypatch.setattr(project_repository_module, "migrate", fail_during_v30)
    with pytest.raises(sqlite3.DatabaseError):
        ProjectRepository(tmp_path)

    assert len(created_v30_tables) == 4
    backup_paths = sorted(
        (tmp_path / "projects" / "backups").glob("pre-migration-v29-to-v31-*.sqlite3")
    )
    assert len(backup_paths) == 1
    backup_path = backup_paths[0]
    with sqlite3.connect(backup_path) as backup_conn:
        assert fingerprint_database(backup_conn) == original_fingerprint

    with sqlite3.connect(db_path) as partial_conn:
        partial_tables = {
            str(row[0])
            for row in partial_conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert set(created_v30_tables[:3]).issubset(partial_tables)
        assert fingerprint_database(partial_conn) != original_fingerprint

    shutil.copy2(backup_path, db_path)
    with sqlite3.connect(db_path) as restored_conn:
        assert fingerprint_database(restored_conn) == original_fingerprint

    monkeypatch.setattr(project_repository_module, "migrate", real_migrate)
    recovered = ProjectRepository(tmp_path)
    assert recovered.db_path == db_path
    with sqlite3.connect(db_path) as conn:
        recovered_history = capture_table_digests(
            conn,
            columns_by_table={
                table: original_history[table].columns
                for table in LEGACY_HISTORY_TABLES
            },
        )
        assert recovered_history == original_history
        assert int(conn.execute("PRAGMA user_version").fetchone()[0]) == 31
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_v30_migration_records_one_database_metric_for_multiple_projects(
    tmp_path: Path,
) -> None:
    db_path = create_v29_project_store(tmp_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        source = conn.execute(
            "SELECT * FROM projects WHERE id = ?",
            (LEGACY_PROJECT_ID,),
        ).fetchone()
        assert source is not None
        columns = [str(item) for item in source.keys()]
        values = [source[column] for column in columns]
        values[columns.index("id")] = "prj_legacy_second"
        values[columns.index("name")] = "第二个历史项目"
        placeholders = ", ".join("?" for _ in columns)
        quoted_columns = ", ".join(f'"{column}"' for column in columns)
        conn.execute(
            f"INSERT INTO projects ({quoted_columns}) VALUES ({placeholders})",
            values,
        )
        conn.commit()

    ProjectRepository(tmp_path)
    with sqlite3.connect(db_path) as conn:
        assert conn.execute(
            """
            SELECT COUNT(*) FROM creator_events
            WHERE event_type = 'METRIC'
              AND json_extract(payload_json, '$.metric') = 'WORK_CREATED'
            """
        ).fetchone()[0] == 2
        assert conn.execute(
            """
            SELECT COUNT(*) FROM creator_system_metrics
            WHERE event_type = 'METRIC'
              AND json_extract(payload_json, '$.metric') =
                  'LEGACY_MIGRATION_FINISHED'
            """
        ).fetchone()[0] == 1


def test_late_v30_repair_failure_never_records_success_metric(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = create_v29_project_store(tmp_path)

    def fail_after_core_repair(_conn: sqlite3.Connection) -> None:
        raise sqlite3.DatabaseError("injected late repair failure")

    monkeypatch.setattr(
        migrations,
        "_repair_v30_creator_physical_runs",
        fail_after_core_repair,
    )
    with pytest.raises(sqlite3.DatabaseError, match="late repair failure"):
        ProjectRepository(tmp_path)

    with sqlite3.connect(db_path) as conn:
        tables = {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        if "creator_system_metrics" in tables:
            assert conn.execute(
                "SELECT COUNT(*) FROM creator_system_metrics"
            ).fetchone()[0] == 0
        if "creator_events" in tables:
            assert conn.execute(
                "SELECT COUNT(*) FROM creator_events WHERE event_type = 'METRIC'"
            ).fetchone()[0] == 0
        assert conn.execute(
            """
            SELECT COUNT(*) FROM schema_migration_audit
            WHERE id = 'migration_v29_v30' AND status = 'applied'
            """
        ).fetchone()[0] == 0
