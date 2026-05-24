from __future__ import annotations

from typing import Any

from app.harness.policy.operation_whitelist import OperationWhitelist
from app.models.schemas import RiskLevel


class PolicyEngine:
    def __init__(self, operation_whitelist: OperationWhitelist | None = None) -> None:
        self._whitelist = operation_whitelist

    def check(self, action: str, risk_level: RiskLevel | None = None, context: dict[str, Any] | None = None) -> bool:
        if risk_level == RiskLevel.high:
            return False
        return True

    def evaluate(self, action: str, risk_level: RiskLevel | None = None, context: dict[str, Any] | None = None) -> dict[str, Any]:
        if self._whitelist is not None:
            mode = (context or {}).get("mode", "")
            permission_scope = (context or {}).get("permission_scope")
            wl_decision = self._whitelist.is_allowed(
                tool_name=action,
                mode=mode,
                risk_level=risk_level.value if risk_level else None,
                permission_scope=permission_scope,
            )
            if not wl_decision.allowed:
                return {
                    "action": action,
                    "risk_level": risk_level.value if risk_level else None,
                    "allowed": False,
                    "requires_approval": False,
                    "reason": f"操作不在白名单内: {wl_decision.reason}",
                    "error_type": "operation_not_whitelisted",
                }

        allowed = self.check(action, risk_level, context)
        reason = ""
        requires_approval = False

        if not allowed:
            requires_approval = True
            reason = f"高风险工具 '{action}' 需要人工审批"

        return {
            "action": action,
            "risk_level": risk_level.value if risk_level else None,
            "allowed": allowed,
            "reason": reason,
            "requires_approval": requires_approval,
        }
