from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.agent.nodes.multitool_planner import MultiToolPlanner, MultiToolPlanStep, MultiToolPlan
from app.harness.gateway.tool_gateway import ToolGateway
from app.harness.policy.engine import PolicyEngine
from app.harness.trace.recorder import TraceRecorder
from app.main import app, reset_runtime_for_test
from app.models.schemas import RiskLevel, ToolSpec
from app.services.multitool_pipeline import MultiToolPipeline, VariableResolutionError
from app.tools.mcp.client import FakeMCPClient

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


def _build_test_pipeline(gateway: ToolGateway | None = None, policy_engine: PolicyEngine | None = None, trace_recorder: TraceRecorder | None = None) -> MultiToolPipeline:
    gw = gateway or _build_test_gateway()
    pe = policy_engine or PolicyEngine()
    tr = trace_recorder or TraceRecorder()
    return MultiToolPipeline(gw, policy_engine=pe, trace_recorder=tr)


def test_multitool_planner_matches_gmv_mom():
    planner = MultiToolPlanner()
    plan = planner.plan("GMV环比增长多少")
    assert plan.matched is True
    assert plan.intent == "gmv_mom"
    assert len(plan.steps) == 3
    step_ids = [s.step_id for s in plan.steps]
    assert "step_date" in step_ids
    assert "step_gmv" in step_ids
    assert "step_calc" in step_ids
    assert "mock" in plan.reason.lower() or "mock" in plan.reason


def test_multitool_planner_matches_refund_rule():
    planner = MultiToolPlanner()
    plan = planner.plan("退款规则是什么")
    assert plan.matched is True
    assert plan.intent == "refund_rule"
    assert len(plan.steps) == 2
    tool_names = [s.tool_name for s in plan.steps]
    assert "rule_lookup" in tool_names
    assert "get_refund_rate" in tool_names


def test_multitool_planner_unmatched():
    planner = MultiToolPlanner()
    plan = planner.plan("今天天气怎么样")
    assert plan.matched is False
    assert plan.intent == ""


def test_multitool_pipeline_refund_rule_success():
    pipeline = _build_test_pipeline()
    result = pipeline.run("退款规则是什么")
    assert result["mode"] == "multitool"
    assert result["success"] is True
    assert result["intent"] == "refund_rule"
    assert len(result["tool_calls"]) == 2
    assert result["tool_calls"][0]["tool_name"] == "rule_lookup"
    assert result["tool_calls"][0]["success"] is True
    assert result["tool_calls"][1]["tool_name"] == "get_refund_rate"
    assert result["tool_calls"][1]["success"] is True
    assert "退款规则" in result["answer"]
    assert "退款率" in result["answer"]


def test_multitool_pipeline_promotion_rule_success():
    pipeline = _build_test_pipeline()
    result = pipeline.run("促销规则")
    assert result["mode"] == "multitool"
    assert result["success"] is True
    assert result["intent"] == "promotion_rule"
    assert len(result["tool_calls"]) == 1
    assert result["tool_calls"][0]["tool_name"] == "rule_lookup"
    assert result["tool_calls"][0]["success"] is True
    assert "促销规则" in result["answer"]


def test_multitool_pipeline_step_failure_stops():
    gateway = ToolGateway()
    gateway.register(
        ToolSpec(tool_name="rule_lookup", description="规则查询", risk_level=RiskLevel.low, source="mcp", server_name="fake_ops_mcp", mcp_tool_name="rule_lookup", is_local=False),
        None,
    )
    result = _build_test_pipeline(gateway=gateway).run("退款规则是什么")
    assert result["success"] is False
    assert "failed_step" in result


