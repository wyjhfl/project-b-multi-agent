from __future__ import annotations

from typing import Any

from app.agent.nodes.multitool_planner import MultiToolPlan, MultiToolPlanner
from app.harness.gateway.tool_gateway import ToolGateway
from app.harness.policy.engine import PolicyEngine
from app.harness.trace.recorder import TraceRecorder
from app.models.schemas import ToolCallRecord


class MultiToolPipeline:
    def __init__(
        self,
        gateway: ToolGateway,
        policy_engine: PolicyEngine | None = None,
        trace_recorder: TraceRecorder | None = None,
        approval_store: Any | None = None,
        audit_recorder: Any | None = None,
    ) -> None:
        self._gateway = gateway
        self._policy_engine = policy_engine
        self._trace_recorder = trace_recorder
        self._approval_store = approval_store
        self._audit_recorder = audit_recorder
        self._planner = MultiToolPlanner()

    def run(self, query: str, task_id: str | None = None) -> dict[str, Any]:
        plan = self._planner.plan(query)

        if not plan.matched:
            return {
                "mode": "multitool",
                "success": False,
                "intent": "",
                "answer": "未匹配多工具任务",
                "plan": plan.model_dump(),
                "tool_calls": [],
            }

        saved: dict[str, ToolCallRecord] = {}
        completed_step_ids: set[str] = set()
        tool_calls: list[dict[str, Any]] = []

        for step in plan.steps:
            missing = self._check_depends_on(step.depends_on, completed_step_ids)
            if missing is not None:
                self._trace("multitool_step_failed", task_id, step_id=step.step_id, error_type="dependency_not_satisfied", missing_depends_on=missing)
                return {
                    "mode": "multitool",
                    "success": False,
                    "intent": plan.intent,
                    "error_type": "dependency_not_satisfied",
                    "missing_depends_on": missing,
                    "answer": f"步骤 {step.step_id} 依赖未满足: {missing}",
                    "plan": plan.model_dump(),
                    "tool_calls": tool_calls,
                    "failed_step": step.step_id,
                }

            spec = self._gateway.get_tool(step.tool_name)
            if spec is None:
                self._trace("operation_whitelist_blocked", task_id, step_id=step.step_id, tool_name=step.tool_name, mode="multitool", reason=f"工具 '{step.tool_name}' 未在 ToolGateway 注册")
                self._audit("operation_whitelist_blocked", task_id=task_id, tool_name=step.tool_name, action="multitool_step", outcome="blocked", severity="high", reason=f"工具 '{step.tool_name}' 未在 ToolGateway 注册", detail={"step_id": step.step_id, "mode": "multitool"})
                call_data = {
                    "step_id": step.step_id,
                    "tool_name": step.tool_name,
                    "arguments": step.arguments,
                    "success": False,
                    "result": None,
                    "latency_ms": 0.0,
                    "error": f"工具 '{step.tool_name}' 未在 ToolGateway 注册",
                    "policy_blocked": True,
                }
                tool_calls.append(call_data)
                return {
                    "mode": "multitool",
                    "success": False,
                    "intent": plan.intent,
                    "error_type": "operation_not_whitelisted",
                    "answer": f"步骤 {step.step_id} 工具 '{step.tool_name}' 未注册，不允许执行",
                    "plan": plan.model_dump(),
                    "tool_calls": tool_calls,
                    "failed_step": step.step_id,
                }

            if spec and self._policy_engine:
                decision = self._policy_engine.evaluate(step.tool_name, risk_level=spec.risk_level)
                if not decision["allowed"]:
                    if decision.get("requires_approval") and self._approval_store is not None:
                        approval = self._approval_store.create_approval(
                            task_id=task_id or "",
                            tool_name=step.tool_name,
                            action=f"多工具步骤 {step.step_id} 调用 {step.tool_name}",
                            risk_level=spec.risk_level,
                            impact_scope=spec.permission_scope,
                            agent_reason=decision["reason"],
                            payload={
                                "mode": "multitool",
                                "query": query,
                                "step_id": step.step_id,
                                "tool_name": step.tool_name,
                                "arguments": step.arguments,
                                "plan": plan.model_dump(),
                                "completed_step_ids": list(completed_step_ids),
                                "tool_calls": tool_calls,
                            },
                        )
                        self._trace("multitool_approval_required", task_id, step_id=step.step_id, tool_name=step.tool_name, approval_id=approval.approval_id, reason=decision["reason"])
                        self._audit("approval_requested", task_id=task_id, approval_id=approval.approval_id, tool_name=step.tool_name, action="multitool_step", outcome="waiting_approval", reason=decision["reason"], detail={"step_id": step.step_id})
                        call_data = {
                            "step_id": step.step_id,
                            "tool_name": step.tool_name,
                            "arguments": step.arguments,
                            "success": False,
                            "result": None,
                            "latency_ms": 0.0,
                            "error": decision["reason"],
                            "policy_blocked": True,
                            "requires_approval": True,
                            "approval_id": approval.approval_id,
                        }
                        tool_calls.append(call_data)
                        return {
                            "mode": "multitool",
                            "success": False,
                            "intent": plan.intent,
                            "error_type": "approval_required",
                            "requires_approval": True,
                            "approval_id": approval.approval_id,
                            "answer": f"步骤 {step.step_id} 需要人工审批: {decision['reason']}",
                            "plan": plan.model_dump(),
                            "tool_calls": tool_calls,
                            "failed_step": step.step_id,
                        }
                    self._trace("multitool_policy_blocked", task_id, step_id=step.step_id, tool_name=step.tool_name, reason=decision["reason"])
                    call_data = {
                        "step_id": step.step_id,
                        "tool_name": step.tool_name,
                        "arguments": step.arguments,
                        "success": False,
                        "result": None,
                        "latency_ms": 0.0,
                        "error": decision["reason"],
                        "policy_blocked": True,
                    }
                    tool_calls.append(call_data)
                    return {
                        "mode": "multitool",
                        "success": False,
                        "intent": plan.intent,
                        "error_type": "policy_blocked",
                        "answer": f"步骤 {step.step_id} 被策略拦截: {decision['reason']}",
                        "plan": plan.model_dump(),
                        "tool_calls": tool_calls,
                        "failed_step": step.step_id,
                    }

            try:
                resolved_args = self._resolve_arguments(step.arguments, saved)
            except VariableResolutionError as exc:
                error_path = exc.path
                self._trace("multitool_step_failed", task_id, step_id=step.step_id, error_type="variable_resolution_failed", error_path=error_path)
                return {
                    "mode": "multitool",
                    "success": False,
                    "intent": plan.intent,
                    "error_type": "variable_resolution_failed",
                    "error_path": error_path,
                    "answer": f"步骤 {step.step_id} 变量解析失败: ${error_path}",
                    "plan": plan.model_dump(),
                    "tool_calls": tool_calls,
                    "failed_step": step.step_id,
                }

            self._trace("multitool_step_started", task_id, step_id=step.step_id, tool_name=step.tool_name)

            record = self._gateway.call(step.tool_name, resolved_args)

            call_data = {
                "step_id": step.step_id,
                "tool_name": record.tool_name,
                "arguments": record.arguments,
                "success": record.success,
                "result": record.result,
                "latency_ms": record.latency_ms,
                "error": record.error,
                "retry_count": record.retry_count,
                "save_as": step.save_as,
            }
            tool_calls.append(call_data)

            if not record.success:
                self._trace("multitool_step_failed", task_id, step_id=step.step_id, tool_name=step.tool_name, error_type="tool_call_failed", error=record.error)
                return {
                    "mode": "multitool",
                    "success": False,
                    "intent": plan.intent,
                    "error_type": "tool_call_failed",
                    "answer": f"步骤 {step.step_id} 工具调用失败: {record.error}",
                    "plan": plan.model_dump(),
                    "tool_calls": tool_calls,
                    "failed_step": step.step_id,
                }

            self._trace("multitool_step_completed", task_id, step_id=step.step_id, tool_name=step.tool_name)

            if step.save_as:
                saved[step.save_as] = record

            completed_step_ids.add(step.step_id)

        answer = self._generate_answer(plan, saved)

        return {
            "mode": "multitool",
            "success": True,
            "intent": plan.intent,
            "answer": answer,
            "plan": plan.model_dump(),
            "tool_calls": tool_calls,
        }

    def _check_depends_on(
        self,
        depends_on: list[str],
        completed_step_ids: set[str],
    ) -> list[str] | None:
        missing = [dep_id for dep_id in depends_on if dep_id not in completed_step_ids]
        if missing:
            return missing
        return None

    def _resolve_arguments(
        self,
        arguments: dict[str, Any],
        saved: dict[str, ToolCallRecord],
    ) -> dict[str, Any]:
        return self._resolve_value(arguments, saved)

    def _resolve_value(self, value: Any, saved: dict[str, ToolCallRecord]) -> Any:
        if isinstance(value, str) and value.startswith("$"):
            path = value[1:]
            result = self._resolve_variable(path, saved)
            if result is _UNRESOLVED:
                raise VariableResolutionError(path)
            return result
        elif isinstance(value, dict):
            return {k: self._resolve_value(v, saved) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._resolve_value(item, saved) for item in value]
        return value

    def _resolve_variable(
        self,
        path: str,
        saved: dict[str, ToolCallRecord],
    ) -> Any:
        parts = path.split(".")
        if len(parts) < 2:
            return _UNRESOLVED

        var_name = parts[0]
        record = saved.get(var_name)
        if record is None:
            return _UNRESOLVED

        current: Any = record
        for part in parts[1:]:
            if isinstance(current, dict):
                if part not in current:
                    return _UNRESOLVED
                current = current[part]
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                return _UNRESOLVED
        return current

    def _generate_answer(self, plan: MultiToolPlan, saved: dict[str, ToolCallRecord]) -> str:
        if plan.intent == "gmv_mom":
            date_info = saved.get("date_info")
            current_gmv = saved.get("current_gmv")
            mom_change = saved.get("mom_change")

            date_str = date_info.result.get("date", "未知") if date_info and date_info.result else "未知"
            gmv_val = current_gmv.result.get("gmv", 0) if current_gmv and current_gmv.result else 0
            change_val = mom_change.result.get("result", 0) if mom_change and mom_change.result else 0

            return f"截至 {date_str}，当前 GMV 为 {gmv_val}，环比变化 {change_val}%（上期基线 mock=100000）"

        elif plan.intent == "refund_rule":
            refund_rule = saved.get("refund_rule")
            refund_rate = saved.get("refund_rate")

            rule_text = refund_rule.result.get("rule", "未知") if refund_rule and refund_rule.result else "未知"
            rate_val = refund_rate.result.get("refund_rate_percent", 0) if refund_rate and refund_rate.result else 0

            return f"退款规则：{rule_text}；当前退款率：{rate_val}%"

        elif plan.intent == "promotion_rule":
            promotion_rule = saved.get("promotion_rule")

            rule_text = promotion_rule.result.get("rule", "未知") if promotion_rule and promotion_rule.result else "未知"

            return f"促销规则：{rule_text}"

        return plan.response_template

    def _trace(self, event_type: str, task_id: str | None, **kwargs: Any) -> None:
        if self._trace_recorder and task_id:
            self._trace_recorder.record(event_type, task_id=task_id, detail=kwargs)

    def _audit(self, event_type: str, **kwargs: Any) -> None:
        if self._audit_recorder:
            try:
                self._audit_recorder.record(event_type=event_type, **kwargs)
            except Exception:
                pass


_UNRESOLVED = object()


class VariableResolutionError(Exception):
    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"变量解析失败: ${path}")
