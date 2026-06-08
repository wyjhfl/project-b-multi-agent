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
  [string]$EnvPath = "",
  [switch]$PreflightOnly,
  [switch]$SkipReadinessBrief,
  [switch]$SkipLandingResume
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
$envPathSafeKeys = @(
  "BUSINESS_INTEGRATION_ENABLED",
  "BUSINESS_INTEGRATION_READ_ONLY",
  "BUSINESS_INTEGRATION_WRITE_ENABLED",
  "BUSINESS_INTEGRATION_APPROVAL_REQUIRED",
  "BUSINESS_INTEGRATION_AUDIT_REQUIRED",
  "BUSINESS_SYSTEM_NAME",
  "BUSINESS_SYSTEM_BASE_URL_ENV",
  "BUSINESS_SYSTEM_TOKEN_ENV",
  "BUSINESS_SYSTEM_TOOL_ALLOWLIST",
  "BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST",
  "BUSINESS_SYSTEM_TIMEOUT_SECONDS",
  "BUSINESS_SYSTEM_READ_PROBE_PATH",
  "BUSINESS_SYSTEM_AUTH_HEADER_NAME",
  "BUSINESS_SYSTEM_AUTH_SCHEME",
  "BUSINESS_SYSTEM_BUSINESS_OWNER",
  "BUSINESS_SYSTEM_SECURITY_REVIEWER",
  "BUSINESS_SYSTEM_OPERATIONS_OWNER",
  "BUSINESS_SYSTEM_DATA_OWNER"
)
$envPathSecretKeys = @(
  "BUSINESS_SYSTEM_BASE_URL",
  "BUSINESS_SYSTEM_TOKEN",
  "DATABASE_URL",
  "REDIS_URL",
  "XIAOMI_LLM_API_KEY",
  "JWT_SECRET"
)
$previousOwnerEnv = @{}
$hadPreviousOwnerEnv = @{}
foreach ($ownerEnvName in $ownerEnvNames) {
  $previousOwnerEnv[$ownerEnvName] = [Environment]::GetEnvironmentVariable($ownerEnvName, "Process")
  $hadPreviousOwnerEnv[$ownerEnvName] = -not [string]::IsNullOrWhiteSpace($previousOwnerEnv[$ownerEnvName])
}
$previousEnvPathEnv = @{}
$hadPreviousEnvPathEnv = @{}
$envPathLoadedKeys = New-Object System.Collections.Generic.List[string]
$valuesInjectedForRun = $false
$ownerValuesInjectedForRun = $false
$envPathLoadedForRun = $false

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

function Invoke-ResolvedPythonCapture {
  param([Parameter(Mandatory = $true)][string[]]$Arguments)

  [string[]]$pythonCommand = @(Resolve-PythonExecutable)
  if ($pythonCommand.Count -gt 1) {
    $output = & $pythonCommand[0] $pythonCommand[1..($pythonCommand.Count - 1)] $Arguments 2>&1
  } else {
    $output = & $pythonCommand[0] $Arguments 2>&1
  }
  foreach ($line in $output) {
    Write-Host $line
  }
  return @($output)
}

function Get-JsonPathFromOutput {
  param([Parameter(Mandatory = $true)][object[]]$OutputLines)

  $jsonPath = ""
  foreach ($line in $OutputLines) {
    $text = [string]$line
    if ($text.StartsWith("json_path=")) {
      $jsonPath = $text.Substring("json_path=".Length).Trim()
    }
  }
  return $jsonPath
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

function Set-EnvPathProcessValue {
  param(
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Value
  )

  if (-not $previousEnvPathEnv.ContainsKey($Name)) {
    $previousEnvPathEnv[$Name] = [Environment]::GetEnvironmentVariable($Name, "Process")
    $hadPreviousEnvPathEnv[$Name] = -not [string]::IsNullOrWhiteSpace($previousEnvPathEnv[$Name])
    [void]$envPathLoadedKeys.Add($Name)
  }
  [Environment]::SetEnvironmentVariable($Name, $Value, "Process")
}

function Import-BusinessEnvPath {
  param([Parameter(Mandatory = $true)][string]$Path)

  if ([string]::IsNullOrWhiteSpace($Path)) {
    return @{ loaded = 0; skipped_secret = 0 }
  }
  $resolvedPath = Resolve-Path -LiteralPath $Path -ErrorAction Stop
  $loaded = 0
  $skippedSecret = 0
  foreach ($rawLine in [System.IO.File]::ReadLines($resolvedPath.Path, [System.Text.UTF8Encoding]::new($false))) {
    $line = $rawLine.Trim()
    if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith("#") -or -not $line.Contains("=")) {
      continue
    }
    $parts = $line.Split("=", 2)
    $key = $parts[0].Trim()
    $value = $parts[1].Trim().Trim('"').Trim("'")
    if ($envPathSecretKeys -contains $key) {
      $skippedSecret += 1
      continue
    }
    if ($envPathSafeKeys -contains $key) {
      Set-EnvPathProcessValue -Name $key -Value $value
      $loaded += 1
    }
  }
  return @{ loaded = $loaded; skipped_secret = $skippedSecret }
}

