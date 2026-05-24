from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.harness.security.injection_guard import PromptInjectionGuard

router = APIRouter(prefix="/approvals", tags=["approvals"])

_injection_guard = PromptInjectionGuard()


class DecideRequest(BaseModel):
    decided_by: str = Field(default="admin", description="决策人")
    reason: str = Field(default="", description="决策原因")
    auto_resume: bool = Field(default=True, description="审批通过后是否自动恢复执行")


def _get_approval_store():
    from app.main import get_approval_store
    return get_approval_store()


def _get_task_store():
    from app.main import get_task_store
    return get_task_store()


def _get_gateway():
    from app.main import get_gateway
    return get_gateway()


def _get_policy_engine():
    from app.main import get_policy_engine
    return get_policy_engine()


def _get_trace_recorder():
    from app.main import get_trace_recorder
    return get_trace_recorder()


def _record_trace(event_type: str, task_id: str, detail: dict) -> None:
    try:
        recorder = _get_trace_recorder()
        recorder.record(event_type, task_id=task_id, detail=detail)
    except Exception:
        pass


def _get_audit_recorder():
    from app.main import get_audit_recorder
    return get_audit_recorder()


def _record_audit(**kwargs) -> None:
    try:
        _get_audit_recorder().record(**kwargs)
    except Exception:
        pass


def _cancel_task(task_id: str, approval_id: str, reason: str) -> dict | None:
    try:
        task_store = _get_task_store()
        return task_store.update_task_status(
            task_id,
            "cancelled",
            result={
                "approval_rejected": True,
                "approval_id": approval_id,
                "decision_reason": reason,
            },
        )
    except Exception:
        return None


def _do_resume(approval_id: str) -> dict | None:
    try:
        store = _get_approval_store()
        approval = store.get_approval(approval_id)
        if approval is None:
            return {"error": f"审批请求 '{approval_id}' 不存在", "resumed": False}

        payload = approval.get("payload") or {}
        payload_finding = _injection_guard.check_payload(payload)
        if payload_finding.action == "block":
            _record_trace("resume_blocked_by_policy", task_id=approval.get("task_id", ""), detail={
                "approval_id": approval_id,
                "severity": payload_finding.severity,
                "reason": payload_finding.reason,
                "matched_patterns": payload_finding.matched_patterns,
            })
            _record_audit(
                event_type="resume_blocked_by_policy",
                task_id=approval.get("task_id", ""),
                approval_id=approval_id,
                action="resume",
                outcome="blocked",
                severity=payload_finding.severity,
                reason=payload_finding.reason,
                detail={"matched_patterns": payload_finding.matched_patterns},
            )
            return {
                "error": f"resume payload 包含注入内容: {payload_finding.reason}",
                "resumed": False,
                "error_type": "prompt_injection_blocked",
            }

        from app.services.approval_resume import ApprovalResumeService
        service = ApprovalResumeService(
            approval_store=store,
            task_store=_get_task_store(),
            gateway=_get_gateway(),
            trace_recorder=_get_trace_recorder(),
            policy_engine=_get_policy_engine(),
            approval_store_for_new=store,
        )
        return service.resume(approval_id)
    except Exception as exc:
        return {"error": str(exc), "resumed": False}


@router.get("")
async def list_approvals(
    status: str | None = Query(default=None),
    limit: int = Query(default=20),
):
    store = _get_approval_store()
    return store.list_approvals(status=status, limit=limit)


@router.get("/{approval_id}")
async def get_approval(approval_id: str):
    store = _get_approval_store()
    result = store.get_approval(approval_id)
    if result is None:
        return {"error": f"审批请求 '{approval_id}' 不存在"}
    return result


