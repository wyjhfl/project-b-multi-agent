from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "business_system_landing_execution_pack"
INPUT_PACKET_DIR = ROOT_DIR / "docs" / "reports" / "business_system_input_packet"
READINESS_DIR = ROOT_DIR / "docs" / "reports" / "business_system_production_readiness"
READ_SMOKE_DIR = ROOT_DIR / "docs" / "reports" / "business_system_read_smoke"
BUSINESS_READ_SMOKE_COMMAND = (
    "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1 "
    "-UseExistingEnv -BusinessOwner WYJ -SecurityReviewer WYJ -OperationsOwner WYJ -DataOwner WYJ"
)
BUSINESS_LANDING_RESUME_COMMAND = (
    "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_landing_resume.ps1 -UseExistingEnv"
)
BUSINESS_READINESS_BRIEF_COMMAND = (
    "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\codex_python.ps1 "
    "scripts\\business_system_production_readiness_brief.py"
)

SOURCE_REPORTS = {
    "business_system_input_packet": (INPUT_PACKET_DIR, "*_business_system_input_packet.json"),
    "business_system_production_readiness": (
        READINESS_DIR,
        "*_business_system_production_readiness.json",
    ),
    "business_system_read_smoke": (READ_SMOKE_DIR, "*_business_system_read_smoke.json"),
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


def _contains_secret_like(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False, default=str) if isinstance(value, (dict, list)) else str(value)
    for pattern in SECRET_TEXT_PATTERNS[:-1]:
        if pattern.search(text):
            return True
    key_value_pattern = SECRET_TEXT_PATTERNS[-1]
    safe_values = {
        "<secret-managed-token>",
        "<secret-managed-url>",
        "<set-in-local-env-only>",
        "<owner-or-staff-id>",
    }
    for match in key_value_pattern.finditer(text):
        raw_value = str(match.group(2) or "").strip()
        for delimiter in ('"', "'", ",", "]", "}", ";"):
            raw_value = raw_value.split(delimiter, 1)[0]
        if raw_value.strip().lower() not in safe_values:
            return True
    return False


def _safe_text(value: Any) -> str:
    text = str(value or "")
    return "[redacted-secret-like-text]" if _contains_secret_like(text) else text


def _safe_list(value: Any, limit: int = 32) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_safe_text(item) for item in value[:limit]]


def _read_source(report_id: str, reports: dict[str, tuple[Path, str]]) -> dict[str, Any]:
    directory, pattern = reports[report_id]
    path = _latest_json(directory, pattern)
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
            "latest_json_path": str(path),
            "generated_at": "",
            "payload": {},
            "secret_detected": False,
            "missing_conditions": [f"{report_id}:json_parse_failed"],
        }
    secret_detected = _contains_secret_like(payload)
    return {
        "present": True,
        "status": "blocked" if secret_detected else _safe_text(payload.get("status") or "missing"),
        "latest_json_path": str(path),
        "generated_at": _safe_text(payload.get("generated_at") or ""),
        "payload": {} if secret_detected else payload,
        "secret_detected": secret_detected,
        "missing_conditions": [f"{report_id}:secret_like_text_detected"] if secret_detected else [],
    }


def _condition_bucket(condition: str) -> str:
    if condition.startswith("owner:"):
        return "owners"
    if condition.startswith("opt_in:") or condition.startswith("env:") or condition.startswith("env_target:"):
        return "environment"
    if condition.startswith("evidence:") or condition.startswith("business_system_read_smoke:"):
        return "evidence"
    if condition.startswith("boundary:") or "secret" in condition:
        return "security_boundary"
    return "other"


def _group_missing(conditions: list[str]) -> dict[str, list[str]]:
    buckets = {
        "owners": [],
        "environment": [],
        "evidence": [],
        "security_boundary": [],
        "other": [],
    }
    for condition in sorted(set(conditions)):
        buckets[_condition_bucket(condition)].append(_safe_text(condition))
    return buckets


def _manual_inputs(input_payload: dict[str, Any], readiness_payload: dict[str, Any]) -> list[dict[str, Any]]:
    manual = input_payload.get("manual_input_checklist")
    if isinstance(manual, list) and manual:
        return [
            {
                "id": _safe_text(item.get("id") if isinstance(item, dict) else ""),
                "env": [_safe_text(value) for value in item.get("env", [])]
                if isinstance(item, dict) and isinstance(item.get("env"), list)
                else [],
                "description": _safe_text(item.get("description") if isinstance(item, dict) else ""),
            }
            for item in manual[:12]
            if isinstance(item, dict)
        ]
    required = readiness_payload.get("required_inputs")
    if not isinstance(required, list):
        return []
    return [
        {
            "id": _safe_text(item.get("id") if isinstance(item, dict) else ""),
            "env": [_safe_text(item.get("env") or "")] if isinstance(item, dict) and item.get("env") else [],
            "description": _safe_text(item.get("description") if isinstance(item, dict) else ""),
        }
        for item in required[:12]
        if isinstance(item, dict)
    ]


