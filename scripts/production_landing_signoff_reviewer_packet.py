from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "production_landing_signoff_reviewer_packet"
REPORT_SOURCES = {
    "pre_signoff_gate": (
        ROOT_DIR / "docs" / "reports" / "production_landing_pre_signoff_gate",
        "*_production_landing_pre_signoff_gate.json",
    ),
    "action_pack": (
        ROOT_DIR / "docs" / "reports" / "production_landing_action_pack",
        "*_production_landing_action_pack.json",
    ),
    "final_verification": (
        ROOT_DIR / "docs" / "reports" / "production_landing_final_verification",
        "*_production_landing_final_verification.json",
    ),
    "manual_signoff_evidence_ack_status": (
        ROOT_DIR / "docs" / "reports" / "manual_signoff_evidence_ack_status",
        "*_manual_signoff_evidence_ack_status.json",
    ),
    "xiaomi_llm_preflight": (
        ROOT_DIR / "docs" / "reports" / "production_landing_xiaomi_llm_preflight",
        "*_production_landing_xiaomi_llm_preflight.json",
    ),
    "real_integration_staging_smoke": (
        ROOT_DIR / "docs" / "reports" / "real_integration_staging_smoke",
        "*_real_integration_staging_smoke.json",
    ),
    "business_system_read_smoke": (
        ROOT_DIR / "docs" / "reports" / "business_system_read_smoke",
        "*_business_system_read_smoke.json",
    ),
    "signoff_closeout": (
        ROOT_DIR / "docs" / "reports" / "production_landing_signoff_closeout",
        "*_production_landing_signoff_closeout.json",
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
    if isinstance(value, dict):
        return any(_contains_secret_like(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_secret_like(item) for item in value)
    text = str(value)
    for pattern in SECRET_TEXT_PATTERNS:
        for match in pattern.finditer(text):
            if len(match.groups()) >= 2:
                candidate = str(match.group(2) or "").strip().strip("\"'<>").lower()
                if candidate in SAFE_SECRET_PLACEHOLDERS:
                    continue
            return True
    return False


def _redact(value: Any) -> Any:
    if isinstance(value, str):
        return "[redacted-secret-like-text]" if _contains_secret_like(value) else value
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, dict):
        return {_redact(str(key)): _redact(item) for key, item in value.items()}
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


def _read_payload(path: Path | None, source_id: str) -> tuple[dict[str, Any], list[str], str]:
    if path is None:
        return {}, [f"{source_id}:report_not_found"], ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}, [f"{source_id}:json_parse_failed"], str(path)
    if not isinstance(payload, dict):
        return {}, [f"{source_id}:json_object_required"], str(path)
    return payload, [], str(path)


def _safe_list(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _evidence_summary(source_id: str, payload: dict[str, Any], missing: list[str], path: str) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "latest_report_present": bool(path),
        "latest_json_path": path,
        "status": str(payload.get("status") or ("missing" if missing else "skipped")),
        "generated_at": str(payload.get("generated_at") or ""),
        "missing_conditions": missing,
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
    }


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Production landing signoff reviewer packet",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- ready_for_manual_signoff: {payload.get('ready_for_manual_signoff', False)}",
        f"- non_signoff_blocker_count: {payload.get('non_signoff_blocker_count', 0)}",
        f"- public_production_direct_launch: {payload.get('public_production_direct_launch', 'No-Go')}",
        "",
        "## Evidence",
    ]
    for item in payload.get("evidence", []):
        lines.append(f"- {item.get('source_id')}: {item.get('status')} | {item.get('latest_json_path') or '-'}")
    lines.extend(["", "## Reviewer command"])
    lines.append("```powershell")
    lines.append(str(payload.get("recommended_closeout_command") or ""))
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def build_production_landing_signoff_reviewer_packet(
    *,
    output_dir: str | Path | None = None,
    sources: dict[str, tuple[Path, str]] | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)
    effective_sources = sources or REPORT_SOURCES
    evidence: list[dict[str, Any]] = []
    payloads: dict[str, dict[str, Any]] = {}
    missing_conditions: list[str] = []

    for source_id, (directory, pattern) in effective_sources.items():
        path = _latest_json(Path(directory), pattern)
        payload, missing, path_text = _read_payload(path, source_id)
        payloads[source_id] = payload
        missing_conditions.extend(missing)
        evidence.append(_evidence_summary(source_id, payload, missing, path_text))

    pre_gate = payloads.get("pre_signoff_gate", {})
    action = payloads.get("action_pack", {})
    final = payloads.get("final_verification", {})
    ack = payloads.get("manual_signoff_evidence_ack_status", {})
    xiaomi = payloads.get("xiaomi_llm_preflight", {})
    staging = payloads.get("real_integration_staging_smoke", {})
    business = payloads.get("business_system_read_smoke", {})
    closeout = payloads.get("signoff_closeout", {})
    ready = pre_gate.get("ready_for_manual_signoff") is True and int(pre_gate.get("non_signoff_blocker_count") or 0) == 0
    secret_like = _contains_secret_like(payloads) or _contains_secret_like(evidence)
    if secret_like:
        missing_conditions.append("signoff_reviewer_packet:secret_like_text_detected")

    status = "ready_for_review" if ready and not missing_conditions else ("blocked" if secret_like else "partial")
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    packet = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.9.2",
        "phase": "v4.9 Production Landing Signoff Reviewer Packet",
        "status": status,
        "mode": "read_only_signoff_reviewer_packet",
        "read_only": True,
        "ready_for_manual_signoff": ready,
        "technical_evidence_ready": bool(pre_gate.get("technical_evidence_ready", False)),
        "non_signoff_blocker_count": int(pre_gate.get("non_signoff_blocker_count") or 0),
        "ack_ready": bool(pre_gate.get("ack_ready", False)),
        "action_required_input_count": action.get("required_input_count"),
        "final_verification": {
            "status": final.get("status", ""),
            "passed_count": final.get("passed_count", 0),
            "requirement_count": final.get("requirement_count", 0),
            "missing_conditions": _safe_list(final.get("missing_conditions"))[:16],
        },
        "real_llm_preflight": {
            "status": xiaomi.get("status", ""),
            "api_key_present": bool(xiaomi.get("api_key_present", False)),
            "network_check_executed": bool(xiaomi.get("network_check_executed", False)),
            "real_llm_executed": bool(xiaomi.get("real_llm_executed", False)),
        },
        "staging_smoke": {
            "status": staging.get("status", ""),
            "database_connected": bool(staging.get("database_connected", False)),
            "redis_connected": bool(staging.get("redis_connected", False)),
            "external_mcp_connected": bool(staging.get("external_mcp_connected", False)),
        },
        "business_read_smoke": {
            "status": business.get("status", ""),
            "business_system_connected": bool(business.get("business_system_connected", False)),
            "business_read_executed": bool(business.get("business_read_executed", False)),
            "business_write_executed": bool(business.get("business_write_executed", False)),
        },
        "manual_ack": {
            "status": ack.get("status", ""),
            "recommended_accept_count": int(ack.get("recommended_accept_count") or 0),
            "item_count": int(ack.get("item_count") or 0),
        },
        "closeout": {
            "status": closeout.get("status", ""),
            "target_record_written": bool(closeout.get("target_record_written", False)),
            "missing_conditions": _safe_list(closeout.get("missing_conditions"))[:16],
        },
        "evidence": evidence,
        "missing_conditions": sorted(set(missing_conditions)),
        "missing_condition_count": len(set(missing_conditions)),
        "recommended_closeout_command": (
            "powershell -NoProfile -ExecutionPolicy Bypass -File "
            "scripts\\production_landing_signoff_closeout.ps1"
        ),
        "secret_plaintext_output": False,
        "auto_signed": False,
        "auto_approved": False,
        "auto_closed": False,
        "public_production_direct_launch": "No-Go",
    }
    safe_packet = _redact(packet)
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_production_landing_signoff_reviewer_packet"
    json_path = output_root / f"{stem}.json"
    markdown_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(safe_packet, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(safe_packet), encoding="utf-8")
    return {
        "status": status,
        "generated_at": generated_at,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "ready_for_manual_signoff": ready,
        "missing_condition_count": packet["missing_condition_count"],
        "secret_plaintext_output": False,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a read-only packet for manual signoff reviewers.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_production_landing_signoff_reviewer_packet(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0 if summary["status"] in {"ready_for_review", "partial", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
