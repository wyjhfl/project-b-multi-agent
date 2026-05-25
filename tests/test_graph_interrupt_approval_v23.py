from __future__ import annotations

import asyncio
import sqlite3

from app.agent.graph.kernel import AgentKernel
from app.harness.context.assembler import ContextAssembler
from app.harness.gateway.tool_gateway import ToolGateway
from app.harness.hooks.pipeline import HookPipeline
from app.harness.policy.engine import PolicyEngine
from app.harness.trace.recorder import TraceRecorder
from app.models.schemas import RiskLevel, TaskRun, TaskStatus, ToolSpec
from app.storage.approval_store import SQLiteApprovalStore
from app.storage.graph_checkpoint_store import SQLiteGraphCheckpointStore


class _DangerPlanner:
    def plan(self, query: str):
        if "危险" in query:
            return {"tool_name": "dangerous_tool", "matched": True, "label": "危险工具"}
        return {"tool_name": "get_today_gmv", "matched": True, "label": "今日 GMV"}

    def get_label(self, tool_name: str | None) -> str:
        return "危险工具" if tool_name == "dangerous_tool" else "今日 GMV"


def _build_gateway(call_count: dict[str, int]) -> ToolGateway:
    gateway = ToolGateway()

    def _low_tool():
        call_count["low"] = call_count.get("low", 0) + 1
        return {"value": 42}

    def _dangerous_tool():
        call_count["dangerous"] = call_count.get("dangerous", 0) + 1
        return {"danger": True}

    gateway.register(
        ToolSpec(tool_name="get_today_gmv", description="低风险 GMV", risk_level=RiskLevel.low, permission_scope="read"),
        _low_tool,
    )
    gateway.register(
        ToolSpec(tool_name="dangerous_tool", description="危险工具", risk_level=RiskLevel.high, permission_scope="admin"),
        _dangerous_tool,
    )
    return gateway


def _build_kernel(checkpoint_store, approval_store=None, call_count=None) -> AgentKernel:
    from app.agent.graph.runtime_adapter import GraphRuntimeAdapter

    call_count = call_count if call_count is not None else {}
    assembler = ContextAssembler()
    gateway = _build_gateway(call_count)
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


def test_graph_high_risk_keyword_creates_approval_and_pending_checkpoint(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "graph_runtime_enabled", True)
    checkpoint_store = SQLiteGraphCheckpointStore(db_path=str(tmp_path / "graph.sqlite"))
    approval_store = SQLiteApprovalStore(db_path=str(tmp_path / "approval.sqlite"))
    call_count: dict[str, int] = {}
    kernel = _build_kernel(checkpoint_store, approval_store, call_count)

    task = TaskRun(task_id="task-danger", query="危险操作")
    result = asyncio.run(kernel.run_with_options(task, mode="keyword"))

    assert result.status == TaskStatus.waiting_approval
    assert result.result is not None
    assert result.result["success"] is False
    assert result.result["requires_approval"] is True
    assert result.result["graph_interrupt"] is True
    assert result.result["graph_runtime"] is True
    assert result.result["not_supported"] is True
    assert result.result["approval_id"].startswith("apr_")
    assert result.result["checkpoint_id"].startswith("graph-task-danger-execute-")
    assert call_count.get("dangerous", 0) == 0

    approval = approval_store.get_approval(result.result["approval_id"])
    assert approval is not None
    assert approval["task_id"] == "task-danger"
    assert approval["tool_name"] == "dangerous_tool"
    assert approval["status"] == "pending"

    payload = approval["payload"]
    assert payload["mode"] == "graph_keyword"
    assert payload["checkpoint_id"] == result.result["checkpoint_id"]
    assert payload["graph_runtime"] is True
    assert payload["query"] == "危险操作"
    assert payload["tool_name"] == "dangerous_tool"
    assert payload["arguments"] == {}
    assert payload["interrupt_payload"]["interrupt_type"] == "tool_approval"
    assert payload["interrupt_payload"]["checkpoint_id"] == result.result["checkpoint_id"]

    checkpoint = checkpoint_store.get_checkpoint(result.result["checkpoint_id"])
    assert checkpoint is not None
    assert checkpoint["status"] in ("interrupted", "blocked")
    assert checkpoint["approval_id"] == result.result["approval_id"]
    assert checkpoint["pending_interrupt"] == payload["interrupt_payload"]


