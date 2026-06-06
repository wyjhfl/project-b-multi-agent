Param(
  [switch]$UseExistingEnv,
  [switch]$CheckPythonOnly,
  [int]$TimeoutSeconds = 20,
  [string]$ClosureEvidence = "docs/reports/launch_blocker_closure/closure_evidence.draft.json"
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$apiKeyEnv = "XIAOMI_LLM_API_KEY"
$previousValue = [Environment]::GetEnvironmentVariable($apiKeyEnv, "Process")
$hadPreviousValue = -not [string]::IsNullOrWhiteSpace($previousValue)
$keyInjectedForRun = $false

function Initialize-CodexProcessEnvironment {
  [Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
  [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
  $script:OutputEncoding = [System.Text.UTF8Encoding]::new($false)
  chcp 65001 | Out-Null

  $xdgRoot = Join-Path $repoRoot ".git-xdg"
  New-Item -ItemType Directory -Force -Path (Join-Path $xdgRoot "git") | Out-Null
  $gitIgnore = Join-Path $xdgRoot "git\ignore"
  if (-not (Test-Path -LiteralPath $gitIgnore)) {
    New-Item -ItemType File -Force -Path $gitIgnore | Out-Null
  }

  $env:XDG_CONFIG_HOME = $xdgRoot
  $env:PYTHONUTF8 = "1"
  $env:PYTHONIOENCODING = "utf-8"
}

function Resolve-PythonExecutable {
  $currentPython = (Get-Command "python.exe" -ErrorAction SilentlyContinue)
  if ($currentPython -and $currentPython.Source -notlike "*WindowsApps*") {
    return @($currentPython.Source)
  }

  $knownPython = Get-ChildItem -LiteralPath "D:\" -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like "codex*" } |
    ForEach-Object { Join-Path $_.FullName "tools\Python312\python.exe" } |
    Where-Object { Test-Path -LiteralPath $_ } |
    Select-Object -First 1
  if ($knownPython) {
    return @($knownPython)
  }

  $pyLauncher = Get-Command "py.exe" -ErrorAction SilentlyContinue
  if ($pyLauncher) {
    return @($pyLauncher.Source, "-3")
  }

  throw "Python runtime not found. Expected bundled Codex runtime under D:\codex*\tools\Python312\python.exe, py -3, or a non-WindowsApps python.exe on PATH."
}

function Convert-SecureStringToPlainText {
  param([Parameter(Mandatory = $true)][Security.SecureString]$SecureValue)

  $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureValue)
  try {
    return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
  } finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
  }
}

function Invoke-CheckedPython {
  param([Parameter(Mandatory = $true)][string[]]$Arguments)

  [string[]]$pythonCommand = @(Resolve-PythonExecutable)
  if ($pythonCommand.Count -gt 1) {
    & $pythonCommand[0] $pythonCommand[1..($pythonCommand.Count - 1)] $Arguments
  } else {
    & $pythonCommand[0] $Arguments
  }
  $exitCode = $LASTEXITCODE
  if ($exitCode -ne 0) {
    throw "python command failed with exit code $exitCode"
  }
}

if ($CheckPythonOnly) {
  Initialize-CodexProcessEnvironment
  [string[]]$pythonCommand = @(Resolve-PythonExecutable)
  Write-Host "[xiaomi_llm_landing_resume] python=$($pythonCommand[0])" -ForegroundColor Cyan
  exit 0
}

try {
  Initialize-CodexProcessEnvironment

  if (-not $UseExistingEnv -or -not $hadPreviousValue) {
    Write-Host "[xiaomi_llm_landing_resume] input=secure_process_env_only" -ForegroundColor Cyan
    Write-Host "[xiaomi_llm_landing_resume] secret_will_not_be_written_to_repo_or_report" -ForegroundColor Cyan
    $secureKey = Read-Host "Enter Xiaomi LLM API key for this process only" -AsSecureString
    $plainKey = Convert-SecureStringToPlainText -SecureValue $secureKey
    if ([string]::IsNullOrWhiteSpace($plainKey)) {
      throw "XIAOMI_LLM_API_KEY is empty"
    }
    [Environment]::SetEnvironmentVariable($apiKeyEnv, $plainKey, "Process")
    $keyInjectedForRun = $true
  } else {
    Write-Host "[xiaomi_llm_landing_resume] input=existing_process_env" -ForegroundColor Cyan
  }

  Write-Host "[xiaomi_llm_landing_resume] step=xiaomi-llm-preflight" -ForegroundColor Yellow
  Invoke-CheckedPython @(
    (Join-Path $repoRoot "scripts/production_landing_xiaomi_llm_preflight_runner.py"),
    "--execute-network-check",
    "--timeout-seconds",
    "$TimeoutSeconds"
  )

  Write-Host "[xiaomi_llm_landing_resume] step=manual-signoff-evidence-ack-status" -ForegroundColor Yellow
  Invoke-CheckedPython @(
    (Join-Path $repoRoot "scripts/manual_signoff_evidence_ack_status.py")
  )

  Write-Host "[xiaomi_llm_landing_resume] step=manual-signoff-record-validation" -ForegroundColor Yellow
  Invoke-CheckedPython @(
    (Join-Path $repoRoot "scripts/manual_signoff_record_validator.py")
  )

  Write-Host "[xiaomi_llm_landing_resume] step=blocker-resolution" -ForegroundColor Yellow
  Invoke-CheckedPython @(
    (Join-Path $repoRoot "scripts/production_landing_blocker_resolution.py")
  )

  Write-Host "[xiaomi_llm_landing_resume] step=refresh-status" -ForegroundColor Yellow
  Invoke-CheckedPython @(
    (Join-Path $repoRoot "scripts/production_landing_refresh_status.py"),
    "--closure-evidence",
    $ClosureEvidence
  )

  Write-Host "[xiaomi_llm_landing_resume] step=final-verification" -ForegroundColor Yellow
  Invoke-CheckedPython @(
    (Join-Path $repoRoot "scripts/production_landing_final_verification.py")
  )

  Write-Host "[xiaomi_llm_landing_resume] status=done" -ForegroundColor Green
} finally {
  if ($keyInjectedForRun) {
    if ($hadPreviousValue) {
      [Environment]::SetEnvironmentVariable($apiKeyEnv, $previousValue, "Process")
    } else {
      [Environment]::SetEnvironmentVariable($apiKeyEnv, $null, "Process")
    }
    Write-Host "[xiaomi_llm_landing_resume] process_env_restored=true" -ForegroundColor Cyan
  }
}
