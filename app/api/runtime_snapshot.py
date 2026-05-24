from __future__ import annotations

import logging

from fastapi import APIRouter

router = APIRouter(prefix="/runtime", tags=["runtime"])


def _safe_section(name: str, fn) -> dict:
    try:
        return fn()
    except Exception as exc:
        logging.warning("runtime snapshot section %s failed: %s", name, exc)
        return {"error": str(exc)}


@router.get("/snapshot")
async def get_runtime_snapshot():
    from app.main import (
        app,
        get_metrics_recorder,
        get_metrics_store,
        get_audit_store,
        get_memory,
        get_skill_registry,
    )

    metrics_recorder = get_metrics_recorder()
    metrics_store = get_metrics_store()
    audit_store = get_audit_store()
    memory = get_memory()
    skill_registry = get_skill_registry()

    metrics_summary = _safe_section("metrics_summary", metrics_recorder.summary)

    cost_summary = _safe_section("cost_summary", metrics_store.cost_summary)

    task_summary = _safe_section("task_summary", metrics_store.task_summary)

    tool_summary = _safe_section("tool_summary", metrics_store.tool_summary)

    def _build_audit_summary():
        audit_events = audit_store.query_events(limit=500)
        summary = {
            "total_events": len(audit_events),
            "by_outcome": {},
            "by_severity": {},
        }
        for ev in audit_events:
            outcome = ev.get("outcome", "unknown")
            summary["by_outcome"][outcome] = summary["by_outcome"].get(outcome, 0) + 1
            severity = ev.get("severity", "unknown")
            summary["by_severity"][severity] = summary["by_severity"].get(severity, 0) + 1
        return summary

    audit_summary = _safe_section("audit_summary", _build_audit_summary)

    memory_summary = _safe_section("memory_summary", memory.summary)

    def _build_skills_summary():
        skills = skill_registry.list_skills()
        return {
            "skill_count": len(skills),
            "skill_names": [s.name for s in skills],
        }

    skills_summary = _safe_section("skills_summary", _build_skills_summary)

    return {
        "app_version": app.version,
        "metrics_summary": metrics_summary,
        "cost_summary": cost_summary,
        "task_summary": task_summary,
        "tool_summary": tool_summary,
        "audit_summary": audit_summary,
        "memory_summary": memory_summary,
        "skills_summary": skills_summary,
    }
