@echo off
echo ============================================
echo  Personal Retirement Assistant - Setup
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python was not found on this computer.
    echo Install it from https://www.python.org/downloads/ first,
    echo then run this script again.
    pause
    exit /b 1
)

where node >nul 2>nul
if errorlevel 1 (
    echo ERROR: Node.js was not found on this computer.
    echo Install it from https://nodejs.org/ first,
    echo then run this script again.
    pause
    exit /b 1
)

echo Installing backend dependencies...
cd backend
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Backend dependency install failed. See the error above.
    pause
    exit /b 1
)
cd ..

echo.
echo Installing frontend dependencies...
cd frontend
call npm install
if errorlevel 1 (
    echo ERROR: Frontend dependency install failed. See the error above.
    pause
    exit /b 1
)
cd ..

echo.
echo ============================================
echo  Setup complete! Run start.bat to launch the app.
echo ============================================
pause
