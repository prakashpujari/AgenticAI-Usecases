"""
tests/conftest.py
──────────────────
Shared pytest fixtures for the Q&A Agent test suite.
"""

import os
import sys

import pytest

# ── Make the project root importable ──────────────────────────────────────────
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Set minimal env vars before any config import
os.environ.setdefault("GROQ_API_KEY",          "test-key")
os.environ.setdefault("GROQ_MODEL",            "llama-3.3-70b-versatile")
os.environ.setdefault("GROQ_FALLBACK_MODEL",   "llama-3.1-8b-instant")
os.environ.setdefault("REDIS_URL",             "")   # in-memory fallback
os.environ.setdefault("IDENTITY_HMAC_SECRET",  "test-secret-32chars-padding000")
os.environ.setdefault("RATE_LIMIT_MAX",        "10")
os.environ.setdefault("RATE_LIMIT_WINDOW",     "3600")
os.environ.setdefault("BURST_MAX",             "3")
os.environ.setdefault("BURST_REFILL_RATE",     "0.05")
os.environ.setdefault("GLOBAL_LLM_MAX",        "100")
os.environ.setdefault("LOG_TO_FILE",           "false")


@pytest.fixture(autouse=True)
def reset_rate_limit_store():
    """Clear the in-memory rate-limit store before each test."""
    from api.middleware.rate_limit import _mem_store, _mem_lock
    with _mem_lock:
        _mem_store.clear()
    yield
    with _mem_lock:
        _mem_store.clear()


@pytest.fixture
def app_client():
    """Return a synchronous TestClient for the FastAPI app."""
    from fastapi.testclient import TestClient
    from api.server import app

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
