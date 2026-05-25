from __future__ import annotations

from typing import Any


class GraphResumeAdapter:
    """Resume a Phase 2 graph_keyword approval from a durable checkpoint.

    This is intentionally a single-tool graph resume adapter. It does not
    implement native LangGraph Command resume or chained interrupts.
    """

    def __init__(
        self,
        checkpoint_store: Any,
        task_store: Any,
        approval_store: Any,
        gateway: Any,
        trace_recorder: Any | None = None,
        audit_recorder: Any | None = None,
    ) -> None:
        self._checkpoint_store = checkpoint_store
        self._task_store = task_store
        self._approval_store = approval_store
        self._gateway = gateway
        self._trace_recorder = trace_recorder
        self._audit_recorder = audit_recorder

    def resume(self, approval_id: str, approval: dict[str, Any]) -> dict[str, Any]:
        payload = approval.get("payload") or {}
        task_id = approval.get("task_id", "")

        if payload.get("mode") != "graph_keyword":
            return {
                "resumed": False,
                "approval_id": approval_id,
                "error": "unsupported graph resume mode",
                "error_type": "unsupported_graph_resume_mode",
            }

        checkpoint_id = payload.get("checkpoint_id")
        if not checkpoint_id:
            return {
                "resumed": False,
                "approval_id": approval_id,
                "error": "graph_keyword approval missing checkpoint_id",
                "error_type": "missing_checkpoint_id",
            }

        if payload.get("resumed"):
            return {
                "already_resumed": True,
                "approval_id": approval_id,
                "checkpoint_id": checkpoint_id,
                "resume_result": payload.get("resume_result"),
            }

        claimed = self._checkpoint_store.claim_for_resume(checkpoint_id, approval_id)
        if claimed is None:
            return self._handle_claim_failed(approval_id, checkpoint_id)

        interrupt_payload = payload.get("interrupt_payload") or claimed.get("pending_interrupt") or {}
        tool_name = interrupt_payload.get("tool_name") or payload.get("tool_name") or approval.get("tool_name", "")
        arguments = interrupt_payload.get("arguments") or payload.get("arguments") or {}

        self._trace("graph_resume_started", task_id, approval_id=approval_id, checkpoint_id=checkpoint_id, tool_name=tool_name)

        try:
            record = self._gateway.call(tool_name, arguments, task_id=task_id)
            resume_result = self._build_result(
                approval_id=approval_id,
                checkpoint_id=checkpoint_id,
                tool_name=tool_name,
                record=record,
                error=None,
            )
        except Exception as exc:
            resume_result = self._build_result(
                approval_id=approval_id,
                checkpoint_id=checkpoint_id,
                tool_name=tool_name,
                record=None,
                error=str(exc),
            )

        task_status = "completed" if resume_result.get("success") else "failed"
        self._task_store.update_task_status(task_id, task_status, result=resume_result)
        self._checkpoint_store.mark_resumed(
            checkpoint_id,
            resume_payload={"decision": "approved", "approval_id": approval_id},
            result_snapshot=resume_result,
        )
        self._approval_store.update_payload(
            approval_id,
            {
                "resumed": True,
                "resume_status": resume_result["resume_status"],
                "resume_result": resume_result,
                "approval_consumed": True,
            },
        )
        self._trace(
            "graph_resume_completed",
            task_id,
            approval_id=approval_id,
            checkpoint_id=checkpoint_id,
            tool_name=tool_name,
            success=resume_result.get("success"),
        )
        self._audit(
            "graph_resume_completed",
            task_id=task_id,
            approval_id=approval_id,
            tool_name=tool_name,
            action="graph_resume",
            outcome="success" if resume_result.get("success") else "failed",
            detail={"checkpoint_id": checkpoint_id, "resume_status": resume_result["resume_status"]},
        )
        return resume_result

    def _handle_claim_failed(self, approval_id: str, checkpoint_id: str) -> dict[str, Any]:
        checkpoint = self._checkpoint_store.get_checkpoint(checkpoint_id)
        if checkpoint is not None:
            status = checkpoint.get("status")
            if checkpoint.get("consumed") and status in ("resumed", "completed"):
                return {
                    "already_resumed": True,
                    "approval_id": approval_id,
                    "checkpoint_id": checkpoint_id,
                    "resume_result": checkpoint.get("result_snapshot"),
                }
            if status in ("cancelled", "expired"):
                return {
                    "resumed": False,
                    "approval_id": approval_id,
                    "checkpoint_id": checkpoint_id,
                    "error": f"checkpoint {status}",
                    "error_type": f"checkpoint_{status}",
                }
        return {
            "resumed": False,
            "approval_id": approval_id,
            "checkpoint_id": checkpoint_id,
            "error": "checkpoint claim failed",
            "error_type": "checkpoint_claim_failed",
        }

    @staticmethod
    def _build_result(
        *,
        approval_id: str,
        checkpoint_id: str,
        tool_name: str,
        record: Any | None,
        error: str | None,
    ) -> dict[str, Any]:
        success = bool(record and record.success and not error)
        result = {
            "mode": "graph_keyword",
            "graph_resumed": True,
            "resumed_from_approval": True,
            "approval_id": approval_id,
            "checkpoint_id": checkpoint_id,
            "tool_called": tool_name,
            "data": getattr(record, "result", None) if record is not None else None,
            "success": success,
            "approved_step_executed": record is not None,
            "approval_consumed": True,
            "resume_status": "completed" if success else "failed",
        }
        record_error = getattr(record, "error", None) if record is not None else None
        if error or record_error:
            result["error"] = error or record_error
        return result

    def _trace(self, event_type: str, task_id: str, **detail: Any) -> None:
        if self._trace_recorder is None:
            return
        try:
            self._trace_recorder.record(event_type, task_id=task_id, detail=detail)
        except Exception:
            pass

    def _audit(self, event_type: str, **kwargs: Any) -> None:
        if self._audit_recorder is None:
            return
        try:
            self._audit_recorder.record(event_type=event_type, **kwargs)
        except Exception:
            pass
