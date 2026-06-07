# AIOps Platform - Screenshot Capture Script (PowerShell)
# Usage: .\capture_screenshots.ps1

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   AIOps Platform - Automated Screenshot Capture               ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Check Node.js
Write-Host "🔍 Checking Node.js..." -ForegroundColor Yellow
$nodeVersion = node --version 2>$null
if (-not $nodeVersion) {
    Write-Host "❌ Node.js not found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install Node.js from: https://nodejs.org" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "✅ Node.js found: $nodeVersion" -ForegroundColor Green
Write-Host ""

# Check backend
Write-Host "🔍 Checking if backend is running..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -ErrorAction SilentlyContinue
    if ($response.StatusCode -eq 200) {
        Write-Host "✅ Backend API is running" -ForegroundColor Green
    } else {
        throw "Not healthy"
    }
} catch {
    Write-Host "❌ Backend API is not running!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please start the platform first:" -ForegroundColor Yellow
    Write-Host "  1. Open PowerShell" -ForegroundColor Yellow
    Write-Host "  2. Navigate to project directory" -ForegroundColor Yellow
    Write-Host "  3. Run: ./start_local.sh" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Then run this script again." -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host ""

# Install Puppeteer
Write-Host "📦 Installing Puppeteer dependencies..." -ForegroundColor Yellow
npm install puppeteer --silent
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to install Puppeteer" -ForegroundColor Red
    Write-Host ""
    Write-Host "Try running manually:" -ForegroundColor Yellow
    Write-Host "  npm install puppeteer" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "✅ Puppeteer installed" -ForegroundColor Green
Write-Host ""

# Run capture
Write-Host "🚀 Starting screenshot capture..." -ForegroundColor Cyan
Write-Host ""
node capture-screenshots.js

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "❌ Screenshot capture failed!" -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "✅ Screenshot capture complete!" -ForegroundColor Green
Write-Host ""
Write-Host "📁 Screenshots saved to: docs\screenshots\" -ForegroundColor Cyan
Write-Host ""
Write-Host "Verification:" -ForegroundColor Yellow
$count = (Get-ChildItem "docs\screenshots\*.png" -ErrorAction SilentlyContinue).Count
Write-Host "   Total files: $count" -ForegroundColor Cyan
Write-Host ""
Write-Host "View screenshots:" -ForegroundColor Yellow
Write-Host "   start docs\screenshots" -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to exit"
