from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "production_landing_action_pack"
OPERATOR_RUNBOOK_PATH = "docs/production_landing_operator_runbook_v47.md"

REPORT_DIRS = {
    "production_landing_input_readiness": ROOT_DIR / "docs" / "reports" / "production_landing_input_readiness",
    "production_landing_xiaomi_llm_preflight": ROOT_DIR / "docs" / "reports" / "production_landing_xiaomi_llm_preflight",
    "production_pilot_signoff": ROOT_DIR / "docs" / "reports" / "production_pilot_signoff",
    "business_system_read_smoke": ROOT_DIR / "docs" / "reports" / "business_system_read_smoke",
    "real_integration_staging_smoke": ROOT_DIR / "docs" / "reports" / "real_integration_staging_smoke",
    "manual_signoff_package": ROOT_DIR / "docs" / "reports" / "manual_signoff_package",
    "manual_signoff_evidence_ack_status": ROOT_DIR / "docs" / "reports" / "manual_signoff_evidence_ack_status",
    "manual_signoff_record_validation": ROOT_DIR / "docs" / "reports" / "manual_signoff_record_validation",
    "production_landing_text_quality": ROOT_DIR / "docs" / "reports" / "production_landing_text_quality",
    "production_landing_final_verification": ROOT_DIR / "docs" / "reports" / "production_landing_final_verification",
    "production_landing_blocker_resolution": ROOT_DIR / "docs" / "reports" / "production_landing_blocker_resolution",
    "closure_evidence_index": ROOT_DIR / "docs" / "reports" / "closure_evidence_index",
    "launch_blocker_closure": ROOT_DIR / "docs" / "reports" / "launch_blocker_closure",
}

SOURCE_DIRS = {
    "launch_blockers": ROOT_DIR / "docs" / "reports" / "launch_blockers",
}

REPORT_GLOBS = {
    "production_landing_input_readiness": "*_production_landing_input_readiness.json",
    "production_landing_xiaomi_llm_preflight": "*_production_landing_xiaomi_llm_preflight.json",
    "production_pilot_signoff": "*_production_pilot_signoff.json",
    "business_system_read_smoke": "*_business_system_read_smoke.json",
    "real_integration_staging_smoke": "*_real_integration_staging_smoke.json",
    "manual_signoff_package": "*_manual_signoff_package.json",
    "manual_signoff_evidence_ack_status": "*_manual_signoff_evidence_ack_status.json",
    "manual_signoff_record_validation": "*_manual_signoff_record_validation.json",
    "production_landing_text_quality": "*_production_landing_text_quality.json",
    "production_landing_final_verification": "*_production_landing_final_verification.json",
    "production_landing_blocker_resolution": "*_production_landing_blocker_resolution.json",
    "closure_evidence_index": "*_closure_evidence_index.json",
    "launch_blocker_closure": "*_launch_blocker_closure_workflow.json",
    "launch_blockers": "*_launch_blocker_register.json",
}

TEMPLATE_PATHS = {
    "business_system_env_template": ROOT_DIR
    / "docs"
    / "reports"
    / "business_system_read_smoke"
    / "business_read_smoke.env.template",
    "manual_signoff_record_template": ROOT_DIR
    / "docs"
    / "reports"
    / "manual_signoff_package"
    / "manual_signoff_record.template.json",
    "manual_signoff_record": ROOT_DIR / "docs" / "reports" / "manual_signoff_package" / "manual_signoff_record.json",
    "manual_signoff_record_draft": ROOT_DIR
    / "docs"
    / "reports"
    / "manual_signoff_package"
    / "manual_signoff_record.draft.json",
    "closure_evidence_template": ROOT_DIR
    / "docs"
    / "reports"
    / "launch_blocker_closure"
    / "closure_evidence.template.json",
    "closure_evidence_draft": ROOT_DIR
    / "docs"
    / "reports"
    / "launch_blocker_closure"
    / "closure_evidence.draft.json",
    "production_landing_env_template": ROOT_DIR / "local" / "production_landing.staging.env.template",
    "production_landing_env_file": ROOT_DIR / "local" / "production_landing.staging.env",
}

