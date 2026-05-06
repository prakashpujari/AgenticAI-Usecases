"""
LangSmith observability integration.

What is LangSmith?
------------------
LangSmith is a hosted platform by LangChain that records every LLM call,
tool invocation, and agent step as a structured "trace". You can use it to:
  - Debug why the agent produced a wrong answer.
  - Measure latency and token cost per step.
  - Compare runs across different model versions (A/B testing).
  - Attach evaluation scores so you can see quality over time.

How it works here
-----------------
When LANGCHAIN_TRACING_V2=true, LangChain automatically sends trace data
to LangSmith for any code that runs inside a LangGraph/LangChain call.
We pass a `config` dict to graph.invoke() that carries a LangChainTracer
callback — LangChain does the rest.

Required environment variables:
  LANGCHAIN_TRACING_V2=true
  LANGCHAIN_API_KEY=<your_langsmith_api_key>
  LANGCHAIN_PROJECT=<project_name>      (default: llmops-production)

Usage in agent graph:
    from observability.langsmith_tracer import get_run_config
    result = graph.invoke(state, config=get_run_config(user, role, session_id, cid))
"""

import os
from observability.logger import get_logger

logger = get_logger("observability.langsmith")

# Read tracing config once at import time — avoids repeated os.getenv() calls
# in hot paths. These are module-level constants (prefixed with _  = private).
_TRACING_ENABLED = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
_PROJECT = os.getenv("LANGCHAIN_PROJECT", "llmops-production")
_API_KEY = os.getenv("LANGCHAIN_API_KEY", "")


def _build_tracer():
    """
    Lazily build and return a LangChainTracer object.

    "Lazy" means we do nothing until someone actually calls this function —
    that way the app starts up fine even if langsmith isn't installed.

    Returns None (instead of raising) so callers can treat missing tracing
    as a non-fatal degradation rather than a hard error.
    """
    # Guard 1: tracing not opted-in via env var → skip entirely
    if not _TRACING_ENABLED:
        return None
    # Guard 2: opted-in but forgot to provide the API key → warn, don't crash
    if not _API_KEY:
        logger.warning("LANGCHAIN_TRACING_V2 is true but LANGCHAIN_API_KEY is not set")
        return None
    try:
        # Import here (not at module top) so the app works even without langsmith installed
        from langchain_core.tracers import LangChainTracer
        # project_name groups all runs together in the LangSmith dashboard
        tracer = LangChainTracer(project_name=_PROJECT)
        logger.info("LangSmith tracer created", extra={"project": _PROJECT})
        return tracer
    except ImportError:
        # langsmith or langchain_core package is missing — degrade gracefully
        logger.warning("langsmith/langchain_core not installed — tracing disabled")
        return None


def get_langsmith_callbacks() -> list:
    """
    Return a list of LangChain callback objects for use in run configs.

    LangChain expects callbacks as a list, so we always return a list:
      - [tracer]  when tracing is active
      - []        when tracing is disabled (empty list = no callbacks)
    """
    tracer = _build_tracer()
    return [tracer] if tracer else []


def get_run_config(
    user: str,
    role: str,
    session_id: str,
    correlation_id: str,
) -> dict:
    """
    Build the run-config dict that gets passed to graph.invoke(state, config=...).

    LangGraph/LangChain reads this dict to know:
      - Which callbacks to fire for each step (our LangSmith tracer).
      - What metadata to attach to the run in LangSmith (searchable/filterable
        fields visible on the LangSmith dashboard).
      - Which tags to apply (useful for filtering runs by role or session).

    The function is safe to call even when LangSmith is disabled — in that
    case `callbacks` is omitted from the config dict so LangGraph ignores it.
    """
    callbacks = get_langsmith_callbacks()

    # metadata fields appear as columns/filters in the LangSmith run list view
    config: dict = {
        "metadata": {
            "user": user,
            "role": role,
            "session_id": session_id,
            "correlation_id": correlation_id,   # ties this trace to the HTTP request log
        },
        # tags allow quick filtering in LangSmith (e.g., "show me all DEVELOPER runs")
        "tags": [f"role:{role}", f"session:{session_id}"],
    }
    if callbacks:
        config["callbacks"] = callbacks
    return config


def trace_custom(name: str, inputs: dict, outputs: dict, metadata: dict | None = None) -> None:
    """
    Manually record a custom span to LangSmith.

    LangSmith auto-captures LangChain/LangGraph steps, but for things that
    happen *outside* those frameworks (e.g., RAGAS scores, DeepEval results)
    we call this function to push a custom run record.

    The function is a no-op (does nothing silently) when:
      - Tracing is disabled (LANGCHAIN_TRACING_V2 != true)
      - The API key is missing
      - The langsmith package is not installed
      - Any API call fails (we log a warning but never raise)

    Args:
        name:     Label shown in the LangSmith run list (e.g., "rag_evaluation").
        inputs:   Dict of input values recorded at span start.
        outputs:  Dict of output/result values recorded at span end.
        metadata: Extra key-value pairs attached to the span for filtering.
    """
    if not _TRACING_ENABLED or not _API_KEY:
        return  # silently skip — tracing is not configured
    try:
        from langsmith import Client
        # LangSmith Python SDK client authenticated with our API key
        client = Client(api_key=_API_KEY)
        # create_run opens the span; update_run closes it with the outputs
        run_id = client.create_run(
            name=name,
            run_type="chain",   # "chain" is the generic span type in LangSmith
            inputs=inputs,
            extra={"metadata": metadata or {}},
        )
        client.update_run(run_id=run_id, outputs=outputs, end_time=None)
    except Exception:
        # Never let observability code crash the main application
        logger.warning("Failed to record custom LangSmith span", exc_info=True)
