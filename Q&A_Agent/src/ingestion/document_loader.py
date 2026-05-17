"""
src/ingestion/document_loader.py
─────────────────────────────────
Universal document loader — accepts any supported format and returns a
clean plain-text string ready for the chunking / embedding stages.

Supported input types
──────────────────────
  • Local files
      .pdf          — extracted via pypdf + cleaning pipeline
      .txt .md .rst .log .csv .tsv — read as UTF-8 plain text
      .docx         — extracted via python-docx (install: pip install python-docx)
      .xlsx .xls    — extracted via openpyxl / xlrd (install: pip install openpyxl)
      <other>       — attempted as UTF-8 plain text; raises ValueError on failure

  • HTTP / HTTPS URLs
      The URL is downloaded to a temporary file, then processed using the
      extension inferred from the Content-Type header or the URL path.

Public API
──────────
    load_document(source) → str
        source: str | Path   — local file path OR an http(s):// URL
        Returns cleaned plain text.
        Raises FileNotFoundError, ValueError, or ImportError on failure.
"""

import base64
import logging
import os
import re
import tempfile
import time
import urllib.request
from html import unescape
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import config
from observability.logger import get_logger
from src.ingestion.pdf_extractor import extract_and_clean

logger = get_logger(__name__)

# Extensions treated as plain-text without any special parsing
_PLAIN_TEXT_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".rst", ".log",
    ".csv", ".tsv", ".json", ".yaml", ".yml", ".xml", ".html", ".htm",
}

_AUDIO_VIDEO_EXTENSIONS = {
    ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".webm",
    ".mp4", ".mov", ".avi", ".mkv", ".mpeg", ".mpg",
}

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff"}


# ─── Private helpers ───────────────────────────────────────────────────────────

def _load_plain_text(path: Path) -> str:
    """Read any UTF-8 (or latin-1 fallback) plain-text file."""
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raw = path.read_text(encoding="latin-1")
    text = raw.strip()
    if not text:
        raise ValueError(f"File appears to be empty: {path}")
    logger.info(
        "Loaded plain-text file '%s' — %d chars",
        path.name,
        len(text),
        extra={"file": str(path), "char_count": len(text)},
    )
    return text


def _load_docx(path: Path) -> str:
    """Extract text from a .docx file using python-docx."""
    try:
        import docx  # python-docx
    except ImportError as exc:
        raise ImportError(
            "python-docx is required to read .docx files.\n"
            "  pip install python-docx"
        ) from exc

    doc = docx.Document(str(path))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    text = "\n\n".join(paragraphs)
    if not text.strip():
        raise ValueError(f"No extractable text found in DOCX: {path}")
    logger.info(
        "Loaded DOCX '%s' — %d paragraphs, %d chars",
        path.name,
        len(paragraphs),
        len(text),
        extra={"file": str(path), "char_count": len(text)},
    )
    return text


def _load_xlsx(path: Path) -> str:
    """Extract text from an .xlsx / .xls spreadsheet using openpyxl."""
    try:
        import openpyxl
    except ImportError as exc:
        raise ImportError(
            "openpyxl is required to read .xlsx files.\n"
            "  pip install openpyxl"
        ) from exc

    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    rows: list[str] = []
    for sheet in wb.worksheets:
        rows.append(f"=== Sheet: {sheet.title} ===")
        for row in sheet.iter_rows(values_only=True):
            # Skip entirely empty rows
            cells = [str(c) if c is not None else "" for c in row]
            line = "\t".join(cells).strip()
            if line:
                rows.append(line)
    wb.close()

    text = "\n".join(rows)
    if not text.strip():
        raise ValueError(f"No extractable data found in spreadsheet: {path}")
    logger.info(
        "Loaded spreadsheet '%s' — %d rows, %d chars",
        path.name,
        len(rows),
        len(text),
        extra={"file": str(path), "char_count": len(text)},
    )
    return text


def _extract_text_from_html(html_text: str) -> str:
    """Best-effort HTML to readable plain text conversion."""
    # Remove script/style blocks first
    html_text = re.sub(r"<script[\\s\\S]*?</script>", " ", html_text, flags=re.IGNORECASE)
    html_text = re.sub(r"<style[\\s\\S]*?</style>", " ", html_text, flags=re.IGNORECASE)
    # Strip all remaining tags
    text = re.sub(r"<[^>]+>", " ", html_text)
    text = unescape(text)
    # Normalize whitespace
    text = re.sub(r"\\s+", " ", text).strip()
    if not text:
        raise ValueError("The webpage did not contain extractable text content.")
    return text


