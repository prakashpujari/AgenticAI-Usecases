"""
Embedding service backed by OpenAI with Redis caching.
All embed calls are deduped against cache before hitting the API.
"""
from __future__ import annotations

import logging
from typing import List

from openai import AsyncOpenAI

from ..config import settings
from .redis_service import redis_service

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Generate OpenAI embeddings with transparent Redis caching."""

    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_embedding_model

    # ------------------------------------------------------------------

    async def embed(self, text: str) -> List[float]:
        """Return embedding for *text*, served from cache when available."""
        cached = await redis_service.get_embedding_cache(text)
        if cached is not None:
            return cached

        response = await self._client.embeddings.create(
            model=self.model,
            input=text,
        )
        embedding: List[float] = response.data[0].embedding
        await redis_service.set_embedding_cache(text, embedding)
        return embedding

    # ------------------------------------------------------------------

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Batch embed *texts*, consulting cache per item.
        Uncached items are sent as a single API request to minimise latency.
        """
        results: dict[int, List[float]] = {}
        uncached_texts: list[str] = []
        uncached_indices: list[int] = []

        for i, text in enumerate(texts):
            cached = await redis_service.get_embedding_cache(text)
            if cached is not None:
                results[i] = cached
            else:
                uncached_texts.append(text)
                uncached_indices.append(i)

        if uncached_texts:
            response = await self._client.embeddings.create(
                model=self.model,
                input=uncached_texts,
            )
            for j, embedding_data in enumerate(response.data):
                original_idx = uncached_indices[j]
                embedding = embedding_data.embedding
                results[original_idx] = embedding
                await redis_service.set_embedding_cache(uncached_texts[j], embedding)

        return [results[i] for i in range(len(texts))]


# Module-level singleton
embedding_service = EmbeddingService()
