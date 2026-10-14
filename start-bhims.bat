@echo off
REM ===========================================================================
REM  BHIMS - start the development server on a guaranteed-clean port.
REM
REM  Why this exists: a runserver left on --noreload keeps serving the
REM  templates it loaded at start-up. Edit a template, refresh, and you are
REM  still looking at the old page with no error anywhere. This script always
REM  clears the port first, so what you see is always the code on disk.
REM
REM  Usage:   start-bhims.bat          -> http://127.0.0.1:8017/
REM          start-bhims.bat 8021     -> a different port
REM ===========================================================================

setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "PORT=%~1"
if "%PORT%"=="" set "PORT=8017"
set "PYTHON=%~dp0venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo.
    echo   Could not find the virtual environment at:
    echo     %PYTHON%
    echo.
    pause
    exit /b 1
)

echo.
echo   BHIMS  -  starting on port %PORT%

REM --- 1. Clear the port. Anything holding it is a stale, pre-edit server. ---
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do (
    echo   clearing pid %%P from port %PORT%
    taskkill /F /PID %%P >nul 2>&1
)

REM Give the OS a moment to actually release the socket before rebinding.
REM (ping, not `timeout`: `timeout` resolves to GNU coreutils outside Explorer)
ping -n 3 127.0.0.1 >nul

REM --- 2. Hold the console open so the server lives as long as you want it ---
REM  --noreload is deliberate: it is what makes this fast. The script above is
REM  what makes it correct, because it guarantees a fresh start.
"%PYTHON%" manage.py runserver 127.0.0.1:%PORT% --noreload

echo.
echo   BHIMS stopped. (port %PORT%)
pause
endlocal