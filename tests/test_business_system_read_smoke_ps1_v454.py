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
    assert "EnvPath" in text
    assert "SkipReadinessBrief" in text
    assert "SkipLandingResume" in text
    assert "Import-BusinessEnvPath" in text
    assert "envPathSafeKeys" in text
    assert "envPathSecretKeys" in text
    assert "env_path_loaded_keys" in text
    assert "env_path_secret_keys_skipped" in text
    assert "env_path_process_env_restored=true" in text
    assert "BUSINESS_SYSTEM_BASE_URL" in text
    assert "BUSINESS_SYSTEM_TOKEN" in text
    assert '"BUSINESS_SYSTEM_BASE_URL",' in text
    assert '"BUSINESS_SYSTEM_TOKEN",' in text
    assert "if ($envPathSecretKeys -contains $key)" in text
    assert "continue" in text
    assert "Assert-OwnerValue" in text
    assert "BUSINESS_SYSTEM_BUSINESS_OWNER" in text
    assert "BUSINESS_SYSTEM_SECURITY_REVIEWER" in text
    assert "BUSINESS_SYSTEM_OPERATIONS_OWNER" in text
    assert "BUSINESS_SYSTEM_DATA_OWNER" in text
    assert "Assert-HeaderName" in text
    assert "BUSINESS_SYSTEM_AUTH_HEADER_NAME\", $effectiveAuthHeaderName, \"Process\"" in text
    assert "BUSINESS_SYSTEM_AUTH_SCHEME\", $effectiveAuthScheme, \"Process\"" in text
    assert "business_system_production_readiness_brief.py" in text
    assert "business_system_input_packet.py" in text
    assert "business_system_landing_execution_pack.py" in text
    assert "business_system_landing_resume.ps1" in text
    assert "owner_process_env_restored=true" in text
    assert "SetEnvironmentVariable($baseUrlEnv, $plainBaseUrl, \"Process\")" in text
    assert "SetEnvironmentVariable($tokenEnv, $plainToken, \"Process\")" in text
    assert "SetEnvironmentVariable($baseUrlEnv, $null, \"Process\")" in text
    assert "SetEnvironmentVariable($tokenEnv, $null, \"Process\")" in text
    assert "process_env_restored=true" in text
    assert "public_production_direct_launch=No-Go" in text
    assert "WriteAllText" not in text
    assert "tp-" not in text
    assert "sk-" not in text


def test_business_system_read_smoke_ps1_rejects_secret_like_base_url() -> None:
    text = Path("scripts/business_system_read_smoke.ps1").read_text(encoding="utf-8")

    assert "Assert-HttpUrl" in text
    assert "must start with http:// or https://" in text
    assert "looks like a secret" in text
    assert "enter only the base URL" in text


def test_business_system_read_smoke_ps1_env_path_only_loads_safe_keys() -> None:
    text = Path("scripts/business_system_read_smoke.ps1").read_text(encoding="utf-8")

    safe_section = text.split("$envPathSafeKeys = @(", 1)[1].split(")", 1)[0]
    secret_section = text.split("$envPathSecretKeys = @(", 1)[1].split(")", 1)[0]

    assert '"BUSINESS_SYSTEM_TOOL_ALLOWLIST",' in safe_section
    assert '"BUSINESS_SYSTEM_AUTH_HEADER_NAME",' in safe_section
    assert '"BUSINESS_SYSTEM_BUSINESS_OWNER",' in safe_section
    assert '"BUSINESS_SYSTEM_BASE_URL",' not in safe_section
    assert '"BUSINESS_SYSTEM_TOKEN",' not in safe_section
    assert '"BUSINESS_SYSTEM_BASE_URL",' in secret_section
    assert '"BUSINESS_SYSTEM_TOKEN",' in secret_section
    assert '"DATABASE_URL",' in secret_section
    assert '"REDIS_URL",' in secret_section
    assert '"XIAOMI_LLM_API_KEY",' in secret_section


def test_business_system_read_smoke_ps1_runs_readiness_after_smoke_and_restores_owner_env() -> None:
    text = Path("scripts/business_system_read_smoke.ps1").read_text(encoding="utf-8")

    assert "readiness_brief=running" in text
    assert "readiness_brief=done" in text
    assert "input_packet=running" in text
    assert "input_packet=done" in text
    assert "execution_pack=running" in text
    assert "execution_pack=done" in text
    assert "landing_resume=running" in text
    assert "landing_resume=done" in text
    assert "SkipBusinessPreparation" in text
    assert '"-EnvPath", $EnvPath' in text
    assert "business_system_production_readiness_brief.py failed" in text
    assert "business_system_input_packet.py failed" in text
    assert "business_system_landing_execution_pack.py failed" in text
    assert "business_system_landing_resume.ps1 failed" in text
    assert "$ownerValuesInjectedForRun = $true" in text
    assert "SetEnvironmentVariable($ownerEnvName, $previousOwnerEnv[$ownerEnvName], \"Process\")" in text
    assert "SetEnvironmentVariable($ownerEnvName, $null, \"Process\")" in text
    assert "Read-CurrentEnvValue" in text
    assert "BUSINESS_SYSTEM_READ_PROBE_PATH" in text
    assert "BUSINESS_SYSTEM_AUTH_HEADER_NAME" in text
    assert "BUSINESS_SYSTEM_AUTH_SCHEME" in text
    assert "Set-EnvPathProcessValue" in text
    assert "SetEnvironmentVariable($envName, $previousEnvPathEnv[$envName], \"Process\")" in text
    assert "SetEnvironmentVariable($envName, $null, \"Process\")" in text


def test_business_system_landing_resume_ps1_refreshes_landing_chain_without_plaintext_secret() -> None:
    text = Path("scripts/business_system_landing_resume.ps1").read_text(encoding="utf-8")

    assert "do_not_enter_tokens_or_connection_strings=true" in text
    assert "input=existing_process_env_only" in text
    assert "SkipBusinessPreparation" in text
    assert "business_system_input_packet.py" in text
    assert "business_system_production_readiness_brief.py" in text
    assert "business_system_landing_execution_pack.py" in text
    assert "production_landing_env_check.py" in text
    assert "production_landing_execution_gate.py" in text
    assert "EnvPath" in text
    assert "production_landing_status.py" in text
    assert "production_landing_final_verification.py" in text
    assert "production_landing_text_quality_check.py" in text
    assert "production_landing_evidence_freshness.py" in text
    assert "evidence-freshness-prime" in text
    assert "evidence-freshness-final" in text
    assert "controlled-pilot-status-summary-prime" in text
    assert "controlled-pilot-operator-packet-prime" in text
    assert "controlled_pilot_status_summary.py" in text
    assert "controlled_pilot_operator_packet.py" in text
    assert "CheckPythonOnly" in text
    assert "Resolve-PythonExecutable" in text
    assert "WindowsApps" in text
    assert "XDG_CONFIG_HOME" in text
    assert "PYTHONUTF8" in text
    assert "Read-Host" not in text
    assert "-AsSecureString" not in text
    assert "SetEnvironmentVariable" not in text
    assert "WriteAllText" not in text
    assert ".env" not in text
    assert "tp-" not in text
    assert "sk-" not in text
