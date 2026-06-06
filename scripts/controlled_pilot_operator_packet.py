from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "controlled_pilot_operator_packet"

REPORTS = {
    "controlled_pilot_status_summary": (
        ROOT_DIR / "docs" / "reports" / "controlled_pilot_status_summary",
        "*_controlled_pilot_status_summary.json",
    ),
    "production_landing_status": (
        ROOT_DIR / "docs" / "reports" / "production_landing_status",
        "*_production_landing_status.json",
    ),
    "controlled_pilot_launch_package": (
        ROOT_DIR / "docs" / "reports" / "controlled_pilot_launch_package",
        "*_controlled_pilot_launch_package.json",
    ),
    "controlled_pilot_window_record": (
        ROOT_DIR / "docs" / "reports" / "controlled_pilot_window_record",
        "*_controlled_pilot_window_record.json",
    ),
    "controlled_pilot_window_status": (
        ROOT_DIR / "docs" / "reports" / "controlled_pilot_window_status",
        "*_controlled_pilot_window_status.json",
    ),
    "operations_console_landing_smoke": (
        ROOT_DIR / "docs" / "reports" / "operations_console_landing_smoke",
        "*_operations_console_landing_smoke.json",
    ),
    "business_system_read_smoke": (
        ROOT_DIR / "docs" / "reports" / "business_system_read_smoke",
        "*_business_system_read_smoke.json",
    ),
    "business_system_production_readiness": (
        ROOT_DIR / "docs" / "reports" / "business_system_production_readiness",
        "*_business_system_production_readiness.json",
    ),
}

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"\btp-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)(postgres(?:ql)?(?:\+\w+)?|redis)://[^,\s]+"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password)\s*[:=]\s*([^\s,]+)"),
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8").strip()
    except Exception:
        return ""


def _contains_secret_like(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False, default=str) if isinstance(value, (dict, list)) else str(value)
    if any(pattern.search(text) for pattern in SECRET_TEXT_PATTERNS[:-1]):
        return True
    key_value_pattern = SECRET_TEXT_PATTERNS[-1]
    for match in key_value_pattern.finditer(text):
        raw_value = str(match.group(2) or "").strip()
        for delimiter in ('"', "'", ",", "]", "}", ";"):
            raw_value = raw_value.split(delimiter, 1)[0]
        raw_value = raw_value.strip().strip("<>")
        normalized = raw_value.lower()
        if normalized in {"secret-managed-token", "secret-managed-url", "set-in-local-env-only"}:
            continue
        return True
    return False


def _safe_text(value: Any) -> str:
    text = str(value or "")
    return "[redacted-secret-like-text]" if _contains_secret_like(text) else text


def _latest_json(directory: Path, pattern: str) -> Path | None:
    if not directory.exists() or not directory.is_dir():
        return None
    files = [item for item in directory.glob(pattern) if item.is_file()]
    if not files:
        return None

    def sort_key(path: Path) -> tuple[str, float, str]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        return str(payload.get("generated_at") or ""), path.stat().st_mtime, path.name

    return max(files, key=sort_key)


def _read_report(report_id: str, reports: dict[str, tuple[Path, str]]) -> dict[str, Any]:
    directory, pattern = reports[report_id]
    path = _latest_successful_executed_json(directory, pattern) if report_id == "operations_console_landing_smoke" else None
    path = path or _latest_json(directory, pattern)
    if path is None:
        return {
            "present": False,
            "status": "missing",
            "latest_json_path": "",
            "generated_at": "",
            "payload": {},
            "secret_detected": False,
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "present": True,
            "status": "blocked",
            "latest_json_path": _safe_text(path),
            "generated_at": "",
            "payload": {},
            "secret_detected": False,
        }
    secret_detected = _contains_secret_like(payload)
    return {
        "present": True,
        "status": "blocked" if secret_detected else str(payload.get("status") or "missing"),
        "latest_json_path": _safe_text(path),
        "generated_at": _safe_text(payload.get("generated_at") or ""),
        "payload": payload if not secret_detected else {},
        "secret_detected": secret_detected,
    }


