from __future__ import annotations

from pathlib import Path


def test_real_integration_infra_smoke_ps1_supports_env_path_without_plaintext_secret() -> None:
    text = Path("scripts/real_integration_infra_smoke.ps1").read_text(encoding="utf-8")

    assert "EnvPath" in text
    assert "Import-InfraEnvPath" in text
    assert "envPathSafeKeys" in text
    assert "envPathSecretKeys" in text
    assert "env_path_loaded_safe_count" in text
    assert "env_path_loaded_secret_count" in text
    assert "env_path_process_env_restored=true" in text
    assert "REAL_INTEGRATION_STAGING_SMOKE_ENABLED" in text
    assert "POSTGRES_STAGING_SMOKE_EXECUTE" in text
    assert "REDIS_STAGING_SMOKE_EXECUTE" in text
    assert "MCP_STAGING_SMOKE_EXECUTE" in text
    assert "DATABASE_URL" in text
    assert "REDIS_URL" in text
    assert "Set-EnvPathProcessValue" in text
    assert "ReadLines($resolvedPath.Path, [System.Text.UTF8Encoding]::new($false))" in text
    assert "WriteAllText" not in text
    assert "tp-" not in text
    assert "sk-" not in text


def test_real_integration_infra_smoke_ps1_env_path_keeps_secret_keys_separate() -> None:
    text = Path("scripts/real_integration_infra_smoke.ps1").read_text(encoding="utf-8")

    safe_section = text.split("$envPathSafeKeys = @(", 1)[1].split(")", 1)[0]
    secret_section = text.split("$envPathSecretKeys = @(", 1)[1].split(")", 1)[0]

    assert '"STORAGE_BACKEND",' in safe_section
    assert '"RATE_LIMIT_BACKEND",' in safe_section
    assert '"MCP_SERVER_COMMAND_ALLOWLIST",' in safe_section
    assert '"MCP_TOOL_ALLOWLIST",' in safe_section
    assert '"DATABASE_URL",' not in safe_section
    assert '"REDIS_URL",' not in safe_section
    assert '"DATABASE_URL",' in secret_section
    assert '"REDIS_URL",' in secret_section
    assert '"XIAOMI_LLM_API_KEY",' in secret_section
    assert '"REAL_LLM_API_KEY",' in secret_section


def test_real_integration_infra_smoke_ps1_accepts_comma_separated_domains() -> None:
    text = Path("scripts/real_integration_infra_smoke.ps1").read_text(encoding="utf-8")

    assert "Resolve-InfraDomains" in text
    assert '.Split(",")' in text
    assert "Unsupported infra smoke domain" in text
    assert '[ValidateSet("postgres", "redis", "external_mcp")]' not in text


def test_real_integration_infra_smoke_ps1_allows_empty_safe_env_values() -> None:
    text = Path("scripts/real_integration_infra_smoke.ps1").read_text(encoding="utf-8")
    assert "function Assert-NonSecretConfigText" in text
    assert "[AllowEmptyString()][string]$Value" in text


def test_production_landing_commands_use_env_path_for_infra_smoke() -> None:
    paths = [
        Path("scripts/production_landing_action_pack.py"),
        Path("scripts/production_landing_env_check.py"),
        Path("scripts/production_landing_env_template.py"),
        Path("scripts/production_landing_input_readiness.py"),
        Path("scripts/real_production_environment_checklist.py"),
    ]
    merged = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    assert "-UseExistingEnv -EnvPath local\\\\production_landing.staging.env" in merged
    assert "real_integration_infra_smoke.ps1" in merged
    assert "-Domains postgres -UseExistingEnv -EnvPath local\\\\production_landing.staging.env" in merged
    assert "-Domains redis -UseExistingEnv -EnvPath local\\\\production_landing.staging.env" in merged
    assert "-Domains external_mcp -UseExistingEnv -EnvPath local\\\\production_landing.staging.env" in merged
