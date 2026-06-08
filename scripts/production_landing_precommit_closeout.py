from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "production_landing_precommit_closeout"

SOURCE_DIRS = {
    "production_landing_action_pack": ROOT_DIR / "docs" / "reports" / "production_landing_action_pack",
    "controlled_pilot_run_packet": ROOT_DIR / "docs" / "reports" / "controlled_pilot_run_packet",
    "real_integration_staging_smoke": ROOT_DIR / "docs" / "reports" / "real_integration_staging_smoke",
    "production_landing_final_verification": ROOT_DIR / "docs" / "reports" / "production_landing_final_verification",
    "production_landing_text_quality": ROOT_DIR / "docs" / "reports" / "production_landing_text_quality",
}

REPORT_GLOBS = {
    "production_landing_action_pack": "*_production_landing_action_pack.json",
    "controlled_pilot_run_packet": "*_controlled_pilot_run_packet.json",
    "real_integration_staging_smoke": "*_real_integration_staging_smoke.json",
    "production_landing_final_verification": "*_production_landing_final_verification.json",
    "production_landing_text_quality": "*_production_landing_text_quality.json",
}

ACCEPTED_PRECOMMIT_MISSING_CONDITIONS = {
    "controlled_pilot_operator_packet:production_landing_evidence_freshness:not_fresh",
    "controlled_pilot_run_packet:required_ready_evidence_not_satisfied",
}
REMAINING_REAL_PRODUCTION_GAPS = ["business_system:real_business_system_required"]
SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"\btp-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"\bk-[A-Za-z0-9_\-]{24,}"),
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
    try:
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    except TypeError:
        text = str(value)
    for pattern in SECRET_TEXT_PATTERNS:
        for match in pattern.finditer(text):
            if len(match.groups()) >= 2:
                raw = str(match.group(2) or "").strip()
                for delimiter in ('"', "'", ",", "]", "}", ";"):
                    raw = raw.split(delimiter, 1)[0]
                normalized = raw.strip().strip("<>").lower()
                if normalized in SAFE_SECRET_PLACEHOLDERS:
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


def _safe_text(value: Any) -> str:
    text = str(value or "")
    redacted = _redact(text)
    return redacted if isinstance(redacted, str) else str(redacted)


def _safe_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_safe_text(item) for item in value]


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


def _read_report(source_id: str, directory: Path) -> dict[str, Any]:
    path = _latest_json(directory, REPORT_GLOBS[source_id])
    if path is None:
        return {
            "source_id": source_id,
            "present": False,
            "status": "missing",
            "latest_json_path": "",
            "payload": {},
            "missing_conditions": [f"{source_id}:latest_report_missing"],
            "secret_detected": False,
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
            "secret_detected": False,
        }
    if not isinstance(payload, dict):
        payload = {}
    secret_detected = _contains_secret_like(payload)
    return {
        "source_id": source_id,
        "present": True,
        "status": "blocked" if secret_detected else str(payload.get("status") or "skipped"),
        "latest_json_path": _safe_text(path),
        "payload": {} if secret_detected else payload,
        "missing_conditions": [f"{source_id}:secret_like_text_detected"] if secret_detected else [],
        "secret_detected": secret_detected,
    }


def _is_infra_ready(payload: dict[str, Any]) -> bool:
    return bool(
        payload.get("status") == "success"
        and payload.get("database_connected") is True
        and payload.get("redis_connected") is True
        and payload.get("external_mcp_connected") is True
        and payload.get("business_data_written") is not True
        and payload.get("audit_data_written") is not True
        and payload.get("metrics_data_written") is not True
        and payload.get("secret_plaintext_output") is not True
    )


