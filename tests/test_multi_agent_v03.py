from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.agent.multi_agent.analyst import AnalystAgent
from app.agent.multi_agent.coordinator import CoordinatorAgent
from app.agent.multi_agent.executor import ExecutorAgent
from app.agent.multi_agent.orchestrator import MultiAgentOrchestrator
from app.agent.multi_agent.reviewer import ReviewerAgent
from app.agent.multi_agent.types import AgentDecision
from app.harness.gateway.tool_gateway import ToolGateway
from app.harness.policy.engine import PolicyEngine
from app.harness.trace.recorder import TraceRecorder
from app.main import app, reset_runtime_for_test
from app.models.schemas import RiskLevel, ToolSpec
from app.services.multitool_pipeline import MultiToolPipeline

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "db", "ops_demo.sqlite")


def _ensure_db():
    if not os.path.exists(DB_PATH):
        from scripts.init_demo_db import init_db
        init_db()


_ensure_db()

client = TestClient(app)


def _build_test_gateway() -> ToolGateway:
    gateway = ToolGateway()
    from app.main import _register_tools, _register_mcp_tools
    _register_tools(gateway)
    _register_mcp_tools(gateway)
    return gateway


def _build_test_orchestrator(gateway: ToolGateway | None = None, recorder: TraceRecorder | None = None) -> MultiAgentOrchestrator:
    gw = gateway or _build_test_gateway()
    rec = recorder or TraceRecorder()
    engine = PolicyEngine()
    mt_pipeline = MultiToolPipeline(gw, policy_engine=engine, trace_recorder=rec)
    executor = ExecutorAgent(
        nl2sql_pipeline=None,
        multitool_pipeline=mt_pipeline,
        tool_gateway=gw,
        policy_engine=engine,
    )
    return MultiAgentOrchestrator(executor, trace_recorder=rec)


def test_coordinator_selects_nl2sql_for_gmv():
    coord = CoordinatorAgent()
    decision = coord.decide("今天GMV多少")
    assert decision.action == "data_query"
    assert decision.metadata["selected_mode"] == "nl2sql"


def test_coordinator_selects_multitool_for_refund_rule():
    coord = CoordinatorAgent()
    decision = coord.decide("退款规则是什么")
    assert decision.action == "compound_tool_query"
    assert decision.metadata["selected_mode"] == "multitool"


def test_analyst_returns_plan_summary():
    coord = CoordinatorAgent()
    analyst = AnalystAgent()
    coord_decision = coord.decide("今天GMV多少")
    analyst_decision = analyst.analyze("今天GMV多少", coord_decision)
    assert analyst_decision.action == "plan_analysis"
    assert "plan_summary" in analyst_decision.metadata
    assert analyst_decision.metadata["needs_schema"] is True


def test_executor_nl2sql_returns_success():
    gateway = _build_test_gateway()
    recorder = TraceRecorder()
    engine = PolicyEngine()
    mt_pipeline = MultiToolPipeline(gateway, policy_engine=engine, trace_recorder=recorder)
    executor = ExecutorAgent(
        nl2sql_pipeline=None,
        multitool_pipeline=mt_pipeline,
        tool_gateway=gateway,
        policy_engine=engine,
    )
    result, decision = executor.execute("今天GMV多少", "nl2sql")
    assert result["success"] is True
    assert decision.role == "executor"


def test_executor_multitool_returns_success():
    gateway = _build_test_gateway()
    recorder = TraceRecorder()
    engine = PolicyEngine()
    mt_pipeline = MultiToolPipeline(gateway, policy_engine=engine, trace_recorder=recorder)
    executor = ExecutorAgent(
        nl2sql_pipeline=None,
        multitool_pipeline=mt_pipeline,
        tool_gateway=gateway,
        policy_engine=engine,
    )
    result, decision = executor.execute("退款规则是什么", "multitool")
    assert result["success"] is True
    assert decision.role == "executor"


def test_reviewer_approves_success():
    reviewer = ReviewerAgent()
    exec_result = {"success": True, "answer": "GMV 为 12345"}
    review_result, decision = reviewer.review(exec_result, "nl2sql")
    assert review_result["approved"] is True
    assert decision.action == "approve"


def test_reviewer_suggests_fallback_on_failure():
    reviewer = ReviewerAgent()
    exec_result = {"success": False, "answer": ""}
    review_result, decision = reviewer.review(exec_result, "nl2sql")
    assert review_result["approved"] is False
    assert review_result["suggested_fallback_mode"] is not None
    assert decision.action in ("suggest_fallback", "reject")


def test_tasks_multi_agent_gmv():
    reset_runtime_for_test()
    response = client.post("/tasks", json={"query": "今天GMV多少", "mode": "multi_agent"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    result = data["result"]
    assert result["mode"] == "multi_agent"
    assert result["success"] is True
    reset_runtime_for_test()


def test_tasks_multi_agent_refund_rule_executed_mode():
    reset_runtime_for_test()
    response = client.post("/tasks", json={"query": "退款规则是什么", "mode": "multi_agent"})
    assert response.status_code == 200
    data = response.json()
    result = data["result"]
    assert result["success"] is True
    assert result["executed_mode"] == "multitool"
    reset_runtime_for_test()


def test_tasks_multi_agent_trace_events():
    reset_runtime_for_test()
    response = client.post("/tasks", json={"query": "今天GMV多少", "mode": "multi_agent"})
    assert response.status_code == 200
    data = response.json()
    task_id = data["task_id"]

    trace_response = client.get(f"/tasks/{task_id}/trace")
    assert trace_response.status_code == 200
    trace_data = trace_response.json()
    event_types = [e["event_type"] for e in trace_data["events"]]
    assert "coordinator_decided" in event_types
    assert "executor_completed" in event_types
    assert "reviewer_completed" in event_types
    reset_runtime_for_test()


def test_tasks_default_keyword_unchanged():
    reset_runtime_for_test()
    response = client.post("/tasks", json={"query": "GMV"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["result"]["success"] is True
    assert data["result"].get("mode") != "multi_agent"
    reset_runtime_for_test()
