from __future__ import annotations

import asyncio
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from app.agent.graph.kernel import AgentKernel
from app.agent.nodes.planner import KeywordPlanner
from app.harness.context.assembler import ContextAssembler
from app.harness.gateway.tool_gateway import ToolGateway
from app.harness.hooks.pipeline import HookPipeline
from app.harness.policy.engine import PolicyEngine
from app.harness.trace.recorder import TraceRecorder
from app.main import app, reset_runtime_for_test
from app.models.schemas import RiskLevel, TaskRun, TaskStatus, ToolSpec
from app.services.multitool_pipeline import MultiToolPipeline
from app.storage.approval_store import SQLiteApprovalStore

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


def _register_dangerous_tool(gateway: ToolGateway) -> None:
    gateway.register(
        ToolSpec(tool_name="dangerous_tool", description="危险工具", risk_level=RiskLevel.high, source="local", is_local=True),
        lambda: {"result": "should not reach"},
    )


def _build_kernel_with_danger(gateway, engine, recorder, approval_store, planner=None):
    mt_pipeline = MultiToolPipeline(gateway, policy_engine=engine, trace_recorder=recorder, approval_store=approval_store)
    if planner is None:
        planner = KeywordPlanner()
        planner.ROUTING_RULES.insert(0, {
            "keywords": ["危险测试"],
            "tool_name": "dangerous_tool",
            "label": "危险测试",
        })
    return AgentKernel(
        context_assembler=ContextAssembler(),
        tool_gateway=gateway,
        hook_pipeline=HookPipeline(),
        policy_engine=engine,
        trace_recorder=recorder,
        planner=planner,
        multitool_pipeline=mt_pipeline,
        approval_store=approval_store,
    )


def test_policy_engine_high_risk_requires_approval():
    engine = PolicyEngine()
    decision = engine.evaluate("dangerous_tool", risk_level=RiskLevel.high)
    assert decision["allowed"] is False
    assert decision["requires_approval"] is True
    assert "人工审批" in decision["reason"]


def test_keyword_high_risk_callable_not_called():
    gateway = _build_test_gateway()
    call_count = 0

    def _never_called():
        nonlocal call_count
        call_count += 1
        return {"result": "never"}

    gateway.register(
        ToolSpec(tool_name="dangerous_tool", description="危险工具", risk_level=RiskLevel.high, source="local", is_local=True),
        _never_called,
    )

    engine = PolicyEngine()
    recorder = TraceRecorder()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_approval.sqlite")
        approval_store = SQLiteApprovalStore(db_path=db_path)
        kernel = _build_kernel_with_danger(gateway, engine, recorder, approval_store)

        task = TaskRun(task_id="test-hitl-1", query="危险测试")
        result_task = asyncio.run(kernel.run(task))

        assert call_count == 0
        assert result_task.status == TaskStatus.waiting_approval


def test_keyword_high_risk_returns_approval_id():
    gateway = _build_test_gateway()
    _register_dangerous_tool(gateway)

    engine = PolicyEngine()
    recorder = TraceRecorder()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_approval.sqlite")
        approval_store = SQLiteApprovalStore(db_path=db_path)
        kernel = _build_kernel_with_danger(gateway, engine, recorder, approval_store)

        task = TaskRun(task_id="test-hitl-2", query="危险测试")
        result_task = asyncio.run(kernel.run(task))

        assert result_task.result is not None
        assert result_task.result.get("requires_approval") is True
        assert result_task.result.get("approval_id") is not None
        assert result_task.result.get("approval_id").startswith("apr_")


def test_multitool_high_risk_returns_approval_required():
    gateway = _build_test_gateway()
    _register_dangerous_tool(gateway)

    engine = PolicyEngine()
    recorder = TraceRecorder()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_approval.sqlite")
        approval_store = SQLiteApprovalStore(db_path=db_path)
        mt_pipeline = MultiToolPipeline(gateway, policy_engine=engine, trace_recorder=recorder, approval_store=approval_store)

        from app.agent.nodes.multitool_planner import MultiToolPlan, MultiToolPlanStep
        plan = MultiToolPlan(
            matched=True,
            intent="danger_test",
            steps=[
                MultiToolPlanStep(step_id="s1", tool_name="dangerous_tool", arguments={}, save_as="danger"),
            ],
            response_template="danger test",
            reason="test",
        )

        original_plan = mt_pipeline._planner.plan

        def _mock_plan(query):
            if "危险多工具" in query:
                return plan
            return original_plan(query)

        mt_pipeline._planner.plan = _mock_plan

        result = mt_pipeline.run("危险多工具", task_id="test-mt-hitl-1")
        assert result["success"] is False
        assert result["error_type"] == "approval_required"
        assert result["requires_approval"] is True
        assert result.get("approval_id") is not None


