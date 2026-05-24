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
from app.services.approval_resume import ApprovalResumeService
from app.services.multitool_pipeline import MultiToolPipeline
from app.storage.approval_store import SQLiteApprovalStore
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


def test_keyword_approval_stores_in_shared_store():
    gateway = _build_test_gateway()
    call_count = 0

    def _danger_fn():
        nonlocal call_count
        call_count += 1
        return {"result": "danger"}

    gateway.register(
        ToolSpec(tool_name="dangerous_tool", description="危险工具", risk_level=RiskLevel.high, source="local", is_local=True),
        _danger_fn,
    )

    engine = PolicyEngine()
    recorder = TraceRecorder()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_approval.sqlite")
        approval_store = SQLiteApprovalStore(db_path=db_path)
        mt_pipeline = MultiToolPipeline(gateway, policy_engine=engine, trace_recorder=recorder, approval_store=approval_store)

        planner = KeywordPlanner()
        planner.ROUTING_RULES.insert(0, {
            "keywords": ["危险测试"],
            "tool_name": "dangerous_tool",
            "label": "危险测试",
        })

        kernel = AgentKernel(
            context_assembler=ContextAssembler(),
            tool_gateway=gateway,
            hook_pipeline=HookPipeline(),
            policy_engine=engine,
            trace_recorder=recorder,
            planner=planner,
            multitool_pipeline=mt_pipeline,
            approval_store=approval_store,
        )

        task = TaskRun(task_id="test-shared-store", query="危险测试")
        asyncio.run(kernel.run(task))

        approvals = approval_store.list_approvals(status="pending")
        assert len(approvals) >= 1
        assert approvals[0]["tool_name"] == "dangerous_tool"


def test_reject_cancels_persisted_task():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_task.sqlite")
        approval_db_path = os.path.join(tmpdir, "test_approval.sqlite")

        task_store = SQLiteTaskStore(db_path=db_path)
        approval_store = SQLiteApprovalStore(db_path=approval_db_path)

        task = TaskRun(task_id="test-reject-cancel", query="危险测试", status=TaskStatus.waiting_approval)
        task_store.save_task(task)

        approval = approval_store.create_approval(
            task_id="test-reject-cancel",
            tool_name="dangerous_tool",
            action="调用工具",
            risk_level=RiskLevel.high,
        )

        import app.main as main_mod
        orig_ts = main_mod._task_store
        orig_as = main_mod._approval_store
        main_mod._task_store = task_store
        main_mod._approval_store = approval_store

        try:
            response = client.post(f"/approvals/{approval.approval_id}/reject", json={"decided_by": "admin", "reason": "拒绝"})
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "rejected"

            task_data = task_store.get_task("test-reject-cancel")
            assert task_data is not None
            assert task_data["status"] == "cancelled"
            assert task_data["result"]["approval_rejected"] is True
        finally:
            main_mod._task_store = orig_ts
            main_mod._approval_store = orig_as
    reset_runtime_for_test()


def test_reject_cancel_trace():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_task.sqlite")
        approval_db_path = os.path.join(tmpdir, "test_approval.sqlite")

        task_store = SQLiteTaskStore(db_path=db_path)
        approval_store = SQLiteApprovalStore(db_path=approval_db_path)
        recorder = TraceRecorder()

        task = TaskRun(task_id="test-reject-trace", query="危险测试", status=TaskStatus.waiting_approval)
        task_store.save_task(task)

        approval = approval_store.create_approval(
            task_id="test-reject-trace",
            tool_name="dangerous_tool",
            action="调用工具",
            risk_level=RiskLevel.high,
        )

        import app.main as main_mod
        orig_ts = main_mod._task_store
        orig_as = main_mod._approval_store
        orig_tr = main_mod._trace_recorder
        main_mod._task_store = task_store
        main_mod._approval_store = approval_store
        main_mod._trace_recorder = recorder

        try:
            client.post(f"/approvals/{approval.approval_id}/reject", json={"decided_by": "admin", "reason": "拒绝"})
            events = recorder.get_events(task_id="test-reject-trace")
            event_types = [e.event_type for e in events]
            assert "task_cancelled_by_approval" in event_types
        finally:
            main_mod._task_store = orig_ts
            main_mod._approval_store = orig_as
            main_mod._trace_recorder = orig_tr
    reset_runtime_for_test()


