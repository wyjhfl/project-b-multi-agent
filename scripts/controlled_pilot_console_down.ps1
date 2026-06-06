param()

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$RuntimeDir = Join-Path $Root "docs\reports\controlled_pilot_console"
$PidFile = Join-Path $RuntimeDir "controlled_pilot_console_processes.json"
$FrontendStderr = Join-Path $RuntimeDir "frontend.stderr.log"

function Stop-LocalProcessId {
    param([Parameter(Mandatory = $true)][int]$ProcessId)

    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($process) {
        Stop-Process -Id $ProcessId -Force -ErrorAction Stop
        Start-Sleep -Milliseconds 300
        $remaining = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
        if ($remaining) {
            throw "failed to stop process id $ProcessId"
        }
        Write-Output "[controlled_pilot_console_down] stopped_pid=$ProcessId"
    }
}

Write-Output "[controlled_pilot_console_down] mode=local_controlled_pilot_console"
Write-Output "[controlled_pilot_console_down] do_not_enter_tokens_or_connection_strings=true"
Write-Output "[controlled_pilot_console_down] public_production_direct_launch=No-Go"

$stoppedAny = $false

if (Test-Path -LiteralPath $PidFile) {
    $record = Get-Content -LiteralPath $PidFile -Encoding UTF8 -Raw | ConvertFrom-Json
    $processIds = @($record.frontend_pid, $record.backend_pid) | Where-Object { $_ -is [int] -or "$_".Trim() -match "^\d+$" }

    foreach ($processId in $processIds) {
        Stop-LocalProcessId -ProcessId ([int]$processId)
        $stoppedAny = $true
    }
}
else {
    Write-Output "[controlled_pilot_console_down] reason=pid_file_missing"
}

if (Test-Path -LiteralPath $FrontendStderr) {
    $stderrText = Get-Content -LiteralPath $FrontendStderr -Raw -ErrorAction SilentlyContinue
    if ($null -eq $stderrText) {
        $stderrText = ""
    }
    $matches = [regex]::Matches($stderrText, "PID:\s*(\d+)")
    foreach ($match in $matches) {
        $stalePid = [int]$match.Groups[1].Value
        if ($stalePid -gt 0) {
            Stop-LocalProcessId -ProcessId $stalePid
            $stoppedAny = $true
        }
    }
}

Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
if ($stoppedAny) {
    Write-Output "[controlled_pilot_console_down] status=stopped"
}
else {
    Write-Output "[controlled_pilot_console_down] status=skipped"
}
