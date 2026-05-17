# Q&A Agent — AI-Powered Document Q&A Generator

> Upload any document, paste a URL, or drop a YouTube link — get structured multiple-choice questions and/or an AI summary as a downloadable PDF in seconds.

**Powered by PrakashPujariAI**

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Tech Stack](#tech-stack)
4. [Features](#features)
5. [Quick Start — Local Development](#quick-start--local-development)
6. [Configuration Reference](#configuration-reference)
7. [API Reference](#api-reference)
8. [Output Modes](#output-modes)
9. [Supported Input Types](#supported-input-types)
10. [Security](#security)
11. [Dashboard & Observability](#dashboard--observability)
12. [Caching & Performance](#caching--performance)
13. [Deployment — Render + Vercel](#deployment--render--vercel)
14. [Project Structure](#project-structure)

---

## Overview

Q&A Agent is a production-grade full-stack AI application that turns any document into study material:

- Accepts **20+ file types** plus web URLs and YouTube links
- Generates **MCQ practice questions** directly from document content via Groq LLM
- Produces **structured document summaries** via LLM
- Outputs both as a styled **downloadable PDF**
- **Two-layer response cache** (Redis + in-memory) — repeated requests skip the LLM entirely
- **PostgreSQL job persistence** with full dashboard analytics
- **Rate limiting, spike arrest, WAF, SSRF protection** — production hardened
- **LangGraph orchestration** — typed state machine pipeline
- **LLM retry + fallback** — primary → fallback model with exponential backoff

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      VERCEL EDGE  (Frontend)                            │
│                                                                         │
│   React + Tailwind  ──► /api/* rewrite ──► Render Backend              │
│   CDN-cached static assets  │  No secrets stored  │  HTTPS only        │
└─────────────────────────────────────────────────────────────────────────┘
                               │ HTTPS
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      RENDER  (FastAPI Backend)                          │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Middleware Stack                                                 │  │
│  │  RequestId → BodySizeLimit → CORS → extract_identity()           │  │
│  │  → check_spike_arrest() → check_rate_limit()                     │  │
│  │  → waf_scan() → validate_file/url()                              │  │
│  └─────────────────────────┬────────────────────────────────────────┘  │
│                             │                                           │
│  ┌──────────────────────────▼────────────────────────────────────────┐ │
│  │  Cache Check (Redis → In-Memory LRU)                              │ │
│  │  HIT → return cached PDF  │  MISS → queue job                    │ │
│  └──────────────────────────┬────────────────────────────────────────┘ │
│                             │                                           │
│  ┌──────────────────────────▼────────────────────────────────────────┐ │
│  │  Background Worker  (5-min hard timeout per job)                  │ │
│  │                                                                   │ │
│  │  LangGraph Pipeline:                                              │ │
│  │  extract_text → [summarize_text | generate_questions]             │ │
│  │               → format_output → convert_pdf                       │ │
│  │                                                                   │ │
│  │  LLM: Groq llama-3.3-70b-versatile                               │ │
│  │       ↳ fallback: llama-3.1-8b-instant                           │ │
│  │       ↳ retry: 3 attempts + exponential backoff                  │ │
│  └──────────────────────────┬────────────────────────────────────────┘ │
│                             │                                           │
│  ┌──────────────────────────▼────────────────────────────────────────┐ │
│  │  Job Lookup (status / download endpoints)                         │ │
│  │  SQLite (ephemeral, fast) ──MISS──► PostgreSQL (persistent)       │ │
│  │  Survives Render sleep/restart — previous jobs always found       │ │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Keep-Alive Pinger  (daemon thread)                              │  │
│  │  GET /health every 10 min → prevents Render free-tier sleep      │  │
│  │  Reads RENDER_EXTERNAL_URL — no-op in local dev                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  Redis (response cache + rate limiting counters)                        │
└─────────────────────────────────────────────────────────────────────────┘
                               │ sslmode=require
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              RENDER POSTGRESQL  (External — Persistent)                 │
│              Host: dpg-d84sbagjo89c73bskf10-a.oregon-postgres.render.com│
│              DB:   ai_apps_db_nzf4   Region: Oregon                     │
│                                                                         │
│  ┌─────────────────┐  ┌──────────────────────┐  ┌───────────────────┐  │
│  │   qa_jobs       │  │  qa_stage_timings    │  │   qa_reviews      │  │
│  │─────────────────│  │──────────────────────│  │───────────────────│  │
│  │ pipeline_id PK  │  │ id  SERIAL PK        │  │ review_id  PK     │  │
│  │ status          │  │ pipeline_id  FK       │  │ rating  1–5       │  │
│  │ created_at TZ   │  │ stage_name           │  │ review_text       │  │
│  │ updated_at TZ   │  │ duration_ms  FLOAT   │  │ use_case          │  │
│  │ input_source    │  │ status               │  │ output_mode       │  │
│  │ output_mode     │  │ created_at  TZ       │  │ job_id            │  │
│  │ num_questions   │  └──────────────────────┘  │ created_at  TZ    │  │
│  │ cached  BOOL    │                             │ sentiment         │  │
│  │ error_message   │   Indexes:                  └───────────────────┘  │
│  └─────────────────┘   idx_qa_jobs_status                               │
│                         idx_qa_jobs_created_at                          │
│                         idx_stage_pipeline_id                           │
│                         idx_reviews_created_at                          │
│                         idx_reviews_rating                              │
└─────────────────────────────────────────────────────────────────────────┘
```

### LangGraph Pipeline Flow

```
                    extract_text
                         │
              ┌──────────┴──────────┐
          questions              text / both
              │                      │
    generate_questions         summarize_text
    (direct LLM, no RAG)           │
              │              ┌──────┴──────┐
              │           text           both
              │              │              │
              │         format_output  generate_questions
              │                    │
              └────────────────────┤
                                   │
                            format_output
                                   │
                            convert_pdf (PDF)
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18, Vite, Tailwind CSS |
| **Backend** | FastAPI (Python 3.11+), uvicorn |
| **LLM** | Groq — `llama-3.3-70b-versatile` (primary), `llama-3.1-8b-instant` (fallback) |
| **Vision/Audio** | Groq — `meta-llama/llama-4-scout-17b-16e-instruct`, `whisper-large-v3` |
| **Orchestration** | LangGraph (typed state machine) |
| **Response Cache** | Redis (primary) + in-memory LRU OrderedDict (fallback) |
| **Job Persistence** | PostgreSQL (primary) + SQLite (fallback) |
| **Rate Limiting** | Sliding-window (Redis-backed), token-bucket spike arrest |
| **Security** | WAF patterns, SSRF blocking, HMAC identity, JWT |
| **Observability** | LangSmith tracing, structured logging, per-stage metrics |
| **Deployment** | Render (backend), Vercel (frontend) |

---

## Features

### Core
- **Three output modes**: Questions only, Summary only, Both combined
- **Direct LLM generation** — no vector embeddings needed; Groq's 128K context window handles full documents
- **Smart text truncation** — fits within Groq TPM limits automatically
- **Styled PDF output** — xhtml2pdf with branded footer

### Reliability
- **LLM retry + fallback** — 3 attempts with exponential backoff; automatic provider switch
- **Groq rate-limit awareness** — parses `retry_after` from 429 errors; skips daily-exhausted providers immediately
- **30-second LLM call timeout** — `request_timeout=30` on ChatGroq prevents hanging
- **5-minute per-job timeout** — worker thread wraps each job with hard cap
- **Startup cleanup** — marks any queued/processing jobs from previous crashes as `failed`
- **Lazy imports** — all heavy LangChain/Groq imports inside function bodies (prevents Windows thread hang)
- **YouTube on cloud hosts** — 3-layer transcript fallback so YouTube URLs work on Render/AWS (see below)

### Caching
- **Two-layer cache**: Redis (persistent, cross-restart) + in-memory LRU (ephemeral, same session)
- **Content-hash key**: `sha256(file_bytes | output_mode | num_questions)` — same document always hits cache
- **24-hour TTL** on Redis; up to 100 entries in memory fallback
- **Cache hit dashboard**: purple row highlight + ⚡ icon

### Security
- **WAF**: XSS, SQLi, path traversal, RCE, file:// scheme blocking
- **SSRF**: Private IP range blocking (127.x, 10.x, 192.168.x, 169.254.x)
- **Rate limiting**: 10 req/hr per identity (sliding window, Redis-backed)
- **Spike arrest**: 3 req/s token bucket
- **Identity**: JWT > device fingerprint > IP/24 subnet, HMAC-hashed
- **Body size limit**: 50 MB max

### Dashboard
- Real-time stats: Total / Completed / Failed / Pending / Cache Hits / Avg Duration
- Jobs by output mode (bar chart with percentages)
- Recent 20 jobs table with status badges, cache badge, duration, and **Reason/Stage** column
- Cache status banner (Redis connected / memory-only)
- Auto-refresh every 30 seconds

---

## Quick Start — Local Development

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL (optional — falls back to SQLite)
- Groq API key ([console.groq.com](https://console.groq.com))

### 1. Clone & install

```bash
git clone https://github.com/mailtopprakash05/AgenticAI-Usecases.git
cd AgenticAI-Usecases/Q&A_Agent
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and set GROQ_API_KEY
```

### 3. Run backend

```bash
uvicorn api.server:app --reload --port 8000
```

The server starts in ~2 seconds (no model pre-loading). On first request, LangChain/Groq libraries load lazily (~5s).

### 4. Run frontend (Windows — use node directly to avoid & escaping)

```bash
cd frontend
node node_modules/vite/bin/vite.js --port 3000
```

### 5. Open browser

- **App**: http://localhost:3000
- **API docs**: http://localhost:8000/docs
- **Dashboard**: click the **Dashboard** tab in the app

---

## Configuration Reference

All settings are in `.env` (copied from `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | *(required)* | Groq API key |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Primary LLM |
| `GROQ_FALLBACK_MODEL` | `llama-3.1-8b-instant` | Fallback LLM |
| `GROQ_VISION_MODEL` | `meta-llama/llama-4-scout-17b-16e-instruct` | Vision model for images |
| `REDIS_URL` | *(empty — memory fallback)* | Redis URL for cache + rate limiting |
| `CACHE_TTL` | `86400` | Response cache TTL in seconds (24h) |
| `DATABASE_URL` | *(empty — SQLite fallback)* | PostgreSQL connection string |
| `RATE_LIMIT_MAX` | `10` | Max requests per user per window |
| `RATE_LIMIT_WINDOW` | `3600` | Rate limit window (seconds) |
| `BURST_MAX` | `3` | Max burst requests per second |
| `IDENTITY_HMAC_SECRET` | *(dev default)* | HMAC secret for identity hashing |
| `CORS_ALLOWED_ORIGIN` | `*` | Allowed frontend origin |
| `NUM_QUESTIONS` | `10` | Default number of questions |
| `TEMPERATURE` | `0.3` | LLM sampling temperature |
| `LANGCHAIN_TRACING_V2` | `false` | Enable LangSmith tracing |

---

## API Reference

### Health
```
GET /health
→ { status, version, timestamp, powered_by }
```

### Submit — File Upload
```
POST /api/qa/generate
Content-Type: multipart/form-data
  file:         <file>
  output_mode:  "questions" | "text" | "both"
  num_questions: int (default 10)

→ { pipeline_id, status, queue_position }
```

### Submit — URL / Source
```
POST /api/qa/generate-source
Content-Type: application/json
{
  "source":       "https://...",
  "output_mode":  "questions" | "text" | "both",
  "num_questions": 3
}

→ { pipeline_id, status, queue_position }
```

### Poll Status
```
GET /api/qa/status/{pipeline_id}
→ { pipeline_id, status, output_mode, result_markdown, result_pdf_path,
    error_message, created_at, updated_at, cached }
```

### Download PDF
```
GET /api/qa/download/{pipeline_id}
→ application/pdf  (streamed)
```

### Dashboard
```
GET /api/dashboard/stats
→ { total, completed, failed, pending, cache_hits, avg_duration_ms,
    by_mode, hourly, stage_avg_ms }

GET /api/dashboard/jobs?limit=20
→ { jobs: [ { pipeline_id, status, output_mode, num_questions,
               cached, duration_ms, reason, created_at } ] }

GET /api/dashboard/reviews?limit=10
→ { reviews: [...], stats: { total, avg_rating, distribution } }

GET /api/dashboard/cache-status
→ { cache_enabled, redis_connected, cache_layers, cache_ttl_seconds }

GET /api/debug/db
→ { using_postgres, db_host, db_url_set, job_count }
```

---

## Output Modes

| Mode | What it generates | Use case |
|------|------------------|----------|
| `questions` | N multiple-choice questions with A/B/C/D options, correct answer, and explanation | Exam prep, self-testing |
| `text` | Structured Markdown summary (Overview, Key Topics, Key Facts, Takeaways) | Quick document digest |
| `both` | Summary first, then MCQ questions — combined PDF | Full study guide |

---

## Supported Input Types

| Category | Extensions / Formats |
|----------|---------------------|
| **Documents** | `.pdf` `.txt` `.md` `.rst` |
| **Office** | `.docx` `.xlsx` `.xls` `.csv` |
| **Images** | `.png` `.jpg` `.jpeg` `.webp` (Groq vision) |
| **Audio/Video** | `.mp3` `.wav` `.m4a` `.mp4` `.mov` `.avi` `.webm` `.mkv` (Groq Whisper) |
| **URLs** | `http://` `https://` (web pages, scraped to plain text) |
| **YouTube** | `youtube.com` `youtu.be` — transcript or Whisper fallback (cloud-safe) |

---

## YouTube on Cloud Hosts (Render / AWS / GCP)

YouTube's transcript/caption API endpoints (`/youtubei/v1/get_transcript`,
`/api/timedtext`) are blocked for **datacenter IP ranges**. The app uses a
three-layer fallback so YouTube URLs always work even when hosted on Render:

```
YouTube URL submitted
       │
       ▼
Layer 1: youtube-transcript-api          (~1s)
         Fast — no download required
         Blocked on cloud IPs → fails on Render
       │ FAIL
       ▼
Layer 2: yt-dlp VTT, Android player      (~5s)
         Uses Android YouTube API client
         Sometimes bypasses cloud-IP filter
       │ FAIL
       ▼
Layer 3: yt-dlp audio → Groq Whisper     (~30s)
         Audio served from googlevideo.com CDN
         CDN is NOT filtered by cloud IP ranges
         Guaranteed to work on any cloud host
       │
       ▼
     Transcript text → Q&A / Summary pipeline
```

**No extra configuration needed.** When Layer 1 fails on Render, the app
automatically falls back through Layers 2 and 3. Layer 3 adds ~30 s of
processing time (audio download + Whisper transcription) but succeeds where
the others are blocked.

> **Note**: Whisper's 25 MB file limit applies. Videos longer than ~2 hours
> may exceed it — in that case, paste the video script as a `.txt` file instead.

---

## Security

### Request Flow
```
Client → RequestId middleware
       → BodySizeLimitMiddleware (50 MB cap)
       → CORS
       → extract_identity()  [JWT > fingerprint > IP/24 subnet, HMAC-hashed]
       → check_spike_arrest() [token bucket: 3 req/s]
       → check_rate_limit()  [sliding window: 10 req/hr]
       → waf_scan()          [XSS, SQLi, path traversal, RCE, file://]
       → validate_url()      [SSRF: blocks 127.x, 10.x, 192.168.x, 169.254.x]
       → pipeline
```

### Structured Error Codes

| Code | HTTP | When |
|------|------|------|
| `RATE_LIMIT_EXCEEDED` | 429 | Hourly quota hit |
| `SPIKE_ARREST` | 429 | Burst limit hit |
| `WAF_BLOCKED` | 400 | Injection pattern detected |
| `SSRF_BLOCKED` | 400 | Private IP target |
| `UNSUPPORTED_FILE_TYPE` | 415 | Extension not allowed |
| `INVALID_OUTPUT_MODE` | 422 | Unknown mode string |

All errors return `{ error_code, message, retry_after_seconds, debug_id }`.

---

## Persistence & Sleep Prevention

### Problem
Render's free tier spins down web services after 15 minutes of inactivity. The first
request after sleep incurs a 30–60 s cold-start delay. Additionally, the ephemeral
filesystem means SQLite data (jobs, stage timings, reviews) is wiped on every restart,
so the dashboard showed zeroes after a sleep cycle.

### Solution

#### 1. External Render PostgreSQL — persistent stats across restarts
All job data is written to the external PostgreSQL instance
(`dpg-d84sbagjo89c73bskf10-a.oregon-postgres.render.com`) via `api/database.py`.
The connection uses `sslmode=require` as mandated by Render's external DB policy.

| Table | Purpose |
|---|---|
| `qa_jobs` | Every pipeline run — status, mode, duration, cached flag |
| `qa_stage_timings` | Per-stage latency (ingestion / retrieval / generation / output) |
| `qa_reviews` | User star ratings + free-text feedback |

SQLite (`api/jobs.db`) is kept as an in-process cache for jobs created in the
current server session. Dashboard endpoints always read from PostgreSQL.

#### 2. Keep-alive pinger — prevents cold starts
A daemon thread (`_keep_alive_pinger`) starts at server startup and pings
`GET /health` every 10 minutes using Render's automatically-set
`RENDER_EXTERNAL_URL` environment variable. This keeps the HTTP dyno warm and
eliminates the cold-start delay for users. The thread is completely dormant in
local development (env var is not set outside Render).

#### 3. Job status PostgreSQL fallback — previous jobs survive restarts
The `/api/qa/status/{pipeline_id}` and download endpoints first check SQLite
(fast, in-process). On a miss — which always happens after a Render restart —
they fall back to PostgreSQL, so users can always retrieve results from previous
sessions.

---

## Dashboard & Observability

The built-in dashboard (click **Dashboard** tab) shows:

- **Summary cards**: Total Jobs · Completed · Failed · Pending · Cache Hits · Avg Duration
- **Mode breakdown**: Bar chart of questions / text / both usage
- **Stage timings**: Average duration per pipeline stage (from PostgreSQL)
- **Recent jobs table** with:
  - Status badge (queued / processing / completed / failed)
  - Cache badge (cached ⚡ purple / fresh)
  - Duration — computed timezone-safely in Python
  - **Reason/Stage column** — human-readable explanation:
    - 🟢 `Pipeline completed`
    - 🟣 `Served from cache`
    - 🔵 `Running pipeline…` (animated)
    - 🟡 `Waiting in queue`
    - 🔴 `Groq API rate limit — retry later`
    - 🔴 `Server restarted mid-job`
- **Cache status banner**: Redis connected / memory-only

---

## Caching & Performance

### Cache Architecture
```
Request
  │
  ▼
make_cache_key(sha256(file_bytes | mode | num_questions))
  │
  ├─► Redis GET  →  HIT: return cached PDF (skip entire pipeline)
  │                 MISS ↓
  ├─► Memory LRU GET  →  HIT: return cached result
  │                       MISS ↓
  ▼
Run full pipeline → store in Redis + Memory LRU
```

### Expected Latencies

| Scenario | Latency |
|----------|---------|
| Redis cache hit | < 2s (PDF generation only) |
| Memory cache hit | < 5s (within same session) |
| Fresh pipeline — small doc | 10–30s |
| Fresh pipeline — large URL | 20–60s |
| YouTube — transcript API (Layer 1) | +1s |
| YouTube — yt-dlp VTT (Layer 2) | +5s |
| YouTube — Whisper audio (Layer 3, Render) | +30–60s |
| Groq per-minute rate limit | +10–30s (auto-retry) |

---

## Deployment — Render + Vercel

### Backend — Render

1. Connect your GitHub repo to Render
2. Use `render.yaml` — it configures the web service automatically
3. Set secrets in Render dashboard (Environment tab):
   - `GROQ_API_KEY` — your Groq key
   - `DATABASE_URL` — PostgreSQL connection string
   - `IDENTITY_HMAC_SECRET` — strong random secret (32+ chars)
4. Redis is pre-configured in `render.yaml` pointing to your Render Redis instance

### Frontend — Vercel

1. Import the `frontend/` directory as a Vercel project
2. Set `VITE_API_BASE_URL` env var to your Render backend URL
3. `vercel.json` handles rewrites and security headers automatically

### Environment Variables Summary (Render)

```yaml
GROQ_API_KEY:          <secret — set in Render dashboard>
GROQ_MODEL:            llama-3.3-70b-versatile
GROQ_FALLBACK_MODEL:   llama-3.1-8b-instant
REDIS_URL:             redis://red-d836e2t7vvec73938sl0:6379
DATABASE_URL:          postgresql://<user>:<pass>@<host>/<db>?sslmode=require
IDENTITY_HMAC_SECRET:  <secret — set in Render dashboard>
CORS_ALLOWED_ORIGIN:   https://frontend-six-red-29.vercel.app
RATE_LIMIT_MAX:        10
BURST_MAX:             3
NUM_QUESTIONS:         10
```

> `DATABASE_URL` is now set in `.env` and `render.yaml` — pointing to the external
> Render PostgreSQL instance. Stats persist across sleep cycles and restarts.
> `RENDER_EXTERNAL_URL` is injected automatically by Render and used by the
> keep-alive pinger — no manual configuration needed.

---

## Project Structure

```
Q&A_Agent/
├── api/
│   ├── server.py           # FastAPI app, worker, all endpoints
│   ├── cache.py            # Two-layer cache (Redis + in-memory LRU)
│   ├── database.py         # PostgreSQL + SQLite persistence
│   ├── errors.py           # Structured error factory
│   └── middleware/
│       ├── security.py     # WAF, SSRF, file validation
│       ├── rate_limit.py   # Sliding-window + spike arrest
│       ├── request_id.py   # X-Request-Id header
│       └── body_size.py    # 50 MB body cap
│
├── src/
│   ├── pipeline/
│   │   ├── graph.py        # LangGraph state machine
│   │   └── stages.py       # Stage wrappers (extract, summarize, format, pdf)
│   ├── generation/
│   │   └── qa_generator.py # LLM calls: generate_questions_from_text, summarize_text
│   ├── ingestion/
│   │   ├── document_loader.py  # Universal loader (PDF, DOCX, XLSX, URL, YouTube)
│   │   ├── pdf_extractor.py    # PDF text cleaning
│   │   └── pdf_generator.py    # Sample PDF creator
│   ├── output/
│   │   ├── output_formatter.py # Markdown templates
│   │   └── pdf_converter.py    # Markdown → HTML → PDF
│   └── retrieval/
│       └── embeddings_store.py # FAISS + HuggingFace (available for future RAG)
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx                  # Tab navigation (Pipeline / Dashboard)
│   │   ├── components/
│   │   │   ├── DocumentUpload.jsx   # File/URL input, rate limit banner
│   │   │   ├── JobStatus.jsx        # Poll + display results
│   │   │   ├── Dashboard.jsx        # Stats + jobs table with reason column
│   │   │   └── RateLimitBanner.jsx  # 429 countdown
│   │   └── utils/
│   │       └── errorHandler.js      # parseApiError, getDeviceFingerprint
│   └── vercel.json                  # Rewrites + security headers
│
├── tests/                 # 65 passing tests
│   ├── test_api_endpoints.py
│   ├── test_rate_limit.py
│   ├── test_security.py
│   └── test_llm_retry.py
│
├── observability/
│   ├── logger.py          # Structured logging (UTF-8, file + console)
│   ├── metrics.py         # PipelineMetrics with stage timings
│   └── langsmith_tracer.py
│
├── config.py              # Central config (all env vars, defaults)
├── render.yaml            # Render deployment spec
├── requirements.txt
└── .env.example
```

---

*Powered by PrakashPujariAI*
