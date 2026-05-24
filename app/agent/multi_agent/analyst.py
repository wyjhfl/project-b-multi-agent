from __future__ import annotations

from app.agent.multi_agent.types import AgentDecision


class AnalystAgent:
    def analyze(self, query: str, coordinator_decision: AgentDecision) -> AgentDecision:
        selected_mode = coordinator_decision.metadata.get("selected_mode", "auto")
        needs_schema = selected_mode == "nl2sql"
        needs_multitool = selected_mode == "multitool"

        parts: list[str] = []
        if needs_schema:
            parts.append("需要 schema 查询")
        if needs_multitool:
            parts.append("需要多工具串联")
        if not parts:
            parts.append("简单查询")

        plan_summary = f"查询 '{query}' → {coordinator_decision.action}，{', '.join(parts)}"

        return AgentDecision(
            role="analyst",
            action="plan_analysis",
            reason=plan_summary,
            confidence=coordinator_decision.confidence,
            metadata={
                "selected_mode": selected_mode,
                "needs_schema": needs_schema,
                "needs_multitool": needs_multitool,
                "plan_summary": plan_summary,
            },
        )
