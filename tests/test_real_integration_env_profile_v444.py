from __future__ import annotations

import json
from pathlib import Path

from scripts.real_integration_env_profile import build_real_integration_env_profile


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _clear_env(monkeypatch) -> None:
    for key in [
        "REAL_LLM_PREFLIGHT_ENABLED",
        "REAL_LLM_ACCEPTANCE_ENABLED",
        "REAL_LLM_SMOKE_ENABLED",
        "REAL_LLM_MODEL",
        "REAL_LLM_API_KEY_ENV",
        "OPENAI_API_KEY",
        "STORAGE_BACKEND",
        "DATABASE_URL",
        "REDIS_ENABLED",
        "REDIS_URL",
        "RATE_LIMIT_BACKEND",
        "MCP_MODE",
        "MCP_SERVER_COMMAND",
        "MCP_SERVER_COMMAND_ALLOWLIST",
        "MCP_TOOL_ALLOWLIST",
        "MCP_SERVER_ENV_ALLOWLIST",
        "MCP_SERVER_TIMEOUT_SECONDS",
        "REAL_INTEGRATION_STAGING_SMOKE_ENABLED",
        "REAL_LLM_STAGING_SMOKE_EXECUTE",
        "POSTGRES_STAGING_SMOKE_EXECUTE",
        "REDIS_STAGING_SMOKE_EXECUTE",
        "MCP_STAGING_SMOKE_EXECUTE",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_real_integration_env_profile_generates_outputs(tmp_path: Path, monkeypatch) -> None:
    _clear_env(monkeypatch)
    summary = build_real_integration_env_profile(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert summary["read_only"] is True
    assert payload["version"] == "4.4.4"
    assert payload["phase"] == "v4.4 Phase 24.4 Env Profile Checker"
    assert payload["profile_count"] == 5
    assert payload["domain_count"] == 5
    assert payload["secret_plaintext_output"] is False
    assert Path(summary["markdown_path"]).exists()


def test_real_integration_env_profile_covers_required_keys_for_four_domains(tmp_path: Path, monkeypatch) -> None:
    _clear_env(monkeypatch)
    summary = build_real_integration_env_profile(output_dir=tmp_path / "out")
    payload = _read_payload(summary)
    profiles = {item["domain_id"]: item for item in payload["profiles"]}

    assert set(profiles) == {"real_llm", "postgres", "redis", "external_mcp", "staging_smoke"}
    assert "REAL_LLM_API_KEY_ENV" in profiles["real_llm"]["required_keys"]
    assert "DATABASE_URL" in profiles["postgres"]["required_keys"]
    assert "RATE_LIMIT_BACKEND" in profiles["redis"]["required_keys"]
    assert "MCP_TOOL_ALLOWLIST" in profiles["external_mcp"]["required_keys"]
    assert "REAL_INTEGRATION_STAGING_SMOKE_ENABLED" in profiles["staging_smoke"]["required_keys"]


def test_real_integration_env_profile_production_template_has_real_llm_smoke_keys(
    tmp_path: Path, monkeypatch
) -> None:
    _clear_env(monkeypatch)
    summary = build_real_integration_env_profile(output_dir=tmp_path / "out")
    payload = _read_payload(summary)
    real_llm = next(item for item in payload["profiles"] if item["domain_id"] == "real_llm")

    assert payload["status"] == "skipped"
    assert "template:.env.production.example:REAL_LLM_PREFLIGHT_ENABLED" not in real_llm["missing_conditions"]
    assert "template:.env.production.example:REAL_LLM_SMOKE_ENABLED" not in real_llm["missing_conditions"]
    assert "template:.env.production.example:REAL_LLM_PREFLIGHT_NETWORK_CHECK" not in real_llm["missing_conditions"]
    assert "opt_in:REAL_LLM_PREFLIGHT_ENABLED" in real_llm["missing_conditions"]
    assert "opt_in:REAL_LLM_SMOKE_ENABLED" in real_llm["missing_conditions"]


def test_real_integration_env_profile_does_not_leak_secret_plaintext(tmp_path: Path, monkeypatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("REAL_LLM_PREFLIGHT_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_ACCEPTANCE_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_SMOKE_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_MODEL", "gpt-test")
    monkeypatch.setenv("REAL_LLM_API_KEY_ENV", "OPENAI_API_KEY")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-sensitive-real-secret")
    monkeypatch.setenv("STORAGE_BACKEND", "postgres")
    monkeypatch.setenv("DATABASE_URL", "postgresql://agent:db-secret@db:5432/project_b")
    monkeypatch.setenv("REDIS_ENABLED", "true")
    monkeypatch.setenv("REDIS_URL", "redis://:redis-secret@redis:6379/0")
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setenv("MCP_MODE", "real")
    monkeypatch.setenv("MCP_SERVER_COMMAND", "node safe-server.js")
    monkeypatch.setenv("MCP_SERVER_COMMAND_ALLOWLIST", "node")
    monkeypatch.setenv("MCP_TOOL_ALLOWLIST", "safe_tool")
    monkeypatch.setenv("MCP_SERVER_ENV_ALLOWLIST", "OPENAI_API_KEY")
    monkeypatch.setenv("MCP_SERVER_TIMEOUT_SECONDS", "10")

    summary = build_real_integration_env_profile(output_dir=tmp_path / "out")
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert "sk-sensitive-real-secret" not in merged
    assert "db-secret" not in merged
    assert "redis-secret" not in merged
    assert "OPENAI_API_KEY" in merged
    assert "DATABASE_URL" in merged
    assert "REDIS_URL" in merged


def test_real_integration_env_profile_skips_when_template_key_missing(tmp_path: Path, monkeypatch) -> None:
    _clear_env(monkeypatch)
    dev_template = tmp_path / "dev.env"
    prod_template = tmp_path / "prod.env"
    dev_template.write_text("REAL_LLM_PREFLIGHT_ENABLED=false\n", encoding="utf-8")
    prod_template.write_text("REAL_LLM_PREFLIGHT_ENABLED=false\n", encoding="utf-8")

    summary = build_real_integration_env_profile(
        output_dir=tmp_path / "out",
        development_template_path=dev_template,
        production_template_path=prod_template,
    )
    payload = _read_payload(summary)

    assert payload["status"] == "skipped"
    assert any(item.startswith("template:.env.example:") for item in payload["missing_conditions"])
    assert any(item.startswith("template:.env.production.example:") for item in payload["missing_conditions"])


def test_real_integration_env_profile_blocks_secret_like_template_plaintext(tmp_path: Path, monkeypatch) -> None:
    _clear_env(monkeypatch)
    dev_template = tmp_path / "dev.env"
    prod_template = tmp_path / "prod.env"
    dev_template.write_text(
        "\n".join(
            [
                "REAL_LLM_PREFLIGHT_ENABLED=false",
                "REAL_LLM_ACCEPTANCE_ENABLED=false",
                "REAL_LLM_SMOKE_ENABLED=false",
                "REAL_LLM_MODEL=",
                "REAL_LLM_API_KEY_ENV=OPENAI_API_KEY",
                "STORAGE_BACKEND=sqlite",
                "DATABASE_URL=",
                "REDIS_ENABLED=false",
                "REDIS_URL=redis://localhost:6379/0",
                "RATE_LIMIT_BACKEND=memory",
                "MCP_MODE=fake",
                "MCP_SERVER_COMMAND=",
                "MCP_SERVER_COMMAND_ALLOWLIST=",
                "MCP_TOOL_ALLOWLIST=",
                "MCP_SERVER_ENV_ALLOWLIST=",
                "MCP_SERVER_TIMEOUT_SECONDS=10",
                "REAL_INTEGRATION_STAGING_SMOKE_ENABLED=false",
                "REAL_LLM_STAGING_SMOKE_EXECUTE=false",
                "POSTGRES_STAGING_SMOKE_EXECUTE=false",
                "REDIS_STAGING_SMOKE_EXECUTE=false",
                "MCP_STAGING_SMOKE_EXECUTE=false",
            ]
        ),
        encoding="utf-8",
    )
    prod_template.write_text(
        "\n".join(
            [
                "REAL_LLM_PREFLIGHT_ENABLED=false",
                "REAL_LLM_ACCEPTANCE_ENABLED=false",
                "REAL_LLM_SMOKE_ENABLED=false",
                "REAL_LLM_MODEL=",
                "REAL_LLM_API_KEY_ENV=OPENAI_API_KEY",
                "STORAGE_BACKEND=postgres",
                "DATABASE_URL=postgresql://agent:real-secret@db:5432/project_b",
                "REDIS_ENABLED=true",
                "REDIS_URL=redis://:<replace-with-strong-password>@redis:6379/0",
                "RATE_LIMIT_BACKEND=redis",
                "MCP_MODE=fake",
                "MCP_SERVER_COMMAND=",
                "MCP_SERVER_COMMAND_ALLOWLIST=",
                "MCP_TOOL_ALLOWLIST=",
                "MCP_SERVER_ENV_ALLOWLIST=",
                "MCP_SERVER_TIMEOUT_SECONDS=10",
                "REAL_INTEGRATION_STAGING_SMOKE_ENABLED=false",
                "REAL_LLM_STAGING_SMOKE_EXECUTE=false",
                "POSTGRES_STAGING_SMOKE_EXECUTE=false",
                "REDIS_STAGING_SMOKE_EXECUTE=false",
                "MCP_STAGING_SMOKE_EXECUTE=false",
            ]
        ),
        encoding="utf-8",
    )

    summary = build_real_integration_env_profile(
        output_dir=tmp_path / "out",
        development_template_path=dev_template,
        production_template_path=prod_template,
    )
    payload = _read_payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert payload["status"] == "blocked"
    assert "template:.env.production.example:DATABASE_URL:secret_like_plaintext" in payload["blocked_by"]
    assert "real-secret" not in merged


def test_real_integration_env_profile_redacts_literal_template_values_and_secret_like_paths(
    tmp_path: Path, monkeypatch
) -> None:
    _clear_env(monkeypatch)
    template_lines = "\n".join(
        [
            "REAL_LLM_PREFLIGHT_ENABLED=false",
            "REAL_LLM_ACCEPTANCE_ENABLED=false",
            "REAL_LLM_SMOKE_ENABLED=false",
            "REAL_LLM_PROVIDER=litellm",
            "REAL_LLM_MODEL=test-model",
            "REAL_LLM_BASE_URL=",
            "REAL_LLM_API_KEY_ENV=OPENAI_API_KEY",
            "REAL_LLM_PREFLIGHT_TIMEOUT_SECONDS=10",
            "REAL_LLM_PREFLIGHT_NETWORK_CHECK=false",
            "STORAGE_BACKEND=postgres",
            "DATABASE_URL=postgresql+psycopg://agent:<replace-with-strong-password>@postgres:5432/project_b",
            "REDIS_ENABLED=true",
            "REDIS_URL=redis://:<replace-with-strong-password>@redis:6379/0",
            "RATE_LIMIT_BACKEND=redis",
            "MCP_MODE=fake",
            "MCP_SERVER_COMMAND=node safe-server.js --tenant internal",
            "MCP_SERVER_COMMAND_ALLOWLIST=node",
            "MCP_TOOL_ALLOWLIST=safe_tool",
            "MCP_SERVER_ENV_ALLOWLIST=OPENAI_API_KEY",
            "MCP_SERVER_TIMEOUT_SECONDS=10",
            "REAL_INTEGRATION_STAGING_SMOKE_ENABLED=false",
            "REAL_LLM_STAGING_SMOKE_EXECUTE=false",
            "POSTGRES_STAGING_SMOKE_EXECUTE=false",
            "REDIS_STAGING_SMOKE_EXECUTE=false",
            "MCP_STAGING_SMOKE_EXECUTE=false",
        ]
    )
    template_root = tmp_path / "token=sk-sensitive-path"
    template_root.mkdir()
    dev_template = template_root / "dev.env"
    prod_template = template_root / "prod.env"
    dev_template.write_text(template_lines, encoding="utf-8")
    prod_template.write_text(template_lines, encoding="utf-8")

    summary = build_real_integration_env_profile(
        output_dir=tmp_path / "out",
        development_template_path=dev_template,
        production_template_path=prod_template,
    )
    payload = _read_payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert payload["profiles"][0]["development_template_expected_values"]["template_path"] == (
        "[redacted-secret-like-text]"
    )
    assert "node safe-server.js --tenant internal" not in merged
    assert "sk-sensitive-path" not in merged
    assert "[literal]" in merged


def test_real_integration_env_profile_partial_when_all_opt_in_present(tmp_path: Path, monkeypatch) -> None:
    _clear_env(monkeypatch)
    template_lines = "\n".join(
        [
            "REAL_LLM_PREFLIGHT_ENABLED=false",
            "REAL_LLM_ACCEPTANCE_ENABLED=false",
            "REAL_LLM_SMOKE_ENABLED=false",
            "REAL_LLM_PROVIDER=litellm",
            "REAL_LLM_MODEL=",
            "REAL_LLM_BASE_URL=",
            "REAL_LLM_API_KEY_ENV=OPENAI_API_KEY",
            "REAL_LLM_PREFLIGHT_TIMEOUT_SECONDS=10",
            "REAL_LLM_PREFLIGHT_NETWORK_CHECK=false",
            "STORAGE_BACKEND=postgres",
            "DATABASE_URL=postgresql+psycopg://agent:<replace-with-strong-password>@postgres:5432/project_b",
            "REDIS_ENABLED=true",
            "REDIS_URL=redis://:<replace-with-strong-password>@redis:6379/0",
            "RATE_LIMIT_BACKEND=redis",
            "MCP_MODE=fake",
            "MCP_SERVER_COMMAND=",
            "MCP_SERVER_COMMAND_ALLOWLIST=",
            "MCP_TOOL_ALLOWLIST=",
            "MCP_SERVER_ENV_ALLOWLIST=",
            "MCP_SERVER_TIMEOUT_SECONDS=10",
            "REAL_INTEGRATION_STAGING_SMOKE_ENABLED=false",
            "REAL_LLM_STAGING_SMOKE_EXECUTE=false",
            "POSTGRES_STAGING_SMOKE_EXECUTE=false",
            "REDIS_STAGING_SMOKE_EXECUTE=false",
            "MCP_STAGING_SMOKE_EXECUTE=false",
        ]
    )
    dev_template = tmp_path / "dev.env"
    prod_template = tmp_path / "prod.env"
    dev_template.write_text(template_lines, encoding="utf-8")
    prod_template.write_text(template_lines, encoding="utf-8")

    monkeypatch.setenv("REAL_LLM_PREFLIGHT_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_ACCEPTANCE_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_SMOKE_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_MODEL", "gpt-test")
    monkeypatch.setenv("REAL_LLM_API_KEY_ENV", "OPENAI_API_KEY")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-sensitive-real-secret")
    monkeypatch.setenv("STORAGE_BACKEND", "postgres")
    monkeypatch.setenv("DATABASE_URL", "placeholder-not-a-real-url")
    monkeypatch.setenv("REDIS_ENABLED", "true")
    monkeypatch.setenv("REDIS_URL", "placeholder-not-a-real-url")
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setenv("MCP_MODE", "real")
    monkeypatch.setenv("MCP_SERVER_COMMAND", "fake-mcp-server")
    monkeypatch.setenv("MCP_SERVER_COMMAND_ALLOWLIST", "fake-mcp-server")
    monkeypatch.setenv("MCP_TOOL_ALLOWLIST", "safe_tool")
    monkeypatch.setenv("MCP_SERVER_ENV_ALLOWLIST", "OPENAI_API_KEY")
    monkeypatch.setenv("MCP_SERVER_TIMEOUT_SECONDS", "10")
    monkeypatch.setenv("REAL_INTEGRATION_STAGING_SMOKE_ENABLED", "true")

    summary = build_real_integration_env_profile(
        output_dir=tmp_path / "out",
        development_template_path=dev_template,
        production_template_path=prod_template,
    )
    payload = _read_payload(summary)

    assert payload["status"] == "partial"
    assert payload["real_llm_executed"] is False
    assert payload["database_connected"] is False
    assert payload["redis_connected"] is False
    assert payload["external_mcp_connected"] is False
    real_llm = next(item for item in payload["profiles"] if item["domain_id"] == "real_llm")
    assert real_llm["target_env_present"]["target_env_present"] is True
