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


def test_resume_failure_not_marked_resumed():
    gateway = _build_test_gateway()
    call_count = 0

    def _failing_fn():
        nonlocal call_count
        call_count += 1
        raise RuntimeError("工具调用失败")

    gateway.register(
        ToolSpec(tool_name="failing_tool", description="失败工具", risk_level=RiskLevel.high, source="local", is_local=True),
        _failing_fn,
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
            "keywords": ["失败测试"],
            "tool_name": "failing_tool",
            "label": "失败测试",
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

        task = TaskRun(task_id="test-fail-resume", query="失败测试")
        asyncio.run(kernel.run(task))
        task_store.save_task(task)

        approvals = approval_store.list_approvals(status="pending")
        approval_id = approvals[0]["approval_id"]

        service = ApprovalResumeService(
            approval_store=approval_store,
            task_store=task_store,
            gateway=gateway,
            trace_recorder=recorder,
            policy_engine=engine,
        )

        approval_store.decide_approval(approval_id, approved=True, decided_by="admin", reason="允许")
        first_result = service.resume(approval_id)
        assert first_result["success"] is False
        assert call_count == 1

        apr = approval_store.get_approval(approval_id)
        assert apr["payload"].get("resumed") is not True
        assert apr["payload"].get("resume_status") == "failed"

        second_result = service.resume(approval_id)
        assert call_count == 2

        apr2 = approval_store.get_approval(approval_id)
        assert apr2["payload"].get("resumed") is not True


def test_resume_success_then_idempotent():
    gateway = _build_test_gateway()
    call_count = 0

    def _success_fn():
        nonlocal call_count
        call_count += 1
        return {"result": "ok"}

    gateway.register(
        ToolSpec(tool_name="success_tool", description="成功工具", risk_level=RiskLevel.high, source="local", is_local=True),
        _success_fn,
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
            "keywords": ["成功测试"],
            "tool_name": "success_tool",
            "label": "成功测试",
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

        task = TaskRun(task_id="test-success-resume", query="成功测试")
        asyncio.run(kernel.run(task))
        task_store.save_task(task)

        approvals = approval_store.list_approvals(status="pending")
        approval_id = approvals[0]["approval_id"]

        service = ApprovalResumeService(
            approval_store=approval_store,
            task_store=task_store,
            gateway=gateway,
            trace_recorder=recorder,
            policy_engine=engine,
        )

        approval_store.decide_approval(approval_id, approved=True, decided_by="admin", reason="允许")
        service.resume(approval_id)
        assert call_count == 1

        third_result = service.resume(approval_id)
        assert call_count == 1
        assert third_result.get("already_resumed") is True


def test_multitool_resume_variable_resolution():
    gateway = _build_test_gateway()

    def _date_fn():
        return {"date": "2024-01-15", "year": 2024}

    def _danger_fn(**kwargs):
        return {"result": "danger_data"}

    gateway.register(
        ToolSpec(tool_name="date_lookup", description="日期查询", risk_level=RiskLevel.low, source="local", is_local=True),
        _date_fn,
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
            intent="var_test",
            steps=[
                MultiToolPlanStep(step_id="s1", tool_name="date_lookup", arguments={}, save_as="date_info"),
                MultiToolPlanStep(step_id="s2", tool_name="dangerous_tool", arguments={"year": "$date_info.result.year"}, save_as="danger_result", depends_on=["s1"]),
            ],
            response_template="var test",
            reason="test",
        )

        original_plan = mt_pipeline._planner.plan

        def _mock_plan(query):
            if "变量测试" in query:
                return plan
            return original_plan(query)

        mt_pipeline._planner.plan = _mock_plan

        result = mt_pipeline.run("变量测试", task_id="test-var-resume")
        assert result["requires_approval"] is True

        task = TaskRun(task_id="test-var-resume", query="变量测试", status=TaskStatus.waiting_approval, result=result)
        task_store.save_task(task)

        approvals = approval_store.list_approvals(status="pending")
        approval_id = approvals[0]["approval_id"]

        service = ApprovalResumeService(
            approval_store=approval_store,
            task_store=task_store,
            gateway=gateway,
            trace_recorder=recorder,
            policy_engine=engine,
        )

        approval_store.decide_approval(approval_id, approved=True, decided_by="admin", reason="允许")
        resume_result = service.resume(approval_id)
        assert resume_result["success"] is True


def test_multitool_resume_missing_variable_fails():
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

        from app.agent.nodes.multitool_planner import MultiToolPlan, MultiToolPlanStep
        plan = MultiToolPlan(
            matched=True,
            intent="missing_var_test",
            steps=[
                MultiToolPlanStep(step_id="s1", tool_name="dangerous_tool", arguments={"year": "$missing_var.result.year"}, save_as="danger_result"),
            ],
            response_template="missing var test",
            reason="test",
        )

        original_plan = mt_pipeline._planner.plan

        def _mock_plan(query):
            if "缺失变量" in query:
                return plan
            return original_plan(query)

        mt_pipeline._planner.plan = _mock_plan

        result = mt_pipeline.run("缺失变量", task_id="test-missing-var")
        assert result["requires_approval"] is True

        task = TaskRun(task_id="test-missing-var", query="缺失变量", status=TaskStatus.waiting_approval, result=result)
        task_store.save_task(task)

        approvals = approval_store.list_approvals(status="pending")
        approval_id = approvals[0]["approval_id"]

        service = ApprovalResumeService(
            approval_store=approval_store,
            task_store=task_store,
            gateway=gateway,
            trace_recorder=recorder,
            policy_engine=engine,
        )

        approval_store.decide_approval(approval_id, approved=True, decided_by="admin", reason="允许")
        resume_result = service.resume(approval_id)
        assert resume_result["success"] is False
        assert resume_result.get("error_type") == "resume_variable_resolution_failed"
        assert resume_result.get("error_path") is not None


def test_multitool_resume_subsequent_low_risk_steps():
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
            intent="subsequent_test",
            steps=[
                MultiToolPlanStep(step_id="s1", tool_name="dangerous_tool", arguments={}, save_as="danger"),
                MultiToolPlanStep(step_id="s2", tool_name="safe_tool", arguments={}, save_as="safe", depends_on=["s1"]),
            ],
            response_template="subsequent test",
            reason="test",
        )

        original_plan = mt_pipeline._planner.plan

        def _mock_plan(query):
            if "后续步骤" in query:
                return plan
            return original_plan(query)

        mt_pipeline._planner.plan = _mock_plan

        result = mt_pipeline.run("后续步骤", task_id="test-subsequent")
        assert result["requires_approval"] is True
        assert danger_call_count == 0
        assert safe_call_count == 0

        task = TaskRun(task_id="test-subsequent", query="后续步骤", status=TaskStatus.waiting_approval, result=result)
        task_store.save_task(task)

        approvals = approval_store.list_approvals(status="pending")
        approval_id = approvals[0]["approval_id"]

        service = ApprovalResumeService(
            approval_store=approval_store,
            task_store=task_store,
            gateway=gateway,
            trace_recorder=recorder,
            policy_engine=engine,
            approval_store_for_new=approval_store,
        )

        approval_store.decide_approval(approval_id, approved=True, decided_by="admin", reason="允许")
        resume_result = service.resume(approval_id)

        assert resume_result["success"] is True
        assert danger_call_count == 1
        assert safe_call_count == 1

        task_data = task_store.get_task("test-subsequent")
        assert task_data["status"] == "completed"

        events = recorder.get_events(task_id="test-subsequent")
        event_types = [e.event_type for e in events]
        assert "multitool_resume_started" in event_types
        assert "multitool_resume_step_completed" in event_types


def test_multitool_resume_subsequent_high_risk_creates_new_approval():
    gateway = _build_test_gateway()
    danger1_count = 0
    danger2_count = 0

    def _danger1_fn():
        nonlocal danger1_count
        danger1_count += 1
        return {"result": "danger1_data"}

    def _danger2_fn():
        nonlocal danger2_count
        danger2_count += 1
        return {"result": "danger2_data"}

    gateway.register(
        ToolSpec(tool_name="dangerous_tool", description="危险工具1", risk_level=RiskLevel.high, source="local", is_local=True),
        _danger1_fn,
    )
    gateway.register(
        ToolSpec(tool_name="dangerous_tool_2", description="危险工具2", risk_level=RiskLevel.high, source="local", is_local=True),
        _danger2_fn,
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
            intent="double_danger_test",
            steps=[
                MultiToolPlanStep(step_id="s1", tool_name="dangerous_tool", arguments={}, save_as="danger1"),
                MultiToolPlanStep(step_id="s2", tool_name="dangerous_tool_2", arguments={}, save_as="danger2", depends_on=["s1"]),
            ],
            response_template="double danger test",
            reason="test",
        )

        original_plan = mt_pipeline._planner.plan

        def _mock_plan(query):
            if "双重危险" in query:
                return plan
            return original_plan(query)

        mt_pipeline._planner.plan = _mock_plan

        result = mt_pipeline.run("双重危险", task_id="test-double-danger")
        assert result["requires_approval"] is True

        task = TaskRun(task_id="test-double-danger", query="双重危险", status=TaskStatus.waiting_approval, result=result)
        task_store.save_task(task)

        approvals = approval_store.list_approvals(status="pending")
        approval_id = approvals[0]["approval_id"]

        service = ApprovalResumeService(
            approval_store=approval_store,
            task_store=task_store,
            gateway=gateway,
            trace_recorder=recorder,
            policy_engine=engine,
            approval_store_for_new=approval_store,
        )

        approval_store.decide_approval(approval_id, approved=True, decided_by="admin", reason="允许")
        resume_result = service.resume(approval_id)

        assert resume_result.get("waiting_approval") is True
        assert resume_result.get("new_approval_id") is not None
        assert danger1_count == 1
        assert danger2_count == 0

        task_data = task_store.get_task("test-double-danger")
        assert task_data["status"] == "waiting_approval"

        events = recorder.get_events(task_id="test-double-danger")
        event_types = [e.event_type for e in events]
        assert "multitool_resume_waiting_approval" in event_types


def test_approvals_summary_api():
    reset_runtime_for_test()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_approval.sqlite")
        store = SQLiteApprovalStore(db_path=db_path)
        store.create_approval(task_id="t1", tool_name="tool1", action="a1", risk_level=RiskLevel.high)
        store.create_approval(task_id="t2", tool_name="tool2", action="a2", risk_level=RiskLevel.high)
        apr = store.create_approval(task_id="t3", tool_name="tool3", action="a3", risk_level=RiskLevel.high)
        store.decide_approval(apr.approval_id, approved=True, decided_by="admin", reason="ok")

        import app.main as main_mod
        original = main_mod._approval_store
        main_mod._approval_store = store

        try:
            response = client.get("/approvals/summary")
            assert response.status_code == 200
            data = response.json()
            assert data["pending_count"] == 2
            assert data["approved_count"] == 1
            assert data["rejected_count"] == 0
        finally:
            main_mod._approval_store = original
    reset_runtime_for_test()


def test_approval_context_api():
    reset_runtime_for_test()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_approval.sqlite")
        store = SQLiteApprovalStore(db_path=db_path)
        apr = store.create_approval(task_id="t-ctx", tool_name="tool1", action="a1", risk_level=RiskLevel.high)

        import app.main as main_mod
        original = main_mod._approval_store
        main_mod._approval_store = store

        try:
            response = client.get(f"/approvals/{apr.approval_id}/context")
            assert response.status_code == 200
            data = response.json()
            assert "approval" in data
            assert "payload" in data
            assert "timeline" in data
            assert data["can_approve"] is True
            assert data["can_reject"] is True
            assert data["can_resume"] is False
        finally:
            main_mod._approval_store = original
    reset_runtime_for_test()


def test_manual_resume_api():
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
            "keywords": ["手动恢复"],
            "tool_name": "dangerous_tool",
            "label": "手动恢复",
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

        task = TaskRun(task_id="test-manual-resume", query="手动恢复")
        asyncio.run(kernel.run(task))
        task_store.save_task(task)

        approvals = approval_store.list_approvals(status="pending")
        approval_id = approvals[0]["approval_id"]

        import app.main as main_mod
        orig_ts = main_mod._task_store
        orig_as = main_mod._approval_store
        orig_gw = main_mod._gateway
        orig_tr = main_mod._trace_recorder
        orig_pe = main_mod._policy_engine
        main_mod._task_store = task_store
        main_mod._approval_store = approval_store
        main_mod._gateway = gateway
        main_mod._trace_recorder = recorder
        main_mod._policy_engine = engine

        try:
            approve_resp = client.post(f"/approvals/{approval_id}/approve", json={"decided_by": "admin", "reason": "允许", "auto_resume": False})
            assert approve_resp.status_code == 200

            resume_resp = client.post(f"/approvals/{approval_id}/resume")
            assert resume_resp.status_code == 200
            data = resume_resp.json()
            assert data.get("resume_result") is not None
            assert data["resume_result"]["resumed_from_approval"] is True

            task_data = task_store.get_task("test-manual-resume")
            assert task_data["status"] == "completed"
        finally:
            main_mod._task_store = orig_ts
            main_mod._approval_store = orig_as
            main_mod._gateway = orig_gw
            main_mod._trace_recorder = orig_tr
            main_mod._policy_engine = orig_pe
    reset_runtime_for_test()


def test_completed_steps_not_repeated_in_resume():
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
            intent="no_repeat_test",
            steps=[
                MultiToolPlanStep(step_id="s1", tool_name="safe_tool", arguments={}, save_as="safe_result"),
                MultiToolPlanStep(step_id="s2", tool_name="dangerous_tool", arguments={}, save_as="danger_result", depends_on=["s1"]),
                MultiToolPlanStep(step_id="s3", tool_name="safe_tool", arguments={}, save_as="safe2_result", depends_on=["s2"]),
            ],
            response_template="no repeat test",
            reason="test",
        )

        original_plan = mt_pipeline._planner.plan

        def _mock_plan(query):
            if "不重复" in query:
                return plan
            return original_plan(query)

        mt_pipeline._planner.plan = _mock_plan

        result = mt_pipeline.run("不重复", task_id="test-no-repeat")
        assert result["requires_approval"] is True
        assert safe_call_count == 1
        assert danger_call_count == 0

        task = TaskRun(task_id="test-no-repeat", query="不重复", status=TaskStatus.waiting_approval, result=result)
        task_store.save_task(task)

        approvals = approval_store.list_approvals(status="pending")
        approval_id = approvals[0]["approval_id"]

        service = ApprovalResumeService(
            approval_store=approval_store,
            task_store=task_store,
            gateway=gateway,
            trace_recorder=recorder,
            policy_engine=engine,
            approval_store_for_new=approval_store,
        )

        approval_store.decide_approval(approval_id, approved=True, decided_by="admin", reason="允许")
        resume_result = service.resume(approval_id)

        assert resume_result["success"] is True
        assert safe_call_count == 2
        assert danger_call_count == 1

        tool_calls = resume_result.get("tool_calls", [])
        step_ids = [tc.get("step_id") for tc in tool_calls]
        assert "s1" in step_ids
        assert "s2" in step_ids
        assert "s3" in step_ids


