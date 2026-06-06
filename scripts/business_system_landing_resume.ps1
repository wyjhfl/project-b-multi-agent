Param(
  [switch]$UseExistingEnv,
  [switch]$CheckPythonOnly,
  [switch]$SkipBusinessPreparation,
  [string]$EnvPath = "",
  [string]$BusinessReadSmokeJsonPath = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

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

function Invoke-CheckedPythonCapture {
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
  $exitCode = $LASTEXITCODE
  if ($exitCode -ne 0) {
    throw "python command failed with exit code $exitCode"
  }
  return @($output)
}

function Get-JsonPathFromOutput {
  param(
    [Parameter(Mandatory = $true)][object[]]$OutputLines,
    [Parameter(Mandatory = $true)][string]$ToolName
  )

  $jsonPath = ""
  foreach ($line in $OutputLines) {
    $text = [string]$line
    if ($text.StartsWith("json_path=")) {
      $jsonPath = $text.Substring("json_path=".Length).Trim()
    }
  }
  if ([string]::IsNullOrWhiteSpace($jsonPath)) {
    throw "$ToolName did not emit json_path"
  }
  return $jsonPath
}

if ($CheckPythonOnly) {
  Initialize-CodexProcessEnvironment
  [string[]]$pythonCommand = @(Resolve-PythonExecutable)
  Write-Host "[business_system_landing_resume] python=$($pythonCommand[0])" -ForegroundColor Cyan
  exit 0
}

Initialize-CodexProcessEnvironment
Write-Host "[business_system_landing_resume] do_not_enter_tokens_or_connection_strings=true" -ForegroundColor Cyan
Write-Host "[business_system_landing_resume] input=existing_process_env_only" -ForegroundColor Cyan
Write-Host "[business_system_landing_resume] public_production_direct_launch=No-Go" -ForegroundColor Cyan

if (-not $SkipBusinessPreparation) {
  $businessReadSmokeJsonPath = $BusinessReadSmokeJsonPath.Trim()

  Write-Host "[business_system_landing_resume] step=business-input-packet" -ForegroundColor Yellow
  $inputPacketArguments = @((Join-Path $repoRoot "scripts/business_system_input_packet.py"))
  if (-not [string]::IsNullOrWhiteSpace($EnvPath)) {
    $inputPacketArguments += @("--env-path", $EnvPath)
  }
  $inputPacketOutput = Invoke-CheckedPythonCapture $inputPacketArguments
  $businessInputPacketJsonPath = Get-JsonPathFromOutput -OutputLines $inputPacketOutput -ToolName "business_system_input_packet.py"

  Write-Host "[business_system_landing_resume] step=business-production-readiness" -ForegroundColor Yellow
  $readinessArguments = @((Join-Path $repoRoot "scripts/business_system_production_readiness_brief.py"))
  if (-not [string]::IsNullOrWhiteSpace($businessReadSmokeJsonPath)) {
    $readinessArguments += @("--business-smoke-json-path", $businessReadSmokeJsonPath)
  }
  $readinessOutput = Invoke-CheckedPythonCapture $readinessArguments
  $businessReadinessJsonPath = Get-JsonPathFromOutput -OutputLines $readinessOutput -ToolName "business_system_production_readiness_brief.py"

  Write-Host "[business_system_landing_resume] step=business-execution-pack" -ForegroundColor Yellow
  $executionPackArguments = @(
    (Join-Path $repoRoot "scripts/business_system_landing_execution_pack.py"),
    "--business-input-packet-json",
    $businessInputPacketJsonPath,
    "--business-readiness-json",
    $businessReadinessJsonPath
  )
  if (-not [string]::IsNullOrWhiteSpace($businessReadSmokeJsonPath)) {
    $executionPackArguments += @("--business-read-smoke-json", $businessReadSmokeJsonPath)
  }
  Invoke-CheckedPython $executionPackArguments
}

Write-Host "[business_system_landing_resume] step=production-env-check" -ForegroundColor Yellow
$envCheckArguments = @((Join-Path $repoRoot "scripts/production_landing_env_check.py"))
if (-not [string]::IsNullOrWhiteSpace($EnvPath)) {
  $envCheckArguments += @("--env-path", $EnvPath)
}
Invoke-CheckedPython $envCheckArguments

Write-Host "[business_system_landing_resume] step=production-execution-gate" -ForegroundColor Yellow
$executionGateArguments = @((Join-Path $repoRoot "scripts/production_landing_execution_gate.py"))
if (-not [string]::IsNullOrWhiteSpace($EnvPath)) {
  $executionGateArguments += @("--env-path", $EnvPath)
}
Invoke-CheckedPython $executionGateArguments

Write-Host "[business_system_landing_resume] step=production-landing-status" -ForegroundColor Yellow
Invoke-CheckedPython @((Join-Path $repoRoot "scripts/production_landing_status.py"))

Write-Host "[business_system_landing_resume] step=production-final-verification" -ForegroundColor Yellow
Invoke-CheckedPython @((Join-Path $repoRoot "scripts/production_landing_final_verification.py"))

Write-Host "[business_system_landing_resume] step=production-text-quality" -ForegroundColor Yellow
Invoke-CheckedPython @((Join-Path $repoRoot "scripts/production_landing_text_quality_check.py"))

Write-Host "[business_system_landing_resume] step=controlled-pilot-status-summary-prime" -ForegroundColor Yellow
Invoke-CheckedPython @((Join-Path $repoRoot "scripts/controlled_pilot_status_summary.py"))

Write-Host "[business_system_landing_resume] step=controlled-pilot-operator-packet-prime" -ForegroundColor Yellow
Invoke-CheckedPython @((Join-Path $repoRoot "scripts/controlled_pilot_operator_packet.py"))

Write-Host "[business_system_landing_resume] step=evidence-freshness-prime" -ForegroundColor Yellow
Invoke-CheckedPython @((Join-Path $repoRoot "scripts/production_landing_evidence_freshness.py"))

Write-Host "[business_system_landing_resume] step=controlled-pilot-status-summary" -ForegroundColor Yellow
Invoke-CheckedPython @((Join-Path $repoRoot "scripts/controlled_pilot_status_summary.py"))

Write-Host "[business_system_landing_resume] step=controlled-pilot-operator-packet" -ForegroundColor Yellow
Invoke-CheckedPython @((Join-Path $repoRoot "scripts/controlled_pilot_operator_packet.py"))

Write-Host "[business_system_landing_resume] step=evidence-freshness-final" -ForegroundColor Yellow
Invoke-CheckedPython @((Join-Path $repoRoot "scripts/production_landing_evidence_freshness.py"))

Write-Host "[business_system_landing_resume] status=done" -ForegroundColor Green
