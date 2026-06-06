from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "production_landing_pre_signoff_gate"
REPORT_SOURCES = {
    "production_landing_status": (
        ROOT_DIR / "docs" / "reports" / "production_landing_status",
        "*_production_landing_status.json",
    ),
    "production_landing_final_verification": (
        ROOT_DIR / "docs" / "reports" / "production_landing_final_verification",
        "*_production_landing_final_verification.json",
    ),
    "production_landing_action_pack": (
        ROOT_DIR / "docs" / "reports" / "production_landing_action_pack",
        "*_production_landing_action_pack.json",
    ),
    "manual_signoff_evidence_ack_status": (
        ROOT_DIR / "docs" / "reports" / "manual_signoff_evidence_ack_status",
        "*_manual_signoff_evidence_ack_status.json",
    ),
    "production_landing_signoff_closeout": (
        ROOT_DIR / "docs" / "reports" / "production_landing_signoff_closeout",
        "*_production_landing_signoff_closeout.json",
    ),
}
SIGNOFF_ONLY_MISSING = {
    "action_pack:required_inputs_remaining",
    "manual_signoff:not_completed",
    "blocker:action_pack:required_inputs_remaining",
    "blocker:manual_signoff:not_completed",
    "manual_signoff_record:not_completed",
    "production_landing_signoff_closeout:confirm_controlled_pilot_go_required",
    "production_landing_signoff_closeout:confirm_manual_signoff_required",
    "production_landing_status:not_ready",
    "production_landing_status:status_not_success",
    "refresh_status:final_status_not_success",
    "refresh_status:status_not_success",
}
SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"tp-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)(postgres(?:ql)?(?:\+\w+)?|redis)://[^,\s]+"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)\s*[:=]\s*([^\s,]+)"),
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8").strip()
    except Exception:
        return ""


def _contains_secret_like(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_secret_like(key) or _contains_secret_like(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_secret_like(item) for item in value)
    return any(pattern.search(str(value)) for pattern in SECRET_TEXT_PATTERNS)


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


def _read_latest(source_id: str, directory: Path, pattern: str) -> tuple[dict[str, Any], dict[str, Any]]:
    latest = _latest_json(directory, pattern)
    if latest is None:
        return {}, {
            "source_id": source_id,
            "latest_report_present": False,
            "latest_json_path": "",
            "status": "missing",
            "missing_conditions": [f"{source_id}:report_not_found"],
        }
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {}, {
            "source_id": source_id,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
            "missing_conditions": [f"{source_id}:json_parse_failed"],
        }
    if not isinstance(payload, dict):
        return {}, {
            "source_id": source_id,
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
            "missing_conditions": [f"{source_id}:json_object_required"],
        }
    return payload, {
        "source_id": source_id,
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": str(payload.get("status") or "skipped"),
        "missing_conditions": [],
    }


def _as_list(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Production landing pre-signoff gate",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- ready_for_manual_signoff: {payload.get('ready_for_manual_signoff', False)}",
        f"- non_signoff_blocker_count: {payload.get('non_signoff_blocker_count', 0)}",
        f"- public_production_direct_launch: {payload.get('public_production_direct_launch', 'No-Go')}",
        "",
        "## Non-signoff blockers",
    ]
    blockers = payload.get("non_signoff_blockers", [])
    lines.extend(f"- {item}" for item in blockers) if blockers else lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def build_production_landing_pre_signoff_gate(
    *,
    output_dir: str | Path | None = None,
    sources: dict[str, tuple[Path, str]] | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)
    effective_sources = sources or REPORT_SOURCES
    payloads: dict[str, dict[str, Any]] = {}
    source_summaries: list[dict[str, Any]] = []
    missing: list[str] = []

    for source_id, (directory, pattern) in effective_sources.items():
        payload, summary = _read_latest(source_id, Path(directory), pattern)
        payloads[source_id] = payload
        source_summaries.append(summary)
        missing.extend(summary.get("missing_conditions", []))

    status_payload = payloads.get("production_landing_status", {})
    final_payload = payloads.get("production_landing_final_verification", {})
    action_payload = payloads.get("production_landing_action_pack", {})
    ack_payload = payloads.get("manual_signoff_evidence_ack_status", {})
    closeout_payload = payloads.get("production_landing_signoff_closeout", {})

    status_blockers = _as_list(status_payload.get("blockers"))
    final_missing = _as_list(final_payload.get("missing_conditions"))
    action_required_inputs = action_payload.get("required_input_count")
    ack_ready = (
        ack_payload.get("status") == "success"
        and int(ack_payload.get("recommended_accept_count") or 0) == int(ack_payload.get("item_count") or -1)
        and int(ack_payload.get("item_count") or 0) >= 4
    )
    closeout_missing = _as_list(closeout_payload.get("missing_conditions"))
    all_missing = sorted(set([*missing, *status_blockers, *final_missing, *closeout_missing]))
    non_signoff_blockers = sorted(item for item in all_missing if item not in SIGNOFF_ONLY_MISSING)

    technical_evidence_ready = (
        ack_ready
        and action_required_inputs == 1
        and set(status_blockers).issubset({"action_pack:required_inputs_remaining", "manual_signoff:not_completed"})
        and set(final_missing).issubset(SIGNOFF_ONLY_MISSING)
        and not non_signoff_blockers
    )
    secret_like_detected = _contains_secret_like(payloads) or _contains_secret_like(source_summaries)
    if secret_like_detected:
        non_signoff_blockers.append("pre_signoff_gate:secret_like_text_detected")
    ready = bool(technical_evidence_ready and not non_signoff_blockers and not secret_like_detected)
    status = "ready_for_manual_signoff" if ready else ("blocked" if secret_like_detected else "partial")

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    report = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.9.1",
        "phase": "v4.9 Production Landing Pre-Signoff Gate",
        "status": status,
        "mode": "read_only_pre_signoff_gate",
        "read_only": True,
        "ready_for_manual_signoff": ready,
        "technical_evidence_ready": bool(technical_evidence_ready),
        "source_summaries": source_summaries,
        "signoff_only_missing_conditions": sorted(item for item in all_missing if item in SIGNOFF_ONLY_MISSING),
        "non_signoff_blockers": sorted(set(non_signoff_blockers)),
        "non_signoff_blocker_count": len(set(non_signoff_blockers)),
        "ack_ready": ack_ready,
        "action_required_input_count": action_required_inputs,
        "status_blockers": status_blockers,
        "final_missing_conditions": final_missing,
        "closeout_missing_conditions": closeout_missing,
        "secret_plaintext_output": False,
        "auto_signed": False,
        "auto_approved": False,
        "auto_closed": False,
        "public_production_direct_launch": "No-Go",
    }
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_production_landing_pre_signoff_gate"
    json_path = output_root / f"{stem}.json"
    markdown_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(report), encoding="utf-8")
    return {
        "status": status,
        "generated_at": generated_at,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "ready_for_manual_signoff": ready,
        "non_signoff_blocker_count": report["non_signoff_blocker_count"],
        "secret_plaintext_output": False,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only gate proving whether only manual signoff remains.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_production_landing_pre_signoff_gate(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0 if summary["status"] in {"ready_for_manual_signoff", "partial", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