def test_subsequent_high_risk_original_approval_consumed():
    gateway = _build_test_gateway()
    danger1_count = 0

    def _danger1_fn():
        nonlocal danger1_count
        danger1_count += 1
        return {"result": "danger1_data"}

    def _danger2_fn():
        return {"result": "danger2_data"}

    gateway.register(
        ToolSpec(tool_name="dangerous_tool", description="危险工具1", risk_level=RiskLevel.high, source="local", is_local=True),
        _danger1_fn,
    )
    gateway.register(
        ToolSpec(tool_name="dangerous_tool_2", description="危险工具2", risk_level=RiskLevel.high, source="local", is_local=True),
        _danger2_fn,
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
            intent="consumed_test",
            steps=[
                MultiToolPlanStep(step_id="s1", tool_name="dangerous_tool", arguments={}, save_as="danger1"),
                MultiToolPlanStep(step_id="s2", tool_name="dangerous_tool_2", arguments={}, save_as="danger2", depends_on=["s1"]),
            ],
            response_template="consumed test",
            reason="test",
        )

        original_plan = mt_pipeline._planner.plan
        mt_pipeline._planner.plan = lambda q: plan if "消费测试" in q else original_plan(q)

        result = mt_pipeline.run("消费测试", task_id="test-consumed")
        assert result["requires_approval"] is True

        task = TaskRun(task_id="test-consumed", query="消费测试", status=TaskStatus.waiting_approval, result=result)
        task_store.save_task(task)

        approvals = approval_store.list_approvals(status="pending")
        approval_id = approvals[0]["approval_id"]

        service = ApprovalResumeService(
            approval_store=approval_store,
            task_store=task_store,
            gateway=gateway,
            trace_recorder=recorder,
            policy_engine=engine,
            approval_store_for_new=approval_store,
        )

        approval_store.decide_approval(approval_id, approved=True, decided_by="admin", reason="允许")
        resume_result = service.resume(approval_id)

        assert resume_result.get("waiting_approval") is True
        assert danger1_count == 1

        apr = approval_store.get_approval(approval_id)
        assert apr["payload"].get("resumed") is True
        assert apr["payload"].get("approval_consumed") is True
        assert apr["payload"].get("resume_status") == "waiting_approval"


