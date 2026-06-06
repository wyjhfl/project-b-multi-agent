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
PRODUCTION_PILOT_BOOTSTRAP_RUNBOOK_PATH = "scripts/production_pilot_bootstrap.py"
PRODUCTION_PILOT_BOOTSTRAP_DEFAULT_DIR = "docs/reports/production_pilot_bootstrap"
FRONTEND_PRODUCTION_BUILD_RUNBOOK_PATH = "scripts/frontend_production_build_check.py"
FRONTEND_PRODUCTION_BUILD_DEFAULT_DIR = "docs/reports/frontend_production_build"
PRODUCTION_RUNTIME_SMOKE_RUNBOOK_PATH = "scripts/production_runtime_smoke.py"
PRODUCTION_RUNTIME_SMOKE_DEFAULT_DIR = "docs/reports/production_runtime_smoke"
PRODUCTION_PILOT_SIGNOFF_RUNBOOK_PATH = "scripts/production_pilot_signoff_summary.py"
PRODUCTION_PILOT_SIGNOFF_DEFAULT_DIR = "docs/reports/production_pilot_signoff"
BUSINESS_SYSTEM_READ_SMOKE_RUNBOOK_PATH = "scripts/business_system_read_smoke.py"
BUSINESS_SYSTEM_READ_SMOKE_DEFAULT_DIR = "docs/reports/business_system_read_smoke"
BUSINESS_SYSTEM_INPUT_PACKET_RUNBOOK_PATH = "scripts/business_system_input_packet.py"
BUSINESS_SYSTEM_INPUT_PACKET_DEFAULT_DIR = "docs/reports/business_system_input_packet"
BUSINESS_SYSTEM_PRODUCTION_READINESS_RUNBOOK_PATH = "scripts/business_system_production_readiness_brief.py"
BUSINESS_SYSTEM_PRODUCTION_READINESS_DEFAULT_DIR = "docs/reports/business_system_production_readiness"
REAL_INTEGRATION_STAGING_SMOKE_RUNBOOK_PATH = "scripts/real_integration_staging_smoke.py"
REAL_INTEGRATION_STAGING_SMOKE_DEFAULT_DIR = "docs/reports/real_integration_staging_smoke"
REAL_PRODUCTION_ENVIRONMENT_CHECKLIST_RUNBOOK_PATH = "docs/v4_5_real_production_environment_landing_plan.md"
REAL_PRODUCTION_ENVIRONMENT_CHECKLIST_DEFAULT_DIR = "docs/reports/real_production_environment_checklist"
REAL_INTEGRATION_INFRA_SMOKE_RUNBOOK_PATH = "scripts/real_integration_infra_smoke.ps1"
SAFE_XIAOMI_LLM_PREFLIGHT_COMMAND = "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\xiaomi_llm_preflight.ps1"
SAFE_BUSINESS_READ_SMOKE_COMMAND = "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1"
SAFE_POSTGRES_INFRA_SMOKE_COMMAND = "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\real_integration_infra_smoke.ps1 -Domains postgres"
SAFE_REDIS_INFRA_SMOKE_COMMAND = "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\real_integration_infra_smoke.ps1 -Domains redis"
SAFE_EXTERNAL_MCP_INFRA_SMOKE_COMMAND = (
    "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\real_integration_infra_smoke.ps1 "
    "-Domains external_mcp -McpServerCommand <approved-command> "
    "-McpServerCommandAllowlist <approved-command> -McpToolAllowlist <approved-tools>"
)
SAFE_INFRA_AND_LLM_SMOKE_COMMAND = " ; ".join(
    [
        SAFE_XIAOMI_LLM_PREFLIGHT_COMMAND,
        SAFE_POSTGRES_INFRA_SMOKE_COMMAND,
        SAFE_REDIS_INFRA_SMOKE_COMMAND,
        SAFE_EXTERNAL_MCP_INFRA_SMOKE_COMMAND,
    ]
)
PRODUCTION_LANDING_ACTION_PACK_RUNBOOK_PATH = "scripts/production_landing_action_pack.py"
PRODUCTION_LANDING_ACTION_PACK_DEFAULT_DIR = "docs/reports/production_landing_action_pack"
PRODUCTION_LANDING_BLOCKER_RESOLUTION_RUNBOOK_PATH = "scripts/production_landing_blocker_resolution.py"
PRODUCTION_LANDING_BLOCKER_RESOLUTION_DEFAULT_DIR = "docs/reports/production_landing_blocker_resolution"
PRODUCTION_LANDING_FINAL_VERIFICATION_RUNBOOK_PATH = "scripts/production_landing_final_verification.py"
PRODUCTION_LANDING_FINAL_VERIFICATION_DEFAULT_DIR = "docs/reports/production_landing_final_verification"
PRODUCTION_LANDING_STATUS_RUNBOOK_PATH = "scripts/production_landing_status.py"
PRODUCTION_LANDING_STATUS_DEFAULT_DIR = "docs/reports/production_landing_status"
PRODUCTION_LANDING_OPERATOR_RUNBOOK_PATH = "docs/production_landing_operator_runbook_v47.md"
XIAOMI_LLM_LANDING_RESUME_RUNBOOK_PATH = "docs/xiaomi_llm_landing_resume_runbook_v47.md"
PRODUCTION_LANDING_XIAOMI_LLM_PREFLIGHT_RUNBOOK_PATH = "scripts/production_landing_xiaomi_llm_preflight_runner.py"
PRODUCTION_LANDING_XIAOMI_LLM_PREFLIGHT_DEFAULT_DIR = "docs/reports/production_landing_xiaomi_llm_preflight"
PRODUCTION_LANDING_ENV_CHECK_RUNBOOK_PATH = "scripts/production_landing_env_check.py"
PRODUCTION_LANDING_ENV_CHECK_DEFAULT_DIR = "docs/reports/production_landing_env_check"
PRODUCTION_LANDING_ENV_RUNNER_RUNBOOK_PATH = "scripts/production_landing_env_runner.py"
PRODUCTION_LANDING_ENV_RUNNER_DEFAULT_DIR = "docs/reports/production_landing_env_runner"
PRODUCTION_LANDING_EXECUTION_GATE_RUNBOOK_PATH = "scripts/production_landing_execution_gate.py"
PRODUCTION_LANDING_EXECUTION_GATE_DEFAULT_DIR = "docs/reports/production_landing_execution_gate"
PRODUCTION_LANDING_INPUT_READINESS_RUNBOOK_PATH = "scripts/production_landing_input_readiness.py"
PRODUCTION_LANDING_INPUT_READINESS_DEFAULT_DIR = "docs/reports/production_landing_input_readiness"
MANUAL_SIGNOFF_EVIDENCE_ACK_STATUS_RUNBOOK_PATH = "scripts/manual_signoff_evidence_ack_status.py"
MANUAL_SIGNOFF_EVIDENCE_ACK_STATUS_DEFAULT_DIR = "docs/reports/manual_signoff_evidence_ack_status"
MANUAL_SIGNOFF_RECORD_VALIDATION_RUNBOOK_PATH = "scripts/manual_signoff_record_validator.py"
MANUAL_SIGNOFF_RECORD_VALIDATION_DEFAULT_DIR = "docs/reports/manual_signoff_record_validation"
MANUAL_SIGNOFF_RECORD_FILL_RUNBOOK_PATH = "scripts/manual_signoff_record_fill.py"
MANUAL_SIGNOFF_RECORD_FILL_DEFAULT_DIR = "docs/reports/manual_signoff_record_fill"
PRODUCTION_LANDING_SIGNOFF_CLOSEOUT_RUNBOOK_PATH = "scripts/production_landing_signoff_closeout.py"
PRODUCTION_LANDING_SIGNOFF_CLOSEOUT_OPERATOR_RUNBOOK_PATH = "docs/production_landing_signoff_closeout_runbook_v48.md"
PRODUCTION_LANDING_SIGNOFF_CLOSEOUT_DEFAULT_DIR = "docs/reports/production_landing_signoff_closeout"
PRODUCTION_LANDING_PRE_SIGNOFF_GATE_RUNBOOK_PATH = "scripts/production_landing_pre_signoff_gate.py"
PRODUCTION_LANDING_PRE_SIGNOFF_GATE_DEFAULT_DIR = "docs/reports/production_landing_pre_signoff_gate"
PRODUCTION_LANDING_SIGNOFF_REVIEWER_PACKET_RUNBOOK_PATH = "scripts/production_landing_signoff_reviewer_packet.py"
PRODUCTION_LANDING_SIGNOFF_REVIEWER_PACKET_DEFAULT_DIR = "docs/reports/production_landing_signoff_reviewer_packet"
MANUAL_SIGNOFF_RECORD_PROMOTE_RUNBOOK_PATH = "scripts/manual_signoff_record_promote.py"
MANUAL_SIGNOFF_RECORD_PROMOTE_DEFAULT_DIR = "docs/reports/manual_signoff_record_promote"
PRODUCTION_LANDING_TEXT_QUALITY_RUNBOOK_PATH = "scripts/production_landing_text_quality_check.py"
PRODUCTION_LANDING_TEXT_QUALITY_DEFAULT_DIR = "docs/reports/production_landing_text_quality"
PRODUCTION_LANDING_EVIDENCE_FRESHNESS_RUNBOOK_PATH = "scripts/production_landing_evidence_freshness.py"
PRODUCTION_LANDING_EVIDENCE_FRESHNESS_DEFAULT_DIR = "docs/reports/production_landing_evidence_freshness"
PRODUCTION_PILOT_EVIDENCE_BUNDLE_RUNBOOK_PATH = "scripts/production_pilot_evidence_bundle.py"
PRODUCTION_PILOT_EVIDENCE_BUNDLE_DEFAULT_DIR = "docs/reports/production_pilot_evidence_bundle"
CONTROLLED_PILOT_LAUNCH_GATE_RUNBOOK_PATH = "scripts/controlled_pilot_launch_gate.py"
CONTROLLED_PILOT_LAUNCH_GATE_DEFAULT_DIR = "docs/reports/controlled_pilot_launch_gate"
CONTROLLED_PILOT_LAUNCH_PACKAGE_RUNBOOK_PATH = "scripts/controlled_pilot_launch_package.py"
CONTROLLED_PILOT_LAUNCH_PACKAGE_DEFAULT_DIR = "docs/reports/controlled_pilot_launch_package"
CONTROLLED_PILOT_WINDOW_RECORD_RUNBOOK_PATH = "scripts/controlled_pilot_window_record.py"
CONTROLLED_PILOT_WINDOW_RECORD_DEFAULT_DIR = "docs/reports/controlled_pilot_window_record"
CONTROLLED_PILOT_WINDOW_STATUS_RUNBOOK_PATH = "scripts/controlled_pilot_window_status_snapshot.py"
CONTROLLED_PILOT_WINDOW_STATUS_DEFAULT_DIR = "docs/reports/controlled_pilot_window_status"
CONTROLLED_PILOT_STATUS_SUMMARY_RUNBOOK_PATH = "scripts/controlled_pilot_status_summary.py"
CONTROLLED_PILOT_STATUS_SUMMARY_DEFAULT_DIR = "docs/reports/controlled_pilot_status_summary"
CONTROLLED_PILOT_OPERATOR_PACKET_RUNBOOK_PATH = "scripts/controlled_pilot_operator_packet.py"
CONTROLLED_PILOT_OPERATOR_PACKET_DEFAULT_DIR = "docs/reports/controlled_pilot_operator_packet"
CONTROLLED_PILOT_CONSOLE_PREFLIGHT_RUNBOOK_PATH = "scripts/controlled_pilot_console_preflight.py"
CONTROLLED_PILOT_CONSOLE_PREFLIGHT_DEFAULT_DIR = "docs/reports/controlled_pilot_console_preflight"
CONTROLLED_PILOT_CONSOLE_VERIFY_RUNBOOK_PATH = "scripts/controlled_pilot_console_verify.ps1"
CONTROLLED_PILOT_CONSOLE_VERIFY_DEFAULT_DIR = "docs/reports/controlled_pilot_console_verify"
OPERATIONS_CONSOLE_LANDING_SMOKE_RUNBOOK_PATH = "scripts/operations_console_landing_smoke.py"
OPERATIONS_CONSOLE_LANDING_SMOKE_DEFAULT_DIR = "docs/reports/operations_console_landing_smoke"
V4_EVIDENCE_RUNBOOKS = {
    "launch_blocker_closure": "docs/launch_blocker_closure_workflow_v41.md",
    "closure_evidence_index": "docs/closure_evidence_index_v41.md",
    "manual_signoff_package": "docs/manual_signoff_package_v41.md",
    "controlled_production_acceptance": "docs/controlled_production_acceptance_drill_v42.md",
    "acceptance_drill_index": "docs/acceptance_drill_evidence_index_v42.md",
    "production_acceptance_gaps": "docs/production_acceptance_gap_register_v42.md",
    "real_production_environment_checklist": REAL_PRODUCTION_ENVIRONMENT_CHECKLIST_RUNBOOK_PATH,
    "frontend_production_build": FRONTEND_PRODUCTION_BUILD_RUNBOOK_PATH,
    "production_runtime_smoke": PRODUCTION_RUNTIME_SMOKE_RUNBOOK_PATH,
    "production_pilot_bootstrap": PRODUCTION_PILOT_BOOTSTRAP_RUNBOOK_PATH,
    "production_pilot_signoff": PRODUCTION_PILOT_SIGNOFF_RUNBOOK_PATH,
    "business_system_read_smoke": BUSINESS_SYSTEM_READ_SMOKE_RUNBOOK_PATH,
    "business_system_input_packet": BUSINESS_SYSTEM_INPUT_PACKET_RUNBOOK_PATH,
    "business_system_production_readiness": BUSINESS_SYSTEM_PRODUCTION_READINESS_RUNBOOK_PATH,
    "real_integration_staging_smoke": REAL_INTEGRATION_STAGING_SMOKE_RUNBOOK_PATH,
    "production_landing_input_readiness": PRODUCTION_LANDING_INPUT_READINESS_RUNBOOK_PATH,
    "production_landing_env_check": PRODUCTION_LANDING_ENV_CHECK_RUNBOOK_PATH,
    "production_landing_env_runner": PRODUCTION_LANDING_ENV_RUNNER_RUNBOOK_PATH,
    "production_landing_execution_gate": PRODUCTION_LANDING_EXECUTION_GATE_RUNBOOK_PATH,
    "production_landing_action_pack": PRODUCTION_LANDING_ACTION_PACK_RUNBOOK_PATH,
    "production_landing_blocker_resolution": PRODUCTION_LANDING_BLOCKER_RESOLUTION_RUNBOOK_PATH,
    "production_landing_final_verification": PRODUCTION_LANDING_FINAL_VERIFICATION_RUNBOOK_PATH,
    "production_landing_status": PRODUCTION_LANDING_STATUS_RUNBOOK_PATH,
    "production_landing_operator_runbook": PRODUCTION_LANDING_OPERATOR_RUNBOOK_PATH,
    "xiaomi_llm_landing_resume_runbook": XIAOMI_LLM_LANDING_RESUME_RUNBOOK_PATH,
    "production_landing_xiaomi_llm_preflight": PRODUCTION_LANDING_XIAOMI_LLM_PREFLIGHT_RUNBOOK_PATH,
    "manual_signoff_evidence_ack_status": MANUAL_SIGNOFF_EVIDENCE_ACK_STATUS_RUNBOOK_PATH,
    "manual_signoff_record_validation": MANUAL_SIGNOFF_RECORD_VALIDATION_RUNBOOK_PATH,
    "manual_signoff_record_fill": MANUAL_SIGNOFF_RECORD_FILL_RUNBOOK_PATH,
    "production_landing_signoff_closeout": PRODUCTION_LANDING_SIGNOFF_CLOSEOUT_RUNBOOK_PATH,
    "production_landing_signoff_closeout_runbook": PRODUCTION_LANDING_SIGNOFF_CLOSEOUT_OPERATOR_RUNBOOK_PATH,
    "production_landing_pre_signoff_gate": PRODUCTION_LANDING_PRE_SIGNOFF_GATE_RUNBOOK_PATH,
    "production_landing_signoff_reviewer_packet": PRODUCTION_LANDING_SIGNOFF_REVIEWER_PACKET_RUNBOOK_PATH,
    "manual_signoff_record_promote": MANUAL_SIGNOFF_RECORD_PROMOTE_RUNBOOK_PATH,
    "production_landing_text_quality": PRODUCTION_LANDING_TEXT_QUALITY_RUNBOOK_PATH,
    "production_landing_evidence_freshness": PRODUCTION_LANDING_EVIDENCE_FRESHNESS_RUNBOOK_PATH,
    "production_pilot_evidence_bundle": PRODUCTION_PILOT_EVIDENCE_BUNDLE_RUNBOOK_PATH,
    "controlled_pilot_launch_gate": CONTROLLED_PILOT_LAUNCH_GATE_RUNBOOK_PATH,
    "controlled_pilot_launch_package": CONTROLLED_PILOT_LAUNCH_PACKAGE_RUNBOOK_PATH,
    "controlled_pilot_window_record": CONTROLLED_PILOT_WINDOW_RECORD_RUNBOOK_PATH,
    "controlled_pilot_window_status": CONTROLLED_PILOT_WINDOW_STATUS_RUNBOOK_PATH,
    "controlled_pilot_status_summary": CONTROLLED_PILOT_STATUS_SUMMARY_RUNBOOK_PATH,
    "controlled_pilot_operator_packet": "docs/controlled_pilot_operator_packet_v48.md",
    "controlled_pilot_console_preflight": CONTROLLED_PILOT_CONSOLE_PREFLIGHT_RUNBOOK_PATH,
    "controlled_pilot_console_verify": CONTROLLED_PILOT_CONSOLE_VERIFY_RUNBOOK_PATH,
    "operations_console_landing_smoke": OPERATIONS_CONSOLE_LANDING_SMOKE_RUNBOOK_PATH,
}
V4_EVIDENCE_DIRS = {
    "launch_blocker_closure": "docs/reports/launch_blocker_closure",
    "closure_evidence_index": "docs/reports/closure_evidence_index",
    "manual_signoff_package": "docs/reports/manual_signoff_package",
    "controlled_production_acceptance": "docs/reports/controlled_production_acceptance",
    "acceptance_drill_index": "docs/reports/acceptance_drill_index",
    "production_acceptance_gaps": "docs/reports/production_acceptance_gaps",
    "real_production_environment_checklist": REAL_PRODUCTION_ENVIRONMENT_CHECKLIST_DEFAULT_DIR,
    "frontend_production_build": FRONTEND_PRODUCTION_BUILD_DEFAULT_DIR,
    "production_runtime_smoke": PRODUCTION_RUNTIME_SMOKE_DEFAULT_DIR,
    "production_pilot_bootstrap": PRODUCTION_PILOT_BOOTSTRAP_DEFAULT_DIR,
    "production_pilot_signoff": PRODUCTION_PILOT_SIGNOFF_DEFAULT_DIR,
    "business_system_read_smoke": BUSINESS_SYSTEM_READ_SMOKE_DEFAULT_DIR,
    "business_system_input_packet": BUSINESS_SYSTEM_INPUT_PACKET_DEFAULT_DIR,
    "business_system_production_readiness": BUSINESS_SYSTEM_PRODUCTION_READINESS_DEFAULT_DIR,
    "real_integration_staging_smoke": REAL_INTEGRATION_STAGING_SMOKE_DEFAULT_DIR,
    "production_landing_input_readiness": PRODUCTION_LANDING_INPUT_READINESS_DEFAULT_DIR,
    "production_landing_env_check": PRODUCTION_LANDING_ENV_CHECK_DEFAULT_DIR,
    "production_landing_env_runner": PRODUCTION_LANDING_ENV_RUNNER_DEFAULT_DIR,
    "production_landing_execution_gate": PRODUCTION_LANDING_EXECUTION_GATE_DEFAULT_DIR,
    "production_landing_action_pack": PRODUCTION_LANDING_ACTION_PACK_DEFAULT_DIR,
    "production_landing_blocker_resolution": PRODUCTION_LANDING_BLOCKER_RESOLUTION_DEFAULT_DIR,
    "production_landing_final_verification": PRODUCTION_LANDING_FINAL_VERIFICATION_DEFAULT_DIR,
    "production_landing_status": PRODUCTION_LANDING_STATUS_DEFAULT_DIR,
    "production_landing_operator_runbook": "docs",
    "xiaomi_llm_landing_resume_runbook": "docs",
    "production_landing_xiaomi_llm_preflight": PRODUCTION_LANDING_XIAOMI_LLM_PREFLIGHT_DEFAULT_DIR,
    "manual_signoff_evidence_ack_status": MANUAL_SIGNOFF_EVIDENCE_ACK_STATUS_DEFAULT_DIR,
    "manual_signoff_record_validation": MANUAL_SIGNOFF_RECORD_VALIDATION_DEFAULT_DIR,
    "manual_signoff_record_fill": MANUAL_SIGNOFF_RECORD_FILL_DEFAULT_DIR,
    "production_landing_signoff_closeout": PRODUCTION_LANDING_SIGNOFF_CLOSEOUT_DEFAULT_DIR,
    "production_landing_signoff_closeout_runbook": "docs",
    "production_landing_pre_signoff_gate": PRODUCTION_LANDING_PRE_SIGNOFF_GATE_DEFAULT_DIR,
    "production_landing_signoff_reviewer_packet": PRODUCTION_LANDING_SIGNOFF_REVIEWER_PACKET_DEFAULT_DIR,
    "manual_signoff_record_promote": MANUAL_SIGNOFF_RECORD_PROMOTE_DEFAULT_DIR,
    "production_landing_text_quality": PRODUCTION_LANDING_TEXT_QUALITY_DEFAULT_DIR,
    "production_landing_evidence_freshness": PRODUCTION_LANDING_EVIDENCE_FRESHNESS_DEFAULT_DIR,
    "production_pilot_evidence_bundle": PRODUCTION_PILOT_EVIDENCE_BUNDLE_DEFAULT_DIR,
    "controlled_pilot_launch_gate": CONTROLLED_PILOT_LAUNCH_GATE_DEFAULT_DIR,
    "controlled_pilot_launch_package": CONTROLLED_PILOT_LAUNCH_PACKAGE_DEFAULT_DIR,
    "controlled_pilot_window_record": CONTROLLED_PILOT_WINDOW_RECORD_DEFAULT_DIR,
    "controlled_pilot_window_status": CONTROLLED_PILOT_WINDOW_STATUS_DEFAULT_DIR,
    "controlled_pilot_status_summary": CONTROLLED_PILOT_STATUS_SUMMARY_DEFAULT_DIR,
    "controlled_pilot_operator_packet": CONTROLLED_PILOT_OPERATOR_PACKET_DEFAULT_DIR,
    "controlled_pilot_console_preflight": CONTROLLED_PILOT_CONSOLE_PREFLIGHT_DEFAULT_DIR,
    "controlled_pilot_console_verify": CONTROLLED_PILOT_CONSOLE_VERIFY_DEFAULT_DIR,
    "operations_console_landing_smoke": OPERATIONS_CONSOLE_LANDING_SMOKE_DEFAULT_DIR,
}


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


