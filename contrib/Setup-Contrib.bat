@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-contrib.ps1" %*
if errorlevel 1 (
    echo.
    echo Setup stopped. Show the message above to Leo or your agent.
)
pause
