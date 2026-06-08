Param(
  [switch]$UseExistingEnv,
  [switch]$CheckPythonOnly,
  [int]$TimeoutSeconds = 20,
  [string]$ApiKeyEnv = "REAL_LLM_API_KEY",
  [string]$BaseUrl = "http://100.119.206.22:8300/v1",
  [string]$Model = "gpt-5.5",
  [string]$Provider = "litellm",
  [string]$ProviderLabel = "real"
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$previousValue = [Environment]::GetEnvironmentVariable($ApiKeyEnv, "Process")
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

function Assert-SafeEnvName {
  param([Parameter(Mandatory = $true)][string]$Name)
  if ($Name -notmatch '^[A-Z][A-Z0-9_]*$') {
    throw "ApiKeyEnv must be an uppercase environment variable name"
  }
}

function Assert-HttpUrl {
  param([Parameter(Mandatory = $true)][string]$Value)
  if ($Value -notmatch '^https?://') {
    throw "BaseUrl must start with http:// or https://"
  }
}

if ($CheckPythonOnly) {
  Initialize-CodexProcessEnvironment
  [string[]]$pythonCommand = @(Resolve-PythonExecutable)
  Write-Host "[real_llm_preflight] python=$($pythonCommand[0])" -ForegroundColor Cyan
  exit 0
}

try {
  Initialize-CodexProcessEnvironment
  Assert-SafeEnvName -Name $ApiKeyEnv
  Assert-HttpUrl -Value $BaseUrl

  if (-not $UseExistingEnv -or -not $hadPreviousValue) {
    Write-Host "[real_llm_preflight] input=secure_process_env_only" -ForegroundColor Cyan
    Write-Host "[real_llm_preflight] secret_will_not_be_written_to_repo_or_report" -ForegroundColor Cyan
    $secureKey = Read-Host "Enter real LLM API key for this process only" -AsSecureString
    $plainKey = Convert-SecureStringToPlainText -SecureValue $secureKey
    if ([string]::IsNullOrWhiteSpace($plainKey)) {
      throw "$ApiKeyEnv is empty"
    }
    [Environment]::SetEnvironmentVariable($ApiKeyEnv, $plainKey, "Process")
    $keyInjectedForRun = $true
  } else {
    Write-Host "[real_llm_preflight] input=existing_process_env" -ForegroundColor Cyan
  }

  Write-Host "[real_llm_preflight] status=running" -ForegroundColor Yellow
  Invoke-ResolvedPython @(
    (Join-Path $repoRoot "scripts/production_landing_real_llm_preflight_runner.py"),
    "--execute-network-check",
    "--timeout-seconds",
    "$TimeoutSeconds",
    "--provider",
    "$Provider",
    "--model",
    "$Model",
    "--base-url",
    "$BaseUrl",
    "--api-key-env",
    "$ApiKeyEnv",
    "--provider-label",
    "$ProviderLabel"
  )
  $exitCode = $LASTEXITCODE
  if ($exitCode -ne 0) {
    throw "production_landing_real_llm_preflight_runner.py failed with exit code $exitCode"
  }
  Write-Host "[real_llm_preflight] status=done" -ForegroundColor Green
} finally {
  if ($keyInjectedForRun) {
    if ($hadPreviousValue) {
      [Environment]::SetEnvironmentVariable($ApiKeyEnv, $previousValue, "Process")
    } else {
      [Environment]::SetEnvironmentVariable($ApiKeyEnv, $null, "Process")
    }
    Write-Host "[real_llm_preflight] process_env_restored=true" -ForegroundColor Cyan
  }
}
