"""
Pinecone Memory Agent — embeds, upserts, and retrieves Jira issues.

Strict system prompt from specification (verbatim).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from .base_agent import BaseAgent
from ..services.pinecone_service import pinecone_service
from ..services.redis_service import redis_service
from ..observability.tracer import trace_agent, log_cache_event, log_layer, log_layer_warn
from ..config import settings

logger = logging.getLogger(__name__)

# ── Verbatim system prompt ────────────────────────────────────────────────────
_SYSTEM_PROMPT = """You are 'Pinecone Memory Agent'.
Your role is to embed, upsert, and retrieve Jira issues.
No creative behavior."""


class PineconeMemoryAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("PineconeMemoryAgent", _SYSTEM_PROMPT)

    # ------------------------------------------------------------------
    # Deduplication check
    # ------------------------------------------------------------------

    @trace_agent(name="pinecone_memory_dedupe")
    async def check_duplicates(
        self,
        input_text: str,
        threshold: float | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Check for duplicate Jira issues in Pinecone.
        Results are cached in Redis (key: dedupe:{hash}).
        """
        # Use caller-supplied threshold or fall back to the configured
        # global dedupe_threshold (typically 0.90 cosine similarity).
        threshold = threshold or settings.dedupe_threshold

        # Redis cache lookup — avoids a Pinecone query for repeated inputs
        # (e.g. user clicks "Generate" twice with the same text).
        cached = await redis_service.get_dedupe_cache(input_text)
        if cached is not None:
            log_cache_event("dedupe", input_text, hit=True)
            return cached

        log_cache_event("dedupe", input_text, hit=False)

        # Embed the input and query Pinecone for semantically close vectors.
        matches = await pinecone_service.query_similar(
            text=input_text,
            top_k=5,
            score_threshold=threshold,
        )

        await redis_service.set_dedupe_cache(input_text, matches)
        logger.info("[PineconeMemoryAgent] Dedupe: %d match(es) found", len(matches))
        return matches

    # ------------------------------------------------------------------
    # Upsert after creation
    # ------------------------------------------------------------------

    @trace_agent(name="pinecone_memory_upsert")
    async def upsert_issues(
        self,
        created_issues: List[Dict[str, Any]],
        ticket_drafts: List[Dict[str, Any]],
    ) -> None:
        """
        Upsert successfully created Jira issues into Pinecone for future
        retrieval and deduplication.
        """
        # Build a lookup from title → draft for metadata enrichment.
        # Title is used as the join key because it's the only stable
        # identifier shared between a created_issue and its draft.
        draft_by_title: dict[str, Dict[str, Any]] = {
            d.get("title", ""): d for d in ticket_drafts
        }

        for issue in created_issues:
            jira_key = issue.get("jira_key")
            if not jira_key:
                continue  # Skip failed creations (e.g. Jira returned an error)

            draft = draft_by_title.get(issue.get("title", ""), {})
            # Merge issue metadata with draft fields to create a rich vector
            # payload that supports both similarity search and metadata filtering.
            issue_data = {
                "title": issue.get("title", ""),
                "issue_type": issue.get("issue_type", ""),
                "summary": draft.get("summary", ""),
                "description": draft.get("description", ""),
                "priority": draft.get("priority", ""),
                "labels": draft.get("labels", []),
                "project_key": draft.get("project_key", ""),
                "status": "Open",
                "url": issue.get("url", ""),
            }

            try:
                await pinecone_service.upsert_issue(jira_key, issue_data)
                log_layer("AGENT", "PineconeMemory",
                          action="upsert_ok",
                          jira_key=jira_key,
                          title=f'"{issue_data.get("title","")[:50]}"')
            except Exception as exc:
                log_layer_warn("AGENT", "PineconeMemory",
                               action="upsert_failed",
                               jira_key=jira_key,
                               error=str(exc)[:120])
                logger.error(
                    "[PineconeMemoryAgent] Upsert failed for %s: %s", jira_key, exc
                )

        log_layer("AGENT", "PineconeMemory",
                  action="upsert_complete",
                  total=len(created_issues),
                  upserted=sum(
                      1 for i in created_issues if i.get("jira_key")
                  ))


# Module-level singleton
pinecone_memory_agent = PineconeMemoryAgent()
