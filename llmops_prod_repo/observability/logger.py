import logging
import json
import time
import uuid
import traceback
from datetime import datetime, timezone
from contextvars import ContextVar   # PEP 567 — per-async-task context storage
from functools import wraps           # preserves the wrapped function's name/docstring

# ---------------------------------------------------------------------------
# Correlation ID — a UUID that links every log line for a single HTTP request.
#
# Problem: In an async server, many requests run concurrently. A normal global
# variable would be shared and overwritten. ContextVar solves this: each
# async task (i.e. each HTTP request) gets its own independent copy of the
# variable, even though they all share the same thread pool.
#
# How to use:
#   set_correlation_id("abc-123")   # set once at request entry (middleware)
#   get_correlation_id()            # read anywhere downstream in the same task
# ---------------------------------------------------------------------------
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


class StructuredFormatter(logging.Formatter):
    """
    Custom log formatter that outputs every log record as a single JSON line.

    Why JSON logs?
    Log aggregators like Datadog, ELK (Elasticsearch/Logstash/Kibana), and
    Splunk expect structured JSON so they can index individual fields and let
    you search/filter by level, correlation_id, user, etc.

    Standard Python logging emits plain text like:
        INFO:app:Agent started
    We emit instead:
        {"timestamp": "...", "level": "INFO", "message": "Agent started", ...}
    """

    def format(self, record: logging.LogRecord) -> str:
        # Build the mandatory base fields present on every log line
        payload = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(timezone.utc).microsecond // 1000:03d}Z",
            "level": record.levelname,          # DEBUG / INFO / WARNING / ERROR
            "logger": record.name,               # e.g. "agent.planner"
            "message": record.getMessage(),      # the actual log message string
            "correlation_id": correlation_id_var.get(""),  # ties this line to the request
        }
        # If an exception was logged (exc_info=True), include the traceback
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # Merge any custom fields passed via logger.info("msg", extra={"key": val})
        # We skip Python's internal LogRecord attributes (the exclusion list)
        # to avoid polluting the JSON with noisy internals.
        for key, val in record.__dict__.items():
            if key not in (
                "args", "asctime", "created", "exc_info", "exc_text",
                "filename", "funcName", "id", "levelname", "levelno",
                "lineno", "message", "module", "msecs", "msg", "name",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "thread", "threadName",
            ):
                payload[key] = val
        # default=str ensures non-serialisable objects (e.g. datetime) become strings
        return json.dumps(payload, default=str)


def get_logger(name: str) -> logging.Logger:
    """
    Create (or retrieve) a named logger with our JSON formatter attached.

    Python's logging module caches loggers by name, so calling get_logger
    with the same name twice returns the SAME object. The `if not logger.handlers`
    guard ensures we only add the StreamHandler once — without it, every call
    would add another handler and every log line would print multiple times.

    Usage:
        logger = get_logger("agent.planner")
        logger.info("Something happened", extra={"user": "alice"})
    """
    logger = logging.getLogger(name)
    if not logger.handlers:   # only configure on first call for this name
        handler = logging.StreamHandler()            # write to stdout/stderr
        handler.setFormatter(StructuredFormatter())  # use our JSON formatter
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)   # INFO and above (WARNING, ERROR, CRITICAL)
        logger.propagate = False        # don't bubble up to the root logger (avoids duplicate output)
    return logger


def new_correlation_id() -> str:
    """
    Generate a fresh UUID, store it in the current async context, and return it.
    Typically called at application startup or in tests.
    """
    cid = str(uuid.uuid4())  # e.g. "f47ac10b-58cc-4372-a567-0e02b2c3d479"
    correlation_id_var.set(cid)
    return cid


def set_correlation_id(cid: str) -> None:
    """
    Store an externally-supplied correlation ID (e.g. from an X-Correlation-ID
    request header) in the current async task's context variable.
    """
    correlation_id_var.set(cid)


def get_correlation_id() -> str:
    """
    Read the correlation ID for the current async task.
    Returns an empty string if no ID has been set yet.
    """
    return correlation_id_var.get("")


def trace_agent(agent_name: str):
    """
    Decorator factory that adds structured timing + logging to any agent function.

    How to use:
        @trace_agent("planner")
        def planner_agent(state):
            ...

    What it does:
        1. Logs when the agent starts (includes user and session for tracing).
        2. Measures wall-clock time with perf_counter (nanosecond precision).
        3. Logs success with elapsed_ms on normal exit.
        4. Catches PermissionError separately so we can log it as WARNING
           (expected business logic) rather than ERROR (unexpected crash).
        5. Re-raises ALL exceptions — the decorator never swallows errors.
    """
    def decorator(fn):
        # Each decorated function gets its own logger scoped to the agent name
        logger = get_logger(f"agent.{agent_name}")

        @wraps(fn)   # makes the wrapper look like 'fn' for debugging/introspection
        def wrapper(state, *args, **kwargs):
            # time.perf_counter() is the highest-resolution timer available;
            # it measures elapsed wall-clock time (not CPU time)
            start = time.perf_counter()
            logger.info(
                "Agent started",
                extra={"agent": agent_name, "session_id": state.get("session_id", ""), "user": state.get("user", "")},
            )
            try:
                result = fn(state, *args, **kwargs)   # call the actual agent function
                elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
                logger.info(
                    "Agent completed",
                    extra={"agent": agent_name, "elapsed_ms": elapsed_ms},
                )
                return result
            except PermissionError:
                # RBAC denied access — this is expected behaviour, log as WARNING
                elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
                logger.warning(
                    "Agent permission denied",
                    extra={"agent": agent_name, "elapsed_ms": elapsed_ms},
                    exc_info=True,   # include stack trace in the JSON log
                )
                raise  # always re-raise so FastAPI can return a 403
            except Exception:
                # Unexpected error — log as ERROR with full traceback
                elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
                logger.error(
                    "Agent failed",
                    extra={"agent": agent_name, "elapsed_ms": elapsed_ms},
                    exc_info=True,
                )
                raise  # always re-raise so FastAPI can return a 500

        return wrapper
    return decorator
