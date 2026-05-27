Param()

$ErrorActionPreference = "Stop"

function Mask-Text {
  param([string]$Value)
  if ([string]::IsNullOrWhiteSpace($Value)) { return "<empty>" }
  if ($Value.Length -le 6) { return "***" }
  return ($Value.Substring(0, 3) + "***" + $Value.Substring($Value.Length - 2, 2))
}

function Is-TrueFlag {
  param([string]$Value)
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

if ($missingFlags.Count -gt 0) {
  Write-Host "[real_llm_smoke] skip: 未显式开启，缺少开关 -> $($missingFlags -join ', ')" -ForegroundColor Yellow
  exit 0
}

$model = ($env:REAL_LLM_MODEL ?? "").Trim()
$apiKeyEnvName = ($env:REAL_LLM_API_KEY_ENV ?? "").Trim()
if ([string]::IsNullOrWhiteSpace($apiKeyEnvName)) {
  $apiKeyEnvName = "OPENAI_API_KEY"
}
$apiKeyValue = (Get-Item -Path ("Env:" + $apiKeyEnvName) -ErrorAction SilentlyContinue).Value
$baseUrlMasked = Mask-Text $env:REAL_LLM_BASE_URL
$reportDir = ($env:REAL_LLM_PILOT_REPORT_DIR ?? "").Trim()
if ([string]::IsNullOrWhiteSpace($reportDir)) {
  $reportDir = "docs/reports/real_llm_pilot"
}

$missingConfig = @()
if ([string]::IsNullOrWhiteSpace($model)) { $missingConfig += "REAL_LLM_MODEL" }
if ([string]::IsNullOrWhiteSpace($apiKeyEnvName)) { $missingConfig += "REAL_LLM_API_KEY_ENV" }
if ([string]::IsNullOrWhiteSpace($apiKeyValue)) { $missingConfig += ("env:" + $apiKeyEnvName) }

Write-Host "[real_llm_smoke] provider=$($env:REAL_LLM_PROVIDER ?? 'litellm') model=$model base_url=$baseUrlMasked api_key_env=$apiKeyEnvName api_key_present=$([string]::IsNullOrWhiteSpace($apiKeyValue) -eq $false)" -ForegroundColor Cyan
Write-Host "[real_llm_smoke] pilot_report_dir=$reportDir (可通过 REAL_LLM_PILOT_REPORT_DIR 覆盖)" -ForegroundColor Cyan

if ($missingConfig.Count -gt 0) {
  Write-Host "[real_llm_smoke] skip: 配置不完整 -> $($missingConfig -join ', ')" -ForegroundColor Yellow
  exit 0
}

Write-Host "[real_llm_smoke] 运行 real_llm smoke（仅 opt-in）..." -ForegroundColor Cyan
python -m pytest tests/test_real_llm_smoke_v52.py -m real_llm -q
python -m pytest tests/test_real_llm_judge_smoke_v54.py -m real_llm -q

Write-Host "[real_llm_smoke] 已完成。请在报告中记录 request_id/fallback_reason/budget_action/cache_hit/cost。" -ForegroundColor Green
Write-Host "[real_llm_smoke] 报告输出目录：$reportDir" -ForegroundColor Green
