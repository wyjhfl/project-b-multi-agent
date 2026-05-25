Param()

$ErrorActionPreference = "Stop"

function Test-Endpoint {
  param(
    [Parameter(Mandatory = $true)][string]$Url
  )

  $maxAttempts = 30
  $lastStatusCode = "ERR"
  for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
    $statusCode = (& curl.exe -s -o NUL -w "%{http_code}" $Url).Trim()
    if ($statusCode -match "^\d{3}$") {
      $lastStatusCode = [int]$statusCode
    } else {
      $lastStatusCode = "ERR"
    }

    if ($lastStatusCode -ge 200 -and $lastStatusCode -lt 400) {
      Write-Host ("[demo_smoke] {0} -> {1}" -f $Url, $lastStatusCode) -ForegroundColor Green
      return
    }

    if ($attempt -eq $maxAttempts) {
      Write-Host ("[demo_smoke] {0} -> {1}" -f $Url, $lastStatusCode) -ForegroundColor Red
      throw "smoke check failed: $Url"
    }
    Start-Sleep -Seconds 2
  }
}

Write-Host "[demo_smoke] start local smoke checks..." -ForegroundColor Cyan

$urls = @(
  "http://localhost:3000/api/health",
  "http://localhost:3000/",
  "http://localhost:3000/tasks",
  "http://localhost:3000/approvals",
  "http://localhost:3000/audit",
  "http://localhost:3000/metrics",
  "http://localhost:3000/observability"
)

foreach ($url in $urls) {
  Test-Endpoint -Url $url
}

Write-Host "[demo_smoke] all checks passed." -ForegroundColor Green
