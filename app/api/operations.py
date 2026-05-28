from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends

from app.auth.dependencies import require_permission
from app.core.deployment_guard import run_deployment_checks
from app.harness.audit.retention import sanitize_audit_event_for_export
from app.harness.llm.pilot_report import DEFAULT_PILOT_REPORT_DIR, sanitize_pilot_report_payload

router = APIRouter(prefix="/operations", tags=["operations"])

ACCEPTANCE_SNAPSHOT_RUNBOOK_PATH = "docs/acceptance_snapshot_runbook_v32.md"
DEMO_ARTIFACT_RUNBOOK_PATH = "docs/demo_artifact_bundle_runbook_v32.md"
ARTIFACT_DEFAULT_DIR = "docs/reports/demo_artifacts"
SNAPSHOT_DEFAULT_DIR = "docs/reports/acceptance_snapshots"


def _get_task_store():
    from app.main import get_task_store

    return get_task_store()


def _get_approval_store():
    from app.main import get_approval_store

    return get_approval_store()


def _get_audit_store():
    from app.main import get_audit_store

    return get_audit_store()


def _get_metrics_recorder():
    from app.main import get_metrics_recorder

    return get_metrics_recorder()


def _get_report_dir() -> Path:
    override = (os.getenv("REAL_LLM_PILOT_REPORT_DIR", "") or "").strip()
    if override:
        return Path(override)
    return DEFAULT_PILOT_REPORT_DIR


def _load_report_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return sanitize_pilot_report_payload(payload)


def _collect_runtime_metrics_summary() -> dict[str, Any]:
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


def _collect_task_approval_summary() -> dict[str, Any]:
    task_store = _get_task_store()
    approval_store = _get_approval_store()

    try:
        tasks = task_store.list_tasks(limit=200)
    except Exception:
        tasks = []
    try:
        approvals = approval_store.list_approvals(limit=200)
    except Exception:
        approvals = []

    status_counts: dict[str, int] = {}
    for item in tasks:
        status = str(item.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1

    pending_count = sum(1 for item in approvals if str(item.get("status")) == "pending")
    recent_tasks = [
        {
            "task_id": item.get("task_id", ""),
            "status": item.get("status", ""),
            "mode": item.get("mode", ""),
            "created_at": item.get("created_at", ""),
        }
        for item in tasks[:5]
    ]
    recent_approvals = [
        {
            "approval_id": item.get("approval_id", ""),
            "task_id": item.get("task_id", ""),
            "status": item.get("status", ""),
            "risk_level": item.get("risk_level", ""),
            "tool_name": item.get("tool_name", ""),
            "requested_at": item.get("requested_at", ""),
        }
        for item in approvals[:5]
    ]

    return {
        "task_count": len(tasks),
        "approval_count": len(approvals),
        "pending_approval_count": pending_count,
        "task_status_counts": status_counts,
        "recent_tasks": recent_tasks,
        "recent_approvals": recent_approvals,
    }


def _collect_audit_summary() -> dict[str, Any]:
    store = _get_audit_store()
    try:
        events = store.query_events(limit=10)
    except Exception:
        events = []

    sanitized_events: list[dict[str, Any]] = []
    for event in events:
        safe = sanitize_audit_event_for_export(event, redaction_enabled=True)
        sanitized_events.append(
            {
                "event_id": safe.get("event_id", ""),
                "event_type": safe.get("event_type", ""),
                "created_at": safe.get("created_at", ""),
                "actor": safe.get("actor", ""),
                "outcome": safe.get("outcome", ""),
                "severity": safe.get("severity", ""),
                "task_id": safe.get("task_id", ""),
                "request_id": safe.get("request_id", ""),
                "summary": safe.get("summary", ""),
                "detail_redacted": safe.get("detail_redacted", {}),
            }
        )
    return {"recent_events": sanitized_events, "event_count": len(sanitized_events)}


def _collect_pilot_report_summary() -> dict[str, Any]:
    report_dir = _get_report_dir()
    if not report_dir.exists() or not report_dir.is_dir():
        return {
            "report_dir": str(report_dir),
            "directory_exists": False,
            "total_reports": 0,
            "reports": [],
        }

    reports: list[dict[str, Any]] = []
    for path in sorted(report_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not path.is_file() or path.suffix.lower() != ".json":
            continue
        payload = _load_report_json(path)
        if not payload:
            continue
        evidence_links = payload.get("evidence_links") or {}
        if not evidence_links and payload.get("cases"):
            first_case = payload["cases"][0] if isinstance(payload["cases"], list) and payload["cases"] else {}
            if isinstance(first_case, dict):
                evidence_links = first_case.get("evidence_links") or {}
        reports.append(
            {
                "report_id": payload.get("report_id") or path.stem,
                "generated_at": payload.get("generated_at", ""),
                "scenario": payload.get("scenario", ""),
                "outcome": payload.get("outcome", ""),
                "request_id": payload.get("request_id", ""),
                "fallback_used": bool(payload.get("fallback_used", False)),
                "cost": float(payload.get("cost", 0.0) or 0.0),
                "total_tokens": int(payload.get("total_tokens", 0) or 0),
                "audit_event_id": str(evidence_links.get("audit_event_id") or ""),
                "name": path.name,
            }
        )
        if len(reports) >= 10:
            break
    return {
        "report_dir": str(report_dir),
        "directory_exists": True,
        "total_reports": len(reports),
        "reports": reports,
    }


@router.get("/summary")
async def get_operations_summary(_current_user=Depends(require_permission("metrics:read"))):
    from app.main import health_check

    health = await health_check()
    deployment = run_deployment_checks().model_dump()

    runtime_metrics = _collect_runtime_metrics_summary()
    task_approval = _collect_task_approval_summary()
    audit = _collect_audit_summary()
    pilot_reports = _collect_pilot_report_summary()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only",
        "health": health,
        "deployment": {
            "ok": bool(deployment.get("ok", False)),
            "environment": deployment.get("environment", ""),
            "error_count": len(deployment.get("errors", [])),
            "warning_count": len(deployment.get("warnings", [])),
            "errors": deployment.get("errors", []),
            "warnings": deployment.get("warnings", []),
            "check_count": len(deployment.get("checks", [])),
        },
        "runtime_metrics": runtime_metrics,
        "task_approval": task_approval,
        "audit": audit,
        "pilot_reports": pilot_reports,
        "observability": {
            "acceptance_snapshot_runbook_path": ACCEPTANCE_SNAPSHOT_RUNBOOK_PATH,
            "demo_artifact_runbook_path": DEMO_ARTIFACT_RUNBOOK_PATH,
            "artifact_default_dir": ARTIFACT_DEFAULT_DIR,
            "snapshot_default_dir": SNAPSHOT_DEFAULT_DIR,
            "last_known_report_counts": {
                "pilot_reports": int(pilot_reports.get("total_reports", 0) or 0),
                "audit_recent_events": int(audit.get("event_count", 0) or 0),
            },
        },
        "demo_evidence": {
            "mode": "fake_offline_default",
            "runbook_path": "docs/demo_e2e_runbook_v31.md",
            "script_path": "scripts/demo_e2e.ps1",
            "tip": "Use demo_e2e script for offline evidence generation. If service is unavailable, online checks are skipped without false success.",
        },
    }