def test_keyword_resume_after_approve():
    gateway = _build_test_gateway()
    call_count = 0

    def _danger_fn():
        nonlocal call_count
        call_count += 1
        return {"result": "danger_data"}

    gateway.register(
        ToolSpec(tool_name="dangerous_tool", description="危险工具", risk_level=RiskLevel.high, source="local", is_local=True),
        _danger_fn,
    )

    engine = PolicyEngine()
    recorder = TraceRecorder()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_approval.sqlite")
        task_db_path = os.path.join(tmpdir, "test_task.sqlite")
        approval_store = SQLiteApprovalStore(db_path=db_path)
        task_store = SQLiteTaskStore(db_path=task_db_path)

        mt_pipeline = MultiToolPipeline(gateway, policy_engine=engine, trace_recorder=recorder, approval_store=approval_store)

        planner = KeywordPlanner()
        planner.ROUTING_RULES.insert(0, {
            "keywords": ["危险测试"],
            "tool_name": "dangerous_tool",
            "label": "危险测试",
        })

        kernel = AgentKernel(
            context_assembler=ContextAssembler(),
            tool_gateway=gateway,
            hook_pipeline=HookPipeline(),
            policy_engine=engine,
            trace_recorder=recorder,
            planner=planner,
            multitool_pipeline=mt_pipeline,
            approval_store=approval_store,
        )

        task = TaskRun(task_id="test-resume-kw", query="危险测试")
        result_task = asyncio.run(kernel.run(task))
        assert result_task.status == TaskStatus.waiting_approval

        task_store.save_task(result_task)

        approvals = approval_store.list_approvals(status="pending")
        approval_id = approvals[0]["approval_id"]

        service = ApprovalResumeService(
            approval_store=approval_store,
            task_store=task_store,
            gateway=gateway,
            trace_recorder=recorder,
        )

        approval_store.decide_approval(approval_id, approved=True, decided_by="admin", reason="允许")
        resume_result = service.resume(approval_id)

        assert call_count == 1
        assert resume_result["resumed_from_approval"] is True
        assert resume_result["approval_id"] == approval_id
        assert resume_result["success"] is True
        assert resume_result["data"] == {"result": "danger_data"}

        task_data = task_store.get_task("test-resume-kw")
        assert task_data["status"] == "completed"
        assert task_data["result"]["resumed_from_approval"] is True


def test_keyword_resume_trace():
    gateway = _build_test_gateway()

    def _danger_fn():
        return {"result": "danger_data"}

    gateway.register(
        ToolSpec(tool_name="dangerous_tool", description="危险工具", risk_level=RiskLevel.high, source="local", is_local=True),
        _danger_fn,
    )

    engine = PolicyEngine()
    recorder = TraceRecorder()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_approval.sqlite")
        task_db_path = os.path.join(tmpdir, "test_task.sqlite")
        approval_store = SQLiteApprovalStore(db_path=db_path)
        task_store = SQLiteTaskStore(db_path=task_db_path)

        mt_pipeline = MultiToolPipeline(gateway, policy_engine=engine, trace_recorder=recorder, approval_store=approval_store)

        planner = KeywordPlanner()
        planner.ROUTING_RULES.insert(0, {
            "keywords": ["危险测试"],
            "tool_name": "dangerous_tool",
            "label": "危险测试",
        })

        kernel = AgentKernel(
            context_assembler=ContextAssembler(),
            tool_gateway=gateway,
            hook_pipeline=HookPipeline(),
            policy_engine=engine,
            trace_recorder=recorder,
            planner=planner,
            multitool_pipeline=mt_pipeline,
            approval_store=approval_store,
        )

        task = TaskRun(task_id="test-resume-trace", query="危险测试")
        asyncio.run(kernel.run(task))
        task_store.save_task(task)

        approvals = approval_store.list_approvals(status="pending")
        approval_id = approvals[0]["approval_id"]

        service = ApprovalResumeService(
            approval_store=approval_store,
            task_store=task_store,
            gateway=gateway,
            trace_recorder=recorder,
        )

        approval_store.decide_approval(approval_id, approved=True, decided_by="admin", reason="允许")
        service.resume(approval_id)

        events = recorder.get_events(task_id="test-resume-trace")
        event_types = [e.event_type for e in events]
        assert "approval_resume_started" in event_types
        assert "approval_resume_tool_called" in event_types
        assert "approval_resume_completed" in event_types


