from __future__ import annotations

from typing import Any

from app.core.config import settings

# 统一路由规则源（单一事实来源）
#
# CoordinatorAgent（multi_agent 模式的意图路由）与 KeywordPlanner（keyword 模式的
# 工具路由）共同消费本表，避免两份关键词表重复维护导致口径漂移（如"退款"类词条）。
# 规则按顺序匹配，先命中先生效：
# - 复合查询规则排最前（需多工具串联，keyword 模式无单一工具可回答，tool_name 为 None）；
# - "模拟退款"高风险演示规则必须排在"退款"泛化词条之前，否则会被 get_refund_rate 抢先命中；
# - 日期等专用意图排在数据查询泛化词条之前，其余顺序与 v0.1 词表保持一致。
#
# 字段说明：
# - keywords: 命中关键词列表（子串匹配）
# - tool_name / label: keyword 模式映射的本地工具（None 表示 keyword 模式跳过该规则）
# - action / selected_mode: multi_agent 模式下 Coordinator 的动作与目标执行模式
# - settings_switch: 可选，settings 中的布尔开关名，关闭时该规则整体失效
ROUTING_RULE_SOURCE: list[dict[str, Any]] = [
    {
        "keywords": ["GMV环比", "环比增长", "退款规则", "退款政策", "促销规则"],
        "tool_name": None,
        "label": None,
        "action": "compound_tool_query",
        "selected_mode": "multitool",
    },
    {
        "keywords": ["模拟退款", "退款演练"],
        "tool_name": "simulate_refund_order",
        "label": "模拟退款单",
        "action": "high_risk_operation",
        "selected_mode": "keyword",
        "settings_switch": "demo_high_risk_tool_enabled",
    },
    {
        "keywords": ["今天几号", "当前日期", "日期"],
        "tool_name": "date_lookup",
        "label": "日期查询",
        "action": "simple_query",
        "selected_mode": "keyword",
    },
    {
        "keywords": ["GMV", "gmv", "销售额"],
        "tool_name": "get_today_gmv",
        "label": "今日 GMV",
        "action": "data_query",
        "selected_mode": "nl2sql",
    },
    {
        "keywords": ["新增用户", "用户"],
        "tool_name": "get_month_new_users",
        "label": "本月新增用户",
        "action": "data_query",
        "selected_mode": "nl2sql",
    },
    {
        "keywords": ["订单", "订单量"],
        "tool_name": "get_order_count",
        "label": "订单数量",
        "action": "data_query",
        "selected_mode": "nl2sql",
    },
    {
        "keywords": ["Top商品", "热销", "热门商品", "top商品"],
        "tool_name": "get_top_products",
        "label": "Top 商品",
        "action": "data_query",
        "selected_mode": "nl2sql",
    },
    {
        "keywords": ["退款率", "退款"],
        "tool_name": "get_refund_rate",
        "label": "退款率",
        "action": "data_query",
        "selected_mode": "nl2sql",
    },
]


def rule_enabled(rule: dict[str, Any]) -> bool:
    """判断路由规则是否生效

    规则声明了 settings_switch 时，读取 settings 上同名布尔开关；
    未声明开关的规则始终生效。
    """
    switch = rule.get("settings_switch")
    if not switch:
        return True
    return bool(getattr(settings, switch, False))


def build_planner_rules() -> list[dict[str, Any]]:
    """从统一路由规则源构建 KeywordPlanner 词表（仅保留有工具映射的规则）"""
    return [dict(rule) for rule in ROUTING_RULE_SOURCE if rule.get("tool_name")]


def build_coordinator_rules() -> list[dict[str, Any]]:
    """从统一路由规则源构建 Coordinator 词表"""
    return [dict(rule) for rule in ROUTING_RULE_SOURCE]


class KeywordPlanner:
    """关键词规划器

    根据用户查询中的关键词匹配对应的工具。
    词表来自 ROUTING_RULE_SOURCE（与 CoordinatorAgent 共用单一规则源），支持：
    - 今天几号 / 当前日期 / 日期 → date_lookup
    - GMV / gmv / 销售额 → get_today_gmv
    - 新增用户 / 用户 → get_month_new_users
    - 订单 / 订单量 → get_order_count
    - Top商品 / 热销 / 热门商品 → get_top_products
    - 退款率 / 退款 → get_refund_rate
    - 模拟退款 / 退款演练 → simulate_refund_order（高风险审批演示，受 demo_high_risk_tool_enabled 控制）
    """

    ROUTING_RULES: list[dict[str, Any]] = build_planner_rules()

    def plan(self, query: str) -> dict[str, Any]:
        """根据查询关键词匹配工具

        Args:
            query: 用户查询

        Returns:
            包含 tool_name、matched、label 的字典
        """
        for rule in self.ROUTING_RULES:
            if not rule_enabled(rule):
                continue
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
