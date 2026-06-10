"""MUnit Agent - inspects the parsed MUnit report, computes coverage/pass rate,
and reasons about gaps and failure root causes."""
from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.models.schemas import AgentFinding, AgentReport, MUnitReport


class MUnitAgent(BaseAgent):
    name = "munit"
    role = (
        "You are an SDET reviewing a MuleSoft MUnit test execution report. "
        "Compute coverage gaps, classify failures, suggest missing tests, and "
        "produce a JSON report with: score (0-100), summary, findings[]. "
        "Each finding MUST have: severity (info|low|medium|high|critical), title, "
        "detail (specific explanation of the issue, gap, or failure root-cause), "
        "recommendation (concrete actionable next step to resolve or improve coverage)."
    )

    def run(self, state: dict[str, Any]) -> AgentReport:
        report: MUnitReport = state["munit_report"]
        failures = [c for s in report.suites for c in s.cases if c.status in ("failed", "errored")]
        failure_summary = (
            "\n".join(
                f"- [{c.failure_type or 'failure'}] {c.name}: {c.failure_message or 'n/a'}"
                for c in failures[:25]
            )
            or "No failing cases."
        )
        suite_summary = "\n".join(
            f"- {s.name}: {s.tests} tests, {s.failures} failures, {s.errors} errors"
            for s in report.suites
        )
        coverage_context = (
            " NOTE: coverage is 0% because these tests were loaded from MUnit test-definition "
            "XML files (src/test/munit/) — no CI execution report was present. "
            "Do NOT raise findings about zero coverage; focus on test-name gaps and suite completeness instead."
            if report.coverage_percent == 0.0 and report.total_tests > 0 and report.total_failures == 0
            else ""
        )
        prompt = (
            f"MUnit execution summary:\n"
            f"- Total tests: {report.total_tests}\n"
            f"- Failures: {report.total_failures}\n"
            f"- Errors: {report.total_errors}\n"
            f"- Skipped: {report.total_skipped}\n"
            f"- Application coverage: {report.coverage_percent}%{coverage_context}\n\n"
            f"Suites:\n{suite_summary}\n\n"
            f"Failure details:\n{failure_summary}\n\n"
            "Provide a JSON report with: score (weight 70% pass-rate, 30% coverage), "
            "summary, findings[]. Each finding must include severity, title, "
            "detail (specific root-cause or gap explanation), and recommendation (concrete fix step)."
        )
        result = self._traced_ask_json(prompt)

        pass_rate = self._pass_rate(report)
        # When coverage is 0% but all tests pass, the tests are from MUnit definition
        # files with no CI execution data — don't penalise the score for missing coverage.
        if report.coverage_percent == 0.0 and report.total_tests > 0 and report.total_failures == 0:
            derived_score = int(round(pass_rate))
        else:
            derived_score = int(round(0.7 * pass_rate + 0.3 * report.coverage_percent))
        score = self._coerce_score(result, default=derived_score)

        findings: list[AgentFinding] = []
        for f in result.get("findings", []):
            if isinstance(f, dict):
                findings.append(
                    AgentFinding(
                        severity=f.get("severity", "medium"),
                        title=f.get("title", "MUnit finding"),
                        detail=f.get("detail", ""),
                        recommendation=f.get("recommendation"),
                    )
                )
        if not findings and failures:
            findings.append(
                AgentFinding(
                    severity="high",
                    title=f"{len(failures)} failing tests",
                    detail="Failing cases require triage before release.",
                    recommendation="Re-run after fixes; inspect stack traces in suite XMLs.",
                )
            )
        if not findings and not failures:
            findings.append(
                AgentFinding(
                    severity="info",
                    title="All tests green",
                    detail=f"All {report.total_tests} tests passed with {report.coverage_percent}% coverage.",
                    recommendation="Consider adding property-based fuzzing for arithmetic edge cases.",
                )
            )

        return AgentReport(
            agent=self.name,
            score=score,
            summary=result.get(
                "summary",
                f"{report.total_tests} tests, {report.total_failures} failures, "
                f"{report.coverage_percent}% coverage.",
            ),
            findings=findings,
            raw_llm_output=str(result),
        )

    @staticmethod
    def _pass_rate(report: MUnitReport) -> float:
        if report.total_tests == 0:
            return 0.0
        passed = report.total_tests - report.total_failures - report.total_errors
        return 100.0 * passed / report.total_tests
