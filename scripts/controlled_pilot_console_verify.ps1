param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 3003,
    [int]$TimeoutSeconds = 20
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$UpScript = Join-Path $Root "scripts\controlled_pilot_console_up.ps1"
$DownScript = Join-Path $Root "scripts\controlled_pilot_console_down.ps1"
$PythonWrapper = Join-Path $Root "scripts\codex_python.ps1"
$SmokeScript = Join-Path $Root "scripts\operations_console_landing_smoke.py"
$OperatorPacketScript = Join-Path $Root "scripts\controlled_pilot_operator_packet.ps1"
$PreflightScript = Join-Path $Root "scripts\controlled_pilot_console_preflight.py"
$VerifyReportScript = Join-Path $Root "scripts\controlled_pilot_console_verify_report.py"

Write-Output "[controlled_pilot_console_verify] mode=local_controlled_pilot_verify"
Write-Output "[controlled_pilot_console_verify] do_not_enter_tokens_or_connection_strings=true"
Write-Output "[controlled_pilot_console_verify] public_production_direct_launch=No-Go"

foreach ($path in @($UpScript, $DownScript, $PythonWrapper, $SmokeScript, $OperatorPacketScript, $PreflightScript, $VerifyReportScript)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "required file not found: $path"
    }
}

Push-Location $Root
$verifySucceeded = $false
$failureReason = ""
try {
    Write-Output "[controlled_pilot_console_verify] preflight=running"
    & powershell -NoProfile -ExecutionPolicy Bypass -File $PythonWrapper $PreflightScript `
        --backend-port $BackendPort `
        --frontend-port $FrontendPort
    if ($LASTEXITCODE -ne 0) {
        throw "controlled_pilot_console_preflight.py failed with exit code $LASTEXITCODE"
    }

    Write-Output "[controlled_pilot_console_verify] start_console=running"
    & powershell -NoProfile -ExecutionPolicy Bypass -File $UpScript -BackendPort $BackendPort -FrontendPort $FrontendPort
    if ($LASTEXITCODE -ne 0) {
        throw "controlled_pilot_console_up.ps1 failed with exit code $LASTEXITCODE"
    }

    Write-Output "[controlled_pilot_console_verify] operations_console_smoke=running"
    & powershell -NoProfile -ExecutionPolicy Bypass -File $PythonWrapper $SmokeScript `
        --execute `
        --frontend-url "http://127.0.0.1:$FrontendPort" `
        --backend-url "http://127.0.0.1:$BackendPort" `
        --timeout-seconds $TimeoutSeconds
    if ($LASTEXITCODE -ne 0) {
        throw "operations_console_landing_smoke.py failed with exit code $LASTEXITCODE"
    }

    Write-Output "[controlled_pilot_console_verify] refresh_operator_packet=running"
    & powershell -NoProfile -ExecutionPolicy Bypass -File $OperatorPacketScript
    if ($LASTEXITCODE -ne 0) {
        throw "controlled_pilot_operator_packet.ps1 failed with exit code $LASTEXITCODE"
    }

    $verifySucceeded = $true
}
catch {
    $failureReason = $_.Exception.Message
    Write-Output "[controlled_pilot_console_verify] status=failed"
    Write-Output "[controlled_pilot_console_verify] failure_reason=$failureReason"
    throw
}
finally {
    Write-Output "[controlled_pilot_console_verify] stop_console=running"
    & powershell -NoProfile -ExecutionPolicy Bypass -File $DownScript
    Write-Output "[controlled_pilot_console_verify] build_verify_report=running"
    $reportArgs = @(
        $VerifyReportScript,
        "--backend-port",
        "$BackendPort",
        "--frontend-port",
        "$FrontendPort"
    )
    if (-not $verifySucceeded) {
        $reportArgs += @("--forced-status", "failed", "--failure-reason", $failureReason)
    }
    & powershell -NoProfile -ExecutionPolicy Bypass -File $PythonWrapper @reportArgs
    if ($verifySucceeded -and $LASTEXITCODE -ne 0) {
        throw "controlled_pilot_console_verify_report.py failed with exit code $LASTEXITCODE"
    }
    if ($verifySucceeded) {
        Write-Output "[controlled_pilot_console_verify] status=success"
    }
    Pop-Location
}
