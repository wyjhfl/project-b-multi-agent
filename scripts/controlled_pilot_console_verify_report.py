from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "controlled_pilot_console_verify"
REPORTS = {
    "operations_console_landing_smoke": (
        ROOT_DIR / "docs" / "reports" / "operations_console_landing_smoke",
        "*_operations_console_landing_smoke.json",
    ),
    "controlled_pilot_operator_packet": (
        ROOT_DIR / "docs" / "reports" / "controlled_pilot_operator_packet",
        "*_controlled_pilot_operator_packet.json",
    ),
    "controlled_pilot_status_summary": (
        ROOT_DIR / "docs" / "reports" / "controlled_pilot_status_summary",
        "*_controlled_pilot_status_summary.json",
    ),
}
CONSOLE_RUNTIME_DIR = ROOT_DIR / "docs" / "reports" / "controlled_pilot_console"
STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]
SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"tp-[A-Za-z0-9_\-]{16,}"),
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
    return any(pattern.search(text) for pattern in SECRET_TEXT_PATTERNS)


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


def _read_report(report_id: str) -> dict[str, Any]:
    directory, pattern = REPORTS[report_id]
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


def _console_logs() -> dict[str, Any]:
    logs = {
        "runtime_dir": str(CONSOLE_RUNTIME_DIR),
        "pid_file_present_after_verify": (CONSOLE_RUNTIME_DIR / "controlled_pilot_console_processes.json").exists(),
        "backend_stdout_log": str(CONSOLE_RUNTIME_DIR / "backend.stdout.log"),
        "backend_stderr_log": str(CONSOLE_RUNTIME_DIR / "backend.stderr.log"),
        "frontend_stdout_log": str(CONSOLE_RUNTIME_DIR / "frontend.stdout.log"),
        "frontend_stderr_log": str(CONSOLE_RUNTIME_DIR / "frontend.stderr.log"),
    }
    return {key: _safe_text(value) if isinstance(value, str) else value for key, value in logs.items()}


