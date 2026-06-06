from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "production_landing_blocker_resolution"
SOFT_BLOCKED_SOURCES = {"production_landing_final_verification"}

REPORT_SOURCES = {
    "production_landing_status": {
        "dir": ROOT_DIR / "docs" / "reports" / "production_landing_status",
        "pattern": "*_production_landing_status.json",
    },
    "production_landing_action_pack": {
        "dir": ROOT_DIR / "docs" / "reports" / "production_landing_action_pack",
        "pattern": "*_production_landing_action_pack.json",
    },
    "production_landing_final_verification": {
        "dir": ROOT_DIR / "docs" / "reports" / "production_landing_final_verification",
        "pattern": "*_production_landing_final_verification.json",
    },
    "production_landing_xiaomi_llm_preflight": {
        "dir": ROOT_DIR / "docs" / "reports" / "production_landing_xiaomi_llm_preflight",
        "pattern": "*_production_landing_xiaomi_llm_preflight.json",
    },
    "manual_signoff_evidence_ack_status": {
        "dir": ROOT_DIR / "docs" / "reports" / "manual_signoff_evidence_ack_status",
        "pattern": "*_manual_signoff_evidence_ack_status.json",
    },
    "manual_signoff_record_validation": {
        "dir": ROOT_DIR / "docs" / "reports" / "manual_signoff_record_validation",
        "pattern": "*_manual_signoff_record_validation.json",
    },
    "manual_signoff_record_promote": {
        "dir": ROOT_DIR / "docs" / "reports" / "manual_signoff_record_promote",
        "pattern": "*_manual_signoff_record_promote.json",
    },
}

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"tp-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)(postgres(?:ql)?(?:\+\w+)?|redis)://[^,\s]+"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)\s*[:=]\s*([^\s,]+)"),
]
SAFE_SECRET_PLACEHOLDERS = {
    "<secret-managed-token>",
    "<secret-managed-url>",
    "<external-secret-managed-url>",
    "<secret-managed-value>",
    "secret-managed-token",
    "secret-managed-url",
    "external-secret-managed-url",
    "secret-managed-value",
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
        return any(_contains_secret_like(key) or _contains_secret_like(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_secret_like(item) for item in value)
    text = str(value)
    for pattern in SECRET_TEXT_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        if len(match.groups()) >= 2 and str(match.group(2)).strip().strip(".,;") in SAFE_SECRET_PLACEHOLDERS:
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


def _read_latest(source_id: str) -> dict[str, Any]:
    source = REPORT_SOURCES[source_id]
    path = _latest_json(Path(source["dir"]), str(source["pattern"]))
    if path is None:
        return {
            "source_id": source_id,
            "present": False,
            "status": "skipped",
            "latest_json_path": "",
            "payload": {},
            "missing_conditions": [f"{source_id}:report_not_found"],
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "source_id": source_id,
            "present": True,
            "status": "blocked",
            "latest_json_path": str(path),
            "payload": {},
            "missing_conditions": [f"{source_id}:json_parse_failed"],
        }
    if not isinstance(payload, dict):
        payload = {}
    missing = payload.get("missing_conditions") if isinstance(payload.get("missing_conditions"), list) else []
    return {
        "source_id": source_id,
        "present": True,
        "status": str(payload.get("status") or "skipped"),
        "latest_json_path": str(path),
        "payload": payload,
        "missing_conditions": [str(item) for item in missing],
    }


def _source_summary(source: dict[str, Any]) -> dict[str, Any]:
    payload = source.get("payload") if isinstance(source.get("payload"), dict) else {}
    return {
        "source_id": source.get("source_id"),
        "present": bool(source.get("present")),
        "status": str(source.get("status") or "skipped"),
        "latest_json_path": _redact(str(source.get("latest_json_path") or "")),
        "generated_at": str(payload.get("generated_at") or ""),
    }


def _make_action(action_id: str, status: str, owner: str, evidence: dict[str, Any], commands: list[str]) -> dict[str, Any]:
    return {
        "action_id": action_id,
        "status": status,
        "owner": owner,
        "evidence": _redact(evidence),
        "safe_commands": _redact(commands),
    }


def _derive_actions(reports: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    status_payload = reports["production_landing_status"].get("payload", {})
    action_payload = reports["production_landing_action_pack"].get("payload", {})
    xiaomi_payload = reports["production_landing_xiaomi_llm_preflight"].get("payload", {})
    ack_payload = reports["manual_signoff_evidence_ack_status"].get("payload", {})
    validation_payload = reports["manual_signoff_record_validation"].get("payload", {})
    promote_payload = reports["manual_signoff_record_promote"].get("payload", {})

    xiaomi_status = status_payload.get("xiaomi_llm") if isinstance(status_payload.get("xiaomi_llm"), dict) else {}
    xiaomi_preflight = xiaomi_payload.get("preflight") if isinstance(xiaomi_payload.get("preflight"), dict) else {}
    manual = status_payload.get("manual_signoff") if isinstance(status_payload.get("manual_signoff"), dict) else {}
    required_inputs = action_payload.get("required_inputs") if isinstance(action_payload.get("required_inputs"), list) else []
    action_ids = {str(item.get("input_id") or "") for item in required_inputs if isinstance(item, dict)}

    actions = [
        _make_action(
            "real_llm_preflight",
            "resolved"
            if (
                xiaomi_status.get("status") == "success"
                and xiaomi_status.get("api_key_present") is True
                and xiaomi_status.get("network_check_executed") is True
                and xiaomi_status.get("real_llm_executed") is True
            )
            else "required",
            "operator",
            {
                "status": xiaomi_status.get("status", xiaomi_payload.get("status", "skipped")),
                "api_key_present": xiaomi_status.get("api_key_present", xiaomi_payload.get("api_key_present", False)),
                "network_check_requested": xiaomi_status.get(
                    "network_check_requested",
                    xiaomi_preflight.get("network_check_requested", xiaomi_payload.get("execute_network_check", False)),
                ),
                "network_check_allowed": xiaomi_status.get(
                    "network_check_allowed",
                    xiaomi_preflight.get("network_check_allowed", False),
                ),
                "network_check_executed": xiaomi_status.get(
                    "network_check_executed",
                    xiaomi_preflight.get("network_check_executed", False),
                ),
                "real_llm_executed": xiaomi_status.get("real_llm_executed", xiaomi_payload.get("real_llm_executed", False)),
                "safe_next_action": xiaomi_status.get("safe_next_action", xiaomi_payload.get("safe_next_action", "")),
                "acceptance_blockers": xiaomi_status.get(
                    "acceptance_blockers",
                    xiaomi_payload.get("acceptance_blockers", []),
                ),
                "secret_plaintext_output": xiaomi_payload.get("secret_plaintext_output", False),
            },
            [
                "powershell -ExecutionPolicy Bypass -File scripts/xiaomi_llm_landing_resume.ps1",
                "python scripts/production_landing_final_verification.py",
            ],
        ),
        _make_action(
            "manual_signoff_record",
            "resolved"
            if (
                manual.get("completed") is True
                and str(manual.get("decision") or "").lower() == "go"
                and "manual_signoff_record" not in action_ids
            )
            else "required",
            "business_owner",
            {
                "completed": manual.get("completed", False),
                "decision": manual.get("decision", ""),
                "required_by_action_pack": "manual_signoff_record" in action_ids,
                "ack_status": ack_payload.get("status", "skipped"),
                "recommended_accept_count": ack_payload.get("recommended_accept_count"),
                "validation_status": validation_payload.get("status", "skipped"),
                "promote_status": promote_payload.get("status", "skipped"),
                "promoted": promote_payload.get("promoted", False),
            },
            [
                "python scripts/manual_signoff_evidence_ack_status.py",
                "python scripts/manual_signoff_record_draft.py",
                "powershell -ExecutionPolicy Bypass -File scripts/production_landing_signoff_closeout.ps1",
                "python scripts/production_landing_signoff_closeout.py --release-manager <name-or-id> --security-reviewer <name-or-id> --business-owner <name-or-id> --operations-owner <name-or-id> --confirm-manual-signoff --confirm-controlled-pilot-go",
                "powershell -ExecutionPolicy Bypass -File scripts/manual_signoff_record_fill.ps1",
                "python scripts/manual_signoff_record_fill.py --release-manager <name-or-id> --security-reviewer <name-or-id> --business-owner <name-or-id> --operations-owner <name-or-id> --confirm-manual-signoff --confirm-controlled-pilot-go",
                "python scripts/manual_signoff_record_promote.py",
                "python scripts/manual_signoff_record_validator.py",
                "python scripts/manual_signoff_package.py",
                "python scripts/production_landing_refresh_status.py --closure-evidence docs/reports/launch_blocker_closure/closure_evidence.draft.json",
            ],
        ),
    ]
    return actions


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 生产落地阻塞解除检查",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- required_action_count: {payload.get('required_action_count', 0)}",
        f"- public_production_direct_launch: {payload.get('public_production_direct_launch', 'No-Go')}",
        "",
        "## Actions",
    ]
    for item in payload.get("actions", []):
        lines.append(f"- {item.get('action_id')}: {item.get('status')} owner={item.get('owner')}")
    lines.append("")
    return "\n".join(lines)


def build_production_landing_blocker_resolution(*, output_dir: str | Path | None = None) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)
    reports = {source_id: _read_latest(source_id) for source_id in REPORT_SOURCES}
    actions = _derive_actions(reports)
    required_actions = [item for item in actions if item.get("status") == "required"]
    source_blocked = [
        source_id
        for source_id, source in reports.items()
        if source.get("status") in {"blocked", "failed"} and source_id not in SOFT_BLOCKED_SOURCES
    ]
    source_missing_conditions = [
        source_id
        for source_id, source in reports.items()
        if source.get("missing_conditions")
    ]
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    status = "blocked" if source_blocked else ("success" if not required_actions else "partial")
    raw_payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.8.1",
        "phase": "v4.8 Production Landing Blocker Resolution",
        "status": status,
        "mode": "read_only_blocker_resolution",
        "read_only": True,
        "sources": {source_id: _source_summary(source) for source_id, source in reports.items()},
        "actions": actions,
        "required_action_count": len(required_actions),
        "required_actions": [str(item.get("action_id")) for item in required_actions],
        "source_blocked_or_failed": source_blocked,
        "source_missing_conditions": source_missing_conditions,
        "secret_plaintext_output": False,
        "auto_approved": False,
        "auto_closed": False,
        "public_production_direct_launch": "No-Go",
    }
    secret_like_detected = _contains_secret_like(raw_payload) or _contains_secret_like(
        {source_id: source.get("payload", {}) for source_id, source in reports.items()}
    )
    payload = _redact(raw_payload)
    if secret_like_detected:
        payload["status"] = "blocked"
        payload["secret_plaintext_output"] = True
        payload["required_actions"] = sorted(set([*payload["required_actions"], "secret_like_output_review"]))
        payload["required_action_count"] = len(payload["required_actions"])

    short_commit = commit[:8] if commit != "unknown" else "unknown"
    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_production_landing_blocker_resolution"
    json_path = output_root / f"{stem}.json"
    markdown_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")
    return {
        "status": payload["status"],
        "generated_at": generated_at,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "required_action_count": int(payload["required_action_count"]),
        "secret_plaintext_output": bool(payload["secret_plaintext_output"]),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成生产落地阻塞解除检查报告。")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_production_landing_blocker_resolution(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0 if summary["status"] in {"success", "partial", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
