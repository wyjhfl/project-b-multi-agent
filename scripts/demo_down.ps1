Param()

$ErrorActionPreference = "Stop"

Write-Host "[demo_down] stop and clean containers..." -ForegroundColor Cyan
docker compose down
Write-Host "[demo_down] done." -ForegroundColor Green
