from __future__ import annotations

import asyncio

from app.agent.graph.kernel import AgentKernel
from app.harness.context.assembler import ContextAssembler
from app.harness.gateway.tool_gateway import ToolGateway
from app.harness.hooks.pipeline import HookPipeline
from app.harness.policy.engine import PolicyEngine
from app.harness.trace.recorder import TraceRecorder
from app.models.schemas import RiskLevel, TaskRun, TaskStatus, ToolSpec
from app.storage.graph_checkpoint_store import SQLiteGraphCheckpointStore


def _build_gateway(call_count: dict[str, int] | None = None) -> ToolGateway:
    gateway = ToolGateway()

    def _low_tool():
        if call_count is not None:
            call_count["low"] = call_count.get("low", 0) + 1
        return {"value": 42}

    def _dangerous_tool():
        if call_count is not None:
            call_count["dangerous"] = call_count.get("dangerous", 0) + 1
        return {"danger": True}

    gateway.register(
        ToolSpec(tool_name="get_today_gmv", description="低风险 GMV", risk_level=RiskLevel.low, source="local", is_local=True),
        _low_tool,
    )
    gateway.register(
        ToolSpec(tool_name="dangerous_tool", description="危险工具", risk_level=RiskLevel.high, source="local", is_local=True),
        _dangerous_tool,
    )
    return gateway


def _build_kernel(checkpoint_store, call_count=None) -> AgentKernel:
    from app.agent.graph.runtime_adapter import GraphRuntimeAdapter
    from app.agent.nodes.planner import KeywordPlanner

    class DangerPlanner(KeywordPlanner):
        ROUTING_RULES = [
            {"keywords": ["危险"], "tool_name": "dangerous_tool", "label": "危险工具"},
            *KeywordPlanner.ROUTING_RULES,
        ]

    assembler = ContextAssembler()
    gateway = _build_gateway(call_count)
    engine = PolicyEngine()
    recorder = TraceRecorder()
    planner = DangerPlanner()
    adapter = GraphRuntimeAdapter(
        context_assembler=assembler,
        gateway=gateway,
        policy_engine=engine,
        checkpoint_store=checkpoint_store,
        trace_recorder=recorder,
        planner=planner,
    )
    return AgentKernel(
        context_assembler=assembler,
        tool_gateway=gateway,
        hook_pipeline=HookPipeline(),
        policy_engine=engine,
        trace_recorder=recorder,
        planner=planner,
        graph_runtime_adapter=adapter,
    )


def test_graph_runtime_enabled_default_false():
    from app.core.config import settings

    assert settings.graph_runtime_enabled is False


def test_default_false_agentkernel_uses_legacy_and_writes_no_graph_checkpoint(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "graph_runtime_enabled", False)
    checkpoint_store = SQLiteGraphCheckpointStore(db_path=str(tmp_path / "graph.sqlite"))
    call_count: dict[str, int] = {}
    kernel = _build_kernel(checkpoint_store, call_count)

    task = TaskRun(task_id="task-legacy", query="今天GMV多少")
    result = asyncio.run(kernel.run_with_options(task, mode="keyword"))

    assert result.status == TaskStatus.completed
    assert call_count.get("low") == 1
    assert checkpoint_store.get_latest_for_task("task-legacy") is None


def test_enabled_keyword_low_risk_writes_multiple_checkpoints(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "graph_runtime_enabled", True)
    checkpoint_store = SQLiteGraphCheckpointStore(db_path=str(tmp_path / "graph.sqlite"))
    call_count: dict[str, int] = {}
    kernel = _build_kernel(checkpoint_store, call_count)

    task = TaskRun(task_id="task-graph", query="今天GMV多少")
    result = asyncio.run(kernel.run_with_options(task, mode="keyword"))

    assert result.status == TaskStatus.completed
    assert result.result is not None
    assert result.result["success"] is True
    assert result.result["graph_runtime"] is True
    assert call_count.get("low") == 1

    latest = checkpoint_store.get_latest_for_task("task-graph")
    assert latest is not None
    assert latest["status"] == "completed"
    assert latest["graph_state"]["response"]["success"] is True


def test_checkpoint_id_unique_per_stage(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "graph_runtime_enabled", True)
    checkpoint_store = SQLiteGraphCheckpointStore(db_path=str(tmp_path / "graph.sqlite"))
    kernel = _build_kernel(checkpoint_store)

    task = TaskRun(task_id="task-unique", query="今天GMV多少")
    asyncio.run(kernel.run_with_options(task, mode="keyword"))

    import sqlite3
    with sqlite3.connect(str(tmp_path / "graph.sqlite")) as conn:
        rows = conn.execute("SELECT checkpoint_id, current_node FROM graph_run_states WHERE task_id = ?", ("task-unique",)).fetchall()

    checkpoint_ids = [row[0] for row in rows]
    stages = {row[1] for row in rows}
    assert len(checkpoint_ids) >= 5
    assert len(checkpoint_ids) == len(set(checkpoint_ids))
    assert {"assemble_context", "plan", "execute", "verify", "respond"}.issubset(stages)


def test_high_risk_returns_requires_approval_without_graph_interrupt(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "graph_runtime_enabled", True)
    checkpoint_store = SQLiteGraphCheckpointStore(db_path=str(tmp_path / "graph.sqlite"))
    call_count: dict[str, int] = {}
    kernel = _build_kernel(checkpoint_store, call_count)

    task = TaskRun(task_id="task-danger", query="危险操作")
    result = asyncio.run(kernel.run_with_options(task, mode="keyword"))

    assert result.status == TaskStatus.failed
    assert result.result is not None
    assert result.result["requires_approval"] is True
    assert result.result["graph_interrupt"] is False
    assert result.result["not_supported"] is True
    assert call_count.get("dangerous", 0) == 0

    latest = checkpoint_store.get_latest_for_task("task-danger")
    assert latest is not None
    assert latest["status"] == "blocked"
    assert latest["pending_interrupt"] is None
    assert latest["approval_id"] is None


def test_reset_runtime_for_test_rebuilds_graph_adapter(monkeypatch, tmp_path):
    from app.core.config import settings
    import app.main as main

    monkeypatch.setattr(settings, "graph_runtime_enabled", True)
    monkeypatch.setattr(settings, "storage_backend", "sqlite")
    monkeypatch.setattr(settings, "database_url", "")
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))

    main.reset_runtime_for_test()
    first = main.get_kernel()
    first_adapter = getattr(first, "_graph_runtime_adapter", None)

    main.reset_runtime_for_test()
    second = main.get_kernel()
    second_adapter = getattr(second, "_graph_runtime_adapter", None)

    assert first_adapter is not None
    assert second_adapter is not None
    assert second_adapter is not first_adapter
    main.reset_runtime_for_test()
