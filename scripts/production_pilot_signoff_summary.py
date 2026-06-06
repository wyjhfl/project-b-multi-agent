from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "production_pilot_signoff"
STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]

SOURCE_DIRS = {
    "production_runtime_smoke": ROOT_DIR / "docs" / "reports" / "production_runtime_smoke",
    "frontend_production_build": ROOT_DIR / "docs" / "reports" / "frontend_production_build",
    "production_pilot_bootstrap": ROOT_DIR / "docs" / "reports" / "production_pilot_bootstrap",
    "real_production_environment_checklist": ROOT_DIR / "docs" / "reports" / "real_production_environment_checklist",
    "real_integration_staging_smoke": ROOT_DIR / "docs" / "reports" / "real_integration_staging_smoke",
    "business_system_read_smoke": ROOT_DIR / "docs" / "reports" / "business_system_read_smoke",
    "manual_signoff_package": ROOT_DIR / "docs" / "reports" / "manual_signoff_package",
}

REQUIRED_SIGNOFF_ROLES = ("release_manager", "security_reviewer", "business_owner", "operations_owner")

SECRET_MARKERS = (
    "sk-",
    "tp-",
    "bearer ",
    "api_key=",
    "apikey=",
    "token=",
    "password=",
    "client_secret=",
    "jwt_secret=",
    "postgresql://",
    "postgres://",
    "redis://",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        output = subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8")
        return output.strip()
    except Exception:
        return ""


def _contains_secret_like(value: Any) -> bool:
    try:
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    except TypeError:
        text = str(value)
    lowered = text.lower()
    for marker in ("sk-", "tp-", "bearer ", "postgresql://", "postgres://", "redis://"):
        if marker in lowered:
            return True
    for marker in ("api_key=", "apikey=", "token=", "password=", "client_secret=", "jwt_secret="):
        start = 0
        while True:
            index = lowered.find(marker, start)
            if index < 0:
                break
            raw_tail = text[index + len(marker) :]
            raw_value = ""
            for char in raw_tail:
                if char.isspace() or char in {",", "]", "}", "\"", "'", ";"}:
                    break
                raw_value += char
            normalized = raw_value.strip("<>").lower()
            if normalized and normalized not in {
                "secret-managed-token",
                "secret-managed-url",
                "external-secret-managed-url",
                "set-in-local-env-only",
            }:
                return True
            start = index + len(marker)
    return False


def _safe_text(value: Any) -> str:
    text = str(value or "")
    return "[redacted-secret-like-text]" if _contains_secret_like(text) else text


def _json_report_sort_key(path: Path) -> tuple[str, float, str]:
    generated_at = ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            generated_at = str(payload.get("generated_at") or "")
    except Exception:
        generated_at = ""
    return generated_at, path.stat().st_mtime, path.name


def _latest_json(directory: Path) -> Path | None:
    if not directory.exists() or not directory.is_dir():
        return None
    files = [item for item in directory.glob("*.json") if item.is_file()]
    if not files:
        return None
    return max(files, key=_json_report_sort_key)


def _preferred_frontend_build_report(directory: Path) -> Path | None:
    if not directory.exists() or not directory.is_dir():
        return None
    success: list[Path] = []
    fallback: list[Path] = []
    for item in directory.glob("*.json"):
        fallback.append(item)
        try:
            payload = json.loads(item.read_text(encoding="utf-8"))
        except Exception:
            continue
        if payload.get("status") == "success" and payload.get("build_executed") is True:
            success.append(item)
    candidates = success or fallback
    if not candidates:
        return None
    return max(candidates, key=_json_report_sort_key)


def _staging_smoke_has_infra_evidence(payload: dict[str, Any]) -> bool:
    return (
        payload.get("status") in {"success", "partial"}
        and payload.get("secret_plaintext_output") is False
        and (
            payload.get("database_connected") is True
            or payload.get("redis_connected") is True
            or payload.get("external_mcp_connected") is True
        )
        and payload.get("migration_executed") is not True
        and payload.get("business_data_written") is not True
    )


def _iter_json_reports(directory: Path) -> list[Path]:
    if not directory.exists() or not directory.is_dir():
        return []
    return sorted(
        (item for item in directory.glob("*.json") if item.is_file()),
        key=_json_report_sort_key,
        reverse=True,
    )


def _preferred_staging_smoke_report(directory: Path) -> Path | None:
    reports = _iter_json_reports(directory)
    return reports[0] if reports else None


def _aggregate_staging_smoke_summary(directory: Path, current_payload: dict[str, Any]) -> dict[str, Any]:
    summary = _safe_report_summary("real_integration_staging_smoke", current_payload)
    evidence_paths: dict[str, str] = {}
    aggregated_flags = {
        "database_connected": bool(summary.get("database_connected") is True),
        "redis_connected": bool(summary.get("redis_connected") is True),
        "external_mcp_connected": bool(summary.get("external_mcp_connected") is True),
    }
    secret_report_count = 0
    unsafe_report_count = 0
    safe_report_count = 0
    for item in _iter_json_reports(directory):
        try:
            payload = json.loads(item.read_text(encoding="utf-8"))
        except Exception:
            continue
        if _contains_secret_like(payload):
            secret_report_count += 1
            continue
        if payload.get("migration_executed") is True or payload.get("business_data_written") is True:
            unsafe_report_count += 1
            continue
        if payload.get("status") not in {"success", "partial"} or payload.get("secret_plaintext_output") is not False:
            continue
        safe_report_count += 1
        for flag in ("database_connected", "redis_connected", "external_mcp_connected"):
            if payload.get(flag) is True:
                aggregated_flags[flag] = True
                evidence_paths.setdefault(flag, _safe_text(item) or "")
    summary["aggregated_evidence_paths"] = evidence_paths
    summary["aggregated_infra_flags"] = aggregated_flags
    summary["aggregated_safe_report_count"] = safe_report_count
    summary["aggregated_secret_report_count"] = secret_report_count
    summary["aggregated_unsafe_report_count"] = unsafe_report_count
    return summary


def _preferred_report(source_id: str, directory: Path) -> Path | None:
    if source_id == "frontend_production_build":
        return _preferred_frontend_build_report(directory)
    if source_id == "real_integration_staging_smoke":
        return _preferred_staging_smoke_report(directory)
    return _latest_json(directory)


def _safe_report_summary(source_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if source_id == "production_runtime_smoke":
        contract = payload.get("operations_contract") if isinstance(payload.get("operations_contract"), dict) else {}
        return {
            "endpoint_check_count": len(payload.get("endpoint_checks", []) if isinstance(payload.get("endpoint_checks"), list) else []),
            "operations_contract_status": contract.get("status"),
            "frontend_build_status": contract.get("frontend_build_status"),
            "frontend_build_executed": contract.get("frontend_build_executed"),
            "business_system_connected": contract.get("business_system_connected"),
            "secret_plaintext_output": payload.get("secret_plaintext_output"),
        }
    if source_id == "frontend_production_build":
        return {
            "build_executed": payload.get("build_executed"),
            "return_code": payload.get("return_code"),
            "frontend_dir_present": payload.get("frontend_dir_present"),
            "package_json_present": payload.get("package_json_present"),
            "node_modules_present": payload.get("node_modules_present"),
            "secret_plaintext_output": payload.get("secret_plaintext_output"),
        }
    if source_id == "production_pilot_bootstrap":
        return {
            "evidence_count": payload.get("evidence_count"),
            "runtime_smoke_passed": payload.get("runtime_smoke_passed"),
            "frontend_build_passed": payload.get("frontend_build_passed"),
            "auth_rbac_acceptance_passed": payload.get("auth_rbac_acceptance_passed"),
            "business_system_connected": payload.get("business_system_connected"),
            "database_connected": payload.get("database_connected"),
            "redis_connected": payload.get("redis_connected"),
            "external_mcp_connected": payload.get("external_mcp_connected"),
            "secret_plaintext_output": payload.get("secret_plaintext_output"),
        }
    if source_id == "real_production_environment_checklist":
        return {
            "domain_count": payload.get("domain_count"),
            "real_llm_executed": payload.get("real_llm_executed"),
            "database_connected": payload.get("database_connected"),
            "redis_connected": payload.get("redis_connected"),
            "external_mcp_connected": payload.get("external_mcp_connected"),
            "secret_plaintext_output": payload.get("secret_plaintext_output"),
        }
    if source_id == "real_integration_staging_smoke":
        return {
            "domain_count": payload.get("domain_count"),
            "real_llm_executed": payload.get("real_llm_executed"),
            "database_connected": payload.get("database_connected"),
            "redis_connected": payload.get("redis_connected"),
            "external_mcp_connected": payload.get("external_mcp_connected"),
            "migration_executed": payload.get("migration_executed"),
            "business_data_written": payload.get("business_data_written"),
            "secret_plaintext_output": payload.get("secret_plaintext_output"),
        }
    if source_id == "business_system_read_smoke":
        return {
            "business_system_connected": payload.get("business_system_connected"),
            "business_read_executed": payload.get("business_read_executed"),
            "business_write_executed": payload.get("business_write_executed"),
            "business_data_written": payload.get("business_data_written"),
            "secret_plaintext_output": payload.get("secret_plaintext_output"),
        }
    if source_id == "manual_signoff_package":
        record = payload.get("manual_signoff_record") if isinstance(payload.get("manual_signoff_record"), dict) else {}
        roles = payload.get("manual_signoff_roles") if isinstance(payload.get("manual_signoff_roles"), list) else []
        blockers = payload.get("manual_signoff_blockers") if isinstance(payload.get("manual_signoff_blockers"), list) else []
        signoff_sections = payload.get("signoff_sections") if isinstance(payload.get("signoff_sections"), list) else []
        closure_section = next(
            (
                item
                for item in signoff_sections
                if isinstance(item, dict) and str(item.get("section") or "") == "closure_evidence_summary"
            ),
            {},
        )
        return {
            "manual_signoff_required": payload.get("manual_signoff_required"),
            "manual_signoff_completed": payload.get("manual_signoff_completed"),
            "manual_signoff_record_present": payload.get("manual_signoff_record_present"),
            "manual_signoff_roles": [str(item) for item in roles],
            "manual_signoff_decision": payload.get("manual_signoff_decision") or record.get("decision"),
            "manual_signoff_blockers": [str(item) for item in blockers],
            "closure_evidence_summary": {
                "latest_report": _safe_text(closure_section.get("latest_report") or ""),
                "report_count": int(closure_section.get("report_count", 0) or 0),
                "closure_item_count": int(closure_section.get("closure_item_count", 0) or 0),
                "review_ready_count": int(closure_section.get("review_ready_count", 0) or 0),
                "evidence_missing_count": int(closure_section.get("evidence_missing_count", 0) or 0),
                "evidence_incomplete_count": int(closure_section.get("evidence_incomplete_count", 0) or 0),
                "blocked_closure_count": int(closure_section.get("blocked_closure_count", 0) or 0),
            },
            "auto_signed": payload.get("auto_signed"),
            "auto_approved": payload.get("auto_approved"),
            "secret_plaintext_output": payload.get("secret_plaintext_output"),
        }
    return {"status": payload.get("status")}


def _load_report(source_id: str, directory: Path) -> dict[str, Any]:
    latest = _preferred_report(source_id, directory)
    if latest is None:
        return {
            "source_id": source_id,
            "status": "skipped",
            "present": False,
            "latest_json_path": "",
            "missing_conditions": [f"{source_id}:report_not_found"],
            "secret_detected": False,
            "summary": {},
        }
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "source_id": source_id,
            "status": "blocked",
            "present": True,
            "latest_json_path": _safe_text(latest),
            "missing_conditions": [f"{source_id}:json_parse_failed:{exc.__class__.__name__}"],
            "secret_detected": False,
            "summary": {},
        }

    secret_detected = _contains_secret_like(payload)
    status = str(payload.get("status") or "skipped")
    missing = payload.get("missing_conditions", [])
    if not isinstance(missing, list):
        missing = []
    if secret_detected:
        status = "blocked"
        missing = [*missing, f"{source_id}:secret_like_text_detected"]
    return {
        "source_id": source_id,
        "status": status if status in STATUS_VOCABULARY else "skipped",
        "present": True,
        "latest_json_path": _safe_text(latest),
        "missing_conditions": sorted({str(item) for item in missing}),
        "secret_detected": secret_detected,
        "summary": _aggregate_staging_smoke_summary(directory, payload)
        if source_id == "real_integration_staging_smoke"
        else _safe_report_summary(source_id, payload),
    }


def _build_readiness_items(sources: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    runtime = sources.get("production_runtime_smoke", {})
    frontend = sources.get("frontend_production_build", {})
    bootstrap = sources.get("production_pilot_bootstrap", {})
    checklist = sources.get("real_production_environment_checklist", {})
    staging_smoke = sources.get("real_integration_staging_smoke", {})
    business = sources.get("business_system_read_smoke", {})
    manual = sources.get("manual_signoff_package", {})
    infra_flags = _combined_infra_flags(bootstrap, staging_smoke)
    infra_ready = all(infra_flags.values())
    manual_summary = manual.get("summary", {}) if isinstance(manual.get("summary"), dict) else {}
    manual_completed = manual_summary.get("manual_signoff_completed") is True
    return [
        {
            "item_id": "runtime_smoke_ready",
            "status": "success" if runtime.get("status") == "success" else "blocked",
            "required": True,
            "evidence": runtime.get("latest_json_path", ""),
            "missing_conditions": [] if runtime.get("status") == "success" else ["runtime_smoke:not_success"],
        },
        {
            "item_id": "frontend_build_ready",
            "status": "success"
            if frontend.get("status") == "success" and frontend.get("summary", {}).get("build_executed") is True
            else "blocked",
            "required": True,
            "evidence": frontend.get("latest_json_path", ""),
            "missing_conditions": []
            if frontend.get("status") == "success" and frontend.get("summary", {}).get("build_executed") is True
            else ["frontend_build:not_success_or_not_executed"],
        },
        {
            "item_id": "auth_rbac_ready",
            "status": "success" if bootstrap.get("summary", {}).get("auth_rbac_acceptance_passed") is True else "blocked",
            "required": True,
            "evidence": bootstrap.get("latest_json_path", ""),
            "missing_conditions": []
            if bootstrap.get("summary", {}).get("auth_rbac_acceptance_passed") is True
            else ["auth_rbac_acceptance:not_passed"],
        },
        {
            "item_id": "business_system_read_ready",
            "status": "success" if business.get("summary", {}).get("business_read_executed") is True else "skipped",
            "required": False,
            "evidence": business.get("latest_json_path", ""),
            "missing_conditions": []
            if business.get("summary", {}).get("business_read_executed") is True
            else ["business_system_read:not_executed"],
        },
        {
            "item_id": "real_infra_ready",
            "status": "success" if infra_ready else "skipped",
            "required": False,
            "evidence": checklist.get("latest_json_path", ""),
            "missing_conditions": [] if infra_ready else ["real_infra:postgres_redis_mcp_not_all_connected"],
        },
        {
            "item_id": "manual_signoff_ready",
            "status": "success" if manual_completed else "skipped",
            "required": False,
            "evidence": manual.get("latest_json_path", ""),
            "missing_conditions": [] if manual_completed else ["manual_signoff:not_completed"],
        },
    ]


def _derive_status(sources: dict[str, dict[str, Any]], items: list[dict[str, Any]]) -> str:
    if any(source.get("secret_detected") for source in sources.values()):
        return "blocked"
    if any(source.get("status") == "blocked" for source in sources.values()):
        return "blocked"
    required = [item for item in items if item.get("required")]
    if all(item.get("status") == "success" for item in required):
        return "partial"
    return "skipped"


def _combined_infra_flags(bootstrap: dict[str, Any], staging_smoke: dict[str, Any]) -> dict[str, bool]:
    bootstrap_summary = bootstrap.get("summary", {})
    staging_summary = staging_smoke.get("summary", {})
    return {
        "database_connected": bootstrap_summary.get("database_connected") is True
        or staging_summary.get("database_connected") is True,
        "redis_connected": bootstrap_summary.get("redis_connected") is True
        or staging_summary.get("redis_connected") is True,
        "external_mcp_connected": bootstrap_summary.get("external_mcp_connected") is True
        or staging_summary.get("external_mcp_connected") is True,
    }


def _build_landing_status(items: list[dict[str, Any]], sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    item_by_id = {str(item.get("item_id")): item for item in items}
    required_ids = ["runtime_smoke_ready", "frontend_build_ready", "auth_rbac_ready"]
    required_local_ready = all(item_by_id.get(item_id, {}).get("status") == "success" for item_id in required_ids)
    business_read_ready = item_by_id.get("business_system_read_ready", {}).get("status") == "success"
    real_infra_ready = item_by_id.get("real_infra_ready", {}).get("status") == "success"
    manual_signoff_ready = item_by_id.get("manual_signoff_ready", {}).get("status") == "success"
    manual_source = sources.get("manual_signoff_package", {})
    manual_summary = manual_source.get("summary", {}) if isinstance(manual_source.get("summary"), dict) else {}
    infra_flags = _combined_infra_flags(
        sources.get("production_pilot_bootstrap", {}),
        sources.get("real_integration_staging_smoke", {}),
    )
    return {
        "required_local_ready": required_local_ready,
        "runtime_smoke_ready": item_by_id.get("runtime_smoke_ready", {}).get("status") == "success",
        "frontend_build_ready": item_by_id.get("frontend_build_ready", {}).get("status") == "success",
        "auth_rbac_ready": item_by_id.get("auth_rbac_ready", {}).get("status") == "success",
        "controlled_pilot_manual_review_ready": required_local_ready,
        "business_system_read_ready": business_read_ready,
        "real_infra_ready": real_infra_ready,
        "manual_signoff_ready": manual_signoff_ready,
        "manual_signoff_record_present": manual_summary.get("manual_signoff_record_present") is True,
        "manual_signoff_package_status": str(manual_source.get("status") or "skipped"),
        "manual_signoff_roles": manual_summary.get("manual_signoff_roles", []),
        "manual_signoff_decision": str(manual_summary.get("manual_signoff_decision") or ""),
        "manual_signoff_blockers": manual_summary.get("manual_signoff_blockers", []),
        "closure_evidence_summary": manual_summary.get("closure_evidence_summary", {}),
        **infra_flags,
        "enterprise_landing_state": "controlled-pilot-manual-review" if required_local_ready else "needs-local-evidence",
        "production_blockers": [
            *([] if business_read_ready else ["business_system_read:not_executed"]),
            *([] if real_infra_ready else ["real_infra:postgres_redis_mcp_not_all_connected"]),
            *([] if manual_signoff_ready else ["manual_signoff:not_completed"]),
        ],
        "public_production_direct_launch": "No-Go",
    }


def _build_markdown(payload: dict[str, Any]) -> str:
    landing = payload.get("landing_status", {}) if isinstance(payload.get("landing_status"), dict) else {}
    lines = [
        "# 生产试点人工签核摘要",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- recommendation: {payload.get('go_no_go', {}).get('recommendation', '')}",
        f"- enterprise_landing_state: {landing.get('enterprise_landing_state', '')}",
        f"- controlled_pilot_manual_review_ready: {landing.get('controlled_pilot_manual_review_ready', False)}",
        f"- public_production_direct_launch: {payload.get('go_no_go', {}).get('public_production_direct_launch', '')}",
        f"- manual_signoff_required: {payload.get('manual_signoff_required', True)}",
        "",
        "## Readiness Items",
    ]
    for item in payload.get("readiness_items", []):
        lines.append(f"- {item.get('item_id')}: {item.get('status')}")
    lines.extend(["", "## Missing Conditions"])
    missing = payload.get("missing_conditions", [])
    if missing:
        for item in missing:
            lines.append(f"- {item}")
    else:
        lines.append("- none")
    lines.extend(["", "## Production Blockers"])
    blockers = landing.get("production_blockers", [])
    if blockers:
        for item in blockers:
            lines.append(f"- {item}")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def build_production_pilot_signoff_summary(
    *,
    output_dir: str | Path | None = None,
    source_dirs: dict[str, str | Path] | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)
    effective_dirs = {key: Path(value) for key, value in (source_dirs or SOURCE_DIRS).items()}
    sources = {source_id: _load_report(source_id, directory) for source_id, directory in effective_dirs.items()}
    readiness_items = _build_readiness_items(sources)
    landing_status = _build_landing_status(readiness_items, sources)
    status = _derive_status(sources, readiness_items)
    missing_conditions = sorted(
        {
            str(condition)
            for source in sources.values()
            for condition in source.get("missing_conditions", [])
        }
        | {
            str(condition)
            for item in readiness_items
            for condition in item.get("missing_conditions", [])
            if item.get("required") or item.get("status") != "success"
        }
    )
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    if _contains_secret_like(commit):
        commit = "redacted"
    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.5.6",
        "phase": "v4.5 Phase 25.8 Production Pilot Signoff Summary",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "mode": "read_only_signoff_summary",
        "sources": sources,
        "readiness_items": readiness_items,
        "landing_status": landing_status,
        "missing_conditions": missing_conditions,
        "manual_signoff_required": True,
        "manual_signoff_completed": bool(landing_status.get("manual_signoff_ready", False)),
        "manual_signoff_record_present": bool(landing_status.get("manual_signoff_record_present", False)),
        "manual_signoff_package_status": str(landing_status.get("manual_signoff_package_status") or "skipped"),
        "manual_signoff_roles": landing_status.get("manual_signoff_roles", []),
        "manual_signoff_decision": str(landing_status.get("manual_signoff_decision") or ""),
        "manual_signoff_blockers": landing_status.get("manual_signoff_blockers", []),
        "closure_evidence_summary": landing_status.get("closure_evidence_summary", {}),
        "auto_signed": False,
        "auto_approved": False,
        "business_data_written": False,
        "secret_plaintext_output": False,
        "go_no_go": {
            "recommendation": "No-Go" if status == "blocked" else "Manual-Review",
            "production_pilot": "Manual-Review" if status == "partial" else "Needs-Input",
            "public_production_direct_launch": "No-Go",
            "manual_signoff_required": True,
        },
        "output_dir": _safe_text(output_root),
    }
    if _contains_secret_like(payload):
        payload["status"] = "blocked"
        payload["secret_plaintext_output"] = False
        payload["go_no_go"]["recommendation"] = "No-Go"
        payload["go_no_go"]["production_pilot"] = "Needs-Input"

    short_commit = commit[:8] if commit != "unknown" else "unknown"
    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_production_pilot_signoff"
    json_path = output_root / f"{stem}.json"
    markdown_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")
    return {
        "status": payload["status"],
        "generated_at": generated_at,
        "commit": commit,
        "mode": payload["mode"],
        "manual_signoff_required": True,
        "manual_signoff_completed": bool(payload.get("manual_signoff_completed", False)),
        "auto_signed": False,
        "auto_approved": False,
        "secret_plaintext_output": False,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "output_dir": str(output_root),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成生产试点人工签核摘要。默认只读消费现有证据报告。")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_production_pilot_signoff_summary(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0 if summary["status"] in {"success", "skipped", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
