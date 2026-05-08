from __future__ import annotations

from typing import Any

import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.logging_config import get_logger

settings = get_settings()
logger = get_logger(__name__)

_client: aioredis.Redis | None = None  # type: ignore[type-arg]


async def get_redis() -> aioredis.Redis:  # type: ignore[type-arg]
    global _client
    if _client is None:
        _client = aioredis.from_url(
            settings.redis_url,
            socket_timeout=settings.redis_socket_timeout,
            socket_connect_timeout=settings.redis_socket_connect_timeout,
            decode_responses=True,
        )
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


class RateLimiter:
    """
    Sliding-window rate limiter using Redis.
    Falls back gracefully (allow) if Redis is unavailable.
    """

    def __init__(self, redis: aioredis.Redis, limit: int, window_seconds: int = 60) -> None:  # type: ignore[type-arg]
        self._redis = redis
        self._limit = limit
        self._window = window_seconds

    async def is_allowed(self, key: str) -> tuple[bool, int]:
        """
        Returns (allowed, requests_remaining).
        Uses a simple fixed-window counter; swap for sliding-log if needed.
        """
        redis_key = f"rl:{key}"
        try:
            pipe = self._redis.pipeline()
            await pipe.incr(redis_key)
            await pipe.expire(redis_key, self._window)
            count_raw, _ = await pipe.execute()
            count = int(count_raw)
            remaining = max(0, self._limit - count)
            return count <= self._limit, remaining
        except Exception as exc:
            logger.warning("rate_limiter_redis_error", error=str(exc))
            return True, self._limit  # fail open


async def check_rate_limit(user_id: str) -> tuple[bool, int]:
    """Convenience wrapper; uses global Redis client."""
    redis = await get_redis()
    limiter = RateLimiter(redis, limit=settings.rate_limit_per_minute)
    return await limiter.is_allowed(user_id)
