from __future__ import annotations

import os
import tempfile
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.agent.multi_agent.executor import ExecutorAgent
from app.agent.multi_agent.orchestrator import MultiAgentOrchestrator
from app.agent.multi_agent.types import AgentDecision
from app.harness.eval.multi_agent_runner import MultiAgentEvalRunner
from app.harness.gateway.tool_gateway import ToolGateway
from app.harness.policy.engine import PolicyEngine
from app.harness.trace.recorder import TraceRecorder
from app.main import app, reset_runtime_for_test
from app.models.schemas import RiskLevel, ToolSpec
from app.services.multitool_pipeline import MultiToolPipeline
from app.storage.task_store import SQLiteTaskStore

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


def test_executor_keyword_high_risk_blocked():
    gateway = _build_test_gateway()
    call_count = 0

    def _dangerous_fn():
        nonlocal call_count
        call_count += 1
        return {"result": "should not reach"}

    gateway.register(
        ToolSpec(tool_name="dangerous_tool", description="危险工具", risk_level=RiskLevel.high, source="local", is_local=True),
        _dangerous_fn,
    )

    engine = PolicyEngine()
    recorder = TraceRecorder()
    mt_pipeline = MultiToolPipeline(gateway, policy_engine=engine, trace_recorder=recorder)

    from app.agent.nodes.planner import KeywordPlanner
    planner = KeywordPlanner()

    planner.ROUTING_RULES.insert(0, {
        "keywords": ["危险测试"],
        "tool_name": "dangerous_tool",
        "label": "危险测试",
    })

    executor = ExecutorAgent(
        multitool_pipeline=mt_pipeline,
        tool_gateway=gateway,
        policy_engine=engine,
        planner=planner,
    )

    result, decision = executor.execute("危险测试", "keyword")
    assert result["success"] is False
    assert result.get("error_type") == "policy_blocked"
    assert result.get("blocked") is True
    assert decision.metadata["policy_blocked"] is True
    assert call_count == 0


def test_executor_keyword_blocked_callable_not_called():
    gateway = ToolGateway()
    call_count = 0

    def _never_called():
        nonlocal call_count
        call_count += 1
        return {"result": "never"}

    gateway.register(
        ToolSpec(tool_name="blocked_tool", description="被阻止的工具", risk_level=RiskLevel.high, source="local", is_local=True),
        _never_called,
    )

    engine = PolicyEngine()
    recorder = TraceRecorder()
    mt_pipeline = MultiToolPipeline(gateway, policy_engine=engine, trace_recorder=recorder)

    from app.agent.nodes.planner import KeywordPlanner
    planner = KeywordPlanner()
    planner.ROUTING_RULES.insert(0, {
        "keywords": ["阻止测试"],
        "tool_name": "blocked_tool",
        "label": "阻止测试",
    })

    executor = ExecutorAgent(
        multitool_pipeline=mt_pipeline,
        tool_gateway=gateway,
        policy_engine=engine,
        planner=planner,
    )

    result, _ = executor.execute("阻止测试", "keyword")
    assert result["success"] is False
    assert call_count == 0


def test_fallback_trace_events():
    recorder = TraceRecorder()
    gateway = _build_test_gateway()
    engine = PolicyEngine()
    mt_pipeline = MultiToolPipeline(gateway, policy_engine=engine, trace_recorder=recorder)

    executor = ExecutorAgent(
        nl2sql_pipeline=None,
        multitool_pipeline=mt_pipeline,
        tool_gateway=gateway,
        policy_engine=engine,
    )
    orchestrator = MultiAgentOrchestrator(executor, trace_recorder=recorder)

    from app.agent.multi_agent.coordinator import CoordinatorAgent
    original_decide = CoordinatorAgent.decide

    def _force_nl2sql(self, query):
        return AgentDecision(
            role="coordinator",
            action="data_query",
            reason="强制 nl2sql 测试 fallback",
            confidence=0.9,
            metadata={"selected_mode": "nl2sql"},
        )

    CoordinatorAgent.decide = _force_nl2sql

    from app.agent.multi_agent.reviewer import ReviewerAgent
    original_review = ReviewerAgent.review
    call_count = [0]

    def _reject_first_approve_second(self, execution_result, selected_mode):
        call_count[0] += 1
        if call_count[0] == 1:
            return (
                {"approved": False, "reason": "强制拒绝触发 fallback", "suggested_fallback_mode": "multitool"},
                AgentDecision(role="reviewer", action="suggest_fallback", reason="强制拒绝触发 fallback", confidence=0.7, metadata={"approved": False, "suggested_fallback_mode": "multitool"}),
            )
        return original_review(self, execution_result, selected_mode)

    ReviewerAgent.review = _reject_first_approve_second

    try:
        result = orchestrator.run("GMV查询", task_id="test-fallback-trace")
    finally:
        CoordinatorAgent.decide = original_decide
        ReviewerAgent.review = original_review

    events = recorder.get_events(task_id="test-fallback-trace")
    event_types = [e.event_type for e in events]
    assert "multi_agent_fallback_started" in event_types
    assert "multi_agent_fallback_completed" in event_types