def _youtube_video_id(url: str) -> str | None:
    """Extract YouTube video ID from common URL formats."""
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if "youtu.be" in host:
        vid = parsed.path.strip("/")
        return vid or None
    if "youtube.com" in host or "youtube-nocookie.com" in host:
        if parsed.path == "/watch":
            return parse_qs(parsed.query).get("v", [None])[0]
        if parsed.path.startswith("/shorts/"):
            return parsed.path.split("/shorts/")[-1].split("/")[0]
        if parsed.path.startswith("/live/"):
            return parsed.path.split("/live/")[-1].split("/")[0]
        if parsed.path.startswith("/embed/"):
            return parsed.path.split("/embed/")[-1].split("/")[0]

    # Conservative fallback for less common URL forms (e.g. /v/<id>, attribution links).
    match = re.search(r"(?:v=|/v/|vi=|/vi/)([A-Za-z0-9_-]{11})", url)
    if match:
        return match.group(1)

    return None


def _parse_vtt(vtt: str) -> str:
    """Extract plain text from a WebVTT subtitle string, stripping timestamps and tags."""
    seen: set[str] = set()
    lines: list[str] = []
    for line in vtt.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(("WEBVTT", "NOTE", "STYLE", "REGION", "Kind:", "Language:")):
            continue
        # Timestamp lines: "00:00:00.000 --> 00:00:05.000 ..."
        if re.match(r"\d{2}:\d{2}[\d:,.>< \-]+", line):
            continue
        # Sequence number lines
        if re.match(r"^\d+$", line):
            continue
        # Strip inline HTML/VTT tags (<c>, <b>, <i>, <00:00:00.000>)
        line = re.sub(r"<[^>]+>", "", line)
        line = unescape(line).strip()
        if line and line not in seen:
            seen.add(line)
            lines.append(line)
    return " ".join(lines)


def _fetch_transcript_api(video_id: str) -> list:
    """Call youtube-transcript-api and return raw transcript items."""
    from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore[import]

    api = YouTubeTranscriptApi()
    fetch_fn = getattr(api, "fetch", None)
    if callable(fetch_fn):
        return list(fetch_fn(video_id))

    list_fn = getattr(api, "list", None)
    if not callable(list_fn):
        raise RuntimeError("Unsupported youtube-transcript-api version.")

    transcript_list = list_fn(video_id)
    try:
        t = transcript_list.find_transcript(["en", "en-US", "en-GB"])
    except Exception:  # noqa: BLE001
        t = transcript_list.find_generated_transcript(["en", "en-US", "en-GB"])
    return list(t.fetch())


