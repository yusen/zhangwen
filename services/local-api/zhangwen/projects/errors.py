"""Project persistence errors."""

from __future__ import annotations


class ProjectError(Exception):
    code = "PROJECT_ERROR"
    status_code = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ProjectNotFoundError(ProjectError):
    code = "PROJECT_NOT_FOUND"
    status_code = 404


class ProjectArchivedError(ProjectError):
    code = "PROJECT_ARCHIVED"
    status_code = 409


class ProjectValidationError(ProjectError):
    code = "PROJECT_VALIDATION_FAILED"
    status_code = 422


class ConversationContextError(ProjectError):
    status_code = 409

    def __init__(self, code: str, message: str, *, status_code: int = 409) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class UnsupportedProjectSchemaError(ProjectError):
    code = "PROJECT_SCHEMA_UNSUPPORTED"
    status_code = 409


class ProjectDatabaseCorruptError(ProjectError):
    code = "PROJECT_DATABASE_CORRUPT"
    status_code = 500
