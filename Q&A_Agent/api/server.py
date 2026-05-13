"""
api/server.py
─────────────
FastAPI gateway server for the Q&A Agent pipeline.

Features:
  • Document upload (PDF, TXT, MD, DOCX, XLSX, CSV)
  • Asynchronous pipeline execution with status tracking
  • Rate limiting / throttling (requests per minute)
  • Request queuing
  • CORS enabled for React frontend
  • Background task management

Architecture:
  • FastAPI app serves HTTP endpoints
  • Pydantic models for request/response validation
  • slowapi for rate limiting
  • threading.Thread for background pipeline execution (single-threaded,
    queued to prevent resource exhaustion)
  • SQLite for persisting job metadata (pipeline_id, status, results)
"""

import logging
import sqlite3
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue
from typing import Any

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

import config
from observability import setup_logging, PipelineMetrics, setup_langsmith
from observability.logger import get_logger

# Heavy pipeline imports are deferred to inside _run_pipeline_job() so
# the server starts quickly on memory-constrained hosts (e.g. Render free tier).
# faiss-cpu and the full langchain stack are only loaded when the first job runs.

# ── Setup logging and observability ────────────────────────────────────────────
setup_logging()
_langsmith_active = setup_langsmith()
logger = get_logger("qa_agent.api")

# ── API Configuration ─────────────────────────────────────────────────────────
API_VERSION = "1.0.0"
API_DIR = Path(__file__).parent
TEMP_UPLOAD_DIR = API_DIR / "uploads"
TEMP_UPLOAD_DIR.mkdir(exist_ok=True)

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Q&A Agent API",
    description="Generate MCQ questions from any document using AI",
    version=API_VERSION,
)

# ── CORS Configuration ────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://localhost:5173",  # local dev
        "https://frontend-six-red-29.vercel.app",          # Vercel production
        "https://*.vercel.app",                            # all Vercel preview URLs
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rate limiting ─────────────────────────────────────────────────────────────
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"],  # Global rate limit
    storage_uri="memory://",  # In-memory storage (use Redis for production)
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Request Queue (single-threaded background worker) ────────────────────────
_job_queue: Queue = Queue()
_jobs_db: dict[str, dict[str, Any]] = {}  # pipeline_id → job metadata
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
            result_markdown TEXT,
            result_pdf_path TEXT,
            error_message TEXT,
            metrics_json TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def _save_job(job_id: str, data: dict[str, Any]) -> None:
    """Save job metadata to SQLite."""
    created_at = data.get("created_at") or datetime.utcnow().isoformat()
    updated_at = data.get("updated_at") or created_at
    db_path = API_DIR / "jobs.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO jobs
        (pipeline_id, status, created_at, updated_at, input_source, result_markdown,
         result_pdf_path, error_message, metrics_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id,
            data.get("status"),
            created_at,
            updated_at,
            data.get("input_source"),
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
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE pipeline_id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "pipeline_id": row[0],
        "status": row[1],
        "created_at": row[2],
        "updated_at": row[3],
        "input_source": row[4],
        "result_markdown": row[5],
        "result_pdf_path": row[6],
        "error_message": row[7],
        "metrics_json": row[8],
    }


# ── Background Worker Thread ──────────────────────────────────────────────────
def _process_job_queue() -> None:
    """
    Worker thread that processes jobs from the queue sequentially.
    This ensures only one pipeline runs at a time, preventing resource exhaustion.
    """
    while True:
        try:
            job = _job_queue.get(timeout=1)
            if job is None:
                break  # Sentinel: stop the worker
            _execute_pipeline(job)
        except Empty:
            # Normal idle state: no queued jobs yet.
            continue
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error in job processor: %s", exc)
            time.sleep(1)  # Brief backoff on error


