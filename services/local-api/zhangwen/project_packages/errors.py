"""Project package domain errors."""

from __future__ import annotations


class ProjectPackageError(Exception):
    code = "PROJECT_PACKAGE_ERROR"
    status_code = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ProjectPackageInvalidError(ProjectPackageError):
    code = "PROJECT_PACKAGE_INVALID"
    status_code = 422


class ProjectPackagePrivacyBlockedError(ProjectPackageError):
    code = "PROJECT_PACKAGE_PRIVACY_BLOCKED"
    status_code = 422


class ProjectPackageUnsafeZipError(ProjectPackageError):
    code = "PROJECT_PACKAGE_UNSAFE_ZIP"
    status_code = 422


class ProjectPackageConflictError(ProjectPackageError):
    code = "PROJECT_PACKAGE_CONFLICT"
    status_code = 409

