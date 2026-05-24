from __future__ import annotations

import asyncio
import os
import sqlite3
import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.agent.graph.kernel import AgentKernel
from app.agent.nodes.planner import KeywordPlanner
from app.harness.context.assembler import ContextAssembler
from app.harness.gateway.tool_gateway import ToolGateway
from app.harness.hooks.pipeline import HookPipeline, HookStage
from app.harness.policy.engine import PolicyEngine
from app.harness.trace.recorder import TraceRecorder
from app.main import app, reset_runtime_for_test
from app.models.schemas import RiskLevel, TaskRun, TaskStatus, ToolCallStatus, ToolSpec

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "db", "ops_demo.sqlite")


def _ensure_db():
    if not os.path.exists(DB_PATH):
        from scripts.init_demo_db import init_db
        init_db()


_ensure_db()

client = TestClient(app)


def _build_test_kernel(
    hook_pipeline: HookPipeline | None = None,
    tool_gateway: ToolGateway | None = None,
) -> tuple[AgentKernel, TraceRecorder]:
    assembler = ContextAssembler()
    gateway = tool_gateway or ToolGateway()
    pipeline = hook_pipeline or HookPipeline()
    engine = PolicyEngine()
    recorder = TraceRecorder()
    planner = KeywordPlanner()

    from app.main import _register_tools
    if tool_gateway is None:
        _register_tools(gateway)

    from app.services.multitool_pipeline import MultiToolPipeline
    multitool_pipeline = MultiToolPipeline(gateway, policy_engine=engine, trace_recorder=recorder)

    from app.agent.multi_agent.executor import ExecutorAgent
    from app.agent.multi_agent.orchestrator import MultiAgentOrchestrator
    executor = ExecutorAgent(
        nl2sql_pipeline=None,
        multitool_pipeline=multitool_pipeline,
        tool_gateway=gateway,
        policy_engine=engine,
        planner=planner,
    )
    orchestrator = MultiAgentOrchestrator(executor, trace_recorder=recorder)

    kernel = AgentKernel(
        context_assembler=assembler,
        tool_gateway=gateway,
        hook_pipeline=pipeline,
        policy_engine=engine,
        trace_recorder=recorder,
        planner=planner,
        multitool_pipeline=multitool_pipeline,
        multi_agent_orchestrator=orchestrator,
    )
    return kernel, recorder


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "project-b-multi-agent"


def test_init_demo_db():
    assert os.path.exists(DB_PATH), f"Demo database not found at {DB_PATH}"
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM products")
    assert cur.fetchone()[0] >= 20
    cur.execute("SELECT COUNT(*) FROM users")
    assert cur.fetchone()[0] >= 50
    cur.execute("SELECT COUNT(*) FROM orders")
    assert cur.fetchone()[0] >= 100
    cur.execute("SELECT COUNT(*) FROM daily_metrics")
    assert cur.fetchone()[0] >= 30
    cur.execute("SELECT COUNT(*) FROM refund_orders")
    assert cur.fetchone()[0] >= 10
    conn.close()


