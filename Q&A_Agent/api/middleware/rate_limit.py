"""
api/middleware/rate_limit.py
─────────────────────────────
Sliding-window rate limiter + token-bucket spike arrest backed by Redis.

Falls back to a thread-safe in-memory store when REDIS_URL is not configured,
so the application works in local development without a Redis instance.

Rate limit:  10 successful requests per rolling 60-minute window per identity.
Spike arrest: 3 requests/second burst max per identity (token bucket).

Identity priority (most → least specific):
  1. Verified JWT sub claim
  2. X-Device-Fingerprint header (SHA-256, sent by frontend)
  3. IP /24 subnet (IPv4) or /48 prefix (IPv6)
"""

import hashlib
import hmac
import math
import threading
import time
from typing import TypedDict

from fastapi import Request

import config
from api.errors import E, api_error

# ── Config ────────────────────────────────────────────────────────────────────
RATE_LIMIT_MAX    = int(config.RATE_LIMIT_MAX)    # 10 requests
RATE_LIMIT_WINDOW = int(config.RATE_LIMIT_WINDOW) # 3600 seconds
BURST_MAX         = int(config.BURST_MAX)          # 3 tokens
BURST_REFILL_RATE = float(config.BURST_REFILL_RATE)# tokens per second
GLOBAL_LLM_MAX    = int(config.GLOBAL_LLM_MAX)     # per-minute global cap


class RateLimitResult(TypedDict):
    allowed: bool
    count: int
    retry_after_seconds: int


# ── Redis client (lazy, optional) ─────────────────────────────────────────────
_redis_client = None
_redis_lock   = threading.Lock()


