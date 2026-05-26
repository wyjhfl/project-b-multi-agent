from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, PlainTextResponse

from app.auth.dependencies import require_permission
from app.core.config import settings
from app.harness.audit.retention import sanitize_audit_event_for_export

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


@router.get("/events/export")
async def export_audit_events(
    event_type: str | None = Query(default=None),
    task_id: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    outcome: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1),
    format: str = Query(default="jsonl"),
    _current_user=Depends(require_permission("audit:export")),
):
    if not settings.audit_export_enabled:
        return JSONResponse(status_code=403, content={"error": "audit_export_disabled"})
    if not settings.audit_export_redaction_enabled:
        return JSONResponse(status_code=403, content={"error": "audit_export_redaction_required"})

    export_format = (format or "").strip().lower()
    configured_format = (settings.audit_export_format or "jsonl").strip().lower()
    if export_format != "jsonl" or configured_format != "jsonl":
        return JSONResponse(status_code=400, content={"error": "unsupported_export_format"})

    capped_limit = min(limit, int(settings.audit_export_max_rows or 1000))
    store = _get_audit_store()
    events = store.query_events(
        event_type=event_type,
        task_id=task_id,
        outcome=outcome,
        severity=severity,
        limit=capped_limit,
    )
    lines = []
    for event in events:
        sanitized = sanitize_audit_event_for_export(event, redaction_enabled=True)
        lines.append(json.dumps(sanitized, ensure_ascii=False))
    payload = "\n".join(lines)
    return PlainTextResponse(content=payload, media_type="application/x-ndjson")


@router.get("/events/{event_id}")
async def get_audit_event(event_id: str, _current_user=Depends(require_permission("audit:read"))):
    store = _get_audit_store()
    result = store.get_event(event_id)
    if result is None:
        return {"error": f"审计事件 '{event_id}' 不存在"}
    return result
