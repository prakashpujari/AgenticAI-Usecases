"""
tests/test_rate_limit.py
─────────────────────────
Tests for rate limiting (sliding window), spike arrest (token bucket),
and identity extraction.
"""

import time
import pytest
from fastapi import HTTPException
from unittest.mock import MagicMock, patch


# ── Identity extraction ───────────────────────────────────────────────────────
class TestExtractIdentity:
    def _extract(self, headers):
        from api.middleware.rate_limit import extract_identity
        req = MagicMock()
        req.headers = headers
        req.client = MagicMock()
        req.client.host = "1.2.3.4"
        return extract_identity(req)

    def test_ip_subnet_identity(self):
        identity = self._extract({})
        assert identity.startswith("subnet:")
        assert len(identity) > 10

    def test_fingerprint_preferred_over_ip(self):
        fp = "a" * 64
        identity = self._extract({"X-Device-Fingerprint": fp})
        assert identity.startswith("fp:")

    def test_jwt_preferred_over_fingerprint(self):
        fp = "a" * 64
        identity = self._extract({
            "Authorization": "Bearer sometoken123",
            "X-Device-Fingerprint": fp,
        })
        assert identity.startswith("jwt:")

    def test_invalid_fingerprint_falls_back_to_ip(self):
        identity = self._extract({"X-Device-Fingerprint": "tooshort"})
        assert identity.startswith("subnet:")

    def test_same_subnet_same_key(self):
        from api.middleware.rate_limit import extract_identity
        req_a = MagicMock()
        req_a.headers = {}
        req_a.client = MagicMock()
        req_a.client.host = "1.2.3.100"

        req_b = MagicMock()
        req_b.headers = {}
        req_b.client = MagicMock()
        req_b.client.host = "1.2.3.200"

        # Same /24 subnet → same identity
        assert extract_identity(req_a) == extract_identity(req_b)

    def test_different_subnet_different_key(self):
        from api.middleware.rate_limit import extract_identity
        req_a = MagicMock()
        req_a.headers = {}
        req_a.client = MagicMock()
        req_a.client.host = "1.2.3.100"

        req_b = MagicMock()
        req_b.headers = {}
        req_b.client = MagicMock()
        req_b.client.host = "1.2.4.100"

        assert extract_identity(req_a) != extract_identity(req_b)


# ── Sliding window rate limiter ───────────────────────────────────────────────
class TestRateLimit:
    def _check(self, identity="test-user"):
        from api.middleware.rate_limit import check_rate_limit
        return check_rate_limit(identity)

    def test_first_request_allowed(self):
        remaining = self._check("rl-test-1")
        assert remaining == 9  # 10 - 1

    def test_requests_up_to_limit_allowed(self):
        for i in range(10):
            self._check("rl-test-2")

    def test_eleventh_request_blocked(self):
        identity = "rl-test-3"
        for _ in range(10):
            self._check(identity)
        with pytest.raises(HTTPException) as exc:
            self._check(identity)
        assert exc.value.status_code == 429
        assert exc.value.detail["error_code"] == "RATE_LIMIT_EXCEEDED"
        assert exc.value.detail["retry_after_seconds"] is not None

    def test_different_identities_independent_counters(self):
        for _ in range(10):
            self._check("rl-user-A")
        # user-B is unaffected
        remaining = self._check("rl-user-B")
        assert remaining == 9

    def test_error_response_has_debug_id(self):
        identity = "rl-test-4"
        for _ in range(10):
            self._check(identity)
        with pytest.raises(HTTPException) as exc:
            self._check(identity)
        assert "debug_id" in exc.value.detail

    def test_remaining_decrements(self):
        identity = "rl-test-5"
        r1 = self._check(identity)
        r2 = self._check(identity)
        assert r2 == r1 - 1


# ── Spike arrest (token bucket) ───────────────────────────────────────────────
class TestSpikeArrest:
    def _check(self, identity="spike-test"):
        from api.middleware.rate_limit import check_spike_arrest
        check_spike_arrest(identity)

    def test_burst_within_limit_allowed(self):
        for _ in range(3):  # BURST_MAX = 3
            self._check("spike-1")

    def test_exceeding_burst_raises_429(self):
        identity = "spike-2"
        # Drain all tokens
        for _ in range(3):
            self._check(identity)
        with pytest.raises(HTTPException) as exc:
            self._check(identity)
        assert exc.value.status_code == 429
        assert exc.value.detail["error_code"] == "SPIKE_ARREST"

    def test_tokens_refill_over_time(self):
        from api.middleware.rate_limit import _mem_store, _mem_lock
        identity = "spike-3"
        key_mem = f"spike_mem:{identity}"

        # Drain all tokens
        for _ in range(3):
            self._check(identity)

        # Manually set the bucket state to have refilled (simulate time passing)
        with _mem_lock:
            entry = _mem_store.get(key_mem)
            if entry and isinstance(entry, tuple):
                data, expiry = entry
                data["tokens"] = 3.0
                data["last_refill"] = time.time()
                _mem_store[key_mem] = (data, expiry)

        # Should now work again
        self._check(identity)
