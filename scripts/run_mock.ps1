param(
  [string]$BackendUrl = "http://localhost:8000",
  [string]$UploadMode = "mvp",
  [int]$TimeoutS = 20
)

$ErrorActionPreference = "Stop"

# Ensure venv + print env status
& .\scripts\verify_env.ps1 -BackendUrl $BackendUrl

# Set env for this session
$env:USE_MOCK = "1"
$env:BACKEND_URL = $BackendUrl
$env:UPLOAD_MODE = $UploadMode
$env:REQUEST_TIMEOUT_S = "$TimeoutS"

Write-Host ""
Write-Host "== RUN MOCK ==" -ForegroundColor Cyan
Write-Host "USE_MOCK=1"
Write-Host ("BACKEND_URL=" + $env:BACKEND_URL)
Write-Host ("UPLOAD_MODE=" + $env:UPLOAD_MODE)
Write-Host ("REQUEST_TIMEOUT_S=" + $env:REQUEST_TIMEOUT_S)
Write-Host ""

python -m streamlit run app.py
