from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import re
import secrets
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

from fastapi import Request

from zhangwen.auth.context import current_owner_subject
from zhangwen.config import settings
from zhangwen.projects.repository import ProjectRepository


PAIRING_TTL = timedelta(minutes=2)
LEASE_TTL = timedelta(minutes=10)
MAX_USED_NONCES = 2048
BRIDGE_PROTOCOL = "zhangwen.local-bridge/v1"
ALLOWED_GRANTS = {"cad.local", "device.serial", "device.upload"}
CAPABILITY_GRANTS = {
    "local_cad": "cad.local",
    "serial_scan": "device.serial",
    "serial_connection": "device.serial",
    "device_upload": "device.upload",
}
_SAFE_TOKEN_PART = re.compile(r"^[A-Za-z0-9._-]{8,180}$")
_SAFE_NONCE = re.compile(r"^[A-Za-z0-9._:-]{16,180}$")


class LocalBridgeError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 403,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable

    def detail(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
        }


class LocalBridgeService:
    def __init__(self) -> None:
        repository = ProjectRepository(settings.data_dir)
        self._projects = repository
        self._db_path = repository.db_path

    def status(self, request: Request) -> dict[str, object]:
        require_loopback(request)
        return {
            "protocol": BRIDGE_PROTOCOL,
            "available": True,
            "loopbackOnly": True,
            "leaseTtlSeconds": int(LEASE_TTL.total_seconds()),
            "capabilities": sorted(ALLOWED_GRANTS),
        }

    def start_pairing(
        self,
        request: Request,
        *,
        origin: str,
        project_id: str,
        capabilities: list[str],
    ) -> dict[str, object]:
        require_loopback(request)
        normalized_origin = require_allowed_origin(origin)
        self._projects.assert_project_access(project_id)
        grants = sorted(set(capabilities))
        if not grants or any(item not in ALLOWED_GRANTS for item in grants):
            raise LocalBridgeError(
                "BRIDGE_CAPABILITY_INVALID",
                "Local Bridge 只能授予受支持的 CAD、串口和上传能力。",
                status_code=422,
            )
        pairing_id = f"bridge-{uuid.uuid4().hex}"
        code = f"{secrets.randbelow(1_000_000):06d}"
        now = _now_dt()
        expires = now + PAIRING_TTL
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO local_bridge_sessions (
                  id, owner_subject, origin, project_id, challenge_hash,
                  capabilities_json, issued_at, expires_at, revoked_at,
                  last_seen_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, NULL, NULL, ?)
                """,
                (
                    pairing_id,
                    current_owner_subject(),
                    normalized_origin,
                    project_id,
                    _pairing_hash(code),
                    _dump({"grants": grants, "usedNonces": []}),
                    expires.isoformat(),
                    now.isoformat(),
                ),
            )
        return {
            "pairingId": pairing_id,
            "code": code,
            "origin": normalized_origin,
            "projectId": project_id,
            "capabilities": grants,
            "expiresAt": expires.isoformat(),
        }

    def claim(
        self,
        request: Request,
        *,
        pairing_id: str,
        code: str,
    ) -> dict[str, object]:
        require_loopback(request)
        origin = request_origin(request)
        now = _now_dt()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM local_bridge_sessions WHERE id = ?", (pairing_id,)
            ).fetchone()
            if row is None:
                raise LocalBridgeError(
                    "BRIDGE_PAIRING_NOT_FOUND", "配对挑战不存在。", status_code=404
                )
            self._require_pairing_row(row, origin, now)
            if not _verify_pairing_hash(code, str(row["challenge_hash"])):
                raise LocalBridgeError(
                    "BRIDGE_PAIRING_CODE_INVALID", "配对码无效或已使用。"
                )
            secret = secrets.token_urlsafe(32)
            lease_token = f"{pairing_id}.{secret}"
            expires = now + LEASE_TTL
            conn.execute(
                """
                UPDATE local_bridge_sessions
                SET challenge_hash = ?, issued_at = ?, expires_at = ?, last_seen_at = ?
                WHERE id = ? AND issued_at IS NULL
                """,
                (
                    f"lease${hashlib.sha256(lease_token.encode('utf-8')).hexdigest()}",
                    now.isoformat(),
                    expires.isoformat(),
                    now.isoformat(),
                    pairing_id,
                ),
            )
            if conn.total_changes != 1:
                raise LocalBridgeError(
                    "BRIDGE_PAIRING_ALREADY_CLAIMED", "配对码已经使用。", status_code=409
                )
            payload = _load_capabilities(row["capabilities_json"])
            return {
                "leaseToken": lease_token,
                "lease": {
                    "id": pairing_id,
                    "projectId": str(row["project_id"]),
                    "origin": str(row["origin"]),
                    "capabilities": payload["grants"],
                    "issuedAt": now.isoformat(),
                    "expiresAt": expires.isoformat(),
                    "revokedAt": None,
                },
            }

    def verify_request(self, request: Request, capability: str) -> bool:
        token = request.headers.get("x-zhangwen-bridge-lease", "").strip()
        if not token:
            return False
        require_loopback(request)
        if request.headers.get("x-zhangwen-host", "").strip().lower() != "web":
            raise LocalBridgeError(
                "BRIDGE_HOST_INVALID", "Local Bridge lease 只接受 Web Host 请求。"
            )
        grant = CAPABILITY_GRANTS.get(capability)
        if grant is None:
            raise LocalBridgeError(
                "BRIDGE_CAPABILITY_DENIED", "该本地能力不能通过 Local Bridge 授权。"
            )
        self._verify_and_touch(request, token, required_grant=grant)
        return True

    def revoke_current(self, request: Request) -> dict[str, object]:
        token = request.headers.get("x-zhangwen-bridge-lease", "").strip()
        if not token:
            raise LocalBridgeError("BRIDGE_LEASE_REQUIRED", "缺少 Local Bridge lease。")
        pairing_id = self._verify_and_touch(request, token, required_grant=None)
        now = _now_dt().isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE local_bridge_sessions SET revoked_at = ? WHERE id = ?",
                (now, pairing_id),
            )
        return {"revoked": True, "leaseId": pairing_id, "revokedAt": now}

    def list_sessions(self, request: Request) -> list[dict[str, object]]:
        require_loopback(request)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM local_bridge_sessions ORDER BY created_at DESC LIMIT 100"
            ).fetchall()
        return [_public_session(row) for row in rows]

    def revoke_session(self, request: Request, session_id: str) -> dict[str, object]:
        require_loopback(request)
        now = _now_dt().isoformat()
        with self._connect() as conn:
            updated = conn.execute(
                "UPDATE local_bridge_sessions SET revoked_at = ? WHERE id = ?",
                (now, session_id),
            )
            if updated.rowcount != 1:
                raise LocalBridgeError(
                    "BRIDGE_LEASE_NOT_FOUND", "Local Bridge lease 不存在。", status_code=404
                )
        return {"revoked": True, "leaseId": session_id, "revokedAt": now}

    def _verify_and_touch(
        self,
        request: Request,
        token: str,
        *,
        required_grant: str | None,
    ) -> str:
        pairing_id, separator, _secret = token.partition(".")
        if not separator or not _SAFE_TOKEN_PART.fullmatch(pairing_id):
            raise LocalBridgeError("BRIDGE_LEASE_INVALID", "Local Bridge lease 格式无效。")
        origin = request_origin(request)
        project_id = project_id_from_path(request.url.path)
        now = _now_dt()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM local_bridge_sessions WHERE id = ?", (pairing_id,)
            ).fetchone()
            if row is None:
                raise LocalBridgeError("BRIDGE_LEASE_INVALID", "Local Bridge lease 无效。")
            expected = str(row["challenge_hash"])
            supplied_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
            if not expected.startswith("lease$") or not hmac.compare_digest(
                expected.removeprefix("lease$"), supplied_hash
            ):
                raise LocalBridgeError("BRIDGE_LEASE_INVALID", "Local Bridge lease 无效。")
            self._require_active_lease(row, origin, project_id, now)
            payload = _load_capabilities(row["capabilities_json"])
            if required_grant is not None and required_grant not in payload["grants"]:
                raise LocalBridgeError(
                    "BRIDGE_CAPABILITY_DENIED",
                    "当前 Local Bridge lease 未授予此能力。",
                )
            if request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
                nonce = request.headers.get(
                    "x-zhangwen-bridge-request-id", ""
                ).strip()
                if not _SAFE_NONCE.fullmatch(nonce):
                    raise LocalBridgeError(
                        "BRIDGE_REQUEST_ID_REQUIRED",
                        "本地写操作需要一次性 request id。",
                    )
                if nonce in payload["usedNonces"]:
                    raise LocalBridgeError(
                        "BRIDGE_REQUEST_REPLAYED",
                        "重复的 Local Bridge 写请求已拒绝。",
                        status_code=409,
                    )
                if len(payload["usedNonces"]) >= MAX_USED_NONCES:
                    raise LocalBridgeError(
                        "BRIDGE_LEASE_NONCE_LIMIT",
                        "Local Bridge lease 已达到写请求上限，请重新配对。",
                        status_code=409,
                    )
                payload["usedNonces"].append(nonce)
            conn.execute(
                """
                UPDATE local_bridge_sessions
                SET capabilities_json = ?, last_seen_at = ? WHERE id = ?
                """,
                (_dump(payload), now.isoformat(), pairing_id),
            )
        return pairing_id

    def _require_pairing_row(
        self, row: sqlite3.Row, origin: str, now: datetime
    ) -> None:
        if row["issued_at"] is not None:
            raise LocalBridgeError(
                "BRIDGE_PAIRING_ALREADY_CLAIMED", "配对码已经使用。", status_code=409
            )
        if row["revoked_at"] is not None or _parse_time(row["expires_at"]) <= now:
            raise LocalBridgeError(
                "BRIDGE_PAIRING_EXPIRED", "配对挑战已过期。", status_code=409
            )
        if not hmac.compare_digest(str(row["origin"]), origin):
            raise LocalBridgeError(
                "BRIDGE_ORIGIN_MISMATCH", "请求 Origin 与配对挑战不一致。"
            )
        _require_owner(row)

    def _require_active_lease(
        self,
        row: sqlite3.Row,
        origin: str,
        project_id: str | None,
        now: datetime,
    ) -> None:
        if row["issued_at"] is None:
            raise LocalBridgeError("BRIDGE_LEASE_INVALID", "配对尚未完成。")
        if row["revoked_at"] is not None:
            raise LocalBridgeError("BRIDGE_LEASE_REVOKED", "Local Bridge lease 已撤销。")
        if _parse_time(row["expires_at"]) <= now:
            raise LocalBridgeError("BRIDGE_LEASE_EXPIRED", "Local Bridge lease 已过期。")
        if not hmac.compare_digest(str(row["origin"]), origin):
            raise LocalBridgeError(
                "BRIDGE_ORIGIN_MISMATCH", "请求 Origin 与 lease 不一致。"
            )
        if project_id is not None and row["project_id"] != project_id:
            raise LocalBridgeError(
                "BRIDGE_PROJECT_SCOPE_MISMATCH", "Local Bridge lease 不属于当前项目。"
            )
        _require_owner(row)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


def require_loopback(request: Request) -> None:
    host = request.client.host if request.client else ""
    try:
        if ipaddress.ip_address(host).is_loopback:
            return
    except ValueError:
        pass
    raise LocalBridgeError(
        "BRIDGE_LOOPBACK_REQUIRED",
        "Local Bridge 只接受本机回环连接。",
        status_code=403,
    )


def require_allowed_origin(origin: str) -> str:
    normalized = normalize_origin(origin)
    allowed = {normalize_origin(item) for item in settings.bridge_allowed_origins}
    if normalized not in allowed:
        raise LocalBridgeError(
            "BRIDGE_ORIGIN_DENIED", "该 Web Origin 未列入 Local Bridge 白名单。"
        )
    return normalized


def request_origin(request: Request) -> str:
    origin = request.headers.get("origin", "").strip()
    if not origin:
        raise LocalBridgeError("BRIDGE_ORIGIN_REQUIRED", "Local Bridge 请求缺少 Origin。")
    return require_allowed_origin(origin)


def normalize_origin(value: str) -> str:
    parsed = urlsplit(value.strip().rstrip("/"))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise LocalBridgeError("BRIDGE_ORIGIN_INVALID", "Local Bridge Origin 无效。")
    if parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise LocalBridgeError("BRIDGE_ORIGIN_INVALID", "Local Bridge Origin 无效。")
    host = parsed.hostname.lower()
    port = f":{parsed.port}" if parsed.port is not None else ""
    return f"{parsed.scheme.lower()}://{host}{port}"


def project_id_from_path(path: str) -> str | None:
    prefix = "/api/projects/"
    if path.startswith(prefix):
        candidate = path[len(prefix) :].split("/", 1)[0]
        return candidate or None
    return None


def _require_owner(row: sqlite3.Row) -> None:
    expected = row["owner_subject"]
    current = current_owner_subject()
    if expected is not None and current != expected:
        raise LocalBridgeError(
            "BRIDGE_OWNER_MISMATCH", "Local Bridge lease 不属于当前登录用户。"
        )


def _pairing_hash(code: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", code.encode("utf-8"), salt, 120_000)
    return f"pair$120000${salt.hex()}${digest.hex()}"


def _verify_pairing_hash(code: str, encoded: str) -> bool:
    try:
        prefix, rounds_raw, salt_hex, expected_hex = encoded.split("$", 3)
        if prefix != "pair":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            code.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(rounds_raw),
        )
        return hmac.compare_digest(digest.hex(), expected_hex)
    except (TypeError, ValueError):
        return False


def _load_capabilities(value: Any) -> dict[str, list[str]]:
    try:
        payload = json.loads(str(value))
    except (TypeError, ValueError):
        payload = {}
    if isinstance(payload, list):
        payload = {"grants": payload, "usedNonces": []}
    grants = [item for item in payload.get("grants", []) if item in ALLOWED_GRANTS]
    nonces = [item for item in payload.get("usedNonces", []) if isinstance(item, str)]
    return {"grants": sorted(set(grants)), "usedNonces": nonces}


def _public_session(row: sqlite3.Row) -> dict[str, object]:
    payload = _load_capabilities(row["capabilities_json"])
    return {
        "id": str(row["id"]),
        "origin": str(row["origin"]),
        "projectId": str(row["project_id"]),
        "capabilities": payload["grants"],
        "issuedAt": row["issued_at"],
        "expiresAt": row["expires_at"],
        "revokedAt": row["revoked_at"],
        "lastSeenAt": row["last_seen_at"],
        "createdAt": row["created_at"],
    }


def _parse_time(value: Any) -> datetime:
    try:
        return datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise LocalBridgeError("BRIDGE_LEASE_INVALID", "Local Bridge 时间字段无效。") from exc


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _now_dt() -> datetime:
    return datetime.now(UTC)
