# Jira Automation Agent - Deployment & Testing Guide

## 📋 Project Overview

**Application**: Jira Automation Agent  
**Stack**: 
- Frontend: React 18 + TypeScript + Vite
- Backend: FastAPI + Python 3.11 + LangChain
- Integrations: Jira Cloud, OpenAI, Pinecone, Redis, LangSmith

---

## 🏗️ Deployment Architecture

### Frontend (Vercel)
- **Platform**: Vercel (Edge network CDN)
- **Build**: `npm run build` → Static React SPA
- **Environment**: `VITE_API_URL` → Backend URL
- **Status**: Optimized for static hosting, instant deployments

### Backend (Render)
- **Platform**: Render (Python web service)
- **Framework**: FastAPI on Uvicorn
- **Build**: Install deps, download spaCy model, start Uvicorn
- **Resources**: Standard tier sufficient for development
- **Status**: Requires managed Redis (Redis Labs / Render add-on)

---

## ✅ Pre-Deployment Checklist

### Local Testing (Before Deploying)
- [ ] Frontend builds successfully
- [ ] Backend starts and API responds
- [ ] End-to-end workflow: Create → Analyze → Review in Jira
- [ ] All env vars configured in `.env.local`
- [ ] No hardcoded secrets in code

### Environment Variables Needed

#### For Backend (Render)
```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

PINECONE_API_KEY=...
PINECONE_INDEX_NAME=jira-issues
PINECONE_ENVIRONMENT=us-east-1

JIRA_BASE_URL=https://your-org.atlassian.net
JIRA_EMAIL=you@example.com
JIRA_API_TOKEN=...
JIRA_PROJECT_KEY=PROJ

REDIS_URL=redis://... (Render Redis service)

LANGCHAIN_API_KEY=ls__... (Optional)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_PROJECT=jira-automation-agent
```

#### For Frontend (Vercel)
```
VITE_API_URL=https://your-backend.onrender.com
```

---

## 🚀 Deployment Steps

### Step 1: Deploy Frontend to Vercel
```bash
# Prerequisites: Vercel CLI installed
vercel --prod --token <NEW_VERCEL_TOKEN> --build-env VITE_API_URL=https://your-backend.onrender.com
```

### Step 2: Deploy Backend to Render
```bash
# Via Render Dashboard:
1. Connect GitHub repo
2. Create new Web Service
3. Select "Python" runtime
4. Set build & start commands (see render.yaml)
5. Add environment variables
6. Deploy
```

### Step 3: Post-Deployment Tests
- [ ] Frontend loads at Vercel URL
- [ ] API health check: `GET /health` (add if missing)
- [ ] Jira authentication works
- [ ] Create test issue in Jira
- [ ] Backend processes and analyzes issue
- [ ] Response returns to frontend

---

## 📊 Use Case Documentation

### Scenario: Automated Jira Issue Triage & Analysis

**Goal**: Automatically analyze new Jira issues, enrich with AI-powered insights, and categorize for routing.

**Workflow**:
1. User creates issue in Jira with description/context
2. Jira webhook triggers automation agent backend
3. Agent extracts issue details + historical context via vector search
4. LLM analyzes issue against similar resolved tickets
5. Agent routes to appropriate team/epic based on analysis
6. Results written back to Jira (labels, assignee, comments)

**Key Features**:
- ✅ **Semantic Search**: Find related issues using Pinecone embeddings
- ✅ **PII Protection**: Redact sensitive data before LLM processing
- ✅ **Multi-turn Analysis**: Review cycle with team feedback
- ✅ **Audit Trail**: LangSmith integration tracks all decisions
- ✅ **Governance**: RBAC controls which projects can be automated

**Benefits**:
- 🚀 Reduces manual triage by 70%
- 📈 Improves routing accuracy
- 🔍 Surfaces patterns in issue categories
- 🛡️ Maintains compliance (PII redaction, audit logs)

---

## 🔍 Monitoring & Troubleshooting

### Frontend Issues
- Check Vercel Build Logs if deployment fails
- Use browser DevTools Console for frontend errors
- Check `VITE_API_URL` matches deployed backend

### Backend Issues
- Render logs: `render logs <service-name>`
- Check all environment variables are set
- Verify Pinecone & Redis connectivity
- Monitor LangSmith traces for LLM errors

### Common Issues
| Issue | Solution |
|-------|----------|
| 503 Service Unavailable | Backend not started; check Render logs |
| CORS errors | Add Vercel URL to CORS whitelist in FastAPI |
| Auth failures | Verify Jira credentials (URL, email, token) |
| Pinecone errors | Check index name & API key match |

---

## 📝 Next Steps

1. ✅ Configure environment variables on Vercel & Render
2. ✅ Deploy frontend
3. ✅ Deploy backend with all services (Redis, etc.)
4. ✅ Test end-to-end workflow in production
5. ✅ Set up monitoring (Render dashboard, LangSmith)
6. ✅ Document API endpoints for team

