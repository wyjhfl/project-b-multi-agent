from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.agent.nl2sql.metadata import DatabaseSchema, SchemaTable


class PrunedSchema(BaseModel):
    tables: list[SchemaTable] = Field(default_factory=list, description="剪枝后的表列表")
    fallback: bool = Field(default=False, description="是否为 fallback（未匹配到规则）")
    reason: str = Field(default="", description="剪枝原因")
    matched_keywords: list[str] = Field(default_factory=list, description="匹配到的关键词")


class SchemaPruner:
    """Schema 剪枝器

    根据用户查询中的关键词选择相关的表，减少 schema 搜索空间。
    v0.2 第一阶段使用关键词规则，不使用 LLM。
    """

    PRUNING_RULES: list[dict[str, Any]] = [
        {
            "keywords": ["GMV", "gmv", "销售额", "指标"],
            "tables": ["daily_metrics"],
            "reason": "查询涉及 GMV/销售额/指标，选择 daily_metrics",
        },
        {
            "keywords": ["订单", "订单量"],
            "tables": ["orders"],
            "reason": "查询涉及订单，选择 orders",
        },
        {
            "keywords": ["用户", "新增用户"],
            "tables": ["users"],
            "reason": "查询涉及用户，选择 users",
        },
        {
            "keywords": ["商品", "Top商品", "热销", "热门商品", "top商品"],
            "tables": ["products", "orders"],
            "reason": "查询涉及商品排名，选择 products + orders",
        },
        {
            "keywords": ["退款", "退款率"],
            "tables": ["refund_orders", "orders"],
            "reason": "查询涉及退款，选择 refund_orders + orders",
        },
    ]

    def prune(self, query: str, schema: DatabaseSchema) -> PrunedSchema:
        """根据查询关键词剪枝 schema

        Args:
            query: 用户查询
            schema: 完整数据库 schema

        Returns:
            剪枝后的 PrunedSchema
        """
        matched_rule = self._match_rule(query)

        if matched_rule is None:
            return PrunedSchema(
                tables=schema.tables,
                fallback=True,
                reason="未匹配到关键词规则，返回所有表",
                matched_keywords=[],
            )

        selected_table_names = matched_rule["tables"]
        selected_tables = [t for t in schema.tables if t.name in selected_table_names]

        matched_keywords = [kw for kw in matched_rule["keywords"] if kw in query]

        return PrunedSchema(
            tables=selected_tables,
            fallback=False,
            reason=matched_rule["reason"],
            matched_keywords=matched_keywords,
        )

    def _match_rule(self, query: str) -> dict[str, Any] | None:
        for rule in self.PRUNING_RULES:
            for kw in rule["keywords"]:
                if kw in query:
                    return rule
        return None