def test_subsequent_high_risk_second_resume_idempotent():
    gateway = _build_test_gateway()
    danger1_count = 0

    def _danger1_fn():
        nonlocal danger1_count
        danger1_count += 1
        return {"result": "danger1_data"}

    def _danger2_fn():
        return {"result": "danger2_data"}

    gateway.register(
        ToolSpec(tool_name="dangerous_tool", description="危险工具1", risk_level=RiskLevel.high, source="local", is_local=True),
        _danger1_fn,
    )
    gateway.register(
        ToolSpec(tool_name="dangerous_tool_2", description="危险工具2", risk_level=RiskLevel.high, source="local", is_local=True),
        _danger2_fn,
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
            intent="idempotent_test",
            steps=[
                MultiToolPlanStep(step_id="s1", tool_name="dangerous_tool", arguments={}, save_as="danger1"),
                MultiToolPlanStep(step_id="s2", tool_name="dangerous_tool_2", arguments={}, save_as="danger2", depends_on=["s1"]),
            ],
            response_template="idempotent test",
            reason="test",
        )

        original_plan = mt_pipeline._planner.plan
        mt_pipeline._planner.plan = lambda q: plan if "幂等测试" in q else original_plan(q)

        result = mt_pipeline.run("幂等测试", task_id="test-idempotent")
        task = TaskRun(task_id="test-idempotent", query="幂等测试", status=TaskStatus.waiting_approval, result=result)
        task_store.save_task(task)

        approvals = approval_store.list_approvals(status="pending")
        approval_id = approvals[0]["approval_id"]

        service = ApprovalResumeService(
            approval_store=approval_store,
            task_store=task_store,
            gateway=gateway,
            trace_recorder=recorder,
            policy_engine=engine,
            approval_store_for_new=approval_store,
        )

        approval_store.decide_approval(approval_id, approved=True, decided_by="admin", reason="允许")
        service.resume(approval_id)
        assert danger1_count == 1

        second_result = service.resume(approval_id)
        assert danger1_count == 1
        assert second_result.get("already_resumed") is True


