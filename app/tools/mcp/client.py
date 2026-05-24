from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from app.models.schemas import RiskLevel


class MCPToolInfo(BaseModel):
    name: str = Field(..., description="MCP 工具名称")
    description: str = Field(default="", description="工具描述")
    input_schema: dict[str, Any] = Field(default_factory=dict, description="输入参数 JSON Schema")
    output_schema: dict[str, Any] = Field(default_factory=dict, description="输出参数 JSON Schema")
    risk_level: RiskLevel = Field(default=RiskLevel.low, description="风险等级")
    permission_scope: str = Field(default="read", description="权限范围")


@runtime_checkable
class MCPClient(Protocol):
    def list_tools(self) -> list[MCPToolInfo]: ...
    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]: ...


_DATE_LOOKUP_INFO = MCPToolInfo(
    name="date_lookup",
    description="返回今天日期、月份、年份",
    input_schema={
        "type": "object",
        "properties": {},
    },
    output_schema={
        "type": "object",
        "properties": {
            "date": {"type": "string"},
            "month": {"type": "integer"},
            "year": {"type": "integer"},
        },
    },
    risk_level=RiskLevel.low,
    permission_scope="read",
)

_CALCULATOR_INFO = MCPToolInfo(
    name="calculator",
    description="支持 add/subtract/percent_change 的计算器",
    input_schema={
        "type": "object",
        "properties": {
            "operation": {"type": "string", "enum": ["add", "subtract", "percent_change"]},
            "a": {"type": "number"},
            "b": {"type": "number"},
        },
        "required": ["operation", "a", "b"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "result": {"type": "number"},
            "operation": {"type": "string"},
        },
    },
    risk_level=RiskLevel.low,
    permission_scope="read",
)

_RULE_LOOKUP_INFO = MCPToolInfo(
    name="rule_lookup",
    description="根据 keyword 返回 mock 运营规则",
    input_schema={
        "type": "object",
        "properties": {
            "keyword": {"type": "string", "description": "规则关键词"},
        },
        "required": ["keyword"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "keyword": {"type": "string"},
            "rule": {"type": "string"},
        },
    },
    risk_level=RiskLevel.low,
    permission_scope="read",
)

_MOCK_RULES: dict[str, str] = {
    "refund": "退款需在 7 天内申请，审核通过后 3 个工作日到账",
    "promotion": "促销活动需提前 3 天提交审批，折扣上限 50%",
    "shipping": "满 99 元包邮，偏远地区加收 15 元运费",
    "inventory": "库存低于 10 件自动触发补货提醒",
    "pricing": "价格调整需经运营总监审批，调价幅度不超过 20%",
}


class FakeMCPClient:
    def list_tools(self) -> list[MCPToolInfo]:
        return [_DATE_LOOKUP_INFO, _CALCULATOR_INFO, _RULE_LOOKUP_INFO]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "date_lookup":
            now = datetime.now()
            return {
                "date": now.strftime("%Y-%m-%d"),
                "month": now.month,
                "year": now.year,
            }
        elif name == "calculator":
            return self._calculator(arguments)
        elif name == "rule_lookup":
            return self._rule_lookup(arguments)
        else:
            return {"error": f"MCP 工具 '{name}' 不存在"}

    @staticmethod
    def _calculator(arguments: dict[str, Any]) -> dict[str, Any]:
        operation = arguments.get("operation")
        a = arguments.get("a")
        b = arguments.get("b")
        if operation is None or a is None or b is None:
            return {"error": "缺少必要参数: operation, a, b"}
        try:
            a_val = float(a)
            b_val = float(b)
        except (TypeError, ValueError):
            return {"error": "a 和 b 必须为数字"}
        if operation == "add":
            return {"result": a_val + b_val, "operation": "add"}
        elif operation == "subtract":
            return {"result": a_val - b_val, "operation": "subtract"}
        elif operation == "percent_change":
            if b_val == 0:
                return {"error": "percent_change 的 b 不能为 0"}
            return {"result": round((a_val - b_val) / abs(b_val) * 100, 2), "operation": "percent_change"}
        else:
            return {"error": f"不支持的操作: {operation}"}

    @staticmethod
    def _rule_lookup(arguments: dict[str, Any]) -> dict[str, Any]:
        keyword = arguments.get("keyword", "")
        if not keyword:
            return {"error": "缺少必要参数: keyword"}
        for k, v in _MOCK_RULES.items():
            if k in keyword:
                return {"keyword": keyword, "rule": v}
        return {"keyword": keyword, "rule": f"未找到与 '{keyword}' 相关的运营规则"}
