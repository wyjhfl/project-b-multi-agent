Param()

$ErrorActionPreference = "Stop"

Write-Host "[prod-up] run config check first" -ForegroundColor Cyan
powershell -ExecutionPolicy Bypass -File "$PSScriptRoot/prod_config_check.ps1"

Write-Host "[prod-up] start app + frontend with production override" -ForegroundColor Cyan
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build app frontend

Write-Host "[prod-up] done" -ForegroundColor Green
