from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "controlled_pilot_delivery_gate"
DEFAULT_STATUS_DIR = ROOT_DIR / "docs" / "reports" / "production_landing_status"
DEFAULT_FINAL_VERIFICATION_DIR = ROOT_DIR / "docs" / "reports" / "production_landing_final_verification"

ACCEPTED_REMAINING_GAPS = {"business_system:real_business_system_required"}
SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"tp-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"\bk-[A-Za-z0-9_\-]{24,}"),
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
    text = str(value)
    for pattern in SECRET_TEXT_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        if len(match.groups()) >= 2:
            raw = str(match.group(2)).strip().strip(".,;\"'")
            if raw in {"<secret-managed-token>", "<secret-managed-url>", "secret-managed-token", "secret-managed-url"}:
                continue
        return True
    return False


def _redact(value: Any) -> Any:
    if isinstance(value, str):
        return "[redacted-secret-like-text]" if _contains_secret_like(value) else value
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, dict):
        return {str(_redact(key)): _redact(item) for key, item in value.items()}
    return value


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


def _read_report(path: str | Path | None, default_dir: Path, pattern: str, source_id: str) -> tuple[dict[str, Any], str, list[str]]:
    resolved = Path(path) if path else _latest_json(default_dir, pattern)
    if resolved is None:
        return {}, "", [f"{source_id}:report_not_found"]
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except Exception:
        return {}, str(resolved), [f"{source_id}:json_parse_failed"]
    if not isinstance(payload, dict):
        return {}, str(resolved), [f"{source_id}:json_object_required"]
    return payload, str(resolved), []


def _real_llm_ready(payload: dict[str, Any]) -> bool:
    real_llm = payload.get("real_llm") if isinstance(payload.get("real_llm"), dict) else {}
    return bool(
        real_llm.get("status") == "success"
        and real_llm.get("api_key_present") is True
        and real_llm.get("network_check_executed") is True
        and real_llm.get("real_llm_executed") is True
    )


def _manual_signoff_ready(payload: dict[str, Any]) -> bool:
    manual = payload.get("manual_signoff") if isinstance(payload.get("manual_signoff"), dict) else {}
    return bool(
        manual.get("completed") is True
        and manual.get("record_present") is True
        and str(manual.get("decision") or "").lower() == "go"
    )


def _business_demo_read_ready(business: dict[str, Any]) -> bool:
    return bool(
        business.get("connected") is True
        and business.get("read_executed") is True
        and business.get("write_executed") is False
        and business.get("business_data_written") is False
        and business.get("local_mock_used") is False
        and business.get("demo_system_used") is True
        and business.get("real_system_connected") is False
    )


