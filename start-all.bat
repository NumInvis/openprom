@echo off
setlocal enabledelayedexpansion

set "PROJECT_DIR=%~dp0"
set "REDIS_EXE=C:\Users\ThinkBook\scoop\apps\redis\8.6.3\redis-server.exe"
set "PYTHON_EXE=%PROJECT_DIR%.venv\Scripts\python.exe"
set "PROMETHEUS_EXE=%PROJECT_DIR%prometheus\prometheus.exe"
set "GRAFANA_EXE=%PROJECT_DIR%grafana\bin\grafana-server.exe"
set "GRAFANA_HOME=%PROJECT_DIR%grafana"

echo =========================================
echo OpenPROM v4.3.0 Full Stack Startup
echo =========================================
echo Project: %PROJECT_DIR%
echo.

:CHECK_REDIS
echo [1/4] Checking Redis (port 6379)...
netstat -an | findstr "0.0.0.0:6379" | findstr "LISTENING" >nul
if !errorlevel! == 0 (
    echo      Redis already running on port 6379.
    goto CHECK_PROMETHEUS
)
if exist "%REDIS_EXE%" (
    start /b "" "%REDIS_EXE%" --port 6379 --loglevel notice
    echo      Redis started.
) else (
    echo      ERROR: Redis not found at %REDIS_EXE%
)

:CHECK_PROMETHEUS
echo.
echo [2/4] Checking Prometheus (port 9090)...
netstat -an | findstr "0.0.0.0:9090" | findstr "LISTENING" >nul
if !errorlevel! == 0 (
    echo      Prometheus already running on port 9090.
    goto CHECK_GRAFANA
)
if exist "%PROMETHEUS_EXE%" (
    start /b "" "%PROMETHEUS_EXE%" --config.file="%PROJECT_DIR%prometheus\prometheus.yml" --storage.tsdb.path="%PROJECT_DIR%prometheus\data" --web.listen-address=:9090
    echo      Prometheus started.
) else (
    echo      ERROR: Prometheus not found at %PROMETHEUS_EXE%
)

:CHECK_GRAFANA
echo.
echo [3/4] Checking Grafana (port 3000)...
netstat -an | findstr "0.0.0.0:3000" | findstr "LISTENING" >nul
if !errorlevel! == 0 (
    echo      Grafana already running on port 3000.
    goto CHECK_API
)
if exist "%GRAFANA_EXE%" (
    set "GF_PATHS_HOME=%GRAFANA_HOME%"
    set "GF_PATHS_DATA=%GRAFANA_HOME%\data"
    set "GF_PATHS_LOGS=%GRAFANA_HOME%\logs"
    set "GF_PATHS_PLUGINS=%GRAFANA_HOME%\plugins"
    set "GF_PATHS_PROVISIONING=%GRAFANA_HOME%\conf\provisioning"
    set "GF_SECURITY_ADMIN_USER=admin"
    set "GF_SECURITY_ADMIN_PASSWORD=admin"
    set "GF_USERS_ALLOW_SIGN_UP=false"
    start /b "" "%GRAFANA_EXE%" --config="%GRAFANA_HOME%\conf\defaults.ini" cfg:default.paths.data="%GRAFANA_HOME%\data" cfg:default.paths.logs="%GRAFANA_HOME%\logs" cfg:default.paths.plugins="%GRAFANA_HOME%\plugins"
    echo      Grafana started.
) else (
    echo      ERROR: Grafana not found at %GRAFANA_EXE%
)

:CHECK_API
echo.
echo [4/4] Checking OpenPROM API (port 30121)...
netstat -an | findstr "0.0.0.0:30121" | findstr "LISTENING" >nul
if !errorlevel! == 0 (
    echo      OpenPROM API already running on port 30121.
    goto DONE
)
if exist "%PYTHON_EXE%" (
    cd /d "%PROJECT_DIR%"
    start /b "" "%PYTHON_EXE%" -m uvicorn openprom.api:app --host 0.0.0.0 --port 30121
    echo      OpenPROM API started.
) else (
    echo      ERROR: Python not found at %PYTHON_EXE%
)

:DONE
echo.
echo =========================================
echo All services are running.
echo.
echo Access URLs:
echo   OpenPROM Web UI:     http://localhost:30121
echo   API Docs:            http://localhost:30121/docs
echo   Health:              http://localhost:30121/health
echo   Prometheus Console:  http://localhost:9090
echo   Grafana Console:     http://localhost:3000  (admin/admin)
echo =========================================
echo.

:: Wait for services to fully initialize
timeout /t 2 /nobreak >nul

echo Service status:
netstat -an | findstr "0.0.0.0:30121" | findstr "LISTENING" >nul && echo   [OK] OpenPROM API  (30121) || echo   [XX] OpenPROM API  (30121) NOT RESPONDING
netstat -an | findstr "0.0.0.0:6379"  | findstr "LISTENING" >nul && echo   [OK] Redis           (6379)  || echo   [XX] Redis           (6379)  NOT RESPONDING
netstat -an | findstr "0.0.0.0:9090"  | findstr "LISTENING" >nul && echo   [OK] Prometheus      (9090)  || echo   [XX] Prometheus      (9090)  NOT RESPONDING
netstat -an | findstr "0.0.0.0:3000"  | findstr "LISTENING" >nul && echo   [OK] Grafana         (3000)  || echo   [XX] Grafana         (3000)  NOT RESPONDING

echo.
echo Press any key to exit this window...
pause >nul
