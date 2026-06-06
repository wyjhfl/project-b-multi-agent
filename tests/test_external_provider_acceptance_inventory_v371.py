from __future__ import annotations

import json
from pathlib import Path

from scripts.external_provider_acceptance_inventory import build_external_provider_acceptance_inventory


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def test_external_provider_inventory_generates_outputs(tmp_path: Path) -> None:
    summary = build_external_provider_acceptance_inventory(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] in {"partial", "skipped"}
    assert summary["read_only"] is True
    assert summary["real_llm_executed"] is False
    assert summary["external_mcp_connected"] is False
    assert summary["business_system_connected"] is False
    assert payload["version"] == "3.7.0"
    assert payload["phase"] == "v3.7 Phase 17.1"
    assert payload["integration_count"] == 8
    assert Path(summary["markdown_path"]).exists()


def test_external_provider_inventory_covers_required_integrations(tmp_path: Path) -> None:
    summary = build_external_provider_acceptance_inventory(output_dir=tmp_path / "out")
    payload = _read_payload(summary)
    ids = {item["integration_id"] for item in payload["integrations"]}

    assert {
        "external_mcp",
        "real_llm_provider",
        "llm_judge_provider",
        "postgres_store",
        "redis_runtime",
        "deployment_guard",
        "tool_approval_audit",
        "frontend_offline_build",
    } <= ids


def test_external_provider_inventory_keeps_default_offline_boundary(tmp_path: Path, monkeypatch) -> None:
    for key in [
        "MCP_MODE",
        "REAL_LLM_SMOKE_ENABLED",
        "REAL_LLM_ACCEPTANCE_ENABLED",
        "REAL_LLM_PREFLIGHT_ENABLED",
        "REAL_LLM_PREFLIGHT_NETWORK_CHECK",
        "REAL_LLM_MODEL",
        "REAL_LLM_API_KEY_ENV",
    ]:
        monkeypatch.delenv(key, raising=False)

    summary = build_external_provider_acceptance_inventory(output_dir=tmp_path / "out")
    payload = _read_payload(summary)
    real_llm = next(item for item in payload["integrations"] if item["integration_id"] == "real_llm_provider")
    external_mcp = next(item for item in payload["integrations"] if item["integration_id"] == "external_mcp")

    assert payload["real_llm_executed"] is False
    assert payload["external_mcp_connected"] is False
    assert payload["business_system_connected"] is False
    assert any("REAL_LLM_SMOKE_ENABLED" in item for item in real_llm["missing_conditions"])
    assert any("MCP_MODE" in item for item in external_mcp["missing_conditions"])


def test_external_provider_inventory_does_not_leak_secret_values(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("REAL_LLM_API_KEY_ENV", "OPENAI_API_KEY")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-sensitive-value")
    monkeypatch.setenv("DATABASE_URL", "postgresql://demo:secret@localhost/db")
    monkeypatch.setenv("REDIS_URL", "redis://:redis-secret@localhost:6379/0")
    monkeypatch.setenv("JWT_SECRET", "jwt-secret-plain")

    summary = build_external_provider_acceptance_inventory(output_dir=tmp_path / "out")
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert "sk-sensitive-value" not in merged
    assert "postgresql://demo:secret@" not in merged
    assert "redis-secret" not in merged
    assert "jwt-secret-plain" not in merged
    assert "REAL_LLM_API_KEY_ENV" in merged
    assert "DATABASE_URL" in merged
    assert "REDIS_URL" in merged


def test_external_provider_inventory_records_local_evidence_without_external_calls(tmp_path: Path) -> None:
    summary = build_external_provider_acceptance_inventory(output_dir=tmp_path / "out")
    payload = _read_payload(summary)
    tool_boundary = next(item for item in payload["integrations"] if item["integration_id"] == "tool_approval_audit")
    frontend = next(item for item in payload["integrations"] if item["integration_id"] == "frontend_offline_build")

    assert tool_boundary["local_checks"]["tool_gateway"]["present"] is True
    assert tool_boundary["local_checks"]["policy_engine"]["present"] is True
    assert frontend["local_checks"]["layout"]["present"] is True
    assert payload["database_migration_executed"] is False
    assert payload["redis_write_executed"] is False
