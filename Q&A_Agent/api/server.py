"""
api/server.py
─────────────
Production-grade FastAPI gateway for the Q&A Agent pipeline.

Security & reliability features:
  • RequestIdMiddleware     — unique request_id on every request/response
  • BodySizeLimitMiddleware — 50 MB cap before body parsing
  • CORS locked to Vercel domain + localhost
  • Sliding-window rate limit: 10 req/hr per identity (Redis-backed)
  • Token-bucket spike arrest: 3 req/sec per identity
  • WAF-style input validation (SSRF, XSS, SQLi patterns)
  • Structured error responses (error_code, message, debug_id)
  • LLM retry + fallback (primary → fallback model)
  • PostgreSQL job persistence (SQLite fallback)
  • Redis response cache — skip full pipeline on repeated content
  • Dashboard API — stats, recent jobs, stage timings from PostgreSQL
"""

import logging
import math
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from queue import Empty, Queue
from typing import Any

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

import config
from observability import setup_logging, PipelineMetrics, setup_langsmith
from observability.logger import get_logger
from api.errors import E, api_error
from api.middleware import RequestIdMiddleware, BodySizeLimitMiddleware
from api.middleware import validate_url, validate_youtube_url, waf_scan, validate_file
from api.middleware.rate_limit import (
    extract_identity,
    check_spike_arrest,
    check_rate_limit,
    add_rate_limit_headers,
    RATE_LIMIT_MAX,
    RATE_LIMIT_WINDOW,
)
from api.database import (
    init_db, save_job, get_job, update_job,
    save_stage_timing, get_dashboard_stats, get_recent_jobs,
    save_review, get_reviews, get_review_stats,
)
from api.cache import make_cache_key, get_cached, set_cached

# ── Setup ─────────────────────────────────────────────────────────────────────
setup_logging()
_langsmith_active = setup_langsmith()
logger = get_logger("qa_agent.api")

API_VERSION     = "1.0.0"
API_DIR         = Path(__file__).parent
TEMP_UPLOAD_DIR = API_DIR / "uploads"
TEMP_UPLOAD_DIR.mkdir(exist_ok=True)

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Q&A Agent API",
    description="Generate MCQ questions from any document using AI.\n\n*Powered by PrakashPujariAI*",
    version=API_VERSION,
    contact={"name": "PrakashPujariAI"},
)

# ── Middleware (order matters — outermost runs first) ─────────────────────────
app.add_middleware(RequestIdMiddleware)
app.add_middleware(BodySizeLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://frontend-six-red-29.vercel.app",
        "https://*.vercel.app",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-Device-Fingerprint", "X-Request-Id"],
)

# ── Coarse slowapi limiter (docs/health endpoints, not pipeline) ──────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Structured error handler for HTTPException ────────────────────────────────
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict):
        return JSONResponse(status_code=exc.status_code, content=detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": "HTTP_ERROR",
            "message": str(detail),
            "retry_after_seconds": None,
            "debug_id": str(uuid.uuid4()),
        },
    )

# ── Request Queue ─────────────────────────────────────────────────────────────
_job_queue: Queue = Queue()
_jobs_db: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()