def test_multitool_high_risk_callable_not_called():
    gateway = _build_test_gateway()
    call_count = 0

    def _never_called():
        nonlocal call_count
        call_count += 1
        return {"result": "never"}

    gateway.register(
        ToolSpec(tool_name="dangerous_tool", description="危险工具", risk_level=RiskLevel.high, source="local", is_local=True),
        _never_called,
    )

    engine = PolicyEngine()
    recorder = TraceRecorder()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_approval.sqlite")
        approval_store = SQLiteApprovalStore(db_path=db_path)
        mt_pipeline = MultiToolPipeline(gateway, policy_engine=engine, trace_recorder=recorder, approval_store=approval_store)

        from app.agent.nodes.multitool_planner import MultiToolPlan, MultiToolPlanStep
        plan = MultiToolPlan(
            matched=True,
            intent="danger_test",
            steps=[
                MultiToolPlanStep(step_id="s1", tool_name="dangerous_tool", arguments={}, save_as="danger"),
            ],
            response_template="danger test",
            reason="test",
        )

        original_plan = mt_pipeline._planner.plan

        def _mock_plan(query):
            if "危险多工具" in query:
                return plan
            return original_plan(query)

        mt_pipeline._planner.plan = _mock_plan

        mt_pipeline.run("危险多工具", task_id="test-mt-hitl-2")
        assert call_count == 0


def test_multitool_waiting_approval_via_api():
    reset_runtime_for_test()
    gateway = _build_test_gateway()
    _register_dangerous_tool(gateway)

    engine = PolicyEngine()
    recorder = TraceRecorder()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_approval.sqlite")
        approval_store = SQLiteApprovalStore(db_path=db_path)
        mt_pipeline = MultiToolPipeline(gateway, policy_engine=engine, trace_recorder=recorder, approval_store=approval_store)

        from app.agent.nodes.multitool_planner import MultiToolPlan, MultiToolPlanStep
        plan = MultiToolPlan(
            matched=True,
            intent="danger_test",
            steps=[
                MultiToolPlanStep(step_id="s1", tool_name="dangerous_tool", arguments={}, save_as="danger"),
            ],
            response_template="danger test",
            reason="test",
        )

        original_plan = mt_pipeline._planner.plan

        def _mock_plan(query):
            if "危险多工具" in query:
                return plan
            return original_plan(query)

        mt_pipeline._planner.plan = _mock_plan

        kernel = AgentKernel(
            context_assembler=ContextAssembler(),
            tool_gateway=gateway,
            hook_pipeline=HookPipeline(),
            policy_engine=engine,
            trace_recorder=recorder,
            multitool_pipeline=mt_pipeline,
            approval_store=approval_store,
        )

        task = TaskRun(task_id="test-mt-waiting", query="危险多工具")
        result_task = asyncio.run(kernel.run_with_options(task, mode="multitool"))

        assert result_task.status == TaskStatus.waiting_approval
        assert result_task.result.get("requires_approval") is True

        events = recorder.get_events(task_id="test-mt-waiting")
        event_types = [e.event_type for e in events]
        assert "multitool_waiting_approval" in event_types
        assert "task_completed" not in event_types
    reset_runtime_for_test()


def test_keyword_approval_payload_mode():
    gateway = _build_test_gateway()
    _register_dangerous_tool(gateway)

    engine = PolicyEngine()
    recorder = TraceRecorder()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_approval.sqlite")
        approval_store = SQLiteApprovalStore(db_path=db_path)
        kernel = _build_kernel_with_danger(gateway, engine, recorder, approval_store)

        task = TaskRun(task_id="test-payload-kw", query="危险测试")
        asyncio.run(kernel.run(task))

        approvals = approval_store.list_approvals(status="pending")
        assert len(approvals) >= 1
        apr = approvals[0]
        assert apr["payload"]["mode"] == "keyword"
        assert apr["payload"]["query"] == "危险测试"
        assert apr["payload"]["tool_name"] == "dangerous_tool"


def test_multitool_approval_payload_mode():
    gateway = _build_test_gateway()
    _register_dangerous_tool(gateway)

    engine = PolicyEngine()
    recorder = TraceRecorder()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_approval.sqlite")
        approval_store = SQLiteApprovalStore(db_path=db_path)
        mt_pipeline = MultiToolPipeline(gateway, policy_engine=engine, trace_recorder=recorder, approval_store=approval_store)

        from app.agent.nodes.multitool_planner import MultiToolPlan, MultiToolPlanStep
        plan = MultiToolPlan(
            matched=True,
            intent="danger_test",
            steps=[
                MultiToolPlanStep(step_id="s1", tool_name="dangerous_tool", arguments={}, save_as="danger"),
            ],
            response_template="danger test",
            reason="test",
        )

        original_plan = mt_pipeline._planner.plan

        def _mock_plan(query):
            if "危险多工具" in query:
                return plan
            return original_plan(query)

        mt_pipeline._planner.plan = _mock_plan

        mt_pipeline.run("危险多工具", task_id="test-payload-mt")

        approvals = approval_store.list_approvals(status="pending")
        assert len(approvals) >= 1
        apr = approvals[0]
        assert apr["payload"]["mode"] == "multitool"
        assert apr["payload"]["step_id"] == "s1"
        assert "plan" in apr["payload"]