def _fetch_transcript_ytdlp_whisper(url: str) -> str:
    """
    Download YouTube audio via yt-dlp and transcribe with Groq Whisper.

    Why this works on cloud IPs (Render, AWS, GCP):
      - YouTube's transcript/caption endpoints (/youtubei/v1/get_transcript,
        /api/timedtext) are filtered by IP and return empty or 403 for
        datacenter ranges.
      - Audio streams are served from YouTube's googlevideo.com CDN, which
        is NOT filtered by cloud-IP blocks — the same CDN used by all
        YouTube users globally.
    So yt-dlp can download the audio even when caption endpoints fail.
    Groq Whisper then transcribes it in ~10-30 s.
    """
    try:
        import yt_dlp  # type: ignore[import]
    except ImportError as exc:
        raise ImportError("yt-dlp is required. pip install yt-dlp") from exc

    if not config.GROQ_API_KEY:
        raise EnvironmentError(
            "GROQ_API_KEY is required for the audio transcription fallback."
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        ydl_opts = {
            # Prefer small audio-only streams that Groq Whisper accepts directly
            "format": (
                "bestaudio[ext=m4a][filesize<20M]"
                "/bestaudio[ext=webm][filesize<20M]"
                "/bestaudio[filesize<20M]"
                "/bestaudio"
            ),
            "outtmpl":    os.path.join(tmpdir, "audio.%(ext)s"),
            "quiet":      True,
            "no_warnings": True,
            "noplaylist": True,
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            },
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        _WHISPER_EXTS = {".m4a", ".webm", ".mp3", ".wav", ".mp4", ".mpeg", ".mpga"}
        audio_files = [
            f for f in os.listdir(tmpdir)
            if Path(f).suffix.lower() in _WHISPER_EXTS
        ]
        if not audio_files:
            raise ValueError(
                "yt-dlp could not download audio from this YouTube video."
            )

        audio_path = Path(os.path.join(tmpdir, audio_files[0]))
        size_mb = audio_path.stat().st_size / (1024 * 1024)
        if size_mb > 24:
            raise ValueError(
                f"Audio is {size_mb:.1f} MB — exceeds Groq Whisper's 25 MB limit. "
                "Try a shorter video, or paste the transcript as a .txt file."
            )

        logger.info(
            "Transcribing YouTube audio via Groq Whisper (%.1f MB, %s)",
            size_mb, audio_path.suffix,
        )
        return _load_media_with_openai(audio_path)


def _fetch_transcript_ytdlp(url: str) -> str:
    """
    Last-resort fallback: download auto-generated VTT subtitles via yt-dlp
    using the Android player client (less blocked than web player on cloud IPs).
    """
    try:
        import yt_dlp  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "yt-dlp is required as a YouTube fallback. "
            "Install with: pip install yt-dlp"
        ) from exc

    with tempfile.TemporaryDirectory() as tmpdir:
        ydl_opts = {
            "writeautomaticsub": True,
            "writesubtitles":    True,
            "skip_download":     True,
            "subtitlesformat":   "vtt",
            "subtitleslangs":    ["en", "en-US", "en-GB", "en.*"],
            "outtmpl":           os.path.join(tmpdir, "%(id)s.%(ext)s"),
            "quiet":             True,
            "no_warnings":       True,
            # Android player client is less filtered on cloud/datacenter IPs
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "web"],
                    "player_skip":   ["webpage"],
                }
            },
            "http_headers": {
                "User-Agent": (
                    "com.google.android.youtube/19.09.37 "
                    "(Linux; U; Android 11) gzip"
                ),
            },
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        vtt_files = [f for f in os.listdir(tmpdir) if f.endswith(".vtt")]
        if not vtt_files:
            raise ValueError("yt-dlp could not find subtitles for this video.")

        vtt_files.sort(key=lambda f: (0 if "en" in f.lower() else 1, f))
        vtt_content = Path(os.path.join(tmpdir, vtt_files[0])).read_text(encoding="utf-8")

    text = _parse_vtt(vtt_content)
    if not text:
        raise ValueError("yt-dlp downloaded subtitles but they contained no readable text.")
    return text


