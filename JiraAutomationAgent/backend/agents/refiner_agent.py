"""
Refiner Agent — improves ticket drafts based on reviewer feedback.

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
_SYSTEM_PROMPT = """You are 'Jira Ticket Refiner'.
Your role is to improve ticket drafts based on reviewer feedback.
Output JSON: { "tickets": [...] }
You MUST NOT approve or reject tickets."""


class RefinerAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("RefinerAgent", _SYSTEM_PROMPT)

    @trace_agent(name="refiner_agent")
    async def refine(
        self,
        tickets: List[Dict[str, Any]],
        feedback: str,
        rbac_context: str,
    ) -> List[Dict[str, Any]]:
        """
        Apply reviewer *feedback* to improve *tickets*.
        Returns the refined ticket list (same schema as input).
        """
        tickets_json = json.dumps(tickets, indent=2, ensure_ascii=False)

        log_layer("AGENT", "Refiner",
                  direction="→",
                  tickets=len(tickets),
                  feedback_chars=len(feedback),
                  feedback_preview=f'"{feedback[:80].replace(chr(10)," ")}"')

        user_message = (
            f"{rbac_context}\n\n"
            "Apply ALL of the following reviewer feedback to improve the ticket drafts.\n"
            "Preserve the exact JSON schema. Do not add or remove tickets unless instructed.\n\n"
            f"--- Reviewer Feedback ---\n{feedback}\n\n"
            f"--- Current Ticket Drafts ---\n{tickets_json}\n\n"
            'Output JSON: { "tickets": [ ...improved tickets... ] }'
        )

        # Disable caching for refinement — each iteration has different
        # feedback text, so the prompt always differs from the previous call.
        # Caching here would return a stale response on the second refine loop.
        raw = await self.call(user_message, temperature=0.2, max_tokens=4096, use_cache=False)
        parsed = safe_parse_json(raw)

        if not parsed or not isinstance(parsed, dict):
            # Parsing failure — return the originals unchanged so the review
            # loop can continue with valid data rather than an empty list.
            logger.error("[RefinerAgent] Failed to parse refined JSON, returning originals")
            return tickets

        refined = parsed.get("tickets", [])
        if isinstance(refined, list) and refined:
            log_layer("AGENT", "Refiner",
                      direction="←",
                      refined=len(refined))
            logger.info("[RefinerAgent] Refined %d ticket(s)", len(refined))
            return refined

        logger.warning("[RefinerAgent] Empty tickets in response, returning originals")
        return tickets


# Module-level singleton
refiner_agent = RefinerAgent()