def _count_json_reports(rel_dir: str) -> dict[str, Any]:
    path = Path(rel_dir)
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists() or not path.is_dir():
        return {"directory": rel_dir, "directory_exists": False, "json_report_count": 0}
    return {
        "directory": rel_dir,
        "directory_exists": True,
        "json_report_count": sum(1 for item in path.iterdir() if item.is_file() and item.suffix.lower() == ".json"),
    }


def _latest_json_report(rel_dir: str) -> Path | None:
    path = Path(rel_dir)
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists() or not path.is_dir():
        return None
    files = [item for item in path.iterdir() if item.is_file() and item.suffix.lower() == ".json"]
    if not files:
        return None
    return max(files, key=_json_report_sort_key)


def _json_report_sort_key(item: Path) -> tuple[str, float, str]:
    try:
        payload = json.loads(item.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    generated_at = str(payload.get("generated_at") or "") if isinstance(payload, dict) else ""
    return (generated_at, item.stat().st_mtime, item.name)


def _preferred_frontend_build_report(rel_dir: str) -> Path | None:
    path = Path(rel_dir)
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists() or not path.is_dir():
        return None

    successful: list[Path] = []
    fallback: list[Path] = []
    for item in path.iterdir():
        if not item.is_file() or item.suffix.lower() != ".json":
            continue
        fallback.append(item)
        try:
            payload = json.loads(item.read_text(encoding="utf-8"))
        except Exception:
            continue
        if payload.get("status") == "success" and payload.get("build_executed") is True:
            successful.append(item)

    candidates = successful or fallback
    if not candidates:
        return None
    return max(candidates, key=_json_report_sort_key)


def _get_production_pilot_bootstrap_report_dir() -> str:
    override = (os.getenv("PRODUCTION_PILOT_BOOTSTRAP_REPORT_DIR", "") or "").strip()
    return override or PRODUCTION_PILOT_BOOTSTRAP_DEFAULT_DIR


def _get_frontend_production_build_report_dir() -> str:
    override = (os.getenv("FRONTEND_PRODUCTION_BUILD_REPORT_DIR", "") or "").strip()
    return override or FRONTEND_PRODUCTION_BUILD_DEFAULT_DIR


def _get_production_runtime_smoke_report_dir() -> str:
    override = (os.getenv("PRODUCTION_RUNTIME_SMOKE_REPORT_DIR", "") or "").strip()
    return override or PRODUCTION_RUNTIME_SMOKE_DEFAULT_DIR


def _get_production_pilot_signoff_report_dir() -> str:
    override = (os.getenv("PRODUCTION_PILOT_SIGNOFF_REPORT_DIR", "") or "").strip()
    return override or PRODUCTION_PILOT_SIGNOFF_DEFAULT_DIR


def _get_business_system_read_smoke_report_dir() -> str:
    override = (os.getenv("BUSINESS_SYSTEM_READ_SMOKE_REPORT_DIR", "") or "").strip()
    return override or BUSINESS_SYSTEM_READ_SMOKE_DEFAULT_DIR


def _get_business_system_input_packet_report_dir() -> str:
    override = (os.getenv("BUSINESS_SYSTEM_INPUT_PACKET_REPORT_DIR", "") or "").strip()
    return override or BUSINESS_SYSTEM_INPUT_PACKET_DEFAULT_DIR


def _get_business_system_production_readiness_report_dir() -> str:
    override = (os.getenv("BUSINESS_SYSTEM_PRODUCTION_READINESS_REPORT_DIR", "") or "").strip()
    return override or BUSINESS_SYSTEM_PRODUCTION_READINESS_DEFAULT_DIR


def _get_real_integration_staging_smoke_report_dir() -> str:
    override = (os.getenv("REAL_INTEGRATION_STAGING_SMOKE_REPORT_DIR", "") or "").strip()
    return override or REAL_INTEGRATION_STAGING_SMOKE_DEFAULT_DIR


def _get_real_production_environment_checklist_report_dir() -> str:
    override = (os.getenv("REAL_PRODUCTION_ENVIRONMENT_CHECKLIST_REPORT_DIR", "") or "").strip()
    return override or REAL_PRODUCTION_ENVIRONMENT_CHECKLIST_DEFAULT_DIR


def _get_production_landing_action_pack_report_dir() -> str:
    override = (os.getenv("PRODUCTION_LANDING_ACTION_PACK_REPORT_DIR", "") or "").strip()
    return override or PRODUCTION_LANDING_ACTION_PACK_DEFAULT_DIR


def _get_production_landing_blocker_resolution_report_dir() -> str:
    override = (os.getenv("PRODUCTION_LANDING_BLOCKER_RESOLUTION_REPORT_DIR", "") or "").strip()
    return override or PRODUCTION_LANDING_BLOCKER_RESOLUTION_DEFAULT_DIR


def _get_production_landing_final_verification_report_dir() -> str:
    override = (os.getenv("PRODUCTION_LANDING_FINAL_VERIFICATION_REPORT_DIR", "") or "").strip()
    return override or PRODUCTION_LANDING_FINAL_VERIFICATION_DEFAULT_DIR


def _get_production_landing_status_report_dir() -> str:
    override = (os.getenv("PRODUCTION_LANDING_STATUS_REPORT_DIR", "") or "").strip()
    return override or PRODUCTION_LANDING_STATUS_DEFAULT_DIR


def _get_production_landing_xiaomi_llm_preflight_report_dir() -> str:
    override = (os.getenv("PRODUCTION_LANDING_XIAOMI_LLM_PREFLIGHT_REPORT_DIR", "") or "").strip()
    return override or PRODUCTION_LANDING_XIAOMI_LLM_PREFLIGHT_DEFAULT_DIR


def _get_operations_console_landing_smoke_report_dir() -> str:
    override = (os.getenv("OPERATIONS_CONSOLE_LANDING_SMOKE_REPORT_DIR", "") or "").strip()
    return override or OPERATIONS_CONSOLE_LANDING_SMOKE_DEFAULT_DIR


def _get_production_landing_env_check_report_dir() -> str:
    override = (os.getenv("PRODUCTION_LANDING_ENV_CHECK_REPORT_DIR", "") or "").strip()
    return override or PRODUCTION_LANDING_ENV_CHECK_DEFAULT_DIR


def _get_production_landing_env_runner_report_dir() -> str:
    override = (os.getenv("PRODUCTION_LANDING_ENV_RUNNER_REPORT_DIR", "") or "").strip()
    return override or PRODUCTION_LANDING_ENV_RUNNER_DEFAULT_DIR


def _get_production_landing_execution_gate_report_dir() -> str:
    override = (os.getenv("PRODUCTION_LANDING_EXECUTION_GATE_REPORT_DIR", "") or "").strip()
    return override or PRODUCTION_LANDING_EXECUTION_GATE_DEFAULT_DIR


def _get_production_landing_input_readiness_report_dir() -> str:
    override = (os.getenv("PRODUCTION_LANDING_INPUT_READINESS_REPORT_DIR", "") or "").strip()
    return override or PRODUCTION_LANDING_INPUT_READINESS_DEFAULT_DIR


def _get_manual_signoff_evidence_ack_status_report_dir() -> str:
    override = (os.getenv("MANUAL_SIGNOFF_EVIDENCE_ACK_STATUS_REPORT_DIR", "") or "").strip()
    return override or MANUAL_SIGNOFF_EVIDENCE_ACK_STATUS_DEFAULT_DIR


def _get_manual_signoff_record_validation_report_dir() -> str:
    override = (os.getenv("MANUAL_SIGNOFF_RECORD_VALIDATION_REPORT_DIR", "") or "").strip()
    return override or MANUAL_SIGNOFF_RECORD_VALIDATION_DEFAULT_DIR


def _get_manual_signoff_record_fill_report_dir() -> str:
    override = (os.getenv("MANUAL_SIGNOFF_RECORD_FILL_REPORT_DIR", "") or "").strip()
    return override or MANUAL_SIGNOFF_RECORD_FILL_DEFAULT_DIR


def _get_production_landing_signoff_closeout_report_dir() -> str:
    override = (os.getenv("PRODUCTION_LANDING_SIGNOFF_CLOSEOUT_REPORT_DIR", "") or "").strip()
    return override or PRODUCTION_LANDING_SIGNOFF_CLOSEOUT_DEFAULT_DIR


def _get_production_landing_pre_signoff_gate_report_dir() -> str:
    override = (os.getenv("PRODUCTION_LANDING_PRE_SIGNOFF_GATE_REPORT_DIR", "") or "").strip()
    return override or PRODUCTION_LANDING_PRE_SIGNOFF_GATE_DEFAULT_DIR


def _get_production_landing_signoff_reviewer_packet_report_dir() -> str:
    override = (os.getenv("PRODUCTION_LANDING_SIGNOFF_REVIEWER_PACKET_REPORT_DIR", "") or "").strip()
    return override or PRODUCTION_LANDING_SIGNOFF_REVIEWER_PACKET_DEFAULT_DIR


def _get_manual_signoff_record_promote_report_dir() -> str:
    override = (os.getenv("MANUAL_SIGNOFF_RECORD_PROMOTE_REPORT_DIR", "") or "").strip()
    return override or MANUAL_SIGNOFF_RECORD_PROMOTE_DEFAULT_DIR


def _get_production_landing_text_quality_report_dir() -> str:
    override = (os.getenv("PRODUCTION_LANDING_TEXT_QUALITY_REPORT_DIR", "") or "").strip()
    return override or PRODUCTION_LANDING_TEXT_QUALITY_DEFAULT_DIR


def _get_production_landing_evidence_freshness_report_dir() -> str:
    override = (os.getenv("PRODUCTION_LANDING_EVIDENCE_FRESHNESS_REPORT_DIR", "") or "").strip()
    return override or PRODUCTION_LANDING_EVIDENCE_FRESHNESS_DEFAULT_DIR


def _get_production_pilot_evidence_bundle_report_dir() -> str:
    override = (os.getenv("PRODUCTION_PILOT_EVIDENCE_BUNDLE_REPORT_DIR", "") or "").strip()
    return override or PRODUCTION_PILOT_EVIDENCE_BUNDLE_DEFAULT_DIR


def _get_controlled_pilot_launch_gate_report_dir() -> str:
    override = (os.getenv("CONTROLLED_PILOT_LAUNCH_GATE_REPORT_DIR", "") or "").strip()
    return override or CONTROLLED_PILOT_LAUNCH_GATE_DEFAULT_DIR


def _get_controlled_pilot_launch_package_report_dir() -> str:
    override = (os.getenv("CONTROLLED_PILOT_LAUNCH_PACKAGE_REPORT_DIR", "") or "").strip()
    return override or CONTROLLED_PILOT_LAUNCH_PACKAGE_DEFAULT_DIR


def _get_controlled_pilot_window_record_report_dir() -> str:
    override = (os.getenv("CONTROLLED_PILOT_WINDOW_RECORD_REPORT_DIR", "") or "").strip()
    return override or CONTROLLED_PILOT_WINDOW_RECORD_DEFAULT_DIR


def _get_controlled_pilot_window_status_report_dir() -> str:
    override = (os.getenv("CONTROLLED_PILOT_WINDOW_STATUS_REPORT_DIR", "") or "").strip()
    return override or CONTROLLED_PILOT_WINDOW_STATUS_DEFAULT_DIR


def _get_controlled_pilot_status_summary_report_dir() -> str:
    override = (os.getenv("CONTROLLED_PILOT_STATUS_SUMMARY_REPORT_DIR", "") or "").strip()
    return override or CONTROLLED_PILOT_STATUS_SUMMARY_DEFAULT_DIR


def _get_controlled_pilot_operator_packet_report_dir() -> str:
    override = (os.getenv("CONTROLLED_PILOT_OPERATOR_PACKET_REPORT_DIR", "") or "").strip()
    return override or CONTROLLED_PILOT_OPERATOR_PACKET_DEFAULT_DIR


def _get_controlled_pilot_console_verify_report_dir() -> str:
    override = (os.getenv("CONTROLLED_PILOT_CONSOLE_VERIFY_REPORT_DIR", "") or "").strip()
    return override or CONTROLLED_PILOT_CONSOLE_VERIFY_DEFAULT_DIR


def _get_controlled_pilot_console_preflight_report_dir() -> str:
    override = (os.getenv("CONTROLLED_PILOT_CONSOLE_PREFLIGHT_REPORT_DIR", "") or "").strip()
    return override or CONTROLLED_PILOT_CONSOLE_PREFLIGHT_DEFAULT_DIR


SAFE_SECRET_PLACEHOLDERS = {
    "secret-managed-token",
    "secret-managed-url",
    "external-secret-managed-url",
    "set-in-local-env-only",
}
SECRET_VALUE_MARKERS = (
    "token=",
    "api_key=",
    "apikey=",
    "client_secret=",
    "password=",
    "secret=",
)


def _extract_marker_value(text: str, index: int, marker: str) -> str:
    raw_tail = text[index + len(marker) :]
    raw_value = ""
    for char in raw_tail:
        if char.isspace() or char in {",", "]", "}", "\"", "'", ";", "|"}:
            break
        raw_value += char
    return raw_value.strip("<>").lower()


def _has_secret_like_text(value: Any) -> bool:
    text = str(value)
    lowered = text.lower()
    if any(marker in lowered for marker in ("sk-", "tp-", "bearer ", "postgresql://", "postgres://", "redis://")):
        return True
    for marker in SECRET_VALUE_MARKERS:
        start = 0
        while True:
            index = lowered.find(marker, start)
            if index < 0:
                break
            candidate = _extract_marker_value(text, index, marker)
            if candidate and candidate not in SAFE_SECRET_PLACEHOLDERS:
                return True
            start = index + len(marker)
    return False


def _safe_command_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    commands: list[str] = []
    for item in value:
        text = str(item)
        if _has_secret_like_text(text):
            commands.append("[redacted-secret-like-command]")
        else:
            commands.append(text)
    return commands[:8]


def _safe_text_value(value: Any) -> str:
    safe = _safe_command_list([value])
    return safe[0] if safe else ""


def _safe_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_safe_text_value(item) for item in value]


def _safe_string_map(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): _safe_text_value(item) for key, item in value.items()}


