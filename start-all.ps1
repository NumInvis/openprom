# OpenPROM v4.3.0 Full Stack Startup (PowerShell)
# Usage: .\start-all.ps1
# Compatible with PowerShell 5.1+

$ErrorActionPreference = 'Stop'
$PROJECT_DIR = $PSScriptRoot

$REDIS_EXE    = "C:\Users\ThinkBook\scoop\apps\redis\8.6.3\redis-server.exe"
$PYTHON_EXE   = Join-Path $PROJECT_DIR ".venv\Scripts\python.exe"
$PROMETHEUS   = Join-Path $PROJECT_DIR "prometheus\prometheus.exe"
$GRAFANA      = Join-Path $PROJECT_DIR "grafana\bin\grafana-server.exe"
$GRAFANA_HOME = Join-Path $PROJECT_DIR "grafana"

function Test-PortListening($port) {
    $conn = (netstat -an | Select-String -Pattern "0.0.0.0:$port.*LISTENING")
    return $conn -ne $null
}

function Start-Component($name, $port, $exePath, $arguments, $envVars = $null) {
    Write-Host "[ ] Checking $name (port $port)..." -NoNewline
    if (Test-PortListening $port) {
        Write-Host "  [RUNNING] Already running on port $port." -ForegroundColor Green
        return
    }
    if (-not (Test-Path $exePath)) {
        Write-Host "  [ERROR] Not found at $exePath" -ForegroundColor Red
        return
    }
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $exePath
    $psi.Arguments = $arguments
    $psi.WorkingDirectory = $PROJECT_DIR
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    if ($envVars) {
        foreach ($key in $envVars.Keys) {
            $psi.EnvironmentVariables[$key] = $envVars[$key]
        }
    }
    [System.Diagnostics.Process]::Start($psi) | Out-Null
    Write-Host "  [STARTED] Port $port." -ForegroundColor Green
}

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "OpenPROM v4.3.0 Full Stack Startup" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Project: $PROJECT_DIR"
Write-Host ""

# 1. Redis
Start-Component -name "Redis" -port 6379 -exePath $REDIS_EXE -arguments "--port 6379 --loglevel notice"

# 2. Prometheus
Start-Component -name "Prometheus" -port 9090 -exePath $PROMETHEUS `
    -arguments "--config.file=`"$PROJECT_DIR\prometheus\prometheus.yml`" --storage.tsdb.path=`"$PROJECT_DIR\prometheus\data`" --web.listen-address=:9090"

# 3. Grafana
$grafanaEnv = @{
    "GF_PATHS_HOME" = $GRAFANA_HOME
    "GF_PATHS_DATA" = Join-Path $GRAFANA_HOME "data"
    "GF_PATHS_LOGS" = Join-Path $GRAFANA_HOME "logs"
    "GF_PATHS_PLUGINS" = Join-Path $GRAFANA_HOME "plugins"
    "GF_PATHS_PROVISIONING" = Join-Path $GRAFANA_HOME "conf\provisioning"
    "GF_SECURITY_ADMIN_USER" = "admin"
    "GF_SECURITY_ADMIN_PASSWORD" = "admin"
    "GF_USERS_ALLOW_SIGN_UP" = "false"
}
Start-Component -name "Grafana" -port 3000 -exePath $GRAFANA `
    -arguments "--config=`"$GRAFANA_HOME\conf\defaults.ini`" cfg:default.paths.data=`"$GRAFANA_HOME\data`" cfg:default.paths.logs=`"$GRAFANA_HOME\logs`" cfg:default.paths.plugins=`"$GRAFANA_HOME\plugins`"" `
    -envVars $grafanaEnv

# 4. OpenPROM API
Start-Component -name "OpenPROM API" -port 30121 -exePath $PYTHON_EXE `
    -arguments "-m uvicorn openprom.api:app --host 0.0.0.0 --port 30121"

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "All services are running." -ForegroundColor Green
Write-Host ""
Write-Host "Access URLs:" -ForegroundColor Yellow
Write-Host "  OpenPROM Web UI:     http://localhost:30121"
Write-Host "  API Docs:            http://localhost:30121/docs"
Write-Host "  Health:              http://localhost:30121/health"
Write-Host "  Prometheus Console:  http://localhost:9090"
Write-Host "  Grafana Console:     http://localhost:3000  (admin/admin)"
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

Start-Sleep -Seconds 2

Write-Host "Service status:"
@(
    @{Port=30121; Name="OpenPROM API"},
    @{Port=6379;  Name="Redis"},
    @{Port=9090;  Name="Prometheus"},
    @{Port=3000;  Name="Grafana"}
) | ForEach-Object {
    if (Test-PortListening $_.Port) {
        Write-Host "  [OK] $($_.Name)  ($($_.Port))" -ForegroundColor Green
    } else {
        Write-Host "  [XX] $($_.Name)  ($($_.Port)) NOT RESPONDING" -ForegroundColor Red
    }
}

Write-Host ""
Read-Host "Press Enter to exit this window"
