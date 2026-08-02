from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{3,32}$")


class AuthAccount(BaseModel):
    id: str
    username: str
    displayName: str
    createdAt: str


class UserPersona(StrEnum):
    TEACHER = "TEACHER"
    STUDENT = "STUDENT"
    ENGINEER = "ENGINEER"
    MAKER = "MAKER"
    OTHER = "OTHER"


class TechnicalLevel(StrEnum):
    BEGINNER = "BEGINNER"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"


class BudgetPreference(StrEnum):
    ECONOMY = "ECONOMY"
    BALANCED = "BALANCED"
    PERFORMANCE = "PERFORMANCE"


class EmailAccount(BaseModel):
    id: str
    email: str
    displayName: str
    emailVerified: bool
    createdAt: str


class AccountProfile(BaseModel):
    persona: UserPersona | None = None
    technicalLevel: TechnicalLevel | None = None
    preferredBoards: list[str] = Field(default_factory=list, max_length=12)
    budgetPreference: BudgetPreference | None = None
    needsLesson: bool = False
    completed: bool = False


class RegisterEmailAccountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=5, max_length=255)
    displayName: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=10, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class VerifyEmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    challengeId: str = Field(min_length=16, max_length=128)
    code: str = Field(pattern=r"^\d{6}$")


class EmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=1, max_length=255)

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class EmailLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class PasswordResetConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    challengeId: str = Field(min_length=16, max_length=128)
    code: str = Field(pattern=r"^\d{6}$")
    newPassword: str = Field(min_length=10, max_length=128)


class VerificationChallengeResponse(BaseModel):
    challengeId: str
    expiresAt: str
    message: str


class EmailAuthResultResponse(BaseModel):
    account: EmailAccount
    profile: AccountProfile
    sessionToken: str
    expiresAt: str
    offlineLeaseExpiresAt: str


class AccountProfileResponse(BaseModel):
    account: EmailAccount
    profile: AccountProfile


class UpdateAccountProfileRequest(AccountProfile):
    model_config = ConfigDict(extra="forbid")


class AcceptedResponse(BaseModel):
    accepted: bool = True
    message: str


class AuthStatusResponse(BaseModel):
    hasAccounts: bool
    hasLocalAccounts: bool
    cloudAuthConfigured: bool


class RegisterAccountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=32)
    displayName: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username", "displayName", mode="before")
    @classmethod
    def _strip_identity_fields(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("username")
    @classmethod
    def _validate_username(cls, value: str) -> str:
        if USERNAME_PATTERN.fullmatch(value) is None:
            raise ValueError("用户名只能包含字母、数字、点、下划线或短横线。")
        return value.lower()

    @field_validator("password")
    @classmethod
    def _validate_password(cls, value: str) -> str:
        if not any(character.isascii() and character.isalpha() for character in value):
            raise ValueError("密码至少需要一个字母。")
        if not any(character.isascii() and character.isdigit() for character in value):
            raise ValueError("密码至少需要一个数字。")
        return value


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("username", mode="before")
    @classmethod
    def _strip_username(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("username")
    @classmethod
    def _normalize_username(cls, value: str) -> str:
        return value.lower()


class AuthResultResponse(BaseModel):
    account: AuthAccount
    sessionToken: str
    expiresAt: str


class AuthSessionResponse(BaseModel):
    account: AuthAccount
    expiresAt: str


class LogoutResponse(BaseModel):
    loggedOut: bool = True


class AuthSession(BaseModel):
    account: AuthAccount
    tokenHash: str
    expiresAt: str
