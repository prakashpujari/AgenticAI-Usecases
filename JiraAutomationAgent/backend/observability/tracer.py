"""
Observability: LangSmith tracing decorators, structured cache-event logging,
and a request-scoped trace-ID context variable for per-layer log enrichment.

Log format (all layers):
  [LAYER·Component]  trace=<id>  key=value  key=value  ...

Layers used across the codebase:
  LLM       – OpenAI calls in base_agent
  RAG       – Pinecone retrieval + LLM reranker
  PII       – Presidio / regex redaction
  AGENT     – per-agent entry/exit
  GUARDRAIL – guardrails / RBAC
  WORKFLOW  – LangGraph node transitions
"""
from __future__ import annotations

import logging
import os
from contextvars import ContextVar
from functools import wraps
from typing import Any, Callable, Optional

from ..config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Request-scoped trace ID
# Each async pipeline run sets this once in normalize_inputs so that every
# downstream log line can include the same trace_id for easy grep/filtering.
# ---------------------------------------------------------------------------
_trace_id_var: ContextVar[str] = ContextVar("trace_id", default="no-trace")


def set_trace_id(trace_id: str) -> None:
    """Bind *trace_id* to the current async context (called once per request)."""
    _trace_id_var.set(trace_id)


def get_trace_id() -> str:
    """Return the trace ID bound to the current async context."""
    return _trace_id_var.get()


# ---------------------------------------------------------------------------
# Structured log helper
# Produces consistent lines like:
#   [LLM·GeneratorAgent]  trace=ef0aade9  tokens=1041  latency=5.73s
# ---------------------------------------------------------------------------

def log_layer(layer: str, component: str, **fields: Any) -> None:
    """
    Emit one INFO log line in the canonical structured format.

    Usage::
        log_layer("LLM", "GeneratorAgent", tokens=1041, latency_s=5.73)
        # → [LLM·GeneratorAgent]  trace=ef0aade9  tokens=1041  latency_s=5.73
    """
    tid = get_trace_id()
    kv = "  ".join(f"{k}={v}" for k, v in fields.items())
    logger.info("[%s·%s]  trace=%.8s  %s", layer, component, tid, kv)


def log_layer_warn(layer: str, component: str, **fields: Any) -> None:
    """Same as :func:`log_layer` but at WARNING level."""
    tid = get_trace_id()
    kv = "  ".join(f"{k}={v}" for k, v in fields.items())
    logger.warning("[%s·%s]  trace=%.8s  %s", layer, component, tid, kv)

# ---------------------------------------------------------------------------
# Configure LangSmith environment at import time
# ---------------------------------------------------------------------------
if settings.langchain_api_key:
    # Write env vars before importing langsmith so the SDK picks them up.
    # setdefault is used for variables the caller may have already set via
    # the shell, to avoid overwriting intentional overrides.
    os.environ.setdefault("LANGCHAIN_API_KEY", settings.langchain_api_key)
    os.environ["LANGCHAIN_TRACING_V2"] = (
        "true" if settings.langchain_tracing_v2 else "false"
    )
    os.environ.setdefault("LANGCHAIN_PROJECT", settings.langchain_project)

try:
    from langsmith import traceable as _ls_traceable  # type: ignore

    # Tracing is active only when both the package is installed AND an API
    # key is configured. Package presence without a key is a no-op.
    _LANGSMITH_AVAILABLE = bool(settings.langchain_api_key)
    logger.info("LangSmith tracing: %s", "enabled" if _LANGSMITH_AVAILABLE else "disabled (no API key)")
except ImportError:
    # LangSmith is an optional dependency. When absent, all decorators
    # degrade to pass-through wrappers with debug-level logging.
    _ls_traceable = None  # type: ignore
    _LANGSMITH_AVAILABLE = False
    logger.warning("langsmith package not installed — tracing disabled")


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------

def trace_agent(name: str, run_type: str = "chain") -> Callable:
    """
    Decorator: wraps an async agent function with LangSmith tracing.
    Falls back to a pass-through wrapper when LangSmith is unavailable.
    """

    def decorator(func: Callable) -> Callable:
        if _LANGSMITH_AVAILABLE and _ls_traceable:
            try:
                return _ls_traceable(name=name, run_type=run_type)(func)
            except Exception:
                pass  # degrade silently if traceable fails (e.g. SDK version mismatch)

        # Pass-through: no tracing overhead, debug logs only
        @wraps(func)
        async def _passthrough(*args, **kwargs):
            logger.debug("[TRACE-AGENT] %s called", name)
            result = await func(*args, **kwargs)
            logger.debug("[TRACE-AGENT] %s finished", name)
            return result

        return _passthrough

    return decorator


def trace_retrieval(name: str = "rag_retrieval") -> Callable:
    """
    Decorator: wraps a RAG retrieval function with LangSmith tracing.
    """

    def decorator(func: Callable) -> Callable:
        if _LANGSMITH_AVAILABLE and _ls_traceable:
            try:
                return _ls_traceable(name=name, run_type="retriever")(func)
            except Exception:
                pass

        @wraps(func)
        async def _passthrough(*args, **kwargs):
            logger.debug("[TRACE-RETRIEVAL] %s called", name)
            result = await func(*args, **kwargs)
            logger.debug("[TRACE-RETRIEVAL] %s finished", name)
            return result

        return _passthrough

    return decorator


# ---------------------------------------------------------------------------
# Cache event logging
# ---------------------------------------------------------------------------

def log_cache_event(cache_type: str, key: str, *, hit: bool) -> None:
    """Emit a structured log line for every Redis cache hit/miss."""
    status = "HIT" if hit else "MISS"
    logger.info("[CACHE] %-10s %s  key=%.40s", cache_type.upper(), status, key)
