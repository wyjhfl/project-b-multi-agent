Param(
  [string]$BaseUrl = "http://localhost:8000",
  [switch]$SkipSeed,
  [string]$ArtifactDir = "docs/reports/demo_artifacts"
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

function Write-JsonFile {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)]$Payload
  )

  $parent = Split-Path -Parent $Path
  if ($parent -and -not (Test-Path $parent)) {
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
  }

  $json = $Payload | ConvertTo-Json -Depth 20
  [System.IO.File]::WriteAllText($Path, $json, [System.Text.Encoding]::UTF8)
}

function Invoke-JsonGet {
  param(
    [Parameter(Mandatory = $true)][string]$Url
  )

  try {
    $response = Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 8
    return @{ status = "ok"; body = $response; error = "" }
  } catch {
    return @{ status = "failed"; body = $null; error = $_.Exception.Message }
  }
}

function Invoke-Nl2SqlPreview {
  param(
    [Parameter(Mandatory = $true)][string]$Url
  )

  try {
    $bodyObj = [ordered]@{
      query = "demo query last 7 days order trend"
      generator = "mock"
      provider = "fake"
      fallback_to_mock = $true
    }
    $body = $bodyObj | ConvertTo-Json -Depth 8
    $response = Invoke-RestMethod -Uri $Url -Method Post -ContentType "application/json" -Body $body -TimeoutSec 10
    return @{ status = "ok"; body = $response; error = "" }
  } catch {
    return @{ status = "failed"; body = $null; error = $_.Exception.Message }
  }
}

Initialize-CodexProcessEnvironment

$artifactRootResolved = if ([System.IO.Path]::IsPathRooted($ArtifactDir)) {
  $ArtifactDir
} else {
  Join-Path $repoRoot $ArtifactDir
}
$artifactRootResolved = [System.IO.Path]::GetFullPath($artifactRootResolved)
$timestamp = [DateTimeOffset]::UtcNow.ToString("yyyy-MM-ddTHH-mm-ss.fffffffzzz").Replace(":", "-")
$shortCommit = (git -C $repoRoot rev-parse --short HEAD).Trim()
if (-not $shortCommit) {
  $shortCommit = "unknown"
}
$runDir = Join-Path $artifactRootResolved ("{0}_{1}" -f $timestamp, $shortCommit)
New-Item -ItemType Directory -Path $runDir -Force | Out-Null

$seedSummaryPath = Join-Path $runDir "seed_summary.json"
$onlineResultPath = Join-Path $runDir "online_smoke_result.json"
$bundleSummaryPath = Join-Path $runDir "demo_e2e_summary.json"
$pilotReportDir = Join-Path $runDir "pilot_reports"

Write-Host "[demo_e2e] status=start" -ForegroundColor Cyan
Write-Host "[demo_e2e] mode=fake_offline_default" -ForegroundColor Cyan
Write-Host "[demo_e2e] real_llm=disabled (default: no real external LLM call)" -ForegroundColor Cyan
Write-Host "[demo_e2e] mcp_mode=fake (default: no real external MCP dependency)" -ForegroundColor Cyan
Write-Host ("[demo_e2e] artifact_dir={0}" -f $runDir) -ForegroundColor Cyan

$seedSummary = $null
if (-not $SkipSeed) {
  Write-Host "[demo_e2e] step=seed_demo_data status=running" -ForegroundColor Yellow
  $seedRaw = & powershell -NoProfile -ExecutionPolicy Bypass -File $pythonWrapper (Join-Path $repoRoot "scripts/demo_seed_data.py") --pilot-report-dir $pilotReportDir 2>&1
  $seedExit = $LASTEXITCODE
  if ($seedExit -ne 0) {
    Write-Host "[demo_e2e] step=seed_demo_data status=failed" -ForegroundColor Red
    throw "demo seed data script failed"
  }

  $seedJson = $null
  $joined = ($seedRaw -join [Environment]::NewLine)
  $startIndex = $joined.IndexOf("{")
  $endIndex = $joined.LastIndexOf("}")
  if ($startIndex -ge 0 -and $endIndex -gt $startIndex) {
    $seedJson = $joined.Substring($startIndex, $endIndex - $startIndex + 1)
  }

  if (-not $seedJson) {
    throw "unable to parse seed summary json"
  }

  $seedSummary = $seedJson | ConvertFrom-Json
  Write-JsonFile -Path $seedSummaryPath -Payload $seedSummary
  Write-Host "[demo_e2e] step=seed_demo_data status=ok" -ForegroundColor Green
} else {
  $seedSummary = [ordered]@{
    status = "skipped"
    reason = "skip_seed_switch"
    offline = $true
  }
  Write-JsonFile -Path $seedSummaryPath -Payload $seedSummary
  Write-Host "[demo_e2e] step=seed_demo_data status=skipped reason=skip_seed_switch" -ForegroundColor Yellow
}

$onlineResult = [ordered]@{
  generated_at = [DateTimeOffset]::UtcNow.ToString("o")
  base_url = $BaseUrl
  status = "running"
  reason = ""
  checks = [ordered]@{}
}

