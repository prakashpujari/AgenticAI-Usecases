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

## Components

| Component | Technology | Host | Purpose |
|-----------|-----------|------|---------|
| Frontend | React 18 + Vite + Tailwind | Vercel | User interface |
| Backend API | FastAPI + Uvicorn | Render (free) | Pipeline orchestration |
| Pipeline | LangGraph state machine | In-process | Document → Q&A flow |
| LLM | Groq (llama-3.3-70b) | Groq Cloud | Q&A + summarisation |
| Embeddings | fastembed (ONNX, local) | In-process | Vector search |
| Vector store | FAISS (in-memory) | In-process | Similarity retrieval |
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
