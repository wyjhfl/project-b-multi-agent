from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from app.agent.graph.kernel import AgentKernel
from app.agent.graph.runtime_adapter import GraphRuntimeAdapter
from app.harness.context.assembler import ContextAssembler
from app.harness.gateway.tool_gateway import ToolGateway
from app.harness.hooks.pipeline import HookPipeline
from app.harness.policy.engine import PolicyEngine
from app.harness.trace.recorder import TraceRecorder
from app.main import app, reset_runtime_for_test
from app.models.schemas import RiskLevel, TaskRun, TaskStatus, ToolSpec
from app.services.approval_resume import ApprovalResumeService
from app.storage.approval_store import SQLiteApprovalStore
from app.storage.graph_checkpoint_store import SQLiteGraphCheckpointStore
from app.storage.task_store import SQLiteTaskStore


client = TestClient(app)


class _DangerPlanner:
    def plan(self, query: str):
        if "危险" in query:
            return {"tool_name": "dangerous_tool", "matched": True, "label": "危险工具"}
        return {"tool_name": "get_today_gmv", "matched": True, "label": "今日 GMV"}

    def get_label(self, tool_name: str | None) -> str:
        return "危险工具" if tool_name == "dangerous_tool" else "今日 GMV"


def _build_gateway(call_count: dict[str, int]) -> ToolGateway:
    gateway = ToolGateway()

    def _dangerous_tool():
        call_count["dangerous"] = call_count.get("dangerous", 0) + 1
        return {"danger": True}

    gateway.register(
        ToolSpec(tool_name="dangerous_tool", description="危险工具", risk_level=RiskLevel.high, permission_scope="admin"),
        _dangerous_tool,
    )
    return gateway


def _build_graph_kernel(checkpoint_store, approval_store, gateway) -> AgentKernel:
    assembler = ContextAssembler()
    engine = PolicyEngine()
    recorder = TraceRecorder()
    planner = _DangerPlanner()
    adapter = GraphRuntimeAdapter(
        context_assembler=assembler,
        gateway=gateway,
        policy_engine=engine,
        checkpoint_store=checkpoint_store,
        trace_recorder=recorder,
        planner=planner,
        approval_store=approval_store,
    )
    return AgentKernel(
        context_assembler=assembler,
        tool_gateway=gateway,
        hook_pipeline=HookPipeline(),
        policy_engine=engine,
        trace_recorder=recorder,
        planner=planner,
        approval_store=approval_store,
        graph_runtime_adapter=adapter,
    )


def _create_graph_approval(tmp_path, monkeypatch, call_count=None):
    from app.core.config import settings

    monkeypatch.setattr(settings, "graph_runtime_enabled", True)
    call_count = call_count if call_count is not None else {}
    checkpoint_store = SQLiteGraphCheckpointStore(db_path=str(tmp_path / "graph.sqlite"))
    approval_store = SQLiteApprovalStore(db_path=str(tmp_path / "approval.sqlite"))
    task_store = SQLiteTaskStore(db_path=str(tmp_path / "task.sqlite"))
    gateway = _build_gateway(call_count)
    kernel = _build_graph_kernel(checkpoint_store, approval_store, gateway)

    task = TaskRun(task_id="task-danger", query="危险操作")
    result_task = asyncio.run(kernel.run_with_options(task, mode="keyword"))
    task_store.save_task(result_task, mode="keyword")
    approval_id = result_task.result["approval_id"]
    checkpoint_id = result_task.result["checkpoint_id"]
    return checkpoint_store, approval_store, task_store, gateway, approval_id, checkpoint_id, call_count


def _build_service(checkpoint_store, approval_store, task_store, gateway) -> ApprovalResumeService:
    return ApprovalResumeService(
        approval_store=approval_store,
        task_store=task_store,
        gateway=gateway,
        trace_recorder=TraceRecorder(),
        policy_engine=PolicyEngine(),
        graph_checkpoint_store=checkpoint_store,
    )


