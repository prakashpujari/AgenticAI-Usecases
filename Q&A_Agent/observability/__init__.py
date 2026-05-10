"""
observability/__init__.py
─────────────────────────
Observability package for the Q&A Agent pipeline.

Exposes the primary utilities so callers can do:

    from observability import setup_logging, get_logger
    from observability import PipelineMetrics
    from observability import setup_langsmith
"""

from observability.logger import get_logger, setup_logging
from observability.metrics import PipelineMetrics
from observability.langsmith_tracer import setup_langsmith

__all__ = ["setup_logging", "get_logger", "PipelineMetrics", "setup_langsmith"]
