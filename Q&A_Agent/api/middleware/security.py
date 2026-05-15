"""
api/middleware/security.py
───────────────────────────
Input validation helpers used at the top of every pipeline-triggering endpoint.

Covers:
  • SSRF protection — blocks requests to private/internal network ranges.
  • YouTube domain allowlist — rejects non-YouTube URLs passed to the
    YouTube ingestion path.
  • WAF patterns — rejects obvious XSS, SQLi, path-traversal, and RCE
    payload signatures.
  • File validation — MIME type allowlist + size cap.
"""

import re
import socket
from urllib.parse import urlparse

from fastapi import UploadFile

from api.errors import E, api_error

# ── SSRF: private/loopback/link-local ranges ──────────────────────────────────
_PRIVATE_IP = re.compile(
    r"(^127\.)|(^10\.)|(^172\.(1[6-9]|2\d|3[01])\.)"
    r"|(^192\.168\.)|(^169\.254\.)|(^0\.0\.0\.0$)",
)
_PRIVATE_HOST = re.compile(
    r"^(localhost|metadata\.google\.internal|169\.254\.169\.254)$",
    re.IGNORECASE,
)

# ── YouTube allowlist ─────────────────────────────────────────────────────────
_YOUTUBE_HOSTS = frozenset({
    "youtube.com", "www.youtube.com", "m.youtube.com",
    "youtu.be", "youtube-nocookie.com", "www.youtube-nocookie.com",
})

# ── WAF patterns ─────────────────────────────────────────────────────────────
_WAF_PATTERNS = [
    (re.compile(r"<\s*script", re.I),                    "XSS script tag"),
    (re.compile(r"javascript\s*:", re.I),                "JavaScript URL"),
    (re.compile(r"on\w+\s*=\s*[\"']", re.I),            "inline event handler"),
    (re.compile(r"(union|select|insert|drop|delete|update|truncate)\s+", re.I), "SQL keyword"),
    (re.compile(r"\.\.[/\\]"),                           "path traversal"),
    (re.compile(r"(exec|eval|system|popen|subprocess)\s*\(", re.I), "RCE pattern"),
    (re.compile(r"file://", re.I),                       "file:// scheme"),
    (re.compile(r"(gopher|ldap|dict|ftp|sftp)://", re.I), "dangerous scheme"),
]

# ── File validation ───────────────────────────────────────────────────────────
ALLOWED_MIME_TYPES = frozenset({
    # Documents
    "application/pdf",
    "text/plain",           # .txt, .md, .rst, .csv
    "text/markdown",
    "text/csv",
    "text/x-rst",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    # Spreadsheets
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
    "application/vnd.ms-excel",                                            # .xls
    # Images
    "image/png",
    "image/jpeg",
    "image/webp",
    # Audio
    "audio/mpeg",           # .mp3
    "audio/wav",            # .wav
    "audio/x-wav",
    "audio/mp4",            # .m4a
    "audio/x-m4a",
    # Video
    "video/mp4",            # .mp4
    "video/webm",           # .webm
    "video/quicktime",      # .mov
    "video/x-msvideo",      # .avi
    "video/x-matroska",     # .mkv
    "video/avi",
    "application/octet-stream",  # generic fallback some browsers send
})

ALLOWED_EXTENSIONS = frozenset({
    ".pdf", ".txt", ".md", ".markdown", ".rst", ".csv",
    ".docx", ".xlsx", ".xls",
    ".png", ".jpg", ".jpeg", ".webp", ".gif",
    ".mp3", ".wav", ".m4a", ".aac", ".flac",
    ".mp4", ".webm", ".mov", ".avi", ".mkv",
})

MAX_FILE_BYTES = 50 * 1024 * 1024  # 50 MB


def _is_private_host(hostname: str) -> bool:
    if _PRIVATE_HOST.match(hostname):
        return True
    if _PRIVATE_IP.match(hostname):
        return True
    try:
        resolved = socket.gethostbyname(hostname)
        return bool(_PRIVATE_IP.match(resolved))
    except socket.gaierror:
        return False


def validate_url(url: str, request_id: str | None = None) -> None:
    """
    Reject non-http(s) schemes and SSRF-targetable hosts.
    Raises HTTPException 400 on violation.
    """
    try:
        parsed = urlparse(url.strip())
    except Exception:
        api_error(400, E.INVALID_URL, "Malformed URL.", request_id=request_id)

    if parsed.scheme not in ("http", "https"):
        api_error(400, E.INVALID_URL,
                  "Only http:// and https:// URLs are accepted.",
                  request_id=request_id)

    host = parsed.hostname or ""
    if not host:
        api_error(400, E.INVALID_URL, "URL has no hostname.", request_id=request_id)

    if _is_private_host(host):
        api_error(400, E.SSRF_BLOCKED,
                  "Requests to private/internal network addresses are not allowed.",
                  request_id=request_id)


def validate_youtube_url(url: str, request_id: str | None = None) -> None:
    """
    Validate URL is a known YouTube domain after passing base URL validation.
    """
    validate_url(url, request_id=request_id)
    host = (urlparse(url).hostname or "").lower().lstrip("www.")
    # Re-add www. check
    full_host = (urlparse(url).hostname or "").lower()
    if full_host not in _YOUTUBE_HOSTS:
        api_error(400, E.INVALID_YOUTUBE_URL,
                  "Only YouTube URLs (youtube.com / youtu.be) are accepted for video ingestion.",
                  request_id=request_id)


def waf_scan(text: str, request_id: str | None = None) -> None:
    """
    Scan a user-supplied string for obvious injection patterns.
    Raises HTTPException 400 if a match is found.
    """
    for pattern, label in _WAF_PATTERNS:
        if pattern.search(text):
            api_error(400, E.WAF_BLOCKED,
                      "Input contains disallowed content.",
                      request_id=request_id)


def validate_file(file: UploadFile, request_id: str | None = None) -> None:
    """
    Validate uploaded file MIME type, extension, and size.
    """
    import pathlib
    filename = file.filename or ""
    ext = pathlib.Path(filename).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        api_error(415, E.INVALID_FILE_TYPE,
                  f"File type '{ext or '(none)'}' is not supported. "
                  "Accepted: PDF, TXT, MD, RST, DOCX · XLSX, XLS, CSV · "
                  "PNG, JPG, JPEG, WEBP · MP3, WAV, M4A, MP4, MOV, AVI, WEBM, MKV.",
                  request_id=request_id)

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type and content_type not in ALLOWED_MIME_TYPES:
        api_error(415, E.INVALID_FILE_TYPE,
                  f"MIME type '{content_type}' is not accepted.",
                  request_id=request_id)

    if file.size and file.size > MAX_FILE_BYTES:
        api_error(413, E.FILE_TOO_LARGE,
                  f"File exceeds the 50 MB size limit ({file.size // (1024*1024)} MB received).",
                  request_id=request_id)
