from __future__ import annotations

from pathlib import Path

from app.tools.mcp.stdio_client import StdioMCPClient


def _server_script() -> str:
    return str((Path(__file__).parent / "fixtures" / "fake_mcp_stdio_server.py").resolve())


def test_initialize_success_and_list_tools_returns_empty():
    client = StdioMCPClient(
        server_name="fake_stdio",
        command="python",
        args=f"\"{_server_script()}\" normal",
        timeout_seconds=1.0,
    )
    tools = client.list_tools()
    assert tools == []
    assert client._initialized is True
    client.close()


def test_command_missing_no_crash():
    client = StdioMCPClient(server_name="missing_command", command="")
    tools = client.list_tools()
    assert tools == []
    result = client.call_tool("x", {})
    assert "error" in result
    assert "未配置 command" in result["error"]


def test_command_allowlist_blocks_unlisted_command():
    client = StdioMCPClient(
        server_name="allowlist_blocked",
        command="python",
        args=f"\"{_server_script()}\" normal",
        command_allowlist="node,python3",
    )
    tools = client.list_tools()
    assert tools == []
    result = client.call_tool("x", {})
    assert "error" in result
    assert "不在 allowlist" in result["error"]


def test_invalid_json_response_no_crash():
    client = StdioMCPClient(
        server_name="invalid_json",
        command="python",
        args=f"\"{_server_script()}\" invalid-json",
        timeout_seconds=1.0,
    )
    tools = client.list_tools()
    assert tools == []
    result = client.call_tool("x", {})
    assert "error" in result
    client.close()


def test_process_crash_no_crash_to_caller():
    client = StdioMCPClient(
        server_name="crash_server",
        command="python",
        args=f"\"{_server_script()}\" crash",
        timeout_seconds=1.0,
    )
    tools = client.list_tools()
    assert tools == []
    result = client.call_tool("x", {})
    assert "error" in result
    client.close()


def test_close_terminates_process():
    client = StdioMCPClient(
        server_name="close_server",
        command="python",
        args=f"\"{_server_script()}\" no-response",
        timeout_seconds=1.0,
    )
    # force start process
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
    # _start_process only
    client._start_process()
    assert called["kwargs"]["shell"] is False
