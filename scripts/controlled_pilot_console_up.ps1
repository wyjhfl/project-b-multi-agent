param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 3003,
    [string]$HostAddress = "127.0.0.1"
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$FrontendRoot = Join-Path $Root "frontend"
$RuntimeDir = Join-Path $Root "docs\reports\controlled_pilot_console"
$PidFile = Join-Path $RuntimeDir "controlled_pilot_console_processes.json"
$NextCli = Join-Path $FrontendRoot "node_modules\next\dist\bin\next"

function Initialize-CodexProcessEnvironment {
    [Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    $script:OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    chcp 65001 | Out-Null

    $processEnvironment = [System.Environment]::GetEnvironmentVariables("Process")
    if ($processEnvironment.Contains("Path") -and $processEnvironment.Contains("PATH")) {
        [System.Environment]::SetEnvironmentVariable("PATH", $null, "Process")
    }
    if (-not [System.Environment]::GetEnvironmentVariable("Path", "Process")) {
        $machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
        $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
        [System.Environment]::SetEnvironmentVariable("Path", (($machinePath, $userPath) -join ";"), "Process")
    }

    $xdgRoot = Join-Path $Root ".git-xdg"
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
    $currentPython = Get-Command "python.exe" -ErrorAction SilentlyContinue
    if ($currentPython -and $currentPython.Source -notlike "*WindowsApps*") {
        return $currentPython.Source
    }

    $knownPython = Get-ChildItem -LiteralPath "D:\" -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "codex*" } |
        ForEach-Object { Join-Path $_.FullName "tools\Python312\python.exe" } |
        Where-Object { Test-Path -LiteralPath $_ } |
        Select-Object -First 1
    if ($knownPython) {
        return $knownPython
    }

    $pyLauncher = Get-Command "py.exe" -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        throw "py.exe launcher is available, but Start-Process requires a direct python.exe path for the console backend"
    }

    throw "Python runtime not found. Expected bundled Codex runtime under D:\codex*\tools\Python312\python.exe or a non-WindowsApps python.exe on PATH."
}

function Resolve-NodeExecutable {
    $nodeCommand = Get-Command "node.exe" -ErrorAction SilentlyContinue
    if ($nodeCommand) {
        return $nodeCommand.Source
    }
    throw "node.exe not found on PATH."
}

function Wait-HttpOk {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $lastError = ""
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300) {
                return
            }
            $lastError = "http_status=$($response.StatusCode)"
        }
        catch {
            $lastError = $_.Exception.Message
        }
        Start-Sleep -Seconds 1
    }
    throw "HTTP health check failed for $Url; last_error=$lastError"
}

function Assert-ProcessRunning {
    param(
        [Parameter(Mandatory = $true)]$Process,
        [Parameter(Mandatory = $true)][string]$Name,
        [string]$StderrLog = ""
    )

    $Process.Refresh()
    if ($Process.HasExited) {
        $tail = ""
        if ($StderrLog -and (Test-Path -LiteralPath $StderrLog)) {
            $tail = (Get-Content -LiteralPath $StderrLog -Tail 20 -ErrorAction SilentlyContinue) -join " | "
        }
        throw "$Name process exited during startup; exit_code=$($Process.ExitCode); stderr_tail=$tail"
    }
}

Initialize-CodexProcessEnvironment
$PythonExe = Resolve-PythonExecutable
$NodeExe = Resolve-NodeExecutable

Write-Output "[controlled_pilot_console_up] mode=local_controlled_pilot_console"
Write-Output "[controlled_pilot_console_up] bind_host=$HostAddress"
Write-Output "[controlled_pilot_console_up] do_not_enter_tokens_or_connection_strings=true"
Write-Output "[controlled_pilot_console_up] public_production_direct_launch=No-Go"