@router.post("/{approval_id}/approve")
async def approve_approval(approval_id: str, req: DecideRequest = DecideRequest()):
    store = _get_approval_store()
    previous = store.get_approval(approval_id)
    if previous is None:
        return {"error": f"审批请求 '{approval_id}' 不存在"}

    previous_status = previous.get("status", "unknown")
    payload = previous.get("payload") or {}

    if req.reason:
        reason_finding = _injection_guard.check_text(req.reason)
        if reason_finding.detected:
            _record_trace("prompt_injection_detected", task_id=previous.get("task_id", ""), detail={
                "approval_id": approval_id,
                "source": "approve_reason",
                "severity": reason_finding.severity,
                "reason": reason_finding.reason,
                "matched_patterns": reason_finding.matched_patterns,
                "action": reason_finding.action,
            })
            _record_audit(
                event_type="prompt_injection_detected",
                task_id=previous.get("task_id", ""),
                approval_id=approval_id,
                actor=req.decided_by,
                action="approve_reason",
                outcome="warn",
                severity=reason_finding.severity,
                reason=reason_finding.reason,
                detail={"matched_patterns": reason_finding.matched_patterns, "source": "approve_reason"},
            )

    if payload.get("resumed"):
        return {
            "status": previous_status,
            "approval_id": approval_id,
            "already_resumed": True,
            "resume_result": payload.get("resume_result"),
        }

    if previous_status == "approved" and not payload.get("resumed"):
        resume_result = _do_resume(approval_id) if req.auto_resume else None
        return {
            "status": "approved",
            "approval_id": approval_id,
            "already_decided": True,
            "resume_result": resume_result,
        }

    result = store.decide_approval(
        approval_id=approval_id,
        approved=True,
        decided_by=req.decided_by,
        reason=req.reason,
    )

    if result.get("already_decided"):
        _record_trace("approval_decision_ignored", task_id=previous.get("task_id", ""), detail={
            "approval_id": approval_id,
            "previous_status": previous_status,
            "attempted_action": "approve",
            "decided_by": req.decided_by,
        })
        return result

    _record_trace("approval_approved", task_id=result.get("task_id", ""), detail={
        "approval_id": approval_id,
        "previous_status": previous_status,
        "new_status": "approved",
        "decided_by": req.decided_by,
        "decision_reason": req.reason,
    })

    _record_audit(
        event_type="approval_approved",
        task_id=result.get("task_id", ""),
        approval_id=approval_id,
        actor=req.decided_by,
        action="approve",
        outcome="approved",
        reason=req.reason,
        detail={"previous_status": previous_status},
    )

    resume_result = None
    if req.auto_resume:
        resume_result = _do_resume(approval_id)

    response = dict(result)
    response["resume_result"] = resume_result
    return response


@router.post("/{approval_id}/reject")
async def reject_approval(approval_id: str, req: DecideRequest = DecideRequest()):
    store = _get_approval_store()
    previous = store.get_approval(approval_id)
    if previous is None:
        return {"error": f"审批请求 '{approval_id}' 不存在"}

    previous_status = previous.get("status", "unknown")
    result = store.decide_approval(
        approval_id=approval_id,
        approved=False,
        decided_by=req.decided_by,
        reason=req.reason,
    )

    if result.get("already_decided"):
        _record_trace("approval_decision_ignored", task_id=previous.get("task_id", ""), detail={
            "approval_id": approval_id,
            "previous_status": previous_status,
            "attempted_action": "reject",
            "decided_by": req.decided_by,
        })
        return result

    _record_trace("approval_rejected", task_id=result.get("task_id", ""), detail={
        "approval_id": approval_id,
        "previous_status": previous_status,
        "new_status": "rejected",
        "decided_by": req.decided_by,
        "decision_reason": req.reason,
    })

    _record_audit(
        event_type="approval_rejected",
        task_id=result.get("task_id", ""),
        approval_id=approval_id,
        actor=req.decided_by,
        action="reject",
        outcome="rejected",
        reason=req.reason,
        detail={"previous_status": previous_status},
    )

    task_id = result.get("task_id", "")
    cancellation_result = None
    if task_id:
        cancellation_result = _cancel_task(task_id, approval_id, req.reason)
        _record_trace("task_cancelled_by_approval", task_id=task_id, detail={
            "approval_id": approval_id,
            "decided_by": req.decided_by,
            "decision_reason": req.reason,
        })

    response = dict(result)
    response["cancellation_result"] = cancellation_result
    return response