def test_subsequent_low_risk_failure_consumes_approval():
    gateway = _build_test_gateway()
    danger_count = 0
    failing_count = 0

    def _danger_fn():
        nonlocal danger_count
        danger_count += 1
        return {"result": "danger_data"}

    def _failing_fn():
        nonlocal failing_count
        failing_count += 1
        return {"error": "low-risk tool failed"}

    gateway.register(
        ToolSpec(tool_name="dangerous_tool", description="危险工具", risk_level=RiskLevel.high, source="local", is_local=True),
        _danger_fn,
    )
    gateway.register(
        ToolSpec(tool_name="failing_safe_tool", description="失败安全工具", risk_level=RiskLevel.low, source="local", is_local=True),
        _failing_fn,
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
            intent="downstream_fail_test",
            steps=[
                MultiToolPlanStep(step_id="s1", tool_name="dangerous_tool", arguments={}, save_as="danger"),
                MultiToolPlanStep(step_id="s2", tool_name="failing_safe_tool", arguments={}, save_as="fail_result", depends_on=["s1"]),
            ],
            response_template="downstream fail test",
            reason="test",
        )

        original_plan = mt_pipeline._planner.plan
        mt_pipeline._planner.plan = lambda q: plan if "下游失败" in q else original_plan(q)

        result = mt_pipeline.run("下游失败", task_id="test-downstream-fail")
        assert result["requires_approval"] is True

        task = TaskRun(task_id="test-downstream-fail", query="下游失败", status=TaskStatus.waiting_approval, result=result)
        task_store.save_task(task)

        approvals = approval_store.list_approvals(status="pending")
        approval_id = approvals[0]["approval_id"]

        service = ApprovalResumeService(
            approval_store=approval_store,
            task_store=task_store,
            gateway=gateway,
            trace_recorder=recorder,
            policy_engine=engine,
            approval_store_for_new=approval_store,
        )

        approval_store.decide_approval(approval_id, approved=True, decided_by="admin", reason="允许")
        resume_result = service.resume(approval_id)

        assert resume_result["success"] is False
        assert danger_count == 1
        assert failing_count == 1

        apr = approval_store.get_approval(approval_id)
        assert apr["payload"].get("resumed") is True
        assert apr["payload"].get("approval_consumed") is True
        assert apr["payload"].get("resume_status") == "downstream_failed"


