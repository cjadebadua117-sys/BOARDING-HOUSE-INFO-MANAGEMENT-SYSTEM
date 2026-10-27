@echo off
REM ===========================================================================
REM  BHIMS - put the public demo back online after a reboot.
REM
REM  Quick tunnels are random and die with the process, so the old
REM  trycloudflare.com link cannot be reopened - a new one has to be issued.
REM  This script does the whole routine in one double-click:
REM
REM    1. starts MySQL for you if XAMPP's copy is not already running
REM    2. starts cloudflared and waits for the new public address
REM    3. starts the production server (DEBUG off, WhiteNoise on) wired to it
REM    4. prints the address, copies it to the clipboard, saves it to
REM       .audit\public-url.txt
REM
REM  That is the whole routine - one double-click, no XAMPP panel needed.
REM
REM  Keep this window open while the site is live; closing it (or Ctrl+C)
REM  takes the site down. The address is only for demos - see
REM  docs\DEPLOY-FREE.md for the free host that survives shutdown.
REM ===========================================================================

setlocal
cd /d "%~dp0"

set "PYTHON=%~dp0venv\Scripts\python.exe"
if not exist "%PYTHON%" (
    echo.
    echo   Could not find the virtual environment at:
    echo     %PYTHON%
    echo   Run these first:  python -m venv venv  ^&^&  venv\Scripts\pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

"%PYTHON%" "tools\Start Public Demo.py"

echo.
pause
endlocal
