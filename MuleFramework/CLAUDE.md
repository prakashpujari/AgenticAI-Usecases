# MuleFramework — mule-validation-hub

AI-powered MuleSoft release-readiness platform. Parses MUnit test reports,
runs a **LangGraph 6-agent pipeline** powered by **Groq llama-3.3-70b-versatile**
against RAML specs and Mule XML, and produces an executive dashboard with a
deployment recommendation (APPROVED / CONDITIONAL / BLOCKED).

---

## Live URLs

| Service | URL | Notes |
|---|---|---|
| **Frontend — git-linked (Vercel)** | https://mule-ai-validation-dashboard.vercel.app | Auto-deploys on every push to `main` |
| **Frontend — CLI project (Vercel)** | https://dashboard-ui-eta-pearl.vercel.app | Deployed via `vercel --prod` from `dashboard-ui/` |
| **Backend API (Render)** | https://mule-ai-validation.onrender.com | Auto-deploys on every push to `main` (Docker) |
| Backend health | https://mule-ai-validation.onrender.com/health | Keep-alive ping target |
| Backend docs (Swagger) | https://mule-ai-validation.onrender.com/docs | Interactive API docs |

> The frontend keeps the Render free-tier backend alive by pinging `/health`
> every 10 minutes from a `useEffect` in `App.tsx`.

---

## Repository layout

```
calculator-api-ai-validation/
├── ai-validation-service/        FastAPI + LangGraph backend
│   ├── app/
│   │   ├── agents/               6 LangGraph agents
│   │   ├── services/             groq_client, munit_parser, workflow
│   │   ├── models/schemas.py
│   │   └── main.py               FastAPI entrypoint
│   ├── sample_reports/           Bundled demo MUnit XML + coverage JSON
│   ├── Dockerfile
│   ├── render.yaml               Render deployment config
│   └── requirements.txt
├── dashboard-ui/                 React 19 + Vite + TypeScript frontend
│   ├── src/
│   │   ├── App.tsx               Root component, keep-alive ping, error UI
│   │   ├── index.css             Global styles, animations, scrollbar
│   │   └── components/
│   │       ├── Header.tsx        Sticky header, LIVE badge, animated title
│   │       ├── InputPanel.tsx    Path/URL mode toggle, pipeline config
│   │       ├── Dashboard.tsx     Results: grade, scores, tiles, agent cards
│   │       ├── AgentCard.tsx     Expandable agent findings accordion
│   │       ├── ScoreRing.tsx     SVG score ring with glow filter
│   │       └── RecommendationBadge.tsx
│   └── vercel.json               Vercel deployment config
├── mule-app/                     Mule 4.9 Calculator API (Java/Maven)
├── k8s/                          Kubernetes manifests
└── .github/workflows/ci-cd.yaml  8-stage CI/CD pipeline
```

---

## Deployment

### Frontend → Vercel
Auto-deploys on every push to `main` branch (Vercel git integration).
Manual deploy:
```bash
cd calculator-api-ai-validation/dashboard-ui
vercel --prod
```
Required env var in Vercel dashboard:
- `VITE_API_URL` = `https://mule-ai-validation.onrender.com`

### Backend → Render
Auto-deploys on every push to `main` branch (Render git integration, Docker).
Service: `mule-ai-validation` (free tier, Docker runtime).
Required env var in Render dashboard:
- `GROQ_API_KEY` = your Groq API key

---

## Run locally

```bash
# Backend
cd calculator-api-ai-validation/ai-validation-service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
GROQ_API_KEY=<key> uvicorn app.main:app --reload --port 8000

# Frontend (new terminal)
cd calculator-api-ai-validation/dashboard-ui
npm install
VITE_API_URL=http://localhost:8000 npm run dev
```

---

## Agent pipeline

```
START → load_munit → api_design → mule_review → munit
      → security → performance → executive_reporting → END
```

| Agent | Responsibility |
|---|---|
| `api_design` | RAML + API-led / C4E standards review |
| `mule_review` | Mule XML best practices |
| `munit` | Failure RCA, coverage gaps |
| `security` | OAuth, JWT, threat protection |
| `performance` | Concurrent latency, tail-latency |
| `executive_reporting` | Synthesises scores → recommendation |

---

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness probe (used by keep-alive ping) |
| GET | `/ready` | Readiness probe |
| POST | `/validate` | Full LangGraph pipeline |
| POST | `/dashboard` | Shortcut — executive dashboard only |
| POST | `/munit/parse` | Parse MUnit XML, no LLM |

