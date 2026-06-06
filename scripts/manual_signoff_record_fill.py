from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.manual_signoff_record_validator import (
    DEFAULT_ACK_STATUS_DIR,
    DEFAULT_DRAFT_SIGNOFF_RECORD,
    _contains_secret_like,
    _latest_json,
    _read_json,
    _redact,
    _validate_ack_status,
    _validate_record,
)

DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "manual_signoff_record_fill"
REQUIRED_ROLES = ("release_manager", "security_reviewer", "business_owner", "operations_owner")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8").strip()
    except Exception:
        return ""


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Manual signoff record fill",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- signoff_record: {payload.get('signoff_record', '')}",
        f"- filled: {payload.get('filled', False)}",
        f"- public_production_direct_launch: {payload.get('public_production_direct_launch', 'No-Go')}",
        "",
        "## Missing conditions",
    ]
    missing = payload.get("missing_conditions", [])
    lines.extend(f"- {item}" for item in missing) if missing else lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def _role_names(*, release_manager: str, security_reviewer: str, business_owner: str, operations_owner: str) -> dict[str, str]:
    return {
        "release_manager": release_manager.strip(),
        "security_reviewer": security_reviewer.strip(),
        "business_owner": business_owner.strip(),
        "operations_owner": operations_owner.strip(),
    }


def _fill_record(record: dict[str, Any], role_names: dict[str, str], *, signed_at: str) -> dict[str, Any]:
    filled = dict(record)
    filled["manual_signoff_completed"] = True
    filled["decision"] = "Go"
    filled["signed_at"] = signed_at
    filled["public_production_direct_launch"] = "No-Go"
    filled["auto_signed"] = False
    filled["auto_approved"] = False
    filled["auto_closed"] = False

    roles = filled.get("roles") if isinstance(filled.get("roles"), list) else []
    by_role = {str(item.get("role") or ""): dict(item) for item in roles if isinstance(item, dict)}
    next_roles: list[dict[str, Any]] = []
    for role in REQUIRED_ROLES:
        item = by_role.get(role, {"role": role})
        item["name"] = role_names[role]
        item["approved"] = True
        next_roles.append(item)
    filled["roles"] = next_roles

    acknowledgements = (
        filled.get("evidence_acknowledgements")
        if isinstance(filled.get("evidence_acknowledgements"), list)
        else []
    )
    next_acknowledgements: list[dict[str, Any]] = []
    for item in acknowledgements:
        if not isinstance(item, dict):
            continue
        ack = dict(item)
        ack["accepted"] = True
        next_acknowledgements.append(ack)
    filled["evidence_acknowledgements"] = next_acknowledgements
    return filled


def build_manual_signoff_record_fill(
    *,
    signoff_record: str | Path | None = None,
    ack_status_report: str | Path | None = None,
    output_dir: str | Path | None = None,
    release_manager: str,
    security_reviewer: str,
    business_owner: str,
    operations_owner: str,
    confirm_manual_signoff: bool = False,
    confirm_controlled_pilot_go: bool = False,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)
    record_path = Path(signoff_record) if signoff_record else DEFAULT_DRAFT_SIGNOFF_RECORD
    ack_path = Path(ack_status_report) if ack_status_report else _latest_json(
        DEFAULT_ACK_STATUS_DIR,
        "*_manual_signoff_evidence_ack_status.json",
    )

    record, record_errors = _read_json(record_path)
    ack_payload, ack_errors = _read_json(ack_path) if ack_path else ({}, ["manual_signoff_evidence_ack_status:not_found"])
    role_names = _role_names(
        release_manager=release_manager,
        security_reviewer=security_reviewer,
        business_owner=business_owner,
        operations_owner=operations_owner,
    )

    missing: list[str] = [*record_errors, *ack_errors]
    if not confirm_manual_signoff:
        missing.append("manual_signoff_record_fill:confirm_manual_signoff_required")
    if not confirm_controlled_pilot_go:
        missing.append("manual_signoff_record_fill:confirm_controlled_pilot_go_required")
    for role, name in role_names.items():
        if not name:
            missing.append(f"manual_signoff_record_fill:{role}_name_required")
    if ack_payload:
        missing.extend(_validate_ack_status(ack_payload))
    if _contains_secret_like(record) or _contains_secret_like(ack_payload) or _contains_secret_like(role_names):
        missing.append("manual_signoff_record_fill:secret_like_value_detected")

    filled_record: dict[str, Any] = {}
    filled = False
    if not missing and record:
        filled_record = _fill_record(record, role_names, signed_at=_utc_now_iso())
        validation_missing = _validate_record(filled_record)
        if validation_missing:
            missing.extend(validation_missing)
        elif _contains_secret_like(filled_record):
            missing.append("manual_signoff_record_fill:secret_like_value_detected")
        else:
            record_path.write_text(json.dumps(_redact(filled_record), ensure_ascii=False, indent=2), encoding="utf-8")
            filled = True

    blocked = any("secret_like_value_detected" in item for item in missing)
    status = "blocked" if blocked else ("success" if filled else "partial")
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.8.5",
        "phase": "v4.8 Manual Signoff Record Fill",
        "status": status,
        "mode": "explicit_manual_signoff_fill",
        "signoff_record": str(record_path),
        "ack_status_report": str(ack_path or ""),
        "filled": filled,
        "manual_signoff_completed": bool(filled_record.get("manual_signoff_completed", False)) if filled_record else False,
        "decision": _redact(str(filled_record.get("decision") or "")) if filled_record else "",
        "missing_conditions": sorted(set(str(item) for item in missing)),
        "missing_condition_count": len(set(str(item) for item in missing)),
        "secret_plaintext_output": False,
        "auto_signed": False,
        "auto_approved": False,
        "auto_closed": False,
        "public_production_direct_launch": "No-Go",
    }
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_manual_signoff_record_fill"
    json_path = output_root / f"{stem}.json"
    markdown_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")
    return {
        "status": status,
        "generated_at": generated_at,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "signoff_record": str(record_path),
        "filled": filled,
        "missing_condition_count": payload["missing_condition_count"],
        "secret_plaintext_output": False,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fill a manual signoff draft only after explicit operator confirmation.")
    parser.add_argument("--signoff-record", default=str(DEFAULT_DRAFT_SIGNOFF_RECORD))
    parser.add_argument("--ack-status-report", default=None)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--release-manager", required=True)
    parser.add_argument("--security-reviewer", required=True)
    parser.add_argument("--business-owner", required=True)
    parser.add_argument("--operations-owner", required=True)
    parser.add_argument("--confirm-manual-signoff", action="store_true")
    parser.add_argument("--confirm-controlled-pilot-go", action="store_true")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_manual_signoff_record_fill(
        signoff_record=args.signoff_record,
        ack_status_report=args.ack_status_report,
        output_dir=args.output_dir,
        release_manager=args.release_manager,
        security_reviewer=args.security_reviewer,
        business_owner=args.business_owner,
        operations_owner=args.operations_owner,
        confirm_manual_signoff=args.confirm_manual_signoff,
        confirm_controlled_pilot_go=args.confirm_controlled_pilot_go,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0 if summary["status"] in {"success", "partial", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
