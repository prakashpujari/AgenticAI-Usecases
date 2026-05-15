"""
api/middleware/request_id.py
─────────────────────────────
Attaches a unique request_id to every request and echoes it in the response
header so the client can correlate frontend errors with backend logs.

Priority:
  1. Use X-Request-Id header supplied by the client (useful for tracing).
  2. Generate a new UUID4 if the header is absent.
"""

import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response
