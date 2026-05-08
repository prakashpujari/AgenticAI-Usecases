from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from app.core.logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


async def retry_with_backoff(
    coro_fn: Callable[..., Awaitable[T]],
    *args: Any,
    max_attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 30.0,
    jitter: bool = True,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
    **kwargs: Any,
) -> T:
    """
    Retry an async callable with exponential backoff + jitter.

    Args:
        coro_fn: The async callable to retry.
        max_attempts: Total attempts (including the first).
        base_delay: Initial delay in seconds.
        max_delay: Cap on delay seconds.
        jitter: Add random ±30 % jitter to avoid thundering-herd.
        retryable_exceptions: Only retry on these exception types.
    """
    last_exc: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            return await coro_fn(*args, **kwargs)
        except retryable_exceptions as exc:
            last_exc = exc
            if attempt == max_attempts:
                break

            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            if jitter:
                delay *= 0.7 + random.random() * 0.6  # ±30 % jitter

            logger.warning(
                "retry_attempt",
                attempt=attempt,
                max_attempts=max_attempts,
                delay_s=round(delay, 2),
                error=str(exc),
            )
            await asyncio.sleep(delay)

    raise last_exc or RuntimeError("Retry exhausted with no exception captured")
