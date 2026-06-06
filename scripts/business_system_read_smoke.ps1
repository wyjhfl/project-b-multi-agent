Param(
  [switch]$UseExistingEnv,
  [switch]$CheckPythonOnly,
  [int]$TimeoutSeconds = 5,
  [string]$ReadProbePath = "/health",
  [string]$AuthHeaderName = "Authorization",
  [string]$AuthScheme = "Bearer",
  [string]$BusinessOwner = "",
  [string]$SecurityReviewer = "",
  [string]$OperationsOwner = "",
  [string]$DataOwner = "",
  [switch]$SkipReadinessBrief
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$baseUrlEnv = "BUSINESS_SYSTEM_BASE_URL"
$tokenEnv = "BUSINESS_SYSTEM_TOKEN"
$previousBaseUrl = [Environment]::GetEnvironmentVariable($baseUrlEnv, "Process")
$previousToken = [Environment]::GetEnvironmentVariable($tokenEnv, "Process")
$hadPreviousBaseUrl = -not [string]::IsNullOrWhiteSpace($previousBaseUrl)
$hadPreviousToken = -not [string]::IsNullOrWhiteSpace($previousToken)
$ownerEnvNames = @(
  "BUSINESS_SYSTEM_BUSINESS_OWNER",
  "BUSINESS_SYSTEM_SECURITY_REVIEWER",
  "BUSINESS_SYSTEM_OPERATIONS_OWNER",
  "BUSINESS_SYSTEM_DATA_OWNER"
)
$previousOwnerEnv = @{}
$hadPreviousOwnerEnv = @{}
foreach ($ownerEnvName in $ownerEnvNames) {
  $previousOwnerEnv[$ownerEnvName] = [Environment]::GetEnvironmentVariable($ownerEnvName, "Process")
  $hadPreviousOwnerEnv[$ownerEnvName] = -not [string]::IsNullOrWhiteSpace($previousOwnerEnv[$ownerEnvName])
}
$valuesInjectedForRun = $false
$ownerValuesInjectedForRun = $false

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

function Assert-HttpUrl {
  param([Parameter(Mandatory = $true)][string]$Value)

  if ($Value -notmatch '^https?://') {
    throw "BUSINESS_SYSTEM_BASE_URL must start with http:// or https://"
  }
  if ($Value -match '(?i)(token|api[_-]?key|secret|password)\s*[:=]') {
    throw "BUSINESS_SYSTEM_BASE_URL looks like a secret; enter only the base URL"
  }
}

function Assert-HeaderName {
  param([Parameter(Mandatory = $true)][string]$Value)

  if ($Value -notmatch '^[A-Za-z0-9-]+$') {
    throw "BUSINESS_SYSTEM_AUTH_HEADER_NAME must contain only letters, numbers, or hyphen"
  }
  if ($Value -match '(?i)(token|api[_-]?key|secret|password)\s*[:=]') {
    throw "BUSINESS_SYSTEM_AUTH_HEADER_NAME looks like a secret"
  }
}

function Assert-OwnerValue {
  param(
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][string]$Value
  )

  if ([string]::IsNullOrWhiteSpace($Value)) {
    throw "$Name is empty"
  }
  if ($Value -match '(?i)(token|api[_-]?key|secret|password)\s*[:=]') {
    throw "$Name looks like a secret; enter only a name or staff id"
  }
}

function Read-OrUseOwnerValue {
  param(
    [Parameter(Mandatory = $true)][string]$Prompt,
    [Parameter(Mandatory = $true)][string]$CurrentValue
  )

  if (-not [string]::IsNullOrWhiteSpace($CurrentValue)) {
    return $CurrentValue.Trim()
  }
  return (Read-Host $Prompt).Trim()
}

if ($CheckPythonOnly) {
  Initialize-CodexProcessEnvironment
  [string[]]$pythonCommand = @(Resolve-PythonExecutable)
  Write-Host "[business_system_read_smoke] python=$($pythonCommand[0])" -ForegroundColor Cyan
  exit 0
}