def test_approve_graph_approval_then_resume_completes_task(tmp_path, monkeypatch):
    checkpoint_store, approval_store, task_store, gateway, approval_id, checkpoint_id, call_count = _create_graph_approval(tmp_path, monkeypatch)
    approval_store.decide_approval(approval_id, approved=True, decided_by="admin", reason="允许")
    service = _build_service(checkpoint_store, approval_store, task_store, gateway)

    result = service.resume(approval_id)

    assert result["graph_resumed"] is True
    assert result["success"] is True
    assert result["tool_called"] == "dangerous_tool"
    assert result["approval_id"] == approval_id
    assert result["checkpoint_id"] == checkpoint_id
    assert result["approved_step_executed"] is True
    assert result["approval_consumed"] is True
    assert call_count["dangerous"] == 1

    task = task_store.get_task("task-danger")
    assert task["status"] == "completed"
    assert task["result"]["graph_resumed"] is True

    checkpoint = checkpoint_store.get_checkpoint(checkpoint_id)
    assert checkpoint["consumed"] is True
    assert checkpoint["status"] == "resumed"
    assert checkpoint["result_snapshot"]["approval_id"] == approval_id

    approval = approval_store.get_approval(approval_id)
    assert approval["payload"]["resumed"] is True
    assert approval["payload"]["resume_result"]["graph_resumed"] is True


def test_repeated_graph_resume_does_not_call_tool_twice(tmp_path, monkeypatch):
    checkpoint_store, approval_store, task_store, gateway, approval_id, _checkpoint_id, call_count = _create_graph_approval(tmp_path, monkeypatch)
    approval_store.decide_approval(approval_id, approved=True, decided_by="admin", reason="允许")
    service = _build_service(checkpoint_store, approval_store, task_store, gateway)

    first = service.resume(approval_id)
    second = service.resume(approval_id)

    assert first["success"] is True
    assert second["already_resumed"] is True
    assert call_count["dangerous"] == 1


def test_graph_checkpoint_claim_failure_does_not_execute_tool(tmp_path, monkeypatch):
    checkpoint_store, approval_store, task_store, gateway, approval_id, checkpoint_id, call_count = _create_graph_approval(tmp_path, monkeypatch)
    approval_store.decide_approval(approval_id, approved=True, decided_by="admin", reason="允许")
    claimed = checkpoint_store.claim_for_resume(checkpoint_id, approval_id)
    assert claimed is not None
    service = _build_service(checkpoint_store, approval_store, task_store, gateway)

    result = service.resume(approval_id)

    assert result["resumed"] is False
    assert result["error_type"] == "checkpoint_claim_failed"
    assert call_count.get("dangerous", 0) == 0


def test_rejected_graph_approval_cancels_checkpoint_and_task(tmp_path, monkeypatch):
    checkpoint_store, approval_store, task_store, _gateway, approval_id, checkpoint_id, _call_count = _create_graph_approval(tmp_path, monkeypatch)

    import app.main as main_mod

    orig_task_store = main_mod._task_store
    orig_approval_store = main_mod._approval_store
    orig_graph_store = main_mod._graph_checkpoint_store
    main_mod._task_store = task_store
    main_mod._approval_store = approval_store
    main_mod._graph_checkpoint_store = checkpoint_store
    try:
        response = client.post(f"/approvals/{approval_id}/reject", json={"decided_by": "admin", "reason": "拒绝"})
    finally:
        main_mod._task_store = orig_task_store
        main_mod._approval_store = orig_approval_store
        main_mod._graph_checkpoint_store = orig_graph_store
        reset_runtime_for_test()

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert task_store.get_task("task-danger")["status"] == "cancelled"
    assert checkpoint_store.get_checkpoint(checkpoint_id)["status"] == "cancelled"


