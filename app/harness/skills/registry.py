from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.models.schemas import RiskLevel


class SkillSpec(BaseModel):
    name: str
    description: str
    triggers: list[str] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    risk_level: str = "low"
    tool_names: list[str] = Field(default_factory=list)


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, SkillSpec] = {}
        self._register_builtin_skills()

    def _register_builtin_skills(self) -> None:
        self.register(SkillSpec(
            name="ops_metrics_skill",
            description="运营指标查询：GMV、订单、用户、退款率",
            triggers=["GMV", "gmv", "订单", "用户", "退款率", "营收", "销售"],
            input_schema={"type": "object", "properties": {"metric": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"value": {"type": "number"}}},
            risk_level="low",
            tool_names=["get_today_gmv", "get_order_count", "get_month_new_users", "get_refund_rate"],
        ))
        self.register(SkillSpec(
            name="product_analysis_skill",
            description="商品分析：Top 商品排行",
            triggers=["Top", "top", "商品", "排行", "热销", "爆款"],
            input_schema={"type": "object", "properties": {"limit": {"type": "integer"}}},
            output_schema={"type": "object", "properties": {"products": {"type": "array"}}},
            risk_level="low",
            tool_names=["get_top_products"],
        ))
        self.register(SkillSpec(
            name="policy_lookup_skill",
            description="规则查询：退款规则、促销规则",
            triggers=["退款规则", "促销", "规则", "政策", "policy"],
            input_schema={"type": "object", "properties": {"policy_type": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"rules": {"type": "array"}}},
            risk_level="low",
            tool_names=[],
        ))
        self.register(SkillSpec(
            name="nl2sql_analysis_skill",
            description="自然语言数据查询：通过 NL2SQL 分析数据",
            triggers=["分析", "查询数据", "数据", "统计", "报表", "对比"],
            input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"sql": {"type": "string"}, "result": {"type": "object"}}},
            risk_level="medium",
            tool_names=[],
        ))

    def register(self, skill: SkillSpec) -> None:
        self._skills[skill.name] = skill

    def list_skills(self) -> list[SkillSpec]:
        return list(self._skills.values())

    def get_skill(self, name: str) -> SkillSpec | None:
        return self._skills.get(name)

    def match(self, query: str) -> list[SkillSpec]:
        matched = []
        query_lower = query.lower()
        for skill in self._skills.values():
            for trigger in skill.triggers:
                if trigger.lower() in query_lower:
                    matched.append(skill)
                    break
        return matched
