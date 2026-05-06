# LLMOps Production Agent — Architecture & Execution Reference

## Table of Contents
1. [Repository Structure](#1-repository-structure)
2. [Technology Stack](#2-technology-stack)
3. [System Architecture Diagram](#3-system-architecture-diagram)
4. [Supporting Infrastructure](#4-supporting-infrastructure)
5. [Step-by-Step Execution Flow](#5-step-by-step-execution-flow)
   - [Phase 0 — Application Startup](#phase-0--application-startup)
   - [Phase 1 — HTTP Request Ingress](#phase-1--http-request-ingress)
   - [Phase 2 — Input Guardrails](#phase-2--input-guardrails-7-checks)
   - [Phase 3 — LangGraph Execution](#phase-3--langgraph-execution)
   - [Phase 4 — HTTP Response](#phase-4--http-response)
   - [Phase 5 — Evaluation Endpoints](#phase-5--evaluation-endpoints-on-demand)
6. [Error Handling & Fallback Matrix](#6-error-handling--fallback-matrix)
7. [API Reference](#7-api-reference)
8. [Environment Variables Reference](#8-environment-variables-reference)
9. [Running the Application](#9-running-the-application)

---

## 1. Repository Structure

```
llmops_prod_repo/
│
├── app.py                        # FastAPI entry point: routing, middleware, lifespan
│
├── agent/
│   ├── graph.py                  # LangGraph StateGraph — wires the 3-node DAG
│   ├── planner.py                # Node 1: decides create_ticket vs view_ticket via GPT-4o-mini
│   ├── tools.py                  # Node 2: executes Jira API calls (create / view)
│   └── response.py               # Node 3: composes final answer with memory + RAG context
│
├── guardrails/
│   ├── rules.py                  # 7-layer input validation + 4-step output sanitisation
│   └── pii_redactor.py           # PII detection (Presidio primary, regex fallback) + redaction
│
├── memory/
│   ├── redis_store.py            # Session conversation memory (get/save per session_id)
│   └── pinecone_store.py         # Vector DB retrieval for RAG context chunks
│
├── observability/
│   ├── logger.py                 # Structured JSON logging + correlation ID + @trace_agent
│   ├── metrics.py                # In-process counters + latency histograms (p50/p95/p99)
│   ├── breakers.py               # pybreaker circuit breakers for all 4 external services
│   └── langsmith_tracer.py       # LangSmith tracing callbacks + custom span recording
│
├── security/
│   └── rbac.py                   # Role-based access control (USER_ROLES + ROLE_PERMISSIONS)
│
├── evaluation/
│   ├── __init__.py
│   ├── rag_evaluator.py          # RAGAS: faithfulness, relevancy, precision, recall
│   └── llm_evaluator.py          # DeepEval: relevancy, toxicity, bias, faithfulness, hallucination
│
└── requirements.txt              # All dependencies, organised by category
```

---

## 2. Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Web framework | FastAPI | HTTP server, request validation, middleware |
| Agent orchestration | LangGraph | Stateful multi-step agent DAG |
| LLM | OpenAI GPT-4o-mini | Planning decisions + moderation |
| LLM integration | LangChain / langchain-core | LLM abstraction layer |
| Observability | LangSmith | Distributed tracing, run replay, evaluation dashboard |
| PII engine (primary) | Microsoft Presidio | NLP-based PII detection (spaCy `en_core_web_lg`) |
| PII engine (fallback) | Regex | Email, phone, SSN, credit card, IPv4, passport |
| RAG evaluation | RAGAS + HuggingFace Datasets | Pipeline quality metrics |
| LLM evaluation | DeepEval | Output safety and quality metrics |
| Vector database | Pinecone | Semantic context retrieval |
| Session memory | Redis | Conversation history per session |
| Ticket system | Jira (atlassian-python-api) | Ticket creation and viewing |
| Circuit breaker | pybreaker | Resilience for all external services |
| Retry | tenacity | Exponential back-off on transient errors |
| Structured logging | Python logging + ContextVar | JSON logs with correlation IDs |

---

## 3. System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          EXTERNAL CLIENTS                                   │
│              Browser / curl / CI pipeline / Postman                         │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │ HTTP POST /run_agent
                                │ (+ optional X-Correlation-ID header)
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       FASTAPI  APPLICATION  (app.py)                        │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  correlation_middleware                                              │   │
│  │  • Generate or forward X-Correlation-ID (UUID)                      │   │
│  │  • Store in ContextVar (async-safe, per-request isolation)          │   │
│  │  • Measure end-to-end HTTP latency → record_duration()              │   │
│  └──────────────────────────────┬──────────────────────────────────────┘   │
│                                 │                                           │
│  ┌──────────────────────────────▼──────────────────────────────────────┐   │
│  │  AgentRequest (Pydantic)                                             │   │
│  │  • input, user (email), role, session_id                            │   │
│  │  • field_validator: rejects blank fields before code even runs      │   │
│  └──────────────────────────────┬──────────────────────────────────────┘   │
│                                 │                                           │
│  ┌──────────────────────────────▼──────────────────────────────────────┐   │
│  │  INPUT GUARDRAILS  (guardrails/rules.py)                             │   │
│  │  Check 1: empty / whitespace input  → 400                           │   │
│  │  Check 2: length > 2000 chars       → 400                           │   │
│  │  Check 3: 8 regex patterns (SQLi, XSS, prompt-injection, jailbreak) │   │
│  │  Check 4: user must be valid email                                  │   │
│  │  Check 5: role must not be blank                                    │   │
│  │  Check 6: session_id min 4 chars                                    │   │
│  │  Check 7: PII audit (Presidio scan, LOG only — never blocks)        │   │
│  └──────────────────────────────┬──────────────────────────────────────┘   │
│                                 │ passes all 7 checks                       │
└─────────────────────────────────┼───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    LANGGRAPH  AGENT  (agent/graph.py)                       │
│                                                                             │
│  StateGraph compiles a 3-node DAG (rebuilt per request for isolation)      │
│  LangSmith run_config injected → all nodes auto-traced to LangSmith         │
│                                                                             │
│  AgentState (shared dict flowing through every node):                      │
│  { input, user, role, session_id, plan, tool_result, output }              │
│                                                                             │
│  [START]                                                                    │
│     │                                                                       │
│     ▼                                                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  NODE 1 — planner_agent  (agent/planner.py)                          │  │
│  │                                                                      │  │
│  │  Prompt → OpenAI GPT-4o-mini (timeout=15s)                          │  │
│  │  "Given role + query → respond: create_ticket OR view_ticket"       │  │
│  │                                                                      │  │
│  │  Reliability stack:                                                  │  │
│  │    tenacity retry: up to 3× on ConnectionError / TimeoutError       │  │
│  │      └─ exponential back-off: 1s → 2s → 4s                          │  │
│  │    openai_breaker: opens after 3 failures, resets after 60s         │  │
│  │                                                                      │  │
│  │  Writes: state["plan"] = "create_ticket" | "view_ticket"            │  │
│  └──────────────────────────────────┬───────────────────────────────────┘  │
│                                     │                                       │
│     ▼                                                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  NODE 2 — tool_agent  (agent/tools.py)                               │  │
│  │                                                                      │  │
│  │  RBAC check FIRST (security/rbac.py):                               │  │
│  │    PRODUCT_OWNER → can create + read                                │  │
│  │    DEVELOPER     → read only                                        │  │
│  │    Violation → PermissionError → HTTP 403                           │  │
│  │                                                                      │  │
│  │  If plan == "create_ticket":                                        │  │
│  │    → _jira_create()  [jira_breaker, 3 retries]                      │  │
│  │  If plan == "view_ticket":                                          │  │
│  │    → _jira_fetch()   [jira_breaker, 3 retries]                      │  │
│  │                                                                      │  │
│  │  jira_breaker: opens after 3 failures, resets after 30s             │  │
│  │                                                                      │  │
│  │  Writes: state["tool_result"]                                        │  │
│  └──────────────────────────────────┬───────────────────────────────────┘  │
│                                     │                                       │
│     ▼                                                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  NODE 3 — response_agent  (agent/response.py)                        │  │
│  │                                                                      │  │
│  │  1. Redis get_memory(session_id)      [redis_breaker, non-fatal]    │  │
│  │  2. Pinecone retrieve_context(input)  [pinecone_breaker, non-fatal] │  │
│  │  3. Compose raw_output = plan + tool_result + memory + context      │  │
│  │  4. OUTPUT GUARDRAILS:                                              │  │
│  │       Step 1: strip null bytes + control chars                      │  │
│  │       Step 2: truncate to 10 000 chars                              │  │
│  │       Step 3: PII redact via Presidio (→ regex fallback)            │  │
│  │       Step 4: OpenAI moderation API (hate / violence / self-harm)   │  │
│  │  5. Redis save_memory(session_id, input, output)  [non-fatal]       │  │
│  │                                                                      │  │
│  │  Writes: state["output"]                                             │  │
│  └──────────────────────────────────┬───────────────────────────────────┘  │
│                                     │                                       │
│                                   [END]                                     │
└─────────────────────────────────────┼───────────────────────────────────────┘
                                      │ state["output"]
                                      ▼
                         { "output": "...", "correlation_id": "uuid" }
                              ← returned to caller (HTTP 200)
```

---

## 4. Supporting Infrastructure

### Observability Layer

```
┌─────────────────────┐  ┌─────────────────────┐  ┌──────────────────────────┐
│  logger.py          │  │  metrics.py          │  │  langsmith_tracer.py     │
│                     │  │                      │  │                          │
│  Structured JSON    │  │  In-process counters │  │  LangSmith spans auto-   │
│  logs with:         │  │  + histograms        │  │  sent on every node      │
│  • timestamp        │  │                      │  │  execution               │
│  • correlation_id   │  │  Exposed at:         │  │                          │
│  • level            │  │  GET /metrics        │  │  Activated by:           │
│  • logger name      │  │                      │  │  LANGCHAIN_TRACING_V2    │
│                     │  │  Percentiles:        │  │  =true                   │
│  @trace_agent       │  │  p50 / p95 / p99     │  │  + LANGCHAIN_API_KEY     │
│  decorator on each  │  │  per metric key      │  │                          │
│  agent function     │  │                      │  │  trace_custom() for      │
│                     │  │                      │  │  evaluation scores       │
└─────────────────────┘  └─────────────────────┘  └──────────────────────────┘
```

### Circuit Breakers (observability/breakers.py)

| Breaker | fail_max | reset_timeout | Used by |
|---------|----------|---------------|---------|
| `openai_breaker` | 3 failures | 60 seconds | planner + moderation |
| `jira_breaker` | 3 failures | 30 seconds | tool agent |
| `redis_breaker` | 5 failures | 20 seconds | memory read/write |
| `pinecone_breaker` | 3 failures | 30 seconds | context retrieval |

**Circuit breaker states:**
```
CLOSED (normal) ──► OPEN (failures ≥ fail_max) ──► HALF-OPEN (after reset_timeout)
   ▲                         │                              │
   └─────── success ─────────┘◄─── test call fails ─────────┘
                                                  └─── test call passes → CLOSED
```

### PII Engine (guardrails/pii_redactor.py)

```
Primary: Microsoft Presidio
  AnalyzerEngine  (loads spaCy en_core_web_lg on startup, ~3-5s)
  AnonymizerEngine (performs replacements)
  Detects 11 entity types:
    PERSON, EMAIL_ADDRESS, PHONE_NUMBER, CREDIT_CARD, IBAN_CODE,
    IP_ADDRESS, US_SSN, US_PASSPORT, LOCATION, DATE_TIME, NRP

Fallback: Regex (6 compiled patterns)
  email, US phone, US SSN, credit card (Visa/MC/Amex/Discover),
  IPv4 address, US passport number

Routing:
  PII_REDACTION_ENABLED=false → text returned unchanged
  Presidio available          → Presidio (higher accuracy, NER-based)
  Presidio unavailable        → regex fallback
```

### Evaluation Endpoints

```
POST /evaluate/rag                     POST /evaluate/llm
     │                                       │
     ▼                                       ▼
evaluation/rag_evaluator.py          evaluation/llm_evaluator.py
     │                                       │
RAGAS metrics (LLM-as-judge):          DeepEval metrics (LLM-as-judge):
• faithfulness                         • AnswerRelevancyMetric  threshold=0.7
• answer_relevancy                     • ToxicityMetric         threshold=0.5
• context_precision                    • BiasMetric             threshold=0.5
• context_recall*                      • FaithfulnessMetric*    threshold=0.7
  (* needs ground_truths)              • HallucinationMetric*   threshold=0.5
     │                                   (* needs retrieval_context)
     └──────────────┬────────────────────────────────┘
                    │ trace_custom() → pushed to LangSmith
                    │ (evaluation scores visible alongside agent traces)
```

---

## 5. Step-by-Step Execution Flow

### Phase 0 — Application Startup

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

| Step | Module | What happens |
|------|--------|-------------|
| 0.1 | `app.py` | `lifespan()` runs → logs "Application starting up" |
| 0.2 | `pii_redactor.py` | `AnalyzerEngine()` + `AnonymizerEngine()` load spaCy `en_core_web_lg` (once, ~3–5 s) |
| 0.3 | `breakers.py` | 4 circuit breakers instantiated with their configs |
| 0.4 | `tools.py` | Jira client initialised from env vars (or mock-mode warning logged if vars missing) |
| 0.5 | `app.py` | FastAPI registers all routes; CORS middleware attached |
| 0.6 | `langsmith_tracer.py` | `_build_tracer()` called; `LangChainTracer` created if `LANGCHAIN_TRACING_V2=true` |

---

### Phase 1 — HTTP Request Ingress

**Client sends:**
```http
POST /run_agent
X-Correlation-ID: abc-123          ← optional; generated if absent
Content-Type: application/json

{
  "input":      "Create ticket for login bug",
  "user":       "alice@company.com",
  "role":       "PRODUCT_OWNER",
  "session_id": "sess-xyz-001"
}
```

| Step | Code location | What happens |
|------|--------------|-------------|
| 1.1 | `correlation_middleware` | Reads `X-Correlation-ID` header or generates `uuid.uuid4()` |
| 1.2 | `correlation_middleware` | Stores ID in `ContextVar` (async-safe isolation per request) |
| 1.3 | `correlation_middleware` | `perf_counter()` starts for end-to-end latency tracking |
| 1.4 | `AgentRequest` (Pydantic) | All 4 fields validated as non-blank; whitespace stripped; returns 422 if any field is empty |
| 1.5 | `run_agent_endpoint` | `increment("api.run_agent.requests")` — counter ticked |

---

### Phase 2 — Input Guardrails (7 checks)

All checks run in `guardrails/rules.py → validate_input()`. First failure raises `GuardrailViolation` → HTTP 400.

| # | Check | Trigger condition | Error message |
|---|-------|------------------|---------------|
| 1 | Blank input | `not input.strip()` | "Input must not be empty" |
| 2 | Length | `len(input) > 2000` | "Input exceeds maximum length of 2000 characters" |
| 3 | Injection patterns | Matches any of 8 compiled regex patterns | "Input contains disallowed content" |
| 4 | User format | Does not match `^[a-zA-Z0-9_.+-]+@[domain]+$` | "Invalid user identifier format" |
| 5 | Role blank | `not role.strip()` | "Role must not be empty" |
| 6 | Session ID length | `len(session_id) < 4` | "session_id is too short or missing" |
| 7 | PII audit | Presidio finds entities | **LOG WARNING only — request continues** |

**Blocked patterns (Check 3):**
```
ignore previous instructions   → classic prompt injection
you are now                    → persona hijack
jailbreak                      → jailbreak keyword
system\s*prompt                → system-prompt extraction
act as (a|an)?                 → role-hijack
<script.*?>                    → XSS injection
drop table / delete from / ... → SQL injection
/etc/passwd / /proc/self       → path traversal
```

All 7 checks pass → execution proceeds to LangGraph.

---

### Phase 3 — LangGraph Execution

#### 3.1 — Graph Construction (`agent/graph.py`)

```python
graph = StateGraph(AgentState)
graph.add_node("planner",  planner_agent)
graph.add_node("tool",     tool_agent)
graph.add_node("response", response_agent)
graph.add_edge(START,      "planner")
graph.add_edge("planner",  "tool")
graph.add_edge("tool",     "response")
graph.add_edge("response", END)
compiled_graph = graph.compile()
```

`get_run_config()` builds a config dict containing:
- `LangChainTracer` callback (sends spans to LangSmith)
- Metadata tags: `user`, `role`, `session_id`, `correlation_id`

`graph.compile()` is lightweight (microseconds); graph is rebuilt per request to guarantee state isolation between concurrent users.

Initial state injected:
```python
{
    "input":       "Create ticket for login bug",
    "user":        "alice@company.com",
    "role":        "PRODUCT_OWNER",
    "session_id":  "sess-xyz-001",
    "plan":        "",   # filled by planner node
    "tool_result": "",   # filled by tool node
    "output":      "",   # filled by response node
}
```

---

#### 3.2 — Node 1: Planner (`agent/planner.py`)

```
Prompt sent to OpenAI GPT-4o-mini:
  "User Role: PRODUCT_OWNER
   Query: Create ticket for login bug
   Respond with exactly one of: create_ticket, view_ticket"

Reliability stack:
  tenacity retry (up to 3 attempts):
    Attempt 1 → ConnectionError → wait 1s
    Attempt 2 → ConnectionError → wait 2s
    Attempt 3 → success
  Wrapped in openai_breaker.call():
    If breaker is OPEN → raises CircuitBreakerError → HTTP 503

LLM response: "create_ticket"
Normalisation: "create" in response → plan = "create_ticket"
               else                 → plan = "view_ticket"
```

State after node: `state["plan"] = "create_ticket"`

Metrics recorded:
- `increment("planner.success")`
- `record_duration("planner.latency_ms", elapsed_ms)`

`@trace_agent("planner")` decorator logs:
```json
{ "event": "agent_start",  "agent": "planner", "correlation_id": "abc-123" }
{ "event": "agent_finish", "agent": "planner", "elapsed_ms": 420.5 }
```

---

#### 3.3 — Node 2: Tool (`agent/tools.py`)

**Step A — RBAC check (before any Jira call):**
```python
check_permission("alice@company.com", "create")
  USER_ROLES["alice@company.com"]    = "PRODUCT_OWNER"
  ROLE_PERMISSIONS["PRODUCT_OWNER"]  = ["create", "read"]
  "create" in ["create", "read"]     → PASS
```
If `"create"` is not in the role's permissions → `PermissionError` → HTTP 403.

**Step B — Jira API call:**
```
plan == "create_ticket"
  → _jira_create("Create ticket for login bug")
      ↳ jira_breaker.call(lambda: jira.create_issue({...}))
      ↳ tenacity: retry 3× on ConnectionError / TimeoutError
                  back-off: 1s → 2s → 4s
      ↳ Jira REST API: POST /rest/api/2/issue
        → returns {"key": "TEST-42", "id": "10042", ...}

plan == "view_ticket"
  → _jira_fetch()
      ↳ jira_breaker.call(lambda: jira.jql("project=TEST ORDER BY created DESC"))
      ↳ returns ["TEST-42: Bug in login", "TEST-41: API timeout", ...]
```

State after node: `state["tool_result"] = "TEST-42 created successfully"`

---

#### 3.4 — Node 3: Response (`agent/response.py`)

**Step 1 — Read Redis session memory:**
```python
mem = get_memory("sess-xyz-001")
# Returns: ["Q: Previous query", "A: Previous answer"]
# If Redis is down → caught by try/except → mem = []  (graceful degradation)
```

**Step 2 — Retrieve Pinecone context:**
```python
ctx = retrieve_context("Create ticket for login bug")
# Returns: ["Jira project key is TEST", "Default issue type is Task"]
# If Pinecone is down → caught by try/except → ctx = ["context unavailable"]
```

**Step 3 — Compose raw output:**
```
raw_output = "Plan: create_ticket | Tool: TEST-42 | History: [...] | Context: [...]"
```

**Step 4 — Output Guardrails (4 steps in sequence):**

| Step | What it does | Example transformation |
|------|-------------|----------------------|
| 1 | Strip null bytes + control chars (keep `\n`, `\t`) | `"hello\x00world"` → `"helloworld"` |
| 2 | Truncate to 10 000 chars | Appends `" [truncated]"` if over limit |
| 3 | Presidio PII redaction | `"alice@company.com"` → `"<EMAIL_ADDRESS>"` |
| 4 | OpenAI moderation API | Flags hate/violence/self-harm categories (non-blocking) |

**Step 5 — Write Redis session memory:**
```python
save_memory("sess-xyz-001", input, output)
# Stores turn for next request's context
# If Redis is down → caught by try/except → silently skipped
```

State after node: `state["output"]` = sanitised final answer.

---

### Phase 4 — HTTP Response

| Step | What happens |
|------|-------------|
| 4.1 | `correlation_middleware` stops `perf_counter()` → `record_duration("http.latency_ms", elapsed_ms)` |
| 4.2 | Response headers set: `X-Correlation-ID: abc-123`, `X-Response-Time-Ms: 342.5` |
| 4.3 | LangSmith tracer flushes all spans for this run (planner + tool + response as child spans) |
| 4.4 | JSON body returned to caller |

**Response:**
```json
{
  "output": "Ticket TEST-42 created: Create ticket for login bug",
  "correlation_id": "abc-123"
}
```

---

### Phase 5 — Evaluation Endpoints (on-demand)

These are called separately from `/run_agent`, typically in a CI pipeline or after collecting a batch of real requests.

#### POST /evaluate/rag

**Request:**
```json
{
  "questions":     ["What is the refund policy?"],
  "answers":       ["Refunds are processed in 7 days."],
  "contexts":      [["Our policy states refunds take 5-7 business days."]],
  "ground_truths": ["Refunds take 5-7 business days."]
}
```

**Execution flow:**
```
1. Validate: equal-length lists, non-empty
2. Build HuggingFace Dataset from lists
3. RAGAS evaluate() — calls LLM judge for each metric on each sample:
     faithfulness:      Is every claim backed by context?    → 0.92
     answer_relevancy:  Does answer address the question?    → 0.87
     context_precision: Are retrieved chunks useful?         → 0.79
     context_recall:    Does context cover ground truth?     → 0.84
4. trace_custom("rag_evaluation", scores) → pushed to LangSmith
5. Return: { "status": "success", "metrics": {...}, "n_samples": 1 }
```

#### POST /evaluate/llm

**Request:**
```json
{
  "input_text":        "What is our SLA?",
  "actual_output":     "Our SLA is 99.9% uptime.",
  "retrieval_context": ["SLA document: 99.9% uptime guaranteed."]
}
```

**Execution flow:**
```
1. Build LLMTestCase(input, actual_output, retrieval_context)
2. DeepEval measure() for each metric (LLM judge called internally):
     AnswerRelevancyMetric:  0.91  ≥ 0.7  → ✅ PASS
     ToxicityMetric:         0.03  ≤ 0.5  → ✅ PASS
     BiasMetric:             0.02  ≤ 0.5  → ✅ PASS
     FaithfulnessMetric:     0.88  ≥ 0.7  → ✅ PASS  (context provided)
     HallucinationMetric:    0.10  ≤ 0.5  → ✅ PASS  (context provided)
3. all_passed = all metrics passed → True
4. trace_custom("llm_evaluation", results) → pushed to LangSmith
5. Return: { "status": "success", "passed": true, "metrics": [...] }
```

---

## 6. Error Handling & Fallback Matrix

| Failure scenario | Detection mechanism | HTTP status | Behaviour |
|-----------------|--------------------|-----------:|-----------|
| Empty / blank field in request | Pydantic `field_validator` | 422 | Rejected before guardrails |
| Input fails guardrail check | `GuardrailViolation` exception | 400 | Request blocked |
| User lacks permission for action | `PermissionError` from RBAC | 403 | Request blocked |
| OpenAI circuit breaker open | `CircuitBreakerError` → `RuntimeError` | 503 | Service unavailable |
| Jira circuit breaker open | `CircuitBreakerError` → `RuntimeError` | 503 | Service unavailable |
| Redis unreachable | `try/except` in response_agent | 200 | Continues without memory |
| Pinecone unreachable | `try/except` in response_agent | 200 | Continues without context |
| Presidio not installed | `ImportError` caught at module load | 200 | Falls back to regex PII redaction |
| LangSmith key missing | `_build_tracer()` returns `None` | 200 | Continues without tracing |
| OpenAI moderation API down | `try/except` in `_openai_moderate` | 200 | Output returned without check |
| Any unhandled exception | Top-level `except Exception` | 500 | Logged + "Internal server error" |

---

## 7. API Reference

### POST `/run_agent`
Execute the agent pipeline for a single user query.

**Request body:**
```json
{
  "input":      "string  (max 2000 chars, required)",
  "user":       "string  (valid email, required)",
  "role":       "string  (e.g. PRODUCT_OWNER | DEVELOPER, required)",
  "session_id": "string  (min 4 chars, required)"
}
```

**Response (200):**
```json
{ "output": "string", "correlation_id": "uuid" }
```

**Error responses:**
| Code | Cause |
|------|-------|
| 400 | Guardrail violation (injection, length, blank, invalid email) |
| 403 | RBAC permission denied |
| 422 | Pydantic validation failed (blank field) |
| 503 | Downstream circuit breaker open |
| 500 | Unexpected internal error |

---

### POST `/evaluate/rag`
Run RAGAS evaluation on a batch of RAG samples.

**Request body:**
```json
{
  "questions":     ["string", ...],
  "answers":       ["string", ...],
  "contexts":      [["string", ...], ...],
  "ground_truths": ["string", ...]   // optional — enables context_recall
}
```

**Response (200):**
```json
{
  "status": "success",
  "metrics": {
    "faithfulness": 0.92,
    "answer_relevancy": 0.87,
    "context_precision": 0.79,
    "context_recall": 0.84
  },
  "n_samples": 5
}
```

---

### POST `/evaluate/llm`
Run DeepEval quality check on a single LLM response.

**Request body:**
```json
{
  "input_text":        "string  (required)",
  "actual_output":     "string  (required)",
  "expected_output":   "string  (optional)",
  "retrieval_context": ["string", ...]  // optional — enables faithfulness + hallucination
}
```

**Response (200):**
```json
{
  "status": "success",
  "passed": true,
  "metrics": [
    { "metric": "AnswerRelevancyMetric", "score": 0.91, "passed": true, "reason": "..." },
    { "metric": "ToxicityMetric",        "score": 0.03, "passed": true, "reason": "..." }
  ]
}
```

---

### GET `/metrics`
Return in-process counters and latency percentiles.

**Response (200):**
```json
{
  "counters": {
    "api.run_agent.requests": 142,
    "planner.success": 139,
    "tools.success": 138
  },
  "histograms": {
    "http.latency_ms{path=/run_agent}": {
      "count": 142, "avg_ms": 387.4,
      "p50_ms": 340.2, "p95_ms": 820.1, "p99_ms": 1240.5
    }
  }
}
```

---

### GET `/health`
Simple liveness check.

**Response (200):** `{ "status": "ok" }`

---

## 8. Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | **Yes** | — | OpenAI API key for GPT-4o-mini + moderation |
| `LANGCHAIN_TRACING_V2` | No | `false` | Set `true` to enable LangSmith tracing |
| `LANGCHAIN_API_KEY` | If tracing | — | LangSmith API key |
| `LANGCHAIN_PROJECT` | No | `llmops-production` | LangSmith project name |
| `PII_REDACTION_ENABLED` | No | `true` | Set `false` to disable PII redaction (dev only) |
| `JIRA_URL` | No | — | Jira instance URL (e.g. `https://yourorg.atlassian.net`) |
| `JIRA_USER` | No | — | Jira username / email |
| `JIRA_TOKEN` | No | — | Jira API token |
| `PINECONE_API_KEY` | No | — | Pinecone API key |
| `PINECONE_INDEX` | No | `default-index` | Pinecone index name |
| `DEEPEVAL_RELEVANCY_THRESHOLD` | No | `0.7` | AnswerRelevancyMetric pass threshold |
| `DEEPEVAL_TOXICITY_THRESHOLD` | No | `0.5` | ToxicityMetric pass threshold |
| `DEEPEVAL_BIAS_THRESHOLD` | No | `0.5` | BiasMetric pass threshold |
| `DEEPEVAL_FAITH_THRESHOLD` | No | `0.7` | FaithfulnessMetric pass threshold |
| `DEEPEVAL_HALLUC_THRESHOLD` | No | `0.5` | HallucinationMetric pass threshold |

---

## 9. Running the Application

### Prerequisites
```powershell
# 1. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Download spaCy model required by Presidio
python -m spacy download en_core_web_lg
```

### Set environment variables (Windows PowerShell)
```powershell
$env:OPENAI_API_KEY           = "sk-..."
$env:LANGCHAIN_TRACING_V2     = "true"
$env:LANGCHAIN_API_KEY        = "ls__..."
$env:LANGCHAIN_PROJECT        = "llmops-production"
$env:JIRA_URL                 = "https://yourorg.atlassian.net"
$env:JIRA_USER                = "you@company.com"
$env:JIRA_TOKEN               = "your-jira-api-token"
$env:PINECONE_API_KEY         = "pcsk_..."
```

### Start the server
```powershell
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

### Test the agent
```powershell
# Run agent
Invoke-RestMethod -Uri "http://localhost:8000/run_agent" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"input":"Create a ticket for login bug","user":"alice@company.com","role":"PRODUCT_OWNER","session_id":"sess-001"}'

# Check metrics
Invoke-RestMethod -Uri "http://localhost:8000/metrics"

# Health check
Invoke-RestMethod -Uri "http://localhost:8000/health"
```

### Run RAG evaluation
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/evaluate/rag" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{
    "questions":     ["What is the SLA?"],
    "answers":       ["Our SLA is 99.9% uptime."],
    "contexts":      [["SLA doc: 99.9% guaranteed"]],
    "ground_truths": ["99.9% uptime"]
  }'
```

### Run LLM evaluation
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/evaluate/llm" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{
    "input_text":        "What is the SLA?",
    "actual_output":     "Our SLA is 99.9% uptime.",
    "retrieval_context": ["SLA doc: 99.9% guaranteed"]
  }'
```