def test_downstream_fail_second_resume_no_repeat():
    gateway = _build_test_gateway()
    danger_count = 0

    def _danger_fn():
        nonlocal danger_count
        danger_count += 1
        return {"result": "danger_data"}

    def _failing_fn():
        return {"error": "low-risk tool failed"}

    gateway.register(
        ToolSpec(tool_name="dangerous_tool", description="危险工具", risk_level=RiskLevel.high, source="local", is_local=True),
        _danger_fn,
    )
    gateway.register(
        ToolSpec(tool_name="failing_safe_tool", description="失败安全工具", risk_level=RiskLevel.low, source="local", is_local=True),
        _failing_fn,
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
            intent="no_repeat_test",
            steps=[
                MultiToolPlanStep(step_id="s1", tool_name="dangerous_tool", arguments={}, save_as="danger"),
                MultiToolPlanStep(step_id="s2", tool_name="failing_safe_tool", arguments={}, save_as="fail_result", depends_on=["s1"]),
            ],
            response_template="no repeat test",
            reason="test",
        )

        original_plan = mt_pipeline._planner.plan
        mt_pipeline._planner.plan = lambda q: plan if "不重复失败" in q else original_plan(q)

        result = mt_pipeline.run("不重复失败", task_id="test-no-repeat-fail")
        task = TaskRun(task_id="test-no-repeat-fail", query="不重复失败", status=TaskStatus.waiting_approval, result=result)
        task_store.save_task(task)

        approvals = approval_store.list_approvals(status="pending")
        approval_id = approvals[0]["approval_id"]

        service = ApprovalResumeService(
            approval_store=approval_store,
            task_store=task_store,
            gateway=gateway,
            trace_recorder=recorder,
            policy_engine=engine,
            approval_store_for_new=approval_store,
        )

        approval_store.decide_approval(approval_id, approved=True, decided_by="admin", reason="允许")
        service.resume(approval_id)
        assert danger_count == 1

        second_result = service.resume(approval_id)
        assert danger_count == 1
        assert second_result.get("already_resumed") is True