function Read-CurrentEnvValue {
  param(
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][string]$Fallback
  )

  $value = [Environment]::GetEnvironmentVariable($Name, "Process")
  if ([string]::IsNullOrWhiteSpace($value)) {
    return $Fallback
  }
  return $value.Trim()
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

function Set-OwnerValueIfPresent {
  param(
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Value
  )

  if ([string]::IsNullOrWhiteSpace($Value)) {
    return $false
  }
  Assert-OwnerValue -Name $Name -Value $Value
  [Environment]::SetEnvironmentVariable($Name, $Value.Trim(), "Process")
  return $true
}

function Test-AutomationEnvironment {
  $automationEnvNames = @(
    "CI",
    "GITHUB_ACTIONS",
    "TF_BUILD",
    "BUILD_BUILDID",
    "JENKINS_URL"
  )
  foreach ($name in $automationEnvNames) {
    $value = [Environment]::GetEnvironmentVariable($name, "Process")
    if (-not [string]::IsNullOrWhiteSpace($value) -and $value -ne "false" -and $value -ne "0") {
      return $true
    }
  }
  return $false
}

if ($CheckPythonOnly) {
  Initialize-CodexProcessEnvironment
  [string[]]$pythonCommand = @(Resolve-PythonExecutable)
  Write-Host "[business_system_read_smoke] python=$($pythonCommand[0])" -ForegroundColor Cyan
  exit 0
}

