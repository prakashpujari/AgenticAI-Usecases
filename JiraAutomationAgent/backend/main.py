"""
FastAPI application entry point.

Endpoints:
  POST /ai/create-ticket  — multi-agent ticket creation flow
  POST /ai/review-ticket  — ticket review / coaching flow
  GET  /health            — service health check
"""
from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings
from .schemas.api_schema import (
    CreateTicketRequest,
    HealthResponse,
    RecentTicketsResponse,
    ReviewTicketRequest,
    TicketResponse,
)
from .graph.workflow import workflow
from .graph.state import JiraAgentState
from .services.redis_service import redis_service
from .services.pinecone_service import pinecone_service
from .services.jira_service import jira_service

# ── Logging ───────────────────────────────────────────────────────────────────
# Production → JSON lines (one dict per log entry, easy to ingest into
# Datadog / CloudWatch / Splunk).  Development → human-readable.
if settings.environment == "production":
    class _JsonFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            log: dict[str, Any] = {
                "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
                "level": record.levelname,
                "logger": record.name,
                "msg": record.getMessage(),
            }
            if record.exc_info:
                log["exc"] = self.formatException(record.exc_info)
            return json.dumps(log)

    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(_JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[_handler], force=True)
else:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    )

logger = logging.getLogger(__name__)


# ── Security-headers middleware ───────────────────────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security-related HTTP response headers to every response."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # Prevent MIME sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Block framing (clickjacking)
        response.headers["X-Frame-Options"] = "DENY"
        # Force HTTPS in production
        if settings.environment == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        # Minimal referrer leakage
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Restrict browser features
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response