def _load_youtube_transcript(url: str) -> str:
    """
    Fetch transcript from a YouTube URL with three-layer fallback.

    Layer 1 — youtube-transcript-api (fastest, no download):
        Works on residential IPs. Blocked on cloud/datacenter IPs (Render,
        AWS, GCP) because YouTube filters /get_transcript web requests by IP.

    Layer 2 — yt-dlp VTT subtitle download (android player client):
        Uses yt-dlp with the Android player API which hits different YouTube
        endpoints. Faster than Whisper; occasionally works on cloud IPs.

    Layer 3 — yt-dlp audio + Groq Whisper (cloud-safe guaranteed):
        Downloads audio from YouTube's googlevideo.com CDN (NOT filtered by
        cloud-IP blocks) then transcribes with Groq Whisper. Slower (~30 s)
        but the only guaranteed path when running on Render or AWS.
    """
    video_id = _youtube_video_id(url)
    if not video_id:
        raise ValueError(f"Could not extract YouTube video id from URL: {url}")

    # ── Layer 1: youtube-transcript-api ───────────────────────────────────────
    try:
        from youtube_transcript_api import YouTubeTranscriptApi  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "youtube-transcript-api is required. pip install youtube-transcript-api"
        ) from exc

    for attempt in range(3):
        try:
            items = _fetch_transcript_api(video_id)

            def _snippet_text(item: object) -> str:
                if isinstance(item, dict):
                    return str(item.get("text", "")).strip()
                return str(getattr(item, "text", "")).strip()

            text = " ".join(_snippet_text(i) for i in items).strip()
            if not text:
                raise ValueError("Transcript API returned empty text.")
            logger.info(
                "YouTube transcript loaded via API (video=%s, %d chars, attempt=%d)",
                video_id, len(text), attempt + 1,
                extra={"video_id": video_id, "char_count": len(text)},
            )
            return text

        except Exception as exc:  # noqa: BLE001
            lowered = f"{type(exc).__name__} {exc}".lower()

            if "transcriptsdisabled" in lowered or "transcript is disabled" in lowered:
                raise ValueError("YouTube captions are disabled for this video.") from exc
            if "notranscriptfound" in lowered or "no transcript" in lowered:
                raise ValueError("No transcript available for this video/language.") from exc
            if "videounavailable" in lowered or "video unavailable" in lowered:
                raise ValueError(
                    "This YouTube video is unavailable (private, removed, or geo-restricted)."
                ) from exc
            if "toomanyrequests" in lowered or "too many requests" in lowered or "429" in lowered:
                wait = 2 ** attempt
                logger.warning("YouTube API rate-limited (attempt %d/3). Waiting %ds…", attempt + 1, wait)
                time.sleep(wait)
                continue

            logger.warning("youtube-transcript-api failed (%s). Trying InnerTube…", type(exc).__name__)
            break

    # ── Layer 2: yt-dlp VTT with Android player client ────────────────────────
    # (Faster than Whisper; sometimes works even on cloud IPs)
    logger.info("Trying yt-dlp VTT (android player) for video %s", video_id)
    try:
        text = _fetch_transcript_ytdlp(url)
        logger.info(
            "YouTube transcript loaded via yt-dlp VTT (video=%s, %d chars)",
            video_id, len(text),
            extra={"video_id": video_id, "char_count": len(text), "method": "yt-dlp-vtt"},
        )
        return text
    except Exception as vtt_exc:  # noqa: BLE001
        logger.warning("yt-dlp VTT failed (%s). Trying Whisper audio fallback…", vtt_exc)

    # ── Layer 3: yt-dlp audio download + Groq Whisper (cloud-safe) ───────────
    # Audio is fetched from googlevideo.com CDN — NOT filtered by cloud-IP blocks.
    logger.info("Trying yt-dlp audio + Groq Whisper for video %s", video_id)
    try:
        text = _fetch_transcript_ytdlp_whisper(url)
        logger.info(
            "YouTube transcript loaded via Whisper (video=%s, %d chars)",
            video_id, len(text),
            extra={"video_id": video_id, "char_count": len(text), "method": "whisper"},
        )
        return text
    except Exception as whisper_exc:  # noqa: BLE001
        logger.error("All YouTube transcript methods failed. Last error: %s", whisper_exc)
        raise ValueError(
            "Could not fetch the YouTube transcript.\n"
            "Possible reasons: video is private/age-restricted, or captions are disabled.\n"
            "Workaround: paste the video script as a .txt file and upload it instead."
        ) from whisper_exc


def _load_media_with_openai(path: Path) -> str:
    """Transcribe local audio/video files with Groq speech-to-text (Whisper)."""
    if not config.GROQ_API_KEY:
        raise EnvironmentError("GROQ_API_KEY is required for audio/video ingestion.")

    from groq import Groq

    client = Groq(api_key=config.GROQ_API_KEY)
    with path.open("rb") as media_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-large-v3",
            file=media_file,
            response_format="text",
        )

    text = transcript.strip() if isinstance(transcript, str) else str(transcript).strip()
    if not text:
        raise ValueError(f"No transcript text produced for media file: {path}")

    logger.info(
        "Transcribed media '%s' — %d chars",
        path.name,
        len(text),
        extra={"file": str(path), "char_count": len(text)},
    )
    return text


def _load_image_with_openai(path: Path) -> str:
    """Extract readable content from an image using Groq vision."""
    if not config.GROQ_API_KEY:
        raise EnvironmentError("GROQ_API_KEY is required for image ingestion.")

    from groq import Groq

    client = Groq(api_key=config.GROQ_API_KEY)
    mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
        ".tiff": "image/tiff",
    }.get(path.suffix.lower(), "image/png")

    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    data_url = f"data:{mime};base64,{b64}"

    resp = client.chat.completions.create(
        model=config.GROQ_VISION_MODEL,
        temperature=0.0,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Extract all meaningful text and key facts from this image. "
                            "Return plain text only."
                        ),
                    },
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
    )
    text = (resp.choices[0].message.content or "").strip()
    if not text:
        raise ValueError(f"No extractable text produced for image: {path}")

    logger.info(
        "Extracted image text '%s' — %d chars",
        path.name,
        len(text),
        extra={"file": str(path), "char_count": len(text)},
    )
    return text


