"""
Redis caching service with per-category key namespacing.

Key format:
  prompt:{sha256[:32]}    — LLM response cache
  embed:{sha256[:32]}     — embedding vector cache
  retrieve:{sha256[:32]}  — RAG retrieval result cache
  dedupe:{sha256[:32]}    — deduplication result cache

TTL defaults to settings.redis_ttl (24 h), configurable per call.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, List, Optional

import redis.asyncio as aioredis

from ..config import settings

logger = logging.getLogger(__name__)


class RedisService:
    """Async Redis client with structured caching helpers."""

    def __init__(self) -> None:
        self._client: Optional[aioredis.Redis] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def _get_client(self) -> aioredis.Redis:
        if self._client is None:
            self._client = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]

    async def _get(self, key: str) -> Optional[str]:
        # Wrapped in try/except so a missing Redis instance (local dev without
        # Docker) results in a cache miss rather than an unhandled exception
        # that would abort the entire pipeline.
        try:
            client = await self._get_client()
            return await client.get(key)
        except Exception as exc:
            logger.debug("[cache] Redis GET failed (cache miss): %s", exc)
            return None

    async def _setex(self, key: str, value: str, ttl: int) -> None:
        # Same rationale: a Redis outage during a cache write must be
        # treated as a non-fatal warning, not a hard failure.
        try:
            client = await self._get_client()
            await client.setex(key, ttl, value)
        except Exception as exc:
            logger.debug("[cache] Redis SET failed (skipping cache write): %s", exc)

    # ------------------------------------------------------------------
    # Prompt cache  (key: prompt:{hash})
    # ------------------------------------------------------------------

    async def get_prompt_cache(self, prompt: str) -> Optional[str]:
        key = f"prompt:{self._hash(prompt)}"
        value = await self._get(key)
        if value:
            logger.debug("[cache] prompt HIT  key=%s", key)
        return value

    async def set_prompt_cache(
        self, prompt: str, response: str, ttl: Optional[int] = None
    ) -> None:
        key = f"prompt:{self._hash(prompt)}"
        await self._setex(key, response, ttl or settings.redis_ttl)

    # ------------------------------------------------------------------
    # Embedding cache  (key: embed:{hash})
    # ------------------------------------------------------------------

    async def get_embedding_cache(self, text: str) -> Optional[List[float]]:
        key = f"embed:{self._hash(text)}"
        value = await self._get(key)
        if value:
            logger.debug("[cache] embed HIT  key=%s", key)
            return json.loads(value)
        return None

    async def set_embedding_cache(
        self, text: str, embedding: List[float], ttl: Optional[int] = None
    ) -> None:
        key = f"embed:{self._hash(text)}"
        await self._setex(key, json.dumps(embedding), ttl or settings.redis_ttl)

    # ------------------------------------------------------------------
    # Retrieval cache  (key: retrieve:{hash})
    # ------------------------------------------------------------------

    async def get_retrieval_cache(self, query: str) -> Optional[list]:
        key = f"retrieve:{self._hash(query)}"
        value = await self._get(key)
        if value:
            logger.debug("[cache] retrieval HIT  key=%s", key)
            return json.loads(value)
        return None

    async def set_retrieval_cache(
        self, query: str, results: list, ttl: Optional[int] = None
    ) -> None:
        key = f"retrieve:{self._hash(query)}"
        await self._setex(key, json.dumps(results), ttl or settings.redis_ttl)

    # ------------------------------------------------------------------
    # Dedupe cache  (key: dedupe:{hash})
    # ------------------------------------------------------------------

    async def get_dedupe_cache(self, text: str) -> Optional[list]:
        key = f"dedupe:{self._hash(text)}"
        value = await self._get(key)
        if value:
            logger.debug("[cache] dedupe HIT  key=%s", key)
            return json.loads(value)
        return None

    async def set_dedupe_cache(
        self, text: str, matches: list, ttl: Optional[int] = None
    ) -> None:
        key = f"dedupe:{self._hash(text)}"
        await self._setex(key, json.dumps(matches), ttl or settings.redis_ttl)

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        try:
            client = await self._get_client()
            return bool(await client.ping())
        except Exception as exc:
            logger.error("Redis health check failed: %s", exc)
            return False


# Module-level singleton
redis_service = RedisService()
