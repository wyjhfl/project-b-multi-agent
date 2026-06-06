from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "production_pilot_evidence_bundle"

REPORT_SOURCES = {
    "production_landing_final_verification": (
        ROOT_DIR / "docs" / "reports" / "production_landing_final_verification",
        "*_production_landing_final_verification.json",
    ),
    "production_landing_signoff_closeout": (
        ROOT_DIR / "docs" / "reports" / "production_landing_signoff_closeout",
        "*_production_landing_signoff_closeout.json",
    ),
    "production_landing_status": (
        ROOT_DIR / "docs" / "reports" / "production_landing_status",
        "*_production_landing_status.json",
    ),
    "real_production_environment_checklist": (
        ROOT_DIR / "docs" / "reports" / "real_production_environment_checklist",
        "*_real_production_environment_checklist.json",
    ),
    "real_integration_gap_register": (
        ROOT_DIR / "docs" / "reports" / "real_integration_gap_register",
        "*_real_integration_gap_register.json",
    ),
    "production_landing_text_quality": (
        ROOT_DIR / "docs" / "reports" / "production_landing_text_quality",
        "*_production_landing_text_quality.json",
    ),
}

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"tp-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)(postgres(?:ql)?(?:\+\w+)?|redis)://[^,\s]+"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)\s*[:=]\s*([^\s,]+)"),
]

SAFE_PLACEHOLDERS = {
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
    text = json.dumps(value, ensure_ascii=False, default=str) if isinstance(value, (dict, list)) else str(value)
    for pattern in SECRET_TEXT_PATTERNS:
        for match in pattern.finditer(text):
            if len(match.groups()) >= 2:
                candidate = str(match.group(2) or "").strip().strip("\"'<>[]{}\\").lower()
                if candidate in SAFE_PLACEHOLDERS:
                    continue
            return True
    return False


def _redact(value: Any) -> Any:
    if isinstance(value, str):
        return "[redacted-secret-like-text]" if _contains_secret_like(value) else value
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _redact(item) for key, item in value.items()}
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


def _read_source(source_id: str, directory: Path, pattern: str) -> dict[str, Any]:
    path = _latest_json(directory, pattern)
    if path is None:
        return {
            "source_id": source_id,
            "present": False,
            "status": "skipped",
            "latest_json_path": "",
            "summary": {},
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
            "summary": {},
            "missing_conditions": [f"{source_id}:json_parse_failed"],
        }
    if not isinstance(payload, dict):
        payload = {}
    missing = payload.get("missing_conditions") if isinstance(payload.get("missing_conditions"), list) else []
    secret_detected = _contains_secret_like(payload)
    return {
        "source_id": source_id,
        "present": True,
        "status": "blocked" if secret_detected else str(payload.get("status") or "skipped"),
        "latest_json_path": str(path),
        "summary": {
            "generated_at": payload.get("generated_at"),
            "phase": payload.get("phase"),
            "version": payload.get("version"),
            "final_status": payload.get("final_status"),
            "controlled_pilot_ready": payload.get("controlled_pilot_ready"),
            "passed_count": payload.get("passed_count"),
            "requirement_count": payload.get("requirement_count"),
            "missing_condition_count": payload.get("missing_condition_count"),
            "required_input_count": payload.get("required_input_count"),
            "open_gap_count": payload.get("open_gap_count"),
            "gap_count": payload.get("gap_count"),
            "domain_count": payload.get("domain_count"),
            "secret_plaintext_output": payload.get("secret_plaintext_output"),
            "public_production_direct_launch": payload.get("public_production_direct_launch")
            or (payload.get("go_no_go") or {}).get("public_production_direct_launch")
            or (payload.get("go_no_go") or {}).get("production_direct_launch"),
        },
        "missing_conditions": [
            *[str(item) for item in missing],
            *([f"{source_id}:secret_like_value_detected"] if secret_detected else []),
        ],
        "secret_detected": secret_detected,
        "redaction": "[redacted-secret-like-text]" if secret_detected else "",
    }


def _build_sources() -> dict[str, dict[str, Any]]:
    return {
        source_id: _read_source(source_id, directory, pattern)
        for source_id, (directory, pattern) in REPORT_SOURCES.items()
    }


