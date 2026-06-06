from __future__ import annotations

import json
from pathlib import Path

from scripts.external_mcp_acceptance_gate import build_external_mcp_acceptance_gate


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _clear_mcp_env(monkeypatch) -> None:
    for key in [
        "MCP_MODE",
        "MCP_SERVER_COMMAND",
        "MCP_SERVER_COMMAND_ALLOWLIST",
        "MCP_TOOL_ALLOWLIST",
        "MCP_SERVER_TIMEOUT_SECONDS",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_external_mcp_acceptance_gate_generates_outputs(tmp_path: Path, monkeypatch) -> None:
    _clear_mcp_env(monkeypatch)
    summary = build_external_mcp_acceptance_gate(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert summary["read_only"] is True
    assert summary["external_mcp_connected"] is False
    assert summary["mcp_process_started"] is False
    assert payload["version"] == "3.7.0"
    assert payload["phase"] == "v3.7 Phase 17.2"
    assert payload["check_count"] == len(payload["acceptance_checks"])
    assert Path(summary["markdown_path"]).exists()


def test_external_mcp_acceptance_gate_covers_required_checks(tmp_path: Path, monkeypatch) -> None:
    _clear_mcp_env(monkeypatch)
    summary = build_external_mcp_acceptance_gate(output_dir=tmp_path / "out")
    payload = _read_payload(summary)
    check_ids = {item["check_id"] for item in payload["acceptance_checks"]}

    assert {
        "real_mode_opt_in",
        "command_configured",
        "command_allowlist",
        "tool_allowlist",
        "timeout_config",
        "lifecycle_hardening",
        "approval_audit_boundary",
        "fake_fixture_coverage",
    } <= check_ids


def test_external_mcp_acceptance_gate_blocks_command_not_allowlisted(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MCP_MODE", "real")
    monkeypatch.setenv("MCP_SERVER_COMMAND", "python")
    monkeypatch.setenv("MCP_SERVER_COMMAND_ALLOWLIST", "node")
    monkeypatch.setenv("MCP_TOOL_ALLOWLIST", "safe_tool")
    monkeypatch.setenv("MCP_SERVER_TIMEOUT_SECONDS", "10")

    summary = build_external_mcp_acceptance_gate(output_dir=tmp_path / "out")
    payload = _read_payload(summary)
    command_allowlist = next(item for item in payload["acceptance_checks"] if item["check_id"] == "command_allowlist")

    assert payload["status"] == "blocked"
    assert command_allowlist["status"] == "blocked"
    assert command_allowlist["evidence"]["command_in_allowlist"] is False
    assert payload["mcp_process_started"] is False


def test_external_mcp_acceptance_gate_partial_when_real_config_present(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MCP_MODE", "real")
    monkeypatch.setenv("MCP_SERVER_COMMAND", "python")
    monkeypatch.setenv("MCP_SERVER_COMMAND_ALLOWLIST", "python,node")
    monkeypatch.setenv("MCP_TOOL_ALLOWLIST", "safe_tool")
    monkeypatch.setenv("MCP_SERVER_TIMEOUT_SECONDS", "10")

    summary = build_external_mcp_acceptance_gate(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert payload["status"] == "partial"
    assert payload["external_mcp_connected"] is False
    assert payload["mcp_tools_list_executed"] is False
    assert payload["mcp_tools_call_executed"] is False
    assert payload["secret_plaintext_output"] is False


def test_external_mcp_acceptance_gate_does_not_leak_secret_values(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MCP_MODE", "real")
    monkeypatch.setenv("MCP_SERVER_COMMAND", "python")
    monkeypatch.setenv("MCP_SERVER_COMMAND_ALLOWLIST", "python")
    monkeypatch.setenv("MCP_TOOL_ALLOWLIST", "safe_tool")
    monkeypatch.setenv("MCP_SERVER_TIMEOUT_SECONDS", "10")
    monkeypatch.setenv("MCP_SERVER_ARGS", "--token sk-sensitive-value")

    summary = build_external_mcp_acceptance_gate(output_dir=tmp_path / "out")
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert "sk-sensitive-value" not in merged
    assert "MCP_SERVER_COMMAND" in merged
    assert "MCP_TOOL_ALLOWLIST" in merged
