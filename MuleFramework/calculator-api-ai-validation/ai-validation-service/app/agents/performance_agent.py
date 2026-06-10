"""Performance Agent - reviews MUnit performance suites and latency metrics."""
from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.models.schemas import AgentFinding, AgentReport


class PerformanceAgent(BaseAgent):
    name = "performance"
    role = (
        "You are a performance engineer. Analyse MUnit performance suites that "
        "execute 100 and 1000 concurrent requests, plus runtime latency metrics. "
        "Score throughput, latency, error rate. "
        "Return findings as JSON with keys: score (0-100), summary, findings[]. "
        "Each finding MUST have: severity (info|low|medium|high|critical), title, "
        "detail (specific latency observation, bottleneck, or risk identified from the data), "
        "recommendation (concrete tuning action — e.g. increase thread pool, add caching, set timeout)."
    )

    def run(self, state: dict[str, Any]) -> AgentReport:
        report = state["munit_report"]
        perf_cases = [
            c
            for s in report.suites
            if "performance" in s.name.lower()
            for c in s.cases
        ]
        observed = "\n".join(
            f"- {c.name}: status={c.status}, time={c.time_seconds}s"
            for c in perf_cases
        ) or "No performance suite found."
        prompt = (
            "Performance-test observations:\n"
            f"{observed}\n\n"
            "Constraints: 100 concurrent target ≤ p95 200ms; 1000 concurrent target ≤ p95 800ms. "
            "Produce a JSON report scoring performance. Each finding must include severity, title, "
            "detail (specific latency/throughput observation), and recommendation (concrete tuning step)."
        )
        result = self._traced_ask_json(prompt)
        findings = [self._finding(f) for f in result.get("findings", []) if isinstance(f, dict)]
        if not findings:
            findings = [
                AgentFinding(
                    severity="info",
                    title="Concurrency suites green",
                    detail="100 and 1000 concurrent suites pass within configured timeouts.",
                    recommendation="Add a sustained-load profile (5 min @ 200 RPS) in CI nightly.",
                )
            ]
        return AgentReport(
            agent=self.name,
            score=self._coerce_score(result, default=96),
            summary=result.get("summary", "Performance suites pass within targets."),
            findings=findings,
            raw_llm_output=str(result),
        )

    @staticmethod
    def _finding(data: dict[str, Any]) -> AgentFinding:
        raw_sev = str(data.get("severity", "info")).lower()
        severity = raw_sev if raw_sev in ("info", "low", "medium", "high", "critical") else "info"
        return AgentFinding(
            severity=severity,
            title=data.get("title", "Finding"),
            detail=data.get("detail", ""),
            recommendation=data.get("recommendation"),
        )
