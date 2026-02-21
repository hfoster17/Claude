# start_engine.ps1 — Launch the Multi-Regime Engine (for Task Scheduler)
# Configure paths below or set environment variables

param(
    [string]$VenvPath = $env:MULTIREGIME_VENV ?? "C:\MultiRegime\venv",
    [string]$EnginePath = $env:MULTIREGIME_ENGINE ?? "C:\MultiRegime\engine",
    [string]$LogDir = $env:MULTIREGIME_LOGS ?? "C:\MultiRegime\logs"
)

$ErrorActionPreference = "Stop"

# Ensure log directory exists
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

$PythonExe = Join-Path $VenvPath "Scripts\python.exe"
$MainScript = Join-Path $EnginePath "main.py"

if (-not (Test-Path $PythonExe)) {
    Write-Error "Python not found: $PythonExe"
    exit 1
}

if (-not (Test-Path $MainScript)) {
    Write-Error "Engine script not found: $MainScript"
    exit 1
}

Write-Host "Starting Multi-Regime Engine..." -ForegroundColor Green
Write-Host "  Python: $PythonExe"
Write-Host "  Script: $MainScript"
Write-Host "  Logs:   $LogDir"

Set-Location $EnginePath

& $PythonExe $MainScript --serve --log-dir $LogDir