SAFE_XIAOMI_LLM_PREFLIGHT_COMMAND = "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\xiaomi_llm_preflight.ps1"
SAFE_XIAOMI_LLM_RESUME_COMMAND = "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\xiaomi_llm_landing_resume.ps1"
SAFE_BUSINESS_READ_SMOKE_COMMAND = "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1"
SAFE_BUSINESS_LANDING_RESUME_COMMAND = "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_landing_resume.ps1 -UseExistingEnv"
SAFE_POSTGRES_INFRA_SMOKE_COMMAND = "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\real_integration_infra_smoke.ps1 -Domains postgres"
SAFE_REDIS_INFRA_SMOKE_COMMAND = "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\real_integration_infra_smoke.ps1 -Domains redis"
SAFE_EXTERNAL_MCP_INFRA_SMOKE_COMMAND = (
    "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\real_integration_infra_smoke.ps1 "
    "-Domains external_mcp -McpServerCommand <approved-command> "
    "-McpServerCommandAllowlist <approved-command> -McpToolAllowlist <approved-tools>"
)

REQUIRED_MANUAL_SIGNOFF_ROLES = ("release_manager", "security_reviewer", "business_owner", "operations_owner")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8").strip()
    except Exception:
        return ""


def _latest_json(directory: Path, *, pattern: str = "*.json") -> Path | None:
    if not directory.exists() or not directory.is_dir():
        return None
    files = [item for item in directory.glob(pattern) if item.is_file()]
    if not files:
        return None

    def sort_key(item: Path) -> tuple[str, float, str]:
        try:
            payload = json.loads(item.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        generated_at = str(payload.get("generated_at") or "") if isinstance(payload, dict) else ""
        return (generated_at, item.stat().st_mtime, item.name)

    return max(files, key=sort_key)


def _to_rel(path: Path | None, fallback: str) -> str:
    if path is None:
        return fallback
    try:
        return str(path.resolve().relative_to(ROOT_DIR.resolve())).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _resolved_paths(reports: dict[str, dict[str, Any]]) -> dict[str, str]:
    launch_blockers = _latest_json(SOURCE_DIRS["launch_blockers"], pattern=REPORT_GLOBS["launch_blockers"])
    closure_index = reports.get("closure_evidence_index", {}).get("latest_json_path") or ""
    closure_index_path = Path(closure_index) if closure_index else None
    return {
        "latest_launch_blockers": _to_rel(launch_blockers, "<latest-launch-blockers.json>"),
        "latest_closure_index": _to_rel(closure_index_path, "<latest-closure-index.json>"),
        "closure_evidence_draft": _to_rel(TEMPLATE_PATHS["closure_evidence_draft"], "docs/reports/launch_blocker_closure/closure_evidence.draft.json"),
        "manual_signoff_record_template": _to_rel(
            TEMPLATE_PATHS["manual_signoff_record_template"],
            "docs/reports/manual_signoff_package/manual_signoff_record.template.json",
        ),
        "manual_signoff_record": _to_rel(
            TEMPLATE_PATHS["manual_signoff_record"],
            "docs/reports/manual_signoff_package/manual_signoff_record.json",
        ),
        "manual_signoff_record_draft": _to_rel(
            TEMPLATE_PATHS["manual_signoff_record_draft"],
            "docs/reports/manual_signoff_package/manual_signoff_record.draft.json",
        ),
        "production_landing_env_template": _to_rel(
            TEMPLATE_PATHS["production_landing_env_template"],
            "local/production_landing.staging.env.template",
        ),
        "production_landing_env_file": _to_rel(
            TEMPLATE_PATHS["production_landing_env_file"],
            "local/production_landing.staging.env",
        ),
    }


def _read_latest_report(report_id: str, directory: Path) -> dict[str, Any]:
    latest = _latest_json(directory, pattern=REPORT_GLOBS.get(report_id, "*.json"))
    if latest is None:
        return {
            "report_id": report_id,
            "status": "skipped",
            "present": False,
            "latest_json_path": "",
            "summary": {},
            "missing_conditions": [f"{report_id}:report_not_found"],
        }
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            "report_id": report_id,
            "status": "blocked",
            "present": True,
            "latest_json_path": str(latest),
            "summary": {},
            "missing_conditions": [f"{report_id}:json_parse_failed"],
        }
    missing = payload.get("missing_conditions") if isinstance(payload.get("missing_conditions"), list) else []
    landing = payload.get("landing_status") if isinstance(payload.get("landing_status"), dict) else {}
    preflight_summary = payload.get("preflight_summary") if isinstance(payload.get("preflight_summary"), dict) else {}
    if report_id == "manual_signoff_evidence_ack_status":
        return {
            "report_id": report_id,
            "status": str(payload.get("status") or "skipped"),
            "present": True,
            "latest_json_path": str(latest),
            "summary": {
                "generated_at": payload.get("generated_at"),
                "recommended_accept_count": payload.get("recommended_accept_count"),
                "item_count": payload.get("item_count"),
                "blocked_item_count": payload.get("blocked_item_count"),
                "items": payload.get("items") if isinstance(payload.get("items"), list) else [],
            },
            "missing_conditions": [str(item) for item in missing],
        }
    return {
        "report_id": report_id,
        "status": str(payload.get("status") or "skipped"),
        "present": True,
        "latest_json_path": str(latest),
        "summary": {
            "generated_at": payload.get("generated_at"),
            "business_read_executed": payload.get("business_read_executed") is True,
            "business_system_connected": payload.get("business_system_connected") is True,
            "manual_signoff_completed": payload.get("manual_signoff_completed") is True,
            "manual_signoff_record_present": payload.get("manual_signoff_record_present") is True,
            "manual_signoff_package_status": payload.get("manual_signoff_package_status"),
            "real_infra_ready": landing.get("real_infra_ready") is True,
            "database_connected": landing.get("database_connected") is True,
            "redis_connected": landing.get("redis_connected") is True,
            "external_mcp_connected": landing.get("external_mcp_connected") is True,
            "production_blockers": landing.get("production_blockers") if isinstance(landing.get("production_blockers"), list) else [],
            "preflight_summary": preflight_summary,
            "closure_item_count": payload.get("closure_item_count"),
            "review_ready_count": payload.get("review_ready_count"),
            "evidence_incomplete_count": payload.get("evidence_incomplete_count"),
            "report_count": payload.get("report_count"),
            "api_key_present": payload.get("api_key_present") is True,
            "network_check_requested": payload.get("execute_network_check") is True
            or (
                payload.get("preflight", {}).get("network_check_requested") is True
                if isinstance(payload.get("preflight"), dict)
                else False
            ),
            "network_check_allowed": payload.get("preflight", {}).get("network_check_allowed") is True
            if isinstance(payload.get("preflight"), dict)
            else False,
            "network_check_executed": payload.get("preflight", {}).get("network_check_executed") is True
            if isinstance(payload.get("preflight"), dict)
            else False,
            "real_llm_executed": payload.get("real_llm_executed") is True,
            "safe_next_action": str(payload.get("safe_next_action") or ""),
            "acceptance_blockers": [
                str(item)
                for item in (payload.get("acceptance_blockers") if isinstance(payload.get("acceptance_blockers"), list) else [])
            ],
        },
        "missing_conditions": [str(item) for item in missing],
    }


