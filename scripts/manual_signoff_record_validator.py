from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "manual_signoff_record_validation"
DEFAULT_SIGNOFF_RECORD_DIR = ROOT_DIR / "docs" / "reports" / "manual_signoff_package"
DEFAULT_SIGNOFF_RECORD = DEFAULT_SIGNOFF_RECORD_DIR / "manual_signoff_record.template.json"
DEFAULT_FILLED_SIGNOFF_RECORD = DEFAULT_SIGNOFF_RECORD_DIR / "manual_signoff_record.json"
DEFAULT_DRAFT_SIGNOFF_RECORD = DEFAULT_SIGNOFF_RECORD_DIR / "manual_signoff_record.draft.json"
DEFAULT_ACK_STATUS_DIR = ROOT_DIR / "docs" / "reports" / "manual_signoff_evidence_ack_status"

REQUIRED_ROLES = ("release_manager", "security_reviewer", "business_owner", "operations_owner")
REQUIRED_ACKS = (
    "real_llm_preflight",
    "postgres_redis_mcp_smoke",
    "business_read_smoke",
    "closure_evidence_review",
)

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"tp-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)(postgres(?:ql)?(?:\+\w+)?|redis)://[^,\s]+"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)\s*[:=]\s*([^\s,]+)"),
]
SAFE_PLACEHOLDERS = {"secret-managed-token", "secret-managed-url", "set-in-local-env-only"}


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
                candidate = str(match.group(2) or "").strip().strip("\"'<>").lower()
                if candidate in SAFE_PLACEHOLDERS:
                    continue
            return True
    return False


def _redact(value: Any) -> Any:
    if isinstance(value, str):
        return "[redacted-secret-like-text]" if _contains_secret_like(value) else value
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _redact(item) for key, item in value.items()}
    return value


def _read_json(path: Path) -> tuple[dict[str, Any], list[str]]:
    if not path.exists():
        return {}, [f"{path.name}:not_found"]
    if not path.is_file() or path.suffix.lower() != ".json":
        return {}, [f"{path.name}:json_file_required"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}, [f"{path.name}:json_parse_failed"]
    if not isinstance(payload, dict):
        return {}, [f"{path.name}:json_object_required"]
    return payload, []


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


def _default_signoff_record_path() -> Path:
    for path in (DEFAULT_FILLED_SIGNOFF_RECORD, DEFAULT_DRAFT_SIGNOFF_RECORD, DEFAULT_SIGNOFF_RECORD):
        if path.exists():
            return path
    return DEFAULT_SIGNOFF_RECORD


def _safe_roles(record: dict[str, Any]) -> list[dict[str, Any]]:
    roles = record.get("roles") if isinstance(record.get("roles"), list) else []
    safe: list[dict[str, Any]] = []
    for item in roles[:12]:
        if not isinstance(item, dict):
            continue
        safe.append(
            {
                "role": str(item.get("role") or ""),
                "name_present": bool(str(item.get("name") or "").strip()),
                "approved": bool(item.get("approved", False)),
            }
        )
    return safe


def _safe_acknowledgements(record: dict[str, Any]) -> list[dict[str, Any]]:
    items = record.get("evidence_acknowledgements") if isinstance(record.get("evidence_acknowledgements"), list) else []
    safe: list[dict[str, Any]] = []
    for item in items[:12]:
        if not isinstance(item, dict):
            continue
        safe.append(
            {
                "item": str(item.get("item") or ""),
                "accepted": bool(item.get("accepted", False)),
                "latest_report": _redact(str(item.get("latest_report") or "")),
                "note_present": bool(str(item.get("note") or "").strip()),
            }
        )
    return safe


