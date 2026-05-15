"""
api/cache.py
─────────────
Two-layer response cache for the Q&A pipeline:
  1. Redis (primary) — persistent, shared across restarts and processes.
     Used in production when REDIS_URL is configured.
  2. In-memory LRU dict (fallback) — ephemeral, per-process.
     Kicks in automatically when Redis is unreachable or not configured,
     so the second identical request is still fast in local dev.

Cache key
─────────
    cache:qa:{sha256(content + output_mode + str(num_questions))[:32]}

Public API
──────────
    make_cache_key(source, output_mode, num_questions) → str
    get_cached(key)                                    → str | None
    set_cached(key, markdown)                          → None
    cache_enabled()                                    → bool
"""

import hashlib
import logging
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Optional

import config

logger = logging.getLogger("qa_agent.cache")

# ── In-memory LRU fallback ────────────────────────────────────────────────────
# Holds up to 100 results in memory. When Redis is unreachable the UI still
# sees a cache hit on the second identical request within the same process.
_MEM_MAX   = 100
_mem_store: OrderedDict[str, str] = OrderedDict()
_mem_lock  = threading.Lock()


def _mem_get(key: str) -> Optional[str]:
    with _mem_lock:
        if key in _mem_store:
            _mem_store.move_to_end(key)   # mark as recently used
            logger.info("Cache HIT  (memory)  key=%s", key)
            return _mem_store[key]
    return None


def _mem_set(key: str, value: str) -> None:
    with _mem_lock:
        if key in _mem_store:
            _mem_store.move_to_end(key)
        _mem_store[key] = value
        if len(_mem_store) > _MEM_MAX:
            _mem_store.popitem(last=False)   # evict oldest
    logger.info("Cache SET  (memory)  key=%s", key)


# ── Redis connection (module-level singleton) ─────────────────────────────────
# One connection pool shared for the lifetime of the process.
# Re-created automatically if the connection is lost.
_redis_client = None
_redis_lock   = threading.Lock()


def cache_enabled() -> bool:
    return config.CACHE_TTL > 0   # always True; Redis just upgrades to persistent


def _get_redis():
    """Return a live Redis client, or None if Redis is unreachable."""
    global _redis_client
    if not config.REDIS_URL:
        return None
    # Fast path — reuse existing connection
    if _redis_client is not None:
        return _redis_client
    with _redis_lock:
        if _redis_client is not None:
            return _redis_client
        try:
            import redis as redis_lib
            client = redis_lib.from_url(
                config.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            client.ping()
            _redis_client = client
            logger.info("Redis cache connected: %s", config.REDIS_URL.split("@")[-1])
            return _redis_client
        except Exception as exc:
            logger.warning("Redis unavailable (%s) — using in-memory cache", exc)
            return None


# ── Public API ────────────────────────────────────────────────────────────────

def make_cache_key(source: str, output_mode: str, num_questions: int) -> str:
    """Deterministic cache key: sha256(file_bytes_or_url | mode | n)[:32]."""
    path = Path(source)
    if path.exists() and path.is_file():
        try:
            source_bytes = path.read_bytes()
        except OSError:
            source_bytes = source.encode()
    else:
        source_bytes = source.encode()

    payload = source_bytes + f"|{output_mode}|{num_questions}".encode()
    digest  = hashlib.sha256(payload).hexdigest()[:32]
    return f"cache:qa:{digest}"


def get_cached(key: str) -> Optional[str]:
    """Return cached markdown, or None on miss. Checks Redis then memory."""
    if config.CACHE_TTL <= 0:
        return None

    # 1. Try Redis
    r = _get_redis()
    if r is not None:
        try:
            value = r.get(key)
            if value:
                logger.info("Cache HIT  (redis)   key=%s", key)
                return value
            logger.debug("Cache MISS (redis)   key=%s", key)
        except Exception as exc:
            logger.warning("Redis get failed: %s — falling back to memory", exc)

    # 2. Fallback: in-memory LRU
    return _mem_get(key)


def set_cached(key: str, markdown: str) -> None:
    """Store markdown in Redis (primary) and in-memory LRU (fallback)."""
    if config.CACHE_TTL <= 0:
        return

    # Always write to memory so local dev benefits immediately
    _mem_set(key, markdown)

    # Also write to Redis when available
    r = _get_redis()
    if r is not None:
        try:
            r.setex(key, config.CACHE_TTL, markdown)
            logger.info("Cache SET  (redis)   key=%s  ttl=%ds", key, config.CACHE_TTL)
        except Exception as exc:
            logger.warning("Redis set failed: %s", exc)
