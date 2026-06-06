from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "manual_signoff_evidence_ack_status"

REPORT_SPECS = {
    "real_llm_preflight": (
        ROOT_DIR / "docs" / "reports" / "production_landing_xiaomi_llm_preflight",
        "*_production_landing_xiaomi_llm_preflight.json",
    ),
    "postgres_redis_mcp_smoke": (
        ROOT_DIR / "docs" / "reports" / "real_integration_staging_smoke",
        "*_real_integration_staging_smoke.json",
    ),
    "business_read_smoke": (
        ROOT_DIR / "docs" / "reports" / "business_system_read_smoke",
        "*_business_system_read_smoke.json",
    ),
    "closure_evidence_review": (
        ROOT_DIR / "docs" / "reports" / "launch_blocker_closure",
        "*_launch_blocker_closure_workflow.json",
    ),
}

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"tp-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)(postgres(?:ql)?(?:\+\w+)?|redis)://[^,\s]+"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)\s*[:=]\s*([^\s,]+)"),
]
SAFE_SECRET_PLACEHOLDERS = {
    "secret-managed-token",
    "secret-managed-url",
    "external-secret-managed-url",
    "set-in-local-env-only",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8").strip()
    except Exception:
        return ""


def _contains_secret_like(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False, default=str) if isinstance(value, (dict, list)) else str(value)
    for pattern in SECRET_TEXT_PATTERNS:
        for match in pattern.finditer(text):
            if len(match.groups()) >= 2:
                candidate = str(match.group(2) or "").strip().strip("\"'<>[]{}(),.;")
                if candidate.lower() in SAFE_SECRET_PLACEHOLDERS:
                    continue
            return True
    return False


def _latest_json(directory: Path, pattern: str) -> Path | None:
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
        return generated_at, item.stat().st_mtime, item.name

    return max(files, key=sort_key)


def _read_report(item_id: str) -> tuple[Path | None, dict[str, Any], list[str]]:
    directory, pattern = REPORT_SPECS[item_id]
    latest = _latest_json(directory, pattern)
    if latest is None:
        return None, {}, [f"{item_id}:report_not_found"]
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return latest, {}, [f"{item_id}:json_parse_failed"]
    if not isinstance(payload, dict):
        return latest, {}, [f"{item_id}:json_object_required"]
    return latest, payload, []


def _evaluate_real_llm(payload: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    preflight = payload.get("preflight") if isinstance(payload.get("preflight"), dict) else {}
    if payload.get("status") != "success":
        missing.append("real_llm_preflight:status_not_success")
    if payload.get("real_llm_executed") is not True:
        missing.append("real_llm_preflight:real_llm_executed_not_true")
    if preflight.get("network_check_executed") is not True:
        missing.append("real_llm_preflight:network_check_not_executed")
    if payload.get("secret_plaintext_output") is not False:
        missing.append("real_llm_preflight:secret_plaintext_output_not_false")
    return missing


def _evaluate_infra(payload: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if payload.get("status") not in {"success", "partial"}:
        missing.append("postgres_redis_mcp_smoke:status_not_success_or_partial")
    for flag in ("database_connected", "redis_connected", "external_mcp_connected"):
        if payload.get(flag) is not True:
            missing.append(f"postgres_redis_mcp_smoke:{flag}_not_true")
    if payload.get("migration_executed") is True or payload.get("business_data_written") is True:
        missing.append("postgres_redis_mcp_smoke:unexpected_write_or_migration")
    if payload.get("secret_plaintext_output") is not False:
        missing.append("postgres_redis_mcp_smoke:secret_plaintext_output_not_false")
    return missing


def _evaluate_business(payload: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if payload.get("status") != "success":
        missing.append("business_read_smoke:status_not_success")
    if payload.get("business_system_connected") is not True:
        missing.append("business_read_smoke:business_system_connected_not_true")
    if payload.get("business_read_executed") is not True:
        missing.append("business_read_smoke:business_read_executed_not_true")
    if payload.get("business_write_executed") is True or payload.get("business_data_written") is True:
        missing.append("business_read_smoke:write_or_data_written_unexpected")
    if payload.get("secret_plaintext_output") is not False:
        missing.append("business_read_smoke:secret_plaintext_output_not_false")
    return missing


def _evaluate_closure(payload: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if payload.get("status") not in {"success", "partial"}:
        missing.append("closure_evidence_review:status_not_success_or_partial")
    if int(payload.get("closure_item_count") or 0) <= 0:
        missing.append("closure_evidence_review:closure_item_count_zero")
    if int(payload.get("review_ready_count") or 0) <= 0:
        missing.append("closure_evidence_review:review_ready_count_zero")
    if int(payload.get("evidence_incomplete_count") or 0) != 0:
        missing.append("closure_evidence_review:evidence_incomplete_count_not_zero")
    return missing


def _evaluate_item(item_id: str) -> dict[str, Any]:
    path, payload, missing = _read_report(item_id)
    secret_detected = bool(payload and _contains_secret_like(payload))
    if secret_detected:
        missing.append(f"{item_id}:secret_like_value_detected")
    if payload and not missing:
        if item_id == "real_llm_preflight":
            missing.extend(_evaluate_real_llm(payload))
        elif item_id == "postgres_redis_mcp_smoke":
            missing.extend(_evaluate_infra(payload))
        elif item_id == "business_read_smoke":
            missing.extend(_evaluate_business(payload))
        elif item_id == "closure_evidence_review":
            missing.extend(_evaluate_closure(payload))
    recommended_accept = not missing
    if item_id == "postgres_redis_mcp_smoke" and missing and not secret_detected:
        unexpected = {
            "postgres_redis_mcp_smoke:unexpected_write_or_migration",
            "postgres_redis_mcp_smoke:secret_plaintext_output_not_false",
        }
        recommended_accept = not any(condition in unexpected for condition in missing)
    if item_id == "business_read_smoke" and missing and not secret_detected:
        unexpected = {
            "business_read_smoke:write_or_data_written_unexpected",
            "business_read_smoke:secret_plaintext_output_not_false",
        }
        recommended_accept = not any(condition in unexpected for condition in missing)
    return {
        "item": item_id,
        "latest_report": str(path or ""),
        "report_present": path is not None,
        "source_status": str(payload.get("status") or "missing") if payload else "missing",
        "recommended_accept": recommended_accept,
        "missing_conditions": sorted(set(missing)),
    }


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Manual signoff evidence acknowledgement status",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- recommended_accept_count: {payload.get('recommended_accept_count', 0)}/{payload.get('item_count', 0)}",
        f"- public_production_direct_launch: {payload.get('public_production_direct_launch', 'No-Go')}",
        "",
        "## Items",
    ]
    for item in payload.get("items", []):
        lines.append(
            f"- {item.get('item')}: recommended_accept={item.get('recommended_accept')} "
            f"missing={len(item.get('missing_conditions', []))} report={item.get('latest_report', '')}"
        )
    lines.append("")
    return "\n".join(lines)


def build_manual_signoff_evidence_ack_status(*, output_dir: str | Path | None = None) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    items = [_evaluate_item(item_id) for item_id in REPORT_SPECS]
    recommended_count = sum(1 for item in items if item.get("recommended_accept") is True)
    blocked_count = sum(
        1
        for item in items
        if any("secret_like_value_detected" in condition for condition in item.get("missing_conditions", []))
    )
    status = "blocked" if blocked_count else ("success" if recommended_count == len(items) else "partial")
    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.7.5",
        "phase": "v4.7 Manual Signoff Evidence Acknowledgement Status",
        "status": status,
        "mode": "read_only_evidence_ack_status",
        "read_only": True,
        "items": items,
        "item_count": len(items),
        "recommended_accept_count": recommended_count,
        "blocked_item_count": blocked_count,
        "secret_plaintext_output": False,
        "auto_approved": False,
        "auto_closed": False,
        "public_production_direct_launch": "No-Go",
    }
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_manual_signoff_evidence_ack_status"
    json_path = output_root / f"{stem}.json"
    markdown_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")
    return {
        "status": status,
        "generated_at": generated_at,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "recommended_accept_count": recommended_count,
        "item_count": len(items),
        "secret_plaintext_output": False,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate manual signoff evidence acknowledgements without mutating signoff.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_manual_signoff_evidence_ack_status(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
