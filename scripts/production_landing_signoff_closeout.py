from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
root_path = str(ROOT_DIR)
if root_path in sys.path:
    sys.path.remove(root_path)
sys.path.insert(0, root_path)

from scripts.manual_signoff_record_fill import build_manual_signoff_record_fill
from scripts.manual_signoff_record_promote import build_manual_signoff_record_promote
from scripts.manual_signoff_record_validator import (
    DEFAULT_DRAFT_SIGNOFF_RECORD,
    DEFAULT_FILLED_SIGNOFF_RECORD,
    _contains_secret_like,
    _redact,
)
from scripts.production_landing_blocker_resolution import build_production_landing_blocker_resolution
from scripts.production_landing_final_verification import build_production_landing_final_verification
from scripts.production_landing_refresh_status import build_production_landing_refresh_status
from scripts.production_landing_status import build_production_landing_status

DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "production_landing_signoff_closeout"
DEFAULT_CLOSURE_EVIDENCE = ROOT_DIR / "docs" / "reports" / "launch_blocker_closure" / "closure_evidence.draft.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8").strip()
    except Exception:
        return ""


def _step_summary(step_id: str, summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "step_id": step_id,
        "status": str(summary.get("status") or ""),
        "json_path": str(summary.get("json_path") or ""),
        "markdown_path": str(summary.get("markdown_path") or ""),
        "secret_plaintext_output": bool(summary.get("secret_plaintext_output", False)),
    }


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Production landing signoff closeout",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- final_status: {payload.get('final_status', '')}",
        f"- public_production_direct_launch: {payload.get('public_production_direct_launch', 'No-Go')}",
        "",
        "## Steps",
    ]
    for step in payload.get("steps", []):
        lines.append(f"- {step.get('step_id')}: {step.get('status')} | {step.get('json_path')}")
    lines.extend(["", "## Missing conditions"])
    missing = payload.get("missing_conditions", [])
    lines.extend(f"- {item}" for item in missing) if missing else lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def _required_input_missing(
    *,
    release_manager: str,
    security_reviewer: str,
    business_owner: str,
    operations_owner: str,
    confirm_manual_signoff: bool,
    confirm_controlled_pilot_go: bool,
) -> list[str]:
    missing: list[str] = []
    for role, value in {
        "release_manager": release_manager,
        "security_reviewer": security_reviewer,
        "business_owner": business_owner,
        "operations_owner": operations_owner,
    }.items():
        if not value.strip():
            missing.append(f"production_landing_signoff_closeout:{role}_required")
    if not confirm_manual_signoff:
        missing.append("production_landing_signoff_closeout:confirm_manual_signoff_required")
    if not confirm_controlled_pilot_go:
        missing.append("production_landing_signoff_closeout:confirm_controlled_pilot_go_required")
    return missing


