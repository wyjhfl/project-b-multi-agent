from __future__ import annotations

from typing import Any

from app.agent.multi_agent.analyst import AnalystAgent
from app.agent.multi_agent.coordinator import CoordinatorAgent
from app.agent.multi_agent.executor import ExecutorAgent
from app.agent.multi_agent.reviewer import ReviewerAgent
from app.agent.multi_agent.types import AgentDecision, MultiAgentRunResult
from app.harness.security.risk_intent_guard import RiskIntentGuard
from app.harness.trace.recorder import TraceRecorder


class MultiAgentOrchestrator:
    def __init__(
        self,
        executor: ExecutorAgent,
        trace_recorder: TraceRecorder | None = None,
        risk_intent_guard: RiskIntentGuard | None = None,
    ) -> None:
        self._coordinator = CoordinatorAgent()
        self._analyst = AnalystAgent()
        self._executor = executor
        self._reviewer = ReviewerAgent()
        self._trace_recorder = trace_recorder
        self._risk_intent_guard = risk_intent_guard or RiskIntentGuard()

    def run(
        self,
        query: str,
        task_id: str | None = None,
        generator: str = "mock",
        provider: str | None = None,
        fallback_to_mock: bool = True,
    ) -> MultiAgentRunResult:
        self._trace("multi_agent_started", task_id, query=query)

        risk_finding = self._risk_intent_guard.check(query)
        if risk_finding.detected:
            self._trace("risk_intent_blocked", task_id, reason=risk_finding.reason, matched_keywords=risk_finding.matched_keywords)
            result = MultiAgentRunResult(
                mode="multi_agent",
                success=False,
                requested_mode="multi_agent",
                executed_mode="blocked",
                final_answer=f"高风险意图被拦截: {risk_finding.reason}",
                decisions=[],
                execution_result={"success": False, "answer": f"高风险意图被拦截: {risk_finding.reason}", "blocked": True, "blocked_reason": risk_finding.reason},
                review_result={"approved": False, "reason": risk_finding.reason},
                fallback_chain=[],
            )
            self._trace("multi_agent_failed", task_id, reason=risk_finding.reason)
            return result

        decisions: list[AgentDecision] = []
        fallback_chain: list[str] = []

        coord_decision = self._coordinator.decide(query)
        decisions.append(coord_decision)
        self._trace("coordinator_decided", task_id, action=coord_decision.action, selected_mode=coord_decision.metadata.get("selected_mode"))

        analyst_decision = self._analyst.analyze(query, coord_decision)
        decisions.append(analyst_decision)
        self._trace("analyst_planned", task_id, plan_summary=analyst_decision.metadata.get("plan_summary", ""))

        selected_mode = coord_decision.metadata.get("selected_mode", "auto")
        fallback_chain.append(selected_mode)

        execution_result, executor_decision = self._executor.execute(
            query=query,
            selected_mode=selected_mode,
            generator=generator,
            provider=provider,
            fallback_to_mock=fallback_to_mock,
            task_id=task_id,
        )
        decisions.append(executor_decision)
        trace_detail: dict[str, Any] = {
            "success": execution_result.get("success", False),
            "executed_mode": execution_result.get("executed_mode", selected_mode),
        }
        tool_called = execution_result.get("tool_called")
        if tool_called:
            trace_detail["tool_called"] = tool_called
        tool_calls = execution_result.get("tool_calls")
        if tool_calls:
            trace_detail["tool_calls"] = tool_calls
        self._trace("executor_completed", task_id, **trace_detail)

        review_result, reviewer_decision = self._reviewer.review(execution_result, selected_mode)
        decisions.append(reviewer_decision)
        self._trace("reviewer_completed", task_id, approved=review_result["approved"])

        if not review_result["approved"] and review_result.get("suggested_fallback_mode"):
            fallback_mode = review_result["suggested_fallback_mode"]
            fallback_chain.append(fallback_mode)
            self._trace("multi_agent_fallback_started", task_id, original_mode=selected_mode, fallback_mode=fallback_mode)

            fb_execution_result, fb_executor_decision = self._executor.execute(
                query=query,
                selected_mode=fallback_mode,
                generator=generator,
                provider=provider,
                fallback_to_mock=fallback_to_mock,
                task_id=task_id,
            )
            fb_executor_decision.metadata["fallback"] = True
            decisions.append(fb_executor_decision)
            fb_trace_detail: dict[str, Any] = {
                "success": fb_execution_result.get("success", False),
                "executed_mode": fallback_mode,
                "fallback": True,
            }
            fb_tool_called = fb_execution_result.get("tool_called")
            if fb_tool_called:
                fb_trace_detail["tool_called"] = fb_tool_called
            fb_tool_calls = fb_execution_result.get("tool_calls")
            if fb_tool_calls:
                fb_trace_detail["tool_calls"] = fb_tool_calls
            self._trace("executor_completed", task_id, **fb_trace_detail)

            fb_review_result, fb_reviewer_decision = self._reviewer.review(fb_execution_result, fallback_mode)
            fb_reviewer_decision.metadata["fallback"] = True
            decisions.append(fb_reviewer_decision)
            self._trace("reviewer_completed", task_id, approved=fb_review_result["approved"], fallback=True)

            if fb_review_result["approved"]:
                execution_result = fb_execution_result
                review_result = fb_review_result
                selected_mode = fallback_mode
                self._trace("multi_agent_fallback_completed", task_id, fallback_mode=fallback_mode, success=True)
            else:
                self._trace("multi_agent_fallback_completed", task_id, fallback_mode=fallback_mode, success=False)

        final_answer = execution_result.get("answer", "") or execution_result.get("formatted_result", {}).get("summary", "")
        executed_mode = execution_result.get("executed_mode", selected_mode)
        success = execution_result.get("success", False)

        result = MultiAgentRunResult(
            mode="multi_agent",
            success=success,
            requested_mode="multi_agent",
            executed_mode=executed_mode,
            final_answer=str(final_answer),
            decisions=decisions,
            execution_result=execution_result,
            review_result=review_result,
            fallback_chain=fallback_chain,
        )

        if success:
            self._trace("multi_agent_completed", task_id, executed_mode=executed_mode)
        else:
            self._trace("multi_agent_failed", task_id, reason=final_answer or "执行失败")

        return result

    def _trace(self, event_type: str, task_id: str | None, **kwargs: Any) -> None:
        if self._trace_recorder and task_id:
            self._trace_recorder.record(event_type, task_id=task_id, detail=kwargs)