def test_graph_resume_restart_recovery_from_persistent_stores(tmp_path, monkeypatch):
    graph_db = tmp_path / "graph.sqlite"
    approval_db = tmp_path / "approval.sqlite"
    task_db = tmp_path / "task.sqlite"
    from app.core.config import settings

    monkeypatch.setattr(settings, "graph_runtime_enabled", True)
    call_count: dict[str, int] = {}
    checkpoint_store = SQLiteGraphCheckpointStore(db_path=str(graph_db))
    approval_store = SQLiteApprovalStore(db_path=str(approval_db))
    task_store = SQLiteTaskStore(db_path=str(task_db))
    gateway = _build_gateway(call_count)
    kernel = _build_graph_kernel(checkpoint_store, approval_store, gateway)
    result_task = asyncio.run(kernel.run_with_options(TaskRun(task_id="task-danger", query="危险操作"), mode="keyword"))
    task_store.save_task(result_task, mode="keyword")
    approval_id = result_task.result["approval_id"]

    approval_store.decide_approval(approval_id, approved=True, decided_by="admin", reason="允许")

    recovered_checkpoint_store = SQLiteGraphCheckpointStore(db_path=str(graph_db))
    recovered_approval_store = SQLiteApprovalStore(db_path=str(approval_db))
    recovered_task_store = SQLiteTaskStore(db_path=str(task_db))
    recovered_service = _build_service(recovered_checkpoint_store, recovered_approval_store, recovered_task_store, gateway)

    result = recovered_service.resume(approval_id)

    assert result["success"] is True
    assert result["graph_resumed"] is True
    assert call_count["dangerous"] == 1


def test_legacy_keyword_resume_still_uses_legacy_path(tmp_path):
    call_count: dict[str, int] = {}
    gateway = _build_gateway(call_count)
    approval_store = SQLiteApprovalStore(db_path=str(tmp_path / "approval.sqlite"))
    task_store = SQLiteTaskStore(db_path=str(tmp_path / "task.sqlite"))
    task_store.save_task(TaskRun(task_id="legacy-task", query="legacy", status=TaskStatus.waiting_approval))
    approval = approval_store.create_approval(
        task_id="legacy-task",
        tool_name="dangerous_tool",
        action="legacy keyword approval",
        risk_level=RiskLevel.high,
        payload={"mode": "keyword", "tool_name": "dangerous_tool", "arguments": {}},
    )
    approval_store.decide_approval(approval.approval_id, approved=True, decided_by="admin", reason="允许")
    service = ApprovalResumeService(approval_store=approval_store, task_store=task_store, gateway=gateway)

    result = service.resume(approval.approval_id)

    assert result.get("graph_resumed") is not True
    assert result["resumed_from_approval"] is True
    assert result["success"] is True
    assert call_count["dangerous"] == 1


def test_graph_approval_without_checkpoint_id_errors_clearly(tmp_path):
    approval_store = SQLiteApprovalStore(db_path=str(tmp_path / "approval.sqlite"))
    task_store = SQLiteTaskStore(db_path=str(tmp_path / "task.sqlite"))
    checkpoint_store = SQLiteGraphCheckpointStore(db_path=str(tmp_path / "graph.sqlite"))
    gateway = _build_gateway({})
    task_store.save_task(TaskRun(task_id="task-missing-cp", query="danger", status=TaskStatus.waiting_approval))
    approval = approval_store.create_approval(
        task_id="task-missing-cp",
        tool_name="dangerous_tool",
        action="graph approval missing checkpoint",
        risk_level=RiskLevel.high,
        payload={"mode": "graph_keyword", "tool_name": "dangerous_tool", "arguments": {}},
    )
    approval_store.decide_approval(approval.approval_id, approved=True, decided_by="admin", reason="允许")
    service = _build_service(checkpoint_store, approval_store, task_store, gateway)

    result = service.resume(approval.approval_id)

    assert result["resumed"] is False
    assert result["error_type"] == "missing_checkpoint_id"
