JiraAutomationAgent/
├── .env                          # API keys and config (never commit)
├── .vscode/
│   └── tasks.json                # Auto-start both servers on folder open
├── start.ps1                     # One-command start (outside VS Code)
│
├── backend/
│   ├── main.py                   # FastAPI app, CORS, endpoints
│   ├── config.py                 # Pydantic Settings (reads .env)
│   ├── requirements.txt
│   │
│   ├── agents/                   # All LLM agents
│   │   ├── base_agent.py         # Shared OpenAI + Redis cache logic
│   │   ├── generator_agent.py
│   │   ├── reviewer_agent.py
│   │   ├── refiner_agent.py
│   │   ├── explainer_agent.py
│   │   ├── jira_writer_agent.py
│   │   └── pinecone_memory_agent.py
│   │
│   ├── graph/
│   │   ├── state.py              # LangGraph TypedDict state definition
│   │   └── workflow.py           # 10-node StateGraph
│   │
│   ├── governance/
│   │   ├── guardrails.py         # Field validation, enum + key format checks
│   │   ├── pii_redaction.py      # Presidio + regex PII masking
│   │   └── rbac.py               # Project-key + role enforcement
│   │
│   ├── rag/
│   │   ├── retriever.py          # Pinecone retrieval + Redis cache
│   │   └── reranker.py           # LLM-based result reranking
│   │
│   ├── services/
│   │   ├── jira_service.py       # Jira Cloud REST v3 client (ADF)
│   │   ├── pinecone_service.py   # Pinecone index client
│   │   ├── redis_service.py      # Async Redis, 4 cache namespaces
│   │   └── embedding_service.py  # OpenAI embedding wrapper
│   │
│   ├── schemas/
│   │   ├── api_schema.py         # FastAPI request/response models
│   │   └── ticket_schema.py      # TicketDraft Pydantic model
│   │
│   ├── observability/
│   │   └── tracer.py             # LangSmith @traceable decorators
│   │
│   └── evaluation/
│       ├── llm_evaluation.py     # DeepEval LLM quality metrics
│       └── rag_evaluation.py     # Ragas RAG evaluation metrics
│
└── frontend/
    ├── vite.config.ts            # Vite dev server + /ai and /health proxy
    ├── tailwind.config.js
    ├── package.json
    └── src/
        ├── App.tsx               # Router + QueryClient setup
        ├── index.tsx             # React entry point
        ├── api/
        │   └── client.ts         # Axios instance, error normalisation
        ├── components/
        │   ├── TicketForm.tsx              # Main creation form
        │   ├── AIReviewPanel.tsx           # Review verdict display
        │   ├── ExplainerPanel.tsx          # PO coaching output
        │   ├── DedupeMatchesPanel.tsx      # Duplicate warnings
        │   └── AcceptanceCriteriaEditor.tsx
        ├── pages/
        │   ├── CreateTicketPage.tsx
        │   └── ReviewTicketPage.tsx
        └── types/
            └── index.ts          # TypeScript interfaces (mirrors Pydantic models)
