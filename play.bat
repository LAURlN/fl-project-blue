@echo off
setlocal
cd /d "%~dp0"
goto main
rem Keep the exit below at byte 104 (see note after :main)..
exit /b
:main
rem Fantasy Life PC. Without arguments (desktop shortcut, double-click) this
rem opens the launcher window. With arguments it is the command-line launcher:
rem   play.bat -Direct          play right away, no window
rem   play.bat -Vanilla         play without data mods
rem   play.bat -Save story      open the window with the story save selected
rem The "exit /b" above ":main" must stay at byte offset 104: an older play.bat
rem that an update replaced while it was running resumes reading there.
if "%~1"=="" goto window
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0play.ps1" %*
if errorlevel 1 (
    echo.
    echo Fantasy Life exited with an error. Check the logs folder for details.
    pause
)
exit /b

:window
if exist "%SystemRoot%\System32\vbscript.dll" if exist "%~dp0bin\launcher\FantasyLife.vbs" (
    start "" "%SystemRoot%\System32\wscript.exe" "%~dp0bin\launcher\FantasyLife.vbs"
    exit /b
)
start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0play.ps1" -Window -Hidden
exit /b
