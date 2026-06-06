from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "production_acceptance_gaps"

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)=([^,\s]+)"),
    re.compile(r"(?i)\"(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)\"\s*:\s*\"[^\"]+\""),
    re.compile(r"(?i)(postgres(?:ql)?|redis)://[^,\s]+"),
    re.compile(r"(?i)(webhook|bearer)\s+[A-Za-z0-9_\-\.]{8,}"),
]

BOUNDARY_DECLARATIONS = [
    "只读生产验收缺口登记册",
    "仅消费 Acceptance Drill Evidence Index JSON 的结构化字段",
    "不读取 Markdown 报告正文",
    "不读取或输出真实 secret 原文",
    "不修改上游报告，不修改 .env 或环境变量",
    "不自动关闭 gap，不自动批准上线",
    "不执行真实外网 LLM，不连接真实外部系统",
    "不执行真实部署、迁移、发布、回滚、压测、备份恢复、安全扫描、审计导出、密钥轮换或权限变更",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        output = subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8")
        return output.strip()
    except Exception:
        return ""


def _sanitize_text(value: Any) -> str:
    text = str(value)
    for pattern in SECRET_TEXT_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


def _contains_secret_like_payload(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False, default=str) if isinstance(value, (dict, list)) else str(value)
    return any(pattern.search(text) for pattern in SECRET_TEXT_PATTERNS)


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _load_index(path_value: str | Path | None) -> dict[str, Any]:
    if not path_value:
        return {
            "path": "",
            "provided": False,
            "exists": False,
            "loaded": False,
            "status": "skipped",
            "payload": {},
            "missing_conditions": ["acceptance_index:input_not_provided"],
            "warnings": [],
            "secret_detected": False,
        }
    path = Path(path_value)
    safe_path = _sanitize_text(path)
    if not path.exists():
        return {
            "path": safe_path,
            "provided": True,
            "exists": False,
            "loaded": False,
            "status": "skipped",
            "payload": {},
            "missing_conditions": ["acceptance_index:path_not_found"],
            "warnings": [],
            "secret_detected": False,
        }
    if not path.is_file() or path.suffix.lower() != ".json":
        return {
            "path": safe_path,
            "provided": True,
            "exists": True,
            "loaded": False,
            "status": "skipped",
            "payload": {},
            "missing_conditions": ["acceptance_index:json_file_required"],
            "warnings": [],
            "secret_detected": False,
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "path": safe_path,
            "provided": True,
            "exists": True,
            "loaded": False,
            "status": "skipped",
            "payload": {},
            "missing_conditions": ["acceptance_index:json_parse_failed"],
            "warnings": [f"acceptance_index:json_parse_failed:{type(exc).__name__}"],
            "secret_detected": False,
        }
    if not isinstance(payload, dict) or not payload:
        return {
            "path": safe_path,
            "provided": True,
            "exists": True,
            "loaded": False,
            "status": "skipped",
            "payload": {},
            "missing_conditions": ["acceptance_index:json_empty_or_not_object"],
            "warnings": [],
            "secret_detected": False,
        }

    status = _sanitize_text(payload.get("status") or "skipped")
    secret_detected = _contains_secret_like_payload(payload)
    missing_conditions = [_sanitize_text(item) for item in _safe_list(payload.get("missing_conditions"))]
    warnings = [_sanitize_text(item) for item in _safe_list(payload.get("warnings"))]
    if status == "skipped":
        missing_conditions.append("acceptance_index:source_status_skipped")
    if status in {"blocked", "failed"}:
        missing_conditions.append(f"acceptance_index:source_status_{status}")
    if payload.get("read_only") is False:
        missing_conditions.append("acceptance_index:not_read_only")
    for flag in [
        "real_llm_executed",
        "external_mcp_connected",
        "external_system_connected",
        "database_connected",
        "redis_connected",
        "business_system_connected",
        "deployment_executed",
        "release_created",
        "tag_created",
        "auto_approved",
        "auto_closed",
    ]:
        if bool(payload.get(flag, False)):
            missing_conditions.append(f"acceptance_index:{flag}_unexpected")
    for report in _safe_list(payload.get("reports")):
        if isinstance(report, dict):
            for flag in _safe_list(report.get("unexpected_execution_flags")):
                missing_conditions.append(f"acceptance_index:report_unexpected_flag:{_sanitize_text(flag)}")
    if secret_detected:
        missing_conditions.append("acceptance_index:secret_like_value_detected")
        warnings.append("acceptance_index:secret_like_value_detected")
    return {
        "path": safe_path,
        "provided": True,
        "exists": True,
        "loaded": True,
        "status": status,
        "payload": payload,
        "missing_conditions": missing_conditions,
        "warnings": warnings,
        "secret_detected": secret_detected,
    }


def _domain_scope(domain: str) -> str:
    if domain in {"real_llm", "external_mcp", "business_system"}:
        return "integration"
    if domain in {"oidc_sso"}:
        return "identity"
    if domain in {"postgres", "redis"}:
        return "storage"
    if domain in {"apm_logging_alerting", "backup_restore_dr", "capacity_load_soak"}:
        return "sre"
    if domain == "security_compliance":
        return "security"
    if domain == "release_rollback_gate":
        return "release"
    return "acceptance"


def _build_gap_register(index_payload: dict[str, Any], source_status: str) -> list[dict[str, Any]]:
    reports = _safe_list(index_payload.get("reports"))
    latest = reports[0] if reports and isinstance(reports[0], dict) else {}
    state_counts = latest.get("domain_status_counts") if isinstance(latest.get("domain_status_counts"), dict) else {}
    domains: list[str] = []
    for domain, count in state_counts.items():
        if str(domain) in {"skipped", "blocked", "failed"} and int(count or 0) > 0:
            domains.append(f"domain_status:{domain}")
    if not domains and source_status == "skipped":
        domains.append("acceptance_index_skipped")
    if not domains and source_status == "blocked":
        domains.append("acceptance_index_blocked")
    if not domains:
        domains.append("manual_acceptance_review_required")

    register = []
    for index, key in enumerate(sorted(set(domains)), start=1):
        status = "skipped" if source_status == "skipped" else "blocked" if source_status in {"blocked", "failed"} else "open"
        scope = _domain_scope(key.replace("domain_status:", ""))
        register.append(
            {
                "gap_id": f"PAG-{index:03d}",
                "source": "acceptance_drill_index",
                "source_key": _sanitize_text(key),
                "scope": scope,
                "risk_description": f"生产验收缺口待人工关闭：{_sanitize_text(key)}",
                "owner": "manual_owner_required",
                "due_at": "manual_due_date_required",
                "compensating_controls": ["manual_compensating_controls_required"],
                "closure_evidence": ["manual_closure_evidence_required"],
                "status": status,
                "approval_state": "not_approved",
                "next_actions": [
                    "指定责任人与到期时间",
                    "补齐脱敏验收证据和补偿控制",
                    "人工复核后重新生成受控验收演练与缺口登记册",
                ],
            }
        )
    return register


def _derive_status(source: dict[str, Any], register: list[dict[str, Any]]) -> str:
    if source.get("secret_detected"):
        return "blocked"
    if source.get("status") in {"blocked", "failed"}:
        return "blocked"
    if any(
        marker in condition
        for condition in source.get("missing_conditions", [])
        for marker in ["_unexpected", "not_read_only", "secret_like_value_detected", "report_unexpected_flag"]
    ):
        return "blocked"
    if not source.get("loaded") or source.get("status") == "skipped":
        return "skipped"
    if any(item.get("status") == "blocked" for item in register):
        return "blocked"
    return "partial"


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v4.2 Production Acceptance Gap Register（只读）",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- gap_count: {payload.get('gap_count', 0)}",
        f"- open_gap_count: {payload.get('open_gap_count', 0)}",
        "",
        "## Gaps",
    ]
    for item in payload.get("gap_register", []):
        lines.append(f"- {item.get('gap_id')}: {item.get('status')} | {item.get('scope')} | {item.get('source_key')}")
    lines.extend(["", "## Missing Conditions"])
    missing = payload.get("missing_conditions", [])
    if missing:
        for item in missing:
            lines.append(f"- {item}")
    else:
        lines.append("- none")
    lines.extend(["", "## Boundary Declarations"])
    for item in payload.get("boundary_declarations", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def build_production_acceptance_gap_register(
    *,
    output_dir: str | Path | None = None,
    acceptance_index: str | Path | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    source = _load_index(acceptance_index)
    source_payload = source.get("payload", {}) if isinstance(source.get("payload"), dict) else {}
    register = _build_gap_register(source_payload, str(source.get("status", "skipped"))) if source.get("loaded") else []
    status = _derive_status(source, register)
    missing_conditions = sorted(set(_sanitize_text(item) for item in source.get("missing_conditions", [])))
    warnings = sorted(set(_sanitize_text(item) for item in source.get("warnings", [])))
    open_gap_count = sum(1 for item in register if item.get("status") == "open")
    blocked_gap_count = sum(1 for item in register if item.get("status") == "blocked")
    skipped_gap_count = sum(1 for item in register if item.get("status") == "skipped")

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.2.0-planning",
        "phase": "v4.2_phase_22.3",
        "status": status,
        "mode": "fake_offline_default",
        "read_only": True,
        "real_llm_executed": False,
        "external_mcp_connected": False,
        "external_system_connected": False,
        "database_connected": False,
        "redis_connected": False,
        "business_system_connected": False,
        "deployment_executed": False,
        "release_created": False,
        "tag_created": False,
        "auto_approved": False,
        "auto_closed": False,
        "acceptance_index_source": {
            "path": source.get("path", ""),
            "provided": source.get("provided", False),
            "exists": source.get("exists", False),
            "loaded": source.get("loaded", False),
            "status": source.get("status", "skipped"),
            "secret_detected": source.get("secret_detected", False),
        },
        "gap_register": register,
        "gap_count": len(register),
        "open_gap_count": open_gap_count,
        "blocked_gap_count": blocked_gap_count,
        "skipped_gap_count": skipped_gap_count,
        "missing_conditions": missing_conditions,
        "warnings": warnings,
        "go_no_go": {
            "recommendation": "No-Go" if status == "blocked" else "Manual-Review",
            "production_direct_launch": "No-Go",
            "auto_changed": False,
            "reason": "生产验收缺口登记册只生成待人工跟踪项，不自动批准上线或关闭缺口。",
        },
        "boundary_declarations": BOUNDARY_DECLARATIONS,
    }

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_production_acceptance_gap_register"
    json_path = output_root / f"{stem}.json"
    markdown_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")

    return {
        "status": status,
        "generated_at": generated_at,
        "commit": commit,
        "mode": "fake_offline_default",
        "read_only": True,
        "real_llm_executed": False,
        "external_mcp_connected": False,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "output_dir": str(output_root),
        "gap_count": len(register),
        "open_gap_count": open_gap_count,
        "missing_conditions": missing_conditions,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 v4.2 生产验收缺口只读登记册（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--acceptance-index", default=None)
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    summary = build_production_acceptance_gap_register(
        output_dir=args.output_dir,
        acceptance_index=args.acceptance_index,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
