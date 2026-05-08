"""
Gunicorn configuration for production deployment.

Run with:
    gunicorn backend.main:app -c backend/gunicorn.conf.py

Tuning guide
------------
workers = (2 × CPU_CORES) + 1  is the standard formula for CPU-bound apps.
For I/O-heavy async apps (like this one — LLM calls dominate) fewer workers
with more threads or async workers are better.  UvicornWorker handles async.
"""
import multiprocessing
import os

# ── Worker settings ───────────────────────────────────────────────────────────
# Use uvicorn workers so FastAPI's async endpoints run properly under gunicorn.
worker_class = "uvicorn.workers.UvicornWorker"

# Default: 2 workers per CPU core, minimum 2.
# Override with GUNICORN_WORKERS env var in your container/deployment.
workers = int(os.environ.get("GUNICORN_WORKERS", max(2, multiprocessing.cpu_count() * 2)))

# Threads per worker (UvicornWorker is async so 1 thread is fine).
threads = 1

# ── Network ───────────────────────────────────────────────────────────────────
bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:8000")

# ── Timeouts ─────────────────────────────────────────────────────────────────
# The full pipeline (embedding + Pinecone + 3 LLM calls + Jira) can take
# 60-90 s under load. Set well above the p99 pipeline latency.
timeout = int(os.environ.get("GUNICORN_TIMEOUT", 180))

# How long to wait for a graceful shutdown before force-killing workers.
graceful_timeout = 30

# ── Keep-alive ────────────────────────────────────────────────────────────────
keepalive = 5

# ── Logging ───────────────────────────────────────────────────────────────────
# Emit access logs to stdout so container platforms (Docker, K8s) capture them.
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")

# ── Process management ───────────────────────────────────────────────────────
# Preload reduces per-worker startup time by loading the app before forking.
preload_app = True

# Max requests per worker before restart (prevents memory leaks).
max_requests = int(os.environ.get("GUNICORN_MAX_REQUESTS", 1000))
max_requests_jitter = 100
