<#
Starts backend and frontend dev servers and runs the backend health check.
Writes PIDs to `dev-pids.json` at repo root so `stop-dev.ps1` can stop them.
#>

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$venvPy = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPy)) {
    Write-Error "Virtualenv python not found at $venvPy"
    exit 1
}

$backendWd = Join-Path $root "backend"
$backendArgs = "-m uvicorn app.main:app --reload --port 8000"
Write-Output "Starting backend in $backendWd (PID will be recorded)"
$backendProc = Start-Process -FilePath $venvPy -ArgumentList $backendArgs -WorkingDirectory $backendWd -PassThru -WindowStyle Hidden

$frontendWd = Join-Path $root "frontend"
Write-Output "Starting frontend in $frontendWd"
$npmCmd = "npm.cmd"
if (-not (Get-Command $npmCmd -ErrorAction SilentlyContinue)) {
    Write-Error "npm.cmd not found in PATH. Ensure Node/npm are installed and available."
    exit 1
}
$frontendProc = Start-Process -FilePath $npmCmd -ArgumentList "run dev" -WorkingDirectory $frontendWd -PassThru

$pids = @{ backend = $backendProc.Id; frontend = $frontendProc.Id } | ConvertTo-Json
$pidsPath = Join-Path $root "dev-pids.json"
Set-Content -Path $pidsPath -Value $pids -Encoding utf8

Start-Sleep -Seconds 3

$healthScript = Join-Path $backendWd "run_health_check.py"
if (Test-Path $healthScript) {
    Write-Output "Running backend health check..."
    Push-Location $backendWd
    try {
        & $venvPy $healthScript
        Write-Output "Health check completed"
    } catch {
        Write-Warning "Health check failed: $_"
    } finally {
        Pop-Location
    }
} else {
    Write-Warning "Health check script not found at $healthScript"
}

Write-Output "Started backend (PID=$($backendProc.Id)) and frontend (PID=$($frontendProc.Id)). PIDs saved to dev-pids.json"
