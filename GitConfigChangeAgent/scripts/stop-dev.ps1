<#
Stops backend and frontend processes started by `start-dev.ps1`.
Reads `dev-pids.json` at repo root and stops processes by PID.
#>

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$pidsPath = Join-Path $root "dev-pids.json"

if (-not (Test-Path $pidsPath)) {
    Write-Warning "No dev-pids.json found at $pidsPath. Nothing to stop."
    exit 0
}

try {
    $p = Get-Content $pidsPath | ConvertFrom-Json
} catch {
    Write-Warning "Failed to read $pidsPath"
    Write-Warning $_
    exit 1
}

if ($p.backend) {
    Write-Output "Stopping backend PID $($p.backend)"
    try { Stop-Process -Id $p.backend -Force -ErrorAction SilentlyContinue } catch {}
}

if ($p.frontend) {
    Write-Output "Stopping frontend PID $($p.frontend)"
    try { Stop-Process -Id $p.frontend -Force -ErrorAction SilentlyContinue } catch {}
}

Remove-Item $pidsPath -Force -ErrorAction SilentlyContinue
Write-Output "Stopped processes and removed $pidsPath"
