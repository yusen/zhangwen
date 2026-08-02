from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS cloud_accounts (
      id TEXT PRIMARY KEY,
      email TEXT NOT NULL UNIQUE,
      display_name TEXT NOT NULL,
      password_hash TEXT NOT NULL,
      email_verified_at TEXT NULL,
      status TEXT NOT NULL,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS email_challenges (
      id TEXT PRIMARY KEY,
      account_id TEXT NULL REFERENCES cloud_accounts(id) ON DELETE CASCADE,
      email TEXT NOT NULL,
      purpose TEXT NOT NULL,
      code_hash TEXT NOT NULL,
      created_at TEXT NOT NULL,
      expires_at TEXT NOT NULL,
      consumed_at TEXT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS refresh_sessions (
      token_hash TEXT PRIMARY KEY,
      family_id TEXT NOT NULL,
      account_id TEXT NOT NULL REFERENCES cloud_accounts(id) ON DELETE CASCADE,
      device_id_hash TEXT NOT NULL,
      created_at TEXT NOT NULL,
      expires_at TEXT NOT NULL,
      replaced_by_hash TEXT NULL,
      revoked_at TEXT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS access_sessions (
      token_hash TEXT PRIMARY KEY,
      account_id TEXT NOT NULL REFERENCES cloud_accounts(id) ON DELETE CASCADE,
      refresh_family_id TEXT NOT NULL,
      created_at TEXT NOT NULL,
      expires_at TEXT NOT NULL,
      revoked_at TEXT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_profiles (
      account_id TEXT PRIMARY KEY REFERENCES cloud_accounts(id) ON DELETE CASCADE,
      persona TEXT NULL,
      technical_level TEXT NULL,
      preferred_boards_json TEXT NOT NULL,
      budget_preference TEXT NULL,
      needs_lesson INTEGER NOT NULL,
      completed INTEGER NOT NULL,
      updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS auth_attempts (
      id TEXT PRIMARY KEY,
      action TEXT NOT NULL,
      key_hash TEXT NOT NULL,
      attempted_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_auth_attempts_window ON auth_attempts(action, key_hash, attempted_at)",
    """
    CREATE TABLE IF NOT EXISTS auth_audit_events (
      id TEXT PRIMARY KEY,
      account_id TEXT NULL,
      event_type TEXT NOT NULL,
      subject_hash TEXT NOT NULL,
      created_at TEXT NOT NULL
    )
    """,
)


class Database:
    def __init__(self, url: str) -> None:
        self.url = url
        self._sqlite_path = self._parse_sqlite(url)

    def initialize(self) -> None:
        with self.transaction() as conn:
            for statement in SCHEMA:
                self.execute(conn, statement)

    @contextmanager
    def transaction(self) -> Iterator[Any]:
        if self._sqlite_path is not None:
            self._sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self._sqlite_path, timeout=30)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
        else:
            try:
                import psycopg
                from psycopg.rows import dict_row
            except ImportError as exc:
                raise RuntimeError("PostgreSQL 运行需要安装 psycopg[binary]。") from exc
            conn = psycopg.connect(self.url, row_factory=dict_row)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute(self, conn: Any, sql: str, params: tuple[Any, ...] = ()) -> Any:
        query = sql if self._sqlite_path is not None else sql.replace("?", "%s")
        return conn.execute(query, params)

    @staticmethod
    def row_dict(row: Any | None) -> dict[str, Any] | None:
        return dict(row) if row is not None else None

    @staticmethod
    def _parse_sqlite(url: str) -> Path | None:
        prefix = "sqlite:///"
        if not url.startswith(prefix):
            return None
        return Path(url[len(prefix) :]).resolve()
