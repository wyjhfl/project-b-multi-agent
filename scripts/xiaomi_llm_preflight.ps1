Param(
  [switch]$UseExistingEnv,
  [switch]$CheckPythonOnly,
  [int]$TimeoutSeconds = 20
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

function Invoke-ResolvedPython {
  param([Parameter(Mandatory = $true)][string[]]$Arguments)

  [string[]]$pythonCommand = @(Resolve-PythonExecutable)
  if ($pythonCommand.Count -gt 1) {
    & $pythonCommand[0] $pythonCommand[1..($pythonCommand.Count - 1)] $Arguments
  } else {
    & $pythonCommand[0] $Arguments
  }
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

if ($CheckPythonOnly) {
  Initialize-CodexProcessEnvironment
  [string[]]$pythonCommand = @(Resolve-PythonExecutable)
  Write-Host "[xiaomi_llm_preflight] python=$($pythonCommand[0])" -ForegroundColor Cyan
  exit 0
}

try {
  Initialize-CodexProcessEnvironment

  if (-not $UseExistingEnv -or -not $hadPreviousValue) {
    Write-Host "[xiaomi_llm_preflight] input=secure_process_env_only" -ForegroundColor Cyan
    Write-Host "[xiaomi_llm_preflight] secret_will_not_be_written_to_repo_or_report" -ForegroundColor Cyan
    $secureKey = Read-Host "Enter Xiaomi LLM API key for this process only" -AsSecureString
    $plainKey = Convert-SecureStringToPlainText -SecureValue $secureKey
    if ([string]::IsNullOrWhiteSpace($plainKey)) {
      throw "XIAOMI_LLM_API_KEY is empty"
    }
    [Environment]::SetEnvironmentVariable($apiKeyEnv, $plainKey, "Process")
    $keyInjectedForRun = $true
  } else {
    Write-Host "[xiaomi_llm_preflight] input=existing_process_env" -ForegroundColor Cyan
  }

  Write-Host "[xiaomi_llm_preflight] status=running" -ForegroundColor Yellow
  Invoke-ResolvedPython @(
    (Join-Path $repoRoot "scripts/production_landing_xiaomi_llm_preflight_runner.py"),
    "--execute-network-check",
    "--timeout-seconds",
    "$TimeoutSeconds"
  )
  $exitCode = $LASTEXITCODE
  if ($exitCode -ne 0) {
    throw "production_landing_xiaomi_llm_preflight_runner.py failed with exit code $exitCode"
  }
  Write-Host "[xiaomi_llm_preflight] status=done" -ForegroundColor Green
} finally {
  if ($keyInjectedForRun) {
    if ($hadPreviousValue) {
      [Environment]::SetEnvironmentVariable($apiKeyEnv, $previousValue, "Process")
    } else {
      [Environment]::SetEnvironmentVariable($apiKeyEnv, $null, "Process")
    }
    Write-Host "[xiaomi_llm_preflight] process_env_restored=true" -ForegroundColor Cyan
  }
}
