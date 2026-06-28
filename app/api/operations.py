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

CURRENT_DOCS = [
    "README.md",
    "docs/architecture.md",
    "docs/api_v1.md",
    "docs/demo_script_v1.md",
    "docs/deployment_runbook.md",
    "docs/interview_guide.md",
    "docs/resume_blog_notes.md",
    "docs/resume_interview_optimization_pack_v50.md",
    "docs/interview_demo_readiness_v50.md",
    "docs/production_policy.md",
]

CURRENT_SCRIPTS = [
    "scripts/init_demo_db.py",
    "scripts/demo_seed_data.py",
    "scripts/start_app.py",
    "scripts/start_dev.py",
    "scripts/demo_up.ps1",
    "scripts/demo_smoke.ps1",
    "scripts/demo_down.ps1",
    "scripts/check_health.py",
    "scripts/local_fake_mcp_stdio_server.py",
    "scripts/interview_demo_readiness.py",
    "scripts/prod_compose_required_env_check.py",
    "scripts/prod_config_check.ps1",
]

TEXT_QUALITY_REPORT_DIR = "docs/reports/production_landing_text_quality"
INTERVIEW_READINESS_REPORT_DIR = "docs/reports/interview_demo_readiness"


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
    return Path(override) if override else DEFAULT_PILOT_REPORT_DIR


def _count_json_reports(directory: str | Path) -> dict[str, Any]:
    path = Path(directory)
    if not path.exists() or not path.is_dir():
        return {"directory": str(path), "directory_exists": False, "json_report_count": 0}
    return {
        "directory": str(path),
        "directory_exists": True,
        "json_report_count": len(list(path.glob("*.json"))),
    }


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
        summary["llm_cache"] = get_llm_result_cache().summary()
    except Exception:
        summary["llm_budget"] = {}
        summary["llm_cache"] = {}
    return summary


