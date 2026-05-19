# Q&A Agent — Architecture & Setup Guide

## System Architecture

![Architecture Diagram](screenshots/architecture_diagram.png)

The diagram above shows the full system layout:

- **Client layer** — React + Vite frontend on Vercel handles file/URL upload, YouTube URL detection, real-time job polling, PDF/Markdown preview, dashboard stats, and ratings.
- **YouTube proxy** — Vercel Edge Function (`/api/youtube-transcript.js`) acts as a residential-IP fallback because YouTube blocks transcript requests from cloud datacenter IPs.
- **FastAPI backend** (Render, Oregon, free tier) — three middleware layers guard every request:
  - Rate limiter (Redis-backed)
  - WAF / input validation (SSRF, XSS, SQLi)
  - CORS middleware (locked to Vercel domain)
- **Dual job queues** — two in-process FIFO queues feed two parallel worker threads, preventing the single worker bottleneck.
- **LangGraph pipeline** — stateful graph with nodes: `extract_text → route_after_extract → summarize_text / generate_qs → format_output → convert_pdf`, backed by `document_loader.py`, `pdf_extractor.py`, `qa_generator.py` (Groq LLM), `output_formatter.py`, `pdf_converter.py`.
- **Background daemons** — keep-alive pinger (600 s) prevents Render free-tier cold starts; `/api/debug/*` endpoints expose DB and YouTube diagnostics.
- **External services** — Redis (rate limit + cache), LangSmith (LLM + pipeline tracing at smith.langchain.com), External Render PostgreSQL (job persistence + dashboard stats).

## Architecture Walk-Through

### Step 1 — User submits input (Client → Backend)

The React frontend accepts one of three input types: a local file upload, a plain URL, or a YouTube URL. On submit, the frontend POST to `/api/qa/generate` with the file/URL and the chosen output mode (`questions`, `summary`, or `both`). For YouTube URLs the browser first calls the Vercel Edge Function (`/api/youtube-transcript.js`), which runs on Cloudflare's residential-IP network to bypass YouTube's datacenter-IP block, then forwards the transcript text to the backend.

### Step 2 — Request enters the backend middleware stack

Every inbound request passes through three FastAPI middleware layers in order:

1. **CORS middleware** — rejects requests not originating from the authorised Vercel domain.
2. **WAF / input validation** — blocks SSRF (private IP ranges, metadata endpoints), XSS payloads in text fields, and SQLi patterns in query params.
3. **Rate limiter** — enforces per-IP request quotas backed by Redis; returns HTTP 429 when the limit is exceeded.

### Step 3 — Job is enqueued and acknowledged

The API handler validates the payload, assigns a `pipeline_id` (UUID), writes an initial `queued` record to PostgreSQL, and pushes the job onto one of two in-process FIFO queues. It immediately returns `202 Accepted` with the `pipeline_id` so the frontend can start polling `/api/qa/status/{id}`.

### Step 4 — Worker thread picks up the job

Two background worker threads run permanently, each consuming from one queue. When a worker dequeues a job it updates the DB record to `processing` and invokes `_execute_pipeline()`.

### Step 5 — LangGraph pipeline: `extract_text`

`document_loader.py` (and `pdf_extractor.py` for PDFs) converts the raw input into a single plain-text string:

- **Files** — PDF (pdfminer), DOCX (python-docx), XLSX/CSV (openpyxl/pandas), PPTX (python-pptx), images (Tesseract OCR), audio/video (Groq Whisper).
- **URLs** — HTML fetched with `requests`, cleaned of `<script>`/`<style>` tags via regex, SPA/auth-portal detection aborts early with a user-friendly message; known cloud-storage domains (OneDrive, Google Drive, Dropbox) are rejected before any HTTP call.
- **YouTube** — transcript text already extracted in Step 1 is passed through directly.

A memory guard caps input at 2 MB (`_MAX_DOC_CHARS = 2_000_000`) to protect the 512 MB Render free-tier instance.

### Step 6 — LangGraph pipeline: `route_after_extract`

A conditional edge inspects `output_mode` and branches the graph:

- `questions` → `generate_qs` only
- `summary` → `summarize_text` only
- `both` → `summarize_text` then `generate_qs`

### Step 7 — LangGraph pipeline: `summarize_text` / `generate_qs` (LLM calls)

`qa_generator.py` handles both nodes using the same map-reduce strategy:

1. **Chunking** — the document is split into `_CHUNK_CHARS = 20,000`-character chunks (≈ 5 K tokens, within Groq's 6 K TPM free-tier limit).
2. **Diversity selection** — TF-IDF vectors are built for all chunks; a greedy farthest-point algorithm picks up to `_MAX_QA_CHUNKS` (20) or `_MAX_SUM_CHUNKS` (30) maximally topic-diverse chunks, always seeding with the first and last chunks for intro/conclusion coverage.
3. **Parallel LLM calls** — a `ThreadPoolExecutor` (`_MAX_PARALLEL_CHUNKS = 3`) sends each selected chunk to the LLM concurrently.
4. **LLM fallback chain** — each call tries providers in order until one succeeds:
   - `groq/llama-3.3-70b-versatile`
   - `groq/llama-3.1-8b-instant`
   - `groq/llama3-8b-8192`
   - `gemini-2.5-flash`
   - `huggingface/Kimi-K2`
5. **Deduplication** — Jaccard token-overlap at threshold 0.65 removes near-duplicate questions before the final list is assembled.

### Step 8 — LangGraph pipeline: `format_output`

`output_formatter.py` renders the questions or summary into structured Markdown, numbering questions, labelling options A–D, and appending the answer key.

### Step 9 — LangGraph pipeline: `convert_pdf`

`pdf_converter.py` converts the Markdown to a styled PDF (WeasyPrint) and writes it to the output directory. The PDF path is stored alongside the Markdown in the result.

### Step 10 — Job completes; file deleted

The worker marks the job `completed` in PostgreSQL, caches the Markdown result in Redis (cache key = SHA-256 of input + mode + question count), and immediately deletes the uploaded file from disk. A background sweeper also purges any files not deleted within 5 minutes (`FILE_EXPIRY_SECONDS = 300`).

### Step 11 — Frontend polls and renders result

The frontend polls `/api/qa/status/{id}` every 2 seconds. On `completed`, it fetches `/api/qa/result/{id}` and renders the Markdown inline with syntax highlighting and a PDF download button. The elapsed time is shown during processing so users know large documents (1 000+ pages) may take 1–2 minutes.

### Step 12 — Observability

Every LLM call and pipeline stage span is traced in LangSmith under project **qa-agent**. Aggregate stats (total jobs, average latency, error rate, access by country) are written to PostgreSQL and surfaced on the Dashboard → Analytics tab. A keep-alive daemon pings `/health` every 600 s to prevent Render's free-tier instance from sleeping.

## Components

| Component | Technology | Host | Purpose |
|-----------|-----------|------|---------|
| Frontend | React 18 + Vite + Tailwind | Vercel | User interface |
| Backend API | FastAPI + Uvicorn | Render (free) | Pipeline orchestration |
| Pipeline | LangGraph state machine | In-process | Document → Q&A flow |
| LLM | Groq (llama-3.3-70b) | Groq Cloud | Q&A + summarisation |
| Job store | PostgreSQL (Render) | Render | Persistent job history |
| Cache | Redis | Render | Rate limiting + result cache |
| Tracing | LangSmith | smith.langchain.com | LLM observability |
| YouTube proxy | Vercel Edge Function | Vercel | Transcript fallback |

## YouTube Transcript Pipeline

YouTube blocks transcript requests from all cloud datacenter IPs. The pipeline
tries layers in order until one succeeds:

```
Layer 0 — Third-party APIs (cloud-IP safe)
  ├─ Supadata.ai (set SUPADATA_API_KEY — free 10k req/month)
  └─ Invidious public instances (no key; tries 6 instances)

Layer 1 — youtube-transcript-api
  └─ With proxy if YOUTUBE_PROXY_URL is set

Layer 2 — requests.Session + cookies
  └─ Requires YOUTUBE_COOKIES (base64 Netscape cookies.txt)

Layer 3 — yt-dlp VTT download
  └─ player_client: tv_embedded, android_creator, ios, mweb

Layer 4 — yt-dlp audio + Groq Whisper
  └─ Downloads audio from CDN → transcribes with whisper-large-v3
```

## LangSmith Tracing

Every pipeline run produces a full trace in LangSmith:

- **extract_text** → ingestion stage (tool span)
- **summarize_text** → LLM call (llm span, tokens + latency)
- **generate_questions** → LLM call (llm span)
- **stage_format_***, **stage_convert_to_pdf** → output stages

View traces at [smith.langchain.com](https://smith.langchain.com) under project **qa-agent**.

## Environment Variables

### Required

| Variable | Where to set | Description |
|----------|-------------|-------------|
| `GROQ_API_KEY` | Render dashboard | Groq LLM API key |
| `DATABASE_URL` | render.yaml (hardcoded) | External Render PostgreSQL |
| `LANGCHAIN_API_KEY` | Render dashboard | LangSmith API key |

### Optional but Recommended

| Variable | Default | Description |
|----------|---------|-------------|
| `SUPADATA_API_KEY` | — | Free YouTube transcript API (supadata.ai) |
| `REDIS_URL` | — | Redis for rate limiting + cache |
| `IDENTITY_HMAC_SECRET` | dev-secret | Random 32-byte hex for IP hashing |
| `CORS_ALLOWED_ORIGIN` | `*` | Lock to your Vercel domain |

### YouTube Transcript (choose one)

| Variable | Description |
|----------|-------------|
| `SUPADATA_API_KEY` | **Easiest**: sign up free at supadata.ai |
| `YOUTUBE_COOKIES` | Base64-encoded Netscape cookies.txt from logged-in YouTube session |
| `YOUTUBE_PROXY_URL` | `socks5://host:port` or `http://user:pass@host:port` |

### LangSmith Tracing

| Variable | Value |
|----------|-------|
| `LANGCHAIN_TRACING_V2` | `true` |
| `LANGCHAIN_API_KEY` | From smith.langchain.com → Settings → API Keys |
| `LANGCHAIN_PROJECT` | `qa-agent` |
| `LANGCHAIN_ENDPOINT` | `https://api.smith.langchain.com` |

## Deployment

### Backend (Render)

Render auto-deploys on every push to `main` via GitHub Actions:

```yaml
# .github/workflows/deploy-render.yml
- name: Trigger Render deploy
  run: curl -s --fail-with-body "${{ secrets.RENDER_DEPLOY_HOOK_URL }}" -X POST
```

Manual deploy hook:
```
POST https://api.render.com/deploy/srv-d82dpljrjlhs73ddl96g?key=Nsh6NYBySj0
```

### Frontend (Vercel)

Vercel auto-deploys from the `frontend/` directory on every push to `main`.
The Vercel Edge Function at `frontend/api/youtube-transcript.js` runs on
Cloudflare's edge network as a YouTube transcript fallback.

## Key API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check (keep-alive ping target) |
| `/api/qa/generate` | POST | Submit document/URL for Q&A generation |
| `/api/qa/status/{id}` | GET | Poll job status |
| `/api/qa/result/{id}` | GET | Download result (JSON) |
| `/api/qa/download/{id}` | GET | Download PDF |
| `/api/dashboard/stats` | GET | Aggregate pipeline stats |
| `/api/dashboard/recent` | GET | Recent job history |
| `/api/debug/db` | GET | PostgreSQL connectivity check |
| `/api/debug/youtube` | GET | YouTube transcript layer diagnostics |

## Local Development

```bash
# 1. Create .env (copy from .env.example and fill in keys)
cp .env.example .env

# 2. Install Python deps
pip install -r requirements.txt

# 3. Start backend
uvicorn api.server:app --reload --port 8000

# 4. Start frontend (separate terminal)
cd frontend && npm install && npm run dev
```

Backend: http://localhost:8000  
Frontend: http://localhost:5173  
Swagger docs: http://localhost:8000/docs  
LangSmith traces: https://smith.langchain.com (project: qa-agent)
