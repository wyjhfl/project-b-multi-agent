from __future__ import annotations

from pathlib import Path


def test_business_system_read_smoke_ps1_uses_process_env_only_without_plaintext_secret() -> None:
    text = Path("scripts/business_system_read_smoke.ps1").read_text(encoding="utf-8")

    assert "business_system_read_smoke.py" in text
    assert "--execute" in text
    assert "Read-Host" in text
    assert "-AsSecureString" in text
    assert "Convert-SecureStringToPlainText" in text
    assert "CheckPythonOnly" in text
    assert "Resolve-PythonExecutable" in text
    assert "WindowsApps" in text
    assert "XDG_CONFIG_HOME" in text
    assert "PYTHONUTF8" in text
    assert "BUSINESS_INTEGRATION_ENABLED\", \"true\", \"Process\"" in text
    assert "BUSINESS_INTEGRATION_READ_ONLY\", \"true\", \"Process\"" in text
    assert "BUSINESS_INTEGRATION_WRITE_ENABLED\", \"false\", \"Process\"" in text
    assert "BUSINESS_INTEGRATION_APPROVAL_REQUIRED\", \"true\", \"Process\"" in text
    assert "BUSINESS_INTEGRATION_AUDIT_REQUIRED\", \"true\", \"Process\"" in text
    assert "BUSINESS_SYSTEM_TOOL_ALLOWLIST\", \"business_read_probe\", \"Process\"" in text
    assert "BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST\", \"\", \"Process\"" in text
    assert "AuthHeaderName" in text
    assert "AuthScheme" in text
    assert "BusinessOwner" in text
    assert "SecurityReviewer" in text
    assert "OperationsOwner" in text
    assert "DataOwner" in text
    assert "SkipReadinessBrief" in text
    assert "Assert-OwnerValue" in text
    assert "BUSINESS_SYSTEM_BUSINESS_OWNER" in text
    assert "BUSINESS_SYSTEM_SECURITY_REVIEWER" in text
    assert "BUSINESS_SYSTEM_OPERATIONS_OWNER" in text
    assert "BUSINESS_SYSTEM_DATA_OWNER" in text
    assert "Assert-HeaderName" in text
    assert "BUSINESS_SYSTEM_AUTH_HEADER_NAME\", $AuthHeaderName, \"Process\"" in text
    assert "BUSINESS_SYSTEM_AUTH_SCHEME\", $AuthScheme, \"Process\"" in text
    assert "business_system_production_readiness_brief.py" in text
    assert "owner_process_env_restored=true" in text
    assert "SetEnvironmentVariable($baseUrlEnv, $plainBaseUrl, \"Process\")" in text
    assert "SetEnvironmentVariable($tokenEnv, $plainToken, \"Process\")" in text
    assert "SetEnvironmentVariable($baseUrlEnv, $null, \"Process\")" in text
    assert "SetEnvironmentVariable($tokenEnv, $null, \"Process\")" in text
    assert "process_env_restored=true" in text
    assert "public_production_direct_launch=No-Go" in text
    assert "WriteAllText" not in text
    assert ".env" not in text
    assert "tp-" not in text
    assert "sk-" not in text


def test_business_system_read_smoke_ps1_rejects_secret_like_base_url() -> None:
    text = Path("scripts/business_system_read_smoke.ps1").read_text(encoding="utf-8")

    assert "Assert-HttpUrl" in text
    assert "must start with http:// or https://" in text
    assert "looks like a secret" in text
    assert "enter only the base URL" in text


def test_business_system_read_smoke_ps1_runs_readiness_after_smoke_and_restores_owner_env() -> None:
    text = Path("scripts/business_system_read_smoke.ps1").read_text(encoding="utf-8")

    assert "readiness_brief=running" in text
    assert "readiness_brief=done" in text
    assert "business_system_production_readiness_brief.py failed" in text
    assert "$ownerValuesInjectedForRun = $true" in text
    assert "SetEnvironmentVariable($ownerEnvName, $previousOwnerEnv[$ownerEnvName], \"Process\")" in text
    assert "SetEnvironmentVariable($ownerEnvName, $null, \"Process\")" in text
