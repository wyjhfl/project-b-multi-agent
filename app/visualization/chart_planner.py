from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.agent.nl2sql.executor import SQLExecutionResult


class ChartSpec(BaseModel):
    chart_type: Literal["table", "bar", "line", "pie", "metric"] = Field(
        ..., description="图表类型"
    )
    title: str = Field(..., description="图表标题")
    x_field: str | None = Field(default=None, description="X 轴字段")
    y_fields: list[str] = Field(default_factory=list, description="Y 轴字段")
    data: list[dict] = Field(default_factory=list, description="图表数据")
    reason: str = Field(default="", description="图表类型选择原因")


_DATE_KEYWORDS = {"date", "metric_date", "order_date", "created_at", "updated_at"}
_CATEGORY_KEYWORDS = {"name", "category", "type", "label", "product_name", "metric_name"}


class ChartPlanner:
    """图表规格规划器

    根据 SQL 执行结果和查询意图，生成 ChartSpec JSON 配置。
    不依赖 Plotly/ECharts，不新增重依赖。
    """

    def plan(self, execution_result: SQLExecutionResult, query: str = "") -> ChartSpec:
        if not execution_result.success:
            return ChartSpec(
                chart_type="table",
                title=query or "查询结果",
                data=[],
                reason=f"执行失败，不可视化: {execution_result.error}",
            )

        if execution_result.row_count == 0:
            return ChartSpec(
                chart_type="table",
                title=query or "查询结果",
                data=[],
                reason="查询成功但无数据",
            )

        columns = execution_result.columns
        rows = execution_result.rows

        if execution_result.row_count == 1 and len(columns) == 1:
            value = rows[0][columns[0]]
            return ChartSpec(
                chart_type="metric",
                title=query or columns[0],
                x_field=None,
                y_fields=columns,
                data=rows,
                reason="单行单指标，适合指标卡片展示",
            )

        date_fields = [c for c in columns if c.lower() in _DATE_KEYWORDS]
        numeric_fields = self._detect_numeric_fields(columns, rows)
        category_fields = [c for c in columns if c.lower() in _CATEGORY_KEYWORDS]

        if date_fields and numeric_fields:
            return ChartSpec(
                chart_type="line",
                title=query or "趋势图",
                x_field=date_fields[0],
                y_fields=numeric_fields,
                data=rows,
                reason=f"包含日期字段 {date_fields[0]} 和数值字段，适合折线图",
            )

        if category_fields and numeric_fields and execution_result.row_count > 1:
            return ChartSpec(
                chart_type="bar",
                title=query or "对比图",
                x_field=category_fields[0],
                y_fields=numeric_fields,
                data=rows,
                reason=f"包含分类字段 {category_fields[0]} 和数值字段，适合柱状图",
            )

        if execution_result.row_count > 1 and numeric_fields:
            x_field = columns[0] if columns else None
            return ChartSpec(
                chart_type="bar",
                title=query or "对比图",
                x_field=x_field,
                y_fields=numeric_fields,
                data=rows,
                reason="多行数值结果，适合柱状图",
            )

        return ChartSpec(
            chart_type="table",
            title=query or "查询结果",
            data=rows,
            reason="无法判断合适的图表类型，使用表格展示",
        )

    def _detect_numeric_fields(self, columns: list[str], rows: list[dict]) -> list[str]:
        numeric: list[str] = []
        for col in columns:
            if col.lower() in _DATE_KEYWORDS or col.lower() in _CATEGORY_KEYWORDS:
                continue
            sample_values = [row.get(col) for row in rows[:5] if row.get(col) is not None]
            if not sample_values:
                continue
            numeric_count = sum(1 for v in sample_values if isinstance(v, (int, float)))
            if numeric_count > len(sample_values) * 0.5:
                numeric.append(col)
        return numeric
