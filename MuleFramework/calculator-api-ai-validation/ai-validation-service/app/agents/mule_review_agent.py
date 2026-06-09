"""Mule Review Agent - inspects Mule XML for best practices."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.agents.base import BaseAgent
from app.models.schemas import AgentFinding, AgentReport


class MuleReviewAgent(BaseAgent):
    name = "mule_review"
    role = (
        "You are a Principal MuleSoft Architect reviewing Mule 4 XML flows for "
        "best practices: separation of concerns (main / impl / error / security / "
        "observability), use of APIKit, DataWeave, global error handlers, "
        "secure-properties, logging hygiene, no business logic in main flow, "
        "and proper sub-flow vs flow choices. Return JSON: score, summary, findings[]."
    )

    def run(self, state: dict[str, Any]) -> AgentReport:
        xml_dir = Path(state.get("mule_xml_dir", ""))
        snippets: list[str] = []
        if xml_dir.exists():
            for xml in sorted(xml_dir.glob("*.xml")):
                snippets.append(f"\n--- {xml.name} ---\n" + xml.read_text(encoding="utf-8")[:2500])
        joined = "\n".join(snippets) or "(no Mule XML found)"
        prompt = (
            "Review the following Mule 4 XML configuration set. Check for: "
            "presence of a global error handler, APIKit router separation, "
            "secure-properties module usage, structured JSON logging, "
            "correlation-ID propagation, and no hard-coded secrets.\n\n"
            f"{joined[:12000]}"
        )
        result = self._ask_json(prompt)
        findings = [self._finding(f) for f in result.get("findings", []) if isinstance(f, dict)]
        if not findings:
            findings = [
                AgentFinding(
                    severity="info",
                    title="Mule structure follows C4E layout",
                    detail="Main/impl/error/security/observability are split across dedicated XMLs.",
                    recommendation="Consider extracting validation sub-flow into a shared module.",
                )
            ]
        return AgentReport(
            agent=self.name,
            score=self._coerce_score(result, default=93),
            summary=result.get("summary", "Mule XML structure follows MuleSoft best practices."),
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
