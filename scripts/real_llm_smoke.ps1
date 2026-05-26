Param()

$ErrorActionPreference = "Stop"

function Mask-Text {
  param(
    [string]$Value
  )
  if ([string]::IsNullOrWhiteSpace($Value)) {
    return "<empty>"
  }
  if ($Value.Length -le 6) {
    return "***"
  }
  return ($Value.Substring(0, 3) + "***" + $Value.Substring($Value.Length - 2, 2))
}

function Is-TrueFlag {
  param(
    [string]$Value
  )
  return (($Value ?? "").Trim().ToLower() -eq "true")
}

$requiredFlags = @(
  "REAL_LLM_SMOKE_ENABLED",
  "REAL_LLM_ACCEPTANCE_ENABLED",
  "REAL_LLM_PREFLIGHT_ENABLED",
  "REAL_LLM_PREFLIGHT_NETWORK_CHECK"
)

$missingFlags = @()
foreach ($flag in $requiredFlags) {
  $flagValue = (Get-Item -Path ("Env:" + $flag) -ErrorAction SilentlyContinue).Value
  if (-not (Is-TrueFlag $flagValue)) {
    $missingFlags += $flag
  }
}

$provider = if ([string]::IsNullOrWhiteSpace($env:REAL_LLM_PROVIDER)) { "litellm" } else { $env:REAL_LLM_PROVIDER }
$model = if ([string]::IsNullOrWhiteSpace($env:REAL_LLM_MODEL)) { "<empty>" } else { $env:REAL_LLM_MODEL }
$baseUrl = Mask-Text $env:REAL_LLM_BASE_URL
$apiKeyEnvName = if ([string]::IsNullOrWhiteSpace($env:REAL_LLM_API_KEY_ENV)) { "OPENAI_API_KEY" } else { $env:REAL_LLM_API_KEY_ENV }
$apiKeyValue = (Get-Item -Path ("Env:" + $apiKeyEnvName) -ErrorAction SilentlyContinue).Value
$apiKeyPresent = if ([string]::IsNullOrWhiteSpace($apiKeyValue)) { "missing" } else { "present" }

Write-Host "[real_llm_smoke] provider=$provider model=$model base_url=$baseUrl api_key_env=$apiKeyEnvName api_key=$apiKeyPresent" -ForegroundColor Cyan

if ([string]::IsNullOrWhiteSpace($env:LLM_MODEL)) {
  Write-Host "[real_llm_smoke] hint: LLM_MODEL is empty, smoke test will map REAL_LLM_MODEL at runtime." -ForegroundColor Yellow
}
if ([string]::IsNullOrWhiteSpace($env:LLM_API_KEY)) {
  Write-Host "[real_llm_smoke] hint: LLM_API_KEY is empty, smoke test will map REAL_LLM_API_KEY_ENV at runtime." -ForegroundColor Yellow
}
if ([string]::IsNullOrWhiteSpace($env:LLM_BASE_URL)) {
  Write-Host "[real_llm_smoke] hint: LLM_BASE_URL is empty, smoke test will map REAL_LLM_BASE_URL at runtime." -ForegroundColor Yellow
}

if ($missingFlags.Count -gt 0) {
  Write-Host "[real_llm_smoke] skip: opt-in flags not enabled -> $($missingFlags -join ', ')" -ForegroundColor Yellow
  exit 0
}

Write-Host "[real_llm_smoke] running pytest real_llm marker..." -ForegroundColor Cyan
python -m pytest tests/test_real_llm_smoke_v52.py -m real_llm -q
Write-Host "[real_llm_smoke] running judge smoke..." -ForegroundColor Cyan
python -m pytest tests/test_real_llm_judge_smoke_v54.py -m real_llm -q
Write-Host "[real_llm_smoke] hint: you can run judge smoke only by:" -ForegroundColor Yellow
Write-Host "python -m pytest tests/test_real_llm_judge_smoke_v54.py -m real_llm -q" -ForegroundColor Yellow
Write-Host "[real_llm_smoke] done." -ForegroundColor Green
