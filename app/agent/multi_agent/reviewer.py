from __future__ import annotations

from typing import Any

from app.agent.multi_agent.types import AgentDecision


class ReviewerAgent:
    """审查者：对 Executor 的执行结果做质量把关

    审查规则（按优先级）：
    - 执行成功且有 answer → approve；
    - 结果被策略拦截 / 需人工审批 → reject，不建议 fallback（换模式无法也不应绕过审批）；
    - auto 模式失败 → reject，不再建议 fallback（auto 内部已完成
      nl2sql→multitool→keyword 级联，fallback 链路已穷尽）；
    - 其他模式失败 → 按 fallback_map 建议降级重试一次；
    - 执行成功但缺少 answer → reject，建议 keyword 兜底。
    """

    def review(
        self,
        execution_result: dict[str, Any],
        selected_mode: str,
    ) -> tuple[dict[str, Any], AgentDecision]:
        success = execution_result.get("success", False)
        has_answer = bool(execution_result.get("answer") or execution_result.get("final_answer"))
        blocked = bool(execution_result.get("blocked") or execution_result.get("requires_approval"))

        if success and has_answer:
            review_result = {
                "approved": True,
                "reason": "执行成功且结果完整",
                "suggested_fallback_mode": None,
            }
            decision = AgentDecision(
                role="reviewer",
                action="approve",
                reason="执行成功且结果完整",
                confidence=0.95,
                metadata={"approved": True},
            )
        elif blocked:
            reason = "执行被策略拦截或等待人工审批，切换模式无法绕过审批，不建议 fallback"
            review_result = {
                "approved": False,
                "reason": reason,
                "suggested_fallback_mode": None,
            }
            decision = AgentDecision(
                role="reviewer",
                action="reject",
                reason=reason,
                confidence=0.85,
                metadata={"approved": False, "suggested_fallback_mode": None, "policy_blocked": True},
            )
        elif not success and selected_mode == "auto":
            reason = "auto 模式执行失败，内部 nl2sql→multitool→keyword 级联已穷尽，不再建议 fallback"
            review_result = {
                "approved": False,
                "reason": reason,
                "suggested_fallback_mode": None,
            }
            decision = AgentDecision(
                role="reviewer",
                action="reject",
                reason=reason,
                confidence=0.8,
                metadata={"approved": False, "suggested_fallback_mode": None},
            )
        elif not success:
            fallback = self._suggest_fallback(selected_mode)
            review_result = {
                "approved": False,
                "reason": f"执行失败，建议 fallback 到 {fallback}",
                "suggested_fallback_mode": fallback,
            }
            decision = AgentDecision(
                role="reviewer",
                action="suggest_fallback",
                reason=f"执行失败，建议 fallback 到 {fallback}",
                confidence=0.7,
                metadata={"approved": False, "suggested_fallback_mode": fallback},
            )
        else:
            review_result = {
                "approved": False,
                "reason": "结果缺少 answer",
                "suggested_fallback_mode": "keyword",
            }
            decision = AgentDecision(
                role="reviewer",
                action="reject",
                reason="结果缺少 answer",
                confidence=0.6,
                metadata={"approved": False, "suggested_fallback_mode": "keyword"},
            )

        return review_result, decision

    def _suggest_fallback(self, failed_mode: str) -> str:
        fallback_map: dict[str, str] = {
            "nl2sql": "multitool",
            "multitool": "keyword",
            "keyword": "auto",
        }
        return fallback_map.get(failed_mode, "keyword")
