from __future__ import annotations

import os

from app.agent.multi_agent.coordinator import CoordinatorAgent
from app.agent.multi_agent.executor import ExecutorAgent
from app.agent.multi_agent.orchestrator import MultiAgentOrchestrator
from app.agent.multi_agent.reviewer import ReviewerAgent
from app.agent.nodes.planner import ROUTING_RULE_SOURCE, KeywordPlanner
from app.harness.gateway.tool_gateway import ToolGateway
from app.harness.policy.engine import PolicyEngine
from app.harness.trace.recorder import TraceRecorder
from app.services.multitool_pipeline import MultiToolPipeline

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "db", "ops_demo.sqlite")


def _ensure_db():
    if not os.path.exists(DB_PATH):
        from scripts.init_demo_db import init_db
        init_db()


_ensure_db()


def _build_test_gateway() -> ToolGateway:
    gateway = ToolGateway()
    from app.main import _register_tools, _register_mcp_tools
    _register_tools(gateway)
    _register_mcp_tools(gateway)
    return gateway


def _build_test_orchestrator() -> MultiAgentOrchestrator:
    gateway = _build_test_gateway()
    recorder = TraceRecorder()
    engine = PolicyEngine()
    mt_pipeline = MultiToolPipeline(gateway, policy_engine=engine, trace_recorder=recorder)
    executor = ExecutorAgent(
        nl2sql_pipeline=None,
        multitool_pipeline=mt_pipeline,
        tool_gateway=gateway,
        policy_engine=engine,
    )
    return MultiAgentOrchestrator(executor, trace_recorder=recorder)


# ---------- Reviewer: auto 失败分支回归 ----------


def test_reviewer_auto_failure_with_answer_rejected():
    """回归：auto 模式失败但带 answer 时，不得被误判为“执行成功”"""
    reviewer = ReviewerAgent()
    exec_result = {"success": False, "answer": "未匹配关键词"}
    review_result, decision = reviewer.review(exec_result, "auto")
    assert review_result["approved"] is False
    assert decision.action == "reject"
    assert decision.metadata["approved"] is False


def test_reviewer_auto_failure_no_fallback_suggested():
    """auto 内部已做过 nl2sql→multitool→keyword 级联，失败后不应再建议 fallback"""
    reviewer = ReviewerAgent()
    exec_result = {"success": False, "answer": "工具调用失败"}
    review_result, _ = reviewer.review(exec_result, "auto")
    assert review_result["suggested_fallback_mode"] is None
    assert "穷尽" in review_result["reason"]


def test_reviewer_auto_success_still_approved():
    reviewer = ReviewerAgent()
    exec_result = {"success": True, "answer": "GMV 为 12345"}
    review_result, decision = reviewer.review(exec_result, "auto")
    assert review_result["approved"] is True
    assert decision.action == "approve"


def test_reviewer_non_auto_failure_still_suggests_fallback():
    reviewer = ReviewerAgent()
    exec_result = {"success": False, "answer": ""}
    review_result, decision = reviewer.review(exec_result, "nl2sql")
    assert review_result["approved"] is False
    assert review_result["suggested_fallback_mode"] == "multitool"
    assert decision.action == "suggest_fallback"


def test_reviewer_success_without_answer_rejected():
    reviewer = ReviewerAgent()
    exec_result = {"success": True, "answer": ""}
    review_result, decision = reviewer.review(exec_result, "nl2sql")
    assert review_result["approved"] is False
    assert decision.action == "reject"
    assert review_result["suggested_fallback_mode"] == "keyword"


def test_reviewer_policy_blocked_rejected_without_fallback():
    """策略拦截/待审批的结果换模式也绕不开审批，Reviewer 不应建议 fallback"""
    reviewer = ReviewerAgent()
    exec_result = {
        "success": False,
        "answer": "工具调用被策略拦截: 高风险工具需要人工审批",
        "blocked": True,
        "error_type": "policy_blocked",
    }
    review_result, decision = reviewer.review(exec_result, "keyword")
    assert review_result["approved"] is False
    assert review_result["suggested_fallback_mode"] is None
    assert decision.action == "reject"


def test_orchestrator_auto_failure_final_state_consistent():
    """auto 全链路失败时，任务最终 success 与 review 结论一致，不产生行为矛盾"""
    orchestrator = _build_test_orchestrator()
    result = orchestrator.run("帮我看看运营情况", task_id="test-auto-fail-445")
    assert result.success is False
    assert result.review_result["approved"] is False
    assert result.review_result.get("suggested_fallback_mode") is None
    reviewer_decisions = [d for d in result.decisions if d.role == "reviewer"]
    assert reviewer_decisions
    assert reviewer_decisions[-1].action == "reject"


# ---------- 路由规则单一来源 ----------


def test_planner_rules_derive_from_rule_source():
    """KeywordPlanner 词表来自统一路由规则源（带 tool_name 的规则）"""
    source_keywords = {
        kw
        for rule in ROUTING_RULE_SOURCE
        if rule.get("tool_name")
        for kw in rule["keywords"]
    }
    planner_keywords = {
        kw
        for rule in KeywordPlanner.ROUTING_RULES
        for kw in rule["keywords"]
    }
    assert source_keywords <= planner_keywords


def test_coordinator_rules_derive_from_rule_source():
    """Coordinator 词表来自统一路由规则源"""
    source_keywords = {kw for rule in ROUTING_RULE_SOURCE for kw in rule["keywords"]}
    coordinator_keywords = {
        kw
        for rule in CoordinatorAgent.ROUTING_RULES
        for kw in rule["keywords"]
    }
    assert source_keywords <= coordinator_keywords


def test_refund_keyword_consistent_between_consumers():
    """“退款”类词条两个消费方口径一致：Coordinator 路由 nl2sql，Planner 映射 get_refund_rate"""
    decision = CoordinatorAgent().decide("退款率是多少")
    assert decision.metadata["selected_mode"] == "nl2sql"
    plan = KeywordPlanner().plan("退款率是多少")
    assert plan["tool_name"] == "get_refund_rate"


def test_refund_rule_keyword_still_routes_multitool():
    decision = CoordinatorAgent().decide("退款规则是什么")
    assert decision.action == "compound_tool_query"
    assert decision.metadata["selected_mode"] == "multitool"


def test_date_keyword_consistent_between_consumers():
    decision = CoordinatorAgent().decide("今天几号")
    assert decision.metadata["selected_mode"] == "keyword"
    plan = KeywordPlanner().plan("今天几号")
    assert plan["tool_name"] == "date_lookup"


# ---------- Coordinator confidence 可解释规则 ----------


def test_coordinator_confidence_not_bare_constant():
    """confidence 按命中词数/词长加权：多词长词命中应高于单个短词命中"""
    coord = CoordinatorAgent()
    single = coord.decide("销售额")
    multi = coord.decide("GMV环比增长多少")
    assert 0.5 < single.confidence <= 0.95
    assert 0.5 < multi.confidence <= 0.95
    assert multi.confidence > single.confidence


def test_coordinator_matched_keywords_in_metadata():
    decision = CoordinatorAgent().decide("GMV环比增长多少")
    matched = decision.metadata.get("matched_keywords")
    assert matched
    assert "GMV环比" in matched


def test_coordinator_unmatched_confidence_floor():
    decision = CoordinatorAgent().decide("今天天气怎么样")
    assert decision.action == "unknown"
    assert decision.confidence == 0.5
    assert decision.metadata["selected_mode"] == "auto"
