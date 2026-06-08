Param(
  [string]$EnvPath = "local\production_landing.staging.env"
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonWrapper = Join-Path $repoRoot "scripts\codex_python.ps1"
$demoSmokeScript = Join-Path $repoRoot "scripts\production_landing_demo_business_smoke.py"
$resumeScript = Join-Path $repoRoot "scripts\business_system_landing_resume.ps1"
$textQualityScript = Join-Path $repoRoot "scripts\production_landing_text_quality_check.py"
$deliveryGateScript = Join-Path $repoRoot "scripts\controlled_pilot_delivery_gate.py"
$runPacketScript = Join-Path $repoRoot "scripts\controlled_pilot_run_packet.py"
$archiveScript = Join-Path $repoRoot "scripts\evidence_archive_manifest.py"

function Initialize-ControlledPilotDemoLandingEnvironment {
  [Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
  [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
  $script:OutputEncoding = [System.Text.UTF8Encoding]::new($false)
  chcp 65001 | Out-Null
}

function Invoke-CheckedPythonCapture {
  param([Parameter(Mandatory = $true)][string[]]$Arguments)

  $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $pythonWrapper @Arguments 2>&1
  foreach ($line in $output) {
    Write-Output $line
  }
  if ($LASTEXITCODE -ne 0) {
    throw "python command failed with exit code $LASTEXITCODE"
  }
  return @($output)
}

function Invoke-CheckedPowerShell {
  param([Parameter(Mandatory = $true)][string[]]$Arguments)

  & powershell -NoProfile -ExecutionPolicy Bypass @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "powershell command failed with exit code $LASTEXITCODE"
  }
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

function Read-JsonObject {
  param([Parameter(Mandatory = $true)][string]$Path)

  $resolvedPath = Resolve-Path -LiteralPath $Path -ErrorAction Stop
  $jsonText = Get-Content -LiteralPath $resolvedPath.Path -Raw -Encoding UTF8
  return $jsonText | ConvertFrom-Json
}

Initialize-ControlledPilotDemoLandingEnvironment

Write-Output "[controlled_pilot_demo_landing] no_real_business_system=true"
Write-Output "[controlled_pilot_demo_landing] mode=demo_read_only_controlled_internal_pilot"
Write-Output "[controlled_pilot_demo_landing] do_not_enter_tokens_or_connection_strings=true"
Write-Output "[controlled_pilot_demo_landing] public_production_direct_launch=No-Go"

foreach ($path in @($pythonWrapper, $demoSmokeScript, $resumeScript, $textQualityScript, $deliveryGateScript, $runPacketScript, $archiveScript)) {
  if (-not (Test-Path -LiteralPath $path)) {
    throw "required file not found: $path"
  }
}

Push-Location $repoRoot
try {
  Write-Output "[controlled_pilot_demo_landing] step=demo-business-smoke"
  $demoArgs = @($demoSmokeScript, "--env-path", $EnvPath)
  $demoOutput = Invoke-CheckedPythonCapture $demoArgs
  $demoSmokeJsonPath = Get-JsonPathFromOutput -OutputLines $demoOutput -ToolName "production_landing_demo_business_smoke.py"

  Write-Output "[controlled_pilot_demo_landing] step=business-landing-resume"
  $resumeArgs = @(
    "-File",
    $resumeScript,
    "-BusinessReadSmokeJsonPath",
    $demoSmokeJsonPath,
    "-EnvPath",
    $EnvPath
  )
  Invoke-CheckedPowerShell $resumeArgs

  Write-Output "[controlled_pilot_demo_landing] step=controlled-pilot-delivery-gate"
  Invoke-CheckedPythonCapture @($deliveryGateScript) | Out-Null

  Write-Output "[controlled_pilot_demo_landing] step=controlled-pilot-run-packet"
  $runPacketOutput = Invoke-CheckedPythonCapture @($runPacketScript)
  $runPacketJsonPath = Get-JsonPathFromOutput -OutputLines $runPacketOutput -ToolName "controlled_pilot_run_packet.py"
  $runPacket = Read-JsonObject -Path $runPacketJsonPath

  Write-Output "[controlled_pilot_demo_landing] step=evidence-archive-manifest"
  Invoke-CheckedPythonCapture @($archiveScript) | Out-Null

  Write-Output "[controlled_pilot_demo_landing] step=production-text-quality"
  Invoke-CheckedPythonCapture @($textQualityScript) | Out-Null

  $controlledInternalPilot = [string]$runPacket.controlled_internal_pilot
  $landingStatus = [string]$runPacket.status
  $missingConditionCount = [int]($runPacket.missing_condition_count)

  if ($runPacket.public_production_direct_launch -ne "No-Go") {
    throw "controlled pilot run packet changed public production boundary"
  }
  if ($runPacket.secret_plaintext_output -ne $false) {
    throw "controlled pilot run packet reported secret plaintext output"
  }
  if ($landingStatus -eq "blocked" -or $controlledInternalPilot -eq "No-Go") {
    throw "controlled pilot run packet is blocked"
  }

  Write-Output "[controlled_pilot_demo_landing] run_packet_json_path=$runPacketJsonPath"
  Write-Output "[controlled_pilot_demo_landing] landing_status=$landingStatus"
  Write-Output "[controlled_pilot_demo_landing] controlled_internal_pilot=$controlledInternalPilot"
  Write-Output "[controlled_pilot_demo_landing] missing_condition_count=$missingConditionCount"
  foreach ($condition in @($runPacket.missing_conditions)) {
    Write-Output "[controlled_pilot_demo_landing] missing_condition=$condition"
  }
  Write-Output "[controlled_pilot_demo_landing] public_production_direct_launch=No-Go"
  Write-Output "[controlled_pilot_demo_landing] status=done"
}
finally {
  Pop-Location
}
