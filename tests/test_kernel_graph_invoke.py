from __future__ import annotations

import asyncio
import os
import sys
import tempfile

from app.agent.graph.kernel import AgentKernel
from app.agent.nodes.planner import KeywordPlanner
from app.harness.context.assembler import ContextAssembler
from app.harness.gateway.tool_gateway import ToolGateway
from app.harness.hooks.pipeline import HookPipeline
from app.harness.policy.engine import PolicyEngine
from app.harness.trace.recorder import TraceRecorder
from app.models.schemas import RiskLevel, TaskRun, TaskStatus, ToolSpec


class _CountingGraph:
    """包装编译后的图，统计 invoke 次数"""

    def __init__(self, inner):
        self._inner = inner
        self.invoke_count = 0

    def invoke(self, *args, **kwargs):
        self.invoke_count += 1
        return self._inner.invoke(*args, **kwargs)


def _build_gateway() -> ToolGateway:
    gateway = ToolGateway()
    gateway.register(
        ToolSpec(tool_name="get_today_gmv", description="获取今日 GMV", risk_level=RiskLevel.low, source="local", is_local=True),
        lambda: {"gmv": 12345.67, "date": "2026-07-26"},
    )
    return gateway


def _make_kernel(
    gateway: ToolGateway | None = None,
    approval_store=None,
    planner: KeywordPlanner | None = None,
) -> tuple[AgentKernel, TraceRecorder]:
    recorder = TraceRecorder()
    kernel = AgentKernel(
        context_assembler=ContextAssembler(),
        tool_gateway=gateway or _build_gateway(),
        hook_pipeline=HookPipeline(),
        policy_engine=PolicyEngine(),
        trace_recorder=recorder,
        planner=planner,
        approval_store=approval_store,
    )
    return kernel, recorder


def _make_danger_planner() -> KeywordPlanner:
    planner = KeywordPlanner()
    planner.ROUTING_RULES = [
        {
            "keywords": ["危险图测试"],
            "tool_name": "dangerous_tool",
            "label": "危险图测试",
        },
    ] + list(KeywordPlanner.ROUTING_RULES)
    return planner


def test_run_invokes_compiled_graph():
    kernel, recorder = _make_kernel()
    kernel.build_graph()
    counting = _CountingGraph(kernel._graph)
    kernel._graph = counting

    task = TaskRun(task_id="test-graph-invoke-1", query="今天GMV多少")
    result = asyncio.run(kernel.run(task))

    assert counting.invoke_count == 1
    assert result.status == TaskStatus.completed
    assert result.result["success"] is True
    assert result.result["tool_called"] == "get_today_gmv"

    started = recorder.get_events(task_id="test-graph-invoke-1", event_type="task_started")
    assert len(started) == 1
    assert started[0].detail["engine"] == "langgraph"


def test_run_lazily_builds_graph():
    kernel, _ = _make_kernel()
    assert kernel._graph is None

    task = TaskRun(task_id="test-graph-lazy-1", query="今天GMV多少")
    result = asyncio.run(kernel.run(task))

    assert kernel._graph is not None
    assert result.status == TaskStatus.completed
    summary = kernel.get_graph_summary()
    assert summary["implemented"] is True


def test_graph_summary_contains_conditional_edges():
    kernel, _ = _make_kernel()
    kernel.build_graph()
    summary = kernel.get_graph_summary()
    assert "execute → verify" in summary["edges"]
    assert "execute → respond" in summary["edges"]
    assert "verify → respond" in summary["edges"]


def test_graph_result_equivalent_to_sequential():
    kernel_a, recorder_a = _make_kernel()
    task_a = TaskRun(task_id="test-graph-eq-a", query="今天GMV多少")
    result_a = asyncio.run(kernel_a.run(task_a))

    started_a = recorder_a.get_events(task_id="test-graph-eq-a", event_type="task_started")
    assert started_a[0].detail["engine"] == "langgraph"

    kernel_b, _ = _make_kernel()
    task_b = TaskRun(task_id="test-graph-eq-b", query="今天GMV多少")
    result_b = kernel_b._run_sequential(task_b)

    assert result_a.result == result_b

    kernel_c, recorder_c = _make_kernel()
    kernel_c.build_graph()
    kernel_c._graph = None
    kernel_c._graph_error = "simulated unavailable"

    original_build = kernel_c.build_graph
    kernel_c.build_graph = lambda: None
    try:
        task_c = TaskRun(task_id="test-graph-eq-c", query="今天GMV多少")
        result_c = asyncio.run(kernel_c.run(task_c))
    finally:
        kernel_c.build_graph = original_build

    assert result_a.result == result_c.result
    assert result_a.status == result_c.status == TaskStatus.completed

    types_a = [e.event_type for e in recorder_a.get_events(task_id="test-graph-eq-a")]
    types_c = [e.event_type for e in recorder_c.get_events(task_id="test-graph-eq-c")]
    assert types_a == types_c
    assert types_a == ["task_started", "context_assembled", "plan_created", "tool_called", "task_completed"]


