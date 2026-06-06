from __future__ import annotations

from pathlib import Path


def test_xiaomi_llm_preflight_ps1_uses_process_env_only_without_plaintext_secret() -> None:
    script = Path("scripts/xiaomi_llm_preflight.ps1")
    text = script.read_text(encoding="utf-8")

    assert "Read-Host" in text
    assert "-AsSecureString" in text
    assert "CheckPythonOnly" in text
    assert "production_landing_xiaomi_llm_preflight_runner.py" in text
    assert "--execute-network-check" in text
    assert "Resolve-PythonExecutable" in text
    assert "WindowsApps" in text
    assert "codex安装" not in text
    assert "SetEnvironmentVariable($apiKeyEnv, $plainKey, \"Process\")" in text
    assert "SetEnvironmentVariable($apiKeyEnv, $null, \"Process\")" in text
    assert "WriteAllText" not in text
    assert ".env" not in text
    assert "tp-" not in text
    assert "sk-" not in text


def test_xiaomi_llm_landing_resume_ps1_runs_preflight_and_refresh_without_plaintext_secret() -> None:
    script = Path("scripts/xiaomi_llm_landing_resume.ps1")
    text = script.read_text(encoding="utf-8")

    assert "Read-Host" in text
    assert "-AsSecureString" in text
    assert "CheckPythonOnly" in text
    assert "production_landing_env_runner.py" in text
    assert "xiaomi-llm-preflight" in text
    assert "manual_signoff_evidence_ack_status.py" in text
    assert "manual_signoff_record_validator.py" in text
    assert "production_landing_blocker_resolution.py" in text
    assert "production_landing_refresh_status.py" in text
    assert "--closure-evidence" in text
    assert "production_landing_final_verification.py" in text
    assert "Resolve-PythonExecutable" in text
    assert "WindowsApps" in text
    assert "codex安装" not in text
    assert "SetEnvironmentVariable($apiKeyEnv, $plainKey, \"Process\")" in text
    assert "SetEnvironmentVariable($apiKeyEnv, $null, \"Process\")" in text
    assert "WriteAllText" not in text
    assert ".env" not in text
    assert "tp-" not in text
    assert "sk-" not in text