**URL input support**: all three path fields in `/validate` also accept
`http://` or `https://` URLs — the backend downloads to temp files and
cleans up after the request.

---

## Key decisions

- **No new packages for URL support**: `httpx` was already in `requirements.txt`.
- **Keep-alive**: frontend `useEffect` pings `/health` every 10 min (not the
  backend), so Render free tier never sleeps between sessions.
- **Temp file cleanup**: `finally` block in `validate()` removes all
  `shutil.rmtree` + `Path.unlink` temp artifacts after every request.
- **Animation keyframes** are centralized in `index.css` (not scattered
  in `<style>` tags inside components).
- **Grade badge** (A+/A/B+/B/C/D) derived from `productionReadiness` score,
  shown in the Executive Summary card alongside elapsed time.

---

## Changelog

### 2026-06-10 (patch — rich agent findings + app rename)
- **UI: App renamed** — `Header.tsx` title changed from "AI Validation Dashboard"
  to `mule-validation-hub`
- **Backend: Agent findings enriched** — `mule_review`, `munit`, and `performance`
  agent `role` prompts now explicitly require `detail` and `recommendation` fields
  in every finding (matching `api_design` agent format). Previously only `severity`
  and `title` were returned, making the AgentCard expand panel appear empty.
- User-level prompts for `munit` and `performance` agents also reinforced to
  request the structured finding format.

### 2026-06-10 (patch — MUnit definition parser)
- **Backend: MUnit definition XML support** — `munit_parser.py` now has a
  two-pass strategy:
  1. Try surefire report format (`TEST-*.xml`, `*surefire*.xml`) as before
  2. **If no surefire reports found**, fall back to parsing MUnit test
     definition XML files (Mule XML with `munit:test` elements — the files
     that live in `src/test/munit/`)
- Uses `{http://www.mulesoft.org/schema/mule/munit}test` Clark-notation tag
  matching; regular Mule flow XML files (no `munit:test` elements) are
  silently skipped
- `expectedErrorType` attribute stored in `classname` field
  (e.g. `negative-tests:APP:VALIDATION_ERROR`) so AI agents can identify
  negative / security / boundary test categories
- Old `_parse_xml` kept as an alias for backwards compatibility
- Verified: 29 tests across 5 suites extracted from `src/test/munit/`

### 2026-06-10 (patch — GitHub URL fix)
- **Backend: GitHub URL auto-conversion** — `validate()` now detects GitHub
  `blob/` and `tree/` URLs and handles them correctly:
  - `github.com/.../blob/...` → resolved to `raw.githubusercontent.com/...`
    before download (was previously fetching the HTML page)
  - `github.com/.../tree/...` → files listed + downloaded via GitHub Contents
    API (`api.github.com/repos/.../contents/...`); handles 403 rate-limit error
- **Frontend: GitHub URL badge** — `FieldInput` shows a contextual badge when
  a GitHub URL is pasted: "⚡ blob → auto-converted", "📂 tree → API fetch",
  "✓ raw — ready"
- **Frontend: better hints** — URL fields now show placeholder examples using
  `github.com/…/blob/…` and `github.com/…/tree/…` formats; MUnit field
  clarifies it expects `TEST-*.xml` surefire reports (not `src/test/munit/`
  source files)
- **Frontend: info banner** — URL mode banner now explains blob vs tree
  handling and warns that `src/test/munit/` is the wrong directory for reports

### 2026-06-10 (initial)
- **UI: URL input mode** — `InputPanel` now has a "📁 Folder Paths / 🔗 URLs"
  pill toggle; all three source fields accept direct download URLs in URL mode.
- **Backend: URL download** — `validate()` detects `http(s)://` values,
  downloads to temp dirs/files via `httpx`, cleans up in `finally`.
- **Keep-alive** — `App.tsx` pings `GET /health` on load + every 10 min
  to prevent Render free-tier sleep.
- **UI: Ambient background** — three large floating gradient orbs + dot-grid
  overlay on a `#0a0d16` base.
- **UI: Animated header** — rainbow 3px top accent line, shimmer on title,
  `● LIVE` badge with expanding ring pulse.
- **UI: Grade badge** — A+/A/B+/B/C/D shown in Executive Summary card.
- **UI: 5th stat tile** — "Production Score" with grade sub-label.
- **UI: Stat tile hover** — lifts 2px on hover with deeper shadow.
- **UI: Richer loading state** — triple concentric spinning rings + glassmorphism card.
- **UI: Footer** — branding bar at page bottom.
- **CSS: Global** — custom scrollbar (purple), `::selection` color,
  autofill dark-theme fix, all keyframes centralized.
