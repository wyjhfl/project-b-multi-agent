from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

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


def _get_trace_recorder():
    from app.main import get_trace_recorder
    return get_trace_recorder()


def _get_task_store():
    from app.main import get_task_store
    return get_task_store()


@router.get("/tasks/summary", response_model=TaskSummaryResponse)
async def get_tasks_summary():
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
async def get_task_timeline(task_id: str):
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


@router.get("/events", response_model=EventsResponse)
async def get_events(
    task_id: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    limit: int = Query(default=100),
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
