# Architecture Overview

## 1. System Components

### 1.1 Frontend
- React + TypeScript application.
- Component library: MUI.
- Server state: React Query.
- UI state: Zustand.
- Key pages: Config Change Request, Run Summary Dashboard, Run Detail, Governance/Audit.
- Diff viewer: Monaco Editor or CodeMirror in read-only mode.

### 1.2 Backend
- FastAPI async service.
- Modular service layers:
  - GitLab Service: project discovery, search, branch and commit operations.
  - LLM Service: Groq client, prompt templates, safety rules.
  - Vector Service: Pinecone embeddings, semantic search, impact analysis.
  - Persistence Service: Postgres with SQLAlchemy / asyncpg.
  - Orchestration Service: LangGraph workflow definition, node dispatch, run state.

### 1.3 Data Stores
- Postgres:
  - Runs, requests, results, diffs, metrics, audit logs, RBAC grants.
- Pinecone:
  - Embeddings for configuration files, YAML snippets, property files, and constant declarations.

### 1.4 Observability
- Structured JSON logging with correlation IDs.
- Metrics via Prometheus/OpenTelemetry.
- Distributed tracing with OpenTelemetry.
- LangSmith for LLM call visibility, prompt/evaluation tracking, and agent trace retention.

## 2. Data Flow

### 2.1 User Interaction
1. User submits a business mandate in the UI.
2. UI sends a create-run request to the FastAPI backend.
3. Backend validates RBAC and creates a `ConfigChangeRun` in Postgres.

### 2.2 Agentic Orchestration
1. IngressAgent normalizes the request and resolves scope.
2. DiscoveryAgent searches GitLab, optionally using Pinecone semantic search.
3. LLMChangeProposalAgent generates safe patches.
4. PatchAndDiffAgent computes diffs, metrics, and stores artifacts.
5. CommitAgent applies changes or prepares merge requests.
6. GovernanceAgent logs identity, checks authorizations, and enforces policies.
7. EvaluationAgent runs risk scoring and missed-reference checks.
8. EgressAgent finalizes the run and returns a summary.

### 2.3 GitLab Integration
- Source of truth: GitLab repository content.
- Read operations use search and file retrieval APIs.
- Write operations create branches, commit patches, and optionally open merge requests.
- Self-hosted GitLab supported by configurable base URL and token.

## 3. Integration Points
- GitLab REST API: `projects`, `repository/files`, `search`, `branches`, `commits`, `merge_requests`.
- Groq APIs: prompt submission, safety enforcement, evaluation.
- Pinecone: vector upsert, query, metadata storage.
- LangSmith: run tracking, trace logging, LLM evaluations.
- Postgres: persistent run state, audit, results, RBAC, user metadata.

## 4. Assumptions
- Authentication is OIDC/JWT-based; the backend receives a validated user identity token.
- GitLab API token and service credentials are injected via environment variables or secret manager.
- The platform can be deployed as stateless FastAPI instances behind a load balancer with worker queues for long-running tasks.
- Pinecone may be optional for initial deployments; the system can degrade to GitLab-only search.

## 5. Deployment Boundaries
- FastAPI application handles public /api surface and orchestrates workflows.
- Background task processor (Celery/Arq/custom worker) handles discovery, patching, commit execution, and evaluation.
- Frontend is a single-page application served separately or via CDN.
- Postgres and Pinecone are external managed services.
- LangSmith and OpenTelemetry exporters are configured with environment-driven endpoints.