def test_fallback_chain_preserves_modes():
    recorder = TraceRecorder()
    gateway = _build_test_gateway()
    engine = PolicyEngine()
    mt_pipeline = MultiToolPipeline(gateway, policy_engine=engine, trace_recorder=recorder)

    executor = ExecutorAgent(
        nl2sql_pipeline=None,
        multitool_pipeline=mt_pipeline,
        tool_gateway=gateway,
        policy_engine=engine,
    )
    orchestrator = MultiAgentOrchestrator(executor, trace_recorder=recorder)

    result = orchestrator.run("退款规则是什么")
    assert len(result.fallback_chain) >= 1
    assert result.fallback_chain[0] in ("nl2sql", "multitool", "keyword", "auto")


def test_tasks_persistence_get_by_id():
    reset_runtime_for_test()
    response = client.post("/tasks", json={"query": "GMV"})
    assert response.status_code == 200
    task_id = response.json()["task_id"]

    get_response = client.get(f"/tasks/{task_id}")
    assert get_response.status_code == 200
    data = get_response.json()
    assert data["task_id"] == task_id
    assert data["query"] == "GMV"
    reset_runtime_for_test()


def test_tasks_persistence_list():
    reset_runtime_for_test()
    client.post("/tasks", json={"query": "GMV"})
    client.post("/tasks", json={"query": "订单"})

    list_response = client.get("/tasks/list")
    assert list_response.status_code == 200
    tasks = list_response.json()
    assert len(tasks) >= 2
    reset_runtime_for_test()


def test_tasks_trace_no_regression():
    reset_runtime_for_test()
    response = client.post("/tasks", json={"query": "GMV"})
    task_id = response.json()["task_id"]

    trace_response = client.get(f"/tasks/{task_id}/trace")
    assert trace_response.status_code == 200
    trace_data = trace_response.json()
    assert "events" in trace_data
    reset_runtime_for_test()


def test_multi_agent_eval_runner():
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
    orchestrator = MultiAgentOrchestrator(executor, trace_recorder=recorder)

    runner = MultiAgentEvalRunner(orchestrator)
    result = runner.run()
    assert result.total >= 6
    assert result.passed >= 4
    assert result.accuracy >= 0.7


def test_eval_api():
    reset_runtime_for_test()
    response = client.post("/tasks/eval/multi-agent")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 6
    assert data["accuracy"] >= 0.7
    reset_runtime_for_test()


# ===== v0.3.6.1 Cleanup 测试 =====


def test_get_tasks_returns_list():
    reset_runtime_for_test()
    client.post("/tasks", json={"query": "GMV"})
    client.post("/tasks", json={"query": "订单"})

    response = client.get("/tasks")
    assert response.status_code == 200
    tasks = response.json()
    assert isinstance(tasks, list)
    assert len(tasks) >= 2
    reset_runtime_for_test()


def test_get_tasks_list_compat():
    reset_runtime_for_test()
    client.post("/tasks", json={"query": "GMV"})

    response = client.get("/tasks/list")
    assert response.status_code == 200
    tasks = response.json()
    assert isinstance(tasks, list)
    assert len(tasks) >= 1
    reset_runtime_for_test()


def test_get_tasks_trace_not_blocked_by_get_tasks():
    reset_runtime_for_test()
    resp = client.post("/tasks", json={"query": "GMV"})
    task_id = resp.json()["task_id"]

    trace_resp = client.get(f"/tasks/{task_id}/trace")
    assert trace_resp.status_code == 200
    assert "events" in trace_resp.json()
    reset_runtime_for_test()


def test_sqlite_task_store_empty_dirname():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "runtime_test.sqlite")
        store = SQLiteTaskStore(db_path=db_path)
        result = store.list_tasks()
        assert isinstance(result, list)

    store2 = SQLiteTaskStore(db_path="runtime_test_cwd.sqlite")
    result2 = store2.list_tasks()
    assert isinstance(result2, list)
    if os.path.exists("runtime_test_cwd.sqlite"):
        os.remove("runtime_test_cwd.sqlite")


def test_list_tasks_limit_zero_uses_default():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_limit.sqlite")
        store = SQLiteTaskStore(db_path=db_path)
        result = store.list_tasks(limit=0)
        assert isinstance(result, list)


def test_list_tasks_limit_large_capped_at_100():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_cap.sqlite")
        store = SQLiteTaskStore(db_path=db_path)
        result = store.list_tasks(limit=999)
        assert isinstance(result, list)
        assert len(result) <= 100


def test_persistence_error_observable():
    reset_runtime_for_test()
    with patch("app.api.tasks._get_task_store", side_effect=RuntimeError("DB 连接失败")):
        response = client.post("/tasks", json={"query": "GMV"})
        assert response.status_code == 200
        data = response.json()
        assert data.get("persistence_error") is not None
        assert "DB 连接失败" in data["persistence_error"]
    reset_runtime_for_test()


def test_persistence_failed_trace():
    reset_runtime_for_test()
    with patch("app.api.tasks._get_task_store", side_effect=RuntimeError("DB 连接失败")):
        response = client.post("/tasks", json={"query": "GMV"})
        task_id = response.json()["task_id"]

    recorder = TraceRecorder()
    from app.main import get_trace_recorder
    rec = get_trace_recorder()
    events = rec.get_events(task_id=task_id)
    event_types = [e.event_type for e in events]
    assert "task_persist_failed" in event_types
    reset_runtime_for_test()


def test_eval_api_no_private_field_access():
    reset_runtime_for_test()
    from app.main import get_multi_agent_orchestrator
    orchestrator = get_multi_agent_orchestrator()
    assert orchestrator is not None
    assert isinstance(orchestrator, MultiAgentOrchestrator)
    reset_runtime_for_test()
