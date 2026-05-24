from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class OperationDecision:
    allowed: bool
    reason: str
    operation: str
    scope: str | None = None


class OperationWhitelist:
    def __init__(self, gateway: Any | None = None) -> None:
        self._gateway = gateway

    def is_allowed(
        self,
        tool_name: str,
        action: str = "",
        mode: str = "",
        risk_level: str | None = None,
        permission_scope: str | None = None,
    ) -> OperationDecision:
        if mode == "nl2sql":
            return self._check_nl2sql(tool_name, action, permission_scope)

        if mode in ("keyword", "multitool", "multi_agent"):
            return self._check_tool_registered(tool_name, mode, risk_level, permission_scope)

        if mode == "approval_resume":
            return self._check_resume(tool_name, mode, risk_level, permission_scope)

        return self._check_tool_registered(tool_name, mode, risk_level, permission_scope)

    def _check_nl2sql(self, tool_name: str, action: str, permission_scope: str | None) -> OperationDecision:
        if permission_scope in ("write", "admin", "schema"):
            return OperationDecision(
                allowed=False,
                reason=f"nl2sql 模式不允许 write/admin/schema 操作: {permission_scope}",
                operation=tool_name,
                scope=permission_scope,
            )
        return OperationDecision(allowed=True, reason="", operation=tool_name, scope=permission_scope)

    def _check_tool_registered(
        self,
        tool_name: str,
        mode: str,
        risk_level: str | None,
        permission_scope: str | None,
    ) -> OperationDecision:
        if self._gateway is not None:
            spec = self._gateway.get_tool(tool_name)
            if spec is None:
                return OperationDecision(
                    allowed=False,
                    reason=f"工具 '{tool_name}' 未在 ToolGateway 注册",
                    operation=tool_name,
                    scope=permission_scope,
                )
            if spec.permission_scope in ("write", "admin", "schema") and risk_level != "high":
                return OperationDecision(
                    allowed=False,
                    reason=f"工具 '{tool_name}' 权限范围 '{spec.permission_scope}' 不允许直接执行",
                    operation=tool_name,
                    scope=spec.permission_scope,
                )
        return OperationDecision(allowed=True, reason="", operation=tool_name, scope=permission_scope)

    def _check_resume(
        self,
        tool_name: str,
        mode: str,
        risk_level: str | None,
        permission_scope: str | None,
    ) -> OperationDecision:
        return self._check_tool_registered(tool_name, mode, risk_level, permission_scope)

    def check_payload_integrity(
        self,
        payload: dict,
        approval_tool_name: str,
        plan_steps: list[dict] | None = None,
    ) -> OperationDecision:
        payload_tool_name = payload.get("tool_name", "")
        if payload_tool_name and payload_tool_name != approval_tool_name:
            return OperationDecision(
                allowed=False,
                reason=f"payload tool_name '{payload_tool_name}' 与审批记录 '{approval_tool_name}' 不匹配",
                operation=payload_tool_name,
            )

        if plan_steps is not None:
            step_id = payload.get("step_id", "")
            found = any(s.get("step_id") == step_id for s in plan_steps)
            if step_id and not found:
                return OperationDecision(
                    allowed=False,
                    reason=f"resume step_id '{step_id}' 不存在于原 plan.steps",
                    operation=step_id,
                )

        return OperationDecision(allowed=True, reason="", operation=approval_tool_name)
