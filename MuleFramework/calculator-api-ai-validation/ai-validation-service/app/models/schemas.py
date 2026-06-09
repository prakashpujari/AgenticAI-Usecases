"""Pydantic schemas shared by the FastAPI endpoints and LangGraph state."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ----------------------------------------------------------------------
# MUnit report
# ----------------------------------------------------------------------
class MUnitTestCase(BaseModel):
    name: str
    classname: str = ""
    time_seconds: float = 0.0
    status: Literal["passed", "failed", "errored", "skipped"] = "passed"
    failure_message: str | None = None
    failure_type: str | None = None
    failure_stack: str | None = None


class MUnitSuite(BaseModel):
    name: str
    tests: int = 0
    failures: int = 0
    errors: int = 0
    skipped: int = 0
    time_seconds: float = 0.0
    cases: list[MUnitTestCase] = Field(default_factory=list)


class MUnitReport(BaseModel):
    suites: list[MUnitSuite] = Field(default_factory=list)
    total_tests: int = 0
    total_failures: int = 0
    total_errors: int = 0
    total_skipped: int = 0
    total_time_seconds: float = 0.0
    coverage_percent: float = 0.0


# ----------------------------------------------------------------------
# Agent findings
# ----------------------------------------------------------------------
class AgentFinding(BaseModel):
    severity: Literal["info", "low", "medium", "high", "critical"]
    title: str
    detail: str
    recommendation: str | None = None


class AgentReport(BaseModel):
    agent: str
    score: int = Field(ge=0, le=100)
    summary: str
    findings: list[AgentFinding] = Field(default_factory=list)
    raw_llm_output: str | None = None


# ----------------------------------------------------------------------
# Executive dashboard
# ----------------------------------------------------------------------
class ExecutiveDashboard(BaseModel):
    application: str = "calculator-api"
    runtime: str = "4.9"
    coverage: int
    testsExecuted: int
    testsPassed: int
    testsFailed: int
    passRate: int
    securityScore: int
    performanceScore: int
    confidenceScore: int
    riskScore: int
    productionReadiness: int
    recommendation: Literal["APPROVED", "CONDITIONAL", "BLOCKED"]


# ----------------------------------------------------------------------
# Pipeline request/response
# ----------------------------------------------------------------------
class PipelineRequest(BaseModel):
    munit_reports_dir: str | None = None
    raml_path: str | None = None
    mule_xml_dir: str | None = None
    application: str = "calculator-api"
    runtime: str = "4.9"


class PipelineResponse(BaseModel):
    dashboard: ExecutiveDashboard
    agent_reports: list[AgentReport]
    executive_summary: str
    artifacts: dict[str, Any] = Field(default_factory=dict)
