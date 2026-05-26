from __future__ import annotations

import json
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from app.models.schemas import RiskLevel
from app.tools.mcp.stdio_client import StdioMCPClient, MCP_STDERR_MAX_CHARS


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


def test_health_initial_state():
    client = _build_client("normal")
    health = client.get_health()
    assert health["started"] is False
    assert health["initialized"] is False
    assert health["process_alive"] is False
    assert health["request_count"] == 0
    client.close()


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
    health = client.get_health()
    assert health["initialized"] is True
    assert health["process_alive"] is True
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
    assert "Invalid tools/list payload" in client.get_health()["last_error"]
    client.close()


def test_command_missing_no_crash():
    client = StdioMCPClient(server_name="missing_command", command="")
    tools = client.list_tools()
    assert tools == []
    result = client.call_tool("x", {})
    assert "error" in result
    assert "missing command" in result["error"]
    client.close()


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
    assert "not in allowlist" in result["error"]
    client.close()


def test_invalid_json_response_no_crash():
    client = _build_client("invalid-json")
    tools = client.list_tools()
    assert tools == []
    result = client.call_tool("x", {})
    assert "error" in result
    assert "invalid JSON" in result["error"] or "error" in result
    client.close()


def test_process_crash_no_crash_to_caller():
    client = _build_client("crash")
    tools = client.list_tools()
    assert tools == []
    result = client.call_tool("x", {})
    assert "error" in result
    health = client.get_health()
    assert health["failure_count"] >= 1
    client.close()


def test_call_tool_success_returns_dict():
    client = _build_client("normal")
    result = client.call_tool("stdio_date_lookup", {})
    assert result["date"] == "2026-05-25"
    assert result["source"] == "stdio"
    client.close()


def test_call_tool_unknown_tool_returns_error():
    client = _build_client("normal")
    result = client.call_tool("unknown_tool", {})
    assert "error" in result
    assert "unknown tool" in result["error"]
    client.close()


def test_call_tool_jsonrpc_error_returns_error():
    client = _build_client("tool-error")
    result = client.call_tool("stdio_date_lookup", {})
    assert "error" in result
    assert "tool call failed" in result["error"]
    client.close()


def test_call_tool_non_dict_result_wrapped_as_content():
    client = _build_client("malformed-result")
    result = client.call_tool("stdio_date_lookup", {})
    assert "content" in result
    assert isinstance(result["content"], list)
    client.close()


def test_close_terminates_process_and_is_idempotent():
    client = _build_client("normal")
    client.list_tools()
    assert client.get_health()["process_alive"] is True
    client.close()
    client.close()
    health = client.get_health()
    assert health["process_alive"] is False
    assert health["initialized"] is False


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
    client.close()


def test_crash_then_recover_on_next_list_tools(tmp_path):
    state_file = tmp_path / "once_crash.flag"
    client = StdioMCPClient(
        server_name="recover_crash",
        command=_python_command(),
        args=f"\"{_server_script()}\" once-crash-then-normal \"{state_file}\"",
        timeout_seconds=1.0,
    )
    first = client.list_tools()
    second = client.list_tools()
    if first == []:
        assert len(second) >= 2
    else:
        assert len(first) >= 2
    health = client.get_health()
    assert health["restart_count"] >= 1
    client.close()


def test_timeout_then_recover_on_next_list_tools(tmp_path):
    state_file = tmp_path / "timeout_once.flag"
    client = StdioMCPClient(
        server_name="recover_timeout",
        command=_python_command(),
        args=f"\"{_server_script()}\" timeout-once-then-normal \"{state_file}\"",
        timeout_seconds=0.5,
    )
    first = client.list_tools()
    second = client.list_tools()
    if first == []:
        assert len(second) >= 2
    else:
        assert len(first) >= 2
    health = client.get_health()
    assert health["restart_count"] >= 1
    assert health["process_alive"] is True
    client.close()


def test_call_tool_timeout_not_replayed(tmp_path):
    state_file = tmp_path / "timeout_once_call.flag"
    client = StdioMCPClient(
        server_name="call_timeout_once",
        command=_python_command(),
        args=f"\"{_server_script()}\" timeout-once-then-normal \"{state_file}\"",
        timeout_seconds=0.5,
    )
    result = client.call_tool("stdio_date_lookup", {})
    assert "error" in result
    assert state_file.exists()
    second = client.call_tool("stdio_date_lookup", {})
    assert second.get("source") == "stdio"
    health = client.get_health()
    assert health["restart_count"] >= 1
    client.close()


def test_concurrent_call_tool_serialized_no_id_mismatch():
    client = _build_client("normal")
    client.list_tools()

    def _call():
        return client.call_tool("stdio_date_lookup", {})

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(lambda _: _call(), range(10)))
    assert all("error" not in r for r in results)
    assert all(r.get("source") == "stdio" for r in results)
    health = client.get_health()
    assert health["request_count"] >= 11
    client.close()


def test_stderr_bounded_capture_and_health_error():
    client = _build_client("stderr-crash")
    result = client.list_tools()
    assert result == []
    health = client.get_health()
    assert health["last_error"]
    assert "stderr_tail" in health["last_error"] or "response" in health["last_error"]
    assert len(health["last_error"]) < MCP_STDERR_MAX_CHARS + 500
    client.close()


def test_timeout_recovery_has_no_stale_process(tmp_path):
    state_file = tmp_path / "timeout_stale_process.flag"
    client = StdioMCPClient(
        server_name="stale_process_check",
        command=_python_command(),
        args=f"\"{_server_script()}\" timeout-once-then-normal \"{state_file}\"",
        timeout_seconds=0.3,
    )
    client.list_tools()
    after_timeout = client.get_health()
    assert after_timeout["process_alive"] is True
    pid_after = after_timeout["pid"]
    tools = client.list_tools()
    assert len(tools) >= 2
    after_recovery = client.get_health()
    assert after_recovery["process_alive"] is True
    assert after_recovery["pid"] == pid_after
    client.close()


def test_initialize_client_version_is_260(tmp_path):
    capture_file = tmp_path / "init_params.json"
    client = StdioMCPClient(
        server_name="capture_init_version",
        command=_python_command(),
        args=f"\"{_server_script()}\" capture-init \"{capture_file}\"",
        timeout_seconds=1.0,
    )
    tools = client.list_tools()
    assert len(tools) >= 2
    assert capture_file.exists()
    payload = json.loads(capture_file.read_text(encoding="utf-8"))
    assert payload["clientInfo"]["name"] == "project-b"
    assert payload["clientInfo"]["version"] == "2.6.0"
    client.close()
