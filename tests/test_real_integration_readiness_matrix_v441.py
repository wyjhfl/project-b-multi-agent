from __future__ import annotations

import json
from pathlib import Path

from scripts.real_integration_readiness_matrix import build_real_integration_readiness_matrix


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _clear_real_integration_env(monkeypatch) -> None:
    for key in [
        "REAL_LLM_PREFLIGHT_ENABLED",
        "REAL_LLM_ACCEPTANCE_ENABLED",
        "REAL_LLM_SMOKE_ENABLED",
        "REAL_LLM_MODEL",
        "REAL_LLM_API_KEY_ENV",
        "LLM_BUDGET_ENABLED",
        "STORAGE_BACKEND",
        "DATABASE_URL",
        "REDIS_ENABLED",
        "REDIS_URL",
        "MCP_MODE",
        "MCP_SERVER_COMMAND",
        "MCP_SERVER_COMMAND_ALLOWLIST",
        "MCP_TOOL_ALLOWLIST",
        "MCP_SERVER_ENV_ALLOWLIST",
        "MCP_SERVER_TIMEOUT_SECONDS",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_real_integration_readiness_matrix_generates_outputs(tmp_path: Path, monkeypatch) -> None:
    _clear_real_integration_env(monkeypatch)
    summary = build_real_integration_readiness_matrix(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert summary["read_only"] is True
    assert summary["real_llm_executed"] is False
    assert summary["database_connected"] is False
    assert summary["redis_connected"] is False
    assert summary["external_mcp_connected"] is False
    assert payload["version"] == "4.4.1"
    assert payload["phase"] == "v4.4 Phase 24.1"
    assert payload["integration_count"] == 4
    assert payload["component_count"] == 4
    assert payload["provider_network_check_executed"] is False
    assert payload["mcp_process_started"] is False
    assert payload["mcp_tools_list_executed"] is False
    assert payload["mcp_tools_call_executed"] is False
    assert payload["business_system_connected"] is False
    assert Path(summary["markdown_path"]).exists()


def test_real_integration_readiness_matrix_covers_required_components(tmp_path: Path, monkeypatch) -> None:
    _clear_real_integration_env(monkeypatch)
    summary = build_real_integration_readiness_matrix(output_dir=tmp_path / "out")
    payload = _read_payload(summary)
    component_ids = {item["integration_id"] for item in payload["integrations"]}

    assert {"real_llm", "postgres", "redis", "external_mcp"} <= component_ids


def test_real_integration_readiness_matrix_partial_when_all_opt_in_present(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("REAL_LLM_PREFLIGHT_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_ACCEPTANCE_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_SMOKE_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_MODEL", "test-model")
    monkeypatch.setenv("REAL_LLM_API_KEY_ENV", "OPENAI_API_KEY")
    monkeypatch.setenv("STORAGE_BACKEND", "postgres")
    monkeypatch.setenv("DATABASE_URL", "placeholder-not-a-url")
    monkeypatch.setenv("REDIS_ENABLED", "true")
    monkeypatch.setenv("REDIS_URL", "placeholder-not-a-url")
    monkeypatch.setenv("MCP_MODE", "real")
    monkeypatch.setenv("MCP_SERVER_COMMAND", "fake-mcp-server")
    monkeypatch.setenv("MCP_SERVER_COMMAND_ALLOWLIST", "fake-mcp-server")
    monkeypatch.setenv("MCP_TOOL_ALLOWLIST", "safe_tool")

    summary = build_real_integration_readiness_matrix(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert payload["status"] == "partial"
    assert payload["real_llm_executed"] is False
    assert payload["database_connected"] is False
    assert payload["redis_connected"] is False
    assert payload["external_mcp_connected"] is False
    assert payload["migration_executed"] is False
    assert payload["go_no_go"]["public_production_direct_launch"] == "No-Go"


def test_real_integration_readiness_matrix_does_not_leak_secret_values(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("REAL_LLM_API_KEY_ENV", "OPENAI_API_KEY")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-sensitive-value")
    monkeypatch.setenv("DATABASE_URL", "postgresql://demo:db-secret@localhost/db")
    monkeypatch.setenv("REDIS_URL", "redis://:redis-secret@localhost:6379/0")
    monkeypatch.setenv("MCP_SERVER_COMMAND", "node safe-server.js")
    monkeypatch.setenv("MCP_SERVER_ENV_ALLOWLIST", "OPENAI_API_KEY")

    summary = build_real_integration_readiness_matrix(output_dir=tmp_path / "out")
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert "sk-sensitive-value" not in merged
    assert "db-secret" not in merged
    assert "redis-secret" not in merged
    assert "postgresql://demo:db-secret@" not in merged
    assert "REAL_LLM_API_KEY_ENV" in merged
    assert "DATABASE_URL" in merged
    assert "REDIS_URL" in merged


def test_real_integration_readiness_matrix_records_local_evidence_without_connections(
    tmp_path: Path, monkeypatch
) -> None:
    _clear_real_integration_env(monkeypatch)
    summary = build_real_integration_readiness_matrix(output_dir=tmp_path / "out")
    payload = _read_payload(summary)
    postgres = next(item for item in payload["components"] if item["component_id"] == "postgres")
    redis = next(item for item in payload["components"] if item["component_id"] == "redis")
    mcp = next(item for item in payload["integrations"] if item["integration_id"] == "external_mcp")

    assert postgres["local_checks"]["store_factory"]["present"] is True
    assert redis["local_checks"]["redis_client"]["present"] is True
    assert mcp["local_checks"]["stdio_client"]["present"] is True
    assert payload["database_connected"] is False
    assert payload["redis_connected"] is False
    assert payload["external_mcp_connected"] is False
