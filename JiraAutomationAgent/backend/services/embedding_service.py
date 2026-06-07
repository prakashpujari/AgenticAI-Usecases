"""
Embedding service using sentence-transformers (local, no API key needed).
Falls back to OpenAI if configured. All embed calls cached in Redis.
"""
from __future__ import annotations

import asyncio
import logging
from typing import List

from ..config import settings
from .redis_service import redis_service

logger = logging.getLogger(__name__)

# Try to use sentence-transformers for local embeddings (no API key)
try:
    from sentence_transformers import SentenceTransformer
    _SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    _SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning("sentence-transformers not installed. Install with: pip install sentence-transformers")

# Fallback to OpenAI if sentence-transformers not available
_OPENAI_AVAILABLE = bool(settings.openai_api_key)
if _OPENAI_AVAILABLE:
    try:
        from openai import AsyncOpenAI
    except ImportError:
        _OPENAI_AVAILABLE = False


class EmbeddingService:
    """Generate embeddings using sentence-transformers (local) or OpenAI (API)."""

    def __init__(self) -> None:
        # Prefer local embeddings (sentence-transformers) if available
        # Only fall back to OpenAI if local is not available and OpenAI key is set
        self.use_local = _SENTENCE_TRANSFORMERS_AVAILABLE
        self.use_openai = _OPENAI_AVAILABLE and not self.use_local

        if self.use_local:
            logger.info("Using local embeddings (sentence-transformers all-MiniLM-L6-v2)")
            logger.info("  - No API key required")
            logger.info("  - Runs on CPU/GPU locally")
            self.model = SentenceTransformer("all-MiniLM-L6-v2")
        elif self.use_openai:
            logger.info(f"Using OpenAI embeddings ({settings.openai_embedding_model})")
            self._openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
            self.model = settings.openai_embedding_model
        else:
            raise RuntimeError(
                "No embedding backend available. Install sentence-transformers: pip install sentence-transformers"
            )

    async def embed(self, text: str) -> List[float]:
        """Return embedding for *text*, served from cache when available."""
        cached = await redis_service.get_embedding_cache(text)
        if cached is not None:
            return cached

        if self.use_local:
            # Run in thread pool to avoid blocking async loop
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(None, self.model.encode, text)
            embedding_list = embedding.tolist() if hasattr(embedding, 'tolist') else list(embedding)
        else:
            response = await self._openai_client.embeddings.create(
                model=self.model,
                input=text,
            )
            embedding_list = response.data[0].embedding

        await redis_service.set_embedding_cache(text, embedding_list)
        return embedding_list

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Batch embed *texts*, consulting cache per item."""
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
            if self.use_local:
                loop = asyncio.get_event_loop()
                embeddings = await loop.run_in_executor(None, self.model.encode, uncached_texts)
                for j, embedding in enumerate(embeddings):
                    original_idx = uncached_indices[j]
                    embedding_list = embedding.tolist() if hasattr(embedding, 'tolist') else list(embedding)
                    results[original_idx] = embedding_list
                    await redis_service.set_embedding_cache(uncached_texts[j], embedding_list)
            else:
                response = await self._openai_client.embeddings.create(
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