def build_controlled_pilot_console_verify_report(
    *,
    output_dir: str | Path | None = None,
    backend_port: int = 8000,
    frontend_port: int = 3003,
    forced_status: str = "",
    failure_reason: str = "",
    write_report: bool = True,
) -> dict[str, Any]:
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    sources = {report_id: _read_report(report_id) for report_id in REPORTS}
    smoke = sources["operations_console_landing_smoke"].get("payload", {})
    packet = sources["controlled_pilot_operator_packet"].get("payload", {})
    status_summary = sources["controlled_pilot_status_summary"].get("payload", {})

    missing_conditions: list[str] = []
    for report_id, source in sources.items():
        if source.get("present") is not True:
            missing_conditions.append(f"{report_id}:latest_report_missing")
        if source.get("secret_detected") is True:
            missing_conditions.append(f"{report_id}:secret_like_text_detected")
        if source.get("status") in {"blocked", "failed", "missing"}:
            missing_conditions.append(f"{report_id}:not_usable")
    if smoke.get("execute") is not True:
        missing_conditions.append("operations_console_landing_smoke:execute_not_true")
    checks = smoke.get("checks") if isinstance(smoke.get("checks"), dict) else {}
    if checks.get("page_http_status") != 200:
        missing_conditions.append("operations_console_landing_smoke:page_http_status_not_200")
    if checks.get("summary_http_status") != 200:
        missing_conditions.append("operations_console_landing_smoke:summary_http_status_not_200")
    if packet.get("controlled_internal_pilot") != "Go":
        missing_conditions.append("controlled_pilot_operator_packet:controlled_internal_pilot_not_go")
    if packet.get("public_production_direct_launch") != "No-Go":
        missing_conditions.append("controlled_pilot_operator_packet:public_direct_launch_not_no_go")
    if status_summary.get("controlled_internal_pilot") != "Go":
        missing_conditions.append("controlled_pilot_status_summary:controlled_internal_pilot_not_go")
    if failure_reason:
        missing_conditions.append(f"verify_script:{_safe_text(failure_reason)}")

    secret_plaintext_output = any(bool(source.get("secret_detected", False)) for source in sources.values())
    success = not missing_conditions and not secret_plaintext_output
    status = "success" if success else "partial"
    controlled_internal_pilot = "Go" if success else "Manual-Review"
    if forced_status:
        status = forced_status if forced_status in STATUS_VOCABULARY else "failed"
        controlled_internal_pilot = "No-Go" if status in {"blocked", "failed"} else controlled_internal_pilot
    payload: dict[str, Any] = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.8.18",
        "phase": "v4.8 Controlled Pilot Console Verify",
        "status_vocabulary": STATUS_VOCABULARY,
        "mode": "read_only_local_console_verify_report",
        "status": status,
        "backend_url": f"http://127.0.0.1:{backend_port}",
        "frontend_url": f"http://127.0.0.1:{frontend_port}/operations",
        "controlled_internal_pilot": controlled_internal_pilot,
        "public_production_direct_launch": "No-Go",
        "failure_reason": _safe_text(failure_reason),
        "missing_conditions": sorted(set(missing_conditions)),
        "missing_condition_count": len(set(missing_conditions)),
        "sources": {
            report_id: {
                "present": source["present"],
                "status": source["status"],
                "latest_json_path": source["latest_json_path"],
                "generated_at": source["generated_at"],
                "secret_detected": source["secret_detected"],
            }
            for report_id, source in sources.items()
        },
        "console_runtime": _console_logs(),
        "real_llm_executed": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "secret_plaintext_output": secret_plaintext_output,
    }
    if payload["secret_plaintext_output"]:
        payload["status"] = "blocked"
        payload["controlled_internal_pilot"] = "No-Go"

    if write_report:
        output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
        output_root.mkdir(parents=True, exist_ok=True)
        short_commit = commit[:8] if commit != "unknown" else "unknown"
        stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_controlled_pilot_console_verify"
        json_path = output_root / f"{stem}.json"
        markdown_path = output_root / f"{stem}.md"
        payload["json_path"] = str(json_path)
        payload["markdown_path"] = str(markdown_path)
        payload["output_dir"] = str(output_root)
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        markdown_path.write_text(_build_markdown(payload), encoding="utf-8")
    return payload


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 受控试点控制台一键验证报告",
        "",
        f"- status: {payload.get('status', '')}",
        f"- controlled_internal_pilot: {payload.get('controlled_internal_pilot', '')}",
        f"- public_production_direct_launch: {payload.get('public_production_direct_launch', 'No-Go')}",
        f"- frontend_url: {payload.get('frontend_url', '')}",
        f"- backend_url: {payload.get('backend_url', '')}",
        f"- missing_condition_count: {payload.get('missing_condition_count', 0)}",
        f"- secret_plaintext_output: {payload.get('secret_plaintext_output', False)}",
        "",
        "## 证据来源",
    ]
    for report_id, source in payload.get("sources", {}).items():
        lines.append(f"- {report_id}: status={source.get('status')} path=`{source.get('latest_json_path')}`")
    lines.extend(["", "## 缺失条件"])
    missing = payload.get("missing_conditions", [])
    lines.extend(f"- {item}" for item in missing) if missing else lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build controlled pilot console verify report.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--backend-port", type=int, default=8000)
    parser.add_argument("--frontend-port", type=int, default=3003)
    parser.add_argument("--forced-status", choices=STATUS_VOCABULARY, default="")
    parser.add_argument("--failure-reason", default="")
    parser.add_argument("--no-write-report", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = build_controlled_pilot_console_verify_report(
        output_dir=args.output_dir,
        backend_port=args.backend_port,
        frontend_port=args.frontend_port,
        forced_status=args.forced_status,
        failure_reason=args.failure_reason,
        write_report=not args.no_write_report,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"status={report['status']}")
        print(f"controlled_internal_pilot={report['controlled_internal_pilot']}")
        print(f"public_production_direct_launch={report['public_production_direct_launch']}")
        print(f"missing_condition_count={report['missing_condition_count']}")
        print(f"secret_plaintext_output={report['secret_plaintext_output']}")
        if report.get("json_path"):
            print(f"json_path={report['json_path']}")
            print(f"markdown_path={report['markdown_path']}")
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