def test_approvals_api_list_pending():
    reset_runtime_for_test()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_approval.sqlite")
        store = SQLiteApprovalStore(db_path=db_path)
        store.create_approval(
            task_id="test-task-1",
            tool_name="dangerous_tool",
            action="调用工具",
            risk_level=RiskLevel.high,
        )

        import app.main as main_mod
        original = main_mod._approval_store
        main_mod._approval_store = store

        try:
            response = client.get("/approvals", params={"status": "pending"})
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) >= 1
            assert data[0]["status"] == "pending"
        finally:
            main_mod._approval_store = original
    reset_runtime_for_test()


def test_approvals_api_approve():
    reset_runtime_for_test()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_approval.sqlite")
        store = SQLiteApprovalStore(db_path=db_path)
        approval = store.create_approval(
            task_id="test-task-2",
            tool_name="dangerous_tool",
            action="调用工具",
            risk_level=RiskLevel.high,
        )

        import app.main as main_mod
        original = main_mod._approval_store
        main_mod._approval_store = store

        try:
            response = client.post(f"/approvals/{approval.approval_id}/approve", json={"decided_by": "admin", "reason": "允许"})
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "approved"
            assert data["decided_by"] == "admin"
        finally:
            main_mod._approval_store = original
    reset_runtime_for_test()


def test_approvals_api_reject():
    reset_runtime_for_test()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_approval.sqlite")
        store = SQLiteApprovalStore(db_path=db_path)
        approval = store.create_approval(
            task_id="test-task-3",
            tool_name="dangerous_tool",
            action="调用工具",
            risk_level=RiskLevel.high,
        )

        import app.main as main_mod
        original = main_mod._approval_store
        main_mod._approval_store = store

        try:
            response = client.post(f"/approvals/{approval.approval_id}/reject", json={"decided_by": "admin", "reason": "拒绝"})
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "rejected"
            assert data["decided_by"] == "admin"
        finally:
            main_mod._approval_store = original
    reset_runtime_for_test()


def test_approval_idempotent_approved_then_reject():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_approval.sqlite")
        store = SQLiteApprovalStore(db_path=db_path)
        approval = store.create_approval(
            task_id="test-idempotent-1",
            tool_name="dangerous_tool",
            action="调用工具",
            risk_level=RiskLevel.high,
        )

        result_approve = store.decide_approval(approval.approval_id, approved=True, decided_by="admin", reason="允许")
        assert result_approve["status"] == "approved"

        result_reject = store.decide_approval(approval.approval_id, approved=False, decided_by="admin", reason="拒绝")
        assert result_reject["status"] == "approved"
        assert result_reject.get("already_decided") is True


def test_approval_idempotent_rejected_then_approve():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_approval.sqlite")
        store = SQLiteApprovalStore(db_path=db_path)
        approval = store.create_approval(
            task_id="test-idempotent-2",
            tool_name="dangerous_tool",
            action="调用工具",
            risk_level=RiskLevel.high,
        )

        result_reject = store.decide_approval(approval.approval_id, approved=False, decided_by="admin", reason="拒绝")
        assert result_reject["status"] == "rejected"

        result_approve = store.decide_approval(approval.approval_id, approved=True, decided_by="admin", reason="允许")
        assert result_approve["status"] == "rejected"
        assert result_approve.get("already_decided") is True


def test_trace_approval_requested():
    gateway = _build_test_gateway()
    _register_dangerous_tool(gateway)

    engine = PolicyEngine()
    recorder = TraceRecorder()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_approval.sqlite")
        approval_store = SQLiteApprovalStore(db_path=db_path)
        kernel = _build_kernel_with_danger(gateway, engine, recorder, approval_store)

        task = TaskRun(task_id="test-hitl-trace", query="危险测试")
        asyncio.run(kernel.run(task))

        events = recorder.get_events(task_id="test-hitl-trace")
        event_types = [e.event_type for e in events]
        assert "approval_requested" in event_types


def test_low_medium_tools_unchanged():
    engine = PolicyEngine()
    decision_low = engine.evaluate("safe_tool", risk_level=RiskLevel.low)
    assert decision_low["allowed"] is True
    assert decision_low["requires_approval"] is False

    decision_med = engine.evaluate("moderate_tool", risk_level=RiskLevel.medium)
    assert decision_med["allowed"] is True
    assert decision_med["requires_approval"] is False
