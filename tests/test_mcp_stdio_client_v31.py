from __future__ import annotations

import sys
from pathlib import Path

from app.models.schemas import RiskLevel
from app.tools.mcp.stdio_client import StdioMCPClient


def _server_script() -> str:
    return str((Path(__file__).parent / "fixtures" / "fake_mcp_stdio_server.py").resolve())


def _python_command() -> str:
    return sys.executable


def _build_client(mode: str = "normal", **kwargs) -> StdioMCPClient:
    return StdioMCPClient(
        server_name=kwargs.pop("server_name", f"fake_stdio_{mode}"),
        command=kwargs.pop("command", _python_command()),
        args=kwargs.pop("args", f"\"{_server_script()}\" {mode}"),
        timeout_seconds=kwargs.pop("timeout_seconds", 1.0),
        **kwargs,
    )


def test_list_tools_returns_mcp_toolinfo_and_mapping():
    client = _build_client("normal")
    tools = client.list_tools()
    assert len(tools) == 3
    by_name = {t.name: t for t in tools}

    assert "stdio_date_lookup" in by_name
    assert by_name["stdio_date_lookup"].risk_level == RiskLevel.low
    assert by_name["stdio_date_lookup"].permission_scope == "read"

    assert "stdio_refund_update" in by_name
    assert by_name["stdio_refund_update"].risk_level == RiskLevel.high
    assert by_name["stdio_refund_update"].permission_scope == "write"
    client.close()


def test_missing_risk_and_permission_use_defaults():
    client = _build_client("normal")
    tools = client.list_tools()
    by_name = {t.name: t for t in tools}
    tool = by_name["stdio_default_policy_tool"]
    assert tool.risk_level == RiskLevel.medium
    assert tool.permission_scope == "read"
    client.close()


def test_list_tools_supports_direct_list_shape():
    client = _build_client("tools-list-direct-list")
    tools = client.list_tools()
    names = [t.name for t in tools]
    assert "stdio_date_lookup" in names
    assert "stdio_refund_update" in names
    client.close()


def test_invalid_tool_item_skipped_without_crash():
    client = _build_client("normal")
    tools = client.list_tools()
    names = [t.name for t in tools]
    assert "" not in names
    assert len(tools) == 3
    client.close()


def test_tools_list_protocol_error_returns_empty():
    client = _build_client("tools-list-bad-structure")
    tools = client.list_tools()
    assert tools == []
    client.close()


def test_command_missing_no_crash():
    client = StdioMCPClient(server_name="missing_command", command="")
    tools = client.list_tools()
    assert tools == []
    result = client.call_tool("x", {})
    assert "error" in result
    assert "未配置 command" in result["error"]


def test_command_allowlist_blocks_unlisted_command():
    client = _build_client(
        "normal",
        command="python",
        command_allowlist="python3,node",
    )
    tools = client.list_tools()
    assert tools == []
    result = client.call_tool("x", {})
    assert "error" in result
    assert "不在 allowlist" in result["error"]


def test_invalid_json_response_no_crash():
    client = _build_client("invalid-json")
    tools = client.list_tools()
    assert tools == []
    result = client.call_tool("x", {})
    assert "error" in result
    client.close()


def test_process_crash_no_crash_to_caller():
    client = _build_client("crash")
    tools = client.list_tools()
    assert tools == []
    result = client.call_tool("x", {})
    assert "error" in result
    client.close()


def test_call_tool_still_not_implemented_phase33():
    client = _build_client("normal")
    result = client.call_tool("stdio_date_lookup", {})
    assert "error" in result
    assert "Phase 3.3" in result["error"]
    client.close()


def test_close_terminates_process():
    client = _build_client("no-response")
    client._start_process()
    assert client._process is not None
    client.close()
    assert client._process is None or client._process.poll() is not None


def test_shell_false_via_monkeypatch(monkeypatch):
    called = {}

    class _DummyProc:
        def __init__(self):
            self.stdin = None
            self.stdout = None
            self.stderr = None

        def poll(self):
            return 0

        def terminate(self):
            return None

        def kill(self):
            return None

        def wait(self, timeout=None):
            return 0

    def _fake_popen(*args, **kwargs):
        called["kwargs"] = kwargs
        return _DummyProc()

    import app.tools.mcp.stdio_client as stdio_mod

    monkeypatch.setattr(stdio_mod.subprocess, "Popen", _fake_popen)
    client = StdioMCPClient(server_name="shell_false", command="python", args="x.py")
    client._start_process()
    assert called["kwargs"]["shell"] is False