def _safe_required_inputs(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    inputs: list[dict[str, Any]] = []
    for item in value[:12]:
        if not isinstance(item, dict):
            continue
        blocking_items = item.get("blocking_evidence_items") if isinstance(item.get("blocking_evidence_items"), list) else []
        inputs.append(
            {
                "input_id": _safe_text_value(item.get("input_id") or ""),
                "status": _safe_text_value(item.get("status") or ""),
                "template": _safe_text_value(item.get("template") or ""),
                "filled_record": _safe_text_value(item.get("filled_record") or ""),
                "draft": _safe_text_value(item.get("draft") or ""),
                "required_domains": _safe_text_value(item.get("required_domains") or ""),
                "required_env": " | ".join(_safe_text_value(value) for value in item.get("required_env", [])[:16])
                if isinstance(item.get("required_env"), list)
                else "",
                "blocking_evidence_items": [
                    {
                        "item": _safe_text_value(blocker.get("item") or ""),
                        "source_status": _safe_text_value(blocker.get("source_status") or ""),
                        "missing_conditions": [
                            _safe_text_value(condition)
                            for condition in (
                                blocker.get("missing_conditions")
                                if isinstance(blocker.get("missing_conditions"), list)
                                else []
                            )[:12]
                        ],
                        "acceptance_blockers": [
                            _safe_text_value(condition)
                            for condition in (
                                blocker.get("acceptance_blockers")
                                if isinstance(blocker.get("acceptance_blockers"), list)
                                else []
                            )[:12]
                        ],
                        "safe_next_action": _safe_text_value(blocker.get("safe_next_action") or ""),
                        "safe_commands": _safe_command_list(blocker.get("safe_commands")),
                    }
                    for blocker in blocking_items[:8]
                    if isinstance(blocker, dict)
                ],
                "command_after_fill": _safe_command_list([item.get("command_after_fill", "")])[0]
                if item.get("command_after_fill")
                else "",
                "promote_command_after_manual_fill": _safe_command_list(
                    [item.get("promote_command_after_manual_fill", "")]
                )[0]
                if item.get("promote_command_after_manual_fill")
                else "",
                "process_env_only_llm_preflight_command": _safe_command_list(
                    [item.get("process_env_only_llm_preflight_command", "")]
                )[0]
                if item.get("process_env_only_llm_preflight_command")
                else "",
            }
        )
    return inputs


def _safe_template_status(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    templates: dict[str, dict[str, Any]] = {}
    for key, item in value.items():
        if not isinstance(item, dict):
            continue
        templates[str(key)] = {
            "path": str(item.get("path") or ""),
            "exists": bool(item.get("exists", False)),
            "size_bytes": int(item.get("size_bytes", 0) or 0),
        }
    return templates


def _safe_blocker_resolution_actions(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    actions: list[dict[str, Any]] = []
    for item in value[:12]:
        if not isinstance(item, dict):
            continue
        evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
        actions.append(
            {
                "action_id": _safe_text_value(item.get("action_id") or ""),
                "status": _safe_text_value(item.get("status") or "required"),
                "owner": _safe_text_value(item.get("owner") or ""),
                "evidence": {
                    str(key): (
                        [_safe_text_value(item) for item in value[:12]]
                        if isinstance(value, list)
                        else _safe_text_value(value)
                    )
                    for key, value in evidence.items()
                },
                "safe_commands": _safe_command_list(item.get("safe_commands")),
            }
        )
    return actions


def _safe_final_verification_requirements(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    requirements: list[dict[str, Any]] = []
    for item in value[:16]:
        if not isinstance(item, dict):
            continue
        missing = item.get("missing_conditions") if isinstance(item.get("missing_conditions"), list) else []
        requirements.append(
            {
                "requirement_id": _safe_text_value(item.get("requirement_id") or ""),
                "passed": bool(item.get("passed", False)),
                "missing_conditions": [_safe_text_value(value) for value in missing[:16]],
            }
        )
    return requirements


def _safe_landing_input_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in value[:12]:
        if not isinstance(item, dict):
            continue
        missing = item.get("missing_conditions") if isinstance(item.get("missing_conditions"), list) else []
        rows.append(
            {
                "input_id": _safe_text_value(item.get("input_id") or ""),
                "path": _safe_text_value(item.get("path") or ""),
                "present": bool(item.get("present", False)),
                "status": _safe_text_value(item.get("status") or "partial"),
                "missing_conditions": [_safe_text_value(value) for value in missing[:24]],
                "missing_count": len(missing),
                "ready_count": int(item.get("ready_count", 0) or 0),
                "closure_item_count": int(item.get("closure_item_count", 0) or 0),
                "base_url_present": bool(item.get("base_url_present", False)),
                "token_present": bool(item.get("token_present", False)),
                "database_connected": bool(item.get("database_connected", False)),
                "redis_connected": bool(item.get("redis_connected", False)),
                "external_mcp_connected": bool(item.get("external_mcp_connected", False)),
                "real_infra_ready": bool(item.get("real_infra_ready", False)),
                "read_only": bool(item.get("read_only", False)),
                "write_enabled": bool(item.get("write_enabled", False)),
                "secret_plaintext_output": bool(item.get("secret_plaintext_output", False)),
                "auto_approved": bool(item.get("auto_approved", False)),
                "auto_closed": bool(item.get("auto_closed", False)),
                "next_action": _safe_text_value(item.get("next_action") or ""),
                "command_after_fill": _safe_text_value(item.get("command_after_fill") or ""),
                "required_env": [_safe_text_value(value) for value in item.get("required_env", [])[:16]]
                if isinstance(item.get("required_env"), list)
                else [],
            }
        )
    return rows


def _safe_manual_signoff_ack_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in value[:12]:
        if not isinstance(item, dict):
            continue
        missing = item.get("missing_conditions") if isinstance(item.get("missing_conditions"), list) else []
        rows.append(
            {
                "item": _safe_text_value(item.get("item") or ""),
                "latest_report": _safe_text_value(item.get("latest_report") or ""),
                "report_present": bool(item.get("report_present", False)),
                "source_status": _safe_text_value(item.get("source_status") or "missing"),
                "recommended_accept": bool(item.get("recommended_accept", False)),
                "missing_conditions": [_safe_text_value(value) for value in missing[:24]],
                "missing_count": len(missing),
            }
        )
    return rows


def _safe_manual_signoff_validation_roles(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    roles: list[dict[str, Any]] = []
    for item in value[:8]:
        if not isinstance(item, dict):
            continue
        roles.append(
            {
                "role": _safe_text_value(item.get("role") or ""),
                "name_present": bool(item.get("name_present", False)),
                "approved": bool(item.get("approved", False)),
            }
        )
    return roles


def _safe_manual_signoff_validation_evidence(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in value[:12]:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "item": _safe_text_value(item.get("item") or ""),
                "accepted": bool(item.get("accepted", False)),
                "latest_report": _safe_text_value(item.get("latest_report") or ""),
                "note_present": bool(item.get("note_present", False)),
            }
        )
    return rows


def _safe_text_quality_files(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in value[:16]:
        if not isinstance(item, dict):
            continue
        markers = item.get("mojibake_markers") if isinstance(item.get("mojibake_markers"), list) else []
        missing = item.get("missing_conditions") if isinstance(item.get("missing_conditions"), list) else []
        rows.append(
            {
                "path": _safe_text_value(item.get("path") or ""),
                "exists": bool(item.get("exists", False)),
                "status": _safe_text_value(item.get("status") or "skipped"),
                "mojibake_markers": [_safe_text_value(marker) for marker in markers[:12]],
                "secret_like_detected": bool(item.get("secret_like_detected", False)),
                "missing_conditions": [_safe_text_value(condition) for condition in missing[:12]],
            }
        )
    return rows


def _safe_business_env_profile(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "execution_requested": False,
            "ready_for_execute": False,
            "required_env": [],
            "auth_mode": "",
            "safe_commands": {},
            "present": {},
            "public_production_gap": True,
            "next_action": "",
        }
    required_env = value.get("required_env") if isinstance(value.get("required_env"), list) else []
    present = value.get("present") if isinstance(value.get("present"), dict) else {}
    safe_commands = value.get("safe_commands") if isinstance(value.get("safe_commands"), dict) else {}
    return {
        "execution_requested": bool(value.get("execution_requested", False)),
        "ready_for_execute": bool(value.get("ready_for_execute", False)),
        "required_env": [_safe_text_value(item) for item in required_env[:16]],
        "auth_mode": _safe_text_value(value.get("auth_mode") or ""),
        "safe_commands": {str(key): _safe_text_value(item) for key, item in safe_commands.items()},
        "present": {str(key): bool(item) for key, item in present.items()},
        "public_production_gap": bool(value.get("public_production_gap", True)),
        "next_action": _safe_text_value(value.get("next_action") or ""),
    }


def _safe_staging_domain_preflight(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "domain_id": "",
            "status": "skipped",
            "execution_allowed": False,
            "execution_invoked": False,
            "ready_for_execute": False,
            "missing_count": 0,
            "env_present": {},
            "required_env": [],
            "next_action": "",
        }
    required_env = value.get("required_env") if isinstance(value.get("required_env"), list) else []
    env_present = value.get("env_present") if isinstance(value.get("env_present"), dict) else {}
    return {
        "domain_id": _safe_text_value(value.get("domain_id") or ""),
        "status": _safe_text_value(value.get("status") or "skipped"),
        "execution_allowed": bool(value.get("execution_allowed", False)),
        "execution_invoked": bool(value.get("execution_invoked", False)),
        "ready_for_execute": bool(value.get("ready_for_execute", False)),
        "missing_count": int(value.get("missing_count", 0) or 0),
        "env_present": {str(key): bool(item) for key, item in env_present.items()},
        "required_env": [_safe_text_value(item) for item in required_env[:16]],
        "next_action": _safe_text_value(value.get("next_action") or ""),
    }


def _safe_staging_preflight_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "ready_domain_count": 0,
            "domain_count": 0,
            "ready_domains": [],
            "blocked_domain_count": 0,
            "failed_domain_count": 0,
            "all_requested_domains_ready_for_execute": False,
            "domains": [],
        }
    domains = value.get("domains") if isinstance(value.get("domains"), list) else []
    ready_domains = value.get("ready_domains") if isinstance(value.get("ready_domains"), list) else []
    return {
        "ready_domain_count": int(value.get("ready_domain_count", 0) or 0),
        "domain_count": int(value.get("domain_count", 0) or 0),
        "ready_domains": [_safe_text_value(item) for item in ready_domains[:12]],
        "blocked_domain_count": int(value.get("blocked_domain_count", 0) or 0),
        "failed_domain_count": int(value.get("failed_domain_count", 0) or 0),
        "all_requested_domains_ready_for_execute": bool(value.get("all_requested_domains_ready_for_execute", False)),
        "domains": [_safe_staging_domain_preflight(item) for item in domains[:8]],
    }


def _safe_landing_env_check_domains(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    domains: list[dict[str, Any]] = []
    for item in value[:8]:
        if not isinstance(item, dict):
            continue
        missing = item.get("missing_keys") if isinstance(item.get("missing_keys"), list) else []
        placeholders = item.get("placeholder_keys") if isinstance(item.get("placeholder_keys"), list) else []
        mismatches = item.get("mismatch_keys") if isinstance(item.get("mismatch_keys"), list) else []
        domains.append(
            {
                "domain_id": _safe_text_value(item.get("domain_id") or ""),
                "ready_for_execute": bool(item.get("ready_for_execute", False)),
                "blocker_reason": _safe_text_value(item.get("blocker_reason") or ""),
                "next_action": _safe_text_value(item.get("next_action") or ""),
                "command_after_fill": _safe_text_value(item.get("command_after_fill") or ""),
                "required_env_keys": [_safe_text_value(value) for value in (item.get("required_env_keys") if isinstance(item.get("required_env_keys"), list) else [])[:24]],
                "missing_count": int(item.get("missing_count", 0) or 0),
                "placeholder_count": int(item.get("placeholder_count", 0) or 0),
                "mismatch_count": int(item.get("mismatch_count", 0) or 0),
                "missing_keys": [_safe_text_value(value) for value in missing[:16]],
                "placeholder_keys": [_safe_text_value(value) for value in placeholders[:16]],
                "mismatch_keys": [_safe_text_value(value) for value in mismatches[:16]],
            }
        )
    return domains


def _safe_landing_env_blocked_domain_summaries(value: Any) -> list[dict[str, Any]]:
    domains = _safe_landing_env_check_domains(value)
    return [
        {
            "domain_id": item["domain_id"],
            "blocker_reason": item["blocker_reason"],
            "next_action": item["next_action"],
            "missing_count": item["missing_count"],
            "placeholder_count": item["placeholder_count"],
            "mismatch_count": item["mismatch_count"],
            "missing_keys": item["missing_keys"],
            "placeholder_keys": item["placeholder_keys"],
            "mismatch_keys": item["mismatch_keys"],
        }
        for item in domains
        if not item["ready_for_execute"]
    ][:8]


def _collect_production_pilot_bootstrap_summary() -> dict[str, Any]:
    report_dir = _get_production_pilot_bootstrap_report_dir()
    latest = _latest_json_report(report_dir)
    if latest is None:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": PRODUCTION_PILOT_BOOTSTRAP_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": Path(report_dir).exists(),
            "latest_report_present": False,
            "status": "skipped",
            "generated_at": "",
            "local_service_status": "unknown",
            "evidence_count": 0,
            "execute_real_smoke": False,
            "real_llm_executed": False,
            "database_connected": False,
            "redis_connected": False,
            "external_mcp_connected": False,
            "migration_executed": False,
            "business_system_connected": False,
            "business_read_executed": False,
            "business_write_executed": False,
            "business_data_written": False,
            "auth_rbac_acceptance_passed": False,
            "signoff_closeout_passed": False,
            "final_verification_passed": False,
            "pilot_evidence_bundle_passed": False,
            "operations_console_smoke_status": "skipped",
            "frontend_build_passed": False,
            "frontend_build_executed": False,
            "frontend_build_return_code": None,
            "runtime_smoke_passed": False,
            "runtime_smoke_endpoint_check_count": 0,
            "auth_enabled": False,
            "rbac_enabled": False,
            "jwt_token_issued": False,
            "secret_plaintext_output": False,
            "public_production_direct_launch": "No-Go",
            "next_commands": {},
            "evidence_runs": [],
        }

    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": PRODUCTION_PILOT_BOOTSTRAP_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": True,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
            "generated_at": "",
            "local_service_status": "unknown",
            "evidence_count": 0,
            "execute_real_smoke": False,
            "real_llm_executed": False,
            "database_connected": False,
            "redis_connected": False,
            "external_mcp_connected": False,
            "migration_executed": False,
            "business_system_connected": False,
            "business_read_executed": False,
            "business_write_executed": False,
            "business_data_written": False,
            "auth_rbac_acceptance_passed": False,
            "signoff_closeout_passed": False,
            "final_verification_passed": False,
            "pilot_evidence_bundle_passed": False,
            "operations_console_smoke_status": "skipped",
            "frontend_build_passed": False,
            "frontend_build_executed": False,
            "frontend_build_return_code": None,
            "runtime_smoke_passed": False,
            "runtime_smoke_endpoint_check_count": 0,
            "auth_enabled": False,
            "rbac_enabled": False,
            "jwt_token_issued": False,
            "secret_plaintext_output": False,
            "public_production_direct_launch": "No-Go",
            "next_commands": {},
            "evidence_runs": [],
        }

    local_smoke = payload.get("local_service_smoke") if isinstance(payload.get("local_service_smoke"), dict) else {}
    go_no_go = payload.get("go_no_go") if isinstance(payload.get("go_no_go"), dict) else {}
    next_commands = payload.get("next_commands") if isinstance(payload.get("next_commands"), dict) else {}
    evidence_runs = payload.get("evidence_runs") if isinstance(payload.get("evidence_runs"), list) else []

    return {
        "mode": "read_only_latest_report",
        "runbook_path": PRODUCTION_PILOT_BOOTSTRAP_RUNBOOK_PATH,
        "report_dir": report_dir,
        "directory_exists": True,
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": str(payload.get("status") or "skipped"),
        "generated_at": str(payload.get("generated_at") or ""),
        "local_service_status": str(local_smoke.get("status") or "unknown"),
        "evidence_count": int(payload.get("evidence_count", len(evidence_runs)) or 0),
        "execute_real_smoke": bool(payload.get("execute_real_smoke", False)),
        "real_llm_executed": bool(payload.get("real_llm_executed", False)),
        "database_connected": bool(payload.get("database_connected", False)),
        "redis_connected": bool(payload.get("redis_connected", False)),
        "external_mcp_connected": bool(payload.get("external_mcp_connected", False)),
        "migration_executed": bool(payload.get("migration_executed", False)),
        "business_system_connected": bool(payload.get("business_system_connected", False)),
        "business_read_executed": bool(payload.get("business_read_executed", False)),
        "business_write_executed": bool(payload.get("business_write_executed", False)),
        "business_data_written": bool(payload.get("business_data_written", False)),
        "auth_rbac_acceptance_passed": bool(payload.get("auth_rbac_acceptance_passed", False)),
        "signoff_closeout_passed": bool(payload.get("signoff_closeout_passed", False)),
        "final_verification_passed": bool(payload.get("final_verification_passed", False)),
        "pilot_evidence_bundle_passed": bool(payload.get("pilot_evidence_bundle_passed", False)),
        "operations_console_smoke_status": str(payload.get("operations_console_smoke_status") or "skipped"),
        "frontend_build_passed": bool(payload.get("frontend_build_passed", False)),
        "frontend_build_executed": bool(payload.get("frontend_build_executed", False)),
        "frontend_build_return_code": payload.get("frontend_build_return_code"),
        "runtime_smoke_passed": bool(payload.get("runtime_smoke_passed", False)),
        "runtime_smoke_endpoint_check_count": int(payload.get("runtime_smoke_endpoint_check_count", 0) or 0),
        "auth_enabled": bool(payload.get("auth_enabled", False)),
        "rbac_enabled": bool(payload.get("rbac_enabled", False)),
        "jwt_token_issued": bool(payload.get("jwt_token_issued", False)),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
        "public_production_direct_launch": str(go_no_go.get("public_production_direct_launch") or "No-Go"),
        "next_commands": {str(key): _safe_command_list(value) for key, value in next_commands.items()},
        "evidence_runs": [
            {
                "evidence_id": str(item.get("evidence_id") or ""),
                "status": str(item.get("status") or "skipped"),
                "json_path": str(item.get("json_path") or ""),
            }
            for item in evidence_runs[:12]
            if isinstance(item, dict)
        ],
    }


def _collect_frontend_production_build_summary() -> dict[str, Any]:
    report_dir = _get_frontend_production_build_report_dir()
    latest = _preferred_frontend_build_report(report_dir)
    if latest is None:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": FRONTEND_PRODUCTION_BUILD_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": Path(report_dir).exists(),
            "latest_report_present": False,
            "status": "skipped",
            "generated_at": "",
            "execute": False,
            "build_executed": False,
            "return_code": None,
            "frontend_dir_present": False,
            "package_json_present": False,
            "node_modules_present": False,
            "missing_conditions": ["frontend_production_build_report:not_found"],
            "secret_plaintext_output": False,
            "public_production_direct_launch": "No-Go",
        }

    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": FRONTEND_PRODUCTION_BUILD_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": True,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
            "generated_at": "",
            "execute": False,
            "build_executed": False,
            "return_code": None,
            "frontend_dir_present": False,
            "package_json_present": False,
            "node_modules_present": False,
            "missing_conditions": ["frontend_production_build_report:unreadable_json"],
            "secret_plaintext_output": False,
            "public_production_direct_launch": "No-Go",
        }

    go_no_go = payload.get("go_no_go") if isinstance(payload.get("go_no_go"), dict) else {}
    missing_conditions = payload.get("missing_conditions") if isinstance(payload.get("missing_conditions"), list) else []
    return {
        "mode": "read_only_latest_report",
        "runbook_path": FRONTEND_PRODUCTION_BUILD_RUNBOOK_PATH,
        "report_dir": report_dir,
        "directory_exists": True,
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": str(payload.get("status") or "skipped"),
        "generated_at": str(payload.get("generated_at") or ""),
        "execute": bool(payload.get("execute", False)),
        "build_executed": bool(payload.get("build_executed", False)),
        "return_code": payload.get("return_code"),
        "frontend_dir_present": bool(payload.get("frontend_dir_present", False)),
        "package_json_present": bool(payload.get("package_json_present", False)),
        "node_modules_present": bool(payload.get("node_modules_present", False)),
        "missing_conditions": [str(item) for item in missing_conditions[:12]],
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
        "public_production_direct_launch": str(go_no_go.get("public_production_direct_launch") or "No-Go"),
    }


def _collect_production_runtime_smoke_summary() -> dict[str, Any]:
    report_dir = _get_production_runtime_smoke_report_dir()
    latest = _latest_json_report(report_dir)
    if latest is None:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": PRODUCTION_RUNTIME_SMOKE_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": Path(report_dir).exists(),
            "latest_report_present": False,
            "status": "skipped",
            "generated_at": "",
            "endpoint_check_count": 0,
            "operations_contract_status": "skipped",
            "frontend_build_status": "skipped",
            "frontend_build_executed": False,
            "bootstrap_status": "skipped",
            "business_system_connected": False,
            "secret_plaintext_output": False,
            "public_production_direct_launch": "No-Go",
        }

    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": PRODUCTION_RUNTIME_SMOKE_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": True,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
            "generated_at": "",
            "endpoint_check_count": 0,
            "operations_contract_status": "blocked",
            "frontend_build_status": "skipped",
            "frontend_build_executed": False,
            "bootstrap_status": "skipped",
            "business_system_connected": False,
            "secret_plaintext_output": False,
            "public_production_direct_launch": "No-Go",
        }

    endpoint_checks = payload.get("endpoint_checks") if isinstance(payload.get("endpoint_checks"), list) else []
    contract = payload.get("operations_contract") if isinstance(payload.get("operations_contract"), dict) else {}
    go_no_go = payload.get("go_no_go") if isinstance(payload.get("go_no_go"), dict) else {}
    return {
        "mode": "read_only_latest_report",
        "runbook_path": PRODUCTION_RUNTIME_SMOKE_RUNBOOK_PATH,
        "report_dir": report_dir,
        "directory_exists": True,
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": str(payload.get("status") or "skipped"),
        "generated_at": str(payload.get("generated_at") or ""),
        "endpoint_check_count": len(endpoint_checks),
        "operations_contract_status": str(contract.get("status") or "skipped"),
        "frontend_build_status": str(contract.get("frontend_build_status") or "skipped"),
        "frontend_build_executed": bool(contract.get("frontend_build_executed", False)),
        "bootstrap_status": str(contract.get("bootstrap_status") or "skipped"),
        "business_system_connected": bool(contract.get("business_system_connected", False)),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
        "public_production_direct_launch": str(go_no_go.get("public_production_direct_launch") or "No-Go"),
    }


def _collect_production_pilot_signoff_summary() -> dict[str, Any]:
    report_dir = _get_production_pilot_signoff_report_dir()
    latest = _latest_json_report(report_dir)
    if latest is None:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": PRODUCTION_PILOT_SIGNOFF_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": Path(report_dir).exists(),
            "latest_report_present": False,
            "status": "skipped",
            "generated_at": "",
            "readiness_item_count": 0,
            "manual_signoff_required": True,
            "manual_signoff_completed": False,
            "manual_signoff_record_present": False,
            "manual_signoff_package_status": "skipped",
            "manual_signoff_roles": [],
            "manual_signoff_decision": "",
            "manual_signoff_blockers": ["production_pilot_signoff_report:not_found"],
            "closure_evidence_summary": {
                "latest_report": "",
                "report_count": 0,
                "closure_item_count": 0,
                "review_ready_count": 0,
                "evidence_missing_count": 0,
                "evidence_incomplete_count": 0,
                "blocked_closure_count": 0,
                "evidence_readiness_summary": {
                    "local_evidence_available_count": 0,
                    "runbook_only_count": 0,
                    "missing_count": 0,
                    "manual_review_required": False,
                    "auto_approved": False,
                    "auto_closed": False,
                },
            },
            "auto_signed": False,
            "auto_approved": False,
            "secret_plaintext_output": False,
            "recommendation": "Manual-Review",
            "production_pilot": "Needs-Input",
            "enterprise_landing_state": "needs-local-evidence",
            "controlled_pilot_manual_review_ready": False,
            "database_connected": False,
            "redis_connected": False,
            "external_mcp_connected": False,
            "real_infra_ready": False,
            "production_blockers": ["production_pilot_signoff_report:not_found"],
            "public_production_direct_launch": "No-Go",
        }

    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": PRODUCTION_PILOT_SIGNOFF_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": True,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
            "generated_at": "",
            "readiness_item_count": 0,
            "manual_signoff_required": True,
            "manual_signoff_completed": False,
            "manual_signoff_record_present": False,
            "manual_signoff_package_status": "blocked",
            "manual_signoff_roles": [],
            "manual_signoff_decision": "",
            "manual_signoff_blockers": ["production_pilot_signoff_report:unreadable_json"],
            "closure_evidence_summary": {
                "latest_report": "",
                "report_count": 0,
                "closure_item_count": 0,
                "review_ready_count": 0,
                "evidence_missing_count": 0,
                "evidence_incomplete_count": 0,
                "blocked_closure_count": 0,
                "evidence_readiness_summary": {
                    "local_evidence_available_count": 0,
                    "runbook_only_count": 0,
                    "missing_count": 0,
                    "manual_review_required": False,
                    "auto_approved": False,
                    "auto_closed": False,
                },
            },
            "auto_signed": False,
            "auto_approved": False,
            "secret_plaintext_output": False,
            "recommendation": "No-Go",
            "production_pilot": "Needs-Input",
            "enterprise_landing_state": "needs-local-evidence",
            "controlled_pilot_manual_review_ready": False,
            "database_connected": False,
            "redis_connected": False,
            "external_mcp_connected": False,
            "real_infra_ready": False,
            "production_blockers": ["production_pilot_signoff_report:unreadable_json"],
            "public_production_direct_launch": "No-Go",
        }

    go_no_go = payload.get("go_no_go") if isinstance(payload.get("go_no_go"), dict) else {}
    readiness_items = payload.get("readiness_items") if isinstance(payload.get("readiness_items"), list) else []
    landing_status = payload.get("landing_status") if isinstance(payload.get("landing_status"), dict) else {}
    blockers = landing_status.get("production_blockers") if isinstance(landing_status.get("production_blockers"), list) else []
    signoff_sections = payload.get("signoff_sections") if isinstance(payload.get("signoff_sections"), list) else []
    closure_section = next(
        (
            item
            for item in signoff_sections
            if isinstance(item, dict) and str(item.get("section") or "") == "closure_evidence_summary"
        ),
        {},
    )
    if not closure_section and isinstance(payload.get("closure_evidence_summary"), dict):
        closure_section = payload.get("closure_evidence_summary") or {}
    evidence_readiness = (
        closure_section.get("evidence_readiness_summary")
        if isinstance(closure_section.get("evidence_readiness_summary"), dict)
        else {}
    )
    return {
        "mode": "read_only_latest_report",
        "runbook_path": PRODUCTION_PILOT_SIGNOFF_RUNBOOK_PATH,
        "report_dir": report_dir,
        "directory_exists": True,
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": str(payload.get("status") or "skipped"),
        "generated_at": str(payload.get("generated_at") or ""),
        "readiness_item_count": len(readiness_items),
        "manual_signoff_required": bool(payload.get("manual_signoff_required", True)),
        "manual_signoff_completed": bool(payload.get("manual_signoff_completed", False)),
        "manual_signoff_record_present": bool(payload.get("manual_signoff_record_present", False)),
        "manual_signoff_package_status": str(payload.get("manual_signoff_package_status") or "skipped"),
        "manual_signoff_roles": [
            str(item) for item in (payload.get("manual_signoff_roles") if isinstance(payload.get("manual_signoff_roles"), list) else [])[:8]
        ],
        "manual_signoff_decision": str(payload.get("manual_signoff_decision") or ""),
        "manual_signoff_blockers": [
            str(item)
            for item in (
                payload.get("manual_signoff_blockers") if isinstance(payload.get("manual_signoff_blockers"), list) else []
            )[:12]
        ],
        "closure_evidence_summary": {
            "latest_report": str(closure_section.get("latest_report") or ""),
            "report_count": int(closure_section.get("report_count", 0) or 0),
            "closure_item_count": int(closure_section.get("closure_item_count", 0) or 0),
            "review_ready_count": int(closure_section.get("review_ready_count", 0) or 0),
            "evidence_missing_count": int(closure_section.get("evidence_missing_count", 0) or 0),
            "evidence_incomplete_count": int(closure_section.get("evidence_incomplete_count", 0) or 0),
            "blocked_closure_count": int(closure_section.get("blocked_closure_count", 0) or 0),
            "evidence_readiness_summary": {
                "local_evidence_available_count": int(
                    evidence_readiness.get("local_evidence_available_count", 0) or 0
                ),
                "runbook_only_count": int(evidence_readiness.get("runbook_only_count", 0) or 0),
                "missing_count": int(evidence_readiness.get("missing_count", 0) or 0),
                "manual_review_required": bool(evidence_readiness.get("manual_review_required", False)),
                "auto_approved": bool(evidence_readiness.get("auto_approved", False)),
                "auto_closed": bool(evidence_readiness.get("auto_closed", False)),
            },
        },
        "auto_signed": bool(payload.get("auto_signed", False)),
        "auto_approved": bool(payload.get("auto_approved", False)),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
        "recommendation": str(go_no_go.get("recommendation") or "Manual-Review"),
        "production_pilot": str(go_no_go.get("production_pilot") or "Needs-Input"),
        "enterprise_landing_state": str(landing_status.get("enterprise_landing_state") or "needs-local-evidence"),
        "controlled_pilot_manual_review_ready": bool(landing_status.get("controlled_pilot_manual_review_ready", False)),
        "database_connected": bool(landing_status.get("database_connected", False)),
        "redis_connected": bool(landing_status.get("redis_connected", False)),
        "external_mcp_connected": bool(landing_status.get("external_mcp_connected", False)),
        "real_infra_ready": bool(landing_status.get("real_infra_ready", False)),
        "production_blockers": [str(item) for item in blockers[:12]],
        "public_production_direct_launch": str(go_no_go.get("public_production_direct_launch") or "No-Go"),
    }


