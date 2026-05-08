from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.config import get_settings
from app.core.logging_config import get_logger

settings = get_settings()
logger = get_logger(__name__)


class IdempotencyRepository:
    """
    Stores idempotency-key → response pairs.
    Uses Redis when available, falls back to an in-memory dict (dev/test only).
    """

    def __init__(self, redis_client: Any | None = None) -> None:
        self._redis = redis_client
        self._mem: dict[str, dict[str, Any]] = {}

    async def get(self, key: str) -> dict[str, Any] | None:
        if self._redis is not None:
            raw = await self._redis.get(f"idem:{key}")
            if raw:
                return json.loads(raw)  # type: ignore[no-any-return]
            return None
        return self._mem.get(key)

    async def set(
        self,
        key: str,
        response_body: dict[str, Any],
        status_code: int,
    ) -> None:
        record = {
            "status_code": status_code,
            "body": response_body,
            "stored_at": datetime.now(UTC).isoformat(),
        }
        if self._redis is not None:
            await self._redis.setex(
                f"idem:{key}",
                settings.idempotency_ttl_seconds,
                json.dumps(record),
            )
        else:
            self._mem[key] = record

    async def exists(self, key: str) -> bool:
        return await self.get(key) is not None