def _recommended_commands(input_payload: dict[str, Any], readiness_payload: dict[str, Any]) -> list[str]:
    command_candidates: list[str] = []
    commands = input_payload.get("recommended_commands")
    if isinstance(commands, list) and commands:
        command_candidates.extend(str(command) for command in commands)
    else:
        next_actions = readiness_payload.get("next_actions")
        if isinstance(next_actions, list) and next_actions:
            command_candidates.extend(str(action) for action in next_actions)
        else:
            command_candidates.extend([BUSINESS_READ_SMOKE_COMMAND, BUSINESS_READINESS_BRIEF_COMMAND])

    command_candidates.append(BUSINESS_LANDING_RESUME_COMMAND)

    result: list[str] = []
    for command in command_candidates:
        safe_command = _safe_text(command)
        if safe_command and safe_command not in result:
            result.append(safe_command)
        if len(result) >= 8:
            break
    return result


def _prioritize_command(commands: list[str], preferred_command: str) -> list[str]:
    if preferred_command not in commands:
        return commands
    return [preferred_command, *[command for command in commands if command != preferred_command]]


def _derive_pack(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    input_payload = sources["business_system_input_packet"].get("payload", {})
    readiness_payload = sources["business_system_production_readiness"].get("payload", {})
    smoke_payload = sources["business_system_read_smoke"].get("payload", {})
    source_missing: list[str] = []
    for source_id, source in sources.items():
        if source.get("present") is not True:
            source_missing.append(f"{source_id}:latest_report_missing")
        if source.get("status") in {"blocked", "failed", "missing"}:
            source_missing.append(f"{source_id}:not_usable")
        source_missing.extend(str(item) for item in source.get("missing_conditions", []))

    input_missing = _safe_list(input_payload.get("missing_conditions"))
    readiness_missing = _safe_list(readiness_payload.get("missing_conditions"))
    smoke_missing = _safe_list(smoke_payload.get("missing_conditions"))
    missing_conditions = sorted(set(source_missing + input_missing + readiness_missing + smoke_missing))

    ready_for_real_read_smoke = (
        input_payload.get("ready_for_real_read_smoke") is True
        and sources["business_system_input_packet"].get("secret_detected") is not True
    )
    real_read_smoke_complete = (
        readiness_payload.get("status") == "ready"
        and smoke_payload.get("business_read_executed") is True
        and smoke_payload.get("business_write_executed") is not True
        and smoke_payload.get("business_data_written") is not True
        and smoke_payload.get("local_business_mock_used") is not True
        and smoke_payload.get("secret_plaintext_output") is not True
    )
    blocked = any(source.get("secret_detected") for source in sources.values()) or any(
        condition.startswith("boundary:") for condition in missing_conditions
    )
    status = "blocked" if blocked else ("ready" if real_read_smoke_complete and not missing_conditions else "needs_input")
    if ready_for_real_read_smoke and not real_read_smoke_complete and not blocked:
        safe_next_action = "execute_real_read_smoke"
    elif real_read_smoke_complete and not blocked:
        safe_next_action = "refresh_controlled_pilot_gate"
    else:
        safe_next_action = "complete_business_system_inputs"

    commands = _recommended_commands(input_payload, readiness_payload)
    if safe_next_action == "refresh_controlled_pilot_gate":
        commands = _prioritize_command(commands, BUSINESS_LANDING_RESUME_COMMAND)
    return {
        "status": status,
        "ready_for_real_read_smoke": ready_for_real_read_smoke,
        "real_read_smoke_complete": real_read_smoke_complete,
        "safe_next_action": safe_next_action,
        "recommended_next_command": commands[0] if commands else "",
        "recommended_commands": commands,
        "manual_input_checklist": _manual_inputs(input_payload, readiness_payload),
        "missing_conditions": missing_conditions,
        "missing_condition_count": len(missing_conditions),
        "missing_by_category": _group_missing(missing_conditions),
        "source_statuses": {
            source_id: _safe_text(source.get("status") or "missing") for source_id, source in sources.items()
        },
        "evidence_paths": {
            source_id: _safe_text(source.get("latest_json_path") or "") for source_id, source in sources.items()
        },
        "owner_inputs_present": input_payload.get("owner_inputs_present")
        if isinstance(input_payload.get("owner_inputs_present"), dict)
        else readiness_payload.get("owner_inputs_present")
        if isinstance(readiness_payload.get("owner_inputs_present"), dict)
        else {},
        "business_system_read_smoke": {
            "status": _safe_text(smoke_payload.get("status") or "missing"),
            "business_system_connected": bool(smoke_payload.get("business_system_connected", False)),
            "business_read_executed": bool(smoke_payload.get("business_read_executed", False)),
            "business_write_executed": bool(smoke_payload.get("business_write_executed", False)),
            "business_data_written": bool(smoke_payload.get("business_data_written", False)),
            "local_business_mock_used": bool(smoke_payload.get("local_business_mock_used", False)),
            "secret_plaintext_output": bool(smoke_payload.get("secret_plaintext_output", False)),
        },
        "manual_signoff_required": True,
        "business_write_executed": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "secret_plaintext_output": False,
        "public_production_direct_launch": "No-Go",
    }


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 业务系统落地执行包",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- ready_for_real_read_smoke: {payload.get('ready_for_real_read_smoke', False)}",
        f"- real_read_smoke_complete: {payload.get('real_read_smoke_complete', False)}",
        f"- safe_next_action: {payload.get('safe_next_action', '')}",
        f"- recommended_next_command: `{payload.get('recommended_next_command', '')}`",
        f"- public_production_direct_launch: {payload.get('public_production_direct_launch', 'No-Go')}",
        f"- secret_plaintext_output: {payload.get('secret_plaintext_output', False)}",
        "",
        "## 缺口分组",
    ]
    for category, items in payload.get("missing_by_category", {}).items():
        lines.append(f"- {category}: {len(items)}")
        for item in items[:8]:
            lines.append(f"  - {item}")
    lines.extend(["", "## 证据来源"])
    for source_id, path in payload.get("evidence_paths", {}).items():
        lines.append(f"- {source_id}: `{path}`")
    lines.extend(["", "## 人工输入"])
    for item in payload.get("manual_input_checklist", []):
        lines.append(f"- {item.get('id')}: {item.get('description')} env={item.get('env')}")
    lines.extend(["", "## 推荐命令"])
    for command in payload.get("recommended_commands", []):
        lines.append(f"- `{command}`")
    lines.extend(
        [
            "",
            "## 边界",
            "- 本执行包只读取脱敏 JSON 报告，不连接真实业务系统。",
            "- 真实只读 smoke 必须通过 PowerShell 入口输入 secret，报告不得输出 secret 原文。",
            "- public_production_direct_launch 始终保持 No-Go。",
            "",
        ]
    )
    return "\n".join(lines)