try {
  Initialize-CodexProcessEnvironment
  Assert-HeaderName -Value $AuthHeaderName

  Write-Host "[business_system_read_smoke] mode=real_business_read_only_smoke" -ForegroundColor Cyan
  Write-Host "[business_system_read_smoke] input=secure_process_env_only" -ForegroundColor Cyan
  Write-Host "[business_system_read_smoke] secret_will_not_be_written_to_repo_or_report" -ForegroundColor Cyan
  Write-Host "[business_system_read_smoke] public_production_direct_launch=No-Go" -ForegroundColor Cyan

  if (-not $UseExistingEnv -or -not ($hadPreviousBaseUrl -and $hadPreviousToken)) {
    $plainBaseUrl = (Read-Host "Enter business system base URL for this process only").Trim()
    if ([string]::IsNullOrWhiteSpace($plainBaseUrl)) {
      throw "BUSINESS_SYSTEM_BASE_URL is empty"
    }
    Assert-HttpUrl -Value $plainBaseUrl

    $secureToken = Read-Host "Enter business system read-only token for this process only" -AsSecureString
    $plainToken = Convert-SecureStringToPlainText -SecureValue $secureToken
    if ([string]::IsNullOrWhiteSpace($plainToken)) {
      throw "BUSINESS_SYSTEM_TOKEN is empty"
    }

    [Environment]::SetEnvironmentVariable($baseUrlEnv, $plainBaseUrl, "Process")
    [Environment]::SetEnvironmentVariable($tokenEnv, $plainToken, "Process")
    $valuesInjectedForRun = $true
  } else {
    Write-Host "[business_system_read_smoke] input=existing_process_env" -ForegroundColor Cyan
  }

  $effectiveBusinessOwner = Read-OrUseOwnerValue -Prompt "business_owner name or staff id" -CurrentValue $BusinessOwner
  $effectiveSecurityReviewer = Read-OrUseOwnerValue -Prompt "security_reviewer name or staff id" -CurrentValue $SecurityReviewer
  $effectiveOperationsOwner = Read-OrUseOwnerValue -Prompt "operations_owner name or staff id" -CurrentValue $OperationsOwner
  $effectiveDataOwner = Read-OrUseOwnerValue -Prompt "data_owner name or staff id" -CurrentValue $DataOwner
  Assert-OwnerValue -Name "BUSINESS_SYSTEM_BUSINESS_OWNER" -Value $effectiveBusinessOwner
  Assert-OwnerValue -Name "BUSINESS_SYSTEM_SECURITY_REVIEWER" -Value $effectiveSecurityReviewer
  Assert-OwnerValue -Name "BUSINESS_SYSTEM_OPERATIONS_OWNER" -Value $effectiveOperationsOwner
  Assert-OwnerValue -Name "BUSINESS_SYSTEM_DATA_OWNER" -Value $effectiveDataOwner
  [Environment]::SetEnvironmentVariable("BUSINESS_SYSTEM_BUSINESS_OWNER", $effectiveBusinessOwner, "Process")
  [Environment]::SetEnvironmentVariable("BUSINESS_SYSTEM_SECURITY_REVIEWER", $effectiveSecurityReviewer, "Process")
  [Environment]::SetEnvironmentVariable("BUSINESS_SYSTEM_OPERATIONS_OWNER", $effectiveOperationsOwner, "Process")
  [Environment]::SetEnvironmentVariable("BUSINESS_SYSTEM_DATA_OWNER", $effectiveDataOwner, "Process")
  $ownerValuesInjectedForRun = $true

  [Environment]::SetEnvironmentVariable("BUSINESS_INTEGRATION_ENABLED", "true", "Process")
  [Environment]::SetEnvironmentVariable("BUSINESS_INTEGRATION_READ_ONLY", "true", "Process")
  [Environment]::SetEnvironmentVariable("BUSINESS_INTEGRATION_WRITE_ENABLED", "false", "Process")
  [Environment]::SetEnvironmentVariable("BUSINESS_INTEGRATION_APPROVAL_REQUIRED", "true", "Process")
  [Environment]::SetEnvironmentVariable("BUSINESS_INTEGRATION_AUDIT_REQUIRED", "true", "Process")
  [Environment]::SetEnvironmentVariable("BUSINESS_SYSTEM_BASE_URL_ENV", $baseUrlEnv, "Process")
  [Environment]::SetEnvironmentVariable("BUSINESS_SYSTEM_TOKEN_ENV", $tokenEnv, "Process")
  [Environment]::SetEnvironmentVariable("BUSINESS_SYSTEM_TOOL_ALLOWLIST", "business_read_probe", "Process")
  [Environment]::SetEnvironmentVariable("BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST", "", "Process")
  [Environment]::SetEnvironmentVariable("BUSINESS_SYSTEM_TIMEOUT_SECONDS", "$TimeoutSeconds", "Process")
  [Environment]::SetEnvironmentVariable("BUSINESS_SYSTEM_READ_PROBE_PATH", $ReadProbePath, "Process")
  [Environment]::SetEnvironmentVariable("BUSINESS_SYSTEM_AUTH_HEADER_NAME", $AuthHeaderName, "Process")
  [Environment]::SetEnvironmentVariable("BUSINESS_SYSTEM_AUTH_SCHEME", $AuthScheme, "Process")

  Write-Host "[business_system_read_smoke] status=running" -ForegroundColor Yellow
  Invoke-ResolvedPython @(
    (Join-Path $repoRoot "scripts/business_system_read_smoke.py"),
    "--execute"
  )
  $exitCode = $LASTEXITCODE
  if ($exitCode -ne 0) {
    throw "business_system_read_smoke.py failed with exit code $exitCode"
  }
  if (-not $SkipReadinessBrief) {
    Write-Host "[business_system_read_smoke] readiness_brief=running" -ForegroundColor Yellow
    Invoke-ResolvedPython @(
      (Join-Path $repoRoot "scripts/business_system_production_readiness_brief.py")
    )
    $readinessExitCode = $LASTEXITCODE
    if ($readinessExitCode -ne 0) {
      throw "business_system_production_readiness_brief.py failed with exit code $readinessExitCode"
    }
    Write-Host "[business_system_read_smoke] readiness_brief=done" -ForegroundColor Green
  }
  Write-Host "[business_system_read_smoke] status=done" -ForegroundColor Green
} finally {
  if ($valuesInjectedForRun) {
    if ($hadPreviousBaseUrl) {
      [Environment]::SetEnvironmentVariable($baseUrlEnv, $previousBaseUrl, "Process")
    } else {
      [Environment]::SetEnvironmentVariable($baseUrlEnv, $null, "Process")
    }
    if ($hadPreviousToken) {
      [Environment]::SetEnvironmentVariable($tokenEnv, $previousToken, "Process")
    } else {
      [Environment]::SetEnvironmentVariable($tokenEnv, $null, "Process")
    }
    Write-Host "[business_system_read_smoke] process_env_restored=true" -ForegroundColor Cyan
  }
  if ($ownerValuesInjectedForRun) {
    foreach ($ownerEnvName in $ownerEnvNames) {
      if ($hadPreviousOwnerEnv[$ownerEnvName]) {
        [Environment]::SetEnvironmentVariable($ownerEnvName, $previousOwnerEnv[$ownerEnvName], "Process")
      } else {
        [Environment]::SetEnvironmentVariable($ownerEnvName, $null, "Process")
      }
    }
    Write-Host "[business_system_read_smoke] owner_process_env_restored=true" -ForegroundColor Cyan
  }
}
