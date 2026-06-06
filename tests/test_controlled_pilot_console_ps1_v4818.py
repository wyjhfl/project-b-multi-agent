from __future__ import annotations

from pathlib import Path


def _read_script(name: str) -> str:
    return Path("scripts", name).read_text(encoding="utf-8")


def test_controlled_pilot_console_up_is_local_and_secret_safe() -> None:
    text = _read_script("controlled_pilot_console_up.ps1")

    assert "local_controlled_pilot_console" in text
    assert "[int]$FrontendPort = 3003" in text
    assert "127.0.0.1" in text
    assert "controlled pilot console must bind to 127.0.0.1" in text
    assert "Initialize-CodexProcessEnvironment" in text
    assert "Resolve-PythonExecutable" in text
    assert "Resolve-NodeExecutable" in text
    assert "WindowsApps" in text
    assert "XDG_CONFIG_HOME" in text
    assert "PYTHONUTF8" in text
    assert "codex*" in text
    assert "D:\\codex安装" not in text
    assert 'SetEnvironmentVariable("PATH", $null, "Process")' in text
    assert 'SetEnvironmentVariable("Path"' in text
    assert "Invoke-WebRequest" in text
    assert "/operations/summary" in text
    assert "backend.stderr.log" in text
    assert "frontend.stderr.log" in text
    assert "RedirectStandardError" in text
    assert "Assert-ProcessRunning" in text
    assert "process exited during startup" in text
    assert "frontend_health_check=running" in text
    assert "frontend_build=running" in text
    assert "npm.cmd run build --prefix $FrontendRoot" in text
    assert "frontend build failed with exit code" in text
    assert "uvicorn" in text
    assert "app.main:app" in text
    assert "node_modules\\next\\dist\\bin\\next" in text
    assert "Start-Process -FilePath $NodeExe" in text
    assert '@($NextCli, "start", "-H", $HostAddress, "-p", "$FrontendPort")' in text
    assert "NEXT_PUBLIC_API_BASE_URL" in text
    assert "docs\\reports\\controlled_pilot_console" in text
    assert "controlled_pilot_console_processes.json" in text
    assert "public_production_direct_launch=No-Go" in text
    assert '"No-Go"' in text
    assert "secret_plaintext_output" in text
    assert "Read-Host" not in text
    assert 'SetEnvironmentVariable("XIAOMI' not in text
    assert 'SetEnvironmentVariable("DATABASE_URL' not in text
    assert 'SetEnvironmentVariable("REDIS_URL' not in text
    assert 'SetEnvironmentVariable("JWT_SECRET' not in text
    assert ".env" not in text
    assert "tp-" not in text
    assert "sk-" not in text


def test_controlled_pilot_console_down_uses_pid_file_only() -> None:
    text = _read_script("controlled_pilot_console_down.ps1")

    assert "local_controlled_pilot_console" in text
    assert "controlled_pilot_console_processes.json" in text
    assert "Get-Content -LiteralPath $PidFile -Encoding UTF8 -Raw | ConvertFrom-Json" in text
    assert "Get-Process" in text
    assert "Stop-Process" in text
    assert "failed to stop process id" in text
    assert "frontend.stderr.log" in text
    assert "PID:\\s*(\\d+)" in text
    assert "reason=pid_file_missing" in text
    assert "$stoppedAny" in text
    assert "Remove-Item -LiteralPath $PidFile" in text
    assert "public_production_direct_launch=No-Go" in text
    assert "Read-Host" not in text
    assert "SetEnvironmentVariable" not in text
    assert ".env" not in text
    assert "tp-" not in text
    assert "sk-" not in text


def test_controlled_pilot_console_verify_wraps_full_local_smoke() -> None:
    text = _read_script("controlled_pilot_console_verify.ps1")

    assert "local_controlled_pilot_verify" in text
    assert "controlled_pilot_console_up.ps1" in text
    assert "operations_console_landing_smoke.py" in text
    assert "--execute" in text
    assert "--frontend-url" in text
    assert "http://127.0.0.1:$FrontendPort" in text
    assert "--backend-url" in text
    assert "http://127.0.0.1:$BackendPort" in text
    assert "controlled_pilot_operator_packet.ps1" in text
    assert "controlled_pilot_console_preflight.py" in text
    assert "preflight=running" in text
    assert "controlled_pilot_console_preflight.py failed with exit code" in text
    assert "controlled_pilot_console_verify_report.py" in text
    assert "controlled_pilot_console_down.ps1" in text
    assert "$verifySucceeded = $false" in text
    assert "$verifySucceeded = $true" in text
    assert "$failureReason" in text
    assert "--forced-status" in text
    assert "--failure-reason" in text
    assert "status=failed" in text
    assert "--backend-port" in text
    assert "--frontend-port" in text
    assert "finally" in text
    assert "public_production_direct_launch=No-Go" in text
    assert "Read-Host" not in text
    assert ".env" not in text
    assert "tp-" not in text
    assert "sk-" not in text
