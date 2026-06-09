"""Executive Reporting Agent - synthesizes all prior agent reports into a
business-readable dashboard and recommendation."""
from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.models.schemas import (
    AgentFinding,
    AgentReport,
    ExecutiveDashboard,
    MUnitReport,
)


class ExecutiveReportingAgent(BaseAgent):
    name = "executive_reporting"
    role = (
        "You are the Head of Engineering producing a business-facing release "
        "readiness summary for a MuleSoft API. Combine scores from upstream "
        "agents into a clear go/no-go recommendation. Return JSON with: "
        "summary (executive paragraph), recommendation (APPROVED|CONDITIONAL|BLOCKED)."
    )

    def run(self, state: dict[str, Any]) -> AgentReport:
        report: MUnitReport = state["munit_report"]
        agent_reports: list[AgentReport] = state["agent_reports"]
        scores = {r.agent: r.score for r in agent_reports}

        pass_rate = self._pass_rate(report)
        coverage = int(round(report.coverage_percent))

        security = scores.get("security", 95)
        performance = scores.get("performance", 95)
        munit = scores.get("munit", int(round(pass_rate)))
        api_design = scores.get("api_design", 95)
        mule_review = scores.get("mule_review", 95)

        confidence = int(round(0.30 * munit + 0.25 * security + 0.20 * performance + 0.15 * api_design + 0.10 * mule_review))
        risk = max(0, 100 - confidence)
        production_readiness = int(round(0.5 * confidence + 0.3 * (coverage if coverage else pass_rate) + 0.2 * pass_rate))

        if production_readiness >= 90 and security >= 90 and pass_rate >= 95:
            recommendation = "APPROVED"
        elif production_readiness >= 75:
            recommendation = "CONDITIONAL"
        else:
            recommendation = "BLOCKED"

        dashboard = ExecutiveDashboard(
            application=state.get("application", "calculator-api"),
            runtime=state.get("runtime", "4.9"),
            coverage=coverage if coverage else int(round(pass_rate)),
            testsExecuted=report.total_tests,
            testsPassed=report.total_tests - report.total_failures - report.total_errors,
            testsFailed=report.total_failures + report.total_errors,
            passRate=int(round(pass_rate)),
            securityScore=security,
            performanceScore=performance,
            confidenceScore=confidence,
            riskScore=risk,
            productionReadiness=production_readiness,
            recommendation=recommendation,  # type: ignore[arg-type]
        )

        prompt = (
            "Produce an executive paragraph (3-5 sentences) summarising release readiness "
            f"for {dashboard.application} (Mule {dashboard.runtime}). "
            f"Tests: {dashboard.testsPassed}/{dashboard.testsExecuted} passed, "
            f"coverage {dashboard.coverage}%, security {dashboard.securityScore}, "
            f"performance {dashboard.performanceScore}, confidence {dashboard.confidenceScore}, "
            f"risk {dashboard.riskScore}, readiness {dashboard.productionReadiness}, "
            f"recommendation {dashboard.recommendation}. "
            "Then return JSON with keys summary, recommendation."
        )
        result = self._traced_ask_json(prompt)
        exec_summary = result.get(
            "summary",
            f"{dashboard.application} (Mule {dashboard.runtime}) is {dashboard.recommendation}. "
            f"{dashboard.testsPassed}/{dashboard.testsExecuted} tests passed, "
            f"coverage {dashboard.coverage}%, readiness {dashboard.productionReadiness}.",
        )
        state["dashboard"] = dashboard
        state["executive_summary"] = exec_summary

        return AgentReport(
            agent=self.name,
            score=production_readiness,
            summary=exec_summary,
            findings=[
                AgentFinding(
                    severity="info" if recommendation == "APPROVED" else "high",
                    title=f"Recommendation: {recommendation}",
                    detail=f"Production readiness score: {production_readiness}.",
                    recommendation="Proceed to production deployment."
                    if recommendation == "APPROVED"
                    else "Address findings from upstream agents before re-running the pipeline.",
                )
            ],
            raw_llm_output=str(result),
        )

    @staticmethod
    def _pass_rate(report: MUnitReport) -> float:
        if report.total_tests == 0:
            return 0.0
        passed = report.total_tests - report.total_failures - report.total_errors
        return 100.0 * passed / report.total_tests
