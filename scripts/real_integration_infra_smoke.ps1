Param(
  [string[]]$Domains = @("postgres", "redis", "external_mcp"),
  [switch]$UseExistingEnv,
  [switch]$CheckPythonOnly,
  [int]$TimeoutSeconds = 10,
  [string]$McpServerCommand = "",
  [string]$McpServerArgs = "",
  [string]$McpServerCommandAllowlist = "",
  [string]$McpToolAllowlist = "",
  [string]$McpServerEnvAllowlist = "",
  [string]$McpServerWorkdir = "",
  [string]$EnvPath = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$secretEnvKeys = @("DATABASE_URL", "REDIS_URL")
$previousSecretEnv = @{}
$hadSecretEnv = @{}
$valuesInjectedForRun = $false
$envPathLoadedForRun = $false
$previousEnvPathEnv = @{}
$hadPreviousEnvPathEnv = @{}
$envPathLoadedKeys = New-Object System.Collections.Generic.List[string]
$envPathSafeKeys = @(
  "REAL_INTEGRATION_STAGING_SMOKE_ENABLED",
  "POSTGRES_STAGING_SMOKE_EXECUTE",
  "STORAGE_BACKEND",
  "REDIS_STAGING_SMOKE_EXECUTE",
  "REDIS_ENABLED",
  "RATE_LIMIT_BACKEND",
  "MCP_STAGING_SMOKE_EXECUTE",
  "MCP_MODE",
  "MCP_SERVER_COMMAND",
  "MCP_SERVER_ARGS",
  "MCP_SERVER_COMMAND_ALLOWLIST",
  "MCP_TOOL_ALLOWLIST",
  "MCP_SERVER_ENV_ALLOWLIST",
  "MCP_SERVER_WORKDIR",
  "MCP_SERVER_TIMEOUT_SECONDS"
)
$envPathSecretKeys = @(
  "DATABASE_URL",
  "REDIS_URL",
  "REAL_LLM_API_KEY",
  "XIAOMI_LLM_API_KEY",
  "OPENAI_API_KEY",
  "JWT_SECRET"
)
$envPathLoadableSecretKeys = @(
  "DATABASE_URL",
  "REDIS_URL"
)

foreach ($key in $secretEnvKeys) {
  $value = [Environment]::GetEnvironmentVariable($key, "Process")
  $previousSecretEnv[$key] = $value
  $hadSecretEnv[$key] = -not [string]::IsNullOrWhiteSpace($value)
}

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

function Read-SecretEnvValue {
  param([Parameter(Mandatory = $true)][string]$EnvName)

  $secureValue = Read-Host "Enter $EnvName for this process only" -AsSecureString
  $plainValue = Convert-SecureStringToPlainText -SecureValue $secureValue
  if ([string]::IsNullOrWhiteSpace($plainValue)) {
    throw "$EnvName is empty"
  }
  return $plainValue
}

function Assert-NonSecretConfigText {
  param(
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Value
  )

  if ($Value -match '(?i)(token|api[_-]?key|secret|password)\s*[:=]') {
    throw "$Name looks like a secret; pass only allowlisted command/tool metadata"
  }
}

function Set-OptionalProcessEnv {
  param(
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Value
  )

  if (-not [string]::IsNullOrWhiteSpace($Value)) {
    Assert-NonSecretConfigText -Name $Name -Value $Value
    [Environment]::SetEnvironmentVariable($Name, $Value, "Process")
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

function Import-InfraEnvPath {
  param([Parameter(Mandatory = $true)][string]$Path)

  if ([string]::IsNullOrWhiteSpace($Path)) {
    return @{ loaded_safe = 0; loaded_secret = 0; skipped_secret = 0 }
  }
  $resolvedPath = Resolve-Path -LiteralPath $Path -ErrorAction Stop
  $loadedSafe = 0
  $loadedSecret = 0
  $skippedSecret = 0
  foreach ($rawLine in [System.IO.File]::ReadLines($resolvedPath.Path, [System.Text.UTF8Encoding]::new($false))) {
    $line = $rawLine.Trim()
    if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith("#") -or -not $line.Contains("=")) {
      continue
    }
    $parts = $line.Split("=", 2)
    $key = $parts[0].Trim()
    $value = $parts[1].Trim().Trim('"').Trim("'")
    if ($envPathSafeKeys -contains $key) {
      Assert-NonSecretConfigText -Name $key -Value $value
      Set-EnvPathProcessValue -Name $key -Value $value
      $loadedSafe += 1
      continue
    }
    if ($envPathSecretKeys -contains $key) {
      if (($envPathLoadableSecretKeys -contains $key) -and -not [string]::IsNullOrWhiteSpace($value)) {
        Set-EnvPathProcessValue -Name $key -Value $value
        $loadedSecret += 1
      } else {
        $skippedSecret += 1
      }
    }
  }
  return @{ loaded_safe = $loadedSafe; loaded_secret = $loadedSecret; skipped_secret = $skippedSecret }
}

function Resolve-InfraDomains {
  param([Parameter(Mandatory = $true)][string[]]$RawDomains)

  $allowedDomains = @("postgres", "redis", "external_mcp")
  $normalized = New-Object System.Collections.Generic.List[string]
  foreach ($rawDomain in $RawDomains) {
    foreach ($candidate in ([string]$rawDomain).Split(",")) {
      $domain = $candidate.Trim()
      if ([string]::IsNullOrWhiteSpace($domain)) {
        continue
      }
      if ($allowedDomains -notcontains $domain) {
        throw "Unsupported infra smoke domain: $domain"
      }
      if (-not $normalized.Contains($domain)) {
        [void]$normalized.Add($domain)
      }
    }
  }
  if ($normalized.Count -eq 0) {
    throw "At least one infra smoke domain is required"
  }
  return @($normalized)
}

if ($CheckPythonOnly) {
  Initialize-CodexProcessEnvironment
  [string[]]$pythonCommand = @(Resolve-PythonExecutable)
  Write-Host "[real_integration_infra_smoke] python=$($pythonCommand[0])" -ForegroundColor Cyan
  exit 0
}

try {
  Initialize-CodexProcessEnvironment

  if (-not [string]::IsNullOrWhiteSpace($EnvPath)) {
    $envPathSummary = Import-InfraEnvPath -Path $EnvPath
    $envPathLoadedForRun = $true
    if ([int]$envPathSummary.loaded_secret -gt 0) {
      $valuesInjectedForRun = $true
    }
    Write-Host "[real_integration_infra_smoke] env_path_loaded_safe_count=$($envPathSummary.loaded_safe)" -ForegroundColor Cyan
    Write-Host "[real_integration_infra_smoke] env_path_loaded_secret_count=$($envPathSummary.loaded_secret)" -ForegroundColor Cyan
    Write-Host "[real_integration_infra_smoke] env_path_skipped_secret_count=$($envPathSummary.skipped_secret)" -ForegroundColor Cyan
  }

  $selectedDomains = @(Resolve-InfraDomains -RawDomains $Domains)
  $domainArg = [string]::Join(",", $selectedDomains)
  Write-Host "[real_integration_infra_smoke] mode=controlled_real_infra_smoke" -ForegroundColor Cyan
  Write-Host "[real_integration_infra_smoke] domains=$domainArg" -ForegroundColor Cyan
  Write-Host "[real_integration_infra_smoke] input=secure_process_env_only" -ForegroundColor Cyan
  Write-Host "[real_integration_infra_smoke] secret_will_not_be_written_to_repo_or_report" -ForegroundColor Cyan
  Write-Host "[real_integration_infra_smoke] public_production_direct_launch=No-Go" -ForegroundColor Cyan

  [Environment]::SetEnvironmentVariable("REAL_INTEGRATION_STAGING_SMOKE_ENABLED", "true", "Process")

  if ($selectedDomains -contains "postgres") {
    [Environment]::SetEnvironmentVariable("POSTGRES_STAGING_SMOKE_EXECUTE", "true", "Process")
    [Environment]::SetEnvironmentVariable("STORAGE_BACKEND", "postgres", "Process")
    $currentDatabaseUrl = [Environment]::GetEnvironmentVariable("DATABASE_URL", "Process")
    if (-not $UseExistingEnv -or [string]::IsNullOrWhiteSpace($currentDatabaseUrl)) {
      [Environment]::SetEnvironmentVariable("DATABASE_URL", (Read-SecretEnvValue -EnvName "DATABASE_URL"), "Process")
      $valuesInjectedForRun = $true
    }
  }

  if ($selectedDomains -contains "redis") {
    [Environment]::SetEnvironmentVariable("REDIS_STAGING_SMOKE_EXECUTE", "true", "Process")
    [Environment]::SetEnvironmentVariable("REDIS_ENABLED", "true", "Process")
    [Environment]::SetEnvironmentVariable("RATE_LIMIT_BACKEND", "redis", "Process")
    $currentRedisUrl = [Environment]::GetEnvironmentVariable("REDIS_URL", "Process")
    if (-not $UseExistingEnv -or [string]::IsNullOrWhiteSpace($currentRedisUrl)) {
      [Environment]::SetEnvironmentVariable("REDIS_URL", (Read-SecretEnvValue -EnvName "REDIS_URL"), "Process")
      $valuesInjectedForRun = $true
    }
  }

  if ($selectedDomains -contains "external_mcp") {
    [Environment]::SetEnvironmentVariable("MCP_STAGING_SMOKE_EXECUTE", "true", "Process")
    [Environment]::SetEnvironmentVariable("MCP_MODE", "real", "Process")
    Set-OptionalProcessEnv -Name "MCP_SERVER_COMMAND" -Value $McpServerCommand
    Set-OptionalProcessEnv -Name "MCP_SERVER_ARGS" -Value $McpServerArgs
    Set-OptionalProcessEnv -Name "MCP_SERVER_COMMAND_ALLOWLIST" -Value $McpServerCommandAllowlist
    Set-OptionalProcessEnv -Name "MCP_TOOL_ALLOWLIST" -Value $McpToolAllowlist
    Set-OptionalProcessEnv -Name "MCP_SERVER_ENV_ALLOWLIST" -Value $McpServerEnvAllowlist
    Set-OptionalProcessEnv -Name "MCP_SERVER_WORKDIR" -Value $McpServerWorkdir
    [Environment]::SetEnvironmentVariable("MCP_SERVER_TIMEOUT_SECONDS", "$TimeoutSeconds", "Process")
  }

  Write-Host "[real_integration_infra_smoke] status=running" -ForegroundColor Yellow
  Invoke-ResolvedPython @(
    (Join-Path $repoRoot "scripts/real_integration_staging_smoke.py"),
    "--execute",
    "--domains",
    $domainArg
  )
  $exitCode = $LASTEXITCODE
  if ($exitCode -ne 0) {
    throw "real_integration_staging_smoke.py failed with exit code $exitCode"
  }
  Write-Host "[real_integration_infra_smoke] status=done" -ForegroundColor Green
} finally {
  if ($valuesInjectedForRun) {
    foreach ($key in $secretEnvKeys) {
      if ($hadSecretEnv[$key]) {
        [Environment]::SetEnvironmentVariable($key, $previousSecretEnv[$key], "Process")
      } else {
        [Environment]::SetEnvironmentVariable($key, $null, "Process")
      }
    }
    Write-Host "[real_integration_infra_smoke] process_env_restored=true" -ForegroundColor Cyan
  }
  if ($envPathLoadedForRun) {
    foreach ($envName in $envPathLoadedKeys) {
      if ($hadPreviousEnvPathEnv[$envName]) {
        [Environment]::SetEnvironmentVariable($envName, $previousEnvPathEnv[$envName], "Process")
      } else {
        [Environment]::SetEnvironmentVariable($envName, $null, "Process")
      }
    }
    Write-Host "[real_integration_infra_smoke] env_path_process_env_restored=true" -ForegroundColor Cyan
  }
}
