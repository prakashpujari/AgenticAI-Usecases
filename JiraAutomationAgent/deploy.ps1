# Jira Automation Agent - Deployment Script
# IMPORTANT: This script uses environment variables, NOT hardcoded tokens

param(
    [string]$Target = "all",  # all, vercel, render
    [switch]$Test = $false,
    [switch]$Prod = $false
)

$ErrorActionPreference = "Stop"

function Write-Header {
    param([string]$Message)
    Write-Host "`n=== $Message ===" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-Error-Custom {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

function Write-Warning-Custom {
    param([string]$Message)
    Write-Host "⚠ $Message" -ForegroundColor Yellow
}

# ============================================================================
# SECURITY CHECK
# ============================================================================
Write-Header "Security Check"

if (Test-Path ".env") {
    Write-Warning-Custom "Found .env file. Never commit this to git!"
    $content = Get-Content ".env" -Raw
    if ($content -match "vcp_|rnd_") {
        Write-Error-Custom "DANGER: Tokens found in .env file!"
        Write-Host "⚠️  REVOKE THESE TOKENS IMMEDIATELY at Vercel/Render dashboard"
        exit 1
    }
}

if ($null -eq $env:VERCEL_TOKEN) {
    Write-Warning-Custom "VERCEL_TOKEN not set. Frontend deployment will be skipped unless you provide it."
    Write-Host "Set it with: `$env:VERCEL_TOKEN = 'your-token'"
}

if ($null -eq $env:RENDER_API_KEY) {
    Write-Warning-Custom "RENDER_API_KEY not set. Manual Render dashboard deployment required."
    Write-Host "Set it with: `$env:RENDER_API_KEY = 'your-key'"
}

Write-Success "Security check passed"

# ============================================================================
# PRE-DEPLOYMENT TESTS
# ============================================================================
if ($Test -or $Target -eq "test") {
    Write-Header "Running Pre-Deployment Tests"

    # Test frontend build
    Write-Host "`nTesting frontend build..."
    Push-Location "frontend"
    if (Test-Path "node_modules") {
        npm run type-check
        if ($LASTEXITCODE -ne 0) {
            Write-Error-Custom "TypeScript check failed"
            exit 1
        }
        Write-Success "TypeScript check passed"
    } else {
        Write-Warning-Custom "node_modules not found. Run 'npm install' in frontend/ first."
    }
    Pop-Location

    # Test backend (basic check)
    Write-Host "`nTesting backend configuration..."
    if (Test-Path "backend/.venv") {
        Write-Success "Python virtual environment found"
    } else {
        Write-Warning-Custom "Python venv not found. Backend tests skipped."
    }

    Write-Success "Pre-deployment tests completed"
}

# ============================================================================
# VERCEL DEPLOYMENT
# ============================================================================
if ($Target -eq "vercel" -or $Target -eq "all") {
    Write-Header "Deploying Frontend to Vercel"

    if ($null -eq $env:VERCEL_TOKEN) {
        Write-Error-Custom "VERCEL_TOKEN not set. Cannot deploy to Vercel."
        exit 1
    }

    # Check if Vercel CLI is installed
    if ($null -eq (Get-Command vercel -ErrorAction SilentlyContinue)) {
        Write-Error-Custom "Vercel CLI not installed. Run: npm install -g vercel"
        exit 1
    }

    Write-Host "Building frontend..."
    Push-Location "frontend"
    npm run build
    if ($LASTEXITCODE -ne 0) {
        Write-Error-Custom "Frontend build failed"
        exit 1
    }
    Pop-Location
    Write-Success "Frontend built successfully"

    # Deploy
    Write-Host "Deploying to Vercel..."
    if ($Prod) {
        $env:VERCEL_TOKEN | vercel --prod
        Write-Success "Deployed to production at Vercel"
    } else {
        $env:VERCEL_TOKEN | vercel
        Write-Success "Deployed to preview at Vercel"
    }
}

# ============================================================================
# RENDER DEPLOYMENT (MANUAL)
# ============================================================================
if ($Target -eq "render" -or $Target -eq "all") {
    Write-Header "Preparing Backend for Render Deployment"

    Write-Warning-Custom "Render deployment requires manual steps via dashboard:"
    Write-Host @"

    1. Go to https://dashboard.render.com
    2. Click "+ New" > "Web Service"
    3. Connect your GitHub repository
    4. Fill in:
       - Name: jira-automation-backend
       - Root Directory: . (current)
       - Build Command: pip install -r backend/requirements.txt && python -m spacy download en_core_web_lg
       - Start Command: cd backend && uvicorn app.main:app --host 0.0.0.0 --port `$PORT

    5. Add Environment Variables (from your secrets):
       - OPENAI_API_KEY
       - PINECONE_API_KEY
       - PINECONE_INDEX_NAME (jira-issues)
       - JIRA_BASE_URL
       - JIRA_EMAIL
       - JIRA_API_TOKEN
       - JIRA_PROJECT_KEY
       - REDIS_URL (use Render Redis add-on)
       - LANGCHAIN_API_KEY (optional)
       - LANGCHAIN_PROJECT

    6. Click "Create Web Service"
    7. Monitor build in Render dashboard

"@

    Write-Host "Checking render.yaml configuration..."
    if (Test-Path "render.yaml") {
        Write-Success "render.yaml found and ready"
    }
}

# ============================================================================
# POST-DEPLOYMENT GUIDANCE
# ============================================================================
Write-Header "Post-Deployment Steps"

Write-Host @"
1. Frontend URL (Vercel):
   https://your-app.vercel.app

2. Backend URL (Render):
   https://jira-automation-backend.onrender.com

3. Update Frontend Environment:
   Add to Vercel dashboard > Settings > Environment Variables:
   - VITE_API_URL=https://jira-automation-backend.onrender.com

4. Test End-to-End:
   Follow E2E_TEST_SCENARIOS.md for comprehensive testing

5. Monitor:
   - Vercel: https://vercel.com/dashboard
   - Render: https://dashboard.render.com
   - LangSmith: https://smith.langchain.com

"@

Write-Success "Deployment preparation complete!"