def _template_status() -> dict[str, dict[str, Any]]:
    return {
        key: {
            "path": str(path),
            "exists": path.exists(),
            "size_bytes": path.stat().st_size if path.exists() else 0,
        }
        for key, path in TEMPLATE_PATHS.items()
    }


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _formal_manual_signoff_record_completed() -> bool:
    record = _read_json_file(TEMPLATE_PATHS["manual_signoff_record"])
    if not record:
        return False
    if record.get("manual_signoff_completed") is not True:
        return False
    if str(record.get("decision") or "").strip().lower() != "go":
        return False
    if str(record.get("public_production_direct_launch") or "").strip().lower() != "no-go":
        return False
    if record.get("auto_signed") is True or record.get("auto_approved") is True or record.get("auto_closed") is True:
        return False

    roles = record.get("roles") if isinstance(record.get("roles"), list) else []
    role_by_id = {str(item.get("role") or ""): item for item in roles if isinstance(item, dict)}
    for role in REQUIRED_MANUAL_SIGNOFF_ROLES:
        item = role_by_id.get(role)
        if not item or not str(item.get("name") or "").strip() or item.get("approved") is not True:
            return False
    return True


def _manual_signoff_completed(reports: dict[str, dict[str, Any]]) -> bool:
    validation = reports.get("manual_signoff_record_validation", {})
    validation_summary = validation.get("summary") if isinstance(validation.get("summary"), dict) else {}
    validation_completed = (
        validation.get("status") == "success"
        and validation_summary.get("manual_signoff_completed") is True
        and not validation.get("missing_conditions")
    )
    if validation_completed or _formal_manual_signoff_record_completed():
        return True

    manual = reports.get("manual_signoff_package", {}).get("summary", {})
    signoff = reports.get("production_pilot_signoff", {}).get("summary", {})
    return bool(
        isinstance(manual, dict)
        and isinstance(signoff, dict)
        and manual.get("manual_signoff_completed")
        and signoff.get("manual_signoff_completed")
    )


