from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from app.agent.nl2sql.metadata import DatabaseSchema
from app.agent.nl2sql.pruner import PrunedSchema, SchemaPruner
from app.agent.nl2sql.sql_guard import SQLGuard, SQLGuardResult


class NL2SQLResult(BaseModel):
    query: str = Field(..., description="用户查询")
    pruned_schema: PrunedSchema = Field(..., description="剪枝后的 schema")
    sql: str = Field(..., description="生成的 SQL")
    confidence: float = Field(..., description="置信度")
    reasoning: str = Field(default="", description="生成推理过程")
    guard_result: SQLGuardResult = Field(..., description="SQL 守卫结果")
    generator_used: str = Field(default="mock", description="实际使用的生成器: mock / llm / mock_fallback")
    provider_used: str | None = Field(default=None, description="使用的 LLM Provider 名称")
    fallback_used: bool = Field(default=False, description="是否发生了 fallback")
    fallback_reason: str | None = Field(default=None, description="fallback 原因")
    warnings: list[str] = Field(default_factory=list, description="生成过程中的警告")


class MockNL2SQLGenerator:
    """Mock NL2SQL 生成器

    v0.2 第一阶段不接 LLM，使用规则生成 SQL。
    支持 5 类运营查询的 SQL 生成。
    """

    SQL_TEMPLATES: list[dict[str, Any]] = [
        {
            "keywords": ["GMV", "gmv", "销售额"],
            "sql": "SELECT metric_date, gmv, order_count FROM daily_metrics WHERE metric_date = '{today}'",
            "confidence": 0.9,
            "reasoning": "根据关键词匹配到 GMV 查询，从 daily_metrics 表获取当日数据",
        },
        {
            "keywords": ["新增用户", "用户"],
            "sql": "SELECT COUNT(*) as new_users FROM users WHERE registered_date LIKE '{month_prefix}%'",
            "confidence": 0.85,
            "reasoning": "根据关键词匹配到新增用户查询，从 users 表统计本月注册用户",
        },
        {
            "keywords": ["订单", "订单量"],
            "sql": "SELECT COUNT(*) as order_count, COALESCE(SUM(total_amount), 0) as total_amount FROM orders WHERE order_date = '{today}'",
            "confidence": 0.85,
            "reasoning": "根据关键词匹配到订单查询，从 orders 表获取当日订单统计",
        },
        {
            "keywords": ["商品", "Top商品", "热销", "热门商品", "top商品"],
            "sql": "SELECT p.name, p.category, SUM(o.quantity) as total_qty, SUM(o.total_amount) as total_revenue FROM orders o JOIN products p ON o.product_id = p.id WHERE o.status = 'completed' GROUP BY o.product_id ORDER BY total_revenue DESC LIMIT 5",
            "confidence": 0.8,
            "reasoning": "根据关键词匹配到商品排名查询，关联 products 和 orders 表",
        },
        {
            "keywords": ["退款", "退款率"],
            "sql": "SELECT (SELECT COUNT(*) FROM refund_orders) * 100.0 / (SELECT COUNT(*) FROM orders) as refund_rate_percent",
            "confidence": 0.8,
            "reasoning": "根据关键词匹配到退款率查询，从 refund_orders 和 orders 表计算比率",
        },
    ]

    def __init__(self) -> None:
        self._pruner = SchemaPruner()
        self._guard = SQLGuard()

    def generate(self, query: str, schema: DatabaseSchema) -> NL2SQLResult:
        """根据用户查询生成 SQL

        Args:
            query: 用户查询
            schema: 数据库 schema

        Returns:
            NL2SQLResult 包含 SQL、置信度、推理过程和守卫结果
        """
        pruned = self._pruner.prune(query, schema)

        template = self._match_template(query)

        if template is None:
            guard_result = SQLGuardResult(allowed=False, sql="", reason="无法生成 SQL：未匹配到查询模板")
            return NL2SQLResult(
                query=query,
                pruned_schema=pruned,
                sql="",
                confidence=0.0,
                reasoning="未匹配到任何查询模板",
                guard_result=guard_result,
                generator_used="mock",
                provider_used=None,
                fallback_used=False,
            )

        sql = self._fill_template(template["sql"])
        guard_result = self._guard.check(sql)

        return NL2SQLResult(
            query=query,
            pruned_schema=pruned,
            sql=guard_result.sql,
            confidence=template["confidence"],
            reasoning=template["reasoning"],
            guard_result=guard_result,
            generator_used="mock",
            provider_used=None,
            fallback_used=False,
        )

    def _match_template(self, query: str) -> dict[str, Any] | None:
        for template in self.SQL_TEMPLATES:
            for kw in template["keywords"]:
                if kw in query:
                    return template
        return None

    def _fill_template(self, sql_template: str) -> str:
        today = date.today().isoformat()
        month_prefix = f"{date.today().year}-{date.today().month:02d}"
        return sql_template.replace("{today}", today).replace("{month_prefix}", month_prefix)
