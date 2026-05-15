"""
observability/logger.py
───────────────────────
Configures the logging sub-system for the entire Q&A Agent pipeline.

Two output streams are set up simultaneously:

  1. Console (stdout)
     ─────────────────
     • Human-readable, left-aligned, coloured by severity level.
     • Colour is applied only when stdout is a real TTY; CI/CD pipelines
       that pipe stdout to a file will NOT see raw ANSI escape codes.

  2. Rotating file  (logs/qa_agent.log)
     ──────────────────────────────────
     • JSON Lines format — one JSON object per log record per line.
     • Machine-readable and directly ingestible by log aggregators
       (Datadog, CloudWatch Logs Insights, ELK stack, Splunk, etc.).
     • Automatically rotates at LOG_MAX_BYTES (default 10 MB),
       keeping LOG_BACKUP_COUNT (default 5) archived copies.
     • Always captures DEBUG-level records regardless of the console
       level, so post-mortem analysis has full detail.

JSON line format (one compact object per line):
    {
      "ts":      "2026-05-10T11:42:01.234+00:00",   ← ISO-8601 UTC
      "level":   "INFO",
      "logger":  "src.retrieval.embeddings_store",
      "message": "FAISS index saved",
      "module":  "embeddings_store",
      "func":    "build_vector_store",
      "line":    87,
      "extra":   { "chunk_count": 42 }               ← optional
    }

Usage
─────
    # In main.py (call once, before any other imports that log):
    from observability.logger import setup_logging
    setup_logging()

    # In any module:
    from observability.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Processing %d chunks", n)

Design notes
────────────
  • We use only Python's built-in `logging` module to avoid additional
    dependencies (structlog, loguru, etc.).
  • setup_logging() is idempotent — calling it multiple times (e.g.
    during test runs) will not add duplicate handlers.
  • Third-party library loggers (httpx, openai, faiss) are explicitly
    capped at WARNING to prevent their INFO/DEBUG spam from drowning out
    application logs.
"""

import json
import logging
import logging.handlers
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Import config lazily to break a potential import cycle:
# config → os.getenv (fine), observability.logger → config (fine as long as
# config does not import observability at module level, which it does not).
import config

# ─── ANSI terminal colour palette ─────────────────────────────────────────────
#
# Map each standard log level to an ANSI SGR colour code.
# The reset sequence _RESET is appended after every coloured line.
#
_LEVEL_COLOURS: dict[int, str] = {
    logging.DEBUG:    "\033[36m",   # Cyan    — low-priority detail
    logging.INFO:     "\033[32m",   # Green   — normal progress
    logging.WARNING:  "\033[33m",   # Yellow  — worth attention
    logging.ERROR:    "\033[31m",   # Red     — something went wrong
    logging.CRITICAL: "\033[35m",   # Magenta — system-level failure
}
_RESET = "\033[0m"


# ─── Console formatter ─────────────────────────────────────────────────────────

class _ColourConsoleFormatter(logging.Formatter):
    """
    Human-readable formatter for the console (stdout) handler.

    Output format:
        HH:MM:SS  LEVEL     module.path                   message text

    Colour behaviour:
        Colours are applied only when sys.stdout is attached to a real TTY
        (sys.stdout.isatty() returns True).  In non-interactive shells,
        CI/CD pipelines, or when stdout is redirected to a file, the plain
        text is emitted without any ANSI codes — preventing garbage
        characters in log files or system journals.

    The level name is left-padded to 8 characters so that DEBUG, INFO,
    WARNING, ERROR, and CRITICAL all produce visually aligned output.
    """

    # Evaluated once at class-definition time so the isatty() check is not
    # repeated for every log record.
    _use_colour: bool = sys.stdout.isatty()

    def format(self, record: logging.LogRecord) -> str:
        # Let the parent class handle %-style message substitution,
        # exception info formatting, and the asctime field.
        formatted = super().format(record)

        if self._use_colour:
            # Look up the colour for this level; fall back to no colour for
            # any custom levels not in the palette.
            colour = _LEVEL_COLOURS.get(record.levelno, "")
            return f"{colour}{formatted}{_RESET}"

        return formatted


# ─── JSON file formatter ───────────────────────────────────────────────────────

