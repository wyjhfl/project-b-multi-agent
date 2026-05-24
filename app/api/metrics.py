from __future__ import annotations

from fastapi import APIRouter, Query

router = APIRouter(prefix="/metrics", tags=["metrics"])


def _get_metrics_recorder():
    from app.main import get_metrics_recorder
    return get_metrics_recorder()


def _get_metrics_store():
    from app.main import get_metrics_store
    return get_metrics_store()


@router.get("/runtime")
async def get_runtime_metrics():
    recorder = _get_metrics_recorder()
    return recorder.summary()


@router.get("/cost/summary")
async def get_cost_summary(
    start_time: str | None = Query(None),
    end_time: str | None = Query(None),
    limit: int = Query(100),
):
    store = _get_metrics_store()
    return store.cost_summary(start_time=start_time, end_time=end_time, limit=limit)


@router.get("/tools/summary")
async def get_tools_summary(
    start_time: str | None = Query(None),
    end_time: str | None = Query(None),
    limit: int = Query(100),
):
    store = _get_metrics_store()
    return store.tool_summary(start_time=start_time, end_time=end_time, limit=limit)


@router.get("/tasks/summary")
async def get_tasks_summary(
    start_time: str | None = Query(None),
    end_time: str | None = Query(None),
    limit: int = Query(100),
):
    store = _get_metrics_store()
    return store.task_summary(start_time=start_time, end_time=end_time, limit=limit)
