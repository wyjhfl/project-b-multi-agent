from __future__ import annotations

import os
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.harness.gateway.tool_gateway import ToolGateway
from app.main import app, reset_runtime_for_test
from app.models.schemas import RiskLevel, ToolCallStatus, ToolSpec
from app.tools.mcp.client import FakeMCPClient, MCPClient, MCPToolInfo

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "db", "ops_demo.sqlite")


def _ensure_db():
    if not os.path.exists(DB_PATH):
        from scripts.init_demo_db import init_db
        init_db()


_ensure_db()

client = TestClient(app)


def test_fake_mcp_client_list_tools_returns_3():
    fake = FakeMCPClient()
    tools = fake.list_tools()
    assert len(tools) == 3
    names = [t.name for t in tools]
    assert "date_lookup" in names
    assert "calculator" in names
    assert "rule_lookup" in names


def test_gateway_discover_mcp_tools_registers():
    gateway = ToolGateway()
    fake = FakeMCPClient()
    gateway.register_mcp_server("fake_ops_mcp", fake)
    specs = gateway.discover_mcp_tools("fake_ops_mcp")
    assert len(specs) == 3
    for spec in specs:
        assert spec.source == "mcp"
        assert spec.server_name == "fake_ops_mcp"
        assert spec.mcp_tool_name is not None
        assert spec.is_local is False
    registered = gateway.list_tools()
    assert len(registered) == 3
    tool_names = [t.tool_name for t in registered]
    assert "date_lookup" in tool_names
    assert "calculator" in tool_names
    assert "rule_lookup" in tool_names


def test_gateway_call_date_lookup_success():
    gateway = ToolGateway()
    fake = FakeMCPClient()
    gateway.register_mcp_server("fake_ops_mcp", fake)
    gateway.discover_mcp_tools("fake_ops_mcp")
    record = gateway.call("date_lookup")
    assert record.status == ToolCallStatus.completed
    assert record.success is True
    assert record.result is not None
    assert "date" in record.result
    assert "month" in record.result
    assert "year" in record.result


def test_gateway_call_calculator_add():
    gateway = ToolGateway()
    fake = FakeMCPClient()
    gateway.register_mcp_server("fake_ops_mcp", fake)
    gateway.discover_mcp_tools("fake_ops_mcp")
    record = gateway.call("calculator", {"operation": "add", "a": 1, "b": 2})
    assert record.status == ToolCallStatus.completed
    assert record.success is True
    assert record.result["result"] == 3


def test_mcp_tool_error_returns_failed_record():
    gateway = ToolGateway()
    fake = FakeMCPClient()
    gateway.register_mcp_server("fake_ops_mcp", fake)
    gateway.discover_mcp_tools("fake_ops_mcp")
    record = gateway.call("calculator", {"operation": "unknown_op", "a": 1, "b": 2})
    assert record.status == ToolCallStatus.failed
    assert record.success is False
    assert record.error is not None

    record2 = gateway.call("nonexistent_mcp_tool")
    assert record2.status == ToolCallStatus.failed
    assert record2.success is False


def test_get_tools_includes_local_and_mcp():
    reset_runtime_for_test()
    response = client.get("/tools")
    assert response.status_code == 200
    tools = response.json()
    sources = {t["source"] for t in tools}
    assert "local" in sources
    assert "mcp" in sources
    tool_names = [t["tool_name"] for t in tools]
    assert "get_today_gmv" in tool_names
    assert "date_lookup" in tool_names
    assert "calculator" in tool_names
    assert "rule_lookup" in tool_names
    reset_runtime_for_test()


def test_post_tools_date_lookup_call():
    reset_runtime_for_test()
    response = client.post("/tools/date_lookup/call", json={"arguments": {}})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["status"] == "completed"
    assert data["result"] is not None
    assert "date" in data["result"]
    reset_runtime_for_test()


def test_tasks_keyword_date_lookup():
    reset_runtime_for_test()
    response = client.post("/tasks", json={"query": "今天几号"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["result"]["success"] is True
    assert data["result"]["tool_called"] == "date_lookup"
    assert "date" in data["result"]["data"]
    reset_runtime_for_test()


def test_existing_local_tools_still_work():
    gateway = ToolGateway()
    fake = FakeMCPClient()
    gateway.register_mcp_server("fake_ops_mcp", fake)
    gateway.discover_mcp_tools("fake_ops_mcp")

    def mock_gmv():
        return {"date": "2026-05-23", "gmv": 12345.6, "currency": "CNY"}

    gateway.register(
        ToolSpec(
            tool_name="get_today_gmv",
            description="获取今日 GMV",
            risk_level=RiskLevel.low,
            source="local",
            is_local=True,
        ),
        mock_gmv,
    )
    record = gateway.call("get_today_gmv")
    assert record.status == ToolCallStatus.completed
    assert record.success is True
    assert record.result["gmv"] == 12345.6

    mcp_record = gateway.call("date_lookup")
    assert mcp_record.status == ToolCallStatus.completed
    assert mcp_record.success is True
