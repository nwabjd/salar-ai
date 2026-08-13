@echo off
REM SALAR Backend - Auto-restart wrapper
REM Keeps uvicorn alive. If it crashes, waits 10s and restarts.
REM Also starts WhatsApp bridge.

REM Start WhatsApp bridge in background
echo [%date% %time%] Starting WhatsApp bridge...
cd /d "%~dp0..\backend\whatsapp"
start /B node bridge.js
cd /d "%~dp0..\backend"

:restart
echo [%date% %time%] Starting SALAR backend...
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
echo [%date% %time%] Backend exited. Restarting in 10 seconds...
timeout /t 10 /nobreak >nul
goto restart