def _collect_business_system_read_smoke_summary() -> dict[str, Any]:
    report_dir = _get_business_system_read_smoke_report_dir()
    latest = _latest_json_report(report_dir)
    if latest is None:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": BUSINESS_SYSTEM_READ_SMOKE_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": Path(report_dir).exists(),
            "latest_report_present": False,
            "status": "skipped",
            "generated_at": "",
            "execute": False,
            "execution_requested": False,
            "read_only": True,
            "env_profile": _safe_business_env_profile({}),
            "business_system_connected": False,
            "business_read_executed": False,
            "business_write_executed": False,
            "business_data_written": False,
            "approval_bypassed": False,
            "audit_bypassed": False,
            "missing_conditions": ["business_system_read_smoke_report:not_found"],
            "secret_plaintext_output": False,
            "business_system_read_smoke": "Needs-Input",
            "public_production_direct_launch": "No-Go",
            "manual_signoff_required": True,
        }

    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": BUSINESS_SYSTEM_READ_SMOKE_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": True,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
            "generated_at": "",
            "execute": False,
            "execution_requested": False,
            "read_only": True,
            "env_profile": _safe_business_env_profile({}),
            "business_system_connected": False,
            "business_read_executed": False,
            "business_write_executed": False,
            "business_data_written": False,
            "approval_bypassed": False,
            "audit_bypassed": False,
            "missing_conditions": ["business_system_read_smoke_report:unreadable_json"],
            "secret_plaintext_output": False,
            "business_system_read_smoke": "Needs-Input",
            "public_production_direct_launch": "No-Go",
            "manual_signoff_required": True,
        }

    go_no_go = payload.get("go_no_go") if isinstance(payload.get("go_no_go"), dict) else {}
    missing_conditions = payload.get("missing_conditions") if isinstance(payload.get("missing_conditions"), list) else []
    return {
        "mode": "read_only_latest_report",
        "runbook_path": BUSINESS_SYSTEM_READ_SMOKE_RUNBOOK_PATH,
        "report_dir": report_dir,
        "directory_exists": True,
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": str(payload.get("status") or "skipped"),
        "generated_at": str(payload.get("generated_at") or ""),
        "execute": bool(payload.get("execute", False)),
        "execution_requested": bool(payload.get("execution_requested", payload.get("execute", False))),
        "read_only": bool(payload.get("read_only", True)),
        "env_profile": _safe_business_env_profile(payload.get("env_profile")),
        "business_system_connected": bool(payload.get("business_system_connected", False)),
        "business_read_executed": bool(payload.get("business_read_executed", False)),
        "business_write_executed": bool(payload.get("business_write_executed", False)),
        "business_data_written": bool(payload.get("business_data_written", False)),
        "approval_bypassed": bool(payload.get("approval_bypassed", False)),
        "audit_bypassed": bool(payload.get("audit_bypassed", False)),
        "missing_conditions": [str(item) for item in missing_conditions[:12]],
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
        "business_system_read_smoke": str(go_no_go.get("business_system_read_smoke") or "Needs-Input"),
        "public_production_direct_launch": str(go_no_go.get("public_production_direct_launch") or "No-Go"),
        "manual_signoff_required": bool(go_no_go.get("manual_signoff_required", True)),
    }


def _safe_business_input_items(value: Any, *, limit: int = 8) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in value[:limit]:
        if not isinstance(item, dict):
            continue
        env = item.get("env") if isinstance(item.get("env"), list) else []
        rows.append(
            {
                "id": _safe_text_value(item.get("id") or ""),
                "env": [_safe_text_value(env_item) for env_item in env[:16]],
                "description": _safe_text_value(item.get("description") or ""),
            }
        )
    return rows


def _collect_business_system_input_packet_summary() -> dict[str, Any]:
    report_dir = _get_business_system_input_packet_report_dir()
    latest = _latest_json_report(report_dir)
    base = {
        "mode": "read_only_latest_report",
        "runbook_path": BUSINESS_SYSTEM_INPUT_PACKET_RUNBOOK_PATH,
        "report_dir": report_dir,
        "directory_exists": Path(report_dir).exists(),
        "latest_report_present": False,
        "status": "skipped",
        "generated_at": "",
        "ready_for_real_read_smoke": False,
        "owner_inputs_present": {},
        "config": {},
        "missing_conditions": ["business_system_input_packet:report_not_found"],
        "missing_condition_count": 1,
        "required_inputs": [],
        "local_env_template_lines": [],
        "manual_input_checklist": [],
        "recommended_commands": [],
        "business_write_executed": False,
        "business_data_written": False,
        "secret_plaintext_output": False,
        "public_production_direct_launch": "No-Go",
    }
    if latest is None:
        return base

    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            **base,
            "directory_exists": True,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
            "missing_conditions": ["business_system_input_packet:json_parse_failed"],
        }

    owners = payload.get("owner_inputs_present") if isinstance(payload.get("owner_inputs_present"), dict) else {}
    config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    missing = payload.get("missing_conditions") if isinstance(payload.get("missing_conditions"), list) else []
    template_lines = payload.get("local_env_template_lines") if isinstance(payload.get("local_env_template_lines"), list) else []
    commands = payload.get("recommended_commands") if isinstance(payload.get("recommended_commands"), list) else []
    return {
        **base,
        "directory_exists": True,
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": _safe_text_value(payload.get("status") or "skipped"),
        "generated_at": _safe_text_value(payload.get("generated_at") or ""),
        "ready_for_real_read_smoke": bool(payload.get("ready_for_real_read_smoke", False)),
        "owner_inputs_present": {str(key): bool(value) for key, value in owners.items()},
        "config": {
            "enabled": bool(config.get("enabled", False)),
            "read_only": bool(config.get("read_only", False)),
            "write_enabled": bool(config.get("write_enabled", False)),
            "approval_required": bool(config.get("approval_required", False)),
            "audit_required": bool(config.get("audit_required", False)),
            "system_name": _safe_text_value(config.get("system_name") or ""),
            "base_url_env": _safe_text_value(config.get("base_url_env") or ""),
            "base_url_present": bool(config.get("base_url_present", False)),
            "token_env": _safe_text_value(config.get("token_env") or ""),
            "token_present": bool(config.get("token_present", False)),
            "tool_allowlist_count": int(config.get("tool_allowlist_count", 0) or 0),
            "write_tool_allowlist_count": int(config.get("write_tool_allowlist_count", 0) or 0),
            "timeout_seconds": float(config.get("timeout_seconds", 0) or 0),
            "read_probe_path_configured": bool(config.get("read_probe_path_configured", False)),
            "auth_header_name": _safe_text_value(config.get("auth_header_name") or ""),
            "auth_scheme_configured": bool(config.get("auth_scheme_configured", False)),
        },
        "missing_conditions": [_safe_text_value(item) for item in missing[:32]],
        "missing_condition_count": int(payload.get("missing_condition_count") or len(missing)),
        "required_inputs": _safe_business_input_items(payload.get("required_inputs"), limit=8),
        "local_env_template_lines": [_safe_text_value(item) for item in template_lines[:32]],
        "manual_input_checklist": _safe_business_input_items(payload.get("manual_input_checklist"), limit=8),
        "recommended_commands": [_safe_text_value(item) for item in commands[:8]],
        "business_write_executed": bool(payload.get("business_write_executed", False)),
        "business_data_written": bool(payload.get("business_data_written", False)),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
        "public_production_direct_launch": _safe_text_value(payload.get("public_production_direct_launch") or "No-Go"),
    }


def _safe_business_production_readiness_required_inputs(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    safe_items: list[dict[str, Any]] = []
    for item in value[:8]:
        if not isinstance(item, dict):
            continue
        safe_items.append(
            {
                "id": _safe_text_value(item.get("id") or ""),
                "description": _safe_text_value(item.get("description") or ""),
                "env": _safe_text_value(item.get("env") or ""),
                "command": _safe_text_value(item.get("command") or ""),
            }
        )
    return safe_items


def _collect_business_system_production_readiness_summary() -> dict[str, Any]:
    report_dir = _get_business_system_production_readiness_report_dir()
    latest = _latest_json_report(report_dir)
    if latest is None:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": BUSINESS_SYSTEM_PRODUCTION_READINESS_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": Path(report_dir).exists(),
            "latest_report_present": False,
            "status": "skipped",
            "generated_at": "",
            "read_only": True,
            "owner_inputs_present": {},
            "required_inputs": [],
            "latest_business_smoke": {},
            "missing_conditions": ["business_system_production_readiness:report_not_found"],
            "missing_condition_count": 1,
            "business_write_executed": False,
            "business_data_written": False,
            "secret_plaintext_output": False,
            "public_production_direct_launch": "No-Go",
        }

    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": BUSINESS_SYSTEM_PRODUCTION_READINESS_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": True,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "failed",
            "generated_at": "",
            "read_only": True,
            "owner_inputs_present": {},
            "required_inputs": [],
            "latest_business_smoke": {},
            "missing_conditions": ["business_system_production_readiness:json_parse_failed"],
            "missing_condition_count": 1,
            "business_write_executed": False,
            "business_data_written": False,
            "secret_plaintext_output": False,
            "public_production_direct_launch": "No-Go",
        }

    owners = payload.get("owner_inputs_present") if isinstance(payload.get("owner_inputs_present"), dict) else {}
    latest_smoke = payload.get("latest_business_smoke") if isinstance(payload.get("latest_business_smoke"), dict) else {}
    missing = payload.get("missing_conditions") if isinstance(payload.get("missing_conditions"), list) else []
    return {
        "mode": "read_only_latest_report",
        "runbook_path": BUSINESS_SYSTEM_PRODUCTION_READINESS_RUNBOOK_PATH,
        "report_dir": report_dir,
        "directory_exists": True,
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": _safe_text_value(payload.get("status") or "skipped"),
        "generated_at": _safe_text_value(payload.get("generated_at") or ""),
        "read_only": bool(payload.get("read_only", True)),
        "owner_inputs_present": {str(key): bool(value) for key, value in owners.items()},
        "required_inputs": _safe_business_production_readiness_required_inputs(payload.get("required_inputs")),
        "latest_business_smoke": {
            "latest_report_present": bool(latest_smoke.get("latest_report_present", False)),
            "status": _safe_text_value(latest_smoke.get("status") or "skipped"),
            "business_system_connected": bool(latest_smoke.get("business_system_connected", False)),
            "business_read_executed": bool(latest_smoke.get("business_read_executed", False)),
            "business_write_executed": bool(latest_smoke.get("business_write_executed", False)),
            "business_data_written": bool(latest_smoke.get("business_data_written", False)),
            "local_business_mock_used": bool(latest_smoke.get("local_business_mock_used", False)),
            "secret_plaintext_output": bool(latest_smoke.get("secret_plaintext_output", False)),
        },
        "missing_conditions": [_safe_text_value(item) for item in missing[:16]],
        "missing_condition_count": int(payload.get("missing_condition_count") or len(missing)),
        "business_write_executed": bool(payload.get("business_write_executed", False)),
        "business_data_written": bool(payload.get("business_data_written", False)),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
        "public_production_direct_launch": str(payload.get("public_production_direct_launch") or "No-Go"),
    }


def _collect_real_integration_staging_smoke_summary() -> dict[str, Any]:
    report_dir = _get_real_integration_staging_smoke_report_dir()
    latest = _latest_json_report(report_dir)
    if latest is None:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": REAL_INTEGRATION_STAGING_SMOKE_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": Path(report_dir).exists(),
            "latest_report_present": False,
            "status": "skipped",
            "generated_at": "",
            "execute_requested": False,
            "read_only": True,
            "execution_mode": "read_only_smoke",
            "database_connected": False,
            "redis_connected": False,
            "external_mcp_connected": False,
            "real_llm_executed": False,
            "migration_executed": False,
            "business_data_written": False,
            "audit_data_written": False,
            "metrics_data_written": False,
            "secret_plaintext_output": False,
            "preflight_summary": _safe_staging_preflight_summary({}),
            "missing_conditions": ["real_integration_staging_smoke_report:not_found"],
            "public_production_direct_launch": "No-Go",
        }

    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": REAL_INTEGRATION_STAGING_SMOKE_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": True,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
            "generated_at": "",
            "execute_requested": False,
            "read_only": True,
            "execution_mode": "read_only_smoke",
            "database_connected": False,
            "redis_connected": False,
            "external_mcp_connected": False,
            "real_llm_executed": False,
            "migration_executed": False,
            "business_data_written": False,
            "audit_data_written": False,
            "metrics_data_written": False,
            "secret_plaintext_output": False,
            "preflight_summary": _safe_staging_preflight_summary({}),
            "missing_conditions": ["real_integration_staging_smoke_report:unreadable_json"],
            "public_production_direct_launch": "No-Go",
        }

    go_no_go = payload.get("go_no_go") if isinstance(payload.get("go_no_go"), dict) else {}
    missing_conditions = payload.get("missing_conditions") if isinstance(payload.get("missing_conditions"), list) else []
    return {
        "mode": "read_only_latest_report",
        "runbook_path": REAL_INTEGRATION_STAGING_SMOKE_RUNBOOK_PATH,
        "report_dir": report_dir,
        "directory_exists": True,
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": str(payload.get("status") or "skipped"),
        "generated_at": str(payload.get("generated_at") or ""),
        "execute_requested": bool(payload.get("execute_requested", False)),
        "read_only": bool(payload.get("read_only", True)),
        "execution_mode": _safe_text_value(payload.get("execution_mode") or "read_only_smoke"),
        "database_connected": bool(payload.get("database_connected", False)),
        "redis_connected": bool(payload.get("redis_connected", False)),
        "external_mcp_connected": bool(payload.get("external_mcp_connected", False)),
        "real_llm_executed": bool(payload.get("real_llm_executed", False)),
        "migration_executed": bool(payload.get("migration_executed", False)),
        "business_data_written": bool(payload.get("business_data_written", False)),
        "audit_data_written": bool(payload.get("audit_data_written", False)),
        "metrics_data_written": bool(payload.get("metrics_data_written", False)),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
        "preflight_summary": _safe_staging_preflight_summary(payload.get("preflight_summary")),
        "missing_conditions": [_safe_text_value(item) for item in missing_conditions[:24]],
        "public_production_direct_launch": str(go_no_go.get("public_production_direct_launch") or "No-Go"),
    }


def _safe_real_production_environment_domains(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    domains: list[dict[str, Any]] = []
    for item in value[:12]:
        if not isinstance(item, dict):
            continue
        missing = item.get("missing_conditions") if isinstance(item.get("missing_conditions"), list) else []
        domains.append(
            {
                "domain_id": _safe_text_value(item.get("domain_id")),
                "status": _safe_text_value(item.get("status")),
                "owner": _safe_text_value(item.get("owner")),
                "phase": _safe_text_value(item.get("phase")),
                "missing_conditions": [_safe_text_value(entry) for entry in missing[:16]],
                "manual_signoff_required": bool(item.get("manual_signoff_required", True)),
                "production_direct_launch": str(item.get("production_direct_launch") or "No-Go"),
            }
        )
    return domains


def _collect_real_production_environment_checklist_summary() -> dict[str, Any]:
    report_dir = _get_real_production_environment_checklist_report_dir()
    latest = _latest_json_report(report_dir)
    base_commands = {
        "real_llm": SAFE_XIAOMI_LLM_PREFLIGHT_COMMAND,
        "postgres": SAFE_POSTGRES_INFRA_SMOKE_COMMAND,
        "redis": SAFE_REDIS_INFRA_SMOKE_COMMAND,
        "external_mcp": SAFE_EXTERNAL_MCP_INFRA_SMOKE_COMMAND,
        "business_system": SAFE_BUSINESS_READ_SMOKE_COMMAND,
    }
    if latest is None:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": REAL_PRODUCTION_ENVIRONMENT_CHECKLIST_RUNBOOK_PATH,
            "infra_smoke_runbook_path": REAL_INTEGRATION_INFRA_SMOKE_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": Path(report_dir).exists(),
            "latest_report_present": False,
            "status": "skipped",
            "generated_at": "",
            "domain_count": 5,
            "domains": [],
            "next_commands": base_commands,
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        }
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": REAL_PRODUCTION_ENVIRONMENT_CHECKLIST_RUNBOOK_PATH,
            "infra_smoke_runbook_path": REAL_INTEGRATION_INFRA_SMOKE_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": True,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
            "generated_at": "",
            "domain_count": 5,
            "domains": [],
            "next_commands": base_commands,
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        }
    go_no_go = payload.get("go_no_go") if isinstance(payload.get("go_no_go"), dict) else {}
    next_commands = {key: _safe_text_value(value) for key, value in base_commands.items()}
    return {
        "mode": "read_only_latest_report",
        "runbook_path": REAL_PRODUCTION_ENVIRONMENT_CHECKLIST_RUNBOOK_PATH,
        "infra_smoke_runbook_path": REAL_INTEGRATION_INFRA_SMOKE_RUNBOOK_PATH,
        "report_dir": report_dir,
        "directory_exists": True,
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": str(payload.get("status") or "skipped"),
        "generated_at": str(payload.get("generated_at") or ""),
        "domain_count": int(payload.get("domain_count", 0) or 0),
        "domains": _safe_real_production_environment_domains(payload.get("domains")),
        "next_commands": next_commands,
        "real_llm_executed": bool(payload.get("real_llm_executed", False)),
        "database_connected": bool(payload.get("database_connected", False)),
        "redis_connected": bool(payload.get("redis_connected", False)),
        "external_mcp_connected": bool(payload.get("external_mcp_connected", False)),
        "business_data_written": bool(payload.get("business_data_written", False)),
        "public_production_direct_launch": str(go_no_go.get("public_production_direct_launch") or "No-Go"),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
    }


def _collect_production_landing_action_pack_summary() -> dict[str, Any]:
    report_dir = _get_production_landing_action_pack_report_dir()
    latest = _latest_json_report(report_dir)
    if latest is None:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": PRODUCTION_LANDING_ACTION_PACK_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": Path(report_dir).exists(),
            "latest_report_present": False,
            "status": "skipped",
            "generated_at": "",
            "required_input_count": 0,
            "required_inputs": [],
            "recommended_commands": [],
            "template_status": {},
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "auto_approved": False,
            "auto_closed": False,
        }

    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": PRODUCTION_LANDING_ACTION_PACK_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": True,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
            "generated_at": "",
            "required_input_count": 0,
            "required_inputs": [],
            "recommended_commands": [],
            "template_status": {},
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "auto_approved": False,
            "auto_closed": False,
        }

    return {
        "mode": "read_only_latest_report",
        "runbook_path": PRODUCTION_LANDING_ACTION_PACK_RUNBOOK_PATH,
        "report_dir": report_dir,
        "directory_exists": True,
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": str(payload.get("status") or "skipped"),
        "generated_at": str(payload.get("generated_at") or ""),
        "required_input_count": int(payload.get("required_input_count", 0) or 0),
        "required_inputs": _safe_required_inputs(payload.get("required_inputs")),
        "recommended_commands": _safe_command_list(payload.get("recommended_commands")),
        "template_status": _safe_template_status(payload.get("templates")),
        "public_production_direct_launch": str(payload.get("public_production_direct_launch") or "No-Go"),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
        "auto_approved": bool(payload.get("auto_approved", False)),
        "auto_closed": bool(payload.get("auto_closed", False)),
    }


def _collect_production_landing_blocker_resolution_summary() -> dict[str, Any]:
    report_dir = _get_production_landing_blocker_resolution_report_dir()
    latest = _latest_json_report(report_dir)
    if latest is None:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": PRODUCTION_LANDING_BLOCKER_RESOLUTION_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": Path(report_dir).exists(),
            "latest_report_present": False,
            "status": "skipped",
            "generated_at": "",
            "required_action_count": 0,
            "required_actions": [],
            "actions": [],
            "source_blocked_or_failed": [],
            "source_missing_conditions": [],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "auto_approved": False,
            "auto_closed": False,
        }

    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": PRODUCTION_LANDING_BLOCKER_RESOLUTION_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": True,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
            "generated_at": "",
            "required_action_count": 1,
            "required_actions": ["production_landing_blocker_resolution:json_parse_failed"],
            "actions": [],
            "source_blocked_or_failed": ["production_landing_blocker_resolution"],
            "source_missing_conditions": [],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "auto_approved": False,
            "auto_closed": False,
        }

    required_actions = payload.get("required_actions") if isinstance(payload.get("required_actions"), list) else []
    source_blocked = (
        payload.get("source_blocked_or_failed") if isinstance(payload.get("source_blocked_or_failed"), list) else []
    )
    source_missing = (
        payload.get("source_missing_conditions") if isinstance(payload.get("source_missing_conditions"), list) else []
    )
    return {
        "mode": "read_only_latest_report",
        "runbook_path": PRODUCTION_LANDING_BLOCKER_RESOLUTION_RUNBOOK_PATH,
        "report_dir": report_dir,
        "directory_exists": True,
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": str(payload.get("status") or "skipped"),
        "generated_at": str(payload.get("generated_at") or ""),
        "required_action_count": int(payload.get("required_action_count", len(required_actions)) or 0),
        "required_actions": [_safe_text_value(item) for item in required_actions[:12]],
        "actions": _safe_blocker_resolution_actions(payload.get("actions")),
        "source_blocked_or_failed": [_safe_text_value(item) for item in source_blocked[:12]],
        "source_missing_conditions": [_safe_text_value(item) for item in source_missing[:12]],
        "public_production_direct_launch": str(payload.get("public_production_direct_launch") or "No-Go"),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
        "auto_approved": bool(payload.get("auto_approved", False)),
        "auto_closed": bool(payload.get("auto_closed", False)),
    }


def _collect_production_landing_final_verification_summary() -> dict[str, Any]:
    report_dir = _get_production_landing_final_verification_report_dir()
    latest = _latest_json_report(report_dir)
    if latest is None:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": PRODUCTION_LANDING_FINAL_VERIFICATION_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": Path(report_dir).exists(),
            "latest_report_present": False,
            "status": "skipped",
            "generated_at": "",
            "passed_count": 0,
            "requirement_count": 0,
            "missing_conditions": [],
            "requirements": [],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "auto_approved": False,
            "auto_closed": False,
        }

    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": PRODUCTION_LANDING_FINAL_VERIFICATION_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": True,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
            "generated_at": "",
            "passed_count": 0,
            "requirement_count": 1,
            "missing_conditions": ["production_landing_final_verification:json_parse_failed"],
            "requirements": [],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "auto_approved": False,
            "auto_closed": False,
        }

    missing = payload.get("missing_conditions") if isinstance(payload.get("missing_conditions"), list) else []
    return {
        "mode": "read_only_latest_report",
        "runbook_path": PRODUCTION_LANDING_FINAL_VERIFICATION_RUNBOOK_PATH,
        "report_dir": report_dir,
        "directory_exists": True,
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": str(payload.get("status") or "skipped"),
        "generated_at": str(payload.get("generated_at") or ""),
        "passed_count": int(payload.get("passed_count", 0) or 0),
        "requirement_count": int(payload.get("requirement_count", 0) or 0),
        "missing_conditions": [_safe_text_value(item) for item in missing[:32]],
        "requirements": _safe_final_verification_requirements(payload.get("requirements")),
        "public_production_direct_launch": str(payload.get("public_production_direct_launch") or "No-Go"),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
        "auto_approved": bool(payload.get("auto_approved", False)),
        "auto_closed": bool(payload.get("auto_closed", False)),
    }


