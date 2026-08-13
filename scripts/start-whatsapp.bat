@echo off
echo Starting SALAR WhatsApp Bridge...
cd /d "%~dp0..\backend\whatsapp"
:loop
node bridge.js
echo Bridge crashed, restarting in 5 seconds...
timeout /t 5 /nobreak >nul
goto loop
