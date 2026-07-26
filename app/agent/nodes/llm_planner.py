from __future__ import annotations

import json
from typing import Any

from app.agent.nodes.planner import KeywordPlanner

# JSON Schema 基础类型 → Python 类型检查
# bool 是 int 的子类，integer/number 需显式排除 bool，避免 true 被当作 1 通过校验
_JSON_TYPE_CHECKS: dict[str, Any] = {
    "string": lambda value: isinstance(value, str),
    "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
    "number": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
    "boolean": lambda value: isinstance(value, bool),
    "array": lambda value: isinstance(value, list),
    "object": lambda value: isinstance(value, dict),
    "null": lambda value: value is None,
}


def build_tools_from_gateway(tool_gateway: Any) -> list[dict[str, Any]]:
    """把 ToolGateway 已注册的 ToolSpec 转为 OpenAI function calling tools 列表

    - name/description 取自 ToolSpec，description 附注 risk_level 供 LLM 感知风险；
    - parameters 取 ToolSpec.input_schema，未声明 schema 的工具按无参数对象处理。
    """
    tools: list[dict[str, Any]] = []
    for spec in tool_gateway.list_tools():
        parameters = spec.input_schema if isinstance(spec.input_schema, dict) and spec.input_schema else {"type": "object", "properties": {}}
        risk = spec.risk_level.value if hasattr(spec.risk_level, "value") else str(spec.risk_level)
        description = spec.description or spec.tool_name
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": spec.tool_name,
                    "description": f"{description}（risk_level={risk}）",
                    "parameters": parameters,
                },
            }
        )
    return tools