def _execute_pipeline(job: dict[str, Any]) -> None:
    """Execute the Q&A generation pipeline for a single job."""
    pipeline_id = job["pipeline_id"]
    input_source = job["input_source"]
    num_questions = int(job.get("num_questions") or config.NUM_QUESTIONS)

    logger.info(
        "Processing job %s with input: %s",
        pipeline_id,
        input_source,
        extra={"pipeline_id": pipeline_id},
    )

    # Update status to "processing"
    _update_job_status(pipeline_id, "processing")

    try:
        # Lazy-load heavy pipeline modules (faiss, langchain, openai) here
        # so the server process itself stays lightweight at startup.
        from src.pipeline.stages import (
            stage_extract_text,
            stage_split_text,
            stage_build_vector_store,
            stage_generate_questions,
            stage_format_markdown,
            stage_convert_to_pdf,
        )
        from src.ingestion.document_loader import load_document  # noqa: F401

        # Initialize metrics tracker
        metrics = PipelineMetrics()
        metrics.pipeline_id = pipeline_id  # Use the API-assigned ID
        metrics.start_pipeline()

        # ── Extract text ─────────────────────────────────────────────────────
        logger.info("[1/6] Extracting and cleaning text …")
        clean_text = stage_extract_text(input_source, metrics)
        logger.info("      ✓ Extracted %d characters", len(clean_text))

        # ── Split text into chunks ────────────────────────────────────────────
        logger.info("[2/6] Splitting text into chunks …")
        chunks = stage_split_text(clean_text, metrics)
        logger.info("      ✓ %d chunks created", len(chunks))

        # ── Build vector store ────────────────────────────────────────────────
        logger.info("[3/6] Building vector store …")
        vector_store = stage_build_vector_store(chunks, metrics)
        logger.info("      ✓ Vector store built")

        # ── Generate questions ────────────────────────────────────────────────
        logger.info("[4/6] Generating questions …")
        questions = stage_generate_questions(
            vector_store,
            metrics,
            num_questions=num_questions,
        )
        logger.info("      ✓ %d questions generated", len(questions))

        # ── Format markdown ───────────────────────────────────────────────────
        logger.info("[5/6] Formatting as Markdown …")
        output_md_path = config.OUTPUT_DIR / f"{pipeline_id}_qa.md"
        stage_format_markdown(
            questions,
            source_name=str(input_source),
            output_path=output_md_path,
            metrics=metrics,
        )
        logger.info("      ✓ Markdown generated: %s", output_md_path)

        # ── Convert to PDF ────────────────────────────────────────────────────
        logger.info("[6/6] Converting to PDF …")
        output_pdf_path = config.OUTPUT_DIR / f"{pipeline_id}_qa.pdf"
        stage_convert_to_pdf(output_md_path, output_pdf_path, metrics)
        logger.info("      ✓ PDF generated: %s", output_pdf_path)

        # ── Mark as complete ─────────────────────────────────────────────────
        metrics.finish_pipeline(status="success")

        # Read the markdown for the response
        markdown_content = output_md_path.read_text(encoding="utf-8")

        _update_job_status(
            pipeline_id,
            "completed",
            result_markdown=markdown_content,
            result_pdf_path=str(output_pdf_path),
        )
        logger.info("Job %s completed successfully", pipeline_id)

    except FileNotFoundError as exc:
        logger.error("File error in job %s: %s", pipeline_id, exc)
        _update_job_status(
            pipeline_id,
            "failed",
            error_message=f"File not found: {exc}",
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error processing job %s: %s", pipeline_id, exc)
        _update_job_status(
            pipeline_id,
            "failed",
            error_message=str(exc),
        )


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
            "created_at": datetime.utcnow().isoformat(),
        }
        job["status"] = status
        job["updated_at"] = datetime.utcnow().isoformat()
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


class SubmitJobRequest(BaseModel):
    """Request to submit a document for Q&A generation."""
    num_questions: int = 5  # Optional; override default


class SubmitSourceJobRequest(BaseModel):
    """Request to submit URL/source-based ingestion for Q&A generation."""
    source: str
    num_questions: int = 5


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
        timestamp=datetime.utcnow().isoformat(),
    )


