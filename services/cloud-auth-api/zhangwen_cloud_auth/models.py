from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


EMAIL_PATTERN = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,}$")


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


class CloudAccount(BaseModel):
    id: str
    email: str
    displayName: str
    emailVerified: bool
    createdAt: str


class UserProfile(BaseModel):
    persona: UserPersona | None = None
    technicalLevel: TechnicalLevel | None = None
    preferredBoards: list[str] = Field(default_factory=list, max_length=12)
    budgetPreference: BudgetPreference | None = None
    needsLesson: bool = False
    completed: bool = False


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=5, max_length=255)
    displayName: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=10, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if EMAIL_PATTERN.fullmatch(normalized) is None:
            raise ValueError("请输入有效的邮箱地址。")
        return normalized

    @field_validator("displayName")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not any(character.isalpha() for character in value):
            raise ValueError("密码至少需要一个字母。")
        if not any(character.isdigit() for character in value):
            raise ValueError("密码至少需要一个数字。")
        return value


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=128)
    deviceId: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class ChallengeResponse(BaseModel):
    challengeId: str
    expiresAt: str
    message: str


class VerifyEmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    challengeId: str = Field(min_length=16, max_length=128)
    code: str = Field(pattern=r"^\d{6}$")
    deviceId: str = Field(min_length=8, max_length=128)


class ResendVerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=1, max_length=255)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class PasswordResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=1, max_length=255)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class PasswordResetConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    challengeId: str = Field(min_length=16, max_length=128)
    code: str = Field(pattern=r"^\d{6}$")
    newPassword: str = Field(min_length=10, max_length=128)

    @field_validator("newPassword")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return RegisterRequest.validate_password(value)


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refreshToken: str = Field(min_length=32, max_length=512)
    deviceId: str = Field(min_length=8, max_length=128)


class LogoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refreshToken: str | None = Field(default=None, min_length=32, max_length=512)


class TokenResponse(BaseModel):
    account: CloudAccount
    accessToken: str
    accessExpiresAt: str
    refreshToken: str
    refreshExpiresAt: str
    offlineLeaseExpiresAt: str


class ProfileResponse(BaseModel):
    account: CloudAccount
    profile: UserProfile


class UpdateProfileRequest(UserProfile):
    model_config = ConfigDict(extra="forbid")


class AcceptedResponse(BaseModel):
    accepted: bool = True
    message: str
