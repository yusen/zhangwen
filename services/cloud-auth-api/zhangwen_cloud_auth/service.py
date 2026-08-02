from __future__ import annotations

import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Callable

from zhangwen_cloud_auth.database import Database
from zhangwen_cloud_auth.mailer import Mailer
from zhangwen_cloud_auth.models import (
    BudgetPreference,
    ChallengeResponse,
    CloudAccount,
    ProfileResponse,
    TechnicalLevel,
    TokenResponse,
    UpdateProfileRequest,
    UserPersona,
    UserProfile,
)
from zhangwen_cloud_auth.security import (
    ACCESS_LIFETIME,
    CHALLENGE_LIFETIME,
    OFFLINE_LEASE_LIFETIME,
    REFRESH_LIFETIME,
    PasswordSecurity,
    iso,
    now,
    random_token,
    secure_hash,
    verification_code,
)


class CloudAuthError(ValueError):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class CloudAuthService:
    def __init__(
        self,
        *,
        database: Database,
        mailer: Mailer,
        secret: str,
        code_generator: Callable[[], str] = verification_code,
        clock: Callable[[], datetime] = now,
    ) -> None:
        self.database = database
        self.mailer = mailer
        self.secret = secret
        self.code_generator = code_generator
        self.clock = clock
        self.passwords = PasswordSecurity()
        self.database.initialize()

    def register(
        self,
        *,
        email: str,
        display_name: str,
        password: str,
        rate_key: str,
    ) -> ChallengeResponse:
        timestamp = self.clock()
        self._check_rate_limit("REGISTER", rate_key, timestamp, limit=5)
        with self.database.transaction() as conn:
            row = self.database.row_dict(
                self.database.execute(
                    conn,
                    "SELECT * FROM cloud_accounts WHERE email = ?",
                    (email,),
                ).fetchone()
            )
            if row is not None and row["email_verified_at"] is not None:
                raise CloudAuthError(
                    "ACCOUNT_ALREADY_EXISTS",
                    "该邮箱已注册，请直接登录或重置密码。",
                    409,
                )
            password_hash = self.passwords.hash(password)
            if row is None:
                account_id = _id("acct")
                self.database.execute(
                    conn,
                    """
                    INSERT INTO cloud_accounts (
                      id, email, display_name, password_hash, email_verified_at,
                      status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, NULL, 'PENDING_VERIFICATION', ?, ?)
                    """,
                    (
                        account_id,
                        email,
                        display_name,
                        password_hash,
                        iso(timestamp),
                        iso(timestamp),
                    ),
                )
                self.database.execute(
                    conn,
                    """
                    INSERT INTO user_profiles (
                      account_id, persona, technical_level, preferred_boards_json,
                      budget_preference, needs_lesson, completed, updated_at
                    ) VALUES (?, NULL, NULL, '[]', NULL, 0, 0, ?)
                    """,
                    (account_id, iso(timestamp)),
                )
            else:
                account_id = str(row["id"])
                self.database.execute(
                    conn,
                    """
                    UPDATE cloud_accounts
                    SET display_name = ?, password_hash = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (display_name, password_hash, iso(timestamp), account_id),
                )
            challenge_id, code, expires_at = self._create_challenge(
                conn,
                account_id=account_id,
                email=email,
                purpose="VERIFY_EMAIL",
                timestamp=timestamp,
            )
            self._audit(conn, account_id, "REGISTER_REQUESTED", email, timestamp)
        self.mailer.send_code(email=email, code=code, purpose="VERIFY_EMAIL")
        return ChallengeResponse(
            challengeId=challenge_id,
            expiresAt=iso(expires_at),
            message="验证码已发送，请在 10 分钟内完成邮箱验证。",
        )

    def resend_verification(
        self,
        *,
        email: str,
        rate_key: str,
    ) -> ChallengeResponse:
        timestamp = self.clock()
        self._check_rate_limit("RESEND", rate_key, timestamp, limit=5)
        with self.database.transaction() as conn:
            account = self.database.row_dict(
                self.database.execute(
                    conn,
                    "SELECT * FROM cloud_accounts WHERE email = ?",
                    (email,),
                ).fetchone()
            )
            if account is None or account["email_verified_at"] is not None:
                raise CloudAuthError(
                    "VERIFICATION_NOT_AVAILABLE",
                    "该验证请求不可用，请重新注册或直接登录。",
                    409,
                )
            challenge_id, code, expires_at = self._create_challenge(
                conn,
                account_id=str(account["id"]),
                email=email,
                purpose="VERIFY_EMAIL",
                timestamp=timestamp,
            )
            self._audit(conn, str(account["id"]), "VERIFICATION_RESENT", email, timestamp)
        self.mailer.send_code(email=email, code=code, purpose="VERIFY_EMAIL")
        return ChallengeResponse(
            challengeId=challenge_id,
            expiresAt=iso(expires_at),
            message="新的验证码已发送。",
        )

    def verify_email(
        self,
        *,
        challenge_id: str,
        code: str,
        device_id: str,
    ) -> TokenResponse:
        timestamp = self.clock()
        with self.database.transaction() as conn:
            challenge = self._consume_challenge(
                conn,
                challenge_id=challenge_id,
                code=code,
                purpose="VERIFY_EMAIL",
                timestamp=timestamp,
            )
            account_id = str(challenge["account_id"])
            self.database.execute(
                conn,
                """
                UPDATE cloud_accounts
                SET email_verified_at = COALESCE(email_verified_at, ?),
                    status = 'ACTIVE', updated_at = ?
                WHERE id = ?
                """,
                (iso(timestamp), iso(timestamp), account_id),
            )
            response = self._issue_tokens(conn, account_id, device_id, timestamp)
            self._audit(conn, account_id, "EMAIL_VERIFIED", str(challenge["email"]), timestamp)
            return response

    def login(
        self,
        *,
        email: str,
        password: str,
        device_id: str,
        rate_key: str,
    ) -> TokenResponse:
        timestamp = self.clock()
        self._check_rate_limit("LOGIN", rate_key, timestamp, limit=10)
        with self.database.transaction() as conn:
            account = self.database.row_dict(
                self.database.execute(
                    conn,
                    "SELECT * FROM cloud_accounts WHERE email = ?",
                    (email,),
                ).fetchone()
            )
            password_hash = str(account["password_hash"]) if account else None
            if not self.passwords.verify(password_hash, password):
                raise _invalid_credentials()
            assert account is not None
            if account["email_verified_at"] is None:
                raise CloudAuthError(
                    "EMAIL_NOT_VERIFIED",
                    "请先完成邮箱验证。",
                    403,
                )
            if account["status"] != "ACTIVE":
                raise _invalid_credentials()
            response = self._issue_tokens(conn, str(account["id"]), device_id, timestamp)
            self._audit(conn, str(account["id"]), "LOGIN_SUCCEEDED", email, timestamp)
            return response

    def refresh(self, *, refresh_token: str, device_id: str) -> TokenResponse:
        timestamp = self.clock()
        token_hash = secure_hash(self.secret, "refresh", refresh_token)
        device_hash = secure_hash(self.secret, "device", device_id)
        with self.database.transaction() as conn:
            session = self.database.row_dict(
                self.database.execute(
                    conn,
                    "SELECT * FROM refresh_sessions WHERE token_hash = ?",
                    (token_hash,),
                ).fetchone()
            )
            if session is None:
                raise _invalid_refresh()
            if session["replaced_by_hash"] is not None or session["revoked_at"] is not None:
                self._revoke_family(conn, str(session["family_id"]), timestamp)
                raise CloudAuthError(
                    "REFRESH_TOKEN_REUSED",
                    "登录凭据已失效，请重新登录。",
                    401,
                )
            if _parse_time(str(session["expires_at"])) <= timestamp:
                self._revoke_family(conn, str(session["family_id"]), timestamp)
                raise _invalid_refresh()
            if not secrets.compare_digest(str(session["device_id_hash"]), device_hash):
                self._revoke_family(conn, str(session["family_id"]), timestamp)
                raise _invalid_refresh()
            next_refresh = random_token()
            next_hash = secure_hash(self.secret, "refresh", next_refresh)
            self.database.execute(
                conn,
                "UPDATE refresh_sessions SET replaced_by_hash = ?, revoked_at = ? WHERE token_hash = ?",
                (next_hash, iso(timestamp), token_hash),
            )
            self.database.execute(
                conn,
                """
                INSERT INTO refresh_sessions (
                  token_hash, family_id, account_id, device_id_hash, created_at,
                  expires_at, replaced_by_hash, revoked_at
                ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)
                """,
                (
                    next_hash,
                    str(session["family_id"]),
                    str(session["account_id"]),
                    device_hash,
                    iso(timestamp),
                    iso(timestamp + REFRESH_LIFETIME),
                ),
            )
            return self._issue_access_for_refresh(
                conn,
                account_id=str(session["account_id"]),
                family_id=str(session["family_id"]),
                refresh_token=next_refresh,
                timestamp=timestamp,
            )

    def request_password_reset(
        self,
        *,
        email: str,
        rate_key: str,
    ) -> ChallengeResponse:
        timestamp = self.clock()
        self._check_rate_limit("PASSWORD_RESET", rate_key, timestamp, limit=5)
        challenge_id = _id("challenge")
        expires_at = timestamp + CHALLENGE_LIFETIME
        code: str | None = None
        with self.database.transaction() as conn:
            account = self.database.row_dict(
                self.database.execute(
                    conn,
                    "SELECT * FROM cloud_accounts WHERE email = ? AND status = 'ACTIVE'",
                    (email,),
                ).fetchone()
            )
            if account is not None:
                challenge_id, code, expires_at = self._create_challenge(
                    conn,
                    account_id=str(account["id"]),
                    email=email,
                    purpose="PASSWORD_RESET",
                    timestamp=timestamp,
                )
                self._audit(conn, str(account["id"]), "PASSWORD_RESET_REQUESTED", email, timestamp)
            else:
                self.passwords.verify(None, "uniform-reset-timing")
        if code is not None:
            self.mailer.send_code(email=email, code=code, purpose="PASSWORD_RESET")
        return ChallengeResponse(
            challengeId=challenge_id,
            expiresAt=iso(expires_at),
            message="如果该邮箱已注册，验证码将发送到对应邮箱。",
        )

    def confirm_password_reset(
        self,
        *,
        challenge_id: str,
        code: str,
        new_password: str,
    ) -> None:
        timestamp = self.clock()
        with self.database.transaction() as conn:
            challenge = self._consume_challenge(
                conn,
                challenge_id=challenge_id,
                code=code,
                purpose="PASSWORD_RESET",
                timestamp=timestamp,
            )
            account_id = str(challenge["account_id"])
            self.database.execute(
                conn,
                "UPDATE cloud_accounts SET password_hash = ?, updated_at = ? WHERE id = ?",
                (self.passwords.hash(new_password), iso(timestamp), account_id),
            )
            self._revoke_account_sessions(conn, account_id, timestamp)
            self._audit(conn, account_id, "PASSWORD_RESET_COMPLETED", str(challenge["email"]), timestamp)

    def validate_access(self, access_token: str) -> CloudAccount:
        timestamp = self.clock()
        token_hash = secure_hash(self.secret, "access", access_token)
        with self.database.transaction() as conn:
            row = self.database.row_dict(
                self.database.execute(
                    conn,
                    """
                    SELECT a.* FROM access_sessions s
                    JOIN cloud_accounts a ON a.id = s.account_id
                    WHERE s.token_hash = ? AND s.revoked_at IS NULL
                    """,
                    (token_hash,),
                ).fetchone()
            )
            session = self.database.row_dict(
                self.database.execute(
                    conn,
                    "SELECT expires_at FROM access_sessions WHERE token_hash = ?",
                    (token_hash,),
                ).fetchone()
            )
            if row is None or session is None or _parse_time(str(session["expires_at"])) <= timestamp:
                raise CloudAuthError("ACCESS_TOKEN_INVALID", "登录已失效，请重新登录。", 401)
            return _account(row)

    def logout(self, *, account_id: str, refresh_token: str | None) -> None:
        timestamp = self.clock()
        with self.database.transaction() as conn:
            if refresh_token:
                token_hash = secure_hash(self.secret, "refresh", refresh_token)
                row = self.database.row_dict(
                    self.database.execute(
                        conn,
                        "SELECT family_id FROM refresh_sessions WHERE token_hash = ? AND account_id = ?",
                        (token_hash, account_id),
                    ).fetchone()
                )
                if row is not None:
                    self._revoke_family(conn, str(row["family_id"]), timestamp)
            else:
                self._revoke_account_sessions(conn, account_id, timestamp)

    def get_profile(self, account_id: str) -> ProfileResponse:
        with self.database.transaction() as conn:
            account_row = self.database.row_dict(
                self.database.execute(conn, "SELECT * FROM cloud_accounts WHERE id = ?", (account_id,)).fetchone()
            )
            profile_row = self.database.row_dict(
                self.database.execute(conn, "SELECT * FROM user_profiles WHERE account_id = ?", (account_id,)).fetchone()
            )
            if account_row is None or profile_row is None:
                raise CloudAuthError("ACCOUNT_NOT_FOUND", "账号不存在。", 404)
            return ProfileResponse(account=_account(account_row), profile=_profile(profile_row))

    def update_profile(self, account_id: str, request: UpdateProfileRequest) -> ProfileResponse:
        timestamp = self.clock()
        completed = bool(
            request.persona
            and request.technicalLevel
            and request.budgetPreference
        )
        with self.database.transaction() as conn:
            self.database.execute(
                conn,
                """
                UPDATE user_profiles
                SET persona = ?, technical_level = ?, preferred_boards_json = ?,
                    budget_preference = ?, needs_lesson = ?, completed = ?, updated_at = ?
                WHERE account_id = ?
                """,
                (
                    request.persona.value if request.persona else None,
                    request.technicalLevel.value if request.technicalLevel else None,
                    json.dumps(request.preferredBoards, ensure_ascii=False),
                    request.budgetPreference.value if request.budgetPreference else None,
                    int(request.needsLesson),
                    int(completed),
                    iso(timestamp),
                    account_id,
                ),
            )
        return self.get_profile(account_id)

    def _issue_tokens(self, conn, account_id: str, device_id: str, timestamp: datetime) -> TokenResponse:
        refresh_token = random_token()
        refresh_hash = secure_hash(self.secret, "refresh", refresh_token)
        family_id = _id("family")
        self.database.execute(
            conn,
            """
            INSERT INTO refresh_sessions (
              token_hash, family_id, account_id, device_id_hash, created_at,
              expires_at, replaced_by_hash, revoked_at
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)
            """,
            (
                refresh_hash,
                family_id,
                account_id,
                secure_hash(self.secret, "device", device_id),
                iso(timestamp),
                iso(timestamp + REFRESH_LIFETIME),
            ),
        )
        return self._issue_access_for_refresh(
            conn,
            account_id=account_id,
            family_id=family_id,
            refresh_token=refresh_token,
            timestamp=timestamp,
        )

    def _issue_access_for_refresh(
        self,
        conn,
        *,
        account_id: str,
        family_id: str,
        refresh_token: str,
        timestamp: datetime,
    ) -> TokenResponse:
        access_token = random_token()
        self.database.execute(
            conn,
            """
            INSERT INTO access_sessions (
              token_hash, account_id, refresh_family_id, created_at, expires_at, revoked_at
            ) VALUES (?, ?, ?, ?, ?, NULL)
            """,
            (
                secure_hash(self.secret, "access", access_token),
                account_id,
                family_id,
                iso(timestamp),
                iso(timestamp + ACCESS_LIFETIME),
            ),
        )
        account_row = self.database.row_dict(
            self.database.execute(conn, "SELECT * FROM cloud_accounts WHERE id = ?", (account_id,)).fetchone()
        )
        if account_row is None:
            raise CloudAuthError("ACCOUNT_NOT_FOUND", "账号不存在。", 404)
        return TokenResponse(
            account=_account(account_row),
            accessToken=access_token,
            accessExpiresAt=iso(timestamp + ACCESS_LIFETIME),
            refreshToken=refresh_token,
            refreshExpiresAt=iso(timestamp + REFRESH_LIFETIME),
            offlineLeaseExpiresAt=iso(timestamp + OFFLINE_LEASE_LIFETIME),
        )

    def _create_challenge(
        self,
        conn,
        *,
        account_id: str,
        email: str,
        purpose: str,
        timestamp: datetime,
    ) -> tuple[str, str, datetime]:
        challenge_id = _id("challenge")
        code = self.code_generator()
        expires_at = timestamp + CHALLENGE_LIFETIME
        self.database.execute(
            conn,
            """
            UPDATE email_challenges SET consumed_at = ?
            WHERE account_id = ? AND purpose = ? AND consumed_at IS NULL
            """,
            (iso(timestamp), account_id, purpose),
        )
        self.database.execute(
            conn,
            """
            INSERT INTO email_challenges (
              id, account_id, email, purpose, code_hash, created_at, expires_at, consumed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                challenge_id,
                account_id,
                email,
                purpose,
                secure_hash(self.secret, f"challenge:{challenge_id}", code),
                iso(timestamp),
                iso(expires_at),
            ),
        )
        return challenge_id, code, expires_at

    def _consume_challenge(
        self,
        conn,
        *,
        challenge_id: str,
        code: str,
        purpose: str,
        timestamp: datetime,
    ) -> dict:
        row = self.database.row_dict(
            self.database.execute(
                conn,
                "SELECT * FROM email_challenges WHERE id = ? AND purpose = ?",
                (challenge_id, purpose),
            ).fetchone()
        )
        expected = secure_hash(self.secret, f"challenge:{challenge_id}", code)
        valid_hash = row is not None and secrets.compare_digest(str(row["code_hash"]), expected)
        if (
            row is None
            or not valid_hash
            or row["consumed_at"] is not None
            or _parse_time(str(row["expires_at"])) <= timestamp
        ):
            raise CloudAuthError("CHALLENGE_INVALID", "验证码无效或已过期。", 422)
        self.database.execute(
            conn,
            "UPDATE email_challenges SET consumed_at = ? WHERE id = ? AND consumed_at IS NULL",
            (iso(timestamp), challenge_id),
        )
        return row

    def _check_rate_limit(
        self,
        action: str,
        rate_key: str,
        timestamp: datetime,
        *,
        limit: int,
    ) -> None:
        key_hash = secure_hash(self.secret, "rate", rate_key)
        cutoff = timestamp - timedelta(minutes=10)
        with self.database.transaction() as conn:
            self.database.execute(conn, "DELETE FROM auth_attempts WHERE attempted_at < ?", (iso(cutoff),))
            row = self.database.execute(
                conn,
                "SELECT COUNT(*) AS count FROM auth_attempts WHERE action = ? AND key_hash = ? AND attempted_at >= ?",
                (action, key_hash, iso(cutoff)),
            ).fetchone()
            count = int(dict(row)["count"])
            if count >= limit:
                raise CloudAuthError("AUTH_RATE_LIMITED", "请求过于频繁，请稍后再试。", 429)
            self.database.execute(
                conn,
                "INSERT INTO auth_attempts (id, action, key_hash, attempted_at) VALUES (?, ?, ?, ?)",
                (_id("attempt"), action, key_hash, iso(timestamp)),
            )

    def _audit(self, conn, account_id: str | None, event_type: str, subject: str, timestamp: datetime) -> None:
        self.database.execute(
            conn,
            "INSERT INTO auth_audit_events (id, account_id, event_type, subject_hash, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                _id("audit"),
                account_id,
                event_type,
                secure_hash(self.secret, "audit-subject", subject),
                iso(timestamp),
            ),
        )

    def _revoke_family(self, conn, family_id: str, timestamp: datetime) -> None:
        self.database.execute(
            conn,
            "UPDATE refresh_sessions SET revoked_at = COALESCE(revoked_at, ?) WHERE family_id = ?",
            (iso(timestamp), family_id),
        )
        self.database.execute(
            conn,
            "UPDATE access_sessions SET revoked_at = COALESCE(revoked_at, ?) WHERE refresh_family_id = ?",
            (iso(timestamp), family_id),
        )

    def _revoke_account_sessions(self, conn, account_id: str, timestamp: datetime) -> None:
        families = self.database.execute(
            conn,
            "SELECT DISTINCT family_id FROM refresh_sessions WHERE account_id = ?",
            (account_id,),
        ).fetchall()
        for row in families:
            self._revoke_family(conn, str(dict(row)["family_id"]), timestamp)


def _account(row: dict) -> CloudAccount:
    return CloudAccount(
        id=str(row["id"]),
        email=str(row["email"]),
        displayName=str(row["display_name"]),
        emailVerified=row["email_verified_at"] is not None,
        createdAt=str(row["created_at"]),
    )


def _profile(row: dict) -> UserProfile:
    return UserProfile(
        persona=UserPersona(row["persona"]) if row["persona"] else None,
        technicalLevel=TechnicalLevel(row["technical_level"]) if row["technical_level"] else None,
        preferredBoards=json.loads(str(row["preferred_boards_json"])),
        budgetPreference=BudgetPreference(row["budget_preference"]) if row["budget_preference"] else None,
        needsLesson=bool(row["needs_lesson"]),
        completed=bool(row["completed"]),
    )


def _invalid_credentials() -> CloudAuthError:
    return CloudAuthError("AUTH_CREDENTIALS_INVALID", "邮箱或密码不正确。", 401)


def _invalid_refresh() -> CloudAuthError:
    return CloudAuthError("REFRESH_TOKEN_INVALID", "登录凭据已失效，请重新登录。", 401)


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"
