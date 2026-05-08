from __future__ import annotations

from http import HTTPStatus
from typing import Any


class AppError(Exception):
    """Base application exception."""

    status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR
    error_code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred"

    def __init__(
        self,
        message: str | None = None,
        *,
        detail: Any | None = None,
        error_code: str | None = None,
    ) -> None:
        self.message = message or self.__class__.message
        self.detail = detail
        if error_code:
            self.error_code = error_code
        super().__init__(self.message)


class AuthenticationError(AppError):
    status_code = HTTPStatus.UNAUTHORIZED
    error_code = "AUTHENTICATION_FAILED"
    message = "Authentication failed"


class AuthorizationError(AppError):
    status_code = HTTPStatus.FORBIDDEN
    error_code = "AUTHORIZATION_FAILED"
    message = "Insufficient permissions"


class NotFoundError(AppError):
    status_code = HTTPStatus.NOT_FOUND
    error_code = "NOT_FOUND"
    message = "Resource not found"


class ConflictError(AppError):
    status_code = HTTPStatus.CONFLICT
    error_code = "CONFLICT"
    message = "Resource already exists"


class ValidationError(AppError):
    status_code = HTTPStatus.UNPROCESSABLE_ENTITY
    error_code = "VALIDATION_ERROR"
    message = "Validation failed"


class RateLimitError(AppError):
    status_code = HTTPStatus.TOO_MANY_REQUESTS
    error_code = "RATE_LIMIT_EXCEEDED"
    message = "Rate limit exceeded"

    def __init__(self, retry_after: int = 60) -> None:
        super().__init__()
        self.retry_after = retry_after


class IdempotencyConflictError(AppError):
    status_code = HTTPStatus.CONFLICT
    error_code = "IDEMPOTENCY_CONFLICT"
    message = "Idempotency key conflict: a different in-flight request is using this key"


class CircuitOpenError(AppError):
    status_code = HTTPStatus.SERVICE_UNAVAILABLE
    error_code = "CIRCUIT_OPEN"
    message = "Downstream service is temporarily unavailable"


class ExternalServiceError(AppError):
    status_code = HTTPStatus.BAD_GATEWAY
    error_code = "EXTERNAL_SERVICE_ERROR"
    message = "External service returned an error"
