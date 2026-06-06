from __future__ import annotations

from pathlib import Path


def test_real_integration_infra_smoke_ps1_uses_process_env_only_for_connection_strings() -> None:
    text = Path("scripts/real_integration_infra_smoke.ps1").read_text(encoding="utf-8")

    assert "real_integration_staging_smoke.py" in text
    assert "--execute" in text
    assert "--domains" in text
    assert "ValidateSet(\"postgres\", \"redis\", \"external_mcp\")" in text
    assert "Read-SecretEnvValue" in text
    assert "-AsSecureString" in text
    assert "Convert-SecureStringToPlainText" in text
    assert "CheckPythonOnly" in text
    assert "Resolve-PythonExecutable" in text
    assert "WindowsApps" in text
    assert "XDG_CONFIG_HOME" in text
    assert "PYTHONUTF8" in text
    assert "REAL_INTEGRATION_STAGING_SMOKE_ENABLED\", \"true\", \"Process\"" in text
    assert "POSTGRES_STAGING_SMOKE_EXECUTE\", \"true\", \"Process\"" in text
    assert "STORAGE_BACKEND\", \"postgres\", \"Process\"" in text
    assert "REDIS_STAGING_SMOKE_EXECUTE\", \"true\", \"Process\"" in text
    assert "REDIS_ENABLED\", \"true\", \"Process\"" in text
    assert "RATE_LIMIT_BACKEND\", \"redis\", \"Process\"" in text
    assert "MCP_STAGING_SMOKE_EXECUTE\", \"true\", \"Process\"" in text
    assert "MCP_MODE\", \"real\", \"Process\"" in text
    assert "SetEnvironmentVariable(\"DATABASE_URL\", (Read-SecretEnvValue" in text
    assert "SetEnvironmentVariable(\"REDIS_URL\", (Read-SecretEnvValue" in text
    assert "SetEnvironmentVariable($key, $null, \"Process\")" in text
    assert "process_env_restored=true" in text
    assert "public_production_direct_launch=No-Go" in text
    assert "WriteAllText" not in text
    assert ".env" not in text
    assert "tp-" not in text
    assert "sk-" not in text


def test_real_integration_infra_smoke_ps1_rejects_secret_like_mcp_metadata() -> None:
    text = Path("scripts/real_integration_infra_smoke.ps1").read_text(encoding="utf-8")

    assert "Assert-NonSecretConfigText" in text
    assert "looks like a secret" in text
    assert "pass only allowlisted command/tool metadata" in text
    assert "MCP_SERVER_COMMAND_ALLOWLIST" in text
    assert "MCP_TOOL_ALLOWLIST" in text