def _content_type_to_suffix(content_type: str) -> str:
    """Map an HTTP Content-Type header value to a file extension."""
    ct = content_type.split(";")[0].strip().lower()
    _map = {
        "application/pdf":                                    ".pdf",
        "text/plain":                                         ".txt",
        "text/markdown":                                      ".md",
        "text/csv":                                           ".csv",
        "application/vnd.openxmlformats-officedocument"
        ".wordprocessingml.document":                         ".docx",
        "application/vnd.openxmlformats-officedocument"
        ".spreadsheetml.sheet":                               ".xlsx",
        "application/msword":                                 ".doc",
    }
    return _map.get(ct, "")


def _load_from_url(url: str) -> str:
    """Download a URL to a temp file, then load it with the appropriate handler."""
    parsed = urlparse(url)
    host = parsed.netloc.lower()

    if "youtube.com" in host or "youtu.be" in host:
        return _load_youtube_transcript(url)

    logger.info("Downloading document from URL: %s", url)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        content_type = resp.headers.get("Content-Type", "")
        # Infer extension: prefer URL path, fall back to Content-Type
        url_path_suffix = Path(urlparse(url).path).suffix.lower()
        suffix = url_path_suffix or _content_type_to_suffix(content_type) or ".txt"
        data = resp.read()

    # If the URL is an HTML webpage, extract visible text directly.
    if content_type.lower().startswith("text/html") or suffix in {"", ".html", ".htm"}:
        html_text = data.decode("utf-8", errors="replace")
        text = _extract_text_from_html(html_text)
        logger.info(
            "Loaded webpage '%s' — %d chars",
            url,
            len(text),
            extra={"url": url, "char_count": len(text)},
        )
        return text

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)

    logger.info(
        "Downloaded %d bytes → temp file %s (suffix=%s)",
        len(data),
        tmp_path.name,
        suffix,
    )
    try:
        return _load_local_file(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


def _load_local_file(path: Path) -> str:
    """Dispatch to the correct loader based on the file extension."""
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return extract_and_clean(path)

    if suffix in _PLAIN_TEXT_EXTENSIONS:
        return _load_plain_text(path)

    if suffix == ".docx":
        return _load_docx(path)

    if suffix in {".xlsx", ".xls"}:
        return _load_xlsx(path)

    if suffix in _AUDIO_VIDEO_EXTENSIONS:
        return _load_media_with_openai(path)

    if suffix in _IMAGE_EXTENSIONS:
        return _load_image_with_openai(path)

    # Unknown extension — attempt plain-text as a best-effort fallback
    logger.warning(
        "Unrecognised file extension '%s' for '%s' — attempting plain-text read",
        suffix,
        path.name,
    )
    return _load_plain_text(path)


# ─── Public API ────────────────────────────────────────────────────────────────

def load_document(source: "str | Path") -> str:
    """
    Load any supported document and return its text content.

    Args:
        source: A local file path (str or Path) OR an http(s):// URL string.

    Returns:
        Cleaned plain-text string ready for chunking.

    Raises:
        FileNotFoundError: If a local file path does not exist.
        ValueError:        If the file is empty or contains no extractable text.
        ImportError:       If a required optional dependency (python-docx,
                           openpyxl) is not installed.
        urllib.error.URLError: If the URL cannot be reached.
    """
    source_str = str(source).strip()

    # URL
    if re.match(r"^https?://", source_str, re.IGNORECASE):
        return _load_from_url(source_str)

    # Local file
    path = Path(source_str)
    if not path.exists():
        raise FileNotFoundError(f"Input document not found: {path.resolve()}")

    logger.info(
        "Loading document: %s  (%.1f KB)",
        path.resolve(),
        path.stat().st_size / 1024,
        extra={"file": str(path.resolve()), "size_kb": round(path.stat().st_size / 1024, 1)},
    )
    return _load_local_file(path)
