Param(
  [string]$SignoffRecord = "docs/reports/manual_signoff_package/manual_signoff_record.draft.json",
  [string]$AckStatusReport = "",
  [int]$TimeoutSeconds = 120,
  [switch]$CheckPythonOnly
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

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
  $exitCode = $LASTEXITCODE
  if ($exitCode -ne 0) {
    throw "python command failed with exit code $exitCode"
  }
}

function Read-RequiredText {
  param([Parameter(Mandatory = $true)][string]$Prompt)

  $value = (Read-Host $Prompt).Trim()
  if ([string]::IsNullOrWhiteSpace($value)) {
    throw "$Prompt is required"
  }
  if ($value -match '(?i)(token|api[_-]?key|secret|password)\s*[:=]' -or $value -match 'sk-[A-Za-z0-9_\-]{6,}' -or $value -match 'tp-[A-Za-z0-9_\-]{16,}') {
    throw "$Prompt looks like a secret; enter only a person name or staff id"
  }
  return $value
}

function Read-Confirmation {
  param([Parameter(Mandatory = $true)][string]$Prompt)

  $value = (Read-Host "$Prompt Type YES to confirm").Trim()
  if ($value -ne "YES") {
    throw "$Prompt was not confirmed"
  }
}

if ($CheckPythonOnly) {
  [string[]]$pythonCommand = @(Resolve-PythonExecutable)
  Write-Host "[manual_signoff_record_fill] python=$($pythonCommand[0])" -ForegroundColor Cyan
  exit 0
}

Write-Host "[manual_signoff_record_fill] explicit_manual_signoff_required=true" -ForegroundColor Cyan
Write-Host "[manual_signoff_record_fill] do_not_enter_tokens_or_connection_strings=true" -ForegroundColor Cyan

$releaseManager = Read-RequiredText "release_manager name or staff id"
$securityReviewer = Read-RequiredText "security_reviewer name or staff id"
$businessOwner = Read-RequiredText "business_owner name or staff id"
$operationsOwner = Read-RequiredText "operations_owner name or staff id"
Read-Confirmation "Confirm manual review of all recommended evidence"
Read-Confirmation "Confirm controlled pilot Go while public production direct launch remains No-Go"

$arguments = @(
  (Join-Path $repoRoot "scripts/manual_signoff_record_fill.py"),
  "--signoff-record",
  $SignoffRecord,
  "--release-manager",
  $releaseManager,
  "--security-reviewer",
  $securityReviewer,
  "--business-owner",
  $businessOwner,
  "--operations-owner",
  $operationsOwner,
  "--confirm-manual-signoff",
  "--confirm-controlled-pilot-go"
)

if (-not [string]::IsNullOrWhiteSpace($AckStatusReport)) {
  $arguments += @("--ack-status-report", $AckStatusReport)
}

Invoke-ResolvedPython $arguments
Write-Host "[manual_signoff_record_fill] status=done" -ForegroundColor Green
