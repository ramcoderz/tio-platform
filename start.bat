@echo off
setlocal

echo [1/4] Checking dependencies...
if not exist "node_modules\" (
    echo Installing frontend dependencies...
    cd frontend && call npm install && cd ..
)

if not exist "venv\" (
    echo Setting up virtual environment...
    python -m venv venv
)
call venv\Scripts\activate
pip install -r requirements.txt

echo.
echo [2/4] Building frontend...
cd frontend
call npm run build
cd ..

echo.
echo [3/4] Starting TiO Intelligence Core...
python main.py
pause
