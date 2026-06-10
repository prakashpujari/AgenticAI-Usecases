"""FastAPI entrypoint exposing the AI test-validation pipeline."""
from __future__ import annotations

import fnmatch
import logging
import os
import re
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

# Matches:  https://github.com/{owner}/{repo}/blob/{branch}/{path}
_GH_BLOB = re.compile(
    r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/blob/(?P<branch>[^/]+)/(?P<path>.+)$"
)
# Matches:  https://github.com/{owner}/{repo}/tree/{branch}/{path}
_GH_TREE = re.compile(
    r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/tree/(?P<branch>[^/]+)/(?P<path>.+)$"
)

_GH_API_HEADERS = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}


def _is_url(value) -> bool:
    return str(value).startswith(("http://", "https://"))


def _resolve_github_file_url(url: str) -> str:
    """If *url* is a GitHub blob URL, return the equivalent raw.githubusercontent.com URL."""
    m = _GH_BLOB.match(url)
    if m:
        raw = (
            f"https://raw.githubusercontent.com"
            f"/{m['owner']}/{m['repo']}/{m['branch']}/{m['path']}"
        )
        logger.info("GitHub blob → raw: %s", raw)
        return raw
    return url  # already a raw/direct URL


def _download_github_tree_to_temp_dir(url: str, file_patterns: list[str]) -> Path:
    """
    Fetch all files matching *file_patterns* from a GitHub tree URL and write
    them into a new temp directory.  Uses the unauthenticated GitHub Contents API.
    """
    m = _GH_TREE.match(url)
    if not m:
        raise HTTPException(status_code=400, detail=f"Not a recognised GitHub tree URL: {url}")

    api_url = (
        f"https://api.github.com/repos/{m['owner']}/{m['repo']}"
        f"/contents/{m['path']}?ref={m['branch']}"
    )
    logger.info("GitHub tree API: %s", api_url)

    tmp_dir = Path(tempfile.mkdtemp(prefix="mule-ai-"))
    try:
        with httpx.Client(follow_redirects=True, timeout=30, headers=_GH_API_HEADERS) as client:
            r = client.get(api_url)
            if r.status_code == 404:
                raise HTTPException(status_code=400, detail=f"GitHub path not found: {url}")
            if r.status_code == 403:
                raise HTTPException(
                    status_code=400,
                    detail="GitHub API rate limit reached. Wait a minute and try again.",
                )
            r.raise_for_status()
            items = r.json()

        if not isinstance(items, list):
            raise HTTPException(status_code=400, detail=f"Expected a directory at: {url}")

        downloaded: list[str] = []
        with httpx.Client(follow_redirects=True, timeout=30) as client:
            for item in items:
                if item.get("type") != "file":
                    continue
                name: str = item.get("name", "")
                if not any(fnmatch.fnmatch(name, pat) for pat in file_patterns):
                    continue
                dl_url = item.get("download_url") or (
                    f"https://raw.githubusercontent.com"
                    f"/{m['owner']}/{m['repo']}/{m['branch']}/{m['path']}/{name}"
                )
                content_r = client.get(dl_url)
                content_r.raise_for_status()
                (tmp_dir / name).write_bytes(content_r.content)
                downloaded.append(name)
                logger.info("Downloaded %s from GitHub", name)

        if not downloaded:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"No files matching {file_patterns} found in GitHub directory. "
                    f"URL: {url}"
                ),
            )

    except HTTPException:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"Error fetching GitHub directory: {exc}")

    return tmp_dir


def _download_to_temp_dir(url: str) -> Path:
    """Download a single raw file URL into a new temp directory; return the dir."""
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
    """Download a raw file URL to a named temp file; return its Path."""
    resolved = _resolve_github_file_url(url)  # blob → raw if needed
    try:
        with httpx.Client(follow_redirects=True, timeout=30) as client:
            r = client.get(resolved)
            r.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to fetch URL (HTTP {exc.response.status_code}): {resolved}",
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
        # Accepts: local path | raw URL (single XML) | GitHub tree URL (directory)
        munit_raw = str(req.munit_reports_dir or settings.munit_reports_dir)
        if _is_url(munit_raw):
            if _GH_TREE.match(munit_raw):
                # GitHub directory → fetch all XML + coverage JSON via API
                munit_dir = _download_github_tree_to_temp_dir(
                    munit_raw, ["TEST-*.xml", "*surefire*.xml", "munit-coverage.json", "*.xml"]
                )
            else:
                munit_dir = _download_to_temp_dir(munit_raw)
            temp_dirs.append(munit_dir)
        else:
            munit_dir = Path(munit_raw)

        # ── Resolve raml_path ──────────────────────────────────────────────
        # Accepts: local path | raw URL | GitHub blob URL (auto-converted to raw)
        raml_raw = str(req.raml_path or settings.raml_path)
        if _is_url(raml_raw):
            # _download_to_temp_file calls _resolve_github_file_url internally
            raml_path = _download_to_temp_file(raml_raw, suffix=".raml")
            temp_files.append(raml_path)
        else:
            raml_path = Path(raml_raw)

        # ── Resolve mule_xml_dir ───────────────────────────────────────────
        # Accepts: local path | raw URL (single XML) | GitHub tree URL (directory)
        mule_raw = str(req.mule_xml_dir or settings.mule_xml_dir)
        if _is_url(mule_raw):
            if _GH_TREE.match(mule_raw):
                mule_dir = _download_github_tree_to_temp_dir(mule_raw, ["*.xml"])
            else:
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
