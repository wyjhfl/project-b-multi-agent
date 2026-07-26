from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth.dependencies import require_permission

router = APIRouter(prefix="/reflection", tags=["reflection"])


class ReflectionCheckRequest(BaseModel):
    task_result: dict[str, Any]
    trace_events: list[dict[str, Any]] | None = None
    audit_events: list[dict[str, Any]] | None = None


@router.post("/check")
async def run_reflection_check(request: ReflectionCheckRequest, _current_user=Depends(require_permission("reflection:run"))):
    from app.harness.reflection.self_check import SelfCheckEngine
    engine = SelfCheckEngine()
    result = engine.check(
        task_result=request.task_result,
        trace_events=request.trace_events,
        audit_events=request.audit_events,
    )
    return result.model_dump()
