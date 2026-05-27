Param(
  [string]$BaseUrl = "http://localhost:8000",
  [switch]$SkipSeed
)

$ErrorActionPreference = "Stop"

Write-Host "[demo_e2e] status=start" -ForegroundColor Cyan
Write-Host "[demo_e2e] mode=fake_offline" -ForegroundColor Cyan
Write-Host "[demo_e2e] real_llm=disabled (default: no real external LLM call)" -ForegroundColor Cyan
Write-Host "[demo_e2e] mcp_mode=fake (default: no real external MCP dependency)" -ForegroundColor Cyan

if (-not $SkipSeed) {
  Write-Host "[demo_e2e] step=seed_demo_data status=running" -ForegroundColor Yellow
  python scripts/demo_seed_data.py
  if ($LASTEXITCODE -ne 0) {
    Write-Host "[demo_e2e] step=seed_demo_data status=failed" -ForegroundColor Red
    throw "demo seed data script failed"
  }
  Write-Host "[demo_e2e] step=seed_demo_data status=ok" -ForegroundColor Green
} else {
  Write-Host "[demo_e2e] step=seed_demo_data status=skipped reason=skip_seed_switch" -ForegroundColor Yellow
}

function Invoke-JsonGet {
  param(
    [Parameter(Mandatory = $true)][string]$Url
  )

  try {
    $response = Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 5
    return @{ ok = $true; body = $response; error = "" }
  } catch {
    return @{ ok = $false; body = $null; error = $_.Exception.Message }
  }
}

$healthUrl = "$BaseUrl/health"
$health = Invoke-JsonGet -Url $healthUrl
if (-not $health.ok) {
  Write-Host "[demo_e2e] step=online_smoke status=skipped reason=service_unavailable" -ForegroundColor Yellow
  Write-Host ("[demo_e2e] detail=service_unavailable {0}, error={1}" -f $healthUrl, $health.error) -ForegroundColor Yellow
  Write-Host "[demo_e2e] hint=run docker compose up -d app frontend first" -ForegroundColor Yellow
  Write-Host "[demo_e2e] status=completed_with_skipped_online_checks" -ForegroundColor Yellow
  exit 0
}

Write-Host "[demo_e2e] step=online_smoke status=running" -ForegroundColor Yellow

$checks = @(
  @{ name = "health"; url = "$BaseUrl/health" },
  @{ name = "tasks"; url = "$BaseUrl/tasks?limit=5" },
  @{ name = "approvals"; url = "$BaseUrl/approvals?limit=5" },
  @{ name = "audit"; url = "$BaseUrl/audit/events?limit=5" },
  @{ name = "metrics"; url = "$BaseUrl/metrics/runtime" },
  @{ name = "pilot_reports"; url = "$BaseUrl/llm/pilot/reports" },
  @{ name = "nl2sql_preview"; url = "$BaseUrl/nl2sql/preview" }
)

foreach ($item in $checks) {
  if ($item.name -eq "nl2sql_preview") {
    try {
      $bodyObj = [ordered]@{
        query = "demo query last 7 days order trend"
        generator = "mock"
        provider = "fake"
        fallback_to_mock = $true
      }
      $body = $bodyObj | ConvertTo-Json -Depth 6
      $resp = Invoke-RestMethod -Uri $item.url -Method Post -ContentType "application/json" -Body $body -TimeoutSec 10
      Write-Host ("[demo_e2e] check={0} status=ok detail=generator_used:{1}" -f $item.name, $resp.generator_used) -ForegroundColor Green
    } catch {
      Write-Host ("[demo_e2e] check={0} status=failed detail={1}" -f $item.name, $_.Exception.Message) -ForegroundColor Red
      throw
    }
    continue
  }

  $result = Invoke-JsonGet -Url $item.url
  if ($result.ok) {
    Write-Host ("[demo_e2e] check={0} status=ok" -f $item.name) -ForegroundColor Green
  } else {
    Write-Host ("[demo_e2e] check={0} status=failed detail={1}" -f $item.name, $result.error) -ForegroundColor Red
    throw "online smoke failed"
  }
}

Write-Host "[demo_e2e] step=online_smoke status=ok" -ForegroundColor Green
Write-Host "[demo_e2e] frontend_hint=http://localhost:3000 (Tasks/Approvals/Audit/Metrics/LLM 页面可用于演示)" -ForegroundColor Cyan
Write-Host "[demo_e2e] status=completed" -ForegroundColor Green