def _validate_record(record: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if record.get("manual_signoff_completed") is not True:
        missing.append("manual_signoff_record:not_completed")
    if str(record.get("decision") or "").strip().lower() != "go":
        missing.append("manual_signoff_record:decision_not_go")
    if str(record.get("public_production_direct_launch") or "No-Go").strip().lower() != "no-go":
        missing.append("manual_signoff_record:public_production_direct_launch_must_remain_no_go")
    if record.get("auto_signed") is True or record.get("auto_approved") is True or record.get("auto_closed") is True:
        missing.append("manual_signoff_record:auto_flag_unexpected")

    roles = record.get("roles") if isinstance(record.get("roles"), list) else []
    role_by_id = {str(item.get("role") or ""): item for item in roles if isinstance(item, dict)}
    for role in REQUIRED_ROLES:
        item = role_by_id.get(role)
        if not item:
            missing.append(f"manual_signoff_record:{role}_missing")
            continue
        if not str(item.get("name") or "").strip():
            missing.append(f"manual_signoff_record:{role}_name_missing")
        if item.get("approved") is not True:
            missing.append(f"manual_signoff_record:{role}_not_approved")

    acknowledgements = (
        record.get("evidence_acknowledgements") if isinstance(record.get("evidence_acknowledgements"), list) else []
    )
    ack_by_id = {str(item.get("item") or ""): item for item in acknowledgements if isinstance(item, dict)}
    for ack_id in REQUIRED_ACKS:
        item = ack_by_id.get(ack_id)
        if not item:
            missing.append(f"manual_signoff_record:evidence_ack_{ack_id}_missing")
            continue
        if item.get("accepted") is not True:
            missing.append(f"manual_signoff_record:evidence_ack_{ack_id}_not_accepted")
    return missing


def _validate_ack_status(payload: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if not payload:
        return ["manual_signoff_evidence_ack_status:not_found"]
    if payload.get("status") != "success":
        missing.append("manual_signoff_evidence_ack_status:status_not_success")
    if int(payload.get("recommended_accept_count") or 0) != int(payload.get("item_count") or len(REQUIRED_ACKS)):
        missing.append("manual_signoff_evidence_ack_status:not_all_recommended_accept")
    if int(payload.get("blocked_item_count") or 0) != 0:
        missing.append("manual_signoff_evidence_ack_status:blocked_items_present")
    if payload.get("secret_plaintext_output") is not False:
        missing.append("manual_signoff_evidence_ack_status:secret_plaintext_output_not_false")
    return missing


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Manual signoff record validation",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- signoff_record_present: {payload.get('signoff_record_present', False)}",
        f"- ack_status: {payload.get('ack_status', '')}",
        f"- public_production_direct_launch: {payload.get('public_production_direct_launch', 'No-Go')}",
        "",
        "## Missing conditions",
    ]
    missing = payload.get("missing_conditions", [])
    lines.extend(f"- {item}" for item in missing) if missing else lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def build_manual_signoff_record_validation(
    *,
    signoff_record: str | Path | None = None,
    ack_status_report: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)
    record_path = Path(signoff_record) if signoff_record else _default_signoff_record_path()
    ack_path = Path(ack_status_report) if ack_status_report else _latest_json(
        DEFAULT_ACK_STATUS_DIR,
        "*_manual_signoff_evidence_ack_status.json",
    )

    record, record_errors = _read_json(record_path)
    ack_payload, ack_errors = _read_json(ack_path) if ack_path else ({}, ["manual_signoff_evidence_ack_status:not_found"])
    missing = [*record_errors, *ack_errors]
    if record:
        missing.extend(_validate_record(record))
    if ack_payload:
        missing.extend(_validate_ack_status(ack_payload))
    if _contains_secret_like(record) or _contains_secret_like(ack_payload):
        missing.append("manual_signoff_record_validation:secret_like_value_detected")

    blocked = any("secret_like_value_detected" in item for item in missing)
    status = "blocked" if blocked else ("success" if not missing else "partial")
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.7.6",
        "phase": "v4.7 Manual Signoff Record Validation",
        "status": status,
        "mode": "read_only_signoff_record_validation",
        "read_only": True,
        "signoff_record_path": str(record_path),
        "signoff_record_present": bool(record),
        "ack_status_report": str(ack_path or ""),
        "ack_status": str(ack_payload.get("status") or "missing") if ack_payload else "missing",
        "manual_signoff_completed": record.get("manual_signoff_completed") is True if record else False,
        "decision": _redact(str(record.get("decision") or "")) if record else "",
        "roles": _safe_roles(record),
        "evidence_acknowledgements": _safe_acknowledgements(record),
        "missing_conditions": sorted(set(str(item) for item in missing)),
        "missing_condition_count": len(set(str(item) for item in missing)),
        "secret_plaintext_output": False,
        "auto_approved": False,
        "auto_closed": False,
        "public_production_direct_launch": "No-Go",
    }
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_manual_signoff_record_validation"
    json_path = output_root / f"{stem}.json"
    markdown_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")
    return {
        "status": status,
        "generated_at": generated_at,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "missing_condition_count": payload["missing_condition_count"],
        "secret_plaintext_output": False,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate manual signoff record without modifying it.")
    parser.add_argument("--signoff-record", default=None)
    parser.add_argument("--ack-status-report", default=None)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_manual_signoff_record_validation(
        signoff_record=args.signoff_record,
        ack_status_report=args.ack_status_report,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0 if summary["status"] in {"success", "partial", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
