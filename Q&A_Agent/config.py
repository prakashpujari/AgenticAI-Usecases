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

# ─── OpenAI ────────────────────────────────────────────────────────────────────
# OPENAI_API_KEY must be set; an empty string causes an EnvironmentError at
# the first API call.  We deliberately do NOT raise here to allow the config
# module to be imported during tests that mock the API.
OPENAI_API_KEY: str         = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str           = os.getenv("OPENAI_MODEL", "gpt-4o")
OPENAI_EMBEDDING_MODEL: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

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
