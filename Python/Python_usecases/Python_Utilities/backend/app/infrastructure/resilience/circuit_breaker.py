from __future__ import annotations

import asyncio
import enum
import time
from typing import Any, Callable, Awaitable

from app.core.exceptions import CircuitOpenError
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class CircuitState(str, enum.Enum):
    CLOSED = "CLOSED"       # Normal operation
    OPEN = "OPEN"           # Failing; reject fast
    HALF_OPEN = "HALF_OPEN" # Probe to see if service recovered


class CircuitBreaker:
    """
    Simple async circuit breaker.

    Transitions:
      CLOSED  → OPEN       after `failure_threshold` consecutive failures
      OPEN    → HALF_OPEN  after `recovery_timeout` seconds
      HALF_OPEN → CLOSED   on successful probe
      HALF_OPEN → OPEN     on failed probe
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
    ) -> None:
        self.name = name
        self._threshold = failure_threshold
        self._recovery_timeout = recovery_timeout

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float | None = None

    @property
    def state(self) -> CircuitState:
        if (
            self._state == CircuitState.OPEN
            and self._last_failure_time is not None
            and time.monotonic() - self._last_failure_time >= self._recovery_timeout
        ):
            self._state = CircuitState.HALF_OPEN
            logger.info("circuit_half_open", circuit=self.name)
        return self._state

    async def call(
        self,
        coro_fn: Callable[..., Awaitable[Any]],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if self.state == CircuitState.OPEN:
            raise CircuitOpenError(f"Circuit '{self.name}' is OPEN")

        try:
            result = await coro_fn(*args, **kwargs)
            self._on_success()
            return result
        except CircuitOpenError:
            raise
        except Exception as exc:
            self._on_failure(exc)
            raise

    def _on_success(self) -> None:
        if self._state == CircuitState.HALF_OPEN:
            logger.info("circuit_closed", circuit=self.name)
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None

    def _on_failure(self, exc: Exception) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        logger.warning(
            "circuit_failure",
            circuit=self.name,
            failures=self._failure_count,
            error=str(exc),
        )
        if self._failure_count >= self._threshold:
            self._state = CircuitState.OPEN
            logger.error("circuit_opened", circuit=self.name, failures=self._failure_count)


# ── Registry ──────────────────────────────────────────────────────────────────

_registry: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str, **kwargs: Any) -> CircuitBreaker:
    if name not in _registry:
        _registry[name] = CircuitBreaker(name, **kwargs)
    return _registry[name]