def build_production_landing_signoff_closeout(
    *,
    output_dir: str | Path | None = None,
    signoff_record: str | Path | None = None,
    target_record: str | Path | None = None,
    ack_status_report: str | Path | None = None,
    closure_evidence: str | Path | None = None,
    release_manager: str,
    security_reviewer: str,
    business_owner: str,
    operations_owner: str,
    confirm_manual_signoff: bool = False,
    confirm_controlled_pilot_go: bool = False,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)
    source_path = Path(signoff_record) if signoff_record else DEFAULT_DRAFT_SIGNOFF_RECORD
    target_path = Path(target_record) if target_record else DEFAULT_FILLED_SIGNOFF_RECORD
    ack_path = Path(ack_status_report) if ack_status_report else None
    closure_path = Path(closure_evidence) if closure_evidence else DEFAULT_CLOSURE_EVIDENCE
    role_values = {
        "release_manager": release_manager,
        "security_reviewer": security_reviewer,
        "business_owner": business_owner,
        "operations_owner": operations_owner,
    }

    steps: list[dict[str, Any]] = []
    missing = _required_input_missing(
        release_manager=release_manager,
        security_reviewer=security_reviewer,
        business_owner=business_owner,
        operations_owner=operations_owner,
        confirm_manual_signoff=confirm_manual_signoff,
        confirm_controlled_pilot_go=confirm_controlled_pilot_go,
    )
    if _contains_secret_like(role_values):
        missing.append("production_landing_signoff_closeout:secret_like_value_detected")

    final_summary: dict[str, Any] = {}
    promoted = False
    if not missing:
        fill = build_manual_signoff_record_fill(
            signoff_record=source_path,
            ack_status_report=ack_path,
            release_manager=release_manager,
            security_reviewer=security_reviewer,
            business_owner=business_owner,
            operations_owner=operations_owner,
            confirm_manual_signoff=True,
            confirm_controlled_pilot_go=True,
        )
        steps.append(_step_summary("manual_signoff_record_fill", fill))
        if fill.get("status") != "success" or fill.get("filled") is not True:
            missing.append("manual_signoff_record_fill:not_success")

    if not missing:
        promote = build_manual_signoff_record_promote(
            source_record=source_path,
            target_record=target_path,
            ack_status_report=ack_path,
        )
        steps.append(_step_summary("manual_signoff_record_promote", promote))
        promoted = promote.get("status") == "success" and promote.get("promoted") is True
        if not promoted:
            missing.append("manual_signoff_record_promote:not_success")

    if not missing:
        blocker = build_production_landing_blocker_resolution()
        steps.append(_step_summary("production_landing_blocker_resolution", blocker))
        refresh = build_production_landing_refresh_status(closure_evidence=closure_path)
        steps.append(_step_summary("production_landing_refresh_status", refresh))
        status = build_production_landing_status()
        steps.append(_step_summary("production_landing_status", status))
        final_summary = build_production_landing_final_verification()
        steps.append(_step_summary("production_landing_final_verification", final_summary))
        if final_summary.get("status") != "success":
            missing.append("production_landing_final_verification:not_success")

    blocked = any("secret_like_value_detected" in item for item in missing)
    status_text = "blocked" if blocked else ("success" if final_summary.get("status") == "success" else "partial")
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.8.8",
        "phase": "v4.8 Production Landing Signoff Closeout",
        "status": status_text,
        "mode": "explicit_manual_signoff_closeout",
        "signoff_record": str(source_path),
        "target_record": str(target_path),
        "ack_status_report": str(ack_path or ""),
        "target_record_written": promoted,
        "steps": steps,
        "final_status": str(final_summary.get("status") or ""),
        "missing_conditions": sorted(set(str(item) for item in missing)),
        "missing_condition_count": len(set(str(item) for item in missing)),
        "secret_plaintext_output": False,
        "auto_signed": False,
        "auto_approved": False,
        "auto_closed": False,
        "public_production_direct_launch": "No-Go",
    }
    safe_payload = _redact(payload)
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_production_landing_signoff_closeout"
    json_path = output_root / f"{stem}.json"
    markdown_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(safe_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(safe_payload), encoding="utf-8")
    return {
        "status": status_text,
        "generated_at": generated_at,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "final_status": payload["final_status"],
        "target_record_written": promoted,
        "missing_condition_count": payload["missing_condition_count"],
        "secret_plaintext_output": False,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Close out production landing after explicit manual signoff.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--signoff-record", default=str(DEFAULT_DRAFT_SIGNOFF_RECORD))
    parser.add_argument("--target-record", default=str(DEFAULT_FILLED_SIGNOFF_RECORD))
    parser.add_argument("--ack-status-report", default=None)
    parser.add_argument("--closure-evidence", default=str(DEFAULT_CLOSURE_EVIDENCE))
    parser.add_argument("--release-manager", required=True)
    parser.add_argument("--security-reviewer", required=True)
    parser.add_argument("--business-owner", required=True)
    parser.add_argument("--operations-owner", required=True)
    parser.add_argument("--confirm-manual-signoff", action="store_true")
    parser.add_argument("--confirm-controlled-pilot-go", action="store_true")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_production_landing_signoff_closeout(
        output_dir=args.output_dir,
        signoff_record=args.signoff_record,
        target_record=args.target_record,
        ack_status_report=args.ack_status_report,
        closure_evidence=args.closure_evidence,
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
