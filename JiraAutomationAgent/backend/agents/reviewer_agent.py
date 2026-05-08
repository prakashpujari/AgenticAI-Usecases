"""
Reviewer Agent — evaluates ticket drafts for quality and RBAC compliance.

Strict system prompt from specification (verbatim).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from .base_agent import BaseAgent
from ..governance.guardrails import safe_parse_json
from ..observability.tracer import log_layer, trace_agent

logger = logging.getLogger(__name__)

# ── Verbatim system prompt ────────────────────────────────────────────────────
_SYSTEM_PROMPT = """You are 'Jira Ticket Reviewer'.
Your role is to evaluate ticket drafts for clarity, completeness, AC quality, priority correctness, dedupe, and RBAC compliance.
Output JSON: { "status": "APPROVED" | "CHANGES_REQUIRED", "feedback": "..." }
You MUST NOT rewrite tickets.
You MUST NOT generate new tickets."""


class ReviewerAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("ReviewerAgent", _SYSTEM_PROMPT)

    @trace_agent(name="reviewer_agent")
    async def review(
        self,
        tickets: List[Dict[str, Any]],
        dedupe_matches: List[Dict[str, Any]],
        context: str,
    ) -> Dict[str, Any]:
        """
        Evaluate *tickets* and return a review decision.

        Returns:
            { "status": "APPROVED" | "CHANGES_REQUIRED", "feedback": "..." }
        """
        tickets_json = json.dumps(tickets, indent=2, ensure_ascii=False)
        dedupe_json = json.dumps(dedupe_matches, indent=2) if dedupe_matches else "[]"

        log_layer("AGENT", "Reviewer",
                  direction="→",
                  tickets=len(tickets),
                  dedupe_matches=len(dedupe_matches),
                  context_chars=len(context))

        user_message = (
            "Review the following Jira ticket draft(s) against ALL criteria below:\n\n"
            "Criteria:\n"
            "1. Clarity — Is the title and description unambiguous?\n"
            "2. Completeness — Are all required fields present and non-empty?\n"
            "3. Acceptance Criteria — Are they in valid Gherkin format (Given/When/Then)?\n"
            "4. Priority — Is the priority appropriate for the described problem?\n"
            "5. Labels — Are labels meaningful and consistently formatted?\n"
            "6. RBAC — No references to disallowed projects or fabricated Jira keys?\n"
            "7. Dedupe — Do any dedupe matches suggest this is a duplicate?\n\n"
            f"--- Potential Duplicates ---\n{dedupe_json}\n\n"
            f"--- RAG Context ---\n{context}\n\n"
            f"--- Ticket Draft(s) ---\n{tickets_json}\n\n"
            "Output exactly:\n"
            '{ "status": "APPROVED" | "CHANGES_REQUIRED", "feedback": "specific actionable feedback" }'
        )

        raw = await self.call(user_message, temperature=0.1, max_tokens=1024)
        parsed = safe_parse_json(raw)

        if not parsed or not isinstance(parsed, dict):
            logger.error("[ReviewerAgent] Failed to parse review JSON")
            return {
                "status": "CHANGES_REQUIRED",
                "feedback": "Review parsing failed. Please retry.",
            }

        if parsed.get("status") not in ("APPROVED", "CHANGES_REQUIRED"):
            parsed["status"] = "CHANGES_REQUIRED"
            parsed["feedback"] = (
                parsed.get("feedback", "") + " [status corrected by guardrail]"
            )

        feedback_snippet = parsed.get("feedback", "")[:120].replace("\n", " ")
        log_layer("AGENT", "Reviewer",
                  direction="←",
                  status=parsed["status"],
                  feedback_chars=len(parsed.get("feedback", "")),
                  feedback_preview=f'"{feedback_snippet}"')
        logger.info("[ReviewerAgent] Decision: %s", parsed["status"])
        return parsed


# Module-level singleton
reviewer_agent = ReviewerAgent()
