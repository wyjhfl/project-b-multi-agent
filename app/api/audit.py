from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import require_permission

router = APIRouter(prefix="/audit", tags=["audit"])


def _get_audit_store():
    from app.main import get_audit_store
    return get_audit_store()


@router.get("/events")
async def list_audit_events(
    event_type: str | None = Query(default=None),
    actor: str | None = Query(default=None),
    task_id: str | None = Query(default=None),
    approval_id: str | None = Query(default=None),
    outcome: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    start_time: str | None = Query(default=None, description="ISO UTC 起始时间"),
    end_time: str | None = Query(default=None, description="ISO UTC 结束时间"),
    limit: int = Query(default=100),
    _current_user=Depends(require_permission("audit:read")),
):
    store = _get_audit_store()
    return store.query_events(
        event_type=event_type,
        actor=actor,
        task_id=task_id,
        approval_id=approval_id,
        outcome=outcome,
        severity=severity,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )


@router.get("/events/{event_id}")
async def get_audit_event(event_id: str, _current_user=Depends(require_permission("audit:read"))):
    store = _get_audit_store()
    result = store.get_event(event_id)
    if result is None:
        return {"error": f"审计事件 '{event_id}' 不存在"}
    return result