# ── Database setup (simple SQLite) ────────────────────────────────────────────
def _init_db() -> None:
    """Initialize SQLite database for job tracking."""
    db_path = API_DIR / "jobs.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            pipeline_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            input_source TEXT NOT NULL,
            output_mode TEXT NOT NULL DEFAULT 'questions',
            result_markdown TEXT,
            result_pdf_path TEXT,
            error_message TEXT,
            metrics_json TEXT
        )
        """
    )
    # Migrate existing DB: add output_mode column if it doesn't exist yet.
    try:
        cursor.execute("ALTER TABLE jobs ADD COLUMN output_mode TEXT NOT NULL DEFAULT 'questions'")
    except sqlite3.OperationalError:
        pass  # Column already exists
    conn.commit()
    conn.close()


def _save_job(job_id: str, data: dict[str, Any]) -> None:
    """Save job metadata to SQLite."""
    created_at = data.get("created_at") or datetime.now(timezone.utc).isoformat()
    updated_at = data.get("updated_at") or created_at
    db_path = API_DIR / "jobs.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO jobs
        (pipeline_id, status, created_at, updated_at, input_source, output_mode,
         result_markdown, result_pdf_path, error_message, metrics_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id,
            data.get("status"),
            created_at,
            updated_at,
            data.get("input_source"),
            data.get("output_mode", "questions"),
            data.get("result_markdown"),
            data.get("result_pdf_path"),
            data.get("error_message"),
            data.get("metrics_json"),
        ),
    )
    conn.commit()
    conn.close()


def _get_job(job_id: str) -> dict[str, Any] | None:
    """Retrieve job metadata from SQLite."""
    db_path = API_DIR / "jobs.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row  # access columns by name
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE pipeline_id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    keys = row.keys()
    return {
        "pipeline_id":     row["pipeline_id"],
        "status":          row["status"],
        "created_at":      row["created_at"],
        "updated_at":      row["updated_at"],
        "input_source":    row["input_source"],
        "output_mode":     row["output_mode"] if "output_mode" in keys else "questions",
        "result_markdown": row["result_markdown"] if "result_markdown" in keys else None,
        "result_pdf_path": row["result_pdf_path"] if "result_pdf_path" in keys else None,
        "error_message":   row["error_message"]   if "error_message"   in keys else None,
        "metrics_json":    row["metrics_json"]     if "metrics_json"    in keys else None,
    }


# ── Background Worker Thread ──────────────────────────────────────────────────
_JOB_TIMEOUT_SECONDS = 300   # 5 min hard cap per job


def _run_pipeline_with_timeout(job: dict[str, Any]) -> None:
    """
    Run _execute_pipeline in a child thread and join with a hard timeout.
    If the child hangs (e.g. LLM connection hang), we mark the job failed
    after _JOB_TIMEOUT_SECONDS and let the main worker continue.
    Python threads can't be forcibly killed; the child will eventually unblock
    once the underlying HTTP socket times out (request_timeout=30 on ChatGroq).
    """
    pipeline_id = job.get("pipeline_id", "unknown")
    result: dict = {}

    def _target():
        try:
            _execute_pipeline(job)
        except Exception as exc:       # already logged inside _execute_pipeline
            result["exc"] = exc

    child = threading.Thread(target=_target, name=f"pipeline-{pipeline_id}", daemon=True)
    child.start()
    child.join(timeout=_JOB_TIMEOUT_SECONDS)

    if child.is_alive():
        msg = f"Pipeline timed out after {_JOB_TIMEOUT_SECONDS}s — forced abort"
        logger.error("Job %s: %s", pipeline_id, msg)
        _update_job_status(pipeline_id, "failed", error_message=msg)
        try:
            update_job(pipeline_id, status="failed", error_message=msg)
        except Exception:
            pass


def _process_job_queue() -> None:
    """Worker thread — processes jobs sequentially, each with a hard timeout."""
    while True:
        try:
            job = _job_queue.get(timeout=1)
            if job is None:
                break  # Sentinel: stop the worker
            _run_pipeline_with_timeout(job)
        except Empty:
            continue
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected worker error: %s", exc)
            time.sleep(1)


def _execute_pipeline(job: dict[str, Any]) -> None:
    """
    Execute the Q&A pipeline for a single job.

    Flow:
      1. Check Redis cache — if HIT, return cached markdown immediately.
      2. Mark job processing in both SQLite and PostgreSQL.
      3. Run LangGraph pipeline.
      4. Store result in Redis cache + PostgreSQL.
      5. Write per-stage timings to PostgreSQL for dashboard analytics.
    """
    pipeline_id   = job["pipeline_id"]
    input_source  = job["input_source"]
    num_questions = int(job.get("num_questions") or config.NUM_QUESTIONS)
    output_mode   = job.get("output_mode", "questions")
    request_id    = job.get("request_id", pipeline_id)

    logger.info(
        "Dispatching job %s  mode=%s  input=%s",
        pipeline_id, output_mode, input_source,
        extra={"pipeline_id": pipeline_id, "output_mode": output_mode,
               "request_id": request_id},
    )

    # ── 1. Cache check ────────────────────────────────────────────────────────
    cache_key = make_cache_key(input_source, output_mode, num_questions)
    cached_md = get_cached(cache_key)
    if cached_md:
        logger.info("Cache HIT for job %s — skipping pipeline", pipeline_id)
        # Write the cached PDF from the markdown
        pdf_path = str(config.OUTPUT_DIR / f"{pipeline_id}_qa.pdf")
        try:
            md_path = config.OUTPUT_DIR / f"{pipeline_id}_qa.md"
            md_path.write_text(cached_md, encoding="utf-8")
            from src.output.pdf_converter import convert_markdown_to_pdf
            convert_markdown_to_pdf(md_path, pdf_path)
        except Exception:
            pdf_path = ""

        _update_job_status(pipeline_id, "completed",
                           result_markdown=cached_md, result_pdf_path=pdf_path)
        update_job(pipeline_id, status="completed", cached=True,
                   result_markdown=cached_md, result_pdf_path=pdf_path)
        return

    # ── 2. Mark processing ────────────────────────────────────────────────────
    _update_job_status(pipeline_id, "processing")
    update_job(pipeline_id, status="processing")

    t_pipeline_start = time.monotonic()
    try:
        from src.pipeline.graph import run_pipeline_graph

        result = run_pipeline_graph(
            input_source    = input_source,
            pipeline_id     = pipeline_id,
            output_mode     = output_mode,
            num_questions   = num_questions,
            request_id      = request_id,
            source_label    = input_source,
            output_md_path  = str(config.OUTPUT_DIR / f"{pipeline_id}_qa.md"),
            output_pdf_path = str(config.OUTPUT_DIR / f"{pipeline_id}_qa.pdf"),
        )
        markdown_content = result.get("markdown_content", "")
        pdf_path         = result.get("output_pdf_path", "")
        duration_ms      = (time.monotonic() - t_pipeline_start) * 1000

        # ── 3. Cache result ───────────────────────────────────────────────────
        if markdown_content:
            set_cached(cache_key, markdown_content)

        # ── 4. Persist to SQLite + PostgreSQL ─────────────────────────────────
        _update_job_status(pipeline_id, "completed",
                           result_markdown=markdown_content,
                           result_pdf_path=pdf_path)
        update_job(pipeline_id, status="completed", cached=False,
                   result_markdown=markdown_content, result_pdf_path=pdf_path)

        # ── 5. Write total pipeline timing to PostgreSQL ──────────────────────
        save_stage_timing(pipeline_id, "total_pipeline", duration_ms, "success")

        logger.info(
            "Job %s completed  mode=%s  duration=%.0fms",
            pipeline_id, output_mode, duration_ms,
            extra={"pipeline_id": pipeline_id, "duration_ms": duration_ms},
        )

    except FileNotFoundError as exc:
        duration_ms = (time.monotonic() - t_pipeline_start) * 1000
        logger.error("File error in job %s: %s", pipeline_id, exc,
                     extra={"pipeline_id": pipeline_id})
        _update_job_status(pipeline_id, "failed",
                           error_message=f"File not found: {exc}")
        update_job(pipeline_id, status="failed", error_message=str(exc))
        save_stage_timing(pipeline_id, "total_pipeline", duration_ms, "failed")

    except Exception as exc:  # noqa: BLE001
        duration_ms = (time.monotonic() - t_pipeline_start) * 1000
        logger.exception("Pipeline error in job %s: %s", pipeline_id, exc,
                         extra={"pipeline_id": pipeline_id})
        _update_job_status(pipeline_id, "failed", error_message=str(exc))
        update_job(pipeline_id, status="failed", error_message=str(exc))
        save_stage_timing(pipeline_id, "total_pipeline", duration_ms, "failed")


def _update_job_status(
    pipeline_id: str,
    status: str,
    *,
    result_markdown: str | None = None,
    result_pdf_path: str | None = None,
    error_message: str | None = None,
) -> None:
    """Update job status in database."""
    with _jobs_lock:
        job = _get_job(pipeline_id) or {
            "pipeline_id": pipeline_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        job["status"] = status
        job["updated_at"] = datetime.now(timezone.utc).isoformat()
        if result_markdown:
            job["result_markdown"] = result_markdown
        if result_pdf_path:
            job["result_pdf_path"] = result_pdf_path
        if error_message:
            job["error_message"] = error_message
        _save_job(pipeline_id, job)


# ── Pydantic Models ───────────────────────────────────────────────────────────
class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    timestamp: str
    powered_by: str = "PrakashPujariAI"


class SubmitJobRequest(BaseModel):
    """Request to submit a document for Q&A generation."""
    num_questions: int = 5  # Optional; override default


class SubmitSourceJobRequest(BaseModel):
    """Request to submit URL/source-based ingestion."""
    source: str
    num_questions: int = 5
    output_mode: str = "questions"  # "text" | "questions" | "both"


class SubmitJobResponse(BaseModel):
    """Response after submitting a job."""
    pipeline_id: str
    status: str
    created_at: str
    message: str


class JobStatusResponse(BaseModel):
    """Response with job status and results."""
    pipeline_id: str
    status: str
    created_at: str
    updated_at: str
    input_source: str
    output_mode: str = "questions"
    result_markdown: str | None = None
    result_pdf_path: str | None = None
    error_message: str | None = None
    queue_position: int | None = None


class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str
    error_code: str


# ── API Endpoints ─────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["Health"])
@limiter.limit("10/minute")
async def health_check(request: Request) -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version=API_VERSION,
        timestamp=datetime.now(timezone.utc).isoformat(),
        powered_by="PrakashPujariAI",
    )


@app.post(
    "/api/qa/generate",
    response_model=SubmitJobResponse,
    tags=["Q&A Generation"],
)
async def submit_qa_job(
    request: Request,
    file: UploadFile = File(...),
    num_questions: int = Form(5),
    output_mode: str = Form("questions"),
) -> SubmitJobResponse:
    """Upload a document and submit a Q&A generation job."""
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    identity   = extract_identity(request)

    # ── Security gates ────────────────────────────────────────────────────────
    check_spike_arrest(identity, request_id=request_id)
    remaining = check_rate_limit(identity, request_id=request_id)

    if not file.filename:
        api_error(400, E.INVALID_PARAM, "A file is required.", request_id=request_id)

    waf_scan(file.filename or "", request_id=request_id)
    validate_file(file, request_id=request_id)

    if num_questions < 1 or num_questions > 50:
        api_error(400, E.INVALID_PARAM,
                  "num_questions must be between 1 and 50.", request_id=request_id)

    if output_mode not in ("text", "questions", "both"):
        api_error(400, E.INVALID_PARAM,
                  "output_mode must be 'text', 'questions', or 'both'.", request_id=request_id)

    if not config.GROQ_API_KEY:
        api_error(500, E.SERVER_MISCONFIGURATION,
                  "Server is not properly configured.", request_id=request_id)

    # ── Save file + enqueue ───────────────────────────────────────────────────
    pipeline_id = str(uuid.uuid4())[:8]
    file_path   = TEMP_UPLOAD_DIR / f"{pipeline_id}_{file.filename}"
    try:
        contents = await file.read()
        file_path.write_bytes(contents)
    except Exception as exc:
        logger.error("Failed to save uploaded file: %s", exc,
                     extra={"request_id": request_id})
        api_error(500, E.PIPELINE_FAILED,
                  "Failed to process the uploaded file.", request_id=request_id)

    job = {
        "pipeline_id":  pipeline_id,
        "input_source": str(file_path),
        "num_questions": num_questions,
        "output_mode":  output_mode,
        "request_id":   request_id,
        "identity":     identity,
        "status":       "queued",
        "created_at":   datetime.now(timezone.utc).isoformat(),
        "updated_at":   datetime.now(timezone.utc).isoformat(),
    }

    with _jobs_lock:
        _save_job(pipeline_id, job)
    save_job(job)        # PostgreSQL (or SQLite fallback)
    _job_queue.put(job)

    logger.info(
        "Job %s submitted (file: %s, mode: %s, queue: %d)",
        pipeline_id, file.filename, output_mode, _job_queue.qsize(),
        extra={"pipeline_id": pipeline_id, "request_id": request_id,
               "identity": identity, "output_mode": output_mode},
    )

    reset_at = int(math.floor(time.time() / RATE_LIMIT_WINDOW) * RATE_LIMIT_WINDOW + RATE_LIMIT_WINDOW)
    from fastapi.responses import JSONResponse as _JR
    resp_data = SubmitJobResponse(
        pipeline_id=pipeline_id,
        status="queued",
        created_at=job["created_at"],
        message=(
            f"Job queued. Output mode: {output_mode}. "
            f"Requests remaining this hour: {remaining}."
        ),
    )
    from fastapi.responses import Response as _R
    return resp_data


@app.get(
    "/api/qa/status/{pipeline_id}",
    response_model=JobStatusResponse,
    tags=["Q&A Generation"],
)
@limiter.limit("30/minute")
async def get_job_status(request: Request, pipeline_id: str) -> JobStatusResponse:
    """
    Get the status of a submitted job.

    Returns:
        Job status ("queued", "processing", "completed", "failed"),
        queue position, and results (if completed).
    """
    with _jobs_lock:
        job = _get_job(pipeline_id)

    # SQLite is ephemeral on Render — fall back to PostgreSQL for jobs from
    # previous server instances (survives restarts and sleep/wake cycles).
    if not job:
        job = get_job(pipeline_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Calculate queue position
    queue_position = None
    if job["status"] == "queued":
        queue_position = _job_queue.qsize()

    return JobStatusResponse(
        pipeline_id=pipeline_id,
        status=job["status"],
        created_at=str(job["created_at"]),
        updated_at=str(job["updated_at"]),
        input_source=job["input_source"],
        output_mode=job.get("output_mode", "questions"),
        result_markdown=job.get("result_markdown"),
        result_pdf_path=job.get("result_pdf_path"),
        error_message=job.get("error_message"),
        queue_position=queue_position,
    )


@app.post(
    "/api/qa/generate-source",
    response_model=SubmitJobResponse,
    tags=["Q&A Generation"],
)
async def submit_source_job(
    request: Request,
    payload: SubmitSourceJobRequest,
) -> SubmitJobResponse:
    """Submit a URL or source string for ingestion (website / YouTube)."""
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    identity   = extract_identity(request)

    check_spike_arrest(identity, request_id=request_id)
    remaining = check_rate_limit(identity, request_id=request_id)

    source = payload.source.strip()
    if not source:
        api_error(400, E.INVALID_PARAM, "source is required.", request_id=request_id)

    # WAF scan on the raw source string
    waf_scan(source, request_id=request_id)

    # URL validation
    from urllib.parse import urlparse as _up
    parsed = _up(source)
    if parsed.scheme in ("http", "https"):
        host = (parsed.hostname or "").lower()
        if "youtube.com" in host or "youtu.be" in host:
            validate_youtube_url(source, request_id=request_id)
        else:
            validate_url(source, request_id=request_id)

    if payload.num_questions < 1 or payload.num_questions > 50:
        api_error(400, E.INVALID_PARAM,
                  "num_questions must be between 1 and 50.", request_id=request_id)

    if payload.output_mode not in ("text", "questions", "both"):
        api_error(400, E.INVALID_PARAM,
                  "output_mode must be 'text', 'questions', or 'both'.", request_id=request_id)

    if not config.GROQ_API_KEY:
        api_error(500, E.SERVER_MISCONFIGURATION,
                  "Server is not properly configured.", request_id=request_id)

    pipeline_id = str(uuid.uuid4())[:8]
    job = {
        "pipeline_id":  pipeline_id,
        "input_source": source,
        "num_questions": payload.num_questions,
        "output_mode":  payload.output_mode,
        "request_id":   request_id,
        "identity":     identity,
        "status":       "queued",
        "created_at":   datetime.now(timezone.utc).isoformat(),
        "updated_at":   datetime.now(timezone.utc).isoformat(),
    }

    with _jobs_lock:
        _save_job(pipeline_id, job)
    save_job(job)        # PostgreSQL (or SQLite fallback)
    _job_queue.put(job)

    logger.info(
        "Source job %s submitted (source=%s, mode=%s, queue=%d)",
        pipeline_id, source, payload.output_mode, _job_queue.qsize(),
        extra={"pipeline_id": pipeline_id, "request_id": request_id, "source": source},
    )

    return SubmitJobResponse(
        pipeline_id=pipeline_id,
        status="queued",
        created_at=job["created_at"],
        message=(
            f"Source job queued. Output mode: {payload.output_mode}. "
            f"Requests remaining this hour: {remaining}."
        ),
    )


@app.get(
    "/api/qa/download/{pipeline_id}",
    tags=["Q&A Generation"],
)
@limiter.limit("20/minute")
async def download_result(request: Request, pipeline_id: str):
    """Download the generated PDF for a completed job."""
    with _jobs_lock:
        job = _get_job(pipeline_id)
    if not job:
        job = get_job(pipeline_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job not ready (status: {job['status']})",
        )

    pdf_path = Path(job["result_pdf_path"])
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found")

    return JSONResponse(
        {
            "download_url": f"/api/qa/file/{pipeline_id}/{pdf_path.name}",
            "filename": pdf_path.name,
        }
    )


@app.get(
    "/api/qa/file/{pipeline_id}/{filename}",
    tags=["Q&A Generation"],
)
@limiter.limit("20/minute")
async def download_file(request: Request, pipeline_id: str, filename: str):
    """Download a file (PDF or other) from a completed job."""
    with _jobs_lock:
        job = _get_job(pipeline_id)
    if not job:
        job = get_job(pipeline_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    file_path = Path(job["result_pdf_path"]).parent / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    from fastapi.responses import FileResponse
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/pdf",
    )


# ── Keep-alive pinger (prevents Render free-tier sleep) ───────────────────────

def _keep_alive_pinger() -> None:
    """
    Ping own /health every 10 minutes so Render doesn't spin the service down.
    Only runs when RENDER_EXTERNAL_URL is set (i.e. on Render, not local dev).
    First ping is delayed 60 s so the server is fully up before we hit it.
    """
    import urllib.request as _urlreq
    app_url = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
    if not app_url:
        return
    ping_url = f"{app_url}/health"
    logger.info("Keep-alive pinger started → %s (every 10 min)", ping_url)
    time.sleep(60)   # wait for server to be fully ready
    while True:
        try:
            with _urlreq.urlopen(ping_url, timeout=15) as resp:
                logger.debug("Keep-alive ping OK (status %s)", resp.status)
        except Exception as exc:
            logger.warning("Keep-alive ping failed: %s", exc)
        time.sleep(600)  # 10 minutes


# ── Startup / Shutdown ────────────────────────────────────────────────────────
_worker_thread: threading.Thread | None = None


@app.on_event("startup")
async def startup():
    """Initialize databases and start background worker."""
    global _worker_thread
    logger.info("Starting Q&A Agent API server")
    _init_db()           # SQLite (legacy fallback)
    init_db()            # PostgreSQL (primary) or SQLite if PG unavailable

    # Mark any jobs left as queued/processing from a previous crash as failed
    # so they don't show as stuck forever in the dashboard.
    try:
        from api.database import get_recent_jobs, update_job
        stuck = [j for j in get_recent_jobs(100)
                 if j.get("status") in ("queued", "processing")]
        for j in stuck:
            update_job(j["pipeline_id"], status="failed",
                       error_message="Server restarted — job interrupted")
        if stuck:
            logger.info("Marked %d interrupted job(s) as failed on startup", len(stuck))
    except Exception as exc:
        logger.warning("Could not clean up stuck jobs: %s", exc)

    _worker_thread = threading.Thread(target=_process_job_queue, daemon=True)
    _worker_thread.start()
    logger.info("Background worker thread started")

    # Start keep-alive pinger (no-op locally; active on Render when env var is set)
    pinger = threading.Thread(target=_keep_alive_pinger, daemon=True, name="keep-alive")
    pinger.start()


@app.on_event("shutdown")
async def shutdown():
    """Gracefully shutdown the worker thread."""
    logger.info("Shutting down Q&A Agent API server")
    _job_queue.put(None)  # Sentinel: stop the worker
    if _worker_thread:
        _worker_thread.join(timeout=5)
    logger.info("Shutdown complete")


# ── Dashboard endpoints ───────────────────────────────────────────────────────

class DashboardStatsResponse(BaseModel):
    total:          int
    completed:      int
    failed:         int
    pending:        int
    cache_hits:     int
    avg_duration_ms: float
    by_mode:        dict
    hourly:         list
    stage_avg_ms:   dict


@app.get("/api/dashboard/stats", tags=["Dashboard"])
@limiter.limit("60/minute")
async def dashboard_stats(request: Request) -> DashboardStatsResponse:
    """
    Aggregate pipeline statistics from PostgreSQL.

    Returns total / completed / failed / pending job counts, cache hit count,
    average pipeline duration, per-output-mode breakdown, hourly throughput
    (last 24 h), and per-stage average timings.
    """
    stats = get_dashboard_stats()
    return DashboardStatsResponse(
        total           = int(stats.get("total", 0) or 0),
        completed       = int(stats.get("completed", 0) or 0),
        failed          = int(stats.get("failed", 0) or 0),
        pending         = int(stats.get("pending", 0) or 0),
        cache_hits      = int(stats.get("cache_hits", 0) or 0),
        avg_duration_ms = float(stats.get("avg_duration_ms", 0) or 0),
        by_mode         = stats.get("by_mode", {}),
        hourly          = stats.get("hourly", []),
        stage_avg_ms    = stats.get("stage_avg_ms", {}),
    )


@app.get("/api/dashboard/jobs", tags=["Dashboard"])
@limiter.limit("60/minute")
async def dashboard_jobs(request: Request, limit: int = 50):
    """
    Most recent pipeline jobs for the dashboard table.
    Returns up to `limit` rows ordered by creation time descending.
    """
    jobs = get_recent_jobs(min(limit, 200))
    # Serialise datetime/Decimal objects that JSON can't handle
    for j in jobs:
        for k, v in j.items():
            if hasattr(v, "isoformat"):
                j[k] = v.isoformat()
            elif v is None:
                j[k] = None
    return {"jobs": jobs, "count": len(jobs)}


class ReviewRequest(BaseModel):
    rating:      int           # 1–5
    review_text: str  = ""
    use_case:    str  = ""     # e.g. "education", "interview prep"
    output_mode: str  = ""
    job_id:      str  = ""


@app.post("/api/reviews", tags=["Reviews"])
@limiter.limit("5/minute")
async def submit_review(request: Request, body: ReviewRequest):
    """
    Submit a star rating (1–5) and optional free-text review.

    Stored verbatim in qa_reviews for later sentiment-analysis / ML use.
    The identity field is the HMAC-hashed device fingerprint (anonymised).
    """
    if not (1 <= body.rating <= 5):
        api_error(400, E.INVALID_PARAM, "rating must be 1–5")

    identity   = extract_identity(request)
    request_id = getattr(request.state, "request_id", "unknown")

    review = {
        "review_id":   str(uuid.uuid4()),
        "rating":      body.rating,
        "review_text": body.review_text.strip()[:2000],  # cap to 2 KB
        "use_case":    body.use_case.strip()[:100],
        "output_mode": body.output_mode.strip()[:20],
        "job_id":      body.job_id.strip()[:20],
        "identity":    identity,
    }
    save_review(review)
    logger.info("Review saved: rating=%d request_id=%s", body.rating, request_id)
    return {"status": "ok", "review_id": review["review_id"]}


@app.get("/api/dashboard/reviews", tags=["Reviews"])
@limiter.limit("60/minute")
async def dashboard_reviews(request: Request, limit: int = 20):
    """Recent reviews + aggregate stats for the dashboard."""
    reviews = get_reviews(min(limit, 100))
    stats   = get_review_stats()
    return {"reviews": reviews, "stats": stats}


@app.get("/api/dashboard/cache-status", tags=["Dashboard"])
async def cache_status(request: Request):
    """Report Redis + in-memory cache status."""
    from api.cache import _get_redis
    redis_ok = False
    try:
        r = _get_redis()
        if r is not None:
            r.ping()
            redis_ok = True
    except Exception:
        pass

    return {
        "cache_enabled":      True,
        "redis_connected":    redis_ok,
        "redis_url_set":      bool(config.REDIS_URL),
        "cache_ttl_seconds":  config.CACHE_TTL,
        "cache_layers":       "redis+memory" if redis_ok else "memory-only",
    }


@app.get("/api/debug/db", tags=["Dashboard"])
async def db_status(request: Request):
    """Show which database backend is active and the configured URL host."""
    from api.database import _using_postgres
    import api.database as _db
    db_url = config.DATABASE_URL or ""
    host = db_url.split("@")[-1].split("/")[0] if "@" in db_url else "none"
    row_count = None
    try:
        from api.database import get_dashboard_stats
        s = get_dashboard_stats()
        row_count = s.get("total")
    except Exception:
        pass
    return {
        "using_postgres": _using_postgres,
        "db_host":        host,
        "db_url_set":     bool(db_url),
        "job_count":      row_count,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
