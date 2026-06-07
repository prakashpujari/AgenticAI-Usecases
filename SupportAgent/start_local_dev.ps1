# AIOps Platform - Local Development Starter (No Docker)
# Usage: .\start_local_dev.ps1

Write-Host ""
Write-Host "==== AIOps Platform - Local Development Setup ====" -ForegroundColor Cyan
Write-Host ""

# Check Python
Write-Host "Checking Python..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Python not found!" -ForegroundColor Red
    Write-Host "Please install Python 3.11+ from: https://www.python.org/downloads/" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "OK: $pythonVersion" -ForegroundColor Green

# Check Node.js
Write-Host "Checking Node.js..." -ForegroundColor Yellow
$nodeVersion = node --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Node.js not found!" -ForegroundColor Red
    Write-Host "Please install Node.js 18+ from: https://nodejs.org/" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "OK: $nodeVersion" -ForegroundColor Green
Write-Host ""

# Create virtual environment if it doesn't exist
if (-not (Test-Path "venv")) {
    Write-Host "Creating Python virtual environment..." -ForegroundColor Yellow
    python -m venv venv
    Write-Host "OK: Virtual environment created" -ForegroundColor Green
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& ".\venv\Scripts\Activate.ps1"
Write-Host "OK: Virtual environment activated" -ForegroundColor Green
Write-Host ""

# Install Python dependencies
Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
$backendDir = Join-Path (Get-Location) "backend"
if (Test-Path (Join-Path $backendDir "requirements.txt")) {
    pip install -q -r (Join-Path $backendDir "requirements.txt")
    Write-Host "OK: Python dependencies installed" -ForegroundColor Green
} else {
    Write-Host "WARNING: requirements.txt not found" -ForegroundColor Yellow
}
Write-Host ""

# Check for Node dependencies
Write-Host "Installing Node.js dependencies..." -ForegroundColor Yellow
$frontendDir = Join-Path (Get-Location) "frontend"
if (Test-Path (Join-Path $frontendDir "package.json")) {
    Push-Location $frontendDir
    npm install --silent
    Pop-Location
    Write-Host "OK: Node.js dependencies installed" -ForegroundColor Green
} else {
    Write-Host "WARNING: package.json not found" -ForegroundColor Yellow
}
Write-Host ""

# Copy .env if it doesn't exist
if (-not (Test-Path ".env")) {
    Write-Host "Creating .env file..." -ForegroundColor Yellow
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "OK: .env created from .env.example" -ForegroundColor Green
    } else {
        Write-Host "WARNING: .env.example not found" -ForegroundColor Yellow
    }
}
Write-Host ""

# Summary
Write-Host "==== Setup Complete ====" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Open TWO more PowerShell windows" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Terminal 1 (Backend):" -ForegroundColor Yellow
Write-Host "    cd backend" -ForegroundColor Cyan
Write-Host "    python -m uvicorn app.main:app --reload --port 8000" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Terminal 2 (Frontend):" -ForegroundColor Yellow
Write-Host "    cd frontend" -ForegroundColor Cyan
Write-Host "    npm run dev" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Then access:" -ForegroundColor Yellow
Write-Host "    Frontend: http://localhost:5173" -ForegroundColor Cyan
Write-Host "    API:      http://localhost:8000" -ForegroundColor Cyan
Write-Host "    Docs:     http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "NOTE: Keep the venv activated in the windows where you run Python commands" -ForegroundColor Yellow
Write-Host ""
