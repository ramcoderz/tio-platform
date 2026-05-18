@echo off
setlocal

echo ========================================================
echo [SYSTEM] Starting TiO Platform Environment Setup
echo ========================================================

:: Change to script's directory
cd /d %~dp0

:: Activate Python virtual environment
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
    echo [SYSTEM] Python virtual environment activated
) else (
    echo [ERROR] Virtual environment not found. Please run set up first.
    pause
    exit /b 1
)

:: Execute the elegant Python launcher script
python launcher.py