def test_graph_unmatched_query_equivalent():
    kernel, _ = _make_kernel()
    task = TaskRun(task_id="test-graph-unmatched", query="今天天气怎么样")
    result = asyncio.run(kernel.run(task))

    assert result.status == TaskStatus.completed
    assert result.result["success"] is False
    assert result.result["tool_called"] is None
    assert "无法识别" in result.result["answer"]


def test_waiting_approval_conditional_edge_skips_verify():
    from app.storage.approval_store import SQLiteApprovalStore

    gateway = _build_gateway()
    call_count = 0

    def _never_called():
        nonlocal call_count
        call_count += 1
        return {"result": "never"}

    gateway.register(
        ToolSpec(tool_name="dangerous_tool", description="危险工具", risk_level=RiskLevel.high, source="local", is_local=True),
        _never_called,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_approval.sqlite")
        approval_store = SQLiteApprovalStore(db_path=db_path)
        kernel, recorder = _make_kernel(gateway=gateway, approval_store=approval_store, planner=_make_danger_planner())

        verify_calls = 0
        original_verify = kernel._verify

        def _counting_verify(tool_result):
            nonlocal verify_calls
            verify_calls += 1
            return original_verify(tool_result)

        kernel._verify = _counting_verify

        task = TaskRun(task_id="test-graph-approval-1", query="危险图测试")
        result = asyncio.run(kernel.run(task))

        assert call_count == 0
        assert verify_calls == 0
        assert result.status == TaskStatus.waiting_approval
        assert result.result["requires_approval"] is True
        assert result.result["approval_id"].startswith("apr_")
        assert result.result["blocked"] is True
        assert result.result["success"] is False

        event_types = [e.event_type for e in recorder.get_events(task_id="test-graph-approval-1")]
        assert "approval_requested" in event_types
        assert "task_completed" not in event_types
        started = recorder.get_events(task_id="test-graph-approval-1", event_type="task_started")
        assert started[0].detail["engine"] == "langgraph"


def test_verify_node_called_on_normal_path():
    kernel, _ = _make_kernel()

    verify_calls = 0
    original_verify = kernel._verify

    def _counting_verify(tool_result):
        nonlocal verify_calls
        verify_calls += 1
        return original_verify(tool_result)

    kernel._verify = _counting_verify

    task = TaskRun(task_id="test-graph-verify-1", query="今天GMV多少")
    result = asyncio.run(kernel.run(task))

    assert verify_calls == 1
    assert result.status == TaskStatus.completed


def test_langgraph_import_failure_falls_back_to_sequential(monkeypatch):
    kernel, recorder = _make_kernel()
    monkeypatch.setitem(sys.modules, "langgraph", None)
    monkeypatch.setitem(sys.modules, "langgraph.graph", None)

    task = TaskRun(task_id="test-graph-fallback-1", query="今天GMV多少")
    result = asyncio.run(kernel.run(task))

    assert kernel._graph is None
    assert result.status == TaskStatus.completed
    assert result.result["success"] is True
    assert result.result["tool_called"] == "get_today_gmv"

    started = recorder.get_events(task_id="test-graph-fallback-1", event_type="task_started")
    assert started[0].detail["engine"] == "sequential"

    summary = kernel.get_graph_summary()
    assert summary["implemented"] is False
    assert summary["error"]


def test_fallback_waiting_approval_behavior_unchanged(monkeypatch):
    from app.storage.approval_store import SQLiteApprovalStore

    gateway = _build_gateway()
    gateway.register(
        ToolSpec(tool_name="dangerous_tool", description="危险工具", risk_level=RiskLevel.high, source="local", is_local=True),
        lambda: {"result": "never"},
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_approval.sqlite")
        approval_store = SQLiteApprovalStore(db_path=db_path)
        kernel, recorder = _make_kernel(gateway=gateway, approval_store=approval_store, planner=_make_danger_planner())

        monkeypatch.setitem(sys.modules, "langgraph", None)
        monkeypatch.setitem(sys.modules, "langgraph.graph", None)

        task = TaskRun(task_id="test-graph-fallback-2", query="危险图测试")
        result = asyncio.run(kernel.run(task))

        assert result.status == TaskStatus.waiting_approval
        assert result.result["requires_approval"] is True
        assert result.result["approval_id"].startswith("apr_")

        started = recorder.get_events(task_id="test-graph-fallback-2", event_type="task_started")
        assert started[0].detail["engine"] == "sequential"
