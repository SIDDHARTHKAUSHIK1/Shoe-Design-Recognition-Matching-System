# Shoe Design Recognition & Matching System - PowerShell Launcher
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "      Starting Shoe Design Recognition & Matching System" -ForegroundColor Cyan
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
try {
    $pyVersion = python --version 2>&1
    Write-Host "[OK] Found $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python is not installed or not in PATH." -ForegroundColor Red
    exit 1
}

# Auto-ingest catalog if not already created
if (-not (Test-Path "storage\shoe_index.faiss")) {
    Write-Host "[1/2] Initializing shoe catalog index..." -ForegroundColor Yellow
    python -m backend.ingestion
} else {
    Write-Host "[1/2] Shoe catalog index verified." -ForegroundColor Green
}

Write-Host "[2/2] Launching Web Studio at http://localhost:8000 ..." -ForegroundColor Cyan
Write-Host ""
Write-Host "Open your browser at: http://localhost:8000" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop the server." -ForegroundColor Gray
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host ""

python run_server.py
