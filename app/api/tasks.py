from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.agent.graph.kernel import AgentKernel
from app.auth.dependencies import require_permission
from app.harness.security.injection_guard import PromptInjectionGuard
from app.models.schemas import TaskRun, TaskStatus

router = APIRouter(prefix="/tasks", tags=["tasks"])

_injection_guard = PromptInjectionGuard()


class CreateTaskRequest(BaseModel):
    query: str
    mode: str = "keyword"
    generator: str = "mock"
    provider: str | None = None
    fallback_to_mock: bool = True
    session_id: str | None = None


class CreateTaskResponse(BaseModel):
    task_id: str
    query: str
    status: str
    result: dict | None = None
    error: str | None = None
    persistence_error: str | None = None


def _get_kernel() -> AgentKernel:
    from app.main import get_kernel
    return get_kernel()


def _get_trace_recorder():
    from app.main import get_trace_recorder
    return get_trace_recorder()


def _get_task_store():
    from app.main import get_task_store
    return get_task_store()


def _get_audit_recorder():
    from app.main import get_audit_recorder
    return get_audit_recorder()


@router.post("", response_model=CreateTaskResponse)
async def create_task(req: CreateTaskRequest, _current_user=Depends(require_permission("tasks:create"))):
    finding = _injection_guard.check_text(req.query)
    if finding.action == "block":
        task_id = str(uuid.uuid4())
        recorder = _get_trace_recorder()
        recorder.record("prompt_injection_blocked", task_id=task_id, detail={
            "query": req.query,
            "severity": finding.severity,
            "reason": finding.reason,
            "matched_patterns": finding.matched_patterns,
            "mode": req.mode,
        })
        _get_audit_recorder().record(
            event_type="prompt_injection_blocked",
            task_id=task_id,
            action="create_task",
            outcome="blocked",
            severity=finding.severity,
            reason=finding.reason,
            detail={"matched_patterns": finding.matched_patterns, "mode": req.mode, "query": req.query},
        )
        return CreateTaskResponse(
            task_id=task_id,
            query=req.query,
            status=TaskStatus.failed.value,
            result={
                "error_type": "prompt_injection_blocked",
                "injection_finding": {
                    "detected": finding.detected,
                    "severity": finding.severity,
                    "reason": finding.reason,
                    "matched_patterns": finding.matched_patterns,
                    "action": finding.action,
                },
            },
        )

    task = TaskRun(
        task_id=str(uuid.uuid4()),
        query=req.query,
        status=TaskStatus.created,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    kernel = _get_kernel()
    session_id = req.session_id or task.task_id
    task = await kernel.run_with_options(
        task,
        mode=req.mode,
        generator=req.generator,
        provider=req.provider,
        fallback_to_mock=req.fallback_to_mock,
        session_id=session_id,
    )

    persistence_error: str | None = None
    try:
        store = _get_task_store()
        store.save_task(task, mode=req.mode)
    except Exception as exc:
        persistence_error = str(exc)
        recorder = _get_trace_recorder()
        recorder.record("task_persist_failed", task_id=task.task_id, detail={"error": persistence_error})

    return CreateTaskResponse(
        task_id=task.task_id,
        query=task.query,
        status=task.status.value,
        result=task.result,
        error=task.error,
        persistence_error=persistence_error,
    )


async def _list_tasks(limit: int = 20):
    try:
        store = _get_task_store()
        return store.list_tasks(limit=limit)
    except Exception:
        return []


@router.get("")
async def get_tasks(limit: int = 20, _current_user=Depends(require_permission("tasks:read"))):
    return await _list_tasks(limit=limit)


@router.get("/list")
async def list_tasks_compat(limit: int = 20, _current_user=Depends(require_permission("tasks:read"))):
    return await _list_tasks(limit=limit)


@router.get("/{task_id}")
async def get_task(task_id: str, _current_user=Depends(require_permission("tasks:read"))):
    try:
        store = _get_task_store()
        result = store.get_task(task_id)
        if result is None:
            return {"error": f"任务 '{task_id}' 不存在"}
        return result
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/{task_id}/trace")
async def get_task_trace(task_id: str, _current_user=Depends(require_permission("tasks:read"))):
    recorder = _get_trace_recorder()
    events = recorder.get_events(task_id=task_id)
    return {
        "task_id": task_id,
        "events": [
            {
                "event_id": e.event_id,
                "event_type": e.event_type,
                "actor": e.actor,
                "detail": e.detail,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in events
        ],
    }
