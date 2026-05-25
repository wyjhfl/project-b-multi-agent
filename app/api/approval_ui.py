from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth.dependencies import require_permission
from app.harness.security.injection_guard import PromptInjectionGuard

router = APIRouter(prefix="/approvals", tags=["approvals-ui"])

_injection_guard = PromptInjectionGuard()


def _get_approval_store():
    from app.main import get_approval_store
    return get_approval_store()


def _get_task_store():
    from app.main import get_task_store
    return get_task_store()


def _get_trace_recorder():
    from app.main import get_trace_recorder
    return get_trace_recorder()


def _get_gateway():
    from app.main import get_gateway
    return get_gateway()


def _get_policy_engine():
    from app.main import get_policy_engine
    return get_policy_engine()


def _get_graph_checkpoint_store():
    from app.main import get_graph_checkpoint_store
    return get_graph_checkpoint_store()


def _record_audit(**kwargs) -> None:
    try:
        from app.main import get_audit_recorder
        get_audit_recorder().record(**kwargs)
    except Exception:
        pass


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
            graph_checkpoint_store=_get_graph_checkpoint_store(),
        )
        return service.resume(approval_id)
    except Exception as exc:
        return {"error": str(exc), "resumed": False}


@router.get("/summary")
async def get_approvals_summary(_current_user=Depends(require_permission("approvals:read"))):
    store = _get_approval_store()
    all_approvals = store.list_approvals(limit=100)

    pending_count = 0
    approved_count = 0
    rejected_count = 0
    expired_count = 0
    recent_pending = []
    recent_decided = []

    for a in all_approvals:
        status = a.get("status", "")
        if status == "pending":
            pending_count += 1
            if len(recent_pending) < 5:
                recent_pending.append(a)
        elif status == "approved":
            approved_count += 1
            if len(recent_decided) < 5:
                recent_decided.append(a)
        elif status == "rejected":
            rejected_count += 1
            if len(recent_decided) < 5:
                recent_decided.append(a)
        elif status == "expired":
            expired_count += 1

    return {
        "pending_count": pending_count,
        "approved_count": approved_count,
        "rejected_count": rejected_count,
        "expired_count": expired_count,
        "recent_pending": recent_pending,
        "recent_decided": recent_decided,
    }


@router.get("/{approval_id}/context")
async def get_approval_context(approval_id: str, _current_user=Depends(require_permission("approvals:read"))):
    store = _get_approval_store()
    approval = store.get_approval(approval_id)
    if approval is None:
        return {"error": f"审批请求 '{approval_id}' 不存在"}

    task_id = approval.get("task_id", "")
    task = None
    if task_id:
        try:
            task = _get_task_store().get_task(task_id)
        except Exception:
            pass

    timeline = []
    try:
        recorder = _get_trace_recorder()
        events = recorder.get_events(task_id=task_id)
        timeline = [
            {
                "event_type": e.event_type,
                "timestamp": e.timestamp.isoformat(),
                "detail": e.detail,
            }
            for e in events
        ]
    except Exception:
        pass

    payload = approval.get("payload") or {}
    resume_status = payload.get("resume_status")
    can_approve = approval.get("status") == "pending"
    can_reject = approval.get("status") == "pending"
    can_resume = approval.get("status") == "approved" and not payload.get("resumed")

    return {
        "approval": approval,
        "task": task,
        "payload": payload,
        "timeline": timeline,
        "resume_status": resume_status,
        "can_approve": can_approve,
        "can_reject": can_reject,
        "can_resume": can_resume,
    }


@router.post("/{approval_id}/resume")
async def manual_resume_approval(approval_id: str, _current_user=Depends(require_permission("approvals:decide"))):
    approval = _get_approval_store().get_approval(approval_id)
    if approval is None:
        return {"error": f"审批请求 '{approval_id}' 不存在"}

    if approval.get("status") != "approved":
        return {"error": f"审批状态为 {approval.get('status')}，无法恢复执行"}

    payload = approval.get("payload") or {}
    if payload.get("resumed"):
        return {
            "already_resumed": True,
            "approval_id": approval_id,
            "resume_result": payload.get("resume_result"),
        }

    result = _do_resume(approval_id)
    return {"approval_id": approval_id, "resume_result": result}
