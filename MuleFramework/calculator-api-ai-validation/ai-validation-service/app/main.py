"""FastAPI entrypoint exposing the AI test-validation pipeline."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File
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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ai-validation", "env": settings.app_env}


@app.get("/ready")
def ready() -> dict[str, str]:
    return {"status": "ready"}


@app.post("/validate", response_model=PipelineResponse)
def validate(req: PipelineRequest) -> PipelineResponse:
    munit_dir = Path(req.munit_reports_dir or settings.munit_reports_dir)
    raml_path = Path(req.raml_path or settings.raml_path)
    mule_dir = Path(req.mule_xml_dir or settings.mule_xml_dir)

    if not munit_dir.exists():
        raise HTTPException(status_code=400, detail=f"MUnit reports dir not found: {munit_dir}")

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
