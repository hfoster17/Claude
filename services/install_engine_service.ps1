# install_engine_service.ps1 — Install Multi-Regime Engine as Windows Service via NSSM
# Requires: NSSM (https://nssm.cc) in PATH or $NSSMPath
# Run as Administrator

param(
    [string]$ServiceName = "MultiRegimeEngine",
    [string]$PythonExe = "C:\MultiRegime\venv\Scripts\python.exe",
    [string]$ScriptPath = "C:\MultiRegime\engine\main.py",
    [string]$WorkingDir = "C:\MultiRegime\engine",
    [string]$LogDir = "C:\MultiRegime\logs",
    [string]$NSSMPath = "C:\Program Files\nssm\nssm.exe"
)

$ErrorActionPreference = "Stop"

# Validate paths
if (-not (Test-Path $NSSMPath)) {
    Write-Error "NSSM not found at $NSSMPath. Download from https://nssm.cc"
    exit 1
}

if (-not (Test-Path $PythonExe)) {
    Write-Error "Python executable not found at $PythonExe"
    exit 1
}

if (-not (Test-Path $ScriptPath)) {
    Write-Error "Engine script not found at $ScriptPath"
    exit 1
}

# Create log directory
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

Write-Host "Installing service: $ServiceName" -ForegroundColor Green

# Install service
& $NSSMPath install $ServiceName $PythonExe "$ScriptPath --serve"
if ($LASTEXITCODE -ne 0) { Write-Error "Failed to install service"; exit 1 }

# Configure service
& $NSSMPath set $ServiceName AppDirectory $WorkingDir
& $NSSMPath set $ServiceName AppStdout "$LogDir\engine_stdout.log"
& $NSSMPath set $ServiceName AppStderr "$LogDir\engine_stderr.log"
& $NSSMPath set $ServiceName AppStdoutCreationDisposition 4
& $NSSMPath set $ServiceName AppStderrCreationDisposition 4
& $NSSMPath set $ServiceName AppRotateFiles 1
& $NSSMPath set $ServiceName AppRotateBytes 10485760

# Auto-start at boot
& $NSSMPath set $ServiceName Start SERVICE_AUTO_START

# Restart on failure
& $NSSMPath set $ServiceName AppExit Default Restart
& $NSSMPath set $ServiceName AppRestartDelay 5000

# Display name
& $NSSMPath set $ServiceName DisplayName "Multi-Regime Trading Engine"
& $NSSMPath set $ServiceName Description "HMM-based regime detection engine for futures trading"

Write-Host "Service installed successfully!" -ForegroundColor Green
Write-Host "Start with: net start $ServiceName" -ForegroundColor Cyan
Write-Host "Or: & '$NSSMPath' start $ServiceName" -ForegroundColor Cyan
