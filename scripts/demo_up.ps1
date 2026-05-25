Param()

$ErrorActionPreference = "Stop"

Write-Host "[demo_up] start build and up app + frontend ..." -ForegroundColor Cyan
docker compose build app frontend
docker compose up -d app frontend
docker compose ps
Write-Host "[demo_up] done." -ForegroundColor Green