def test_multitool_resume_after_approve():
    gateway = _build_test_gateway()
    call_count = 0

    def _danger_fn():
        nonlocal call_count
        call_count += 1
        return {"result": "danger_data"}

    gateway.register(
        ToolSpec(tool_name="dangerous_tool", description="危险工具", risk_level=RiskLevel.high, source="local", is_local=True),
        _danger_fn,
    )

    engine = PolicyEngine()
    recorder = TraceRecorder()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_approval.sqlite")
        task_db_path = os.path.join(tmpdir, "test_task.sqlite")
        approval_store = SQLiteApprovalStore(db_path=db_path)
        task_store = SQLiteTaskStore(db_path=task_db_path)

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

        result = mt_pipeline.run("危险多工具", task_id="test-resume-mt")
        assert result["requires_approval"] is True

        task = TaskRun(task_id="test-resume-mt", query="危险多工具", status=TaskStatus.waiting_approval, result=result)
        task_store.save_task(task)

        approvals = approval_store.list_approvals(status="pending")
        approval_id = approvals[0]["approval_id"]

        service = ApprovalResumeService(
            approval_store=approval_store,
            task_store=task_store,
            gateway=gateway,
            trace_recorder=recorder,
        )

        approval_store.decide_approval(approval_id, approved=True, decided_by="admin", reason="允许")
        resume_result = service.resume(approval_id)

        assert call_count == 1
        assert resume_result["resumed_from_approval"] is True
        assert resume_result["resumed_step_id"] == "s1"
        assert resume_result["success"] is True

        task_data = task_store.get_task("test-resume-mt")
        assert task_data["status"] == "completed"


def test_idempotent_resume():
    gateway = _build_test_gateway()
    call_count = 0

    def _danger_fn():
        nonlocal call_count
        call_count += 1
        return {"result": "danger_data"}

    gateway.register(
        ToolSpec(tool_name="dangerous_tool", description="危险工具", risk_level=RiskLevel.high, source="local", is_local=True),
        _danger_fn,
    )

    engine = PolicyEngine()
    recorder = TraceRecorder()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_approval.sqlite")
        task_db_path = os.path.join(tmpdir, "test_task.sqlite")
        approval_store = SQLiteApprovalStore(db_path=db_path)
        task_store = SQLiteTaskStore(db_path=task_db_path)

        mt_pipeline = MultiToolPipeline(gateway, policy_engine=engine, trace_recorder=recorder, approval_store=approval_store)

        planner = KeywordPlanner()
        planner.ROUTING_RULES.insert(0, {
            "keywords": ["危险测试"],
            "tool_name": "dangerous_tool",
            "label": "危险测试",
        })

        kernel = AgentKernel(
            context_assembler=ContextAssembler(),
            tool_gateway=gateway,
            hook_pipeline=HookPipeline(),
            policy_engine=engine,
            trace_recorder=recorder,
            planner=planner,
            multitool_pipeline=mt_pipeline,
            approval_store=approval_store,
        )

        task = TaskRun(task_id="test-idempotent-resume", query="危险测试")
        asyncio.run(kernel.run(task))
        task_store.save_task(task)

        approvals = approval_store.list_approvals(status="pending")
        approval_id = approvals[0]["approval_id"]

        service = ApprovalResumeService(
            approval_store=approval_store,
            task_store=task_store,
            gateway=gateway,
            trace_recorder=recorder,
        )

        approval_store.decide_approval(approval_id, approved=True, decided_by="admin", reason="允许")
        service.resume(approval_id)
        assert call_count == 1

        second_resume = service.resume(approval_id)
        assert call_count == 1
        assert second_resume.get("already_resumed") is True


