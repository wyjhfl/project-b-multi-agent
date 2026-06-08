from __future__ import annotations

import json
from pathlib import Path

from scripts.production_landing_local_mcp_bootstrap import build_production_landing_local_mcp_bootstrap


def _codex_python(script_command: str) -> str:
    return "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\codex_python.ps1 " + script_command.replace(
        "/", "\\"
    )


def test_local_mcp_bootstrap_writes_controlled_stdio_fixture_config(tmp_path: Path) -> None:
    env_path = tmp_path / "local" / "production_landing.staging.env"

    summary = build_production_landing_local_mcp_bootstrap(env_path=env_path)
    env_text = env_path.read_text(encoding="utf-8")
    summary_text = json.dumps(summary, ensure_ascii=False)

    assert summary["env_file_present"] is True
    assert summary["mcp_server_fixture_present"] is True
    assert summary["mcp_command_configured"] is True
    assert summary["mcp_command_allowlist_configured"] is True
    assert summary["mcp_tool_allowlist"] == ["stdio_date_lookup"]
    assert "MCP_STAGING_SMOKE_EXECUTE=true" in env_text
    assert "MCP_MODE=real" in env_text
    assert "MCP_SERVER_COMMAND=" in env_text
    assert "local_fake_mcp_stdio_server.py normal" in env_text
    assert "MCP_SERVER_COMMAND_ALLOWLIST=" in env_text
    assert "MCP_TOOL_ALLOWLIST=stdio_date_lookup" in env_text
    assert "stdio_refund_update" not in env_text
    assert _codex_python("scripts/production_landing_env_runner.py --action staging-smoke") in summary["next_commands"]
    assert not any(command.startswith("python scripts/") for command in summary["next_commands"])
    assert "token=" not in summary_text.lower()
    assert summary["secret_plaintext_output"] is False
