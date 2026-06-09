# calculator-api-ai-validation

Production-grade MuleSoft Calculator REST API **plus** an AI-powered test-validation
platform that generates, executes, analyses, and summarises MUnit results using
**Groq llama-3.3-70b-versatile** orchestrated by **LangGraph**.

## Repository layout

```
calculator-api-ai-validation/
├── mule-app/                       # Mule 4.9 experience API (Java 17, APIKit, DataWeave 2.x)
│   ├── pom.xml
│   ├── mule-artifact.json
│   └── src/
│       ├── main/
│       │   ├── mule/               # calculator-api-main, impl, error, security, observability
│       │   └── resources/
│       │       ├── api/calculator-api.raml
│       │       ├── config/         # common.yaml, dev/qa/prod yaml + secure-dev.yaml
│       │       ├── dwl/            # add / subtract / multiply / divide / error / validate
│       │       └── log4j2.xml      # structured JSON logging
│       └── test/munit/             # happy / negative / business / security / performance
├── ai-validation-service/          # FastAPI + LangGraph + Groq
│   ├── app/
│   │   ├── agents/                 # 6 LangGraph agents
│   │   ├── services/               # groq_client, munit_parser, workflow
│   │   ├── models/schemas.py
│   │   ├── utils/logging_config.py
│   │   └── main.py                 # FastAPI app
│   ├── sample_reports/             # Sample Surefire XML + coverage JSON
│   ├── tests/                      # pytest
│   ├── Dockerfile
│   └── requirements.txt
├── k8s/                            # namespace, deployment, service, HPA, ingress, PVC
├── .github/workflows/ci-cd.yaml    # 8-stage CI/CD pipeline
└── docs/
    ├── architecture.md             # ASCII architecture diagram
    └── executive-dashboard.sample.json
```

## 1. MuleSoft Calculator API

| Endpoint                  | Method | Behaviour                                                    |
|---------------------------|--------|--------------------------------------------------------------|
| `/calculator/v1/add`      | POST   | `result = num1 + num2`                                       |
| `/calculator/v1/subtract` | POST   | `result = num1 - num2`                                       |
| `/calculator/v1/multiply` | POST   | `result = num1 * num2`                                       |
| `/calculator/v1/divide`   | POST   | `result = num1 / num2` (422 with `DIVIDE_BY_ZERO` if num2=0) |

Sample request / response:

```bash
curl -X POST https://api.example.com/calculator/v1/add \
  -H "Authorization: Bearer <JWT>" \
  -H "client_id: <ID>" -H "client_secret: <SECRET>" \
  -H "Content-Type: application/json" \
  -d '{"num1": 10, "num2": 20}'
# 200 OK
# {"result":30}
```

### Error contract (all error responses)

```json
{
  "success": false,
  "errorCode": "DIVIDE_BY_ZERO",
  "message":   "Cannot divide by zero",
  "correlationId": "12345"
}
```

| HTTP | `errorCode`                  |
|------|------------------------------|
| 400  | `BAD_REQUEST`, `JSON_THREAT_DETECTED` |
| 401  | `UNAUTHORIZED`               |
| 404  | `NOT_FOUND`                  |
| 405  | `METHOD_NOT_ALLOWED`         |
| 422  | `VALIDATION_ERROR`, `DIVIDE_BY_ZERO` |
| 429  | `RATE_LIMIT_EXCEEDED`        |
| 500  | `INTERNAL_SERVER_ERROR`      |

### Build and run locally

```bash
cd mule-app
mvn -B clean package
mvn mule:run -Denv=dev
```

### Run MUnit suite with coverage

```bash
cd mule-app
mvn test
# coverage report: target/site/munit/coverage/index.html
# surefire xml:    target/surefire-reports/
```

## 2. AI Validation Service

### Run locally

```bash
cd ai-validation-service
python -m venv .venv && source .venv/bin/activate   # (Windows: .venv\Scripts\activate)
pip install -r requirements.txt
cp .env.example .env                                 # set GROQ_API_KEY
uvicorn app.main:app --reload --port 8000
```

### Exercise the pipeline

```bash
curl -X POST http://localhost:8000/validate \
  -H "Content-Type: application/json" \
  -d '{
    "munit_reports_dir": "./sample_reports",
    "raml_path": "../mule-app/src/main/resources/api/calculator-api.raml",
    "mule_xml_dir": "../mule-app/src/main/mule"
  }'
```

