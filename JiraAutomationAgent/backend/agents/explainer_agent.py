"""
Explainer Agent — coaches Product Owners on ticket quality principles.

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
_SYSTEM_PROMPT = """You are 'Ticket Explainer Coach'.
Your role is to teach POs how to create good tickets.
Output JSON: { "principles": [...], "applied_to_this_ticket": [...] }
You MUST NOT modify tickets."""


class ExplainerAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("ExplainerAgent", _SYSTEM_PROMPT)

    @trace_agent(name="explainer_agent")
    async def explain(
        self,
        tickets: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Generate PO coaching output for *tickets*.

        Returns:
            {
              "principles": ["..."],                  # 5-7 general principles
              "applied_to_this_ticket": ["..."]        # Ticket-specific application
            }
        """
        tickets_json = json.dumps(tickets, indent=2, ensure_ascii=False)

        log_layer("AGENT", "Explainer",
                  direction="→",
                  tickets=len(tickets))

        user_message = (
            "Analyse the following Jira ticket draft(s) and produce coaching output.\n\n"
            f"--- Ticket Draft(s) ---\n{tickets_json}\n\n"
            "Provide:\n"
            "1. 5–7 general principles for creating high-quality Jira tickets.\n"
            "2. For each principle, a concrete observation about how it applies "
            "(positively or negatively) to the tickets above.\n\n"
            "Output JSON:\n"
            "{\n"
            '  "principles": ["string — general principle"],\n'
            '  "applied_to_this_ticket": ["string — specific observation with ticket reference"]\n'
            "}"
        )

        raw = await self.call(user_message, temperature=0.3, max_tokens=2048)
        parsed = safe_parse_json(raw)

        if not parsed or not isinstance(parsed, dict):
            logger.warning("[ExplainerAgent] Failed to parse, returning defaults")
            return {
                "principles": [
                    "Keep titles concise and action-oriented.",
                    "Write acceptance criteria in Gherkin (Given/When/Then).",
                    "Assign realistic priority with clear reasoning.",
                    "List open questions and assumptions explicitly.",
                    "Avoid vague language — prefer measurable outcomes.",
                ],
                "applied_to_this_ticket": [
                    "Review the generated ticket for improvements using the principles above."
                ],
            }

        log_layer("AGENT", "Explainer",
                  direction="←",
                  principles=len(parsed.get("principles", [])),
                  applied=len(parsed.get("applied_to_this_ticket", [])))
        logger.info("[ExplainerAgent] Explanation generated")
        return parsed


# Module-level singleton
explainer_agent = ExplainerAgent()