def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    if not config.REDIS_URL:
        return None
    with _redis_lock:
        if _redis_client is not None:
            return _redis_client
        try:
            import redis as redis_lib
            _redis_client = redis_lib.from_url(
                config.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            _redis_client.ping()
        except Exception:
            _redis_client = None
    return _redis_client


# ── In-memory fallback (local dev / Redis unavailable) ───────────────────────
_mem_store: dict[str, float | int] = {}
_mem_lock = threading.Lock()


def _mem_incr(key: str, ttl: int) -> int:
    with _mem_lock:
        now = time.time()
        # Expire old keys lazily
        expired = [k for k, v in _mem_store.items()
                   if isinstance(v, tuple) and now > v[1]]
        for k in expired:
            del _mem_store[k]

        entry = _mem_store.get(key)
        if isinstance(entry, tuple):
            count, expires_at = entry
            if now > expires_at:
                count = 0
        else:
            count = 0
        count += 1
        _mem_store[key] = (count, now + ttl)
        return count


def _mem_get(key: str) -> tuple[float, float] | None:
    with _mem_lock:
        return _mem_store.get(key)


def _mem_set(key: str, data: dict, ttl: int) -> None:
    with _mem_lock:
        _mem_store[key] = (data, time.time() + ttl)


# ── Identity extraction ───────────────────────────────────────────────────────
def _hmac_hex(value: str) -> str:
    secret = config.IDENTITY_HMAC_SECRET.encode()
    return hmac.new(secret, value.encode(), hashlib.sha256).hexdigest()[:16]


def extract_identity(request: Request) -> str:
    # 1. JWT Bearer token
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer ") and len(auth) > 10:
        return f"jwt:{_hmac_hex(auth[7:])}"

    # 2. Device fingerprint (64-char hex SHA-256 from frontend)
    fp = request.headers.get("X-Device-Fingerprint", "")
    if len(fp) == 64 and all(c in "0123456789abcdef" for c in fp.lower()):
        return f"fp:{_hmac_hex(fp)}"

    # 3. IP /24 subnet
    ip = (request.client.host if request.client else None) or "0.0.0.0"
    parts = ip.split(".")
    if len(parts) == 4:
        subnet = ".".join(parts[:3]) + ".0"
    else:
        # IPv6: use /48 prefix
        subnet = ":".join(ip.split(":")[:3])
    return f"subnet:{_hmac_hex(subnet)}"


# ── Spike arrest (token bucket) ───────────────────────────────────────────────
def check_spike_arrest(identity: str, request_id: str | None = None) -> None:
    """Raise 429 SPIKE_ARREST if bursting beyond BURST_MAX req/sec."""
    now  = time.time()
    r    = _get_redis()
    key  = f"spike:{identity}"

    if r:
        try:
            raw = r.hgetall(key)
            tokens     = float(raw.get("tokens",     BURST_MAX))
            last_refill = float(raw.get("last_refill", now))
        except Exception:
            return  # Redis error → fail open

        elapsed = now - last_refill
        tokens  = min(BURST_MAX, tokens + elapsed * BURST_REFILL_RATE)

        if tokens < 1:
            api_error(429, E.SPIKE_ARREST,
                      "Too many requests at once. Please wait a moment.",
                      retry_after=5, request_id=request_id)

        tokens -= 1
        try:
            pipe = r.pipeline()
            pipe.hset(key, mapping={"tokens": round(tokens, 4), "last_refill": now})
            pipe.expire(key, 10)
            pipe.execute()
        except Exception:
            pass
    else:
        # In-memory token bucket
        key_mem = f"spike_mem:{identity}"
        entry = _mem_get(key_mem)
        if entry and isinstance(entry, tuple):
            data, _ = entry
            tokens     = float(data.get("tokens",     BURST_MAX))
            last_refill = float(data.get("last_refill", now))
        else:
            tokens, last_refill = float(BURST_MAX), now

        elapsed = now - last_refill
        tokens  = min(BURST_MAX, tokens + elapsed * BURST_REFILL_RATE)

        if tokens < 1:
            api_error(429, E.SPIKE_ARREST,
                      "Too many requests at once. Please wait a moment.",
                      retry_after=5, request_id=request_id)

        tokens -= 1
        _mem_set(key_mem, {"tokens": tokens, "last_refill": now}, 10)


# ── Sliding window rate limiter ───────────────────────────────────────────────
def check_rate_limit(identity: str, request_id: str | None = None) -> int:
    """
    Increment and check the sliding-window counter.
    Returns remaining requests allowed this window.
    Raises 429 RATE_LIMIT_EXCEEDED if the limit is reached.
    """
    now          = time.time()
    window_start = math.floor(now / RATE_LIMIT_WINDOW) * RATE_LIMIT_WINDOW
    reset_at     = window_start + RATE_LIMIT_WINDOW
    key          = f"rate_limit:{identity}:{int(window_start)}"

    r = _get_redis()
    if r:
        try:
            pipe  = r.pipeline()
            pipe.incr(key)
            pipe.expire(key, RATE_LIMIT_WINDOW)
            count, _ = pipe.execute()
        except Exception:
            return RATE_LIMIT_MAX  # Redis error → fail open

        # Global LLM cost guard
        global_key = f"global:llm_calls:{int(math.floor(now / 60))}"
        try:
            g_count = r.incr(global_key)
            r.expire(global_key, 120)
            if g_count > GLOBAL_LLM_MAX:
                api_error(503, E.GLOBAL_CAPACITY,
                          "Service is at capacity. Please retry in a minute.",
                          retry_after=60, request_id=request_id)
        except Exception:
            pass
    else:
        count = _mem_incr(key, RATE_LIMIT_WINDOW)

    if count > RATE_LIMIT_MAX:
        retry_after = int(reset_at - now)
        api_error(429, E.RATE_LIMIT_EXCEEDED,
                  f"You've used all {RATE_LIMIT_MAX} requests for this hour. "
                  f"Try again in {retry_after // 60} minute(s).",
                  retry_after=retry_after,
                  request_id=request_id)

    return RATE_LIMIT_MAX - count


def add_rate_limit_headers(response, remaining: int, reset_at: int) -> None:
    """Attach standard rate-limit headers to a response."""
    response.headers["X-RateLimit-Limit"]     = str(RATE_LIMIT_MAX)
    response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
    response.headers["X-RateLimit-Reset"]     = str(reset_at)