def test_tasks_multitool_refund_rule():
    reset_runtime_for_test()
    response = client.post("/tasks", json={"query": "退款规则是什么", "mode": "multitool"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["result"]["mode"] == "multitool"
    assert data["result"]["success"] is True
    assert "退款规则" in data["result"]["answer"]
    reset_runtime_for_test()


def test_tasks_multitool_unmatched_no_500():
    reset_runtime_for_test()
    response = client.post("/tasks", json={"query": "今天天气怎么样", "mode": "multitool"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["result"]["success"] is False
    reset_runtime_for_test()


def test_tasks_auto_fallback_to_multitool():
    reset_runtime_for_test()
    response = client.post("/tasks", json={"query": "促销规则是什么", "mode": "auto"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["result"]["success"] is True
    assert data["result"].get("auto_fallback") is True or data["result"].get("mode") == "auto"
    reset_runtime_for_test()


def test_multitool_trace_events():
    reset_runtime_for_test()
    response = client.post("/tasks", json={"query": "退款规则是什么", "mode": "multitool"})
    assert response.status_code == 200
    data = response.json()
    task_id = data["task_id"]

    trace_response = client.get(f"/tasks/{task_id}/trace")
    assert trace_response.status_code == 200
    trace_data = trace_response.json()
    event_types = [e["event_type"] for e in trace_data["events"]]
    assert "multitool_started" in event_types
    assert "multitool_completed" in event_types
    reset_runtime_for_test()


def test_tools_high_risk_policy_blocked():
    reset_runtime_for_test()
    gateway = _build_test_gateway()
    gateway.register(
        ToolSpec(
            tool_name="dangerous_tool",
            description="危险工具",
            risk_level=RiskLevel.high,
            permission_scope="write",
            source="local",
            is_local=True,
        ),
        lambda: {"result": "should not reach"},
    )
    from app.main import get_policy_engine
    engine = get_policy_engine()
    decision = engine.evaluate("dangerous_tool", risk_level=RiskLevel.high)
    assert decision["allowed"] is False
    reset_runtime_for_test()


# ===== v0.3.3 新增测试 =====


def test_high_risk_tool_blocked_in_multitool():
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

    planner_override = MultiToolPlanner()
    original_plan = planner_override.plan

    def _patched_plan(query: str) -> MultiToolPlan:
        if "危险测试" in query:
            return MultiToolPlan(
                matched=True,
                intent="test_danger",
                steps=[
                    MultiToolPlanStep(step_id="s1", tool_name="dangerous_tool", arguments={}, save_as="danger"),
                ],
                response_template="危险测试",
                reason="测试 high risk 阻断",
            )
        return original_plan(query)

    pipeline = _build_test_pipeline(gateway=gateway)
    pipeline._planner.plan = _patched_plan

    result = pipeline.run("危险测试")
    assert result["success"] is False
    assert result["tool_calls"][0].get("policy_blocked") is True
    assert call_count == 0


def test_depends_on_unmet_fails():
    gateway = _build_test_gateway()
    pipeline = _build_test_pipeline(gateway=gateway)

    def _patched_plan(query: str) -> MultiToolPlan:
        if "依赖测试" in query:
            return MultiToolPlan(
                matched=True,
                intent="test_depends",
                steps=[
                    MultiToolPlanStep(step_id="s2", tool_name="date_lookup", arguments={}, depends_on=["s1"], save_as="date_info"),
                ],
                response_template="依赖测试",
                reason="测试 depends_on",
            )
        return pipeline._planner.plan(query)

    pipeline._planner.plan = _patched_plan
    result = pipeline.run("依赖测试")
    assert result["success"] is False
    assert result["failed_step"] == "s2"
    assert result["error_type"] == "dependency_not_satisfied"
    assert result["missing_depends_on"] == ["s1"]
    assert "依赖未满足" in result["answer"]


def test_depends_on_predecessor_failed_stops_successor():
    gateway = ToolGateway()
    call_count = 0

    def _failing_fn():
        nonlocal call_count
        call_count += 1
        raise RuntimeError("intentional failure")

    gateway.register(
        ToolSpec(tool_name="failing_tool", description="失败工具", risk_level=RiskLevel.low, source="local", is_local=True),
        _failing_fn,
    )
    gateway.register(
        ToolSpec(tool_name="date_lookup", description="日期", risk_level=RiskLevel.low, source="local", is_local=True),
        lambda: {"date": "2026-05-23"},
    )

    pipeline = _build_test_pipeline(gateway=gateway)

    def _patched_plan(query: str) -> MultiToolPlan:
        if "前置失败" in query:
            return MultiToolPlan(
                matched=True,
                intent="test_predecessor_fail",
                steps=[
                    MultiToolPlanStep(step_id="s1", tool_name="failing_tool", arguments={}, save_as="step1"),
                    MultiToolPlanStep(step_id="s2", tool_name="date_lookup", arguments={}, depends_on=["s1"], save_as="step2"),
                ],
                response_template="前置失败测试",
                reason="测试前置失败",
            )
        return pipeline._planner.plan(query)

    pipeline._planner.plan = _patched_plan
    result = pipeline.run("前置失败")
    assert result["success"] is False
    assert result["failed_step"] == "s1"
    assert call_count == 1


def test_nested_dict_list_variable_resolution():
    gateway = _build_test_gateway()
    pipeline = _build_test_pipeline(gateway=gateway)

    def _patched_plan(query: str) -> MultiToolPlan:
        if "嵌套测试" in query:
            return MultiToolPlan(
                matched=True,
                intent="test_nested",
                steps=[
                    MultiToolPlanStep(step_id="s1", tool_name="date_lookup", arguments={}, save_as="date_info"),
                    MultiToolPlanStep(
                        step_id="s2",
                        tool_name="calculator",
                        arguments={
                            "operation": "add",
                            "a": "$date_info.result.year",
                            "b": 1,
                            "nested": {"val": "$date_info.result.year"},
                            "list_val": ["$date_info.result.year", 100],
                        },
                        depends_on=["s1"],
                        save_as="calc_result",
                    ),
                ],
                response_template="嵌套测试",
                reason="测试嵌套变量",
            )
        return pipeline._planner.plan(query)

    pipeline._planner.plan = _patched_plan
    result = pipeline.run("嵌套测试")
    assert result["success"] is True
    assert len(result["tool_calls"]) == 2
    calc_args = result["tool_calls"][1]["arguments"]
    assert calc_args["a"] == 2026
    assert calc_args["nested"]["val"] == 2026
    assert calc_args["list_val"][0] == 2026
    assert calc_args["list_val"][1] == 100


def test_variable_missing_returns_path():
    gateway = _build_test_gateway()
    pipeline = _build_test_pipeline(gateway=gateway)

    def _patched_plan(query: str) -> MultiToolPlan:
        if "缺失变量" in query:
            return MultiToolPlan(
                matched=True,
                intent="test_missing_var",
                steps=[
                    MultiToolPlanStep(
                        step_id="s1",
                        tool_name="calculator",
                        arguments={"operation": "add", "a": "$nonexistent.result.gmv", "b": 1},
                        save_as="calc",
                    ),
                ],
                response_template="缺失变量",
                reason="测试缺失变量",
            )
        return pipeline._planner.plan(query)

    pipeline._planner.plan = _patched_plan
    result = pipeline.run("缺失变量")
    assert result["success"] is False
    assert result["failed_step"] == "s1"
    assert result["error_type"] == "variable_resolution_failed"
    assert result["error_path"] == "nonexistent.result.gmv"
    assert "nonexistent.result.gmv" in result["answer"]


def test_retry_policy_max_retries_2():
    gateway = ToolGateway()
    call_count = 0

    def _always_fail():
        nonlocal call_count
        call_count += 1
        raise RuntimeError("always fails")

    gateway.register(
        ToolSpec(
            tool_name="flaky_tool",
            description="不稳定工具",
            risk_level=RiskLevel.low,
            source="local",
            is_local=True,
            retry_policy={"max_retries": 2},
        ),
        _always_fail,
    )

    record = gateway.call("flaky_tool")
    assert record.success is False
    assert record.retry_count == 2
    assert call_count == 3


def test_retry_policy_success_after_retry():
    gateway = ToolGateway()
    call_count = 0

    def _succeed_on_second():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise RuntimeError("first attempt fails")
        return {"result": "ok"}

    gateway.register(
        ToolSpec(
            tool_name="recoverable_tool",
            description="可恢复工具",
            risk_level=RiskLevel.low,
            source="local",
            is_local=True,
            retry_policy={"max_retries": 2},
        ),
        _succeed_on_second,
    )

    record = gateway.call("recoverable_tool")
    assert record.success is True
    assert record.retry_count == 1
    assert call_count == 2


def test_retry_policy_still_fails_after_max():
    gateway = ToolGateway()
    call_count = 0

    def _always_error_dict():
        nonlocal call_count
        call_count += 1
        return {"error": "persistent error"}

    gateway.register(
        ToolSpec(
            tool_name="error_dict_tool",
            description="返回 error dict",
            risk_level=RiskLevel.low,
            source="local",
            is_local=True,
            retry_policy={"max_retries": 2},
        ),
        _always_error_dict,
    )

    record = gateway.call("error_dict_tool")
    assert record.success is False
    assert record.retry_count == 2
    assert call_count == 3


def test_tasks_auto_executed_mode_and_fallback_chain():
    reset_runtime_for_test()
    response = client.post("/tasks", json={"query": "促销规则是什么", "mode": "auto"})
    assert response.status_code == 200
    data = response.json()
    result = data["result"]
    assert result["requested_mode"] == "auto"
    assert result["executed_mode"] == "multitool"
    assert "fallback_chain" in result
    assert "nl2sql" in result["fallback_chain"]
    assert "multitool" in result["fallback_chain"]
    reset_runtime_for_test()


def test_trace_contains_step_events():
    recorder = TraceRecorder()
    gateway = _build_test_gateway()
    pipeline = _build_test_pipeline(gateway=gateway, trace_recorder=recorder)
    result = pipeline.run("退款规则是什么", task_id="test-trace-step")
    assert result["success"] is True

    events = recorder.get_events(task_id="test-trace-step")
    event_types = [e.event_type for e in events]
    assert "multitool_step_started" in event_types
    assert "multitool_step_completed" in event_types


# ===== v0.3.4 Review Cleanup 测试 =====


def test_variable_resolution_failed_trace_includes_error_path():
    recorder = TraceRecorder()
    gateway = _build_test_gateway()
    pipeline = _build_test_pipeline(gateway=gateway, trace_recorder=recorder)

    def _patched_plan(query: str) -> MultiToolPlan:
        if "缺失变量trace" in query:
            return MultiToolPlan(
                matched=True,
                intent="test_missing_var_trace",
                steps=[
                    MultiToolPlanStep(
                        step_id="s1",
                        tool_name="calculator",
                        arguments={"operation": "add", "a": "$nonexistent.result.gmv", "b": 1},
                        save_as="calc",
                    ),
                ],
                response_template="缺失变量trace",
                reason="测试缺失变量trace",
            )
        return pipeline._planner.plan(query)

    pipeline._planner.plan = _patched_plan
    result = pipeline.run("缺失变量trace", task_id="test-var-trace")
    assert result["success"] is False

    events = recorder.get_events(task_id="test-var-trace", event_type="multitool_step_failed")
    assert len(events) == 1
    detail = events[0].detail
    assert detail["error_type"] == "variable_resolution_failed"
    assert detail["error_path"] == "nonexistent.result.gmv"
