import json
import redis
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from observability.logger import get_logger
from observability.breakers import redis_breaker

logger = get_logger("memory.redis")

_pool = redis.ConnectionPool(host="localhost", port=6379, decode_responses=True, max_connections=10)


def _get_client() -> redis.Redis:
    return redis.Redis(connection_pool=_pool)


@retry(
    retry=retry_if_exception_type(redis.RedisError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    reraise=True,
)
def get_memory(sid: str) -> list:
    def _read():
        r = _get_client()
        data = r.get(sid)
        return json.loads(data) if data else []

    return redis_breaker.call(_read)


@retry(
    retry=retry_if_exception_type(redis.RedisError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    reraise=True,
)
def save_memory(sid: str, q: str, a: str) -> None:
    def _write():
        r = _get_client()
        hist = get_memory(sid)
        hist.append({"q": q, "a": a})
        r.setex(sid, 3600, json.dumps(hist))

    redis_breaker.call(_write)
    logger.info("Session memory saved", extra={"session_id": sid})
