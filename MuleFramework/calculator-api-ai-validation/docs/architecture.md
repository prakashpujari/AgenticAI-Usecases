# Architecture — calculator-api-ai-validation

```
                       ┌──────────────────────────────────────────────┐
                       │                CLIENTS                        │
                       │  curl / Postman / partner systems             │
                       └────────────────────┬─────────────────────────┘
                                            │ HTTPS  (Bearer JWT + client_id)
                                            ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                       MULE 4.9  /  CALCULATOR EXPERIENCE API                  │
│                                                                               │
│  ┌──────────────────┐   ┌────────────────┐   ┌───────────────────────────┐    │
│  │ HTTP Listener    │──▶│ security.xml   │──▶│  APIKit Router (RAML)     │    │
│  │ /calculator/v1/* │   │  • JSON threat │   │   /add /subtract          │    │
│  └──────────────────┘   │  • rate limit  │   │   /multiply /divide       │    │
│                         │  • client-id   │   └──────────────┬────────────┘    │
│                         │  • JWT         │                  │                 │
│                         └────────────────┘                  ▼                 │
│                                              ┌──────────────────────────┐    │
│                                              │ calculator-api-impl.xml  │    │
│                                              │  • validate-request       │    │
│                                              │  • DataWeave add/sub/mul  │    │
│                                              │  • divide-by-zero guard   │    │
│                                              └──────────────┬───────────┘    │
│                                                             ▼                 │
│           ┌─────────────────────┐                 ┌──────────────────────┐    │
│           │ global-error-handler│ ◀───errors──── │ observability.xml    │    │
│           │  standard contract  │                 │ • correlationId      │    │
│           │  + JSON err payload │                 │ • counters / latency │    │
│           └─────────────────────┘                 │ • JSON structured log│    │
│                                                   └──────────────────────┘    │
└───────────────────────────────────────────────────────────────────────────────┘
                                            │ MUnit + Surefire XML
                                            ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                  AI VALIDATION SERVICE  (FastAPI + LangGraph)                  │
│                                                                                │
│   POST /validate                                                              │
│        │                                                                       │
│        ▼                                                                       │
│   ┌─────────────────────────────────────────────────────────────────────┐     │
│   │                  LangGraph Workflow (deterministic)                  │     │
│   │                                                                     │     │
│   │   START                                                             │     │
│   │     │                                                               │     │
│   │     ▼                                                               │     │
│   │  load_munit  (parse Surefire XML + coverage JSON)                    │     │
│   │     │                                                               │     │
│   │     ▼                                                               │     │
│   │  api_design  ── Groq llama-3.3-70b-versatile ──► RAML review        │     │
│   │     │                                                               │     │
│   │     ▼                                                               │     │
│   │  mule_review ── Groq ──► XML best-practice review                   │     │
│   │     │                                                               │     │
│   │     ▼                                                               │     │
│   │  munit       ── Groq ──► failure RCA + coverage gap analysis        │     │
│   │     │                                                               │     │
│   │     ▼                                                               │     │
│   │  security    ── Groq ──► OAuth/JWT/threat/rate-limit posture        │     │
│   │     │                                                               │     │
│   │     ▼                                                               │     │
│   │  performance ── Groq ──► 100/1000 concurrent latency review         │     │
│   │     │                                                               │     │
│   │     ▼                                                               │     │
│   │  executive_reporting ──► confidence + risk + recommendation         │     │
│   │     │                                                               │     │
│   │     ▼                                                               │     │
│   │   END  →  ExecutiveDashboard JSON                                   │     │
│   └─────────────────────────────────────────────────────────────────────┘     │
└───────────────────────────────────────────────────────────────────────────────┘
                                            │  dashboard.json
                                            ▼
                          ┌────────────────────────────────┐
                          │ GitHub Actions: ai-validation  │
                          │ stage. BLOCKED ⇒ pipeline fail │
                          └────────────────────────────────┘
```

## Components

| Layer                         | Tech                                     |
|-------------------------------|------------------------------------------|
| Experience API                | Mule 4.9, APIKit, DataWeave 2.x, Java 17 |
| Security                      | OAuth2 (RAML scheme), JWT (HMAC-SHA256), Client-ID enforcement, JSON threat protection, in-memory token-bucket rate limiter |
| Observability                 | log4j2 JsonTemplateLayout, correlation IDs, custom counters via ObjectStore |
| Tests                         | MUnit 3.3 — happy / negative / business / security / performance suites |
| AI Service                    | FastAPI, LangGraph, Groq llama-3.3-70b-versatile |
| Container                     | Multi-stage Python 3.11 slim, non-root user |
| Orchestration                 | Kubernetes Deployment + HPA + Ingress |
| CI/CD                         | GitHub Actions: Build → Unit → MUnit → AI Validation → Deploy DEV/QA/PROD |
