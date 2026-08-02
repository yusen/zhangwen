from __future__ import annotations

import base64
import hashlib
import json
import secrets
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from zhangwen.auth.models import AccountProfile, AuthAccount, AuthSession, EmailAccount


AUTH_SCHEMA_VERSION = 2
PASSWORD_ITERATIONS = 600_000
SESSION_LIFETIME = timedelta(days=30)
_DUMMY_SALT = b"zhangwen-auth-dummy-salt"


class AuthError(ValueError):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class AuthRepository:
    def __init__(self, data_dir: Path) -> None:
        self._directory = data_dir / "auth"
        self._directory.mkdir(parents=True, exist_ok=True)
        self._db_path = self._directory / "zhangwen-auth.sqlite3"
        with self._connect() as conn:
            self._migrate(conn)

    def has_accounts(self) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM local_accounts WHERE status = 'active' LIMIT 1"
            ).fetchone()
        return row is not None

    def has_local_accounts(self) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT 1
                FROM local_accounts
                WHERE status = 'active' AND auth_kind = 'local'
                LIMIT 1
                """
            ).fetchone()
        return row is not None

    def local_accounts(self) -> list[AuthAccount]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, username, display_name, created_at
                FROM local_accounts
                WHERE status = 'active' AND auth_kind = 'local'
                ORDER BY created_at, username
                """
            ).fetchall()
        return [
            AuthAccount(
                id=str(row["id"]),
                username=str(row["username"]),
                displayName=str(row["display_name"]),
                createdAt=str(row["created_at"]),
            )
            for row in rows
        ]

    def reset_local_password(self, *, username: str, new_password: str) -> AuthAccount:
        normalized_username = username.strip().lower()
        _validate_local_password(new_password)
        salt = secrets.token_bytes(16)
        password_hash = _derive_password(new_password, salt, PASSWORD_ITERATIONS)
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT id, username, display_name, created_at
                FROM local_accounts
                WHERE username = ? COLLATE NOCASE
                  AND status = 'active'
                  AND auth_kind = 'local'
                """,
                (normalized_username,),
            ).fetchone()
            if row is None:
                raise AuthError(
                    "AUTH_LOCAL_ACCOUNT_NOT_FOUND",
                    "没有找到可恢复的本机账号。",
                    404,
                )
            account_id = str(row["id"])
            conn.execute(
                """
                UPDATE local_accounts
                SET password_hash = ?,
                    password_salt = ?,
                    password_iterations = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    password_hash,
                    base64.b64encode(salt).decode("ascii"),
                    PASSWORD_ITERATIONS,
                    now,
                    account_id,
                ),
            )
            conn.execute(
                "DELETE FROM auth_sessions WHERE account_id = ?",
                (account_id,),
            )
        return AuthAccount(
            id=account_id,
            username=str(row["username"]),
            displayName=str(row["display_name"]),
            createdAt=str(row["created_at"]),
        )

    def device_id(self) -> str:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM auth_metadata WHERE key = 'device_id'"
            ).fetchone()
            if row is not None:
                return str(row["value"])
            value = _id("device")
            conn.execute(
                "INSERT INTO auth_metadata (key, value, updated_at) VALUES ('device_id', ?, ?)",
                (value, _now()),
            )
            return value

    def create_cloud_session(
        self,
        *,
        account_data: dict[str, object],
        profile_data: dict[str, object],
        offline_lease_expires_at: str,
    ) -> tuple[EmailAccount, AccountProfile, str, str]:
        account = EmailAccount.model_validate(account_data)
        profile = AccountProfile.model_validate(profile_data)
        now = _now()
        local_account_id = f"cloud_{account.id}"
        token = secrets.token_urlsafe(32)
        token_hash = _token_hash(token)
        session_expires_at = _bounded_session_expiry(now, offline_lease_expires_at)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO local_accounts (
                  id, username, display_name, password_hash, password_salt,
                  password_iterations, status, created_at, updated_at,
                  auth_kind, cloud_subject, email, email_verified_at,
                  offline_lease_expires_at, profile_json
                ) VALUES (?, ?, ?, 'CLOUD_MANAGED', '', 0, 'active', ?, ?,
                          'cloud', ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  username=excluded.username,
                  display_name=excluded.display_name,
                  status='active',
                  updated_at=excluded.updated_at,
                  email=excluded.email,
                  email_verified_at=excluded.email_verified_at,
                  offline_lease_expires_at=excluded.offline_lease_expires_at,
                  profile_json=excluded.profile_json
                """,
                (
                    local_account_id,
                    account.email,
                    account.displayName,
                    account.createdAt,
                    now,
                    account.id,
                    account.email,
                    now if account.emailVerified else None,
                    offline_lease_expires_at,
                    profile.model_dump_json(),
                ),
            )
            self._insert_session(
                conn,
                account_id=local_account_id,
                token_hash=token_hash,
                created_at=now,
                expires_at=session_expires_at,
            )
        return account, profile, token, session_expires_at

    def cloud_identity(self, account_id: str) -> dict[str, object] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT cloud_subject, email, display_name, created_at,
                       email_verified_at, offline_lease_expires_at, profile_json
                FROM local_accounts
                WHERE id = ? AND auth_kind = 'cloud' AND status = 'active'
                """,
                (account_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "subject": str(row["cloud_subject"]),
            "account": {
                "id": str(row["cloud_subject"]),
                "email": str(row["email"]),
                "displayName": str(row["display_name"]),
                "emailVerified": row["email_verified_at"] is not None,
                "createdAt": str(row["created_at"]),
            },
            "profile": json.loads(str(row["profile_json"] or "{}")),
            "offlineLeaseExpiresAt": str(row["offline_lease_expires_at"]),
        }

    def update_cloud_profile(
        self,
        *,
        cloud_subject: str,
        account_data: dict[str, object],
        profile_data: dict[str, object],
        offline_lease_expires_at: str | None = None,
    ) -> tuple[EmailAccount, AccountProfile]:
        account = EmailAccount.model_validate(account_data)
        profile = AccountProfile.model_validate(profile_data)
        with self._connect() as conn:
            values: list[object] = [
                account.displayName,
                account.email,
                profile.model_dump_json(),
                _now(),
            ]
            lease_sql = ""
            if offline_lease_expires_at is not None:
                lease_sql = ", offline_lease_expires_at = ?"
                values.append(offline_lease_expires_at)
            values.append(cloud_subject)
            cursor = conn.execute(
                f"""
                UPDATE local_accounts
                SET display_name = ?, email = ?, profile_json = ?, updated_at = ?
                    {lease_sql}
                WHERE cloud_subject = ? AND auth_kind = 'cloud'
                """,
                values,
            )
            if cursor.rowcount != 1:
                raise _invalid_session()
        return account, profile

    def register(
        self,
        *,
        username: str,
        display_name: str,
        password: str,
    ) -> tuple[AuthAccount, str, str]:
        now = _now()
        account_id = _id("account")
        salt = secrets.token_bytes(16)
        password_hash = _derive_password(password, salt, PASSWORD_ITERATIONS)
        token, token_hash, expires_at = _new_session(now)
        try:
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                existing = conn.execute(
                    "SELECT 1 FROM local_accounts WHERE username = ? COLLATE NOCASE",
                    (username,),
                ).fetchone()
                if existing is not None:
                    raise _account_exists()
                conn.execute(
                    """
                    INSERT INTO local_accounts (
                      id, username, display_name, password_hash, password_salt,
                      password_iterations, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)
                    """,
                    (
                        account_id,
                        username,
                        display_name,
                        password_hash,
                        base64.b64encode(salt).decode("ascii"),
                        PASSWORD_ITERATIONS,
                        now,
                        now,
                    ),
                )
                self._insert_session(
                    conn,
                    account_id=account_id,
                    token_hash=token_hash,
                    created_at=now,
                    expires_at=expires_at,
                )
        except sqlite3.IntegrityError as exc:
            raise _account_exists() from exc
        return (
            AuthAccount(
                id=account_id,
                username=username,
                displayName=display_name,
                createdAt=now,
            ),
            token,
            expires_at,
        )

    def login(self, *, username: str, password: str) -> tuple[AuthAccount, str, str]:
        now = _now()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, username, display_name, password_hash, password_salt,
                       password_iterations, status, created_at
                FROM local_accounts
                WHERE username = ? COLLATE NOCASE
                """,
                (username,),
            ).fetchone()
            if row is None:
                candidate = _derive_password(password, _DUMMY_SALT, PASSWORD_ITERATIONS)
                secrets.compare_digest(candidate, candidate)
                raise _invalid_credentials()
            salt = base64.b64decode(str(row["password_salt"]).encode("ascii"))
            candidate = _derive_password(
                password,
                salt,
                int(row["password_iterations"]),
            )
            if row["status"] != "active" or not secrets.compare_digest(
                candidate,
                str(row["password_hash"]),
            ):
                raise _invalid_credentials()
            token, token_hash, expires_at = _new_session(now)
            self._insert_session(
                conn,
                account_id=str(row["id"]),
                token_hash=token_hash,
                created_at=now,
                expires_at=expires_at,
            )
            account = self._account(row)
        return account, token, expires_at

    def validate_session(self, token: str) -> AuthSession:
        token_hash = _token_hash(token)
        now = datetime.now(UTC)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT s.token_hash, s.expires_at, s.revoked_at,
                       a.id, a.username, a.display_name, a.created_at, a.status,
                       a.auth_kind, a.offline_lease_expires_at
                FROM auth_sessions s
                JOIN local_accounts a ON a.id = s.account_id
                WHERE s.token_hash = ?
                """,
                (token_hash,),
            ).fetchone()
            if row is None or row["revoked_at"] is not None or row["status"] != "active":
                raise _invalid_session()
            try:
                expires_at = datetime.fromisoformat(str(row["expires_at"]))
            except ValueError as exc:
                raise _invalid_session() from exc
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if expires_at <= now:
                conn.execute(
                    "UPDATE auth_sessions SET revoked_at = ? WHERE token_hash = ?",
                    (_now(), token_hash),
                )
                raise _invalid_session()
            if row["auth_kind"] == "cloud":
                lease_value = row["offline_lease_expires_at"]
                try:
                    lease_expires_at = datetime.fromisoformat(str(lease_value))
                except (TypeError, ValueError) as exc:
                    raise _invalid_session() from exc
                if lease_expires_at.tzinfo is None:
                    lease_expires_at = lease_expires_at.replace(tzinfo=UTC)
                if lease_expires_at <= now:
                    conn.execute(
                        "UPDATE auth_sessions SET revoked_at = ? WHERE token_hash = ?",
                        (_now(), token_hash),
                    )
                    raise AuthError(
                        "OFFLINE_LEASE_EXPIRED",
                        "离线使用期限已到，请联网重新登录。",
                        401,
                    )
            conn.execute(
                "UPDATE auth_sessions SET last_seen_at = ? WHERE token_hash = ?",
                (_now(), token_hash),
            )
            return AuthSession(
                account=self._account(row),
                tokenHash=token_hash,
                expiresAt=expires_at.isoformat(),
            )

    def logout(self, token: str) -> None:
        token_hash = _token_hash(token)
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE auth_sessions
                SET revoked_at = COALESCE(revoked_at, ?)
                WHERE token_hash = ?
                """,
                (_now(), token_hash),
            )

    @staticmethod
    def _insert_session(
        conn: sqlite3.Connection,
        *,
        account_id: str,
        token_hash: str,
        created_at: str,
        expires_at: str,
    ) -> None:
        conn.execute(
            "DELETE FROM auth_sessions WHERE expires_at <= ? OR revoked_at IS NOT NULL",
            (created_at,),
        )
        conn.execute(
            """
            INSERT INTO auth_sessions (
              id, account_id, token_hash, created_at, expires_at,
              last_seen_at, revoked_at
            ) VALUES (?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                _id("session"),
                account_id,
                token_hash,
                created_at,
                expires_at,
                created_at,
            ),
        )

    @staticmethod
    def _account(row: sqlite3.Row) -> AuthAccount:
        return AuthAccount(
            id=str(row["id"]),
            username=str(row["username"]),
            displayName=str(row["display_name"]),
            createdAt=str(row["created_at"]),
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @staticmethod
    def _migrate(conn: sqlite3.Connection) -> None:
        version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        if version > AUTH_SCHEMA_VERSION:
            raise RuntimeError("认证数据库版本高于当前应用支持版本。")
        if version == 0:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS local_accounts (
                  id TEXT PRIMARY KEY,
                  username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                  display_name TEXT NOT NULL,
                  password_hash TEXT NOT NULL,
                  password_salt TEXT NOT NULL,
                  password_iterations INTEGER NOT NULL,
                  status TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS auth_sessions (
                  id TEXT PRIMARY KEY,
                  account_id TEXT NOT NULL REFERENCES local_accounts(id) ON DELETE CASCADE,
                  token_hash TEXT NOT NULL UNIQUE,
                  created_at TEXT NOT NULL,
                  expires_at TEXT NOT NULL,
                  last_seen_at TEXT NOT NULL,
                  revoked_at TEXT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_auth_sessions_account
                  ON auth_sessions(account_id, expires_at);

                PRAGMA user_version=1;
                """
            )
            version = 1
        if version == 1:
            conn.executescript(
                """
                ALTER TABLE local_accounts ADD COLUMN auth_kind TEXT NOT NULL DEFAULT 'local';
                ALTER TABLE local_accounts ADD COLUMN cloud_subject TEXT NULL;
                ALTER TABLE local_accounts ADD COLUMN email TEXT NULL;
                ALTER TABLE local_accounts ADD COLUMN email_verified_at TEXT NULL;
                ALTER TABLE local_accounts ADD COLUMN offline_lease_expires_at TEXT NULL;
                ALTER TABLE local_accounts ADD COLUMN profile_json TEXT NOT NULL DEFAULT '{}';

                CREATE UNIQUE INDEX IF NOT EXISTS idx_local_accounts_cloud_subject
                  ON local_accounts(cloud_subject) WHERE cloud_subject IS NOT NULL;
                CREATE UNIQUE INDEX IF NOT EXISTS idx_local_accounts_email
                  ON local_accounts(email COLLATE NOCASE) WHERE email IS NOT NULL;

                CREATE TABLE IF NOT EXISTS auth_metadata (
                  key TEXT PRIMARY KEY,
                  value TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );

                PRAGMA user_version=2;
                """
            )


def _derive_password(password: str, salt: bytes, iterations: int) -> str:
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return base64.b64encode(derived).decode("ascii")


def _validate_local_password(password: str) -> None:
    if not 8 <= len(password) <= 128:
        raise AuthError(
            "AUTH_PASSWORD_INVALID",
            "密码必须为 8–128 位。",
            422,
        )
    if not any(character.isascii() and character.isalpha() for character in password):
        raise AuthError(
            "AUTH_PASSWORD_INVALID",
            "密码至少需要一个字母。",
            422,
        )
    if not any(character.isascii() and character.isdigit() for character in password):
        raise AuthError(
            "AUTH_PASSWORD_INVALID",
            "密码至少需要一个数字。",
            422,
        )


def _new_session(now: str) -> tuple[str, str, str]:
    token = secrets.token_urlsafe(32)
    created_at = datetime.fromisoformat(now)
    expires_at = (created_at + SESSION_LIFETIME).isoformat()
    return token, _token_hash(token), expires_at


def _bounded_session_expiry(now: str, offline_lease_expires_at: str) -> str:
    created_at = datetime.fromisoformat(now)
    lease_expires_at = datetime.fromisoformat(offline_lease_expires_at)
    if lease_expires_at.tzinfo is None:
        lease_expires_at = lease_expires_at.replace(tzinfo=UTC)
    return min(created_at + SESSION_LIFETIME, lease_expires_at).isoformat()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _invalid_credentials() -> AuthError:
    return AuthError(
        "AUTH_CREDENTIALS_INVALID",
        "用户名或密码不正确。",
        401,
    )


def _account_exists() -> AuthError:
    return AuthError(
        "ACCOUNT_ALREADY_EXISTS",
        "该用户名已被使用，请更换后重试。",
        409,
    )


def _invalid_session() -> AuthError:
    return AuthError(
        "AUTH_SESSION_INVALID",
        "登录已失效，请重新登录。",
        401,
    )


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _now() -> str:
    return datetime.now(UTC).isoformat()