def build_business_system_landing_execution_pack(
    *,
    output_dir: str | Path | None = None,
    report_dirs: dict[str, str | Path] | None = None,
) -> dict[str, Any]:
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    effective_reports = {
        report_id: (Path(report_dirs[report_id]), config[1]) if report_dirs and report_id in report_dirs else config
        for report_id, config in SOURCE_REPORTS.items()
    }
    sources = {report_id: _read_source(report_id, effective_reports) for report_id in effective_reports}
    derived = _derive_pack(sources)
    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.8.23",
        "phase": "v4.8 Business System Landing Execution Pack",
        "mode": "read_only_execution_pack",
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
        **derived,
    }
    if _contains_secret_like(payload):
        payload["status"] = "blocked"
        payload["secret_plaintext_output"] = False
        payload["missing_conditions"] = sorted(
            set(payload["missing_conditions"] + ["boundary:secret_like_text_detected"])
        )
        payload["missing_condition_count"] = len(payload["missing_conditions"])
        payload["missing_by_category"] = _group_missing(payload["missing_conditions"])

    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_business_system_landing_execution_pack"
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
        "ready_for_real_read_smoke": payload["ready_for_real_read_smoke"],
        "real_read_smoke_complete": payload["real_read_smoke_complete"],
        "safe_next_action": payload["safe_next_action"],
        "missing_condition_count": payload["missing_condition_count"],
        "secret_plaintext_output": False,
        "public_production_direct_launch": "No-Go",
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成业务系统落地执行包。")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_business_system_landing_execution_pack(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0 if summary["status"] in {"ready", "needs_input", "blocked"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
