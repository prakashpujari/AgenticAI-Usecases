"""
api/middleware/body_size.py
────────────────────────────
Rejects requests whose Content-Length header exceeds MAX_BODY_BYTES before
FastAPI even begins parsing the body. Prevents memory exhaustion from large
uploads that bypass multipart field-level limits.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

MAX_BODY_BYTES = 50 * 1024 * 1024  # 50 MB


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_bytes: int = MAX_BODY_BYTES):
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self.max_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error_code": "FILE_TOO_LARGE",
                            "message": f"Request body exceeds {self.max_bytes // (1024*1024)} MB limit.",
                            "retry_after_seconds": None,
                            "debug_id": None,
                        },
                    )
            except ValueError:
                pass
        return await call_next(request)