def _build_required_inputs(reports: dict[str, dict[str, Any]], paths: dict[str, str]) -> list[dict[str, Any]]:
    signoff = reports["production_pilot_signoff"]["summary"]
    business = reports["business_system_read_smoke"]["summary"]
    staging_smoke = reports["real_integration_staging_smoke"]["summary"]
    xiaomi_preflight_report = reports.get("production_landing_xiaomi_llm_preflight", {})
    xiaomi_preflight = xiaomi_preflight_report.get("summary") if isinstance(xiaomi_preflight_report.get("summary"), dict) else {}
    manual = reports["manual_signoff_package"]["summary"]
    closure = reports["launch_blocker_closure"]["summary"]
    inputs: list[dict[str, Any]] = []
    if not business.get("business_read_executed"):
        inputs.append(
            {
                "input_id": "business_system_read_only_credentials",
                "status": "required",
                "template": str(TEMPLATE_PATHS["business_system_env_template"]),
                "must_not_commit": True,
                "command_after_fill": SAFE_BUSINESS_READ_SMOKE_COMMAND,
                "required_env": [
                    "BUSINESS_INTEGRATION_ENABLED=true",
                    "BUSINESS_INTEGRATION_READ_ONLY=true",
                    "BUSINESS_INTEGRATION_WRITE_ENABLED=false",
                    "BUSINESS_INTEGRATION_APPROVAL_REQUIRED=true",
                    "BUSINESS_INTEGRATION_AUDIT_REQUIRED=true",
                    "BUSINESS_SYSTEM_BASE_URL=<secret-managed-url>",
                    "BUSINESS_SYSTEM_TOKEN=<secret-managed-token>",
                    "BUSINESS_SYSTEM_TOOL_ALLOWLIST=business_read_probe",
                    "BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST=",
                    "BUSINESS_SYSTEM_AUTH_HEADER_NAME=Authorization",
                    "BUSINESS_SYSTEM_AUTH_SCHEME=Bearer",
                    "BUSINESS_SYSTEM_BUSINESS_OWNER=<owner-or-staff-id>",
                    "BUSINESS_SYSTEM_SECURITY_REVIEWER=<owner-or-staff-id>",
                    "BUSINESS_SYSTEM_OPERATIONS_OWNER=<owner-or-staff-id>",
                    "BUSINESS_SYSTEM_DATA_OWNER=<owner-or-staff-id>",
                ],
            }
        )
    if int(closure.get("evidence_incomplete_count") or 0) > 0:
        inputs.append(
            {
                "input_id": "launch_blocker_closure_evidence",
                "status": "required",
                "template": str(TEMPLATE_PATHS["closure_evidence_template"]),
                "draft": str(TEMPLATE_PATHS["closure_evidence_draft"]),
                "must_not_commit_secrets": True,
                "command_after_fill": f"python scripts/launch_blocker_closure_workflow.py --launch-blockers {paths['latest_launch_blockers']} --closure-evidence {paths['closure_evidence_draft']}",
            }
        )
    elif not reports["launch_blocker_closure"].get("present"):
        inputs.append(
            {
                "input_id": "launch_blocker_closure_evidence",
                "status": "required",
                "template": str(TEMPLATE_PATHS["closure_evidence_template"]),
                "draft": str(TEMPLATE_PATHS["closure_evidence_draft"]),
                "must_not_commit_secrets": True,
                "command_after_fill": f"python scripts/launch_blocker_closure_workflow.py --launch-blockers {paths['latest_launch_blockers']} --closure-evidence {paths['closure_evidence_draft']}",
            }
        )
    if not signoff.get("real_infra_ready"):
        production_blockers = signoff.get("production_blockers") if isinstance(signoff.get("production_blockers"), list) else []
        preflight_summary = staging_smoke.get("preflight_summary") if isinstance(staging_smoke.get("preflight_summary"), dict) else {}
        preflight_domains = preflight_summary.get("domains") if isinstance(preflight_summary.get("domains"), list) else []
        inputs.append(
            {
                "input_id": "real_infra_current_round_acceptance",
                "status": "required",
                "template": paths["production_landing_env_template"],
                "local_env_path": paths["production_landing_env_file"],
                "draft": "Set REAL_INTEGRATION_STAGING_SMOKE_ENABLED=true plus POSTGRES_STAGING_SMOKE_EXECUTE=true, REDIS_STAGING_SMOKE_EXECUTE=true, MCP_STAGING_SMOKE_EXECUTE=true in local env only.",
                "required_domains": "postgres,redis,external_mcp",
                "required_env": [
                    "REAL_INTEGRATION_STAGING_SMOKE_ENABLED=true",
                    "REAL_LLM_STAGING_SMOKE_EXECUTE=true",
                    "REAL_LLM_ACCEPTANCE_ENABLED=true",
                    "REAL_LLM_PREFLIGHT_ENABLED=true",
                    "REAL_LLM_SMOKE_ENABLED=true",
                    "REAL_LLM_PREFLIGHT_NETWORK_CHECK=true",
                    "REAL_LLM_PROVIDER=litellm",
                    "REAL_LLM_MODEL=mimo-v2.5-pro",
                    "REAL_LLM_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1",
                    "REAL_LLM_API_KEY_ENV=XIAOMI_LLM_API_KEY",
                    "XIAOMI_LLM_API_KEY=<secret-managed-token>",
                    "POSTGRES_STAGING_SMOKE_EXECUTE=true",
                    "REDIS_STAGING_SMOKE_EXECUTE=true",
                    "MCP_STAGING_SMOKE_EXECUTE=true",
                    "STORAGE_BACKEND=postgres",
                    "DATABASE_URL=<secret-managed-url>",
                    "REDIS_ENABLED=true",
                    "REDIS_URL=<secret-managed-url>",
                    "RATE_LIMIT_BACKEND=redis",
                    "MCP_MODE=real",
                    "MCP_SERVER_COMMAND=<approved-command>",
                    "MCP_SERVER_COMMAND_ALLOWLIST=<approved-command>",
                    "MCP_TOOL_ALLOWLIST=<approved-tools>",
                ],
                "current_blockers": [str(item) for item in production_blockers if str(item).startswith("real_infra:")],
                "preflight_summary": preflight_summary,
                "preflight_domains": preflight_domains,
                "must_use_current_round_evidence": True,
                "process_env_only_llm_preflight_command": SAFE_XIAOMI_LLM_PREFLIGHT_COMMAND,
                "xiaomi_llm_preflight": xiaomi_preflight,
                "xiaomi_llm_acceptance_blockers": xiaomi_preflight.get("acceptance_blockers", [])
                if isinstance(xiaomi_preflight.get("acceptance_blockers"), list)
                else [],
                "xiaomi_llm_safe_next_action": str(xiaomi_preflight.get("safe_next_action") or ""),
                "command_after_fill": " ; ".join(
                    [
                        SAFE_XIAOMI_LLM_PREFLIGHT_COMMAND,
                        SAFE_POSTGRES_INFRA_SMOKE_COMMAND,
                        SAFE_REDIS_INFRA_SMOKE_COMMAND,
                        SAFE_EXTERNAL_MCP_INFRA_SMOKE_COMMAND,
                    ]
                ),
            }
        )
    if not _manual_signoff_completed(reports):
        ack_report = reports.get("manual_signoff_evidence_ack_status", {})
        ack_summary = ack_report.get("summary") if isinstance(ack_report.get("summary"), dict) else {}
        ack_items = ack_summary.get("items") if isinstance(ack_summary.get("items"), list) else []
        blocking_ack_items = [
            {
                "item": str(item.get("item") or ""),
                "source_status": str(item.get("source_status") or ""),
                "missing_conditions": [
                    str(condition)
                    for condition in item.get("missing_conditions", [])
                    if isinstance(condition, (str, int, float))
                ],
                "acceptance_blockers": xiaomi_preflight.get("acceptance_blockers", [])
                if str(item.get("item") or "") == "real_llm_preflight"
                and isinstance(xiaomi_preflight.get("acceptance_blockers"), list)
                else [],
                "safe_next_action": str(xiaomi_preflight.get("safe_next_action") or "")
                if str(item.get("item") or "") == "real_llm_preflight"
                else "",
                "safe_commands": [
                    SAFE_XIAOMI_LLM_RESUME_COMMAND,
                    "python scripts/manual_signoff_evidence_ack_status.py",
                    "python scripts/production_landing_action_pack.py",
                ]
                if str(item.get("item") or "") == "real_llm_preflight"
                else [],
            }
            for item in ack_items
            if isinstance(item, dict) and item.get("recommended_accept") is not True
        ]
        inputs.append(
            {
                "input_id": "manual_signoff_record",
                "status": "required",
                "template": str(TEMPLATE_PATHS["manual_signoff_record_template"]),
                "filled_record": str(TEMPLATE_PATHS["manual_signoff_record"]),
                "draft": str(TEMPLATE_PATHS["manual_signoff_record_draft"]),
                "must_keep_public_production_direct_launch": "No-Go",
                "evidence_ack_status": ack_summary,
                "evidence_ack_report": ack_report.get("latest_json_path", ""),
                "blocking_evidence_items": blocking_ack_items,
                "promote_command_after_manual_fill": (
                    f"python scripts/manual_signoff_record_promote.py "
                    f"--source-record {paths['manual_signoff_record_draft']} "
                    f"--target-record {paths['manual_signoff_record']}"
                ),
                "command_after_fill": (
                    f"python scripts/manual_signoff_package.py --closure-index {paths['latest_closure_index']} "
                    f"--signoff-record {paths['manual_signoff_record']}"
                ),
            }
        )
    return inputs