def _latest_successful_executed_json(directory: Path, pattern: str) -> Path | None:
    if not directory.exists() or not directory.is_dir():
        return None
    candidates: list[Path] = []
    for path in directory.glob(pattern):
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if payload.get("status") == "success" and payload.get("execute") is True:
            candidates.append(path)
    if not candidates:
        return None
    return max(candidates, key=lambda path: _latest_json_sort_key(path))


def _latest_json_sort_key(path: Path) -> tuple[str, float, str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    return str(payload.get("generated_at") or ""), path.stat().st_mtime, path.name


def _derive_packet(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    status_payload = sources["controlled_pilot_status_summary"].get("payload", {})
    landing_status_payload = sources["production_landing_status"].get("payload", {})
    package_payload = sources["controlled_pilot_launch_package"].get("payload", {})
    window_payload = sources["controlled_pilot_window_record"].get("payload", {})
    window_status_payload = sources["controlled_pilot_window_status"].get("payload", {})
    smoke_payload = sources["operations_console_landing_smoke"].get("payload", {})
    business_smoke_payload = sources["business_system_read_smoke"].get("payload", {})
    business_readiness_payload = sources["business_system_production_readiness"].get("payload", {})

    missing_conditions: list[str] = []
    for source_id, source in sources.items():
        if source.get("present") is not True:
            missing_conditions.append(f"{source_id}:latest_report_missing")
        if source.get("secret_detected") is True:
            missing_conditions.append(f"{source_id}:secret_like_text_detected")
        if source.get("status") in {"blocked", "failed", "missing"}:
            missing_conditions.append(f"{source_id}:not_usable")

    ready = (
        status_payload.get("status") == "ready"
        and status_payload.get("controlled_internal_pilot") == "Go"
        and landing_status_payload.get("status") == "success"
        and landing_status_payload.get("controlled_pilot_ready") is True
        and package_payload.get("status") == "ready"
        and package_payload.get("launch_package_ready") is True
        and window_payload.get("opened") is True
        and window_status_payload.get("status") == "healthy"
        and smoke_payload.get("status") == "success"
        and smoke_payload.get("execute") is True
        and not missing_conditions
    )
    public_production_gaps: list[str] = []
    if business_smoke_payload.get("business_read_executed") is not True:
        public_production_gaps.append("business_system:real_read_only_smoke_not_executed")
    env_profile = (
        business_smoke_payload.get("env_profile")
        if isinstance(business_smoke_payload.get("env_profile"), dict)
        else {}
    )
    if env_profile.get("public_production_gap") is True:
        public_production_gaps.append("business_system:public_production_gap")
    if business_readiness_payload.get("status") != "ready":
        public_production_gaps.append("business_system:production_readiness_not_ready")
    business_ready_for_controlled_pilot = (
        business_smoke_payload.get("business_read_executed") is True
        and env_profile.get("public_production_gap") is not True
        and business_readiness_payload.get("status") == "ready"
    )
    business_safe_commands = env_profile.get("safe_commands") if isinstance(env_profile.get("safe_commands"), dict) else {}
    ready = ready and business_ready_for_controlled_pilot and not public_production_gaps
    return {
        "status": "ready" if ready else "partial",
        "controlled_internal_pilot": "Go" if ready else "Manual-Review",
        "public_production_direct_launch": "No-Go",
        "window": {
            "window_id": _safe_text(window_payload.get("window_id") or ""),
            "opened": bool(window_payload.get("opened", False)),
            "opened_by": _safe_text(window_payload.get("opened_by") or ""),
            "window_status": _safe_text(window_status_payload.get("status") or ""),
        },
        "evidence_paths": {
            source_id: _safe_text(source.get("latest_json_path") or "") for source_id, source in sources.items()
        },
        "operator_commands": [
            _safe_text(item)
            for item in (
                package_payload.get("operator_commands")
                if isinstance(package_payload.get("operator_commands"), list)
                else []
            )
        ],
        "business_system_read_smoke": {
            "status": _safe_text(business_smoke_payload.get("status") or "missing"),
            "business_system_connected": bool(business_smoke_payload.get("business_system_connected", False)),
            "business_read_executed": bool(business_smoke_payload.get("business_read_executed", False)),
            "auth_mode": _safe_text(env_profile.get("auth_mode") or ""),
            "safe_commands": {str(key): _safe_text(value) for key, value in business_safe_commands.items()},
        },
        "business_system_production_readiness": {
            "status": _safe_text(business_readiness_payload.get("status") or "missing"),
            "missing_condition_count": int(business_readiness_payload.get("missing_condition_count") or 0),
            "public_production_direct_launch": _safe_text(
                business_readiness_payload.get("public_production_direct_launch") or "No-Go"
            ),
        },
        "public_production_gaps": sorted(set(public_production_gaps)),
        "public_production_gap_count": len(set(public_production_gaps)),
        "pilot_roles": package_payload.get("pilot_roles") if isinstance(package_payload.get("pilot_roles"), list) else [],
        "rollback_required": True,
        "external_expansion_requires_new_manual_go_no_go": True,
        "manual_signoff_required": True,
        "missing_conditions": sorted(set(missing_conditions)),
        "missing_condition_count": len(set(missing_conditions)),
        "secret_plaintext_output": any(bool(source.get("secret_detected", False)) for source in sources.values()),
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
    }


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 受控试点操作员交接包",
        "",
        f"- status: {payload.get('status', '')}",
        f"- controlled_internal_pilot: {payload.get('controlled_internal_pilot', '')}",
        f"- public_production_direct_launch: {payload.get('public_production_direct_launch', 'No-Go')}",
        f"- window_id: {payload.get('window', {}).get('window_id', '')}",
        f"- opened: {payload.get('window', {}).get('opened', False)}",
        f"- rollback_required: {payload.get('rollback_required', True)}",
        f"- external_expansion_requires_new_manual_go_no_go: {payload.get('external_expansion_requires_new_manual_go_no_go', True)}",
        f"- secret_plaintext_output: {payload.get('secret_plaintext_output', False)}",
        "",
        "## 证据路径",
    ]
    for source_id, path in payload.get("evidence_paths", {}).items():
        lines.append(f"- {source_id}: `{path}`")
    lines.extend(["", "## 操作员命令"])
    commands = payload.get("operator_commands", [])
    lines.extend(f"- `{item}`" for item in commands) if commands else lines.append("- none")
    lines.extend(["", "## 真实生产扩展缺口"])
    public_gaps = payload.get("public_production_gaps", [])
    lines.extend(f"- {item}" for item in public_gaps) if public_gaps else lines.append("- none")
    lines.extend(["", "## 缺失条件"])
    missing = payload.get("missing_conditions", [])
    lines.extend(f"- {item}" for item in missing) if missing else lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def build_controlled_pilot_operator_packet(
    *,
    output_dir: str | Path | None = None,
    report_dirs: dict[str, str | Path] | None = None,
) -> dict[str, Any]:
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    effective_reports = {
        report_id: (Path(report_dirs[report_id]), config[1]) if report_dirs and report_id in report_dirs else config
        for report_id, config in REPORTS.items()
    }
    sources = {report_id: _read_report(report_id, effective_reports) for report_id in effective_reports}
    packet = _derive_packet(sources)
    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.8.16",
        "phase": "v4.8 Controlled Pilot Operator Packet",
        "mode": "read_only_operator_packet",
        "read_only": True,
        "sources": {
            source_id: {
                "present": source["present"],
                "status": source["status"],
                "latest_json_path": source["latest_json_path"],
                "generated_at": source["generated_at"],
                "secret_detected": source["secret_detected"],
            }
            for source_id, source in sources.items()
        },
        **packet,
    }
    if payload["secret_plaintext_output"]:
        payload["status"] = "blocked"
        payload["controlled_internal_pilot"] = "No-Go"

    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_controlled_pilot_operator_packet"
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
        "controlled_internal_pilot": payload["controlled_internal_pilot"],
        "public_production_direct_launch": payload["public_production_direct_launch"],
        "window_id": payload["window"]["window_id"],
        "missing_condition_count": payload["missing_condition_count"],
        "secret_plaintext_output": payload["secret_plaintext_output"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a read-only controlled pilot operator packet.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()
    summary = build_controlled_pilot_operator_packet(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
