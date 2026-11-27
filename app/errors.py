"""Business errors mapped onto the unified envelope."""

from __future__ import annotations


class AppError(Exception):
    status_code = 400
    code = 40000
    message = "BAD_REQUEST"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message


class UnauthorizedError(AppError):
    status_code = 401
    code = 40101
    message = "UNAUTHORIZED"


class ForbiddenError(AppError):
    status_code = 403
    code = 40301
    message = "PERMISSION_DENIED"


class ValidationError(AppError):
    status_code = 422
    code = 42200
    message = "VALIDATION_ERROR"


class FieldListEmptyError(AppError):
    status_code = 422
    code = 42201
    message = "FIELD_LIST_EMPTY"


class CaliberUnavailableError(AppError):
    status_code = 503
    code = 50301
    message = "CALIBER_UNAVAILABLE"