def test_post_task_gmv():
    response = client.post("/tasks", json={"query": "今天GMV多少"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["result"] is not None
    assert data["result"]["success"] is True
    assert data["result"]["tool_called"] == "get_today_gmv"
    assert "gmv" in data["result"]["data"]


def test_post_task_new_users():
    response = client.post("/tasks", json={"query": "本月新增用户多少"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["result"]["success"] is True
    assert data["result"]["tool_called"] == "get_month_new_users"
    assert "new_users" in data["result"]["data"]


def test_post_task_order_count():
    response = client.post("/tasks", json={"query": "今天订单量多少"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["result"]["success"] is True
    assert data["result"]["tool_called"] == "get_order_count"
    assert "order_count" in data["result"]["data"]


def test_post_task_top_products():
    response = client.post("/tasks", json={"query": "Top商品有哪些"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["result"]["success"] is True
    assert data["result"]["tool_called"] == "get_top_products"
    assert "top_products" in data["result"]["data"]


def test_post_task_refund_rate():
    response = client.post("/tasks", json={"query": "退款率是多少"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["result"]["success"] is True
    assert data["result"]["tool_called"] == "get_refund_rate"
    assert "refund_rate_percent" in data["result"]["data"]


def test_post_task_unrecognized():
    response = client.post("/tasks", json={"query": "今天天气怎么样"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("completed", "failed")
    assert data["result"] is not None
    assert data["result"]["success"] is False
    assert data["result"]["tool_called"] is None


def test_post_task_trace():
    response = client.post("/tasks", json={"query": "今天GMV多少"})
    assert response.status_code == 200
    data = response.json()
    task_id = data["task_id"]

    trace_response = client.get(f"/tasks/{task_id}/trace")
    assert trace_response.status_code == 200
    trace_data = trace_response.json()
    assert trace_data["task_id"] == task_id
    assert len(trace_data["events"]) > 0
    event_types = [e["event_type"] for e in trace_data["events"]]
    assert "task_started" in event_types
    assert "context_assembled" in event_types
    assert "plan_created" in event_types
    assert "tool_called" in event_types
    assert "task_completed" in event_types


def test_tool_gateway_unregistered_tool():
    gateway = ToolGateway()
    record = gateway.call("nonexistent_tool")
    assert record.success is False
    assert record.status == ToolCallStatus.failed
    assert record.error is not None
    assert "未注册" in record.error


def test_tool_gateway_error_dict_result():
    gateway = ToolGateway()

    def error_tool():
        return {"error": "数据库连接失败", "data": None}

    gateway.register(
        ToolSpec(tool_name="error_tool", description="总是返回错误的工具", risk_level=RiskLevel.low),
        error_tool,
    )
    record = gateway.call("error_tool")
    assert record.success is False
    assert record.status == ToolCallStatus.failed
    assert record.error == "数据库连接失败"
    assert record.result == {"error": "数据库连接失败", "data": None}


def test_policy_engine_rejects_high_risk():
    engine = PolicyEngine()
    decision = engine.evaluate("dangerous_tool", risk_level=RiskLevel.high)
    assert decision["allowed"] is False
    assert decision["requires_approval"] is True
    assert "人工审批" in decision["reason"]


def test_policy_engine_allows_low_risk():
    engine = PolicyEngine()
    decision = engine.evaluate("safe_tool", risk_level=RiskLevel.low)
    assert decision["allowed"] is True


def test_policy_engine_allows_medium_risk():
    engine = PolicyEngine()
    decision = engine.evaluate("moderate_tool", risk_level=RiskLevel.medium)
    assert decision["allowed"] is True


def test_tool_spec_with_new_fields():
    spec = ToolSpec(
        tool_name="test_tool",
        description="测试工具",
        input_schema={"type": "object", "properties": {"x": {"type": "integer"}}},
        output_schema={"type": "object", "properties": {"result": {"type": "string"}}},
        risk_level=RiskLevel.medium,
        permission_scope="write",
        timeout_seconds=60.0,
        retry_policy={"max_retries": 3, "backoff": "exponential"},
        is_local=True,
    )
    assert spec.tool_name == "test_tool"
    assert spec.risk_level == RiskLevel.medium
    assert spec.timeout_seconds == 60.0
    assert spec.retry_policy["max_retries"] == 3


def test_tool_call_record_with_new_fields():
    from app.models.schemas import ToolCallRecord

    record = ToolCallRecord(
        call_id="test-call-001",
        tool_name="test_tool",
        arguments={"x": 1},
        status=ToolCallStatus.failed,
        success=False,
        latency_ms=123.45,
        retry_count=2,
        error="连接超时",
    )
    assert record.status == ToolCallStatus.failed
    assert record.latency_ms == 123.45
    assert record.retry_count == 2
    assert record.error == "连接超时"


def test_hook_error_observable():
    pipeline = HookPipeline()

    def bad_hook(payload):
        raise RuntimeError("hook 故意报错")

    pipeline.register(HookStage.before_task, bad_hook)
    result = pipeline.run(HookStage.before_task, {"task_id": "test-001"})
    assert "hook_errors" in result
    assert len(result["hook_errors"]) == 1
    assert result["hook_errors"][0]["stage"] == "before_task"
    assert "hook 故意报错" in result["hook_errors"][0]["error"]


def test_hook_error_trace_recorded():
    pipeline = HookPipeline()

    def bad_hook(payload):
        raise RuntimeError("测试 hook 异常")

    pipeline.register(HookStage.before_task, bad_hook)

    kernel, recorder = _build_test_kernel(hook_pipeline=pipeline)

    task = TaskRun(
        task_id=str(uuid.uuid4()),
        query="今天GMV多少",
        status=TaskStatus.created,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    asyncio.run(kernel.run(task))

    events = recorder.get_events(task_id=task.task_id, event_type="hook_failed")
    assert len(events) > 0
    assert "hook_errors" in events[0].detail


def test_reset_runtime_for_test():
    reset_runtime_for_test()
    from app.main import get_trace_recorder
    recorder_before = get_trace_recorder()
    recorder_before.record("test_event", task_id="old-task")

    reset_runtime_for_test()
    recorder_after = get_trace_recorder()
    events = recorder_after.get_events(task_id="old-task")
    assert len(events) == 0

    reset_runtime_for_test()


def test_db_not_found_returns_error():
    gateway = ToolGateway()

    def mock_gmv_no_db():
        from app.tools.local.ops_query import _db_error_result
        return _db_error_result("get_today_gmv", "数据库文件不存在: /tmp/nonexistent.sqlite")

    gateway.register(
        ToolSpec(tool_name="get_today_gmv", description="获取今日 GMV", risk_level=RiskLevel.low),
        mock_gmv_no_db,
    )

    record = gateway.call("get_today_gmv")
    assert record.success is False
    assert record.status == ToolCallStatus.failed
    assert "数据库文件不存在" in record.error


def test_task_with_tool_error_returns_success_false():
    gateway = ToolGateway()

    def error_tool():
        return {"error": "数据库连接失败", "data": None}

    gateway.register(
        ToolSpec(tool_name="get_today_gmv", description="获取今日 GMV", risk_level=RiskLevel.low),
        error_tool,
    )

    kernel, recorder = _build_test_kernel(tool_gateway=gateway)

    task = TaskRun(
        task_id=str(uuid.uuid4()),
        query="今天GMV多少",
        status=TaskStatus.created,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    result_task = asyncio.run(kernel.run(task))
    assert result_task.status == TaskStatus.completed
    assert result_task.result["success"] is False
    assert "数据库连接失败" in result_task.result["answer"]


def test_trace_tool_called_includes_error_on_failure():
    gateway = ToolGateway()

    def error_tool():
        return {"error": "查询超时", "data": None}

    gateway.register(
        ToolSpec(tool_name="get_today_gmv", description="获取今日 GMV", risk_level=RiskLevel.low),
        error_tool,
    )

    kernel, recorder = _build_test_kernel(tool_gateway=gateway)

    task = TaskRun(
        task_id=str(uuid.uuid4()),
        query="今天GMV多少",
        status=TaskStatus.created,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    asyncio.run(kernel.run(task))

    tool_events = recorder.get_events(task_id=task.task_id, event_type="tool_called")
    assert len(tool_events) > 0
    failed_event = tool_events[0]
    assert failed_event.detail["success"] is False
    assert failed_event.detail["error"] is not None
    assert "查询超时" in failed_event.detail["error"]


def test_v025_tasks_nl2sql_gmv():
    response = client.post("/tasks", json={"query": "今天GMV多少", "mode": "nl2sql"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["result"]["mode"] == "nl2sql"
    assert data["result"]["success"] is True
    assert "sql" in data["result"]
    assert "execution" in data["result"]
    assert "formatted_result" in data["result"]
    assert "chart_spec" in data["result"]


def test_v025_tasks_nl2sql_top_products():
    response = client.post("/tasks", json={"query": "Top商品有哪些", "mode": "nl2sql"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["result"]["mode"] == "nl2sql"
    assert data["result"]["success"] is True
    assert data["result"]["execution"]["row_count"] > 1


def test_v025_tasks_nl2sql_unmatched():
    response = client.post("/tasks", json={"query": "今天天气怎么样", "mode": "nl2sql"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["result"]["mode"] == "nl2sql"
    assert data["result"]["success"] is False


def test_v025_tasks_auto_gmv():
    response = client.post("/tasks", json={"query": "今天GMV多少", "mode": "auto"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["result"]["mode"] == "nl2sql"
    assert data["result"]["success"] is True


def test_v025_tasks_auto_unmatched_fallback():
    response = client.post("/tasks", json={"query": "今天天气怎么样", "mode": "auto"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("completed", "failed")
    assert data["result"] is not None
    assert data["result"].get("auto_fallback") is True or data["result"].get("mode") == "auto"


def test_v025_tasks_nl2sql_trace():
    response = client.post("/tasks", json={"query": "今天GMV多少", "mode": "nl2sql"})
    assert response.status_code == 200
    data = response.json()
    task_id = data["task_id"]

    trace_response = client.get(f"/tasks/{task_id}/trace")
    assert trace_response.status_code == 200
    trace_data = trace_response.json()
    event_types = [e["event_type"] for e in trace_data["events"]]
    assert "nl2sql_started" in event_types
    assert "nl2sql_completed" in event_types


def test_v025_tasks_nl2sql_litellm_fallback():
    response = client.post("/tasks", json={
        "query": "今天GMV多少",
        "mode": "nl2sql",
        "generator": "llm",
        "provider": "litellm",
        "fallback_to_mock": True,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["result"]["generator_used"] == "mock_fallback"


def test_v025_tasks_keyword_default_unchanged():
    response = client.post("/tasks", json={"query": "今天GMV多少"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["result"]["success"] is True
    assert data["result"]["tool_called"] == "get_today_gmv"
    assert "gmv" in data["result"]["data"]
