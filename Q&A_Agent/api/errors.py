"""
api/errors.py
─────────────
Centralised error codes, structured error responses, and the api_error()
factory used by every FastAPI endpoint.

All client-facing errors conform to ErrorResponse so the frontend can map
error_code → friendly message without parsing raw exception text.
"""

import uuid
import logging
from fastapi import HTTPException

logger = logging.getLogger("qa_agent.api")

# ── Stable error code registry ────────────────────────────────────────────────
class E:
    RATE_LIMIT_EXCEEDED    = "RATE_LIMIT_EXCEEDED"
    SPIKE_ARREST           = "SPIKE_ARREST"
    GLOBAL_CAPACITY        = "GLOBAL_CAPACITY"
    FILE_TOO_LARGE         = "FILE_TOO_LARGE"
    INVALID_FILE_TYPE      = "INVALID_FILE_TYPE"
    INVALID_URL            = "INVALID_URL"
    SSRF_BLOCKED           = "SSRF_BLOCKED"
    INVALID_YOUTUBE_URL    = "INVALID_YOUTUBE_URL"
    YOUTUBE_UNAVAILABLE    = "YOUTUBE_UNAVAILABLE"
    WAF_BLOCKED            = "WAF_BLOCKED"
    LLM_UNAVAILABLE        = "LLM_UNAVAILABLE"
    PIPELINE_FAILED        = "PIPELINE_FAILED"
    SERVER_MISCONFIGURATION = "SERVER_MISCONFIGURATION"
    JOB_NOT_FOUND          = "JOB_NOT_FOUND"
    INVALID_PARAM          = "INVALID_PARAM"


def api_error(
    status: int,
    error_code: str,
    message: str,
    retry_after: int | None = None,
    request_id: str | None = None,
) -> HTTPException:
    """
    Build and raise a structured HTTPException.

    Every error response body has the shape:
        {
            "error_code":           str,
            "message":              str,
            "retry_after_seconds":  int | null,
            "debug_id":             str   # UUID — correlate with server logs
        }
    """
    debug_id = str(uuid.uuid4())
    logger.error(
        "API error: %s — %s",
        error_code,
        message,
        extra={
            "error_code": error_code,
            "debug_id":   debug_id,
            "http_status": status,
            "request_id": request_id,
        },
    )
    raise HTTPException(
        status_code=status,
        detail={
            "error_code":          error_code,
            "message":             message,
            "retry_after_seconds": retry_after,
            "debug_id":            debug_id,
        },
    )