def _safe_pilot_bundle_sources(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    sources: dict[str, dict[str, Any]] = {}
    for source_id, item in value.items():
        if not isinstance(item, dict):
            continue
        summary = item.get("summary") if isinstance(item.get("summary"), dict) else {}
        sources[str(source_id)] = {
            "source_id": _safe_text_value(item.get("source_id") or source_id),
            "present": bool(item.get("present", False)),
            "status": _safe_text_value(item.get("status") or "skipped"),
            "latest_json_path": _safe_text_value(item.get("latest_json_path") or ""),
            "generated_at": _safe_text_value(summary.get("generated_at") or ""),
            "passed_count": int(summary.get("passed_count") or 0),
            "requirement_count": int(summary.get("requirement_count") or 0),
            "missing_condition_count": int(summary.get("missing_condition_count") or 0),
            "open_gap_count": int(summary.get("open_gap_count") or 0),
            "gap_count": int(summary.get("gap_count") or 0),
            "domain_count": int(summary.get("domain_count") or 0),
            "secret_plaintext_output": bool(summary.get("secret_plaintext_output", False)),
            "public_production_direct_launch": _safe_text_value(
                summary.get("public_production_direct_launch") or "No-Go"
            ),
            "missing_conditions": [_safe_text_value(entry) for entry in item.get("missing_conditions", [])[:12]]
            if isinstance(item.get("missing_conditions"), list)
            else [],
            "secret_detected": bool(item.get("secret_detected", False)),
        }
    return sources


def _collect_production_pilot_evidence_bundle_summary() -> dict[str, Any]:
    report_dir = _get_production_pilot_evidence_bundle_report_dir()
    latest = _latest_json_report(report_dir)
    if latest is None:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": PRODUCTION_PILOT_EVIDENCE_BUNDLE_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": Path(report_dir).exists(),
            "latest_report_present": False,
            "status": "skipped",
            "generated_at": "",
            "controlled_pilot_ready": False,
            "controlled_pilot": "Manual-Review",
            "final_verification_passed_count": 0,
            "final_verification_requirement_count": 0,
            "missing_condition_count": 0,
            "missing_conditions": [],
            "sources": {},
            "next_actions": [],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "auto_approved": False,
            "auto_closed": False,
        }

    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": PRODUCTION_PILOT_EVIDENCE_BUNDLE_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": True,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
            "generated_at": "",
            "controlled_pilot_ready": False,
            "controlled_pilot": "No-Go",
            "final_verification_passed_count": 0,
            "final_verification_requirement_count": 0,
            "missing_condition_count": 1,
            "missing_conditions": ["production_pilot_evidence_bundle:json_parse_failed"],
            "sources": {},
            "next_actions": [],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "auto_approved": False,
            "auto_closed": False,
        }

    missing = payload.get("missing_conditions") if isinstance(payload.get("missing_conditions"), list) else []
    go_no_go = payload.get("go_no_go") if isinstance(payload.get("go_no_go"), dict) else {}
    return {
        "mode": "read_only_latest_report",
        "runbook_path": PRODUCTION_PILOT_EVIDENCE_BUNDLE_RUNBOOK_PATH,
        "report_dir": report_dir,
        "directory_exists": True,
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": str(payload.get("status") or "skipped"),
        "generated_at": str(payload.get("generated_at") or ""),
        "controlled_pilot_ready": bool(payload.get("controlled_pilot_ready", False)),
        "controlled_pilot": _safe_text_value(go_no_go.get("controlled_pilot") or "Manual-Review"),
        "final_verification_passed_count": int(payload.get("final_verification_passed_count") or 0),
        "final_verification_requirement_count": int(payload.get("final_verification_requirement_count") or 0),
        "missing_condition_count": int(payload.get("missing_condition_count") or len(missing) or 0),
        "missing_conditions": [_safe_text_value(item) for item in missing[:32]],
        "sources": _safe_pilot_bundle_sources(payload.get("sources")),
        "next_actions": [_safe_text_value(item) for item in (payload.get("next_actions") or [])[:8]]
        if isinstance(payload.get("next_actions"), list)
        else [],
        "public_production_direct_launch": _safe_text_value(
            payload.get("public_production_direct_launch")
            or go_no_go.get("public_production_direct_launch")
            or "No-Go"
        ),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
        "auto_approved": bool(payload.get("auto_approved", False)),
        "auto_closed": bool(payload.get("auto_closed", False)),
    }


def _collect_controlled_pilot_launch_gate_summary(
    *,
    production_pilot_evidence_bundle: dict[str, Any],
    production_landing_final_verification: dict[str, Any],
    production_landing_signoff_closeout: dict[str, Any],
    production_pilot_bootstrap: dict[str, Any],
) -> dict[str, Any]:
    missing_conditions: list[str] = []

    evidence_ready = (
        production_pilot_evidence_bundle.get("status") == "success"
        and production_pilot_evidence_bundle.get("controlled_pilot_ready") is True
        and production_pilot_evidence_bundle.get("controlled_pilot") == "Go"
        and int(production_pilot_evidence_bundle.get("missing_condition_count") or 0) == 0
    )
    if not evidence_ready:
        missing_conditions.append("controlled_pilot_launch_gate:evidence_bundle_not_go")

    final_passed_count = int(production_landing_final_verification.get("passed_count") or 0)
    final_requirement_count = int(production_landing_final_verification.get("requirement_count") or 0)
    final_verification_ready = (
        production_landing_final_verification.get("status") == "success"
        and final_requirement_count > 0
        and final_passed_count == final_requirement_count
    )
    if not final_verification_ready:
        missing_conditions.append("controlled_pilot_launch_gate:final_verification_not_complete")

    signoff_ready = (
        production_landing_signoff_closeout.get("status") == "success"
        and production_landing_signoff_closeout.get("final_status") == "success"
        and int(production_landing_signoff_closeout.get("missing_condition_count") or 0) == 0
        and production_landing_signoff_closeout.get("target_record_written") is True
    )
    if not signoff_ready:
        missing_conditions.append("controlled_pilot_launch_gate:signoff_closeout_not_complete")

    public_direct_values = [
        production_pilot_evidence_bundle.get("public_production_direct_launch"),
        production_landing_final_verification.get("public_production_direct_launch"),
        production_landing_signoff_closeout.get("public_production_direct_launch"),
        production_pilot_bootstrap.get("public_production_direct_launch"),
    ]
    public_boundary_ok = all(str(value or "No-Go") == "No-Go" for value in public_direct_values)
    if not public_boundary_ok:
        missing_conditions.append("controlled_pilot_launch_gate:public_direct_launch_boundary_changed")

    secret_plaintext_output = any(
        bool(source.get("secret_plaintext_output", False))
        for source in (
            production_pilot_evidence_bundle,
            production_landing_final_verification,
            production_landing_signoff_closeout,
            production_pilot_bootstrap,
        )
    )
    if secret_plaintext_output:
        missing_conditions.append("controlled_pilot_launch_gate:secret_plaintext_output_detected")

    auto_approval_blocked = any(
        bool(source.get("auto_approved", False) or source.get("auto_closed", False) or source.get("auto_signed", False))
        for source in (
            production_pilot_evidence_bundle,
            production_landing_final_verification,
            production_landing_signoff_closeout,
        )
    )
    if auto_approval_blocked:
        missing_conditions.append("controlled_pilot_launch_gate:auto_approval_or_close_detected")

    ready_for_controlled_pilot = len(missing_conditions) == 0
    return {
        "mode": "read_only_derived_gate",
        "status": "ready" if ready_for_controlled_pilot else "blocked",
        "ready_for_controlled_pilot": ready_for_controlled_pilot,
        "controlled_pilot": "Go" if ready_for_controlled_pilot else "Manual-Review",
        "public_production_direct_launch": "No-Go",
        "manual_signoff_required": True,
        "evidence_bundle_status": str(production_pilot_evidence_bundle.get("status") or "skipped"),
        "final_verification_status": str(production_landing_final_verification.get("status") or "skipped"),
        "signoff_closeout_status": str(production_landing_signoff_closeout.get("status") or "skipped"),
        "bootstrap_status": str(production_pilot_bootstrap.get("status") or "skipped"),
        "final_verification_passed_count": final_passed_count,
        "final_verification_requirement_count": final_requirement_count,
        "missing_condition_count": len(missing_conditions),
        "missing_conditions": missing_conditions,
        "safe_next_action": (
            "start_controlled_internal_pilot_window"
            if ready_for_controlled_pilot
            else "resolve_missing_conditions_before_pilot"
        ),
        "operator_command": "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\production_landing_signoff_closeout.ps1",
        "secret_plaintext_output": secret_plaintext_output,
        "auto_approved": False,
        "auto_closed": False,
    }


def _safe_controlled_pilot_package_sources(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    sources: dict[str, dict[str, Any]] = {}
    for source_id, item in value.items():
        if not isinstance(item, dict):
            continue
        summary = item.get("summary") if isinstance(item.get("summary"), dict) else {}
        missing = item.get("missing_conditions") if isinstance(item.get("missing_conditions"), list) else []
        sources[str(source_id)] = {
            "source_id": _safe_text_value(item.get("source_id") or source_id),
            "present": bool(item.get("present", False)),
            "status": _safe_text_value(item.get("status") or "skipped"),
            "latest_json_path": _safe_text_value(item.get("latest_json_path") or ""),
            "generated_at": _safe_text_value(item.get("generated_at") or ""),
            "missing_conditions": [_safe_text_value(entry) for entry in missing[:16]],
            "secret_detected": bool(item.get("secret_detected", False)),
            "summary": {
                str(key): _safe_text_value(val) if isinstance(val, str) else val
                for key, val in summary.items()
                if key
                in {
                    "ready_for_controlled_pilot",
                    "controlled_pilot",
                    "missing_condition_count",
                    "safe_next_action",
                    "public_production_direct_launch",
                    "manual_signoff_required",
                    "secret_plaintext_output",
                    "final_status",
                    "target_record_written",
                    "passed_count",
                    "requirement_count",
                    "controlled_pilot_ready",
                    "evidence_count",
                    "signoff_closeout_passed",
                    "final_verification_passed",
                    "pilot_evidence_bundle_passed",
                    "operations_console_smoke_status",
                    "execute",
                    "page_http_status",
                    "summary_http_status",
                }
            },
        }
    return sources


def _safe_pilot_roles(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    roles: list[dict[str, str]] = []
    for item in value[:8]:
        if not isinstance(item, dict):
            continue
        roles.append(
            {
                "role": _safe_text_value(item.get("role") or ""),
                "responsibility": _safe_text_value(item.get("responsibility") or ""),
            }
        )
    return roles


def _collect_controlled_pilot_launch_package_summary() -> dict[str, Any]:
    report_dir = _get_controlled_pilot_launch_package_report_dir()
    latest = _latest_json_report(report_dir)
    if latest is None:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": CONTROLLED_PILOT_LAUNCH_PACKAGE_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": Path(report_dir).exists(),
            "latest_report_present": False,
            "status": "skipped",
            "generated_at": "",
            "launch_package_ready": False,
            "controlled_pilot": "Manual-Review",
            "public_production_direct_launch": "No-Go",
            "manual_signoff_required": True,
            "missing_condition_count": 0,
            "missing_conditions": [],
            "safe_next_action": "generate_controlled_pilot_launch_package",
            "operator_commands": [],
            "pilot_roles": [],
            "launch_window": {},
            "sources": {},
            "secret_plaintext_output": False,
            "business_data_written": False,
            "audit_data_written": False,
            "metrics_data_written": False,
            "auto_approved": False,
            "auto_closed": False,
        }

    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": CONTROLLED_PILOT_LAUNCH_PACKAGE_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": True,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
            "generated_at": "",
            "launch_package_ready": False,
            "controlled_pilot": "Manual-Review",
            "public_production_direct_launch": "No-Go",
            "manual_signoff_required": True,
            "missing_condition_count": 1,
            "missing_conditions": ["controlled_pilot_launch_package:json_parse_failed"],
            "safe_next_action": "resolve_launch_package_missing_conditions",
            "operator_commands": [],
            "pilot_roles": [],
            "launch_window": {},
            "sources": {},
            "secret_plaintext_output": False,
            "business_data_written": False,
            "audit_data_written": False,
            "metrics_data_written": False,
            "auto_approved": False,
            "auto_closed": False,
        }

    missing = payload.get("missing_conditions") if isinstance(payload.get("missing_conditions"), list) else []
    launch_window = payload.get("launch_window") if isinstance(payload.get("launch_window"), dict) else {}
    operator_commands = payload.get("operator_commands") if isinstance(payload.get("operator_commands"), list) else []
    return {
        "mode": "read_only_latest_report",
        "runbook_path": CONTROLLED_PILOT_LAUNCH_PACKAGE_RUNBOOK_PATH,
        "report_dir": report_dir,
        "directory_exists": True,
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": _safe_text_value(payload.get("status") or "skipped"),
        "generated_at": _safe_text_value(payload.get("generated_at") or ""),
        "launch_package_ready": bool(payload.get("launch_package_ready", False)),
        "controlled_pilot": _safe_text_value(payload.get("controlled_pilot") or "Manual-Review"),
        "public_production_direct_launch": _safe_text_value(payload.get("public_production_direct_launch") or "No-Go"),
        "manual_signoff_required": bool(payload.get("manual_signoff_required", True)),
        "missing_condition_count": int(payload.get("missing_condition_count") or len(missing) or 0),
        "missing_conditions": [_safe_text_value(item) for item in missing[:32]],
        "safe_next_action": _safe_text_value(payload.get("safe_next_action") or ""),
        "operator_commands": _safe_command_list(operator_commands[:12]),
        "pilot_roles": _safe_pilot_roles(payload.get("pilot_roles")),
        "launch_window": {
            "scope": _safe_text_value(launch_window.get("scope") or ""),
            "public_production_direct_launch": _safe_text_value(
                launch_window.get("public_production_direct_launch") or "No-Go"
            ),
            "rollback_required": bool(launch_window.get("rollback_required", False)),
            "external_expansion_requires_new_manual_go_no_go": bool(
                launch_window.get("external_expansion_requires_new_manual_go_no_go", False)
            ),
        },
        "sources": _safe_controlled_pilot_package_sources(payload.get("sources")),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
        "business_data_written": bool(payload.get("business_data_written", False)),
        "audit_data_written": bool(payload.get("audit_data_written", False)),
        "metrics_data_written": bool(payload.get("metrics_data_written", False)),
        "auto_approved": bool(payload.get("auto_approved", False)),
        "auto_closed": bool(payload.get("auto_closed", False)),
    }


def _collect_controlled_pilot_window_record_summary() -> dict[str, Any]:
    report_dir = _get_controlled_pilot_window_record_report_dir()
    latest = _latest_json_report(report_dir)
    if latest is None:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": CONTROLLED_PILOT_WINDOW_RECORD_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": Path(report_dir).exists(),
            "latest_report_present": False,
            "status": "skipped",
            "generated_at": "",
            "window_id": "",
            "opened": False,
            "opened_by": "",
            "confirm_open": "not_confirmed",
            "controlled_pilot": "Manual-Review",
            "public_production_direct_launch": "No-Go",
            "manual_signoff_required": True,
            "launch_package": {},
            "missing_conditions": [],
            "missing_condition_count": 0,
            "rollback_required": True,
            "external_expansion_requires_new_manual_go_no_go": True,
            "secret_plaintext_output": False,
            "business_data_written": False,
            "audit_data_written": False,
            "metrics_data_written": False,
            "auto_approved": False,
            "auto_closed": False,
        }

    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": CONTROLLED_PILOT_WINDOW_RECORD_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": True,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
            "generated_at": "",
            "window_id": "",
            "opened": False,
            "opened_by": "",
            "confirm_open": "not_confirmed",
            "controlled_pilot": "Manual-Review",
            "public_production_direct_launch": "No-Go",
            "manual_signoff_required": True,
            "launch_package": {},
            "missing_conditions": ["controlled_pilot_window_record:json_parse_failed"],
            "missing_condition_count": 1,
            "rollback_required": True,
            "external_expansion_requires_new_manual_go_no_go": True,
            "secret_plaintext_output": False,
            "business_data_written": False,
            "audit_data_written": False,
            "metrics_data_written": False,
            "auto_approved": False,
            "auto_closed": False,
        }

    missing = payload.get("missing_conditions") if isinstance(payload.get("missing_conditions"), list) else []
    launch_package = payload.get("launch_package") if isinstance(payload.get("launch_package"), dict) else {}
    return {
        "mode": "read_only_latest_report",
        "runbook_path": CONTROLLED_PILOT_WINDOW_RECORD_RUNBOOK_PATH,
        "report_dir": report_dir,
        "directory_exists": True,
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": _safe_text_value(payload.get("status") or "skipped"),
        "generated_at": _safe_text_value(payload.get("generated_at") or ""),
        "window_id": _safe_text_value(payload.get("window_id") or ""),
        "opened": bool(payload.get("opened", False)),
        "opened_by": _safe_text_value(payload.get("opened_by") or ""),
        "confirm_open": _safe_text_value(payload.get("confirm_open") or "not_confirmed"),
        "controlled_pilot": _safe_text_value(payload.get("controlled_pilot") or "Manual-Review"),
        "public_production_direct_launch": _safe_text_value(payload.get("public_production_direct_launch") or "No-Go"),
        "manual_signoff_required": bool(payload.get("manual_signoff_required", True)),
        "launch_package": {
            "present": bool(launch_package.get("present", False)),
            "status": _safe_text_value(launch_package.get("status") or "skipped"),
            "path": _safe_text_value(launch_package.get("path") or ""),
            "launch_package_ready": bool(launch_package.get("launch_package_ready", False)),
            "controlled_pilot": _safe_text_value(launch_package.get("controlled_pilot") or "Manual-Review"),
            "public_production_direct_launch": _safe_text_value(
                launch_package.get("public_production_direct_launch") or "No-Go"
            ),
            "missing_condition_count": int(launch_package.get("missing_condition_count") or 0),
            "safe_next_action": _safe_text_value(launch_package.get("safe_next_action") or ""),
            "operator_command_count": int(launch_package.get("operator_command_count") or 0),
            "pilot_role_count": int(launch_package.get("pilot_role_count") or 0),
            "source_count": int(launch_package.get("source_count") or 0),
            "secret_plaintext_output": bool(launch_package.get("secret_plaintext_output", False)),
        },
        "missing_conditions": [_safe_text_value(item) for item in missing[:32]],
        "missing_condition_count": int(payload.get("missing_condition_count") or len(missing) or 0),
        "rollback_required": bool(payload.get("rollback_required", True)),
        "external_expansion_requires_new_manual_go_no_go": bool(
            payload.get("external_expansion_requires_new_manual_go_no_go", True)
        ),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
        "business_data_written": bool(payload.get("business_data_written", False)),
        "audit_data_written": bool(payload.get("audit_data_written", False)),
        "metrics_data_written": bool(payload.get("metrics_data_written", False)),
        "auto_approved": bool(payload.get("auto_approved", False)),
        "auto_closed": bool(payload.get("auto_closed", False)),
    }


def _collect_controlled_pilot_window_status_summary() -> dict[str, Any]:
    report_dir = _get_controlled_pilot_window_status_report_dir()
    latest = _latest_json_report(report_dir)
    if latest is None:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": CONTROLLED_PILOT_WINDOW_STATUS_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": Path(report_dir).exists(),
            "latest_report_present": False,
            "status": "skipped",
            "generated_at": "",
            "window": {},
            "operations_summary": {},
            "missing_conditions": [],
            "missing_condition_count": 0,
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "business_data_written": False,
            "audit_data_written": False,
            "metrics_data_written": False,
            "auto_approved": False,
            "auto_closed": False,
        }

    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": CONTROLLED_PILOT_WINDOW_STATUS_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": True,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
            "generated_at": "",
            "window": {},
            "operations_summary": {},
            "missing_conditions": ["controlled_pilot_window_status:json_parse_failed"],
            "missing_condition_count": 1,
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "business_data_written": False,
            "audit_data_written": False,
            "metrics_data_written": False,
            "auto_approved": False,
            "auto_closed": False,
        }

    missing = payload.get("missing_conditions") if isinstance(payload.get("missing_conditions"), list) else []
    window = payload.get("window") if isinstance(payload.get("window"), dict) else {}
    operations = payload.get("operations_summary") if isinstance(payload.get("operations_summary"), dict) else {}
    return {
        "mode": "read_only_latest_report",
        "runbook_path": CONTROLLED_PILOT_WINDOW_STATUS_RUNBOOK_PATH,
        "report_dir": report_dir,
        "directory_exists": True,
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": _safe_text_value(payload.get("status") or "skipped"),
        "generated_at": _safe_text_value(payload.get("generated_at") or ""),
        "window": {
            "present": bool(window.get("present", False)),
            "status": _safe_text_value(window.get("status") or "skipped"),
            "path": _safe_text_value(window.get("path") or ""),
            "opened": bool(window.get("opened", False)),
            "window_id": _safe_text_value(window.get("window_id") or ""),
            "opened_by": _safe_text_value(window.get("opened_by") or ""),
            "controlled_pilot": _safe_text_value(window.get("controlled_pilot") or "Manual-Review"),
            "public_production_direct_launch": _safe_text_value(
                window.get("public_production_direct_launch") or "No-Go"
            ),
            "missing_condition_count": int(window.get("missing_condition_count") or 0),
            "rollback_required": bool(window.get("rollback_required", False)),
            "launch_package_ready": bool(window.get("launch_package_ready", False)),
            "launch_package_status": _safe_text_value(window.get("launch_package_status") or "skipped"),
            "secret_plaintext_output": bool(window.get("secret_plaintext_output", False)),
        },
        "operations_summary": {
            "status": _safe_text_value(operations.get("status") or "skipped"),
            "http_status": operations.get("http_status"),
            "health_status": _safe_text_value(operations.get("health_status") or ""),
            "deployment_ok": bool(operations.get("deployment_ok", False)),
            "deployment_error_count": int(operations.get("deployment_error_count") or 0),
            "deployment_warning_count": int(operations.get("deployment_warning_count") or 0),
            "controlled_pilot_window_status": _safe_text_value(
                operations.get("controlled_pilot_window_status") or "skipped"
            ),
            "controlled_pilot_window_opened": bool(operations.get("controlled_pilot_window_opened", False)),
            "controlled_pilot_window_id": _safe_text_value(operations.get("controlled_pilot_window_id") or ""),
            "launch_package_status": _safe_text_value(operations.get("launch_package_status") or "skipped"),
            "launch_package_ready": bool(operations.get("launch_package_ready", False)),
            "launch_gate_status": _safe_text_value(operations.get("launch_gate_status") or "skipped"),
            "launch_gate_ready": bool(operations.get("launch_gate_ready", False)),
            "public_production_direct_launch": _safe_text_value(
                operations.get("public_production_direct_launch") or "No-Go"
            ),
        },
        "missing_conditions": [_safe_text_value(item) for item in missing[:32]],
        "missing_condition_count": int(payload.get("missing_condition_count") or len(missing) or 0),
        "public_production_direct_launch": _safe_text_value(payload.get("public_production_direct_launch") or "No-Go"),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
        "business_data_written": bool(payload.get("business_data_written", False)),
        "audit_data_written": bool(payload.get("audit_data_written", False)),
        "metrics_data_written": bool(payload.get("metrics_data_written", False)),
        "auto_approved": bool(payload.get("auto_approved", False)),
        "auto_closed": bool(payload.get("auto_closed", False)),
    }