if ($HostAddress -ne "127.0.0.1") {
    throw "controlled pilot console must bind to 127.0.0.1"
}
if (-not (Test-Path -LiteralPath $FrontendRoot)) {
    throw "frontend directory not found: $FrontendRoot"
}
if (-not (Test-Path -LiteralPath $NextCli)) {
    throw "Next.js CLI not found: $NextCli. Run npm.cmd install and npm.cmd run build under frontend first."
}

New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
$BackendStdout = Join-Path $RuntimeDir "backend.stdout.log"
$BackendStderr = Join-Path $RuntimeDir "backend.stderr.log"
$FrontendStdout = Join-Path $RuntimeDir "frontend.stdout.log"
$FrontendStderr = Join-Path $RuntimeDir "frontend.stderr.log"

Push-Location $Root
try {
    $env:NEXT_PUBLIC_API_BASE_URL = "http://$HostAddress`:$BackendPort"
    Write-Output "[controlled_pilot_console_up] frontend_build=running"
    & npm.cmd run build --prefix $FrontendRoot
    if ($LASTEXITCODE -ne 0) {
        throw "frontend build failed with exit code $LASTEXITCODE"
    }

    $backend = Start-Process -FilePath $PythonExe `
        -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", $HostAddress, "--port", "$BackendPort") `
        -WorkingDirectory $Root `
        -WindowStyle Hidden `
        -RedirectStandardOutput $BackendStdout `
        -RedirectStandardError $BackendStderr `
        -PassThru

    $frontend = Start-Process -FilePath $NodeExe `
        -ArgumentList @($NextCli, "start", "-H", $HostAddress, "-p", "$FrontendPort") `
        -WorkingDirectory $FrontendRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $FrontendStdout `
        -RedirectStandardError $FrontendStderr `
        -PassThru

    $record = [ordered]@{
        mode = "local_controlled_pilot_console"
        backend_pid = $backend.Id
        frontend_pid = $frontend.Id
        backend_url = "http://$HostAddress`:$BackendPort"
        frontend_url = "http://$HostAddress`:$FrontendPort/operations"
        bind_host = $HostAddress
        public_production_direct_launch = "No-Go"
        secret_plaintext_output = $false
        pid_file = $PidFile
        backend_stdout_log = $BackendStdout
        backend_stderr_log = $BackendStderr
        frontend_stdout_log = $FrontendStdout
        frontend_stderr_log = $FrontendStderr
    }
    $record | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $PidFile -Encoding UTF8

    Write-Output "[controlled_pilot_console_up] backend_url=$($record.backend_url)"
    Write-Output "[controlled_pilot_console_up] frontend_url=$($record.frontend_url)"
    Write-Output "[controlled_pilot_console_up] pid_file=$PidFile"
    Write-Output "[controlled_pilot_console_up] backend_stderr_log=$BackendStderr"
    Write-Output "[controlled_pilot_console_up] frontend_stderr_log=$FrontendStderr"

    Write-Output "[controlled_pilot_console_up] backend_health_check=running"
    Assert-ProcessRunning -Process $backend -Name "backend" -StderrLog $BackendStderr
    Assert-ProcessRunning -Process $frontend -Name "frontend" -StderrLog $FrontendStderr
    Wait-HttpOk -Url "http://$HostAddress`:$BackendPort/health" -TimeoutSeconds 30
    Wait-HttpOk -Url "http://$HostAddress`:$BackendPort/operations/summary" -TimeoutSeconds 30
    Assert-ProcessRunning -Process $frontend -Name "frontend" -StderrLog $FrontendStderr
    Write-Output "[controlled_pilot_console_up] frontend_health_check=running"
    Wait-HttpOk -Url "http://$HostAddress`:$FrontendPort/operations" -TimeoutSeconds 30

    Write-Output "[controlled_pilot_console_up] status=started"
}
catch {
    if ($frontend -and -not $frontend.HasExited) {
        Stop-Process -Id $frontend.Id -Force -ErrorAction SilentlyContinue
    }
    if ($backend -and -not $backend.HasExited) {
        Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
    }
    throw
}
finally {
    Pop-Location
}
