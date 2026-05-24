from __future__ import annotations

from typing import Any

from app.harness.audit.recorder import AuditRecorder
from app.harness.gateway.tool_gateway import ToolGateway
from app.harness.policy.engine import PolicyEngine
from app.harness.policy.operation_whitelist import OperationWhitelist
from app.harness.trace.recorder import TraceRecorder
from app.storage.approval_store import SQLiteApprovalStore
from app.storage.task_store import SQLiteTaskStore


class ResumeVariableResolutionError(Exception):
    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"resume 变量解析失败: ${path}")


class ApprovalResumeService:
    def __init__(
        self,
        approval_store: SQLiteApprovalStore,
        task_store: SQLiteTaskStore,
        gateway: ToolGateway,
        trace_recorder: TraceRecorder | None = None,
        policy_engine: PolicyEngine | None = None,
        approval_store_for_new: SQLiteApprovalStore | None = None,
        audit_recorder: AuditRecorder | None = None,
    ) -> None:
        self._approval_store = approval_store
        self._task_store = task_store
        self._gateway = gateway
        self._trace_recorder = trace_recorder
        self._policy_engine = policy_engine
        self._approval_store_for_new = approval_store_for_new or approval_store
        self._audit_recorder = audit_recorder

    def resume(self, approval_id: str) -> dict[str, Any]:
        approval = self._approval_store.get_approval(approval_id)
        if approval is None:
            return {"error": f"审批请求 '{approval_id}' 不存在", "resumed": False}

        if approval.get("status") != "approved":
            return {"error": f"审批状态为 {approval.get('status')}，无法恢复执行", "resumed": False}

        payload = approval.get("payload") or {}
        task_id = approval.get("task_id", "")

        if payload.get("resumed"):
            return {
                "already_resumed": True,
                "approval_id": approval_id,
                "task_id": task_id,
                "resume_result": payload.get("resume_result"),
            }

        mode = payload.get("mode", "")

        self._trace("approval_resume_started", task_id, approval_id=approval_id, mode=mode)
        self._audit("approval_resume_started", task_id=task_id, approval_id=approval_id, action="resume", outcome="success", detail={"mode": mode})

        approval_tool_name = approval.get("tool_name", "")
        plan_steps = payload.get("plan", {}).get("steps") if mode == "multitool" else None
        whitelist = OperationWhitelist(self._gateway)
        integrity = whitelist.check_payload_integrity(payload, approval_tool_name, plan_steps)
        if not integrity.allowed:
            self._trace("approval_payload_tampered", task_id, approval_id=approval_id, reason=integrity.reason, operation=integrity.operation, error_type="approval_payload_tampered")
            self._audit("approval_payload_tampered", task_id=task_id, approval_id=approval_id, action="resume", outcome="blocked", severity="critical", reason=integrity.reason, detail={"operation": integrity.operation, "error_type": "approval_payload_tampered"})
            return {
                "resumed": False,
                "error": integrity.reason,
                "error_type": "approval_payload_tampered",
                "approval_id": approval_id,
                "approval_consumed": False,
            }

        if mode == "keyword":
            result = self._resume_keyword(approval_id, task_id, payload)
        elif mode == "multitool":
            result = self._resume_multitool(approval_id, task_id, payload)
        else:
            result = {
                "resumed": False,
                "error": f"不支持的 resume mode: {mode}",
                "approval_id": approval_id,
            }

        if result.get("approval_consumed"):
            resume_status = result.get("resume_status", "completed")
            self._approval_store.update_payload(approval_id, {
                "resumed": True,
                "resume_status": resume_status,
                "resume_result": result,
                "approval_consumed": True,
            })
        else:
            current_payload = (self._approval_store.get_approval(approval_id) or {}).get("payload") or {}
            attempt_count = current_payload.get("resume_attempt_count", 0) + 1
            self._approval_store.update_payload(approval_id, {
                "resume_status": "failed",
                "last_resume_result": result,
                "last_resume_error": result.get("error", ""),
                "resume_attempt_count": attempt_count,
            })

        return result

    def _resume_keyword(self, approval_id: str, task_id: str, payload: dict) -> dict[str, Any]:
        tool_name = payload.get("tool_name", "")
        arguments = payload.get("arguments", {})

        self._trace("approval_resume_tool_called", task_id, approval_id=approval_id, tool_name=tool_name, mode="keyword")

        try:
            record = self._gateway.call(tool_name, arguments)
            success = record.success
            data = record.result
            error = record.error

            task_status = "completed" if success else "failed"
            resume_result = {
                "resumed_from_approval": True,
                "approval_id": approval_id,
                "tool_called": tool_name,
                "data": data,
                "success": success,
                "approved_step_executed": True,
                "approval_consumed": success,
            }
            if error:
                resume_result["error"] = error

            self._task_store.update_task_status(task_id, task_status, result=resume_result)

            self._trace("approval_resume_completed", task_id, approval_id=approval_id, tool_name=tool_name, success=success)

            self._audit("approval_resume_completed", task_id=task_id, approval_id=approval_id, tool_name=tool_name, action="resume_keyword", outcome="success" if success else "failed", reason=error if error else None)

            return resume_result

        except Exception as exc:
            self._task_store.update_task_status(task_id, "failed", result={
                "resumed_from_approval": True,
                "approval_id": approval_id,
                "tool_called": tool_name,
                "success": False,
                "error": str(exc),
                "approved_step_executed": False,
                "approval_consumed": False,
            })
            self._trace("approval_resume_failed", task_id, approval_id=approval_id, error=str(exc))
            self._audit("approval_resume_failed", task_id=task_id, approval_id=approval_id, tool_name=tool_name, action="resume_keyword", outcome="failed", reason=str(exc))
            return {
                "resumed_from_approval": True,
                "approval_id": approval_id,
                "tool_called": tool_name,
                "success": False,
                "error": str(exc),
                "approved_step_executed": False,
                "approval_consumed": False,
            }

    def _resume_multitool(self, approval_id: str, task_id: str, payload: dict) -> dict[str, Any]:
        plan_data = payload.get("plan", {})
        step_id = payload.get("step_id", "")
        tool_name = payload.get("tool_name", "")
        arguments = payload.get("arguments", {})
        completed_step_ids = set(payload.get("completed_step_ids", []))
        completed_tool_calls = payload.get("tool_calls", [])

        saved = self._rebuild_saved(completed_tool_calls)

        self._trace("multitool_resume_started", task_id, approval_id=approval_id, step_id=step_id)

        try:
            resolved_args = self._resolve_arguments(arguments, saved)
        except ResumeVariableResolutionError as exc:
            result = {
                "mode": "multitool",
                "resumed_from_approval": True,
                "approval_id": approval_id,
                "resumed_step_id": step_id,
                "success": False,
                "error_type": "resume_variable_resolution_failed",
                "error_path": exc.path,
                "approved_step_executed": False,
                "approval_consumed": False,
            }
            self._trace("approval_resume_failed", task_id, approval_id=approval_id, error=f"变量解析失败: ${exc.path}")
            return result

        self._trace("multitool_resume_step_started", task_id, approval_id=approval_id, step_id=step_id, tool_name=tool_name)

        try:
            record = self._gateway.call(tool_name, resolved_args)
        except Exception as exc:
            result = {
                "mode": "multitool",
                "resumed_from_approval": True,
                "approval_id": approval_id,
                "resumed_step_id": step_id,
                "success": False,
                "error": str(exc),
                "approved_step_executed": False,
                "approval_consumed": False,
            }
            self._task_store.update_task_status(task_id, "failed", result=result)
            self._trace("multitool_resume_step_failed", task_id, approval_id=approval_id, step_id=step_id, error=str(exc))
            return result

        step_call = {
            "step_id": step_id,
            "tool_name": tool_name,
            "success": record.success,
            "result": record.result,
            "save_as": self._find_save_as(plan_data, step_id),
        }
        if record.error:
            step_call["error"] = record.error

        all_tool_calls = list(completed_tool_calls) + [step_call]

        if not record.success:
            result = {
                "mode": "multitool",
                "resumed_from_approval": True,
                "approval_id": approval_id,
                "resumed_step_id": step_id,
                "success": False,
                "error": record.error,
                "tool_calls": all_tool_calls,
                "approved_step_executed": True,
                "approval_consumed": False,
            }
            self._task_store.update_task_status(task_id, "failed", result=result)
            self._trace("multitool_resume_step_failed", task_id, approval_id=approval_id, step_id=step_id, error=record.error)
            return result

        self._trace("multitool_resume_step_completed", task_id, approval_id=approval_id, step_id=step_id, tool_name=tool_name)

        completed_step_ids.add(step_id)
        if step_call.get("save_as"):
            saved[step_call["save_as"]] = record

        steps = plan_data.get("steps", [])
        subsequent_result = self._execute_subsequent_steps(
            task_id, approval_id, steps, completed_step_ids, saved, all_tool_calls
        )

        if subsequent_result.get("waiting_approval"):
            final_result = {
                "mode": "multitool",
                "resumed_from_approval": True,
                "approval_id": approval_id,
                "resumed_step_id": step_id,
                "success": False,
                "waiting_approval": True,
                "new_approval_id": subsequent_result.get("new_approval_id"),
                "tool_calls": subsequent_result.get("tool_calls", all_tool_calls),
                "approved_step_executed": True,
                "approval_consumed": True,
                "resume_status": "waiting_approval",
            }
            self._task_store.update_task_status(task_id, "waiting_approval", result=final_result)
            self._trace("multitool_resume_waiting_approval", task_id, approval_id=approval_id, new_approval_id=subsequent_result.get("new_approval_id"))
            return final_result

        all_tool_calls = subsequent_result.get("tool_calls", all_tool_calls)
        overall_success = subsequent_result.get("success", True)

        if subsequent_result.get("dependency_error"):
            task_status = "failed"
            resume_status = "downstream_failed"
        elif not overall_success:
            task_status = "failed"
            resume_status = "downstream_failed"
        else:
            task_status = "completed"
            resume_status = "completed"

        final_result = {
            "mode": "multitool",
            "resumed_from_approval": True,
            "approval_id": approval_id,
            "resumed_step_id": step_id,
            "success": overall_success,
            "tool_calls": all_tool_calls,
            "approved_step_executed": True,
            "approval_consumed": True,
            "resume_status": resume_status,
        }
        if not overall_success and subsequent_result.get("error"):
            final_result["error"] = subsequent_result["error"]
        if subsequent_result.get("error_type"):
            final_result["error_type"] = subsequent_result["error_type"]
        if subsequent_result.get("missing_depends_on"):
            final_result["missing_depends_on"] = subsequent_result["missing_depends_on"]

        self._task_store.update_task_status(task_id, task_status, result=final_result)
        self._trace("multitool_resume_completed", task_id, approval_id=approval_id, success=overall_success)
        self._audit("approval_resume_completed", task_id=task_id, approval_id=approval_id, tool_name=tool_name, action="resume_multitool", outcome="success" if overall_success else "failed", reason=final_result.get("error"), detail={"resume_status": resume_status})

        return final_result

    def _execute_subsequent_steps(
        self,
        task_id: str,
        original_approval_id: str,
        steps: list[dict],
        completed_step_ids: set[str],
        saved: dict[str, Any],
        tool_calls: list[dict],
    ) -> dict[str, Any]:
        for step_data in steps:
            step_id = step_data.get("step_id", "")
            if step_id in completed_step_ids:
                continue

            tool_name = step_data.get("tool_name", "")
            arguments = step_data.get("arguments", {})
            save_as = step_data.get("save_as")
            depends_on = step_data.get("depends_on") or []

            missing = [d for d in depends_on if d not in completed_step_ids]
            if missing:
                self._trace("multitool_resume_step_failed", task_id, approval_id=original_approval_id, step_id=step_id, error_type="resume_dependency_not_satisfied", missing_depends_on=missing)
                return {
                    "success": False,
                    "error": f"步骤 {step_id} 依赖未满足: {missing}",
                    "error_type": "resume_dependency_not_satisfied",
                    "missing_depends_on": missing,
                    "tool_calls": tool_calls,
                    "dependency_error": True,
                }

            spec = self._gateway.get_tool(tool_name)
            if spec is None:
                self._trace("operation_whitelist_blocked", task_id, approval_id=original_approval_id, step_id=step_id, tool_name=tool_name, mode="multitool_resume", reason=f"工具 '{tool_name}' 未在 ToolGateway 注册")
                return {
                    "success": False,
                    "error": f"步骤 {step_id} 工具 '{tool_name}' 未注册，不允许执行",
                    "error_type": "operation_not_whitelisted",
                    "tool_calls": tool_calls,
                }

            if spec and self._policy_engine:
                decision = self._policy_engine.evaluate(tool_name, risk_level=spec.risk_level)
                if not decision["allowed"]:
                    if decision.get("requires_approval") and self._approval_store_for_new is not None:
                        new_approval = self._approval_store_for_new.create_approval(
                            task_id=task_id,
                            tool_name=tool_name,
                            action=f"多工具恢复步骤 {step_id} 调用 {tool_name}",
                            risk_level=spec.risk_level,
                            impact_scope=spec.permission_scope,
                            agent_reason=decision["reason"],
                            payload={
                                "mode": "multitool",
                                "query": "",
                                "step_id": step_id,
                                "tool_name": tool_name,
                                "arguments": arguments,
                                "plan": {"steps": steps},
                                "completed_step_ids": list(completed_step_ids),
                                "tool_calls": tool_calls,
                            },
                        )
                        return {
                            "waiting_approval": True,
                            "new_approval_id": new_approval.approval_id,
                            "tool_calls": tool_calls,
                        }
                    return {
                        "success": False,
                        "error": f"步骤 {step_id} 被策略拦截: {decision['reason']}",
                        "tool_calls": tool_calls,
                    }

            try:
                resolved_args = self._resolve_arguments(arguments, saved)
            except ResumeVariableResolutionError as exc:
                return {
                    "success": False,
                    "error": f"步骤 {step_id} 变量解析失败: ${exc.path}",
                    "tool_calls": tool_calls,
                }

            self._trace("multitool_resume_step_started", task_id, approval_id=original_approval_id, step_id=step_id, tool_name=tool_name)

            record = self._gateway.call(tool_name, resolved_args)

            call_data = {
                "step_id": step_id,
                "tool_name": tool_name,
                "success": record.success,
                "result": record.result,
                "save_as": save_as,
            }
            if record.error:
                call_data["error"] = record.error
            tool_calls.append(call_data)

            if not record.success:
                self._trace("multitool_resume_step_failed", task_id, approval_id=original_approval_id, step_id=step_id, error=record.error)
                return {
                    "success": False,
                    "error": f"步骤 {step_id} 工具调用失败: {record.error}",
                    "tool_calls": tool_calls,
                }

            self._trace("multitool_resume_step_completed", task_id, approval_id=original_approval_id, step_id=step_id, tool_name=tool_name)

            if save_as:
                saved[save_as] = record
            completed_step_ids.add(step_id)

        return {"success": True, "tool_calls": tool_calls}

    def _rebuild_saved(self, tool_calls: list[dict]) -> dict[str, Any]:
        saved: dict[str, Any] = {}
        for tc in tool_calls:
            key = tc.get("save_as") or tc.get("step_id")
            if key and tc.get("success") and tc.get("result") is not None:
                saved[key] = tc
        return saved

    def _resolve_arguments(self, arguments: dict[str, Any], saved: dict[str, Any]) -> dict[str, Any]:
        return self._resolve_value(arguments, saved)

    def _resolve_value(self, value: Any, saved: dict[str, Any]) -> Any:
        if isinstance(value, str) and value.startswith("$"):
            path = value[1:]
            result = self._resolve_variable(path, saved)
            if result is None:
                raise ResumeVariableResolutionError(path)
            return result
        elif isinstance(value, dict):
            return {k: self._resolve_value(v, saved) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._resolve_value(item, saved) for item in value]
        return value

    def _resolve_variable(self, path: str, saved: dict[str, Any]) -> Any:
        parts = path.split(".")
        if len(parts) < 2:
            return None
        var_name = parts[0]
        record = saved.get(var_name)
        if record is None:
            return None
        current: Any = record
        for part in parts[1:]:
            if isinstance(current, dict):
                if part not in current:
                    return None
                current = current[part]
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                return None
        return current

    def _find_save_as(self, plan_data: dict, step_id: str) -> str | None:
        for step in plan_data.get("steps", []):
            if step.get("step_id") == step_id:
                return step.get("save_as")
        return None

    def _trace(self, event_type: str, task_id: str, **kwargs: Any) -> None:
        if self._trace_recorder and task_id:
            self._trace_recorder.record(event_type, task_id=task_id, detail=kwargs)

    def _audit(self, event_type: str, **kwargs: Any) -> None:
        if self._audit_recorder:
            try:
                self._audit_recorder.record(event_type=event_type, **kwargs)
            except Exception:
                pass
