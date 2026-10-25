@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0play.ps1" %*
if errorlevel 1 (
    echo.
    echo Game exited with an error. Check logs\play.log for details.
    pause
)