class _JSONFileFormatter(logging.Formatter):
    """
    Machine-readable JSON Lines formatter for the rotating file handler.

    Why JSON Lines (one JSON object per line)?
      • Every log aggregator can ingest it without configuration.
      • grep / jq can filter log files without a custom parser.
      • Timestamps are ISO-8601 UTC, so timezone conversion is unambiguous.
      • Structured fields (module, line, extra) are first-class — no
        regex scraping needed for alerting rules.

    Extra fields:
        Callers can attach arbitrary metadata to a log record via the
        extra= keyword argument:

            logger.info("chunks embedded", extra={"chunk_count": 42})

        These appear under the "extra" key in the JSON payload.  Standard
        LogRecord attributes (msg, args, exc_info, etc.) are excluded to
        keep the output clean.
    """

    # Attributes that exist on every LogRecord — we don't want to duplicate
    # them under "extra" when the caller uses extra={}.
    _SKIP: frozenset[str] = frozenset(
        logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()
    ) | {"message", "asctime", "args", "msg", "exc_info", "exc_text", "stack_info"}

    def format(self, record: logging.LogRecord) -> str:
        # getMessage() applies %-formatting AND returns the final message string.
        message = record.getMessage()

        # If an exception was passed, append the formatted traceback so the
        # full stack trace is captured in the JSON "message" field rather than
        # being silently dropped.
        if record.exc_info:
            message += "\n" + self.formatException(record.exc_info)

        payload: dict[str, Any] = {
            # Use fromtimestamp with UTC timezone for an unambiguous timestamp.
            # timespec="milliseconds" gives sub-second precision without
            # the microsecond noise that makes logs hard to read.
            "ts":      datetime.fromtimestamp(record.created, tz=timezone.utc)
                               .isoformat(timespec="milliseconds"),
            "level":   record.levelname,
            "logger":  record.name,
            "message": message,
            "module":  record.module,
            "func":    record.funcName,
            "line":    record.lineno,
        }

        # Collect caller-provided extra= fields, filtering out standard attrs.
        extra = {k: v for k, v in record.__dict__.items() if k not in self._SKIP}
        if extra:
            payload["extra"] = extra

        # separators=(',', ':') produces compact JSON with no extra whitespace,
        # keeping each log line as short as possible.
        # default=str handles any non-serialisable types (Path, Enum, etc.)
        # gracefully by converting them to their string representation.
        return json.dumps(payload, separators=(",", ":"), default=str)


# ─── Public API ────────────────────────────────────────────────────────────────

def setup_logging() -> None:
    """
    Configures the root logger.  Call ONCE at program startup (main.py),
    before any module-level loggers are used.

    Idempotency:
        Checks root.handlers before adding anything.  Multiple calls
        (e.g. in test suites that import main) will not duplicate handlers.

    Handlers installed:
        • StreamHandler   → sys.stdout, _ColourConsoleFormatter
        • RotatingFileHandler → logs/qa_agent.log, _JSONFileFormatter
          (only if config.LOG_TO_FILE is True)

    Third-party noise suppression:
        httpx, httpcore, openai, and faiss are capped at WARNING to
        prevent their per-request INFO logs from cluttering the output.
    """
    root = logging.getLogger()

    # Guard against duplicate handler registration (idempotency).
    if root.handlers:
        return

    # Convert the configured level string ("INFO", "DEBUG", …) to its
    # integer value.  getattr falls back to INFO for unknown strings.
    numeric_level = getattr(logging, config.LOG_LEVEL, logging.INFO)
    root.setLevel(numeric_level)

    # ── Console handler ────────────────────────────────────────────────────────
    # On Windows the default stdout encoding is cp1252 which can't render
    # Unicode arrows/checkmarks used in log messages.  Reconfigure to utf-8.
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(
        _ColourConsoleFormatter(
            fmt="%(asctime)s  %(levelname)-8s  %(name)-40s %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    root.addHandler(console_handler)

    # ── Rotating JSON file handler ─────────────────────────────────────────────
    if config.LOG_TO_FILE:
        log_file = config.LOGS_DIR / "qa_agent.log"

        # RotatingFileHandler renames qa_agent.log → qa_agent.log.1, .log.2, …
        # when the file grows beyond maxBytes, keeping backupCount old copies.
        # This prevents unbounded disk growth while retaining recent history.
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_file,
            maxBytes=config.LOG_MAX_BYTES,
            backupCount=config.LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        # The file always captures DEBUG so we have full detail for post-mortem
        # analysis, even if the console only shows INFO.
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(_JSONFileFormatter())
        root.addHandler(file_handler)

    # ── Silence chatty third-party loggers ─────────────────────────────────────
    # httpx (used by the OpenAI SDK) logs every HTTP request at INFO level.
    # That adds ~4 lines per API call with headers and URL — pure noise.
    for noisy_logger in ("httpx", "httpcore", "openai", "faiss"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    root.debug(
        "Logging initialised",
        extra={"level": config.LOG_LEVEL, "file_logging": config.LOG_TO_FILE},
    )


def get_logger(name: str) -> logging.Logger:
    """
    Returns a named logger that inherits from the root logger configured
    by setup_logging().

    Args:
        name: Typically __name__ of the calling module so the logger
              hierarchy mirrors the package hierarchy.  This makes it
              easy to selectively adjust log levels for specific modules.

    Returns:
        A logging.Logger instance.  Handlers and level are inherited from
        the root logger; no additional configuration is needed here.

    Example:
        # At the top of any module:
        from observability.logger import get_logger
        logger = get_logger(__name__)
    """
    return logging.getLogger(name)
