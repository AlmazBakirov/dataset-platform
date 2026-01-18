param(
  [string]$BackendUrl = "http://localhost:8000"
)

$ErrorActionPreference = "Stop"

Write-Host "== Dataset Platform UI: verify_env ==" -ForegroundColor Cyan
Write-Host ("Repo: " + (Get-Location).Path)

# Detect python launcher
$pythonCmd = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
  $pythonCmd = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
  $pythonCmd = "py -3"
} else {
  throw "Python not found. Install Python 3.11+ and ensure it is on PATH."
}

# Ensure .venv exists
if (-not (Test-Path ".\.venv")) {
  Write-Host "Creating venv: .venv" -ForegroundColor Yellow
  iex "$pythonCmd -m venv .venv"
}

# Activate venv
$activatePath = ".\.venv\Scripts\Activate.ps1"
if (-not (Test-Path $activatePath)) {
  throw "Activation script not found: $activatePath"
}

. $activatePath

Write-Host ""
Write-Host "== VENV ==" -ForegroundColor Cyan
Write-Host ("VIRTUAL_ENV: " + $env:VIRTUAL_ENV)
Write-Host ("where python: ")
where python
Write-Host ("python executable: " + (& python -c "import sys; print(sys.executable)"))

Write-Host ""
Write-Host "== PACKAGES ==" -ForegroundColor Cyan
& python -c "import sys; print('python:', sys.version)"
try {
  & python -c "import streamlit as st; print('streamlit:', st.__version__)"
} catch {
  Write-Host "streamlit: NOT INSTALLED" -ForegroundColor Red
}
try {
  & python -c "import httpx; print('httpx:', httpx.__version__)"
} catch {
  Write-Host "httpx: NOT INSTALLED" -ForegroundColor Red
}

Write-Host ""
Write-Host "== ENV (effective) ==" -ForegroundColor Cyan
Write-Host ("USE_MOCK=" + ($env:USE_MOCK))
Write-Host ("BACKEND_URL=" + ($env:BACKEND_URL))
Write-Host ("REQUEST_TIMEOUT_S=" + ($env:REQUEST_TIMEOUT_S))
Write-Host ("UPLOAD_MODE=" + ($env:UPLOAD_MODE))

Write-Host ""
Write-Host "== BACKEND PROBE ==" -ForegroundColor Cyan
if ([string]::IsNullOrWhiteSpace($env:BACKEND_URL)) {
  $base = $BackendUrl.TrimEnd("/")
} else {
  $base = $env:BACKEND_URL.TrimEnd("/")
}

$endpoints = @("/health", "/_health", "/api/health", "/docs")
$ok = $false
$last = ""

foreach ($ep in $endpoints) {
  $url = $base + $ep
  try {
    $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3
    Write-Host ("OK: " + $url + " -> " + $resp.StatusCode) -ForegroundColor Green
    $ok = $true
    break
  } catch {
    $last = $_.Exception.Message
  }
}

if (-not $ok) {
  Write-Host ("Backend not confirmed at " + $base + ". Last error: " + $last) -ForegroundColor Yellow
  Write-Host "This is fine if backend isn't running yet." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "== READY ==" -ForegroundColor Cyan
Write-Host "If Streamlit/httpx are missing, run: pip install -r requirements.txt"
