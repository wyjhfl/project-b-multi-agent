Param()

$ErrorActionPreference = "Stop"

Write-Host "[prod-down] stop and cleanup containers" -ForegroundColor Cyan
docker compose -f docker-compose.yml -f docker-compose.prod.yml down
Write-Host "[prod-down] done" -ForegroundColor Green
