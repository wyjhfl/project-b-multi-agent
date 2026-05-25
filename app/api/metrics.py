from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import require_permission

router = APIRouter(prefix="/metrics", tags=["metrics"])


def _get_metrics_recorder():
    from app.main import get_metrics_recorder
    return get_metrics_recorder()


def _get_metrics_store():
    from app.main import get_metrics_store
    return get_metrics_store()


@router.get("/runtime")
async def get_runtime_metrics(_current_user=Depends(require_permission("metrics:read"))):
    recorder = _get_metrics_recorder()
    summary = recorder.summary()
    try:
        from app.harness.llm.budget import get_llm_budget_manager
        from app.harness.llm.cache import get_llm_result_cache

        summary["llm_budget"] = get_llm_budget_manager().summary()
        summary["llm_cache"] = get_llm_result_cache().stats()
    except Exception:
        summary["llm_budget"] = {"enabled": False}
        summary["llm_cache"] = {"enabled": False}
    return summary


@router.get("/cost/summary")
async def get_cost_summary(
    start_time: str | None = Query(None),
    end_time: str | None = Query(None),
    limit: int = Query(100),
    _current_user=Depends(require_permission("metrics:read")),
):
    store = _get_metrics_store()
    return store.cost_summary(start_time=start_time, end_time=end_time, limit=limit)


@router.get("/tools/summary")
async def get_tools_summary(
    start_time: str | None = Query(None),
    end_time: str | None = Query(None),
    limit: int = Query(100),
    _current_user=Depends(require_permission("metrics:read")),
):
    store = _get_metrics_store()
    return store.tool_summary(start_time=start_time, end_time=end_time, limit=limit)


@router.get("/tasks/summary")
async def get_tasks_summary(
    start_time: str | None = Query(None),
    end_time: str | None = Query(None),
    limit: int = Query(100),
    _current_user=Depends(require_permission("metrics:read")),
):
    store = _get_metrics_store()
    return store.task_summary(start_time=start_time, end_time=end_time, limit=limit)
