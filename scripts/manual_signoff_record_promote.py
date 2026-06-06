from __future__ import annotations

import argparse
import json
import shutil
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
    DEFAULT_FILLED_SIGNOFF_RECORD,
    _contains_secret_like,
    _latest_json,
    _read_json,
    _redact,
    _validate_ack_status,
    _validate_record,
)

DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "manual_signoff_record_promote"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8").strip()
    except Exception:
        return ""


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Manual signoff record promote",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- source_record: {payload.get('source_record', '')}",
        f"- target_record: {payload.get('target_record', '')}",
        f"- promoted: {payload.get('promoted', False)}",
        f"- public_production_direct_launch: {payload.get('public_production_direct_launch', 'No-Go')}",
        "",
        "## Missing conditions",
    ]
    missing = payload.get("missing_conditions", [])
    lines.extend(f"- {item}" for item in missing) if missing else lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def build_manual_signoff_record_promote(
    *,
    source_record: str | Path | None = None,
    target_record: str | Path | None = None,
    ack_status_report: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)
    source_path = Path(source_record) if source_record else DEFAULT_DRAFT_SIGNOFF_RECORD
    target_path = Path(target_record) if target_record else DEFAULT_FILLED_SIGNOFF_RECORD
    ack_path = Path(ack_status_report) if ack_status_report else _latest_json(
        DEFAULT_ACK_STATUS_DIR,
        "*_manual_signoff_evidence_ack_status.json",
    )

    record, record_errors = _read_json(source_path)
    ack_payload, ack_errors = _read_json(ack_path) if ack_path else ({}, ["manual_signoff_evidence_ack_status:not_found"])
    missing = [*record_errors, *ack_errors]
    if record:
        missing.extend(_validate_record(record))
    if ack_payload:
        missing.extend(_validate_ack_status(ack_payload))
    if _contains_secret_like(record) or _contains_secret_like(ack_payload):
        missing.append("manual_signoff_record_promote:secret_like_value_detected")
    if target_path.resolve() == source_path.resolve():
        missing.append("manual_signoff_record_promote:source_target_must_differ")

    blocked = any("secret_like_value_detected" in item for item in missing)
    promoted = False
    if not missing:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = target_path.with_suffix(target_path.suffix + ".tmp")
        temp_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        shutil.move(str(temp_path), str(target_path))
        promoted = True

    status = "blocked" if blocked else ("success" if promoted else "partial")
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.8.3",
        "phase": "v4.8 Manual Signoff Record Promote",
        "status": status,
        "mode": "validated_promote_only",
        "read_only_until_valid": True,
        "source_record": str(source_path),
        "target_record": str(target_path),
        "ack_status_report": str(ack_path or ""),
        "source_record_present": bool(record),
        "target_record_written": promoted,
        "promoted": promoted,
        "manual_signoff_completed": record.get("manual_signoff_completed") is True if record else False,
        "decision": _redact(str(record.get("decision") or "")) if record else "",
        "missing_conditions": sorted(set(str(item) for item in missing)),
        "missing_condition_count": len(set(str(item) for item in missing)),
        "secret_plaintext_output": False,
        "auto_approved": False,
        "auto_closed": False,
        "public_production_direct_launch": "No-Go",
    }
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_manual_signoff_record_promote"
    json_path = output_root / f"{stem}.json"
    markdown_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")
    return {
        "status": status,
        "generated_at": generated_at,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "source_record": str(source_path),
        "target_record": str(target_path),
        "promoted": promoted,
        "missing_condition_count": payload["missing_condition_count"],
        "secret_plaintext_output": False,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Promote a completed manual signoff draft into the formal record.")
    parser.add_argument("--source-record", default=str(DEFAULT_DRAFT_SIGNOFF_RECORD))
    parser.add_argument("--target-record", default=str(DEFAULT_FILLED_SIGNOFF_RECORD))
    parser.add_argument("--ack-status-report", default=None)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_manual_signoff_record_promote(
        source_record=args.source_record,
        target_record=args.target_record,
        ack_status_report=args.ack_status_report,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0 if summary["status"] in {"success", "partial", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
