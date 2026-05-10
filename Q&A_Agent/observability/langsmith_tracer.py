"""
observability/langsmith_tracer.py
──────────────────────────────────
LangSmith tracing initialisation for the Q&A Agent pipeline.

What is LangSmith?
──────────────────
LangSmith is LangChain's observability and evaluation platform.  When tracing
is active, every LangChain LCEL component invoked in the process — prompts,
LLM calls, retrievers, output parsers — is captured as a structured "run" and
uploaded to the LangSmith UI.  This gives you:

  • Full input/output visibility for every chain step
  • Per-step latency and token-usage breakdown
  • A hierarchical trace tree (pipeline run → stage → chain → LLM call)
  • The ability to replay, annotate, and evaluate any trace

How auto-tracing works
──────────────────────
LangChain's SDK checks three os.environ variables at import time:

    LANGCHAIN_TRACING_V2=true      — enables the background tracer
    LANGCHAIN_API_KEY=<key>        — authenticates uploads to LangSmith
    LANGCHAIN_PROJECT=<project>    — groups traces under a named project

setup_langsmith() writes these from config.*  constants into os.environ,
then constructs a LangSmith Client to verify the connection.  The call is
idempotent (safe to call multiple times).

Explicit @traceable spans
─────────────────────────
LangChain LCEL calls are auto-traced; plain Python functions are not.
Decorate non-LCEL functions with @traceable to wrap them in their own span:

    from langsmith import traceable

    @traceable(name="my_function", run_type="chain")
    def my_function(arg):
        ...

The span will appear as a child of whatever outer run is active at call time.

Pipeline metadata
──────────────────
Pass pipeline-level metadata to every trace in the run via the LangSmith
context manager in main.py:

    with langsmith.trace(
        name="Q&A Pipeline",
        run_type="chain",
        metadata={"pipeline_id": metrics.pipeline_id, "model": config.OPENAI_MODEL},
    ):
        ...  # all LangChain calls inside here are nested under this parent run

Public API
──────────
    setup_langsmith() -> bool
        Configures tracing, logs status, returns True when tracing is active.
"""

import os

import config
from observability.logger import get_logger

logger = get_logger(__name__)


def setup_langsmith() -> bool:
    """
    Configures LangSmith tracing from config.* constants.

    What this does:
      1. Writes LANGCHAIN_TRACING_V2, LANGCHAIN_API_KEY, LANGCHAIN_PROJECT,
         and LANGCHAIN_ENDPOINT into os.environ so LangChain's SDK picks them
         up immediately (even if they were read from .env by load_dotenv()
         before the SDK was imported).
      2. If tracing is enabled, imports langsmith.Client and performs a
         lightweight list_projects() call to verify the API key and network
         connectivity.  Logs success or warning (never raises — tracing
         failures must not block the pipeline).
      3. Logs an INFO line summarising the tracing state so operators can
         confirm it from the console output.

    Idempotency:
      Calling this function more than once is safe.  The env vars will be
      re-set to the same values and the Client will be re-verified, but no
      side effects accumulate.

    Returns:
        True if tracing is successfully enabled, False otherwise.
    """
    # ── Step 1: Push config values into os.environ ────────────────────────────
    # load_dotenv() already set these if a .env file was present.  We
    # explicitly write them again here so that dynamically-generated values
    # (e.g. from a secrets manager in production) override stale env vars.
    os.environ["LANGCHAIN_TRACING_V2"] = "true" if config.LANGCHAIN_TRACING_V2 else "false"
    os.environ["LANGCHAIN_PROJECT"]    = config.LANGCHAIN_PROJECT
    os.environ["LANGCHAIN_ENDPOINT"]   = config.LANGCHAIN_ENDPOINT

    if config.LANGCHAIN_API_KEY:
        os.environ["LANGCHAIN_API_KEY"] = config.LANGCHAIN_API_KEY

    # ── Step 2: Early-exit if tracing is disabled ─────────────────────────────
    if not config.LANGCHAIN_TRACING_V2:
        logger.info(
            "LangSmith tracing DISABLED "
            "(set LANGCHAIN_TRACING_V2=true in .env to enable)."
        )
        return False

    # ── Step 3: Check API key is present ──────────────────────────────────────
    if not config.LANGCHAIN_API_KEY:
        logger.warning(
            "LangSmith tracing is enabled (LANGCHAIN_TRACING_V2=true) but "
            "LANGCHAIN_API_KEY is not set.  Traces will not be uploaded.\n"
            "  → Set LANGCHAIN_API_KEY in your .env file."
        )
        return False

    # ── Step 4: Verify connectivity with a lightweight API call ───────────────
    try:
        from langsmith import Client  # deferred import — langsmith may not be installed

        client = Client(
            api_url=config.LANGCHAIN_ENDPOINT,
            api_key=config.LANGCHAIN_API_KEY,
        )
        # list_projects() is the cheapest read-only call; we only take the
        # first page to avoid large payloads.
        list(client.list_projects(limit=1))

        logger.info(
            "LangSmith tracing ENABLED  project='%s'  endpoint='%s'",
            config.LANGCHAIN_PROJECT,
            config.LANGCHAIN_ENDPOINT,
            extra={
                "langsmith_project":  config.LANGCHAIN_PROJECT,
                "langsmith_endpoint": config.LANGCHAIN_ENDPOINT,
            },
        )
        return True

    except ImportError:
        logger.warning(
            "langsmith package is not installed.  "
            "Run:  pip install langsmith>=0.1.0\n"
            "Tracing will be disabled for this run."
        )
        return False

    except Exception as exc:  # noqa: BLE001
        # Connectivity failures are logged as warnings — they must NOT abort
        # the pipeline.  The LangSmith background tracer will keep retrying
        # uploads; this check is just an early indicator.
        logger.warning(
            "LangSmith connectivity check failed: %s\n"
            "Tracing may still work if the network issue is transient.",
            exc,
            extra={"langsmith_error": str(exc)},
        )
        # Return True anyway — the SDK is configured even if the ping failed.
        return True
