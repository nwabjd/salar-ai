@echo off
echo Starting SALAR Cloudflare Tunnel...
echo Backend: http://localhost:8000
echo Public URL: https://api.salaar.cloud
echo.
"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel run salar