def _derive_status(sources: dict[str, dict[str, Any]]) -> tuple[str, list[str]]:
    missing: list[str] = []
    final = sources["production_landing_final_verification"]
    closeout = sources["production_landing_signoff_closeout"]
    status = sources["production_landing_status"]
    quality = sources["production_landing_text_quality"]

    if final.get("status") != "success":
        missing.append("production_landing_final_verification:not_success")
    if closeout.get("status") != "success" or closeout.get("summary", {}).get("final_status") != "success":
        missing.append("production_landing_signoff_closeout:not_success")
    if status.get("status") != "success" or status.get("summary", {}).get("controlled_pilot_ready") is not True:
        missing.append("production_landing_status:not_ready")
    if quality.get("status") != "success":
        missing.append("production_landing_text_quality:not_success")

    for source_id, source in sources.items():
        summary = source.get("summary") if isinstance(source.get("summary"), dict) else {}
        if summary.get("secret_plaintext_output") is not False:
            missing.append(f"{source_id}:secret_plaintext_output_not_false")
        public_direct = summary.get("public_production_direct_launch")
        if public_direct not in {"", None, "No-Go"}:
            missing.append(f"{source_id}:public_production_direct_launch_not_no_go")
        if source.get("status") in {"blocked", "failed"}:
            missing.append(f"{source_id}:blocked_or_failed")
        if source.get("secret_detected") is True:
            missing.append(f"{source_id}:secret_like_value_detected")

    return ("success" if not missing else "partial"), sorted(set(missing))


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 生产试点证据包",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- controlled_pilot_ready: {payload.get('controlled_pilot_ready', False)}",
        f"- public_production_direct_launch: {payload.get('public_production_direct_launch', 'No-Go')}",
        f"- missing_condition_count: {payload.get('missing_condition_count', 0)}",
        "",
        "## 证据源",
    ]
    for source_id, source in payload.get("sources", {}).items():
        summary = source.get("summary", {})
        lines.append(
            f"- {source_id}: status={source.get('status')} "
            f"path={source.get('latest_json_path')} generated_at={summary.get('generated_at', '')}"
        )
    lines.extend(["", "## 缺失条件"])
    missing = payload.get("missing_conditions", [])
    lines.extend(f"- {item}" for item in missing) if missing else lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def build_production_pilot_evidence_bundle(*, output_dir: str | Path | None = None) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)
    sources = _build_sources()
    status, missing = _derive_status(sources)
    secret_like_detected = _contains_secret_like(sources) or any(
        source.get("secret_detected") is True for source in sources.values()
    )
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    final_summary = sources["production_landing_final_verification"].get("summary", {})
    landing_summary = sources["production_landing_status"].get("summary", {})

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.8.9",
        "phase": "v4.8 Production Pilot Evidence Bundle",
        "status": "blocked" if secret_like_detected else status,
        "mode": "read_only_pilot_evidence_bundle",
        "read_only": True,
        "sources": _redact(sources),
        "controlled_pilot_ready": bool(landing_summary.get("controlled_pilot_ready", False)),
        "final_verification_passed_count": int(final_summary.get("passed_count") or 0),
        "final_verification_requirement_count": int(final_summary.get("requirement_count") or 0),
        "missing_conditions": sorted(
            set(
                [
                    *missing,
                    *(["production_pilot_evidence_bundle:secret_like_output_detected"] if secret_like_detected else []),
                ]
            )
        ),
        "missing_condition_count": 0,
        "secret_plaintext_output": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "auto_approved": False,
        "auto_closed": False,
        "public_production_direct_launch": "No-Go",
        "go_no_go": {
            "controlled_pilot": "Go" if status == "success" and not secret_like_detected else "Manual-Review",
            "public_production_direct_launch": "No-Go",
            "manual_signoff_required": True,
        },
        "next_actions": [
            "进入有限企业内网受控试点窗口",
            "继续补齐真实生产环境 checklist 中的 L1/L2 域级证据",
            "保持公网生产直上 No-Go，任何扩大范围必须重新人工 Go/No-Go",
        ],
    }
    payload["missing_condition_count"] = len(payload["missing_conditions"])
    if payload["status"] == "blocked":
        payload["go_no_go"]["controlled_pilot"] = "No-Go"

    short_commit = commit[:8] if commit != "unknown" else "unknown"
    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_production_pilot_evidence_bundle"
    json_path = output_root / f"{stem}.json"
    markdown_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")
    return {
        "status": payload["status"],
        "generated_at": generated_at,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "controlled_pilot_ready": payload["controlled_pilot_ready"],
        "missing_condition_count": payload["missing_condition_count"],
        "secret_plaintext_output": payload["secret_plaintext_output"],
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成生产试点证据包，只读取结构化报告。")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_production_pilot_evidence_bundle(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0 if summary["status"] in {"success", "partial", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
