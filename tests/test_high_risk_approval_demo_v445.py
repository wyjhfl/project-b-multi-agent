from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.agent.nodes.planner import KeywordPlanner
from app.core.config import settings
from app.harness.gateway.tool_gateway import ToolGateway
from app.main import app, reset_runtime_for_test
from app.models.schemas import RiskLevel
from app.tools.local.ops_query import simulate_refund_order

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "db", "ops_demo.sqlite")


def _ensure_db():
    if not os.path.exists(DB_PATH):
        from scripts.init_demo_db import init_db
        init_db()


_ensure_db()

client = TestClient(app)


@pytest.fixture()
def isolated_runtime(monkeypatch, tmp_path):
    """将 runtime 库指向临时目录并重建运行时，避免污染仓库数据"""
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    reset_runtime_for_test()
    yield
    reset_runtime_for_test()


def _build_registered_gateway() -> ToolGateway:
    gateway = ToolGateway()
    from app.main import _register_tools
    _register_tools(gateway)
    return gateway


# ---------- 工具注册与路由 ----------


def test_simulate_refund_order_registered_as_high_risk():
    gateway = _build_registered_gateway()
    spec = gateway.get_tool("simulate_refund_order")
    assert spec is not None
    assert spec.risk_level == RiskLevel.high
    assert spec.permission_scope == "write"


def test_simulate_refund_order_pure_simulation():
    """工具为纯内存仿真，不触碰真实数据"""
    result = simulate_refund_order(order_id="ORD-1001", amount=50.0)
    assert result["simulated"] is True
    assert result["order_id"] == "ORD-1001"
    assert result["refund_id"].startswith("SIM-RF-")


def test_simulate_refund_order_not_registered_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "demo_high_risk_tool_enabled", False)
    gateway = _build_registered_gateway()
    assert gateway.get_tool("simulate_refund_order") is None


def test_planner_routes_simulate_refund_when_enabled():
    plan = KeywordPlanner().plan("为订单ORD-1001模拟退款")
    assert plan["matched"] is True
    assert plan["tool_name"] == "simulate_refund_order"


def test_planner_falls_back_to_refund_rate_when_disabled(monkeypatch):
    """开关关闭时保持历史行为：“模拟退款”按“退款”词条命中 get_refund_rate"""
    monkeypatch.setattr(settings, "demo_high_risk_tool_enabled", False)
    plan = KeywordPlanner().plan("模拟退款怎么处理")
    assert plan["tool_name"] == "get_refund_rate"


# ---------- keyword 模式端到端审批链路 ----------


def test_keyword_high_risk_full_approval_resume_chain(isolated_runtime):
    """PolicyEngine 拦截 → 审批单创建 → waiting_approval → 审批通过 → resume → completed"""
    response = client.post("/tasks", json={"query": "为订单ORD-1001模拟退款", "mode": "keyword"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "waiting_approval"
    result = data["result"]
    assert result["requires_approval"] is True
    assert result["tool_called"] == "simulate_refund_order"
    assert result["risk_level"] == "high"
    approval_id = result["approval_id"]
    assert approval_id.startswith("apr_")
    task_id = data["task_id"]

    pending = client.get("/approvals", params={"status": "pending"}).json()
    assert any(a["approval_id"] == approval_id for a in pending)

    approve_resp = client.post(
        f"/approvals/{approval_id}/approve",
        json={"decided_by": "admin", "reason": "确认执行", "auto_resume": True},
    )
    assert approve_resp.status_code == 200
    approve_data = approve_resp.json()
    assert approve_data["status"] == "approved"
    resume_result = approve_data["resume_result"]
    assert resume_result["success"] is True
    assert resume_result["tool_called"] == "simulate_refund_order"
    assert resume_result["data"]["simulated"] is True

    task_row = client.get(f"/tasks/{task_id}").json()
    assert task_row["status"] == "completed"
    assert task_row["result"]["resumed_from_approval"] is True


def test_keyword_high_risk_reject_cancels_task(isolated_runtime):
    response = client.post("/tasks", json={"query": "模拟退款", "mode": "keyword"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "waiting_approval"
    approval_id = data["result"]["approval_id"]
    task_id = data["task_id"]

    reject_resp = client.post(
        f"/approvals/{approval_id}/reject",
        json={"decided_by": "admin", "reason": "风险过高，拒绝执行"},
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "rejected"

    task_row = client.get(f"/tasks/{task_id}").json()
    assert task_row["status"] == "cancelled"
    assert task_row["result"]["approval_rejected"] is True


def test_keyword_high_risk_trace_records_approval_requested(isolated_runtime):
    response = client.post("/tasks", json={"query": "模拟退款", "mode": "keyword"})
    task_id = response.json()["task_id"]
    trace = client.get(f"/tasks/{task_id}/trace").json()
    event_types = [e["event_type"] for e in trace["events"]]
    assert "approval_requested" in event_types


def test_direct_tool_call_api_blocked_for_high_risk(isolated_runtime):
    """直接调用工具 API 也无法绕过 PolicyEngine 拦截"""
    resp = client.post("/tools/simulate_refund_order/call", json={"arguments": {}})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "人工审批" in (data["error"] or "")


# ---------- multi_agent 模式：策略拦截且不产生假成功 ----------


def test_multi_agent_high_risk_blocked_no_false_success(isolated_runtime):
    response = client.post("/tasks", json={"query": "为订单ORD-1001模拟退款", "mode": "multi_agent"})
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["success"] is False
    assert result["review_result"]["approved"] is False
    assert result["review_result"].get("suggested_fallback_mode") is None
    assert "审批" in result["final_answer"] or "拦截" in result["final_answer"]
