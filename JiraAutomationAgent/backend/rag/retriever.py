"""
RAG Retriever: Pinecone retrieval with Redis caching and structured context formatting.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from ..services.pinecone_service import pinecone_service
from ..services.redis_service import redis_service
from ..observability.tracer import log_cache_event, log_layer, trace_retrieval

logger = logging.getLogger(__name__)


class RAGRetriever:
    """
    Retrieves relevant Jira issues from Pinecone for RAG augmentation.
    Results are cached in Redis to avoid redundant vector lookups.
    """

    @trace_retrieval(name="pinecone_rag_retrieval")
    async def retrieve(
        self,
        query: str,
        top_k: int = 10,  # fetch top-10, then rerank down to top-5 in the caller
        filter: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve similar Jira issues for the given *query*.
        Redis is checked first; Pinecone is queried on a cache miss.
        """
        # Cache-aside pattern: check Redis before hitting Pinecone.
        # Retrieval results are stable for the TTL window (24 h by default),
        # which is acceptable for a Jira knowledge base that changes slowly.
        cached = await redis_service.get_retrieval_cache(query)
        if cached is not None:
            log_cache_event("retrieval", query, hit=True)
            log_layer("RAG", "Retriever",
                      cache="HIT",
                      hits=len(cached),
                      query=f'"{query[:50]}..."')
            return cached

        log_cache_event("retrieval", query, hit=False)

        t0 = time.monotonic()
        results = await pinecone_service.query_for_retrieval(
            text=query,
            top_k=top_k,
            filter=filter,
        )
        latency = time.monotonic() - t0

        await redis_service.set_retrieval_cache(query, results)

        top_keys = [
            f"{r.get('jira_key','?')}({r.get('similarity_score',0):.3f})"
            for r in results[:5]
        ]
        log_layer("RAG", "Retriever",
                  cache="MISS",
                  hits=len(results),
                  top=top_keys,
                  latency_s=f"{latency:.2f}")
        logger.info("[RAGRetriever] Retrieved %d items for query (%.60s)", len(results), query)
        return results

    # ------------------------------------------------------------------

    def format_context(self, results: List[Dict[str, Any]]) -> str:
        """
        Render retrieved issues as a compact, LLM-friendly context block.
        Only the top-5 are surfaced to keep prompt sizes manageable.
        """
        if not results:
            return "No similar issues found in the knowledge base."

        lines = ["=== Similar Jira Issues (RAG Context) ==="]
        # Slice to top-5: the reranker already ordered by relevance, so
        # cutting here balances context quality against prompt token cost.
        for i, r in enumerate(results[:5], start=1):
            lines.append(
                f"\n{i}. [{r.get('jira_key', 'N/A')}] {r.get('title', '')}\n"
                f"   Type: {r.get('issue_type', 'N/A')} | "
                f"Priority: {r.get('priority', 'N/A')} | "
                f"Score: {r.get('similarity_score', 0):.2f}\n"
                f"   Summary: {r.get('summary', '')[:150]}"
            )
        lines.append("\n=== End RAG Context ===")
        return "\n".join(lines)


# Module-level singleton
rag_retriever = RAGRetriever()
