"""
tests/test_security.py
───────────────────────
Tests for WAF patterns, URL validation, SSRF protection,
YouTube allowlist, and file validation.
"""

import io
import pytest
from fastapi import HTTPException


# ── WAF pattern tests ─────────────────────────────────────────────────────────
class TestWafScan:
    def _waf(self, text):
        from api.middleware.security import waf_scan
        return waf_scan(text)

    def test_clean_text_passes(self):
        self._waf("Cloud computing introduction chapter 1")

    def test_xss_script_tag_blocked(self):
        with pytest.raises(HTTPException) as exc:
            self._waf("<script>alert('xss')</script>")
        assert exc.value.status_code == 400
        assert exc.value.detail["error_code"] == "WAF_BLOCKED"

    def test_javascript_url_blocked(self):
        with pytest.raises(HTTPException):
            self._waf("javascript:void(0)")

    def test_sql_injection_blocked(self):
        with pytest.raises(HTTPException):
            self._waf("SELECT * FROM users WHERE 1=1")

    def test_path_traversal_blocked(self):
        with pytest.raises(HTTPException):
            self._waf("../../etc/passwd")

    def test_rce_pattern_blocked(self):
        with pytest.raises(HTTPException):
            self._waf("eval(os.system('ls'))")

    def test_file_scheme_blocked(self):
        with pytest.raises(HTTPException):
            self._waf("file:///etc/hosts")

    def test_youtube_url_not_blocked(self):
        self._waf("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    def test_normal_url_not_blocked(self):
        self._waf("https://en.wikipedia.org/wiki/Cloud_computing")


# ── URL validation / SSRF tests ───────────────────────────────────────────────
class TestValidateUrl:
    def _validate(self, url):
        from api.middleware.security import validate_url
        return validate_url(url)

    def test_valid_https_url_passes(self):
        self._validate("https://example.com/article")

    def test_valid_http_url_passes(self):
        self._validate("http://example.com/page")

    def test_localhost_blocked(self):
        with pytest.raises(HTTPException) as exc:
            self._validate("http://localhost/admin")
        assert exc.value.detail["error_code"] == "SSRF_BLOCKED"

    def test_127_blocked(self):
        with pytest.raises(HTTPException):
            self._validate("http://127.0.0.1/secret")

    def test_10_range_blocked(self):
        with pytest.raises(HTTPException):
            self._validate("http://10.0.0.1/internal")

    def test_192_168_blocked(self):
        with pytest.raises(HTTPException):
            self._validate("http://192.168.1.1/router")

    def test_file_scheme_blocked(self):
        with pytest.raises(HTTPException) as exc:
            self._validate("file:///etc/passwd")
        assert exc.value.status_code == 400

    def test_ftp_scheme_blocked(self):
        with pytest.raises(HTTPException):
            self._validate("ftp://files.example.com/doc.pdf")

    def test_empty_host_blocked(self):
        with pytest.raises(HTTPException):
            self._validate("https:///no-host")


# ── YouTube URL allowlist tests ───────────────────────────────────────────────
class TestValidateYoutubeUrl:
    def _validate_yt(self, url):
        from api.middleware.security import validate_youtube_url
        return validate_youtube_url(url)

    def test_youtube_com_accepted(self):
        self._validate_yt("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    def test_youtu_be_accepted(self):
        self._validate_yt("https://youtu.be/dQw4w9WgXcQ")

    def test_m_youtube_accepted(self):
        self._validate_yt("https://m.youtube.com/watch?v=abc123")

    def test_vimeo_rejected(self):
        with pytest.raises(HTTPException) as exc:
            self._validate_yt("https://vimeo.com/123456")
        assert exc.value.detail["error_code"] == "INVALID_YOUTUBE_URL"

    def test_dailymotion_rejected(self):
        with pytest.raises(HTTPException):
            self._validate_yt("https://www.dailymotion.com/video/x123")

    def test_ssrf_still_blocked_for_youtube_path(self):
        with pytest.raises(HTTPException):
            self._validate_yt("http://127.0.0.1/watch?v=abc")


# ── File validation tests ─────────────────────────────────────────────────────
class TestValidateFile:
    def _make_upload(self, filename, content_type, size_bytes=1024):
        from unittest.mock import MagicMock
        upload = MagicMock()
        upload.filename = filename
        upload.content_type = content_type
        upload.size = size_bytes
        return upload

    def _validate(self, filename, content_type="application/pdf", size=1024):
        from api.middleware.security import validate_file
        upload = self._make_upload(filename, content_type, size)
        return validate_file(upload)

    def test_pdf_accepted(self):
        self._validate("document.pdf", "application/pdf")

    def test_txt_accepted(self):
        self._validate("notes.txt", "text/plain")

    def test_mp4_accepted(self):
        self._validate("video.mp4", "video/mp4")

    def test_exe_rejected(self):
        with pytest.raises(HTTPException) as exc:
            self._validate("malware.exe", "application/octet-stream")
        assert exc.value.detail["error_code"] == "INVALID_FILE_TYPE"

    def test_sh_rejected(self):
        with pytest.raises(HTTPException):
            self._validate("script.sh", "text/plain")

    def test_oversized_file_rejected(self):
        with pytest.raises(HTTPException) as exc:
            self._validate("big.pdf", "application/pdf", size=51 * 1024 * 1024)
        assert exc.value.detail["error_code"] == "FILE_TOO_LARGE"
