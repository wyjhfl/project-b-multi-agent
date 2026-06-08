from __future__ import annotations

from pathlib import Path
import re


def test_real_llm_preflight_ps1_uses_process_env_only_without_plaintext_secret() -> None:
    script = Path("scripts/real_llm_preflight.ps1")
    text = script.read_text(encoding="utf-8")

    assert "Read-Host" in text
    assert "-AsSecureString" in text
    assert "CheckPythonOnly" in text
    assert "production_landing_real_llm_preflight_runner.py" in text
    assert "--execute-network-check" in text
    assert "--api-key-env" in text
    assert "--base-url" in text
    assert "--model" in text
    assert "Resolve-PythonExecutable" in text
    assert "WindowsApps" in text
    assert "SetEnvironmentVariable($ApiKeyEnv, $plainKey, \"Process\")" in text
    assert "SetEnvironmentVariable($ApiKeyEnv, $null, \"Process\")" in text
    assert "WriteAllText" not in text
    assert ".env" not in text
    assert not re.search(r"\bk-[A-Za-z0-9_\-]{24,}", text)
    assert "tp-" not in text
    assert "sk-" not in text
