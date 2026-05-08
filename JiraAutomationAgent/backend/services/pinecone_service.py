"""
Pinecone vector database service.
Handles index initialisation, upserts, and similarity queries.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pinecone import Pinecone, ServerlessSpec

from ..config import settings
from .embedding_service import embedding_service

logger = logging.getLogger(__name__)

# Similarity threshold presets
_DEDUPE_THRESHOLD = settings.dedupe_threshold
_RETRIEVAL_THRESHOLD = 0.60


class PineconeService:
    """Pinecone client wrapper with async-friendly interface."""

    def __init__(self) -> None:
        self._pc = Pinecone(api_key=settings.pinecone_api_key)
        self._index = None

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    def _get_index(self):
        if self._index is None:
            # If PINECONE_HOST is explicitly set, use it directly — no control plane lookup needed.
            # This avoids Pinecone returning a stale/cached host URL after index recreation.
            if settings.pinecone_host:
                host = settings.pinecone_host
                logger.info("Connecting to Pinecone '%s' via pinecone_host=%s", settings.pinecone_index_name, host)
            else:
                # Fall back to describe_index (skip list_indexes to avoid stale host cache)
                try:
                    index_info = self._pc.describe_index(settings.pinecone_index_name)
                    host = index_info.host
                except Exception:
                    self._pc.create_index(
                        name=settings.pinecone_index_name,
                        dimension=settings.pinecone_dimension,
                        metric="cosine",
                        spec=ServerlessSpec(
                            cloud="aws",
                            region=settings.pinecone_environment,
                        ),
                    )
                    logger.info("Created Pinecone index: %s", settings.pinecone_index_name)
                    index_info = self._pc.describe_index(settings.pinecone_index_name)
                    host = index_info.host
                logger.info("Connected to Pinecone '%s' at %s", settings.pinecone_index_name, host)
            self._index = self._pc.Index(settings.pinecone_index_name, host=host)
        return self._index

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def upsert_issue(
        self, jira_key: str, issue_data: Dict[str, Any]
    ) -> None:
        """Embed *issue_data* and upsert to Pinecone."""
        text = f"{issue_data.get('title', '')} {issue_data.get('description', '')}"
        embedding = await embedding_service.embed(text)

        index = self._get_index()
        index.upsert(
            vectors=[
                {
                    "id": jira_key,
                    "values": embedding,
                    "metadata": {
                        "jira_key": jira_key,
                        "title": str(issue_data.get("title", ""))[:512],
                        "issue_type": str(issue_data.get("issue_type", "")),
                        "priority": str(issue_data.get("priority", "")),
                        "project_key": str(issue_data.get("project_key", "")),
                        "summary": str(issue_data.get("summary", ""))[:512],
                        "labels": issue_data.get("labels", []),
                        "status": str(issue_data.get("status", "Open")),
                        "url": str(issue_data.get("url", "")),
                    },
                }
            ]
        )
        logger.info("Upserted %s to Pinecone", jira_key)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def query_similar(
        self,
        text: str,
        top_k: int = 5,
        filter: Optional[Dict] = None,
        score_threshold: float = _DEDUPE_THRESHOLD,
    ) -> List[Dict[str, Any]]:
        """Return issues with cosine similarity >= *score_threshold*."""
        embedding = await embedding_service.embed(text)
        index = self._get_index()

        response = index.query(
            vector=embedding,
            top_k=top_k,
            include_metadata=True,
            filter=filter,
        )

        matches = []
        for match in response.matches:
            if match.score >= score_threshold:
                meta = match.metadata or {}
                matches.append(
                    {
                        "jira_key": meta.get("jira_key", match.id),
                        "title": meta.get("title", ""),
                        "summary": meta.get("summary", ""),
                        "similarity_score": round(match.score, 4),
                        "issue_type": meta.get("issue_type", ""),
                        "priority": meta.get("priority", ""),
                        "url": meta.get("url", ""),
                        "metadata": meta,
                    }
                )
        return matches

    async def query_for_retrieval(
        self,
        text: str,
        top_k: int = 10,
        filter: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        """RAG-oriented query with a lower similarity threshold."""
        return await self.query_similar(
            text,
            top_k=top_k,
            filter=filter,
            score_threshold=_RETRIEVAL_THRESHOLD,
        )

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        try:
            self._get_index()
            return True
        except Exception as exc:
            logger.error("Pinecone health check failed: %s", exc)
            return False


# Module-level singleton
pinecone_service = PineconeService()
