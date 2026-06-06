from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "production_landing_final_verification"
DEFAULT_STATUS_DIR = ROOT_DIR / "docs" / "reports" / "production_landing_status"
DEFAULT_REFRESH_DIR = ROOT_DIR / "docs" / "reports" / "production_landing_refresh_status"
DEFAULT_OPERATIONS_CONSOLE_SMOKE_DIR = ROOT_DIR / "docs" / "reports" / "operations_console_landing_smoke"

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


def _latest_json_with_status(directory: Path, pattern: str, status: str) -> Path | None:
    if not directory.exists() or not directory.is_dir():
        return None
    files: list[Path] = []
    for item in directory.glob(pattern):
        if not item.is_file():
            continue
        try:
            payload = json.loads(item.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, dict) and payload.get("status") == status:
            files.append(item)
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


def _read_json(path: Path | None, *, source_id: str) -> tuple[dict[str, Any], list[str], str]:
    if path is None:
        return {}, [f"{source_id}:report_not_found"], ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}, [f"{source_id}:json_parse_failed"], str(path)
    if not isinstance(payload, dict):
        return {}, [f"{source_id}:json_object_required"], str(path)
    return payload, [], str(path)


def _requirement(requirement_id: str, passed: bool, evidence: Any, missing: list[str]) -> dict[str, Any]:
    return {
        "requirement_id": requirement_id,
        "passed": bool(passed),
        "evidence": _redact(evidence),
        "missing_conditions": [_redact(item) for item in missing],
    }


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 生产落地最终验证",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- passed_count: {payload.get('passed_count', 0)}/{payload.get('requirement_count', 0)}",
        f"- public_production_direct_launch: {payload.get('public_production_direct_launch', 'No-Go')}",
        "",
        "## 要求",
    ]
    for item in payload.get("requirements", []):
        lines.append(
            f"- {item.get('requirement_id')}: passed={item.get('passed')} missing={item.get('missing_conditions', [])}"
        )
    lines.append("")
    return "\n".join(lines)