def _build_commands(paths: dict[str, str]) -> list[str]:
    return [
        "python scripts/production_landing_status.py",
        "python scripts/production_landing_env_init.py",
        "python scripts/production_landing_local_infra_bootstrap.py",
        "python scripts/production_landing_xiaomi_llm_bootstrap.py",
        "python scripts/production_landing_env_runner.py --action xiaomi-llm-preflight",
        "python scripts/production_landing_xiaomi_llm_preflight_runner.py --execute-network-check",
        SAFE_XIAOMI_LLM_PREFLIGHT_COMMAND,
        SAFE_XIAOMI_LLM_RESUME_COMMAND,
        "python scripts/production_landing_local_mcp_bootstrap.py",
        "python scripts/production_landing_local_business_bootstrap.py",
        "python scripts/production_landing_env_template.py",
        "python scripts/production_landing_env_check.py",
        "python scripts/production_landing_execution_gate.py",
        "python scripts/production_landing_env_runner.py --action env-check",
        "python scripts/production_landing_env_runner.py --action staging-smoke",
        "python scripts/production_landing_env_runner.py --action business-smoke",
        f"python scripts/production_landing_closure_evidence_draft.py --launch-blockers {paths['latest_launch_blockers']} --output-path {paths['closure_evidence_draft']}",
        f"python scripts/production_landing_input_readiness.py --closure-evidence {paths['closure_evidence_draft']}",
        SAFE_BUSINESS_READ_SMOKE_COMMAND,
        SAFE_BUSINESS_LANDING_RESUME_COMMAND,
        SAFE_XIAOMI_LLM_PREFLIGHT_COMMAND,
        SAFE_POSTGRES_INFRA_SMOKE_COMMAND,
        SAFE_REDIS_INFRA_SMOKE_COMMAND,
        SAFE_EXTERNAL_MCP_INFRA_SMOKE_COMMAND,
        f"python scripts/launch_blocker_closure_workflow.py --launch-blockers {paths['latest_launch_blockers']} --closure-evidence {paths['closure_evidence_draft']}",
        "python scripts/closure_evidence_index.py",
        "python scripts/production_landing_text_quality_check.py",
        "python scripts/production_landing_blocker_resolution.py",
        "python scripts/production_landing_final_verification.py",
        "python scripts/production_landing_final_verification.py --strict",
        "python scripts/manual_signoff_evidence_ack_status.py",
        "python scripts/manual_signoff_record_draft.py",
        "powershell -ExecutionPolicy Bypass -File scripts/production_landing_signoff_closeout.ps1",
        "python scripts/production_landing_signoff_closeout.py --release-manager <name-or-id> --security-reviewer <name-or-id> --business-owner <name-or-id> --operations-owner <name-or-id> --confirm-manual-signoff --confirm-controlled-pilot-go",
        "powershell -ExecutionPolicy Bypass -File scripts/manual_signoff_record_fill.ps1",
        "python scripts/manual_signoff_record_fill.py --release-manager <name-or-id> --security-reviewer <name-or-id> --business-owner <name-or-id> --operations-owner <name-or-id> --confirm-manual-signoff --confirm-controlled-pilot-go",
        f"python scripts/manual_signoff_record_promote.py --source-record {paths['manual_signoff_record_draft']} --target-record {paths['manual_signoff_record']}",
        "python scripts/manual_signoff_record_validator.py",
        f"python scripts/manual_signoff_package.py --closure-index {paths['latest_closure_index']} --signoff-record {paths['manual_signoff_record']}",
        "python scripts/production_pilot_signoff_summary.py",
    ]


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 生产落地行动包",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- required_input_count: {payload.get('required_input_count', 0)}",
        f"- public_production_direct_launch: {payload.get('public_production_direct_launch', '')}",
        "",
        "## Required Inputs",
    ]
    for item in payload.get("required_inputs", []):
        lines.append(f"- {item.get('input_id')}: {item.get('template')}")
    lines.extend(["", "## Commands"])
    for command in payload.get("recommended_commands", []):
        lines.append(f"- `{command}`")
    lines.append("")
    return "\n".join(lines)


