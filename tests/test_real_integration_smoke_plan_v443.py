from __future__ import annotations

import json
from pathlib import Path

from scripts.real_integration_smoke_plan import build_real_integration_smoke_plan


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
    ]:
        monkeypatch.delenv(key, raising=False)


def test_real_integration_smoke_plan_default_skipped(tmp_path: Path, monkeypatch) -> None:
    _clear_env(monkeypatch)
    summary = build_real_integration_smoke_plan(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert payload["phase"] == "v4.4 Phase 24.4"
    assert payload["version"] == "4.4.3"
    assert payload["domain_count"] == 4
    assert payload["go_no_go"]["combined_staging_gate"] == "Needs-Input"
    assert payload["go_no_go"]["public_production_direct_launch"] == "No-Go"
    assert payload["go_no_go"]["execute_parameter_available"] is False
    assert Path(summary["json_path"]).exists()
    assert Path(summary["markdown_path"]).exists()


def test_real_integration_smoke_plan_partial_when_four_domains_opted_in(tmp_path: Path, monkeypatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("REAL_LLM_PREFLIGHT_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_ACCEPTANCE_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_SMOKE_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_MODEL", "demo-model")
    monkeypatch.setenv("REAL_LLM_API_KEY_ENV", "OPENAI_API_KEY")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-sensitive-value")
    monkeypatch.setenv("STORAGE_BACKEND", "postgres")
    monkeypatch.setenv("DATABASE_URL", "postgresql://demo:secret@localhost/db")
    monkeypatch.setenv("REDIS_ENABLED", "true")
    monkeypatch.setenv("REDIS_URL", "redis://:secret@localhost:6379/0")
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setenv("MCP_MODE", "real")
    monkeypatch.setenv("MCP_SERVER_COMMAND", "fake-mcp-server")
    monkeypatch.setenv("MCP_SERVER_COMMAND_ALLOWLIST", "fake-mcp-server")
    monkeypatch.setenv("MCP_TOOL_ALLOWLIST", "safe_tool")

    summary = build_real_integration_smoke_plan(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert payload["status"] == "partial"
    assert payload["go_no_go"]["combined_staging_gate"] == "Manual-Review"
    assert {item["domain_id"] for item in payload["domains"]} == {
        "real_llm",
        "postgres",
        "redis",
        "external_mcp",
    }
    assert all(item["status"] == "partial" for item in payload["domains"])
    real_llm = next(item for item in payload["domains"] if item["domain_id"] == "real_llm")
    assert real_llm["target_secret_env_name"] == "OPENAI_API_KEY"
    assert real_llm["target_secret_env_present"] is True


def test_real_integration_smoke_plan_does_not_leak_secret_plaintext(tmp_path: Path, monkeypatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("REAL_LLM_API_KEY_ENV", "OPENAI_API_KEY")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-sensitive-value")
    monkeypatch.setenv("DATABASE_URL", "postgresql://demo:db-secret@localhost/db")
    monkeypatch.setenv("REDIS_URL", "redis://:redis-secret@localhost:6379/0")

    summary = build_real_integration_smoke_plan(output_dir=tmp_path / "out")
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert "sk-sensitive-value" not in merged
    assert "db-secret" not in merged
    assert "redis-secret" not in merged
    assert "postgresql://demo:db-secret@" not in merged
    assert "OPENAI_API_KEY" in merged


def test_real_integration_smoke_plan_blocks_secret_like_target_env_name(tmp_path: Path, monkeypatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("REAL_LLM_PREFLIGHT_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_ACCEPTANCE_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_SMOKE_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_MODEL", "demo-model")
    monkeypatch.setenv("REAL_LLM_API_KEY_ENV", "token=sk-sensitive-value")

    summary = build_real_integration_smoke_plan(output_dir=tmp_path / "out")
    payload = _read_payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert payload["status"] == "blocked"
    assert "target_secret_env_name_secret_like" in payload["blocked_by"]
    assert "token=sk-sensitive-value" not in merged


def test_real_integration_smoke_plan_required_flags_are_all_false_and_markdown_generated(
    tmp_path: Path, monkeypatch
) -> None:
    _clear_env(monkeypatch)
    summary = build_real_integration_smoke_plan(output_dir=tmp_path / "out")
    payload = _read_payload(summary)
    markdown = Path(summary["markdown_path"]).read_text(encoding="utf-8")

    for flag in [
        "real_llm_executed",
        "database_connected",
        "redis_connected",
        "external_mcp_connected",
        "migration_executed",
        "business_data_written",
        "audit_data_written",
        "metrics_data_written",
    ]:
        assert payload[flag] is False

    for domain in payload["domains"]:
        assert all(value is False for value in domain["execution_flags"].values())

    assert "## 域计划" in markdown
    assert "## Go/No-Go" in markdown


def test_real_integration_smoke_plan_redacts_secret_like_output_dir(tmp_path: Path, monkeypatch) -> None:
    _clear_env(monkeypatch)
    output_dir = tmp_path / "token=sk-sensitive-path" / "out"

    summary = build_real_integration_smoke_plan(output_dir=output_dir)
    payload = _read_payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert summary["output_dir"] == "[redacted-secret-like-text]"
    assert payload["output_dir"] == "[redacted-secret-like-text]"
    assert "sk-sensitive-path" not in merged