$healthUrl = "$BaseUrl/health"
$health = Invoke-JsonGet -Url $healthUrl
if ($health.status -ne "ok") {
  $onlineResult.status = "skipped"
  $onlineResult.reason = "service_unavailable"
  $onlineResult.checks.health = [ordered]@{
    status = "skipped"
    url = $healthUrl
    error = [string]$health.error
  }
  Write-JsonFile -Path $onlineResultPath -Payload $onlineResult

  Write-Host "[demo_e2e] step=online_smoke status=skipped reason=service_unavailable" -ForegroundColor Yellow
  Write-Host ("[demo_e2e] detail=service_unavailable {0}, error={1}" -f $healthUrl, $health.error) -ForegroundColor Yellow
  Write-Host "[demo_e2e] hint=run docker compose up -d app frontend first" -ForegroundColor Yellow
} else {
  Write-Host "[demo_e2e] step=online_smoke status=running" -ForegroundColor Yellow

  $checks = @(
    @{ name = "health"; url = "$BaseUrl/health"; method = "GET" },
    @{ name = "tasks"; url = "$BaseUrl/tasks?limit=5"; method = "GET" },
    @{ name = "approvals"; url = "$BaseUrl/approvals?limit=5"; method = "GET" },
    @{ name = "audit"; url = "$BaseUrl/audit/events?limit=5"; method = "GET" },
    @{ name = "metrics"; url = "$BaseUrl/metrics/runtime"; method = "GET" },
    @{ name = "pilot_reports"; url = "$BaseUrl/llm/pilot/reports"; method = "GET" },
    @{ name = "operations_summary"; url = "$BaseUrl/operations/summary"; method = "GET" },
    @{ name = "nl2sql_preview"; url = "$BaseUrl/nl2sql/preview"; method = "POST" }
  )

  $hasFailure = $false
  foreach ($item in $checks) {
    if ($item.method -eq "POST") {
      $result = Invoke-Nl2SqlPreview -Url $item.url
    } else {
      $result = Invoke-JsonGet -Url $item.url
    }

    if ($result.status -eq "ok") {
      $onlineResult.checks[$item.name] = [ordered]@{
        status = "ok"
        url = $item.url
        body = $result.body
      }
      Write-Host ("[demo_e2e] check={0} status=ok" -f $item.name) -ForegroundColor Green
    } else {
      $hasFailure = $true
      $onlineResult.checks[$item.name] = [ordered]@{
        status = "failed"
        url = $item.url
        error = [string]$result.error
      }
      Write-Host ("[demo_e2e] check={0} status=failed detail={1}" -f $item.name, $result.error) -ForegroundColor Red
    }
  }

  if ($hasFailure) {
    $onlineResult.status = "partial"
    $onlineResult.reason = "some_checks_failed"
    Write-Host "[demo_e2e] step=online_smoke status=partial" -ForegroundColor Yellow
  } else {
    $onlineResult.status = "ok"
    Write-Host "[demo_e2e] step=online_smoke status=ok" -ForegroundColor Green
  }

  Write-Host "[demo_e2e] frontend_hint=http://localhost:3000 (Tasks/Approvals/Audit/Metrics/LLM 页面可用于演示)" -ForegroundColor Cyan
  Write-JsonFile -Path $onlineResultPath -Payload $onlineResult
}

$bundleCmd = @(
  (Join-Path $repoRoot "scripts/demo_artifact_bundle.py"),
  "--artifact-dir", $artifactRootResolved,
  "--base-url", $BaseUrl,
  "--online-input", $onlineResultPath,
  "--seed-input", $seedSummaryPath,
  "--artifact-run-dir", $runDir,
  "--pilot-report-dir", $pilotReportDir
)

$bundleRaw = & powershell -NoProfile -ExecutionPolicy Bypass -File $pythonWrapper @bundleCmd
$bundleExit = $LASTEXITCODE
if ($bundleExit -ne 0) {
  throw "demo artifact bundle generation failed"
}

$bundleText = ($bundleRaw -join [Environment]::NewLine)
$bundleStart = $bundleText.IndexOf("{")
$bundleEnd = $bundleText.LastIndexOf("}")
if ($bundleStart -lt 0 -or $bundleEnd -le $bundleStart) {
  throw "unable to parse bundle summary json"
}
$bundleSummary = $bundleText.Substring($bundleStart, $bundleEnd - $bundleStart + 1) | ConvertFrom-Json

Write-Host ("[demo_e2e] artifact_summary={0}" -f $bundleSummary.summary_path) -ForegroundColor Cyan
Write-Host ("[demo_e2e] acceptance_snapshot_json={0}" -f $bundleSummary.acceptance_snapshot_json_path) -ForegroundColor Cyan
Write-Host ("[demo_e2e] pilot_report_index={0}" -f $bundleSummary.pilot_report_index_path) -ForegroundColor Cyan
Write-Host ("[demo_e2e] artifact_run_dir={0}" -f $bundleSummary.artifact_run_dir) -ForegroundColor Cyan
Write-Host ("[demo_e2e] status={0}" -f $bundleSummary.status) -ForegroundColor Green
exit 0
