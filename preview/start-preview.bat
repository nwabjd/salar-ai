@echo off
setlocal
cd /d "%~dp0"

if not exist node_modules (
  echo Installing preview dependencies...
  call npm install
  if errorlevel 1 goto :error
)

echo Starting SALAR preview at http://127.0.0.1:4174
call npm run dev
if errorlevel 1 goto :error
goto :eof

:error
echo.
echo The preview could not be started. Review the error above.
pause
exit /b 1
