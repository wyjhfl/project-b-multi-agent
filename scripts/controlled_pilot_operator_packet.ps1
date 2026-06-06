param(
    [string]$OutputDir = "",
    [switch]$Json
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PythonWrapper = Join-Path $Root "scripts\codex_python.ps1"
$StatusScript = Join-Path $Root "scripts\controlled_pilot_status_summary.py"
$PacketScript = Join-Path $Root "scripts\controlled_pilot_operator_packet.py"

Write-Output "[controlled_pilot_operator_packet] mode=read_only_operator_handoff"
Write-Output "[controlled_pilot_operator_packet] do_not_enter_tokens_or_connection_strings=true"
Write-Output "[controlled_pilot_operator_packet] public_production_direct_launch=No-Go"

if (-not (Test-Path -LiteralPath $PythonWrapper)) {
    throw "codex_python.ps1 not found: $PythonWrapper"
}

Push-Location $Root
try {
    Write-Output "[controlled_pilot_operator_packet] refresh_status_summary=running"
    & powershell -NoProfile -ExecutionPolicy Bypass -File $PythonWrapper $StatusScript
    if ($LASTEXITCODE -ne 0) {
        throw "controlled_pilot_status_summary.py failed with exit code $LASTEXITCODE"
    }

    Write-Output "[controlled_pilot_operator_packet] build_operator_packet=running"
    $packetArgs = @($PacketScript)
    if ($OutputDir.Trim() -ne "") {
        $packetArgs += @("--output-dir", $OutputDir)
    }
    & powershell -NoProfile -ExecutionPolicy Bypass -File $PythonWrapper @packetArgs
    if ($LASTEXITCODE -ne 0) {
        throw "controlled_pilot_operator_packet.py failed with exit code $LASTEXITCODE"
    }

    Write-Output "[controlled_pilot_operator_packet] status=done"
}
finally {
    Pop-Location
}
