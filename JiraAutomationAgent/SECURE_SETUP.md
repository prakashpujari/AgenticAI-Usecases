# Secure Environment Setup Guide

## 🔒 Part 1: Remove Exposed .env from Git History

The `.env` file with exposed credentials is currently in git history. We need to remove it.

### Option A: Remove from Current Branch Only (Recommended for now)
```powershell
# Remove .env from staging
git rm --cached .env

# Verify it's not staged
git status

# Commit the removal
git commit -m "Remove: Exposed .env file with secrets

- Revoked all exposed API keys
- Using .env.local for local development
- All sensitive data now in environment variables only"
```

### Option B: Remove from All Git History (Nuclear Option)
**Only do this if the repo is not yet public/shared.**

```powershell
# Install BFG Repo Cleaner (if not already installed)
choco install bfg-repo-cleaner

# Remove .env from all history
bfg --delete-files .env

# Clean up reflog
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Force push (be careful!)
git push origin --force
```

---

## ✅ Part 2: Set Up Secure Environment Variables

### Step 1: Copy Template to .env.local

```powershell
# From project root
Copy-Item .env.local.template .env.local
```

### Step 2: Edit .env.local with Your New Tokens

Open `.env.local` in your editor and replace:

```
OPENAI_API_KEY=sk-proj-YOUR_NEW_OPENAI_KEY_HERE
                      ↓↓↓ Replace with actual key
OPENAI_API_KEY=sk-proj-abc123xyz789...
```

**Generate new tokens at:**
- OpenAI: https://platform.openai.com/api-keys
- Pinecone: https://console.pinecone.io
- Jira: https://id.atlassian.com/manage-profile/security/api-tokens
- LangSmith: https://smith.langchain.com/settings
- Vercel: https://vercel.com/account/tokens
- Render: https://dashboard.render.com

### Step 3: Load Environment Variables

#### For Current Session Only:
```powershell
.\setup-env.ps1
```

#### For Permanent (Every PowerShell Startup):
```powershell
.\setup-env.ps1 -Permanent
```

This will add the loader to your PowerShell profile automatically.

### Step 4: Verify Variables Are Loaded

```powershell
# Check if variables are set
$env:OPENAI_API_KEY
$env:PINECONE_API_KEY
$env:JIRA_API_TOKEN

# All three should show values (not $null)
```

---

## 🚀 Part 3: Development Workflow

Once environment variables are set:

### Terminal 1: Backend
```powershell
# Load env vars
.\setup-env.ps1

# Start backend
cd backend
python -m uvicorn main:app --reload
# Backend runs on http://localhost:8000
```

### Terminal 2: Frontend
```powershell
# Load env vars (in new PowerShell window)
.\setup-env.ps1

# Start frontend
cd frontend
npm run dev
# Frontend runs on http://localhost:5173
```

### Access the App
Open browser: http://localhost:5173

---

## 🎯 Part 4: Deployment with Environment Variables

### For Vercel (Frontend)

**Option A: Via Vercel CLI**
```powershell
# Load env vars
.\setup-env.ps1

# Deploy (env vars auto-loaded)
cd frontend
npm run build
vercel --prod
```

**Option B: Via Vercel Dashboard**
1. Go to https://vercel.com/dashboard
2. Select your project
3. Settings → Environment Variables
4. Add:
   - `VITE_API_URL` = `https://your-render-backend.onrender.com`

### For Render (Backend)

**Via Render Dashboard**
1. Go to https://dashboard.render.com
2. Select your service
3. Environment → Add Environment Variable
4. Add all from `.env.local`:
   - `OPENAI_API_KEY`
   - `PINECONE_API_KEY`
   - `JIRA_API_TOKEN`
   - `LANGCHAIN_API_KEY`
   - `JIRA_BASE_URL`
   - `JIRA_EMAIL`
   - `REDIS_URL`
   - etc.

---

## 🔐 Security Best Practices

### ✅ DO:
- [ ] Store tokens in `.env.local` (git-ignored)
- [ ] Use environment variables for all secrets
- [ ] Rotate tokens every 90 days
- [ ] Use `-Permanent` flag for persistent env loading
- [ ] Review `.gitignore` before committing
- [ ] Use `git status` to verify `.env` not staged

### ❌ DON'T:
- [ ] Paste tokens in chat/email/Slack
- [ ] Commit `.env` to git
- [ ] Share `.env.local` files
- [ ] Hardcode tokens in code
- [ ] Log sensitive values
- [ ] Store tokens in version control

---

## 🆘 Troubleshooting

### "Cannot find path" when running setup-env.ps1
```powershell
# Make sure you're in the project root
cd c:\pp\GitHub\AgenticAI-Usecases\JiraAutomationAgent

# Allow script execution
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Try again
.\setup-env.ps1
```

### ".env.local not found"
```powershell
# Create it from template
Copy-Item .env.local.template .env.local

# Edit it with your actual values
code .env.local
```

### Environment variables not persisting after close/reopen terminal
```powershell
# Use -Permanent flag to auto-load on every session
.\setup-env.ps1 -Permanent
```

### "Placeholder still needs configuration"
```powershell
# Open .env.local and replace all YOUR_NEW_* with actual values
code .env.local

# Verify no placeholders remain
Select-String "YOUR_NEW_|_HERE" .env.local

# Reload
.\setup-env.ps1
```

---

## 📋 Checklist

- [ ] Revoked ALL exposed tokens
- [ ] Generated NEW tokens for all services
- [ ] Created `.env.local` from template
- [ ] Replaced all placeholders with actual values
- [ ] Ran `.\setup-env.ps1` to load variables
- [ ] Verified `$env:OPENAI_API_KEY` returns value
- [ ] Removed `.env` from git staging (`git rm --cached .env`)
- [ ] Committed the removal
- [ ] Ready for deployment

---

## Next: Deployment

Once all checklist items are complete, you're ready to:
1. Deploy frontend to Vercel
2. Deploy backend to Render
3. Run production E2E tests

See [DEPLOYMENT.md](DEPLOYMENT.md) for full instructions.

