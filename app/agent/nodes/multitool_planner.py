from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MultiToolPlanStep(BaseModel):
    step_id: str = Field(..., description="步骤唯一标识")
    tool_name: str = Field(..., description="工具名称")
    arguments: dict[str, Any] = Field(default_factory=dict, description="调用参数，支持 $var.path 占位符")
    depends_on: list[str] = Field(default_factory=list, description="依赖的步骤 ID")
    save_as: str | None = Field(default=None, description="将结果保存为变量名")


class MultiToolPlan(BaseModel):
    matched: bool = Field(..., description="是否匹配到多工具任务")
    intent: str = Field(default="", description="任务意图")
    steps: list[MultiToolPlanStep] = Field(default_factory=list, description="执行步骤")
    response_template: str = Field(default="", description="响应模板")
    reason: str = Field(default="", description="规划原因说明")


_GMV_MOM_PLAN = MultiToolPlan(
    matched=True,
    intent="gmv_mom",
    steps=[
        MultiToolPlanStep(
            step_id="step_date",
            tool_name="date_lookup",
            arguments={},
            depends_on=[],
            save_as="date_info",
        ),
        MultiToolPlanStep(
            step_id="step_gmv",
            tool_name="get_today_gmv",
            arguments={},
            depends_on=[],
            save_as="current_gmv",
        ),
        MultiToolPlanStep(
            step_id="step_calc",
            tool_name="calculator",
            arguments={
                "operation": "percent_change",
                "a": "$current_gmv.result.gmv",
                "b": 100000,
            },
            depends_on=["step_date", "step_gmv"],
            save_as="mom_change",
        ),
    ],
    response_template="GMV环比增长",
    reason="使用 mock baseline=100000 作为上期 GMV，v0.3.2 将接入真实上月查询",
)

_REFUND_RULE_PLAN = MultiToolPlan(
    matched=True,
    intent="refund_rule",
    steps=[
        MultiToolPlanStep(
            step_id="step_rule",
            tool_name="rule_lookup",
            arguments={"keyword": "refund"},
            depends_on=[],
            save_as="refund_rule",
        ),
        MultiToolPlanStep(
            step_id="step_rate",
            tool_name="get_refund_rate",
            arguments={},
            depends_on=[],
            save_as="refund_rate",
        ),
    ],
    response_template="退款规则+退款率",
    reason="查询退款规则并获取当前退款率",
)

_PROMOTION_RULE_PLAN = MultiToolPlan(
    matched=True,
    intent="promotion_rule",
    steps=[
        MultiToolPlanStep(
            step_id="step_rule",
            tool_name="rule_lookup",
            arguments={"keyword": "promotion"},
            depends_on=[],
            save_as="promotion_rule",
        ),
    ],
    response_template="促销规则",
    reason="查询促销规则",
)

_UNMATCHED_PLAN = MultiToolPlan(
    matched=False,
    intent="",
    steps=[],
    response_template="",
    reason="未匹配到多工具任务",
)


class MultiToolPlanner:
    RULES: list[dict[str, Any]] = [
        {
            "keywords": ["GMV环比", "环比增长"],
            "plan": _GMV_MOM_PLAN,
        },
        {
            "keywords": ["退款规则", "退款政策"],
            "plan": _REFUND_RULE_PLAN,
        },
        {
            "keywords": ["促销规则"],
            "plan": _PROMOTION_RULE_PLAN,
        },
    ]

    def plan(self, query: str) -> MultiToolPlan:
        for rule in self.RULES:
            for kw in rule["keywords"]:
                if kw in query:
                    return rule["plan"]
        return _UNMATCHED_PLAN
