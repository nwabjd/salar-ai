@echo off
REM SALAR Backend Watchdog
REM Checks health every 5 minutes. If backend is down, restarts it.

set BACKEND_URL=http://127.0.0.1:8000/api/health
set LOG_FILE=%~dp0watchdog.log

:loop
REM Check if backend is alive
curl -s -o nul -w "%%{http_code}" %BACKEND_URL% > "%TEMP%\health_check.txt" 2>nul
set /p STATUS=<"%TEMP%\health_check.txt"

if "%STATUS%"=="200" (
    echo [%date% %time%] Backend healthy (HTTP %STATUS%) >> "%LOG_FILE%"
) else (
    echo [%date% %time%] Backend DOWN (HTTP %STATUS%) - restarting... >> "%LOG_FILE%"

    REM Kill any existing uvicorn
    taskkill /F /IM python.exe /FI "WINDOWTITLE eq *uvicorn*" >nul 2>&1

    REM Start backend
    start "SALAR Backend" /min cmd /c "cd /d C:\Users\JD\Documents\SALAR AI\backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
    timeout /t 10 /nobreak >nul
    echo [%date% %time%] Backend restarted >> "%LOG_FILE%"
)

REM Wait 5 minutes
timeout /t 300 /nobreak >nul
goto loop