def test_approved_step_failure_allows_retry():
    gateway = _build_test_gateway()
    call_count = 0

    def _flaky_fn():
        nonlocal call_count
        call_count += 1
        if call_count <= 1:
            return {"error": "transient failure"}
        return {"result": "ok"}

    gateway.register(
        ToolSpec(tool_name="flaky_tool", description="不稳定工具", risk_level=RiskLevel.high, source="local", is_local=True),
        _flaky_fn,
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
            intent="retry_test",
            steps=[
                MultiToolPlanStep(step_id="s1", tool_name="flaky_tool", arguments={}, save_as="flaky"),
            ],
            response_template="retry test",
            reason="test",
        )

        original_plan = mt_pipeline._planner.plan
        mt_pipeline._planner.plan = lambda q: plan if "重试测试" in q else original_plan(q)

        result = mt_pipeline.run("重试测试", task_id="test-retry")
        task = TaskRun(task_id="test-retry", query="重试测试", status=TaskStatus.waiting_approval, result=result)
        task_store.save_task(task)

        approvals = approval_store.list_approvals(status="pending")
        approval_id = approvals[0]["approval_id"]

        service = ApprovalResumeService(
            approval_store=approval_store,
            task_store=task_store,
            gateway=gateway,
            trace_recorder=recorder,
            policy_engine=engine,
        )

        approval_store.decide_approval(approval_id, approved=True, decided_by="admin", reason="允许")
        first_result = service.resume(approval_id)
        assert first_result["success"] is False
        assert call_count == 1

        apr = approval_store.get_approval(approval_id)
        assert apr["payload"].get("resumed") is not True
        assert apr["payload"].get("approval_consumed") is not True

        second_result = service.resume(approval_id)
        assert call_count == 2
        assert second_result["success"] is True

        apr2 = approval_store.get_approval(approval_id)
        assert apr2["payload"].get("resumed") is True
        assert apr2["payload"].get("approval_consumed") is True


