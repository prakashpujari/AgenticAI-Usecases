"""
Circuit breakers for all external services.

What is a Circuit Breaker?
--------------------------
A circuit breaker is a resilience pattern that prevents an application from
repeatedly calling a failing service. Think of it like an electrical fuse:
  - CLOSED  (normal) : requests flow through to the service.
  - OPEN    (tripped): requests are rejected immediately — no network call made.
  - HALF-OPEN        : after reset_timeout seconds, one test request is allowed
                       through. If it succeeds the breaker resets to CLOSED;
                       if it fails it stays OPEN.

Flow for each breaker:
  - After FAIL_MAX consecutive failures → breaker OPENS.
  - After RESET_TIMEOUT seconds in OPEN state → enters HALF-OPEN.
  - First success in HALF-OPEN → CLOSES again.

Why per-service breakers?
  Different services have different reliability profiles.
  OpenAI needs a longer cooldown (60 s) because quota errors resolve slowly;
  Redis can recover faster (20 s).
"""
import pybreaker                          # third-party circuit breaker library
from observability.logger import get_logger

# Module-level logger — logs breaker events as structured JSON
logger = get_logger("circuit_breaker")


class _LoggingListener(pybreaker.CircuitBreakerListener):
    """
    A hook that pybreaker calls automatically when something notable happens.
    By subclassing CircuitBreakerListener we plug into the breaker lifecycle
    without changing any call-site code.
    """

    def __init__(self, name: str):
        # Store the service name so log messages identify which breaker fired
        self._name = name

    def state_change(self, cb, old_state, new_state):
        # Called whenever the breaker transitions between CLOSED / OPEN / HALF-OPEN.
        # 'cb' is the CircuitBreaker instance itself (not used here).
        logger.warning(
            "Circuit breaker state changed",
            extra={"breaker": self._name, "from": str(old_state), "to": str(new_state)},
        )

    def failure(self, cb, exc):
        # Called every time a wrapped call raises an exception.
        # Lets us log the error before pybreaker increments its failure counter.
        logger.error(
            "Circuit breaker recorded failure",
            extra={"breaker": self._name, "error": str(exc)},
        )


def _make(name: str, fail_max: int = 3, reset_timeout: int = 30) -> pybreaker.CircuitBreaker:
    """
    Factory helper — creates a configured CircuitBreaker with our logging listener.

    Args:
        name:          Human-readable name shown in logs and the LangSmith UI.
        fail_max:      Number of consecutive failures before the breaker opens.
        reset_timeout: Seconds to wait before transitioning OPEN → HALF-OPEN.
    """
    return pybreaker.CircuitBreaker(
        fail_max=fail_max,
        reset_timeout=reset_timeout,
        listeners=[_LoggingListener(name)],   # attach our custom logging hook
        name=name,
    )


# ---------------------------------------------------------------------------
# One breaker per downstream dependency.
# Import these breakers in the agent modules and wrap every external call with:
#   result = <service>_breaker.call(lambda: <actual_api_call>)
# If the breaker is OPEN, pybreaker raises CircuitBreakerError immediately.
# ---------------------------------------------------------------------------

# OpenAI: longer cooldown because rate-limit errors don't resolve quickly
openai_breaker   = _make("openai",   fail_max=3, reset_timeout=60)

# Jira: ticket operations can tolerate a 30-second pause before retry
jira_breaker     = _make("jira",     fail_max=3, reset_timeout=30)

# Redis: fast in-memory store — allow 5 failures before tripping, recover in 20 s
redis_breaker    = _make("redis",    fail_max=5, reset_timeout=20)

# Pinecone: vector DB used for RAG context retrieval
pinecone_breaker = _make("pinecone", fail_max=3, reset_timeout=30)
