"""FastAPI entrypoint exposing the AI test-validation pipeline."""
from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.models.schemas import (
    ExecutiveDashboard,
    PipelineRequest,
    PipelineResponse,
)
from app.services.munit_parser import MUnitReportParser
from app.services.workflow import run_pipeline
from app.utils.logging_config import configure_logging

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)

# ── LangSmith tracing ──────────────────────────────────────────────────────
# Ensure the API key is available under both env var names that langsmith
# recognises, so LangChainTracer initialises correctly regardless of version.
if settings.langchain_api_key:
    os.environ.setdefault("LANGCHAIN_API_KEY", settings.langchain_api_key)
    os.environ.setdefault("LANGSMITH_API_KEY", settings.langchain_api_key)
    os.environ.setdefault("LANGCHAIN_PROJECT", settings.langchain_project)
    os.environ.setdefault("LANGCHAIN_ENDPOINT", settings.langchain_endpoint)
    logger.info("LangSmith configured project=%s", settings.langchain_project)
else:
    logger.info("LangSmith disabled (no LANGCHAIN_API_KEY)")

app = FastAPI(
    title="calculator-api AI Validation Service",
    version="1.0.0",
    description=(
        "AI-powered MuleSoft test validation: parses MUnit reports, runs a "
        "LangGraph multi-agent pipeline against the RAML and Mule XML, and "
        "emits an executive dashboard with a deployment recommendation."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── URL helpers ────────────────────────────────────────────────────────────

def _is_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))


def _download_to_temp_dir(url: str) -> Path:
    """Download a single file from *url* into a new temp directory; return the dir."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="mule-ai-"))
    filename = url.split("?")[0].rstrip("/").rsplit("/", 1)[-1] or "report.xml"
    try:
        with httpx.Client(follow_redirects=True, timeout=30) as client:
            r = client.get(url)
            r.raise_for_status()
        (tmp_dir / filename).write_bytes(r.content)
    except httpx.HTTPStatusError as exc:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(
            status_code=400,
            detail=f"Failed to fetch URL (HTTP {exc.response.status_code}): {url}",
        )
    except httpx.RequestError as exc:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"Network error fetching URL: {exc}")
    return tmp_dir


def _download_to_temp_file(url: str, suffix: str = "") -> Path:
    """Download a single file from *url* to a named temp file; return its Path."""
    try:
        with httpx.Client(follow_redirects=True, timeout=30) as client:
            r = client.get(url)
            r.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to fetch URL (HTTP {exc.response.status_code}): {url}",
        )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=400, detail=f"Network error fetching URL: {exc}")

    tmp = Path(tempfile.mktemp(prefix="mule-ai-", suffix=suffix))
    tmp.write_bytes(r.content)
    return tmp


# ── Routes ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ai-validation", "env": settings.app_env}


@app.get("/trace-status")
def trace_status() -> dict:
    """Diagnostic: report LangSmith connectivity from this container."""
    import importlib
    result: dict = {
        "langchain_api_key_set": bool(os.environ.get("LANGCHAIN_API_KEY")),
        "langsmith_api_key_set": bool(os.environ.get("LANGSMITH_API_KEY")),
        "langchain_project": os.environ.get("LANGCHAIN_PROJECT", ""),
        "langsmith_installed": False,
        "langsmith_version": None,
        "langchain_core_installed": False,
        "tracer_created": False,
        "test_run_id": None,
        "error": None,
    }
    try:
        ls = importlib.import_module("langsmith")
        result["langsmith_installed"] = True
        result["langsmith_version"] = getattr(ls, "__version__", "?")

        api_key = os.environ.get("LANGCHAIN_API_KEY") or os.environ.get("LANGSMITH_API_KEY")
        client = ls.Client(api_key=api_key)
        import uuid, datetime
        run_id = uuid.uuid4()
        client.create_run(
            id=run_id,
            name="trace-test",
            run_type="chain",
            project_name=os.environ.get("LANGCHAIN_PROJECT", "mule-ai-validation"),
            inputs={"source": "trace-status endpoint"},
            start_time=datetime.datetime.utcnow(),
        )
        client.update_run(
            run_id,
            outputs={"result": "ok"},
            end_time=datetime.datetime.utcnow(),
        )
        result["test_run_id"] = str(run_id)
        result["tracer_created"] = True
    except Exception as exc:
        result["error"] = str(exc)

    try:
        lc = importlib.import_module("langchain_core")
        result["langchain_core_installed"] = True
        result["langchain_core_version"] = getattr(lc, "__version__", "?")
    except Exception:
        pass

    return result


@app.get("/ready")
def ready() -> dict[str, str]:
    return {"status": "ready"}


@app.post("/validate", response_model=PipelineResponse)
def validate(req: PipelineRequest) -> PipelineResponse:
    temp_dirs: list[Path] = []
    temp_files: list[Path] = []
    try:
        # ── Resolve munit_reports_dir ──────────────────────────────────────
        munit_raw = req.munit_reports_dir or settings.munit_reports_dir
        if _is_url(munit_raw):
            munit_dir = _download_to_temp_dir(munit_raw)
            temp_dirs.append(munit_dir)
        else:
            munit_dir = Path(munit_raw)

        # ── Resolve raml_path ──────────────────────────────────────────────
        raml_raw = req.raml_path or settings.raml_path
        if _is_url(raml_raw):
            raml_path = _download_to_temp_file(raml_raw, suffix=".raml")
            temp_files.append(raml_path)
        else:
            raml_path = Path(raml_raw)

        # ── Resolve mule_xml_dir ───────────────────────────────────────────
        mule_raw = req.mule_xml_dir or settings.mule_xml_dir
        if _is_url(mule_raw):
            mule_dir = _download_to_temp_dir(mule_raw)
            temp_dirs.append(mule_dir)
        else:
            mule_dir = Path(mule_raw)

        if not munit_dir.exists():
            raise HTTPException(
                status_code=400, detail=f"MUnit reports dir not found: {munit_dir}"
            )

        result = run_pipeline(
            munit_reports_dir=munit_dir,
            raml_path=raml_path,
            mule_xml_dir=mule_dir,
            application=req.application,
            runtime=req.runtime,
        )
        return PipelineResponse(
            dashboard=result["dashboard"],
            agent_reports=result["agent_reports"],
            executive_summary=result["executive_summary"],
            artifacts={
                "munit_total": result["munit_report"].total_tests,
                "munit_failures": result["munit_report"].total_failures,
                "munit_coverage": result["munit_report"].coverage_percent,
            },
        )
    finally:
        for d in temp_dirs:
            shutil.rmtree(d, ignore_errors=True)
        for f in temp_files:
            f.unlink(missing_ok=True)


@app.post("/dashboard", response_model=ExecutiveDashboard)
def dashboard(req: PipelineRequest) -> ExecutiveDashboard:
    """Shortcut: run the pipeline and return only the executive dashboard."""
    return validate(req).dashboard


@app.post("/munit/parse")
def parse_munit(
    reports_dir: str | None = None,
) -> JSONResponse:
    target = Path(reports_dir or settings.munit_reports_dir)
    if not target.exists():
        raise HTTPException(status_code=400, detail=f"Reports dir not found: {target}")
    parser = MUnitReportParser(target)
    return JSONResponse(parser.parse().model_dump())
