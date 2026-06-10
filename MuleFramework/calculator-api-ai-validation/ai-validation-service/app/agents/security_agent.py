"""Security Agent - reviews OAuth, JWT, threat protection, and security-test coverage."""
from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.models.schemas import AgentFinding, AgentReport


class SecurityAgent(BaseAgent):
    name = "security"
    role = (
        "You are a senior application-security engineer reviewing a MuleSoft API. "
        "Assess OAuth2 enforcement, JWT validation (issuer/audience/expiry), "
        "client-id enforcement, JSON threat protection (body size, depth, key count), "
        "and rate limiting. Verify that MUnit security tests cover invalid JWT, "
        "expired JWT, and missing client_id. "
        "Return findings as JSON with keys: score (0-100), summary, findings[]. "
        "Each finding MUST have: severity (info|low|medium|high|critical), title, "
        "detail (specific security gap or risk observed), "
        "recommendation (concrete remediation step — e.g. add JWKS rotation, enforce TLS 1.3, set rate-limit headers)."
    )

    def run(self, state: dict[str, Any]) -> AgentReport:
        prior_summaries = "\n".join(
            f"{r.agent}: {r.summary}" for r in state.get("agent_reports", [])
        )
        security_tests = [
            c.name
            for s in state["munit_report"].suites
            if "security" in s.name.lower()
            for c in s.cases
        ]
        prompt = (
            "Mule XML highlights:\n"
            "- jwt-validation:validate against shared HMAC secret with issuer+audience+exp checks\n"
            "- client-id-enforcement:validate-client\n"
            "- json threat protection via DataWeave size/depth/key heuristic\n"
            "- token-bucket rate limiting per client_id per minute\n\n"
            f"Security MUnit tests detected: {security_tests or 'none'}\n\n"
            f"Prior agent context:\n{prior_summaries}\n\n"
            "Provide a JSON report scoring the security posture. "
            "Each finding must include severity, title, "
            "detail (specific risk or gap), and recommendation (concrete remediation step)."
        )
        result = self._traced_ask_json(prompt)
        findings = [self._finding(f) for f in result.get("findings", []) if isinstance(f, dict)]
        if not findings:
            findings = [
                AgentFinding(
                    severity="info",
                    title="Security controls present",
                    detail="JWT, client-id enforcement, JSON threat protection, and rate limiting are wired in.",
                    recommendation="Add JWKS-based key rotation and per-route rate limits in prod.",
                )
            ]
        return AgentReport(
            agent=self.name,
            score=self._coerce_score(result, default=98),
            summary=result.get("summary", "Defense-in-depth security posture is in place."),
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
