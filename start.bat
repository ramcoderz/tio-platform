@echo off
echo [1/4] Installing backend dependencies...
python -m pip install -r requirements.txt

echo.
echo [2/4] Installing frontend dependencies...
cd frontend
call npm install

echo.
echo [3/4] Building frontend...
call npm run build
cd ..

echo.
echo [4/4] Starting TiO Intelligence Core...
python main.py
pause