def test_depends_on_not_satisfied_in_resume():
    gateway = _build_test_gateway()
    danger_count = 0

    def _danger_fn():
        nonlocal danger_count
        danger_count += 1
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
            intent="dep_test",
            steps=[
                MultiToolPlanStep(step_id="s1", tool_name="dangerous_tool", arguments={}, save_as="danger"),
                MultiToolPlanStep(step_id="s2", tool_name="dangerous_tool", arguments={}, save_as="danger2", depends_on=["s1", "s_missing"]),
            ],
            response_template="dep test",
            reason="test",
        )

        original_plan = mt_pipeline._planner.plan
        mt_pipeline._planner.plan = lambda q: plan if "依赖测试" in q else original_plan(q)

        result = mt_pipeline.run("依赖测试", task_id="test-dep")
        task = TaskRun(task_id="test-dep", query="依赖测试", status=TaskStatus.waiting_approval, result=result)
        task_store.save_task(task)

        approvals = approval_store.list_approvals(status="pending")
        approval_id = approvals[0]["approval_id"]

        service = ApprovalResumeService(
            approval_store=approval_store,
            task_store=task_store,
            gateway=gateway,
            trace_recorder=recorder,
            policy_engine=engine,
            approval_store_for_new=approval_store,
        )

        approval_store.decide_approval(approval_id, approved=True, decided_by="admin", reason="允许")
        resume_result = service.resume(approval_id)

        assert resume_result["success"] is False
        assert resume_result.get("error_type") == "resume_dependency_not_satisfied"
        assert "s_missing" in resume_result.get("missing_depends_on", [])
        assert danger_count == 1
