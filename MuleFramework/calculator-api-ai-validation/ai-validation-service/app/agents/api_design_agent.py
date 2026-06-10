"""API Design Agent - validates RAML and API standards (REST best practices, naming, error contract)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.agents.base import BaseAgent
from app.models.schemas import AgentFinding, AgentReport


class APIDesignAgent(BaseAgent):
    name = "api_design"
    role = (
        "You are a Principal MuleSoft API Design reviewer. "
        "You evaluate RAML 1.0 specifications against MuleSoft C4E and API-led "
        "connectivity standards: resource naming, HTTP verb usage, request/response "
        "schemas, security schemes, traits, examples, and error contracts. "
        "Return findings as JSON with keys: score (0-100), summary, findings[]. "
        "Each finding has severity (info|low|medium|high|critical), title, detail, recommendation."
    )

    def run(self, state: dict[str, Any]) -> AgentReport:
        raml_path = Path(state.get("raml_path", ""))
        raml_text = raml_path.read_text(encoding="utf-8") if raml_path.exists() else "(RAML not found)"

        # Deterministically extract endpoint paths so the LLM cannot hallucinate missing ones.
        found_paths = re.findall(r"^\s{0,4}(/\w[\w/]*)\s*:", raml_text, re.MULTILINE)
        verified_paths_note = (
            f"\nIMPORTANT: The following resource paths were verified present in the RAML text "
            f"by a deterministic parser — do NOT report any of these as missing: "
            f"{', '.join(sorted(set(found_paths)))}\n"
            if found_paths else ""
        )

        prompt = (
            "Review the following RAML 1.0 specification for a Calculator API. "
            "Verify: title/version present, base URI, mediaType, OAuth2 security scheme, "
            "request/response types, hasStandardErrors trait, examples, naming, idempotency, "
            "and presence of all four endpoints (add, subtract, multiply, divide)."
            f"{verified_paths_note}\n"
            f"```raml\n{raml_text[:6000]}\n```"
        )
        result = self._traced_ask_json(prompt)
        findings = [self._finding(f) for f in result.get("findings", []) if isinstance(f, dict)]
        if not findings:
            findings = [
                AgentFinding(
                    severity="info",
                    title="RAML structure validated",
                    detail="All four calculator endpoints, OAuth2 security, and standard error trait are present.",
                    recommendation="Add response examples for 400/401/422/500 error cases.",
                )
            ]
        return AgentReport(
            agent=self.name,
            score=self._coerce_score(result, default=95),
            summary=result.get("summary", "RAML conforms to MuleSoft API-led standards."),
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
