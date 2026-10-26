@echo off
setlocal
goto main
rem Keep the exit below at byte 104 (LF) / 108 (CRLF); see note after :mai
exit /b
:main
cd /d "%~dp0"
rem Fantasy Life PC. Without arguments (desktop shortcut, double-click) this
rem opens the launcher window. With arguments it is the command-line launcher:
rem   play.bat -Direct          play right away, no window
rem   play.bat -Vanilla         play without data mods
rem   play.bat -Save story      open the window with the story save selected
rem The "exit /b" above ":main" must stay the 5th line at byte offset 104 (108 with
rem CRLF line ends): an older play.bat that an update replaced while it was
rem running resumes reading at exactly that offset.
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