def test_interrupt_payload_contains_required_fields(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "graph_runtime_enabled", True)
    checkpoint_store = SQLiteGraphCheckpointStore(db_path=str(tmp_path / "graph.sqlite"))
    approval_store = SQLiteApprovalStore(db_path=str(tmp_path / "approval.sqlite"))
    kernel = _build_kernel(checkpoint_store, approval_store, {})

    task = TaskRun(task_id="task-payload", query="危险操作")
    result = asyncio.run(kernel.run_with_options(task, mode="keyword"))
    approval = approval_store.get_approval(result.result["approval_id"])
    interrupt_payload = approval["payload"]["interrupt_payload"]

    assert interrupt_payload["schema_version"] == 1
    assert interrupt_payload["interrupt_type"] == "tool_approval"
    assert interrupt_payload["task_id"] == "task-payload"
    assert interrupt_payload["node"] == "execute"
    assert interrupt_payload["mode"] == "keyword"
    assert interrupt_payload["tool_name"] == "dangerous_tool"
    assert interrupt_payload["arguments"] == {}
    assert interrupt_payload["risk_level"] == "high"
    assert interrupt_payload["permission_scope"] == "admin"
    assert interrupt_payload["policy_decision"]["requires_approval"] is True
    assert "agent_reason" in interrupt_payload
    assert isinstance(interrupt_payload["trace_context"], dict)
    assert interrupt_payload["created_at"]


def test_graph_high_risk_without_approval_store_fails_not_waiting(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "graph_runtime_enabled", True)
    checkpoint_store = SQLiteGraphCheckpointStore(db_path=str(tmp_path / "graph.sqlite"))
    call_count: dict[str, int] = {}
    kernel = _build_kernel(checkpoint_store, approval_store=None, call_count=call_count)

    task = TaskRun(task_id="task-no-approval-store", query="危险操作")
    result = asyncio.run(kernel.run_with_options(task, mode="keyword"))

    assert result.status == TaskStatus.failed
    assert result.result is not None
    assert result.result["requires_approval"] is True
    assert result.result["approval_id"] is None
    assert result.result["graph_interrupt"] is False
    assert result.result["not_supported"] is True
    assert call_count.get("dangerous", 0) == 0


def test_low_risk_graph_path_still_success_and_creates_no_approval(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "graph_runtime_enabled", True)
    checkpoint_store = SQLiteGraphCheckpointStore(db_path=str(tmp_path / "graph.sqlite"))
    approval_store = SQLiteApprovalStore(db_path=str(tmp_path / "approval.sqlite"))
    call_count: dict[str, int] = {}
    kernel = _build_kernel(checkpoint_store, approval_store, call_count)

    task = TaskRun(task_id="task-low", query="今天GMV多少")
    result = asyncio.run(kernel.run_with_options(task, mode="keyword"))

    assert result.status == TaskStatus.completed
    assert result.result["success"] is True
    assert call_count.get("low") == 1
    assert approval_store.list_approvals() == []


def test_default_graph_runtime_false_still_uses_legacy_hitl(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "graph_runtime_enabled", False)
    checkpoint_store = SQLiteGraphCheckpointStore(db_path=str(tmp_path / "graph.sqlite"))
    approval_store = SQLiteApprovalStore(db_path=str(tmp_path / "approval.sqlite"))
    call_count: dict[str, int] = {}
    kernel = _build_kernel(checkpoint_store, approval_store, call_count)

    task = TaskRun(task_id="task-legacy-danger", query="危险操作")
    result = asyncio.run(kernel.run_with_options(task, mode="keyword"))

    assert result.status == TaskStatus.waiting_approval
    assert result.result is not None
    assert result.result["requires_approval"] is True
    assert result.result["approval_id"].startswith("apr_")
    assert result.result.get("graph_runtime") is None
    assert checkpoint_store.get_latest_for_task("task-legacy-danger") is None
    assert approval_store.get_approval(result.result["approval_id"]) is not None
    assert call_count.get("dangerous", 0) == 0
