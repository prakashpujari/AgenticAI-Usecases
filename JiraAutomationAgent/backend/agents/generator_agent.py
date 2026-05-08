"""
Generator Agent — produces Jira ticket drafts from unstructured input.

Strict system prompt from specification (verbatim):
  "You are 'Jira AI Automation Assistant'. ..."
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from .base_agent import BaseAgent
from ..governance.guardrails import safe_parse_json
from ..observability.tracer import log_layer, trace_agent

logger = logging.getLogger(__name__)

# ── Verbatim system prompt from specification ─────────────────────────────────
_SYSTEM_PROMPT = """You are 'Jira AI Automation Assistant'.
Your role is to generate high-quality Jira ticket drafts from unstructured inputs.
You MUST follow RBAC constraints and project context.
You MUST output valid JSON in the required schema.
You MUST NOT fabricate Jira keys, systems, or data outside context.
You MUST NOT leak PII.
You MUST NOT perform review, refinement, or explanation tasks."""

# ── Required output schema (injected into every user message) ─────────────────
_OUTPUT_SCHEMA = """
Required JSON output schema:
{
  "tickets": [
    {
      "issue_type": "Epic | Story | Bug | Task | Sub-task",
      "title": "string (5–255 chars)",
      "summary": "string",
      "description": "string (detailed, markdown ok)",
      "acceptance_criteria": [
        {
          "scenario": "string",
          "given": "string",
          "when": "string",
          "then": "string"
        }
      ],
      "priority": "P0 | P1 | P2 | P3",
      "priority_reasoning": "string",
      "labels": ["string"],
      "linked_epic_key": "string | null",
      "assumptions": ["string"],
      "open_questions": ["string"],
      "source_references": ["string"],
      "project_key": "string (one of the allowed projects)"
    }
  ]
}
"""


class GeneratorAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("GeneratorAgent", _SYSTEM_PROMPT)

    @trace_agent(name="generator_agent")
    async def generate(
        self,
        input_text: str,
        context: str,
        rbac_context: str,
    ) -> List[Dict[str, Any]]:
        """
        Generate Jira ticket drafts for *input_text*.

        Args:
            input_text:   Normalised + PII-redacted user input.
            context:      Formatted RAG context (similar existing issues).
            rbac_context: RBAC constraints block to prefix the prompt.
        """
        user_message = (
            # RBAC block comes first so the LLM reads constraints before
            # it sees any user-supplied text, reducing the chance of
            # ignoring the restrictions due to anchoring on the input.
            f"{rbac_context}\n\n"
            f"--- RAG Context (existing similar issues for reference) ---\n"
            f"{context}\n\n"
            f"{_OUTPUT_SCHEMA}\n"
            f"--- User Input ---\n"
            f"{input_text}\n\n"
            "Instructions:\n"
            "1. Infer the correct Jira issue type(s) from the input.\n"
            "2. For Bugs: include steps to reproduce and expected vs actual behaviour.\n"
            "3. For Stories / Tasks: include detailed Gherkin acceptance criteria.\n"
            "4. For Epics: include high-level description and mention expected child stories.\n"
            "5. Use only allowed project keys from the RBAC context.\n"
            # Prevents the model from blindly copying RAG example keys as
            # parent epic links, which would create invalid Jira references.
            "6. Do NOT copy Jira keys from the RAG context as linked_epic_key unless explicitly mentioned.\n"
        )

        # Context metrics for the entry log
        rag_chunks = context.count("\n1.") + context.count("\n2.") + context.count("\n3.")
        log_layer("AGENT", "Generator",
                  direction="→",
                  input_chars=len(input_text),
                  context_chunks=rag_chunks,
                  prompt_chars=len(user_message))

        raw = await self.call(user_message, temperature=0.3, max_tokens=4096)
        parsed = safe_parse_json(raw)
        if not parsed:
            logger.error("[GeneratorAgent] Failed to parse JSON response")
            return []

        tickets = parsed.get("tickets", [])
        if not isinstance(tickets, list):
            return []

        titles = [
            f"{t.get('title','?')[:40]}({t.get('issue_type','?')}/{t.get('priority','?')})"
            for t in tickets
        ]
        log_layer("AGENT", "Generator",
                  direction="←",
                  tickets=len(tickets),
                  drafts=titles)
        logger.info("[GeneratorAgent] Generated %d ticket(s)", len(tickets))
        return tickets


# Module-level singleton
generator_agent = GeneratorAgent()
