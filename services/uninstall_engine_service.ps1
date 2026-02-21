# uninstall_engine_service.ps1 — Remove Multi-Regime Engine Windows Service
# Run as Administrator

param(
    [string]$ServiceName = "MultiRegimeEngine",
    [string]$NSSMPath = "C:\Program Files\nssm\nssm.exe"
)

$ErrorActionPreference = "Stop"

Write-Host "Stopping service: $ServiceName" -ForegroundColor Yellow
try {
    & $NSSMPath stop $ServiceName 2>$null
    Start-Sleep -Seconds 2
} catch {
    Write-Host "Service may not be running" -ForegroundColor Gray
}

Write-Host "Removing service: $ServiceName" -ForegroundColor Yellow
& $NSSMPath remove $ServiceName confirm

if ($LASTEXITCODE -eq 0) {
    Write-Host "Service removed successfully!" -ForegroundColor Green
} else {
    Write-Error "Failed to remove service"
}