def _get_field(item: Any, name: str, default: Any = "") -> Any:
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _collect_task_approval_summary() -> dict[str, Any]:
    task_store = _get_task_store()
    approval_store = _get_approval_store()
    tasks = task_store.list_tasks(limit=200)
    approvals = approval_store.list_approvals(limit=200)

    status_counts: dict[str, int] = {}
    for task in tasks:
        status = str(_get_field(task, "status", "") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1

    def _task_row(task: Any) -> dict[str, Any]:
        return {
            "task_id": str(_get_field(task, "task_id", "")),
            "status": str(_get_field(task, "status", "")),
            "mode": str(_get_field(task, "mode", "")),
            "created_at": str(_get_field(task, "created_at", "")),
        }

    def _approval_row(approval: Any) -> dict[str, Any]:
        return {
            "approval_id": str(_get_field(approval, "approval_id", "")),
            "task_id": str(_get_field(approval, "task_id", "")),
            "status": str(_get_field(approval, "status", "")),
            "risk_level": str(_get_field(approval, "risk_level", "")),
            "tool_name": str(_get_field(approval, "tool_name", "")),
            "requested_at": str(_get_field(approval, "requested_at", "")),
        }

    return {
        "task_count": len(tasks),
        "approval_count": len(approvals),
        "pending_approval_count": sum(1 for item in approvals if _get_field(item, "status", "") == "pending"),
        "task_status_counts": status_counts,
        "recent_tasks": [_task_row(item) for item in tasks[:10]],
        "recent_approvals": [_approval_row(item) for item in approvals[:10]],
    }


def _collect_audit_summary() -> dict[str, Any]:
    audit_store = _get_audit_store()
    events = audit_store.query_events(limit=20)
    rows = []
    for event in events:
        sanitized = sanitize_audit_event_for_export(event)
        rows.append(
            {
                "event_id": str(sanitized.get("event_id", "")),
                "event_type": str(sanitized.get("event_type", "")),
                "created_at": str(sanitized.get("created_at") or sanitized.get("timestamp") or ""),
                "actor": str(sanitized.get("actor", "")),
                "outcome": str(sanitized.get("outcome", "")),
                "severity": str(sanitized.get("severity", "")),
                "task_id": str(sanitized.get("task_id", "")),
                "request_id": str(sanitized.get("request_id", "")),
                "summary": str(sanitized.get("summary", "")),
                "detail_redacted": sanitized.get("detail", {}) if isinstance(sanitized.get("detail"), dict) else {},
            }
        )
    return {"event_count": len(rows), "recent_events": rows}


def _collect_pilot_report_summary() -> dict[str, Any]:
    report_dir = _get_report_dir()
    if not report_dir.exists():
        return {"report_dir": str(report_dir), "directory_exists": False, "total_reports": 0, "reports": []}

    reports = []
    for path in sorted(report_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:10]:
        payload = _load_report_json(path)
        if payload is None:
            continue
        reports.append(
            {
                "report_id": str(payload.get("report_id", path.stem)),
                "generated_at": str(payload.get("generated_at", "")),
                "scenario": str(payload.get("scenario", "")),
                "outcome": str(payload.get("outcome", "")),
                "request_id": str(payload.get("request_id", "")),
                "fallback_used": bool(payload.get("fallback_used", False)),
                "cost": float(payload.get("cost", 0) or 0),
                "total_tokens": int(payload.get("total_tokens", 0) or 0),
                "audit_event_id": str(payload.get("audit_event_id", "")),
                "name": path.name,
            }
        )
    return {
        "report_dir": str(report_dir),
        "directory_exists": True,
        "total_reports": len(list(report_dir.glob("*.json"))),
        "reports": reports,
    }


def _latest_text_quality_status() -> dict[str, Any]:
    report_dir = Path(os.getenv("PRODUCTION_LANDING_TEXT_QUALITY_REPORT_DIR", TEXT_QUALITY_REPORT_DIR))
    latest = sorted(report_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:1]
    if not latest:
        return {"status": "not-run", "blocked_file_count": 0}
    try:
        payload = json.loads(latest[0].read_text(encoding="utf-8"))
    except Exception:
        return {"status": "unreadable", "blocked_file_count": 1}
    return {
        "status": str(payload.get("status", "unknown")),
        "blocked_file_count": int(payload.get("blocked_file_count", 0) or 0),
    }


def _build_landing_command_center_summary(
    *,
    health: dict[str, Any],
    deployment: dict[str, Any],
    text_quality: dict[str, Any],
) -> dict[str, Any]:
    deployment_ok = bool(deployment.get("ok", False))
    text_quality_ok = text_quality.get("status") in {"success", "not-run"}
    precommit_ready = deployment_ok and text_quality_ok
    review_reasons = []
    if not deployment_ok:
        review_reasons.append("deployment_guard:not_ok")
    if not text_quality_ok:
        review_reasons.append("text_quality:blocked")
    review_reasons.append("business_system:real_system_not_connected")

    return {
        "mode": "read_only_showcase",
        "status": "ready" if precommit_ready else "partial",
        "controlled_internal_pilot": "Manual-Review",
        "controlled_internal_pilot_source": "showcase_runtime_summary",
        "public_production_direct_launch": "No-Go",
        "precommit_ready": precommit_ready,
        "action_pack_status": "showcase-ready" if precommit_ready else "review",
        "action_required_input_count": len(review_reasons),
        "infra_ready": deployment_ok,
        "real_business_system_connected": False,
        "business_system_gap_accepted_for_controlled_pilot": True,
        "business_system_public_production_blocker": True,
        "run_packet_missing_conditions": review_reasons,
        "secret_plaintext_output": False,
        "evidence": {
            "runtime": {"status": str(health.get("status", "unknown")), "detail": "FastAPI runtime health"},
            "deployment": {
                "status": "success" if deployment_ok else "blocked",
                "detail": f"errors={len(deployment.get('errors', []))} warnings={len(deployment.get('warnings', []))}",
            },
            "tests": {"status": "tracked-in-ci", "detail": "pytest, frontend lint/build, docker compose config"},
            "text_quality": text_quality,
        },
        "next_actions": [
            "run_interview_demo_readiness",
            "start_local_demo",
            "run_demo_smoke",
            "inspect_multi_agent_trajectory",
            "keep_public_production_direct_launch_no_go_until_real_business_system_acceptance",
        ],
        "operator_guidance": {
            "status": "ready",
            "runbook_paths": [
                "README.md",
                "docs/interview_demo_readiness_v50.md",
                "docs/resume_interview_optimization_pack_v50.md",
            ],
            "commands": [
                {
                    "id": "run_interview_readiness",
                    "label": "Run read-only interview readiness check",
                    "command": "python scripts/interview_demo_readiness.py",
                    "safe_boundary": "read_only_no_secret_plaintext",
                },
                {
                    "id": "start_local_demo",
                    "label": "Start local Docker demo",
                    "command": "powershell -NoProfile -ExecutionPolicy Bypass -File scripts/demo_up.ps1",
                    "safe_boundary": "local_demo_no_secret_plaintext",
                },
                {
                    "id": "run_demo_smoke",
                    "label": "Run local demo smoke check",
                    "command": "powershell -NoProfile -ExecutionPolicy Bypass -File scripts/demo_smoke.ps1",
                    "safe_boundary": "local_read_only_smoke",
                },
            ],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    }


@router.get("/summary")
async def get_operations_summary(_current_user=Depends(require_permission("metrics:read"))):
    health = {
        "status": "ok",
        "service": "project-b-multi-agent",
        "version": os.getenv("APP_VERSION", "unknown"),
        "storage_backend": os.getenv("STORAGE_BACKEND", "sqlite"),
        "auth_enabled": os.getenv("AUTH_ENABLED", "false").lower() == "true",
        "rbac_enabled": os.getenv("RBAC_ENABLED", "false").lower() == "true",
    }
    deployment = run_deployment_checks().model_dump()
    runtime_metrics = _collect_runtime_metrics_summary()
    task_approval = _collect_task_approval_summary()
    audit = _collect_audit_summary()
    pilot_reports = _collect_pilot_report_summary()
    text_quality = _latest_text_quality_status()
    landing_command_center = _build_landing_command_center_summary(
        health=health,
        deployment=deployment,
        text_quality=text_quality,
    )

    text_quality_count = _count_json_reports(os.getenv("PRODUCTION_LANDING_TEXT_QUALITY_REPORT_DIR", TEXT_QUALITY_REPORT_DIR))
    interview_count = _count_json_reports(os.getenv("INTERVIEW_DEMO_READINESS_REPORT_DIR", INTERVIEW_READINESS_REPORT_DIR))

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
            "landing_command_center": landing_command_center,
            "current_docs": CURRENT_DOCS,
            "current_scripts": CURRENT_SCRIPTS,
            "last_known_report_counts": {
                "pilot_reports": int(pilot_reports.get("total_reports", 0) or 0),
                "audit_recent_events": int(audit.get("event_count", 0) or 0),
                "text_quality_reports": int(text_quality_count.get("json_report_count", 0) or 0),
                "interview_demo_readiness_reports": int(interview_count.get("json_report_count", 0) or 0),
            },
        },
        "demo_evidence": {
            "mode": "fake_offline_default",
            "runbook_path": "docs/interview_demo_readiness_v50.md",
            "script_path": "scripts/interview_demo_readiness.py",
            "tip": "Use interview_demo_readiness and the Operations Command Center for local showcase validation.",
        },
    }
