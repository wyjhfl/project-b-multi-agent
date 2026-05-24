from __future__ import annotations

from typing import Any

from app.agent.multi_agent.types import AgentDecision


class ReviewerAgent:
    def review(
        self,
        execution_result: dict[str, Any],
        selected_mode: str,
    ) -> tuple[dict[str, Any], AgentDecision]:
        success = execution_result.get("success", False)
        has_answer = bool(execution_result.get("answer") or execution_result.get("final_answer"))

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
        elif not success and selected_mode != "auto":
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
        elif not has_answer:
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
        else:
            review_result = {
                "approved": True,
                "reason": "执行成功",
                "suggested_fallback_mode": None,
            }
            decision = AgentDecision(
                role="reviewer",
                action="approve",
                reason="执行成功",
                confidence=0.9,
                metadata={"approved": True},
            )

        return review_result, decision

    def _suggest_fallback(self, failed_mode: str) -> str:
        fallback_map: dict[str, str] = {
            "nl2sql": "multitool",
            "multitool": "keyword",
            "keyword": "auto",
        }
        return fallback_map.get(failed_mode, "keyword")