Response (truncated):

```json
{
  "dashboard": {
    "application": "calculator-api",
    "runtime": "4.9",
    "coverage": 98,
    "testsExecuted": 50,
    "testsPassed": 49,
    "testsFailed": 1,
    "passRate": 98,
    "securityScore": 100,
    "performanceScore": 96,
    "confidenceScore": 97,
    "riskScore": 4,
    "productionReadiness": 95,
    "recommendation": "APPROVED"
  },
  "executive_summary": "...",
  "agent_reports": [ ... ]
}
```

### Endpoints

| Method | Path             | Purpose                                                |
|--------|------------------|--------------------------------------------------------|
| GET    | `/health`        | Liveness + env                                          |
| GET    | `/ready`         | Readiness probe                                         |
| POST   | `/validate`      | Run full LangGraph pipeline                             |
| POST   | `/dashboard`     | Shortcut returning only the executive dashboard         |
| POST   | `/munit/parse`   | Parse MUnit XML + coverage JSON, no LLM                 |

### Offline / no-API-key mode

If `GROQ_API_KEY` is missing or unreachable, `GroqClient` returns deterministic
placeholders. The pipeline still completes and emits a valid `ExecutiveDashboard`
so CI never wedges on a transient LLM outage.

## 3. LangGraph workflow

```
START → load_munit → api_design → mule_review → munit → security → performance → executive_reporting → END
```

| Agent                  | Responsibility                                                |
|------------------------|---------------------------------------------------------------|
| `api_design`           | RAML + API-led / C4E standards review                          |
| `mule_review`          | Mule XML best practices, separation of concerns                |
| `munit`                | Failure RCA, coverage gaps, missing test suggestions           |
| `security`             | OAuth, JWT, client-id, threat protection, security MUnit       |
| `performance`          | 100 / 1000 concurrent latency, tail-latency analysis           |
| `executive_reporting`  | Synthesises scores → confidence, risk, recommendation          |

## 4. Container + Kubernetes

```bash
docker build -t ai-validation-service:1.0.0 ai-validation-service/
docker run --rm -p 8000:8000 -e GROQ_API_KEY=... ai-validation-service:1.0.0

kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/ai-validation-service.yaml
kubectl apply -f k8s/calculator-api.yaml
```

## 5. CI/CD stages (`.github/workflows/ci-cd.yaml`)

1. **build** — Mule app `mvn package` + AI service deps
2. **unit-test** — `pytest --cov=app`
3. **munit-test** — `mvn test` (coverage gate ≥95%)
4. **ai-validation** — LangGraph pipeline emits `dashboard.json`; fails build if `recommendation == BLOCKED`
5. **docker** — build + push image to GHCR
6. **deploy-dev** → **deploy-qa** → **deploy-prod** (each gated by GitHub Environments approval)

## 6. Security model

| Control                  | Where                              | Notes                                        |
|--------------------------|------------------------------------|----------------------------------------------|
| OAuth2 client credentials | RAML securityScheme                | Token issued by `auth.example.com`           |
| JWT validation            | `security.xml` `jwt-validation`    | HMAC-SHA256, issuer + audience + exp checks  |
| Client ID enforcement     | `security.xml`                     | Validates `client_id` / `client_secret` headers |
| JSON threat protection    | `security.xml` `json-threat-protection` | Body size, depth, key-count guards |
| Rate limiting             | `security.xml` `rate-limit-check`  | Token bucket per client_id per minute        |
| Secure properties         | Mule secure-properties module      | AES-CBC with random IVs, runtime key         |

## 7. Observability

- Correlation IDs (header `X-Correlation-ID`, propagated to every log line and error payload)
- Structured JSON logs via `log4j2.xml` (`JsonTemplateLayout`) for ELK/Splunk/Datadog
- Custom counters: `counter.request`, `counter.success`, `counter.failure`, `latency.total`, `latency.count` (ObjectStore-backed)

## 8. Standards followed

- MuleSoft C4E layout (main / impl / error / security / observability XML split)
- API-led connectivity (Experience API exposed; RAML-first)
- Production-grade security (defence in depth)
- 95%+ MUnit coverage target
- Twelve-factor configuration (env-specific YAML + secure properties)