def _derive_payload(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    missing: list[str] = []
    for source_id, source in sources.items():
        if source.get("present") is not True:
            missing.append(f"{source_id}:latest_report_missing")
        if source.get("secret_detected") is True:
            missing.append(f"{source_id}:secret_like_text_detected")
        if source.get("status") in {"blocked", "failed", "missing"}:
            missing.append(f"{source_id}:not_usable")
        missing.extend(_safe_string_list(source.get("missing_conditions")))

    action = sources["production_landing_action_pack"]["payload"]
    run_packet = sources["controlled_pilot_run_packet"]["payload"]
    infra = sources["real_integration_staging_smoke"]["payload"]
    final = sources["production_landing_final_verification"]["payload"]
    text_quality = sources["production_landing_text_quality"]["payload"]

    if action.get("status") != "success" or int(action.get("required_input_count") or 0) != 0:
        missing.append("production_landing_action_pack:not_success_or_inputs_remaining")
    if not _is_infra_ready(infra):
        missing.append("real_integration_staging_smoke:infra_not_ready")
    if text_quality.get("status") != "success" or int(text_quality.get("blocked_file_count") or 0) != 0:
        missing.append("production_landing_text_quality:not_success")
    if final.get("secret_plaintext_output") is True:
        missing.append("production_landing_final_verification:secret_plaintext_output")

    run_missing = _safe_string_list(run_packet.get("missing_conditions"))
    unexpected_run_missing = sorted(set(run_missing) - ACCEPTED_PRECOMMIT_MISSING_CONDITIONS)
    missing.extend(
        f"run_packet:unexpected_missing_condition:{condition}" for condition in unexpected_run_missing
    )
    accepted_precommit_missing = sorted(set(run_missing) & ACCEPTED_PRECOMMIT_MISSING_CONDITIONS)
    run_packet_ready = bool(
        run_packet.get("status") == "ready"
        and run_packet.get("run_packet_ready") is True
        and str(run_packet.get("controlled_internal_pilot") or "") == "Go"
        and not run_missing
    )
    if not run_packet_ready:
        if set(accepted_precommit_missing) != ACCEPTED_PRECOMMIT_MISSING_CONDITIONS:
            missing.append("controlled_pilot_run_packet:precommit_freshness_conditions_not_explicit")
        if str(run_packet.get("controlled_internal_pilot") or "") != "Manual-Review":
            missing.append("controlled_pilot_run_packet:controlled_internal_pilot_not_manual_review")

    public_values = [
        action.get("public_production_direct_launch"),
        run_packet.get("public_production_direct_launch"),
        infra.get("public_production_direct_launch"),
        final.get("public_production_direct_launch"),
        text_quality.get("public_production_direct_launch"),
    ]
    if not all(str(value or "No-Go") == "No-Go" for value in public_values):
        missing.append("public_production_direct_launch:not_no_go")

    secret_plaintext_output = any(
        source.get("secret_detected") is True
        or source.get("payload", {}).get("secret_plaintext_output") is True
        for source in sources.values()
    )
    if secret_plaintext_output:
        missing.append("precommit_closeout:secret_plaintext_output")

    blocked_by_unexpected_run_packet = bool(unexpected_run_missing)
    ready = not missing and not secret_plaintext_output
    return {
        "status": "ready"
        if ready
        else ("blocked" if secret_plaintext_output or blocked_by_unexpected_run_packet else "partial"),
        "precommit_landing_ready": ready,
        "controlled_internal_pilot": _safe_text(run_packet.get("controlled_internal_pilot") or "Manual-Review"),
        "post_commit_required": True,
        "accepted_precommit_missing_conditions": accepted_precommit_missing,
        "remaining_real_production_gaps": REMAINING_REAL_PRODUCTION_GAPS,
        "missing_conditions": sorted(set(missing)),
        "missing_condition_count": len(set(missing)),
        "public_production_direct_launch": "No-Go",
        "secret_plaintext_output": secret_plaintext_output,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "source_statuses": {source_id: _safe_text(source.get("status") or "") for source_id, source in sources.items()},
        "evidence_paths": {
            source_id: _safe_text(source.get("latest_json_path") or "") for source_id, source in sources.items()
        },
        "safe_next_steps": [
            "review_current_diff_and_commit_when_ready",
            "rerun_production_landing_evidence_freshness_after_commit",
            "rerun_controlled_pilot_demo_landing_after_commit",
            "do_not_claim_public_production_direct_launch",
        ],
    }


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 生产落地预提交收口摘要",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- precommit_landing_ready: {payload.get('precommit_landing_ready', False)}",
        f"- controlled_internal_pilot: {payload.get('controlled_internal_pilot', '')}",
        f"- post_commit_required: {payload.get('post_commit_required', True)}",
        f"- public_production_direct_launch: {payload.get('public_production_direct_launch', 'No-Go')}",
        "",
        "## Accepted Precommit Missing Conditions",
    ]
    accepted = payload.get("accepted_precommit_missing_conditions", [])
    lines.extend(f"- {item}" for item in accepted) if accepted else lines.append("- none")
    lines.extend(["", "## Missing Conditions"])
    missing = payload.get("missing_conditions", [])
    lines.extend(f"- {item}" for item in missing) if missing else lines.append("- none")
    lines.extend(["", "## Safe Next Steps"])
    for item in payload.get("safe_next_steps", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def build_production_landing_precommit_closeout(
    *,
    output_dir: str | Path | None = None,
    source_dirs: dict[str, str | Path] | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)
    effective_dirs = {
        source_id: Path(source_dirs[source_id]) if source_dirs and source_id in source_dirs else directory
        for source_id, directory in SOURCE_DIRS.items()
    }
    sources = {source_id: _read_report(source_id, directory) for source_id, directory in effective_dirs.items()}
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.9.10",
        "phase": "v4.9 Production Landing Precommit Closeout",
        "mode": "read_only_precommit_closeout",
        "read_only": True,
        **_derive_payload(sources),
        "sources": {
            source_id: {
                "present": source["present"],
                "status": source["status"],
                "latest_json_path": source["latest_json_path"],
                "missing_conditions": source["missing_conditions"],
                "secret_detected": source["secret_detected"],
            }
            for source_id, source in sources.items()
        },
    }
    if _contains_secret_like(payload):
        payload["status"] = "blocked"
        payload["precommit_landing_ready"] = False
        payload["secret_plaintext_output"] = True
        payload["missing_conditions"] = sorted(
            set([*payload["missing_conditions"], "precommit_closeout:secret_like_text_detected"])
        )
        payload["missing_condition_count"] = len(payload["missing_conditions"])
        payload = _redact(payload)

    short_commit = commit[:8] if commit != "unknown" else "unknown"
    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_production_landing_precommit_closeout"
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
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "output_dir": str(output_root),
        "precommit_landing_ready": bool(payload["precommit_landing_ready"]),
        "public_production_direct_launch": "No-Go",
        "secret_plaintext_output": bool(payload["secret_plaintext_output"]),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成生产落地预提交收口摘要（只读）。")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_production_landing_precommit_closeout(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0 if summary["status"] in {"ready", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
