# 🚀 Run AIOps Platform Locally (No Docker)

This guide shows how to run the entire platform natively on Windows without Docker.

---

## 📋 Prerequisites

### Windows Requirements:
- ✅ Python 3.11+ ([Download](https://www.python.org/downloads/))
- ✅ Node.js 18+ ([Download](https://nodejs.org/))
- ✅ Git
- ✅ PostgreSQL 14+ ([Download](https://www.postgresql.org/download/windows/)) - OR use local SQLite
- ✅ Redis ([Windows Port](https://github.com/microsoftarchive/redis/releases)) - OPTIONAL

### Check Prerequisites:
```powershell
python --version    # Should be 3.11+
node --version      # Should be 18+
npm --version       # Should be 9+
git --version
```

---

## ⚙️ Option A: Quick Setup (Using SQLite - Easiest)

SQLite requires NO extra setup - just Python and Node.js!

### Step 1: Setup Backend

```powershell
# Navigate to project
cd c:\pp\GitHub\AgenticAI-Usecases\SupportAgent

# Create Python virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# If that fails, try:
. .\venv\Scripts\Activate.ps1

# You should see (venv) in your prompt
```

### Step 2: Install Python Dependencies

```powershell
# Make sure (venv) is active
cd backend
pip install -r requirements.txt

# This will take 2-3 minutes
```

### Step 3: Setup Environment

```powershell
# Go back to project root
cd ..

# Copy environment file
cp .env.example .env

# Edit .env for local development
# Change these lines:
# DATABASE_URL=sqlite:///./aiops.db
# REDIS_URL=  (leave empty for in-memory cache)
# ENVIRONMENT=development
```

### Step 4: Run Backend

```powershell
# In project root with (venv) active
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**You should see:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

✅ Backend is ready at: http://localhost:8000

---

### Step 5: Run Frontend (New PowerShell Window)

```powershell
# In new PowerShell window, navigate to project
cd c:\pp\GitHub\AgenticAI-Usecases\SupportAgent

# Install dependencies (first time only)
cd frontend
npm install

# Start dev server
npm run dev
```

**You should see:**
```
VITE v5.0.0  ready in XXX ms

➜  Local:   http://localhost:5173/
➜  press h to show help
```

✅ Frontend is ready at: http://localhost:5173

---

## ⚙️ Option B: Full Setup (Using PostgreSQL + Redis)

For better performance and closer to production.

### Step 1: Install and Start PostgreSQL

**If not installed:**
```powershell
# Download from: https://www.postgresql.org/download/windows/
# Run installer, remember the password you set for 'postgres' user
```

**Start PostgreSQL:**
```powershell
# PostgreSQL should run as a service automatically
# Verify it's running:
psql -U postgres -c "SELECT version();"

# If not installed as service, find and run:
"C:\Program Files\PostgreSQL\15\bin\pg_ctl" -D "C:\Program Files\PostgreSQL\15\data" start
```

### Step 2: Create Database

```powershell
# Connect to PostgreSQL as admin
psql -U postgres

# In psql prompt, run:
CREATE DATABASE aiops_db;
CREATE USER aiops WITH PASSWORD 'aiops';
ALTER ROLE aiops SET client_encoding TO 'utf8';
ALTER ROLE aiops SET default_transaction_isolation TO 'read committed';
ALTER ROLE aiops SET default_transaction_deferrable TO on;
ALTER ROLE aiops SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE aiops_db TO aiops;
\q

# Verify:
psql -U aiops -d aiops_db -c "SELECT 1;"
```

### Step 3: Install and Start Redis

**Option A: Using Windows Subsystem for Linux (WSL2)**
```powershell
# In WSL terminal:
sudo apt-get install redis-server
redis-server

# Keep this terminal open
```

**Option B: Using Windows Redis Port**
```powershell
# Download from: https://github.com/microsoftarchive/redis/releases
# Extract and run:
redis-server.exe
```

**Option C: Use Memurai (Modern Windows Redis)**
```powershell
# Download: https://www.memurai.com/
# Install and it runs as service automatically
# Verify:
redis-cli ping
# Should respond: PONG
```

### Step 4: Backend Setup (Same as above)

```powershell
cd c:\pp\GitHub\AgenticAI-Usecases\SupportAgent

# Create venv
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
cd backend
pip install -r requirements.txt

# Update .env for PostgreSQL/Redis
# DATABASE_URL=postgresql+asyncpg://aiops:aiops@localhost:5432/aiops_db
# REDIS_URL=redis://localhost:6379/0
```

### Step 5: Initialize Database

```powershell
# Create tables
cd backend
python -c "from app.database import Base, engine; Base.metadata.create_all(bind=engine)"

# Or using async:
python app/scripts/init_db.py
```

### Step 6: Run Backend & Frontend

**Backend (PowerShell Window 1):**
```powershell
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend (PowerShell Window 2):**
```powershell
cd frontend
npm run dev
```

---

## 🧪 Test the Platform

Once both backend and frontend are running:

### Test 1: Health Check
```powershell
curl http://localhost:8000/health
```

Should return:
```json
{"status":"healthy","timestamp":"...","environment":"development"}
```

### Test 2: Create Incident
```powershell
$body = @{
    title = "Test Incident"
    description = "Testing local setup"
    severity = "P2_HIGH"
    affected_services = @("api", "database")
    affected_components = @("postgres")
    environment = "production"
    detection_source = "test"
    confidence_score = 0.85
} | ConvertTo-Json

Invoke-WebRequest -Uri "http://localhost:8000/api/v1/incidents" `
  -Method POST `
  -Body $body `
  -ContentType "application/json" | ConvertFrom-Json | ConvertTo-Json
```

### Test 3: Access UI
Open browser to: http://localhost:5173

You should see the dashboard with your test incident!

---

## 📊 Running Multiple Services Locally

### Option 1: Use PowerShell Terminal Tabs

```powershell
# Tab 1 - Backend
cd c:\pp\GitHub\AgenticAI-Usecases\SupportAgent\backend
python -m uvicorn app.main:app --reload

# Tab 2 - Frontend  
cd c:\pp\GitHub\AgenticAI-Usecases\SupportAgent\frontend
npm run dev

# Tab 3 - PostgreSQL (if not running as service)
# Keep running

# Tab 4 - Redis (if not running as service)
redis-server
```

### Option 2: Use Start-Process

```powershell
# Backend
Start-Process powershell -ArgumentList "cd backend; python -m uvicorn app.main:app --reload"

# Frontend
Start-Process powershell -ArgumentList "cd frontend; npm run dev"

# Redis (if needed)
Start-Process redis-server
```

---

## ⚡ Quick Start Script (PowerShell)

Create file `start_local_dev.ps1`:

```powershell
# Activate venv
.\venv\Scripts\Activate.ps1

# Start backend in new window
Write-Host "Starting backend..."
Start-Process powershell -ArgumentList {
    Set-Location backend
    python -m uvicorn app.main:app --reload --port 8000
}

# Start frontend in new window
Write-Host "Starting frontend..."
Start-Process powershell -ArgumentList {
    Set-Location frontend
    npm run dev
}

Write-Host ""
Write-Host "Backend: http://localhost:8000"
Write-Host "Frontend: http://localhost:5173"
Write-Host ""
Write-Host "Press Ctrl+C to stop"
```

Run with:
```powershell
.\start_local_dev.ps1
```

---

## 🔧 Troubleshooting

### Python: "No module named 'uvicorn'"
```powershell
# Make sure venv is activated (should see (venv) in prompt)
.\venv\Scripts\Activate.ps1

# Reinstall dependencies
cd backend
pip install -r requirements.txt
```

### Port 8000/5173 already in use
```powershell
# Find process using port 8000
Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess

# Or use different ports in .env:
# API_PORT=8001
# FRONTEND_PORT=5174
```

### PostgreSQL connection failed
```powershell
# Check if PostgreSQL is running
psql -U postgres -c "SELECT 1;"

# Start PostgreSQL service on Windows:
net start PostgreSQL15  # or version number
```

### Redis connection failed
```powershell
# Check if Redis is running
redis-cli ping

# Start Redis (if using manual setup):
redis-server

# Or start service:
net start Redis
```

### "ModuleNotFoundError" for dependencies
```powershell
# Ensure you're in backend directory
cd backend

# Reinstall all dependencies
pip install -r requirements.txt --force-reinstall
```

---

## 📁 Project Structure (Local)

```
SupportAgent/
├── venv/                    # Python virtual environment
├── backend/
│   ├── app/
│   │   ├── main.py         # FastAPI app
│   │   ├── agents/
│   │   ├── connectors/
│   │   └── ml/
│   ├── requirements.txt
│   └── aiops.db            # SQLite database (if using SQLite)
├── frontend/
│   ├── src/
│   ├── package.json
│   └── node_modules/       # Created after npm install
├── .env                     # Configuration
└── ...
```

---

## 🚀 Summary: Quick Start (SQLite)

```powershell
# 1. Create and activate venv
python -m venv venv
.\venv\Scripts\Activate.ps1

# 2. Install dependencies
cd backend
pip install -r requirements.txt
cd ..

# 3. Setup .env (already has SQLite default)
cp .env.example .env

# 4. Run backend (Terminal 1)
cd backend
python -m uvicorn app.main:app --reload --port 8000

# 5. Run frontend (Terminal 2)
cd frontend
npm install
npm run dev

# 6. Access
# Frontend: http://localhost:5173
# API: http://localhost:8000
# Docs: http://localhost:8000/docs
```

**Time to running: ~5-10 minutes** ⏱️

---

## 📚 Documentation

- API Docs (auto): http://localhost:8000/docs
- SwaggerUI: http://localhost:8000/docs

---

## ✅ Success Criteria

You're successful when:
- ✅ Backend running at http://localhost:8000
- ✅ Frontend running at http://localhost:5173
- ✅ Can access dashboard
- ✅ Can create incident via API
- ✅ Incidents appear in UI
- ✅ No errors in terminal

---

**Happy local development!** 🎉

