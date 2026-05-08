# start.ps1 — start both servers in parallel (use outside VS Code)
# Usage: .\start.ps1
# Stop with: Ctrl+C in both terminal tabs, or close the windows.

$root = $PSScriptRoot

# Start backend in a new terminal window
Start-Process powershell -ArgumentList "-NoExit", "-Command",
  "Set-Location '$root'; backend\.venv\Scripts\uvicorn.exe backend.main:app --port 8000 --log-level warning" `
  -WindowStyle Normal

# Start frontend in a new terminal window
Start-Process powershell -ArgumentList "-NoExit", "-Command",
  "Set-Location '$root\frontend'; npm run dev" `
  -WindowStyle Normal

Write-Host "Both servers starting in separate windows."
Write-Host "  Backend  -> http://localhost:8000/health"
Write-Host "  Frontend -> http://localhost:5173"
