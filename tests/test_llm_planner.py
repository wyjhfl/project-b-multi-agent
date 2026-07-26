from __future__ import annotations

import asyncio
import json
import os
import tempfile

import pytest

from app.agent.graph.kernel import AgentKernel
from app.agent.multi_agent.coordinator import CoordinatorAgent
from app.agent.nodes.llm_planner import (
    LLMToolPlanner,
    build_tools_from_gateway,
    validate_tool_arguments,
)
from app.agent.nl2sql.provider import FakeLLMProvider, LLMGenerateMetadata
from app.core.config import settings
from app.harness.context.assembler import ContextAssembler
from app.harness.gateway.tool_gateway import ToolGateway
from app.harness.hooks.pipeline import HookPipeline
from app.harness.policy.engine import PolicyEngine
from app.harness.trace.recorder import TraceRecorder
from app.models.schemas import RiskLevel, TaskRun, TaskStatus, ToolSpec


class _StubProvider:
    """按预设返回 tool_calls 或抛异常的桩 provider（模拟真实 LLM 的各类返回形态）"""

    def __init__(self, tool_calls: list[dict] | None = None, error: Exception | None = None):
        self.calls = 0
        self._tool_calls = tool_calls
        self._error = error

    def generate_with_metadata(self, prompt, *, tools=None, tool_choice=None):
        self.calls += 1
        if self._error is not None:
            raise self._error
        return LLMGenerateMetadata(
            content="" if self._tool_calls else "文本回复",
            provider="stub",
            model="stub-model",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost=0.0,
            request_id="stub-request",
            latency_ms=0.1,
            error_type=None,
            tool_calls=self._tool_calls,
        )


def _tool_call(name: str, arguments) -> list[dict]:
    if not isinstance(arguments, str):
        arguments = json.dumps(arguments, ensure_ascii=False)
    return [{"id": "call-1", "type": "function", "function": {"name": name, "arguments": arguments}}]


def _build_gateway() -> ToolGateway:
    gateway = ToolGateway()
    gateway.register(
        ToolSpec(
            tool_name="get_today_gmv",
            description="获取今日 GMV",
            input_schema={"type": "object", "properties": {}},
            risk_level=RiskLevel.low,
            source="local",
            is_local=True,
        ),
        lambda: {"gmv": 12345.67, "date": "2026-07-26"},
    )
    gateway.register(
        ToolSpec(
            tool_name="get_top_products",
            description="获取 Top 商品",
            input_schema={"type": "object", "properties": {"limit": {"type": "integer", "default": 5}}},
            risk_level=RiskLevel.low,
            source="local",
            is_local=True,
        ),
        lambda limit=5: {"top_products": [], "count": limit},
    )
    return gateway


def _register_high_risk_tool(gateway: ToolGateway, counter: dict) -> None:
    def _simulate(order_id: str = "", amount: float = 0.0):
        counter["calls"] += 1
        return {"simulated": True, "order_id": order_id, "amount": amount}

    gateway.register(
        ToolSpec(
            tool_name="simulate_refund_order",
            description="模拟创建退款单",
            input_schema={"type": "object", "properties": {"order_id": {"type": "string"}, "amount": {"type": "number"}}},
            risk_level=RiskLevel.high,
            permission_scope="write",
            source="local",
            is_local=True,
        ),
        _simulate,
    )


def _make_kernel(gateway: ToolGateway | None = None, approval_store=None) -> tuple[AgentKernel, TraceRecorder]:
    recorder = TraceRecorder()
    kernel = AgentKernel(
        context_assembler=ContextAssembler(),
        tool_gateway=gateway or _build_gateway(),
        hook_pipeline=HookPipeline(),
        policy_engine=PolicyEngine(),
        trace_recorder=recorder,
        approval_store=approval_store,
    )
    return kernel, recorder


# ---------- tools 列表构建与参数校验 ----------


def test_build_tools_from_gateway_contains_schema_and_risk_level():
    tools = build_tools_from_gateway(_build_gateway())
    assert [t["function"]["name"] for t in tools] == ["get_today_gmv", "get_top_products"]
    gmv = tools[0]["function"]
    assert "risk_level=low" in gmv["description"]
    assert gmv["parameters"] == {"type": "object", "properties": {}}
    top = tools[1]["function"]
    assert top["parameters"]["properties"]["limit"]["type"] == "integer"


