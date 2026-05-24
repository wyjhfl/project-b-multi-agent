from __future__ import annotations

from typing import Any


class KeywordPlanner:
    """关键词规划器

    根据用户查询中的关键词匹配对应的工具。
    v0.1 支持以下 5 类查询：
    - GMV / gmv / 销售额 → get_today_gmv
    - 新增用户 / 用户 → get_month_new_users
    - 订单 / 订单量 → get_order_count
    - Top商品 / 热销 / 热门商品 → get_top_products
    - 退款率 / 退款 → get_refund_rate
    """

    ROUTING_RULES: list[dict[str, Any]] = [
        {
            "keywords": ["今天几号", "当前日期", "日期"],
            "tool_name": "date_lookup",
            "label": "日期查询",
        },
        {
            "keywords": ["GMV", "gmv", "销售额"],
            "tool_name": "get_today_gmv",
            "label": "今日 GMV",
        },
        {
            "keywords": ["新增用户", "用户"],
            "tool_name": "get_month_new_users",
            "label": "本月新增用户",
        },
        {
            "keywords": ["订单", "订单量"],
            "tool_name": "get_order_count",
            "label": "订单数量",
        },
        {
            "keywords": ["Top商品", "热销", "热门商品", "top商品"],
            "tool_name": "get_top_products",
            "label": "Top 商品",
        },
        {
            "keywords": ["退款率", "退款"],
            "tool_name": "get_refund_rate",
            "label": "退款率",
        },
    ]

    def plan(self, query: str) -> dict[str, Any]:
        """根据查询关键词匹配工具

        Args:
            query: 用户查询

        Returns:
            包含 tool_name、matched、label 的字典
        """
        for rule in self.ROUTING_RULES:
            for kw in rule["keywords"]:
                if kw in query:
                    return {
                        "tool_name": rule["tool_name"],
                        "matched": True,
                        "label": rule["label"],
                    }
        return {
            "tool_name": None,
            "matched": False,
            "label": None,
        }

    def get_label(self, tool_name: str | None) -> str:
        """根据工具名称获取标签"""
        if not tool_name:
            return "未知"
        for rule in self.ROUTING_RULES:
            if rule["tool_name"] == tool_name:
                return rule["label"]
        return tool_name