def _collect_production_landing_xiaomi_llm_preflight_summary() -> dict[str, Any]:
    report_dir = _get_production_landing_xiaomi_llm_preflight_report_dir()
    latest = _latest_json_report(report_dir)
    base = {
        "mode": "read_only_latest_report",
        "runbook_path": PRODUCTION_LANDING_XIAOMI_LLM_PREFLIGHT_RUNBOOK_PATH,
        "report_dir": report_dir,
        "directory_exists": Path(report_dir).exists(),
        "latest_report_present": False,
        "status": "skipped",
        "generated_at": "",
        "api_key_env": "XIAOMI_LLM_API_KEY",
        "api_key_present": False,
        "real_llm_model": "mimo-v2.5-pro",
        "real_llm_base_url": "https://token-plan-cn.xiaomimimo.com/v1",
        "execute_network_check": False,
        "network_check_requested": False,
        "network_check_allowed": False,
        "network_check_executed": False,
        "real_llm_executed": False,
        "env_file_written": False,
        "local_env_modified": False,
        "safe_next_action": "",
        "acceptance_blockers": [],
        "warnings": [],
        "errors": [],
        "public_production_direct_launch": "No-Go",
        "secret_plaintext_output": False,
    }
    if latest is None:
        return base

    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            **base,
            "directory_exists": True,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
        }

    preflight = payload.get("preflight") if isinstance(payload.get("preflight"), dict) else {}
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    errors = payload.get("errors") if isinstance(payload.get("errors"), list) else []
    return {
        **base,
        "directory_exists": True,
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": str(payload.get("status") or "skipped"),
        "generated_at": str(payload.get("generated_at") or ""),
        "api_key_env": _safe_text_value(payload.get("api_key_env") or "XIAOMI_LLM_API_KEY"),
        "api_key_present": bool(payload.get("api_key_present", False)),
        "real_llm_model": _safe_text_value(payload.get("real_llm_model") or "mimo-v2.5-pro"),
        "real_llm_base_url": _safe_text_value(payload.get("real_llm_base_url") or "https://token-plan-cn.xiaomimimo.com/v1"),
        "execute_network_check": bool(payload.get("execute_network_check", False)),
        "network_check_requested": bool(preflight.get("network_check_requested", payload.get("execute_network_check", False))),
        "network_check_allowed": bool(preflight.get("network_check_allowed", False)),
        "network_check_executed": bool(preflight.get("network_check_executed", False)),
        "real_llm_executed": bool(payload.get("real_llm_executed", False)),
        "env_file_written": bool(payload.get("env_file_written", False)),
        "local_env_modified": bool(payload.get("local_env_modified", False)),
        "safe_next_action": _safe_text_value(payload.get("safe_next_action") or ""),
        "acceptance_blockers": [
            _safe_text_value(item)
            for item in (
                payload.get("acceptance_blockers") if isinstance(payload.get("acceptance_blockers"), list) else []
            )[:12]
        ],
        "warnings": [_safe_text_value(item) for item in warnings[:12]],
        "errors": [_safe_text_value(item) for item in errors[:12]],
        "public_production_direct_launch": str(payload.get("public_production_direct_launch") or "No-Go"),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
    }


def _collect_operations_console_landing_smoke_summary() -> dict[str, Any]:
    report_dir = _get_operations_console_landing_smoke_report_dir()
    latest = _latest_json_report(report_dir)
    selected_latest = latest
    selected_mode = "latest"
    root = Path(report_dir)
    if root.exists() and root.is_dir():
        executed_candidates: list[tuple[str, float, Path]] = []
        for item in root.glob("*_operations_console_landing_smoke.json"):
            if not item.is_file():
                continue
            try:
                candidate_payload = json.loads(item.read_text(encoding="utf-8"))
            except Exception:
                continue
            if candidate_payload.get("status") == "success" and candidate_payload.get("execute") is True:
                executed_candidates.append(
                    (str(candidate_payload.get("generated_at") or ""), item.stat().st_mtime, item)
                )
        if executed_candidates:
            _, _, selected_latest = max(executed_candidates, key=lambda row: (row[0], row[1], row[2].name))
            selected_mode = "latest_successful_executed"
    base = {
        "mode": "read_only_latest_report",
        "runbook_path": OPERATIONS_CONSOLE_LANDING_SMOKE_RUNBOOK_PATH,
        "report_dir": report_dir,
        "selection": selected_mode,
        "directory_exists": Path(report_dir).exists(),
        "latest_report_present": False,
        "status": "skipped",
        "generated_at": "",
        "execute": False,
        "page_http_status": None,
        "summary_http_status": None,
        "backend_summary_http_status": None,
        "preflight_status": "",
        "network_check_requested": False,
        "network_check_allowed": False,
        "safe_next_action": "",
        "acceptance_blockers": [],
        "blocker_action_present": False,
        "blocker_safe_next_action": "",
        "blocker_acceptance_blockers": [],
        "missing_conditions": [],
        "public_production_direct_launch": "No-Go",
        "secret_plaintext_output": False,
    }
    if selected_latest is None:
        return base

    try:
        payload = json.loads(selected_latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            **base,
            "directory_exists": True,
            "latest_report_present": True,
            "latest_json_path": str(selected_latest),
            "status": "blocked",
            "missing_conditions": ["operations_console_landing_smoke:json_parse_failed"],
        }

    acceptance_blockers = payload.get("acceptance_blockers") if isinstance(payload.get("acceptance_blockers"), list) else []
    blocker_acceptance_blockers = (
        payload.get("blocker_acceptance_blockers")
        if isinstance(payload.get("blocker_acceptance_blockers"), list)
        else []
    )
    missing = payload.get("missing_conditions") if isinstance(payload.get("missing_conditions"), list) else []
    return {
        **base,
        "directory_exists": True,
        "latest_report_present": True,
        "latest_json_path": str(selected_latest),
        "status": str(payload.get("status") or "skipped"),
        "generated_at": str(payload.get("generated_at") or ""),
        "execute": bool(payload.get("execute", False)),
        "page_http_status": payload.get("page_http_status"),
        "summary_http_status": payload.get("summary_http_status"),
        "backend_summary_http_status": payload.get("backend_summary_http_status"),
        "preflight_status": _safe_text_value(payload.get("preflight_status") or ""),
        "network_check_requested": bool(payload.get("network_check_requested", False)),
        "network_check_allowed": bool(payload.get("network_check_allowed", False)),
        "safe_next_action": _safe_text_value(payload.get("safe_next_action") or ""),
        "acceptance_blockers": [_safe_text_value(item) for item in acceptance_blockers[:12]],
        "blocker_action_present": bool(payload.get("blocker_action_present", False)),
        "blocker_safe_next_action": _safe_text_value(payload.get("blocker_safe_next_action") or ""),
        "blocker_acceptance_blockers": [_safe_text_value(item) for item in blocker_acceptance_blockers[:12]],
        "missing_conditions": [_safe_text_value(item) for item in missing[:12]],
        "public_production_direct_launch": str(payload.get("public_production_direct_launch") or "No-Go"),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
    }


def _derive_controlled_pilot_status_summary(
    *,
    production_pilot_bootstrap: dict[str, Any],
    production_pilot_evidence_bundle: dict[str, Any],
    controlled_pilot_launch_gate: dict[str, Any],
    controlled_pilot_launch_package: dict[str, Any],
    controlled_pilot_window_status: dict[str, Any],
    operations_console_landing_smoke: dict[str, Any],
    business_system_read_smoke: dict[str, Any],
    business_system_production_readiness: dict[str, Any],
) -> dict[str, Any]:
    report_dir = _get_controlled_pilot_status_summary_report_dir()
    latest = _latest_json_report(report_dir)
    reports = {
        "production_pilot_bootstrap": production_pilot_bootstrap,
        "production_pilot_evidence_bundle": production_pilot_evidence_bundle,
        "controlled_pilot_launch_gate": controlled_pilot_launch_gate,
        "controlled_pilot_launch_package": controlled_pilot_launch_package,
        "controlled_pilot_window_status": controlled_pilot_window_status,
        "operations_console_landing_smoke": operations_console_landing_smoke,
        "business_system_read_smoke": business_system_read_smoke,
        "business_system_production_readiness": business_system_production_readiness,
    }
    blocking_reports = [
        report_id
        for report_id, report in reports.items()
        if bool(report.get("secret_plaintext_output", False))
        or str(report.get("public_production_direct_launch") or "No-Go") != "No-Go"
        or str(report.get("status") or "missing") in {"blocked", "failed", "missing"}
    ]
    public_production_gaps: list[str] = []
    if business_system_read_smoke.get("business_read_executed") is not True:
        public_production_gaps.append("business_system:real_read_only_smoke_not_executed")
    env_profile = (
        business_system_read_smoke.get("env_profile")
        if isinstance(business_system_read_smoke.get("env_profile"), dict)
        else {}
    )
    if env_profile.get("public_production_gap") is True:
        public_production_gaps.append("business_system:public_production_gap")
    if business_system_production_readiness.get("status") != "ready":
        public_production_gaps.append("business_system:production_readiness_not_ready")
    ready = (
        not blocking_reports
        and not public_production_gaps
        and controlled_pilot_launch_gate.get("status") == "ready"
        and controlled_pilot_launch_gate.get("ready_for_controlled_pilot") is True
        and controlled_pilot_launch_package.get("status") == "ready"
        and controlled_pilot_launch_package.get("launch_package_ready") is True
        and controlled_pilot_window_status.get("status") == "healthy"
        and operations_console_landing_smoke.get("status") == "success"
        and operations_console_landing_smoke.get("execute") is True
        and business_system_read_smoke.get("business_read_executed") is True
        and business_system_production_readiness.get("status") == "ready"
    )
    return {
        "mode": "derived_from_operations_summary",
        "runbook_path": CONTROLLED_PILOT_STATUS_SUMMARY_RUNBOOK_PATH,
        "report_dir": report_dir,
        "directory_exists": Path(report_dir).exists(),
        "latest_report_present": latest is not None,
        "latest_json_path": str(latest or ""),
        "status": "ready" if ready else "partial",
        "controlled_internal_pilot": "Go" if ready else "Manual-Review",
        "public_production_direct_launch": "No-Go",
        "secret_plaintext_output": False,
        "blocking_reports": blocking_reports,
        "public_production_gaps": sorted(set(public_production_gaps)),
        "public_production_gap_count": len(set(public_production_gaps)),
        "source_statuses": {report_id: str(report.get("status") or "missing") for report_id, report in reports.items()},
        "operations_console_smoke_execute": bool(operations_console_landing_smoke.get("execute", False)),
        "runtime_smoke_passed": bool(production_pilot_bootstrap.get("runtime_smoke_passed", False)),
    }


def _collect_controlled_pilot_operator_packet_summary() -> dict[str, Any]:
    report_dir = _get_controlled_pilot_operator_packet_report_dir()
    latest = _latest_json_report(report_dir)
    base = {
        "mode": "read_only_latest_report",
        "runbook_path": CONTROLLED_PILOT_OPERATOR_PACKET_RUNBOOK_PATH,
        "report_dir": report_dir,
        "directory_exists": Path(report_dir).exists(),
        "latest_report_present": False,
        "status": "skipped",
        "generated_at": "",
        "controlled_internal_pilot": "Manual-Review",
        "public_production_direct_launch": "No-Go",
        "window_id": "",
        "missing_condition_count": 0,
        "missing_conditions": [],
        "evidence_paths": {},
        "operator_command_count": 0,
        "pilot_role_count": 0,
        "rollback_required": True,
        "external_expansion_requires_new_manual_go_no_go": True,
        "secret_plaintext_output": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "public_production_gaps": [],
        "public_production_gap_count": 0,
        "business_system_read_smoke": {},
    }
    if latest is None:
        return base
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            **base,
            "directory_exists": True,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
            "missing_conditions": ["controlled_pilot_operator_packet:json_parse_failed"],
            "missing_condition_count": 1,
        }
    evidence_paths = payload.get("evidence_paths") if isinstance(payload.get("evidence_paths"), dict) else {}
    commands = payload.get("operator_commands") if isinstance(payload.get("operator_commands"), list) else []
    roles = payload.get("pilot_roles") if isinstance(payload.get("pilot_roles"), list) else []
    missing = payload.get("missing_conditions") if isinstance(payload.get("missing_conditions"), list) else []
    public_gaps = payload.get("public_production_gaps") if isinstance(payload.get("public_production_gaps"), list) else []
    business_smoke = (
        payload.get("business_system_read_smoke") if isinstance(payload.get("business_system_read_smoke"), dict) else {}
    )
    window = payload.get("window") if isinstance(payload.get("window"), dict) else {}
    return {
        **base,
        "directory_exists": True,
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": _safe_text_value(payload.get("status") or "skipped"),
        "generated_at": _safe_text_value(payload.get("generated_at") or ""),
        "controlled_internal_pilot": _safe_text_value(payload.get("controlled_internal_pilot") or "Manual-Review"),
        "public_production_direct_launch": _safe_text_value(
            payload.get("public_production_direct_launch") or "No-Go"
        ),
        "window_id": _safe_text_value(window.get("window_id") or ""),
        "missing_condition_count": int(payload.get("missing_condition_count") or 0),
        "missing_conditions": [_safe_text_value(item) for item in missing[:16]],
        "public_production_gaps": [_safe_text_value(item) for item in public_gaps[:16]],
        "public_production_gap_count": int(payload.get("public_production_gap_count") or len(public_gaps)),
        "business_system_read_smoke": {
            "status": _safe_text_value(business_smoke.get("status") or ""),
            "business_system_connected": bool(business_smoke.get("business_system_connected", False)),
            "business_read_executed": bool(business_smoke.get("business_read_executed", False)),
            "auth_mode": _safe_text_value(business_smoke.get("auth_mode") or ""),
        },
        "evidence_paths": {str(key): _safe_text_value(value) for key, value in evidence_paths.items()},
        "operator_command_count": len(commands),
        "pilot_role_count": len(roles),
        "rollback_required": bool(payload.get("rollback_required", True)),
        "external_expansion_requires_new_manual_go_no_go": bool(
            payload.get("external_expansion_requires_new_manual_go_no_go", True)
        ),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
        "business_data_written": bool(payload.get("business_data_written", False)),
        "audit_data_written": bool(payload.get("audit_data_written", False)),
        "metrics_data_written": bool(payload.get("metrics_data_written", False)),
    }


def _collect_controlled_pilot_console_verify_summary() -> dict[str, Any]:
    report_dir = _get_controlled_pilot_console_verify_report_dir()
    latest = _latest_json_report(report_dir)
    base = {
        "mode": "read_only_latest_report",
        "runbook_path": CONTROLLED_PILOT_CONSOLE_VERIFY_RUNBOOK_PATH,
        "report_dir": report_dir,
        "directory_exists": Path(report_dir).exists(),
        "latest_report_present": False,
        "status": "skipped",
        "generated_at": "",
        "controlled_internal_pilot": "Manual-Review",
        "public_production_direct_launch": "No-Go",
        "backend_url": "",
        "frontend_url": "",
        "missing_condition_count": 0,
        "missing_conditions": [],
        "pid_file_present_after_verify": False,
        "secret_plaintext_output": False,
        "real_llm_executed": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
    }
    if latest is None:
        return base
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            **base,
            "directory_exists": True,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
            "missing_conditions": ["controlled_pilot_console_verify:json_parse_failed"],
            "missing_condition_count": 1,
        }
    missing = payload.get("missing_conditions") if isinstance(payload.get("missing_conditions"), list) else []
    runtime = payload.get("console_runtime") if isinstance(payload.get("console_runtime"), dict) else {}
    return {
        **base,
        "directory_exists": True,
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": _safe_text_value(payload.get("status") or "skipped"),
        "generated_at": _safe_text_value(payload.get("generated_at") or ""),
        "controlled_internal_pilot": _safe_text_value(payload.get("controlled_internal_pilot") or "Manual-Review"),
        "public_production_direct_launch": _safe_text_value(
            payload.get("public_production_direct_launch") or "No-Go"
        ),
        "backend_url": _safe_text_value(payload.get("backend_url") or ""),
        "frontend_url": _safe_text_value(payload.get("frontend_url") or ""),
        "missing_condition_count": int(payload.get("missing_condition_count") or 0),
        "missing_conditions": [_safe_text_value(item) for item in missing[:16]],
        "pid_file_present_after_verify": bool(runtime.get("pid_file_present_after_verify", False)),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
        "real_llm_executed": bool(payload.get("real_llm_executed", False)),
        "business_data_written": bool(payload.get("business_data_written", False)),
        "audit_data_written": bool(payload.get("audit_data_written", False)),
        "metrics_data_written": bool(payload.get("metrics_data_written", False)),
    }


def _collect_controlled_pilot_console_preflight_summary() -> dict[str, Any]:
    report_dir = _get_controlled_pilot_console_preflight_report_dir()
    latest = _latest_json_report(report_dir)
    base = {
        "mode": "read_only_latest_report",
        "runbook_path": CONTROLLED_PILOT_CONSOLE_PREFLIGHT_RUNBOOK_PATH,
        "report_dir": report_dir,
        "directory_exists": Path(report_dir).exists(),
        "latest_report_present": False,
        "status": "skipped",
        "generated_at": "",
        "ready_for_local_verify": False,
        "recommended_command": "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\controlled_pilot_console_verify.ps1",
        "backend_url": "",
        "frontend_url": "",
        "blocking_condition_count": 0,
        "blocking_conditions": [],
        "latest_verify_status": "skipped",
        "latest_verify_controlled_internal_pilot": "Manual-Review",
        "public_production_direct_launch": "No-Go",
        "secret_plaintext_output": False,
        "real_llm_executed": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
    }
    if latest is None:
        return base
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            **base,
            "directory_exists": True,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
            "blocking_conditions": ["controlled_pilot_console_preflight:json_parse_failed"],
            "blocking_condition_count": 1,
        }
    blocking = payload.get("blocking_conditions") if isinstance(payload.get("blocking_conditions"), list) else []
    latest_verify = payload.get("latest_verify") if isinstance(payload.get("latest_verify"), dict) else {}
    return {
        **base,
        "directory_exists": True,
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": _safe_text_value(payload.get("status") or "skipped"),
        "generated_at": _safe_text_value(payload.get("generated_at") or ""),
        "ready_for_local_verify": bool(payload.get("ready_for_local_verify", False)),
        "recommended_command": _safe_text_value(payload.get("recommended_command") or base["recommended_command"]),
        "backend_url": _safe_text_value(payload.get("backend_url") or ""),
        "frontend_url": _safe_text_value(payload.get("frontend_url") or ""),
        "blocking_condition_count": int(payload.get("blocking_condition_count") or 0),
        "blocking_conditions": [_safe_text_value(item) for item in blocking[:16]],
        "latest_verify_status": _safe_text_value(latest_verify.get("status") or "skipped"),
        "latest_verify_controlled_internal_pilot": _safe_text_value(
            latest_verify.get("controlled_internal_pilot") or "Manual-Review"
        ),
        "public_production_direct_launch": _safe_text_value(
            payload.get("public_production_direct_launch") or "No-Go"
        ),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
        "real_llm_executed": bool(payload.get("real_llm_executed", False)),
        "business_data_written": bool(payload.get("business_data_written", False)),
        "audit_data_written": bool(payload.get("audit_data_written", False)),
        "metrics_data_written": bool(payload.get("metrics_data_written", False)),
    }


def _collect_production_landing_status_summary() -> dict[str, Any]:
    report_dir = _get_production_landing_status_report_dir()
    latest = _latest_json_report(report_dir)
    base = {
        "mode": "read_only_latest_report",
        "runbook_path": PRODUCTION_LANDING_STATUS_RUNBOOK_PATH,
        "report_dir": report_dir,
        "directory_exists": Path(report_dir).exists(),
        "latest_report_present": False,
        "status": "skipped",
        "generated_at": "",
        "controlled_pilot_ready": False,
        "ready_domain_count": 0,
        "domain_count": 0,
        "blocked_domains": [],
        "blockers": [],
        "next_commands": [],
        "public_production_direct_launch": "No-Go",
        "secret_plaintext_output": False,
    }
    if latest is None:
        return base
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            **base,
            "directory_exists": True,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
        }
    blocked_domains = payload.get("blocked_domains") if isinstance(payload.get("blocked_domains"), list) else []
    blockers = payload.get("blockers") if isinstance(payload.get("blockers"), list) else []
    commands = payload.get("next_commands") if isinstance(payload.get("next_commands"), list) else []
    return {
        **base,
        "directory_exists": True,
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": str(payload.get("status") or "skipped"),
        "generated_at": str(payload.get("generated_at") or ""),
        "controlled_pilot_ready": bool(payload.get("controlled_pilot_ready", False)),
        "ready_domain_count": int(payload.get("ready_domain_count", 0) or 0),
        "domain_count": int(payload.get("domain_count", 0) or 0),
        "blocked_domains": [_safe_text_value(item) for item in blocked_domains[:12]],
        "blockers": [_safe_text_value(item) for item in blockers[:24]],
        "next_commands": _safe_command_list(commands[:12]),
        "public_production_direct_launch": str(payload.get("public_production_direct_launch") or "No-Go"),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
    }


def _collect_production_landing_env_check_summary() -> dict[str, Any]:
    report_dir = _get_production_landing_env_check_report_dir()
    latest = _latest_json_report(report_dir)
    if latest is None:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": PRODUCTION_LANDING_ENV_CHECK_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": Path(report_dir).exists(),
            "latest_report_present": False,
            "status": "skipped",
            "generated_at": "",
            "env_file_present": False,
            "ready_domain_count": 0,
            "blocked_domain_count": 5,
            "domain_count": 5,
            "domains": [],
            "blocked_domain_summaries": [],
            "staging_smoke_command": SAFE_INFRA_AND_LLM_SMOKE_COMMAND,
            "business_smoke_command": SAFE_BUSINESS_READ_SMOKE_COMMAND,
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        }

    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": PRODUCTION_LANDING_ENV_CHECK_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": True,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
            "generated_at": "",
            "env_file_present": False,
            "ready_domain_count": 0,
            "blocked_domain_count": 5,
            "domain_count": 5,
            "domains": [],
            "blocked_domain_summaries": [],
            "staging_smoke_command": SAFE_INFRA_AND_LLM_SMOKE_COMMAND,
            "business_smoke_command": SAFE_BUSINESS_READ_SMOKE_COMMAND,
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        }

    return {
        "mode": "read_only_latest_report",
        "runbook_path": PRODUCTION_LANDING_ENV_CHECK_RUNBOOK_PATH,
        "report_dir": report_dir,
        "directory_exists": True,
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": str(payload.get("status") or "skipped"),
        "generated_at": str(payload.get("generated_at") or ""),
        "env_file_present": bool(payload.get("env_file_present", False)),
        "ready_domain_count": int(payload.get("ready_domain_count", 0) or 0),
        "blocked_domain_count": int(payload.get("blocked_domain_count", 0) or 0),
        "domain_count": int(payload.get("domain_count", 5) or 5),
        "domains": _safe_landing_env_check_domains(payload.get("domains")),
        "blocked_domain_summaries": _safe_landing_env_blocked_domain_summaries(payload.get("domains")),
        "staging_smoke_command": _safe_text_value(
            payload.get("staging_smoke_command")
            or SAFE_INFRA_AND_LLM_SMOKE_COMMAND
        ),
        "business_smoke_command": _safe_text_value(payload.get("business_smoke_command") or SAFE_BUSINESS_READ_SMOKE_COMMAND),
        "public_production_direct_launch": str(payload.get("public_production_direct_launch") or "No-Go"),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
    }


