# ═══════════════════════════════════════════════════════════════════════════════
# Environment Variable Setup Script
# ═══════════════════════════════════════════════════════════════════════════════
#
# This script securely loads environment variables from .env.local
# and sets them for the current PowerShell session.
#
# Usage:
#   .\setup-env.ps1              # Load .env.local for current session
#   .\setup-env.ps1 -Permanent  # Load .env.local permanently in PowerShell profile
#
# ═══════════════════════════════════════════════════════════════════════════════

param(
    [switch]$Permanent = $false,
    [string]$EnvFile = ".env.local"
)

$ErrorActionPreference = "Stop"

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

# ── Step 1: Check if .env.local exists ────────────────────────────────────────
Write-Host "`n=== Environment Variable Setup ===" -ForegroundColor Cyan

if (-not (Test-Path $EnvFile)) {
    Write-Error-Custom "$EnvFile not found!"
    Write-Host "`nCreate it from the template:"
    Write-Host "  cp .env.local.template .env.local"
    Write-Host "`nThen edit .env.local and replace placeholders with your actual tokens."
    exit 1
}

Write-Success "$EnvFile found"

# ── Step 2: Load environment variables ─────────────────────────────────────────
Write-Host "`nLoading environment variables from $EnvFile..." -ForegroundColor Cyan

$envContent = Get-Content $EnvFile -Raw
$envVars = @{}
$unsetCount = 0

foreach ($line in $envContent -split "`n") {
    $line = $line.Trim()

    # Skip empty lines and comments
    if ([string]::IsNullOrEmpty($line) -or $line.StartsWith("#")) {
        continue
    }

    # Parse KEY=VALUE
    if ($line -match "^([^=]+)=(.*)$") {
        $key = $matches[1].Trim()
        $value = $matches[2].Trim()

        # Check for unset placeholders
        if ($value.Contains("YOUR_NEW_") -or $value.Contains("_HERE")) {
            Write-Warning-Custom "Placeholder found: $key (set this to your actual value)"
            $unsetCount++
        }

        # Set environment variable in current session
        Set-Item -Path "env:$key" -Value $value
        $envVars[$key] = "***" # Don't display actual values
    }
}

Write-Success "Loaded $(($envVars.Count - $unsetCount)) environment variables"

if ($unsetCount -gt 0) {
    Write-Warning-Custom "$unsetCount placeholders still need to be configured"
    Write-Host "`nEdit .env.local and replace all YOUR_NEW_* placeholders with actual values."
    exit 1
}

# ── Step 3: Verify critical variables are set ──────────────────────────────────
Write-Host "`nVerifying critical environment variables..." -ForegroundColor Cyan

$criticalVars = @(
    "OPENAI_API_KEY",
    "PINECONE_API_KEY",
    "JIRA_API_TOKEN",
    "LANGCHAIN_API_KEY"
)

$missingVars = @()
foreach ($var in $criticalVars) {
    if ([string]::IsNullOrEmpty((Get-Item "env:$var" -ErrorAction SilentlyContinue).Value)) {
        $missingVars += $var
    } else {
        Write-Success "$var is set"
    }
}

if ($missingVars.Count -gt 0) {
    Write-Error-Custom "Missing critical variables: $($missingVars -join ', ')"
    exit 1
}

# ── Step 4: Optional - Make permanent in PowerShell profile ────────────────────
if ($Permanent) {
    Write-Host "`nSetting up permanent environment variables..." -ForegroundColor Cyan

    # Create profile if it doesn't exist
    $profilePath = $PROFILE.CurrentUserAllHosts
    $profileDir = Split-Path $profilePath

    if (-not (Test-Path $profileDir)) {
        New-Item -ItemType Directory -Path $profileDir -Force | Out-Null
        Write-Success "Created PowerShell profile directory: $profileDir"
    }

    # Add setup to profile
    $setupCommand = @"

# ── Jira Automation Agent Environment ──────────────────────────────────────
`$AgentRoot = Split-Path -Parent (Get-Location)
if (Test-Path "`$AgentRoot\.env.local") {
    Write-Host "Loading Jira Automation Agent environment variables..."
    Get-Content "`$AgentRoot\.env.local" | ForEach-Object {
        if (`$_ -match '^([^#=]+)=(.*)$') {
            `$key = `$matches[1].Trim()
            `$value = `$matches[2].Trim()
            Set-Item -Path "env:`$key" -Value `$value -ErrorAction SilentlyContinue
        }
    }
}
"@

    # Check if already added
    if ((Get-Content $profilePath -ErrorAction SilentlyContinue) -notmatch "Jira Automation Agent") {
        Add-Content -Path $profilePath -Value $setupCommand
        Write-Success "Added environment loader to PowerShell profile: $profilePath"
    } else {
        Write-Success "Environment loader already in PowerShell profile"
    }
}

# ── Step 5: Summary ────────────────────────────────────────────────────────────
Write-Host "`n=== Setup Complete ===" -ForegroundColor Green
Write-Host @"

Environment variables loaded for this session.

Next steps:
1. Run the development server:
   cd frontend && npm run dev

2. In another terminal, run the backend:
   cd backend && python -m uvicorn main:app --reload

3. Visit: http://localhost:5173

⚠️  Important:
- These variables are ONLY set for this PowerShell session
- Close the terminal to unload them
- Use -Permanent flag to auto-load on every PowerShell startup

Security Reminder:
- NEVER commit .env.local to git
- NEVER share .env.local via email/Slack
- Rotate tokens every 90 days
- Delete token immediately if exposed

"@
