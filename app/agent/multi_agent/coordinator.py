from __future__ import annotations

from typing import Any

from app.agent.multi_agent.types import AgentDecision


class CoordinatorAgent:
    ROUTING_RULES: list[dict[str, Any]] = [
        {
            "keywords": ["GMV环比", "环比增长", "退款规则", "退款政策", "促销规则"],
            "action": "compound_tool_query",
            "selected_mode": "multitool",
        },
        {
            "keywords": ["GMV", "gmv", "销售额", "新增用户", "用户", "订单", "Top商品", "热销", "热门商品", "退款率", "退款"],
            "action": "data_query",
            "selected_mode": "nl2sql",
        },
        {
            "keywords": ["今天几号", "当前日期", "日期"],
            "action": "simple_query",
            "selected_mode": "keyword",
        },
    ]

    def decide(self, query: str) -> AgentDecision:
        for rule in self.ROUTING_RULES:
            for kw in rule["keywords"]:
                if kw in query:
                    return AgentDecision(
                        role="coordinator",
                        action=rule["action"],
                        reason=f"关键词 '{kw}' 匹配规则，选择 {rule['selected_mode']} 模式",
                        confidence=0.9,
                        metadata={"selected_mode": rule["selected_mode"]},
                    )

        return AgentDecision(
            role="coordinator",
            action="unknown",
            reason="未匹配任何路由规则，使用 auto 模式",
            confidence=0.5,
            metadata={"selected_mode": "auto"},
        )
