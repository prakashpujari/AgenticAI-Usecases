from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.config import get_settings
from app.core.logging_config import get_logger

settings = get_settings()
logger = get_logger(__name__)

_SENSITIVE_HEADERS = frozenset({"authorization", "cookie", "set-cookie"})
_SENSITIVE_FIELDS = frozenset({"password", "ssn", "social_security_number", "secret"})


# ── Correlation ID ────────────────────────────────────────────────────────────


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Inject a correlation_id into every request context and response header."""

    HEADER = "X-Correlation-ID"

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        correlation_id = request.headers.get(self.HEADER, str(uuid.uuid4()))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            correlation_id=correlation_id,
            request_id=str(uuid.uuid4()),
        )
        response = await call_next(request)
        response.headers[self.HEADER] = correlation_id
        return response


# ── Request / Response logging ────────────────────────────────────────────────


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log structured request/response pairs without leaking sensitive data."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.perf_counter()
        log = logger.bind(
            method=request.method,
            path=request.url.path,
            client=request.client.host if request.client else "unknown",
        )
        log.info("request_started")

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        log.info(
            "request_finished",
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response


# ── Security headers ──────────────────────────────────────────────────────────


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security-related HTTP response headers."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers.update(
            {
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "X-XSS-Protection": "1; mode=block",
                "Referrer-Policy": "strict-origin-when-cross-origin",
                "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
                "Cache-Control": "no-store",
            }
        )
        if settings.environment == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )
        return response