@app.post(
    "/api/qa/generate",
    response_model=SubmitJobResponse,
    tags=["Q&A Generation"],
)
@limiter.limit("10/minute")
async def submit_qa_job(
    request: Request,
    file: UploadFile = File(...),
    num_questions: int = Form(5),
) -> SubmitJobResponse:
    """
    Upload a document and submit a job for Q&A generation.

    Supported formats: PDF, TXT, MD, DOCX, XLSX, CSV

    Rate limit: 10 requests per minute per IP

    Returns:
        Job metadata including pipeline_id for status tracking.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="File is required")

    if num_questions < 1 or num_questions > 50:
        raise HTTPException(status_code=400, detail="num_questions must be between 1 and 50")

    if file.size and file.size > 50 * 1024 * 1024:  # 50 MB limit
        raise HTTPException(status_code=413, detail="File too large (max 50 MB)")

    # Validate API key
    if not config.OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not configured")
        raise HTTPException(status_code=500, detail="Server misconfiguration")

    # Generate unique job ID
    pipeline_id = str(uuid.uuid4())[:8]

    # Save uploaded file
    file_path = TEMP_UPLOAD_DIR / f"{pipeline_id}_{file.filename}"
    try:
        contents = await file.read()
        file_path.write_bytes(contents)
    except Exception as exc:
        logger.error("Failed to save uploaded file: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to process file")

    # Create job
    job = {
        "pipeline_id": pipeline_id,
        "input_source": str(file_path),
        "num_questions": num_questions,
        "status": "queued",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }

    with _jobs_lock:
        _save_job(pipeline_id, job)

    # Enqueue for processing
    _job_queue.put(job)

    logger.info(
        "Job %s submitted (file: %s, queue depth: %d)",
        pipeline_id,
        file.filename,
        _job_queue.qsize(),
        extra={"pipeline_id": pipeline_id, "upload_filename": file.filename},
    )

    return SubmitJobResponse(
        pipeline_id=pipeline_id,
        status="queued",
        created_at=job["created_at"],
        message=(
            f"Job queued for {num_questions} question(s). "
            f"Position in queue: {_job_queue.qsize()}"
        ),
    )


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

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Calculate queue position
    queue_position = None
    if job["status"] == "queued":
        # This is a rough estimate; in production use a proper queue
        queue_position = _job_queue.qsize()

    return JobStatusResponse(
        pipeline_id=pipeline_id,
        status=job["status"],
        created_at=job["created_at"],
        updated_at=job["updated_at"],
        input_source=job["input_source"],
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
@limiter.limit("10/minute")
async def submit_source_job(
    request: Request,
    payload: SubmitSourceJobRequest,
) -> SubmitJobResponse:
    """
    Submit a source string for ingestion (website / YouTube / local path).

    Supported examples:
      - Website URL: https://example.com/article
      - YouTube URL: https://www.youtube.com/watch?v=<id>
      - Local media/image path accessible to the server process
    """
    source = payload.source.strip()
    if not source:
        raise HTTPException(status_code=400, detail="source is required")

    if payload.num_questions < 1 or payload.num_questions > 50:
        raise HTTPException(status_code=400, detail="num_questions must be between 1 and 50")

    if not config.OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not configured")
        raise HTTPException(status_code=500, detail="Server misconfiguration")

    pipeline_id = str(uuid.uuid4())[:8]
    job = {
        "pipeline_id": pipeline_id,
        "input_source": source,
        "num_questions": payload.num_questions,
        "status": "queued",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }

    with _jobs_lock:
        _save_job(pipeline_id, job)

    _job_queue.put(job)

    logger.info(
        "Source job %s submitted (source=%s, queue depth=%d)",
        pipeline_id,
        source,
        _job_queue.qsize(),
        extra={"pipeline_id": pipeline_id, "source": source},
    )

    return SubmitJobResponse(
        pipeline_id=pipeline_id,
        status="queued",
        created_at=job["created_at"],
        message=(
            f"Source job queued for {payload.num_questions} question(s). "
            f"Position in queue: {_job_queue.qsize()}"
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


# ── Startup / Shutdown ────────────────────────────────────────────────────────
_worker_thread: threading.Thread | None = None


@app.on_event("startup")
async def startup():
    """Initialize database and start background worker."""
    global _worker_thread
    logger.info("Starting Q&A Agent API server")
    _init_db()
    _worker_thread = threading.Thread(target=_process_job_queue, daemon=True)
    _worker_thread.start()
    logger.info("Background worker thread started")


@app.on_event("shutdown")
async def shutdown():
    """Gracefully shutdown the worker thread."""
    logger.info("Shutting down Q&A Agent API server")
    _job_queue.put(None)  # Sentinel: stop the worker
    if _worker_thread:
        _worker_thread.join(timeout=5)
    logger.info("Shutdown complete")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
