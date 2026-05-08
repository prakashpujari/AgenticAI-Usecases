from __future__ import annotations

from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Request, Response

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

AI_CALL_COUNT = Counter(
    "ai_calls_total",
    "Total AI provider calls",
    ["provider", "operation", "status"],
)

AI_CALL_LATENCY = Histogram(
    "ai_call_duration_seconds",
    "AI provider call latency",
    ["provider", "operation"],
)


async def metrics_endpoint(_: Request) -> Response:
    """Expose Prometheus metrics at /metrics."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
