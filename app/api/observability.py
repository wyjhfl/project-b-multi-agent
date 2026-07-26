from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.auth.dependencies import require_permission

router = APIRouter(prefix="/observability", tags=["observability"])


class TaskSummaryResponse(BaseModel):
    total_tasks: int = 0
    success_count: int = 0
    failed_count: int = 0
    mode_counts: dict[str, int] = Field(default_factory=dict)
    recent_tasks: list[dict] = Field(default_factory=list)


class TimelineEvent(BaseModel):
    event_type: str
    timestamp: str
    actor: str
    detail: dict
    duration_from_prev_ms: float | None = None


class TimelineResponse(BaseModel):
    task_id: str
    events: list[TimelineEvent] = Field(default_factory=list)


class EventsResponse(BaseModel):
    events: list[dict] = Field(default_factory=list)
    count: int = 0


class TrajectoryStep(BaseModel):
    role: str
    event_type: str
    status: str = ""
    action: str = ""
    reason: str = ""
    selected_mode: str = ""
    executed_mode: str = ""
    tool_names: list[str] = Field(default_factory=list)
    approved: bool | None = None
    timestamp: str
    detail: dict = Field(default_factory=dict)


class TrajectorySummary(BaseModel):
    task_id: str
    is_multi_agent: bool = False
    roles: list[str] = Field(default_factory=list)
    selected_mode: str = ""
    executed_mode: str = ""
    status: str = "unknown"
    fallback_used: bool = False
    approval_required: bool = False
    tool_names: list[str] = Field(default_factory=list)
    event_count: int = 0


class TrajectoryResponse(BaseModel):
    task_id: str
    summary: TrajectorySummary
    steps: list[TrajectoryStep] = Field(default_factory=list)


def _get_trace_recorder():
    from app.main import get_trace_recorder
    return get_trace_recorder()


def _get_task_store():
    from app.main import get_task_store
    return get_task_store()


@router.get("/tasks/summary", response_model=TaskSummaryResponse)
async def get_tasks_summary(_current_user=Depends(require_permission("metrics:read"))):
    store = _get_task_store()
    tasks = store.list_tasks(limit=100)

    total_tasks = len(tasks)
    success_count = 0
    failed_count = 0
    mode_counts: dict[str, int] = {}

    for t in tasks:
        status = t.get("status", "")
        mode = t.get("mode", "") or "unknown"
        if status == "completed":
            success_count += 1
        elif status == "failed":
            failed_count += 1
        mode_counts[mode] = mode_counts.get(mode, 0) + 1

    recent_tasks = tasks[:5]

    return TaskSummaryResponse(
        total_tasks=total_tasks,
        success_count=success_count,
        failed_count=failed_count,
        mode_counts=mode_counts,
        recent_tasks=recent_tasks,
    )


@router.get("/tasks/{task_id}/timeline", response_model=TimelineResponse)
async def get_task_timeline(task_id: str, _current_user=Depends(require_permission("metrics:read"))):
    recorder = _get_trace_recorder()
    events = recorder.get_events(task_id=task_id)

    timeline_events: list[TimelineEvent] = []
    prev_ts = None

    for e in events:
        duration_from_prev_ms = None
        if prev_ts is not None:
            delta = (e.timestamp - prev_ts).total_seconds() * 1000
            duration_from_prev_ms = round(delta, 2)
        prev_ts = e.timestamp

        timeline_events.append(TimelineEvent(
            event_type=e.event_type,
            timestamp=e.timestamp.isoformat(),
            actor=e.actor,
            detail=e.detail,
            duration_from_prev_ms=duration_from_prev_ms,
        ))

    return TimelineResponse(task_id=task_id, events=timeline_events)


def _append_unique(values: list[str], value: str | None) -> None:
    text = str(value or "").strip()
    if text and text not in values:
        values.append(text)


def _extract_tool_names(detail: dict) -> list[str]:
    names: list[str] = []
    _append_unique(names, detail.get("tool_called"))
    for item in detail.get("tool_calls") or []:
        if isinstance(item, dict):
            _append_unique(names, item.get("tool_name") or item.get("tool_called"))
    return names


def _trajectory_role(event_type: str) -> str:
    if event_type.startswith("coordinator_"):
        return "coordinator"
    if event_type.startswith("analyst_"):
        return "analyst"
    if event_type.startswith("executor_"):
        return "executor"
    if event_type.startswith("reviewer_"):
        return "reviewer"
    if event_type.startswith("multi_agent_"):
        return "orchestrator"
    if event_type.startswith("approval_") or event_type.startswith("multitool_approval"):
        return "approval"
    if event_type.startswith("multitool_"):
        return "multitool"
    if event_type.startswith("nl2sql_"):
        return "nl2sql"
    return "runtime"


