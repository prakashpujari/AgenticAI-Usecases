# ⚡ Quick Local Setup (No Docker)

## 5-Minute Setup

### Prerequisites
- ✅ Python 3.11+
- ✅ Node.js 18+
- ✅ Git

### Step 1: Prepare (1 minute)

```powershell
cd c:\pp\GitHub\AgenticAI-Usecases\SupportAgent

# Create Python virtual environment
python -m venv venv

# Activate it
.\venv\Scripts\Activate.ps1

# You should see (venv) in the prompt
```

### Step 2: Install Dependencies (2 minutes)

```powershell
# Install Python packages
cd backend
pip install -r requirements.txt
cd ..

# Install Node packages
cd frontend
npm install
cd ..
```

### Step 3: Setup Environment (30 seconds)

```powershell
# Copy default config (uses SQLite - no setup needed!)
cp .env.example .env
```

### Step 4: Run Services (2 minutes)

**Terminal 1 - Backend:**
```powershell
# Make sure (venv) is active
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

Wait for: `Application startup complete`

**Terminal 2 - Frontend:**
```powershell
# In a NEW PowerShell window
cd frontend
npm run dev
```

Wait for: `ready in XXX ms`

---

## 🌐 Access

- **Frontend:** http://localhost:5173
- **API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

---

## 🧪 Test It

Create an incident:
```powershell
# In any PowerShell window
$body = '{"title":"Test","description":"Testing","severity":"P2_HIGH","affected_services":["api"],"affected_components":["test"],"environment":"production","detection_source":"test","confidence_score":0.85}'

Invoke-WebRequest -Uri "http://localhost:8000/api/v1/incidents" `
  -Method POST `
  -Body $body `
  -ContentType "application/json" | ConvertFrom-Json | ConvertTo-Json
```

Go to http://localhost:5173 and see it in the dashboard!

---

## 🆘 Quick Fixes

| Problem | Solution |
|---------|----------|
| `python: command not found` | Install Python from https://www.python.org |
| `ModuleNotFoundError` | Make sure (venv) is active: `.\venv\Scripts\Activate.ps1` |
| `npm: command not found` | Install Node.js from https://nodejs.org |
| Port 8000 in use | Change in .env: `API_PORT=8001` |
| Port 5173 in use | Change in .env: `FRONTEND_PORT=5174` |

---

## 📁 What Happens

- **SQLite Database:** Created at `backend/aiops.db` (auto-created)
- **Frontend Files:** Built in `frontend/dist/`
- **Python Virtual Env:** Isolated in `venv/` folder

**No Docker. No setup complexity. Pure local development.** 🎉

---

## 📖 Full Guide

For PostgreSQL + Redis setup, see: `RUN_LOCAL_NO_DOCKER.md`

---

**Ready? Start with Terminal 1 and Terminal 2 above!** 🚀
