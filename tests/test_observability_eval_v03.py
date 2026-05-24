from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.agent.multi_agent.orchestrator import MultiAgentOrchestrator
from app.harness.eval.multi_agent_runner import MultiAgentEvalRunner
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


def test_observability_tasks_summary():
    reset_runtime_for_test()
    response = client.get("/observability/tasks/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_tasks" in data
    assert "success_count" in data
    assert "failed_count" in data
    assert "mode_counts" in data
    assert "recent_tasks" in data
    reset_runtime_for_test()


def test_observability_summary_after_task_creation():
    reset_runtime_for_test()
    client.post("/tasks", json={"query": "今天GMV多少", "mode": "keyword"})

    response = client.get("/observability/tasks/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["total_tasks"] >= 1
    queries = [t.get("query", "") for t in data["recent_tasks"]]
    assert any("GMV" in q for q in queries)
    reset_runtime_for_test()


def test_observability_task_timeline():
    reset_runtime_for_test()
    create_resp = client.post("/tasks", json={"query": "今天几号", "mode": "keyword"})
    task_id = create_resp.json()["task_id"]

    timeline_resp = client.get(f"/observability/tasks/{task_id}/timeline")
    assert timeline_resp.status_code == 200
    data = timeline_resp.json()
    assert data["task_id"] == task_id
    assert "events" in data
    assert isinstance(data["events"], list)
    for evt in data["events"]:
        assert "event_type" in evt
        assert "timestamp" in evt
        assert "actor" in evt
        assert "detail" in evt
    reset_runtime_for_test()


def test_observability_events_filter_by_type():
    reset_runtime_for_test()
    client.post("/tasks", json={"query": "今天GMV多少", "mode": "keyword"})

    response = client.get("/observability/events", params={"event_type": "task_started"})
    assert response.status_code == 200
    data = response.json()
    assert "events" in data
    assert "count" in data
    for evt in data["events"]:
        assert evt["event_type"] == "task_started"
    reset_runtime_for_test()


def test_observability_events_limit_cap():
    recorder = TraceRecorder()
    for i in range(10):
        recorder.record("test_event", task_id="limit-test", detail={"idx": i})

    from app.main import _trace_recorder
    import app.main as main_mod
    original = main_mod._trace_recorder
    main_mod._trace_recorder = recorder

    try:
        resp = client.get("/observability/events", params={"limit": 5})
        assert resp.status_code == 200
        assert resp.json()["count"] == 5

        resp_zero = client.get("/observability/events", params={"limit": 0})
        assert resp_zero.status_code == 200
        assert resp_zero.json()["count"] == 10

        resp_large = client.get("/observability/events", params={"limit": 1000})
        assert resp_large.status_code == 200
        assert resp_large.json()["count"] == 10
    finally:
        main_mod._trace_recorder = original


def test_multi_agent_eval_12_cases_accuracy():
    gateway = _build_test_gateway()
    recorder = TraceRecorder()
    engine = PolicyEngine()
    mt_pipeline = MultiToolPipeline(gateway, policy_engine=engine, trace_recorder=recorder)

    from app.agent.multi_agent.executor import ExecutorAgent
    executor = ExecutorAgent(
        nl2sql_pipeline=None,
        multitool_pipeline=mt_pipeline,
        tool_gateway=gateway,
        policy_engine=engine,
    )
    orchestrator = MultiAgentOrchestrator(executor, trace_recorder=recorder)

    runner = MultiAgentEvalRunner(orchestrator, trace_recorder=recorder)
    result = runner.run()
    assert result.total >= 12
    assert result.accuracy >= 0.75


def test_eval_failures_contain_trace_task_id():
    gateway = _build_test_gateway()
    recorder = TraceRecorder()
    engine = PolicyEngine()
    mt_pipeline = MultiToolPipeline(gateway, policy_engine=engine, trace_recorder=recorder)

    from app.agent.multi_agent.executor import ExecutorAgent
    executor = ExecutorAgent(
        nl2sql_pipeline=None,
        multitool_pipeline=mt_pipeline,
        tool_gateway=gateway,
        policy_engine=engine,
    )
    orchestrator = MultiAgentOrchestrator(executor, trace_recorder=recorder)

    runner = MultiAgentEvalRunner(orchestrator, trace_recorder=recorder)
    result = runner.run()
    for f in result.failures:
        assert f.trace_task_id is not None
        assert f.trace_task_id.startswith("eval_")


def test_eval_summary_api():
    reset_runtime_for_test()
    response = client.get("/eval/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["multi_agent_eval_available"] is True
    assert "nl2sql_eval_available" in data
    assert "case_counts" in data
    reset_runtime_for_test()


def test_eval_run_all_api():
    reset_runtime_for_test()
    response = client.post("/eval/run-all")
    assert response.status_code == 200
    data = response.json()
    assert "suites" in data
    assert isinstance(data["suites"], list)
    assert len(data["suites"]) >= 1
    assert "overall_accuracy" in data
    assert "total_cases" in data
    assert "total_passed" in data
    suite_names = [s["suite"] for s in data["suites"]]
    assert "multi_agent" in suite_names
    reset_runtime_for_test()


def test_bad_case_export():
    gateway = _build_test_gateway()
    recorder = TraceRecorder()
    engine = PolicyEngine()
    mt_pipeline = MultiToolPipeline(gateway, policy_engine=engine, trace_recorder=recorder)

    from app.agent.multi_agent.executor import ExecutorAgent
    executor = ExecutorAgent(
        nl2sql_pipeline=None,
        multitool_pipeline=mt_pipeline,
        tool_gateway=gateway,
        policy_engine=engine,
    )
    orchestrator = MultiAgentOrchestrator(executor, trace_recorder=recorder)

    runner = MultiAgentEvalRunner(orchestrator)
    result = runner.run()
    bad_cases = runner.export_bad_cases()
    assert isinstance(bad_cases, list)
    if len(bad_cases) > 0:
        bc = bad_cases[0]
        assert bc.suite == "multi_agent"
        assert bc.case_id is not None
        assert bc.trace_task_id is not None


def test_trace_eval_association():
    gateway = _build_test_gateway()
    recorder = TraceRecorder()
    engine = PolicyEngine()
    mt_pipeline = MultiToolPipeline(gateway, policy_engine=engine, trace_recorder=recorder)

    from app.agent.multi_agent.executor import ExecutorAgent
    executor = ExecutorAgent(
        nl2sql_pipeline=None,
        multitool_pipeline=mt_pipeline,
        tool_gateway=gateway,
        policy_engine=engine,
    )
    orchestrator = MultiAgentOrchestrator(executor, trace_recorder=recorder)

    runner = MultiAgentEvalRunner(orchestrator)
    result = runner.run()

    if result.failures:
        f = result.failures[0]
        tid = f.trace_task_id
        assert tid is not None
        events = recorder.get_events(task_id=tid)
        assert len(events) > 0
