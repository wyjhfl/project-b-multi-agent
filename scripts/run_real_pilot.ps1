# 真实 LLM 试点一键启动（PowerShell）
# 凭据放在仓库根目录的 .env.pilot（已被 .gitignore 忽略），本脚本不含任何密钥。
# 用法：
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_real_pilot.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_real_pilot.ps1 -IntervalSeconds 12 -Limit 17
param(
    [double]$IntervalSeconds = 10,
    [int]$Limit = 20,
    [string]$PilotEnvFile = ".env.pilot",
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (-not (Test-Path $PilotEnvFile)) {
    Write-Error "缺少 $PilotEnvFile：请复制 .env.example 的 REAL_LLM_* 段创建它并填入网关地址与 key。"
    exit 2
}

foreach ($line in Get-Content $PilotEnvFile) {
    $trimmed = $line.Trim()
    if ($trimmed -eq "" -or $trimmed.StartsWith("#")) { continue }
    $idx = $trimmed.IndexOf("=")
    if ($idx -lt 1) { continue }
    $name = $trimmed.Substring(0, $idx).Trim()
    $value = $trimmed.Substring($idx + 1).Trim()
    Set-Item -Path "env:$name" -Value $value
}

# 试点总开关只在本进程内打开，不落任何配置文件
$env:REAL_LLM_ACCEPTANCE_ENABLED = "true"

Write-Host "[run_real_pilot] provider=$env:REAL_LLM_PROVIDER model=$env:REAL_LLM_MODEL key_present=$([bool]$env:OPENAI_API_KEY)"

& $Python scripts/run_llm_pilot.py --interval-seconds $IntervalSeconds --limit $Limit
exit $LASTEXITCODE
