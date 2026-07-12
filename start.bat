@echo off
echo Starting Personal Retirement Assistant...
echo.

start "Backend" cmd /k "cd backend && python app.py"

timeout /t 2 /nobreak >nul

start "Frontend" cmd /k "cd frontend && npm run dev"

timeout /t 3 /nobreak >nul

start http://localhost:3000

echo.
echo Two windows just opened: one for the backend, one for the frontend.
echo Leave both windows open while using the app.
echo Close both windows (or press Ctrl+C in each) to stop the app.
echo This window can be closed.
pause