try {
  Initialize-CodexProcessEnvironment

  if (-not [string]::IsNullOrWhiteSpace($EnvPath)) {
    $envPathSummary = Import-BusinessEnvPath -Path $EnvPath
    $envPathLoadedForRun = $true
    Write-Host "[business_system_read_smoke] env_path_loaded_keys=$($envPathSummary.loaded)" -ForegroundColor Cyan
    Write-Host "[business_system_read_smoke] env_path_secret_keys_skipped=$($envPathSummary.skipped_secret)" -ForegroundColor Cyan
  }

  $effectiveTimeoutSeconds = $TimeoutSeconds
  if (-not $PSBoundParameters.ContainsKey("TimeoutSeconds")) {
    $timeoutFromEnv = [Environment]::GetEnvironmentVariable("BUSINESS_SYSTEM_TIMEOUT_SECONDS", "Process")
    if (-not [string]::IsNullOrWhiteSpace($timeoutFromEnv)) {
      $parsedTimeout = 0
      if ([int]::TryParse($timeoutFromEnv, [ref]$parsedTimeout) -and $parsedTimeout -gt 0) {
        $effectiveTimeoutSeconds = $parsedTimeout
      }
    }
  }
  $effectiveReadProbePath = if ($PSBoundParameters.ContainsKey("ReadProbePath")) { $ReadProbePath } else { Read-CurrentEnvValue -Name "BUSINESS_SYSTEM_READ_PROBE_PATH" -Fallback $ReadProbePath }
  $effectiveAuthHeaderName = if ($PSBoundParameters.ContainsKey("AuthHeaderName")) { $AuthHeaderName } else { Read-CurrentEnvValue -Name "BUSINESS_SYSTEM_AUTH_HEADER_NAME" -Fallback $AuthHeaderName }
  $effectiveAuthScheme = if ($PSBoundParameters.ContainsKey("AuthScheme")) { $AuthScheme } else { Read-CurrentEnvValue -Name "BUSINESS_SYSTEM_AUTH_SCHEME" -Fallback $AuthScheme }

  Assert-HeaderName -Value $effectiveAuthHeaderName

  Write-Host "[business_system_read_smoke] mode=real_business_read_only_smoke" -ForegroundColor Cyan
  Write-Host "[business_system_read_smoke] input=secure_process_env_only" -ForegroundColor Cyan
  Write-Host "[business_system_read_smoke] secret_will_not_be_written_to_repo_or_report" -ForegroundColor Cyan
  Write-Host "[business_system_read_smoke] public_production_direct_launch=No-Go" -ForegroundColor Cyan

  if ($PreflightOnly) {
    Write-Host "[business_system_read_smoke] preflight_only=true" -ForegroundColor Cyan

    $ownerValuesInjectedForRun = $false
    $ownerValuesInjectedForRun = (Set-OwnerValueIfPresent -Name "BUSINESS_SYSTEM_BUSINESS_OWNER" -Value ($(if (-not [string]::IsNullOrWhiteSpace($BusinessOwner)) { $BusinessOwner } else { [Environment]::GetEnvironmentVariable("BUSINESS_SYSTEM_BUSINESS_OWNER", "Process") }))) -or $ownerValuesInjectedForRun
    $ownerValuesInjectedForRun = (Set-OwnerValueIfPresent -Name "BUSINESS_SYSTEM_SECURITY_REVIEWER" -Value ($(if (-not [string]::IsNullOrWhiteSpace($SecurityReviewer)) { $SecurityReviewer } else { [Environment]::GetEnvironmentVariable("BUSINESS_SYSTEM_SECURITY_REVIEWER", "Process") }))) -or $ownerValuesInjectedForRun
    $ownerValuesInjectedForRun = (Set-OwnerValueIfPresent -Name "BUSINESS_SYSTEM_OPERATIONS_OWNER" -Value ($(if (-not [string]::IsNullOrWhiteSpace($OperationsOwner)) { $OperationsOwner } else { [Environment]::GetEnvironmentVariable("BUSINESS_SYSTEM_OPERATIONS_OWNER", "Process") }))) -or $ownerValuesInjectedForRun
    $ownerValuesInjectedForRun = (Set-OwnerValueIfPresent -Name "BUSINESS_SYSTEM_DATA_OWNER" -Value ($(if (-not [string]::IsNullOrWhiteSpace($DataOwner)) { $DataOwner } else { [Environment]::GetEnvironmentVariable("BUSINESS_SYSTEM_DATA_OWNER", "Process") }))) -or $ownerValuesInjectedForRun

    [Environment]::SetEnvironmentVariable("BUSINESS_INTEGRATION_ENABLED", "true", "Process")
    [Environment]::SetEnvironmentVariable("BUSINESS_INTEGRATION_READ_ONLY", "true", "Process")
    [Environment]::SetEnvironmentVariable("BUSINESS_INTEGRATION_WRITE_ENABLED", "false", "Process")
    [Environment]::SetEnvironmentVariable("BUSINESS_INTEGRATION_APPROVAL_REQUIRED", "true", "Process")
    [Environment]::SetEnvironmentVariable("BUSINESS_INTEGRATION_AUDIT_REQUIRED", "true", "Process")
    [Environment]::SetEnvironmentVariable("BUSINESS_SYSTEM_BASE_URL_ENV", $baseUrlEnv, "Process")
    [Environment]::SetEnvironmentVariable("BUSINESS_SYSTEM_TOKEN_ENV", $tokenEnv, "Process")
    [Environment]::SetEnvironmentVariable("BUSINESS_SYSTEM_TOOL_ALLOWLIST", "business_read_probe", "Process")
    [Environment]::SetEnvironmentVariable("BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST", "", "Process")
    [Environment]::SetEnvironmentVariable("BUSINESS_SYSTEM_TIMEOUT_SECONDS", "$effectiveTimeoutSeconds", "Process")
    [Environment]::SetEnvironmentVariable("BUSINESS_SYSTEM_READ_PROBE_PATH", $effectiveReadProbePath, "Process")
    [Environment]::SetEnvironmentVariable("BUSINESS_SYSTEM_AUTH_HEADER_NAME", $effectiveAuthHeaderName, "Process")
    [Environment]::SetEnvironmentVariable("BUSINESS_SYSTEM_AUTH_SCHEME", $effectiveAuthScheme, "Process")

    Write-Host "[business_system_read_smoke] preflight=input_packet" -ForegroundColor Yellow
    $inputPacketArguments = @((Join-Path $repoRoot "scripts/business_system_input_packet.py"))
    if (-not [string]::IsNullOrWhiteSpace($EnvPath)) {
      $inputPacketArguments += @("--env-path", $EnvPath)
    }
    Invoke-ResolvedPython @($inputPacketArguments)
    $preflightExitCode = $LASTEXITCODE
    if ($preflightExitCode -ne 0) {
      throw "business_system_input_packet.py failed with exit code $preflightExitCode"
    }
    Write-Host "[business_system_read_smoke] preflight=done" -ForegroundColor Green
    return
  }

  if (Test-AutomationEnvironment) {
    throw "Real business read smoke is blocked in CI or automation environments. Run -PreflightOnly there, then execute the real smoke from an explicit operator session."
  }

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

  $effectiveBusinessOwner = Read-OrUseOwnerValue -Prompt "business_owner name or staff id" -CurrentValue ($(if (-not [string]::IsNullOrWhiteSpace($BusinessOwner)) { $BusinessOwner } else { [Environment]::GetEnvironmentVariable("BUSINESS_SYSTEM_BUSINESS_OWNER", "Process") }))
  $effectiveSecurityReviewer = Read-OrUseOwnerValue -Prompt "security_reviewer name or staff id" -CurrentValue ($(if (-not [string]::IsNullOrWhiteSpace($SecurityReviewer)) { $SecurityReviewer } else { [Environment]::GetEnvironmentVariable("BUSINESS_SYSTEM_SECURITY_REVIEWER", "Process") }))
  $effectiveOperationsOwner = Read-OrUseOwnerValue -Prompt "operations_owner name or staff id" -CurrentValue ($(if (-not [string]::IsNullOrWhiteSpace($OperationsOwner)) { $OperationsOwner } else { [Environment]::GetEnvironmentVariable("BUSINESS_SYSTEM_OPERATIONS_OWNER", "Process") }))
  $effectiveDataOwner = Read-OrUseOwnerValue -Prompt "data_owner name or staff id" -CurrentValue ($(if (-not [string]::IsNullOrWhiteSpace($DataOwner)) { $DataOwner } else { [Environment]::GetEnvironmentVariable("BUSINESS_SYSTEM_DATA_OWNER", "Process") }))
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
  [Environment]::SetEnvironmentVariable("BUSINESS_SYSTEM_TIMEOUT_SECONDS", "$effectiveTimeoutSeconds", "Process")
  [Environment]::SetEnvironmentVariable("BUSINESS_SYSTEM_READ_PROBE_PATH", $effectiveReadProbePath, "Process")
  [Environment]::SetEnvironmentVariable("BUSINESS_SYSTEM_AUTH_HEADER_NAME", $effectiveAuthHeaderName, "Process")
  [Environment]::SetEnvironmentVariable("BUSINESS_SYSTEM_AUTH_SCHEME", $effectiveAuthScheme, "Process")

  Write-Host "[business_system_read_smoke] status=running" -ForegroundColor Yellow
  $smokeOutput = Invoke-ResolvedPythonCapture @(
    (Join-Path $repoRoot "scripts/business_system_read_smoke.py"),
    "--execute"
  )
  $exitCode = $LASTEXITCODE
  if ($exitCode -ne 0) {
    throw "business_system_read_smoke.py failed with exit code $exitCode"
  }
  $businessReadSmokeJsonPath = Get-JsonPathFromOutput -OutputLines $smokeOutput
  if ([string]::IsNullOrWhiteSpace($businessReadSmokeJsonPath)) {
    throw "business_system_read_smoke.py did not emit json_path"
  }
  if (-not $SkipReadinessBrief) {
    Write-Host "[business_system_read_smoke] input_packet=running" -ForegroundColor Yellow
    $inputPacketOutput = Invoke-ResolvedPythonCapture @(
      (Join-Path $repoRoot "scripts/business_system_input_packet.py")
    )
    $inputPacketExitCode = $LASTEXITCODE
    if ($inputPacketExitCode -ne 0) {
      throw "business_system_input_packet.py failed with exit code $inputPacketExitCode"
    }
    $businessInputPacketJsonPath = Get-JsonPathFromOutput -OutputLines $inputPacketOutput
    if ([string]::IsNullOrWhiteSpace($businessInputPacketJsonPath)) {
      throw "business_system_input_packet.py did not emit json_path"
    }
    Write-Host "[business_system_read_smoke] input_packet=done" -ForegroundColor Green

    Write-Host "[business_system_read_smoke] readiness_brief=running" -ForegroundColor Yellow
    $readinessArguments = @(
      (Join-Path $repoRoot "scripts/business_system_production_readiness_brief.py"),
      "--business-smoke-json-path",
      $businessReadSmokeJsonPath
    )
    if (-not [string]::IsNullOrWhiteSpace($EnvPath)) {
      $readinessArguments += @("--env-path", $EnvPath)
    }
    $readinessOutput = Invoke-ResolvedPythonCapture $readinessArguments
    $readinessExitCode = $LASTEXITCODE
    if ($readinessExitCode -ne 0) {
      throw "business_system_production_readiness_brief.py failed with exit code $readinessExitCode"
    }
    $businessReadinessJsonPath = Get-JsonPathFromOutput -OutputLines $readinessOutput
    if ([string]::IsNullOrWhiteSpace($businessReadinessJsonPath)) {
      throw "business_system_production_readiness_brief.py did not emit json_path"
    }
    Write-Host "[business_system_read_smoke] readiness_brief=done" -ForegroundColor Green

    Write-Host "[business_system_read_smoke] execution_pack=running" -ForegroundColor Yellow
    Invoke-ResolvedPython @(
      (Join-Path $repoRoot "scripts/business_system_landing_execution_pack.py"),
      "--business-input-packet-json",
      $businessInputPacketJsonPath,
      "--business-readiness-json",
      $businessReadinessJsonPath,
      "--business-read-smoke-json",
      $businessReadSmokeJsonPath
    )
    $executionPackExitCode = $LASTEXITCODE
    if ($executionPackExitCode -ne 0) {
      throw "business_system_landing_execution_pack.py failed with exit code $executionPackExitCode"
    }
    Write-Host "[business_system_read_smoke] execution_pack=done" -ForegroundColor Green
  }
  if (-not $SkipLandingResume) {
    Write-Host "[business_system_read_smoke] landing_resume=running" -ForegroundColor Yellow
    $resumeArguments = @(
      "-NoProfile",
      "-ExecutionPolicy",
      "Bypass",
      "-File",
      (Join-Path $repoRoot "scripts/business_system_landing_resume.ps1"),
      "-UseExistingEnv"
    )
    if (-not $SkipReadinessBrief) {
      $resumeArguments += "-SkipBusinessPreparation"
    }
    if (-not [string]::IsNullOrWhiteSpace($EnvPath)) {
      $resumeArguments += @("-EnvPath", $EnvPath)
    }
    & powershell.exe @resumeArguments
    $resumeExitCode = $LASTEXITCODE
    if ($resumeExitCode -ne 0) {
      throw "business_system_landing_resume.ps1 failed with exit code $resumeExitCode"
    }
    Write-Host "[business_system_read_smoke] landing_resume=done" -ForegroundColor Green
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
  if ($envPathLoadedForRun) {
    foreach ($envName in $envPathLoadedKeys) {
      if ($hadPreviousEnvPathEnv[$envName]) {
        [Environment]::SetEnvironmentVariable($envName, $previousEnvPathEnv[$envName], "Process")
      } else {
        [Environment]::SetEnvironmentVariable($envName, $null, "Process")
      }
    }
    Write-Host "[business_system_read_smoke] env_path_process_env_restored=true" -ForegroundColor Cyan
  }
}