def test_validate_arguments_filters_undeclared_and_checks_type():
    schema = {"type": "object", "properties": {"limit": {"type": "integer"}}}
    cleaned, ignored = validate_tool_arguments(schema, {"limit": 3, "sql": "SELECT 1"})
    assert cleaned == {"limit": 3}
    assert ignored == ["sql"]

    with pytest.raises(ValueError):
        validate_tool_arguments(schema, {"limit": "abc"})
    # bool 是 int 子类，不应通过 integer 校验
    with pytest.raises(ValueError):
        validate_tool_arguments(schema, {"limit": True})


def test_validate_arguments_required_missing_rejected():
    schema = {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}
    with pytest.raises(ValueError, match="必填"):
        validate_tool_arguments(schema, {})


# ---------- LLM planner：fake provider 命中与降级链 ----------


def test_llm_planner_selects_tool_with_fake_provider():
    planner = LLMToolPlanner(_build_gateway(), provider=FakeLLMProvider())
    plan = planner.plan("今天GMV多少")

    assert plan["matched"] is True
    assert plan["tool_name"] == "get_today_gmv"
    assert plan["planner"] == "llm"
    assert plan["provider"] == "fake"
    assert plan["model"] == "fake-offline"
    # fake provider 夹带的 sql 参数未在 schema 声明，应被过滤而非进入 gateway
    assert plan["arguments"] == {}
    assert "sql" in plan["ignored_arguments"]
    assert "fallback_reason" not in plan


def test_llm_planner_fallback_on_provider_error():
    planner = LLMToolPlanner(_build_gateway(), provider=_StubProvider(error=RuntimeError("boom")))
    plan = planner.plan("今天GMV多少")

    assert plan["planner"] == "keyword"
    assert plan["fallback_reason"].startswith("provider_error")
    assert plan["tool_name"] == "get_today_gmv"
    assert plan["matched"] is True


def test_llm_planner_fallback_on_no_tool_call():
    planner = LLMToolPlanner(_build_gateway(), provider=_StubProvider(tool_calls=None))
    plan = planner.plan("今天GMV多少")

    assert plan["fallback_reason"].startswith("no_tool_call")
    assert plan["tool_name"] == "get_today_gmv"


def test_llm_planner_fake_no_match_falls_back_to_keyword_rules():
    """fake provider 未命中关键词时不返回 tool_call，降级后仍由关键词规则接住"""
    planner = LLMToolPlanner(_build_gateway(), provider=FakeLLMProvider())
    plan = planner.plan("今天几号")

    assert plan["planner"] == "keyword"
    assert plan["fallback_reason"].startswith("no_tool_call")
    assert plan["tool_name"] == "date_lookup"


def test_llm_planner_fallback_on_unknown_tool():
    planner = LLMToolPlanner(_build_gateway(), provider=_StubProvider(tool_calls=_tool_call("nonexistent_tool", {})))
    plan = planner.plan("今天GMV多少")

    assert plan["fallback_reason"].startswith("unknown_tool")
    assert plan["tool_name"] == "get_today_gmv"


def test_llm_planner_fallback_on_malformed_arguments_json():
    planner = LLMToolPlanner(_build_gateway(), provider=_StubProvider(tool_calls=_tool_call("get_top_products", "{not json")))
    plan = planner.plan("Top商品有哪些")

    assert plan["fallback_reason"].startswith("invalid_arguments")
    assert plan["planner"] == "keyword"
    assert plan["tool_name"] == "get_top_products"


def test_llm_planner_fallback_on_argument_type_mismatch():
    planner = LLMToolPlanner(_build_gateway(), provider=_StubProvider(tool_calls=_tool_call("get_top_products", {"limit": "abc"})))
    plan = planner.plan("Top商品有哪些")

    assert plan["fallback_reason"].startswith("invalid_arguments")
    assert "arguments" not in plan