def test_approve_auto_resume_via_api():
    gateway = _build_test_gateway()

    def _danger_fn():
        return {"result": "danger_data"}

    gateway.register(
        ToolSpec(tool_name="dangerous_tool", description="危险工具", risk_level=RiskLevel.high, source="local", is_local=True),
        _danger_fn,
    )

    engine = PolicyEngine()
    recorder = TraceRecorder()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_approval.sqlite")
        task_db_path = os.path.join(tmpdir, "test_task.sqlite")
        approval_store = SQLiteApprovalStore(db_path=db_path)
        task_store = SQLiteTaskStore(db_path=task_db_path)

        mt_pipeline = MultiToolPipeline(gateway, policy_engine=engine, trace_recorder=recorder, approval_store=approval_store)

        planner = KeywordPlanner()
        planner.ROUTING_RULES.insert(0, {
            "keywords": ["危险测试"],
            "tool_name": "dangerous_tool",
            "label": "危险测试",
        })

        kernel = AgentKernel(
            context_assembler=ContextAssembler(),
            tool_gateway=gateway,
            hook_pipeline=HookPipeline(),
            policy_engine=engine,
            trace_recorder=recorder,
            planner=planner,
            multitool_pipeline=mt_pipeline,
            approval_store=approval_store,
        )

        task = TaskRun(task_id="test-api-resume", query="危险测试")
        asyncio.run(kernel.run(task))
        task_store.save_task(task)

        approvals = approval_store.list_approvals(status="pending")
        approval_id = approvals[0]["approval_id"]

        import app.main as main_mod
        orig_ts = main_mod._task_store
        orig_as = main_mod._approval_store
        orig_gw = main_mod._gateway
        orig_tr = main_mod._trace_recorder
        main_mod._task_store = task_store
        main_mod._approval_store = approval_store
        main_mod._gateway = gateway
        main_mod._trace_recorder = recorder

        try:
            response = client.post(f"/approvals/{approval_id}/approve", json={"decided_by": "admin", "reason": "允许", "auto_resume": True})
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "approved"
            assert data.get("resume_result") is not None
            assert data["resume_result"]["resumed_from_approval"] is True
            assert data["resume_result"]["success"] is True

            task_data = task_store.get_task("test-api-resume")
            assert task_data["status"] == "completed"
        finally:
            main_mod._task_store = orig_ts
            main_mod._approval_store = orig_as
            main_mod._gateway = orig_gw
            main_mod._trace_recorder = orig_tr
    reset_runtime_for_test()


def test_multitool_resume_no_duplicate_completed_steps():
    gateway = _build_test_gateway()
    safe_call_count = 0
    danger_call_count = 0

    def _safe_fn():
        nonlocal safe_call_count
        safe_call_count += 1
        return {"result": "safe_data"}

    def _danger_fn():
        nonlocal danger_call_count
        danger_call_count += 1
        return {"result": "danger_data"}

    gateway.register(
        ToolSpec(tool_name="safe_tool", description="安全工具", risk_level=RiskLevel.low, source="local", is_local=True),
        _safe_fn,
    )
    gateway.register(
        ToolSpec(tool_name="dangerous_tool", description="危险工具", risk_level=RiskLevel.high, source="local", is_local=True),
        _danger_fn,
    )

    engine = PolicyEngine()
    recorder = TraceRecorder()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_approval.sqlite")
        task_db_path = os.path.join(tmpdir, "test_task.sqlite")
        approval_store = SQLiteApprovalStore(db_path=db_path)
        task_store = SQLiteTaskStore(db_path=task_db_path)

        mt_pipeline = MultiToolPipeline(gateway, policy_engine=engine, trace_recorder=recorder, approval_store=approval_store)

        from app.agent.nodes.multitool_planner import MultiToolPlan, MultiToolPlanStep
        plan = MultiToolPlan(
            matched=True,
            intent="mixed_test",
            steps=[
                MultiToolPlanStep(step_id="s1", tool_name="safe_tool", arguments={}, save_as="safe_result"),
                MultiToolPlanStep(step_id="s2", tool_name="dangerous_tool", arguments={}, save_as="danger_result", depends_on=["s1"]),
            ],
            response_template="mixed test",
            reason="test",
        )

        original_plan = mt_pipeline._planner.plan

        def _mock_plan(query):
            if "混合危险" in query:
                return plan
            return original_plan(query)

        mt_pipeline._planner.plan = _mock_plan

        result = mt_pipeline.run("混合危险", task_id="test-mt-no-dup")
        assert result["requires_approval"] is True
        assert safe_call_count == 1
        assert danger_call_count == 0

        task = TaskRun(task_id="test-mt-no-dup", query="混合危险", status=TaskStatus.waiting_approval, result=result)
        task_store.save_task(task)

        approvals = approval_store.list_approvals(status="pending")
        approval_id = approvals[0]["approval_id"]

        service = ApprovalResumeService(
            approval_store=approval_store,
            task_store=task_store,
            gateway=gateway,
            trace_recorder=recorder,
        )

        approval_store.decide_approval(approval_id, approved=True, decided_by="admin", reason="允许")
        resume_result = service.resume(approval_id)

        assert safe_call_count == 1
        assert danger_call_count == 1
        assert resume_result["resumed_step_id"] == "s2"