def build_production_landing_action_pack(*, output_dir: str | Path | None = None) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)
    reports = {key: _read_latest_report(key, directory) for key, directory in REPORT_DIRS.items()}
    paths = _resolved_paths(reports)
    required_inputs = _build_required_inputs(reports, paths)
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    status = "partial" if required_inputs else "success"
    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.5.7",
        "phase": "v4.5 Phase 25.9 Production Landing Action Pack",
        "status": status,
        "mode": "read_only_action_pack",
        "read_only": True,
        "reports": reports,
        "operator_runbook_path": OPERATOR_RUNBOOK_PATH,
        "resolved_paths": paths,
        "input_readiness": reports.get("production_landing_input_readiness", {}),
        "templates": _template_status(),
        "required_inputs": required_inputs,
        "required_input_count": len(required_inputs),
        "recommended_commands": _build_commands(paths),
        "public_production_direct_launch": "No-Go",
        "secret_plaintext_output": False,
        "business_data_written": False,
        "auto_approved": False,
        "auto_closed": False,
    }
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_production_landing_action_pack"
    json_path = output_root / f"{stem}.json"
    markdown_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")
    return {
        "status": status,
        "generated_at": generated_at,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "output_dir": str(output_root),
        "required_input_count": len(required_inputs),
        "public_production_direct_launch": "No-Go",
        "secret_plaintext_output": False,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成生产落地下一步行动包（只读）。")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_production_landing_action_pack(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
