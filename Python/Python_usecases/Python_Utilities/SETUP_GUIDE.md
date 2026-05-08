# Mortgage Utilities Platform — Complete Setup & Architecture Guide

---

## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Component Breakdown](#2-component-breakdown)
3. [Prerequisites](#3-prerequisites)
4. [Project Structure](#4-project-structure)
5. [Step-by-Step Setup](#5-step-by-step-setup)
6. [Environment Configuration](#6-environment-configuration)
7. [Running the Application](#7-running-the-application)
8. [Authentication Flows](#8-authentication-flows)
9. [API Reference](#9-api-reference)
10. [Borrower Search (OR Logic)](#10-borrower-search-or-logic)
11. [Google OAuth Setup](#11-google-oauth-setup)
12. [Known Issues & Fixes](#12-known-issues--fixes)
13. [Test Credentials](#13-test-credentials)

---

## 1. System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CLIENT BROWSER                                     │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │            React + TypeScript (Vite)  — http://localhost:3000        │  │
│   │                                                                       │  │
│   │  ┌──────────┐  ┌──────────────┐  ┌───────────────┐  ┌───────────┐  │  │
│   │  │  Auth    │  │  Borrower    │  │  Underwriting │  │ Documents │  │  │
│   │  │  Pages   │  │  Lookup      │  │  Pages        │  │  Pages    │  │  │
│   │  └────┬─────┘  └──────┬───────┘  └───────┬───────┘  └─────┬─────┘  │  │
│   │       │               │                  │                 │        │  │
│   │  ┌────▼───────────────▼──────────────────▼─────────────────▼──────┐ │  │
│   │  │                  Zustand Store (auth-store, ui-store)           │ │  │
│   │  └────────────────────────────┬────────────────────────────────────┘ │  │
│   │                               │                                       │  │
│   │  ┌────────────────────────────▼────────────────────────────────────┐ │  │
│   │  │              Axios API Client  (api-client.ts)                  │ │  │
│   │  │          Base URL: http://localhost:8000                        │ │  │
│   │  │   JWT Bearer token injected on every request via interceptor    │ │  │
│   │  └────────────────────────────┬────────────────────────────────────┘ │  │
│   └───────────────────────────────│────────────────────────────────────────┘ │
└───────────────────────────────────│─────────────────────────────────────────┘
                                    │ HTTP/JSON
                                    │
┌───────────────────────────────────▼─────────────────────────────────────────┐
│                   FastAPI Backend  — http://localhost:8000                   │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                        Middleware Stack                               │  │
│  │   CORSMiddleware → SecurityHeadersMiddleware →                        │  │
│  │   CorrelationIdMiddleware → RequestLoggingMiddleware                  │  │
│  └───────────────────────────────┬──────────────────────────────────────┘  │
│                                  │                                          │
│  ┌───────────────────────────────▼──────────────────────────────────────┐  │
│  │                     API Router  /api/v1                               │  │
│  │   /auth  │  /borrowers  │  /documents  │  /underwriting  │  /utils   │  │
│  └──┬───────┴──┬───────────┴──────────────┴─────────────────┴───────────┘  │
│     │          │                                                             │
│  ┌──▼──────┐ ┌─▼───────────────────────────────────────────────────────┐   │
│  │Auth     │ │                    Services Layer                        │   │
│  │Service  │ │  BorrowerService │ UnderwritingService │ DocumentService │   │
│  │OAuth    │ │  CalculatorSvc   │ RuleEngine          │ AuthService     │   │
│  │Service  │ └─────────────────────────┬───────────────────────────────┘   │
│  └──┬──────┘                           │                                    │
│     │                        ┌─────────▼──────────────────────────────┐    │
│     │                        │           Repositories Layer            │    │
│     │                        │  BorrowerRepo │ UserRepo │ IdempotRepo  │    │
│     │                        └─────────────────────────┬──────────────┘    │
│     │                                                   │                   │
│  ┌──▼───────────────────────────────────────────────────▼──────────────┐   │
│  │                       Infrastructure                                 │   │
│  │                                                                      │   │
│  │  ┌─────────────────┐  ┌──────────────────┐  ┌───────────────────┐  │   │
│  │  │  SQLAlchemy 2.0  │  │  Redis (cache /  │  │  AI Provider      │  │   │
│  │  │  asyncpg driver  │  │  rate limiting)  │  │  (mock / OpenAI)  │  │   │
│  │  └────────┬─────────┘  └──────────────────┘  └───────────────────┘  │   │
│  └───────────│─────────────────────────────────────────────────────────┘   │
└──────────────│──────────────────────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────────────────────┐
│            PostgreSQL 17  —  localhost:5432 / database: postgres             │
│                                                                              │
│   Tables:  borrowers │ users │ idempotency_keys │ underwriting_scenarios     │
└──────────────────────────────────────────────────────────────────────────────┘

External Services:
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  Google OAuth  →  https://accounts.google.com  (ID token verification)  │
  │  Google JWKS   →  https://www.googleapis.com/oauth2/v3/certs            │
  └─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Breakdown

### Frontend (React + TypeScript + Vite)

| Layer | Files | Purpose |
|-------|-------|---------|
| Pages | `src/pages/` | Auth, Borrower Lookup, Underwriting, Documents |
| State | `src/store/auth-store.ts`, `ui-store.ts` | Zustand global state |
| Services | `src/services/api-client.ts` | Axios instance with JWT interceptor |
| Routes | `src/routes/index.tsx` | React Router with `ProtectedRoute` guard |
| Types | `src/types/` | TypeScript interfaces matching backend models |
| Config | `src/config/index.ts` | Reads `VITE_*` environment variables |

### Backend (FastAPI + Python 3.13)

| Layer | Location | Purpose |
|-------|----------|---------|
| API | `app/api/v1/` | Route handlers (auth, borrower, documents, underwriting, utilities) |
| Services | `app/services/` | Business logic (auth, OAuth, borrower, underwriting, document, calculator, rule engine) |
| Repositories | `app/repositories/` | Data access with SQLAlchemy async sessions |
| Domain Models | `app/models/domain/` | Pydantic domain entities |
| Request/Response | `app/models/requests/`, `app/models/responses/` | API contracts |
| Infrastructure | `app/infrastructure/` | Database engine, Redis client, AI provider, circuit breaker, metrics |
| Core | `app/core/` | Config (pydantic-settings), security (JWT), middleware, exceptions, logging |

---

## 3. Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.13+ | Backend runtime |
| Node.js | 18+ | Frontend build |
| PostgreSQL | 17 | Primary database |
| Redis | 7+ | Rate limiting & caching (optional in dev — fails gracefully) |
| Git | any | Version control |

---

## 4. Project Structure

```
Python_usecases/
├── docker-compose.yml          ← Run everything with Docker
├── backend/
│   ├── .env                    ← Backend environment variables  ← IMPORTANT
│   ├── Dockerfile
│   ├── pyproject.toml          ← Python dependencies
│   └── app/
│       ├── main.py             ← FastAPI app + lifespan + seeding
│       ├── api/v1/
│       │   ├── router.py       ← Mounts all sub-routers at /api/v1
│       │   ├── auth.py         ← /auth/login, /auth/refresh, /auth/google
│       │   ├── borrower.py     ← /borrowers/search, /borrowers/{id}
│       │   ├── documents.py    ← /documents/checklist, /documents/classify
│       │   ├── underwriting.py ← /underwriting/evaluate, /underwriting/compare
│       │   └── utilities.py    ← /utils/dti, /utils/ltv, /utils/mortgage
│       ├── core/
│       │   ├── config.py       ← Settings (reads .env via pydantic-settings)
│       │   ├── security.py     ← JWT creation/verification, bcrypt
│       │   ├── middleware.py   ← CORS, correlation ID, request logging
│       │   └── exceptions.py  ← AppError hierarchy
│       ├── infrastructure/
│       │   ├── database/
│       │   │   ├── engine.py   ← SQLAlchemy async engine + session factory
│       │   │   └── models.py   ← ORM table definitions (BorrowerORM, UserORM…)
│       │   ├── cache/
│       │   │   └── redis_client.py  ← Redis connection + RateLimiter
│       │   └── ai/
│       │       └── mock_provider.py ← Mock AI responses for dev
│       ├── models/domain/      ← Pydantic domain models
│       ├── repositories/       ← Async DB access
│       └── services/           ← Business logic
└── frontend/
    ├── .env                    ← Frontend environment variables  ← IMPORTANT
    ├── src/
    │   ├── main.tsx            ← React entry point
    │   ├── App.tsx             ← Router setup
    │   ├── pages/              ← All UI pages
    │   ├── services/           ← API call functions
    │   ├── store/              ← Zustand state
    │   └── routes/             ← ProtectedRoute guard
    └── vite.config.ts
```

---

## 5. Step-by-Step Setup

### Step 1 — Install PostgreSQL

1. Download PostgreSQL 17 from https://www.postgresql.org/download/windows/
2. Install with default settings
3. Set superuser password to `postgres` (or update the `DATABASE_URL` in `.env`)
4. Default port: `5432`, default database: `postgres`

No manual table creation needed — the backend creates tables automatically on first startup.

### Step 2 — Install Redis (optional for development)

Redis is used for rate limiting. If not available, the app falls back gracefully.

**Option A — Docker:**
```powershell
docker run -d -p 6379:6379 redis:7
```

**Option B — Windows port from https://github.com/tporadowski/redis/releases**

### Step 3 — Set Up Python Virtual Environment

```powershell
# From the repo root
Set-Location "c:\pp\GitHub\Python_usecases\backend"

# Create venv
python -m venv .venv

# Activate
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
# OR if pyproject.toml:
pip install -e ".[dev]"
```

**Required packages** (key ones):
```
fastapi
uvicorn[standard]
sqlalchemy[asyncio]==2.0.49
asyncpg==0.31.0
pydantic-settings
python-jose[cryptography]
bcrypt
httpx
structlog
redis
prometheus-client
```

> ⚠️ **Windows Defender Note**: On first import, Windows Defender scans newly-installed
> `.pyd` (C extension) files. This can cause Python to appear frozen for 10-30 seconds.
> To fix: add `c:\pp\GitHub\Python_usecases\backend\.venv` to Windows Defender exclusions.
> *Windows Security → Virus & threat protection → Exclusions → Add Folder*

### Step 4 — Configure Backend Environment

Edit `backend/.env`:

```env
APP_NAME=Mortgage Utilities Platform
APP_VERSION=0.1.0
ENVIRONMENT=development
DEBUG=true

SECRET_KEY=dev_secret_change_in_prod_min_32_chars_xx
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# PostgreSQL (required)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/postgres

# Redis (optional in dev)
REDIS_URL=redis://localhost:6379/0

AI_PROVIDER=mock
LOG_LEVEL=INFO

# Google OAuth (required for Google login)
GOOGLE_CLIENT_ID=<your-google-client-id>
OAUTH_REDIRECT_URI=http://localhost:3000/auth/callback
```

> ⚠️ Do NOT use `sqlite+aiosqlite://` in DATABASE_URL — aiosqlite is not installed.
> Always use `postgresql+asyncpg://`.

### Step 5 — Set Up Frontend

```powershell
Set-Location "c:\pp\GitHub\Python_usecases\frontend"
npm install
```

### Step 6 — Configure Frontend Environment

Edit `frontend/.env`:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_APP_NAME=Mortgage Utilities Platform
VITE_GOOGLE_CLIENT_ID=<your-google-client-id>
VITE_OAUTH_REDIRECT_URI=http://localhost:3000/auth/callback
```

---

## 6. Environment Configuration

### backend/.env — Full Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | *(required)* | Must be `postgresql+asyncpg://user:pass@host:port/db` |
| `SECRET_KEY` | `dev_secret...` | Min 32 chars — change in production |
| `REDIS_URL` | `redis://localhost:6379/0` | Rate limiter; app works without Redis |
| `GOOGLE_CLIENT_ID` | *(empty)* | OAuth 2.0 client ID from Google Console |
| `OAUTH_REDIRECT_URI` | `http://localhost:3000/auth/callback` | Must match frontend port |
| `AI_PROVIDER` | `mock` | Options: `mock`, `openai`, `bedrock`, `azure_openai` |
| `ENVIRONMENT` | `development` | Options: `development`, `staging`, `production` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | JWT access token lifetime |

### frontend/.env — Full Reference

| Variable | Description |
|----------|-------------|
| `VITE_API_BASE_URL` | Backend URL (must match CORS origins in `config.py`) |
| `VITE_GOOGLE_CLIENT_ID` | Same value as backend `GOOGLE_CLIENT_ID` |
| `VITE_OAUTH_REDIRECT_URI` | Must match the port Vite is running on |

### CORS Configuration (backend/app/core/config.py)

The backend allows requests from these origins by default:
```python
cors_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
    "http://localhost:3003",
    "http://localhost:5173",
]
```

If Vite auto-selects a different port, add it to this list and restart the backend.

---

## 7. Running the Application

### Start the Backend

```powershell
Set-Location "c:\pp\GitHub\Python_usecases\backend"
& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Expected output:
```
INFO     Started server process
INFO     Waiting for application startup.
INFO     application_starting  name=Mortgage Utilities Platform
INFO     database_tables_ready
INFO     Application startup complete.
INFO     Uvicorn running on http://0.0.0.0:8000
```

On first run the backend auto-seeds 5 sample borrowers into the database.

### Start the Frontend

```powershell
Set-Location "c:\pp\GitHub\Python_usecases\frontend"
npx vite --port 3000
```

Expected output:
```
  VITE v5.x  ready in xxx ms
  ➜  Local:   http://localhost:3000/
```

> If ports 3000-3002 are occupied, Vite auto-selects the next available port.
> Update `VITE_OAUTH_REDIRECT_URI` in `frontend/.env` and `OAUTH_REDIRECT_URI` in
> `backend/.env` to match the actual port, then restart both servers.

### Verify Backend is Running

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/health"
# Expected: { "status": "ok" }

Invoke-RestMethod -Uri "http://localhost:8000/docs"
# Opens Swagger UI
```

---

## 8. Authentication Flows

### Flow A — Username/Password Login

```
Browser                Frontend               Backend               PostgreSQL
   │                      │                      │                      │
   │  Enter credentials   │                      │                      │
   │─────────────────────►│                      │                      │
   │                      │  POST /api/v1/auth/  │                      │
   │                      │  login               │                      │
   │                      │  {username,password} │                      │
   │                      │─────────────────────►│                      │
   │                      │                      │  SELECT user         │
   │                      │                      │─────────────────────►│
   │                      │                      │◄─────────────────────│
   │                      │                      │  bcrypt.verify()     │
   │                      │                      │  create JWT          │
   │                      │◄─────────────────────│                      │
   │                      │  {access_token,       │                      │
   │                      │   refresh_token}      │                      │
   │                      │                      │                      │
   │  Navigate to /dash   │                      │                      │
   │◄─────────────────────│                      │                      │
```

### Flow B — Google OAuth Login

```
Browser               Frontend              Backend              Google
   │                     │                     │                     │
   │  Click "Google"     │                     │                     │
   │────────────────────►│                     │                     │
   │                     │  GoogleOAuthProvider│                     │
   │                     │  .signIn()          │                     │
   │◄────────────────────│                     │                     │
   │  Google popup opens │                     │                     │
   │────────────────────────────────────────────────────────────────►│
   │◄────────────────────────────────────────────────────────────────│
   │  id_token returned  │                     │                     │
   │────────────────────►│                     │                     │
   │                     │  POST /api/v1/auth/ │                     │
   │                     │  google             │                     │
   │                     │  {id_token}         │                     │
   │                     │────────────────────►│                     │
   │                     │                     │  GET /oauth2/v3/    │
   │                     │                     │  certs (JWKS)       │
   │                     │                     │────────────────────►│
   │                     │                     │◄────────────────────│
   │                     │                     │  jose_jwt.decode()  │
   │                     │                     │  Provision user if  │
   │                     │                     │  first login (OPS   │
   │                     │                     │  role assigned)     │
   │                     │◄────────────────────│                     │
   │                     │  {access_token,      │                     │
   │                     │   refresh_token}     │                     │
   │  Navigate /dashboard│                     │                     │
   │◄────────────────────│                     │                     │
```

### JWT Token Structure

```
Header:  { "alg": "HS256", "typ": "JWT" }
Payload: {
  "sub":  "<user_id>",
  "iat":  <issued_at_unix_timestamp>,
  "exp":  <expiry_unix_timestamp>,
  "role": "UNDERWRITER" | "OPS" | "ADMIN"
}
Signature: HMAC-SHA256(base64(header) + "." + base64(payload), SECRET_KEY)
```

---

## 9. API Reference

### Authentication

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| POST | `/api/v1/auth/login` | `{username, password}` | Password login → JWT pair |
| POST | `/api/v1/auth/refresh` | `{refresh_token}` | Rotate tokens |
| POST | `/api/v1/auth/google` | `{id_token}` | Google login → JWT pair |
| GET | `/api/v1/auth/me` | — | Current user info |

### Borrower

| Method | Endpoint | Params | Description |
|--------|----------|--------|-------------|
| GET | `/api/v1/borrowers/search` | `loan_number`, `first_name`, `last_name`, `ssn_last4` | Search (any one field) |
| GET | `/api/v1/borrowers/{id}` | — | Get borrower by ID |

### Underwriting

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/underwriting/evaluate` | Evaluate rules for a loan scenario |
| POST | `/api/v1/underwriting/compare` | Compare multiple loan scenarios |

### Utilities (calculator)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/utils/dti` | Calculate Debt-to-Income ratio |
| POST | `/api/v1/utils/ltv` | Calculate Loan-to-Value ratio |
| POST | `/api/v1/utils/mortgage` | Calculate monthly payment |

### Documents

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/documents/checklist` | Get required documents for a loan program |
| POST | `/api/v1/documents/classify` | Classify an uploaded document type |

---

## 10. Borrower Search (OR Logic)

The search endpoint accepts **any single field** or combination. It uses SQL OR logic so a result is returned if **any** field matches.

```
GET /api/v1/borrowers/search?last_name=Carter
GET /api/v1/borrowers/search?loan_number=LN-2024-001
GET /api/v1/borrowers/search?ssn_last4=3821
GET /api/v1/borrowers/search?first_name=James
GET /api/v1/borrowers/search?first_name=James&last_name=Carter
```

### How it works — Repository layer

```python
# borrower_repository.py
conditions = []
if loan_number:
    conditions.append(BorrowerORM.loan_number.ilike(f"%{loan_number}%"))
if last_name:
    conditions.append(BorrowerORM.last_name.ilike(f"%{last_name}%"))
if ssn_last4:
    conditions.append(BorrowerORM.ssn_last4 == ssn_last4)
if first_name:
    conditions.append(BorrowerORM.first_name.ilike(f"%{first_name}%"))

stmt = stmt.where(or_(*conditions))   # ← OR, not AND
```

### Why empty strings caused 422 errors

The frontend sends `""` for unfilled fields. Pydantic models have `min_length=1`.
Fix applied in `backend/app/api/v1/borrower.py`:

```python
# Convert empty strings → None before Pydantic validation
request = BorrowerLookupRequest(
    loan_number=loan_number or None,
    last_name=last_name or None,
    ssn_last4=ssn_last4 or None,
    first_name=first_name or None,
)
```

---

## 11. Google OAuth Setup

### Step 1 — Create Google Cloud Project

1. Go to https://console.cloud.google.com/
2. Create a new project (or use an existing one)
3. Navigate to **APIs & Services → Credentials**

### Step 2 — Create OAuth 2.0 Client ID

1. Click **Create Credentials → OAuth client ID**
2. Application type: **Web application**
3. Add **Authorized JavaScript origins**:
   ```
   http://localhost:3000
   http://localhost:3001
   http://localhost:3002
   http://localhost:3003
   ```
4. Add **Authorized redirect URIs**:
   ```
   http://localhost:3000/auth/callback
   http://localhost:3001/auth/callback
   http://localhost:3002/auth/callback
   http://localhost:3003/auth/callback
   ```
5. Click **Create** — copy the **Client ID**

### Step 3 — Configure Both Environments

`backend/.env`:
```env
GOOGLE_CLIENT_ID=<your-client-id>.apps.googleusercontent.com
OAUTH_REDIRECT_URI=http://localhost:3000/auth/callback
```

`frontend/.env`:
```env
VITE_GOOGLE_CLIENT_ID=<your-client-id>.apps.googleusercontent.com
VITE_OAUTH_REDIRECT_URI=http://localhost:3000/auth/callback
```

> ⚠️ Both files must use the **same port** in their redirect URIs, and that port must be
> listed as an Authorized origin in Google Console. Mismatches cause "Access blocked"
> or "Network Error" after the Google popup closes.

---

## 12. Known Issues & Fixes

### Issue 1 — Windows Defender freezes Python on first run

**Symptom:** `import sqlalchemy` hangs indefinitely; backend exit code 1 with no output.

**Root Cause:** Windows Defender scans newly-compiled `.pyd` C-extension files when Python loads them for the first time.

**Fix:**
```
Windows Security → Virus & threat protection → Manage settings
→ Exclusions → Add an exclusion → Folder
→ Add: c:\pp\GitHub\Python_usecases\backend\.venv
```

After adding the exclusion, restart the backend normally.

---

### Issue 2 — `DATABASE_URL` in `.env` overrides PostgreSQL default

**Symptom:** Backend crashes silently if `.env` contains `sqlite+aiosqlite:///` but `aiosqlite` is not installed.

**Root Cause:** `pydantic-settings` reads `.env` and overrides the Python default in `config.py`.

**Fix:** Ensure `backend/.env` has:
```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/postgres
```

---

### Issue 3 — CORS error when frontend port changes

**Symptom:** Browser console shows `CORS policy: No 'Access-Control-Allow-Origin' header`.

**Root Cause:** Vite auto-selected a port not in `cors_origins` list.

**Fix:** Add the new port to `backend/app/core/config.py`:
```python
cors_origins: list[str] = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
    "http://localhost:3003",
    "http://localhost:5173",
]
```
Then restart the backend.

---

### Issue 4 — Google OAuth "Network Error" after successful popup

**Symptom:** Google popup succeeds, but the frontend shows "Network Error".

**Root Cause:** `GOOGLE_CLIENT_ID` is empty in `backend/.env`, causing the backend to immediately reject the token with `AuthenticationError("Google OAuth is not configured on this server")`.

**Fix:** Set `GOOGLE_CLIENT_ID` in `backend/.env` (see [Section 11](#11-google-oauth-setup)).

---

### Issue 5 — Borrower search returns results only when all fields are filled

**Symptom:** Search with only `last_name` returns no results.

**Root Cause:** Original repository used AND logic — all non-null filters had to match.

**Fix:** Changed to OR logic in `borrower_repository.py` using `sqlalchemy.or_()`.

---

## 13. Test Credentials

These users are seeded into the database on first startup:

| Username | Password | Role | Access |
|----------|----------|------|--------|
| `admin` | `Admin@123456` | ADMIN | Full access |
| `underwriter1` | `Underwriter@123` | UNDERWRITER | All features |
| `ops_user1` | `OpsUser@123` | OPS | Limited — no underwriting |

### Sample Borrowers (seeded automatically)

| Loan Number | Name | SSN Last 4 | Program |
|-------------|------|-----------|---------|
| LN-2024-001 | James Carter | 3821 | CONV_30 |
| LN-2024-002 | Maria Gonzalez | 5590 | FHA_30 |
| LN-2024-003 | David Kim | 7743 | JUMBO_30 |
| LN-2024-004 | Sarah Thompson | 4412 | CONV_30 |
| LN-2024-005 | Robert Martinez | 9901 | CONV_30 |

### Quick API Test

```powershell
# 1. Login
$resp = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/auth/login" `
  -Method Post -ContentType "application/json" `
  -Body '{"username":"admin","password":"Admin@123456"}'
$token = $resp.access_token

# 2. Search borrowers
$h = @{ Authorization = "Bearer $token" }
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/borrowers/search?last_name=carter" -Headers $h

# 3. Check docs
Start-Process "http://localhost:8000/docs"
```

---

## 14. Docker Compose (Alternative)

To run everything in containers:

```powershell
docker-compose up --build
```

This starts:
- **backend** on port 8000
- **frontend** on port 3000  
- **postgres** on port 5432
- **redis** on port 6379

Edit `docker-compose.yml` to set environment variables for production use.
