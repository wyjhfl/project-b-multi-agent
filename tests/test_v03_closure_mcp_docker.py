from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.harness.eval.multi_agent_runner import MultiAgentEvalResult
from app.main import app, reset_runtime_for_test

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "db", "ops_demo.sqlite")


def _ensure_db():
    if not os.path.exists(DB_PATH):
        from scripts.init_demo_db import init_db
        init_db()


_ensure_db()

client = TestClient(app)


def test_eval_result_no_shared_mutable_defaults():
    r1 = MultiAgentEvalResult()
    r2 = MultiAgentEvalResult()
    assert r1.failures is not r2.failures
    assert r1.bad_cases is not r2.bad_cases
    r1.failures.append.__module__
    r1.failures.append(
        __import__("app.harness.eval.multi_agent_runner", fromlist=["EvalFailure"]).EvalFailure(
            case_id="test", query="q", reason="r"
        )
    )
    assert len(r1.failures) == 1
    assert len(r2.failures) == 0


def test_fake_mcp_mode_includes_mcp_tools():
    reset_runtime_for_test()
    with patch("app.core.config.Settings.model_post_init", lambda self, __: None):
        response = client.get("/tools")
    assert response.status_code == 200
    tools = response.json()
    tool_names = [t["tool_name"] for t in tools]
    assert "date_lookup" in tool_names
    assert "calculator" in tool_names
    assert "rule_lookup" in tool_names
    reset_runtime_for_test()


def test_real_mcp_mode_empty_command_no_crash():
    reset_runtime_for_test()
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.mcp_mode = "real"
        mock_settings.mcp_server_name = "test_real_mcp"
        mock_settings.mcp_server_command = ""
        mock_settings.mcp_server_args = ""
        mock_settings.mcp_server_timeout_seconds = 10.0

        from app.main import _register_mcp_tools
        from app.harness.gateway.tool_gateway import ToolGateway

        gateway = ToolGateway()
        from app.main import _register_tools
        _register_tools(gateway)
        _register_mcp_tools(gateway)

        local_tools = [t for t in gateway.list_tools() if t.source == "local"]
        assert len(local_tools) >= 5

    reset_runtime_for_test()


def test_stdio_mcp_client_empty_command_error():
    from app.tools.mcp.stdio_client import StdioMCPClient, MCPConfigError

    client_instance = StdioMCPClient(
        server_name="test_server",
        command="",
    )

    with pytest.raises(MCPConfigError):
        client_instance._ensure_configured()

    tools = client_instance.list_tools()
    assert tools == []

    result = client_instance.call_tool("any_tool", {})
    assert "error" in result
    assert "未配置 command" in result["error"]


def test_docker_compose_file_exists():
    project_root = os.path.dirname(__file__) + "/.."
    compose_path = os.path.join(project_root, "docker-compose.yml")
    assert os.path.exists(compose_path)

    with open(compose_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "app" in content
    assert "8000" in content


def test_dockerfile_exists():
    project_root = os.path.dirname(__file__) + "/.."
    dockerfile_path = os.path.join(project_root, "Dockerfile")
    assert os.path.exists(dockerfile_path)

    with open(dockerfile_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "uvicorn" in content
    assert "app.main:app" in content


def test_check_health_script_exists():
    project_root = os.path.dirname(__file__) + "/.."
    script_path = os.path.join(project_root, "scripts", "check_health.py")
    assert os.path.exists(script_path)

    with open(script_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "/health" in content
    assert "/tools" in content
    assert "/eval/summary" in content
    assert "/observability/tasks/summary" in content


def _fake_stdio_script() -> str:
    return str((Path(__file__).parent / "fixtures" / "fake_mcp_stdio_server.py").resolve())


def test_real_mode_allowlist_allows_stdio_tools(monkeypatch):
    reset_runtime_for_test()
    from app.core.config import settings
    from app.main import get_gateway

    command = sys.executable
    monkeypatch.setattr(settings, "mcp_mode", "real")
    monkeypatch.setattr(settings, "mcp_server_name", "fake_stdio_allow")
    monkeypatch.setattr(settings, "mcp_server_command", command)
    monkeypatch.setattr(settings, "mcp_server_args", f"\"{_fake_stdio_script()}\" normal")
    monkeypatch.setattr(settings, "mcp_server_timeout_seconds", 1.0)
    monkeypatch.setattr(settings, "mcp_server_workdir", "")
    monkeypatch.setattr(settings, "mcp_server_env_allowlist", "")
    monkeypatch.setattr(settings, "mcp_server_command_allowlist", command)

    gateway = get_gateway()
    tools = gateway.list_tools()
    tool_names = [t.tool_name for t in tools]
    assert "stdio_date_lookup" in tool_names
    assert "get_today_gmv" in tool_names
    reset_runtime_for_test()


def test_real_mode_allowlist_blocks_unlisted_command_but_local_tools_remain(monkeypatch):
    reset_runtime_for_test()
    from app.core.config import settings
    from app.main import get_gateway

    command = sys.executable
    monkeypatch.setattr(settings, "mcp_mode", "real")
    monkeypatch.setattr(settings, "mcp_server_name", "fake_stdio_blocked")
    monkeypatch.setattr(settings, "mcp_server_command", command)
    monkeypatch.setattr(settings, "mcp_server_args", f"\"{_fake_stdio_script()}\" normal")
    monkeypatch.setattr(settings, "mcp_server_timeout_seconds", 1.0)
    monkeypatch.setattr(settings, "mcp_server_workdir", "")
    monkeypatch.setattr(settings, "mcp_server_env_allowlist", "")
    monkeypatch.setattr(settings, "mcp_server_command_allowlist", "python3,node")

    gateway = get_gateway()
    tools = gateway.list_tools()
    tool_names = [t.tool_name for t in tools]
    assert "stdio_date_lookup" not in tool_names
    assert "stdio_refund_update" not in tool_names
    assert "get_today_gmv" in tool_names
    reset_runtime_for_test()


def test_real_mode_tools_api_call_stdio_smoke(monkeypatch):
    reset_runtime_for_test()
    from app.core.config import settings

    command = sys.executable
    monkeypatch.setattr(settings, "mcp_mode", "real")
    monkeypatch.setattr(settings, "mcp_server_name", "fake_stdio_tools_api")
    monkeypatch.setattr(settings, "mcp_server_command", command)
    monkeypatch.setattr(settings, "mcp_server_args", f"\"{_fake_stdio_script()}\" normal")
    monkeypatch.setattr(settings, "mcp_server_timeout_seconds", 1.0)
    monkeypatch.setattr(settings, "mcp_server_workdir", "")
    monkeypatch.setattr(settings, "mcp_server_env_allowlist", "")
    monkeypatch.setattr(settings, "mcp_server_command_allowlist", command)

    response = client.post("/tools/stdio_date_lookup/call", json={"arguments": {}})
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["result"]["source"] == "stdio"
    reset_runtime_for_test()