def _derive_missing(status_payload: dict[str, Any], final_payload: dict[str, Any], source_errors: list[str]) -> list[str]:
    missing = list(source_errors)
    blockers = [str(item) for item in (status_payload.get("blockers") if isinstance(status_payload.get("blockers"), list) else [])]
    unexpected_blockers = sorted(set(blockers) - ACCEPTED_REMAINING_GAPS)
    missing.extend(f"blocker:{item}" for item in unexpected_blockers)
    if not blockers:
        missing.append("controlled_pilot:remaining_gap_not_declared")
    if not set(blockers).issubset(ACCEPTED_REMAINING_GAPS):
        missing.append("controlled_pilot:unexpected_blockers_present")
    if status_payload.get("execution_allowed") is not True:
        missing.append("execution_gate:not_allowed")
    if int(status_payload.get("ready_domain_count") or 0) < int(status_payload.get("domain_count") or 0):
        missing.append("env_check:not_all_domains_ready")
    if not _real_llm_ready(status_payload):
        missing.append("real_llm:not_ready")
    if not _manual_signoff_ready(status_payload):
        missing.append("manual_signoff:not_ready")
    business = status_payload.get("business_system") if isinstance(status_payload.get("business_system"), dict) else {}
    if not _business_demo_read_ready(business):
        missing.append("business_system:demo_read_not_ready")
    if business.get("write_executed") is True or business.get("business_data_written") is True:
        missing.append("business_system:write_or_data_mutation_detected")
    if status_payload.get("public_production_direct_launch") != "No-Go":
        missing.append("public_production_direct_launch:not_no_go")
    if status_payload.get("secret_plaintext_output") is not False:
        missing.append("production_landing_status:secret_plaintext_output")
    if final_payload and final_payload.get("secret_plaintext_output") is not False:
        missing.append("final_verification:secret_plaintext_output")
    if _contains_secret_like({"status": status_payload, "final": final_payload}):
        missing.append("controlled_pilot_delivery_gate:secret_like_text_detected")
    return sorted(set(missing))


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Controlled Pilot Delivery Gate",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- controlled_pilot_delivery_ready: {payload.get('controlled_pilot_delivery_ready', False)}",
        f"- enterprise_landing_scope: {payload.get('enterprise_landing_scope', '')}",
        f"- public_production_direct_launch: {payload.get('public_production_direct_launch', 'No-Go')}",
        "",
        "## Accepted Remaining Gaps",
    ]
    accepted = payload.get("accepted_remaining_gaps", [])
    lines.extend(f"- {item}" for item in accepted) if accepted else lines.append("- none")
    lines.extend(["", "## Missing Conditions"])
    missing = payload.get("missing_conditions", [])
    lines.extend(f"- {item}" for item in missing) if missing else lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def build_controlled_pilot_delivery_gate(
    *,
    output_dir: str | Path | None = None,
    status_report: str | Path | None = None,
    final_verification_report: str | Path | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)
    status_payload, status_path, status_errors = _read_report(
        status_report,
        DEFAULT_STATUS_DIR,
        "*_production_landing_status.json",
        "production_landing_status",
    )
    final_payload, final_path, final_errors = _read_report(
        final_verification_report,
        DEFAULT_FINAL_VERIFICATION_DIR,
        "*_production_landing_final_verification.json",
        "production_landing_final_verification",
    )
    source_errors = status_errors + ([] if final_verification_report is None and not final_path else final_errors)
    missing = _derive_missing(status_payload, final_payload, source_errors)
    blockers = [str(item) for item in (status_payload.get("blockers") if isinstance(status_payload.get("blockers"), list) else [])]
    accepted_remaining_gaps = [item for item in blockers if item in ACCEPTED_REMAINING_GAPS]
    ready = not missing and accepted_remaining_gaps == ["business_system:real_business_system_required"]
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    business = status_payload.get("business_system") if isinstance(status_payload.get("business_system"), dict) else {}
    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.9.7",
        "phase": "v4.9 Controlled Pilot Delivery Gate",
        "status": "success" if ready else ("blocked" if any(item.startswith("business_system:write") or item.startswith("blocker:") for item in missing) else "partial"),
        "mode": "read_only_controlled_pilot_delivery_gate",
        "controlled_pilot_delivery_ready": ready,
        "enterprise_landing_scope": "controlled_internal_pilot",
        "status_report": _redact(status_path),
        "final_verification_report": _redact(final_path),
        "accepted_remaining_gaps": accepted_remaining_gaps,
        "missing_conditions": missing,
        "missing_condition_count": len(missing),
        "business_system": {
            "connected": bool(business.get("connected", False)),
            "read_executed": bool(business.get("read_executed", False)),
            "write_executed": bool(business.get("write_executed", False)),
            "business_data_written": bool(business.get("business_data_written", False)),
            "local_mock_used": bool(business.get("local_mock_used", False)),
            "demo_system_used": bool(business.get("demo_system_used", False)),
            "real_system_connected": bool(business.get("real_system_connected", False)),
        },
        "real_llm_ready": _real_llm_ready(status_payload),
        "manual_signoff_ready": _manual_signoff_ready(status_payload),
        "execution_allowed": bool(status_payload.get("execution_allowed", False)),
        "ready_domain_count": int(status_payload.get("ready_domain_count") or 0),
        "domain_count": int(status_payload.get("domain_count") or 0),
        "secret_plaintext_output": False,
        "public_production_direct_launch": "No-Go",
        "auto_approved": False,
        "auto_closed": False,
    }
    if _contains_secret_like(payload):
        payload["status"] = "blocked"
        payload["controlled_pilot_delivery_ready"] = False
        payload["secret_plaintext_output"] = True
        payload["missing_conditions"] = sorted(
            set([*payload["missing_conditions"], "controlled_pilot_delivery_gate:secret_like_text_detected"])
        )
        payload["missing_condition_count"] = len(payload["missing_conditions"])
        payload = _redact(payload)

    short_commit = commit[:8] if commit != "unknown" else "unknown"
    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_controlled_pilot_delivery_gate"
    json_path = output_root / f"{stem}.json"
    markdown_path = output_root / f"{stem}.md"
    payload["json_path"] = str(json_path)
    payload["markdown_path"] = str(markdown_path)
    payload["output_dir"] = str(output_root)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")
    return {
        "status": payload["status"],
        "generated_at": generated_at,
        "controlled_pilot_delivery_ready": payload["controlled_pilot_delivery_ready"],
        "accepted_remaining_gap_count": len(payload["accepted_remaining_gaps"]),
        "missing_condition_count": payload["missing_condition_count"],
        "secret_plaintext_output": payload["secret_plaintext_output"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only controlled pilot delivery gate.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--status-report", default=None)
    parser.add_argument("--final-verification-report", default=None)
    parser.add_argument("--strict", action="store_true")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_controlled_pilot_delivery_gate(
        output_dir=args.output_dir,
        status_report=args.status_report,
        final_verification_report=args.final_verification_report,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    if args.strict and summary["status"] != "success":
        return 1
    return 0 if summary["status"] in {"success", "partial", "blocked"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
