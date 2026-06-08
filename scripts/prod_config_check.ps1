Param(
  [switch]$UseApi
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot ".." )).Path
$pythonWrapper = Join-Path $repoRoot "scripts\codex_python.ps1"

function Initialize-CodexProcessEnvironment {
  [Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
  [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
  $script:OutputEncoding = [System.Text.UTF8Encoding]::new($false)
  chcp 65001 | Out-Null
}

Write-Host "[prod-config-check] start" -ForegroundColor Cyan

function Get-LocalDeploymentCheckResult {
  $pythonCode = "from app.core.deployment_guard import run_deployment_checks; print(run_deployment_checks().model_dump_json())"
  $json = & powershell -NoProfile -ExecutionPolicy Bypass -File $pythonWrapper -c $pythonCode
  if ($LASTEXITCODE -ne 0) {
    throw "[prod-config-check] local deployment check python command failed with exit code $LASTEXITCODE"
  }
  return $json | ConvertFrom-Json
}

function Get-ApiDeploymentCheckResult {
  return Invoke-RestMethod -Uri "http://localhost:8000/deployment/check" -Method Get -TimeoutSec 10
}

$response = $null
Initialize-CodexProcessEnvironment

if ($UseApi) {
  Write-Host "[prod-config-check] mode=api" -ForegroundColor Yellow
  $response = Get-ApiDeploymentCheckResult
} else {
  Write-Host "[prod-config-check] mode=local_python" -ForegroundColor White
  $response = Get-LocalDeploymentCheckResult
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
