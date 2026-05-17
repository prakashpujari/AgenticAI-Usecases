"""
config.py
─────────
Central, immutable configuration for the Q&A Agent pipeline.

Every value has a sensible hard-coded default and can be overridden via:
  • A .env file in the project root (loaded by python-dotenv at import time)
  • A real OS environment variable (takes precedence over .env)

Design choice — flat module-level namespace
────────────────────────────────────────────
All settings are plain module-level constants (not a class or dataclass).
This avoids circular-import problems that arise when a settings object is
instantiated and passed between modules.  Any module that needs a config
value does:

    import config
    config.OPENAI_MODEL   # always up-to-date, no object to pass around

Why python-dotenv?
──────────────────
load_dotenv() reads key=value pairs from .env into os.environ.  It is:
  • Idempotent — safe to call multiple times (e.g. during testing).
  • Non-destructive — will NOT overwrite variables already set in the
    actual OS environment, so CI/CD secrets take precedence over .env.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# ─── Bootstrap ────────────────────────────────────────────────────────────────
# Must run before any os.getenv() call so the .env values are available.
load_dotenv()

# Force PyTorch-only mode in transformers — prevents the broken TF import chain
# (transformers → image_transforms → tensorflow → protobuf version error).
# Must be set before any 'import transformers' happens anywhere in the process.
os.environ["USE_TORCH"] = "1"
os.environ["USE_TF"] = "0"

# ─── Directory layout ─────────────────────────────────────────────────────────
# BASE_DIR is the project root (the directory containing this file).
# All other paths are expressed relative to it so the project is relocatable.
BASE_DIR: Path   = Path(__file__).parent
DATA_DIR: Path   = BASE_DIR / "data"      # Source PDFs + FAISS vector index
OUTPUT_DIR: Path = BASE_DIR / "output"   # Generated Markdown + PDF outputs
LOGS_DIR: Path   = BASE_DIR / "logs"     # Rotating application log files

# Create on first import — downstream modules must never mkdir themselves.
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# ─── File paths ────────────────────────────────────────────────────────────────
SAMPLE_PDF_PATH: Path      = DATA_DIR   / "sample_document.pdf"
FAISS_INDEX_PATH: Path     = DATA_DIR   / "faiss_index"
OUTPUT_MARKDOWN_PATH: Path = OUTPUT_DIR / "qa_output.md"
OUTPUT_PDF_PATH: Path      = OUTPUT_DIR / "qa_output.pdf"
# Pipeline metrics JSON report — written at the end of every successful run.
METRICS_REPORT_PATH: Path  = OUTPUT_DIR / "pipeline_metrics.json"

# ─── Groq ──────────────────────────────────────────────────────────────────────
GROQ_API_KEY: str        = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL: str          = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_FALLBACK_MODEL: str = os.getenv("GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant")
GROQ_VISION_MODEL: str   = os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

# ── Google Gemini (free fallback when Groq quota is exhausted) ─────────────────
# IMPORTANT: Use a key from https://aistudio.google.com/apikey (NOT Google Cloud
# Console) — AI Studio keys include the free tier quota automatically.
# Free tier: 1 500 req/day, 15 req/min for gemini-2.0-flash.
GEMINI_API_KEY: str  = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str    = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# ── Hugging Face (secondary free fallback) ─────────────────────────────────────
# Free Serverless Inference API — no credit card, just a HuggingFace account.
# Get a token at https://huggingface.co/settings/tokens (read-only token).
HF_API_KEY: str   = os.getenv("HF_API_KEY", "")
HF_MODEL: str     = os.getenv("HF_MODEL", "mistralai/Mistral-7B-Instruct-v0.3")

# Embeddings use a local ONNX model via fastembed (Groq has no embedding API).
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

# ─── YouTube transcript (bypass cloud-IP block) ───────────────────────────────
# Render/AWS datacenter IPs are blocked by YouTube for transcript requests.
#
# Option A — Supadata.ai (recommended, easiest):
#   1. Sign up free at https://supadata.ai  (10 000 requests/month free tier).
#   2. Copy your API key from the dashboard.
#   3. Set SUPADATA_API_KEY in the Render dashboard (Environment → Add variable).
#
# Option B — YouTube cookies (advanced):
#   1. Log into YouTube in Chrome/Firefox.
#   2. Install the "Get cookies.txt LOCALLY" browser extension.
#   3. Visit youtube.com, click the extension, export "Current site" cookies.
#   4. Base64-encode the file:  base64 -w0 cookies.txt
#   5. Set YOUTUBE_COOKIES in Render dashboard (Environment → Add variable).
SUPADATA_API_KEY: str  = os.getenv("SUPADATA_API_KEY", "")
YOUTUBE_COOKIES: str   = os.getenv("YOUTUBE_COOKIES", "")
# Option C — generic HTTP/SOCKS5 proxy for transcript fetching.
# Format: "http://user:pass@host:port" or "socks5://host:port".
# Used by both youtube-transcript-api and yt-dlp.
YOUTUBE_PROXY_URL: str = os.getenv("YOUTUBE_PROXY_URL", "")

# ─── Redis (rate limiting + response cache) ───────────────────────────────────
# When REDIS_URL is empty the rate limiter falls back to in-memory counters
# and the response cache is disabled.
REDIS_URL: str = os.getenv("REDIS_URL", "")

# How long (seconds) to cache a pipeline result keyed on content hash.
# 0 = caching disabled.
CACHE_TTL: int = int(os.getenv("CACHE_TTL", "86400"))  # 24 hours

# ─── PostgreSQL (job persistence + dashboard analytics) ───────────────────────
# External Render PostgreSQL — stats persist across sleep/restart cycles.
# Override via DATABASE_URL env var in Render dashboard or render.yaml.
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://ai_apps_db_nzf4_user:upzKUnedEMR1EvhNJsiltS1SGnoBzE3F"
    "@dpg-d84sbagjo89c73bskf10-a.oregon-postgres.render.com/ai_apps_db_nzf4"
    "?sslmode=require",
)

# ─── Rate limiting ─────────────────────────────────────────────────────────────
RATE_LIMIT_MAX:    int   = int(os.getenv("RATE_LIMIT_MAX",    "10"))
RATE_LIMIT_WINDOW: int   = int(os.getenv("RATE_LIMIT_WINDOW", "3600"))  # seconds
BURST_MAX:         int   = int(os.getenv("BURST_MAX",         "3"))
BURST_REFILL_RATE: float = float(os.getenv("BURST_REFILL_RATE", "0.05")) # tokens/sec (3/min)
GLOBAL_LLM_MAX:    int   = int(os.getenv("GLOBAL_LLM_MAX",   "100"))    # per minute

# ─── Security ─────────────────────────────────────────────────────────────────
# IDENTITY_HMAC_SECRET must be a random 32-byte hex string.
# Used to one-way hash IP/fingerprint before storing in Redis (GDPR-safe).
IDENTITY_HMAC_SECRET: str = os.getenv(
    "IDENTITY_HMAC_SECRET",
    "dev-secret-change-in-production-000000000000000000000000",
)

# Allowed CORS origin — set to your exact Vercel domain in production.
CORS_ALLOWED_ORIGIN: str = os.getenv(
    "CORS_ALLOWED_ORIGIN",
    "*",  # permissive default for local dev; lock down in production
)

# ─── RAG / text-splitting ──────────────────────────────────────────────────────
# CHUNK_SIZE controls the maximum number of characters per chunk fed to the
# embeddings API.  Larger chunks → more context per retrieval result but
# fewer unique chunks → lower recall diversity.
CHUNK_SIZE: int    = int(os.getenv("CHUNK_SIZE", "1000"))
# CHUNK_OVERLAP ensures adjacent chunks share context so sentence boundaries
# don't cause a topic to be split across two non-overlapping chunks.
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "200"))

# ─── Q&A generation ────────────────────────────────────────────────────────────
NUM_QUESTIONS: int   = int(os.getenv("NUM_QUESTIONS", "10"))
# TOP_K_RETRIEVAL: how many chunks are fetched per similarity query.
# A higher value gives the LLM broader context at the cost of a larger prompt.
TOP_K_RETRIEVAL: int = int(os.getenv("TOP_K_RETRIEVAL", "15"))
# TEMPERATURE = 0 → deterministic, factual responses.
# TEMPERATURE > 0.5 → more creative / varied wording (not recommended for Q&A).
TEMPERATURE: float   = float(os.getenv("TEMPERATURE", "0.3"))

# ─── Observability ─────────────────────────────────────────────────────────────
# LOG_LEVEL applies to the console handler.  The file handler always captures
# DEBUG regardless of this setting.
LOG_LEVEL: str  = os.getenv("LOG_LEVEL", "INFO").upper()

# Set LOG_TO_FILE=false to disable file logging (useful in serverless envs
# where the filesystem may not be writable).
LOG_TO_FILE: bool = os.getenv("LOG_TO_FILE", "true").lower() in ("1", "true", "yes")

# RotatingFileHandler will create a new file once the current one exceeds
# LOG_MAX_BYTES, keeping LOG_BACKUP_COUNT archived copies.
LOG_MAX_BYTES: int    = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))  # 10 MB
LOG_BACKUP_COUNT: int = int(os.getenv("LOG_BACKUP_COUNT", "5"))

# ─── LangSmith tracing ─────────────────────────────────────────────────────────
# LangSmith is LangChain's observability platform.  When tracing is enabled,
# every LCEL chain invocation (prompts, LLM calls, retrievers) is automatically
# captured as a structured trace run in the LangSmith UI.
#
# To enable:
#   1. Create a free account at https://smith.langchain.com/
#   2. Generate an API key (Settings → API Keys).
#   3. In your .env file, set:
#        LANGCHAIN_TRACING_V2=true
#        LANGCHAIN_API_KEY=<your_key>
#        LANGCHAIN_PROJECT=qa-agent          # optional; defaults below
#        LANGCHAIN_ENDPOINT=https://api.smith.langchain.com  # optional
#
# LangChain's SDK checks these variables in os.environ at import time.
# config.py re-exports them as typed constants AND ensures they are written
# back into os.environ (see setup_langsmith() in observability/langsmith_tracer.py)
# so that loading from .env via load_dotenv() is sufficient.
LANGCHAIN_TRACING_V2: bool = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() in (
    "1", "true", "yes"
)
LANGCHAIN_API_KEY: str     = os.getenv("LANGCHAIN_API_KEY", "")
LANGCHAIN_PROJECT: str     = os.getenv("LANGCHAIN_PROJECT", "qa-agent")
LANGCHAIN_ENDPOINT: str    = os.getenv(
    "LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com"
)
