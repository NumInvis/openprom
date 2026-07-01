@echo off
setlocal enabledelayedexpansion

set "PROJECT_DIR=%~dp0"
set "PYTHON_EXE=%PROJECT_DIR%.venv\Scripts\python.exe"
set "PORT=30121"
set "HOST=0.0.0.0"

echo =========================================
echo OpenPROM v4.3.0 Startup
echo =========================================
echo Project: %PROJECT_DIR%
echo.

if not exist "%PYTHON_EXE%" (
    echo ERROR: Python virtual environment not found at %PYTHON_EXE%
    echo Please run: uv venv  or  python -m venv .venv
    pause
    exit /b 1
)

netstat -an | findstr "0.0.0.0:%PORT%" | findstr "LISTENING" >nul
if !errorlevel! == 0 (
    echo OpenPROM API is already running on port %PORT%.
    goto DONE
)

cd /d "%PROJECT_DIR%"
start /b "" "%PYTHON_EXE%" -m uvicorn openprom.api:app --host %HOST% --port %PORT%
echo OpenPROM API started on port %PORT%.

:DONE
echo.
echo =========================================
echo Access URLs:
echo   Web UI:   http://localhost:%PORT%
echo   API Docs: http://localhost:%PORT%/docs
echo   Health:   http://localhost:%PORT%/health
echo =========================================
echo.

timeout /t 2 /nobreak >nul
netstat -an | findstr "0.0.0.0:%PORT%" | findstr "LISTENING" >nul && echo   [OK] OpenPROM API (%PORT%) || echo   [FAIL] OpenPROM API (%PORT%) NOT RESPONDING

echo.
echo Press any key to exit...
pause >nul