def validate_tool_arguments(
    input_schema: dict[str, Any] | None,
    arguments: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """按 ToolSpec.input_schema 校验并过滤 LLM 给出的调用参数

    - properties 中声明的参数按 type 做类型检查，不符即抛 ValueError；
    - required 声明的参数缺失时抛 ValueError；
    - schema 未声明的参数一律丢弃（本地工具以 **arguments 调用，未声明参数
      会直接 TypeError，丢弃可同时防止 LLM 夹带参数注入），键名在返回值中回报。

    Returns:
        (通过校验的参数, 被丢弃的未声明参数键名列表)
    """
    schema = input_schema if isinstance(input_schema, dict) else {}
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        properties = {}
    required = schema.get("required")
    if not isinstance(required, list):
        required = []

    cleaned: dict[str, Any] = {}
    ignored: list[str] = []
    for key, value in arguments.items():
        if key not in properties:
            ignored.append(key)
            continue
        prop_schema = properties[key] if isinstance(properties[key], dict) else {}
        expected = prop_schema.get("type")
        check = _JSON_TYPE_CHECKS.get(expected) if isinstance(expected, str) else None
        if check is not None and not check(value):
            raise ValueError(f"参数 '{key}' 类型不符，期望 {expected}")
        cleaned[key] = value

    missing = [key for key in required if key not in cleaned]
    if missing:
        raise ValueError(f"缺少必填参数: {', '.join(missing)}")
    return cleaned, ignored


class LLMToolPlanner:
    """LLM Function Calling 规划器

    用 LLM 的 function calling 能力从 ToolGateway 已注册工具中选择调用目标：
    tools 列表由 ToolSpec 构建（含 JSON Schema 与 risk_level 注记），LLM 返回的
    tool_call 解析出工具名与 arguments，arguments 经 input_schema 校验通过后
    才随 plan_result 进入 ToolGateway。

    plan() 产出与 KeywordPlanner.plan() 兼容（tool_name/matched/label），
    LLM 命中时附加 planner=llm 与 provider/model 元数据；以下任一失败点都
    降级到 KeywordPlanner，并以 fallback_reason 记录原因（前缀标记触发点）：
    - no_tools_available: ToolGateway 未注册任何工具（不发起 LLM 调用）
    - provider_error: provider 创建或调用异常
    - no_tool_call: provider 未返回 tool_call
    - unknown_tool: tool_call 的工具名未在 ToolGateway 注册
    - invalid_arguments: arguments 非法 JSON / 类型不符 / 缺必填参数

    工具执行的策略评估与高风险审批仍由 AgentKernel._execute 的治理层负责，
    规划器只做选择与参数校验，不绕过任何拦截。
    """

    def __init__(
        self,
        tool_gateway: Any,
        *,
        provider: Any | None = None,
        fallback_planner: KeywordPlanner | None = None,
    ) -> None:
        self._tool_gateway = tool_gateway
        self._provider = provider
        self._fallback = fallback_planner or KeywordPlanner()

    def plan(self, query: str) -> dict[str, Any]:
        """用 LLM function calling 选择工具，失败降级 KeywordPlanner

        Args:
            query: 用户查询

        Returns:
            包含 tool_name、matched、label 的字典；LLM 命中时附加
            planner/arguments/provider/model，降级时附加 fallback_reason
        """
        tools = build_tools_from_gateway(self._tool_gateway)
        if not tools:
            return self._fallback_plan(query, "no_tools_available: ToolGateway 未注册任何工具")

        try:
            provider = self._get_provider()
            metadata = provider.generate_with_metadata(self._build_prompt(query), tools=tools)
        except Exception as exc:
            return self._fallback_plan(query, f"provider_error: {exc}")

        tool_calls = metadata.tool_calls or []
        if not tool_calls:
            return self._fallback_plan(query, "no_tool_call: provider 未返回工具调用")

        function = tool_calls[0].get("function") if isinstance(tool_calls[0], dict) else None
        tool_name = str((function or {}).get("name") or "")
        spec = self._tool_gateway.get_tool(tool_name)
        if spec is None:
            return self._fallback_plan(query, f"unknown_tool: 工具 '{tool_name}' 未注册")

        try:
            arguments = self._parse_arguments((function or {}).get("arguments"))
            cleaned, ignored = validate_tool_arguments(spec.input_schema, arguments)
        except ValueError as exc:
            return self._fallback_plan(query, f"invalid_arguments: {exc}")

        result: dict[str, Any] = {
            "tool_name": tool_name,
            "matched": True,
            "label": self.get_label(tool_name),
            "planner": "llm",
            "arguments": cleaned,
            "provider": metadata.provider,
            "model": metadata.model,
        }
        if ignored:
            result["ignored_arguments"] = ignored
        return result

    def get_label(self, tool_name: str | None) -> str:
        """根据工具名称获取标签（沿用关键词词表，未收录的工具回退工具名）"""
        return self._fallback.get_label(tool_name)

    def _get_provider(self) -> Any:
        if self._provider is None:
            from app.agent.nl2sql.provider import create_provider

            self._provider = create_provider()
        return self._provider

    @staticmethod
    def _build_prompt(query: str) -> str:
        return (
            "你是工具规划器。请根据可用工具的描述与 JSON Schema，"
            "为下面的查询选择最合适的工具并给出调用参数；"
            "没有合适工具时不要调用任何工具。\n"
            f"查询: {query}"
        )

    @staticmethod
    def _parse_arguments(raw: Any) -> dict[str, Any]:
        """解析 tool_call 的 arguments（JSON 字符串或 dict），非法时抛 ValueError"""
        if raw is None:
            return {}
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            if not raw.strip():
                return {}
            try:
                parsed = json.loads(raw)
            except ValueError as exc:
                raise ValueError(f"arguments 不是合法 JSON: {exc}") from exc
            if not isinstance(parsed, dict):
                raise ValueError("arguments 必须是 JSON object")
            return parsed
        raise ValueError(f"arguments 类型不受支持: {type(raw).__name__}")

    def _fallback_plan(self, query: str, reason: str) -> dict[str, Any]:
        """降级到 KeywordPlanner，plan_result 标记 fallback_reason"""
        result = self._fallback.plan(query)
        result["planner"] = "keyword"
        result["fallback_reason"] = reason
        return result