def build_production_landing_final_verification(
    *,
    output_dir: str | Path | None = None,
    status_report: str | Path | None = None,
    refresh_report: str | Path | None = None,
    operations_console_smoke_report: str | Path | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)
    status_path = Path(status_report) if status_report else _latest_json(DEFAULT_STATUS_DIR, "*_production_landing_status.json")
    refresh_path = (
        Path(refresh_report)
        if refresh_report
        else _latest_json(DEFAULT_REFRESH_DIR, "*_production_landing_refresh_status.json")
    )
    operations_console_path = (
        Path(operations_console_smoke_report)
        if operations_console_smoke_report
        else (
            _latest_json_with_status(DEFAULT_OPERATIONS_CONSOLE_SMOKE_DIR, "*_operations_console_landing_smoke.json", "success")
            or _latest_json(DEFAULT_OPERATIONS_CONSOLE_SMOKE_DIR, "*_operations_console_landing_smoke.json")
        )
    )
    landing_status, status_errors, status_path_text = _read_json(status_path, source_id="production_landing_status")
    refresh_status, refresh_errors, refresh_path_text = _read_json(
        refresh_path,
        source_id="production_landing_refresh_status",
    )
    operations_console, operations_console_errors, operations_console_path_text = _read_json(
        operations_console_path,
        source_id="operations_console_landing_smoke",
    )

    blockers = landing_status.get("blockers") if isinstance(landing_status.get("blockers"), list) else []
    final_blockers = refresh_status.get("final_blockers") if isinstance(refresh_status.get("final_blockers"), list) else []
    xiaomi = landing_status.get("xiaomi_llm") if isinstance(landing_status.get("xiaomi_llm"), dict) else {}
    business = landing_status.get("business_system") if isinstance(landing_status.get("business_system"), dict) else {}
    manual_signoff = landing_status.get("manual_signoff") if isinstance(landing_status.get("manual_signoff"), dict) else {}
    secret_like_detected = _contains_secret_like(
        {
            "landing_status": landing_status,
            "refresh_status": refresh_status,
            "operations_console": operations_console,
            "paths": [status_path_text, refresh_path_text, operations_console_path_text],
        }
    )
    operations_checks = operations_console.get("checks") if isinstance(operations_console.get("checks"), dict) else {}
    operations_console_missing = (
        operations_console.get("missing_conditions") if isinstance(operations_console.get("missing_conditions"), list) else []
    )
    operations_console_passed = (
        operations_console.get("status") == "success"
        and operations_console.get("execute") is True
        and int(operations_checks.get("page_http_status") or 0) == 200
        and int(operations_checks.get("summary_http_status") or 0) == 200
        and int(operations_checks.get("backend_summary_http_status") or 0) == 200
        and str(operations_checks.get("safe_next_action") or "") != ""
        and isinstance(operations_checks.get("acceptance_blockers"), list)
        and operations_console.get("secret_plaintext_output") is False
    )

    requirements = [
        _requirement(
            "landing_status_success",
            landing_status.get("status") == "success" and landing_status.get("controlled_pilot_ready") is True,
            {"status": landing_status.get("status"), "controlled_pilot_ready": landing_status.get("controlled_pilot_ready")},
            status_errors
            + ([] if landing_status.get("status") == "success" else ["production_landing_status:status_not_success"])
            + ([] if landing_status.get("controlled_pilot_ready") is True else ["production_landing_status:not_ready"]),
        ),
        _requirement(
            "refresh_chain_success",
            refresh_status.get("status") == "success"
            and refresh_status.get("final_status") == "success"
            and int(refresh_status.get("blocked_step_count") or 0) == 0,
            {
                "status": refresh_status.get("status"),
                "final_status": refresh_status.get("final_status"),
                "blocked_step_count": refresh_status.get("blocked_step_count"),
            },
            refresh_errors
            + ([] if refresh_status.get("status") == "success" else ["refresh_status:status_not_success"])
            + ([] if refresh_status.get("final_status") == "success" else ["refresh_status:final_status_not_success"])
            + ([] if int(refresh_status.get("blocked_step_count") or 0) == 0 else ["refresh_status:blocked_steps_present"]),
        ),
        _requirement(
            "no_open_blockers",
            not blockers and not final_blockers,
            {"blockers": blockers, "final_blockers": final_blockers},
            [f"blocker:{item}" for item in [*blockers, *final_blockers]],
        ),
        _requirement(
            "real_llm_preflight_success",
            xiaomi.get("status") == "success"
            and xiaomi.get("api_key_present") is True
            and xiaomi.get("network_check_executed") is True
            and xiaomi.get("real_llm_executed") is True,
            xiaomi,
            []
            if (
                xiaomi.get("status") == "success"
                and xiaomi.get("api_key_present") is True
                and xiaomi.get("network_check_executed") is True
                and xiaomi.get("real_llm_executed") is True
            )
            else ["real_llm_preflight:not_success"],
        ),
        _requirement(
            "business_read_only_public_production_gap_tracked",
            business.get("write_executed") is False
            and business.get("business_data_written") is False
            and business.get("real_read_smoke_required_for_public_production") is True
            and "real_read_smoke_gap" in business
            and "production_readiness_public_production_gap" in business
            and "production_readiness_status" in business,
            business,
            []
            if (
                business.get("write_executed") is False
                and business.get("business_data_written") is False
                and business.get("real_read_smoke_required_for_public_production") is True
                and "real_read_smoke_gap" in business
                and "production_readiness_public_production_gap" in business
                and "production_readiness_status" in business
            )
            else ["business_read_only:public_production_gap_not_tracked"],
        ),
        _requirement(
            "business_landing_execution_pack_ready",
            business.get("landing_execution_pack_status") == "ready"
            and business.get("landing_execution_real_read_smoke_complete") is True,
            {
                "landing_execution_pack_status": business.get("landing_execution_pack_status"),
                "landing_execution_ready_for_real_read_smoke": business.get(
                    "landing_execution_ready_for_real_read_smoke"
                ),
                "landing_execution_real_read_smoke_complete": business.get(
                    "landing_execution_real_read_smoke_complete"
                ),
                "landing_execution_safe_next_action": business.get("landing_execution_safe_next_action"),
                "landing_execution_missing_count": business.get("landing_execution_missing_count"),
            },
            []
            if (
                business.get("landing_execution_pack_status") == "ready"
                and business.get("landing_execution_real_read_smoke_complete") is True
            )
            else ["business_landing_execution_pack:not_ready"],
        ),
        _requirement(
            "operations_console_landing_smoke_success",
            operations_console_passed,
            {
                "status": operations_console.get("status"),
                "execute": operations_console.get("execute"),
                "page_http_status": operations_checks.get("page_http_status"),
                "summary_http_status": operations_checks.get("summary_http_status"),
                "backend_summary_http_status": operations_checks.get("backend_summary_http_status"),
                "safe_next_action": operations_checks.get("safe_next_action"),
                "acceptance_blocker_count": len(operations_checks.get("acceptance_blockers", []))
                if isinstance(operations_checks.get("acceptance_blockers"), list)
                else 0,
            },
            operations_console_errors
            + [str(item) for item in operations_console_missing]
            + ([] if operations_console_passed else ["operations_console_landing_smoke:not_success"]),
        ),
        _requirement(
            "manual_signoff_completed",
            manual_signoff.get("completed") is True
            and manual_signoff.get("record_present") is True
            and str(manual_signoff.get("decision") or "").lower() == "go",
            manual_signoff,
            []
            if (
                manual_signoff.get("completed") is True
                and manual_signoff.get("record_present") is True
                and str(manual_signoff.get("decision") or "").lower() == "go"
            )
            else ["manual_signoff:not_completed"],
        ),
        _requirement(
            "safe_no_public_direct_launch",
            landing_status.get("public_production_direct_launch") == "No-Go"
            and refresh_status.get("public_production_direct_launch") == "No-Go",
            {
                "landing": landing_status.get("public_production_direct_launch"),
                "refresh": refresh_status.get("public_production_direct_launch"),
            },
            []
            if (
                landing_status.get("public_production_direct_launch") == "No-Go"
                and refresh_status.get("public_production_direct_launch") == "No-Go"
            )
            else ["public_production_direct_launch:not_no_go"],
        ),
        _requirement(
            "no_secret_plaintext_output",
            landing_status.get("secret_plaintext_output") is False
            and refresh_status.get("secret_plaintext_output") is False,
            {
                "landing": landing_status.get("secret_plaintext_output"),
                "refresh": refresh_status.get("secret_plaintext_output"),
            },
            []
            if (
                landing_status.get("secret_plaintext_output") is False
                and refresh_status.get("secret_plaintext_output") is False
            )
            else ["secret_plaintext_output:not_false"],
        ),
    ]
    if secret_like_detected:
        requirements.append(
            _requirement(
                "verification_output_secret_scan",
                False,
                "secret-like text detected and redacted",
                ["final_verification:secret_like_output_detected"],
            )
        )

    passed_count = sum(1 for item in requirements if item["passed"])
    status = "blocked" if secret_like_detected else ("success" if passed_count == len(requirements) else "partial")
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.8.0",
        "phase": "v4.8 Production Landing Final Verification",
        "status": status,
        "mode": "read_only_final_verification",
        "read_only": True,
        "status_report": _redact(status_path_text),
        "refresh_report": _redact(refresh_path_text),
        "operations_console_smoke_report": _redact(operations_console_path_text),
        "requirements": requirements,
        "requirement_count": len(requirements),
        "passed_count": passed_count,
        "missing_conditions": sorted(
            {
                str(condition)
                for item in requirements
                for condition in item.get("missing_conditions", [])
                if condition
            }
        ),
        "secret_plaintext_output": False,
        "auto_approved": False,
        "auto_closed": False,
        "public_production_direct_launch": "No-Go",
    }
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_production_landing_final_verification"
    json_path = output_root / f"{stem}.json"
    markdown_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")
    return {
        "status": payload["status"],
        "generated_at": generated_at,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "requirement_count": len(requirements),
        "passed_count": passed_count,
        "secret_plaintext_output": False,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生产落地最终只读验证。")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--status-report", default=None)
    parser.add_argument("--refresh-report", default=None)
    parser.add_argument("--operations-console-smoke-report", default=None)
    parser.add_argument("--strict", action="store_true", help="status 不是 success 时返回非零。")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_production_landing_final_verification(
        output_dir=args.output_dir,
        status_report=args.status_report,
        refresh_report=args.refresh_report,
        operations_console_smoke_report=args.operations_console_smoke_report,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    if args.strict and summary["status"] != "success":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