def _collect_production_landing_env_runner_summary() -> dict[str, Any]:
    report_dir = _get_production_landing_env_runner_report_dir()
    latest = _latest_json_report(report_dir)
    if latest is None:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": PRODUCTION_LANDING_ENV_RUNNER_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": Path(report_dir).exists(),
            "latest_report_present": False,
            "status": "skipped",
            "generated_at": "",
            "action": "",
            "env_file_present": False,
            "env_key_count": 0,
            "command": "",
            "return_code": None,
            "child_status": "",
            "child_summary": {
                "status": "",
                "ready_domain_count": 0,
                "domain_count": 0,
                "secret_plaintext_output": False,
            },
            "stdout": [],
            "stderr": [],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        }

    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": PRODUCTION_LANDING_ENV_RUNNER_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": True,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
            "generated_at": "",
            "action": "",
            "env_file_present": False,
            "env_key_count": 0,
            "command": "",
            "return_code": None,
            "child_status": "",
            "child_summary": {
                "status": "",
                "ready_domain_count": 0,
                "domain_count": 0,
                "secret_plaintext_output": False,
            },
            "stdout": [],
            "stderr": [],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        }

    stdout = payload.get("stdout") if isinstance(payload.get("stdout"), list) else []
    stderr = payload.get("stderr") if isinstance(payload.get("stderr"), list) else []
    child_summary = payload.get("child_summary") if isinstance(payload.get("child_summary"), dict) else {}
    return {
        "mode": "read_only_latest_report",
        "runbook_path": PRODUCTION_LANDING_ENV_RUNNER_RUNBOOK_PATH,
        "report_dir": report_dir,
        "directory_exists": True,
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": str(payload.get("status") or "skipped"),
        "generated_at": str(payload.get("generated_at") or ""),
        "action": _safe_text_value(payload.get("action") or ""),
        "env_file_present": bool(payload.get("env_file_present", False)),
        "env_key_count": int(payload.get("env_key_count", 0) or 0),
        "command": _safe_text_value(payload.get("command") or ""),
        "return_code": payload.get("return_code") if isinstance(payload.get("return_code"), int) else None,
        "child_status": _safe_text_value(payload.get("child_status") or child_summary.get("status") or ""),
        "child_summary": {
            "status": _safe_text_value(child_summary.get("status") or ""),
            "ready_domain_count": int(child_summary.get("ready_domain_count", 0) or 0),
            "domain_count": int(child_summary.get("domain_count", 0) or 0),
            "secret_plaintext_output": bool(child_summary.get("secret_plaintext_output", False)),
        },
        "stdout": [_safe_text_value(item) for item in stdout[:12]],
        "stderr": [_safe_text_value(item) for item in stderr[:12]],
        "public_production_direct_launch": str(payload.get("public_production_direct_launch") or "No-Go"),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
    }


def _collect_production_landing_execution_gate_summary() -> dict[str, Any]:
    report_dir = _get_production_landing_execution_gate_report_dir()
    latest = _latest_json_report(report_dir)
    if latest is None:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": PRODUCTION_LANDING_EXECUTION_GATE_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": Path(report_dir).exists(),
            "latest_report_present": False,
            "status": "skipped",
            "generated_at": "",
            "env_file_present": False,
            "requested_domains": [],
            "ready_domains": [],
            "blocked_domains": [],
            "requested_domain_count": 0,
            "ready_domain_count": 0,
            "blocked_domain_count": 0,
            "all_requested_domains_ready_for_execute": False,
            "execution_allowed": False,
            "real_smoke_executed": False,
            "business_smoke_executed": False,
            "domains": [],
            "safe_runner_commands": [],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        }

    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": PRODUCTION_LANDING_EXECUTION_GATE_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": True,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
            "generated_at": "",
            "env_file_present": False,
            "requested_domains": [],
            "ready_domains": [],
            "blocked_domains": [],
            "requested_domain_count": 0,
            "ready_domain_count": 0,
            "blocked_domain_count": 0,
            "all_requested_domains_ready_for_execute": False,
            "execution_allowed": False,
            "real_smoke_executed": False,
            "business_smoke_executed": False,
            "domains": [],
            "safe_runner_commands": [],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        }

    requested_domains = payload.get("requested_domains") if isinstance(payload.get("requested_domains"), list) else []
    ready_domains = payload.get("ready_domains") if isinstance(payload.get("ready_domains"), list) else []
    blocked_domains = payload.get("blocked_domains") if isinstance(payload.get("blocked_domains"), list) else []
    return {
        "mode": "read_only_latest_report",
        "runbook_path": PRODUCTION_LANDING_EXECUTION_GATE_RUNBOOK_PATH,
        "report_dir": report_dir,
        "directory_exists": True,
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": str(payload.get("status") or "skipped"),
        "generated_at": str(payload.get("generated_at") or ""),
        "env_file_present": bool(payload.get("env_file_present", False)),
        "requested_domains": [_safe_text_value(item) for item in requested_domains[:12]],
        "ready_domains": [_safe_text_value(item) for item in ready_domains[:12]],
        "blocked_domains": [_safe_text_value(item) for item in blocked_domains[:12]],
        "requested_domain_count": int(payload.get("requested_domain_count", 0) or 0),
        "ready_domain_count": int(payload.get("ready_domain_count", 0) or 0),
        "blocked_domain_count": int(payload.get("blocked_domain_count", 0) or 0),
        "all_requested_domains_ready_for_execute": bool(payload.get("all_requested_domains_ready_for_execute", False)),
        "execution_allowed": bool(payload.get("execution_allowed", False)),
        "real_smoke_executed": bool(payload.get("real_smoke_executed", False)),
        "business_smoke_executed": bool(payload.get("business_smoke_executed", False)),
        "domains": _safe_landing_env_check_domains(payload.get("domains")),
        "safe_runner_commands": _safe_command_list(payload.get("safe_runner_commands")),
        "public_production_direct_launch": str(payload.get("public_production_direct_launch") or "No-Go"),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
    }


def _collect_production_landing_input_readiness_summary() -> dict[str, Any]:
    report_dir = _get_production_landing_input_readiness_report_dir()
    latest = _latest_json_report(report_dir)
    if latest is None:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": PRODUCTION_LANDING_INPUT_READINESS_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": Path(report_dir).exists(),
            "latest_report_present": False,
            "status": "skipped",
            "generated_at": "",
            "ready_input_count": 0,
            "required_input_count": 4,
            "missing_input_count": 4,
            "blocked_input_count": 0,
            "source_reports": {},
            "resolved_paths": {},
            "inputs": [],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "auto_approved": False,
            "auto_closed": False,
        }

    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": PRODUCTION_LANDING_INPUT_READINESS_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": True,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
            "generated_at": "",
            "ready_input_count": 0,
            "required_input_count": 4,
            "missing_input_count": 4,
            "blocked_input_count": 1,
            "source_reports": {},
            "resolved_paths": {},
            "inputs": [],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "auto_approved": False,
            "auto_closed": False,
        }

    return {
        "mode": "read_only_latest_report",
        "runbook_path": PRODUCTION_LANDING_INPUT_READINESS_RUNBOOK_PATH,
        "report_dir": report_dir,
        "directory_exists": True,
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": str(payload.get("status") or "skipped"),
        "generated_at": str(payload.get("generated_at") or ""),
        "ready_input_count": int(payload.get("ready_input_count", 0) or 0),
        "required_input_count": int(payload.get("required_input_count", 4) or 4),
        "missing_input_count": int(payload.get("missing_input_count", 0) or 0),
        "blocked_input_count": int(payload.get("blocked_input_count", 0) or 0),
        "source_reports": _safe_string_map(payload.get("source_reports")),
        "resolved_paths": _safe_string_map(payload.get("resolved_paths")),
        "inputs": _safe_landing_input_items(payload.get("inputs")),
        "public_production_direct_launch": str(payload.get("public_production_direct_launch") or "No-Go"),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
        "auto_approved": bool(payload.get("auto_approved", False)),
        "auto_closed": bool(payload.get("auto_closed", False)),
    }


def _collect_manual_signoff_evidence_ack_status_summary() -> dict[str, Any]:
    report_dir = _get_manual_signoff_evidence_ack_status_report_dir()
    latest = _latest_json_report(report_dir)
    if latest is None:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": MANUAL_SIGNOFF_EVIDENCE_ACK_STATUS_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": Path(report_dir).exists(),
            "latest_report_present": False,
            "status": "skipped",
            "generated_at": "",
            "recommended_accept_count": 0,
            "item_count": 4,
            "blocked_item_count": 0,
            "items": [],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "auto_approved": False,
            "auto_closed": False,
        }

    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": MANUAL_SIGNOFF_EVIDENCE_ACK_STATUS_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": True,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
            "generated_at": "",
            "recommended_accept_count": 0,
            "item_count": 4,
            "blocked_item_count": 1,
            "items": [],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "auto_approved": False,
            "auto_closed": False,
        }

    return {
        "mode": "read_only_latest_report",
        "runbook_path": MANUAL_SIGNOFF_EVIDENCE_ACK_STATUS_RUNBOOK_PATH,
        "report_dir": report_dir,
        "directory_exists": True,
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": str(payload.get("status") or "skipped"),
        "generated_at": str(payload.get("generated_at") or ""),
        "recommended_accept_count": int(payload.get("recommended_accept_count", 0) or 0),
        "item_count": int(payload.get("item_count", 4) or 4),
        "blocked_item_count": int(payload.get("blocked_item_count", 0) or 0),
        "items": _safe_manual_signoff_ack_items(payload.get("items")),
        "public_production_direct_launch": str(payload.get("public_production_direct_launch") or "No-Go"),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
        "auto_approved": bool(payload.get("auto_approved", False)),
        "auto_closed": bool(payload.get("auto_closed", False)),
    }


def _collect_manual_signoff_record_validation_summary() -> dict[str, Any]:
    report_dir = _get_manual_signoff_record_validation_report_dir()
    latest = _latest_json_report(report_dir)
    if latest is None:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": MANUAL_SIGNOFF_RECORD_VALIDATION_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": Path(report_dir).exists(),
            "latest_report_present": False,
            "status": "skipped",
            "generated_at": "",
            "signoff_record_present": False,
            "ack_status": "skipped",
            "manual_signoff_completed": False,
            "decision": "No-Go",
            "roles": [],
            "evidence_acknowledgements": [],
            "missing_conditions": [],
            "missing_condition_count": 0,
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "auto_approved": False,
            "auto_closed": False,
        }

    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": MANUAL_SIGNOFF_RECORD_VALIDATION_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": True,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
            "generated_at": "",
            "signoff_record_present": False,
            "ack_status": "blocked",
            "manual_signoff_completed": False,
            "decision": "No-Go",
            "roles": [],
            "evidence_acknowledgements": [],
            "missing_conditions": ["manual_signoff_record_validation:json_parse_failed"],
            "missing_condition_count": 1,
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "auto_approved": False,
            "auto_closed": False,
        }

    missing = payload.get("missing_conditions") if isinstance(payload.get("missing_conditions"), list) else []
    return {
        "mode": "read_only_latest_report",
        "runbook_path": MANUAL_SIGNOFF_RECORD_VALIDATION_RUNBOOK_PATH,
        "report_dir": report_dir,
        "directory_exists": True,
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": str(payload.get("status") or "skipped"),
        "generated_at": str(payload.get("generated_at") or ""),
        "signoff_record_present": bool(payload.get("signoff_record_present", False)),
        "ack_status": _safe_text_value(payload.get("ack_status") or "skipped"),
        "manual_signoff_completed": bool(payload.get("manual_signoff_completed", False)),
        "decision": _safe_text_value(payload.get("decision") or "No-Go"),
        "roles": _safe_manual_signoff_validation_roles(payload.get("roles")),
        "evidence_acknowledgements": _safe_manual_signoff_validation_evidence(
            payload.get("evidence_acknowledgements")
        ),
        "missing_conditions": [_safe_text_value(item) for item in missing[:32]],
        "missing_condition_count": int(payload.get("missing_condition_count", len(missing)) or 0),
        "public_production_direct_launch": str(payload.get("public_production_direct_launch") or "No-Go"),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
        "auto_approved": bool(payload.get("auto_approved", False)),
        "auto_closed": bool(payload.get("auto_closed", False)),
    }


def _collect_manual_signoff_record_fill_summary() -> dict[str, Any]:
    report_dir = _get_manual_signoff_record_fill_report_dir()
    latest = _latest_json_report(report_dir)
    if latest is None:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": MANUAL_SIGNOFF_RECORD_FILL_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": Path(report_dir).exists(),
            "latest_report_present": False,
            "status": "skipped",
            "generated_at": "",
            "signoff_record": "",
            "filled": False,
            "manual_signoff_completed": False,
            "decision": "No-Go",
            "missing_conditions": [],
            "missing_condition_count": 0,
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "auto_signed": False,
            "auto_approved": False,
            "auto_closed": False,
        }

    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": MANUAL_SIGNOFF_RECORD_FILL_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": True,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
            "generated_at": "",
            "signoff_record": "",
            "filled": False,
            "manual_signoff_completed": False,
            "decision": "No-Go",
            "missing_conditions": ["manual_signoff_record_fill:json_parse_failed"],
            "missing_condition_count": 1,
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "auto_signed": False,
            "auto_approved": False,
            "auto_closed": False,
        }

    missing = payload.get("missing_conditions") if isinstance(payload.get("missing_conditions"), list) else []
    return {
        "mode": "read_only_latest_report",
        "runbook_path": MANUAL_SIGNOFF_RECORD_FILL_RUNBOOK_PATH,
        "report_dir": report_dir,
        "directory_exists": True,
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": str(payload.get("status") or "skipped"),
        "generated_at": str(payload.get("generated_at") or ""),
        "signoff_record": _safe_text_value(payload.get("signoff_record") or ""),
        "filled": bool(payload.get("filled", False)),
        "manual_signoff_completed": bool(payload.get("manual_signoff_completed", False)),
        "decision": _safe_text_value(payload.get("decision") or "No-Go"),
        "missing_conditions": [_safe_text_value(item) for item in missing[:32]],
        "missing_condition_count": int(payload.get("missing_condition_count", len(missing)) or 0),
        "public_production_direct_launch": str(payload.get("public_production_direct_launch") or "No-Go"),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
        "auto_signed": bool(payload.get("auto_signed", False)),
        "auto_approved": bool(payload.get("auto_approved", False)),
        "auto_closed": bool(payload.get("auto_closed", False)),
    }


def _safe_signoff_closeout_steps(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    steps: list[dict[str, Any]] = []
    for item in value[:16]:
        if not isinstance(item, dict):
            continue
        steps.append(
            {
                "step_id": _safe_text_value(item.get("step_id") or ""),
                "status": _safe_text_value(item.get("status") or ""),
                "json_path": _safe_text_value(item.get("json_path") or ""),
                "secret_plaintext_output": bool(item.get("secret_plaintext_output", False)),
            }
        )
    return steps


def _collect_production_landing_signoff_closeout_summary() -> dict[str, Any]:
    report_dir = _get_production_landing_signoff_closeout_report_dir()
    latest = _latest_json_report(report_dir)
    if latest is None:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": PRODUCTION_LANDING_SIGNOFF_CLOSEOUT_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": Path(report_dir).exists(),
            "latest_report_present": False,
            "status": "skipped",
            "generated_at": "",
            "final_status": "",
            "signoff_record": "",
            "target_record": "",
            "target_record_written": False,
            "steps": [],
            "missing_conditions": [],
            "missing_condition_count": 0,
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "auto_signed": False,
            "auto_approved": False,
            "auto_closed": False,
        }

    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": PRODUCTION_LANDING_SIGNOFF_CLOSEOUT_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": True,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
            "generated_at": "",
            "final_status": "",
            "signoff_record": "",
            "target_record": "",
            "target_record_written": False,
            "steps": [],
            "missing_conditions": ["production_landing_signoff_closeout:json_parse_failed"],
            "missing_condition_count": 1,
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "auto_signed": False,
            "auto_approved": False,
            "auto_closed": False,
        }

    missing = payload.get("missing_conditions") if isinstance(payload.get("missing_conditions"), list) else []
    return {
        "mode": "read_only_latest_report",
        "runbook_path": PRODUCTION_LANDING_SIGNOFF_CLOSEOUT_RUNBOOK_PATH,
        "report_dir": report_dir,
        "directory_exists": True,
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": str(payload.get("status") or "skipped"),
        "generated_at": str(payload.get("generated_at") or ""),
        "final_status": _safe_text_value(payload.get("final_status") or ""),
        "signoff_record": _safe_text_value(payload.get("signoff_record") or ""),
        "target_record": _safe_text_value(payload.get("target_record") or ""),
        "target_record_written": bool(payload.get("target_record_written", False)),
        "steps": _safe_signoff_closeout_steps(payload.get("steps")),
        "missing_conditions": [_safe_text_value(item) for item in missing[:32]],
        "missing_condition_count": int(payload.get("missing_condition_count", len(missing)) or 0),
        "public_production_direct_launch": str(payload.get("public_production_direct_launch") or "No-Go"),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
        "auto_signed": bool(payload.get("auto_signed", False)),
        "auto_approved": bool(payload.get("auto_approved", False)),
        "auto_closed": bool(payload.get("auto_closed", False)),
    }


def _collect_production_landing_pre_signoff_gate_summary() -> dict[str, Any]:
    report_dir = _get_production_landing_pre_signoff_gate_report_dir()
    latest = _latest_json_report(report_dir)
    if latest is None:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": PRODUCTION_LANDING_PRE_SIGNOFF_GATE_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": Path(report_dir).exists(),
            "latest_report_present": False,
            "status": "skipped",
            "generated_at": "",
            "ready_for_manual_signoff": False,
            "technical_evidence_ready": False,
            "ack_ready": False,
            "action_required_input_count": 0,
            "non_signoff_blockers": [],
            "non_signoff_blocker_count": 0,
            "signoff_only_missing_conditions": [],
            "status_blockers": [],
            "final_missing_conditions": [],
            "closeout_missing_conditions": [],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "auto_signed": False,
            "auto_approved": False,
            "auto_closed": False,
        }

    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": PRODUCTION_LANDING_PRE_SIGNOFF_GATE_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": True,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
            "generated_at": "",
            "ready_for_manual_signoff": False,
            "technical_evidence_ready": False,
            "ack_ready": False,
            "action_required_input_count": 0,
            "non_signoff_blockers": ["production_landing_pre_signoff_gate:json_parse_failed"],
            "non_signoff_blocker_count": 1,
            "signoff_only_missing_conditions": [],
            "status_blockers": [],
            "final_missing_conditions": [],
            "closeout_missing_conditions": [],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "auto_signed": False,
            "auto_approved": False,
            "auto_closed": False,
        }

    non_signoff = payload.get("non_signoff_blockers") if isinstance(payload.get("non_signoff_blockers"), list) else []
    signoff_only = (
        payload.get("signoff_only_missing_conditions")
        if isinstance(payload.get("signoff_only_missing_conditions"), list)
        else []
    )
    return {
        "mode": "read_only_latest_report",
        "runbook_path": PRODUCTION_LANDING_PRE_SIGNOFF_GATE_RUNBOOK_PATH,
        "report_dir": report_dir,
        "directory_exists": True,
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": str(payload.get("status") or "skipped"),
        "generated_at": str(payload.get("generated_at") or ""),
        "ready_for_manual_signoff": bool(payload.get("ready_for_manual_signoff", False)),
        "technical_evidence_ready": bool(payload.get("technical_evidence_ready", False)),
        "ack_ready": bool(payload.get("ack_ready", False)),
        "action_required_input_count": int(payload.get("action_required_input_count") or 0),
        "non_signoff_blockers": [_safe_text_value(item) for item in non_signoff[:32]],
        "non_signoff_blocker_count": int(payload.get("non_signoff_blocker_count", len(non_signoff)) or 0),
        "signoff_only_missing_conditions": [_safe_text_value(item) for item in signoff_only[:32]],
        "status_blockers": [_safe_text_value(item) for item in _safe_string_list(payload.get("status_blockers"))[:32]],
        "final_missing_conditions": [
            _safe_text_value(item) for item in _safe_string_list(payload.get("final_missing_conditions"))[:32]
        ],
        "closeout_missing_conditions": [
            _safe_text_value(item) for item in _safe_string_list(payload.get("closeout_missing_conditions"))[:32]
        ],
        "public_production_direct_launch": str(payload.get("public_production_direct_launch") or "No-Go"),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
        "auto_signed": bool(payload.get("auto_signed", False)),
        "auto_approved": bool(payload.get("auto_approved", False)),
        "auto_closed": bool(payload.get("auto_closed", False)),
    }


