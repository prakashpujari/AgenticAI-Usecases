# Render Backend Deployment Guide

## 🚀 Quick Deployment to Render

Since Render doesn't have automated CLI deployment for all features, follow these manual steps:

### Step 1: Connect GitHub to Render

1. Go to: https://dashboard.render.com
2. Click **+ New** → **Web Service**
3. Select **GitHub** and authorize
4. Find and select: `mailtopprakash05/AgenticAI-Usecases`
5. Click **Connect**

### Step 2: Configure Service

**Name**: `jira-automation-backend`

**Runtime**: `Python`

**Root Directory**: `.` (current)

**Build Command**:
```bash
pip install -r backend/requirements.txt && python -m spacy download en_core_web_lg
```

**Start Command**:
```bash
cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT
```

**Branch**: `main`

### Step 3: Add Environment Variables

Click **+ Add Environment Variable** for each:

```
OPENAI_API_KEY=REDACTED_OPENAI_API_KEY

OPENAI_MODEL=gpt-4o

OPENAI_EMBEDDING_MODEL=text-embedding-3-small

PINECONE_API_KEY=pcsk_6Vtb2n_Hz4fzzdc9DSFvaKdGBrEwERN2f4Z1PAmmKMVVRfFcpsus7qdfpo8x9du9TcZmvm

PINECONE_INDEX_NAME=mortgageindex

PINECONE_ENVIRONMENT=us-east-1

PINECONE_HOST=https://mortgageindex-96hwyzx.svc.aped-4627-b74a.pinecone.io

REDIS_URL=redis://localhost:6379

JIRA_BASE_URL=https://mailtopprakash01.atlassian.net

JIRA_EMAIL=mailtopprakash01@gmail.com

JIRA_API_TOKEN=ATATT3xFfGF0V_Z951h9V31ZVqf-vWtzTf2YrWFJnMbkHWFRo8EXimkTuBw8z-qU_PfwWUuJD0E9oChm3xzSTrF8fwpfO2Vf7-lKKV1vgCm6uVwdLNWGKqhl5RrypXTeaMQXfB2lKaPBTvIB7tn9GL3ptJN0DxhK6HDcQnLNlzOi8fJcZ1TUhVE=CF80A708

JIRA_DEFAULT_PROJECT=MC

LANGCHAIN_TRACING_V2=true

LANGCHAIN_ENDPOINT=https://api.smith.langchain.com

LANGCHAIN_API_KEY=REDACTED_LANGSMITH_API_KEY

LANGCHAIN_PROJECT=jira-automation-agent

ALLOWED_PROJECTS=MC,PROJ,INFRA,PLATFORM

MAX_REVIEW_ITERATIONS=2

DEDUPE_THRESHOLD=0.85
```

### Step 4: Add Redis Service (Optional but Recommended)

1. In the same Render dashboard
2. Click **+ New** → **Redis**
3. Give it a name: `jira-automation-redis`
4. Copy the **Internal URL** from Redis service
5. Update backend's `REDIS_URL` with the internal URL

### Step 5: Deploy

Click **Create Web Service** and wait for deployment to complete (~3-5 minutes).

Once ready, you'll see:
```
✅ Service live at: https://jira-automation-backend.onrender.com
```

---

## 📊 Expected Deployment Time

- Build: 2-3 minutes (spacy model download takes time)
- Deploy: 1-2 minutes
- **Total: ~5 minutes**

---

## ✅ Post-Deployment Verification

Once deployed, test the backend:

```bash
# Health check
curl https://jira-automation-backend.onrender.com/health

# Get recent tickets
curl https://jira-automation-backend.onrender.com/ai/recent-tickets?projects=MC

# Check API docs
https://jira-automation-backend.onrender.com/docs
```

---

## 🔗 Update Frontend with Backend URL

Once backend is deployed, update frontend's environment variable:

1. Go to: https://vercel.com/dashboard
2. Select `jira-automation-frontend`
3. Settings → Environment Variables
4. Add/Update:
   ```
   VITE_API_URL=https://jira-automation-backend.onrender.com
   ```
5. Redeploy frontend (Vercel will auto-redeploy)

---

## 🆘 Troubleshooting

### Build Fails: "spacy download timeout"
- Render has limited download bandwidth for large files
- Solution: Increase build timeout in Render settings to 30 minutes

### Service Won't Start
- Check logs in Render dashboard
- Verify Python version matches (3.11+)
- Ensure all dependencies in requirements.txt are correct

### Redis Connection Failed
- If using Render Redis, use the **Internal URL** not External
- Format: `redis://internal-redis-url:6379`

### CORS Errors in Frontend
- Add Vercel URL to CORS whitelist in backend
- Update `CORS_ORIGINS` env var if needed

