"""
Jira Writer Agent — maps validated ticket drafts to Jira API calls.

Strict system prompt from specification (verbatim).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from .base_agent import BaseAgent
from ..services.jira_service import jira_service
from ..observability.tracer import log_layer, trace_agent

logger = logging.getLogger(__name__)

# ── Verbatim system prompt ────────────────────────────────────────────────────
_SYSTEM_PROMPT = """You are 'Jira Writer'.
Your role is to map validated drafts to Jira fields and call Jira APIs.
No creative behavior."""


class JiraWriterAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("JiraWriterAgent", _SYSTEM_PROMPT)

    @trace_agent(name="jira_writer_agent")
    async def write(
        self,
        tickets: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Create each ticket in Jira via the REST API.
        Failures per ticket are captured and returned without stopping others.
        """
        created: list[Dict[str, Any]] = []

        titles = [t.get("title", "?")[:40] for t in tickets]
        log_layer("AGENT", "JiraWriter",
                  direction="→",
                  tickets=len(tickets),
                  titles=titles)

        for ticket in tickets:
            try:
                issue = await jira_service.create_issue(ticket)
                created.append(issue)
                logger.info("[JiraWriterAgent] Created %s", issue["jira_key"])
            except Exception as exc:
                # Per-ticket error capture: a failure on one ticket (e.g. a
                # duplicate key conflict) should not abort the remaining ones.
                # The error is surfaced in the response so the caller can retry.
                logger.error(
                    "[JiraWriterAgent] Failed to create '%s': %s",
                    ticket.get("title", "N/A"),
                    exc,
                )
                created.append(
                    {
                        "jira_key": None,
                        "issue_type": ticket.get("issue_type", ""),
                        "title": ticket.get("title", ""),
                        "url": None,
                        "error": str(exc),
                    }
                )

        created_keys = [i["jira_key"] for i in created if i.get("jira_key")]
        failed = [i["title"] for i in created if not i.get("jira_key")]
        log_layer("AGENT", "JiraWriter",
                  direction="←",
                  created=len(created_keys),
                  keys=created_keys,
                  failed=len(failed))
        return created


# Module-level singleton
jira_writer_agent = JiraWriterAgent()
