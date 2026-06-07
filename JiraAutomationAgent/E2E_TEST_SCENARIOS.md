# End-to-End Test Scenarios

## Pre-Deployment Testing (Local)

### Scenario 1: Basic API Connectivity
**Objective**: Verify backend starts and responds to requests

```bash
# 1. Start backend
cd backend
python -m uvicorn app.main:app --reload

# 2. Test health check (add if missing)
curl http://localhost:8000/health
# Expected: 200 OK, {"status": "ok"}

# 3. Test API availability
curl http://localhost:8000/docs
# Expected: 200 OK, Swagger UI loads
```

---

### Scenario 2: Frontend Build & Development
**Objective**: Verify frontend builds and connects to backend

```bash
# 1. Build frontend
cd frontend
npm run build
# Expected: dist/ folder created, no build errors

# 2. Type checking
npm run type-check
# Expected: No TypeScript errors

# 3. Run dev server
npm run dev
# Expected: http://localhost:5173 loads without errors
```

---

### Scenario 3: Jira Authentication
**Objective**: Verify Jira credentials are correct

```bash
# Test via FastAPI:
curl -X POST http://localhost:8000/api/jira/validate \
  -H "Content-Type: application/json" \
  -d '{
    "jira_url": "https://your-org.atlassian.net",
    "jira_email": "your-email@example.com",
    "jira_token": "your-api-token"
  }'

# Expected: 200 OK, {"authenticated": true, "projects": [...]}
```

---

### Scenario 4: Pinecone Vector Search
**Objective**: Verify vector embeddings and search work

```bash
# 1. Check vector index
curl http://localhost:8000/api/pinecone/status

# 2. Test semantic search (after seeding data)
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Database connection timeout",
    "top_k": 5
  }'

# Expected: 200 OK, [{"id": "...", "score": 0.95, "metadata": {...}}]
```

---

### Scenario 5: Full Workflow - Create & Analyze Issue
**Objective**: End-to-end issue creation, analysis, and review

#### Step 1: Create Issue in Jira
```
Project: PROJ (or your test project)
Type: Task
Title: "Test issue for automation agent"
Description: "This is a test to verify the automation workflow"
```

#### Step 2: Trigger Analysis (via API)
```bash
curl -X POST http://localhost:8000/api/issues/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "issue_key": "PROJ-123",
    "project_key": "PROJ"
  }'
```

#### Step 3: Verify Results
- ✅ Analysis completes without errors
- ✅ Response includes AI insights & recommendations
- ✅ Updated issue in Jira with:
  - Comment with analysis summary
  - Labels added (if applicable)
  - Assignee suggested

#### Step 4: Check Frontend UI
1. Navigate to frontend at `http://localhost:5173`
2. Verify issue appears in dashboard
3. Click to view analysis details
4. Confirm all data displays correctly

---

## Post-Deployment Testing (Production)

### Scenario 6: Production Frontend Load
**Objective**: Verify Vercel deployment works

```bash
# 1. Visit Vercel URL
https://jira-automation.vercel.app/

# 2. Verify:
# - Page loads without errors
# - Console has no 404s or CORS errors
# - Can see dashboard/interface
# - API calls go to correct backend URL
```

---

### Scenario 7: Production Backend Health
**Objective**: Verify Render deployment is operational

```bash
# 1. Check health endpoint
curl https://jira-automation-backend.onrender.com/health

# 2. Test API with sample request
curl https://jira-automation-backend.onrender.com/docs

# 3. Check environment variables are loaded
curl https://jira-automation-backend.onrender.com/api/config/status
```

---

### Scenario 8: Production Jira Integration
**Objective**: Test full workflow in production

1. Create test issue in Jira
2. Call analysis endpoint on production backend
3. Wait for processing
4. Verify Jira issue updated with analysis results
5. Check frontend dashboard shows the analysis

---

### Scenario 9: Error Handling & Recovery
**Objective**: Verify graceful failure handling

#### Test 1: Invalid Jira Credentials
```bash
curl -X POST https://backend.onrender.com/api/jira/validate \
  -d '{"jira_url": "https://invalid.atlassian.net", ...}'
# Expected: 401 Unauthorized with helpful error message
```

#### Test 2: Pinecone Service Down
- Temporarily disable Pinecone in config
- Attempt analysis
- Expected: Graceful error, fallback behavior, user-friendly message

#### Test 3: Rate Limiting
- Send 100 requests rapidly
- Expected: 429 Too Many Requests, rate limit headers

---

## Testing Checklist

### Before Deploying
- [ ] Backend starts without errors
- [ ] Frontend builds successfully
- [ ] No TypeScript errors
- [ ] Jira authentication works
- [ ] Pinecone connectivity verified
- [ ] Redis connection works
- [ ] Full workflow (create → analyze) succeeds
- [ ] No console errors in frontend
- [ ] All env vars configured

### After Deploying to Vercel & Render
- [ ] Frontend loads from Vercel URL
- [ ] Backend responds to requests
- [ ] CORS issues resolved
- [ ] Full production workflow succeeds
- [ ] Error handling works gracefully
- [ ] Performance acceptable (< 3s response time)
- [ ] Can view analysis in UI

### Monitoring (Ongoing)
- [ ] Check Render logs daily for errors
- [ ] Monitor Vercel Build Logs
- [ ] Watch LangSmith for LLM failures
- [ ] Track Pinecone vector search latency
- [ ] Monitor Redis memory usage