# ── Request-size-limit middleware ─────────────────────────────────────────────
class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Rejects requests whose body exceeds settings.max_body_size."""

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > settings.max_body_size:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"detail": "Request body too large."},
            )
        return await call_next(request)


# ── Simple in-process rate limiter ────────────────────────────────────────────
# Uses a token-bucket per IP stored in a plain dict.
# For multi-worker deployments, replace this with Redis-backed rate limiting.
import collections
import threading

_rate_lock = threading.Lock()
_rate_buckets: dict[str, list[float]] = collections.defaultdict(list)


def _is_rate_limited(ip: str, limit: int, window: int = 60) -> bool:
    now = time.monotonic()
    with _rate_lock:
        bucket = _rate_buckets[ip]
        # Remove timestamps older than the window
        _rate_buckets[ip] = [t for t in bucket if now - t < window]
        if len(_rate_buckets[ip]) >= limit:
            return True
        _rate_buckets[ip].append(now)
    return False


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Jira AI Automation Agent starting …  environment=%s", settings.environment)
    yield
    logger.info("Shutting down …")
    await redis_service.close()


# ── App factory ───────────────────────────────────────────────────────────────
_is_prod = settings.environment == "production"

app = FastAPI(
    title="Jira AI Automation Agent",
    description=(
        "AI-powered Jira ticket creation, review, and coaching "
        "using LangGraph multi-agent orchestration."
    ),
    version="1.0.0",
    lifespan=lifespan,
    # Disable interactive docs in production — they expose your schema and
    # can be used to probe the API. Re-enable behind auth if needed.
    docs_url=None if _is_prod else "/docs",
    redoc_url=None if _is_prod else "/redoc",
    openapi_url=None if _is_prod else "/openapi.json",
)

# Order matters: CORS must be first so pre-flight OPTIONS requests are handled
# before any other middleware inspects them.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,   # read from CORS_ORIGINS env var
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)


# ── Global exception handler ──────────────────────────────────────────────────
@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled error: %s", exc, exc_info=True)
    # In development, return actual error for debugging
    error_detail = str(exc) if settings.environment != "production" else "Internal server error. Please check server logs."
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": error_detail},
    )


# ── Helpers ───────────────────────────────────────────────────────────────────
def _build_state(
    *,
    raw_input: str,
    allowed_projects: list[str],
    allowed_components: list[str],
    user_role: str,
    user_id: str,
    mode: str = "create",
    jira_key: str | None = None,
    create_in_jira: bool = False,
) -> JiraAgentState:
    # All fields must be explicitly initialised here because LangGraph reads
    # the typed dict at graph entry and expects every key to be present.
    # Missing keys would cause KeyError exceptions inside node functions.
    return JiraAgentState(
        raw_input=raw_input,
        jira_key=jira_key,
        mode=mode,                          # controls which LLM prompts are selected
        allowed_projects=allowed_projects,  # RBAC: LLM is constrained to these keys
        allowed_components=allowed_components,
        user_role=user_role,                # RBAC: affects prompt tone and permissions
        user_id=user_id,                    # for audit logging
        # Pre-processing fields start empty; nodes fill them in order.
        normalized_input="",
        redacted_input="",
        pii_detected=[],
        rbac_violations=[],
        rbac_context="",
        dedupe_matches=[],
        retrieved_context=[],
        formatted_context="",
        ticket_drafts=[],
        review_result={},
        explainer_output={},
        validation_errors=[],
        is_valid=False,
        # Explicit opt-in: callers must set True to persist tickets to Jira.
        create_in_jira=create_in_jira,
        created_issues=[],
        iteration_count=0,
        max_iterations=settings.max_review_iterations,
        error=None,
        trace_id=str(uuid.uuid4()),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@app.post(
    "/ai/create-ticket",
    response_model=TicketResponse,
    summary="Create Jira ticket(s) from unstructured input",
)
async def create_ticket(request: CreateTicketRequest, http_request: Request) -> TicketResponse:
    """
    Accepts raw unstructured input (complaints, support tickets, notes),
    runs the multi-agent LangGraph flow, and returns generated ticket drafts,
    review, coaching, and optionally created Jira issues.
    """
    client_ip = http_request.client.host if http_request.client else "unknown"
    if _is_rate_limited(client_ip, settings.api_rate_limit):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Max {settings.api_rate_limit} requests/minute.",
            headers={"Retry-After": "60"},
        )

    logger.info(
        "[create-ticket] user=%s projects=%s ip=%s",
        request.user_id, request.allowed_projects, client_ip,
    )

    initial_state = _build_state(
        raw_input=request.raw_input,
        allowed_projects=request.allowed_projects,
        allowed_components=request.allowed_components,
        user_role=request.user_role,
        user_id=request.user_id,
        mode="create",
        create_in_jira=request.create_in_jira,
    )

    final_state: JiraAgentState = await workflow.ainvoke(initial_state)

    return TicketResponse(
        ticket_drafts=final_state.get("ticket_drafts", []),
        ai_review=final_state.get("review_result") or None,
        how_to_create_explainer=final_state.get("explainer_output") or None,
        created_issues=final_state.get("created_issues", []),
        dedupe_matches=final_state.get("dedupe_matches", []),
        retrieved_context=final_state.get("retrieved_context", []),
        trace_id=final_state.get("trace_id"),
    )


@app.post(
    "/ai/review-ticket",
    response_model=TicketResponse,
    summary="Review an existing ticket for quality improvements",
)
async def review_ticket(request: ReviewTicketRequest, http_request: Request) -> TicketResponse:
    """
    Reviews an existing Jira ticket (by key or pasted content) and returns
    an AI quality review plus PO coaching guidance.
    """
    client_ip = http_request.client.host if http_request.client else "unknown"
    if _is_rate_limited(client_ip, settings.api_rate_limit):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Max {settings.api_rate_limit} requests/minute.",
            headers={"Retry-After": "60"},
        )

    logger.info(
        "[review-ticket] user=%s key=%s ip=%s", request.user_id, request.jira_key, client_ip,
    )

    if not request.jira_key and not request.ticket_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            # Both fields are optional individually, but at least one
            # must be provided so the pipeline has something to review.
            detail="Provide either jira_key or ticket_content.",
        )

    # When a Jira key is given without pasted content, synthesise a prompt
    # that tells the pipeline to fetch and review that specific ticket.
    raw_input = request.ticket_content or f"Review Jira ticket: {request.jira_key}"

    initial_state = _build_state(
        raw_input=raw_input,
        allowed_projects=request.allowed_projects,
        allowed_components=[],
        user_role=request.user_role,
        user_id=request.user_id,
        mode="review",
        jira_key=request.jira_key,
    )

    final_state: JiraAgentState = await workflow.ainvoke(initial_state)

    return TicketResponse(
        ticket_drafts=final_state.get("ticket_drafts", []),
        ai_review=final_state.get("review_result"),
        how_to_create_explainer=final_state.get("explainer_output"),
        created_issues=[],  # Review mode never creates issues
        dedupe_matches=final_state.get("dedupe_matches", []),
        retrieved_context=final_state.get("retrieved_context", []),
        trace_id=final_state.get("trace_id"),
    )


@app.get("/health", response_model=HealthResponse, summary="Service health check")
async def health_check() -> HealthResponse:
    """Returns the health status of all dependent services."""
    redis_ok = await redis_service.health_check()
    pinecone_ok = await pinecone_service.health_check()
    jira_ok = await jira_service.health_check()

    services = {
        "redis": "ok" if redis_ok else "degraded",
        "pinecone": "ok" if pinecone_ok else "degraded",
        "jira": "ok" if jira_ok else "degraded",
    }
    # Overall status is degraded if any single dependency is unhealthy.
    # Redis degraded is expected in local dev (no Redis running).
    overall = "ok" if all(v == "ok" for v in services.values()) else "degraded"
    return HealthResponse(status=overall, services=services)


@app.get(
    "/ai/recent-tickets",
    response_model=RecentTicketsResponse,
    summary="Fetch the 5 most recently created Jira tickets",
)
async def get_recent_tickets(
    projects: str = settings.jira_default_project,
    limit: int = 5,
) -> RecentTicketsResponse:
    """
    Returns the most recently created Jira tickets for the given project keys
    (comma-separated query param, e.g. ?projects=MC,PROJ).
    Limit is capped at 20.
    """
    project_keys = [p.strip() for p in projects.split(",") if p.strip()]
    # Enforce a hard cap so callers cannot request unbounded results
    safe_limit = min(limit, 20)
    tickets = await jira_service.get_recent_tickets(project_keys, safe_limit)
    return RecentTicketsResponse(tickets=tickets)


@app.post(
    "/ai/seed-pinecone",
    summary="Backfill existing Jira tickets into Pinecone knowledge base",
)
async def seed_pinecone(
    projects: str = settings.jira_default_project,
    limit: int = 100,
) -> dict:
    """
    Fetches up to *limit* recent Jira tickets from the given project(s) and
    upserts them into Pinecone so RAG retrieval and dedupe have historical data.

    Call this once after deploying or whenever the Pinecone index is empty.
    Existing vectors are overwritten by their Jira key, so it is safe to run
    multiple times (idempotent).
    """
    project_keys = [p.strip() for p in projects.split(",") if p.strip()]
    # Cap at 200 to avoid very long upsert runs
    safe_limit = min(limit, 200)

    logger.info("[seed-pinecone] Fetching up to %d tickets from %s", safe_limit, project_keys)
    tickets = await jira_service.get_recent_tickets(project_keys, safe_limit)

    upserted: list[str] = []
    failed: list[str] = []

    for ticket in tickets:
        jira_key = ticket.get("jira_key", "")
        if not jira_key:
            continue
        try:
            await pinecone_service.upsert_issue(
                jira_key,
                {
                    "title": ticket.get("title", ""),
                    "issue_type": ticket.get("issue_type", ""),
                    "summary": ticket.get("title", ""),  # title is the best summary we have
                    "description": "",
                    "priority": ticket.get("priority", ""),
                    "labels": ticket.get("labels", []),
                    "project_key": jira_key.split("-")[0] if "-" in jira_key else "",
                    "status": ticket.get("status", ""),
                    "url": ticket.get("url", ""),
                },
            )
            upserted.append(jira_key)
        except Exception as exc:
            logger.error("[seed-pinecone] Upsert failed for %s: %s", jira_key, exc)
            failed.append(jira_key)

    logger.info(
        "[seed-pinecone] Done: upserted=%d  failed=%d", len(upserted), len(failed)
    )
    return {
        "total_fetched": len(tickets),
        "upserted": len(upserted),
        "upserted_keys": upserted,
        "failed": len(failed),
        "failed_keys": failed,
    }

