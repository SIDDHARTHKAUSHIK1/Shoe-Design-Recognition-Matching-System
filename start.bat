@echo off
title Shoe Design Recognition & Matching System
echo =====================================================================
echo       Starting Shoe Design Recognition & Matching System
echo =====================================================================
echo.

:: Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not found in PATH.
    echo Please install Python 3.10+ from https://www.python.org/
    pause
    exit /b 1
)

:: Install/verify requirements
echo [1/3] Checking dependencies...
pip install -r requirements.txt --quiet

:: Auto-ingest catalog if not already created
echo [2/3] Checking shoe catalog index...
if not exist "storage\shoe_index.faiss" (
    echo Initializing and indexing catalog from dataset...
    python -m backend.ingestion
)

:: Launch FastAPI Server
echo [3/3] Launching ShoeMatch Web Studio at http://localhost:8000 ...
echo.
echo Open your browser at: http://localhost:8000
echo Press Ctrl+C in this terminal to stop the server.
echo =====================================================================
echo.

python run_server.py
pause
