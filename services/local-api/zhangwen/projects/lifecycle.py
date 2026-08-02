"""Recoverable project duplication and permanent-deletion workflows."""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from zhangwen.auth.context import current_owner_subject
from zhangwen.projects.errors import (
    ProjectArchivedError,
    ProjectNotFoundError,
    ProjectValidationError,
)
from zhangwen.projects.repository import ProjectRepository


_CLONE_EXCLUDED_TABLES = {
    "device_operations",
    "device_sessions",
    "package_exports",
}
_DEFERRED_DEPENDENCY_EDGES = {("cad_runs", "cad_jobs")}
_SERIAL_KEYS = {
    "deviceid",
    "deviceidentifier",
    "port",
    "portid",
    "portname",
    "serial",
    "serialid",
    "serialnumber",
    "uniqueidhash",
}


class ProjectLifecycleService:
    """Clone local project graphs and delete archived projects behind a backup."""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = Path(data_dir).resolve()
        self._repo = ProjectRepository(self._data_dir)
        self._db_path = self._repo.db_path

    def duplicate(self, project_id: str, *, name: str | None = None):
        source = self._repo.get_workspace(project_id)
        new_project_id = f"project_{uuid.uuid4().hex}"
        now = _now()
        destination_artifact_root = (
            self._data_dir / "artifact-files" / new_project_id
        ).resolve()

        with self._connect() as conn:
            clone_rows = self._project_rows(conn, project_id)
            excluded_artifacts = self._device_log_artifact_ids(clone_rows)
            clone_rows = self._without_device_log_artifacts(
                clone_rows,
                excluded_artifacts,
            )
            identifier_map = self._identifier_map(
                clone_rows,
                source_project_id=project_id,
                new_project_id=new_project_id,
            )
            table_order = self._table_order(conn, clone_rows)
            project_row = conn.execute(
                "SELECT * FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            if project_row is None:
                raise ProjectNotFoundError("项目不存在。")

            copied_files: list[tuple[Path, Path]] = []
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("PRAGMA defer_foreign_keys=ON")
                self._insert_project(
                    conn,
                    project_row,
                    new_project_id=new_project_id,
                    name=name or f"{source.project.name}（副本）",
                    identifier_map=identifier_map,
                    now=now,
                )
                for table in table_order:
                    for row in clone_rows[table]:
                        values = self._clone_row(
                            table,
                            row,
                            source_project_id=project_id,
                            new_project_id=new_project_id,
                            identifier_map=identifier_map,
                            copied_files=copied_files,
                        )
                        self._insert_row(conn, table, values)
                self._set_active_project(conn, new_project_id, now)
                violations = conn.execute("PRAGMA foreign_key_check").fetchall()
                if violations:
                    raise ProjectValidationError("项目副本 ID 图校验失败，未创建副本。")
                conn.commit()
            except Exception:
                if conn.in_transaction:
                    conn.rollback()
                if destination_artifact_root.is_dir():
                    shutil.rmtree(destination_artifact_root)
                raise

        return self._repo.get_workspace(new_project_id)

    def permanently_delete(
        self,
        project_id: str,
        *,
        confirmation_name: str,
    ) -> tuple[str, str]:
        workspace = self._repo.get_workspace(project_id)
        if workspace.project.archivedAt is None:
            raise ProjectArchivedError("只有归档区中的项目才能永久删除。")
        if confirmation_name != workspace.project.name:
            raise ProjectValidationError("输入的项目名称不匹配，未执行永久删除。")

        now = datetime.now(UTC)
        stamp = now.strftime("%Y%m%d-%H%M%S-%f")
        backup_id = f"project-delete-{stamp}-{project_id}"
        backup_root = (self._data_dir / "project-deletion-backups" / backup_id).resolve()
        backup_root.mkdir(parents=True, exist_ok=False)
        backup_db = backup_root / "zhangwen.sqlite3"
        with sqlite3.connect(self._db_path) as source_conn:
            with sqlite3.connect(backup_db) as backup_conn:
                source_conn.backup(backup_conn)

        active_artifacts = (self._data_dir / "artifact-files" / project_id).resolve()
        if active_artifacts.is_dir():
            shutil.copytree(active_artifacts, backup_root / "artifact-files")

        try:
            with self._connect() as conn:
                project = conn.execute(
                    "SELECT archived_at FROM projects WHERE id = ?",
                    (project_id,),
                ).fetchone()
                if project is None:
                    raise ProjectNotFoundError("项目不存在。")
                if project["archived_at"] is None:
                    raise ProjectArchivedError("只有归档区中的项目才能永久删除。")
                tables = self._project_tables(conn, include_excluded=True)
                table_order = self._table_order(
                    conn,
                    {table: [] for table in tables},
                )
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("PRAGMA defer_foreign_keys=ON")
                conn.execute(
                    "UPDATE account_workspace_state SET current_project_id = NULL "
                    "WHERE current_project_id = ?",
                    (project_id,),
                )
                for table in reversed(table_order):
                    conn.execute(
                        f"DELETE FROM {_quote_identifier(table)} WHERE project_id = ?",
                        (project_id,),
                    )
                conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
                violations = conn.execute("PRAGMA foreign_key_check").fetchall()
                if violations:
                    raise ProjectValidationError("删除后的数据库一致性检查失败，已自动回滚。")
                conn.commit()
        except Exception:
            raise

        if active_artifacts.is_dir():
            shutil.rmtree(active_artifacts)
        return backup_id, now.isoformat()

    def _project_rows(
        self,
        conn: sqlite3.Connection,
        project_id: str,
    ) -> dict[str, list[sqlite3.Row]]:
        return {
            table: conn.execute(
                f"SELECT * FROM {_quote_identifier(table)} WHERE project_id = ?",
                (project_id,),
            ).fetchall()
            for table in self._project_tables(conn)
        }

    def _project_tables(
        self,
        conn: sqlite3.Connection,
        *,
        include_excluded: bool = False,
    ) -> list[str]:
        tables = [
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        ]
        return [
            table
            for table in tables
            if (include_excluded or table not in _CLONE_EXCLUDED_TABLES)
            and "project_id" in self._columns(conn, table)
        ]

    @staticmethod
    def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
        return [
            str(row[1])
            for row in conn.execute(
                f"PRAGMA table_info({_quote_identifier(table)})"
            ).fetchall()
        ]

    @staticmethod
    def _device_log_artifact_ids(
        rows: dict[str, list[sqlite3.Row]],
    ) -> set[str]:
        return {
            str(row["id"])
            for row in rows.get("artifacts", [])
            if str(row["kind"]) == "DEVICE_LOG"
        }

    @staticmethod
    def _without_device_log_artifacts(
        rows: dict[str, list[sqlite3.Row]],
        excluded_artifacts: set[str],
    ) -> dict[str, list[sqlite3.Row]]:
        if not excluded_artifacts:
            return rows
        excluded_versions = {
            str(row["id"])
            for row in rows.get("artifact_versions", [])
            if str(row["artifact_id"]) in excluded_artifacts
        }
        filtered: dict[str, list[sqlite3.Row]] = {}
        for table, candidates in rows.items():
            kept: list[sqlite3.Row] = []
            for row in candidates:
                keys = set(row.keys())
                if "artifact_id" in keys and str(row["artifact_id"]) in excluded_artifacts:
                    continue
                if (
                    "artifact_version_id" in keys
                    and str(row["artifact_version_id"]) in excluded_versions
                ):
                    continue
                if table == "artifacts" and str(row["id"]) in excluded_artifacts:
                    continue
                if table == "artifact_versions" and str(row["id"]) in excluded_versions:
                    continue
                kept.append(row)
            filtered[table] = kept
        return filtered

    @staticmethod
    def _identifier_map(
        rows: dict[str, list[sqlite3.Row]],
        *,
        source_project_id: str,
        new_project_id: str,
    ) -> dict[str, str]:
        result = {source_project_id: new_project_id}
        for table, candidates in rows.items():
            prefix = re.sub(r"[^a-z0-9]+", "_", table.lower()).strip("_") or "row"
            for row in candidates:
                if "id" not in row.keys() or row["id"] is None:
                    continue
                old_id = str(row["id"])
                result.setdefault(
                    old_id,
                    (
                        old_id.replace(source_project_id, new_project_id)
                        if source_project_id in old_id
                        else f"{prefix}_{uuid.uuid4().hex}"
                    ),
                )
        return result

    def _table_order(
        self,
        conn: sqlite3.Connection,
        rows: dict[str, list[sqlite3.Row]],
    ) -> list[str]:
        tables = set(rows)
        dependencies: dict[str, set[str]] = {table: set() for table in tables}
        for table in tables:
            for foreign_key in conn.execute(
                f"PRAGMA foreign_key_list({_quote_identifier(table)})"
            ).fetchall():
                referenced = str(foreign_key[2])
                if (
                    referenced in tables
                    and referenced != table
                    and (table, referenced) not in _DEFERRED_DEPENDENCY_EDGES
                ):
                    dependencies[table].add(referenced)
        order: list[str] = []
        remaining = set(tables)
        while remaining:
            ready = sorted(
                table for table in remaining if not (dependencies[table] & remaining)
            )
            if not ready:
                raise ProjectValidationError("项目数据表依赖存在循环，无法安全处理。")
            order.extend(ready)
            remaining.difference_update(ready)
        return order

    def _insert_project(
        self,
        conn: sqlite3.Connection,
        row: sqlite3.Row,
        *,
        new_project_id: str,
        name: str,
        identifier_map: dict[str, str],
        now: str,
    ) -> None:
        values = dict(row)
        values["id"] = new_project_id
        values["name"] = name
        values["owner_subject"] = current_owner_subject() or row["owner_subject"]
        values["archived_at"] = None
        values["created_at"] = now
        values["updated_at"] = now
        values["last_opened_at"] = now
        for key, value in tuple(values.items()):
            values[key] = _rewrite_value(key, value, identifier_map)
        self._insert_row(conn, "projects", values)

    def _clone_row(
        self,
        table: str,
        row: sqlite3.Row,
        *,
        source_project_id: str,
        new_project_id: str,
        identifier_map: dict[str, str],
        copied_files: list[tuple[Path, Path]],
    ) -> dict[str, Any]:
        values = {
            key: _rewrite_value(key, row[key], identifier_map)
            for key in row.keys()
        }
        values["project_id"] = new_project_id
        if table == "artifact_files":
            version_id = str(values["artifact_version_id"])
            artifact_id = str(values["artifact_id"])
            source = _artifact_file_path(self._data_dir, str(row["storage_key"]))
            destination_key = PurePosixPath(
                new_project_id,
                artifact_id,
                version_id,
                str(values["file_name"]),
            ).as_posix()
            destination = _artifact_file_path(self._data_dir, destination_key)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            copied_files.append((source, destination))
            values["storage_key"] = destination_key
        return values

    @staticmethod
    def _insert_row(
        conn: sqlite3.Connection,
        table: str,
        values: dict[str, Any],
    ) -> None:
        columns = list(values)
        placeholders = ", ".join("?" for _ in columns)
        conn.execute(
            f"INSERT INTO {_quote_identifier(table)} "
            f"({', '.join(_quote_identifier(column) for column in columns)}) "
            f"VALUES ({placeholders})",
            tuple(values[column] for column in columns),
        )

    @staticmethod
    def _set_active_project(
        conn: sqlite3.Connection,
        project_id: str,
        now: str,
    ) -> None:
        owner = current_owner_subject()
        if owner is None:
            conn.execute(
                "INSERT INTO meta (key, value) VALUES ('activeProjectId', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (project_id,),
            )
            return
        conn.execute(
            """
            INSERT INTO account_workspace_state (
              owner_subject, current_project_id, legacy_claim_decision_at, updated_at
            ) VALUES (?, ?, NULL, ?)
            ON CONFLICT(owner_subject) DO UPDATE SET
              current_project_id = excluded.current_project_id,
              updated_at = excluded.updated_at
            """,
            (owner, project_id, now),
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


def _rewrite_value(column: str, value: Any, identifier_map: dict[str, str]) -> Any:
    if not isinstance(value, str):
        return value
    if value in identifier_map:
        return identifier_map[value]
    if column.endswith("_json") or column in {"metadata", "structured_payload"}:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return value
        return json.dumps(
            _rewrite_json(parsed, identifier_map),
            ensure_ascii=False,
            separators=(",", ":"),
        )
    if column in {"workspace_root", "storage_key"}:
        return _replace_embedded_identifiers(value, identifier_map)
    return value


def _rewrite_json(value: Any, identifier_map: dict[str, str]) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if normalized_key in _SERIAL_KEYS:
                continue
            result[str(key)] = _rewrite_json(item, identifier_map)
        return result
    if isinstance(value, list):
        return [_rewrite_json(item, identifier_map) for item in value]
    if isinstance(value, str):
        return _replace_embedded_identifiers(value, identifier_map)
    return value


def _replace_embedded_identifiers(value: str, identifier_map: dict[str, str]) -> str:
    if value in identifier_map:
        return identifier_map[value]
    rewritten = value
    for old, new in sorted(identifier_map.items(), key=lambda item: -len(item[0])):
        if old in rewritten:
            rewritten = rewritten.replace(old, new)
    return rewritten


def _artifact_file_path(data_dir: Path, storage_key: str) -> Path:
    root = (data_dir / "artifact-files").resolve()
    relative = PurePosixPath(storage_key)
    if relative.is_absolute() or ".." in relative.parts or "\\" in storage_key:
        raise ProjectValidationError("产物文件路径无效，无法复制项目。")
    path = root.joinpath(*relative.parts).resolve()
    if not path.is_relative_to(root):
        raise ProjectValidationError("产物文件路径越界，无法复制项目。")
    return path


def _quote_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ProjectValidationError("项目数据库包含不安全的表或字段名。")
    return f'"{value}"'


def _now() -> str:
    return datetime.now(UTC).isoformat()
