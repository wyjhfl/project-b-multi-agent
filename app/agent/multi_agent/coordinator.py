from __future__ import annotations

from typing import Any

from app.agent.multi_agent.types import AgentDecision
from app.agent.nodes.planner import build_coordinator_rules, rule_enabled
from app.core.config import settings


class CoordinatorAgent:
    """协调者：为查询选择执行模式

    默认按关键词规则路由，词表来自 app.agent.nodes.planner.ROUTING_RULE_SOURCE，
    与 KeywordPlanner 共用单一规则源，避免双路由表漂移。

    settings.coordinator_llm_enabled 开启时优先用 LLM function calling 做
    结构化路由决策：候选模式各暴露为一个 route_to_<mode> 函数，LLM 选中哪个
    函数即路由到哪个模式；provider 异常 / 未返回 tool_call / 模式名不合法时
    降级关键词规则，metadata.llm_fallback_reason 记录原因。

    metadata.decision_source 标记决策来源（llm|rule），confidence 依据
    （metadata.confidence_basis）：
    - rule 路径（可解释规则，替代裸常数）：
      基础分 0.6：规则命中即具备基本路由依据；
      命中词数加分：每命中一个关键词 +0.1，最多 +0.2（多词命中更可信）；
      词长加分：最长命中词 >= 4 字符 +0.1，否则 +0.05（长词更具体，误命中概率更低）；
      上限 0.95；未命中任何规则固定 0.5（回退 auto，不确定性最高）。
    - llm 路径：结构化输出本身不含概率，置信依据取与关键词规则的交叉验证——
      与规则结论一致 0.9（llm_rule_agree），规则未命中或结论不一致 0.7（llm_only）。
    """

    ROUTING_RULES: list[dict[str, Any]] = build_coordinator_rules()

    CANDIDATE_MODES: tuple[str, ...] = ("nl2sql", "multitool", "keyword", "auto")

    ROUTE_MODE_DESCRIPTIONS: dict[str, str] = {
        "nl2sql": "数据指标类查询，走 NL2SQL 管线生成并执行 SQL",
        "multitool": "复合查询，需要多个工具串联（如指标环比 + 规则说明）",
        "keyword": "单一本地工具即可回答的简单查询（如日期）",
        "auto": "无法判断时的自动级联模式（nl2sql → multitool → keyword）",
    }

    def __init__(self, provider: Any | None = None) -> None:
        self._provider = provider

    def decide(self, query: str) -> AgentDecision:
        llm_fallback_reason: str | None = None
        if settings.coordinator_llm_enabled:
            decision, llm_fallback_reason = self._decide_with_llm(query)
            if decision is not None:
                return decision
        return self._decide_with_rules(query, llm_fallback_reason)

    def _decide_with_rules(self, query: str, llm_fallback_reason: str | None = None) -> AgentDecision:
        """关键词规则路由（默认路径，也是 LLM 决策失败时的降级路径）"""
        extra_metadata: dict[str, Any] = {}
        if llm_fallback_reason is not None:
            extra_metadata["llm_fallback_reason"] = llm_fallback_reason

        rule, matched = self._match_rule(query)
        if rule is not None:
            return AgentDecision(
                role="coordinator",
                action=rule["action"],
                reason=f"关键词 '{matched[0]}' 匹配规则，选择 {rule['selected_mode']} 模式",
                confidence=self._confidence(matched),
                metadata={
                    "selected_mode": rule["selected_mode"],
                    "matched_keywords": matched,
                    "decision_source": "rule",
                    "confidence_basis": "keyword_match_count_and_length",
                    **extra_metadata,
                },
            )

        return AgentDecision(
            role="coordinator",
            action="unknown",
            reason="未匹配任何路由规则，使用 auto 模式",
            confidence=0.5,
            metadata={
                "selected_mode": "auto",
                "decision_source": "rule",
                "confidence_basis": "no_rule_matched",
                **extra_metadata,
            },
        )

    def _decide_with_llm(self, query: str) -> tuple[AgentDecision | None, str | None]:
        """LLM function calling 结构化路由决策

        失败时返回 (None, 原因)，由 decide() 降级关键词规则；原因前缀标记触发点：
        provider_error / no_tool_call / invalid_mode。
        """
        tools = [
            {
                "type": "function",
                "function": {
                    "name": f"route_to_{mode}",
                    "description": self.ROUTE_MODE_DESCRIPTIONS[mode],
                    "parameters": {"type": "object", "properties": {"reason": {"type": "string"}}},
                },
            }
            for mode in self.CANDIDATE_MODES
        ]
        prompt = (
            "你是路由决策器。请调用 route_to_<mode> 中最合适的一个函数，"
            "为下面的查询选择执行模式。\n"
            f"查询: {query}"
        )

        try:
            provider = self._get_provider()
            metadata = provider.generate_with_metadata(prompt, tools=tools)
        except Exception as exc:
            return None, f"provider_error: {exc}"

        tool_calls = metadata.tool_calls or []
        if not tool_calls:
            return None, "no_tool_call: provider 未返回路由决策"

        function = tool_calls[0].get("function") if isinstance(tool_calls[0], dict) else None
        name = str((function or {}).get("name") or "")
        selected_mode = name[len("route_to_"):] if name.startswith("route_to_") else ""
        if selected_mode not in self.CANDIDATE_MODES:
            return None, f"invalid_mode: 无法识别的路由函数 '{name}'"

        rule, _ = self._match_rule(query)
        if rule is not None and rule["selected_mode"] == selected_mode:
            confidence, basis, action = 0.9, "llm_rule_agree", rule["action"]
        else:
            confidence, basis, action = 0.7, "llm_only", "llm_route"

        return (
            AgentDecision(
                role="coordinator",
                action=action,
                reason=f"LLM function calling 选择 {selected_mode} 模式",
                confidence=confidence,
                metadata={
                    "selected_mode": selected_mode,
                    "decision_source": "llm",
                    "confidence_basis": basis,
                    "provider": metadata.provider,
                    "model": metadata.model,
                },
            ),
            None,
        )

    def _match_rule(self, query: str) -> tuple[dict[str, Any] | None, list[str]]:
        """按顺序匹配首条命中的路由规则，返回 (规则, 命中关键词列表)"""
        for rule in self.ROUTING_RULES:
            if not rule_enabled(rule):
                continue
            matched = [kw for kw in rule["keywords"] if kw in query]
            if matched:
                return rule, matched
        return None, []

    def _get_provider(self) -> Any:
        if self._provider is None:
            from app.agent.nl2sql.provider import create_provider

            self._provider = create_provider()
        return self._provider

    @staticmethod
    def _confidence(matched: list[str]) -> float:
        """按命中词数与词长加权计算路由置信度（依据见类 docstring）"""
        count_bonus = min(len(matched), 2) * 0.1
        length_bonus = 0.1 if max(len(kw) for kw in matched) >= 4 else 0.05
        return round(min(0.6 + count_bonus + length_bonus, 0.95), 2)
