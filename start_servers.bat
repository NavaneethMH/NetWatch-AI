@echo off
setlocal
cls

echo ========================================================
echo           NetWatch AI - Launching Servers
echo ========================================================
echo.

cd /d "%~dp0"

:: Clean up stale PID file if present
if exist "backend\netwatch.pid" (
    del /f /q "backend\netwatch.pid" >nul 2>&1
)

:: 1. Launch Backend Server in new window
echo [1/2] Starting Backend Server (FastAPI on http://127.0.0.1:8000)...
start "NetWatch AI - Backend" "%~dp0run_backend.bat"

:: Wait 3 seconds
ping -n 4 127.0.0.1 >nul

:: 2. Launch Frontend Dev Server in new window
echo [2/2] Starting Frontend Dev Server (Vite on http://localhost:5173)...
start "NetWatch AI - Frontend" "%~dp0run_frontend.bat"

:: Wait 3 seconds
ping -n 4 127.0.0.1 >nul

:: 3. Open browser
echo.
echo [3/3] Opening Dashboard in browser (http://localhost:5173)...
start http://localhost:5173

echo.
echo ========================================================
echo   NetWatch AI servers have been launched!
echo     - Backend:  http://127.0.0.1:8000
echo     - Frontend: http://localhost:5173
echo.
echo   Keep both server windows open while using NetWatch AI.
echo ========================================================
echo.
ping -n 6 127.0.0.1 >nul
exit /b 0
