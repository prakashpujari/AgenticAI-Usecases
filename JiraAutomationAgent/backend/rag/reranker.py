"""
LLM-based cross-encoder reranker for RAG retrieval results.
Uses a lightweight GPT call to re-score candidate passages by relevance.
Falls back to the original ordering on failure.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

from openai import AsyncOpenAI

from ..config import settings
from ..observability.tracer import log_layer, log_layer_warn

logger = logging.getLogger(__name__)


class LLMReranker:
    """
    Scores and reorders retrieval candidates using an LLM as a cross-encoder.
    Keeps the top-*k* most relevant results.
    """

    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Return the *top_k* candidates ordered by LLM-assessed relevance.
        If fewer than *top_k* candidates are provided they are returned as-is.
        """
        if not candidates or len(candidates) <= top_k:
            return candidates

        candidate_lines = [
            f"{i}. [{c.get('jira_key', 'N/A')}] {c.get('title', '')}: "
            f"{c.get('summary', '')[:100]}"
            for i, c in enumerate(candidates)
        ]
        candidates_text = "\n".join(candidate_lines)

        prompt = (
            f"Query: {query}\n\n"
            f"Rank the following Jira issues by relevance to the query.\n"
            f"Return ONLY comma-separated 0-based indices of the top {top_k} "
            f"most relevant issues (most relevant first). "
            f"Example for 5 results: 2,0,4,1,3\n\n"
            f"Candidates:\n{candidates_text}"
        )

        try:
            t0 = time.monotonic()
            response = await self._client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a relevance ranking assistant. "
                            "Output only comma-separated indices. No explanation."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=60,
                temperature=0,
            )
            latency = time.monotonic() - t0

            raw = response.choices[0].message.content.strip()
            indices = [
                int(x.strip())
                for x in raw.split(",")
                if x.strip().lstrip("-").isdigit()
            ]

            reranked: list[Dict[str, Any]] = []
            seen: set[int] = set()
            for idx in indices:
                if 0 <= idx < len(candidates) and idx not in seen:
                    reranked.append(candidates[idx])
                    seen.add(idx)
                if len(reranked) >= top_k:
                    break

            # Back-fill with remaining candidates to reach top_k
            for i, c in enumerate(candidates):
                if len(reranked) >= top_k:
                    break
                if i not in seen:
                    reranked.append(c)

            tok = response.usage.total_tokens if response.usage else 0
            log_layer("RAG", "Reranker",
                      candidates_in=len(candidates),
                      top_k=top_k,
                      llm_indices=indices[:top_k],
                      tokens=tok,
                      latency_s=f"{latency:.2f}")
            logger.debug("[Reranker] %d → %d candidates after reranking", len(candidates), len(reranked))
            return reranked

        except Exception as exc:
            logger.warning("Reranking failed (%s); using original order", exc)
            return candidates[:top_k]


# Module-level singleton
reranker = LLMReranker()