def test_llm_planner_fallback_on_missing_required_argument():
    gateway = _build_gateway()
    gateway.register(
        ToolSpec(
            tool_name="echo_name",
            description="回显名称",
            input_schema={"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
            risk_level=RiskLevel.low,
            source="local",
            is_local=True,
        ),
        lambda name: {"name": name},
    )
    planner = LLMToolPlanner(gateway, provider=_StubProvider(tool_calls=_tool_call("echo_name", {})))
    plan = planner.plan("今天GMV多少")

    assert plan["fallback_reason"].startswith("invalid_arguments")


def test_llm_planner_empty_gateway_skips_provider_call():
    provider = _StubProvider(error=RuntimeError("不应被调用"))
    planner = LLMToolPlanner(ToolGateway(), provider=provider)
    plan = planner.plan("今天GMV多少")

    assert provider.calls == 0
    assert plan["fallback_reason"].startswith("no_tools_available")
    assert plan["tool_name"] == "get_today_gmv"


def test_llm_planner_valid_arguments_passed_through():
    planner = LLMToolPlanner(_build_gateway(), provider=_StubProvider(tool_calls=_tool_call("get_top_products", {"limit": 3})))
    plan = planner.plan("Top商品有哪些")

    assert plan["planner"] == "llm"
    assert plan["arguments"] == {"limit": 3}
    assert "ignored_arguments" not in plan


# ---------- kernel 按 planner_mode 选择规划器 ----------


def test_kernel_default_planner_mode_uses_keyword_planner():
    kernel, recorder = _make_kernel()
    assert kernel._active_planner() is kernel._planner

    task = TaskRun(task_id="test-llm-planner-default", query="今天GMV多少")
    result = asyncio.run(kernel.run(task))

    assert result.status == TaskStatus.completed
    assert result.result["tool_called"] == "get_today_gmv"
    plan_events = recorder.get_events(task_id="test-llm-planner-default", event_type="plan_created")
    assert "planner" not in plan_events[0].detail


def test_kernel_llm_mode_end_to_end_with_fake_provider(monkeypatch):
    monkeypatch.setattr(settings, "planner_mode", "llm")
    monkeypatch.setattr(settings, "llm_provider", "fake")
    kernel, recorder = _make_kernel()

    task = TaskRun(task_id="test-llm-planner-e2e", query="今天GMV多少")
    result = asyncio.run(kernel.run(task))

    assert result.status == TaskStatus.completed
    assert result.result["success"] is True
    assert result.result["tool_called"] == "get_today_gmv"

    plan_events = recorder.get_events(task_id="test-llm-planner-e2e", event_type="plan_created")
    assert plan_events[0].detail["planner"] == "llm"
    assert plan_events[0].detail["model"] == "fake-offline"

    tool_events = recorder.get_events(task_id="test-llm-planner-e2e", event_type="tool_called")
    assert tool_events[0].detail["success"] is True


def test_kernel_llm_mode_fallback_reason_recorded_in_trace(monkeypatch):
    monkeypatch.setattr(settings, "planner_mode", "llm")
    kernel, recorder = _make_kernel()
    kernel._llm_planner = LLMToolPlanner(
        kernel._tool_gateway,
        provider=_StubProvider(error=RuntimeError("boom")),
        fallback_planner=kernel._planner,
    )

    task = TaskRun(task_id="test-llm-planner-trace-fb", query="今天GMV多少")
    result = asyncio.run(kernel.run(task))

    assert result.status == TaskStatus.completed
    assert result.result["tool_called"] == "get_today_gmv"
    plan_events = recorder.get_events(task_id="test-llm-planner-trace-fb", event_type="plan_created")
    assert plan_events[0].detail["planner"] == "keyword"
    assert plan_events[0].detail["fallback_reason"].startswith("provider_error")


# ---------- 治理层：高风险工具经 LLM planner 选中仍走审批 ----------


def test_high_risk_tool_via_llm_planner_still_requires_approval(monkeypatch):
    from app.storage.approval_store import SQLiteApprovalStore

    monkeypatch.setattr(settings, "planner_mode", "llm")
    gateway = _build_gateway()
    counter = {"calls": 0}
    _register_high_risk_tool(gateway, counter)

    with tempfile.TemporaryDirectory() as tmpdir:
        approval_store = SQLiteApprovalStore(db_path=os.path.join(tmpdir, "test_approval.sqlite"))
        kernel, recorder = _make_kernel(gateway=gateway, approval_store=approval_store)
        kernel._llm_planner = LLMToolPlanner(
            gateway,
            provider=_StubProvider(tool_calls=_tool_call("simulate_refund_order", {"order_id": "ORD-1001", "amount": 99.0})),
            fallback_planner=kernel._planner,
        )

        task = TaskRun(task_id="test-llm-planner-approval", query="帮我执行高风险演练")
        result = asyncio.run(kernel.run(task))

        # 治理层不被绕过：工具零调用、任务挂起等待审批
        assert counter["calls"] == 0
        assert result.status == TaskStatus.waiting_approval
        assert result.result["requires_approval"] is True
        approval_id = result.result["approval_id"]
        assert approval_id.startswith("apr_")

        # 审批单 payload 保留 LLM 校验后的参数与 planner 标记，供 resume 使用
        approval = approval_store.get_approval(approval_id)
        assert approval["payload"]["arguments"] == {"order_id": "ORD-1001", "amount": 99.0}
        assert approval["payload"]["plan_result"]["planner"] == "llm"

        event_types = [e.event_type for e in recorder.get_events(task_id="test-llm-planner-approval")]
        assert "approval_requested" in event_types
        assert "task_completed" not in event_types


# ---------- Coordinator LLM 路由决策 ----------


def test_coordinator_llm_disabled_by_default_never_calls_provider():
    provider = _StubProvider(error=RuntimeError("不应被调用"))
    decision = CoordinatorAgent(provider=provider).decide("今天GMV多少")

    assert provider.calls == 0
    assert decision.metadata["selected_mode"] == "nl2sql"
    assert decision.metadata["decision_source"] == "rule"
    assert decision.action == "data_query"


def test_coordinator_llm_decision_with_fake_provider(monkeypatch):
    monkeypatch.setattr(settings, "coordinator_llm_enabled", True)
    decision = CoordinatorAgent(provider=FakeLLMProvider()).decide("今天GMV多少")

    assert decision.metadata["decision_source"] == "llm"
    assert decision.metadata["selected_mode"] == "nl2sql"
    assert decision.metadata["confidence_basis"] == "llm_rule_agree"
    assert decision.metadata["model"] == "fake-offline"
    assert decision.confidence == 0.9
    assert decision.action == "data_query"


def test_coordinator_llm_disagrees_with_rule_lower_confidence(monkeypatch):
    monkeypatch.setattr(settings, "coordinator_llm_enabled", True)
    provider = _StubProvider(tool_calls=_tool_call("route_to_multitool", {}))
    decision = CoordinatorAgent(provider=provider).decide("今天GMV多少")

    assert decision.metadata["decision_source"] == "llm"
    assert decision.metadata["selected_mode"] == "multitool"
    assert decision.metadata["confidence_basis"] == "llm_only"
    assert decision.confidence == 0.7
    assert decision.action == "llm_route"


def test_coordinator_llm_provider_error_falls_back_to_rules(monkeypatch):
    monkeypatch.setattr(settings, "coordinator_llm_enabled", True)
    provider = _StubProvider(error=RuntimeError("boom"))
    decision = CoordinatorAgent(provider=provider).decide("今天GMV多少")

    assert decision.metadata["decision_source"] == "rule"
    assert decision.metadata["selected_mode"] == "nl2sql"
    assert decision.metadata["llm_fallback_reason"].startswith("provider_error")


def test_coordinator_llm_no_tool_call_falls_back_to_rules(monkeypatch):
    monkeypatch.setattr(settings, "coordinator_llm_enabled", True)
    decision = CoordinatorAgent(provider=FakeLLMProvider()).decide("今天几号")

    assert decision.metadata["decision_source"] == "rule"
    assert decision.metadata["selected_mode"] == "keyword"
    assert decision.metadata["llm_fallback_reason"].startswith("no_tool_call")


def test_coordinator_llm_invalid_mode_falls_back_to_rules(monkeypatch):
    monkeypatch.setattr(settings, "coordinator_llm_enabled", True)
    provider = _StubProvider(tool_calls=_tool_call("route_to_banana", {}))
    decision = CoordinatorAgent(provider=provider).decide("今天GMV多少")

    assert decision.metadata["decision_source"] == "rule"
    assert decision.metadata["llm_fallback_reason"].startswith("invalid_mode")
    assert decision.metadata["selected_mode"] == "nl2sql"


def test_coordinator_rule_unmatched_metadata_unchanged_shape():
    decision = CoordinatorAgent().decide("今天天气怎么样")

    assert decision.action == "unknown"
    assert decision.confidence == 0.5
    assert decision.metadata["selected_mode"] == "auto"
    assert decision.metadata["decision_source"] == "rule"
    assert decision.metadata["confidence_basis"] == "no_rule_matched"