def _safe_reviewer_packet_evidence(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    evidence: list[dict[str, Any]] = []
    for item in value[:16]:
        if not isinstance(item, dict):
            continue
        evidence.append(
            {
                "source_id": _safe_text_value(item.get("source_id") or ""),
                "status": _safe_text_value(item.get("status") or ""),
                "latest_report_present": bool(item.get("latest_report_present", False)),
                "latest_json_path": _safe_text_value(item.get("latest_json_path") or ""),
                "secret_plaintext_output": bool(item.get("secret_plaintext_output", False)),
            }
        )
    return evidence


def _collect_production_landing_signoff_reviewer_packet_summary() -> dict[str, Any]:
    report_dir = _get_production_landing_signoff_reviewer_packet_report_dir()
    latest = _latest_json_report(report_dir)
    if latest is None:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": PRODUCTION_LANDING_SIGNOFF_REVIEWER_PACKET_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": Path(report_dir).exists(),
            "latest_report_present": False,
            "status": "skipped",
            "generated_at": "",
            "ready_for_manual_signoff": False,
            "technical_evidence_ready": False,
            "non_signoff_blocker_count": 0,
            "ack_ready": False,
            "missing_conditions": [],
            "missing_condition_count": 0,
            "recommended_closeout_command": "",
            "evidence": [],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "auto_signed": False,
            "auto_approved": False,
            "auto_closed": False,
        }

    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": PRODUCTION_LANDING_SIGNOFF_REVIEWER_PACKET_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": True,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
            "generated_at": "",
            "ready_for_manual_signoff": False,
            "technical_evidence_ready": False,
            "non_signoff_blocker_count": 1,
            "ack_ready": False,
            "missing_conditions": ["production_landing_signoff_reviewer_packet:json_parse_failed"],
            "missing_condition_count": 1,
            "recommended_closeout_command": "",
            "evidence": [],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "auto_signed": False,
            "auto_approved": False,
            "auto_closed": False,
        }

    missing = payload.get("missing_conditions") if isinstance(payload.get("missing_conditions"), list) else []
    return {
        "mode": "read_only_latest_report",
        "runbook_path": PRODUCTION_LANDING_SIGNOFF_REVIEWER_PACKET_RUNBOOK_PATH,
        "report_dir": report_dir,
        "directory_exists": True,
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": str(payload.get("status") or "skipped"),
        "generated_at": str(payload.get("generated_at") or ""),
        "ready_for_manual_signoff": bool(payload.get("ready_for_manual_signoff", False)),
        "technical_evidence_ready": bool(payload.get("technical_evidence_ready", False)),
        "non_signoff_blocker_count": int(payload.get("non_signoff_blocker_count") or 0),
        "ack_ready": bool(payload.get("ack_ready", False)),
        "missing_conditions": [_safe_text_value(item) for item in missing[:32]],
        "missing_condition_count": int(payload.get("missing_condition_count", len(missing)) or 0),
        "recommended_closeout_command": _safe_text_value(payload.get("recommended_closeout_command") or ""),
        "evidence": _safe_reviewer_packet_evidence(payload.get("evidence")),
        "public_production_direct_launch": str(payload.get("public_production_direct_launch") or "No-Go"),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
        "auto_signed": bool(payload.get("auto_signed", False)),
        "auto_approved": bool(payload.get("auto_approved", False)),
        "auto_closed": bool(payload.get("auto_closed", False)),
    }


def _collect_manual_signoff_record_promote_summary() -> dict[str, Any]:
    report_dir = _get_manual_signoff_record_promote_report_dir()
    latest = _latest_json_report(report_dir)
    if latest is None:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": MANUAL_SIGNOFF_RECORD_PROMOTE_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": Path(report_dir).exists(),
            "latest_report_present": False,
            "status": "skipped",
            "generated_at": "",
            "source_record_present": False,
            "target_record_written": False,
            "promoted": False,
            "manual_signoff_completed": False,
            "decision": "No-Go",
            "missing_conditions": [],
            "missing_condition_count": 0,
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "auto_approved": False,
            "auto_closed": False,
        }

    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": MANUAL_SIGNOFF_RECORD_PROMOTE_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": True,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
            "generated_at": "",
            "source_record_present": False,
            "target_record_written": False,
            "promoted": False,
            "manual_signoff_completed": False,
            "decision": "No-Go",
            "missing_conditions": ["manual_signoff_record_promote:json_parse_failed"],
            "missing_condition_count": 1,
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "auto_approved": False,
            "auto_closed": False,
        }

    missing = payload.get("missing_conditions") if isinstance(payload.get("missing_conditions"), list) else []
    return {
        "mode": "read_only_latest_report",
        "runbook_path": MANUAL_SIGNOFF_RECORD_PROMOTE_RUNBOOK_PATH,
        "report_dir": report_dir,
        "directory_exists": True,
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": str(payload.get("status") or "skipped"),
        "generated_at": str(payload.get("generated_at") or ""),
        "source_record": _safe_text_value(payload.get("source_record") or ""),
        "target_record": _safe_text_value(payload.get("target_record") or ""),
        "source_record_present": bool(payload.get("source_record_present", False)),
        "target_record_written": bool(payload.get("target_record_written", False)),
        "promoted": bool(payload.get("promoted", False)),
        "manual_signoff_completed": bool(payload.get("manual_signoff_completed", False)),
        "decision": _safe_text_value(payload.get("decision") or "No-Go"),
        "missing_conditions": [_safe_text_value(item) for item in missing[:32]],
        "missing_condition_count": int(payload.get("missing_condition_count", len(missing)) or 0),
        "public_production_direct_launch": str(payload.get("public_production_direct_launch") or "No-Go"),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
        "auto_approved": bool(payload.get("auto_approved", False)),
        "auto_closed": bool(payload.get("auto_closed", False)),
    }


def _collect_production_landing_text_quality_summary() -> dict[str, Any]:
    report_dir = _get_production_landing_text_quality_report_dir()
    latest = _latest_json_report(report_dir)
    if latest is None:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": PRODUCTION_LANDING_TEXT_QUALITY_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": Path(report_dir).exists(),
            "latest_report_present": False,
            "status": "skipped",
            "generated_at": "",
            "checked_file_count": 0,
            "blocked_file_count": 0,
            "files": [],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "auto_approved": False,
            "auto_closed": False,
        }

    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": PRODUCTION_LANDING_TEXT_QUALITY_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": True,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
            "generated_at": "",
            "checked_file_count": 0,
            "blocked_file_count": 1,
            "files": [],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "auto_approved": False,
            "auto_closed": False,
        }

    return {
        "mode": "read_only_latest_report",
        "runbook_path": PRODUCTION_LANDING_TEXT_QUALITY_RUNBOOK_PATH,
        "report_dir": report_dir,
        "directory_exists": True,
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": str(payload.get("status") or "skipped"),
        "generated_at": str(payload.get("generated_at") or ""),
        "checked_file_count": int(payload.get("checked_file_count", 0) or 0),
        "blocked_file_count": int(payload.get("blocked_file_count", 0) or 0),
        "files": _safe_text_quality_files(payload.get("files")),
        "public_production_direct_launch": str(payload.get("public_production_direct_launch") or "No-Go"),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
        "auto_approved": bool(payload.get("auto_approved", False)),
        "auto_closed": bool(payload.get("auto_closed", False)),
    }


def _safe_evidence_freshness_sources(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows = []
    for item in value[:24]:
        if not isinstance(item, dict):
            continue
        missing = item.get("missing_conditions") if isinstance(item.get("missing_conditions"), list) else []
        rows.append(
            {
                "source_id": _safe_text_value(item.get("source_id") or ""),
                "present": bool(item.get("present", False)),
                "status": _safe_text_value(item.get("status") or "unknown"),
                "generated_at": _safe_text_value(item.get("generated_at") or ""),
                "report_commit": _safe_text_value(item.get("report_commit") or ""),
                "commit_matches_head": bool(item.get("commit_matches_head", False)),
                "secret_like_detected": bool(item.get("secret_like_detected", False)),
                "missing_conditions": [_safe_text_value(condition) for condition in missing[:16]],
            }
        )
    return rows


def _collect_production_landing_evidence_freshness_summary() -> dict[str, Any]:
    report_dir = _get_production_landing_evidence_freshness_report_dir()
    latest = _latest_json_report(report_dir)
    if latest is None:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": PRODUCTION_LANDING_EVIDENCE_FRESHNESS_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": Path(report_dir).exists(),
            "latest_report_present": False,
            "status": "skipped",
            "generated_at": "",
            "current_commit": "",
            "worktree_clean": False,
            "source_count": 0,
            "stale_source_count": 0,
            "sources": [],
            "missing_conditions": [],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "auto_approved": False,
            "auto_closed": False,
        }

    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            "mode": "read_only_latest_report",
            "runbook_path": PRODUCTION_LANDING_EVIDENCE_FRESHNESS_RUNBOOK_PATH,
            "report_dir": report_dir,
            "directory_exists": True,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
            "generated_at": "",
            "current_commit": "",
            "worktree_clean": False,
            "source_count": 0,
            "stale_source_count": 1,
            "sources": [],
            "missing_conditions": ["production_landing_evidence_freshness:json_parse_failed"],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "auto_approved": False,
            "auto_closed": False,
        }

    missing = payload.get("missing_conditions") if isinstance(payload.get("missing_conditions"), list) else []
    return {
        "mode": "read_only_latest_report",
        "runbook_path": PRODUCTION_LANDING_EVIDENCE_FRESHNESS_RUNBOOK_PATH,
        "report_dir": report_dir,
        "directory_exists": True,
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": _safe_text_value(payload.get("status") or "skipped"),
        "generated_at": _safe_text_value(payload.get("generated_at") or ""),
        "current_commit": _safe_text_value(payload.get("current_commit") or payload.get("commit") or ""),
        "worktree_clean": bool(payload.get("worktree_clean", False)),
        "source_count": int(payload.get("source_count", 0) or 0),
        "stale_source_count": int(payload.get("stale_source_count", 0) or 0),
        "sources": _safe_evidence_freshness_sources(payload.get("sources")),
        "missing_conditions": [_safe_text_value(condition) for condition in missing[:32]],
        "public_production_direct_launch": _safe_text_value(payload.get("public_production_direct_launch") or "No-Go"),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
        "auto_approved": bool(payload.get("auto_approved", False)),
        "auto_closed": bool(payload.get("auto_closed", False)),
    }


def _collect_v4_evidence_summary() -> dict[str, Any]:
    entries = {
        key: {
            "runbook_path": V4_EVIDENCE_RUNBOOKS[key],
            **_count_json_reports(directory),
        }
        for key, directory in V4_EVIDENCE_DIRS.items()
    }
    return {
        "mode": "read_only",
        "entries": entries,
        "total_json_report_count": sum(int(item.get("json_report_count", 0) or 0) for item in entries.values()),
        "boundary": {
            "report_content_read": False,
            "real_llm_executed": False,
            "external_system_connected": False,
            "auto_approved": False,
            "auto_closed": False,
        },
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
    v4_evidence = _collect_v4_evidence_summary()
    production_pilot_bootstrap = _collect_production_pilot_bootstrap_summary()
    frontend_production_build = _collect_frontend_production_build_summary()
    production_runtime_smoke = _collect_production_runtime_smoke_summary()
    production_pilot_signoff = _collect_production_pilot_signoff_summary()
    business_system_read_smoke = _collect_business_system_read_smoke_summary()
    business_system_input_packet = _collect_business_system_input_packet_summary()
    business_system_production_readiness = _collect_business_system_production_readiness_summary()
    real_integration_staging_smoke = _collect_real_integration_staging_smoke_summary()
    real_production_environment_checklist = _collect_real_production_environment_checklist_summary()
    production_landing_input_readiness = _collect_production_landing_input_readiness_summary()
    production_landing_env_check = _collect_production_landing_env_check_summary()
    production_landing_env_runner = _collect_production_landing_env_runner_summary()
    production_landing_execution_gate = _collect_production_landing_execution_gate_summary()
    production_landing_action_pack = _collect_production_landing_action_pack_summary()
    production_landing_blocker_resolution = _collect_production_landing_blocker_resolution_summary()
    production_landing_final_verification = _collect_production_landing_final_verification_summary()
    production_pilot_evidence_bundle = _collect_production_pilot_evidence_bundle_summary()
    production_landing_xiaomi_llm_preflight = _collect_production_landing_xiaomi_llm_preflight_summary()
    operations_console_landing_smoke = _collect_operations_console_landing_smoke_summary()
    production_landing_status = _collect_production_landing_status_summary()
    manual_signoff_evidence_ack_status = _collect_manual_signoff_evidence_ack_status_summary()
    manual_signoff_record_validation = _collect_manual_signoff_record_validation_summary()
    manual_signoff_record_fill = _collect_manual_signoff_record_fill_summary()
    production_landing_signoff_closeout = _collect_production_landing_signoff_closeout_summary()
    controlled_pilot_launch_gate = _collect_controlled_pilot_launch_gate_summary(
        production_pilot_evidence_bundle=production_pilot_evidence_bundle,
        production_landing_final_verification=production_landing_final_verification,
        production_landing_signoff_closeout=production_landing_signoff_closeout,
        production_pilot_bootstrap=production_pilot_bootstrap,
    )
    controlled_pilot_launch_package = _collect_controlled_pilot_launch_package_summary()
    controlled_pilot_window_record = _collect_controlled_pilot_window_record_summary()
    controlled_pilot_window_status = _collect_controlled_pilot_window_status_summary()
    controlled_pilot_status_summary = _derive_controlled_pilot_status_summary(
        production_pilot_bootstrap=production_pilot_bootstrap,
        production_pilot_evidence_bundle=production_pilot_evidence_bundle,
        controlled_pilot_launch_gate=controlled_pilot_launch_gate,
        controlled_pilot_launch_package=controlled_pilot_launch_package,
        controlled_pilot_window_status=controlled_pilot_window_status,
        operations_console_landing_smoke=operations_console_landing_smoke,
        business_system_read_smoke=business_system_read_smoke,
        business_system_production_readiness=business_system_production_readiness,
    )
    controlled_pilot_operator_packet = _collect_controlled_pilot_operator_packet_summary()
    controlled_pilot_console_preflight = _collect_controlled_pilot_console_preflight_summary()
    controlled_pilot_console_verify = _collect_controlled_pilot_console_verify_summary()
    production_landing_pre_signoff_gate = _collect_production_landing_pre_signoff_gate_summary()
    production_landing_signoff_reviewer_packet = _collect_production_landing_signoff_reviewer_packet_summary()
    manual_signoff_record_promote = _collect_manual_signoff_record_promote_summary()
    production_landing_text_quality = _collect_production_landing_text_quality_summary()
    production_landing_evidence_freshness = _collect_production_landing_evidence_freshness_summary()

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
            "production_pilot_bootstrap": production_pilot_bootstrap,
            "frontend_production_build": frontend_production_build,
            "production_runtime_smoke": production_runtime_smoke,
            "production_pilot_signoff": production_pilot_signoff,
            "business_system_read_smoke": business_system_read_smoke,
            "business_system_input_packet": business_system_input_packet,
            "business_system_production_readiness": business_system_production_readiness,
            "real_integration_staging_smoke": real_integration_staging_smoke,
            "real_production_environment_checklist": real_production_environment_checklist,
            "production_landing_input_readiness": production_landing_input_readiness,
            "production_landing_env_check": production_landing_env_check,
            "production_landing_env_runner": production_landing_env_runner,
            "production_landing_execution_gate": production_landing_execution_gate,
            "production_landing_action_pack": production_landing_action_pack,
            "production_landing_blocker_resolution": production_landing_blocker_resolution,
            "production_landing_final_verification": production_landing_final_verification,
            "production_pilot_evidence_bundle": production_pilot_evidence_bundle,
            "controlled_pilot_status_summary": controlled_pilot_status_summary,
            "controlled_pilot_operator_packet": controlled_pilot_operator_packet,
            "controlled_pilot_console_preflight": controlled_pilot_console_preflight,
            "controlled_pilot_console_verify": controlled_pilot_console_verify,
            "controlled_pilot_launch_gate": controlled_pilot_launch_gate,
            "controlled_pilot_launch_package": controlled_pilot_launch_package,
            "controlled_pilot_window_record": controlled_pilot_window_record,
            "controlled_pilot_window_status": controlled_pilot_window_status,
            "production_landing_xiaomi_llm_preflight": production_landing_xiaomi_llm_preflight,
            "operations_console_landing_smoke": operations_console_landing_smoke,
            "production_landing_status": production_landing_status,
            "manual_signoff_evidence_ack_status": manual_signoff_evidence_ack_status,
            "manual_signoff_record_validation": manual_signoff_record_validation,
            "manual_signoff_record_fill": manual_signoff_record_fill,
            "production_landing_signoff_closeout": production_landing_signoff_closeout,
            "production_landing_pre_signoff_gate": production_landing_pre_signoff_gate,
            "production_landing_signoff_reviewer_packet": production_landing_signoff_reviewer_packet,
            "manual_signoff_record_promote": manual_signoff_record_promote,
            "production_landing_text_quality": production_landing_text_quality,
            "production_landing_evidence_freshness": production_landing_evidence_freshness,
            "v4_evidence": v4_evidence,
            "last_known_report_counts": {
                "pilot_reports": int(pilot_reports.get("total_reports", 0) or 0),
                "audit_recent_events": int(audit.get("event_count", 0) or 0),
                "v4_evidence_reports": int(v4_evidence.get("total_json_report_count", 0) or 0),
                "production_pilot_bootstrap_reports": int(
                    _count_json_reports(_get_production_pilot_bootstrap_report_dir()).get("json_report_count", 0) or 0
                ),
                "frontend_production_build_reports": int(
                    _count_json_reports(_get_frontend_production_build_report_dir()).get("json_report_count", 0) or 0
                ),
                "production_runtime_smoke_reports": int(
                    _count_json_reports(_get_production_runtime_smoke_report_dir()).get("json_report_count", 0) or 0
                ),
                "production_pilot_signoff_reports": int(
                    _count_json_reports(_get_production_pilot_signoff_report_dir()).get("json_report_count", 0) or 0
                ),
                "business_system_read_smoke_reports": int(
                    _count_json_reports(_get_business_system_read_smoke_report_dir()).get("json_report_count", 0) or 0
                ),
                "business_system_input_packet_reports": int(
                    _count_json_reports(_get_business_system_input_packet_report_dir()).get("json_report_count", 0) or 0
                ),
                "business_system_production_readiness_reports": int(
                    _count_json_reports(_get_business_system_production_readiness_report_dir()).get(
                        "json_report_count", 0
                    )
                    or 0
                ),
                "real_integration_staging_smoke_reports": int(
                    _count_json_reports(_get_real_integration_staging_smoke_report_dir()).get("json_report_count", 0) or 0
                ),
                "real_production_environment_checklist_reports": int(
                    _count_json_reports(_get_real_production_environment_checklist_report_dir()).get("json_report_count", 0) or 0
                ),
                "production_landing_env_check_reports": int(
                    _count_json_reports(_get_production_landing_env_check_report_dir()).get("json_report_count", 0) or 0
                ),
                "production_landing_env_runner_reports": int(
                    _count_json_reports(_get_production_landing_env_runner_report_dir()).get("json_report_count", 0) or 0
                ),
                "production_landing_execution_gate_reports": int(
                    _count_json_reports(_get_production_landing_execution_gate_report_dir()).get("json_report_count", 0) or 0
                ),
                "production_landing_input_readiness_reports": int(
                    _count_json_reports(_get_production_landing_input_readiness_report_dir()).get("json_report_count", 0) or 0
                ),
                "production_landing_action_pack_reports": int(
                    _count_json_reports(_get_production_landing_action_pack_report_dir()).get("json_report_count", 0) or 0
                ),
                "production_landing_blocker_resolution_reports": int(
                    _count_json_reports(_get_production_landing_blocker_resolution_report_dir()).get(
                        "json_report_count", 0
                    )
                    or 0
                ),
                "production_landing_final_verification_reports": int(
                    _count_json_reports(_get_production_landing_final_verification_report_dir()).get(
                        "json_report_count", 0
                    )
                    or 0
                ),
                "production_pilot_evidence_bundle_reports": int(
                    _count_json_reports(_get_production_pilot_evidence_bundle_report_dir()).get(
                        "json_report_count", 0
                    )
                    or 0
                ),
                "controlled_pilot_launch_gate_reports": int(
                    _count_json_reports(_get_controlled_pilot_launch_gate_report_dir()).get("json_report_count", 0)
                    or 0
                ),
                "controlled_pilot_launch_package_reports": int(
                    _count_json_reports(_get_controlled_pilot_launch_package_report_dir()).get("json_report_count", 0)
                    or 0
                ),
                "controlled_pilot_window_record_reports": int(
                    _count_json_reports(_get_controlled_pilot_window_record_report_dir()).get("json_report_count", 0)
                    or 0
                ),
                "controlled_pilot_window_status_reports": int(
                    _count_json_reports(_get_controlled_pilot_window_status_report_dir()).get("json_report_count", 0)
                    or 0
                ),
                "controlled_pilot_status_summary_reports": int(
                    _count_json_reports(_get_controlled_pilot_status_summary_report_dir()).get("json_report_count", 0)
                    or 0
                ),
                "controlled_pilot_operator_packet_reports": int(
                    _count_json_reports(_get_controlled_pilot_operator_packet_report_dir()).get("json_report_count", 0)
                    or 0
                ),
                "controlled_pilot_console_preflight_reports": int(
                    _count_json_reports(_get_controlled_pilot_console_preflight_report_dir()).get("json_report_count", 0)
                    or 0
                ),
                "controlled_pilot_console_verify_reports": int(
                    _count_json_reports(_get_controlled_pilot_console_verify_report_dir()).get("json_report_count", 0)
                    or 0
                ),
                "production_landing_xiaomi_llm_preflight_reports": int(
                    _count_json_reports(_get_production_landing_xiaomi_llm_preflight_report_dir()).get("json_report_count", 0) or 0
                ),
                "operations_console_landing_smoke_reports": int(
                    _count_json_reports(_get_operations_console_landing_smoke_report_dir()).get("json_report_count", 0)
                    or 0
                ),
                "production_landing_status_reports": int(
                    _count_json_reports(_get_production_landing_status_report_dir()).get("json_report_count", 0) or 0
                ),
                "manual_signoff_evidence_ack_status_reports": int(
                    _count_json_reports(_get_manual_signoff_evidence_ack_status_report_dir()).get(
                        "json_report_count", 0
                    )
                    or 0
                ),
                "manual_signoff_record_validation_reports": int(
                    _count_json_reports(_get_manual_signoff_record_validation_report_dir()).get(
                        "json_report_count", 0
                    )
                    or 0
                ),
                "manual_signoff_record_fill_reports": int(
                    _count_json_reports(_get_manual_signoff_record_fill_report_dir()).get("json_report_count", 0)
                    or 0
                ),
                "production_landing_signoff_closeout_reports": int(
                    _count_json_reports(_get_production_landing_signoff_closeout_report_dir()).get(
                        "json_report_count", 0
                    )
                    or 0
                ),
                "production_landing_pre_signoff_gate_reports": int(
                    _count_json_reports(_get_production_landing_pre_signoff_gate_report_dir()).get(
                        "json_report_count", 0
                    )
                    or 0
                ),
                "production_landing_signoff_reviewer_packet_reports": int(
                    _count_json_reports(_get_production_landing_signoff_reviewer_packet_report_dir()).get(
                        "json_report_count", 0
                    )
                    or 0
                ),
                "manual_signoff_record_promote_reports": int(
                    _count_json_reports(_get_manual_signoff_record_promote_report_dir()).get(
                        "json_report_count", 0
                    )
                    or 0
                ),
                "production_landing_text_quality_reports": int(
                    _count_json_reports(_get_production_landing_text_quality_report_dir()).get(
                        "json_report_count", 0
                    )
                    or 0
                ),
                "production_landing_evidence_freshness_reports": int(
                    _count_json_reports(_get_production_landing_evidence_freshness_report_dir()).get(
                        "json_report_count", 0
                    )
                    or 0
                ),
            },
        },
        "demo_evidence": {
            "mode": "fake_offline_default",
            "runbook_path": "docs/demo_e2e_runbook_v31.md",
            "script_path": "scripts/demo_e2e.ps1",
            "tip": "Use demo_e2e script for offline evidence generation. If service is unavailable, online checks are skipped without false success.",
        },
    }
