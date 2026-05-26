Param()

$ErrorActionPreference = "Stop"

Write-Host "[prod-config-check] start" -ForegroundColor Cyan

$response = $null
try {
  $response = Invoke-RestMethod -Uri "http://localhost:8000/deployment/check" -Method Get -TimeoutSec 10
} catch {
  Write-Host "[prod-config-check] api unavailable, fallback to local python" -ForegroundColor Yellow
  $pythonScript = @'
import json
from app.core.deployment_guard import run_deployment_checks
result = run_deployment_checks()
print(result.model_dump_json())
'@
  $json = $pythonScript | python -
  $response = $json | ConvertFrom-Json
}

if ($null -eq $response) {
  throw "[prod-config-check] no valid result"
}

Write-Host ("[prod-config-check] environment={0}, ok={1}" -f $response.environment, $response.ok) -ForegroundColor White

if ($response.warnings -and $response.warnings.Count -gt 0) {
  Write-Host "[prod-config-check] warnings:" -ForegroundColor Yellow
  $response.warnings | ForEach-Object { Write-Host ("  - {0}" -f $_) -ForegroundColor Yellow }
}

if ($response.errors -and $response.errors.Count -gt 0) {
  Write-Host "[prod-config-check] errors:" -ForegroundColor Red
  $response.errors | ForEach-Object { Write-Host ("  - {0}" -f $_) -ForegroundColor Red }
}

if (-not $response.ok) {
  Write-Host "[prod-config-check] failed, exit 1" -ForegroundColor Red
  exit 1
}

Write-Host "[prod-config-check] passed" -ForegroundColor Green
