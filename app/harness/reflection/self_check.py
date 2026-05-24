from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ReflectionResult(BaseModel):
    passed: bool
    score: float
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    checked_items: list[str] = Field(default_factory=list)


class SelfCheckEngine:
    def check(
        self,
        task_result: dict[str, Any],
        trace_events: list[dict[str, Any]] | None = None,
        audit_events: list[dict[str, Any]] | None = None,
    ) -> ReflectionResult:
        issues: list[str] = []
        suggestions: list[str] = []
        checked_items: list[str] = []

        self._check_result_success(task_result, issues, suggestions, checked_items)
        self._check_approval_consistency(task_result, issues, suggestions, checked_items)
        self._check_injection_consistency(task_result, trace_events, issues, suggestions, checked_items)
        self._check_tool_call_consistency(task_result, trace_events, issues, suggestions, checked_items)
        self._check_nl2sql_consistency(task_result, issues, suggestions, checked_items)
        self._check_audit_consistency(task_result, audit_events, issues, suggestions, checked_items)
        self._check_empty_result(task_result, issues, suggestions, checked_items)
        self._check_waiting_approval(task_result, issues, suggestions, checked_items)

        score = 1.0
        if issues:
            score = max(0.0, 1.0 - len(issues) * 0.2)
        passed = len(issues) == 0

        return ReflectionResult(
            passed=passed,
            score=round(score, 2),
            issues=issues,
            suggestions=suggestions,
            checked_items=checked_items,
        )

    def _check_result_success(self, task_result: dict, issues: list, suggestions: list, checked: list) -> None:
        checked.append("result_success")
        if task_result.get("requires_approval"):
            return
        if task_result.get("success") is False:
            issues.append("task_result.success is false")
            suggestions.append("检查工具调用或策略拦截原因")

    def _check_approval_consistency(self, task_result: dict, issues: list, suggestions: list, checked: list) -> None:
        checked.append("approval_consistency")
        if task_result.get("requires_approval") and not task_result.get("approval_id"):
            issues.append("requires_approval=true but no approval_id")
            suggestions.append("确保审批请求已创建并返回 approval_id")

    def _check_injection_consistency(self, task_result: dict, trace_events: list | None, issues: list, suggestions: list, checked: list) -> None:
        checked.append("injection_consistency")
        if trace_events:
            injection_blocked = any(
                e.get("event_type") == "prompt_injection_blocked"
                for e in trace_events
            )
            if injection_blocked and task_result.get("success") is True:
                issues.append("prompt_injection_blocked but task completed successfully")
                suggestions.append("注入被拦截后任务不应标记为成功")

    def _check_tool_call_consistency(self, task_result: dict, trace_events: list | None, issues: list, suggestions: list, checked: list) -> None:
        checked.append("tool_call_consistency")
        if trace_events:
            tool_failed = any(
                e.get("event_type") == "tool_called"
                and e.get("detail", {}).get("success") is False
                for e in trace_events
            )
            if tool_failed and task_result.get("success") is True:
                issues.append("tool_call failed but task claims success")
                suggestions.append("工具调用失败时任务不应标记为成功")

    def _check_nl2sql_consistency(self, task_result: dict, issues: list, suggestions: list, checked: list) -> None:
        checked.append("nl2sql_consistency")
        if task_result.get("guard_allowed") is False and task_result.get("success") is True:
            issues.append("nl2sql guard_allowed=false but execution success")
            suggestions.append("SQL 被拦截后不应执行成功")

    def _check_audit_consistency(self, task_result: dict, audit_events: list | None, issues: list, suggestions: list, checked: list) -> None:
        checked.append("audit_consistency")
        if audit_events is not None:
            security_events = [e for e in audit_events if e.get("event_type", "").startswith("prompt_injection")]
            if security_events and not any(e.get("event_type") == "prompt_injection_blocked" for e in security_events):
                issues.append("security event found but no prompt_injection_blocked audit")
                suggestions.append("安全事件应记录 prompt_injection_blocked 审计")

    def _has_presentable_result(self, task_result: dict) -> bool:
        answer = task_result.get("answer")
        if answer and str(answer).strip():
            return True
        summary = task_result.get("summary")
        if summary and str(summary).strip():
            return True
        formatted = task_result.get("formatted_result")
        if isinstance(formatted, dict) and formatted.get("summary") and str(formatted["summary"]).strip():
            return True
        execution = task_result.get("execution")
        if isinstance(execution, dict) and execution.get("rows"):
            return True
        chart = task_result.get("chart_spec")
        if chart and str(chart).strip():
            return True
        result_val = task_result.get("result")
        if result_val and str(result_val).strip() and result_val is not True and result_val is not False:
            return True
        return False

    def _check_empty_result(self, task_result: dict, issues: list, suggestions: list, checked: list) -> None:
        checked.append("empty_result")
        if not self._has_presentable_result(task_result):
            issues.append("no presentable result in task result")
            suggestions.append("任务结果应包含可展示内容（answer/summary/rows/chart/result）")

    def _check_waiting_approval(self, task_result: dict, issues: list, suggestions: list, checked: list) -> None:
        checked.append("waiting_approval")
        if task_result.get("requires_approval"):
            if "failed" in str(task_result.get("status", "")).lower():
                issues.append("waiting_approval task marked as failed")
                suggestions.append("等待审批的任务不应标记为 failed，应为 waiting_approval")
