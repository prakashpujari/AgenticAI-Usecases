import time
from collections import defaultdict, deque
from threading import Lock

# ---------------------------------------------------------------------------
# In-process metrics store
#
# Why not Prometheus right now?
# This module is intentionally simple: no external dependencies, no sidecar
# process needed. It works perfectly for development and moderate traffic.
# When you need a production Prometheus setup, replace `increment` and
# `record_duration` with prometheus_client equivalents — the call-sites
# across the codebase don't need to change.
#
# Thread safety: all writes go through `_lock` so concurrent requests
# don't corrupt the counters or histogram lists.
# ---------------------------------------------------------------------------

# defaultdict(int)  — any new key automatically starts at 0
_counters: dict = defaultdict(int)

# defaultdict(list) — any new key automatically starts as an empty list
_histograms: dict = defaultdict(list)

# A re-entrant lock that serialises all writes; reads also hold the lock
# so callers always see a consistent snapshot.
_lock = Lock()


def increment(metric: str, labels: dict | None = None) -> None:
    """
    Increment a named counter by 1.

    Args:
        metric: Dot-separated metric name, e.g. "api.run_agent.requests".
        labels: Optional key-value tags that become part of the storage key,
                e.g. {"path": "/run_agent"} → stored as "metric{path=/run_agent}".

    Example:
        increment("planner.success")
        increment("http.requests", {"method": "POST"})
    """
    key = _make_key(metric, labels)
    with _lock:  # ensure atomic read-modify-write in multi-threaded FastAPI
        _counters[key] += 1


def record_duration(metric: str, elapsed_ms: float, labels: dict | None = None) -> None:
    """
    Append an elapsed-time sample to a named histogram.

    We keep only the last 1 000 samples per metric to bound memory usage.
    Percentiles (p50/p95/p99) are computed lazily in get_snapshot() so this
    function stays O(1).

    Args:
        metric:     Metric name, e.g. "planner.latency_ms".
        elapsed_ms: Duration in milliseconds as a float.
        labels:     Optional dimension tags (same as increment).
    """
    key = _make_key(metric, labels)
    with _lock:
        _histograms[key].append(elapsed_ms)
        # Sliding-window cap: drop oldest samples beyond 1 000 to bound memory
        if len(_histograms[key]) > 1000:
            _histograms[key] = _histograms[key][-1000:]


def get_snapshot() -> dict:
    """
    Return a point-in-time snapshot of all counters and histogram summaries.

    Called by the GET /metrics endpoint so operators can see the current
    state without needing an external metrics system.

    Histogram output per key:
        count   — total number of recorded samples
        avg_ms  — arithmetic mean
        p50_ms  — 50th percentile (median)
        p95_ms  — 95th percentile (SLO threshold)
        p99_ms  — 99th percentile (tail latency)
    """
    with _lock:
        hist_summary = {}
        for key, samples in _histograms.items():
            if samples:
                sorted_s = sorted(samples)   # sort once; reused for all percentiles
                n = len(sorted_s)
                hist_summary[key] = {
                    "count":   n,
                    "avg_ms":  round(sum(sorted_s) / n, 2),
                    # int(n * 0.50) gives the index of the 50th percentile element
                    "p50_ms":  round(sorted_s[int(n * 0.50)], 2),
                    "p95_ms":  round(sorted_s[int(n * 0.95)], 2),
                    # min(..., n-1) prevents index-out-of-bounds for small samples
                    "p99_ms":  round(sorted_s[min(int(n * 0.99), n - 1)], 2),
                }
        return {
            "counters":   dict(_counters),
            "histograms": hist_summary,
        }


def _make_key(metric: str, labels: dict | None) -> str:
    """
    Build a Prometheus-style metric key from a name and optional label dict.

    Examples:
        _make_key("http.latency_ms", None)            → "http.latency_ms"
        _make_key("http.latency_ms", {"path": "/run"}) → "http.latency_ms{path=/run}"

    Labels are sorted alphabetically so the same label set always produces
    the same key regardless of the insertion order of the dict.
    """
    if not labels:
        return metric
    tag_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
    return f"{metric}{{{tag_str}}}"
