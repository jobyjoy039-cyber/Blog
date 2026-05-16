# Claude Blog — Local Runner (Windows PowerShell)
# Usage: .\web\start.ps1 [port]

param([int]$Port = 5000)

$Root = Split-Path $PSScriptRoot -Parent
Write-Host ""
Write-Host "  Claude Blog Local Runner" -ForegroundColor Cyan
Write-Host "  ========================" -ForegroundColor Cyan

# Python check
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "  x python not found. Install Python 3.11+ from python.org" -ForegroundColor Red
    exit 1
}

$pyVer = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Write-Host "  Python $pyVer" -ForegroundColor Green

# Install deps
Write-Host "  Installing dependencies..."
python -m pip install -q -r "$Root\web\requirements.txt"

# .env setup
$envFile = "$Root\.env"
$envExample = "$Root\.env.example"
if (-not (Test-Path $envFile)) {
    Copy-Item $envExample $envFile
    Write-Host ""
    Write-Host "  ! Created .env from .env.example" -ForegroundColor Yellow
    Write-Host "  Add your ANTHROPIC_API_KEY to $envFile" -ForegroundColor Yellow
    Write-Host "  Or configure it at http://localhost:$Port/settings after launch" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  -> http://localhost:$Port" -ForegroundColor Green
Write-Host "  -> Press Ctrl+C to stop"
Write-Host ""

$env:PORT = $Port
python "$Root\web\app.py"