def _trajectory_action(event_type: str, detail: dict) -> str:
    if event_type == "multi_agent_started":
        return "start"
    if event_type == "coordinator_decided":
        return "route_intent"
    if event_type == "analyst_planned":
        return "analyze_plan"
    if event_type == "executor_completed":
        return "execute"
    if event_type == "reviewer_completed":
        return "review"
    if event_type == "multi_agent_completed":
        return "complete"
    if event_type == "multi_agent_failed":
        return "fail"
    if "approval" in event_type:
        return "approval"
    return event_type


def _trajectory_status(event_type: str, detail: dict) -> str:
    if event_type.endswith("_failed") or detail.get("success") is False:
        return "failed"
    if detail.get("approved") is False:
        return "rejected"
    if "approval" in event_type or detail.get("requires_approval"):
        return "waiting_approval"
    if event_type.endswith("_started"):
        return "running"
    if event_type.endswith("_completed") or detail.get("success") is True or detail.get("approved") is True:
        return "completed"
    return "recorded"


@router.get("/tasks/{task_id}/trajectory", response_model=TrajectoryResponse)
async def get_task_trajectory(task_id: str, _current_user=Depends(require_permission("metrics:read"))):
    recorder = _get_trace_recorder()
    events = recorder.get_events(task_id=task_id)

    roles: list[str] = []
    all_tool_names: list[str] = []
    selected_mode = ""
    executed_mode = ""
    fallback_used = False
    approval_required = False
    status = "unknown"
    steps: list[TrajectoryStep] = []

    for e in events:
        detail = e.detail or {}
        role = _trajectory_role(e.event_type)
        action = _trajectory_action(e.event_type, detail)
        step_status = _trajectory_status(e.event_type, detail)
        tool_names = _extract_tool_names(detail)

        _append_unique(roles, role)
        for name in tool_names:
            _append_unique(all_tool_names, name)
        if detail.get("selected_mode"):
            selected_mode = str(detail["selected_mode"])
        if detail.get("executed_mode"):
            executed_mode = str(detail["executed_mode"])
        if detail.get("fallback") or "fallback" in e.event_type:
            fallback_used = True
        if detail.get("requires_approval") or "approval" in e.event_type:
            approval_required = True
        if e.event_type == "multi_agent_completed":
            status = "completed"
        elif e.event_type == "multi_agent_failed":
            status = "failed"

        steps.append(TrajectoryStep(
            role=role,
            event_type=e.event_type,
            status=step_status,
            action=action,
            reason=str(detail.get("reason") or detail.get("plan_summary") or ""),
            selected_mode=str(detail.get("selected_mode") or ""),
            executed_mode=str(detail.get("executed_mode") or ""),
            tool_names=tool_names,
            approved=detail.get("approved") if isinstance(detail.get("approved"), bool) else None,
            timestamp=e.timestamp.isoformat(),
            detail=detail,
        ))

    is_multi_agent = any(step.role in {"coordinator", "analyst", "executor", "reviewer", "orchestrator"} for step in steps)
    summary = TrajectorySummary(
        task_id=task_id,
        is_multi_agent=is_multi_agent,
        roles=roles,
        selected_mode=selected_mode,
        executed_mode=executed_mode,
        status=status,
        fallback_used=fallback_used,
        approval_required=approval_required,
        tool_names=all_tool_names,
        event_count=len(events),
    )
    return TrajectoryResponse(task_id=task_id, summary=summary, steps=steps)


@router.get("/events", response_model=EventsResponse)
async def get_events(
    task_id: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    limit: int = Query(default=100),
    _current_user=Depends(require_permission("metrics:read")),
):
    if limit <= 0:
        limit = 100
    if limit > 500:
        limit = 500

    recorder = _get_trace_recorder()
    events = recorder.get_events(task_id=task_id, event_type=event_type)

    sliced = events[:limit]

    result = [
        {
            "event_id": e.event_id,
            "event_type": e.event_type,
            "task_id": e.task_id,
            "actor": e.actor,
            "detail": e.detail,
            "timestamp": e.timestamp.isoformat(),
        }
        for e in sliced
    ]

    return EventsResponse(events=result, count=len(result))
