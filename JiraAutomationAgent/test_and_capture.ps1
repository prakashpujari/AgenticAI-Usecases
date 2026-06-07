# Test API and capture screenshot
param(
    [switch]$RestartBackend = $false
)

Write-Host "================================" -ForegroundColor Cyan
Write-Host "LOCAL E2E TEST" -ForegroundColor Cyan
Write-Host "================================`n"

# Kill old backend process if requested
if ($RestartBackend) {
    Write-Host "Killing old backend processes..." -ForegroundColor Yellow
    Get-Process python | Where-Object { $_.CommandLine -match "uvicorn" } | Stop-Process -Force
    Start-Sleep -Seconds 2

    Write-Host "Starting fresh backend..." -ForegroundColor Yellow
    $backendPath = "c:\pp\GitHub\AgenticAI-Usecases\JiraAutomationAgent\backend"
    $envPath = "c:\pp\GitHub\AgenticAI-Usecases\JiraAutomationAgent\.env.local"

    # Set env vars and start uvicorn in background
    $env:PYTHONPATH = $backendPath
    cd $backendPath

    # Load .env.local
    $envContent = Get-Content $envPath
    foreach ($line in $envContent) {
        if ($line -match "^([^=]+)=(.*)$") {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            if ($key -and $value) {
                Set-Item "env:$key" $value
            }
        }
    }

    # Start backend
    python -m uvicorn main:app --host 0.0.0.0 --port 8000 | Out-Null &

    Start-Sleep -Seconds 3
    Write-Host "Backend restarted`n" -ForegroundColor Green
}

# Test backend health
Write-Host "Testing backend health..." -ForegroundColor Cyan
$health = curl.exe -s "http://localhost:8000/health"
Write-Host "Response: $health`n"

# Test API endpoint
Write-Host "Testing API create-ticket endpoint..." -ForegroundColor Cyan
$payload = @{
    raw_input = "Database connection timeout issue in production"
    allowed_projects = @("MC")
    allowed_components = @()
    user_id = "test-user"
    user_role = "engineer"
    create_in_jira = $false
} | ConvertTo-Json

$response = curl.exe -s -X POST "http://localhost:8000/ai/create-ticket" `
    -H "Content-Type: application/json" `
    -d $payload

Write-Host "API Response:`n" -ForegroundColor Cyan
$parsedResponse = $response | ConvertFrom-Json

if ($parsedResponse.ticket_drafts -and $parsedResponse.ticket_drafts.Count -gt 0) {
    Write-Host "✅ SUCCESS! Generated ticket:" -ForegroundColor Green
    Write-Host "  Title: $($parsedResponse.ticket_drafts[0].title)" -ForegroundColor Green
    Write-Host "  Type:  $($parsedResponse.ticket_drafts[0].issue_type)" -ForegroundColor Green
    Write-Host "  Priority: $($parsedResponse.ticket_drafts[0].priority)" -ForegroundColor Green
    Write-Host "`nTest PASSED! Proceeding to UI test...`n" -ForegroundColor Green
} else {
    Write-Host "Response: $response`n" -ForegroundColor Red
    Write-Host "❌ API test failed. Check error above." -ForegroundColor Red
    exit 1
}

# Open browser and give user instructions
Write-Host "Opening browser for UI test..." -ForegroundColor Cyan
Write-Host "`nNavigate to: http://localhost:5174" -ForegroundColor Yellow
Write-Host "`nTest steps:" -ForegroundColor Yellow
Write-Host "1. Fill in: 'Database connection timeout after 30 seconds'" -ForegroundColor Yellow
Write-Host "2. Select project: MC" -ForegroundColor Yellow
Write-Host "3. Click 'Create Ticket'" -ForegroundColor Yellow
Write-Host "4. Wait for response" -ForegroundColor Yellow
Write-Host "5. Verify ticket is displayed" -ForegroundColor Yellow
Write-Host "`nPress Enter once you've tested the UI...`n" -ForegroundColor Cyan

Start-Process "http://localhost:5174"

Read-Host "Press Enter when done with UI testing"

Write-Host "`n================================" -ForegroundColor Green
Write-Host "✅ E2E TEST COMPLETE" -ForegroundColor Green
Write-Host "================================`n"
