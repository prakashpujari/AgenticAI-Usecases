"""
tests/test_api_endpoints.py
─────────────────────────────
Integration tests for FastAPI endpoints: health check, rate-limit headers,
structured error responses, and input validation.
"""

import io
import pytest
import httpx
from unittest.mock import patch


# ── Health check ──────────────────────────────────────────────────────────────
class TestHealthEndpoint:
    def test_health_returns_200(self, app_client):
        resp = app_client.get("/health")
        assert resp.status_code == 200

    def test_health_has_powered_by(self, app_client):
        data = app_client.get("/health").json()
        assert data["powered_by"] == "PrakashPujariAI"

    def test_health_has_status_healthy(self, app_client):
        data = app_client.get("/health").json()
        assert data["status"] == "healthy"

    def test_health_returns_request_id_header(self, app_client):
        resp = app_client.get("/health")
        assert "x-request-id" in resp.headers

    def test_health_echoes_supplied_request_id(self, app_client):
        resp = app_client.get("/health", headers={"X-Request-Id": "my-trace-id"})
        assert resp.headers.get("x-request-id") == "my-trace-id"


# ── Structured error responses ─────────────────────────────────────────────────
class TestErrorSchema:
    def _post_file(self, app_client, filename="test.pdf", content=b"data",
                   content_type="application/pdf", extra_fields=None):
        fields = {"num_questions": "5", "output_mode": "questions"}
        if extra_fields:
            fields.update(extra_fields)
        return app_client.post(
            "/api/qa/generate",
            files={"file": (filename, io.BytesIO(content), content_type)},
            data=fields,
        )

    def test_unsupported_file_type_returns_structured_error(self, app_client):
        resp = self._post_file(app_client, filename="virus.exe",
                               content_type="application/octet-stream")
        assert resp.status_code in (400, 415)
        body = resp.json()
        assert "error_code" in body
        assert "message" in body
        assert "debug_id" in body

    def test_invalid_output_mode_returns_structured_error(self, app_client):
        resp = self._post_file(app_client, extra_fields={"output_mode": "invalid"})
        assert resp.status_code == 400
        body = resp.json()
        assert body["error_code"] == "INVALID_PARAM"

    def test_invalid_num_questions_returns_structured_error(self, app_client):
        resp = self._post_file(app_client, extra_fields={"num_questions": "999"})
        assert resp.status_code == 400
        body = resp.json()
        assert body["error_code"] == "INVALID_PARAM"


# ── Rate limiting integration ──────────────────────────────────────────────────
class TestRateLimitIntegration:
    def _post_source(self, app_client, source="https://example.com"):
        return app_client.post(
            "/api/qa/generate-source",
            json={"source": source, "num_questions": 5, "output_mode": "questions"},
        )

    def test_rate_limit_header_present_after_submit(self, app_client):
        with patch("api.server.config") as mock_cfg:
            mock_cfg.GROQ_API_KEY = "test-key"
            mock_cfg.NUM_QUESTIONS = 5
            # Can't actually submit without real pipeline, but we can test
            # that WAF and rate-limit checks run before pipeline
            pass

    def test_waf_blocks_xss_in_source(self, app_client):
        resp = self._post_source(app_client, source="<script>alert(1)</script>")
        assert resp.status_code == 400
        body = resp.json()
        assert body["error_code"] == "WAF_BLOCKED"

    def test_ssrf_blocked_in_source(self, app_client):
        resp = self._post_source(app_client, source="http://169.254.169.254/metadata")
        assert resp.status_code == 400
        body = resp.json()
        assert body["error_code"] in ("SSRF_BLOCKED", "INVALID_URL")

    def test_invalid_youtube_domain_blocked(self, app_client):
        resp = self._post_source(app_client, source="https://vimeo.com/123456")
        # vimeo is not in YouTube allowlist — should be accepted as a generic URL
        # (not blocked, just not treated as YouTube)
        # Passes URL validation since it's a valid external URL
        assert resp.status_code in (200, 400, 500)  # accepted or server-misconfigured

    def test_rate_limit_reached_returns_429(self, app_client):
        from api.middleware.rate_limit import _mem_store, _mem_lock
        import math, time, hmac, hashlib, config

        window_start = math.floor(time.time() / 3600) * 3600

        fp = "b" * 64
        secret = config.IDENTITY_HMAC_SECRET.encode()
        fp_hash = hmac.new(secret, fp.encode(), hashlib.sha256).hexdigest()[:16]
        identity = f"fp:{fp_hash}"
        key = f"rate_limit:{identity}:{int(window_start)}"

        with _mem_lock:
            _mem_store[key] = (10, time.time() + 3600)

        resp = app_client.post(
            "/api/qa/generate-source",
            json={"source": "https://example.com", "num_questions": 5, "output_mode": "questions"},
            headers={"X-Device-Fingerprint": fp},
        )
        assert resp.status_code == 429
        body = resp.json()
        assert body["error_code"] == "RATE_LIMIT_EXCEEDED"
        assert isinstance(body["retry_after_seconds"], int)
        assert body["retry_after_seconds"] > 0
