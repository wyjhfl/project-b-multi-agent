Param(
  [string]$SignoffRecord = "docs/reports/manual_signoff_package/manual_signoff_record.draft.json",
  [string]$TargetRecord = "docs/reports/manual_signoff_package/manual_signoff_record.json",
  [string]$AckStatusReport = "",
  [string]$ClosureEvidence = "docs/reports/launch_blocker_closure/closure_evidence.draft.json",
  [switch]$CheckPythonOnly
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

Initialize-CodexProcessEnvironment

if ($CheckPythonOnly) {
  [string[]]$pythonCommand = @(Resolve-PythonExecutable)
  Write-Host "[production_landing_signoff_closeout] python=$($pythonCommand[0])" -ForegroundColor Cyan
  exit 0
}

Write-Host "[production_landing_signoff_closeout] explicit_manual_signoff_required=true" -ForegroundColor Cyan
Write-Host "[production_landing_signoff_closeout] do_not_enter_tokens_or_connection_strings=true" -ForegroundColor Cyan
Write-Host "[production_landing_signoff_closeout] public_production_direct_launch=No-Go" -ForegroundColor Cyan

$releaseManager = Read-RequiredText "release_manager name or staff id"
$securityReviewer = Read-RequiredText "security_reviewer name or staff id"
$businessOwner = Read-RequiredText "business_owner name or staff id"
$operationsOwner = Read-RequiredText "operations_owner name or staff id"
Read-Confirmation "Confirm manual review of all recommended evidence"
Read-Confirmation "Confirm controlled pilot Go while public production direct launch remains No-Go"

$arguments = @(
  (Join-Path $repoRoot "scripts/production_landing_signoff_closeout.py"),
  "--signoff-record",
  $SignoffRecord,
  "--target-record",
  $TargetRecord,
  "--closure-evidence",
  $ClosureEvidence,
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
Write-Host "[production_landing_signoff_closeout] status=done" -ForegroundColor Green
