from __future__ import annotations

import pytest

from app.agent.graph.kernel import AgentKernel
from app.harness.context.assembler import ContextAssembler
from app.harness.gateway.tool_gateway import ToolGateway
from app.harness.hooks.pipeline import HookPipeline
from app.harness.policy.engine import PolicyEngine
from app.harness.trace.recorder import TraceRecorder


def _make_kernel() -> AgentKernel:
    assembler = ContextAssembler()
    gateway = ToolGateway()
    pipeline = HookPipeline()
    recorder = TraceRecorder()
    engine = PolicyEngine()
    return AgentKernel(
        context_assembler=assembler,
        tool_gateway=gateway,
        hook_pipeline=pipeline,
        policy_engine=engine,
        trace_recorder=recorder,
    )


class TestLangGraphKernelV11:

    def test_build_graph_summary_implemented(self):
        kernel = _make_kernel()
        kernel.build_graph()
        summary = kernel.get_graph_summary()
        assert summary["implemented"] is True

    def test_graph_nodes(self):
        kernel = _make_kernel()
        kernel.build_graph()
        summary = kernel.get_graph_summary()
        nodes = summary["nodes"]
        assert "assemble_context" in nodes
        assert "plan" in nodes
        assert "execute" in nodes
        assert "verify" in nodes
        assert "respond" in nodes

    def test_graph_edges(self):
        kernel = _make_kernel()
        kernel.build_graph()
        summary = kernel.get_graph_summary()
        edges = summary["edges"]
        assert len(edges) > 0

    def test_build_graph_before_call(self):
        kernel = _make_kernel()
        summary = kernel.get_graph_summary()
        assert summary["implemented"] is False

    @pytest.mark.asyncio
    async def test_keyword_api_unchanged(self):
        from app.models.schemas import TaskRun
        kernel = _make_kernel()
        kernel.build_graph()
        task = TaskRun(task_id="test_v11_keyword", query="今天GMV多少")
        result = await kernel.run(task)
        assert result.status in ("completed", "failed")
